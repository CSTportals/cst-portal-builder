#!/usr/bin/env python3
"""
fetch_market.py — read the headline, sub-headline and key stats off MSS market
reports so portal emails never carry retyped or stale figures.

Two sources, local first:

    python3 fetch_market.py --dir ~/mss/webmss_final --all
    python3 fetch_market.py --dir ~/mss/webmss_final Centreville_Family_Market_Snapshot
    python3 fetch_market.py --all                    # falls back to the live site
    python3 fetch_market.py --show <slug>            # print, save nothing

Reading the local MSS build folder is the better habit: it is the same content
that will deploy, it works before the site goes live, and it cannot be blocked.

Results cache to market_cache.json keyed by slug, with the "Week of" date taken
from the page itself, so a build can say exactly how current its figures are.
build_portal.py reads that cache automatically.

Run this after each Thursday MSS rebuild, before rebuilding portals.

Selectors are pinned to the real page structure:
    <h2 class="headline">      the headline
    <p class="subhead">        the sub-headline
    <div class="keystats">     .keystat blocks of .num + .lbl
    <div class="zone-strip">   .zone-num and .zone-pill
    <span class="weekof">      the week the report covers
"""

import html as htmllib
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "market_cache.json"
BASE = "https://cstmarketupdate.netlify.app"


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()


def grab(pattern, source):
    m = re.search(pattern, source, re.S)
    return text_of(m.group(1)) if m else None


def parse(page):
    headline = grab(r'<h2 class="headline">(.*?)</h2>', page)
    subhead = grab(r'<p class="subhead">(.*?)</p>', page)
    weekof = grab(r'<span class="weekof">(.*?)</span>', page)

    # Three things only: which way contracts are moving, the share of the
    # market under contract, and who that leaves in control.
    ks = {}
    start = page.find('<div class="keystats">')
    if start != -1:
        end = page.find('<div class="zone-strip">', start)
        block = page[start:end if end != -1 else start + 4000]
        for num, lbl in re.findall(
                r'<div class="num">(.*?)</div>\s*<div class="lbl">(.*?)</div>',
                block, re.S):
            ks[text_of(lbl).lower()] = text_of(num)

    # Control sits in the chart card: <span class="v">44% (Neutral)</span>
    control = None
    m = re.search(r'<span>%UC</span>\s*<span class="v">[^(]*\(([^)]+)\)', page, re.S)
    if m:
        control = text_of(m.group(1))

    parts = []
    contracts = ks.get("30 day sales")
    if contracts:
        n = contracts.replace("%", "").replace(",", "").strip()
        try:
            v = float(n)
            direction = "down" if v < 0 else "up"
            parts.append(f"Contracts {direction} {abs(v):g}%")
        except ValueError:
            parts.append(f"Contracts {contracts}")

    uc = ks.get("%uc")
    if uc:
        parts.append(f"{uc} Under Contract")

    if control:
        word = control.strip()
        parts.append(word if word.lower().endswith("market") else f"{word} Market")

    zone_num = grab(r'<div class="zone-num">(.*?)</div>', page)
    zone_pill = grab(r'<span class="zone-pill[^"]*">(.*?)</span>', page)

    # The chart card carries everything the Roadmap's market table needs.
    chart = {}
    ci = page.find('<div class="chart-card">')
    if ci != -1:
        for lbl, val in re.findall(
                r'<div class="row"><span>(.*?)</span><span class="v">(.*?)</span>',
                page[ci:ci + 2000], re.S):
            chart[text_of(lbl).lower()] = text_of(val)

    uc_raw = chart.get("%uc", "")
    stats = None
    if chart:
        stats = {
            "market": (headline or "").split()[0] if headline else None,
            "inventory": chart.get("30 day inv"),
            # "30 Day Sales" is a CHANGE against last year (-75%), not a
            # share. The share of listings that actually went under contract
            # in 30 days is its own keystat, and it is the figure the red-flag
            # logic means when it asks whether anything is selling.
            "contracts": chart.get("30 day sales"),
            "uc_30": ks.get("went under in 30 days"),
            "under_contract": uc_raw.split(" (")[0] or None,
            "uc_14": chart.get("14 day absorption rate"),
            "success_rate": (re.search(r"A\s+(\d+)%\s+success rate", page, re.I).group(1) + "%"
                             if re.search(r"A\s+(\d+)%\s+success rate", page, re.I) else None),
            "control": control,
        }

    absorption = None
    if zone_num:
        absorption = {"rate": zone_num, "zone": zone_pill,
                      "note": subhead}

    # ---- Current Market Conditions, the MSS flag block -------------------
    # Kept as its own structure because the Roadmap reproduces it verbatim:
    # the counts behind it ("6 of the 9", "the 3 needed to keep pace") exist
    # nowhere else, so they cannot be rebuilt from the percentages above.
    conditions = None
    hm = re.search(r'<h2 class="headline">(.*?)</h2>', page, re.S)
    if hm:
        raw = hm.group(1)
        flagset = re.search(r'<span class="flagset">(.*?)</span>', raw, re.S)
        n_flags, colour = 0, None
        if flagset:
            fills = re.findall(r'<path[^>]*fill="(#[0-9A-Fa-f]{6})"', flagset.group(1))
            n_flags = len(fills)
            if fills:
                # Green #1B9E4B vs anything redder; judged on the channels, not
                # a hard-coded hex, so a palette tweak upstream does not lie.
                r, g = int(fills[0][1:3], 16), int(fills[0][3:5], 16)
                colour = "green" if g > r else "red"
        head_html = re.sub(r'<span class="city-flag">.*?</span></span></span>', '',
                           raw, flags=re.S)
        figure = None
        fm = re.search(r'<span class="num">(.*?)</span>', head_html, re.S)
        if fm:
            figure = text_of(fm.group(1))
        head_txt = text_of(head_html)

        ks_pairs = []
        kstart = page.find('<div class="keystats">')
        if kstart != -1:
            kend = page.find('</div>\n    </div>', kstart)
            blk = page[kstart:kend if kend != -1 else kstart + 2500]
            for num, lbl in re.findall(
                    r'<div class="num">(.*?)</div>\s*<div class="lbl">(.*?)</div>',
                    blk, re.S):
                ks_pairs.append([text_of(num), text_of(lbl)])

        narrative = grab(r'<p class="narrative">(.*?)</p>', page)
        if narrative:
            narrative = re.sub(r'^Market Update:\s*', '', narrative).strip()

        if head_txt and ks_pairs:
            conditions = {
                "flags": n_flags,
                "flag_color": colour,
                "headline": head_txt,
                "headline_figure": figure,
                "sub": subhead,
                "stats": ks_pairs,
                "update": narrative,
            }

    return {
        "stats": stats,
        "conditions": conditions,
        "absorption": absorption,
        "headline": headline,
        "subheadline": subhead,
        "keystats": " &middot; ".join(parts) if parts else None,
        "week_of": weekof,
    }


