from dotenv import load_dotenv

load_dotenv()

import os
import re
import sqlite3
from io import BytesIO
from urllib.parse import urljoin

import flask
import requests
import segno
from bs4 import BeautifulSoup

app = flask.Flask(__name__)
SQLITE_PATH = os.environ.get("SQLITE_PATH", "nbwtf.db")
WIKI_BASE_URL = os.environ["WIKI_BASE_URL"]
USER_AGENT = "nb-wtf/1.0 <audiodude@gmail.com>"

RE_SELF_LINK = re.compile(r"^https?://nb.wtf")

# Canonical short host the QR codes point back into.
SHORT_HOST = "nb.wtf"


def get_db():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS links (slug TEXT PRIMARY KEY, url TEXT NOT NULL)"
    )
    return conn


def update_db(mapping):
    with get_db() as conn:
        conn.execute("DELETE FROM links")
        conn.executemany(
            "INSERT INTO links (slug, url) VALUES (?, ?)",
            list(mapping.items()),
        )


def qr_code(link, mimetype="image/png", scale=8):
    qrcode = segno.make(link)
    out = BytesIO()
    if mimetype == "image/svg+xml":
        qrcode.save(out, kind="svg", scale=scale)
    elif mimetype == "image/png":
        qrcode.save(out, kind="png", scale=scale)
    else:
        raise ValueError("Invalid mimetype")
    out.seek(0)
    return out


def qr_target(prefix, slug):
    """The nb.wtf short link to encode in the QR, case-mirrored.

    We never alter the slug's case (we can't know a wiki page's true case
    without parsing, and Anubis blocks that). We only vary the front part
    (scheme + host + prefix): if the slug has no lowercase letters, the whole
    URL is uppercased so it fits QR's dense alphanumeric mode; otherwise it
    stays lowercase so it matches exactly what the user typed. `prefix` is
    "" for a bare shortcode, "w/" for wiki, "u/" for user pages.
    """
    path = prefix + slug
    if slug == slug.upper():  # slug has no lowercase letters
        return f"HTTPS://{SHORT_HOST.upper()}/{path.upper()}"
    return f"https://{SHORT_HOST}/{path}"


def maybe_qr(target):
    """If the request asked for a QR (?qr, ?qr=svg, ?s=<scale>), return the
    image response for `target`; otherwise None so the caller redirects."""
    if "qr" not in flask.request.args:
        return None
    mimetype = "image/png"
    if flask.request.args["qr"] == "svg":
        mimetype = "image/svg+xml"
    scale = int(flask.request.args.get("s", 8))
    return flask.send_file(
        qr_code(target, mimetype=mimetype, scale=scale), mimetype=mimetype
    )


@app.route("/")
def index():
    return flask.redirect("https://www.noisebridge.net/wiki/Nb.wtf")


@app.route("/api/v1/on_update")
def update():
    print("on_update")

    PAGE_URL = urljoin(WIKI_BASE_URL, "Nb.wtf")
    resp = requests.get(PAGE_URL, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    mapping = {}
    table = soup.find("table", {"class": "wikitable"})
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if not cols:
            continue
        slug, url = cols[0].text.strip(), cols[1].text.strip()
        mapping[slug] = url

    update_db(mapping)

    return "Updated!"


@app.route("/w/<path:slug>")
@app.route("/W/<path:slug>")
def wiki_redirect(slug):
    colon_escaped = slug.replace(":", "%3A")
    final_link = urljoin(WIKI_BASE_URL, colon_escaped)

    qr = maybe_qr(qr_target("w/", slug))
    if qr is not None:
        return qr

    return flask.redirect(final_link)


@app.route("/u/<path:name>")
@app.route("/U/<path:name>")
def user_redirect(name):
    # /u/audiodude -> wiki User:audiodude (incl. sub / sub-sub pages). We
    # leave the first-letter capitalization to MediaWiki. Colons are escaped
    # so urljoin doesn't mistake "User:" for a URL scheme.
    title = "User:" + name
    colon_escaped = title.replace(":", "%3A")
    final_link = urljoin(WIKI_BASE_URL, colon_escaped)

    qr = maybe_qr(qr_target("u/", name))
    if qr is not None:
        return qr

    return flask.redirect(final_link)


@app.route("/<slug>")
def redirect(slug):
    with get_db() as conn:
        row = conn.execute(
            "SELECT url FROM links WHERE slug = ? COLLATE NOCASE", (slug,)
        ).fetchone()
    if not row:
        flask.abort(404)

    final_link = row["url"]
    if not final_link.startswith("http"):
        final_link = WIKI_BASE_URL + final_link

    if RE_SELF_LINK.search(final_link):
        flask.abort(400, "Self-referential links are not allowed")

    qr = maybe_qr(qr_target("", slug))
    if qr is not None:
        return qr

    print("redirecting to", final_link)
    return flask.redirect(final_link)
