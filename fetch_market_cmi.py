#!/usr/bin/env python3
"""Read the October 2026 MSS pages, which are CST Market Intelligence pages.

Casey, 18 Oct 2026: "Use the latest market updates for seller portals moving
forward."

The MSS was converted to the CST Market Intelligence band and dashboard, so
the selectors fetch_market.py pins -- h2.headline, p.subhead, div.keystats --
are gone from those pages and it reads every market as NOT FOUND. This reads
the new shape and writes the same market_cache.json entries, so the portals,
the Roadmap and the Pricing Strategy Summary are unchanged downstream.

    python3 fetch_market_cmi.py --dir <mss folder> --all
    python3 fetch_market_cmi.py --dir <mss folder> Oakton_Luxury_Market_Snapshot
    python3 fetch_market_cmi.py --dir <mss folder> --show <slug>   # print only

What it takes off each page:

    .cmi-t / .cmi-n / .cmi-d / .cmi-verdict   the five gauge cards
    h1                                        who controls the market
    "Market Update: ..."                      the read, in the team's words
    .cmi-gscore                               strength and momentum scores

The five cards now include Success Rate, which the September pages did not
carry. It is stored, and the four the dashboard draws -- % under contract,
average days on market, the 30-day and the 14-day -- are unchanged.

NOTHING IS INVENTED. A card the page does not carry is left out of the entry
rather than filled with a figure from somewhere else, and the run says which
markets came up short.
"""
import html as htmllib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "market_cache.json"

# The card title on the page -> the key the builders read it by.
CARDS = {
    "success rate": "success_rate",
    "total homes under contract": "under_contract",
    "average days on market": "avg_dom",
    "under contract (last 30 days)": "uc_30",
    "14-day absorption rate": "uc_14",
}
# The dashboard's cards, in the order the MSS draws them. Success rate opens
# Market Strength on the October 12 pages.
FOUR = [("success_rate", "Success rate"),
        ("under_contract", "Under contract"),
        ("avg_dom", "Days on market, active and pending"),
        ("uc_30", "Under contract on homes listed 30 days"),
        ("uc_14", "Of all listings, under contract in 14 days")]
# A page without one of these is not cached; success rate is newer, so a
# market that predates it is still complete.
REQUIRED = ["under_contract", "avg_dom", "uc_30", "uc_14"]
FLAG = {"red": ("red", "#D42A21"), "yel": ("yellow", "#F2C117"),
        "grn": ("green", "#2E9B52")}