def load(slug, folder):
    if folder:
        f = Path(folder).expanduser() / f"{slug}.html"
        if not f.exists():
            print(f"  {slug}: NOT FOUND in {folder}")
            return None
        return f.read_text(errors="replace")
    try:
        with urllib.request.urlopen(f"{BASE}/{slug}.html", timeout=20) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  {slug}: FETCH FAILED — {e}")
        return None


def main():
    argv = sys.argv[1:]
    show = "--show" in argv
    do_all = "--all" in argv
    folder = None
    if "--dir" in argv:
        i = argv.index("--dir")
        folder = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    slugs = [a for a in argv if not a.startswith("--")]

    if do_all:
        # Skip properties with no market page, such as Lake Anna.
        # Only real property files: anything underscore-prefixed is a parked
        # fragment, and a file with no "market" block has no page to read.
        found = set()
        for f in sorted((HERE / "properties").glob("*.json")):
            if f.name.startswith("_"):
                continue
            try:
                mk = json.loads(f.read_text()).get("market") or {}
            except (json.JSONDecodeError, OSError) as e:
                print(f"  ! {f.name} unreadable ({e}) — skipped")
                continue
            if mk.get("slug"):
                found.add(mk["slug"])
        slugs = sorted(found)
    if not slugs:
        sys.exit(__doc__)

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    print(f"Reading {len(slugs)} market report(s) from {folder or BASE}\n")

    got = 0
    for slug in slugs:
        page = load(slug, folder)
        if not page:
            print()
            continue
        d = parse(page)
        print(f"  {slug}   [{d['week_of'] or 'week unknown'}]")
        for k in ("headline", "subheadline", "keystats"):
            print(f"    {k:12} {d[k] or 'NOT FOUND'}")
        print()
        if not show and any(d[k] for k in ("headline", "subheadline", "keystats")):
            cache[slug] = d
            got += 1

    if show:
        print("--show: nothing written")
    else:
        CACHE.write_text(json.dumps(cache, indent=2))
        print(f"Cached {got} of {len(slugs)} into {CACHE.name}")


if __name__ == "__main__":
    main()
