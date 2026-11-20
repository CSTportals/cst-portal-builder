#!/usr/bin/env python3
"""Partnership flyer — Samson Properties x CST Pricing LLC.

Built in the Seller Portal's visual system (same stylesheet, same hero,
band, record card and feature cards) so the flyer looks like the product it
is selling. The audience is Samson agents, not sellers, so the three
documents are replaced by what the portals do for an agent's business.

    python3.12 build_partner_flyer.py [--out DIR]
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build_index_v2 import CSS, TEAM_STATS                       # noqa: E402

TPL = HERE / "templates"
HERO_SRC = HERE / "output" / "502_MacArthur" / "502_MacArthur_front.jpg"

# The record under the portals is the TEAM's record, not CST's: the combined
# production of the 53 agents on the board this flyer links to. Every figure
# is the totals row of "Top 53 Agents - Volume and Track Record", so the
# number here and the number on that page can never disagree.
STATS_TITLE = "The Listing Recovery Team &mdash; Track Record"
STATS_NOTE = "Verified MLS Bright performance"
LRT_STATS = [
    ("53", "Agents"),
    ("$818,579,384", "Closed volume"),
    ("1,013", "Closed sales"),
    ("90%", "Avg sold / listed"),
    ("10.1", "Avg trimmed DOM"),
    ("205", "Avg score"),
]

# The market the agent is actually selling into: the four luxury counties,
# averaged. Taken from COUNTY_LUXURY in the MSS build (mss_data.py) — a
# straight mean of the four, which is why only rate measures are shown;
# averaging inventory or contract swings across counties this different in
# size would say nothing. Refresh these when the MSS week changes.
COUNTY_WEEK = "Week of October 1, 2026"
COUNTY_LABEL = ("Northern Virginia Luxury &mdash; Fairfax, Arlington, "
                "Loudoun and Prince William, averaged")
# Five slots matching the CST row above, so each market figure sits under
# the team figure it answers — 71% success rate beneath 97.5%.
COUNTY_STATS = [
    None,
    ("12%", "14 day absorption"),
    ("23%", "% under contract"),
    ("71%", "Success rate"),
    None,
]

# Live examples. The flyer is handed out and emailed, so every link is
# absolute — a relative path would die the moment the PDF leaves the folder.
MACARTHUR_SELLER = "https://502macarthur.netlify.app"
MACARTHUR_BUYER = "https://buymacarthur.netlify.app"
# The sample Buyer Report rides inside the flyer folder rather than
# pointing at the listing site, so the card works the moment the flyer
# deploys and keeps the reader on the flyer.
MACARTHUR_PDF_SRC = HERE / "output" / "502_MacArthur" / "502_MacArthur_Buyer_Report.pdf"
MACARTHUR_PDF = "502_MacArthur_Buyer_Report.pdf"
MACARTHUR_ROADMAP = ("https://502macarthur.netlify.app/"
                     "502_MacArthur_Roadmap.html")
# The stuck-listing example. Casey, 14 Oct 2026: point it at the Haybine
# seller portal. That IS the seller's own portal, which is why the note
# that used to sit here said not to -- his call, made deliberately.
HAYBINE_RECOVERY = "https://41057haybine.netlify.app"

# What the portals do for the agent, in the order the business feels it.
BAND_TAG = "Save Time, Save Energy, Make More Money"
# The portals' own mission, distinct from the team's.
BAND_MISSION = ("Provide Samson agents tools to close listings and position "
                "them for success.")
# The three tools, and what each one does for the seller.
BAND = [
    ("Recovery Roadmap", "For listings that are stuck on the market",
     HAYBINE_RECOVERY, "See a live Recovery Roadmap"),
    ("Seller Roadmap", "For new listings &mdash; steering the seller to the "
     "right decisions", MACARTHUR_ROADMAP, "See a live Seller Roadmap"),
    ("Buyer Portal", "Demonstrating the home&rsquo;s values and amenities",
     MACARTHUR_BUYER, "See a live Buyer Portal"),
]
# What it costs. The recovery split is shown broken out because 25% + 15%
# is the 40% above it -- an agent should be able to see the whole commission
# share accounted for rather than take it on trust.
FEES = [
    ("Recovery Fees", "$250", "up front", "40%", "of the commission",
     [("25%", "to the recovery agent"),
      ("15%", "for CST Tools")]),
    ("Seller Portals for New Listings", "$250", "up front", "15%",
     "of the commission", []),
]
FEES_NOTE = ("The $250 goes to upfront operations &mdash; producing the pricing "
             "model and the portals.")

# The calendar. Each entry is (kicker, title, where, when).
SCHEDULE = [
    ("First Event &middot; Invitation Only", "Lunch and Learn",
     "The Tower Club", "Date and time to be announced"),
    ("Monthly", "Operations Workshop",
     "At the office", "First Tuesday of the month"),
    ("Monthly", "Operations Workshop",
     "Location to be announced", "Third week of the month"),
]

# What the three of them produce together.
BAND_RESULTS = ["Close More Listings", "First-Week Sales",
                "Happy Sellers", "More Referrals"]

# The two Top 53 boards ride inside the flyer folder rather than pointing at
# another site, so both work the moment the flyer deploys and the reader stays
# with the flyer. Casey supplied them as a pair that cross-link to each other.
TOP53_SRC = HERE.parent / "top53"
A_LISTERS = "top_53_volume.html"
# The A Listers board, by city. The recovered-income model that used to sit
# here is an internal document -- "Private, Internal Use Only, Not For
# Distribution", naming 364+ agents with their lost volume and CST fees -- so
# it must never be linked from a flyer handed to those same agents.
A_LISTERS_BY_CITY = "top_53_by_city.html"

FEATURES = [
    ("1", "For the Seller", "The Seller Portal",
     "A private page carrying the Gold Standard Roadmap&trade;, the marketing plan "
     "and the transaction tracker &mdash; authenticated values, money at risk and "
     "the week-one plan, in the seller&rsquo;s hands before they sign.",
     "Why it matters: The listing appointment ends with a strategy, not a debate about price.",
     MACARTHUR_SELLER, "See a live Seller Portal"),
    ("2", "For the Buyer", "The Buyer Portal",
     "A public page for buyers and their agents &mdash; photography, video, "
     "authenticated values, disclosures, conveyances and the instructions for "
     "writing an offer, all in one link.",
     "Why it matters: One place buyers trust means stronger, cleaner offers.",
     MACARTHUR_BUYER, "See a live Buyer Portal"),
    ("3", "For the Open House", "The Open House PDF",
     "Buyer Reports are at every open house, for all potential buyers and sellers. "
     "Two pages, front and back: the home, the authenticated values and the "
     "premiums, with your name and photograph on the back.",
     "Why it matters: Great opportunity for new business &mdash; every visitor leaves "
     "holding your work.",
     MACARTHUR_PDF, "Open the sample Buyer Report (PDF)"),
]

GOALS = [
    ("Virginia&rsquo;s Recovery Team",
     "Ranked by volume and track record &mdash; the agents who close their "
     "listings and sell them in a time advantageous to the seller.",
     "Top 53 Agents &mdash; Volume and Track Record"),
    ("Virginia&rsquo;s Recovery Team by City",
     "The same standard, market by market, so every agent can see where "
     "they stand in the cities they actually work.",
     "Top 53 Agents &mdash; By City"),
]

PARTNERS = [
    ("Partner", "Samson Properties",
     "6,500 agents across Virginia, Maryland and DC."),
    ("Partner", "CST Pricing LLC",
     "The Gold Standard pricing engine, portals and production."),
    ("Sponsor", "Cardinal Title",
     "Proud sponsor of the Samson Properties A Listers program."),
]

EXTRA_CSS = """
/* ---- flyer ---- */
/* The sponsor now sits directly under "at Samson Properties" and is set in
   the same face and size, so the two read as one credit line. */