def txt(x):
    return re.sub(r"\s+", " ",
                  htmllib.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()


def parse(page, slug):
    cards, missing = {}, []
    for m in re.finditer(r'<span class="cmi-t">(.*?)</span>', page):
        name = txt(m.group(1)).lower()
        key = next((v for k, v in CARDS.items() if name.startswith(k)), None)
        if not key:
            continue
        tail = page[m.end():m.end() + 1200]
        n = re.search(r'class="cmi-n">(.*?)</div>', tail, re.S)
        d = re.search(r'class="cmi-d">(.*?)</div>', tail, re.S)
        v = re.search(r'class="cmi-verdict ([a-z]+)">(.*?)</div>', tail, re.S)
        if not n:
            continue
        cards[key] = {"value": txt(n.group(1)),
                      "detail": txt(d.group(1)) if d else None,
                      "verdict": txt(v.group(2)) if v else None,
                      "band": v.group(1) if v else None}

    for key in REQUIRED:
        if key not in cards:
            missing.append(key)

    # The band's headline -- "Buyers Control the Oakton Luxury Market" -- is
    # h2.lms-head on these pages. Earlier MSS builds used h2.headline, so both
    # are tried before giving up.
    hm = (re.search(r'<h2 class="lms-head">(.*?)</h2>', page, re.S)
          or re.search(r'<h2 class="headline">(.*?)</h2>', page, re.S)
          or re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S))
    headline = txt(hm.group(1)) if hm else None
    read = re.search(r"Market Update:\s*(.*?)(?:</p>|</div>)", page, re.S)
    update = txt(read.group(1)) if read else None
    # The pages set this line in capitals -- "AS OF OCTOBER 12, 2026" -- so
    # the match is case-insensitive and the month is title-cased back for the
    # documents, which print it as written.
    asof = re.search(r"(?:AS OF|WEEK OF)\s+([A-Z]+ \d{1,2}, \d{4})",
                     txt(page), re.I)
    week_of = None
    if asof:
        mon, rest = asof.group(1).split(" ", 1)
        week_of = f"As of {mon.capitalize()} {rest}"
    scores = [txt(x) for x in re.findall(r'class="cmi-gscore">(.*?)</span>',
                                         page, re.S)]

    # Control and the flag come off the band's own capsule -- "NEUTRAL MARKET
    # -- YELLOW FLAG" -- which is the page's overall reading. Taking control
    # from a single card's verdict instead had Vienna Family stored as a
    # Buyer's market off the under-contract card while the page's own headline
    # read "Neither Side Controls the Vienna Family Market". A seller document
    # must never contradict the market report it cites.
    uc = cards.get("under_contract", {})
    cap = re.search(r'<div class="lms-cap ([a-z]+)">(.*?)</div>\s*</div>',
                    page, re.S)
    control, colour, hexv, flags = None, None, None, 0
    if cap:
        colour = cap.group(1)
        hexv = {"red": "#D42A21", "yellow": "#F2C117",
                "green": "#2E9B52"}.get(colour)
        words = txt(cap.group(2)).replace("’", "'").upper()
        for name in ("BUYER'S", "SELLER'S", "NEUTRAL"):
            if name in words:
                control = name.capitalize() if name == "NEUTRAL" else \
                    name[0] + name[1:].lower()
                break
        flags = 2 if "DOUBLE" in words else (1 if "FLAG" in words else 0)
        cap_text = txt(cap.group(2))
    else:
        cap_text = None
    if not control:
        missing.append("control (no band capsule on the page)")
    # The band's own strings, kept verbatim so a page built from this cache
    # reads exactly as the MSS reads. The read is the italic line; the meta
    # is "VIENNA - LUXURY HOMES - AS OF OCTOBER 12, 2026".
    rd = re.search(r'class="lms-read"[^>]*>(.*?)</p>', page, re.S)
    mt = re.search(r'class="lms-meta"[^>]*>(.*?)</p>', page, re.S)
    read_line = txt(rd.group(1)) if rd else None
    meta_line = txt(mt.group(1)) if mt else None

    stats = {"market": slug.split("_")[0]}
    for key in ("uc_30", "under_contract", "avg_dom", "uc_14", "success_rate"):
        if key in cards:
            stats[key] = cards[key]["value"]
    if control:
        stats["control"] = control

    entry = {
        "stats": stats,
        "conditions": {
            "flags": flags,
            "flag_color": colour,
            "flag_hex": hexv,
            "headline": headline,
            "headline_figure": uc.get("value"),
            "sub": update,
            "stats": [[cards[k]["value"], lbl] for k, lbl in FOUR
                      if k in cards],
            "capsule": cap_text,
            "read": read_line,
            "meta": meta_line,
            "update": update,
            "strength": scores[0] if scores else None,
            "momentum": scores[1] if len(scores) > 1 else None,
        },
        "absorption": None,
        "headline": headline,
        "subheadline": update,
        "keystats": f"{control} Market" if control else None,
        "week_of": week_of,
    }
    return entry, missing, cards


def slugs_in_use():
    out = set()
    for f in sorted((HERE / "properties").glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            mk = json.loads(f.read_text()).get("market") or {}
        except (json.JSONDecodeError, OSError):
            continue
        if mk.get("slug"):
            out.add(mk["slug"])
    return sorted(out)


def main(argv):
    show = "--show" in argv
    folder = None
    if "--dir" in argv:
        i = argv.index("--dir")
        folder = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not folder:
        sys.exit("--dir <mss folder> is required; these pages are read "
                 "locally, not fetched.")
    names = [a for a in argv if not a.startswith("--")]
    if "--all" in argv:
        names = slugs_in_use()
    if not names:
        sys.exit(__doc__)

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    wrote, skipped = 0, []
    for slug in names:
        f = folder / f"{slug}.html"
        if not f.exists():
            skipped.append((slug, "no page in this MSS build"))
            print(f"  ! {slug}: not in {folder.name}")
            continue
        entry, missing, cards = parse(f.read_text(encoding="utf-8"), slug)
        if missing:
            skipped.append((slug, "missing " + ", ".join(missing)))
            print(f"  ! {slug}: no {', '.join(missing)} on the page — "
                  "left as it was rather than part-filled")
            continue
        was = (cache.get(slug) or {}).get("week_of") or "not cached"
        print(f"  {slug}   [{was}  ->  {entry['week_of']}]")
        for k, lbl in FOUR:
            old = ((cache.get(slug) or {}).get("stats") or {}).get(k)
            new = entry["stats"].get(k)
            mark = "  <-- changed" if old != new else ""
            print(f"      {lbl:42} {str(old):>6}  ->  {str(new):>6}{mark}")
        if "success_rate" in entry["stats"]:
            print(f"      {'Success rate (new on the Oct 18 pages)':42} "
                  f"{'':>6}  ->  {entry['stats']['success_rate']:>6}")
        print(f"      control: {entry['keystats']}")
        wrote += 1
        if not show:
            cache[slug] = entry
        print()

    if not show:
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False),
                         encoding="utf-8")
    print(f"{'Would cache' if show else 'Cached'} {wrote} of {len(names)}.")
    if skipped:
        print("\nLeft alone (still carrying their previous figures):")
        for slug, why in skipped:
            print(f"  {slug}  —  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
