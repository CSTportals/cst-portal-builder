"""Local Market Snapshot™ — the Market Snapshot card inside one portal.

A city Market Snapshot answers "how is the market". This answers "how is
the market for homes like *this one*": the pull is bounded by area, size,
age and price around the subject, so the seller sees the homes they are
actually competing with.

Ported from the MSS handoff spec (LOCAL_MARKET_SNAPSHOT_SPEC.md) with two
deliberate changes.

1. **The Original price model.** Casey, 14 Oct 2026: "produce a market
   Snapshot from Original price model." Every price figure on this page is
   the price the home LAUNCHED at, not the price it has retreated to —
   bands, medians, dollars per foot, asking against assessed. It is the
   same convention his track record already runs on ("over-asking measured
   from the ORIGINAL list price"), and it matters most here: under the
   current-list model a home that cut 6% is scored in the band it fell
   into, which hides the one thing this page exists to show. The cut
   itself is still measured original against current, because that is
   what a cut is.

2. The shell is cached. The spec says lift the head, backbar and footer
   from a live city snapshot so the styling cannot drift. That still
   happens when the site is reachable; when it is not, the page builds
   from templates/mss_shell.html rather than failing. A portal that will
   not build because a web page was unreachable is worse than a portal
   built from last week's stylesheet.

Driven from the property JSON:

    "local_snapshot": {
        "pull": "market_pulls/502_MacArthur.txt",   # default: by prefix
        "ref": "2026-10-14",                        # default: today
        "bands": [[0, 2.3, "Under $2.3M"], ...],    # default: thirds
        "shell": "https://.../Vienna_Luxury_Market_Snapshot.html"
    }

No block and no pull file means no page and no card. The spec is explicit
about that: pointing a seller at another property's comps would be worse
than no card at all.
"""
import base64
import csv
import datetime
import json
import re
import statistics
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE / "templates"
PULLS = HERE / "market_pulls"

MSS_SITE = "https://cstmarketupdate.netlify.app"
DEFAULT_SHELL = f"{MSS_SITE}/Vienna_Luxury_Market_Snapshot.html"
SHELL_CACHE = TPL / "mss_shell.html"

# The price every figure on this page is measured at, and the fallback for
# a row the MLS exported without one.
PRICE_COL = "Original List Price"
LIST_COL = "List Price"

WON = {"A/C", "PND", "CLS"}
COMING_SOON = "C/S"

# Casey, 14 Oct 2026: "Total % under contract ((pending + (a/c*.7))/total
# listings)." A contingent contract is not a pending one — the inspection,
# the appraisal and the buyer's own sale are all still ahead of it — so it
# counts as seven tenths of a contract. A closed sale counts whole: it is a
# contract that already finished.
UC_WEIGHT = {"PND": 1.0, "CLS": 1.0, "A/C": 0.7}

# Casey's control bands, read off that weighted figure.
CONTROL = [(40, "Buyer&rsquo;s Market", "buyer"),
           (60, "Neutral Market", "mixed"),
           (999, "Seller&rsquo;s Market", "seller")]

STATUS_WORDS = {"ACT": "For Sale", "A/C": "Contingent", "PND": "Under Contract",
                "CLS": "Sold", "C/S": "Coming Soon", "WTH": "Withdrawn",
                "EXP": "Expired", "CNL": "Cancelled", "T/O": "Temp Off"}

EXTRA_CSS = """
<style>
  .badge.seller{background:#E3EDE4; color:#2F6B43;}
  .badge.mixed{background:#EDE9DF; color:#6B6354;}
  .keystat .badge{margin-top:7px;}
  table.homes{font-size:12.5px; min-width:600px;}
  table.homes td.addr{text-align:left; font-weight:600; white-space:nowrap;}
  table.homes td.cut{color:#8C4A3B;}
  table.homes td.same{color:var(--muted-2);}
  table.homes .st{display:inline-block; font-size:10px; font-weight:700;
    letter-spacing:.04em; text-transform:uppercase; padding:2px 8px;
    border-radius:20px; white-space:nowrap;}
  table.homes .st.uc{background:#E3EDE4; color:#2F6B43;}
  table.homes .st.ct{background:#EFE7D3; color:#8A6A2E;}
  table.homes .st.on{background:#EDE9DF; color:#6B6354;}
  .table-note{text-align:center; font-size:12px; font-style:italic;
    color:var(--muted-2); margin:-18px auto 22px; max-width:780px;}
  .rest-of-market{text-align:center; margin:0 0 4px;}
  .rest-of-market a{font-size:14px; font-weight:700; letter-spacing:.02em;
    color:var(--gold-deep); text-decoration:none;}
  .rest-of-market a:hover{text-decoration:underline;}
</style>
"""
MIN_AGE, COHORT_DAYS, RECENT_DAYS = 8, 38, 14
THIN = 5

# Casey, 14 Oct 2026: "Flags should be based on Total under contract: double
# red under 20%, 20-39% red flag, 40% to 50% yellow, 50-60% is green, over
# 60% double green." The flag used to read off the 30-day cohort, which on a
# small pull is seven or eight homes; it now reads off the whole standing
# inventory, which is the same figure the control bands use. The two line up:
# buyer's market flies red, neutral flies yellow or green, seller's market
# flies double green.
#
# ceiling (inclusive) -> (words, number of flags, colour)
TIERS = [(19, "Double Red Flag", 2, "#D42A21"),
         (39, "Red Flag", 1, "#D42A21"),
         (50, "Yellow Flag", 1, "#F2C117"),
         (60, "Green Flag", 1, "#1B9E4B"),
         (999, "Double Green Flag", 2, "#1B9E4B")]


# --------------------------------------------------------------- utilities
def money(v):
    return float(str(v or "").replace("$", "").replace(",", "").strip() or 0)