.hero .spons-line{margin-top:3px;}
.hero .spons{margin-top:18px; font-size:10.5px; letter-spacing:.18em; text-transform:uppercase;
  color:#D9C79A; font-weight:700; text-shadow:0 2px 10px rgba(0,0,0,.85);}
.hero .spons b{color:#FFFDF7;}
/* Six across. A flex row wraps 5+1 at PDF width and orphans the last figure,
   so this is an explicit six-column grid that cannot wrap. */
.fact-row.six{display:grid !important; grid-template-columns:repeat(6,1fr);
  gap:0; align-items:start;}
.fact-row.six .fact{padding:0 6px; flex:none !important; min-width:0;}
.fact-row.six .fact .n{font-size:23px; white-space:nowrap;}
.fact-row.six .fact .l{font-size:9.5px; line-height:1.3;}
@media (max-width:760px){ .fact-row.six{grid-template-columns:repeat(3,1fr); row-gap:18px;} }
@media print{
  /* The base print rule pins .fact-row to 5 columns with !important, which
     wraps the sixth figure onto its own line. Match that weight. */
  .fact-row.six{grid-template-columns:repeat(6,1fr) !important;}
  .fact-row.six .fact .n{font-size:16px !important;}
  .fact-row.six .fact .l{font-size:7.8px !important; letter-spacing:.06em !important;}
  .fact-row.six .fact{padding:0 4px !important;} }
/* The subhead carries as much of the pitch as the headline, so it is set at
   the same size rather than as supporting text. */
h2.st.ra-head{max-width:860px; margin-left:auto; margin-right:auto;}
@media print{ h2.st.ra-head{font-size:17px !important; margin-bottom:14px !important;}
  section{padding-top:14px !important; padding-bottom:14px !important;}
  h2.st{margin-bottom:5px !important;}
  p.ss{margin-bottom:12px !important;} }
.fees{display:grid; grid-template-columns:repeat(2,1fr); gap:16px; max-width:900px;
  margin:0 auto;}
.fee{background:var(--card); border:1px solid var(--rule); border-radius:10px;
  padding:20px 22px 18px; text-align:center; break-inside:avoid;}
.fee-k{font-size:11px; font-weight:700; letter-spacing:.16em; text-transform:uppercase;
  color:var(--muted); margin-bottom:12px;}
.fee-line{display:flex; align-items:baseline; justify-content:center; gap:8px;}
.fee-n{font-family:'Playfair Display',Georgia,serif; font-size:30px; font-weight:700;
  color:var(--gold-deep); line-height:1.1;}
.fee-u{font-size:12.5px; color:var(--muted);}
.fee-plus{font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted-2, #A79C88); margin:5px 0;}
.fee-split{margin-top:14px; padding-top:12px; border-top:1px solid var(--gold-line);}
.fee-row{display:flex; justify-content:space-between; align-items:baseline;
  font-size:12.5px; padding:3px 0;}
.fee-row b{color:var(--gold-deep); font-size:14px;}
.fee-row span{color:var(--muted);}
.fees-note{max-width:640px; margin:18px auto 0; text-align:center; font-size:13px;
  color:var(--muted); line-height:1.55;}
@media (max-width:700px){ .fees{grid-template-columns:1fr;} }
@media print{ .fee{padding:13px 16px 12px !important;} .fee-n{font-size:22px !important;}
  .fees-note{font-size:11px !important; margin-top:12px !important;} }
.band-mission{max-width:640px; margin:-4px auto 22px; text-align:center;
  font-size:14.5px; line-height:1.55; color:#E8DFC9;}
@media print{ .band-mission{font-size:12px !important; margin-bottom:16px !important;} }
.hero .mission{max-width:620px; margin:14px auto 0; font-size:15px; line-height:1.55;
  color:#F2EADA; text-shadow:0 2px 12px rgba(0,0,0,.85);}
@media print{ .hero .mission{font-size:12.5px !important; margin-top:10px !important;} }
.goals{display:grid; grid-template-columns:repeat(2,1fr); gap:16px; max-width:900px;
  margin:0 auto;}
.goal{background:var(--card); border:1px solid var(--rule); border-radius:10px;
  border-top:3px solid var(--gold-deep); padding:22px 24px;
  text-decoration:none; color:inherit; display:block;}
.goal:hover{border-color:var(--gold-line); border-top-color:var(--gold-deep);
  box-shadow:0 6px 18px rgba(60,45,10,.11);}
.band.standalone{background:transparent; padding:0 26px; margin:0 0 26px;}
.band .cols .placard{display:flex; flex-direction:column; text-decoration:none;
  color:inherit; background:rgba(255,253,247,.06); border:1px solid rgba(240,228,196,.35);
  border-radius:9px; padding:16px 16px 14px; margin:0 7px; text-align:center;}
.band .cols .placard + .placard{border-left:1px solid rgba(240,228,196,.35);}
.band .cols .placard:hover{background:rgba(255,253,247,.12);
  border-color:rgba(240,228,196,.75);}
.band .cols .placard .val{color:#FFFDF7;}
.band .cols .placard .sub{margin-top:5px;}
.pl-go{margin-top:auto; padding-top:10px; font-size:10.5px; font-weight:700;
  letter-spacing:.04em; color:#D9C79A;}
.events{display:grid; grid-template-columns:repeat(3,1fr); gap:16px; max-width:940px;
  margin:0 auto;}
.ev{background:var(--card); border:1px solid var(--rule); border-radius:10px;
  border-top:3px solid var(--gold-deep); padding:18px 20px; text-align:center;}
.ev .k{font-size:9.5px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--gold-deep); font-weight:700;}
.ev .nm{font-family:'Playfair Display',Georgia,serif; font-size:19px; font-weight:700;
  margin:7px 0 8px; line-height:1.2;}
.ev .wh{font-size:13px; font-weight:700;}
.ev .wn{font-size:12.5px; color:var(--muted); margin-top:3px;}
@media (max-width:760px){ .events{grid-template-columns:1fr;} }
.close-ask{margin:26px auto 22px !important; font-weight:700; color:var(--ink);}
.strategy .partners{margin-bottom:0;}
.band-join{display:flex; justify-content:center; margin:16px 0 0;}
.band-join span{display:block; width:0; height:0; border-left:7px solid transparent;
  border-right:7px solid transparent; border-top:8px solid rgba(240,228,196,.5);}
.band-results{text-align:center; margin:12px 0 0; padding-top:14px;
  border-top:1px solid rgba(240,228,196,.3);}
.band-results .rk{font-size:10px; letter-spacing:.16em; text-transform:uppercase;
  color:#D3B060; font-weight:700; margin-bottom:7px;}
.band-results .rv span{font-family:'Playfair Display',Georgia,serif; font-size:16px;
  font-weight:700; color:#FFFDF7;}
.band-results .rv .sep{color:rgba(240,228,196,.55); margin:0 10px; font-weight:400;
  font-family:'Lora',Georgia,serif;}
.band-tag{text-align:center; font-family:'Playfair Display',Georgia,serif;
  font-style:italic; font-size:17px; font-weight:600; color:#F0E4C4; margin:20px 0 0;
  padding-top:15px; border-top:1px solid rgba(240,228,196,.3);}
.band.standalone > .wrap{background:var(--navy); border-radius:10px;
  padding:24px 22px 26px; max-width:988px; margin:0 auto;}
.band-title{font-family:'Playfair Display',Georgia,serif; font-size:23px; font-weight:600;
  text-align:center; color:#FFFDF7; margin:0 0 20px; padding-bottom:14px;
  border-bottom:1px solid rgba(240,228,196,.3); max-width:420px;
  margin-left:auto; margin-right:auto;}
section.tools{padding-top:0 !important;}
.tool-aims{list-style:none; margin:0 auto 20px; padding:0; max-width:420px; text-align:center;}
.tool-aims li{font-family:'Playfair Display',Georgia,serif; font-size:16px; font-weight:700;
  padding:6px 0;}
.tool-aims li + li{border-top:1px solid var(--rule);}
.goal .gl{display:block; margin-top:9px; padding-top:7px; font-size:11.5px; font-weight:700;
  color:var(--gold-deep); border-top:1px solid var(--rule);}
.goal h3{font-family:'Playfair Display',Georgia,serif; font-size:19px; font-weight:700;
  margin:0 0 6px;}
.goal p{margin:0; font-size:14px; color:var(--muted);}
.partners{display:grid; grid-template-columns:repeat(3,1fr); gap:16px; max-width:940px;
  margin:0 auto;}
.partner{background:var(--card); border:1px solid var(--rule); border-radius:10px;
  padding:22px 20px; text-align:center;}
.partner .k{font-size:9.5px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--gold-deep); font-weight:700;}
.partner .nm{font-family:'Playfair Display',Georgia,serif; font-size:20px; font-weight:700;
  margin:7px 0 6px; line-height:1.2;}
.partner .d{font-size:12.5px; color:var(--muted); margin:0;}
.partner.sponsor{background:var(--banner); border-color:var(--gold-line);}
/* Each card opens a live example, so it carries the address it opens —
   the flyer is printed as often as it is clicked. */
.feat .lk{margin:8px 0 0; font-size:11.5px; letter-spacing:.04em; font-weight:700;
  color:var(--gold-deep); border-top:1px solid var(--rule); padding-top:7px;}
@media (max-width:760px){ .goals,.partners{grid-template-columns:1fr;} }

@media print{
  /* A printed page is narrower than a laptop, so the stylesheet's phone
     breakpoints fire and every row stacks. Pin the columns back. */
  @page{size:Letter; margin:0.4in;}
  body{background:#fff;}
  .wrap{padding:0 10px !important;}
  section{padding:6px 0 !important;}

  .hero{min-height:198px !important;}
  .hero-inner{padding:18px 0 34px !important;}
  .hero-inner img.seal{width:44px !important; margin-bottom:8px !important;}
  .hero h1{font-size:31px !important;}
  .hero .label{font-size:15px !important;}
  .hero .city{font-size:12.5px !important;}
  .badge.creed{font-size:16.5px !important; padding:9px 22px !important;}
  .badges{margin-top:10px !important;}
  .hero .spons{margin-top:12px !important;}

  .band{break-inside:avoid; page-break-inside:avoid;}
  .band.standalone{padding:0 10px !important; margin-bottom:9px !important;}
  .band.standalone > .wrap{padding:10px 15px 10px !important;}
  .band-title{font-size:18px !important; margin-bottom:9px !important;
    padding-bottom:7px !important;}
  .band-tag{font-size:12.5px !important; margin-top:6px !important;
    padding-top:0 !important; border-top:none !important;}
  .band-join{margin-top:6px !important;}
  .band-results{margin-top:5px !important; padding-top:6px !important;}
  .band-results .rv span{font-size:13.5px !important;}
  .band-results .rv .sep{margin:0 7px !important;}
  .band .cols{display:grid !important; grid-template-columns:repeat(3,1fr) !important;
    flex-wrap:nowrap !important;}
  .band .col{padding:2px 16px !important; border-top:none !important; margin-top:0 !important;}
  .band .cols .placard{padding:9px 12px 8px !important; margin:0 5px !important;}
  .pl-go{font-size:9px !important; padding-top:7px !important;}
  .band .col + .col{border-left:1px solid rgba(240,228,196,.25) !important;}
  .band .val{font-size:15.5px !important;}
  .band .sub{font-size:10.5px !important;}

  .facts{margin-top:-24px !important; padding:8px 8px !important;
    box-shadow:none !important; break-inside:avoid; page-break-inside:avoid;}
  .fact-row{display:grid !important;
    grid-template-columns:repeat(5,1fr) !important;}
  .fact-row .fact.empty{display:block !important;}
  .fact .n{font-size:18px !important;}
  .facts-sub{font-size:8.5px !important; margin:7px 0 6px !important;
    padding-top:8px !important;}
  .facts-title{margin-bottom:10px !important; padding-bottom:8px !important;}

  h2.st{font-size:20px !important;}
  p.ss{font-size:12.5px !important; margin-bottom:9px !important;}
  .tool-aims{margin-bottom:8px !important; max-width:380px !important;}
  .tool-aims li{font-size:13px !important; padding:2px 0 !important;}

  .goals{display:grid !important; grid-template-columns:repeat(2,1fr) !important;}
  .partners{display:grid !important; grid-template-columns:repeat(3,1fr) !important;}
  .goal .gl{font-size:10.5px !important; margin-top:7px !important;
    padding-top:5px !important;}
  .goal,.partner{padding:10px 14px !important; break-inside:avoid; page-break-inside:avoid;}
  .goal h3{font-size:16px !important;}
  .goal p,.partner .d{font-size:11.5px !important;}
  .partner .nm{font-size:17px !important; margin:5px 0 4px !important;}

  .feat{flex-direction:row !important; box-shadow:none !important; margin-bottom:5px !important;
    break-inside:avoid; page-break-inside:avoid;}
  .feat .num{width:48px !important; height:auto !important; border-right:1px solid var(--rule) !important;
    border-bottom:none !important; font-size:19px !important;}
  .feat .body{padding:7px 14px !important;}
  .feat .t{font-size:16px !important;}
  .feat .d{font-size:12px !important;}
  .feat .why{font-size:11.5px !important; margin-top:6px !important;}
  .feat .lk{font-size:10.5px !important; margin-top:6px !important;
    padding-top:5px !important;}
  .feat .tag{font-size:9px !important; margin-bottom:5px !important;}

  .tri{display:grid !important; grid-template-columns:repeat(3,1fr) !important;}
  .tri > div + div{border-left:1px solid var(--gold-line) !important;
    border-top:none !important; margin-top:0 !important; padding-top:0 !important;}
  .tri .t{font-size:14px !important;} .tri .t.sm{font-size:12px !important;}
  footer{padding:9px 0 0 !important;}
  footer .produced{font-size:13px !important; margin-bottom:2px !important;}
  footer .contact-line{font-size:12px !important;}
  section.strategy{padding:9px 0 12px !important;}
  .close-ask{margin:9px auto 8px !important; font-size:11.5px !important;}
  section.strategy h2.st{font-size:19px !important;}
  section.strategy p.ss{margin-bottom:11px !important;}
  footer .copy{font-size:8.5px !important; margin-top:6px !important; line-height:1.35 !important;}
  /* Page two carries the box, the three cards, the partnership row and the
     close, so the lower sections run tighter than the top of the flyer. */
  .partner .nm{font-size:16px !important; margin:5px 0 4px !important;}
  .partner .d{font-size:10.5px !important;}
  .partner .k{font-size:8.5px !important;}
  .events{display:grid !important; grid-template-columns:repeat(3,1fr) !important;
    gap:11px !important;}
  .ev{padding:11px 13px !important; break-inside:avoid; page-break-inside:avoid;}
  .ev .k{font-size:8.5px !important;}
  .ev .nm{font-size:16px !important; margin:5px 0 6px !important;}
  .ev .wh{font-size:11.5px !important;}
  .ev .wn{font-size:11px !important;}
  section.strategy h2.st{font-size:17px !important;}
  .tri .n{font-size:11px !important; margin-bottom:5px !important;}
  .tri > div{padding:0 14px !important;}
  .feat .t{font-size:15px !important;}
  .feat .d{font-size:11.5px !important;}
  .feat .why{font-size:11px !important; margin-top:5px !important;}
  .feat .lk{font-size:10px !important; margin-top:5px !important; padding-top:4px !important;}
}"""


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(TPL / "Gold_Standard_Logo.png", out / "Gold_Standard_Logo.png")
    if MACARTHUR_PDF_SRC.exists():
        shutil.copy(MACARTHUR_PDF_SRC, out / MACARTHUR_PDF)
    else:
        print(f"  ! sample Buyer Report not found at {MACARTHUR_PDF_SRC}")
    # The two Top 53 boards. Their filenames carry spaces, which make ugly
    # percent-encoded URLs, so they are renamed -- and the link each one holds
    # to the other is rewritten to match, or the rename breaks the pair.
    _t53 = {"Top 53 Agents - Volume and Track Record.html": "top_53_volume.html",
            "Top 53 Agents - By City.html": "top_53_by_city.html"}
    import urllib.parse as _up
    for _src, _dst in _t53.items():
        _f = TOP53_SRC / _src
        if not _f.exists():
            print(f"  ! Top 53 board not found at {_f}")
            continue
        _h = _f.read_text(encoding="utf-8")
        for _o, _n in _t53.items():
            _h = _h.replace(_up.quote(_o), _n).replace(_o, _n)
        # A way back. The boards are reached from the flyer, so without this
        # the reader's only route back is the browser button.
        _crumb = ('<a class="lrt-back" href="index.html">&larr; Back to '
                  'The Listing Recovery Team</a>\n')
        _css = ("""<style>
.lrt-back{display:block; max-width:1100px; margin:14px auto 0; padding:0 22px;
  font-size:13px; font-weight:600; color:var(--gold-deep); text-decoration:none;
  letter-spacing:.01em;}
.lrt-back:hover{text-decoration:underline;}
@media print{ .lrt-back{display:none;} }
</style>
""")
        if "</head>" in _h:
            _h = _h.replace("</head>", _css + "</head>", 1)
        if "<body>" in _h:
            _h = _h.replace("<body>", "<body>\n" + _crumb, 1)
        else:
            print(f"  ! no <body> in {_src} — breadcrumb not added")
        (out / _dst).write_text(_h, encoding="utf-8")

    hero_name = "Flyer_Hero.jpg"
    if HERO_SRC.exists():
        shutil.copy(HERO_SRC, out / hero_name)
        hero_img = f'<img src="{hero_name}" alt="">'
        noshot = ""
    else:
        print(f"  ! hero photo not found at {HERO_SRC} — flyer built without it")
        hero_img, noshot = "", " noshot"

    band = ('<div class="band standalone"><div class="wrap">'
            '<h2 class="band-title">Seller and Buyer Portals</h2>'
            f'<p class="band-mission">{BAND_MISSION}</p><div class="cols">'
            + "".join(
                f'<a class="col placard" href="{href}" target="_blank" rel="noopener">'
                f'<div class="val">{name}</div><div class="sub">{desc}</div>'
                f'<div class="pl-go">{cta} &rarr;</div></a>'
                for name, desc, href, cta in BAND)
            + '</div>'
            '<div class="band-results"><div class="rk">Results</div><div class="rv">'
            + '<span class="sep">&middot;</span>'.join(
                  f"<span>{r}</span>" for r in BAND_RESULTS)
            + '</div></div>'
            f'<p class="band-tag">{BAND_TAG}</p>'
            + "</div></div>")

    fees = ('<section><div class="wrap">'
            '<h2 class="st">Fees</h2>'
            '<div class="fees">'
            + "".join(
                f'<div class="fee">'
                f'<div class="fee-k">{k}</div>'
                f'<div class="fee-line"><span class="fee-n">{a}</span>'
                f'<span class="fee-u">{au}</span></div>'
                f'<div class="fee-plus">plus</div>'
                f'<div class="fee-line"><span class="fee-n">{b}</span>'
                f'<span class="fee-u">{bu}</span></div>'
                + ('<div class="fee-split">'
                   + "".join(f'<div class="fee-row"><b>{pc}</b><span>{who}</span></div>'
                             for pc, who in split)
                   + '</div>' if split else '')
                + '</div>'
                for k, a, au, b, bu, split in FEES)
            + '</div>'
            f'<p class="fees-note">{FEES_NOTE}</p>'
            '</div></section>')

    facts = ('<div class="wrap"><div class="facts">'
             f'<p class="facts-title">{STATS_TITLE}</p><div class="fact-row six">'
             + "".join(f'<div class="fact"><span class="n">{n}</span>'
                       f'<div class="l">{l}</div></div>' for n, l in LRT_STATS)
             + '</div>'
             + f'<p class="facts-note">{STATS_NOTE} &middot; {COUNTY_WEEK}</p></div>')

    feats = "".join(
        f'<a class="feat" href="{href}" target="_blank" rel="noopener">'
        f'<div class="num">{n}</div><div class="body">'
        f'<span class="tag">{tag}</span><p class="t">{title}</p>'
        f'<p class="d">{desc}</p><p class="why">{why}</p>'
        f'<p class="lk">{cta} &rarr;</p></div>'
        f'<span class="arrow">&rarr;</span></a>'
        for n, tag, title, desc, why, href, cta in FEATURES)

    goals = "".join(
        f'<a class="goal" href="{href}" target="_blank" rel="noopener">'
        f'<h3>{h}</h3><p>{d}</p><span class="gl">{label} &rarr;</span></a>'
        for (h, d, label), href in zip(GOALS, (A_LISTERS, A_LISTERS_BY_CITY)))
    schedule = "".join(
        f'<div class="ev"><div class="k">{k}</div><div class="nm">{title}</div>'
        f'<div class="wh">{where}</div><div class="wn">{when}</div></div>'
        for k, title, where, when in SCHEDULE)

    partners = "".join(
        f'<div class="partner{" sponsor" if k == "Sponsor" else ""}">'
        f'<div class="k">{k}</div><div class="nm">{nm}</div><p class="d">{d}</p></div>'
        for k, nm, d in PARTNERS)

    html = f"""<!-- PARTNERSHIP FLYER — Samson Properties x CST Pricing LLC -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Listing Recovery Team — Samson Properties</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500;1,600&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap');
{CSS}
{EXTRA_CSS}
</style>
</head>
<body>

<div class="hero{noshot}">
{hero_img}
  <div class="hero-shade"></div>
  <div class="hero-inner">
    <img class="seal" src="Gold_Standard_Logo.png" alt="">
    <h1>The Listing Recovery Team</h1>
    <p class="city">at Samson Properties</p>
    <p class="city spons-line">Sponsored by Cardinal Title</p>
    <p class="mission">Provide agents the tools to save troubled listings.</p>
    <div class="badges">
      <div class="badge creed">It is not about price, It&rsquo;s about Strategy.</div>
    </div>
  </div>
</div>

{facts}

<section>
  <div class="wrap">
    <h2 class="st ra-head">Samson&rsquo;s Recovery Team consists of elite Samson
    listing agents trained to evaluate struggling properties, identify the
    underlying problems, and provide a Roadmap&trade; to recovery.</h2>
    <div class="goals">{goals}</div>

  </div>
</section>

{band}

{fees}

<section>
  <div class="wrap">
    <h2 class="st">Introduction and Training</h2>
    <p class="ss">How Samson agents get started with the portals.</p>
    <div class="events">{schedule}</div>
  </div>
</section>

<section class="strategy">
  <div class="wrap">
    <h2 class="st">The Partnership</h2>
    <p class="ss">Built by CST Pricing LLC for Samson Properties agents.</p>
    <div class="partners">{partners}</div>
    <p class="ss close-ask">Ask about the Private Label Seller and Buyer Portals.</p>
    <div class="tri">
      <div><div class="n">Online</div><div class="t"><a href="https://caseysamson.com">caseysamson.com</a></div></div>
      <div><div class="n">Call</div><div class="t">703-508-2535</div></div>
      <div><div class="n">Email</div><div class="t sm"><a href="mailto:Casey@caseysamson.com">Casey@caseysamson.com</a></div></div>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <div class="produced">CST Pricing LLC</div>
    <div class="contact-line">In partnership with Samson Properties<span class="sep">|</span>Sponsored by Cardinal Title</div>
    <div class="copy">&copy; 2026 CST Pricing LLC. All Rights Reserved. Gold Standard Pricing Roadmap&trade;,
    Authenticated Values&trade; and Moving the Needle&trade; are marks of CST Pricing LLC.</div>
  </div>
</footer>

</body>
</html>
"""
    # The page is index.html like every other portal in this system, so the
    # folder deploys as it stands and the flyer is the site's front door.
    (out / "index.html").write_text(html)
    (out / "DEPLOY.txt").write_text(
        "PARTNERSHIP FLYER  \u2014  public\n"
        "Private Label Seller and Buyer Portals\n"
        "Samson Properties \u00d7 CST Pricing LLC, sponsored by Cardinal Title\n\n"
        "Deploy this folder to its own Netlify site. index.html is the flyer.\n"
        "Partnership_Flyer.pdf is the printable, two-page version.\n\n"
        "Links (the Buyer Report is local; the three portals are live):\n"
        f"  Seller Portal example   {MACARTHUR_SELLER}\n"
        f"  Buyer Portal example    {MACARTHUR_BUYER}\n"
        f"  Roadmap example         {MACARTHUR_ROADMAP}\n"
        f"  A Listers board         {A_LISTERS}\n"
        f"  A Listers by city      {A_LISTERS_BY_CITY}\n"
        f"  Recovery Roadmap       {HAYBINE_RECOVERY}\n")
    print(f"Flyer -> {out / 'index.html'}")


def render_pdf(out: Path):
    import asyncio
    import os
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as pw:
            exe = os.environ.get("CST_CHROME") or next(
                (str(x) for x in Path("/opt/pw-browsers").glob(
                    "chromium*/chrome-linux/chrome")), None)
            b = await pw.chromium.launch(executable_path=exe) if exe \
                else await pw.chromium.launch()
            pg = await b.new_page()
            await pg.goto((out / "index.html").resolve().as_uri())
            await pg.wait_for_timeout(1400)
            await pg.pdf(path=str(out / "Partnership_Flyer.pdf"), format="Letter",
                         print_background=True,
                         margin={"top": "0.4in", "bottom": "0.4in",
                                 "left": "0.4in", "right": "0.4in"})
            await b.close()

    asyncio.run(go())
    print(f"PDF   -> {out / 'Partnership_Flyer.pdf'}")


if __name__ == "__main__":
    d = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else HERE / "output" / "Partnership_Flyer"
    build(d)
    render_pdf(d)
