#!/usr/bin/env python3
"""
build_index_v2.py — a redesigned Seller Portal nav page.

The current nav page is a stack of seven near-identical link cards: the
seller reads a list of documents. The Buyer Portal reads like a magazine
because it puts something to LOOK at above the links — a tall hero, a
colour band of real numbers, an overlapping facts card — and only then
asks you to click.

This applies the same three moves to the seller side, using the numbers
the seller actually cares about: the Coming Soon price, the expected sale
range and who controls the market.

Written as index_v2.html so it sits next to the current index.html and the
two can be compared before either is adopted.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build_portal import (listing_page_url, show_luxury, buyer_portal_url,
                          track_record_file, track_record_card,  # noqa: E402
                          SUMMARY_TRACK_RECORD, record_band_title,  # noqa: E402
                          local_snapshot_file, is_example_home,  # noqa: E402
                          competition_dom, market_kind,  # noqa: E402
                          money, abbrev, sf, DEFAULT_AGENT, summary_name,
                          EXAMPLE_BUYER_PORTAL, EXAMPLE_BUYER_HOME,
                          EXAMPLE_BUYER_PDF, buyer_portal_ready)
from pricing import compute                                                 # noqa: E402

NOTES = []

# The team's own contact details. They close the page in the band above the
# footer, which is why the footer only repeats an agent's number or address
# when it differs from these.
TEAM_SITE = "caseysamson.com"
TEAM_PHONE = DEFAULT_AGENT["phone"]
TEAM_EMAIL = DEFAULT_AGENT["email"]

# The Casey Samson Team's production record. The seller portal opens with
# this rather than with the home's numbers: the nav page is about confidence
# in the team, and every pricing figure lives in the Roadmap.
# Casey, 12 Oct 2026: "replace current cst stats with stats from portfolio
# under 1.5."
#
# These five were hardcoded, and the title above them said "on Homes Over
# $1.5M" — so a $1.3M listing like 403 John Marshall was being sold on the
# team's luxury record. The band now reads the matching Portfolio page, the
# same source as the Pricing Strategy back page, so a seller sees the record
# in their own price band and all three surfaces quote one set of figures.
TEAM_STATS_FALLBACK = [
    ("114", "Transactions"),
    ("$262M", "Total volume"),
    ("6.5", "Days on market"),
    ("97.5%", "Success rate"),
    ("102.9%", "SP over list price"),
]



# Casey, 15 Oct 2026, off Casey_samson_team_production_since_2025.csv:
# "update Casey Samson Team stats... Totals of Volume and # of transactions
# come from total. DOM, % over List, Sold in first 10 days and Sold over
# list price... just use sale from Casey Samson."
#
# Volume and sales are the whole team at $1.5M and above -- 128 of the 134
# transactions in the file, resales, new homes and purchases together. The
# four performance figures are Casey's own resale listings (35 of them),
# because the export carries "New Home" and "Buyer" in place of days on
# market for the other two sections, and every new home shows CDOM 0.
#
# Shared with the Working With CST flyer and the buyer portal, so the three
# surfaces cannot drift apart.
PRODUCTION_SINCE_2025 = [
    # Casey, Nov 2026: "$296.9M" labeled "CST 1 year production"; 97% success
    # rate replaces "128 total sales"; DOM is 6.
    ("$296.9M", "CST 1 year production"),
    ("97%", "Success rate"),
    ("6", "Avg days on market"),
    ("102.4%", "Of original list price"),
    ("80%", "Sold in the first 10 days"),
    ("74%", "Sold above list price"),
]


def portfolio_stats(p):
    """Rebuilt 19 Nov 2026: the band reads PRODUCTION_SINCE_2025, the same six
    figures as the Summary's back page and the buyer portal.
The six figures in the portal's band.

    Casey, 12 Oct 2026: "The summary should mirror Portal." Since 18 Oct the
    Summary's back page carries one CST resale record for every property, so
    the portal reads the same file — otherwise the same house shows one set
    of team figures on its portal and a different set on its sheet, and the
    market row below lands under measures it does not answer.
    """
    return list(PRODUCTION_SINCE_2025)
    src = HERE / "templates" / SUMMARY_TRACK_RECORD
    if not src.exists():
        src = HERE / "templates" / track_record_file(p)
    if not src.exists():
        return TEAM_STATS_FALLBACK
    pairs = re.findall(r'<span class="n">([^<]+)</span>'
                       r'<span class="l">([^<]+)</span>',
                       src.read_text(encoding="utf-8"))
    return pairs or TEAM_STATS_FALLBACK


# The town's own current numbers, set beneath the team's so the two read as
# a comparison on the same measures. Success rate comes from the MSS cache;
# days on market and SP over list price are not carried in the MSS, so a
# property supplies them under "town_stats" as {"dom": "...", "sp_lp": "..."}.
TOWN_STATS_NOTE = "Current market, same measures"
# What the record covers. The figures are the team's production on homes at
# $1.5M and above, so the line only belongs on a portal at that level — the
# same test that decides the Luxury Experience page. A property overrides it
# with "team_stats_title", and "" removes it.
TEAM_STATS_TITLE = ("CST Strategy &mdash; Total Production Since 2025 "
                    "on Homes Over $1.5M")
TEAM_STATS_NOTE = "Verified MLS Bright performance"
MARKET_NOTE_KEY = "market_local"


def note(m):
    if m not in NOTES:
        NOTES.append(m)


CSS = """
:root{
  --bg:#FAF7F0; --card:#FFFFFF; --banner:#F1EBDA; --ink:#221C14;
  --muted:#71695A; --muted-2:#968972; --gold:#A5813B; --gold-deep:#8A6A2E;
  --gold-line:#D3B978; --rule:#E4DCC8; --navy:#1B2233;
}
*{box-sizing:border-box;}
body{margin:0; background:var(--bg); color:var(--ink);
  font-family:'Lora',Georgia,serif; line-height:1.6; -webkit-font-smoothing:antialiased;}
