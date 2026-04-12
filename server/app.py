import os
import re
from io import BytesIO
from urllib.parse import urljoin

import flask
import requests
import segno
from bs4 import BeautifulSoup  # type: ignore
from dotenv import load_dotenv

load_dotenv()

app = flask.Flask(__name__)
WIKI_BASE_URL = os.environ["WIKI_BASE_URL"]
PAGE_URL = urljoin(WIKI_BASE_URL, "Nb.wtf")
USER_AGENT = "nb-wtf/2.0 <audiodude@gmail.com>"

RE_SELF_LINK = re.compile(r"^https?://nb.wtf")


def _qr_code(link, mimetype="image/png", scale=8):
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


@app.route("/")
def index():
    return flask.redirect(urljoin(WIKI_BASE_URL, "Nb.wtf"))


def _parse_wiki():
    resp = requests.get(PAGE_URL, headers={"User-Agent": USER_AGENT})
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        flask.abort(resp.status_code, f"Failed to fetch nb.wtf page:\n\n{e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    mapping = {}
    table = soup.find("table", {"class": "wikitable"})
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if not cols:
            continue
        slug, url = cols[0].text, cols[1].text
        mapping[slug] = url
    return mapping


@app.route("/<slug>")
def redirect(slug):
    print("got request for:", slug)
    mapping = _parse_wiki()
    final_link = mapping.get(slug)
    if not final_link:
        flask.abort(404)

    if not final_link.startswith("http"):
        final_link = WIKI_BASE_URL + final_link

    if RE_SELF_LINK.search(final_link):
        flask.abort(400, "Self-referential links are not allowed")

    if "qr" in flask.request.args:
        print("generating QR code")
        mimetype = "image/png"
        if flask.request.args["qr"] == "svg":
            mimetype = "image/svg+xml"
        scale = int(flask.request.args.get("s", 8))
        return flask.send_file(
            _qr_code(final_link, mimetype=mimetype, scale=scale), mimetype=mimetype
        )

    print("redirecting to", final_link)
    return flask.redirect(final_link)


@app.route("/w/<path:slug>")
def wiki_redirect(slug):
    colon_escaped = slug.replace(":", "%3A")
    final_link = urljoin(WIKI_BASE_URL, colon_escaped)
    return flask.redirect(final_link)
