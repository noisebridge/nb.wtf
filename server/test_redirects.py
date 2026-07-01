"""Tabular tests characterizing today's redirect + QR behavior.

The table format is the point: each row says "this path redirects there with
this status." Later branches (qr-all, u-links) extend the same tables. These
tests pin *current* behavior, so an intended change (e.g. QR encoding the
short link instead of the destination, or case-insensitive shortcodes) shows
up as a legible diff to a row here.
"""

from io import BytesIO

import pytest
import segno

from conftest import WIKI_BASE_URL

WIKI = WIKI_BASE_URL.rstrip("/")


def png_bytes(link, scale=8):
    buf = BytesIO()
    segno.make(link).save(buf, kind="png", scale=scale)
    return buf.getvalue()


def svg_bytes(link, scale=8):
    buf = BytesIO()
    segno.make(link).save(buf, kind="svg", scale=scale)
    return buf.getvalue()


# --- Static routes: no DB, no network -------------------------------------

# (path, status, Location)
STATIC_REDIRECTS = [
    ("/", 302, "https://www.noisebridge.net/wiki/Nb.wtf"),
    ("/w/FooBar", 302, f"{WIKI}/FooBar"),
    ("/w/User:Audiodude", 302, f"{WIKI}/User%3AAudiodude"),
    ("/w/Foo/Bar", 302, f"{WIKI}/Foo/Bar"),  # subpage
]


@pytest.mark.parametrize("path, status, location", STATIC_REDIRECTS)
def test_static_redirects(client, path, status, location):
    resp = client.get(path)
    assert resp.status_code == status
    assert resp.headers["Location"] == location


# /u/<name> -> wiki User:<name>, incl. sub / sub-sub pages and the /U/ prefix.
# First-letter capitalization is left to MediaWiki (we don't munge the name).
USER_REDIRECTS = [
    ("/u/audiodude", 302, f"{WIKI}/User%3Aaudiodude"),
    ("/u/mcint/foo", 302, f"{WIKI}/User%3Amcint/foo"),  # subpage
    ("/u/mcint/foo/bar", 302, f"{WIKI}/User%3Amcint/foo/bar"),  # sub-subpage
    ("/U/MCINT", 302, f"{WIKI}/User%3AMCINT"),  # uppercase prefix route
]


@pytest.mark.parametrize("path, status, location", USER_REDIRECTS)
def test_user_redirects(client, path, status, location):
    resp = client.get(path)
    assert resp.status_code == status
    assert resp.headers["Location"] == location


# --- Shortcode routes: DB-backed ------------------------------------------

SEED = {
    "NoiseTable": "https://www.noisebridge.net/wiki/NoiseTable",  # absolute
    "About": "About",  # relative -> concatenated onto WIKI_BASE_URL
    "loop": "https://nb.wtf/About",  # self-referential
}

# (slug, status, Location or None)
SHORTCODE_REDIRECTS = [
    ("NoiseTable", 302, "https://www.noisebridge.net/wiki/NoiseTable"),
    ("About", 302, f"{WIKI_BASE_URL}About"),  # note: plain concat, not urljoin
    ("loop", 400, None),  # self-referential links are rejected
    ("DoesNotExist", 404, None),
]


@pytest.mark.parametrize("slug, status, location", SHORTCODE_REDIRECTS)
def test_shortcode_redirects(client, seed, slug, status, location):
    seed(SEED)
    resp = client.get(f"/{slug}")
    assert resp.status_code == status
    if location is not None:
        assert resp.headers["Location"] == location


def test_shortcode_lookup_is_case_insensitive(client, seed):
    """Lookup is COLLATE NOCASE, so an all-caps shortcode still resolves to
    the same destination — you can always uppercase a slug for a dense QR."""
    seed(SEED)
    resp = client.get("/NOISETABLE")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://www.noisebridge.net/wiki/NoiseTable"


def test_uppercase_wiki_prefix_route(client):
    """An all-caps QR link reads /W/...; the server must serve it too."""
    resp = client.get("/W/FOOBAR")
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"{WIKI}/FOOBAR"


# --- qr_target: the case-mirroring core (encode the nb.wtf short link) -----

# (prefix, slug, expected encoded URL)
QR_TARGETS = [
    ("", "NoiseTable", "https://nb.wtf/NoiseTable"),
    ("", "NOISETABLE", "HTTPS://NB.WTF/NOISETABLE"),
    ("w/", "FooBar", "https://nb.wtf/w/FooBar"),
    ("w/", "FOOBAR", "HTTPS://NB.WTF/W/FOOBAR"),
    ("u/", "mcint", "https://nb.wtf/u/mcint"),
    ("u/", "MCINT", "HTTPS://NB.WTF/U/MCINT"),
]


@pytest.mark.parametrize("prefix, slug, expected", QR_TARGETS)
def test_qr_target(app_module, prefix, slug, expected):
    assert app_module.qr_target(prefix, slug) == expected


# --- QR generation: now encodes the nb.wtf short link, case-mirrored ------

# (path, expected encoded URL) — QR image must match segno output for the URL
QR_ENCODINGS = [
    ("/NoiseTable?qr", "https://nb.wtf/NoiseTable"),
    ("/NOISETABLE?qr", "HTTPS://NB.WTF/NOISETABLE"),  # dense, via COLLATE NOCASE
    ("/w/FooBar?qr", "https://nb.wtf/w/FooBar"),
    ("/W/FOOBAR?qr", "HTTPS://NB.WTF/W/FOOBAR"),
    ("/u/mcint?qr", "https://nb.wtf/u/mcint"),
    ("/U/MCINT?qr", "HTTPS://NB.WTF/U/MCINT"),
]


@pytest.mark.parametrize("path, encoded", QR_ENCODINGS)
def test_qr_png_encodes_short_link(client, seed, path, encoded):
    seed(SEED)
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data == png_bytes(encoded)


def test_qr_svg(client, seed):
    seed(SEED)
    resp = client.get("/NoiseTable?qr=svg")
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
    assert resp.data == svg_bytes("https://nb.wtf/NoiseTable")


def test_qr_scale(client, seed):
    seed(SEED)
    resp = client.get("/NoiseTable?qr&s=4")
    assert resp.status_code == 200
    assert resp.data == png_bytes("https://nb.wtf/NoiseTable", scale=4)


# --- Scrape / on_update parser (no live wiki) -----------------------------

FIXTURE_HTML = """
<html><body>
<table class="wikitable">
  <tr><th>Slug</th><th>URL</th></tr>
  <tr><td> NoiseTable </td><td> https://www.noisebridge.net/wiki/NoiseTable </td></tr>
  <tr><td>About</td><td>About</td></tr>
</table>
</body></html>
"""


def test_on_update_parses_table(client, app_module, monkeypatch):
    class FakeResp:
        text = FIXTURE_HTML

        def raise_for_status(self):
            pass

    monkeypatch.setattr(app_module.requests, "get", lambda *a, **k: FakeResp())

    resp = client.get("/api/v1/on_update")
    assert resp.status_code == 200

    with app_module.get_db() as conn:
        rows = {r["slug"]: r["url"] for r in conn.execute("SELECT slug, url FROM links")}

    assert rows == {
        "NoiseTable": "https://www.noisebridge.net/wiki/NoiseTable",
        "About": "About",
    }
