# QR on all routes, `/u/` user links, and case-mirrored uppercasing

**Status:** design approved, implementing
**Date:** 2026-07-01
**Related:** issue #15 (`/u/` user links), issue #1 (`/w/`, closed), issue #2 (`?qr`, closed)

## Goal

Make QR generation available on every nb.wtf redirect route, add a `/u/`
user-page shortcut, and make the QR encode a compact, no-surprise
**nb.wtf** short link — using QR's dense alphanumeric mode when (and only
when) it is safe to do so.

## Decomposition — three tightly-scoped, stacked PRs

```
main
 └─ PR 1: tests      foundation — tabular redirect tests for today's behavior
     ├─ PR 2: qr-all  QR on all routes + link-into-nb.wtf + case-mirrored uppercasing + capitalization docs
     └─ PR 3: u-links /u/<User> (incl. sub / sub-sub pages) -> /w/User:<User>/...
```

PR 2 and PR 3 are **siblings**, both branched off PR 1. Each merges
independently once PR 1 lands. PR 1 is the base because both feature PRs
extend the same tabular test pattern.

### Deferred (noted here, not built now)

- Usage stats (public vs private undecided; likely public first).
- Other `?`-codes, especially a meta/status endpoint reporting state
  derived from the most recent scrape (stays "stateless" — state is just
  the last scrape).
- Browser-extension feature: embed a page's `/w/` shortlink + a QR button
  directly on wiki pages.
- Generalizing the shortener to other sites with their own shorteners.

## Cross-cutting decisions (shape PR 2 and PR 3)

### 1. QR encodes the nb.wtf short link, not the destination

`nb.wtf/w/FooBar?qr` produces a QR for `nb.wtf/w/FooBar` **itself**
("link into nb.wtf"). This is an intentional **behavior change** from
today, where `/<slug>?qr` encodes the destination wiki URL.

Rationale: the whole point is to popularize the short service and keep
the printed/scanned link pointing at nb.wtf (which can evolve routing,
add stats, etc.) rather than baking in a destination.

### 2. Stateless, case-mirroring, no-surprise uppercasing

We have **Anubis** on the wiki (anti-bot), so the server cannot reliably
fetch a page to discover its canonical capitalization. We therefore do
**not** parse the wiki and do **not** guess case. We trust the slug the
user copied from MediaWiki and **never alter the slug's case**.

The only thing we vary is the **front part** (scheme + `nb.wtf` +
route-prefix), keyed on whether the slug is already all-uppercase:

```
slug_is_upper = (slug == slug.upper())      # i.e. slug has no lowercase letters
if slug_is_upper:
    front = "HTTPS://NB.WTF" + PREFIX.upper()   # e.g. HTTPS://NB.WTF/W/
else:
    front = "https://nb.wtf" + PREFIX.lower()   # e.g. https://nb.wtf/w/
qr_target = front + slug                         # slug is passed through unchanged
```

Applies identically to all three slug kinds: bare shortcode (no prefix),
`/w/` wiki, `/u/` user.

Why this shape:

- `HTTPS://NB.WTF/W/FOOBAR` is **entirely** within QR's alphanumeric
  charset (`0-9 A-Z space $ % * + - . / :`), so an all-caps slug yields a
  markedly denser, easier-to-scan QR.
- A single lowercase character forces byte mode anyway, so for mixed-case
  slugs there is no benefit to uppercasing the front — and doing so would
  surprise users with a URL that does not match what they typed. So we
  don't.
- The scheme/domain are case-insensitive (DNS + URL spec), so an
  uppercase front always resolves.

### 3. Routes must accept the uppercase prefix

Flask routes are case-sensitive by default. Because an all-caps QR link
reads `.../W/...` or `.../U/...`, the server must serve **both**
`/w/` and `/W/` (and `/u/` and `/U/`). Bare shortcodes already match any
case via `/<slug>`; their resolution is unchanged (exact-case DB lookup).

Implementation options (decide in PR 2/3 plan): register both-cased
routes, or a single route with a case-insensitive prefix converter.

### 4. When uppercase auto-works (this becomes the docs)

