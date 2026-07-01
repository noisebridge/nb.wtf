# Wiki page capitalization & nb.wtf short links

This note explains a gotcha inherent to MediaWiki that affects nb.wtf
`/w/` and `/u/` links (and QR codes), and the techniques for working
around it. It lives here in the repo and is mirrored on the Noisebridge
wiki (a guild / manual subpage).

## The gotcha: MediaWiki titles are case-sensitive after the first letter

By default MediaWiki auto-capitalizes only the **first letter** of a page
title (`$wgCapitalLinks` is on). Everything after that is
**case-sensitive**:

- `FooBar`, `Foobar`, and `FOOBAR` are three **different** pages.
- Subpages inherit this: `User:Mcint/ProjectX` ≠ `User:Mcint/projectx`.

So `nb.wtf/w/FOOBAR` redirects to `noisebridge.net/wiki/FOOBAR` — which is
**not** the same page as `FooBar`. nb.wtf passes the title through verbatim;
it does not (and cannot cheaply) know the "correct" capitalization.

References:
- MediaWiki `Manual:$wgCapitalLinks`:
  <https://www.mediawiki.org/wiki/Manual:$wgCapitalLinks>
- MediaWiki `Manual:Page_title`:
  <https://www.mediawiki.org/wiki/Manual:Page_title>

## Why nb.wtf doesn't auto-correct capitalization

nb.wtf is deliberately **stateless** for `/w/` and `/u/`: it transforms the
path and redirects, without fetching the wiki. It *could* in principle query
the wiki to discover a page's canonical title, but the wiki runs **Anubis**
(anti-bot), so automated lookups are unreliable. We therefore trust the slug
you copied from MediaWiki and never alter its case.

## Uppercasing & QR codes: when it auto-works

QR codes have a dense **alphanumeric** mode limited to `A–Z 0–9` and a few
symbols. An all-uppercase URL like `HTTPS://NB.WTF/W/FOOBAR` fits that mode,
producing a smaller, easier-to-scan code. So nb.wtf **case-mirrors**: if the
slug you give it is already all-uppercase, it uppercases the scheme/host/
prefix too (dense QR); otherwise it leaves everything lowercase (a QR that
matches exactly what you'd type). It never changes the slug itself.

| What you link | Auto-uppercases to dense QR? | Why |
|---|---|---|
| Shortcode `nb.wtf/SLUG` | **Yes, always** | nb.wtf owns the lookup; it is case-insensitive, so `/SLUG` resolves regardless of the stored case |
| Wiki `nb.wtf/w/PAGE` | Only if the page title itself is all-caps | MediaWiki resolves the title case-sensitively; we can't know the true case |
| User `nb.wtf/u/NAME` | Only if the username is all-caps | same as wiki titles |

**Bottom line:** shortcodes can always be uppercased for a nice QR. Wiki and
user links only get the dense uppercase QR when the underlying title really
is uppercase — otherwise use them as-is (they still work; the QR is just a
little denser in byte mode).

## Workarounds for wiki/user pages

1. **Create an ALL-CAPS redirect page on the wiki.** Make `FOOBAR` a
   `#REDIRECT [[FooBar]]`. Then `nb.wtf/w/FOOBAR` resolves (via the wiki
   redirect) *and* gets a dense uppercase QR. This is the reliable way to get
   a scannable QR for a mixed-case page.

2. **Avoid spaces in page titles; prefer CamelCase.** Spaces become `_` (or
   `%20`) in URLs and make links fragile to type and share. A single
   CamelCase token (`NoiseTable`, `HackerSpace`) is one clean path segment.

   This is the old wiki **WikiWord** convention: on Ward Cunningham's
   original wiki (c2, "WardsWiki", 1995) a run-together CamelCase word like
   `WikiWord` *was* the link syntax. MediaWiki dropped the requirement (you
   use `[[...]]`), but the habit remains a good one for short, unambiguous,
   QR-friendly titles.
   - c2 `WikiWord`: <https://wiki.c2.com/?WikiWord>
   - c2 `WikiCase`: <https://wiki.c2.com/?WikiCase>

## Summary

- Wiki titles are case-sensitive after the first letter — `FOOBAR` ≠ `FooBar`.
- nb.wtf trusts the slug you give it and never changes its case.
- Shortcodes are case-insensitive and always uppercase-able for dense QRs.
- For a scannable QR of a mixed-case wiki page, add an ALL-CAPS redirect page.
- Prefer CamelCase, space-free titles (the WikiWord habit) for clean links.