.wrap{max-width:1040px; margin:0 auto; padding:0 26px;}
img{max-width:100%;}

/* hero */
.hero{position:relative; min-height:540px; display:flex; align-items:flex-end; overflow:hidden;
  background:
    radial-gradient(ellipse 900px 520px at 22% 12%, #2E3346 0%, transparent 62%),
    radial-gradient(ellipse 800px 500px at 82% 88%, #3A3527 0%, transparent 58%),
    linear-gradient(150deg, #1B2233 0%, #232838 48%, #2A2A22 100%);}
/* Casey, 20 Nov 2026: no photo -> a compact hero, not 540px of empty gradient */
.hero.noshot{min-height:0;}
.hero.noshot .hero-inner{padding:44px 0 34px;}
.hero.noshot .hero-shade{background:linear-gradient(to bottom,
  rgba(12,10,6,.20) 0%, rgba(12,10,6,.05) 40%, rgba(12,10,6,.55) 100%);}
.hero > img{position:absolute; inset:0; width:100%; height:100%; object-fit:cover;}
.hero-shade{position:absolute; inset:0;
  background:linear-gradient(to bottom, rgba(12,10,6,.50) 0%, rgba(12,10,6,.12) 36%, rgba(12,10,6,.82) 100%);}
.hero-inner{position:relative; z-index:2; width:100%; padding:40px 0 38px; text-align:center;}
.hero-inner img.seal{width:66px; display:block; margin:0 auto 12px;
  filter:drop-shadow(0 2px 8px rgba(0,0,0,.6));}
.hero .brandline{letter-spacing:.24em; font-size:11.5px; font-weight:700; color:#F0E4C4;
  text-transform:uppercase; text-shadow:0 2px 10px rgba(0,0,0,.85);}
.hero .label{font-family:'Playfair Display',Georgia,serif; font-style:italic;
  font-size:19px; color:#F0E4C4; margin:6px 0 0; text-shadow:0 2px 10px rgba(0,0,0,.85);}
.hero h1{font-family:'Playfair Display',Georgia,serif; font-weight:700; color:#FFFDF7;
  font-size:clamp(30px,4.6vw,48px); margin:4px 0 2px; line-height:1.08;
  text-shadow:0 2px 14px rgba(0,0,0,.88);}
.hero .city{color:#EDE6D3; font-style:italic; font-size:15px; margin:0;
  text-shadow:0 2px 12px rgba(0,0,0,.85);}
.badges{display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-top:20px;}
.badge{border:1px solid rgba(240,228,196,.72); border-radius:4px; padding:9px 20px;
  background:rgba(12,10,6,.42); text-align:center;}
.badge .k{font-size:9.5px; letter-spacing:.16em; text-transform:uppercase; color:#D9C79A;
  font-weight:700;}
.badge .v{font-family:'Playfair Display',Georgia,serif; font-size:21px; font-weight:700;
  color:#FFFDF7; line-height:1.2; text-shadow:0 2px 10px rgba(0,0,0,.7);}
.badge.creed{font-family:'Playfair Display',Georgia,serif; font-style:italic;
  font-weight:600; font-size:clamp(17px,2.2vw,23px); color:#FFFDF7; padding:12px 30px;
  text-shadow:0 2px 10px rgba(0,0,0,.75);}

/* navy band */
.band{background:var(--navy); color:#F6F1E3; padding:24px 0 54px;}
.band .cols{display:flex; flex-wrap:wrap; justify-content:center; text-align:center;}
.band .col{flex:1 1 250px; padding:6px 26px;}
.band .col + .col{border-left:1px solid rgba(240,228,196,.25);}
.band .lbl{font-size:10px; letter-spacing:.16em; text-transform:uppercase; color:#D3B060;
  font-weight:700; margin-bottom:5px;}
.band .val{font-family:'Playfair Display',Georgia,serif; font-size:19px; font-weight:700;}
.band .sub{font-size:12.5px; color:#BFB7A5; margin-top:3px;}
@media (max-width:760px){ .band .col + .col{border-left:none; border-top:1px solid rgba(240,228,196,.25);
  margin-top:14px; padding-top:16px;} }

/* facts card, overlapping the band */
.facts{background:var(--card);
  border:1px solid var(--rule); border-radius:8px; margin:-30px auto 0; position:relative;
  z-index:3; max-width:980px; box-shadow:0 8px 26px rgba(60,45,10,.10); padding:18px 10px;}
.fact-row{display:grid; grid-template-columns:repeat(6,1fr);}.fact-row .fact.rowlabel{grid-column:span 2; text-align:left; display:flex; align-items:center; font-size:12px; font-weight:700; letter-spacing:.07em; text-transform:uppercase; color:var(--gold-deep); line-height:1.35;}@media (max-width:760px){.fact-row .fact.rowlabel{grid-column:span 2; justify-content:center; text-align:center;}}
@media (max-width:760px){ .fact-row{grid-template-columns:repeat(2,1fr);}
  .fact-row .fact.empty{display:none;} }
.facts-sub{text-align:center; font-size:10.5px; letter-spacing:.12em; text-transform:uppercase;
  font-weight:700; color:var(--muted); margin:14px 0 10px; padding-top:11px;
  border-top:1px solid var(--rule);}
.fact-row.town .fact .n{color:var(--ink);}
.fact-row .fact.rowlabel.one{grid-column:span 1; font-size:10.5px; letter-spacing:.05em; padding-right:6px;}
.facts-title{text-align:center; font-size:11px; letter-spacing:.12em; text-transform:uppercase;
  font-weight:700; color:var(--gold-deep); margin:0 0 14px; padding:0 12px 11px;
  border-bottom:1px solid var(--rule); line-height:1.5;}
.fact{flex:1 1 120px; text-align:center; padding:6px 10px;}
.fact .n{font-family:'Playfair Display',Georgia,serif; font-size:22px; font-weight:700;
  color:var(--gold-deep); display:block; line-height:1.15;}
.fact .l{font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
  margin-top:3px;}
.facts-note{text-align:center; font-size:11px; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted-2); margin:12px 0 0;}

section{padding:46px 0;}
section + section{border-top:1px solid var(--rule);}
h2.st{font-family:'Playfair Display',Georgia,serif; font-size:24px; font-weight:600;
  text-align:center; margin:0 0 8px;}
p.ss{text-align:center; color:var(--muted); font-size:14.5px; max-width:640px; margin:0 auto 30px;}

/* feature cards */
.feat{display:flex; align-items:stretch; gap:0; background:var(--card);
  border:1px solid var(--rule); border-radius:10px; overflow:hidden; margin-bottom:14px;
  text-decoration:none; color:inherit; box-shadow:0 2px 10px rgba(60,45,10,.06);}
.feat:hover{box-shadow:0 8px 24px rgba(60,45,10,.13); border-color:var(--gold-line);}
.feat .num{flex:none; width:64px; background:var(--banner); display:flex;
  align-items:center; justify-content:center; font-family:'Playfair Display',Georgia,serif;
  font-size:24px; font-weight:700; color:var(--gold-deep);
  border-right:1px solid var(--rule);}
.feat .body{flex:1; padding:20px 24px;}
.feat .tag{display:inline-block; font-size:10px; font-weight:700; letter-spacing:.1em;
  text-transform:uppercase; color:var(--gold-deep); background:var(--banner);
  padding:3px 11px; border-radius:11px; margin-bottom:7px;}
.feat .t{font-family:'Playfair Display',Georgia,serif; font-size:20px; font-weight:700;
  margin:0 0 4px; line-height:1.25;}
.feat .d{font-size:14px; color:var(--muted); margin:0;}
.feat .why{font-size:13px; font-weight:700; color:var(--gold-deep); margin:9px 0 0;}
.feat .arrow{flex:none; display:flex; align-items:center; padding:0 22px 0 8px;
  font-size:20px; color:var(--gold-deep);}
/* The PDF button that lives inside a card. .feat-hit is the stretched
   anchor that makes the whole card clickable; the button sits above it. */
.feat{position:relative;}
.feat-hit{position:absolute; inset:0; z-index:1; border-radius:10px;}
.feat-pdf{position:relative; z-index:2; display:inline-flex; align-items:center;
  gap:7px; margin-top:13px; padding:8px 15px; border:1.5px solid var(--gold-deep);
  border-radius:8px; background:var(--banner); color:var(--gold-deep);
  font-size:12.5px; font-weight:700; letter-spacing:.03em; text-decoration:none;
  transition:background .15s, color .15s;}
.feat-pdf:hover{background:var(--gold-deep); color:#fff;}
.feat-pdf svg{flex:none;}
/* The one button on the page that is the point of the page. */
.feat-pdf-key{background:var(--gold-deep); color:#fff; border-color:var(--gold-deep);
  box-shadow:0 2px 10px rgba(138,106,46,.28);}
.feat-pdf-key:hover{background:#6f5526; border-color:#6f5526;}
.pdf-star{margin-right:-1px;}
.pdf-tag{margin-left:9px; padding:2px 7px; border-radius:999px;
  background:rgba(255,255,255,.22); font-size:10px; letter-spacing:.09em;
  text-transform:uppercase;}
@media print{ .feat-pdf-key{box-shadow:none;} }
/* Under the Market Snapshot card: the public navigator, which is current
   whether or not this property has a pull of its own. */
.rest-of-market{text-align:center; margin:-4px 0 18px;}
.rest-of-market a{font-size:13px; font-weight:700; letter-spacing:.02em;
  color:var(--gold-deep); text-decoration:none;}
.rest-of-market a:hover{text-decoration:underline;}
.print{display:block; text-align:right; font-size:12px; font-weight:600;
  color:var(--gold-deep); text-decoration:none; margin:-8px 0 16px; padding-right:6px;}
.print:hover{text-decoration:underline;}
@media (max-width:620px){ .feat{flex-direction:column;} .feat .num{width:100%; height:44px;
  border-right:none; border-bottom:1px solid var(--rule);} .feat .arrow{display:none;} }

/* secondary grid */
.grid{display:grid; grid-template-columns:repeat(2,1fr); gap:14px;}
.tile{display:flex; align-items:center; gap:14px; background:var(--card);
  border:1px solid var(--rule); border-left:4px solid var(--gold-deep); border-radius:8px;
  padding:16px 18px; text-decoration:none; color:inherit;}
.tile:hover{border-color:var(--gold-line); border-left-color:var(--gold-deep);
  box-shadow:0 5px 16px rgba(60,45,10,.11);}
.tile svg{flex:none; color:var(--gold-deep);}
.tile .t{font-family:'Playfair Display',Georgia,serif; font-weight:700; font-size:16px;}
.tile .d{font-size:12.5px; color:var(--muted); margin-top:2px;}
@media (max-width:700px){ .grid{grid-template-columns:1fr;} }

/* strategy close */
.strategy{background:var(--banner); border-top:1px solid var(--gold-line);
  border-bottom:1px solid var(--gold-line);}
.tri{display:grid; grid-template-columns:repeat(3,1fr); gap:0; max-width:900px; margin:0 auto;}
.tri > div{padding:0 26px; text-align:center;}
.tri > div + div{border-left:1px solid var(--gold-line);}
.tri .n{font-family:'Playfair Display',Georgia,serif; font-size:13px; font-weight:700;
  letter-spacing:.14em; text-transform:uppercase; color:var(--gold-deep); margin-bottom:8px;}
.tri .t{font-family:'Playfair Display',Georgia,serif; font-size:18px; font-weight:700;
  line-height:1.3;}
/* the closing band carries contact details, so the long ones (an email
   address) step down a size rather than wrap mid-column. */
.tri .t.sm{font-size:15.5px; word-break:break-word;}
.tri .t a{color:inherit; text-decoration:none; border-bottom:1px solid var(--gold-line);}
.tri .t a:hover{border-bottom-color:var(--gold-deep);}
@media (max-width:700px){ .tri{grid-template-columns:1fr;} .tri > div + div{border-left:none;
  border-top:1px solid var(--gold-line); padding-top:22px; margin-top:22px;} }

footer{text-align:center; padding:36px 0 50px;}
footer .produced{font-weight:700; font-size:14.5px; margin-bottom:4px;}
footer .contact-line{font-weight:700; font-size:13.5px;}
footer .contact-line a{color:inherit; text-decoration:none;}
footer .contact-line .sep{font-weight:400; color:var(--muted-2); margin:0 8px;}
footer .copy{font-size:11.5px; color:var(--muted); margin-top:14px;}
"""

I = {
 "pdf": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
 "agent": '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2A5 5 0 0 1 21 19"/>',
 "market": '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/>',
 "site": '<rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 6l1.5-2h5L16 6"/>',
 "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
}


def icon(k):
    return (f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.7">{I[k]}</svg>')


def build_index_v2(p, s, out, filename="index.html"):
    pre = p["prefix"]
    addr = p["address"]
    subj = p.get("subject") or {}
    v = p.get("values") or {}

    hero = p.get("hero_photo")
    src_dir = Path(p.get("asset_dir", "."))
    if not src_dir.is_absolute():
        src_dir = HERE / src_dir
    if hero and not (src_dir / hero).exists():
        note(f"Hero photo MISSING — {hero} is not in {src_dir}; the cover falls back "
             "to the brand gradient.")
        hero = None
    hero_img = f'  <img src="{hero}" alt="{addr}">' if hero else ""
    if not hero:
        note("Hero photo OMITTED — the cover uses the brand gradient. Add one to "
             "hero_photo and rebuild.")

    # ---- hero badges: the two numbers a seller looks for first ----------
    # Coming Soon and Expected Sale Price live in the Roadmap. What goes under
    # the address here is the promise, not the number.
    badge_html = ('<div class="badges"><div class="badge creed">'
                  "It is not about price, It&rsquo;s about Strategy."
                  "</div></div>")

    # ---- navy band: strategy in three numbers --------------------------
    cache = HERE / "market_cache.json"
    st, absorb = {}, {}
    if cache.exists() and p["market"].get("slug"):
        c = json.loads(cache.read_text()).get(p["market"]["slug"], {}) or {}
        st, absorb = c.get("stats") or {}, c.get("absorption") or {}
    # The page argues in three beats: the hero says it is about strategy,
    # this band says what the strategy IS, and the record below shows it
    # working. Market conditions live in the Market Snapshot.
    cols = [
        ("First", "Build Confidence",
         "In the value and the condition of the home"),
        ("Then", "Create Competition",
         "Maximum exposure to the largest qualified buyer pool"),
        ("Result", "Validate Highest and Best Price",
         "Buyers compete, and the price is proven"),
    ]
    # A property can carry its own band colour — "band_color": "#000000"
    # puts the strategy band in black rather than the house navy.
    band_style = f' style="background:{p["band_color"]};"' if p.get("band_color") else ""
    band = (f'<div class="band"{band_style}><div class="wrap"><div class="cols">'
            + "".join(f'<div class="col"><div class="lbl">{k}</div>'
                      f'<div class="val">{val}</div><div class="sub">{sub}</div></div>'
                      for k, val, sub in cols)
            + "</div></div></div>")

    # The record box can carry a line saying what the numbers cover, so the
    # seller reads them as this team's production in their price range
    # rather than as the whole market.
    # The title has to name the same band the figures come from. It used to
    # say "on Homes Over $1.5M" and appear only on luxury portals, which left
    # every other portal showing an unlabelled row of numbers.
    # At $1.5M and above the figures are the production file, which runs
    # from 2025 to today, so the band says that rather than the older
    # August-to-September window the Luxury Experience page covered.
    # The title names the record the figures came from, which since 18 Oct
    # is the one CST resale record. A property's own "team_stats_title" names
    # a size band or a price split the figures no longer follow, so it would
    # caption this row with something it contradicts.
    stats_title = record_band_title(p)
    if p.get("team_stats_title"):
        note(f'Seller portal: "{p["team_stats_title"]}" not used as the band '
             "title — the band carries the one CST resale record now, not "
             "this property's size band.")
    title_html = f'<p class="facts-title">{stats_title}</p>' if stats_title else ""

    # Second row: the town at this moment, on the measures the team row ends
    # with. Only the cells that have real figures are drawn.
    # Read as the market moves: how fast it is absorbing right now, how much
    # of it is already spoken for, and how the year has actually finished out.
    # Five slots, matching the team row above it, so each market figure sits
    # under the team figure it answers — success rate beneath success rate.
    # Slots 1 and 5 stay empty until the town's own DOM and SP/LP exist.
    town = p.get("town_stats") or {}
    town_cells = [
        None,
        (st.get("uc_14"), "14 day absorption"),
        (st.get("under_contract"), "% under contract"),
        (st.get("success_rate") or town.get("success_rate"), "Success rate"),
        None,
    ]
    # Casey, 12 Oct 2026: he supplied the Bright export for this market, so
    # the comparison row is measured off every listing in it rather than the
    # handful of direct competitors or the MSS's own windows.
    _ml = p.get("market_local")
    wide_label = False
    if _ml and _ml.get("cells"):
        _c = [tuple(c) if c else None for c in _ml["cells"]]
        # Five figures leave one column for the market's name, under the
        # team's volume, with every figure beneath the measure it answers.
        # Four is the older shape, where the name took the first two.
        if len(_c) == 5:
            town_cells, wide_label = [None] + _c, True
        else:
            town_cells = [None, None] + _c
    else:
        # Without a market_local set there is nothing that answers the team's
        # last three measures, and absorption / % under contract / success
        # rate are not those measures — stacked in those columns they read as
        # a comparison. On Vintage Crest the team's "sold above list price"
        # and the market's "success rate" both landed on 70%, which looks
        # like a tie between two figures that count different things. Only
        # the competitor DOM answers a column the team row actually has, so
        # it is the only cell kept; the rest stay blank and the builder says
        # what export would fill them.
        _cd = competition_dom(p)
        town_cells = [None, None,
                      (_cd[0], f"Avg DOM &mdash; the {_cd[1]} homes now on "
                               "the market") if _cd else None,
                      None, None, None]
        if _cd:
            note("Seller portal market row: only days on market is comparable "
                 "— the team figure is days to contract on closed sales, the "
                 f'market figure is days so far for the {_cd[1]} listings '
                 "still unsold. Supply a closed-sale export for this size "
                 'band to fill the row as "market_local".')
        else:
            note("Seller portal market row: no market comparison available "
                 "— the property has no market_local set and no competition "
                 "listings with days on market.")
    town_cells = [c if c and c[0] else None for c in town_cells]
    town_html = ""
    if any(town_cells):
        # Casey, 12 Oct 2026: "The white space in Market section could have
        # the title in it." The first two cells of this row are empty — the
        # team has figures there the market has no counterpart for — so the
        # label sits in that gap instead of as a centred line above it.
        label = (p.get("town_stats_label")
                 or (p.get("market_local") or {}).get("label")
                 or f'Rest of the {p["city"]} {market_kind(p)} Market')
        # Casey, 15 Nov 2026: the market row reads "... over the last 90 days".
        if "90 days" not in label and not p.get("town_stats_label"):
            label = f"{label} over the last 90 days"
        cells = "".join(
            '<div class="fact empty"></div>' if c is None else
            f'<div class="fact"><span class="n">{c[0]}</span>'
            f'<div class="l">{c[1]}</div></div>'
            for c in (town_cells[1:] if wide_label else town_cells[2:]))
        lab = (f'<div class="fact rowlabel{" one" if wide_label else ""}">'
               f'{label}</div>')
        town_html = f'<div class="fact-row town">{lab}{cells}</div>'
    facts_html = ('<div class="wrap"><div class="facts">'
                  + title_html
                  + '<div class="fact-row">'
                  + "".join(f'<div class="fact"><span class="n">{n}</span>'
                            f'<div class="l">{l}</div></div>'
                            for n, l in portfolio_stats(p))
                  + '</div>' + town_html
                  # Casey, 15 Nov 2026: "Source: MLS Bright" inside the box.
                  + '<p style="text-align:center;font-size:11px;color:#71695A;margin:8px 0 0;">Source: MLS Bright</p>'
                  + f'</div><p class="facts-note">{TEAM_STATS_NOTE}</p></div>')

    # ---- the three things the seller opens -----------------------------
    # Casey, 11 Oct 2026: "instead of text under buyer portal and roadmap,
    # make the links more visible by putting box in the box with
    # Roadmap/buyer portal." The PDF link used to float outside the card as
    # small right-aligned text, which read as a caption rather than
    # something to click. It is now a bordered button inside the card body.
    #
    # A link cannot be nested inside a link, so a card carrying a button is
    # a <div> with a stretched hit-area anchor behind the content; the button
    # sits above it. A card with no button stays a plain <a>.
    def feat(n, tag, title, desc, why, href, blank=False, pdf=None):
        t = ' target="_blank" rel="noopener"' if blank else ""
        inner = (f'<div class="num">{n}</div>'
                 f'<div class="body"><span class="tag">{tag}</span>'
                 f'<p class="t">{title}</p><p class="d">{desc}</p>'
                 f'<p class="why">{why}</p>{pdf_btn(*pdf) if pdf else ""}</div>'
                 f'<span class="arrow">&rarr;</span>')
        if not pdf:
            return f'<a class="feat" href="{href}"{t}>{inner}</a>'
        return (f'<div class="feat"><a class="feat-hit" href="{href}"{t} '
                f'aria-label="{title}"></a>{inner}</div>')

    def card_no_link(n, tag, title, desc, why, pdf):
        """A card whose only clickable thing is its button.

        Used when the home's Buyer Pricing Report exists but the Buyer Portal
        site is not published: there is a document to open and no page to
        send anyone to, so the card carries no stretched link and no arrow.
        """
        return (f'<div class="feat"><div class="num">{n}</div>'
                f'<div class="body"><span class="tag">{tag}</span>'
                f'<p class="t">{title}</p><p class="d">{desc}</p>'
                f'<p class="why">{why}</p>{pdf_btn(*pdf)}</div></div>')

    def pdf_btn(href, label, key=False, tag=""):
        """key = the filled gold treatment; tag = the pill, e.g. "Start here".

        Casey, 14 Oct 2026: "Color the Macarthur the same way without Start
        here." The fill and the pill are separate now -- the colour marks a
        button as one of the two that matter, the pill marks the single one
        to open first.
        """
        star_svg = ('<svg class="pdf-star" width="14" height="14" '
                    'viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
                    '<path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.3'
                    ' 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8z"/></svg>') if tag else ""
        return (f'<a class="feat-pdf{" feat-pdf-key" if key else ""}" '
                f'href="{href}" target="_blank" '
                f'rel="noopener">{star_svg}<svg width="13" height="13" '
                'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2"><path d="M6 9V2h12v7"/>'
                '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 '
                '2 2v5a2 2 0 0 1-2 2h-2"/>'
                f'<path d="M6 14h12v8H6z"/></svg>{label}'
                + (f'<span class="pdf-tag">{tag}</span>' if tag else "")
                + "</a>")

    main = [feat("1", "Seller Roadmap", "Current Seller Roadmap",
                 "The pricing, preparation, launch and negotiation plan designed to "
                 "create traffic and competition.",
                 "Why it matters: You know what happens next, and why.",
                 f"{pre}_Roadmap.html",
                 # Casey, 11 Oct 2026: the one-page Pricing Strategy is the
                 # print deliverable now, not the nine-page Roadmap.
                 pdf=(f"{pre}_Pricing_Strategy_Summary.pdf",
                      f"{summary_name(p)} (PDF)"))]
                 # Casey, 20 Nov 2026: sellers were opening the Summary instead of
                 # the Roadmap -- the button goes back to tan, no "Start here".

    # Casey, 10 Oct 2026: the home's own Buyer Portal sits ABOVE the example,
    # and the luxury track record comes straight after the example. So the
    # numbering runs off a counter rather than literals — the own-portal card
    # is only there once the home has a live portal.
    _n = iter("23456789")

    bp = buyer_portal_url(p)

    # Casey, 14 Oct 2026: "move Example to second tier right below Seller
    # roadmap." The example is the one buyer card that always resolves -- a
    # home's own portal is frequently not published yet -- so it takes the
    # second slot and the home's own portal follows it. The comment above
    # the own-portal block below is from the 10 Oct ordering and no longer
    # describes the layout.
    # Casey, 20 Oct 2026: "as soon as a buyer portal is updated with pictures
    # and premiums, remove Example Buyer Portal." The example took the second
    # slot on 14 Oct because a home's own portal was usually not built yet.
    # Once this one HAS its pictures and premiums that no longer holds, and
    # leaving the example above it hands the seller a click onto somebody
    # else's house.
    if not is_example_home(p) and not buyer_portal_ready(p):
        main.append(feat(next(_n), "Buyer Portal",
                     "Buyer Portal &mdash; Example",
                     f"This is {EXAMPLE_BUYER_HOME}&rsquo;s portal, not yours. It shows "
                     "the total picture we prepare &mdash; photography, video, "
                     "authenticated values, disclosures and the instructions for writing "
                     "an offer."
                     + ("" if bp else " Yours is built once we have the photographs "
                        "and documents for your home."),
                     "Why it matters: One place buyers trust means stronger offers.",
                     EXAMPLE_BUYER_PORTAL, blank=True,
                     # Casey, 12 Oct 2026: the example card gets the same
                     # button the home's own portal card has, pointing at the
                     # example home's Buyer Pricing Report, which ships inside
                     # the portal folder.
                     pdf=(EXAMPLE_BUYER_PDF,
                          f"{EXAMPLE_BUYER_HOME} Buyer Pricing Report (PDF)")))
                     # Casey, 20 Nov 2026: back to tan as well.

    _own_pdf = (f"{pre}_Buyer_Report.pdf", "Printable Buyer Pricing (PDF)")
    # Casey, 23 Nov 2026: "Remove options ... to go to Subject or sample.
    # Completeness ... dictates." One buyer card: the Example until this
    # home's portal is finished, then this home's own.
    _own_ok = is_example_home(p) or buyer_portal_ready(p)
    if bp and not _own_ok:
        pass
    elif bp:
        main.append(feat(next(_n), "Buyer Portal", "Buyer Portal",
                         "The total picture of your home&rsquo;s offering &mdash; "
                         "photography, video, authenticated values, disclosures and the "
                         "instructions for writing an offer.",
                         "Why it matters: One place buyers trust means stronger offers.",
                         bp, blank=True, pdf=_own_pdf))
    elif _own_ok and (out / f"{pre}_Buyer_Report.pdf").exists():
        # The Buyer Pricing Report is a file inside this folder, so it works
        # whether or not the portal site is published. Gating the button on
        # "live" withheld the seller's own pricing document because a web
        # page was not up yet. The card carries the button and no outbound
        # link, so there is still nothing here that can 404.
        main.append(card_no_link(next(_n), "Buyer Portal",
                                 "Buyer Pricing",
                                 "The authenticated values and the comparable "
                                 "sales buyers and their agents are shown. Your "
                                 "full Buyer Portal &mdash; photography, video, "
                                 "documents and offer instructions &mdash; goes "
                                 "live with the listing.",
                                 "Why it matters: One place buyers trust means "
                                 "stronger offers.",
                                 pdf=_own_pdf))

    # Casey, 14 Oct 2026: "produce a market Snapshot from Original price model
    # and make it the forth section behind seller roadmap, maple buyer portal
    # and buyer portal for this property." The card goes only where this
    # property's own pull exists — pointing a seller at another home's comps
    # would be worse than no card. The Rest of the Market line below it goes
    # on every portal, because the public navigator is current either way.
    _mss = local_snapshot_file(p, out)
    if _mss:
        _live = _mss.startswith("http")
        _mname = (p.get("market") or {}).get("name") or "your market"
        main.append(feat(next(_n), "Market Snapshot",
                         _mname if _live else "Local Market Snapshot&trade;",
                         (f"Current conditions in the {_mname} &mdash; what "
                          "share of the homes here are under contract, how "
                          "long they have been listed, and which way the "
                          "market is moving." if _live else
                          "Homes like yours &mdash; bounded by size, age and "
                          "price range, not by city. What came on the market, "
                          "what went under contract, and the price each one "
                          "launched at."),
                         "Why it matters: The price you launch at is the price "
                         "that works.",
                         _mss, blank=_live))
    main.append('<p class="rest-of-market"><a href="https://cstmarketupdate.'
                'netlify.app/#" target="_blank" rel="noopener">Rest of the '
                'Market &rarr;</a></p>')

    # Track record, directly under the example. This used to test
    # show_luxury(p) first, which meant a property that explicitly named its
    # track_record page still got the Luxury Experience card — the card and
    # the rest of the portal pointed at different records. The explicit
    # setting wins now, and track_record_card() is the single place that
    # decides.
    # Casey, 15 Oct 2026: "remove 4 from seller portals... #4 is luxury
    # market experience. we have it on pricing summary and top of portal.
    # Redundent." The record now appears twice above this card -- in the
    # production band at the top of the portal and on the back of the
    # Pricing Strategy Summary -- so the card is a third telling of the
    # same thing. The page itself is still built and still linked from the
    # Pricing Strategy Summary; only the nav card comes off.
    _trf, _trt, _trh, _trb = track_record_card(p)
    note("Seller Portal: the %s card is not shown — the production band at "
         "the top of the portal and the Pricing Strategy Summary already "
         "carry that record." % _trt)

    main.append(feat(next(_n), "Marketing", "Marketing Your Home",
                     "Professional photography, video and a custom property website, then "
                     "four channels of Coming Soon exposure to reach the largest qualified "
                     "buyer pool.",
                     "Why it matters: Maximum exposure in the days that matter most.",
                     f"{pre}_Marketing.html"))
    # Casey, 21 Nov 2026: "It should have its own channel on the Seller portal."
    if (out / f"{pre}_Move_Up.html").exists():
        main.append(feat(next(_n), "Move Up (or Down)", "Move Up (or Down) Calculator",
                         "Your walk out the door proceeds from this sale, and what they do "
                         "for the down payment and monthly payment on your next home.",
                         "Why it matters: You know your next move before you list.",
                         f"{pre}_Move_Up.html"))

    # ---- everything else, two up ---------------------------------------
    tiles = []
    if p.get("include_tracker", True):
        tiles.append(("pdf", "Seller Tracker", "Every date, figure and contact in one place",
                      f"{pre}_Seller_Tracker.html", True))
    # The luxury track record moved up under the Buyer Portal example, so it is
    # no longer one of the two-up tiles down the page.
    if p["market"].get("slug"):
        # Two cards both called "Market Snapshot" on one page, going to two
        # different pages, is a question the seller should not have to ask.
        # Once the local one is in the stack above, this one is named for the
        # market it covers.
        _mkt_name = p["market"].get("name", "Market")
        _tile_title = ("Market Snapshot" if not _mss else
                       _mkt_name if _mkt_name.endswith("Snapshot")
                       else f"{_mkt_name} Snapshot")
        tiles.append(("market", _tile_title,
                      "Know what buyers are doing right now",
                      f'https://cstmarketupdate.netlify.app/{p["market"]["slug"]}.html', True))
    listing = listing_page_url(p)
    if listing:
        tiles.append(("site", "View Full Listing", "Photos and details on our site",
                      listing, True))
    tiles.append(("book", "Listing Protocol", "Every stage of the sale, explained",
                  "https://weekly-update.my.canva.site/listing-protocol", True))
    tiles_html = "".join(
        f'<a class="tile" href="{h}"{" target=\"_blank\" rel=\"noopener\"" if b else ""}>'
        f'{icon(k)}<div><div class="t">{t}</div><div class="d">{d}</div></div></a>'
        for k, t, d, h, b in tiles)

    # The closing band now carries the team's own name, site, phone and
    # email, so the footer names the listing agent and repeats a number
    # only when it is not the one already printed in that band.
    a = p.get("agent") or dict(DEFAULT_AGENT)
    name = a.get("display") or a["lookup"]
    contact = []
    if a.get("phone") and a["phone"] != TEAM_PHONE:
        contact.append(a["phone"])
    if a.get("email") and a["email"].lower() != TEAM_EMAIL.lower():
        contact.append(f'<a href="mailto:{a["email"]}">{a["email"]}</a>')
    contact_html = '<span class="sep">|</span>'.join(contact)

    noshot = "" if hero else " noshot"
    # Casey, 22 Nov 2026: "Guides to Understanding CST Tools" near the top --
    # navy boxes for the Seller Roadmap, Buyer Portal, Market Snapshot and
    # Move Up Buyers guides. Only guides that were copied into the site show.
    _g = [(f"{pre}_Roadmap_Guide.html", "Seller Roadmap"), ("Buyer_Portal_Guide.html", "Buyer Portal"),
          ("Market_Snapshot_Guide.html", "Market Snapshot"), ("Move_Up_Guide.html", "Move Up Buyers")]
    _g = [(h, t) for h, t in _g if (out / h).exists()]
    guides_html = ("" if not _g or p.get("guides") is False else
        '<section class="guides"><div class="wrap"><h2 class="st">Guides to Understanding CST Tools</h2>'
        '<div class="guide-row">' + "".join(
            f'<a class="guide-box" href="{h}" target="_blank" rel="noopener"><span>Guide</span>{t}</a>'
            for h, t in _g) + "</div></div></section>\n")
    html = f"""<!-- SELLER PORTAL (private) — {addr}. Deploy to {p.get("portal_url", "(portal_url not set)")} -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{addr} &mdash; Seller Portal, The Casey Samson Team</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500;1,600&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap');
{CSS}
.guides{{padding:34px 0 6px;}}
.guide-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:14px;}}
.guide-box{{display:block;background:#1F2A44;color:#E8C77A;text-decoration:none;text-align:center;
  border-radius:8px;padding:20px 12px;font:700 19px 'Playfair Display',Georgia,serif;
  box-shadow:0 6px 16px rgba(31,42,68,.18);transition:transform .15s;}}
.guide-box span{{display:block;font:700 10.5px 'Lora',Georgia,serif;letter-spacing:.22em;
  text-transform:uppercase;color:#C9D2E0;margin-bottom:6px;}}
.guide-box:hover{{transform:translateY(-2px);background:#26355A;}}
@media (max-width:760px){{.guide-row{{grid-template-columns:repeat(2,1fr);}}}}
</style>
</head>
<body>

<div class="hero{noshot}">
{hero_img}
  <div class="hero-shade"></div>
  <div class="hero-inner">
    <img class="seal" src="Gold_Standard_Logo.png" alt="The Casey Samson Team">
    <div class="brandline">The Casey Samson Team</div>
    <p class="label">Seller Portal</p>
    <h1>{addr}</h1>
    <p class="city">{p["city"]}, {p["state"]}</p>
    {badge_html}
  </div>
</div>

{band}{facts_html}
{guides_html}
<section>
  <div class="wrap">
    {"".join(main)}
  </div>
</section>

<section>
  <div class="wrap">
    <h2 class="st">Track the Sale</h2>
    <p class="ss">Your tracker, our record, the market and the listing itself.</p>
    <div class="grid">{tiles_html}</div>
  </div>
</section>

<section class="strategy">
  <div class="wrap">
    <h2 class="st">The Casey Samson Team</h2>
    <p class="ss">Samson Properties &mdash; Northern Virginia</p>
    <div class="tri">
      <div><div class="n">Online</div><div class="t"><a href="https://{TEAM_SITE}" target="_blank" rel="noopener">{TEAM_SITE}</a></div></div>
      <div><div class="n">Call</div><div class="t">{TEAM_PHONE}</div></div>
      <div><div class="n">Email</div><div class="t sm"><a href="mailto:{TEAM_EMAIL}">{TEAM_EMAIL}</a></div></div>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <div class="produced">Your Listing Agent &mdash; {name}</div>
    <div class="contact-line">{contact_html}</div>
    <div class="copy">&copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </div>
</footer>

</body>
</html>
"""
    (out / filename).write_text(html)


def main():
    p = json.loads(Path(sys.argv[1]).read_text())
    p.setdefault("prefix", re.sub(r"[^A-Za-z0-9]+", "_", p["address"]).strip("_"))
    v = p["values"]
    s = compute(dated=v["dated"], customary=v["customary"],
                customary_list=v["customary_list"], premium=v.get("premium", 0),
                upgrades=v.get("upgrades", 0), discount=v.get("discount", 0),
                discount_reason=v.get("discount_reason", ""),
                coming_soon_override=v.get("coming_soon_override"))
    out = HERE / "output" / p["prefix"]
    out.mkdir(parents=True, exist_ok=True)
    build_index_v2(p, s, out)
    print(f'{p["address"]} -> {out / "index.html"}')
    for m in NOTES:
        print(f"  - {m}")


if __name__ == "__main__":
    main()