def parse_date(v):
    """MLS dates arrive as MM/DD/YYYY and MM/DD/YY, sometimes in one file."""
    v = (v or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def sqft(v):
    try:
        return float(str(v or "").replace(",", "").strip())
    except ValueError:
        return None


def dom(r):
    try:
        return int(money(r.get("DOM")))
    except (TypeError, ValueError):
        return 0


def original(r):
    """The price this home launched at.

    Falls back to the current list price only when the export left the
    original blank — better one row measured at the wrong price than a
    row silently dropped out of the counts.
    """
    v = money(r.get(PRICE_COL))
    return v if v > 0 else money(r.get(LIST_COL))


# ------------------------------------------------- the pricing model source
# Casey, 14 Oct 2026: "instead of Haymarket Luxury just do local snapshot
# based on pricing model."
#
# The Gold Standard pricing worksheet already carries a MARKET SNAPSHOT
# table — the homes around the subject, with status, days on market, age,
# size, lot, assessment, list price and sale price. That is the local
# market, already assembled, and it means a property does not need a
# separate MLS export before its portal can carry a snapshot.
#
# What the worksheet does NOT carry is dates: no listing entry date and no
# agreement date. So the 30-day cohort and the 14-day figure cannot be
# computed from it, and this path does not pretend otherwise — it reports
# the three things the worksheet does support and says which source it was
# built from.
MODEL_LIVE = {"ACT", "A/C", "PND"}
MODEL_CLOSED = {"CLS"}
MODEL_FAILED = {"WTH", "EXP", "CNL", "T/O"}


def competition_record(rows, key="Status"):
    """The Local Competition row for the Pricing Strategy's track record.

    Casey, 18 Oct 2026: "The market stats should mirror Local Competition --
    success rate, DOM, % of LP, first week sales" and "above list". Five
    measures under the team's five, from this property's own pull rather
    than a separate city export.

    Measured exactly as the team's side is, except days on market: that is
    the homes STILL on the market and how long they have sat, which is the
    reading Casey corrected twice (70.1 on MacArthur, 145.8 on Oakton). The
    other four come off the closed sales. Returns None when the pull has no
    closed sales, because four of the five would have nothing behind them.
    """
    def num(x):
        d = re.sub(r"[^0-9.]", "", str(x or ""))
        return float(d) if d else None

    def get(r, *names):
        for n in names:
            if r.get(n) not in (None, ""):
                return r[n]
        return None

    S = lambda r: str(r.get(key) or r.get(key.lower()) or "").strip().upper()
    sold, fail, live = [], [], []
    for r in rows:
        s = S(r)
        (sold if s in MODEL_CLOSED else
         fail if s in MODEL_FAILED else
         live if s in MODEL_LIVE else []).append(r)
    sold = [r for r in sold
            if num(get(r, "Close Price", "sale")) and
            num(get(r, "Original List Price", "list"))]
    if not sold:
        return None

    cp = [num(get(r, "Close Price", "sale")) for r in sold]
    olp = [num(get(r, "Original List Price", "list")) for r in sold]
    dm = [int(num(get(r, "DOM", "dom")) or 0) for r in sold]
    n = len(sold)
    week = sum(1 for x in dm if x <= 7)
    above = sum(1 for c, o in zip(cp, olp) if c > o)
    cells = []
    if sold or fail:
        cells.append(["%d%%" % round(n / (n + len(fail)) * 100),
                      "Success rate (%d of %d listings)" % (n, n + len(fail))])
    else:
        cells.append(None)
    if live:
        ld = [int(num(get(r, "DOM", "dom")) or 0) for r in live]
        cells.append(["%.1f" % (sum(ld) / len(ld)),
                      "Avg days on market (%d now listed)" % len(ld)])
    else:
        cells.append(None)
    cells.append(["%.1f%%" % (sum(cp) / sum(olp) * 100),
                  "Of original list price"])
    cells.append(["%d%%" % round(week / n * 100),
                  "Sold in the first week (%d of %d)" % (week, n)])
    cells.append(["%d%%" % round(above / n * 100),
                  "Sold above list price (%d of %d)" % (above, n)])
    return {"label": "Local Competition", "cells": cells}


def success_counts(rows, key="Status"):
    """(sold, unsold) off a pull, for the Success Rate gauge.

    Casey, 18 Oct 2026: "I am bringing in new sales and withdraws." Success
    rate is the only measure the competition set cannot give on its own --
    it needs the listings that did not sell. Sold is CLS; unsold is
    withdrawn, expired, cancelled or taken off. Both are None when the pull
    carries neither, so the gauge is left off rather than shown at 100%
    because every row in it is still for sale.
    """
    sold = unsold = 0
    for r in rows:
        s = str(r.get(key) or r.get(key.lower()) or "").strip().upper()
        sold += s in MODEL_CLOSED
        unsold += s in MODEL_FAILED
    if not (sold or unsold):
        return None, None
    return sold, unsold


def model_rows(raw):
    """Worksheet rows into the shape the rest of this module reads.

    Casey, 14 Oct 2026: "the local market is just non sold properties,
    ACT, A/C and pending." So the sold, expired and cancelled rows come
    out of the table and out of every figure.

    They are read first, though, for one thing: a home that was cancelled
    at a higher price and relisted lower is the same property, and the
    higher price is its real original list. That is the Original price
    model, and dropping those rows without reading them would have thrown
    it away.
    """
    key = lambda a: re.sub(r"[^a-z0-9]", "", (a or "").lower())
    launched = {}
    for r in raw:
        k = key(r.get("address"))
        lp = float(r.get("original") or r.get("list") or 0)
        launched[k] = max(launched.get(k, 0), lp)

    out = []
    for r in raw:
        if (r.get("status") or "").strip().upper() not in MODEL_LIVE:
            continue
        lp = float(r.get("list") or 0)
        out.append({
            "Status": (r.get("status") or "").strip().upper(),
            "Address": r.get("address", ""),
            "DOM": r.get("dom") or 0,
            "CDOM": r.get("cdom") or r.get("dom") or 0,
            "Year Built": str(r.get("built") or ""),
            "Above Grade Finished SQFT": str(r.get("sf") or ""),
            "Lot Size Square Feet": str(r.get("lot") or ""),
            "Tax Assessed Value": str(r.get("assessment") or ""),
            "Original List Price": str(launched.get(key(r.get("address")))
                                       or lp or ""),
            "List Price": str(lp or ""),
            "Listing Entry Date": r.get("entry", ""),
            "Agreement of Sale/Signed Lease Date": r.get("agreed", ""),
            "MLS #": r.get("mls", "model"),
        })
    return out


def distinct(rows):
    """One entry per address.

    A home that was cancelled twice and relisted is one property making
    three rows. Counted as three it is two failures and a listing; counted
    once it is a home still trying.
    """
    seen = {}
    for r in rows:
        seen.setdefault(re.sub(r"[^a-z0-9]", "", r["Address"].lower()), r)
    return list(seen.values())


def figures_from_model(live, ref):
    """Current Market Conditions, off the pricing model's own market table.

    Casey, 15 Oct 2026: "on seller portal current market conditions will
    come from new pricing model and that will include contract date. we
    will show 4 things: total % uc, and DOM for active and pending, % uc
    of homes listed in last 30 days (DOM 8-38), and % of total uc in last
    14 days."

    Two things changed from the MLS-pull rules:

    * The 30-day cohort is **DOM 8 to 38**, not a listing entry date in
      that window. The pricing model already carries DOM, so the cohort
      needs no dates at all and the first three figures build today.
    * The 14-day figure is a share of **every** listing, not of the
      cohort. That settles the question left open on 14 Oct: on the
      MacArthur pull the same two contracts read 14% of the cohort and 9%
      of everything. Casey wants the second.

    The consequence is that the 30 and 14 day figures no longer share a
    denominator, so the 14 day is NOT part of the 30 day and the old
    assertion between them does not apply. It also means the momentum
    rule -- p14 above half of p30 -- is comparing two different
    populations, which is why it is not used on this path.
    """
    if not live:
        raise ValueError("the pricing model has no active, contingent or "
                         "pending rows to measure")

    uc_w, _credit, counts = weighted_uc(live)
    # The control reading takes days on market as well as the share under
    # contract, so it is computed once the median is in hand, below.
    uc = [r for r in live if r["Status"] in WON]
    act = [r for r in live if r["Status"] == "ACT"]

    _med_dom = statistics.median(dom(r) for r in live)
    control, control_cls = control_of(uc_w, _med_dom)

    f = dict(
        model=True, dated=False, n=len(live), presold=0,
        thin=len(live) < THIN,
        uc=len(uc), uc_pct=round(len(uc) / len(live) * 100),
        uc_w=uc_w, control=control, control_cls=control_cls,
        n_pnd=counts.get("PND", 0), n_ac=counts.get("A/C", 0),
        n_cls=counts.get("CLS", 0),
        act=len(act), cohort=0, w30=0, w14=0, p30=0, p14=0,
        # "DOM for active and pending" — every listing still competing,
        # not the actives alone. A pending at 2 days and an active at 267
        # are both part of what this market looks like.
        act_dom=_med_dom,
        act_cut=sum(1 for r in act if original(r) > money(r["List Price"])),
        uc_cut=sum(1 for r in uc if original(r) > money(r["List Price"])),
    )
    cuts = [(original(r) - money(r["List Price"])) / original(r) * 100
            for r in act if original(r) > 0]
    reduced = [c for c in cuts if c > 0.5]
    f["act_cut"] = len(reduced)
    f["act_cut_avg"] = statistics.mean(reduced) if reduced else 0

    # Casey, 15 Oct 2026: the average reduction, under the criteria line in
    # Local Market Stats. Every competing home that has cut, not the actives
    # alone -- a home that only got its contract after cutting is the clearest
    # evidence the page has, so leaving it out would understate the market.
    allcuts = [(original(r) - money(r["List Price"])) / original(r) * 100
               for r in live if original(r) > 0]
    allred = [c for c in allcuts if c > 0.5]
    f["cut_n"] = len(allred)
    f["cut_avg"] = statistics.mean(allred) if allred else 0

    # The 30 day cohort, straight off DOM. No dates needed.
    coh = [r for r in live if MIN_AGE <= dom(r) <= COHORT_DAYS]
    if coh:
        won = [r for r in coh if r["Status"] in WON]
        f.update(cohort=len(coh), w30=len(won),
                 p30=round(len(won) / len(coh) * 100))

    # The 14 day figure needs the contract date the pricing model is
    # gaining. Its denominator is every listing, so it stands on its own.
    agreed = [parse_date(r.get("Agreement of Sale/Signed Lease Date"))
              for r in live if r["Status"] in WON]
    if not uc:
        # Nothing is under contract, so nothing went under contract in the
        # last 14 days, and no dates are needed to know it. Casey, 15 Oct
        # 2026, chose to print that 0% rather than drop the tile: it is the
        # strongest thing this page can say about a market that has stopped.
        f.update(dated=True, w14=0, p14=0)
    elif all(agreed):
        cut = ref - datetime.timedelta(days=RECENT_DAYS)
        f.update(dated=True, w14=sum(1 for a in agreed if a > cut))
        f["p14"] = round(f["w14"] / len(live) * 100)
    return f


def weighted_uc(rows):
    """Total % under contract, with contingent contracts discounted.

    The raw count treats a contingent contract and a pending one as the
    same event. They are not: one still has an inspection, an appraisal
    and often a buyer's own sale ahead of it. Both figures are reported —
    the raw count in the sentence, the weighted one as the market reading.
    """
    counts = {}
    for r in rows:
        st = (r.get("Status") or "").strip()
        counts[st] = counts.get(st, 0) + 1
    credit = sum(counts.get(st, 0) * w for st, w in UC_WEIGHT.items())
    pct = round(credit / len(rows) * 100) if rows else 0
    return pct, credit, counts


# ------------------------------------------------- the 0 to 10 scoring
# Casey, 16 Oct 2026: "Here are the 4 ratings: UC just multiply times 100,
# 29% is 2.9. DOM is on a scale, 0 DOM is 10, 60 DOM is 0, so do the math.
# Subheadline is the market: buyers under 4, neutral 4-6, sellers over 6.
# On the momentum, % in 30 days *100; 14 days is (# * 2) * 100."
#
# Four different units -- two shares of inventory, a share of a cohort and
# a count of days -- put on one 0 to 10 scale so they can be averaged and
# compared. The 14 day figure doubles before scaling because a fortnight is
# half the window the 30 day cohort gets, so doubling it is what makes the
# two momentum readings the same measure.
DOM_FLOOR = 60          # 60 days on market scores 0; 0 days scores 10


def _clamp10(x):
    return max(0.0, min(10.0, x))


def score_uc(pct):
    """Share under contract, 29% -> 2.9."""
    return _clamp10(pct / 10.0)


def score_dom(days):
    """Days on market, reversed: 0 days -> 10, 60 days -> 0."""
    return _clamp10((DOM_FLOOR - days) / (DOM_FLOOR / 10.0))


def score_30(pct):
    """The 30 day cohort, scored like the total."""
    return _clamp10(pct / 10.0)


def score_14(pct):
    """The 14 day absorption, doubled first -- half the window."""
    return _clamp10(pct * 2 / 10.0)


def strength_score(f):
    """Where the market stands: under contract and days on market."""
    return (score_uc(f["uc_w"]) + score_dom(f["act_dom"])) / 2


def momentum_score(f):
    """Which way it is moving: the 30 day cohort and the 14 day absorption.

    None where the report has neither figure -- a market with no contract
    dates and no cohort has no momentum reading, and inventing one from
    half the pair would be worse than leaving the arrow off.
    """
    parts = []
    if f.get("cohort"):
        parts.append(score_30(f["p30"]))
    if f.get("dated"):
        parts.append(score_14(f["p14"]))
    return sum(parts) / len(parts) if parts else None


# A gap this small is the same market twice, not a market on the move.
MOMENTUM_STEADY = 0.25


def momentum_read(f):
    """Improving, holding steady or declining, and by how much.

    Casey, 16 Oct 2026: "We will compare average score of UC and DOM to avg
    of 30 day and 14 day to see if market is Improving, Staying the same or
    declining... If the current market comes out 3.9 and momentum is 2.9,
    the market is declining."
    """
    mo = momentum_score(f)
    if mo is None:
        return None
    st = strength_score(f)
    gap = mo - st
    if gap > MOMENTUM_STEADY:
        word, cls = "Improving", "up"
    elif gap < -MOMENTUM_STEADY:
        word, cls = "Declining", "down"
    else:
        word, cls = "Holding Steady", "flat"
    return {"strength": st, "momentum": mo, "gap": gap,
            "word": word, "cls": cls,
            # Casey: "If homes going under contract in 30 is more than 1
            # point over %UC, then good homes are selling if they are
            # priced correctly."
            "priced_right": bool(f.get("cohort")
                                 and score_30(f["p30"]) - score_uc(f["uc_w"]) > 1)}


def control_of(pct, dom=None):
    """Who controls the market, off the strength score.

    Casey, 16 Oct 2026: "buyers under 4, neutral 4-6, sellers over 6."

    The bands used to read the share under contract alone -- under 40%
    buyers, 40 to 60 neither, over 60 sellers. They now read the average of
    that share and days on market, so a market where little is under
    contract but what sells goes fast is no longer called the same as one
    where nothing moves at all. With no days-on-market figure the old
    reading stands, which is the same number: 40% scores 4.0.
    """
    score = pct / 10.0 if dom is None else (score_uc(pct) + score_dom(dom)) / 2
    if score < 4:
        return "Buyer&rsquo;s Market", "buyer"
    if score <= 6:
        return "Neutral Market", "mixed"
    return "Seller&rsquo;s Market", "seller"


def tier_of(pct):
    for ceiling, words, n, colour in TIERS:
        if pct <= ceiling:
            return words, n, colour
    raise AssertionError("percentage above every tier ceiling")


def flag_svg(n, colour, scale=0.85):
    one = ('<svg width="%d" height="%d" viewBox="0 0 21 27" aria-hidden="true"'
           ' style="display:block">'
           '<rect x="1.5" y="0" width="1.8" height="27" rx=".9" fill="#5E5345"/>'
           '<path d="M3.3 1.6 C8 0.2 13 3.4 18.6 1.8 L18.6 11.4 '
           'C13 13 8 9.8 3.3 11.2 Z" fill="%s"/></svg>'
           % (round(20 * scale), round(26 * scale), colour))
    return '<span class="flagset">%s</span>' % (one * n)


def never_competed(row, listed_on):
    """A home cannot go under contract before it is for sale.

    These rows reached the MLS with the deal already done — new
    construction, pocket listings, office exclusives, relists carrying an
    old contract date. Left in, every one is an automatic win.
    """
    agreed = parse_date(row.get("Agreement of Sale/Signed Lease Date"))
    return agreed is not None and agreed <= listed_on


# -------------------------------------------------------------------- read
def load(path):
    raw = Path(path).read_text(encoding="utf-8-sig")
    delim = "\t" if raw.split("\n")[0].count("\t") > 2 else ","
    rows = [r for r in csv.DictReader(raw.splitlines(), delimiter=delim)
            if (r.get("MLS #") or "").strip()]
    for r in rows:                        # exports name this column both ways
        if not (r.get("City Name") or "").strip():
            r["City Name"] = r.get("City", "") or ""
    return rows


def auto_bands(rows):
    """Three bands off the data when the property JSON does not name them.

    Cut at the tertiles of the original prices and rounded to the nearest
    $100k, so the labels read like prices rather than like arithmetic.
    """
    pr = sorted(original(r) for r in rows if original(r) > 0)
    if len(pr) < 3:
        return [(0, 9999, "All listings")]
    lo = round(pr[len(pr) // 3] / 1e5) / 10
    hi = round(pr[2 * len(pr) // 3] / 1e5) / 10
    if hi <= lo:
        hi = lo + 0.5
    fmt = lambda v: ("$%.1fM" % v).replace(".0M", "M")
    return [(0, lo, "Under %s" % fmt(lo)),
            (lo, hi, "%s &ndash; %s" % (fmt(lo), fmt(hi))),
            (hi, 9999, "%s and up" % fmt(hi))]


def price_range(rows):
    """Casey, 14 Oct 2026: "Under name MacArthur on title put Min price-Max
    price." Whole dollars, not $1.9M: the low end of this pull is
    $1,850,000 and rounding it to one decimal would print a number no home
    in the table actually asks.
    """
    pr = sorted(v for r in rows if (v := original(r)) > 0)
    if not pr:
        return ""
    return "$%s &ndash; $%s" % (format(pr[0], ",.0f"), format(pr[-1], ",.0f"))


def criteria(rows, city=""):
    """Read the bounds off the pull.

    Typed by hand they eventually disagree with the rows, and the page is
    then wrong in a way nobody notices.
    """
    sf = sorted(x for r in rows if (x := sqft(r.get("Above Grade Finished SQFT"))))
    yr = sorted(int(r["Year Built"]) for r in rows
                if (r.get("Year Built") or "").strip())
    pr = sorted(v for r in rows if (v := original(r)) > 0)
    cities = sorted({(r.get("City Name") or "").strip() for r in rows
                     if (r.get("City Name") or "").strip()})
    # A two-row pull of identical condos used to read "1,499-1,499 SF, Built
    # 2016-2016, $0.4M-$0.4M". A range of one value is a value.
    def span(lo, hi, fmt):
        return fmt(lo) if lo == hi else "%s&ndash;%s" % (fmt(lo), fmt(hi))

    def price(v):
        # $0.4M is not how anyone writes $425,000.
        return ("$%.1fM" % (v / 1e6)).replace(".0M", "M") if v >= 1e6 \
            else "$%dK" % round(v / 1000.0)

    bits = [", ".join(cities)] if cities else ([city] if city else [])
    if sf:
        bits.append(span(sf[0], sf[-1], lambda v: format(v, ",.0f")) + " SF")
    if yr:
        bits.append("Built " + span(yr[0], yr[-1], str))
    if pr:
        bits.append(span(pr[0], pr[-1], price))
    return " &nbsp;&middot;&nbsp; ".join(bits)


# ----------------------------------------------------------------- figures
def figures(rows, ref, bands):
    live = [r for r in rows if (r.get("Status") or "").strip() != COMING_SOON]
    if not live:
        raise ValueError("every row in the pull is Coming Soon")
    cut = ref - datetime.timedelta(days=RECENT_DAYS)
    coh, won, w14, presold = [], [], [], 0
    for r in live:
        d = parse_date(r.get("Listing Entry Date"))
        if d is None or not (MIN_AGE <= (ref - d).days <= COHORT_DAYS):
            continue
        if never_competed(r, d):
            presold += 1
            continue
        coh.append(r)
        if (r.get("Status") or "").strip() in WON:
            won.append(r)
            a = parse_date(r.get("Agreement of Sale/Signed Lease Date"))
            if a and a > cut:
                w14.append(r)
    if not coh:
        raise ValueError("no listings in the %d-%d day window — check the pull "
                         "and the reference date" % (MIN_AGE, COHORT_DAYS))

    # Thirty days holds two fourteen-day periods, and both percentages share
    # one denominator, so the 14 day figure is part of the 30 day figure.
    assert len(w14) <= len(won), "14 day cannot exceed 30 day"
    p30 = round(len(won) / len(coh) * 100)
    p14 = round(len(w14) / len(coh) * 100)

    uc = [r for r in live if (r.get("Status") or "").strip() in WON]
    act = [r for r in live if (r.get("Status") or "").strip() == "ACT"]
    stale = [r for r in act if dom(r) > 90]
    uc_w, credit, counts = weighted_uc(live)
    _med_dom = statistics.median(dom(r) for r in act) if act else None
    control, control_cls = control_of(uc_w, _med_dom)

    def psf(rs):
        v = [original(r) / s for r in rs
             if (s := sqft(r.get("Above Grade Finished SQFT"))) and original(r)]
        return statistics.median(v) if v else 0

    def assessed(rs):
        v = [original(r) / money(r.get("Tax Assessed Value")) for r in rs
             if money(r.get("Tax Assessed Value")) > 1000 and original(r)]
        return statistics.median(v) if v else 0

    def median_price(rs):
        v = [original(r) for r in rs if original(r) > 0]
        return statistics.median(v) if v else 0

    # A cut is the only figure measured against the CURRENT list price,
    # because the cut is the distance between the two.
    cuts = [(original(r) - money(r.get(LIST_COL))) / original(r) * 100
            for r in act if original(r) > 0]
    reduced = [c for c in cuts if c > 0.5]
    _allcuts = [(original(r) - money(r.get(LIST_COL))) / original(r) * 100
                for r in live if original(r) > 0]
    _allred = [c for c in _allcuts if c > 0.5]

    return dict(
        cut_n=len(_allred),
        cut_avg=statistics.mean(_allred) if _allred else 0,
        n=len(live), presold=presold, cohort=len(coh), w30=len(won),
        w14=len(w14), p30=p30, p14=p14, thin=len(coh) < THIN,
        # Casey, 14 Oct 2026: "Last 14 days is about market deteriorating or
        # improving." Thirty days holds two fourteen-day periods, so more
        # than half the month's contracts landing in the last fortnight is
        # the market picking up.
        momentum="improve" if p14 > p30 / 2 else "deteriorate",
        uc=len(uc), uc_pct=round(len(uc) / len(live) * 100),
        uc_w=uc_w, uc_credit=credit, control=control, control_cls=control_cls,
        n_pnd=counts.get("PND", 0), n_ac=counts.get("A/C", 0),
        n_cls=counts.get("CLS", 0),
        act=len(act), over90=len(stale),
        act_dom=_med_dom or 0,
        fast=sum(1 for r in uc if dom(r) <= 5),
        uc_cut=sum(1 for r in uc if original(r) > money(r.get(LIST_COL))),
        act_cut=len(reduced),
        act_cut_avg=statistics.mean(reduced) if reduced else 0,
        uc_psf=psf(uc), stale_psf=psf(stale),
        uc_assessed=assessed(uc), stale_assessed=assessed(stale),
        uc_median=median_price(uc), act_median=median_price(act),
        bands=band_table(live, bands),
    )


def band_table(rows, bands):
    out = []
    for lo, hi, label in bands:
        g = [r for r in rows if lo <= original(r) / 1e6 < hi]
        if not g:
            continue
        u = [r for r in g if (r.get("Status") or "").strip() in WON]
        out.append(dict(label=label, n=len(g), uc=len(u),
                        pct=round(len(u) / len(g) * 100),
                        dom=statistics.median(dom(r) for r in g),
                        supply=(len(g) - len(u)) / len(u) if u else None))
    return out


def same_home(a, b):
    key = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    return bool(key(a)) and key(a) == key(b)


# Casey, 14 Oct 2026: "sorted by act, a/c, pending, then by price in status
# group and the pending by contract date."
STATUS_ORDER = {"ACT": 0, "A/C": 1, "PND": 2, "CLS": 3, "C/S": 4}
# The groups ordered by contract date rather than by price. Pending and
# closed are the done deals, and their order is a timeline.
BY_DATE = {2, 3}


def sort_key(r):
    """Status group first, then price — except pending, which runs by date.

    Pending runs newest contract first: what just happened is the part of
    the table the 14 day figure is about.
    """
    st = (r.get("Status") or "").strip()
    grp = STATUS_ORDER.get(st, 9)
    agreed = parse_date(r.get("Agreement of Sale/Signed Lease Date"))
    if grp in BY_DATE and agreed:
        return (grp, -agreed.toordinal(), -original(r))
    return (grp, 0, -original(r))


def homes_table(rows, subject="", model=False):
    """Every home in the pull, read at the price it launched at.

    Casey, 14 Oct 2026: "bring in table of all homes." The percentages
    above are a summary of this table; a seller who wants to check one
    against the other should not have to ask for the rows.
    """
    out = []
    for r in sorted(rows, key=sort_key):
        st = (r.get("Status") or "").strip()
        chip = "uc" if st in ("PND", "CLS") else "ct" if st == "A/C" else "on"
        op, lp = original(r), money(r.get(LIST_COL))
        s = sqft(r.get("Above Grade Finished SQFT"))
        # Cumulative days on market, not DOM: a home relisted to reset its
        # clock has a small DOM and a true CDOM.
        cd = int(money(r.get("CDOM") or r.get("DOM")))
        yr = (r.get("Year Built") or "").strip()
        if lp and op and lp < op - 1:
            now = ('<td class="num cut">$%s<br><span style="font-size:11px">'
                   '&minus;%.1f%%</span></td>'
                   % (format(lp, ",.0f"), (op - lp) / op * 100))
        else:
            now = '<td class="num same">&mdash;</td>'
        # The seller's own row carries the portal's spelling of the address,
        # not the MLS's.
        mine = same_home(r.get("Address"), subject)
        out.append(
            '          <tr%s><td class="num"><span class="st %s">%s</span></td>'
            '<td class="addr">%s</td><td class="num">%d</td>'
            '<td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">$%s</td>%s</tr>'
            % (' class="self"' if mine else "", chip, st,
               subject if mine else r.get("Address", ""), cd,
               format(s, ",.0f") if s else "&mdash;", yr or "&mdash;",
               format(op, ",.0f"), now))
    return "\n".join(out)


def band_rows(f):
    """Not on the page since Casey cut everything between the table and the
    footer on 14 Oct 2026. The figures are still computed in figures(), so
    restoring the band section is a template change, not a rewrite.
    """
    out = []
    for b in f["bands"]:
        supply = "&mdash;" if b["supply"] is None else "%.1f mo" % b["supply"]
        # No colour on a band with no absorption to measure: a red dot there
        # would contradict the caveat printed further down the same page.
        tone = "" if b["supply"] is None else (
            "up" if b["pct"] >= 40 else "down" if b["pct"] <= 15 else "")
        out.append(
            '          <tr><td class="market" style="white-space:nowrap">%s</td>'
            '<td class="num">%d</td><td class="num">%d</td>'
            '<td class="num %s">%d%%</td><td class="num">%.0f</td>'
            '<td class="num">%s</td></tr>'
            % (b["label"], b["n"], b["uc"], tone, b["pct"], b["dom"], supply))
    return "\n".join(out)


# ------------------------------------------------------------------- shell
FOOTER_BUYER_TEXT = "What buyers see!"


def shell(source, back_href, portal_url="", buyer_url="",
          buyer_text=FOOTER_BUYER_TEXT):
    """Head, backbar and footer from a city snapshot, so styling matches.

    Live when the site is reachable, cached when it is not.
    """
    html, origin = None, ""
    if source and str(source).startswith("http"):
        try:
            with urllib.request.urlopen(source, timeout=20) as r:
                html, origin = r.read().decode("utf-8"), str(source)
        except (urllib.error.URLError, OSError, UnicodeDecodeError):
            html = None
    elif source:
        pth = Path(source)
        if pth.exists():
            html, origin = pth.read_text(encoding="utf-8"), str(pth)
    if html is None:
        if not SHELL_CACHE.exists():
            raise FileNotFoundError(
                "no Market Snapshot shell: %s is unreachable and there is no "
                "cache at %s" % (source, SHELL_CACHE))
        html = SHELL_CACHE.read_text(encoding="utf-8")
        origin = "cache (%s)" % SHELL_CACHE.name

    head = html[:html.index("</head>") + len("</head>")]
    head = re.sub(r"<title>.*?</title>",
                  "<title>Local Market Snapshot™ &mdash; "
                  "The Casey Samson Team</title>", head, count=1, flags=re.S)

    m = re.search(r'<div class="backbar">.*?</div>', html, re.S)
    bar = m.group(0) if m else '<div class="backbar"></div>'
    # Casey, 15 Oct 2026: "Local snapshot should not have breadcrumbs to
    # recovery team. Make the breadcrumb back to Home of Market snapshot."
    # Then: "the problem is not the link at bottom, its the breadcrumb on
    # top that goes back to recovery team."
    #
    # The city shell's backbar carried two links and both were wrong here.
    # The right-hand one was "Look Before You Launch", the Early Warning
    # page -- a recovery pitch, and the wrong thing to put in front of a
    # seller reading their own market. The left-hand one was a bare
    # relative "index.html", which only means the seller's portal when the
    # page is sitting inside one; opened on its own, or deployed anywhere
    # else, it resolves to whatever index happens to be next to it.
    #
    # So the whole backbar is rebuilt rather than patched. The breadcrumb
    # is the Market Snapshot home, and the portal link comes back only
    # where there is a real portal to return to, as an absolute address.
    # Casey, 16 Oct 2026: "the upper left should go to Buyer Portal."
    # Without one on file the Market Snapshot home is still the right
    # left-hand link -- it is never the recovery team.
    if buyer_url:
        home = '<a class="back" href="%s">&larr; Buyer Portal</a>' % buyer_url
    else:
        home = ('<a class="back" href="%s/#">&larr; Market Snapshot Home</a>'
                % MSS_SITE)
    portal = ""
    if portal_url:
        portal = ('<a class="back" href="%s">Back to Your Portal &rarr;</a>'
                  % portal_url)
    elif back_href and not str(back_href).startswith("index.html"):
        portal = ('<a class="back" href="%s">Back to Your Portal &rarr;</a>'
                  % back_href)
    bar = '<div class="backbar">%s%s</div>' % (home, portal)

    foot = html[html.index("<footer"):]

    # The zero-width characters in the copy line, the CST-FP comment and the
    # cst-fp meta are the SOURCE page's fingerprint. Carried over they label
    # this page as that one.
    strip_fp = lambda s: re.sub(r"<!--\s*CST-FP[^>]*?-->", "", re.sub(
        r'<meta\s+name="cst-fp"[^>]*>', "",
        re.sub("[​‌⁠﻿]+", "", s)))
    head, bar, foot = strip_fp(head), strip_fp(bar), strip_fp(foot)

    # The market-control badge and the all-homes table are this page's own,
    # so their rules go in after the copied stylesheet rather than into it.
    head = head.replace("</head>", EXTRA_CSS + "</head>")

    # The footer's strategy banner points at the featured listing's own
    # portal and buyer portal. Copied verbatim onto a different property it
    # would send this seller to somebody else's pages.
    if portal_url:
        foot = re.sub(r'(<p>Selling Homes is About Strategy.*?<a href=")[^"]*(")',
                      lambda mm: mm.group(1) + portal_url + mm.group(2),
                      foot, count=1, flags=re.S)
    if buyer_url:
        # Casey, 14 Oct 2026: "Footer should read What buyer see! Link —
        # https://buymacarthur.netlify.app". Both the address and the words
        # are replaced, so the copied footer carries this page's own.
        foot = re.sub(r'<p class="strategy-second">.*?</p>',
                      '<p class="strategy-second"><a href="%s">%s</a></p>'
                      % (buyer_url, buyer_text), foot, count=1, flags=re.S)
    else:
        foot = re.sub(r'<p class="strategy-second">.*?</p>', "", foot,
                      count=1, flags=re.S)

    # This page lives in the Seller Portal, not on the MSS site, so every
    # link the shell carried to a sibling MSS page has to become absolute or
    # it 404s once deployed. The portal back link stays relative.
    def absolutize(chunk):
        return re.sub(
            r'href="(?!https?:|mailto:|tel:|#|' + re.escape(back_href) + r')'
            r'([^"]+\.html[^"]*)"',
            lambda mm: 'href="%s/%s"' % (MSS_SITE, mm.group(1)), chunk)

    return head, absolutize(bar), absolutize(foot), origin


CONTROL_HEAD = {"buyer": "Buyers Are in Control of This Local Market",
                "mixed": "Neither Side Controls This Local Market",
                "seller": "Sellers Are in Control of This Local Market"}


def headline(f, flag):
    """Casey, 14 Oct 2026: "Headlines are about buyer or seller market."

    The flag reads off the whole standing inventory, not the 30-day
    cohort. The cohort is seven homes on this pull, and a flag that swings
    14 points on one contract is not a flag.
    """
    words = tier_of(f["uc_w"])[0]
    lead = CONTROL_HEAD[f["control_cls"]]
    article = "an" if words[0] in "AEIOU" else "a"
    if f["n"] < THIN:
        # "0 of the 2 Homes Here Are Under Contract" is the shape this used
        # to print. A market with no contracts says so in words.
        count = "None" if not f["uc"] else str(f["uc"])
        return ('%s%s &mdash; %s %s, with <span class="num">%s of the %d</span> '
                'Homes Here Under Contract'
                % (flag, lead, article.title(), words, count, f["n"]))
    return ('%s%s &mdash; %s %s, with <span class="num">%d%%</span> of All '
            'Listings Under Contract'
            % (flag, lead, article.title(), words, f["uc_w"]))


def cut_sentence(f):
    """What the homes under contract did about price.

    The handoff draft printed "Not one of the homes under contract had ever
    cut its price" whatever the data said, so a pull where one had would
    have contradicted the chart two inches above it.
    """
    if not f["uc"]:
        # "All 0 homes under contract had cut first" is what the branches
        # below produce when nothing is under contract.
        # The sentence before this one already said nothing is under
        # contract, so this one only has the price cuts left to report.
        if not f["act_cut"]:
            return "Not one of them has cut its price."
        return ("%d of them have already cut, by an average of %.1f%%."
                % (f["act_cut"], f["act_cut_avg"]))
    if f["uc"] == 1:
        head = ("The one home under contract never cut its price"
                if not f["uc_cut"] else "The one home under contract cut first")
    elif f["uc"] and not f["uc_cut"]:
        head = ("Not one of the %d homes under contract had ever cut its price"
                % f["uc"])
    elif f["uc_cut"] == f["uc"]:
        head = "All %d homes under contract had cut first" % f["uc"]
    else:
        head = ("%d of the %d homes under contract had cut first"
                % (f["uc_cut"], f["uc"]))
    if not f["act_cut"]:
        return head + ", and none of the %d still for sale have cut." % f["act"]
    if f["act_cut"] == 1:
        return (head + ", while one of the %d still for sale has cut %.1f%% "
                "and is still sitting." % (f["act"], f["act_cut_avg"]))
    return (head + ", while %d of the %d still for sale have cut by an average "
            "of %.1f%% and are still sitting." % (f["act_cut"], f["act"],
                                                  f["act_cut_avg"]))


def subhead(f):
    """Casey, 14 Oct 2026: the subhead is the 30 day and the 14 day.

    "If the last 30 days is higher then total market it means homes
    priced right and prepared are selling. Last 14 days is about market
    deteriorating or improving."

    So the 30 day is read against the Total rather than on its own — a
    cohort percentage means nothing until you know what the market behind
    it is doing — and the 14 day carries the direction.
    """
    if f.get("model"):
        if not f["cohort"]:
            return ("Every home competing with this one right now &mdash; on "
                    "the market, under contract with contingencies, or "
                    "pending. Nothing here has been listed between 8 and 38 "
                    "days, so there is no 30 day read to give.")
        # Casey, 16 Oct 2026: the direction comes off the two scores, and
        # a 30 day cohort more than a point clear of the market as a whole
        # means the homes that are right are selling.
        r = momentum_read(f)
        out = ["%d%% of the homes listed in the past 30 days are under "
               "contract" % f["p30"]]
        if r and r["priced_right"]:
            out.append("so the homes that are priced and prepared correctly "
                       "are selling")
        elif f["p30"] > f["uc_w"]:
            out.append("a little ahead of the market as a whole")
        elif f["p30"] == f["uc_w"]:
            out.append("level with the market as a whole")
        else:
            out.append("so even the newest listings are not finding buyers "
                       "any faster than the homes already sitting")
        tail = ""
        if f.get("dated"):
            tail = (" %d%% of every listing here went under contract in the "
                    "last 14 days" % f["p14"])
            if r:
                tail += ", so the market is %s." % r["word"].lower()
            else:
                tail += "."
        return "%s, %s.%s" % (out[0], out[1], tail)
    if f["thin"]:
        return ("Only %d homes came on the market here in the past 30 days, so "
                "read the 30 and 14 day figures alongside the markets around "
                "it." % f["cohort"])
    if f["p30"] > f["uc_w"]:
        read = "so buyers are buying homes that are priced and prepared well"
    elif f["p30"] < f["uc_w"]:
        read = ("so even the newest listings are not finding buyers any faster "
                "than the homes already sitting")
    else:
        read = "so new listings are selling at the market&rsquo;s own pace"
    # "of them" and not "of the total market": both percentages share the
    # 30-day cohort as their denominator, which is what keeps the 14 day
    # figure inside the 30 day one. Measured against every listing in the
    # pull the same two contracts read 9%, not 14%.
    return ("%d%% of the homes listed in the past 30 days are under contract, "
            "%s. %d%% of them went under in the last 14 days, so the market is "
            "starting to %s." % (f["p30"], read, f["p14"], f["momentum"]))


def conditions_from_figures(f, nflags, colour):
    """The Current Market Conditions block, built from this page's figures.

    Casey, 14 Oct 2026: "in current market condition, bring in Local
    snapshot." The Roadmap and the Pricing Strategy Summary used to read a
    city MSS report; they now read the homes this one is actually
    competing with, which is also what decides the pricing posture.
    """
    plain = re.sub(r"<[^>]+>", "", headline(f, ""))
    fig = "%d%%" % f["uc_w"]
    if not f.get("model"):
        stats = [(fig, "Under contract"),
                 ("%d%%" % f["p30"], "Under contract on homes listed 30 days"),
                 ("%d%%" % f["p14"], "Under contract, last 14 days")]
    else:
        # Casey's CST Market Intelligence layout, 15 Oct 2026: total,
        # then the 30 day cohort, then the 14 day absorption, with days on
        # market last -- the three shares read together and the clock
        # closes the row.
        # Casey, 16 Oct 2026: "Categorize 4 stats on market. First two are
        # % UC and Days on Market. The other two, homes listed in last 30
        # days UC and 14 days, are Market Momentum." So the pair that says
        # how the market stands comes first, then the pair that says which
        # way it is moving.
        # Casey, 18 Oct 2026: Success Rate opens Market Strength, ahead of
        # the share under contract. It is only here where the pull carries
        # the listings that did not sell; without them there is no rate to
        # state and the gauge is left off rather than guessed at.
        stats = []
        if f.get("sold") is not None and (f["sold"] + f["unsold"]):
            stats.append(("%d%%" % round(f["sold"] / (f["sold"] + f["unsold"])
                                         * 100), "Success rate"))
        stats += [(fig, "Under contract"),
                  ("%.0f" % f["act_dom"], "Days on market, active and pending")]
        if f["cohort"]:
            # Casey, 18 Oct 2026: "New rule for local -- add number of homes
            # coming on and UC, like 4 for 4, in the 30 day index." A
            # percentage off a handful of homes needs its counts beside it:
            # MacArthur's 30-day read 100% off one listing. The card picks
            # the "(n of m)" up and prints it under the figure.
            stats.append(("%d%%" % f["p30"],
                          "Under contract on homes listed 30 days (%d of %d)"
                          % (f["w30"], f["cohort"])))
        if f.get("dated"):
            stats.append(("%d%%" % f["p14"],
                          "Of all listings, under contract in 14 days"))
    _r = momentum_read(f)
    return {
        "strength_score": round(strength_score(f), 1),
        "momentum": ({"score": round(_r["momentum"], 1), "word": _r["word"],
                      "cls": _r["cls"]} if _r else None),
        "flags": nflags, "flag_hex": colour,
        "flag_color": "green" if colour == "#1B9E4B" else "red",
        "headline": plain, "headline_figure": fig,
        "sub": re.sub(r"<[^>]+>", "", subhead(f)),
        "stats": stats, "advice": demand_advice(f), "uc30_explain": uc30_explain(f),
        "update": re.sub(r"^<b>Market Update:</b>\s*", "",
                         market_update(f)).strip(),
    }


LMS_CMI_CSS = """
  /* ---- the Market Update band -------------------------------------- */
  .lms-band{position:relative; overflow:hidden; background:var(--cream,#F7F2E7);
    border-bottom:1px solid var(--gold-line); padding:40px 0 34px;}
  .lms-photo{position:absolute; top:0; right:0; height:100%; width:24%;
    object-fit:cover; opacity:.45; pointer-events:none;
    -webkit-mask-image:linear-gradient(to left,#000 30%,transparent 100%);
    mask-image:linear-gradient(to left,#000 30%,transparent 100%);}
  .lms-rail{position:absolute; left:4.5%; top:50%; transform:translateY(-50%);
    padding-left:18px; border-left:1px solid var(--gold-line);
    font-size:13px; font-weight:700; letter-spacing:.26em; line-height:2;
    text-transform:uppercase; color:var(--gold-deep);}
  .lms-bandinner{position:relative; max-width:760px; margin:0 auto;
    padding:0 20px; text-align:center;}
  .lms-meta{font-size:11.5px; font-weight:700; letter-spacing:.17em;
    text-transform:uppercase; color:var(--muted); margin:16px 0 0;}
  .lms-read{font-family:Georgia,serif; font-style:italic; font-size:17px;
    line-height:1.55; color:var(--muted); max-width:640px;
    margin:14px auto 0;}
  @media (max-width:1100px){ .lms-rail{display:none;} }
  @media (max-width:760px){ .lms-photo{display:none;} }

  /* The Market Intelligence masthead: kicker, verdict capsule, headline. */
  .lms-eyebrow{font-family:'Playfair Display',Georgia,serif; font-size:13px;
    font-weight:700; letter-spacing:.3em; text-transform:uppercase;
    color:var(--gold-deep); text-align:center; margin-bottom:5px;
    display:flex; align-items:center; justify-content:center; gap:16px;}
  .lms-eyebrow:before, .lms-eyebrow:after{content:""; height:1px; width:66px;
    background:var(--gold-line);}
  .lms-sub2{font-size:12.5px; font-weight:700; letter-spacing:.22em;
    text-transform:uppercase; color:var(--muted); margin-bottom:12px;}
  .lms-head{font-family:'Playfair Display',Georgia,serif; font-size:35px;
    font-weight:700; line-height:1.18; color:var(--ink); margin:0 0 13px;}
  /* Group headings, Casey's reference: a circled mark, the name, and the
     question the pair of cards answers. */
  .lms-cmi .cmi-glabel{gap:13px;}
  .lms-cmi .cmi-gring{display:inline-flex; align-items:center;
    justify-content:center; width:40px; height:40px; border-radius:50%;
    border:1px solid var(--gold-line); color:var(--gold-deep); flex:none;}
  .lms-cmi .cmi-gi{width:19px; height:19px;}
  .lms-cmi .cmi-gtw{display:flex; flex-direction:column; align-items:center;
    gap:2px;}
  .lms-cmi .cmi-gt{font-size:13px; letter-spacing:.14em;}
  .lms-cmi .cmi-gq{font-family:Georgia,serif; font-style:italic;
    font-size:12.5px; letter-spacing:0; text-transform:none;
    color:var(--muted); white-space:nowrap;}
  .lms-cmi .cmi-glabel{justify-content:center;}
  .lms-cmi .cmi-gscore{margin-left:2px;}
  /* Three names under one bar only work if they are allowed to wrap --
     "BUYER'S MARKET" on one line is wider than a third of the bar. */
  .lms-cmi .cmi-bands.wide{height:auto; display:flex;
    justify-content:space-between; margin-top:4px;}
  .lms-cmi .cmi-bands.wide span{position:static; font-size:9px;
    line-height:1.3; white-space:normal; width:32%; text-align:center;}
  .lms-cmi .cmi-bands.wide span:first-child{text-align:left;}
  .lms-cmi .cmi-bands.wide span:last-child{text-align:right;}
  .lms-cmi .cmi-bands .yel{color:#9A7A0C;}
  .lms-eyebrow em{font-style:normal; font-size:.62em; vertical-align:.55em;
    letter-spacing:0;}
  .lms-head .lms-who{color:var(--gold-deep);}
  .lms-cap{display:inline-flex; align-items:center; gap:9px;
    padding:7px 20px; border-radius:22px; margin:0 auto 14px;
    font-size:13px; font-weight:700; letter-spacing:.11em;
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  .lms-capwrap{text-align:center;}
  .lms-cap .flagset{display:inline-flex; gap:2px;}
  .lms-cap.red{background:#FBE9E7; color:#B3261E;}
  .lms-cap.yellow{background:#F7EFD6; color:#8A6A2E;}
  .lms-cap.green{background:#E8F1E8; color:#1B7A3D;}
  /* The snapshot is read on a screen, not folded into a print sheet, so
     the two groups sit side by side the way Casey's reference shows them
     and fall back to the Roadmap's stacked 2x2 on a narrow window. */
  /* The dashboard sits outside the page's text column: four cards need
     more room than a column of reading width. */
  .lms-dash{max-width:1160px; margin:0 auto; padding:0 24px;}
  .lms-cmi{margin-bottom:28px;}
  .lms-cmi .cmi-wrap{grid-template-columns:1fr 1fr; max-width:1120px;
    gap:40px;}
  .lms-cmi .cmi-wrap .cmi-row{max-width:none;}
  /* A group with one card should not stretch to the width of a pair. */
  .lms-cmi .cmi-wrap .cmi-row.n1{max-width:300px; margin:0 auto;}
  @media (max-width:980px){ .lms-cmi .cmi-wrap{grid-template-columns:1fr;
    max-width:560px; gap:18px;} }
  @media (max-width:640px){ .lms-eyebrow{letter-spacing:.2em; font-size:11px;}
    .lms-cap{font-size:11px; letter-spacing:.07em; padding:6px 14px;} }
"""


def _photo_src(out, name):
    """The band photo as a data URI, scaled down to banner size.

    Falls back to the plain relative name if anything about the file or the
    imaging library is not what it should be -- a missing picture is worth a
    broken <img> on one page, not a failed build.
    """
    try:
        from io import BytesIO                      # noqa: PLC0415
        from PIL import Image                       # noqa: PLC0415
        src = Path(out) / name
        if not src.exists():
            return name
        im = Image.open(src).convert("RGB")
        if im.width > 1000:
            im = im.resize((1000, round(im.height * 1000 / im.width)),
                           Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "JPEG", quality=72, optimize=True)
        return ("data:image/jpeg;base64,"
                + base64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        return name


def cmi_block(f, p, nflags, colour, meta=""):
    """Casey, 16 Oct 2026: "Change the header and whole look for the Market
    Updates."

    The band his reference draws: the market name standing on its left edge,
    the kicker between two rules, the headline with the side in control in
    gold, the verdict in a capsule, the read in italics, and the home itself
    faded into the right edge. Under it, the same CST Market Intelligence
    dashboard the Seller Roadmap carries -- imported from build_portal, not
    copied, so the two cannot drift -- widened for a screen: all three band
    names under each bar, and each group heading carrying the question that
    group answers.
    """
    from build_portal import cmi_dashboard, GAUGE_CSS   # noqa: PLC0415

    c = conditions_from_figures(f, nflags, colour)
    mname = ((p.get("market") or {}).get("name") or "").strip()
    who = {"buyer": "Buyers", "mixed": "Neither Side",
           "seller": "Sellers"}[f["control_cls"]]
    verb = "Controls" if who == "Neither Side" else "Control"
    head = "%s %s %s" % (who, verb, "the " + mname if mname
                         else "This Local Market")
    # The first word carries the whole reading, so it is the one in gold.
    head = head.replace(who, '<span class="lms-who">%s</span>' % who, 1)
    # The flag and the control reading used to run on into the headline as a
    # second clause. On its own line, in a capsule, it is a verdict.
    tier = tier_of(f["uc_w"])[0].upper()
    tone = ("red" if colour == "#D42A21" else
            "yellow" if colour == "#F2C117" else "green")
    cap = ('<div class="lms-capwrap"><div class="lms-cap %s">%s'
           '<span>%s &mdash; %s</span></div></div>'
           % (tone, flag_svg(nflags, colour, 0.62),
              re.sub("<[^>]+>", "", f["control"])
              .replace("&rsquo;", "\u2019").upper(), tier))
    # The rail only goes up when there is a market name to stand on it.
    rail = ""
    if mname:
        rail = ('<div class="lms-rail">%s</div>'
                % "<br>".join(mname.split()))
    photo = ""
    if p.get("hero_photo"):
        # Embedded, not linked: this page is read on the Market Snapshot
        # site, inside the portal and as a file on its own, and a relative
        # src only survives one of the three.
        photo = ('<img class="lms-photo" src="%s" alt="">'
                 % (_photo_src(p.get("_out"), p["hero_photo"])))
    band = ('<div class="lms-band">\n%s%s'
            '  <div class="lms-bandinner">\n'
            '    <div class="lms-eyebrow"><span>CST Market '
            'Intelligence<em>&trade;</em></span></div>\n'
            '    <div class="lms-sub2">Current Market Conditions</div>\n'
            '    <h2 class="lms-head">%s</h2>\n'
            '%s\n'
            '    <p class="lms-read">%s</p>\n'
            '    <p class="lms-meta">%s</p>\n'
            '  </div>\n</div>\n'
            % (photo, rail, head, cap, re.sub("<b>|</b>", "", subhead(f)),
               meta))
    dash = ('    <div class="lms-cmi">%s</div>\n'
            % cmi_dashboard(c.get("stats", []), c, wide=True))
    return GAUGE_CSS, band, dash


def uc30_explain(f):
    """Casey, 22 Nov 2026: "Current competition should comment on the circled
    index and explain." The circled number is Under Contract (Last 30 Days):
    of the homes listed in the last 30 days, the share already under contract
    -- the freshest read on how buyers respond to homes priced at today's
    values. Bands follow the gauge: under 25% buyers, 25-40% neutral, over 40%
    sellers."""
    coh, won, p30 = f.get("cohort") or 0, f.get("w30") or 0, f.get("p30")
    if not coh or p30 is None:
        return ""
    of = (f"{won} of the {coh} homes listed in the last 30 days" if coh > 1
          else f"{won} of the 1 home listed in the last 30 days")
    if p30 > 40:
        read = ("New listings priced at today&rsquo;s values are selling fast &mdash; buyers are "
                "acting on the right home at the right price, even where older listings sit.")
    elif p30 >= 25:
        read = ("New listings are selling at a steady pace &mdash; buyers are active, but only for "
                "homes that are priced and prepared correctly.")
    else:
        read = ("Few new listings are finding buyers &mdash; buyers are waiting, so price and "
                "condition have to be right from the first day.")
    thin = (" With only a handful of new listings, read it alongside the other gauges."
            if coh < 5 else "")
    return (f"<b>The circled number &mdash; Under Contract (Last 30 Days), {p30}%:</b> {of} "
            f"{'is' if won == 1 else 'are'} already under contract. It is the freshest measure of "
            "the market, because it shows how buyers are responding right now, not how long older "
            f"listings have been sitting. Under 25% favors buyers, over 40% favors sellers. {read}{thin}")


def demand_advice(f):
    """Casey, 15 Oct 2026: "Current market conditions follow with Advice:
    There are no or limited (whichever is appropriate) homes under contract
    indicating weak buyer demand."

    "No" and "limited" are the weak-demand cases, which is where the
    control reading already sits at under 40%. The other two bands get the
    sentence that matches them rather than a weak-demand line that the
    figures contradict.
    """
    if not f["uc"]:
        return ("<b>Advice:</b> There are no homes under contract, "
                "indicating weak buyer demand.")
    if f["control_cls"] == "buyer":
        return ("<b>Advice:</b> There are limited homes under contract, "
                "indicating weak buyer demand.")
    if f["control_cls"] == "mixed":
        return ("<b>Advice:</b> Homes are going under contract at a steady "
                "pace, indicating neither side has the advantage.")
    return ("<b>Advice:</b> Homes are going under contract quickly, "
            "indicating strong buyer demand.")


def market_stats_from_figures(f):
    """The figures the Pricing Strategy Summary and the posture rule read."""
    control = {"buyer": "Buyer's", "mixed": "Neutral",
               "seller": "Seller's"}[f["control_cls"]]
    stats = {"control": control, "under_contract": "%d%%" % f["uc_w"],
             "advice": demand_advice(f), "uc30_explain": uc30_explain(f)}
    # Casey, 18 Oct 2026: Success Rate leads both the Roadmap's five and the
    # Summary's four. It is the one measure the competition set alone cannot
    # give -- it needs the listings that did NOT sell -- so it is computed
    # only where the pull carries withdrawn, expired or cancelled rows, and
    # is left out entirely where it does not. A success rate built from
    # active listings alone would read 100% and be worthless.
    if f.get("unsold") is not None and f.get("sold") is not None:
        won, lost = f["sold"], f["unsold"]
        if won + lost:
            stats["success_rate"] = "%d%%" % round(won / (won + lost) * 100)
    if f.get("model"):
        if f["cohort"]:
            stats["uc_30"] = "%d%%" % f["p30"]
        if f.get("dated"):
            stats["uc_14"] = "%d%%" % f["p14"]
    else:
        stats["uc_30"] = "%d%%" % f["p30"]
        stats["uc_14"] = "%d%%" % f["p14"]
    return stats


def table_note(f, n_all):
    legend = ("ACT for sale &middot; A/C under contract with contingencies "
              "&middot; PND pending &middot; CLS closed")
    if f.get("model"):
        return ("The %d homes competing with this one &mdash; on the market, "
                "under contract with contingencies, or pending. Sold, expired "
                "and cancelled listings are not the competition and are not "
                "counted. %s. A home relisted after a cancellation carries "
                "the price it first launched at, so &ldquo;Now&rdquo; shows "
                "what it has given up since." % (n_all, legend))
    presold = ("" if not f["presold"] else
               " %d listing%s already under contract on the day it reached the "
               "MLS %s excluded from both sides of the ratio."
               % (f["presold"], "" if f["presold"] == 1 else "s",
                  "was" if f["presold"] == 1 else "were"))
    return ("All %d homes in the pull, highest original list price first. %s. "
            "CDOM is cumulative days on market, so a relisted home shows its "
            "true age. Every price is the price the home launched at; "
            "&ldquo;Now&rdquo; appears only where it has been cut. Active and "
            "pending listings only, with no closed, withdrawn or expired "
            "sales, so this reads lower than the public Market Snapshot for "
            "the same area.%s" % (n_all, legend, presold))


def market_update(f):
    """The paragraph under the key stats, for whichever source built them."""
    control = re.sub("&rsquo;", "’", f["control"]).lower()
    # Casey, 16 Oct 2026: the control reading is the strength score now --
    # the share under contract and days on market averaged on a 0 to 10
    # scale -- so the sentence that explains it has to say that and not the
    # old 40/60 percentage bands.
    bands = ("Market Strength scores the share under contract and the days "
             "on market from 0 to 10: under 4 the buyers are in control, "
             "4 to 6 neither side is, over 6 the sellers are.")
    if not f.get("model"):
        opening = ("%d of the %d homes in this local market listed over the "
                   "last 30 days are under contract. Across the whole standing "
                   "inventory, %d of %d homes are under contract"
                   % (f["w30"], f["cohort"], f["uc"], f["n"]))
    else:
        lead = ("" if not f["cohort"] else
                "%d of the %d homes listed 8 to 38 days ago %s under "
                "contract. " % (f["w30"], f["cohort"],
                                "is" if f["w30"] == 1 else "are"))
        opening = ("%sOf the %d homes competing with this one, %s under "
                   "contract" % (lead, f["n"],
                                 "none are" if not f["uc"] else
                                 "1 is" if f["uc"] == 1 else
                                 "%d are" % f["uc"]))
    # act_dom is the median across active AND pending, so the sentence has to
    # name that population rather than "the N still for sale".
    dom_who = ("%d homes competing here have" % f["n"] if f.get("model")
               else "%d still for sale have" % f["act"])
    # mix_phrase is empty when nothing is under contract, which used to leave
    # a space in front of the comma.
    _mix = mix_phrase(f)
    return ("<b>Market Update:</b> %s%s, which carries the market at "
            "<b>%d%%</b> and puts it in a %s. %s The %s been on the market a "
            "median of %.0f days. %s"
            % (opening, (" " + _mix) if _mix else "", f["uc_w"], control,
               bands, dom_who, f["act_dom"], cut_sentence(f)))


def mix_phrase(f):
    """Says what the raw count is made of, so the two figures reconcile.

    The sentence reports 5 of 22 and the tile reads 20%. Without the mix
    spelled out that looks like one of them is wrong.
    """
    bits = []
    if f["n_pnd"]:
        bits.append("%d pending" % f["n_pnd"])
    if f["n_ac"]:
        bits.append("%d contingent, counted at seven tenths" % f["n_ac"])
    if f["n_cls"]:
        bits.append("%d already closed" % f["n_cls"])
    if not bits:
        return ""
    if len(bits) == 1:
        return "(%s)" % bits[0]
    return "(%s and %s)" % (", ".join(bits[:-1]), bits[-1])


def psf_sentence(f):
    """Also off the page since 14 Oct 2026; kept with band_rows()."""
    if not (f["uc_psf"] and f["stale_psf"]):
        return ("Price per square foot is reported on the original asking "
                "price, so a home that has cut is still measured where it "
                "launched.")
    higher = f["uc_psf"] > f["stale_psf"]
    return ("The homes going under contract asked a <i>%s</i> original price "
            "per square foot &mdash; $%s against $%s for those past 90 days "
            "&mdash; so buyers here are capped on %s. Original asking price "
            "against assessed says the same: %.2fx sells, %.2fx sits."
            % ("higher" if higher else "lower",
               format(f["uc_psf"], ",.0f"), format(f["stale_psf"], ",.0f"),
               "total dollars, not on value" if higher
               else "value, not on total dollars",
               f["uc_assessed"], f["stale_assessed"]))


# ------------------------------------------------------------------- build
def pull_for(p, cfg):
    named = cfg.get("pull")
    # Casey, 16 Nov 2026: "Use homes in the model for current competition."
    # Rows from the model win over an MLS pull file unless a pull is named.
    if cfg.get("rows") and not named:
        return None
    if named:
        pth = Path(named)
        if not pth.is_absolute():
            pth = HERE / pth
        return pth if pth.exists() else None
    for name in ("%s.txt" % p["prefix"], "%s.csv" % p["prefix"]):
        if (PULLS / name).exists():
            return PULLS / name
    return None


def build_local_snapshot(p, out, note=print, buyer_url=None):
    """Write <prefix>_Local_Market_Snapshot.html, or return None.

    Returns the filename so the portal nav can show the card only where
    this property's own pull exists.
    """
    cfg = p.get("local_snapshot") or {}
    if cfg.get("skip"):
        return None
    ref = parse_date(cfg.get("ref")) or datetime.date.today()

    # Two sources. An MLS export carries dates, so it can answer the 30 and
    # 14 day questions. The pricing model's own Market Snapshot table does
    # not, so that path reports what the worksheet supports and says so.
    pull = pull_for(p, cfg)
    if pull is not None:
        allrows = load(pull)
        if not allrows:
            note("Local Market Snapshot SKIPPED: %s has no usable rows."
                 % pull.name)
            return None
        source = pull.name

        # Casey, 14 Oct 2026: "the local market I just non sold properties
        # act a/c and pending, stay with the stats and formulas of what we
        # agreed to in local snapshot." So an MLS export is measured the
        # same way the pricing model is -- competing listings only, the
        # four agreed figures -- and the two sources stop disagreeing about
        # the same market. An export also carries the Agreement of Sale
        # date, so the fourth figure computes here where the model path
        # often cannot.
        #
        # "include_sold": true on local_snapshot restores the older reading
        # (every row in the pull, the three MSS-style figures) for a report
        # that wants it.
        if cfg.get("include_sold"):
            rows = allrows
            bands = ([tuple(b) for b in cfg["bands"]] if cfg.get("bands")
                     else auto_bands(rows))
            try:
                f = figures(rows, ref, bands)
            except (ValueError, AssertionError) as e:
                note("Local Market Snapshot SKIPPED: %s" % e)
                return None
        else:
            rows = [r for r in allrows
                    if (r.get("Status") or "").strip() in MODEL_LIVE]
            try:
                f = figures_from_model(rows, ref)
            except ValueError as e:
                note("Local Market Snapshot SKIPPED: %s" % e)
                return None
            f["sold"], f["unsold"] = success_counts(allrows)
            f["competition_record"] = competition_record(allrows)
            gone = len(allrows) - len(rows)
            if gone:
                kinds = sorted({(r.get("Status") or "").strip()
                                for r in allrows
                                if (r.get("Status") or "").strip()
                                not in MODEL_LIVE})
                note("Local Market Snapshot: %d of the %d rows in %s are not "
                     "competing listings (%s) and are left out of both the "
                     "table and the figures."
                     % (gone, len(allrows), pull.name, ", ".join(kinds)))
    elif cfg.get("rows"):
        rows = model_rows(cfg["rows"])
        try:
            f = figures_from_model(rows, ref)
        except ValueError as e:
            note("Local Market Snapshot SKIPPED: %s" % e)
            return None
        f["sold"], f["unsold"] = success_counts(cfg["rows"], "status")
        f["competition_record"] = competition_record(cfg["rows"], "status")
        source = "pricing model"
    else:
        return None

    crit = criteria(rows, p.get("city", ""))
    head, bar, foot, origin = shell(
        cfg.get("shell", DEFAULT_SHELL), "index.html",
        portal_url=p.get("portal_url", ""),
        # The caller passes buyer_portal_url(p) so the footer credit lands on
        # the same address the portal's own Buyer Portal card points at; the
        # raw "url" field in the JSON has gone stale more than once.
        # local_snapshot.buyer_url overrides both, for a property whose
        # caseysamson.com redirect is not in place yet.
        buyer_url=(cfg.get("buyer_url") or buyer_url
                   or (p.get("buyer_portal") or {}).get("url", "")),
        buyer_text=cfg.get("buyer_text", FOOTER_BUYER_TEXT))
    words, nflags, colour = tier_of(f["uc_w"])
    flag = '<span class="city-flag">%s</span>' % flag_svg(nflags, colour)
    as_of = "%s %d, %d" % (ref.strftime("%B"), ref.day, ref.year)

    addr = ", ".join(x for x in (p["address"], p.get("city", "")) if x)
    badge = ('<span class="badge %s">%s</span>'
             % (f["control_cls"], f["control"]))
    tiles = [("%d%%" % f["uc_w"], "Total Under Contract", badge)]
    if f.get("model"):
        # Casey, 15 Oct 2026: four things, in this order.
        tiles.append(("%.0f" % f["act_dom"],
                      "Days on Market &mdash; Active and Pending", ""))
        if f["cohort"]:
            tiles.append(("%d%%" % f["p30"],
                          "Under Contract on Homes Listed 30 Days", ""))
        if f.get("dated"):
            tiles.append(("%d%%" % f["p14"],
                          "Of All Listings, Under Contract in 14 Days", ""))
    else:
        tiles += [("%d%%" % f["p30"], "Went Under in 30 Days", ""),
                  ("%d%%" % f["p14"], "Went Under in 14 Days", "")]
    tiles_html = "\n".join(
        '      <div class="keystat"><div class="num">%s</div>'
        '<div class="lbl">%s</div>%s</div>' % t for t in tiles)

    # Casey, 15 Oct 2026: 'In the Local Market stats put "Average %
    # reduction of home that reduced their list price: %" under city sq ft
    # built etc.' A market where nothing has cut is worth saying outright
    # rather than printing a 0% that reads like a missing figure.
    if f.get("cut_n"):
        cut_line = ("Average %% reduction of home reducing their price: "
                    "<b>%.1f%%</b>" % f["cut_avg"])
    else:
        cut_line = ("Not one of these %d homes has reduced its price."
                    % f["n"])

    # The cached MSS shell lays the key stats out for three, with a 60px
    # gap. A fourth tile with a long label wraps to a second row and leaves
    # a hole, so four tiles get a tighter gap and a capped width.
    # Casey, 16 Oct 2026: the four plain tiles are the CST Market
    # Intelligence dashboard now -- the same component the Seller Roadmap and
    # the Pricing Strategy Summary carry, so all three read alike.
    # Casey, 16 Oct 2026: "I am thinking this is the whole market update.
    # Lose the other header." So the band is the masthead, and the line the
    # old one carried -- what this market is, the range it covers and the
    # date it was pulled -- rides under the read.
    meta = " &middot; ".join(x for x in (addr, price_range(rows),
                                         "As of " + as_of) if x)
    # The band needs the output folder to embed the hero photo, but a copy
    # with it added is a COPY: anything set on it below is invisible to the
    # caller. Keep the real property dict so the figures this build hands
    # back land on it. Nested blocks like "market" are shared either way;
    # a new top-level key is not, which is how the Local Competition row
    # silently failed to reach the Pricing Strategy Summary.
    prop = p
    p = dict(p, _out=out)
    gauge_css, band_html, cmi_html = cmi_block(f, p, nflags, colour, meta)
    tile_css = "<style>%s%s</style>\n" % (gauge_css, LMS_CMI_CSS)

    page = """%(head)s
%(tile_css)s<body>
%(bar)s

%(band)s
<section>
  <div class="lms-dash">
%(cmi)s  </div>
  <div class="wrap">
    <p class="narrative">%(update)s</p>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="eyebrow">Local Market Stats</div>
    <p class="subhead" style="margin-bottom:6px">%(crit)s</p>
    <p class="subhead cut-line" style="margin-bottom:26px">%(cut_line)s</p>
    <div class="table-wrap">
      <table class="homes">
        <thead><tr><th class="num">Status</th><th>Address</th>
          <th class="num">%(dom_h)s</th><th class="num">Above Grade SF</th>
          <th class="num">Built</th><th class="num">%(lp_h)s</th>
          <th class="num">%(now_h)s</th></tr></thead>
        <tbody>
%(homes)s
        </tbody>
      </table>
    </div>
    <p class="table-note">%(table_note)s</p>
    <p class="rest-of-market"><a href="%(mss_site)s/#" target="_blank"
      rel="noopener">Rest of the Market &rarr;</a></p>
  </div>
</section>

%(foot)s""" % dict(
        head=head, bar=bar, foot=foot, prop=addr, crit=crit, as_of=as_of,
        tile_css=tile_css, cut_line=cut_line, cmi=cmi_html, band=band_html,
        update=market_update(f),
        homes=homes_table(rows, p["address"], model=f.get("model", False)),
        n_all=len(rows), mss_site=MSS_SITE, range=price_range(rows),
        # The column header follows the rows, not the source: homes_table
        # prints CDOM wherever the export supplies it, and the pricing
        # model's own rows carry DOM alone.
        dom_h="CDOM" if any(r.get("CDOM") for r in rows) else "DOM",
        lp_h="Original LP", now_h="Now",
        table_note=table_note(f, len(rows)))

    name = "%s_Local_Market_Snapshot.html" % p["prefix"]
    (Path(out) / name).write_text(page, encoding="utf-8")

    # Hand the figures to the rest of the build. The Roadmap's Current
    # Market Conditions block, the Pricing Strategy Summary's market tiles
    # and the posture that sets Preview and Coming Soon all read these, so
    # the whole strategy now moves with this property's own market rather
    # than with a city report.
    mk = p.setdefault("market", {})
    # Casey, 18 Oct 2026: the track record's market row is the Local
    # Competition. Computed from this property's own pull, it replaces a
    # hand-entered market_local block; where the pull has no closed sales
    # there is nothing to compute and whatever is on file stands.
    # Casey, Nov 2026: the track record keeps "Rest of <Market> over the last
    # 90 days" from the MSS; the local competition replaces it only when the
    # property asks ("track_record_local") or a pull is named.
    if f.get("competition_record") and not (cfg.get("track_record_local") or cfg.get("pull")):
        pass
    elif f.get("competition_record"):
        if prop.get("market_local"):
            note("Track record: the market row now reads Local Competition "
                 "from this property's own pull, replacing the "
                 '"%s" block on the property file.'
                 % re.sub("<[^>]+>", "", (prop["market_local"] or {}).get(
                     "label", "market_local")))
        prop["market_local"] = f["competition_record"]
    elif p.get("local_snapshot"):
        note("Track record: no closed sales in this property's pull, so the "
             "market row is not the Local Competition. Add sold and "
             "withdrawn rows to the pricing model and it computes.")
    # Casey, 17 Oct 2026, on 3101 Wheatland Farms: "Current Market Condition
    # use Oakton Luxury." Two competing homes is a true reading of this
    # property's own competition but too thin a sample to set the posture,
    # so "conditions": "market" on the local_snapshot block keeps the page
    # and hands the dashboard back to the city MSS report instead.
    if (cfg.get("conditions") or "").lower() == "market":
        note("Local Market Snapshot: built as a page, but Current Market "
             "Conditions and the pricing posture read the %s instead of "
             "these %d competing homes."
             % (p.get("market", {}).get("name") or "city market", f["n"]))
    else:
        mk["conditions"] = conditions_from_figures(f, nflags, colour)
        mk["stats"] = market_stats_from_figures(f)
        mk.setdefault("avg_dom", round(f["act_dom"]) or None)
    if f.get("model"):
        print("  local snapshot  %s  —  total %d%% UC (%d of %d competing), "
              "DOM %.0f, 30 day %s, 14 day %s  [%s, shell: %s]"
              % (name, f["uc_w"], f["uc"], f["n"], f["act_dom"],
                 ("%d%% (%d of %d)" % (f["p30"], f["w30"], f["cohort"]))
                 if f["cohort"] else "no listing 8-38 days old",
                 ("%d%%" % f["p14"]) if f.get("dated") else "no contract date",
                 source, origin))
        if not f.get("dated"):
            note("Local Market Snapshot: the pricing model carries no "
                 "contract date, so the 14 day tile is left off. Add "
                 '"agreed" to the rows under contract and it computes.')
    else:
        print("  local snapshot  %s  —  30 day %d%% (%d of %d), 14 day %d%%, "
              "inventory %d%% UC  [%s, shell: %s]"
              % (name, f["p30"], f["w30"], f["cohort"], f["p14"], f["uc_pct"],
                 source, origin))
    if f["thin"]:
        note("Local Market Snapshot: thin sample (%d homes), so the headline "
             "states counts rather than a percentage."
             % (f["n"] if f.get("model") else f["cohort"]))
    return name
