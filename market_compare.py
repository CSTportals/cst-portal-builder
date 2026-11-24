"""The "Rest of <Market>" row under the team's track record.

Rebuilt 19 Nov 2026 after the workspace reset. Casey, Nov 2026: the CST stats
on the portal are compared to the property's OWN MSS market (e.g. Lupine Den
-> Vienna Luxury), labeled "Rest of [Market]" over the last 90 days, on the
same measures as the team row: success rate, avg DOM, % of list, % sold in the
first 10 days, % sold above list.

The figures are read from the published MSS page for the market (saved copies
in mss_pages/, refreshed with each MSS package). A property's own
"market_local" block wins.
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
PAGES = HERE / "mss_pages"


def read_row(slug):
    import townhome_mss as _th
    f = _th.mss_page(slug)
    if not f or not f.exists():
        return None
    s = f.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'<div class="cstf-row mkt"><div class="cstf-c lab">(.*?)</div>(.*?)</div></div>', s, re.S)
    if not m:
        return None
    cells = re.findall(r'<span class="n">([^<]+)</span><span class="l">([^<]+)</span>', m.group(2))
    return {"label": re.sub(r"<[^>]+>", "", m.group(1)).strip(), "cells": [list(c) for c in cells]}


def build(p, note=print):
    if p.get("market_local"):
        return
    slug = (p.get("market") or {}).get("slug")
    if not slug:
        return
    row = read_row(slug)
    if not row or len(row["cells"]) != 5:
        note(f"Track record market row: no saved MSS page for {slug} -- copy the "
             "latest MSS package's pages into mss_pages/.")
        return
    p["market_local"] = row
    note(f"Track record market row: {row['label']} -- "
         + ", ".join(f"{n} {l}" for n, l in row["cells"]) + " (MSS page).")