| URL part | Uppercased? | Why safe |
|---|---|---|
| scheme + `NB.WTF` + `/W/` `/U/` prefix | when slug is all-caps | case-insensitive (DNS/URL); server serves both prefix cases |
| slug / page title / username | **never changed** | MediaWiki is case-sensitive after char 1; we can't know true case |

So a dense uppercase QR happens exactly when the slug itself is all-caps.
For a wiki page that is *not* all-caps, the documented workaround is to
create an **ALL-CAPS redirect page** on the wiki (`FOOBAR` -> `FooBar`);
then `/w/FOOBAR?qr` is both dense and resolves through the wiki redirect.

## PR 1 — tests (built first)

- Add **pytest** and a Flask test-client fixture. Seed an in-memory /
  temp sqlite DB directly (no network).
- **Tabular parametrized** redirect tests — the succinct format requested:
  ```python
  @pytest.mark.parametrize("path, status, location", [
      ("/",                 302, "https://www.noisebridge.net/wiki/Nb.wtf"),
      ("/w/FooBar",         302, "https://www.noisebridge.net/wiki/FooBar"),
      ("/w/User:Audiodude", 302, ".../wiki/User%3AAudiodude"),
      ("/NoiseTable",       302, "<seeded destination>"),   # from seeded DB
  ])
  ```
- One small test for the scrape / `on_update` parser using a fixture HTML
  snippet (mocked; no live wiki).
- Tooling: keep the existing **Pipfile**, add pytest. (Migrating to
  `uv`/`pyproject.toml` is possible but out of scope for this branch to
  respect least-surprise in an existing repo.)
- `app.py` reads `WIKI_BASE_URL` at import time; the test fixture sets env
  before import (via `conftest.py`). A minimal lazy-config refactor is
  acceptable if it makes tests cleaner.

## PR 2 — qr-all (atop PR 1)

- Extract a single `qr_target(...)` helper implementing decisions 1 and 2.
- Extend `/w/` and (bare) `/<slug>` to honor `?qr`, `?qr=svg`, `?s=<n>`,
  encoding the **nb.wtf short link** per decision 1.
- Add uppercase-prefix route acceptance (decision 3) so all-caps QR links
  resolve.
- **Behavior-change** test: `/<slug>?qr` now encodes the short link, not
  the destination. Update/add tabular cases (decode the QR and assert the
  encoded string, incl. the uppercase-front cases).
- **Docs deliverable** (coupled here): a succinct in-repo note
  (`docs/capitalization.md` or similar) covering decision 4 — the
  MediaWiki case-sensitivity gotcha, when auto-uppercase works, and the
  ALL-CAPS-redirect-page workaround. Same content is destined for a wiki
  guild subpage (links to the MW manual on case sensitivity; the
  CamelCase / WikiWord lineage from Ward's c2 wiki onward as a
  no-spaces-in-titles technique).

## PR 3 — u-links (atop PR 1)

- Add `/u/<path:name>` -> `/w/User:<name>` (i.e. `noisebridge.net/wiki/
  User:<name>`), preserving **sub-pages and sub-sub-pages**
  (`/u/mcint/foo/bar` -> `User:Mcint/foo/bar`). Path converter captures
  slashes.
- MediaWiki auto-capitalizes the first letter of a username; confirm
  whether the server should capitalize `name[0]` or leave it to MW. Decide
  in the plan; default to leaving it to MW (least code), with tests
  documenting the resulting redirect.
- QR support via the same `qr_target` helper (encodes `/u/...` short form).
- Tabular tests for user pages incl. sub / sub-sub pages.

## Testing strategy (whole initiative)

- Every route change ships with tabular cases: `(path, status, location)`
  and, for QR, `(path, decoded-qr-string, mimetype)`.
- QR assertions decode the generated image (or assert the encoded payload)
  so uppercase-front behavior is verified, not just mimetype.
- No live network in tests: DB seeded directly; scrape tested against a
  fixture HTML snippet.

## Risks / notes

- Case-mirroring means a user only gets a dense uppercase QR when the real
  slug is all-caps — by design; we never invent case.
- Serving both `/w/` and `/W/` slightly widens the route surface; keep the
  handler shared so behavior can't drift between cases.
- `/<slug>?qr` behavior change is user-visible; call it out in the PR
  description and the docs.
