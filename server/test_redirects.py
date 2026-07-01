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


def test_shortcode_is_currently_case_sensitive(client, seed):
    """Documents today's exact-case lookup. The qr-all branch makes this
    COLLATE NOCASE, at which point this row flips to a 302."""
    seed(SEED)
    assert client.get("/NOISETABLE").status_code == 404


# --- QR generation --------------------------------------------------------
# Today the QR encodes the *destination* URL. The qr-all branch changes this
# to the nb.wtf short link; these byte-for-byte expectations will change then.

def test_qr_png_encodes_destination(client, seed):
    seed(SEED)
    resp = client.get("/NoiseTable?qr")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data == png_bytes("https://www.noisebridge.net/wiki/NoiseTable")


def test_qr_svg(client, seed):
    seed(SEED)
    resp = client.get("/NoiseTable?qr=svg")
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
    assert resp.data == svg_bytes("https://www.noisebridge.net/wiki/NoiseTable")


def test_qr_scale(client, seed):
    seed(SEED)
    resp = client.get("/NoiseTable?qr&s=4")
    assert resp.status_code == 200
    assert resp.data == png_bytes(
        "https://www.noisebridge.net/wiki/NoiseTable", scale=4
    )


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
