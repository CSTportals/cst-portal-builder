#!/usr/bin/env python3
"""
build_portal.py — build a complete Seller Portal from one property JSON file.

    python3 build_portal.py properties/502_macarthur.json
    python3 build_portal.py properties/502_macarthur.json --out /tmp/mac --no-pdf

Emits, into the output folder:
    index.html                  Nav page (promo-v2 style)
    <Prefix>_Roadmap.html/.pdf  Gold Standard Seller Roadmap
    <Prefix>_Buyer_Report.*     Buyer Pricing Report
    <Prefix>_Seller_Tracker.html
    Gold_Standard_Logo.png

All pricing is computed by pricing.py — no dollar figure below the worksheet
inputs is typed by hand. Run assign_agent.py afterwards to point the portal
at a listing agent.

Design notes:
  * The document CSS is lifted live from templates/*.html, so restyling the
    samples restyles every future portal. Only the <body> is generated.
  * Sections with no data are OMITTED, never filled with placeholders. A
    missing market table prints nothing; missing photos print no gallery.
  * Every omission and every pricing warning is reported to stdout at the end
    so nothing silently disappears.
"""

import argparse
import os
import json
import re
import shutil
import sys
from pathlib import Path

import watermark
from pricing import compute, money, abbrev, buyer_pools, recovery
from local_snapshot import build_local_snapshot

try:
    import segno
except ImportError:                                   # pragma: no cover
    segno = None

HERE = Path(__file__).resolve().parent
TPL = HERE / "templates"

NOTICES = []
NEWLINE = "\n"


def addr_line(p):
    """Address and city on one row, in the headline font (see README)."""
    return f'{p["address"]}, {p["city"]}, {p["state"]}'


def note(msg):
    if msg not in NOTICES:
        NOTICES.append(msg)


STREET_TYPES = {
    "st": "street", "rd": "road", "ln": "lane", "ct": "court", "dr": "drive",
    "ave": "avenue", "av": "avenue", "pl": "place", "cir": "circle",
    "ter": "terrace", "trce": "trace", "blvd": "boulevard", "pkwy": "parkway",
    "hwy": "highway", "sq": "square", "trl": "trail", "way": "way",
    # "loop" was in build_buyer_portal's copy of this list but not here, so
    # 6032 Erinblair Loop produced buyerinblairloop once the slug started
    # keeping the whole street name.
    "loop": "loop", "lp": "loop",
}


def listing_page_url(p):
    """The property's page on caseysamson.com. Only ever the URL you supply:
    the live slugs don't follow a single pattern (Verna Drive uses
    "drive ... va-22124", MacArthur uses "ave-ne ... virginia" with no ZIP),
    so any generated URL risks pointing at a page that doesn't exist. With no
    URL on file, the card and email row are left out."""
    if p.get("listing_page_url"):
        return p["listing_page_url"]
    note("Nav page / emails: View Full Listing OMITTED — no listing_page_url "
         "on file. Add it once the property has its page on caseysamson.com.")
    return None


LUXURY_MINIMUM = 1_500_000


def show_luxury(p):
    """The Luxury Experience page documents sales at $1.5M and above, so it
    only earns a place in portals at that level. Set "luxury_experience":
    true/false on the property to force it either way."""
    if "luxury_experience" in p:
        return bool(p["luxury_experience"])
    return p["values"].get("customary", 0) >= LUXURY_MINIMUM


# Until a listing has its own Buyer Portal, the seller portal and the emails
# carry the 502 MacArthur portal as a worked example -- always labelled as
# another home, never as this one. It is replaced the moment this property's
# own portal is built from its photographs and documents.
# Casey, 9 Oct 2026: example links go to caseysamson.com/market-snapshot, not
# the netlify host the site deploys to. SUPERSEDED 12 Oct 2026: "Until
# further notice buystreetname.netlify.app is the default buyer portal" — the
# example is a buyer portal like any other, so it follows the same rule
# rather than being the one link on the page that still needs a redirect.
SAMPLE_PORTAL_EMAIL = "https://samplebuyerportal.netlify.app/"   # Casey, 25 Nov 2026, potential seller email
EXAMPLE_BUYER_PORTAL = "https://buymacarthur.netlify.app"   # Casey, 23 Nov 2026: buyer portals live at buy<street>.netlify.app
EXAMPLE_BUYER_HOME = "502 MacArthur"
# Casey, 12 Oct 2026: "Seller portals need a button on the Buyer Example to
# the buyer PDF and attach PDF." The example home's own Buyer Pricing Report,
# vendored in templates/ and copied into every seller portal, so the button
# opens a local file rather than reaching for another property's folder.
EXAMPLE_BUYER_PDF = "502_MacArthur_Buyer_Report.pdf"
# The example home's own prefix. Its seller portal was carrying the example
# card as well as its own, so cards 2 and 3 were the same portal and card 2
# told that seller "this is 502 MacArthur's portal, not yours" on 502
# MacArthur's portal. is_example_home(p) drops the card there.
EXAMPLE_BUYER_PREFIX = "502_MacArthur"


def is_example_home(p):
    return p.get("prefix") == EXAMPLE_BUYER_PREFIX


def buyer_portal_ready(p):
    """Does this home's own buyer portal have real content on it yet?

    Casey, 20 Oct 2026: *"as soon as a buyer portal is updated with pictures
    and premiums, remove Example Buyer Portal."*

    Pictures and premiums are the two things that make a buyer portal the
    home's own rather than a shell. Once both are there, showing 502
    MacArthur's portal beside it stops selling the idea and starts competing
    with the real thing -- the seller clicks the example and looks at
    somebody else's house.

    Premiums count whether they are written as `features` or as
    `feature_headlines`; both render the same band.
    """
    b = p.get("buyer_portal") or {}
    # Casey, 16 Nov 2026: "recovery portals do not need example buyer portal".
    if p.get("listing_status") in ("recovery", "relaunch"):
        return True
    # Casey, 13 Nov 2026: the Sample Buyer Portal tile stays until the home has
    # real pictures -- one front photo is not a buyer portal. Four or more.
    pics = len(b.get("gallery") or []) >= 4 or len(p.get("photos") or []) >= 4
    prem = bool(b.get("features")) or bool(b.get("feature_headlines"))
    return pics and prem


_SITE_BASE = "https://caseysamson.com/market-snapshot"


def buyer_slug(p):
    """buy<full street name> — every word of it, run together.

    Casey, 12 Oct 2026: "1 buyer portal does not go to
    buyStreetname.netlify.app it goes to buyjohn.netlify.app lets goes full
    street name." This replaces the 10 Oct one-word rule, which turned
    403 John Marshall Dr NE into buyjohn and 9082 Best Bower into buybest —
    neither of which names the street a seller would recognise.

    The house number still goes, and so do the street type and the quadrant:
    403 John Marshall Dr NE -> buyjohnmarshall
    2583 Vintage Crest Ln   -> buyvintagecrest
    502 MacArthur Ave NE    -> buymacarthur
    """
    words = re.sub(r"[^A-Za-z0-9 ]", " ", p.get("address", "")).split()
    if words and words[0][0].isdigit():
        words.pop(0)                                       # house number, incl. "117A"
    spelled = set(STREET_TYPES.values())
    while words and (words[-1].lower() in STREET_TYPES
                     or words[-1].lower() in spelled
                     or words[-1].upper() in ("NE", "NW", "SE", "SW", "N", "S", "E", "W")):
        words.pop()                                        # type, then quadrant
    return ("buy" + "".join(w.lower() for w in words)) if words else None


def _slug_clash(p, slug):
    """Another property on file whose buyer slug is the same one.

    One name per street means the namespace is thin: two houses on the SAME
    street produce the same buyer address, and without an override one
    portal silently serves the other's. 6029 and 6032 Erinblair Loop are the
    first real pair. Returns that property's address, or None.
    """
    if not slug:
        return None
    here = Path(__file__).resolve().parent / "properties"
    mine = (p.get("address") or "").strip().lower()
    for f in sorted(here.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            q = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        if (q.get("address") or "").strip().lower() == mine:
            continue
        if buyer_slug(q) == slug:
            return q.get("address") or f.stem
    return None


def seller_host(p):
    """Where the Seller Portal deploys.

    Casey, 11 Oct 2026: "seller portals will be at street number street
    name.netlify.app and buyer portals will be at buy street name.netlify.app"
    Both derive from the address every build, so the property files cannot
    drift out of the convention one edit at a time.
    """
    # The Sample lives at samplesellerportal, not 502macarthur (Casey, 15 Nov
    # 2026: the sample emails linked the wrong site).
    # The address the portal was actually published at wins (4608 Freedmen,
    # 20 Nov 2026: published as 4608freedman, so 4608freedmen links failed).
    if "netlify.app" in (p.get("portal_url") or ""):
        return p["portal_url"].rstrip("/")
    s = site_slug(p)
    return f"https://{s}.netlify.app" if s else None


def buyer_host(p):
    """Where the Buyer Portal deploys — buy + the one street name.

    An explicit "deploy_to" in the buyer_portal block beats the convention.
    A site already published under Netlify's auto-generated name is a fact,
    not drift, and DEPLOY.txt has to send the folder where the site actually
    is. The override is announced so it never goes unnoticed.
    """
    s = buyer_slug(p)
    conv = f"https://{s}.netlify.app" if s else None
    set_to = ((p.get("buyer_portal") or {}).get("deploy_to") or "").rstrip("/")
    if set_to and conv and set_to != conv:
        # Casey, 19 Oct 2026, on 6029 Erinblair: "address conflict make buyer
        # portal buyerinblair2.netlify.app." The one-name rule gave 6029 and
        # 6032 Erinblair Loop the same slug, and 6032's portal is already
        # live at it. Telling Casey to "put it back on protocol" there would
        # have pointed the new folder at his published page -- so the note
        # names the other property instead of giving advice that breaks it.
        clash = _slug_clash(p, s)
        if clash:
            note(f"Buyer Portal: deploying to {set_to}. The protocol address "
                 f"{conv} belongs to {clash} — one name per street means "
                 "these two collide, so the override has to stay. Do NOT "
                 f'clear "deploy_to".')
        else:
            note(f'Buyer Portal: deploying to {set_to}, set on the property '
                 f"file, not the convention address {conv}. Rename the "
                 f'Netlify site to "{s}" and clear "deploy_to" to put it '
                 "back on protocol.")
        return set_to
    return set_to or conv



def model_competition_rows(p):
    """Casey, 16 Nov 2026: "current competition should be the competition for
    this market which is the properties I submitted with model" -- "This should
    be the rule: Use homes in the model for current competition."

    Builds local_snapshot rows from the worksheet's own homes: the competition
    (Active, A/C, Pending), the closed sales in market_map.solds, and the
    withdrawn / expired / cancelled homes in "model_unsold" (for the success
    rate). A hand-written local_snapshot (skip, rows or a named pull) wins.
    """
    ls = p.get("local_snapshot") or {}
    if ls.get("skip") or ls.get("rows") or ls.get("pull"):
        return
    code = {"Active": "ACT", "Active Under Contract": "A/C", "Pending": "PND"}
    rows = []
    for c in p.get("competition") or []:
        rows.append({"status": code.get(c.get("status"), c.get("status")), "address": c.get("address"),
                     "dom": c.get("dom") or 0, "built": c.get("built"), "sf": c.get("sf"),
                     "lot": c.get("lot"), "assessment": c.get("assessment"), "list": c.get("list")})
    for x in (p.get("market_map") or {}).get("solds") or []:
        rows.append({"status": "CLS", "address": x.get("address"), "dom": x.get("dom") or 0,
                     "list": x.get("orig_list") or x.get("list") or x.get("sale")})
    for x in p.get("model_unsold") or []:
        rows.append({"status": x.get("status", "EXP"), "address": x.get("address"),
                     "dom": x.get("dom") or 0, "list": x.get("list")})
    if not any(r["status"] in ("ACT", "A/C", "PND") for r in rows):
        return
    ms = p.get("market_snapshot") or {}
    p["local_snapshot"] = dict(ls, rows=rows, label=ls.get("label") or ms.get("label")
                               or f'{p.get("subdivision") or p.get("city", "")} Competition')
    note(f"Current Competition: {len(rows)} homes from the model "
         f"({sum(r['status'] in ('ACT','A/C','PND') for r in rows)} competing).")

def local_snapshot_file(p, out):
    """This property's own Local Market Snapshot page, if one was built.

    The three nav builders all ask this rather than testing the JSON, so a
    card can never advertise a page that is not in the folder. No pull, no
    page, no card: pointing a seller at another property's comps would be
    worse than leaving the card off.
    """
    # Casey, 18 Oct 2026, looking at MacArthur's page beside the MSS page:
    # "You don't have to recreate anything, just point to Vienna Luxury on
    # the site." Where the property reads the city market rather than its own
    # competition, the card goes to the live MSS page -- the report the team
    # publishes and keeps current -- instead of a copy of it built here that
    # is only as fresh as the last portal build.
    live = market_snapshot_url(p)
    if live:
        return live
    name = f'{p["prefix"]}_Local_Market_Snapshot.html'
    return name if (Path(out) / name).exists() else None


# The MSS publishes each market at a lowercase slug with no extension:
# https://cstmarketupdate.netlify.app/vienna_luxury_market_snapshot
MSS_SITE = "https://cstmarketupdate.netlify.app"


def market_snapshot_url(p):
    """The live MSS page for this property's market.

    Casey, 18 Oct 2026: the portal's Market Snapshot card "pulls exact data
    from the correct market" on the MSS site. The card goes to the published
    report, which the team keeps current, rather than to a copy of it built
    here that is only as fresh as the last portal build.

    This is independent of where the Roadmap gets its figures: the Roadmap
    reads the local market from the pricing model, the card reads the city
    report, and each says which it is.
    """
    slug = (p.get("market") or {}).get("slug")
    if not slug:
        note('Market Snapshot card: no "slug" on the market block, so there '
             "is no MSS page to link to. The card falls back to this "
             "property's own Local Market Snapshot page if one was built.")
        return None
    return f"{MSS_SITE}/{slug.lower()}"


# Casey, 18 Oct 2026: "For Pricing strategy back page use this track record on
# all summaries." The back page of every Pricing Strategy Summary reads this
# one file, whatever the property's own track_record is set to. Rebuild it
# from a fresh MLS export with build_cst_resales.py.
SUMMARY_TRACK_RECORD = "CST_Resales.html"

# The heading over the Pricing Strategy Summary's two-row band. The seller
# portal keeps its own, which names the record because that band is read on
# its own rather than against a competition row.
SUMMARY_BAND_TITLE = "The Casey Samson Team &mdash; Track Record Comparison"


def record_band_title(p=None):
    """The caption over the team's figures, read off the record itself.

    Both the seller portal and the Summary's back page show the same six
    figures now, so both take their title from the same place — the record
    page's own heading plus the price range out of its subtitle. Composing
    it from a property setting is what once put "Homes Sold Under $1.5M"
    over a table whose top sale was $2,250,000.
    """
    import html as _html
    src = TPL / SUMMARY_TRACK_RECORD
    raw = src.read_text(encoding="utf-8") if src.exists() else ""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
    name = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else ""
    if not name:
        note(f"Band title OMITTED — {SUMMARY_TRACK_RECORD} has no heading.")
        return ""
    sub = re.search(r'<p class="subtitle">(.*?)</p>', raw, re.S)
    period = ""
    if sub:
        halves = re.split(r"&mdash;|—", re.sub(r"<[^>]+>", "", sub.group(1)))
        period = next((h.strip() for h in halves if "$" in h), "")
    # Casey, 16 Nov 2026: "THE CASEY SAMSON TEAM — The Gold Standard of
    # Pricing Strategy" on all portals (replaces "It's about Strategy, not
    # Price", which replaced the record heading on 15 Nov).
    return "The Casey Samson Team &mdash; The Gold Standard of Pricing Strategy"


def track_record_file(p):
    """Which track-record page this property's figures and table come from.

    Casey, 12 Oct 2026: "use this as Casey Samson Track record under 3500 and
    compare to Market under 3500." A property sets "track_record" to name the
    page; otherwise the $1.5M split still decides.
    """
    name = p.get("track_record")
    if name:
        return name if name.endswith(".html") else name + ".html"
    return ("Luxury_Experience.html" if show_luxury(p)
            else "Portfolio_Under_1_5M.html")


# Nav-card copy per track-record page: (card title, one-line blurb). The
# headline under the title is NOT written here — it is read out of the page
# itself by track_record_card(), so a card can never advertise a sale count
# the page no longer has. That drift is exactly what put "41 homes sold,
# 104.4%" on a portal whose table said 37.
TRACK_RECORD_COPY = {
    "Track_Record_Under_3500.html": (
        "Track Record Under 3,500 SF",
        "Every Casey Samson Team sale under 3,500 finished square feet "
        "&mdash; days on market, original list price and final sale price, "
        "straight from MLS Bright."),
    "Track_Record_Over_3500.html": (
        "Track Record Over 3,500 SF",
        "Every Casey Samson Team sale over 3,500 finished square feet "
        "&mdash; days on market, original list price and final sale price, "
        "straight from MLS Bright."),
    "Luxury_Experience.html": (
        "Luxury Experience",
        "Every CST sale at $1.5M and above &mdash; days on market, original "
        "list price and final sale price, from MLS Bright."),
    "Portfolio_Under_1_5M.html": (
        "Portfolio Under $1.5M",
        "Every CST sale under $1.5M &mdash; days on market, original list "
        "price and final sale price, from MLS Bright."),
}


def track_record_card(p):
    """(file, title, headline, blurb) for the track-record nav card.

    The headline comes from the page's own stat band — the sale count and the
    percent-of-original-list figure — so the card and the page it opens always
    agree. Falls back to the blurb alone if the band cannot be read.
    """
    fn = track_record_file(p)
    title, blurb = TRACK_RECORD_COPY.get(
        fn, (fn[:-5].replace("_", " "), "Closed sales from MLS Bright."))
    headline, src = "", TPL / fn
    if src.exists():
        band = re.findall(r'<span class="n">([^<]+)</span>\s*'
                          r'<span class="l">([^<]+)</span>', src.read_text())
        n = next((v for v, l in band if "homes sold" in l.lower()), "")
        pct = next((v for v, l in band if "original list" in l.lower()), "")
        if n and pct:
            headline = f"{n} homes sold, {pct} of original list price"
    if not headline:
        note(f"Track-record card headline OMITTED — could not read the stat "
             f"band out of {fn}.")
    return fn, title, headline, blurb


def market_kind(p):
    """"Family" / "Luxury" etc., off the market name the property carries."""
    nm = ((p.get("market") or {}).get("name") or "").strip()
    city = (p.get("city") or "").strip()
    nm = nm.replace(city, "").replace("Market", "").strip()
    return nm or "Home"


# Casey, 17 Oct 2026: "When calculating days on market only use active,
# pending and sold. Do NOT use Coming Soon." A Coming Soon listing has not
# been on the market yet -- its days on market is zero by definition, and
# averaging those zeros in understates how long the real competition has
# been sitting. Withdrawn and expired listings come out for the same
# reason: they stopped competing.
DOM_STATUSES = {"active", "active under contract", "contract/show",
                "pending", "sold", "closed", "a/c", "act", "pnd", "cls"}


def counts_for_dom(status):
    return str(status or "").strip().lower() in DOM_STATUSES


def competition_dom(p):
    """Average days on market of the homes this one is competing against.

    Casey, 12 Oct 2026: "also bring in avg days on market from rest of homes
    on the market if you have it." Every active, under-contract and pending
    listing in the property's own competition set, which is what makes the
    team's own days-on-market figure mean anything to a seller.
    """
    comp = p.get("competition") or []
    rows = [c for c in comp
            if isinstance(c.get("dom"), (int, float))
            and counts_for_dom(c.get("status"))]
    if not rows:
        return None
    left_out = [c for c in comp
                if isinstance(c.get("dom"), (int, float))
                and not counts_for_dom(c.get("status"))]
    if left_out:
        note("Days on market: %d of the %d competing homes left out of the "
             "average (%s) \u2014 only active, pending and sold listings count."
             % (len(left_out), len(comp),
                ", ".join(sorted({str(c.get("status")) for c in left_out}))))
    return f"{sum(c['dom'] for c in rows) / len(rows):.1f}", len(rows)


def recovery_prices(p):
    """`pricing.recovery` for this property, with Casey's hand-set prices in.

    One place, so the Roadmap, the facts strip, the Summary and the seller
    email cannot quote different numbers -- which is exactly what four
    separate calls to `recovery()` invited.
    """
    v, r = p["values"], (p.get("recovery") or {})
    # Casey, 21 Nov 2026: "email should match Models Fall back and rip cord."
    # On a recovery the worksheet's Fall Back and 0-showings (Rip Cord) prices
    # ARE the two relaunch prices, used exactly as hardcoded.
    _fb, _rc = v.get("fallback_override"), v.get("deep_override")
    out = recovery(int(p["current_list"]), v["customary"],
                   v.get("customary_list"),
                   soft_override=_fb or r.get("soft_override"),
                   hard_override=_rc or r.get("hard_override"),
                   exact=bool(r.get("exact")) or bool(_fb or _rc))
    if r.get("soft_override") or r.get("hard_override"):
        note("Roadmap: relaunch prices set by hand — "
             f'{money(out["soft"])} if 2 to 3 call, {money(out["hard"])} if '
             "no one calls. The rule would have said "
             f'{money(recovery(int(p["current_list"]), v["customary"], v.get("customary_list"))["soft"])}'
             " and "
             f'{money(recovery(int(p["current_list"]), v["customary"], v.get("customary_list"))["hard"])}.')
    if out.get("warning"):
        note("Roadmap: RECOVERY RULE NOT APPLIED — " + out["warning"])
    if out["hard"] >= out["soft"]:
        note("Roadmap: the no-calls relaunch price is NOT below the 2-to-3-calls "
             f'price ({money(out["hard"])} vs {money(out["soft"])}) — the page '
             "recommends a shallower cut for the worse outcome. Check "
             '"soft_override" and "hard_override" on the property file.')
    return out


def is_recovery(p):
    """A listing already on the market, being repriced to find its pool."""
    return p.get("listing_status") == "recovery" and bool(p.get("current_list"))


def signoff(p, full=False):
    """How the seller emails sign off — in the listing agent's name.

    Casey, 12 Oct 2026: "Take me off Haybine." The three sign-offs were
    hardcoded to Casey, which also signed his name on Mastery and
    Flynnsbrooke, whose listing agents are somebody else.
    """
    a = p.get("agent") or {}
    nm = (a.get("display") or a.get("lookup") or "Casey Samson").strip()
    first = nm.split()[0]
    return (f"Warmest regards,<br>{nm}<br>The Casey Samson Team" if full
            else f"Warmest regards,<br>{first}")


def summary_name(p):
    """What the one-page print-out is called on this portal.

    Casey, 11 Oct 2026: "There are two type portals. One is normal new
    listings, one is a recovery listing so Pricing Strategy Summary on
    normal, Recovery Strategy Summary on the recovery portals."

    One helper so the button, the Roadmap CTA and the seller email can never
    call the same document three different things.
    """
    return ("Recovery Strategy Summary" if is_recovery(p)
            else "Pricing Strategy Summary")


def buyer_portal_address(p):
    """The protocol address, derived — never read from the property file."""
    slug = buyer_slug(p)
    return f"{_SITE_BASE}/{slug}" if slug else None


def buyer_portal_url(p):
    """Where every seller-facing link to the Buyer Portal points.

    Casey, 12 Oct 2026: "Until further notice buystreetname.netlify.app is
    the default buyer portal."

    So the Netlify host is the default, derived from the address on every
    build. It was the caseysamson.com/market-snapshot path, which only
    resolves once a redirect is in place — and the redirects are not in, so
    each property had to be corrected by hand as it came up. Deriving the
    host that actually serves the page fixes them all at once.

    An explicit url on the buyer_portal block still wins, for a site
    published under some other name, and says so in the omissions.
    """
    bp = p.get("buyer_portal")
    if not bp:
        return None
    canon = buyer_host(p)
    if not canon:
        note("Buyer Portal card OMITTED — no slug could be derived from the "
             f'address "{p.get("address")}".')
        return None

    set_url = (bp.get("url") or "").rstrip("/")
    if set_url and set_url != canon:
        note(f"Buyer Portal: every seller-facing link points at {set_url}, set "
             f'on the property file, not the default {canon}. Clear "url" to '
             "go back to the convention.")
        canon = set_url

    # Casey, 11 Oct 2026: "when doing a new portal leave the buyer portal link
    # out. So it is a dead link until we build a buyer portal. Period. A buyer
    # portal is built when the home is almost ready to be delivered online."
    #
    # So the link is opt-IN. It appears only when "live" is explicitly true,
    # meaning the page is built and published. Unset counts as not built —
    # which is the whole point: the old test was `is False`, so a property
    # that had never had the field set shipped a link to a page that did not
    # exist. The seller portal shows the labelled example alone instead.
    if bp.get("live") is not True:
        why = ("marked not live" if bp.get("live") is False
               else 'no "live" flag on file')
        note("Buyer Portal link OMITTED — this home has no published buyer "
             f"portal ({why}), so the seller portal shows {EXAMPLE_BUYER_HOME} "
             'alone. Set "live": true on the day the page goes up.')
        return None
    return canon


def head_of(template_name, title, extra_css=""):
    """Take everything before <body> from a sample file; swap the title."""
    s = (TPL / template_name).read_text()
    head = s.split("<body>")[0]
    head = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", head, count=1)
    if extra_css:
        head = head.replace("</style>", extra_css + "\n</style>")
    return head


PRINT_CSS = ("  @media print{ .back{display:none !important;}\n"
             "    .needle-table{break-inside:avoid; page-break-inside:avoid;}\n"
             "    .needle-frame{break-inside:avoid; page-break-inside:avoid;}\n"
             "    .needle-rail{break-inside:avoid; page-break-inside:avoid;}\n"
             "    .needle-col{break-inside:avoid; page-break-inside:avoid;} }")

# What the market takes off for, and by how much. These are the conditions
# buyers do not prefer, so they belong on every Roadmap rather than being
# priced per property; a home with its own detractor can override the list
# with a "needle_down" block of {"item", "amount"} pairs.
NEEDLE_DOWN = [
    ("Pipestem", "&minus;$35K to &minus;$50K"),
    ("Double-yellow-line traffic", "&minus;$50K to &minus;$250K"),
    ("No back yard", ""),
    ("Non-functioning floor plan", ""),
    # Casey, 24 Nov 2026: "Corner lots are a negative and so are homes with
    # less than the customary BR and BAs."
    ("Corner lot", ""),
    ("Fewer bedrooms or baths than customary", ""),
    ("Unfinished basement", "&minus;$25K to &minus;$75K depending on size"),
    ("Roof over 20 years", "&minus;$25K+ &middot; deal killer"),
]


def value_story_html(p):
    """"Understanding Today's Value" -- under Customary Value on the Roadmap.

    Casey, 21 Oct 2026, on 1360 Snow Meadow: the worksheet's purchase-year
    discount and the market's move since purchase, explained in his words.
    Everything printed comes from the "value_story" block on the property
    file; the Updated Authenticated Values table reads the values block, so
    the two can never disagree.
    """
    vs = p.get("value_story")
    if not vs:
        return ""
    v = p["values"]
    steps = "".join(
        f'<div style="display:grid;grid-template-columns:34px 1fr auto;gap:4px 14px;'
        f'align-items:baseline;padding:12px 0;border-bottom:1px solid var(--rule,#E4DCC8);">'
        f'<div style="font-family:\'Playfair Display\',Georgia,serif;font-size:22px;'
        f'color:var(--gold-deep,#8A6A2E);">{i}</div>'
        f'<div style="font-weight:700;">{s["head"]}</div>'
        f'<div style="font-weight:700;font-size:18px;color:var(--ink,#221C14);'
        f'font-variant-numeric:tabular-nums;">{s["figure"]}</div>'
        f'<div></div><div style="grid-column:2 / 4;color:var(--muted,#71695A);'
        f'font-size:14px;line-height:1.5;">{s["text"]}</div></div>'
        for i, s in enumerate(vs.get("steps", []), 1))

    def table(head, rows, strong_last=False):
        trs = "".join(
            f'<tr{" style=\"font-weight:700;\"" if strong_last and j == len(rows) - 1 else ""}>'
            f'<td style="text-align:left;">{a}</td><td>{b}</td></tr>'
            for j, (a, b) in enumerate(rows))
        return (f'<div class="table-wrap" style="margin:10px 0 0;"><table>'
                f'<thead><tr><th style="text-align:left;">{head[0]}</th><th>{head[1]}</th></tr></thead>'
                f'<tbody>{trs}</tbody></table></div>')

    meaning = table(("What This Means", "Value"),
                    [(a, b) for a, b in vs.get("meaning", [])], strong_last=True)
    updated = table(("Updated Authenticated Values&trade;", "Value"), [
        ("Dated Value", money(v["dated"])),
        ("Customary Value", money(v["customary"])),
        ("Premium Value", money(v["premium"]))])
    note(f'Roadmap: "{vs.get("title", "Understanding Today\'s Value")}" added '
         "under Customary Value.")
    return (
        '    <div style="margin:26px auto 22px;max-width:760px;background:var(--card,#fff);'
        'border:1px solid var(--gold-line,#D3B978);border-radius:10px;padding:22px 24px;">\n'
        f'      <h3 style="font-family:\'Playfair Display\',Georgia,serif;font-size:21px;'
        f'margin:0 0 6px;text-align:center;">{vs.get("title", "Understanding Today&rsquo;s Value")}</h3>\n'
        f'      {steps}\n'
        f'      {meaning}\n'
        '      <div style="margin:18px 0 6px;font-weight:700;font-family:\'Playfair Display\','
        'Georgia,serif;font-size:16px;">The Bottom Line</div>\n'
        f'      <p style="margin:0 0 4px;line-height:1.55;">{vs.get("bottom_line", "")}</p>\n'
        f'      {updated}\n'
        + (f'      <p style="margin:10px 0 0;font-size:12px;color:var(--muted,#71695A);'
           f'font-style:italic;">{vs["footnote"]}</p>\n' if vs.get("footnote") else "")
        + '    </div>\n')


def needle_down_items(p):
    """The right rail of Moving the Needle: what buyers discount for.

    An amount is optional — 'No back yard' has no standard figure, and
    inventing one would put a number in front of a seller that the market
    has not set.
    """
    rows = list(p.get("needle_down") or NEEDLE_DOWN)
    # Casey, 21 Oct 2026: "highlight double yellow traffic in discount
    # section" / "From now on I will comment on the + or - number under it."
    # The word he writes under Extraordinary Upgrades on the worksheet goes
    # on the property file as values.adjustment_note, with the signed amount
    # as values.adjustment. A minus highlights the matching discount here
    # and prints this home's own figure on it.
    v = p.get("values") or {}
    adj, adj_note = v.get("adjustment"), (v.get("adjustment_note") or "").strip()
    hit = None
    if adj_note and adj and adj < 0:
        key = adj_note.lower()
        for i, r in enumerate(rows):
            name = (r["item"] if isinstance(r, dict) else r[0]).lower()
            words = [w for w in re.findall(r"[a-z]+", key) if len(w) > 3]
            if any(w in name for w in words) or ("traffic" in key and "traffic" in name):
                hit = i
                break
        if hit is None:
            rows.insert(0, (adj_note.title(), ""))
            hit = 0
        note(f'Moving the Needle: "{adj_note}" highlighted -- '
             f"{round(v.get('adjustment_pct', 0.33) * 100)}% of a "
             f"-{money(abs(adj))} Realtor correction.")
    out = []
    for i, r in enumerate(rows):
        item, amount = (r["item"], r.get("amount", "")) if isinstance(r, dict) else r
        amt = f'<span class="amt">{amount}</span>' if amount else ""
        if i == hit:
            # Casey, 21 Oct 2026: "I only use a % of the discount that I see
            # fit. I actually decreased the customary value by 33% of the
            # discount. The 33% is next to it. This is a Realtor correction."
            # So the figure is the APPLIED share, with the correction and the
            # share named beside it.
            _pct = v.get("adjustment_pct", 0.33)
            _applied = round(abs(adj) * _pct)
            mine = (f'<span class="amt" style="color:#fff;background:#8C4A3B;'
                    f'display:inline-block;padding:1px 8px;border-radius:10px;'
                    f'margin-top:3px;">This home: &minus;{money(_applied)}</span>'
                    f'<span style="display:block;font-size:11.5px;color:#71695A;'
                    f'margin-top:3px;">{round(_pct * 100)}% of a &minus;{money(abs(adj))} '
                    f'Realtor correction, taken off Customary Value</span>')
            out.append('              <li style="background:#FBEDE8;border-left:4px solid '
                       '#8C4A3B;padding:6px 10px;border-radius:0 6px 6px 0;">'
                       f'<span class="it">{item}</span>{amt}{mine}</li>')
        else:
            out.append(f'              <li><span class="it">{item}</span>{amt}</li>')
    return "\n".join(out)

# The Buyer Pricing Guide prints as a two-page, front-and-back brochure:
# no photography, and the spacing pulled in so the URL callout and footer
# stay on page two.
BR_BANNER_CSS = """
  .site-callout a.is-url{font-size:clamp(14px,2.2vw,19px); white-space:nowrap;}
  header.masthead{padding:16px 0 14px !important; border-bottom:1px solid var(--gold-line);}
  .mast-row{
    display:flex; align-items:center; justify-content:space-between; gap:0;
    max-width:1180px; margin:0 auto; padding:0 28px;
  }
  .mast-left{width:210px; flex:0 0 210px; text-align:center; padding-right:22px;}
  .mast-left img{display:block; width:96px; margin:0 auto 2px;}
  .mast-team{
    font-size:9.5px; font-weight:700; letter-spacing:.16em; text-transform:uppercase;
    color:var(--gold-deep); line-height:1.4;
  }
  .mast-mid{
    flex:1; text-align:center; padding:0 26px;
    border-left:1px solid var(--gold-line); border-right:1px solid var(--gold-line);
  }
  .mast-mid .addr{font-family:'Playfair Display',Georgia,serif; font-size:26px; font-weight:700; margin:0;}
  .mast-mid .city{font-size:14.5px; color:var(--muted); margin:4px 0 0;}
  .mast-right{
    width:215px; flex:0 0 215px; text-align:center; padding-left:22px;
  }
  .mast-right h1.title{
    font-size:21px !important; margin:0 !important; line-height:1.25; text-align:center;
  }
  .lead-photo{max-width:1180px; margin:26px auto 0; padding:0 28px;}
  .lead-photo img{
    width:100%; max-height:430px; object-fit:cover; display:block;
    border-radius:6px; box-shadow:0 2px 10px rgba(60,45,10,.10);
  }
  @media screen and (max-width:820px){
    .mast-row{flex-direction:column; gap:12px; text-align:center;}
    .mast-left, .mast-right{width:auto; flex:none; padding:0;}
    .mast-mid{border:none; padding:0;}
  }
  @media print{
    .lead-photo{display:none !important;}
    header.masthead{padding:12px 0 10px !important;}
    .mast-row{padding:0 16px !important;}
    .mast-left{width:150px !important; flex:0 0 150px !important; padding-right:14px !important;}
    .mast-left img{width:66px !important;}
    .mast-left .mast-team{font-size:8px !important;}
    .mast-mid{padding:0 16px !important;}
    .mast-mid .addr{font-size:20px !important;}
    .mast-mid .city{font-size:12px !important;}
    .mast-right{width:150px !important; flex:0 0 150px !important; padding-left:14px !important;}
    .mast-right h1.title{font-size:16px !important;}
  }"""

BR_PRINT_CSS = """
  @media print{
    /* Authenticated Values starts page two: the cover, headlines and comps
       fill page one, and the values and upgrades get the back page. */
    section.br-values{page-break-before:always; padding-top:6px !important;}
    section.br-values .value-card ul{display:none !important;}
    section.br-values .value-card{padding:16px 14px !important;}
    section.br-values .value-num{margin-bottom:0 !important; font-size:30px !important;}
    section.br-values .value-card h3{margin-bottom:6px !important;}
    .rating-box{margin-top:22px !important;}
  }
  .br-cover{min-height:300px;}
  .br-cover .rm-hero-inner{padding:24px 26px 22px;}
  .br-cover .seal{width:48px; margin-bottom:7px;}
  .br-cover h1{font-size:clamp(24px,3.4vw,34px);}
  .br-cover .rm-badges{margin-top:14px;}
  .br-price{padding:9px 26px !important;}
  .br-price .v{font-size:25px !important;}
  .rm-site{display:block; margin-top:10px; font-size:11px; letter-spacing:.14em;
    text-transform:uppercase; color:#F0E4C4; font-weight:700;
    text-shadow:0 2px 10px rgba(0,0,0,.8);}
  @media print{
    /* The cover has to earn its place on a two-page document, so in print
       it runs about a third the height it does on screen. */
    .br-cover{min-height:290px;} .br-cover .rm-hero-inner{padding:26px 22px 22px;}
    .br-cover h1{font-size:30px;} .br-cover .city{font-size:12.5px; margin-bottom:0;}
    .br-cover .seal{width:42px; margin-bottom:8px;}
    .br-cover .bl{font-size:10px;}
    .br-cover .rm-badges{margin-top:12px;} .br-price{padding:5px 18px !important;}
    .br-price .v{font-size:19px !important;}
    .rm-site{font-size:10px; margin-top:9px;}
    .br-cover + .rm-band{padding:8px 0 24px;}
    .rm-col{padding:2px 16px;} .rm-col .k{font-size:8px; margin-bottom:2px;}
    .rm-col .v{font-size:12.5px;} .rm-col .s{font-size:9px; margin-top:1px;}
  }
  .br-stats{display:flex; flex-wrap:wrap; justify-content:center; background:var(--card);
    border:1px solid var(--rule); border-radius:6px; max-width:780px; margin:-26px auto 0;
    position:relative; z-index:3; box-shadow:0 6px 18px rgba(60,45,10,.10);
    padding:11px 6px;}
  .br-stat{flex:1 1 84px; text-align:center; padding:3px 6px;}
  .br-stat .n{font-family:'Playfair Display',Georgia,serif; font-size:16px; font-weight:700;
    color:var(--gold-deep); display:block; line-height:1.15;}
  .br-stat .l{font-size:8.5px; letter-spacing:.05em; text-transform:uppercase;
    color:var(--muted); margin-top:2px;}
  @media print{ .br-stats{margin:-18px auto 0; padding:6px 4px; break-inside:avoid;}
    .br-stat{padding:2px 5px;} .br-stat .n{font-size:12.5px;} .br-stat .l{font-size:7px;} }
  footer .agent-line{font-weight:700; font-size:13.5px; margin-bottom:3px;}
  footer .agent-line a{color:inherit; text-decoration:none;}
  footer .agent-line .sep{font-weight:400; color:var(--muted-2); margin:0 8px;}
  .agent-card{display:flex; align-items:center; gap:26px; max-width:820px;
    margin:0 auto; background:var(--card); border:1px solid var(--gold-line);
    border-radius:10px; padding:20px 26px; text-align:left;}
  .agent-card img{width:168px; border-radius:8px; flex:none; display:block;}
  .ac-name{font-family:'Playfair Display',Georgia,serif; font-size:21px; font-weight:700;
    margin:0 0 2px;}
  .ac-team{font-size:11.5px; letter-spacing:.09em; text-transform:uppercase;
    color:var(--gold-deep); font-weight:700; margin-bottom:12px;}
  .ac-row{font-size:13.5px; margin-bottom:3px;}
  .ac-row b{display:inline-block; min-width:124px;}
  .ac-ph{font-variant-numeric:tabular-nums;}
  .ac-sep{color:var(--muted-2); margin:0 7px;}
  .ac-row a{color:inherit;}
  .ac-office{font-size:12px; color:var(--muted); margin-top:10px;}
  footer.card-foot{background:transparent !important; border-top:none !important;}
  footer.card-foot .copy{margin-top:14px;}
  @media (max-width:640px){ .agent-card{flex-direction:column; text-align:center;}
    .ac-row b{display:block; min-width:0;} }
  @media print{ .agent-card{padding:14px 20px; gap:20px; break-inside:avoid;}
    .agent-card img{width:132px;} .ac-name{font-size:18px;}
    .ac-team{font-size:10px; margin-bottom:9px;} .ac-row{font-size:11.5px;}
    .ac-office{font-size:10px; margin-top:7px;}
    footer.card-foot{padding:14px 0 10px !important;} }
  /* The web page's offer of its own printable twin. It must never appear in
     the PDF -- the PDF is rendered from this very page, and a "download this
     as a PDF" link printed inside the PDF is a loop. */
  .br-pdf{padding:4px 0 26px; text-align:center;}
  .br-pdf-link{display:inline-block; text-decoration:none; font-size:13.5px;
    font-weight:700; letter-spacing:.02em; color:var(--gold-deep);
    border:1.5px solid var(--gold-line); border-radius:6px; padding:11px 22px;
    background:#FFFDF8;}
  @media print{ .br-pdf{display:none !important;} }

  .br-loves{padding-top:6px !important;}
  .br-loves-list{list-style:none; margin:0 auto; padding:0; max-width:780px;
    columns:2; column-gap:34px; font-size:12px; color:var(--muted);}
  /* A gold rule instead of a bullet glyph: the headless PDF renderer has no
     reliable bullet in this font stack and draws a missing-glyph box. */
  .br-loves-list li{padding:2px 0 2px 12px; border-left:2px solid var(--gold-line);
    margin-bottom:5px; break-inside:avoid; line-height:1.45;}
  @media (max-width:560px){ .br-loves-list{columns:1;} }
  @media print{ .br-loves{padding:10px 0 4px !important;}
    .br-loves-list{font-size:10.5px; column-gap:28px;}
    .br-loves-list li{padding:2px 0 2px 10px; margin-bottom:4px; line-height:1.4;} }
  /* Scan-to-open QR, top right of page one. Over the photo cover it needs
     its own white tile to stay scannable; in the plain masthead it sits
     under the title. */
  .br-qr-corner{position:absolute; top:16px; right:18px; z-index:3;
    text-align:center; width:84px;}
  .br-qr-corner .bqc-tile{width:84px; height:84px; background:#fff;
    border-radius:5px; padding:6px; box-sizing:border-box;
    box-shadow:0 2px 8px rgba(0,0,0,.18);
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  .br-qr-corner .bqc-tile svg{width:100%; height:100%; display:block;
    shape-rendering:crispEdges;}
  .br-qr-corner .bqc-cap{margin-top:5px; font-size:8.5px; font-weight:700;
    letter-spacing:.11em; text-transform:uppercase; color:var(--gold-deep);}
  .br-qr-corner.on-photo .bqc-cap{color:#F3ECDC;
    text-shadow:0 1px 3px rgba(0,0,0,.55);}
  /* The plain (condensed) masthead is a flex row and the report is fitted
     to two pages, so the QR here must add as little height as possible: it
     sits beside the title, small, with the caption dropped. */
  .mast-right{display:flex; align-items:center; justify-content:flex-end; gap:12px;}
  .mast-right .br-qr-corner{position:static; width:auto; flex:none;}
  /* The caseysamson.com address is a longer string than the old deploy URL,
     so the code carries 41 modules instead of 37. At 58px those modules fall
     below what a phone can read, hence 76. */
  .mast-right .br-qr-corner .bqc-tile{width:76px; height:76px; padding:4px;
    box-shadow:none; border:1px solid var(--gold-line);}
  .mast-right .br-qr-corner .bqc-cap{display:none;}
  @media print{
    .br-qr-corner{top:14px; right:15px; width:76px;}
    .br-qr-corner .bqc-tile{width:76px; height:76px; box-shadow:none;
      border:1px solid rgba(0,0,0,.12);}
  }

  .br-fhs{display:grid; grid-template-columns:1fr 1fr; gap:16px 34px; max-width:780px;
    margin:0 auto;}
  .br-fh{border-top:2px solid var(--gold-line); padding-top:10px;}
  .br-fh h3{font-family:'Playfair Display',Georgia,serif; font-size:17px; font-weight:700;
    margin:0 0 4px; line-height:1.25;}
  .br-fh p{margin:0; font-size:12.5px; color:var(--muted); line-height:1.6;}
  @media (max-width:560px){ .br-fhs{grid-template-columns:1fr;} }
  /* Features & Updates, the same block the Buyer Portal carries. */
  .br-fcs{display:grid; grid-template-columns:1fr 1fr; gap:14px 34px;
    max-width:780px; margin:0 auto;}
  .br-fc h3{font-size:11.5px; font-weight:700; letter-spacing:.13em;
    text-transform:uppercase; color:var(--gold-deep); margin:0 0 7px;
    padding-bottom:5px; border-bottom:1px solid var(--gold-line);}
  .br-fc ul{margin:0; padding-left:17px; font-size:12.5px; line-height:1.55;
    color:var(--ink);}
  .br-fc li{margin-bottom:4px;}
  @media (max-width:560px){ .br-fcs{grid-template-columns:1fr;} }
  @media print{
    .br-fcs{gap:12px 30px;} .br-fc{break-inside:avoid;}
    .br-fc h3{font-size:10.5px; margin-bottom:5px;}
    .br-fc ul{font-size:11px; line-height:1.45;}
    section.br-feats{padding:20px 0 14px !important; break-inside:avoid;}
  }
  @media print{ .br-fhs{gap:20px 34px;} .br-fh{padding-top:12px; break-inside:avoid;}
    .br-fh h3{font-size:15.5px; margin-bottom:6px;}
    .br-fh p{font-size:11.5px; line-height:1.55;}
    section:has(.br-fhs){padding:26px 0 18px !important;} }

  @media print{
    .photo-gallery{display:none !important;}
    section:has(.photo-gallery){display:none !important; padding:0 !important;}
    header.masthead{padding:20px 0 16px !important;}
    section{padding:14px 0 !important;}
    .table-wrap{margin-bottom:10px !important;}
    tbody td{padding:6px 12px !important;}
    thead th{padding:7px 12px !important;}
    p.section-sub{margin-bottom:14px !important;}
    .value-card{padding:14px 16px !important;}
    .value-num{font-size:24px !important; margin-bottom:8px !important;}
    .rating-box{margin-top:16px !important; padding-top:12px !important;}
    .sf-col li{padding:2px 0 !important; line-height:1.3 !important;}
    .sf-label{padding:9px 0 4px !important;}
    .site-callout{padding:18px 20px !important;}
    .site-callout a{font-size:26px !important;}
    .site-callout a.is-url{font-size:15px !important; white-space:nowrap !important;}
    footer{padding:16px 0 18px !important;}
    footer .copy{margin-top:8px !important;}
    .rating-box h3{margin-bottom:4px !important;}
    .rating-box h3, .rating-headline{break-after:avoid; page-break-after:avoid;}
    .sf-label{break-after:avoid; page-break-after:avoid;}
  }"""

ALERT_CSS = """  .alert-box{max-width:700px; margin:26px auto 0; padding:20px 26px; background:#F3EAD3;
    border:1px solid var(--gold-line); border-radius:8px; text-align:center;}
  .alert-box h3{font-family:'Playfair Display',Georgia,serif; font-size:17px; margin:0 0 10px; color:var(--gold-deep);}
  .alert-box p{font-size:14px; margin:0 0 10px;}
  .alert-box p:last-child{margin-bottom:0;}
  .pending{color:var(--muted-2); font-style:italic;}"""


def sf(v):
    return f"{v:,}" if isinstance(v, (int, float)) else v


def lot_cell(v):
    """Lot size for a table cell; unknown or zero shows as a dash."""
    # Casey, 29 Oct 2026: "take out SF on lot" -- the number alone.
    return "&mdash;" if v in (0, None, "", "&mdash;") else sf(v)


def size_cell(v):
    return "&mdash;" if v in (0, None, "", "&mdash;") else sf(v)


def comp_rows(rows, cls="", extra=None, p=None):
    """A comp row may carry an optional 7th element: a URL. When present the
    address becomes a link. Supply real URLs — nothing here builds or guesses
    them, because a comp pointing at the wrong house is worse than no link.

    Casey, 28 Oct 2026: "In seller road map appraisal comps should have
    Adjusted PPSF and % of assessment." With `extra` (a dict address ->
    adjusted value, from comps.adjusted), two cells follow the price:
    Adjusted PPSF = adjusted value / that home's SF (the sale price when no
    adjusted value is on file), and % of assessment = sale price /
    assessment. A row whose "sale" is None (the subject) uses its value."""
    out = []
    for r in rows:
        addr, built, size, lot, assessment, sale = r[:6]
        url = r[6] if len(r) > 6 else None
        _dot = ""
        if p is not None and not cls:   # comps only -- not the subject or averages
            import market_map as _mm
            _dot = _mm.grade_dot(p, addr)
        if url:
            addr = (f'<a href="{url}" target="_blank" rel="noopener" '
                    f'style="color:inherit;">{addr}</a>')
        sale_cell = "&mdash;" if sale in (None, "", 0) else f"<b>{money(sale)}</b>"
        if cls:
            sale_cell = sale_cell.replace("<b>", "").replace("</b>", "")
        c = f' class="{cls}"' if cls else ""
        out.append(
            f'          <tr{c}><td class="addr-cell">{_dot}{addr}</td><td>{built}</td>'
            f"<td>{size_cell(size)}</td><td>{lot_cell(lot)}</td><td>{money(assessment)}</td>"
            f"<td>{sale_cell}</td>"
            + (_extra_cells(r, extra) if extra is not None else "") + "</tr>")
    return "\n".join(out)


def _extra_cells(r, extra):
    addr, built, size, lot, assessment, sale = r[:6]
    import html as _hh
    _plain = _hh.unescape(re.sub(r"<[^>]+>", "", str(addr)))
    _e = extra.get(_plain) or extra.get(addr)
    # Casey, 29 Oct 2026: "Make a point of using my adjusted PPSF in the
    # summary of age and size and price range. I adjust for size and age."
    # A {"ppsf": n} entry is his worksheet figure, printed as given.
    if isinstance(_e, dict):
        ppsf = f"${_e['ppsf']:,.0f}" if _e.get("ppsf") else "&mdash;"
        base = sale
    else:
        adj = _e or sale
        ppsf = f"${adj / size:,.0f}" if adj and size else "&mdash;"
        base = sale or _e
    pct = f"{base / assessment * 100:.0f}%" if base and assessment else "&mdash;"
    return f"<td>{ppsf}</td><td>{pct}</td>"


def cap_twelve(rows, p=None, s=None, key="list"):
    if len(rows) <= 12:
        return rows
    ref = (getattr(s, "coming_soon", 0) if s is not None else 0) or \
          ((p or {}).get("values") or {}).get("customary") or 0
    keep = sorted(rows, key=lambda c: abs((c.get(key) or 0) - ref))[:12]
    ids = {id(c) for c in keep}
    return [c for c in rows if id(c) in ids]


def competition_block(comp, p=None, s=None):
    """Competition table + stat line. PMA standard: Active, A/C and Pending only.

    The subject leads the table so the seller reads their own home against the
    competition on the same terms -- age, size, assessment and price. Lot size
    came out: on these segments it varies far more than it explains, and the
    assessment is what buyers and the online estimates actually anchor on."""
    order = {"Active": 0, "Active Under Contract": 1, "Pending": 2}

    # Bright exports the same three states under several spellings. Without
    # normalising, an unrecognised status drops out of the stat line while
    # still counting toward the total, so the page says "Ten homes" over
    # counts that add to six.
    aliases = {
        "act": "Active", "active": "Active",
        "a/c": "Active Under Contract", "ac": "Active Under Contract",
        "active under contract": "Active Under Contract",
        "active/contract": "Active Under Contract",
        "contract/show": "Active Under Contract",
        "cnts": "Active Under Contract",
        "pnd": "Pending", "pending": "Pending", "under contract": "Pending",
    }
    comp = list(comp)
    for c in comp:
        key = str(c.get("status", "")).strip().lower()
        canon = aliases.get(key)
        if canon:
            c["status"] = canon
        elif c.get("status") not in order:
            note(f'Roadmap: competition status "{c.get("status")}" for '
                 f'{c.get("address")} is not Active, Active Under Contract or '
                 "Pending — it is listed but left out of the counts.")

    rows = sorted(comp, key=lambda c: (order.get(c["status"], 9), -c.get("list", 0)))
    # Casey, 27 Nov 2026: "Only 12 homes listed under Current market map" --
    # the 12 priced closest to this home's Coming Soon price.
    rows = cap_twelve(rows, p, s)
    counts = {k: sum(1 for c in rows if c["status"] == k) for k in order}
    stat = "<span class=\"sep\">|</span>".join(
        f"{counts[k]} {k}" for k in order)
    def _assess(c):
        a = c.get("assessment")
        return money(a) if a else "&mdash;"

    body = "\n".join(
        f'          <tr><td><b>{c["status"]}</b></td>'
        f'<td class="addr-cell">{c["address"]}</td><td>{c["dom"]}</td>'
        f'<td>{c["built"] or "&mdash;"}</td><td>{size_cell(c["sf"])}</td><td>{_assess(c)}</td>'
        f'<td><b>{money(c["list"])}</b></td></tr>' for c in rows)

    # The average of the competition, so the subject is read against the
    # group rather than against four separate rows. Zeros are missing data,
    # not values, so each column averages only what is actually on file.
    if p and rows:
        def _avg(key):
            vals = [c.get(key) for c in rows if c.get(key)]
            return round(sum(vals) / len(vals)) if vals else None
        _a = {k: _avg(k) for k in ("dom", "built", "sf", "assessment", "list")}
        body = body + (
            f'\n          <tr class="total-row"><td><b>Average</b></td>'
            f'<td class="addr-cell"><b>Competition Average</b></td>'
            f'<td>{_a["dom"] if _a["dom"] is not None else "&mdash;"}</td>'
            f'<td>{_a["built"] if _a["built"] is not None else "&mdash;"}</td>'
            f'<td>{size_cell(_a["sf"]) if _a["sf"] else "&mdash;"}</td>'
            f'<td>{money(_a["assessment"]) if _a["assessment"] else "&mdash;"}</td>'
            f'<td><b>{money(_a["list"]) if _a["list"] else "&mdash;"}</b></td></tr>')

    # The subject sits at the foot of the list, in the same columns.
    if p and p.get("subject"):
        _sj = p["subject"]
        # On a recovery portal the subject is already on the market, so the
        # row has to show what it is listed at NOW and how long it has sat.
        # Showing the recommended price here would put the home at the bottom
        # of the table when it is actually at the top.
        if p.get("listing_status") == "recovery" and p.get("current_list"):
            _price = money(p["current_list"])
        else:
            _price = money(s.coming_soon) if s is not None else "&mdash;"
        _dom = p.get("days_on_market") or "&mdash;"
        body = body + (
            f'\n          <tr class="total-row"><td><b>Subject</b></td>'
            f'<td class="addr-cell"><b>{p["address"]}</b></td><td>{_dom}</td>'
            f'<td>{_sj.get("built", "&mdash;")}</td><td>{size_cell(_sj.get("sf"))}</td>'
            f'<td>{money(_sj["assessment"]) if _sj.get("assessment") else "&mdash;"}</td>'
            f'<td><b>{_price}</b></td></tr>')
        if any(not c.get("assessment") for c in rows):
            note("Roadmap: competition assessments missing for "
                 + ", ".join(c["address"] for c in rows if not c.get("assessment"))
                 + " — shown as a dash until the figures are on file.")
    total = len(rows)
    if total == 0:
        # No qualifying competition at all — say so plainly rather than
        # printing an empty table with a zero count.
        note("Roadmap: competition table OMITTED — no Active, Active Under "
             "Contract or Pending listings in the segment.")
        return ("", "",
                "There is no active competition in this segment &mdash; no Active, "
                "Active Under Contract or Pending listings.")

    word = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
            7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
            12: "Twelve"}.get(total, str(total))
    parts = [f"{counts[k]} {k.lower()}" for k in order if counts[k]]
    if len(parts) > 1:
        summary = ", ".join(parts[:-1]) + " and " + parts[-1]
    else:
        summary = parts[0] if parts else "none"
    lede = (f"{word} home{'s' if total != 1 else ''} make"
            f"{'' if total != 1 else 's'} up the current competition &mdash; {summary}.")
    return stat, body, lede


# ---------------------------------------------------------------- gauges
# Casey, 15 Oct 2026: "Add a horizontal market gauge beneath each statistic
# and description... RED (Buyer's/Declining), YELLOW (Neutral), GREEN
# (Seller's/Improving)... a black triangular pointer marking the actual
# statistic... threshold values beneath each gauge... The objective is for
# sellers to understand market conditions visually in less than five
# seconds."
#
# One component, two surfaces: the Seller Roadmap's Current Market
# Conditions and the Pricing Strategy Summary's market tiles both call
# gauge_html(), so the two can never disagree about where a number sits.
#
# "lo" is the value at the left end of the bar and "hi" the value at the
# right end, so a measure that reads better descending -- days on market,
# where fewer is stronger -- is expressed by putting the larger number on
# the left rather than by a separate reversed drawing path. Everything
# else (segment widths, pointer position, which band a figure falls in)
# falls out of that one pair.
#
# Nothing here is specific to this property or this market: the figures
# arrive from the report's own data and the thresholds are the standing
# CST bands.
# Scales are Casey's, 15 Oct 2026 (CST Market Intelligence master
# instructions): 0-100 for the total, 0-70 for the 30 day cohort, 0-60 for
# the 14 day absorption, and 60-to-0 for days on market, which is the one
# measure where fewer is stronger and so runs backwards.
CMI_SPECS = {
    "uc_total": dict(lo=0, hi=100, red=40, green=60, unit="%", icon="doc",
                     ends=("Buyers", "Sellers"),
                     # Casey, 16 Oct 2026: "Make it Total Homes Under
                     # Contract so it will be on two lines and line up with
                     # everyone else." The one-line title left that card's
                     # heading a row shallower than its neighbours.
                     # Casey, 27 Nov 2026: "the title say % of homes under contract".
                     title="% of Homes Under Contract",
                     vnames=("Buyer&rsquo;s Market", "Neutral Market",
                             "Seller&rsquo;s Market"),
                     desc="Of listings under contract",
                     names=("Buyer&rsquo;s Market", "Neutral",
                            "Seller&rsquo;s Market")),
    "uc_30":    dict(lo=0, hi=70, red=25, green=40, unit="%", icon="cal",
                     ends=("Buyers", "Sellers"),
                     open_top=True,
                     title="Under Contract (Last 30 Days)",
                     vnames=("Buyer&rsquo;s Market", "Neutral Market",
                             "Seller&rsquo;s Market"),
                     desc="Of homes listed in the last 30 days "
                          "went under contract",
                     names=("Buyer&rsquo;s Market", "Neutral",
                            "Seller&rsquo;s Market")),
    "uc_14":    dict(lo=0, hi=60, red=20, green=30, unit="%", icon="trend",
                     ends=("Declining", "Improving"),
                     open_top=True,
                     title="14-Day Absorption Rate",
                     desc="Of all listings went under contract "
                          "in the last 14 days",
                     names=("Declining", "Neutral", "Improving")),
    # Casey, 18 Oct 2026, pointing at the live Vienna Luxury page: "This is
    # what should come up." The MSS now opens Market Strength with Success
    # Rate -- the share of listings that sold rather than coming off the
    # market -- so the dashboard carries it too. Red under 60%, neutral to
    # 80%, green above. The caption names the other half: a 61% success rate
    # is 39% of the homes withdrawn unsold, which is the figure that lands.
    "success_rate": dict(lo=0, hi=100, red=60, green=80, unit="%",
                         icon="shield",
                         ends=("Buyers", "Sellers"),
                         # 80 and 100 collide on a narrow bar; the 80 stays.
                         hide_hi=True,
                         title="Success Rate",
                         vnames=("Buyer&rsquo;s Market", "Neutral Market",
                                 "Seller&rsquo;s Market"),
                         desc="Of listings sold",
                         desc_complement="of the homes withdrew unsold",
                         names=("Buyer&rsquo;s Market", "Neutral",
                                "Seller&rsquo;s Market")),
    # Days on market runs backwards -- 60+ on the left, 0 on the right --
    # so the open end of the scale is the left one.
    "dom":      dict(lo=60, hi=0, red=30, green=15, unit="", icon="clock",
                     ends=("Buyers", "Sellers"),
                     open_lo=True,
                     title="Average Days on Market (Active &amp; Pending)",
                     vnames=("Buyer&rsquo;s Market", "Neutral Market",
                             "Seller&rsquo;s Market"),
                     desc="Average days on market",
                     names=("Buyer&rsquo;s Market", "Neutral",
                            "Seller&rsquo;s Market")),
    # Casey, 27 Nov 2026: the MSS "Sold or Withdrawn in the Last 90 Days"
    # headline gauges above the Comparable Sales map -- same scales as the MSS.
    "sold_dom": dict(lo=120, hi=0, red=60, green=30, unit="", icon="clock",
                     ends=("Buyers", "Sellers"), open_lo=True,
                     title="Avg. Days on Market",
                     desc="Sold and withdrawn, last 90 days",
                     names=("Buyer&rsquo;s Market", "Neutral", "Seller&rsquo;s Market")),
    "sp_lp": dict(lo=94, hi=104, red=98, green=100, unit="%", icon="shield",
                  ends=("Buyers", "Sellers"),
                  title="Sale Price to List Price",
                  desc="Of list price, closed sales, last 90 days",
                  names=("Buyer&rsquo;s Market", "Neutral", "Seller&rsquo;s Market")),
}
GAUGE_SPECS = CMI_SPECS          # the name the first cut used


def sold_gauges(p):
    """Casey, 27 Nov 2026: "Above Comp sales chart should be headline gauges
    of Success Rate, Avg DOM, % of LP" -- the market's sold-or-withdrawn
    figures for the last 90 days, read off the MSS page (market_local)."""
    ml = p.get("market_local") or {}
    cells = {l.lower(): n for n, l in ml.get("cells") or []}
    sr = next((n for l, n in cells.items() if "success" in l), None)
    dm = next((n for l, n in cells.items() if "days" in l), None)
    lp = next((n for l, n in cells.items() if "list price" in l and "above" not in l), None)
    picks = [(k, n) for k, n in (("success_rate", sr), ("sold_dom", dm), ("sp_lp", lp)) if n]
    if len(picks) < 3:
        return ""
    cards = "".join(cmi_card(k, n, shared=True) for k, n in picks)
    lab = re.sub(r"^Rest of (the )?", "", ml.get("label") or "the market")
    return ('<div class="sold-g"><div class="sold-g-h">' + lab
            + ' &middot; Sold or withdrawn in the last 90 days</div>'
            '<div class="cmi-wrap cmi-three"><div class="cmi-group">'
            f'<div class="cmi-row n3">{cards}</div></div></div>' + CMI_SCALE + '</div>')

# One small gold mark per statistic, set beside the figure rather than
# above it so the card gains a signal and no height.
CMI_ICONS = {
    "doc": '<path d="M2.6 8.2L9 2.6l6.4 5.6" fill="none" '
           'stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
           'stroke-linejoin="round"/><path d="M4.4 9.4v6h9.2v-6" '
           'fill="none" stroke="currentColor" stroke-width="1.4" '
           'stroke-linecap="round" stroke-linejoin="round"/>',
    "cal": '<rect x="2.4" y="3.2" width="13.2" height="11.6" rx="1.6" '
           'fill="none" stroke="currentColor" stroke-width="1.3"/>'
           '<path d="M2.4 7h13.2M6 1.6v3M12 1.6v3" stroke="currentColor" '
           'stroke-width="1.3" stroke-linecap="round"/>',
    "trend": '<path d="M3.2 15.2v-4.6M8.4 15.2V7.4M13.6 15.2V3.2" '
             'fill="none" stroke="currentColor" stroke-width="2.1" '
             'stroke-linecap="round"/>',
    # A shield with a check, the mark the MSS puts on Success Rate.
    "shield": '<path d="M9 1.9l5.9 2.4v4.4c0 3.4-2.4 6-5.9 7.4-3.5-1.4-5.9-4'
              '-5.9-7.4V4.3z" fill="none" stroke="currentColor" '
              'stroke-width="1.3" stroke-linejoin="round"/>'
              '<path d="M6.4 8.9l1.9 1.9 3.5-3.6" fill="none" '
              'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
              'stroke-linejoin="round"/>',
    "clock": '<circle cx="9" cy="9" r="6.8" fill="none" '
             'stroke="currentColor" stroke-width="1.3"/>'
             '<path d="M9 4.8V9l3 1.9" fill="none" stroke="currentColor" '
             'stroke-width="1.4" stroke-linecap="round" '
             'stroke-linejoin="round"/>',
}


def stat_icon(key):
    """The gold mark for one statistic, or "" where there is no gauge."""
    spec = CMI_SPECS.get(key)
    if not spec:
        return ""
    return ('<svg class="cmi-ico" viewBox="0 0 18 18" aria-hidden="true">'
            + CMI_ICONS[spec["icon"]] + "</svg>")

GAUGE_CSS = """
  /* CST Market Gauge: one bar, three proportional bands, a black pointer.
     Widths and positions are percentages of the bar, so every gauge is the
     same size whatever its scale. */
  /* The four labels wrap to different line counts, so the cards are set
     as columns and the gauge is pushed to the bottom -- four bars on one
     line read as a row of gauges, four at different heights do not. */
  .mc-stat, .ps-tile{display:flex; flex-direction:column;}
  .gauge{margin:9px auto 0; max-width:168px; width:100%; align-self:center;}
  .mc-stat .gauge, .ps-tile .gauge{margin-top:auto; padding-top:9px;}
  .gauge-bar{position:relative; height:8px; border-radius:4px;
    background:#E8E1D1; overflow:hidden;
    box-shadow:inset 0 1px 2px rgba(60,45,10,.18);}
  .gauge-bar .g-fill{position:absolute; inset:0;}
  .gauge-ptr{position:relative; height:7px;}
  .gauge-ptr i{position:absolute; top:0; width:0; height:0;
    transform:translateX(-50%); border-left:5px solid transparent;
    border-right:5px solid transparent; border-top:7px solid #141009;}
  .gauge-ticks{position:relative; height:12px; margin-top:3px;}
  .gauge-ticks span{position:absolute; top:0; transform:translateX(-50%);
    font-size:8.5px; letter-spacing:.04em; color:#8A8071; white-space:nowrap;
    font-family:'Lora',Georgia,serif;}
  /* The classification as a capsule rather than a line of text: it is a
     verdict, and a verdict should look pinned on. */
  .gauge-cls{margin-top:3px; text-align:center;}
  .gauge-cls span{display:inline-block; font-size:8px; font-weight:700;
    letter-spacing:.1em; text-transform:uppercase; border-radius:999px;
    padding:2px 8px; border:1px solid transparent;}
  .gauge-cls .red{color:#9E2118; background:#FBE9E7; border-color:#F0C8C3;}
  .gauge-cls .yel{color:#8A6C08; background:#FBF2D8; border-color:#EEDFAE;}
  .gauge-cls .grn{color:#136B34; background:#E6F4EA; border-color:#BFE0C9;}

  /* ---- CST Market Intelligence(TM): the full card -------------------
     Four equal cards on one row, thin gold rule, rounded, cream. Inside:
     a gold mark and the measure's name, the figure, what it is of, the
     instrument, and the verdict. */
  /* Stacked two by two: strength above, momentum below. */
  .cmi-wrap{display:grid; grid-template-columns:1fr; gap:16px;
    max-width:720px; margin:14px auto 0;}
  .cmi-group{display:flex; flex-direction:column;}
  .cmi-glabel{display:flex; align-items:center; justify-content:center;
    gap:9px; padding-bottom:6px; margin-bottom:9px;
    border-bottom:1px solid var(--gold-line);}
  .cmi-gt{font-size:10px; font-weight:700; letter-spacing:.17em;
    text-transform:uppercase; color:var(--gold-deep);}
  .cmi-gmark{display:inline-flex; align-items:center; gap:2px;}
  .cmi-flag{width:11px; height:14px;}
  .cmi-arw{width:15px; height:15px;}
  .cmi-arw.up{color:#1B9E4B;} .cmi-arw.down{color:#D42A21;}
  .cmi-arw.flat{color:#E0A800;}
  .cmi-gscore{font-family:'Playfair Display',Georgia,serif; font-size:14px;
    font-weight:700; color:var(--ink); display:inline-flex;
    align-items:baseline; gap:6px;}
  .cmi-gscore em{font-family:'Lora',Georgia,serif; font-style:normal;
    font-size:8.5px; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase;}
  .cmi-gscore.up em{color:#16823E;} .cmi-gscore.down em{color:#B3261E;}
  .cmi-gscore.flat em{color:#9A7A0C;}
  /* Both rows the same width: the strength pair was sizing to its own
     content and coming out 70px narrower than the momentum pair under it. */
  .cmi-wrap .cmi-row{margin:0 auto; width:100%; max-width:520px;}
  .cmi-wrap.cmi-three .cmi-row{max-width:780px;}
  /* screen only: a printed page is 816px wide, so a bare max-width rule
     here stacks the two groups on paper as well as on a phone. */
  @media screen and (max-width:860px){
    .cmi-wrap{grid-template-columns:1fr !important;} }
  @media print{ .cmi-wrap{gap:9px; margin-top:7px; max-width:620px;}
    .cmi-glabel{gap:7px; padding-bottom:3px; margin-bottom:5px;}
    .cmi-gt{font-size:8px; letter-spacing:.13em;}
    .cmi-flag{width:9px; height:12px;} .cmi-arw{width:12px; height:12px;}
    .cmi-gscore{font-size:12px; gap:5px;}
    .cmi-gscore em{font-size:7px;} }
  /* One scale for the whole dashboard: red through yellow to green, with
     the three readings named once underneath. */
  .cmi-scale-wrap{max-width:720px; margin:14px auto 0;}
  .cmi-scale-bar{height:9px; border-radius:5px;
    background:linear-gradient(to right,#C62828 0%,#C62828 34%,#E8B21E 44%,
      #E8B21E 56%,#1B9E4B 66%,#1B9E4B 100%);
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  .cmi-scale-l{display:flex; justify-content:space-between; margin-top:6px;
    font-size:11px; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase;}
  .cmi-scale-l .red{color:#B3261E;} .cmi-scale-l .yel{color:#9A7A0C;}
  .cmi-scale-l .grn{color:#16823E;}
  .cmi-scale-wrap.bare{max-width:660px; margin:11px auto 0;}
  @media print{ .cmi-scale-wrap.bare{margin-top:7px; max-width:560px;}
    .cmi-scale-wrap.bare .cmi-scale-bar{height:6px;} }
  @media print{ .cmi-scale-wrap{margin-top:8px; max-width:620px;}
    .cmi-scale-bar{height:7px;} .cmi-scale-l{font-size:8px; margin-top:4px;} }
  .cmi-row.n3{grid-template-columns:repeat(3,1fr); max-width:760px;}
  .cmi-row.n2{grid-template-columns:repeat(2,1fr); max-width:520px;}
  .cmi-row.n1{grid-template-columns:1fr; max-width:270px;}
  .cmi-row{display:grid; grid-template-columns:repeat(4,1fr); gap:12px;
    max-width:1000px; margin:14px auto 0;}
  /* Casey, 16 Oct 2026: "Make %UC and DOM larger boxes like 30 day and 14
     day." A one-line description made those two cards shallower than the
     pair beneath them; every card is one height now. */
  .cmi-card{background:#FFFDF8; border:1px solid var(--gold-line);
    border-radius:11px; padding:13px 12px 11px; text-align:center;
    display:flex; flex-direction:column; min-height:232px;
    box-shadow:0 1px 4px rgba(60,45,10,.05);}
  /* Casey, 15 Oct 2026: "LINES IN CURRENT MARKET SHOULD BE ON SAME LINE."
     One title runs to one line and the next to two, so every row below
     them used to start at a different height and the four bars stepped
     down the row. The two text rows are fixed, so the figure, the bar and
     the verdict all sit on one line across the four cards. */
  .cmi-head{display:flex; align-items:center; justify-content:center;
    gap:7px; height:30px;}
  .cmi-ico{width:16px; height:16px; color:var(--gold-deep); flex:none;}
  /* Capped so every title breaks to two lines rather than one card's
     heading sitting a row shallower than its neighbours. */
  .cmi-t{font-size:9.5px; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase; color:#4A4034; line-height:1.3;
    max-width:168px;}
  .cmi-n{font-family:'Playfair Display',Georgia,serif; font-size:34px;
    font-weight:700; color:var(--gold-deep); line-height:1.05;
    margin-top:5px;}
  .cmi-d{font-size:10.5px; color:var(--muted); line-height:1.4;
    margin-top:5px; height:30px; display:flex; align-items:center;
    justify-content:center;}
  .cmi-g{margin-top:9px;}
  .cmi-ptr{position:relative; height:17px;}
  .cmi-ptr i{position:absolute; bottom:0; transform:translateX(-50%);}
  .cmi-ptr i b{display:block; font-family:'Lora',Georgia,serif;
    font-size:9px; font-weight:700; color:#2B2318; margin-bottom:2px;
    white-space:nowrap;}
  .cmi-ptr i::after{content:""; display:block; margin:0 auto; width:0;
    height:0; border-left:5px solid transparent;
    border-right:5px solid transparent; border-top:7px solid #141009;}
  .cmi-bar{position:relative; height:9px; border-radius:5px;
    overflow:hidden; background:#E8E1D1;
    box-shadow:inset 0 1px 2px rgba(60,45,10,.2);}
  .cmi-bar .g-fill{position:absolute; inset:0;}
  .cmi-scale{position:relative; height:11px; margin-top:4px;}
  .cmi-scale span{position:absolute; top:0; transform:translateX(-50%);
    font-size:7.5px; letter-spacing:.03em; color:#8A8071; white-space:nowrap;
    font-family:'Lora',Georgia,serif;}
  .cmi-scale .e.l{left:0; transform:none;}
  .cmi-scale .e.r{right:0; left:auto; transform:none;}
  .cmi-bands{position:relative; height:21px; margin-top:2px;}
  .cmi-bands{height:12px;}
  .cmi-bands span{position:absolute; top:0; font-size:8px; font-weight:700;
    letter-spacing:.09em; text-transform:uppercase; line-height:1.2;
    white-space:nowrap;}
  .cmi-bands .e.l{left:0;} .cmi-bands .e.r{right:0;}
  .cmi-bands .red{color:#B3261E;} .cmi-bands .yel{color:#9A7A0C;}
  .cmi-bands .grn{color:#16823E;}
  .cmi-verdict{margin-top:auto; padding-top:9px;}
  .cmi-verdict::before{content:attr(data-v);}
  .cmi-verdict{font-size:8.5px; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; border-radius:999px; padding:6px 8px;
    border:1px solid transparent;}
  .cmi-verdict.red{color:#9E2118; background:#FBE9E7; border-color:#F0C8C3;}
  .cmi-verdict.yel{color:#8A6C08; background:#FBF2D8; border-color:#EEDFAE;}
  .cmi-verdict.grn{color:#136B34; background:#E6F4EA; border-color:#BFE0C9;}
  .cmi-plain .cmi-n{margin-top:0;}

  /* The one line that joins the market read to the pricing call. */
  .ps-posture{max-width:760px; margin:0 auto 20px; text-align:center;
    font-size:15.5px; line-height:1.55; color:var(--ink);}
  .ps-posture b{color:var(--gold-deep);}
  @media print{ .ps-posture{font-size:12.5px; margin-bottom:12px;} }
  @media screen and (max-width:860px){ .cmi-row{grid-template-columns:repeat(2,1fr);} }
  @media screen and (max-width:480px){ .cmi-row{grid-template-columns:1fr;} }
  @media print{
    /* A footer alone on a last page is the one break this document should
       never take: it reads as a mistake. */
    footer{break-before:avoid-page; page-break-before:avoid;}
    .cmi-row{grid-template-columns:repeat(4,1fr) !important; gap:8px;
      margin-top:8px;}
    .cmi-row.n3{grid-template-columns:repeat(3,1fr) !important;}
    .cmi-row.n2{grid-template-columns:repeat(2,1fr) !important;}
    .cmi-card{padding:8px 7px 7px; border-radius:9px; box-shadow:none;
      min-height:168px;}
    .cmi-head{height:23px; gap:5px;}
    .cmi-ico{width:13px; height:13px;}
    .cmi-t{font-size:8px; letter-spacing:.07em; max-width:142px;}
    .cmi-n{font-size:25px; margin-top:3px;}
    .cmi-d{font-size:8.5px; margin-top:3px; height:23px;}
    .cmi-g{margin-top:6px;}
    .cmi-ptr{height:14px;} .cmi-ptr i b{font-size:7.5px; margin-bottom:1px;}
    .cmi-bar{height:7px;}
    .cmi-scale{height:9px; margin-top:3px;}
    .cmi-scale span{font-size:6.5px;}
    .cmi-bands{height:10px;} .cmi-bands span{font-size:6.8px;}
    .cmi-verdict{font-size:7px; padding:4px 6px; padding-top:4px;}
    .cmi-verdict{margin-top:auto;}
  }
  @media (max-width:640px){ .gauge{max-width:100%;} }
  @media print{
    .gauge{margin-top:2px !important; max-width:148px;}
    .mc-stat .gauge, .ps-tile .gauge{padding-top:2px !important;}
    .gauge-bar{height:6px;}
    .gauge-ptr{height:6px;}
    .gauge-ptr i{border-left-width:4px; border-right-width:4px;
      border-top-width:6px;}
    .gauge-ticks{height:8px; margin-top:1px;}
    .gauge-ticks span{font-size:6.5px;}
    .gauge-cls{margin-top:1px;}
    .gauge-cls span{font-size:6.5px; padding:1px 6px; letter-spacing:.07em;}
    .mc-stats .mc-stat{padding:8px 7px 7px;}
    .cmi-ico{width:11px; height:11px; margin-right:4px;} }
"""


def _gauge_value(raw):
    """The number behind a published figure: "29%" -> 29.0, 37 -> 37.0."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"-?\d+(?:\.\d+)?", str(raw))
    return float(m.group(0)) if m else None


def gauge_key(label):
    """Which gauge a tile's own label asks for.

    The two surfaces word their labels differently -- "Total under contract"
    against "Under Contract" -- so the match is on what the label is about,
    not on an exact string.
    """
    t = re.sub(r"<[^>]+>", " ", str(label)).lower()
    if "success rate" in t or "withdrew unsold" in t:
        return "success_rate"
    if "14 day" in t or "14 days" in t:
        return "uc_14"
    if "30 day" in t or "30 days" in t:
        return "uc_30"
    if "days on market" in t or t.strip() in ("dom", "days"):
        return "dom"
    if "under contract" in t:
        return "uc_total"
    return None


# Casey, 16 Oct 2026: "Categorize 4 stats on market. first two are % UC and
# Days on Market. The other two, Homes listed in last 30 day UC and 14 days,
# are Market Momentum."
#
# Two questions, not four readings. Strength is where the market stands --
# how much of the inventory is spoken for and how long it takes. Momentum is
# which way it is moving -- what the newest listings are doing and what the
# last fortnight did. A seller who reads the first pair knows the weather;
# the second pair says whether it is clearing or closing in.
CMI_GROUPS = [("Market Strength", ("success_rate", "uc_total", "dom")),
              ("Market Momentum", ("uc_30", "uc_14"))]


CMI_ARROWS = {
    "up":   ('<svg class="cmi-arw up" viewBox="0 0 20 20" aria-hidden="true">'
             '<path d="M10 16.5V4.2M4.6 9.4L10 3.6l5.4 5.8" fill="none" '
             'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>'),
    "down": ('<svg class="cmi-arw down" viewBox="0 0 20 20" aria-hidden="true">'
             '<path d="M10 3.5v12.3M4.6 10.6L10 16.4l5.4-5.8" fill="none" '
             'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>'),
    "flat": ('<svg class="cmi-arw flat" viewBox="0 0 20 20" aria-hidden="true">'
             '<path d="M3.4 10h13.2" fill="none" stroke="currentColor" '
             'stroke-width="2.6" stroke-linecap="round"/></svg>'),
}


CMI_QUESTIONS = {"Market Strength": "Who controls the market today?",
                 "Market Momentum": "Is the market improving or declining?"}

CMI_GICONS = {
    "Market Strength": ('<svg class="cmi-gi" viewBox="0 0 24 24" fill="none" '
                        'stroke="currentColor" stroke-width="1.6" '
                        'stroke-linecap="round" stroke-linejoin="round">'
                        '<path d="M3 10.5 12 3l9 7.5"/>'
                        '<path d="M5.5 9.8V20h13V9.8"/></svg>'),
    "Market Momentum": ('<svg class="cmi-gi" viewBox="0 0 24 24" fill="none" '
                        'stroke="currentColor" stroke-width="1.8" '
                        'stroke-linecap="round">'
                        '<path d="M5 19V13"/><path d="M12 19V8"/>'
                        '<path d="M19 19V4"/></svg>'),
}


# Casey, 17 Oct 2026: "On the Seller Roadmap, and stripped of title and
# legend in the Summary." The one-page sheet has no room for three more
# words under a bar the agent is standing there explaining, so it carries
# the gradient alone.
CMI_SCALE_BARE = '<div class="cmi-scale-wrap bare"><div class="cmi-scale-bar"></div></div>'

CMI_SCALE = (
    '<div class="cmi-scale-wrap"><div class="cmi-scale-bar"></div>'
    '<div class="cmi-scale-l"><span class="red">Buyer&rsquo;s Market</span>'
    '<span class="yel">Neutral</span>'
    '<span class="grn">Seller&rsquo;s Market</span></div></div>')


ROADMAP_GAUGES = ("uc_total", "dom", "uc_30")


def cmi_dashboard(stats, cond=None, wide=False, shared=True, three=False):
    """The whole dashboard: the cards, under their two group headings.

    three=True (Roadmap Current Competition): Casey, 22 Nov 2026 -- "only
    three index matter: % under contract, DOM and Contracts last 30 days".
    One row of three, no group headings or scores.

    `stats` is the (figure, label) list the report already carries. A group
    with no figures on file is left out rather than printed empty, so a
    property without contract dates shows one heading and not two.
    """
    seen = [(gauge_key(l), n, l) for n, l in stats]
    if three:
        pick = {k: (k, n, l) for k, n, l in seen if k in ROADMAP_GAUGES}
        mine = [pick[k] for k in ROADMAP_GAUGES if k in pick]
        if not mine:
            return ""
        cards = "".join(cmi_card(k, n, l, wide=wide, shared=shared) for k, n, l in mine)
        return ('<div class="cmi-wrap cmi-three"><div class="cmi-group">'
                f'<div class="cmi-row n{len(mine)}">{cards}</div></div></div>'
                + (CMI_SCALE if shared else ""))
    groups = []
    for title, keys in CMI_GROUPS:
        mine = [(k, n, l) for k, n, l in seen if k in keys]
        if mine:
            groups.append((title, mine))
    # A figure with no gauge of its own -- a city MSS reading like "1.8x
    # More Sellers Than Buyers" -- still says where the market stands, so
    # it joins Market Strength rather than trailing the row under a blank
    # heading.
    claimed = {k for _, g in groups for k, _, _ in g}
    rest = [(k, n, l) for k, n, l in seen if k not in claimed]
    if rest:
        if groups and groups[0][0] == CMI_GROUPS[0][0]:
            groups[0] = (groups[0][0], groups[0][1] + rest)
        else:
            groups.insert(0, (CMI_GROUPS[0][0], rest))
    if not groups:
        return ""
    # Casey, 16 Oct 2026: "Go ahead and stack 2 by 2. Have flag system and
    # Market Strength. Market Momentum will have green arrows going up, red
    # arrow going down, or yellow line signifying market holding steady."
    #
    # So the two groups sit one above the other, two cards wide, and each
    # heading carries its own signal: the flag the report already uses for
    # strength, an arrow for momentum. Each also carries its score, because
    # the arrow is the comparison of those two numbers and a seller should
    # be able to see the arithmetic.
    cond = cond or {}
    out = []
    for title, mine in groups:
        cards = "".join(cmi_card(k, n, l, wide=wide, shared=shared)
                        for k, n, l in mine)
        mark = score = ""
        if title == CMI_GROUPS[0][0]:
            fill = cond.get("flag_hex") or "#D42A21"
            mark = (f'<span class="cmi-gmark">'
                    f'{cmi_flag(fill) * int(cond.get("flags") or 0)}</span>')
            if cond.get("strength_score") is not None:
                score = (f'<span class="cmi-gscore">'
                         f'{cond["strength_score"]:.1f}</span>')
        elif title == CMI_GROUPS[1][0] and cond.get("momentum"):
            m = cond["momentum"]
            mark = f'<span class="cmi-gmark">{CMI_ARROWS[m["cls"]]}</span>'
            score = (f'<span class="cmi-gscore {m["cls"]}">{m["score"]:.1f}'
                     f'<em>{m["word"]}</em></span>')
        if wide:
            # Casey's reference, 16 Oct 2026: a circled mark, the group name
            # and the question that group answers.
            q = CMI_QUESTIONS.get(title, "")
            ico = CMI_GICONS.get(title, "")
            head = (f'<div class="cmi-glabel">'
                    f'<span class="cmi-gring">{ico}</span>'
                    f'<span class="cmi-gtw"><span class="cmi-gt">'
                    f'{title or "&nbsp;"}</span>'
                    + (f'<em class="cmi-gq">{q}</em>' if q else "")
                    + f'</span>{mark}{score}</div>')
        else:
            head = (f'<div class="cmi-glabel">{mark}'
                    f'<span class="cmi-gt">{title or "&nbsp;"}</span>'
                    f'{score}</div>')
        out.append(f'<div class="cmi-group">{head}'
                   f'<div class="cmi-row n{len(mine)}">{cards}</div></div>')
    return ('<div class="cmi-wrap">' + "".join(out) + '</div>'
            + (CMI_SCALE if shared else ""))


def cmi_flag(fill):
    """The same flag the headline uses, at heading size."""
    return ('<svg class="cmi-flag" viewBox="0 0 21 27" aria-hidden="true">'
            '<rect x="1.5" y="0" width="1.8" height="27" rx=".9" '
            'fill="#5E5345"/>'
            '<path d="M3.3 1.6 C8 0.2 13 3.4 18.6 1.8 L18.6 11.4 '
            f'C13 13 8 9.8 3.3 11.2 Z" fill="{fill}"/></svg>')


def _cmi_geom(spec, v):
    """Positions on the bar: the two thresholds, the pointer, and the band."""
    lo, hi = spec["lo"], spec["hi"]

    def pos(x):
        return max(0.0, min(1.0, (x - lo) / float(hi - lo))) * 100

    p_red, p_grn, p_true = pos(spec["red"]), pos(spec["green"]), pos(v)
    # Which band the figure is in, read off the bar rather than off the raw
    # number, so an ascending and a descending gauge use one rule. Casey,
    # 15 Oct 2026: "Place 40% and 20% boundary readings in Neutral, not
    # Red... 30 days DOM in Neutral and 15 days DOM in Neutral" -- so a
    # figure sitting exactly on a threshold belongs to the middle band.
    band = 0 if p_true < p_red else (2 if p_true > p_grn else 1)
    # The pointer is centred on its position, so a figure at either end --
    # 0% under contract, or 102 days against a 60 day scale -- would hang
    # half off the bar. It is held just inside, which still reads as "at
    # the end".
    return p_red, p_grn, min(97.0, max(3.0, p_true)), band, p_true


def _cmi_fill(p_red, p_grn):
    """The bar itself: flat colour across each band, blended at the two
    thresholds. One gradient rather than three blocks is what makes it read
    as an instrument rather than a bar chart; the blend is narrower than
    the tick label beneath it, so the thresholds stay legible."""
    b = 2.0
    stops = (f"#C62828 0%, #C62828 {max(0.0, p_red - b):.4g}%, "
             f"#E8B931 {min(100.0, p_red + b):.4g}%, "
             f"#E8B931 {max(0.0, p_grn - b):.4g}%, "
             f"#2E9B52 {min(100.0, p_grn + b):.4g}%, #2E9B52 100%")
    return (f'<span class="g-fill" style="background:linear-gradient('
            f'90deg,{stops})"></span>')


def _cmi_verdict(spec, band, v):
    """The capsule under the gauge.

    The band row above it is set tight, so it reads "Neutral"; the capsule
    is the verdict and says "Neutral Market" in full.

    A figure sitting on the bottom of the neutral band is called out --
    it is one point from the red band and the seller should know which way
    it is leaning. Casey's reference card does this at 20% and not at 40%,
    so the top of the band is left alone.
    """
    name = spec.get("vnames", spec["names"])[band]
    if band == 1 and v == spec["red"]:
        return name.split(" &mdash;")[0] + " &mdash; Lower Boundary"
    return name


def gauge_html(key, raw, compact=True, verdict=True):
    """One CST Market Intelligence(TM) gauge, or "" where it does not apply.

    compact=True is the strip used on the Pricing Strategy Summary, where
    the sheet has one page to give: bar, thresholds, verdict. The full card
    is cmi_card() below.
    """
    spec = CMI_SPECS.get(key)
    v = _gauge_value(raw)
    if not spec or v is None:
        return ""
    p_red, p_grn, p_val, band, _ = _cmi_geom(spec, v)
    cls = ("red", "yel", "grn")[band]
    u = spec["unit"]
    # Two threshold labels centred on positions a few points apart would
    # print on top of each other -- 25% and 40% are 15% of the bar apart,
    # about 25px. Close together, they splay outwards instead of centring.
    _tight = (p_grn - p_red) < 22
    _sh = ("translateX(-86%)", "translateX(-14%)") if _tight else \
          ("translateX(-50%)", "translateX(-50%)")
    ticks = (f'<span style="left:{p_red:.4g}%;transform:{_sh[0]}">'
             f'{spec["red"]:g}{u}</span>'
             f'<span style="left:{p_grn:.4g}%;transform:{_sh[1]}">'
             f'{spec["green"]:g}{u}</span>')
    return ('<div class="gauge">'
            f'<div class="gauge-bar">{_cmi_fill(p_red, p_grn)}</div>'
            f'<div class="gauge-ptr"><i style="left:{p_val:.4g}%"></i></div>'
            f'<div class="gauge-ticks">{ticks}</div>'
            + (f'<div class="gauge-cls"><span class="{cls}">'
               f'{_cmi_verdict(spec, band, v)}</span></div>'
               if verdict else "")
            + '</div>')


def cmi_card(key, raw, fallback_label="", wide=False, shared=False):
    """CST Market Intelligence(TM) -- the full card for one statistic.

    Casey, 15 Oct 2026: "I'd make this look like a luxury real estate
    market intelligence dashboard, not four ordinary statistic boxes."

    Top to bottom: a gold mark and the measure's name, the figure, what it
    is of, then the instrument -- pointer carrying its own reading, the
    graded bar, the scale with both ends and both thresholds, the three
    band names under the stretch each one owns, and the verdict.

    Nothing here is specific to a property or a market: the figure arrives
    from the report's own data and the thresholds are the standing CST
    bands, so the same card serves a Seller Roadmap, a Pricing Report, a
    Market Snapshot summary and a Recovery Roadmap alike.
    """
    spec = CMI_SPECS.get(key)
    v = _gauge_value(raw)
    if not spec or v is None:
        # No gauge for this measure: the figure and its own label, plainly.
        return ('<div class="cmi-card cmi-plain">'
                f'<div class="cmi-n">{raw}</div>'
                f'<div class="cmi-d">{fallback_label}</div></div>')
    p_red, p_grn, p_val, band, p_true = _cmi_geom(spec, v)
    cls = ("red", "yel", "grn")[band]
    u = spec["unit"]
    lo_t = f'{spec["lo"]:g}{u}' + ("+" if spec.get("open_lo") else "")
    hi_t = f'{spec["hi"]:g}{u}' + ("+" if spec.get("open_top") else "")

    # Success Rate's green threshold sits at 80 on a scale that ends at 100,
    # and on a narrow bar those two labels run together -- the card printed
    # "80%100%". The end label is the one to drop: the threshold is the
    # number that means something, and the bar's own end already shows where
    # the scale stops. Flagged on the spec rather than inferred from the
    # spacing, so no other gauge loses a label by accident.
    scale = (f'<span class="e l">{lo_t}</span>'
             f'<span style="left:{p_red:.4g}%">{spec["red"]:g}{u}</span>'
             f'<span style="left:{p_grn:.4g}%">{spec["green"]:g}{u}</span>')
    if not spec.get("hide_hi"):
        scale += f'<span class="e r">{hi_t}</span>'
    # Each band name sits over the stretch of bar it owns, so the colour,
    # the numbers and the words all line up on one vertical.
    # Casey, 16 Oct 2026: "Sellers and buyers market are scrunched. You do
    # not have to use buyer's market on every chart. Just have a scale at
    # the bottom with buyers under red and sellers under green. Everyone
    # knows what yellow is."
    #
    # Three names fought for room under a bar 170px wide and the middle one
    # lost every time. Two words at the two ends say the same thing and
    # leave the bar legible; the verdict capsule underneath still gives the
    # full reading, middle band included.
    _l, _r = spec["ends"]
    bands = (f'<span class="red e l">{_l}</span>'
             f'<span class="grn e r">{_r}</span>')
    # wide=True is the screen-width dashboard on the Local Market Snapshot,
    # where the bar is half the page and all three names fit under the
    # stretch each one owns -- which is how Casey drew it.
    if wide:
        # Three names on one line will not sit under the exact stretch each
        # owns without colliding -- the neutral band is 15% of the bar on
        # the 30-day gauge. Laid out in thirds they stay legible and still
        # read left to right with the colours.
        _n = spec["names"]
        bands = "".join(f'<span class="{c}">{t}</span>'
                        for c, t in zip(("red", "yel", "grn"), _n))
    # Casey, 17 Oct 2026: one scale under the whole dashboard instead of
    # band names and a verdict on every card. The cards keep the figure, the
    # pointer and the numbers; the reading is made once, underneath.
    if shared:
        bands = ""
    read = f'{v:g}{u}' if v != int(v) else f'{int(v):d}{u}'
    # Success Rate names the other half underneath -- 61% sold is "39% of the
    # homes withdrew unsold" -- which is the number that actually lands on a
    # seller. The complement is computed, never typed.
    desc = spec["desc"]
    if spec.get("desc_complement"):
        desc = f'{100 - v:g}{u} {spec["desc_complement"]}'
    # Casey, 18 Oct 2026: the local market's 30-day gauge carries its counts
    # -- "4 of 4" -- because a percentage off a handful of homes is not a
    # reading on its own. The source puts them on the label; the card moves
    # them under the figure where the seller reads them.
    _counts = re.search(r"\((\d+ of \d+)\)\s*$", str(fallback_label or ""))
    if _counts and key == "uc_total":
        # Casey, 27 Nov 2026: "11 out of 17 homes under contract".
        _a, _b = _counts.group(1).split(" of ")
        desc = f"{_a} out of {_b} homes under contract"
    elif _counts:
        desc = f"{desc} &mdash; {_counts.group(1)}"
    return ('<div class="cmi-card">'
            f'<div class="cmi-head">{stat_icon(key)}'
            f'<span class="cmi-t">{spec["title"]}</span></div>'
            f'<div class="cmi-n">{read}</div>'
            f'<div class="cmi-d">{desc}</div>'
            '<div class="cmi-g">'
            f'<div class="cmi-ptr"><i style="left:{p_val:.4g}%">'
            f'<b>{read}</b></i></div>'
            f'<div class="cmi-bar">{_cmi_fill(p_red, p_grn)}</div>'
            f'<div class="cmi-scale">{scale}</div>'
            + (f'<div class="cmi-bands{" wide" if wide else ""}">{bands}'
               '</div>' if bands else "")
            + '</div>'
            + ("" if shared else f'<div class="cmi-verdict {cls}">'
               f'{_cmi_verdict(spec, band, v)}</div>')
            + '</div>')


# The master component, under the name Casey gave it.
CSTMarketIntelligence = cmi_card


# Casey, 17 Oct 2026: "All market updates, whether local or city, family or
# luxury, should be Current Market (% UC and avg DOM) and Momentum (30 day
# listing UC and % of total listings UC in last 14 days), with gauges."
#
# A city MSS report caches whatever stats it happened to publish -- Oakton
# Luxury carried "1.5x More Sellers Than Buyers" where the share under
# contract belongs, and no days on market at all. The local snapshot already
# produces the four in this order. This puts the city reports on the same
# four, with the same labels, so every dashboard reads alike.
# In the order the MSS draws them: Success Rate opens Market Strength, then
# the two that have always been there, then the two momentum reads.
CMI_FOUR = [("success_rate", "Success rate"),
            ("under_contract", "Under contract"),
            ("avg_dom", "Days on market, active and pending"),
            ("uc_30", "Under contract on homes listed 30 days"),
            ("uc_14", "Of all listings, under contract in 14 days")]
# The four that every market update has carried since 17 Oct. Success rate
# only appeared on the MSS pages with the October 12 build, so a market
# cached before that has four and is complete at four.
CMI_REQUIRED = {"uc_total", "dom", "uc_30", "uc_14"}


def canonical_stats(market, cond):
    """The measures, in the order the MSS draws them.

    Returns the list unchanged when the report already supplies all of them
    -- which is what the local snapshot does -- and otherwise rebuilds it
    from the market's own figures. Anything genuinely missing is named in a
    note rather than quietly leaving a short dashboard.
    """
    have = {gauge_key(l) for _, l in (cond.get("stats") or [])}
    if have >= CMI_REQUIRED:
        return cond.get("stats")
    flat = dict(market.get("stats") or {})
    if market.get("avg_dom") and not flat.get("avg_dom"):
        flat["avg_dom"] = f'{round(float(market["avg_dom"]))}'
    out, missing = [], []
    # Keep the report's own label where it carries counts ("(4 of 11)").
    _own = {gauge_key(l): l for _, l in (cond.get("stats") or []) if re.search(r"\(\d+ of \d+\)", str(l))}
    for key, label in CMI_FOUR:
        v = flat.get(key)
        if v:
            out.append((str(v), _own.get(gauge_key(label), label)))
        else:
            missing.append(label)
    if not out:
        return cond.get("stats")
    # Success rate is new with the October 12 MSS; a market cached before it
    # is not short of anything, so it does not raise a note.
    missing = [m for m in missing if m != "Success rate"]
    if missing:
        note(f'Market update for {market.get("name") or "this market"}: '
             + ", ".join(missing) + " not published by that report, so the "
             "dashboard shows " + str(len(out)) + " gauges. "
             'Add "avg_dom" to the market block, or refresh the MSS.')
    return out


def market_conditions(market, three=False):
    """Current Market Conditions, in the MSS's own flag format: eyebrow, flag
    headline with the figure called out, the italic read, three stats and the
    Market Update. Everything here is text the MSS produces — nothing is
    derived here, because the counts behind it (6 of 9, 3 needed to keep pace)
    do not exist in the percentage-only market cache."""
    c = market.get("conditions")
    if not c:
        return ""
    # Drawn as SVG, not an emoji: the headless PDF renderer has no colour
    # emoji font and prints a grey flag, which defeats the whole signal.
    # flag_hex when the source names an exact colour — a Yellow Flag read as
    # "not green" used to print red, which is the one thing a flag must not
    # get wrong.
    fill = c.get("flag_hex") or (
        "#1B9E4B" if c.get("flag_color", "green") == "green" else "#B3261E")
    one = ('<svg width="15" height="19" viewBox="0 0 21 27" aria-hidden="true">'
           '<rect x="1.5" y="0" width="1.8" height="27" rx=".9" fill="#5E5345"/>'
           '<path d="M3.3 1.6 C8 0.2 13 3.4 18.6 1.8 L18.6 11.4 '
           f'C13 13 8 9.8 3.3 11.2 Z" fill="{fill}"/></svg>')
    flags = (f'<span class="mc-flags">{one * int(c.get("flags", 0))}</span>'
             if c.get("flags") else "")
    # A market whose page carried no headline leaves this None, not "". The
    # build used to die on None.replace() rather than render the section
    # without a headline, which is the wrong trade: one missing line of prose
    # should not take down a property's whole Roadmap.
    head = c.get("headline") or ""
    if not head:
        note(f'Market conditions for {market.get("name") or market.get("slug")}'
             ": no headline on the market page — the section renders without "
             "one. Re-run fetch_market_cmi.py if the page has since been "
             "rebuilt.")
    if head and c.get("headline_figure"):
        head = head.replace(c["headline_figure"],
                            f'<span class="mc-fig">{c["headline_figure"]}</span>', 1)
    # Casey, 15 Oct 2026: the four statistics are now the CST Market
    # Intelligence(TM) dashboard -- "not four ordinary statistic boxes".
    stats = cmi_dashboard(canonical_stats(market, c), c, three=three)
    if three:
        stats = stats.replace(CMI_SCALE, "")
    sub = f'<p class="mc-sub">{c["sub"]}</p>' if c.get("sub") else ""
    upd = (f'<div class="mc-update"><b>Market Update:</b> {c["update"]}</div>'
           if c.get("update") else "")
    # Casey, 15 Oct 2026: Current Market Conditions is followed by Advice.
    if c.get("advice"):
        upd = f'<p class="mc-advice">{c["advice"]}</p>' + upd
    # Casey, 22 Nov 2026: "The portals are for facts, the guides are for
    # explanation." The circled-number explanation goes to the Roadmap Guide,
    # not the Roadmap -- handed over through GUIDE_NOTES.
    if c.get("uc30_explain"):
        GUIDE_NOTES["uc30"] = c["uc30_explain"]
    if three:
        # Casey, 22 Nov 2026: "Just do headlines three indexes: %UC, DOM,
        # %UC last 30, then map then homes ... Cut everything else out of
        # Current Comp."
        return ('    <div class="mc">\n'
                f'      <h3 class="mc-head">{flags}{head}</h3>\n'
                f'      {stats}\n'
                '    </div>')
    return (
        '    <div class="mc">\n'
        '      <div class="mc-eyebrow">Current Market Conditions</div>\n'
        f'      <h3 class="mc-head">{flags}{head}</h3>\n'
        f'      {sub}\n'
        f'      {stats}\n'
        f'      {upd}\n'
        '    </div>')


def market_block(market, compact=False):
    """Regional market heading, optional stats table, optional absorption strip.
    compact=True (Roadmap Current Competition, Casey 22 Nov 2026): the flag
    headline and three gauges only -- no market name, update, table or strip.
    Not live-wrapped: the live MSS block would bring the rest back; the
    gauges refresh when the portal is rebuilt on the week's MSS."""
    slug = market.get("slug")
    head = '    <h3 style="text-align:center; font-family:\'Playfair Display\',Georgia,serif; font-size:16px; margin:0 0 4px;">'
    if slug:
        url = f"https://cstmarketupdate.netlify.app/{slug}.html"
        out = [head + f'<a href="{url}" target="_blank" rel="noopener" '
               'style="color:inherit; text-decoration:none; border-bottom:1px dotted var(--gold-line);">'
               f'{market["name"]}</a></h3>']
    elif market.get("name"):
        # No MSS page covers this market — name it, but do not link nowhere.
        note(f'No MSS slug for {market["name"]} — heading is unlinked and the '
             "Market Snapshot card and email row are omitted.")
        out = [head + f'{market["name"]}</h3>']
    else:
        # No market at all: no heading, just the competition below.
        note("Roadmap: no market named — market heading, stats, Market Snapshot "
             "card and email row all omitted.")
        out = []
    if not market:
        # Run with no market snapshot. Nothing below this point has anything
        # to read, and every note it would write names a market that does
        # not exist, so the section ends here.
        return ""
    # Fall back to the cached MSS figures for the Roadmap's market table,
    # conditions block and absorption strip, same source the emails use.
    cache_file = HERE / "market_cache.json"
    cached = {}
    if cache_file.exists() and market.get("slug"):
        cached = json.loads(cache_file.read_text()).get(market["slug"], {}) or {}
        if not market.get("conditions") and cached.get("conditions"):
            market["conditions"] = cached["conditions"]
        # The flag block reads the market's own figures to fill its four
        # gauges, so they have to be in place before it is built -- they used
        # to be adopted a few lines later and the dashboard came out short.
        if not market.get("stats") and cached.get("stats"):
            market["stats"] = cached["stats"]

    if market.get("conditions"):
        # The MSS flag block replaces the old subhead line: it says the same
        # thing and more, and two reads of the market stacked is noise.
        _mc = market_conditions(market, three=True)
        if compact:
            return _mc
        # Casey, 21 Oct 2026: follows the weekly MSS live (see live_slug).
        _ls = market.get("slug")
        if _mc and _ls and cached.get("conditions") is market.get("conditions"):
            _mc = live_wrap("mc", _ls, _mc)
        out.append(_mc)
    elif market.get("subhead"):
        out.append(f'    <p class="section-sub" style="margin-bottom:14px;">{market["subhead"]}</p>')

    if cache_file.exists():
        if not market.get("stats") and cached.get("stats"):
            market["stats"] = cached["stats"]
        if not market.get("absorption") and cached.get("absorption"):
            market["absorption"] = cached["absorption"]

    stats = market.get("stats")
    if stats and market.get("conditions"):
        # The flag block above already gives the seller the read in plain
        # words. The six-column percentage table restates it in jargon and
        # makes the page harder to follow, so it goes when both are present.
        stats = None
    if stats:
        cols = ["Market", "Inventory", "Contracts", "% Under Contract",
                "UC Last 14 Days", "Control"]
        vals = [stats["market"], stats["inventory"], stats["contracts"],
                stats["under_contract"], stats["uc_14"], stats["control"]]
        out.append('    <div class="table-wrap">\n      <table>\n        <thead><tr>'
                   + "".join(f"<th>{c}</th>" for c in cols)
                   + '</tr></thead>\n        <tbody>\n          <tr>'
                   + f'<td class="addr-cell">{vals[0]}</td>'
                   + "".join(f"<td>{v}</td>" for v in vals[1:])
                   + "</tr>\n        </tbody>\n      </table>\n    </div>")
    elif market.get("conditions"):
        note(f"Roadmap: {market['name']} stats table dropped — the Current "
             "Market Conditions block carries the same read in plain words.")
    else:
        note(f"Roadmap: {market['name']} stats table OMITTED — no figures supplied.")

    ab = market.get("absorption")
    if ab:
        zone_cls = {"Go Zone": "go", "Slow Go Zone": "slowgo",
                    "No Go Zone": "nogo"}.get(ab["zone"], "slowgo")
        out.append(
            '    <div class="zone-strip">\n'
            '      <div style="text-align:center;">\n'
            f'        <div class="zone-num">{ab["rate"]}</div>\n'
            '        <div class="zone-lbl">14 Day Absorption</div>\n'
            "      </div>\n"
            '      <div class="zone-divider"></div>\n'
            f'      <span class="zone-pill {zone_cls}">{ab["zone"]}</span>\n'
            "    </div>")
        if ab.get("note"):
            out.append(f'    <p class="notes-box">{ab["note"]}</p>')
    else:
        note("Roadmap: 14 Day Absorption strip OMITTED — the MSS no longer "
             "publishes it; the red flag check reads the 14-day figure from "
             "the market stats instead.")

    # Outside the strip: the warning must still fire when the MSS gives no
    # absorption strip at all, which is every market since the flag format.
    warn = absorption_warning(market.get("absorption"), market.get("name", ""),
                              market.get("stats"))
    if warn:
        out.append(warn)

    return "\n".join(out)


ABSORPTION_WARN_AT = 15      # 14-day absorption under this is a red flag
UC_WARN_AT = 20              # percent under contract under this is a red flag


def _pct(v):
    """'15%' -> 15.0; anything unparseable -> None."""
    try:
        return float(str(v).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def absorption_warning(ab, market_name="", stats=None):
    """Red Flag Market box. Fires when 14-day absorption is under 15% OR the
    share under contract is under 20% — either one on its own means buyers
    are not transacting. A percentage does not land with a seller, so the
    absorption rate is restated as '1 out of N'."""
    stats = stats or {}
    ab = ab or {}
    # The MSS dropped the 14 Day Absorption strip when it moved to the flag
    # format, so the rate now comes from the stats' own 14-day figure and the
    # strip is only a fallback for older cached markets.
    rate = _pct(ab.get("rate"))
    if rate is None:
        rate = _pct(stats.get("uc_14"))
    uc = _pct(stats.get("under_contract"))

    # 30-day sales: the MSS prints a dash where the figure is zero, so a dash
    # in that slot is not missing data -- it means nothing closed. Nothing
    # selling in 30 days is worse than slow absorption, and it flies two flags.
    # uc_30 is the share that went under contract in 30 days. "contracts" is
    # a year-over-year change and was standing in for it, so a market with a
    # genuine 0% share but a non-zero change raised no flag at all.
    _sales = stats.get("uc_30", stats.get("contracts"))
    _sales_pct = _pct(_sales)
    no_sales = (_sales_pct == 0) or (str(_sales).strip() in {"\u2014", "-", "0", "0%"})

    # 0 was excluded here, which meant the worst possible reading -- nothing
    # at all going under contract in 14 days -- raised no flag. It is now the
    # severe case, phrased without the "1 out of N" that zero cannot produce.
    slow_absorption = rate is not None and rate < ABSORPTION_WARN_AT
    slow_uc = uc is not None and 0 < uc < UC_WARN_AT
    if not (slow_absorption or slow_uc or no_sales):
        return ""

    label = market_name.replace(" Market", "").strip() or "this market"
    bits = []
    if no_sales:
        bits.append(
            f"<b>No {label} homes sold in the last 30 days.</b> Not a slow month "
            "&mdash; zero.")
    if slow_absorption and rate == 0:
        bits.append(
            f"<b>Not one {label} home went under contract in the last 14 days.</b>")
    elif slow_absorption:
        # int(x + .5) rather than round(), which is banker's rounding and
        # would turn 8% (1 in 12.5) into 1 in 12 rather than 1 in 13.
        n = int(100.0 / rate + 0.5)
        bits.append(
            f"Only <b>{rate:g}%</b> of {label} homes went under contract in the "
            f"last 14 days &mdash; about <b>1 out of {n}</b>.")
    if slow_uc:
        n_uc = int(100.0 / uc + 0.5)
        bits.append(
            f"Just <b>{uc:g}%</b> of the homes on the market are under contract "
            f"&mdash; about <b>1 out of {n_uc}</b>.")
    bits.append(
        "A home priced above the market in these conditions is unlikely to find "
        "its buyer in the first week, and the ones that sit are the ones that "
        "end up reducing.")
    flags = "&#9873;&#9873;" if (no_sales or rate == 0) else "&#9873;"
    return (
        '    <div class="absorb-warn">\n'
        f'      <div class="aw-flag">{flags} Red Flag Market</div>\n'
        f'      <p>{" ".join(bits)}</p>\n'
        "    </div>")


def comp_gallery(rows, cls_note=""):
    """A photo band under the comps table: what each comp looked like and what
    it sold for. Built only from photos supplied per comp — an 8th element on
    the row. Comps with no photo are skipped rather than shown blank."""
    shown = [r for r in rows if len(r) > 7 and r[7]]
    if not shown:
        return ""
    cards = []
    for r in shown[:4]:
        addr, sale, photo = r[0], r[5], r[7]
        url = r[6] if len(r) > 6 and r[6] else None
        name = (f'<a href="{url}" target="_blank" rel="noopener" '
                f'style="color:inherit; text-decoration:none;">{addr}</a>'
                if url else addr)
        price = money(sale) if sale else "&mdash;"
        cards.append(
            '    <div style="text-align:center;">\n'
            f'      <img src="{photo}" alt="{addr}" style="width:100%; height:120px; '
            'object-fit:cover; border-radius:6px; display:block; margin-bottom:6px;">\n'
            f'      <div style="font-size:12px; font-weight:600;">{name}</div>\n'
            f'      <div style="font-size:13px; font-weight:700; color:var(--gold-deep);">{price}</div>\n'
            "    </div>")
    n = len(cards)
    return (f'\n  <div style="display:grid; grid-template-columns:repeat({n},1fr); '
            'gap:12px; max-width:780px; margin:18px auto 0;">\n'
            + "\n".join(cards) + "\n  </div>\n"
            '  <p class="notes-box">What the comparable homes look like, and what each '
            "one sold for. Condition is the difference between the top and the bottom "
            "of this range.</p>\n")


# --------------------------------------------------------------- Roadmap ----
RATING_CSS = """
  .rating-box{max-width:680px; margin:26px auto 0; text-align:center; padding-top:20px;
    border-top:1px dashed var(--rule);}
  .rating-box h3{font-size:13px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
    color:var(--muted); margin:0 0 8px;}
  .sf-grid{display:grid; grid-template-columns:1fr 1fr; gap:0; max-width:680px; margin:0 auto;
    text-align:left;}
  .sf-col{padding:0 24px;}
  .sf-col + .sf-col{border-left:1px solid var(--rule);}
  .sf-col ul{list-style:none; margin:0; padding:0; font-size:14px;}
  .sf-col li{padding:6px 0; border-bottom:1px dotted var(--rule);}
  .sf-col li:last-child{border-bottom:none;}
  .sf-col ul li.sf-label:first-child{padding-top:0 !important;}
  .sf-label{
    list-style:none; text-align:left; font-family:'Playfair Display',Georgia,serif;
    font-weight:700; font-size:12px; letter-spacing:.05em; text-transform:uppercase;
    color:var(--gold-deep); border-bottom:none !important; padding:14px 0 6px !important;
  }
  @media (max-width:640px){
    .sf-grid{grid-template-columns:1fr; gap:28px 0;}
    .sf-col + .sf-col{border-left:none; border-top:1px solid var(--rule); padding-top:24px;}
  }
"""


def balance_rows(groups):
    """Split flat (label, item) rows into two even columns.

    balance_columns can only cut between groups, so a single long list —
    which is what "Other Upgrades" usually is — leaves one column empty.
    This splits inside a group and repeats the label, continued, at the top
    of the second column.
    """
    rows = []
    for g in groups:
        for n, item in enumerate(g["items"]):
            rows.append((g["label"] if n == 0 else None, item, g["label"]))
    if not rows:
        return [], []
    half = (len(rows) + 1) // 2
    left, right = rows[:half], rows[half:]
    # Only repeat a label that exists; the unlabelled upgrade list just runs on.
    if right and right[0][0] is None and right[0][2]:
        right[0] = (right[0][2] + " (continued)", right[0][1], right[0][2])
    return left, right


def balance_columns(cols):
    """Even out the two Premium Rating columns.

    The worksheet splits groups by topic, which often leaves one column a
    third longer than the other and the box looking lopsided. This keeps the
    group order but moves the split point to wherever the two sides come
    closest in height — a group header costs about as much as two items.
    """
    groups = [g for c in cols for g in c]

    def weight(g):
        return 2 + sum(1 + len(i) // 60 for i in g["items"])

    total = sum(weight(g) for g in groups)
    best, split, run = None, 1, 0
    for i, g in enumerate(groups[:-1]):
        run += weight(g)
        gap = abs(total - 2 * run)
        if best is None or gap < best:
            best, split = gap, i + 1
    return [groups[:split], groups[split:]]


def upgrades_only(p):
    """Recast the Premium Rating for the printable Buyer Pricing.

    The headline features already say what the home is, so repeating them
    below wastes the page. Everything that reads as a feature list is
    dropped, the remaining update and improvement groups are merged under a
    single "Other Upgrades" heading, and Schools is kept as its own short
    group. Anything already named in a headline is filtered out.
    """
    cols = p.get("premium_rating") or []
    groups = [g for c in cols for g in c]
    if not groups:
        return None

    said = " ".join(
        (x["head"] + " " + " ".join(x["sub"])).lower()
        for x in ((p.get("buyer_portal") or {}).get("feature_headlines") or []))

    def already_said(item):
        words = [w for w in re.findall(r"[a-z0-9']{4,}", item.lower())
                 if w not in ("with", "from", "that", "this", "your", "level", "room")]
        if not words:
            return False
        hits = sum(1 for w in words if w in said)
        return hits / len(words) >= 0.7

    schools, upgrades = [], []
    for g in groups:
        label = g["label"].lower()
        if "school" in label:
            schools.append(g)
            continue
        if "top feature" in label and said.strip():
            continue          # that IS the headlines
        if "top feature" in label:
            # No headline features on this property, so nothing else on the
            # sheet carries what the home actually is. Dropping the group
            # here left the Buyer Report as comps and two value cards.
            note("Buyer Report: Top Features kept in the Premium Rating — "
                 "there are no headline features to carry them. Add "
                 '"feature_headlines" to the buyer_portal block and they '
                 "move up to the top of the sheet.")
            upgrades += g["items"]
            continue
        upgrades += [i for i in g["items"] if not already_said(i)]

    out = []
    if upgrades:
        out.append({"label": "", "items": upgrades})   # the box heading says it
    out += schools
    return out or None


def premium_rating_block(p, placeholder=True, balance=False, groups=None):
    """The Premium Rating box, used by both the Roadmap and the Buyer Report."""
    if groups:
        left, right = balance_rows(groups)

        def rowcol(rows):
            out = []
            for label, item, _ in rows:
                if label:
                    out.append(f'            <li class="sf-label">{label}</li>')
                out.append(f"            <li>{item}</li>")
            return "\n".join(out)

        headline = (
            '      <p class="rating-headline" style="font-family:\'Playfair Display\',Georgia,serif; '
            'font-size:17px; font-weight:700; color:var(--gold-deep); font-style:normal; '
            f'margin:0 0 14px;">{p["premium_rating_headline"]}</p>\n'
            if p.get("premium_rating_headline") else "")
        return (
            '    <div class="rating-box">\n      <h3>Other Upgrades</h3>\n'
            + headline +
            '      <div class="sf-grid">\n'
            f'        <div class="sf-col">\n          <ul>\n{rowcol(left)}\n          </ul>\n        </div>\n'
            f'        <div class="sf-col">\n          <ul>\n{rowcol(right)}\n          </ul>\n        </div>\n'
            "      </div>\n    </div>\n")

    if p.get("premium_rating"):
        cols = p["premium_rating"]
        if balance:
            cols = balance_columns(cols)

        def col(groups):
            items = []
            for g in groups:
                items.append(f'            <li class="sf-label">{g["label"]}</li>')
                items += [f"            <li>{i}</li>" for i in g["items"]]
            return "\n".join(items)

        headline = (
            '      <p class="rating-headline" style="font-family:\'Playfair Display\',Georgia,serif; '
            'font-size:17px; font-weight:700; color:var(--gold-deep); font-style:normal; '
            f'margin:0 0 14px;">{p["premium_rating_headline"]}</p>\n'
            if p.get("premium_rating_headline") else "")
        return (
            '    <div class="rating-box">\n      <h3>Premium Rating</h3>\n'
            + headline +
            '      <div class="sf-grid">\n'
            f'        <div class="sf-col">\n          <ul>\n{col(cols[0])}\n          </ul>\n        </div>\n'
            f'        <div class="sf-col">\n          <ul>\n{col(cols[1])}\n          </ul>\n        </div>\n'
            "      </div>\n    </div>\n")
    if not placeholder:
        return ""
    return (
        '    <div class="rating-box">\n      <h3>Premium Rating</h3>\n'
        '      <p class="rating-headline" style="font-family:\'Playfair Display\','
        "Georgia,serif; font-size:17px; font-weight:700; color:var(--gold-deep); "
        'font-style:normal; margin:0;">Here is where your list of Premiums go!</p>\n'
        "    </div>\n")


def avm_chart(p):
    """Bar chart contrasting each comparable's assessment — the figure the
    online estimates anchor on — with what it actually sold for."""
    rows = [r for r in p["comps"]["rows"] if r[4] and r[5]]
    if len(rows) < 2:
        note("Roadmap: online-pricing chart OMITTED — needs at least two comps "
             "with both an assessment and a sale price.")
        return ""

    over = [(r[5] / r[4] - 1) * 100 for r in rows]
    avg = sum(over) / len(over)

    # A comp that sold BELOW its assessment makes "X% to Y% above" contradict
    # itself, so the sentence is written to match the spread it actually has.
    _avg_txt = (f"{avg:.0f}% above" if avg >= 0 else f"{abs(avg):.0f}% below")
    if min(over) >= 0:
        spread_sentence = (
            f"Every one of these homes sold for <b>{min(over):.0f}% to "
            f"{max(over):.0f}% above its assessment</b>, averaging <b>{avg:.0f}%</b>.")
    elif max(over) <= 0:
        spread_sentence = (
            f"Every one of these homes sold <b>{abs(max(over)):.0f}% to "
            f"{abs(min(over)):.0f}% below its assessment</b>, averaging "
            f"<b>{abs(avg):.0f}%</b>.")
    elif round(min(over)) == 0:
        # One comp landed a shade under its assessment but rounds to zero, so
        # "0% below" would be a strange way to say "level with it".
        spread_sentence = (
            f"These homes sold from <b>level with their assessment to "
            f"{max(over):.0f}% above</b> it, averaging <b>{_avg_txt}</b>.")
    else:
        spread_sentence = (
            f"These homes sold anywhere from <b>{abs(min(over)):.0f}% below to "
            f"{max(over):.0f}% above</b> their assessments, averaging "
            f"<b>{_avg_txt}</b>.")
    hi = max(max(r[5] for r in rows), max(r[4] for r in rows))

    # How the subject's own assessment compares with those same homes.
    avg_asmt = sum(r[4] for r in rows) / len(rows)
    subj_asmt = p["subject"].get("assessment") or 0
    gap = subj_asmt - avg_asmt
    gap_pct = (subj_asmt / avg_asmt - 1) * 100 if avg_asmt else 0
    if subj_asmt and gap_pct >= 5:
        gap_para = (
            '    <p class="price-para" style="margin-top:14px;">The online estimates also '
            f'miss a second point: this home&rsquo;s own assessment of <b>{money(subj_asmt)}</b> '
            f'is <b>{money(round(gap))} higher</b> than the {money(round(avg_asmt))} average '
            "across those same homes of equal size and age &mdash; "
            f"{gap_pct:.0f}% above them. Part of the difference the market pays for is "
            "already inside the assessment here, which is why this home does not carry the "
            "same percentage lift those sales did.</p>")
    else:
        gap_para = ""

    W, LEFT, RIGHT = 700, 150, 92
    span = W - LEFT - RIGHT
    row_h, gap, bar_h = 46, 12, 15
    top = 8
    H = top + len(rows) * (row_h + gap) + 10

    def x(v):
        return LEFT + span * (v / hi)

    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
             f'aria-label="Assessment against sale price for each comparable" '
             'xmlns="http://www.w3.org/2000/svg" style="font-family:Lora,Georgia,serif;">']
    # the legend sits under the chart, so no header labels here

    for i, (r, pct) in enumerate(zip(rows, over)):
        y = top + i * (row_h + gap)
        addr, asmt, sold = r[0], r[4], r[5]
        parts.append(f'<text x="{LEFT - 10}" y="{y + 14}" text-anchor="end" font-size="12" '
                     f'fill="#221C14">{addr}</text>')
        parts.append(f'<rect x="{LEFT}" y="{y + 3}" width="{x(asmt) - LEFT:.1f}" '
                     f'height="{bar_h}" fill="#C9BFA6" rx="2"/>')
        parts.append(f'<text x="{x(asmt) + 6:.1f}" y="{y + 15}" font-size="10.5" '
                     f'fill="#6E6552">{money(asmt)}</text>')
        parts.append(f'<rect x="{LEFT}" y="{y + 22}" width="{x(sold) - LEFT:.1f}" '
                     f'height="{bar_h}" fill="#C9A253" rx="2"/>')
        parts.append(f'<text x="{x(sold) + 6:.1f}" y="{y + 34}" font-size="10.5" '
                     f'font-weight="600" fill="#8A6A2E">{money(sold)}</text>')
        # Sign comes off the ROUNDED figure, not the raw one: a comp that sold
        # a shade under its assessment rounds to zero, and a hard-coded "+"
        # in front of it printed "+-0%".
        shown = round(pct)
        label = f"+{shown:.0f}%" if shown > 0 else (
            f"&minus;{abs(shown):.0f}%" if shown < 0 else "0%")
        parts.append(f'<text x="{W - 4}" y="{y + 25}" text-anchor="end" font-size="13" '
                     f'font-weight="700" fill="#8A6A2E">{label}</text>')
    parts.append("</svg>")
    svg = "\n".join(parts)

    return f"""<section>
  <div class="wrap">
    <h2 class="section-title">What the Online Estimates Miss</h2>
    <p class="section-sub">Zillow, Redfin and the other automated valuations lean on the
    public assessment. Here is the assessment of each comparable home against what a buyer
    actually paid for it.</p>

    <div style="max-width:720px; margin:0 auto;">
      {svg}
      <p style="text-align:center; font-size:12px; color:var(--muted); margin:6px 0 0;">
        <span style="display:inline-block; width:10px; height:10px; background:#C9BFA6;
        border-radius:2px; margin-right:5px;"></span>Assessment
        <span style="display:inline-block; width:10px; height:10px; background:#C9A253;
        border-radius:2px; margin:0 5px 0 18px;"></span>Actual sale price
      </p>
    </div>

    <p class="price-para" style="margin-top:20px;">{spread_sentence}
    An automated estimate built on assessment data starts that far
    behind the market before it considers condition, upgrades or presentation &mdash;
    none of which it can see.</p>
{gap_para}
  </div>
</section>

"""


RM_BADGE_CSS = """

  .rm-hero{position:relative; min-height:560px; display:flex; align-items:flex-end;
    overflow:hidden;
    background:
      radial-gradient(ellipse 900px 520px at 22% 12%, #2E3346 0%, transparent 62%),
      radial-gradient(ellipse 800px 500px at 82% 88%, #3A3527 0%, transparent 58%),
      linear-gradient(150deg, #1B2233 0%, #232838 48%, #2A2A22 100%);}
  .rm-hero > img{position:absolute; inset:0; width:100%; height:100%; object-fit:cover;}
  .rm-shade{position:absolute; inset:0;
    background:linear-gradient(to bottom, rgba(12,10,6,.50) 0%, rgba(12,10,6,.12) 32%,
      rgba(12,10,6,.86) 100%);}
  .rm-hero-inner{position:relative; z-index:2; width:100%; padding:38px 26px 34px;
    text-align:center; max-width:1040px; margin:0 auto;}
  .rm-hero-inner .seal{width:64px; display:block; margin:0 auto 10px;
    filter:drop-shadow(0 2px 8px rgba(0,0,0,.6));}
  .rm-hero-inner .bl{letter-spacing:.24em; font-size:11.5px; font-weight:700;
    color:#F0E4C4; text-transform:uppercase; text-shadow:0 2px 10px rgba(0,0,0,.85);}
  .rm-hero-inner .lbl{font-family:'Playfair Display',Georgia,serif; font-style:italic;
    font-size:19px; color:#F0E4C4; margin:6px 0 0; text-shadow:0 2px 10px rgba(0,0,0,.85);}
  /* On a recovery Roadmap the label IS the title, so it is set upright and
     in caps rather than as the italic subtitle the standard version uses. */
  .rm-hero-inner .lbl.recovery{font-style:normal; font-weight:700;
    font-size:clamp(17px,2.4vw,23px); letter-spacing:.14em; text-transform:uppercase;
    color:#F2DFA8; margin:8px 0 2px;}
  .rm-hero-inner h1{font-family:'Playfair Display',Georgia,serif; font-weight:700;
    color:#FFFDF7; font-size:clamp(28px,4.4vw,46px); margin:4px 0 2px; line-height:1.08;
    text-shadow:0 2px 14px rgba(0,0,0,.88);}
  .rm-hero-inner .city{color:#EDE6D3; font-style:italic; font-size:15px; margin:0 0 10px;
    text-shadow:0 2px 12px rgba(0,0,0,.85);}
  .rm-hero-inner .tag{color:#E2D9C2; font-size:13.5px; margin:0 0 12px;
    text-shadow:0 2px 12px rgba(0,0,0,.85);}
  .asof-pill{display:inline-block; font-size:11px; font-weight:700; letter-spacing:.04em;
    border:1px solid rgba(240,228,196,.6); color:#F0E4C4; padding:4px 14px;
    border-radius:20px; background:rgba(12,10,6,.35);}
  .rm-note{max-width:820px; margin:18px auto 0; font-size:12px; font-weight:700;
    letter-spacing:.07em; line-height:1.6; color:#F0E4C4; text-transform:uppercase;
    text-shadow:0 2px 10px rgba(0,0,0,.9);}
  @media (max-width:560px){ .rm-hero{min-height:440px;} .rm-note{font-size:11px;} }
  .rm-badges{display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin:16px 0 2px;}
  .rm-badge{border:1px solid rgba(240,228,196,.72); border-radius:4px; padding:9px 22px;
    background:rgba(12,10,6,.42); text-align:center;}
  .rm-badge .k{font-size:9.5px; letter-spacing:.15em; text-transform:uppercase;
    color:#D9C79A; font-weight:700;}
  .rm-badge .v{font-family:'Playfair Display',Georgia,serif; font-size:21px;
    font-weight:700; color:#FFFDF7; line-height:1.2;
    text-shadow:0 2px 10px rgba(0,0,0,.7);}
  @media print{ .rm-badges{margin:12px 0 0;} .rm-badge{padding:6px 16px;}
    .rm-badge .v{font-size:17px;} }
  .rm-band{background:#1B2233; color:#F6F1E3; padding:22px 0 50px;
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  .rm-cols{display:flex; flex-wrap:wrap; justify-content:center; text-align:center;}
  .rm-col{flex:1 1 210px; padding:6px 22px;}
  .rm-col + .rm-col{border-left:1px solid rgba(240,228,196,.28);}
  .rm-col .k{font-size:9.5px; letter-spacing:.15em; text-transform:uppercase;
    color:#D3B060; font-weight:700; margin-bottom:4px;}
  .rm-col .v{font-family:'Playfair Display',Georgia,serif; font-size:17px; font-weight:700;}
  .rm-col .s{font-size:11.5px; color:#BFB7A5; margin-top:3px;}
  .rm-specs{padding:26px 0 56px;}
  .rm-specs .wrap{max-width:1100px;}
  .rm-specs .rm-cols{flex-wrap:nowrap;}
  .rm-specs .rm-col{flex:1 1 0; min-width:0; padding:6px 10px;}
  .rm-specs .rm-col .k{font-size:10px; margin-bottom:8px; min-height:2.6em; display:flex;
    align-items:flex-end; justify-content:center;}
  .rm-specs .rm-col .v{font-size:23px; color:#FFFDF7; white-space:nowrap;}
  @media (max-width:760px){ .rm-specs .rm-cols{flex-wrap:wrap;} .rm-specs .rm-col{flex:1 1 40%;}
    .rm-specs .rm-col + .rm-col{border-left:none;} }
  @media print{ .rm-specs{padding:14px 0 40px;} .rm-specs .rm-col .v{font-size:18px;} }
  /* Casey, 23 Nov 2026: the home's specs in a navy box; the white box
     under it is the CST-vs-market comparison. "Just one navy box" -- the
     Authenticated Range / Money at Risk / market band is gone. */
  .rm-facts{display:flex; flex-wrap:wrap; justify-content:center; background:#1F2A44;
    border:1px solid #B8902F; border-radius:8px; margin:30px auto 0; position:relative;
    z-index:3; max-width:860px; box-shadow:0 8px 24px rgba(20,25,40,.25); padding:16px 8px;
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  .rm-fact{flex:1 1 110px; text-align:center; padding:5px 8px;}
  .rm-fact .n{font-family:'Playfair Display',Georgia,serif; font-size:19px; font-weight:700;
    color:#E8C77A; display:block; line-height:1.15;}
  .rm-fact .l{font-size:9.5px; letter-spacing:.06em; text-transform:uppercase;
    color:#C9D2E0; margin-top:3px;}
  /* Casey, 24 Nov 2026: "title is all in lower 1/2 of header. Needs balance.
     Make Casey Samson Team larger." New-listing heroes centre the title. */
  .rm-hero:has(.lbl.rts){align-items:center;}
  .rm-hero:has(.lbl.rts) .rm-shade{background:radial-gradient(ellipse 70% 65% at 50% 50%,
      rgba(12,10,6,.62) 0%, rgba(12,10,6,.38) 60%, rgba(12,10,6,.30) 100%);}
  .rm-hero:has(.lbl.rts) .seal{width:84px;margin-bottom:14px;}
  .rm-hero-inner .lbl.rts .rts-1{display:block;font-size:clamp(28px,3.8vw,42px);letter-spacing:.12em;
    text-transform:uppercase;line-height:1.1;}
  .rm-hero-inner .lbl.rts .rts-2{display:block;font-size:clamp(24px,3vw,32px);color:#FFFDF7;letter-spacing:.01em;margin-top:6px;}
  .rm-steps{padding:30px 0 60px;}
  .rm-steps .rm-col{flex:1 1 0;min-width:0;padding:6px 18px;}
  .rm-steps .rm-col .k{font-size:11px;letter-spacing:.22em;margin-bottom:8px;}
  .rm-steps .rm-col .v{font-size:26px;color:#FFFDF7;}
  .rm-steps .rm-col .s{font-size:15px;color:#C9D2E0;margin-top:6px;line-height:1.4;}
  @media (max-width:760px){ .rm-steps .rm-cols{flex-direction:column;} .rm-steps .rm-col + .rm-col{border-left:none;border-top:1px solid rgba(255,255,255,.15);} }
  .rm-subj{padding:26px 0 0;border-top:none!important;}
  .sch-row{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 0;margin-top:10px;padding-top:10px;border-top:1px solid #E4DCC8}
  .sch-row .sch{flex:1 1 160px;text-align:center;padding:2px 8px}
  .sch-row .sl{display:block;font:700 10.5px Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:#8A6A2E}
  .sch-row .sn{display:block;font-family:'Playfair Display',Georgia,serif;font-size:18px;font-weight:700;color:#1F2A44}
  .sch-row .sr{display:block;font:600 12.5px Georgia,serif;color:#8A6A2E;margin-top:2px}
  .sch-row .sch-src{flex:1 1 100%;text-align:center;font:italic 11px Georgia,serif;color:#71695A;margin-top:4px}
  .rm-subj-card{max-width:820px;margin:0 auto;background:#fff;border:1px solid var(--rule,#E4DCC8);border-radius:10px;padding:14px 18px;}
  .rm-subj-t{text-align:center;font:700 12px Georgia,serif;letter-spacing:.22em;text-transform:uppercase;color:var(--gold-deep,#8A6A2E);margin-bottom:8px;}
  .rm-subj-row{display:flex;flex-wrap:wrap;justify-content:center;}
  .rm-subj-f{flex:1 1 140px;text-align:center;padding:4px 8px;}
  .rm-subj-f .n{display:block;font-family:'Playfair Display',Georgia,serif;font-size:22px;font-weight:700;color:var(--gold-deep,#8A6A2E);}
  .rm-subj-f .l{display:block;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted,#71695A);margin-top:2px;}
  .rm-hero-inner .lbl.rts{font-size:26px; font-style:normal; font-weight:700; letter-spacing:.02em;
    color:#E8C77A; margin-bottom:6px;}
  .rc-sec{max-width:860px; margin:22px auto 0;}
  .rc-head{font-family:'Playfair Display',Georgia,serif; font-size:17px;
    text-align:center; color:var(--gold-deep); margin:0 0 12px;}
  .rc-card{background:var(--card); border:1px solid var(--rule); border-radius:8px;
    padding:16px 20px; text-align:center; max-width:560px; margin:0 auto;}
  .rc-note{font-size:11.5px; color:var(--muted); text-align:center;
    margin:11px auto 0; max-width:600px; line-height:1.55;}
  .rc-note b{color:var(--gold-deep);}
  .rc-k{font-size:9.5px; letter-spacing:.12em; text-transform:uppercase;
    color:var(--muted); font-weight:700;}
  .rc-v{font-family:'Playfair Display',Georgia,serif; font-size:23px;
    font-weight:700; color:var(--gold-deep); line-height:1.15; margin:5px 0 6px;}
  .rc-s{font-size:11.5px; color:var(--muted); line-height:1.4;}
  .rc-g{font-size:10px; letter-spacing:.05em; text-transform:uppercase;
    color:var(--muted-2); margin-top:7px;}
  @media print{ .rm-band{padding:14px 0 40px;} .rm-col .v{font-size:15px;}
    .rm-facts{margin:18px auto 0; padding:12px 6px;} .rm-fact .n{font-size:16px;}
    .rm-band, .rm-facts{break-inside:avoid;}
    .rc-sec{break-inside:avoid; margin-top:16px;} .rc-v{font-size:19px;} }

"""


# Aggressive Coming Soon sits this far under the Preview price.
AGGRESSIVE_UNDER_PREVIEW = 100_000

# ---- Predictive Analysis thresholds -------------------------------------
# Showings in the first week are the traffic test. Below SHOWINGS_FALLBACK_AT
# the price is not reaching enough buyers to create competition; below
# SHOWINGS_CRITICAL_AT, with the market also against the home, the gap is
# bigger than one standard step.
SHOWINGS_FALLBACK_AT = 5
SHOWINGS_CRITICAL_AT = 3
MAJOR_ADJUSTMENT = 100_000


def market_is_unfavorable(p):
    """Is the market currently working against this home? Same test the Red
    Flag box uses, so the two can never say different things. Returns
    (True/False/None, sentence) -- None when no figures are cached."""
    cache = HERE / "market_cache.json"
    slug = (p.get("market") or {}).get("slug")
    if not (cache.exists() and slug):
        return None, ""
    st = (json.loads(cache.read_text()).get(slug, {}) or {}).get("stats") or {}
    if not st:
        return None, ""
    uc = _pct(st.get("under_contract"))
    uc14 = _pct(st.get("uc_14"))
    control = (st.get("control") or "").strip()
    _sales = str(st.get("uc_30") or st.get("contracts", "")).strip()
    no_sales = _sales in {"\u2014", "-", "0", "0%"} or _pct(_sales) == 0
    bad = (no_sales
           or (uc is not None and uc < UC_WARN_AT)
           or (uc14 is not None and uc14 < ABSORPTION_WARN_AT)
           or control.lower().startswith("buyer"))
    bits = []
    if control:
        bits.append(f"a {control} Market")
    if no_sales:
        bits.append("<b>zero sales in the last 30 days</b>")
    if st.get("under_contract"):
        bits.append(f'{st["under_contract"]} of listings under contract')
    if st.get("uc_14"):
        bits.append(f'{st["uc_14"]} in the last 14 days')
    where = (p.get("market") or {}).get("name", "").replace(" Market", "")
    if not bits:
        return bad, ""
    return bad, f'Right now {where} is {", ".join(bits)}.'


def cohort_read(p, ceiling):
    """Where the pool actually is, in the market's own numbers.

    The valuation says what the home is worth. This says what buyers of this
    age and size are willing to shop at, which on a home that has been sitting
    is the only figure that decides anything. Everything here is read off the
    competition and the sold comps already on file -- nothing is asserted.
    """
    comp = p.get("competition") or []
    act = [c for c in comp if str(c.get("status", "")).strip() == "Active"]
    under = [c for c in act if c.get("list") and c["list"] < ceiling]
    sold = [r[5] for r in (p.get("comps", {}).get("rows") or []) if len(r) > 5 and r[5]]
    out = {"actives": len(act), "under": len(under), "sold": sold}
    if under:
        out["lo"], out["hi"] = min(c["list"] for c in under), max(c["list"] for c in under)
        doms = sorted(c.get("dom") or 0 for c in under)
        out["dom"] = doms[len(doms) // 2]
    if sold:
        out["sold_lo"], out["sold_hi"] = min(sold), max(sold)
    return out


def recovery_evidence(p, pool, upgrades, prem_top, current_list):
    """The pool diagnosis, in the market's own numbers.

    The Roadmap and the seller email make the same argument, so they build it
    here rather than each assembling its own copy. Every clause is omitted
    when the data behind it is missing -- that is what stopped the email
    printing "priced between $0 and $0" for a home whose competing actives all
    sit ABOVE the pool, and "$0 in upgrades" for a home with none.
    """
    co = cohort_read(p, pool)
    ev = []
    if co.get("under") and co["under"] == co["actives"]:
        ev.append(f'all {co["under"]} competing active listings are priced '
                  f'between {money(co["lo"])} and {money(co["hi"])}')
    elif co.get("under"):
        ev.append(f'{co["under"]} of the {co["actives"]} competing active '
                  f'listings are priced under {abbrev(pool)}')
    elif co.get("actives"):
        # Nothing under the ceiling at all: the actives are not the evidence,
        # they are part of the problem, and saying so is the honest reading.
        ev.append(f'not one of the {co["actives"]} competing active listings is '
                  f'priced under {abbrev(pool)}')
    if co.get("sold"):
        n = len(co["sold"])
        if n == 1:
            ev.append(f'the home that has actually sold went at {money(co["sold_lo"])}')
        elif n == 2:
            ev.append("the 2 homes that have actually sold went at "
                      f'{money(co["sold_lo"])} and {money(co["sold_hi"])}')
        else:
            # A range, not a pair -- naming only the ends of four sales as
            # "went at X and Y" reads as though there were two.
            ev.append(f'the {n} homes that have actually sold ranged from '
                      f'{money(co["sold_lo"])} to {money(co["sold_hi"])}')
    txt = ", and ".join(ev)
    ev_txt = (txt[0].upper() + txt[1:] + ". ") if txt else ""
    worth = (f'{money(upgrades)} in upgrades may well make this home worth '
             f'{abbrev(prem_top or current_list)}'
             if upgrades else
             f'The valuation supports {abbrev(prem_top or current_list)}')
    return ev_txt, worth


def _recovery_order(body):
    """Reorder a recovery Roadmap.

    Casey, 19 Oct 2026: *"Recovery roadmap should still have customary and
    premium pages over before Recovery strategy."* So the valuation leads,
    exactly as it does on a standard Roadmap -- the comps, Authenticated
    Values, Moving the Needle and the pricing work -- and the recovery
    argument lands on top of a value the seller has already been shown.

    The order is the standard one with the two recovery sections inserted
    where Predictive Analysis would have been:

        1. the valuation group (comps, Authenticated Values, pricing)
        2. Reconciling Value and Price, then Recovery Strategy
        3. Current Competition and market conditions
        4. the Buyer Portal card

    Until today the valuation was cut to the BACK of the page under an
    "Authenticating Value" eyebrow, on the reasoning that a seller who has
    been sitting wants the way out first. That buried the customary and
    premium work -- which is the product -- behind the reduction.
    """
    def cut(tag):
        a, b = f"<!--SEC:{tag}-start-->", f"<!--SEC:{tag}-end-->"
        if a not in body or b not in body:
            note(f"Roadmap: recovery reorder skipped — {tag} markers missing.")
            return None
        return body[body.index(a) + len(a):body.index(b)].strip()

    bg, nxt, comp = cut("bg"), cut("next"), cut("comp")
    if not all((bg, nxt, comp)):
        return body
    # The Buyer Portal card is written inside the strategy section but belongs
    # after the competition and market read -- that is the moment the seller
    # wants to see the same homes through a buyer's eyes.
    cta = ""
    a, b = "<!--SEC:cta-start-->", "<!--SEC:cta-end-->"
    if a in nxt and b in nxt:
        cta = nxt[nxt.index(a) + len(a):nxt.index(b)].strip()
        nxt = (nxt[:nxt.index(a)] + nxt[nxt.index(b) + len(b):]).strip()

    head = body[:body.index("<!--SEC:bg-start-->")]
    tail = body[body.index("<!--SEC:comp-end-->") + len("<!--SEC:comp-end-->"):]
    # No "Authenticating Value" eyebrow any more: it existed to label the
    # valuation as background when it sat at the back. Leading the page, it
    # needs no label -- it is the page, the same as on a standard Roadmap.
    return head + "\n".join(x for x in (bg, nxt, comp, cta) if x) + tail


PS_CSS = """
  /* Pricing Strategy print-out. Casey, 11 Oct 2026: "Try less words bigger
     text. I am struggling to read it." Nothing here drops below 12px in
     print — the page is kept to one sheet by cutting copy, never type. */
  /* ---- CST Market Intelligence masthead, short form ---------------- */
  .ps-mk{position:relative; overflow:hidden; padding:0;}
  .ps-mk-photo{position:absolute; top:0; right:0; width:27%; height:100%;
    object-fit:cover; opacity:.5;
    -webkit-mask-image:linear-gradient(to left,#000 36%,transparent 100%);
    mask-image:linear-gradient(to left,#000 36%,transparent 100%);}
  .ps-mk-inner{position:relative; z-index:2; display:flex;
    align-items:center; gap:18px; padding:14px 215px 13px 20px;}
  .ps-mk-eyebrow{font-size:10.5px; font-weight:700; letter-spacing:.3em;
    text-transform:uppercase; color:var(--gold-deep);}
  .ps-mk-eyebrow em{font-style:normal; font-size:8px; vertical-align:super;}
  .ps-mk .title{margin-top:5px;}
  .ps-mk .city{margin-top:4px;}
  @media print{
    .ps-mk-inner{padding:9px 186px 8px 16px; gap:12px;}
    .ps-mk-eyebrow{font-size:9px; letter-spacing:.24em;}
    .ps-mk-photo{width:24%;}
  }
  @media (max-width:720px){
    .ps-mk-inner{flex-direction:column; padding:16px 18px;}
    .ps-mk-photo{display:none;}
  }
  .ps-mast{display:flex; align-items:center; justify-content:space-between;
    gap:18px;}
  .ps-mast-mid{flex:1 1 auto; text-align:center; min-width:0;}
  .ps-mast-mid .city{margin-top:4px;}
  .ps-flag{flex:0 0 auto; border:1.5px solid var(--gold-deep); border-radius:9px;
    padding:12px 16px; background:var(--card); text-align:center;}
  .ps-flag-k{font-size:10px; font-weight:700; letter-spacing:.16em;
    text-transform:uppercase; color:var(--muted);}
  .ps-flag-t{font-family:'Playfair Display',Georgia,serif; font-size:19px;
    font-weight:700; color:var(--gold-deep); margin-top:2px; line-height:1.15;}
  .ps-qr{flex:0 0 auto; text-align:center;}
  .ps-qr svg{width:86px; height:86px; display:block;}
  .ps-qr-cap{font-size:9.5px; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase; color:var(--muted); margin-top:4px;}
  @media (max-width:720px){
    .ps-mast{flex-direction:column;}
    .ps-mast-mid{order:-1;}
  }

  /* Casey, 16 Oct 2026: the goal line moved up into the masthead, where
     it frames the sheet rather than opening it. */
  .ps-mk-goal{font-family:'Lora',Georgia,serif; font-size:13px;
    line-height:1.5; color:var(--ink); margin:7px auto 0; max-width:540px;}
  .ps-mk-goal b{color:var(--gold-deep); letter-spacing:.04em;}
  @media print{ .ps-mk-goal{font-size:10.5px; margin-top:4px; max-width:none;
    white-space:nowrap;} }
  .ps-goal{max-width:none; margin:0 auto; text-align:center; font-size:17px;
    line-height:1.5; color:var(--ink);}
  .ps-sec{max-width:780px; margin:26px auto 0;}
  .ps-head{font-family:'Playfair Display',Georgia,serif; font-size:19px;
    font-weight:700; color:var(--gold-deep); margin:0 0 6px;
    border-bottom:1px solid var(--gold-line); padding-bottom:6px;}
  .ps-body{font-size:16px; line-height:1.5; color:var(--ink); margin:10px 0 0;
    text-align:left;}
  .ps-head.ps-center{text-align:center;}
  /* The Advice line under Current Market Conditions. */
  .ps-advice{margin-top:12px; font-size:15px;}
  .ps-strategy{margin-top:13px; font-size:15px;}
  .ps-strategy b{color:var(--gold-deep);}
  .ps-sec.ps-mid .ps-head,
  .ps-sec.ps-mid .ps-body{text-align:center;}
  .ps-sec.ps-mid .ps-rows{max-width:700px; margin-left:auto; margin-right:auto;}
  .ps-sec.ps-mid .ps-mkt{margin-left:auto; margin-right:auto; max-width:700px;}
  .ps-sec.ps-mid .ps-k{white-space:nowrap; padding-right:16px;}
  @media print{
    .ps-sec.ps-mid .ps-rows{max-width:660px;}
  }
  /* The market gauges added a band to this sheet, so the value cards give
     the room back -- they are the tallest block on the page and lose
     nothing by sitting a little tighter. */
  .ps-vals{grid-template-columns:repeat(2,1fr) !important; max-width:620px;
    margin-top:9px !important;}
  .ps-vals .value-num{margin-bottom:0 !important; font-size:23px !important;}
  .ps-vals .value-card{padding:13px 16px !important;}
  .ps-vals .value-card h3{font-size:14px !important;}

  .ps-rows{width:100%; border-collapse:collapse; margin-top:8px;}
  .ps-rows td{padding:5px 0; border-bottom:1px solid var(--gold-line);
    font-size:17px; vertical-align:middle; text-align:left;
    word-spacing:normal; letter-spacing:normal;}
  .ps-rows tr:last-child td{border-bottom:none;}
  .ps-k{font-weight:700; width:36%;}
  .ps-d{color:var(--muted); font-size:14px; padding-left:14px; width:40%;}
  /* Scoped to .ps-rows td, not bare .ps-v: the row rule above is (0,1,1) and
     would otherwise win the cascade and set every price at body size. That
     silently undid Casey's "raise prices in preview coming soon etc 4 pts" —
     the figures printed at 13px on every sheet the system had produced. */
  .ps-rows td.ps-v{text-align:right !important; white-space:nowrap;
    font-family:'Playfair Display',Georgia,serif; font-size:19px;
    font-weight:700; color:var(--gold-deep); line-height:1.05;}
  /* A stated figure, not a recommended one — see price_row(mute=True). */
  .ps-rows td.ps-v.ps-mute{color:var(--ink);}
  /* Casey, 11 Oct 2026: the recovery sheet's four figures set smaller than
     the pricing sheet's. Seven-digit numbers in four rows at 32px took over
     the page; the pricing arc keeps 32px. */
  .ps-rows.ps-rec td.ps-v{font-size:19px;}  /* same as the pricing sheet */

  .ps-mwrap{display:grid; gap:14px; align-items:start; margin-top:10px;}
  .ps-grp{display:flex; flex-direction:column;}
  .ps-glabel{font-size:9px; font-weight:700; letter-spacing:.15em;
    text-transform:uppercase; color:var(--gold-deep); text-align:center;
    padding-bottom:4px; margin-bottom:6px;
    border-bottom:1px solid var(--gold-line);}
  .ps-mwrap .ps-mkt{margin-top:0 !important;}
  @media print{ .ps-mwrap{gap:9px; margin-top:5px;}
    .ps-glabel{font-size:7.5px; letter-spacing:.12em; padding-bottom:3px;
      margin-bottom:4px;} }
  .ps-mkt{display:grid; grid-template-columns:repeat(3,1fr); gap:12px;
    margin-top:12px;}
  .ps-mkt.n1{grid-template-columns:1fr; max-width:320px;}
  .ps-mkt.n2{grid-template-columns:repeat(2,1fr);}
  .ps-mkt.n4{grid-template-columns:repeat(4,1fr);}
  """ + GAUGE_CSS + """
  /* Every tile the same height, whatever its wording -- Casey, 16 Oct. */
  .ps-mkt .ps-tile{display:flex; flex-direction:column; min-height:116px;}
  .ps-mkt .ps-tile .gauge{margin-top:auto;}
  @media print{ .ps-mkt .ps-tile{min-height:88px;} }
  .ps-tile{background:var(--card); border:1px solid var(--gold-line);
    border-radius:8px; padding:13px 9px; text-align:center;}
  .ps-tile-n{font-family:'Playfair Display',Georgia,serif; font-size:21px;
    font-weight:700; color:var(--gold-deep); line-height:1.05;}
  /* Fixed rows so the four bars sit on one line however the wording
     wraps -- the same rule the Roadmap cards use. */
  .ps-tile-t{font-size:9.5px; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:#4A4034; margin-top:5px;
    line-height:1.25; height:24px; display:flex; align-items:center;
    justify-content:center;}
  @media print{ .ps-tile-t{font-size:8px; height:20px;} }
  .ps-mkt .ps-tile-l{height:30px; display:flex; align-items:center;
    justify-content:center;}
  @media print{ .ps-mkt .ps-tile-l{height:24px; font-size:8.5px !important;} }
  .ps-tile-l{font-size:12px; color:var(--muted); margin-top:5px;
    line-height:1.3;}

  @media print{
    /* Casey, 15 Oct 2026: "We need to save space." The closing line has to
       fit under the last price without pushing the sheet to a third page,
       so the sections, headings and body copy each give up a little. */
    .ps-sec{margin-top:4px !important; break-inside:avoid;}
    .ps-head{font-size:14.5px !important; padding-bottom:2px !important;
      margin-bottom:2px !important;}
    .ps-body{font-size:12.5px !important; margin-top:3px !important;}
    .ps-advice{margin-top:5px !important; font-size:12.5px !important;}
    .ps-strategy{margin-top:5px !important; font-size:12px !important;}
    .ps-rows td{padding:3px 0 !important; font-size:13px !important;}
    .ps-d{font-size:12px !important;}
    .ps-rows td.ps-v{font-size:19px !important;}
    .ps-rows.ps-rec td.ps-v{font-size:19px !important;}
    .ps-vals{margin-top:6px !important;}
    .ps-vals .value-card{padding:7px 10px !important;}
    .ps-vals .value-num{font-size:20px !important;}
    .ps-vals .value-card h3{font-size:11px !important;}
    .ps-mkt{gap:7px !important; margin-top:3px !important;}
    .ps-tile{padding:4px 5px 5px !important;}
    .ps-tile-n{font-size:16px !important;}
    .ps-tile-l{font-size:10.5px !important;}
    .ps-flag{padding:7px 11px !important;}
    .ps-flag-t{font-size:13px !important;}
    .ps-flag-k{font-size:9.5px !important;}
    .ps-qr svg{width:58px !important; height:58px !important;}
    .ps-qr-cap{font-size:9.5px !important;}
    header.masthead{padding:6px 0 5px !important;}
    .seal{width:21px !important; height:21px !important; margin-bottom:1px !important;}
    h1.title{font-size:16.5px !important; margin:0 !important;}
    .brandline{font-size:9px !important; margin-bottom:2px !important;}
    .ps-mast-mid .city{font-size:10.5px !important; margin-top:2px !important;}
    section{padding:8px 0 !important;}
    /* The footer was the only thing tipping onto a second sheet. */
    footer{padding:6px 0 2px !important;}
    footer *{line-height:1.25 !important;}
    footer .produced{font-size:11px !important; margin:0 0 2px !important;}
    footer .contact-line{font-size:9.5px !important; margin:0 !important;}
    footer .copy, footer .copyright, footer small{font-size:7.5px !important;
      margin-top:2px !important;}
  }

  /* Casey, 15 Oct 2026: the line that closes the sheet, above the
     qualifier. Whatever the list price does, this is what the Buyer Portal
     is arguing. */
  .ps-closing{max-width:780px; margin:16px auto 0; text-align:center;
    font-size:14.5px; font-weight:700; color:var(--gold-deep);
    line-height:1.45;}
  @media print{
    .ps-closing{font-size:11px !important; line-height:1.45 !important;
      break-inside:avoid;}
  }

  /* The Buyer Portal address, set as the thing to go and look at. */
  .ps-bp{display:inline-block; margin-left:10px; vertical-align:middle;}
  .ps-bp a{display:inline-block; font-family:'Lora',Georgia,serif;
    font-size:15px; font-weight:700; letter-spacing:.02em; color:#fff;
    background:var(--gold-deep); border-radius:999px; padding:9px 26px;
    text-decoration:none; box-shadow:0 2px 10px rgba(138,106,46,.28);}
  .ps-bp a:hover{background:#6f5526;}
  @media print{
    .ps-bp a{font-size:10.5px !important; padding:3px 15px !important;
      box-shadow:none !important;}
  }

  /* The qualifier that closes the sheet, under the last price. */
  .ps-note{max-width:780px; margin:14px auto 0; font-size:12.5px;
    line-height:1.45; color:var(--muted); text-align:center;
    border-top:1px solid var(--gold-line); padding-top:10px;}
  @media print{
    .ps-note{margin-top:6px !important; padding-top:5px !important;
      font-size:11px !important; break-inside:avoid;}
  }

  /* Page two: the track record. */
  .tr-back{max-width:780px; margin:0 auto; break-before:page;
    page-break-before:always;}
  .tr-sub{text-align:center; font-size:11px; color:var(--muted);
    margin:4px 0 0;}
  .tr-tiles{display:grid; grid-template-columns:repeat(3,1fr); gap:6px;
    margin:7px 0 8px;}
  .tr-tile{background:var(--card); border:1px solid var(--gold-line);
    border-radius:7px; padding:5px 5px; text-align:center;}
  .tr-tn{font-family:'Playfair Display',Georgia,serif; font-size:18px;
    font-weight:700; color:var(--gold-deep); line-height:1.1;}
  .tr-tl{font-size:9px; color:var(--muted); margin-top:2px; line-height:1.25;}
  /* The seller portal's stat band, brought onto the back page as it is:
     the team's six figures in gold, the market's four in ink beneath the
     measures they answer. */
  .tr-band{background:var(--card); border:1px solid var(--gold-line);
    border-radius:9px; padding:9px 12px 10px; margin:0 0 9px;}
  .tr-band-t{text-align:center; font-size:9.5px; font-weight:700;
    letter-spacing:.09em; text-transform:uppercase; color:var(--gold-deep);
    padding-bottom:7px; border-bottom:1px solid var(--gold-line);
    margin-bottom:8px;}
  .tr-grid{display:grid; grid-template-columns:repeat(6,1fr);
    row-gap:9px; align-items:start;}
  .tr-cell{text-align:center; padding:0 3px;}
  .tr-cell .tr-n{display:block;
    font-family:'Playfair Display',Georgia,serif; font-size:16px;
    font-weight:700; color:var(--gold-deep); line-height:1.1;}
  .tr-cell .tr-l{display:block; font-size:8px; letter-spacing:.04em;
    text-transform:uppercase; color:var(--muted); margin-top:2px;
    line-height:1.25;}
  .tr-cell.mkt .tr-n{color:var(--ink);}
  .tr-rowlabel{grid-column:span 2; display:flex; flex-direction:column; justify-content:center; align-items:center;
    text-align:center; font-size:9px; font-weight:700; letter-spacing:.06em;
    text-transform:uppercase; color:var(--gold-deep); line-height:1.3;
    padding:0 6px 0 2px;}
  /* One column, so the name sits under the team's volume and the five
     market figures line up under the five measures they answer. */
  .tr-rowlabel.one{grid-column:span 1; font-size:8px; letter-spacing:.04em;
    padding:0 4px 0 2px;}
  .tr-table{width:100%; border-collapse:collapse;}
  .tr-table th{font-size:8.5px; font-weight:700; letter-spacing:.06em;
    text-transform:uppercase; color:var(--muted); padding:0 4px 4px;
    border-bottom:1px solid var(--gold-deep); text-align:right;}
  .tr-table td{font-size:9.2px; padding:1.9px 4px;
    border-bottom:1px solid var(--gold-line); text-align:right;
    word-spacing:normal; letter-spacing:normal;}
  .tr-table th.tr-a, .tr-table td.tr-a,
  .tr-table th.tr-c, .tr-table td.tr-c{text-align:left;}
  .tr-a{width:30%;} .tr-c{width:16%;}
  .tr-table.dense td{font-size:8.4px; padding:1.25px 4px;}
  .tr-table.dense th{font-size:8px; padding-bottom:4px;}
  /* The one CST resale record runs to 50 rows and counting, and at .dense
     the last row fell onto a third sheet. One more step down keeps the whole
     record on the single back page it is printed to be. */
  .tr-table.denser td{font-size:7.9px; padding:0.75px 4px;}
  .tr-table.denser th{font-size:7.6px; padding-bottom:3px;}
  .tr-s{font-weight:700; color:var(--gold-deep);}
  .tr-o{color:var(--muted);}
  @media print{
    .tr-tiles{grid-template-columns:repeat(3,1fr) !important;}
    .tr-back{break-before:page !important; page-break-before:always !important;}
  }

  /* The button on the Roadmap that leads here. */
  .ps-cta{display:block; max-width:430px; margin:26px auto 0; text-align:center;
    background:var(--gold-deep); color:#fff; text-decoration:none;
    border-radius:9px; padding:14px 20px;
    font-family:'Playfair Display',Georgia,serif; font-size:16px; font-weight:700;}
  .ps-cta span{display:block; font-family:inherit; font-size:11px;
    font-weight:400; letter-spacing:.05em; opacity:.85; margin-top:3px;}
  @media print{ .ps-cta{display:none !important;} }
"""


SUMMARY_CSS = """
  /* Pricing Strategy Summary — one sheet, no argument. */
  .sum-sub{text-align:center; font-size:13px; color:var(--muted); margin:0 0 26px;}
  .sum-head{font-family:'Playfair Display',Georgia,serif; font-size:19px; font-weight:700;
    color:var(--gold-deep); text-align:center; margin:26px 0 10px;}
  .sum-table{width:100%; border-collapse:collapse;}
  .sum-table td{padding:9px 12px; border-bottom:1px solid var(--gold-line); font-size:14px;}
  .sum-l{width:34%; font-weight:700; color:var(--ink);}
  .sum-v{width:28%; text-align:right; font-family:'Playfair Display',Georgia,serif;
    font-size:18px; font-weight:700; color:var(--gold-deep); white-space:nowrap;}
  .sum-n{color:var(--muted); font-size:12.5px; padding-left:18px;}
  .sum-foot{display:grid; grid-template-columns:repeat(2,1fr); gap:16px;
    max-width:620px; margin:30px auto 0;}
  .sum-box{background:var(--card); border:1px solid var(--gold-line); border-radius:9px;
    padding:16px; text-align:center;}
  .sum-box-l{font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
    color:var(--muted);}
  .sum-box-v{font-family:'Playfair Display',Georgia,serif; font-size:25px; font-weight:700;
    color:var(--gold-deep); margin-top:5px;}
  .sum-tag{text-align:center; font-family:'Playfair Display',Georgia,serif; font-weight:700;
    font-size:16px; color:var(--ink); margin:26px 0 0;}
  @media print{
    .sum-head{margin:16px 0 7px !important; font-size:16px !important;}
    .sum-table td{padding:6px 10px !important; font-size:12px !important;}
    .sum-v{font-size:15px !important;}
    .sum-foot{margin-top:18px !important;}
    .sum-box-v{font-size:20px !important;}
    header.masthead{padding:16px 0 14px !important;}
    .seal{width:42px !important; height:42px !important; margin-bottom:8px !important;}
    h1.title{font-size:22px !important;}
    .subtitle{margin-bottom:8px !important; font-size:13px !important;}
    .sum-sub{margin-bottom:12px !important; font-size:11.5px !important;}
    section{padding:18px 0 !important;}
    /* The copyright line alone was tipping onto a second sheet. */
    .sum-foot{margin-top:14px !important;}
    footer{padding:10px 0 4px !important;}
    footer .copyright, footer small{font-size:8px !important;}
  }
"""


# Where a listing lives on caseysamson.com: street number and street name run
# together, no suffix, no quadrant, lower case. 2583 Vintage Crest Ln ->
# /market-snapshot/2583vintagecrest. The Buyer Portal uses the same slug with a
# "buy" prefix, which is what keeps the two from colliding.
SITE_BASE = _SITE_BASE
_SLUG_DROP = {"st", "street", "ave", "avenue", "dr", "drive", "ter", "terrace",
              "ct", "court", "rd", "road", "ln", "lane", "way", "pl", "place",
              "cir", "circle", "blvd", "boulevard", "pkwy", "parkway", "trl",
              "trail", "loop", "sq", "square", "ne", "nw", "se", "sw",
              "n", "s", "e", "w"}
EXAMPLE_BUYER_SITE = EXAMPLE_BUYER_PORTAL   # one address for the example, everywhere


def site_slug(p):
    words = re.sub(r"[^A-Za-z0-9 ]", "", p.get("address", "")).split()
    return "".join(w for w in words if w.lower() not in _SLUG_DROP).lower()


def site_roadmap_url(p):
    """The portal root on caseysamson.com — /market-snapshot/<slug>."""
    slug = site_slug(p)
    return f"{SITE_BASE}/{slug}" if slug else None


def site_roadmap_page(p):
    """The Roadmap itself, not the portal it sits in. A seller sent "the
    Roadmap" should land on the Roadmap, not on a nav page of cards."""
    root = site_roadmap_url(p)
    return f'{root}/{p["prefix"]}_Roadmap.html' if root else None


def market_posture(p):
    """Who controls the market, and therefore which pricing formula applies.

    Casey, 10 Oct 2026: "In Conservative market (buyers or neutral market)
    Preview price is first threshold under premium value. In Aggressive
    market first threshold over premium. Coming Soon in conservative market
    first threshold under Customary Value, aggressive first threshold over
    customary Value."

    Casey, 16 Oct 2026, institutional rule: "Coming Soon is the first
    threshold under Customary Value. No exceptions." That supersedes the
    aggressive half of the 10 Oct rule for Coming Soon; the posture still
    sets the Preview price.

    So the control reading in the weekly MSS decides both prices, and the
    whole strategy moves with the report rather than being set by hand.

    Returns the posture plus the four figures the Pricing Strategy section
    shows. `contracts` is deliberately NOT used as a stand-in for uc_30 — it
    is a year-over-year change, not a share of listings, and reading one as
    the other is the mistake that hid Aldie Family's genuine 0%.
    """
    m = p.get("market") or {}
    # The Local Market Snapshot writes its own figures onto the market block
    # before anything else is built, and they win: the homes this one is
    # competing with are a better read than a city report, and Casey asked
    # for Current Market Conditions to come from the local snapshot.
    stats = m.get("stats") or {}
    if not stats and m.get("slug"):
        cf = HERE / "market_cache.json"
        if cf.exists():
            stats = (json.loads(cf.read_text()).get(m["slug"]) or {}).get("stats") or {}
    control = (stats.get("control") or "").strip()
    cl = control.lower()
    if "seller" in cl:
        posture = "aggressive"
    elif "buyer" in cl or "neutral" in cl:
        posture = "conservative"
    else:
        posture = None
    # Average days on market is carried on the property file, not the MSS —
    # some markets (Madison, Culpeper) have no snapshot at all and a single
    # DOM figure is the only market reading there is.
    # The market's own report publishes days on market now, so a figure set
    # on the property block is only an override. Casey, 17 Oct 2026: every
    # market update carries all four gauges, and this is the one the city
    # reports used not to supply.
    dom = m.get("avg_dom") or stats.get("avg_dom")
    return {"posture": posture, "control": control, "name": m.get("name"),
            "under_contract": stats.get("under_contract"),
            "uc_30": stats.get("uc_30"), "uc_14": stats.get("uc_14"),
            # Casey, 18 Oct 2026: Success Rate opens the Summary's four.
            "success_rate": stats.get("success_rate"),
            "avg_dom": f"{int(dom)}" if dom else None,
            "advice": stats.get("advice")}


def summary_market_tiles(mk):
    """The Pricing Strategy Summary's four market gauges, from a
    market_posture()-shaped dict. Its own function so the weekly live feed
    (export_live_markets.py) renders exactly what a build does."""
    _tiles = [(mk.get("success_rate"), "Success rate"),
              (mk.get("under_contract"), "Total under contract"),
              (mk.get("avg_dom"), "Days on market, active and pending"),
              (mk.get("uc_30"), "Under contract on homes listed 30 days")]
    _have = [(a, b) for a, b in _tiles if a]
    _mkt_html = ""
    if _have:
        # Casey, 16 Oct 2026: "On the pricing summary we should have the
        # same wording as this... With limited space on the pricing flier
        # they need to be 4 across and leave out buyer or seller markets.
        # We explain to seller."
        #
        # So the sheet borrows the dashboard's own titles and descriptions
        # -- one vocabulary across both documents -- but stays four across
        # and drops the verdict capsule. The agent says "buyer's market" out
        # loud; the sheet does not need to say it four times.
        def _lbl(key, fallback):
            s = CMI_SPECS.get(key)
            if not s:
                return f'<div class="ps-tile-l">{fallback}</div>'
            return (f'<div class="ps-tile-t">{s["title"]}</div>'
                    f'<div class="ps-tile-l">{s["desc"]}</div>')
        _cells = "".join(
            f'      <div class="ps-tile">'
            f'<div class="ps-tile-n">{stat_icon(gauge_key(b))}{a}</div>'
            f'{_lbl(gauge_key(b), b)}'
            f'{gauge_html(gauge_key(b), a, verdict=False)}</div>\n'
            for a, b in _have)
        _mkt_html = (f'    <div class="ps-mkt n{len(_have)}">\n{_cells}'
                     f'    </div>\n    {CMI_SCALE_BARE}\n')

    return _mkt_html


LIVE_FEED = "https://cstmarketupdate.netlify.app/cst-live-markets.js"


def live_slug(p):
    """The MSS slug a portal's market sections can follow live, or None.

    Casey, 21 Oct 2026: "When cst snapshots updates once a week, all active
    portals should update without running new portals." Only a portal whose
    figures came from the MSS follows it -- one whose market block carries a
    Local Market Snapshot's own figures keeps them, because the weekly MSS
    does not publish those.
    """
    m = p.get("market") or {}
    slug = m.get("slug")
    if not slug:
        return None
    # Casey, 24 Nov 2026: town home markets (TH_) are not in the detached
    # MSS live feed, so their figures stay as built.
    import townhome_mss as _th
    if _th.is_th_slug(slug):
        return None
    cf = HERE / "market_cache.json"
    if not cf.exists():
        return None
    cached = (json.loads(cf.read_text()).get(slug) or {}).get("stats") or {}
    mine = m.get("stats") or {}
    if mine and cached and mine != cached:
        return None
    return slug if cached else None


def live_wrap(kind, slug, inner):
    return (f'<div class="cst-live" data-cst-live="{kind}" data-slug="{slug}">'
            f'{inner}</div>')


LIVE_LOADER = """<!--cst-live--><script>
(function(){
  var els=document.querySelectorAll('[data-cst-live]');
  if(!els.length) return;
  var s=document.createElement('script');
  s.src='""" + "https://cstmarketupdate.netlify.app/cst-live-markets.js" + """?h='+Math.floor(Date.now()/36e5);
  s.async=true;
  s.onload=function(){
    var F=window.CST_LIVE_MARKETS; if(!F||!F.markets) return;
    if(document.getElementById('cst-exp-bar')) return;
    [].forEach.call(els,function(el){
      var m=F.markets[el.getAttribute('data-slug')];
      var h=m&&m[el.getAttribute('data-cst-live')];
      if(h) el.innerHTML=h;
    });
  };
  document.head.appendChild(s);
})();
</script><!--/cst-live-->"""


def add_live_loader(out):
    """Every page in the folder with a live market section gets the loader."""
    n = 0
    for f in Path(out).glob("*.html"):
        h = f.read_text(encoding="utf-8")
        h = re.sub(r"<!--cst-live-->.*?<!--/cst-live-->", "", h, flags=re.S)
        if "data-cst-live=" in h:
            h = h.replace("</body>", LIVE_LOADER + "\n</body>", 1)
            n += 1
        f.write_text(h, encoding="utf-8")
    return n



def deep_after_fallback(fb):
    """Casey, 20 Nov 2026 (3106 Whimbrell): "final fall back at that level
    should have dropped $100k to $2.4." When the Fall Back is set by hand, the
    last rung steps down from it -- $100,000 at $2M and up, $50,000 from
    $500K, $25,000 under $500K -- never back up toward Coming Soon."""
    step = 100_000 if fb >= 2_000_000 else (50_000 if fb >= 500_000 else 25_000)
    return fb - step


def strategy_figures(p, s):
    """Every number the Pricing Strategy Summary shows, in one place.

    The one-page summary and the email version both read this, so the two can
    never quote different figures for the same property.
    """
    from pricing import (preview_price as _pvp, preview_price_above as _pvpa,
                         preview_over_customary as _pvoc,
                         increment_for as _inc_for, safe_haven as _safe_haven,
                         draw_downs as _draw_downs,
                         grid_line_at_or_above as grid_at_or_above)
    v = p["values"]
    mk = market_posture(p)
    posture = mk["posture"]
    if posture is None:
        posture = "conservative"
        _why = ("Refresh the MSS to price off the live market."
                if (p.get("market") or {}).get("slug") else
                "This market has no MSS snapshot, so there is no control "
                "reading to price off.")
        note(f'Pricing Strategy: no market-control reading for '
             f'{mk["name"] or "this market"}, so the conservative formulas are '
             "used — Preview and Coming Soon both at the first threshold "
             f"under Customary Value. {_why}")

    prem = v.get("premium") or (s.premium_top if s.has_upgrades else 0)

    cs_set = v.get("coming_soon_override")
    # Casey, 16 Oct 2026, institutional rule: "Coming Soon is the first
    # threshold under Customary Value. No exceptions."
    #
    # It used to test the first threshold OVER Customary wherever sellers
    # held the market (s.coming_soon_above). That is gone: the posture now
    # shows in the Preview price and in the draw-down ladder, never in the
    # price the home goes live at. A hand-set Coming Soon is still the
    # seller's own decision and still wins.
    cs_market = s.computed_coming_soon
    cs = int(cs_set) if cs_set else cs_market

    # Casey, 15 Oct 2026: "Prices should be safe haven under major
    # thresholds if they are $50K away." A conservative market takes the
    # haven: a price sitting just above a major threshold is outside every
    # search that stops there and buys nothing for the money. MacArthur at
    # $2,199,999 gave up everyone searching to $2.15M for $50,000.
    #
    # A hand-set Coming Soon price is left alone -- an override is a
    # decision already made.
    # Casey, 15 Oct 2026: "Basic strategy is move to lower threshold but IS
    # BUYER MARKET, if that number is within $50[K] of safe haven, you
    # should be at safe haven." A buyer's market, not merely a conservative
    # one: where neither side is in control the price is already at the
    # authenticated value and the market is not asking for another $50,000.
    safe = None
    if not cs_set and "buyer" in (mk.get("control") or "").lower():
        safe = _safe_haven(cs)
        if safe:
            note(f"Pricing: Coming Soon takes the safe haven at "
                 f"{money(safe)} rather than {money(cs)} \u2014 a "
                 f"conservative market and the {abbrev(safe + 1)} major "
                 f"threshold only {money(cs - safe)} below.")
            cs = safe

    # Casey, 13 Oct 2026: "Preview is first Threshold over Customary, Coming
    # Soon is first threshold under Customary then progression based on
    # performance."
    #
    # Casey, 14 Oct 2026: "When a home is in a buyers market the seller needs
    # to be more conservative. The preview would not be first threshold over
    # customary, it should be first threshold under customary just like coming
    # soon." So the 13 Oct rule is the AGGRESSIVE case, and in a conservative
    # market Preview and Coming Soon are the same number — the home previews
    # at the price it will go live at, which is what conservative means. A
    # hand-set price still wins.
    _cust = v.get("customary")
    if v.get("preview_override"):
        pv = int(v["preview_override"])
    elif prem and not p.get("preview_legacy"):
        # Casey, 27 Nov 2026: "Preview is the first threshold under Premium
        # Value" -- the seller's chance to test higher values.
        pv = _pvp(int(prem)) - 1
    elif _cust and posture == "aggressive":
        pv = _pvoc(int(_cust))
        # An aggressive market puts Coming Soon ABOVE Customary, on the same
        # grid line Preview takes — which would publish a Preview at or below
        # the live price.
        if cs and pv <= cs:
            _inc = _inc_for(int(_cust))
            pv = grid_at_or_above(cs + 1, _inc)
            note("Pricing Strategy: this market reads aggressive, so Coming "
                 f"Soon sits above Customary at {money(cs)} — the same grid "
                 "line the Preview rule calls for. Preview was stepped up to "
                 f"{money(pv)} to stay above the live price. Confirm how "
                 "Preview should be set in an aggressive market.")
    elif _cust:
        pv = cs
    elif prem:
        pv = _pvpa(prem) if posture == "aggressive" else _pvp(prem)
        note("Pricing Strategy: no Customary Value on file, so Preview fell "
             "back to the retired Premium-anchored formula. Add "
             '"customary" to the values block.')
    else:
        pv = 0

    if v.get("aggressive_coming_soon"):
        note("Pricing Strategy: the property file still carries "
             f'"aggressive_coming_soon": {money(int(v["aggressive_coming_soon"]))}. '
             "That field is retired — the market's control reading now picks a "
             "single Coming Soon price. The value is ignored; delete it from "
             "the property file.")

    # The two Predictive draw-downs can be set by hand, like Preview and
    # Coming Soon. Read here as well as in the Roadmap so the summary page and
    # the seller email can never quote a different ladder.
    # When the safe haven moved Coming Soon, the ladder moves with it --
    # otherwise the fall back would sit on the same number as the launch.
    _dd = _draw_downs(cs) if safe else {"fallback": s.fallback, "deep": s.deep}
    fb = int(v["fallback_override"]) if v.get("fallback_override") \
        else _dd["fallback"]
    deep = int(v["deep_override"]) if v.get("deep_override") else _dd["deep"]
    if not v.get("deep_override") and (v.get("fallback_override") or deep >= fb):
        deep = deep_after_fallback(fb)
    # Casey, 11 Oct 2026: five numbers override the protocol — Preview, Coming
    # Soon, Launch at 5+ showings, under 5, under 3. The 5+ launch is normally
    # the Coming Soon price held, so it only needs its own slot when he gives
    # a figure that differs.
    launch = int(v["launch_override"]) if v.get("launch_override") else cs
    floor = v.get("price_floor")
    if floor and deep < int(floor):
        deep = int(floor)
    if floor and fb < int(floor):
        fb = int(floor)
    # In a conservative market Preview and Coming Soon are deliberately the
    # same price, so only a Preview BELOW Coming Soon is wrong there. In an
    # aggressive market Preview is meant to set a ceiling the home then goes
    # live under, so equal is wrong too.
    if pv and cs and (pv < cs or (pv == cs and posture == "aggressive")):
        note(f"PRICING STRATEGY: the Preview price {money(pv)} is at or below "
             f"the Coming Soon price {money(cs)}. Check the overrides.")

    # Casey, 11 Oct 2026: "can you integrate the new Pricing Strategy Summary
    # into a recovery property". A home that is already on the market has no
    # Preview and no Coming Soon — it has a current list price, a buyer pool
    # sitting below it, and the two relaunch prices that come out of the 14-day
    # test. Those come straight from the engine, so the print-out, the Roadmap
    # and the seller email can never quote three different numbers.
    rec = None
    if p.get("listing_status") == "recovery" and p.get("current_list"):
        from pricing import recovery as _recovery
        _cl = int(p["current_list"])
        rec = dict(recovery_prices(p))
        _rb = p.get("recovery") or {}
        rec["current_list"] = _cl
        rec["dom"] = p.get("days_on_market")
        # Casey, 15 Oct 2026: "Anticipated buyer pool should also be $100
        # under." The threshold is where the pool ends; the number a seller
        # reads is the price that sits inside it, the same $100 under the
        # line the relaunch prices use.
        from pricing import UNDER_THRESHOLD as _UT
        rec["pool_line"] = _rb.get("buyer_pool") or s.closest_buyer_threshold
        rec["pool"] = rec["pool_line"] - _UT
        rec["pool_label"] = _rb.get("buyer_pool_label") or money(rec["pool"])
        # Casey, 15 Oct 2026: "If the list price and buyer pool are within
        # $10,000 of each other..." — the home is already sitting at the
        # edge of its pool, so a relaunch into the same pool is no move at
        # all. That is a different conversation from the standard ladder.
        rec["at_pool"] = abs(_cl - rec["pool"]) <= 10_000
    elif p.get("listing_status") == "recovery":
        note("Pricing Strategy: recovery property has no \"current_list\", so "
             "the print-out falls back to the Preview/Coming Soon arc, which "
             "is wrong for a home already on the market. Add the price the "
             "home is sitting at and rebuild.")

    return {"preview": pv, "coming_soon": cs, "deep": deep, "launch": launch,
            "safe_haven": safe,
            "fallback": fb, "no_room": bool(floor) and fb <= s.coming_soon,
            "posture": posture, "market": mk, "recovery": rec,
            "preview_set": bool(v.get("preview_override")),
            "coming_soon_set": bool(cs_set)}


def _qr_svg(url, scale=1, border=2):
    """Inline QR as SVG, sized by CSS at the call site. None when unavailable."""
    if not url or segno is None:
        return None
    import io
    buf = io.BytesIO()
    segno.make(url, error="m").save(
        buf, kind="svg", scale=scale, border=border, dark="#2B2622",
        svgclass=None, lineclass=None, omitsize=True, xmldecl=False, svgns=True)
    return buf.getvalue().decode("utf-8").strip()


def track_record_back(p):
    """Page two of the Pricing Strategy: the team's track record.

    Casey, 11 Oct 2026: "Would you be able to put my Track record on the back
    of the Pricing summary". Re-rendered compactly rather than embedded,
    because the source page is built to be scrolled and this one has to fit a
    sheet.

    Casey, 18 Oct 2026: "For Pricing strategy back page use this track record
    on all summaries." One record now, on every property's sheet — so this
    reads SUMMARY_TRACK_RECORD and never the property's own track_record,
    which still decides the standalone page and the nav card.
    """
    import html as _html
    src = TPL / SUMMARY_TRACK_RECORD
    if not src.exists():
        note(f"Pricing Strategy back page OMITTED — {src.name} is missing.")
        return ""
    raw = src.read_text()

    sub = re.search(r'<p class="subtitle">(.*?)</p>', raw, re.S)
    stats = re.findall(r'<span class="n">([^<]+)</span>\s*'
                       r'<span class="l">([^<]+)</span>', raw)
    body = re.search(r"<tbody>(.*?)</tbody>", raw, re.S)
    if not (stats and body):
        note(f"Pricing Strategy back page OMITTED — could not read the stats "
             f"or the sales table out of {src.name}.")
        return ""

    rows = re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S)
    out_rows = ""
    for r in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(cells) < 6:
            continue
        txt = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        # address, city, DOM, original list, sale, over asking — the source
        # page now carries exactly these six (see sync_portfolio.py), so the
        # back page copies them straight across.
        out_rows += (f'      <tr><td class="tr-a">{txt[0]}</td>'
                     f'<td class="tr-c">{txt[1]}</td>'
                     f'<td class="tr-n">{txt[2]}</td>'
                     f'<td class="tr-n">{txt[3]}</td>'
                     f'<td class="tr-s">{txt[4]}</td>'
                     f'<td class="tr-o">{txt[5]}</td></tr>\n')
    if not out_rows:
        note(f"Pricing Strategy back page OMITTED — no sales rows in {src.name}.")
        return ""

    # Casey, 11 Oct 2026: "Change % at or above list price to % Above list
    # price." The template's own figure counts at-list sales too, so relabeling
    # it would overstate the claim. Recount from the Over Asking column:
    # strictly positive only.
    _over = []
    for r in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(cells) < 6:
            continue
        raw_o = re.sub(r"<[^>]+>", "", cells[5]).strip().replace("$-", "-")
        digits = re.sub(r"[^\d\-]", "", raw_o)
        _over.append(int(digits) if digits not in ("", "-") else 0)
    _above = sum(1 for x in _over if x > 0)
    _above_tot = len(_over)

    # Casey, 11 Oct 2026: "lets take out median DOM avg price and PPSF. That
    # will give more room." Six tiles fit two rows instead of three, and the
    # room goes to the sales table.
    _drop = ("median days", "average sale price", "per square foot")
    keep = [(n_, l_) for n_, l_ in stats
            if not any(d in l_.lower() for d in _drop)]

    # "also what percentage closed over list what % sold in first week" — the
    # template states these as "29 of 41", which is the same fact but makes
    # the reader do the division. Lead with the percentage, keep the count.
    def _pct(n_, l_):
        m = re.fullmatch(r"(\d+)\s+of\s+(\d+)", n_.strip())
        if not m:
            return n_, l_
        hit, tot = int(m.group(1)), int(m.group(2))
        if not tot:
            return n_, l_
        share = f"{round(hit / tot * 100)}%"
        low = l_.lower()
        if "week" in low:
            return share, f"Sold in the first week ({hit} of {tot})"
        if "asking" in low:
            if _above_tot:
                a_share = f"{round(_above / _above_tot * 100)}%"
                return a_share, (f"Sold above list price "
                                 f"({_above} of {_above_tot})")
            return share, f"Closed at or over list ({hit} of {tot})"
        return share, f"{l_} ({hit} of {tot})"

    # Six: two clean rows of three. The template carries more than that
    # ("Markets served", "Sold above $1.5M"), which pushed a third row and
    # took back the room dropping the other three had freed.
    keep = [_pct(n_, l_) for n_, l_ in keep]
    # Casey, 12 Oct 2026: "Just bring this right to the track record
    # portfolio on Summary page" — the seller portal's own band, not a
    # restyled version of it: the team's six figures in gold across the top,
    # the market's four in ink directly beneath the measures they answer.
    # Casey, 29 Oct 2026: "use the one in the buyer portal as our Track
    # record every where but DOM is 6." The six tiles are the buyer portal's
    # production band; the sales table below still lists the resales.
    from build_index_v2 import production_rows as _prod
    keep = _prod(p)
    tiles = "".join(
        f'      <div class="tr-cell"><span class="tr-n">{n_}</span>'
        f'<span class="tr-l">{l_}</span></div>\n' for n_, l_ in keep[:6])

    # The band is named by the page it was read from, not by the $1.5M split.
    # Hardcoding "Homes Sold Under $1.5M" put that header over the under-3,500
    # SF record, whose top sale is $2,250,000 — the page said one thing and
    # the table under it said another.
    _h1 = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
    _name = re.sub(r"<[^>]+>", "", _h1.group(1)).strip() if _h1 else ""
    if not _name:
        _name = "Track Record " + ("Over" if show_luxury(p) else "Under") + " $1.5M"
        note(f"Pricing Strategy back page: {src.name} has no heading to name "
             f'the band, so it falls back to "{_name}".')
    # The subtitle reads "<price range> &mdash; <what the set is>". The range
    # is the half worth keeping; the other half restates the heading.
    _period = ""
    if sub:
        halves = re.split(r"&mdash;|—",
                          re.sub(r"<[^>]+>", "", sub.group(1)))
        _period = next((h.strip() for h in halves if "$" in h), "")
        _period = _period[:1].lower() + _period[1:] if _period else ""
    # The band is named by the record it is actually showing. Until 18 Oct
    # 2026 it took the property's "team_stats_title" verbatim. That title
    # names a size band — "Homes Sold Over 3,500 SF" — and neither the back
    # page nor the portal shows a size band any more, so honouring it would
    # caption both with something they contradict. The portal emits its own
    # note; this one is silent to keep the build log to one line per cause.
    # Casey, 18 Oct 2026: "In summary title The Casey Samson Team - Track
    # Record Comparison." The band is two rows now -- the team's record over
    # the Local Competition's -- so it is named for the comparison rather
    # than for the record alone. The price range moves out of the title with
    # it: it described the team's set, and a title over both rows should not
    # claim to bound either.
    _band_title = SUMMARY_BAND_TITLE

    # Casey, 12 Oct 2026: "The same stats from seller portal should appear on
    # Track record section of Pricing strategy summary." The seller portal
    # sets the team's figures against the same four measures for the market;
    # on its own the back page was only half that argument.
    _ml = p.get("market_local") or {}
    _mkt_row = ""
    if _ml.get("cells"):
        # The team's tiles directly above spell these out, and the market
        # figures sit in the same columns, so the printed row uses the short
        # form — a wrapped label pushed its number off the shared baseline.
        def _short(l):
            return (l.replace("Sold in the first week", "First week")
                     .replace("Sold in the first 10 days", "First 10 days")
                     .replace("% Sold in first 10 days", "First 10 days")
                     .replace("Sold above list price", "Above list")
                     .replace("Of original list price", "Of original list"))

        def _cell(c):
            # A null cell holds the column open. The market has no figure
            # that answers the team's total volume, and leaving the slot out
            # would slide every figure after it under the wrong measure.
            if not c:
                return '<div class="tr-cell mkt"></div>'
            return (f'<div class="tr-cell mkt"><span class="tr-n">{c[0]}</span>'
                    f'<span class="tr-l">{_short(c[1])}</span></div>')

        _cells = "".join(_cell(c) for c in _ml["cells"])
        # Casey, 18 Oct 2026: "Move title under CST volume and then line
        # everything else up." Five market figures leave exactly one column
        # for the name, under the team's volume, and each figure lands under
        # the measure it answers. Four figures are the older shape, where the
        # name took the first two columns instead.
        _one = " one" if len(_ml["cells"]) == 5 else ""
        _mkt_row = (f'\n      <div class="tr-cell tr-rowlabel{_one}">'
                    + _ml.get("label", "The market")
                    + '<br><span style="font-weight:600;font-size:.7em">Over the last 90 days</span>'
                    + "</div>" + _cells)
    else:
        # Casey, 12 Oct 2026: "The summary should mirror Portal." Without a
        # market_local set the portal falls back to the one cell that is
        # genuinely comparable — the days on market of the homes currently
        # listed against this one — so the back page carries the same cell
        # rather than dropping the row and diverging from the portal.
        _cd = competition_dom(p)
        if _cd:
            _lbl = (p.get("town_stats_label")
                    or f'Rest of the {p["city"]} {market_kind(p)} Market')
            _mkt_row = ('\n      <div class="tr-cell tr-rowlabel">' + _lbl
                        + '<br><span style="font-weight:600;font-size:.7em">Over the last 90 days</span></div><div class="tr-cell mkt"><span class="tr-n">'
                        + _cd[0] + '</span><span class="tr-l">Avg DOM &mdash; '
                        + f'the {_cd[1]} homes now on the market</span></div>')
            note("Pricing Strategy back page: market row shows days on market "
                 "only — the team figure is days to contract on closed sales, "
                 f"the market figure is days so far for the {_cd[1]} unsold "
                 "listings. Supply a closed-sale export for this size band to "
                 'fill the row as "market_local".')
        else:
            note("Pricing Strategy back page: no market comparison — the "
                 'property has no "market_local" block and no competition '
                 "listings with days on market, so the team figures stand "
                 "alone.")
    dense = (" dense denser" if len(rows) > 44
             else " dense" if len(rows) > 38 else "")
    if len(rows) > 56:
        note(f"Pricing Strategy back page: {len(rows)} sales is past what one "
             "sheet holds even at the tightest setting — check that the back "
             "page has not run to a third page.")
    return f"""
  <div class="tr-back">
    <div class="tr-band">
      <div class="tr-band-t">{_band_title}</div>
      <div class="tr-grid">
{tiles}{_mkt_row}
      </div>
    </div>

    <table class="tr-table{dense}">
      <thead><tr><th class="tr-a">Address</th><th class="tr-c">City</th>
      <th class="tr-n">DOM</th><th class="tr-n">Original List</th>
      <th class="tr-s">Sale Price</th><th class="tr-o">Over Asking</th></tr></thead>
      <tbody>
{out_rows}      </tbody>
    </table>
  </div>
"""


def build_strategy_summary(p, s, out):
    """The Pricing Strategy print-out — one sheet, read at arm's length.

    Casey, 11 Oct 2026: "move the print out of pricing strategy and QR code
    into header, Use the same boxes we display in buyer portal for customary
    and Premium. Try less words bigger text. I am struggling to read it."

    So the label box and the QR flank the masthead, Target Values uses the
    Buyer Portal's own .value-card, and every paragraph is one line. The
    earlier draft fitted a page by shrinking type to 10px, which is the wrong
    trade — cut the words, not the point size.
    """
    v, subj = p["values"], p["subject"]
    pre, addr = p["prefix"], p["address"]
    f = strategy_figures(p, s)
    _pv, _cs, _deep, _fb = f["preview"], f["coming_soon"], f["deep"], f["fallback"]
    _cons = f["posture"] == "conservative"
    mk = f["market"]
    rec = f.get("recovery")
    _is_rec = bool(rec)

    def price_row(k, val, d="", mute=False):
        # Gold is reserved for a price being recommended. A figure that is
        # simply a fact of the file — what the home is listed at today, where
        # the pool sits — is set in ink, so the sheet never reads as though
        # the current list price were the recommendation.
        return (f'      <tr><td class="ps-k">{k}</td>'
                f'<td class="ps-d">{d}</td>'
                f'<td class="ps-v{" ps-mute" if mute else ""}">{val}</td></tr>\n')

    # ---- Target Values: the Buyer Portal's own cards -------------------
    target = f"""    <div class="values-grid ps-vals">
      <div class="value-card">
        <h3>Customary Value</h3>
        <div class="value-num">{money(v["customary"])}</div>
      </div>
      <div class="value-card" style="border-color:var(--gold-line);
        box-shadow:0 4px 14px rgba(138,106,46,.08);">
        <h3>Premium Value</h3>
        <div class="value-num">{s.premium_display}</div>
      </div>
    </div>
"""

    # ---- Current Market Conditions -------------------------------------
    _ctrl = (mk.get("control") or "").lower()
    # Casey, 16 Oct 2026: "Remember I am talking to a seller, so just facts,
    # no explanation." One sentence: the posture, the market it comes from,
    # and what the 30-day figure says about it. Nothing about thresholds --
    # the price rows below say that themselves.
    if mk.get("posture") == "aggressive":
        _read = ("<b>Pricing Strategy: Aggressive</b>, based on current "
                 "seller&rsquo;s market")
    elif "buyer" in _ctrl:
        _read = ("<b>Pricing Strategy: Conservative</b>, based on current "
                 "buyer&rsquo;s market")
    elif "neutral" in _ctrl:
        _read = ("<b>Pricing Strategy: Conservative</b>, based on current "
                 "neutral market")
    else:
        _read = ""
        note("Pricing Strategy Summary: no market control reading on file, "
             "so the sheet carries no strategy line under the gauges.")
    # "If last 30 exceeds %UC, then homes priced and prepared are selling."
    _uc_all = _gauge_value(mk.get("under_contract"))
    _uc_new = _gauge_value(mk.get("uc_30"))
    _mom = "."
    if _read and _uc_all is not None and _uc_new is not None:
        if _uc_new > _uc_all + 1:
            _mom = (f', however <b>{mk["uc_30"]}</b> of homes listed in the '
                    'last 30 days went under contract, so well-priced homes '
                    'in good condition are selling.')
        elif _uc_new < _uc_all - 1:
            _mom = (f', and <b>{mk["uc_30"]}</b> of homes listed in the last '
                    f'30 days went under contract against '
                    f'<b>{mk["under_contract"]}</b> overall.')
        else:
            _mom = (f', with <b>{mk["uc_30"]}</b> of homes listed in the last '
                    f'30 days under contract, in line with '
                    f'<b>{mk["under_contract"]}</b> overall.')
    _strategy = (f'    <p class="ps-body ps-strategy">{_read}{_mom}</p>\n'
                 if _read else "")
    # Casey, 15 Oct 2026: "we will show 4 things: total % uc, and DOM for
    # active and pending, % uc of homes listed in last 30 days (DOM 8-38),
    # and % of total uc in last 14 days" — in that order.
    # Market strength first, then market momentum (Casey, 16 Oct 2026).
    # Casey, 18 Oct 2026: "Strategy Summary is Success Rate, %UC, 30 day"
    # plus days on market -- "we had to drop one in Summary to make it fit.
    # Let's drop 14 day instead and leave DOM in." So the sheet carries the
    # Roadmap's first four, in the Roadmap's order, and only the 14-day read
    # is left to the Roadmap.
    _mkt_html = summary_market_tiles(mk)
    if _mkt_html and live_slug(p):
        _mkt_html = live_wrap("ps", live_slug(p), _mkt_html)

    # ---- Recovery: value against price, then the two relaunch prices -----
    rec_problem = rec_relaunch = ""
    if _is_rec:
        _dom = (f'{rec["dom"]} days on market' if rec.get("dom")
                else "on the market now")
        if not rec.get("dom"):
            note("Pricing Strategy: no \"days_on_market\" on file, so the "
                 "Current List Price row reads \"on the market now\". The "
                 "number is the strongest thing in that row — add it.")
        # The preposition belongs in the row label, not in the 32px figure:
        # "Under $2,000,000" set at price size outweighs the list price above
        # it and breaks the right-aligned column.
        _pool_txt = re.sub(r"^(under|below|at or below)\s+", "",
                           rec["pool_label"], flags=re.I)
        # Casey, 15 Oct 2026: "'Buyers have rejected list price' should be in
        # Reconciling Value and Price section." It replaces the standard lead
        # rather than sitting beside it: "being worth more than the buyer
        # pool will pay" describes a home priced ABOVE its pool, and a home
        # already inside its pool is the opposite case.
        if rec.get("at_pool"):
            _lead = ('<b>Buyers have rejected the list price</b>, and any '
                     f'offers will already be discounted {money(25000)} under '
                     'the current list price. Beating them to a price drop '
                     'brings in a larger buyer pool.')
            note("Pricing Strategy: the list price "
                 f'{money(rec["current_list"])} is within {money(10000)} of '
                 f'the Anticipated Buyer Pool {money(rec["pool"])}, so '
                 "Reconciling Value and Price leads with the rejected-price "
                 "paragraph instead of the priced-above-the-pool one.")
        else:
            _lead = ('<b>Being worth more than the buyer pool will pay is not '
                     'the same as selling</b>, and days on market do not '
                     'close that distance.')
        rec_problem = f"""  <div class="ps-sec">
    <h2 class="ps-head">Reconciling Value and Price</h2>
    <p class="ps-body">{_lead}</p>
    <table class="ps-rows ps-rec"><tbody>
{price_row("Current List Price", money(rec["current_list"]), _dom, mute=True)}\
{price_row("Anticipated Buyer Pool", _pool_txt,
           "The pool for this age and size", mute=True)}    </tbody></table>
  </div>

"""
        # Casey, 15 Oct 2026: "Recommend 10-14 days temp off. During that
        # period Inspect condition and make necessary changes. Test buyer
        # pool see below, Analyze market conditions and relaunch at 5:00 on
        # a Thursday and plan an open house."
        # Casey, 20 Oct 2026, on 915 Winstead: "warn the Customary Buyer
        # Pool is at $1.75M". When a hand-set relaunch price still sits above
        # the buyer pool, the one-page sheet says so under the prices, not
        # only the Roadmap.
        _pw_pool = (p.get("recovery") or {}).get("buyer_pool")
        _pool_warn = ""
        if _pw_pool and rec.get("hard") and rec["hard"] > _pw_pool:
            _pool_warn = (f'    <p class="ps-body"><b>Warning:</b> the Customary '
                          f'Buyer Pool is at {abbrev(_pw_pool)}. Both relaunch '
                          f'prices sit above it.</p>\n')
        rec_relaunch = f"""  <div class="ps-sec">
    <h2 class="ps-head">The Relaunch</h2>
    <p class="ps-body"><b>Ten to fourteen days Temporarily Off Market.</b>
    During that period: inspect condition and make the necessary changes;
    test the buyer pool, below; and analyze market conditions. Relaunch at
    5:00 on a Thursday, and plan an open house.</p>
    <table class="ps-rows ps-rec"><tbody>
{price_row("2 or 3 inquire, market holds", money(rec["soft"]),
           f'Buyers are watching &mdash; {rec["soft_basis"]}')}\
{price_row("No one calls", money(rec["hard"]),
           rec["hard_basis"][:1].upper() + rec["hard_basis"][1:])}\
    </tbody></table>
{_pool_warn}  </div>

"""

    # ---- The three prices ----------------------------------------------
    preview_sec = ""
    if _pv:
        _pv_why = ("Set for this home." if f["preview_set"]
                   else "The first threshold under Premium Value &mdash; the "
                   "seller&rsquo;s chance to test higher values.")
        preview_sec = f"""  <div class="ps-sec ps-mid">
    <h2 class="ps-head">Preview</h2>
    <p class="ps-body">Public within two days of signing &mdash; Zillow,
    Homes.com, Samson. {_pv_why}</p>
    <table class="ps-rows"><tbody>
{price_row("Preview Price", money(_pv))}    </tbody></table>
  </div>

"""
    # Institutional rule, 16 Oct 2026: under Customary Value, always.
    _cs_why = ("Set for this home." if f["coming_soon_set"]
               else "The first threshold under Customary Value.")
    # Casey, 25 Oct 2026, on 2838 Cedar: "$1.15-$1.2 depending on preview
    # traffic and market conditions. The fall back minimum is $1.1." A
    # Coming Soon range is values.coming_soon_low_override (the low end) with
    # the Coming Soon override as the top; a floor at the fall back means
    # there is no further step, so the third row goes.
    _cs_low = v.get("coming_soon_low_override")
    _cs_show = (f"{money(int(_cs_low))} &ndash; {money(_cs)}"
                if _cs_low and int(_cs_low) < _cs else money(_cs))
    _floor_v = v.get("price_floor")
    _at_floor = bool(_floor_v) and _deep <= _fb == int(_floor_v)
    _launch = (price_row("6 or more showings",
                         _cs_show if (_cs_low and f["launch"] == _cs) else money(f["launch"]),
                         "Hold position")
               + price_row("2&ndash;5 showings", money(_fb),
                           "Minimum &mdash; no further reduction" if _at_floor
                           else "Presentation and marketing" if f["no_room"]
                           else "Move to the next buyer pool")
               + ("" if _at_floor else
                  price_row("Low or no showings", money(_deep),
                            "Condition and reach" if f["no_room"]
                            else "A further adjustment")))

    # Casey, 15 Oct 2026: "seller road map has flags headlines subheadlines
    # and 4 key stats. pricing strategy summary has just 4 key stats." So the
    # control sentence stays on the Roadmap, inside the flag block, and the
    # one-page print-out carries the figures alone.
    # Casey, 16 Oct 2026: "Pull Advice section out." The strategy line above
    # already says what the market dictates; the Advice sentence said it a
    # second time. It stays on the Roadmap, under Current Market Conditions.
    _advice = ""
    market_sec = f"""  <div class="ps-sec ps-mid">
    <h2 class="ps-head">Current Market Conditions</h2>
{_mkt_html}{_strategy}{_advice}  </div>

"""
    coming_soon_sec = f"""  <div class="ps-sec ps-mid">
    <h2 class="ps-head">Coming Soon</h2>
    <p class="ps-body"><b>If no contracts, Coming Soon pricing.</b> Live on
    the MLS with full photography and marketing. {_cs_why}</p>
    <table class="ps-rows"><tbody>
{price_row("Coming Soon Price", _cs_show,
           "Depending on Preview traffic and market conditions" if _cs_low else "")}    </tbody></table>
  </div>

"""
    launch_sec = f"""  <div class="ps-sec ps-mid">
    <h2 class="ps-head">The Launch</h2>
    <p class="ps-body"><b>If no contracts, Launch pricing.</b> First-week
    showings set the Active Launch Price.</p>
    <table class="ps-rows"><tbody>
{_launch}    </tbody></table>
  </div>

"""
    # Casey, 13 Oct 2026: "can we fit reality check in Pricing strategy
    # Summary." Page 1 had about 1.2in of tail, and the Roadmap's card is
    # roughly double that, so this is the compact form: the sheet's own
    # section pattern -- heading, one sentence, one right-aligned figure --
    # plus the affordability line. It closes the sheet rather than
    # interrupting the Preview / Coming Soon / Launch ladder.
    reality_sec = ""
    # Casey, 13 Nov 2026: no Reality Check on new construction.
    if v.get("customary") and not p.get("new_construction"):
        from pricing import reality_check as _rc
        _rr = _rc(v["customary"])

        def _pc(x):
            t = f"{x * 100:.2f}".rstrip("0").rstrip(".")
            return f"{t}%"

        reality_sec = f"""  <div class="ps-sec ps-mid">
    <h2 class="ps-head">Reality Check</h2>
    <p class="ps-body">If this home appreciated at the rate of inflation
    ({_pc(_rr["inflation_rate"])}) since the pandemic, the value would be:</p>
    <table class="ps-rows"><tbody>
{price_row("Value based on inflation", money(_rr["inflation"]))}    </tbody></table>
  </div>

"""

    # A home already on the market reads the other way round: what it is worth,
    # what it is listed at against the pool, what the market is doing, then the
    # move. The standard arc runs values, market, Preview, Coming Soon, Launch.
    # Casey, 16 Oct 2026: "Reality Check in the Summary is at the bottom
    # after all prices; on the Seller Roadmap it comes after Authenticated
    # Values." So the one-page sheet keeps its original order and only the
    # Roadmap moves.
    arc = (rec_problem + market_sec + rec_relaunch + reality_sec if _is_rec
           else market_sec + preview_sec + coming_soon_sec + launch_sec
                + reality_sec)

    # Casey, 15 Oct 2026: 'take out "these prices are based...." and add
    # distinctive link to buyer portal'. The qualifier is gone and the sheet
    # closes on the Buyer Portal instead -- the one place a seller can go and
    # see the Customary and Premium Values argued in front of buyers.
    # buyer_portal_url() is gated on "live", which suppresses every
    # seller-facing link until the page is published. Casey asked for this
    # address on the sheet by name, so it reads the configured URL directly
    # and the omission note below says that "live" is still off.
    _bpb = p.get("buyer_portal") or {}
    _bp = buyer_portal_url(p) or _bpb.get("url") or _bpb.get("deploy_to") or ""
    if _bp:
        # Casey, 15 Oct 2026: "don't spell out link just say What Buyers
        # See!" The address is the plumbing; the invitation is the point.
        # Casey, 15 Oct 2026: the market gauges made this sheet taller and
        # the pill, as its own block beneath the closing line, was the one
        # thing that would not fit -- it took a whole page with it. It now
        # sits inside the closing sentence, so the two travel together and
        # centre together.
        if (p.get("buyer_portal") or {}).get("live"):
            _bp_link = (f'<span class="ps-bp"><a href="{_bp}" target="_blank" '
                        'rel="noopener">What Buyers See!</a></span>')
        else:
            # Casey, 11 Oct 2026: "live" false "suppresses every seller-facing
            # link to that portal. Period." The sheet is seller-facing and it
            # is PRINTED, so a link here is the same failure as the dead QR --
            # worse, because the page it opens is the one the seller was told
            # about. It used to read the URL directly and print the pill
            # anyway, which is how 6029 Erinblair came out carrying a link to
            # a site that does not exist.
            _bp_link = ""
            note("Pricing Strategy: Buyer Portal link OMITTED from the sheet "
                 f'&mdash; "live" is false, so {_bp} would be a dead link on '
                 'a printed page. Set "live": true the day it goes up.')
    else:
        _bp_link = ""
        note("Pricing Strategy: no Buyer Portal link on the sheet — no URL "
             "for this property. The closing line still names the portal.")

    _back = track_record_back(p)
    _qr = _qr_svg(site_roadmap_page(p))
    if not _qr:
        note("Pricing Strategy print-out: QR OMITTED — "
             + ("segno is not installed." if segno is None
                else "no Roadmap address could be derived."))
    qr_html = (f'      <div class="ps-qr">{_qr}'
               f'<div class="ps-qr-cap">Full Roadmap</div></div>\n'
               if _qr else "      <div></div>\n")

    # Casey, 16 Oct 2026: "Bring back look with shortened header and current
    # message on pricing summary. You can move QR code to upper left."
    #
    # The CST Market Intelligence masthead, cut down for a sheet that has
    # one page to give: the eyebrow, the title, one line of attribution.
    # The QR takes the left, the home takes the right, faded back so the
    # type stays readable across it.
    _ps_hero = p.get("hero_photo")
    ps_photo = (f'  <img class="ps-mk-photo" src="{_ps_hero}" alt="">\n'
                if _ps_hero else "")
    if not _ps_hero:
        note("Pricing Strategy: no hero photo on file, so the masthead "
             'runs without one. Add "hero_photo" to the property file.')

    head = head_of("roadmap.html",
                   f'{addr} — {"Recovery" if _is_rec else "Pricing"} Strategy '
                   "— The Casey Samson Team",
                   PS_CSS + "\n" + SUMMARY_CSS + "\n" + PRINT_CSS)
    body = f"""<body>

<header class="masthead ps-mk">
{ps_photo}  <div class="wrap ps-mk-inner">
{qr_html}      <div class="ps-mast-mid">
        <div class="ps-mk-eyebrow">CST Market Intelligence<em>&trade;</em></div>
        <h1 class="title">{"Recovery" if _is_rec else "Pricing"} Strategy for {addr}</h1>
        <p class="city">The Casey Samson Team &middot; {p["city"]},
        {p["state"]} &middot; {p["report_date"]}</p>
        <p class="ps-mk-goal"><b>Goal:</b> use Customary Value, Market
        Conditions and Buyer Thresholds to establish
        {"Recovery" if _is_rec else "Pricing"} Strategy.</p>
      </div>
  </div>
</header>

<section>
  <div class="wrap">

  <div class="ps-sec">
    <h2 class="ps-head ps-center">Authenticated Values Based on Appraisal-Quality Comparables</h2>
{target}{('<p class="ps-closing" style="margin-top:10px;"><b>' + p["values"]["customary_note"] + '</b></p>') if p["values"].get("customary_note") else ""}  </div>

{arc}    <p class="ps-closing">Regardless of the list price, the Buyer Portal
    promotes the Customary and Premium Values and the home&rsquo;s amenities.{_bp_link}</p>
{_back}
  </div>
</section>

{footer(p, produced="The Casey Samson Team")}
</body>
</html>
"""
    (out / f"{pre}_Pricing_Strategy_Summary.html").write_text(head + body,
                                                              encoding="utf-8")


def _abbr_m(x):
    """$2,750,000 -> $2.75M; $1,775,000 -> $1.775M; $2,649,999 -> $2.65M; $575,000 -> $575K."""
    # Nearest $1,000, so $1,775,000 stays $1.775M and $1,699,000 $1.699M
    # (a $2,649,999 Coming Soon still reads $2.65M).
    x = int(round(x / 1_000.0) * 1_000)
    if x >= 1_000_000:
        return "$" + (f"{x / 1e6:.3f}".rstrip("0").rstrip(".")) + "M"
    return f"${x // 1000}K"


def _range_m(x):
    """A value as Casey writes it in the follow-up: the band it sits in --
    $2,470,613 -> $2.45M&ndash;$2.5M (50K bands over $1M, 25K under)."""
    step = 50_000 if x >= 1_000_000 else 25_000
    lo = int(x // step * step)
    return f"{_abbr_m(lo)}&ndash;{_abbr_m(lo + step)}"


def cst_over_list_rows():
    """Casey, 22 Nov 2026: the top 30 Casey Samson Team sales over list price
    since 2025 (data/CST_Over_List_Top30.csv, from his list), largest first."""
    import csv
    src = Path(__file__).resolve().parent / "data" / "CST_Over_List_Top30.csv"
    if not src.exists():
        return []
    rows = [dict(address=r["address"], city=r["city"], orig=int(r["list"]), sold=int(r["sold"]),
                 over=int(r["over"]), pct=r["pct"], dom=int(r["dom"]))
            for r in csv.DictReader(src.open(encoding="utf-8"))]
    return sorted(rows, key=lambda x: -x["over"])[:30]


def is_townhome(p):
    t = str((p or {}).get("property_type", "")).lower().replace("-", "").replace(" ", "")
    return t in ("townhome", "townhouse", "th", "rowhouse")


def townhome_table_html(H):
    """Casey, 22 Nov 2026: on a town home, "93% of our town homes sell over list
    price in an average of 5 days" with the town home sales behind it
    (data/CST_Townhome_Sales.csv). The figures are computed from the list."""
    import csv
    src = Path(__file__).resolve().parent / "data" / "CST_Townhome_Sales.csv"
    if not src.exists():
        return ""
    rows = [dict(address=r["address"], orig=int(r["list"]), sold=int(r["sold"]),
                 over=int(r["over"]), dom=int(r["dom"]))
            for r in csv.DictReader(src.open(encoding="utf-8"))]
    ov = sorted([x for x in rows if x["over"] > 0], key=lambda x: -x["over"])
    if not ov:
        return ""
    pct = round(100 * len(ov) / len(rows))
    days = round(sum(x["dom"] for x in ov) / len(ov))
    td = 'style="padding:5px 8px;border-bottom:1px solid #ddd;"'
    tr = 'style="padding:5px 8px;border-bottom:1px solid #ddd;text-align:right;"'
    th = 'style="padding:5px 8px;border-bottom:2px solid #000;text-align:left;"'
    thr = 'style="padding:5px 8px;border-bottom:2px solid #000;text-align:right;"'
    body = "".join(
        f"<tr><td {td}>{x['address']}</td><td {tr}>{money(x['orig'])}</td>"
        f"<td {tr}>{money(x['sold'])}</td><td {tr}><b>+{money(x['over'])}</b></td>"
        f"<td {tr}>{round(100 * x['sold'] / x['orig'])}%</td><td {tr}>{x['dom']}</td></tr>" for x in ov)
    return (f'<h3 {H}>CST Track Record &mdash; Town Homes</h3>\n'
            f'<p><b>{pct}% of our town homes sell over list price in an average of {days} days.</b></p>\n'
            f'<table style="border-collapse:collapse;width:100%;font-size:0.7em;font-family:inherit;">'
            f"<tr><th {th}>Town Home</th><th {thr}>List</th><th {thr}>Sold</th><th {thr}>Over List</th>"
            f"<th {thr}>% of List</th><th {thr}>Days</th></tr>{body}</table>\n"
            f'<p style="font-size:0.6em;color:#444;">{len(ov)} of {len(rows)} CST town home sales closed '
            "over list price. Source: MLS Bright.</p>\n")


def over_list_table_html(H='style="margin:26px 0 8px;font-weight:700;"', p=None):
    """The track record at the bottom of the seller emails (regular, recovery
    and follow-up): CST homes sold over list price, top 30 since 2025 -- or,
    on a town home ("property_type": "townhome"), the town home record."""
    if is_townhome(p):
        return townhome_table_html(H)
    ov = cst_over_list_rows()
    if not ov:
        return ""
    td = 'style="padding:5px 8px;border-bottom:1px solid #ddd;"'
    tr = 'style="padding:5px 8px;border-bottom:1px solid #ddd;text-align:right;"'
    th = 'style="padding:5px 8px;border-bottom:2px solid #000;text-align:left;"'
    thr = 'style="padding:5px 8px;border-bottom:2px solid #000;text-align:right;"'
    body = "".join(
        f"<tr><td {td}>{x['address']}, {x['city']}</td><td {tr}>{money(x['orig'])}</td>"
        f"<td {tr}>{money(x['sold'])}</td><td {tr}><b>+{money(x['over'])}</b></td>"
        f"<td {tr}>{x['pct']}</td><td {tr}>{x['dom']}</td></tr>" for x in ov)
    # Labeled "CST" so private-label branding never renames it: on a PL
    # portal the track record stays CST's (Casey, Nov 2026).
    return (f'<h3 {H}>CST Track Record</h3>\n'
            f'<table style="border-collapse:collapse;width:100%;font-size:0.7em;font-family:inherit;">'
            f"<tr><th {th}>Home</th><th {thr}>List</th><th {thr}>Sold</th><th {thr}>Over List</th>"
            f"<th {thr}>% of List</th><th {thr}>Days</th></tr>{body}</table>\n"
            f'<p style="font-size:0.6em;color:#444;">Top {len(ov)} CST sales over list '
            "price since 2025. Source: MLS Bright.</p>\n")

def _band_span(lo, hi):
    """Customary to Premium in Casey's round numbers: $1,791,436-$1,934,751
    -> $1.75M-$1.95M (50K bands over $1M, 25K under)."""
    step = 50_000 if lo >= 1_000_000 else 25_000
    a = int(lo // step * step)
    b = int(-(-hi // step) * step)
    return f"{_abbr_m(a)}&ndash;{_abbr_m(b)}"


def build_followup_email(p, s, out):
    """The follow-up email after the walk-through (Casey, 21 Nov 2026, from his
    3106 Whimbrell letter to Chad). "Once I have seen the home, I will update
    the model and those numbers appear on the follow up email": values and
    the pricing ladder come from the model; the home's own story comes from
    the property file's "followup" block --
      intro: [paragraphs], upgrade_desc, tier2_note, target_range,
      pool_note, target_areas: [...], golive_note, over_list_note, ps.
    Not written for a recovery (the recovery email covers it)."""
    if is_recovery(p):
        return
    fu = p.get("followup") or {}
    v = p["values"]
    f = strategy_figures(p, s)
    pre = p["prefix"]
    root = (seller_host(p) or "").rstrip("/")
    bp = (buyer_portal_url(p) or "").rstrip("/")
    mk = p.get("market") or {}
    slug = mk.get("slug") or ""
    mkt = f"https://cstmarketupdate.netlify.app/{slug.lower()}" if slug else None
    mkt_words = re.sub(r"\s*Market$", "", mk.get("name", "")).strip()
    mkt_words = (mkt_words.split()[0] + " " + " ".join(w.lower() for w in mkt_words.split()[1:])).strip() if mkt_words else ""
    names = p.get("seller_names") or "(Seller Name)"

    # ---- where we see value: straight from the model
    cust = int(v.get("customary_unadjusted") or v["customary"])
    ul, up = v.get("upgrade_labels"), int(v.get("significant_upgrades") or 0)
    vals = [f"<b>{_range_m(cust)}:</b> Customary Value"]
    if ul and up:
        pct = [re.search(r"(\d+)%", x).group(1) if re.search(r"(\d+)%", x) else "" for x in ul]
        desc = fu.get("upgrade_desc", "upgrade")
        vals.append(f"<b>{_range_m(int(v['customary']))}:</b> With a {pct[0]}% return on the "
                    f"{_abbr_m(up)} {desc} investment")
        vals.append(f"<b>{_range_m(int(v['premium']))}:</b> With a {pct[1]}% return"
                    + (f"&mdash;{fu['tier2_note']}" if fu.get("tier2_note") else ""))
    elif v.get("premium"):
        vals.append(f"<b>{_range_m(int(v['premium']))}:</b> Premium Value &mdash; finishes and "
                    "presentation above the standard")
    pv, cs, fb, deep = f["preview"], f["coming_soon"], f["fallback"], f["deep"]
    tr = fu.get("target_range") or (f"{_abbr_m(cs)}&ndash;{_abbr_m(pv)}" if pv > cs
                                     else _band_span(cust, int(v.get("premium") or cust)))
    vals.append(f"<b>{tr}:</b> Our target sales range once buyers experience the home")
    vli = "".join(f"<li>{x}</li>" for x in vals)

    # ---- the ladder: straight from the model
    steps = [f"Preview at <b>{_abbr_m(pv)}</b> on Zillow, Samson Properties, and Realtor.com to establish value and test interest.",
             f"Coming Soon at <b>{_abbr_m(cs)}</b> to gauge buyer response.",
             f"Go Live at <b>{_abbr_m(fb)}</b> if we don&rsquo;t generate offers. "
             + fu.get("golive_note", "This is a major buyer threshold that opens a larger pool."),
             f"Consider <b>{_abbr_m(deep)}</b> if interest and showings are weak. We let the market guide us. Your call."]
    sli = "".join(f"<li>{x}</li>" for x in steps)
    areas = fu.get("target_areas")
    if areas:
        areas = (", ".join(areas[:-1]) + ", and " + areas[-1]) if len(areas) > 2 else " and ".join(areas)

    def a(h, t):
        return f'<a href="{h}">{t}</a>' if h else t
    tools = [
        (f"{root}/{pre}_Roadmap.html" if root else None, "Seller Roadmap&trade;",
         "Authenticated values, preparation, pricing, and marketing plan."),
        (f"{root}/{pre}_Pricing_Strategy_Summary.pdf" if root else None, "Pricing Strategy Summary&trade;",
         "Pricing ladder, buyer thresholds, and adjustment triggers."),
        (bp + "/" if bp else None, "Buyer Portal&trade;",
         "Showcases your home&rsquo;s value, upgrades, amenities, and lifestyle advantages."),
        (f"{root}/{pre}_Buyer_Report.pdf" if root else None, "Buyer Flyer",
         "Helps buyers recognize and appreciate your home&rsquo;s premiums."),
        (mkt, "Market Snapshot", f"Weekly {mkt_words + ' ' if mkt_words else ''}market conditions and buyer demand."),
    ]
    tli = "".join(f"<li>{a(u, n)} &mdash; {d}</li>" for u, n, d in tools)

    pl = p.get("private_label") or {}
    ag = p.get("agent") or {}
    full = pl.get("name") or ag.get("display") or "Casey Samson"
    first = full.split()[0]
    team = pl.get("team_name") or ("Samson Properties" if pl else "The Casey Samson Team")
    phone = pl.get("phone") or ag.get("phone") or "703-508-2535"
    intro = "".join(f"<p>{x}</p>\n" for x in fu.get("intro", []))
    H = 'style="margin:26px 0 8px;font-size:24pt;font-weight:700;"'
    # Casey, 21 Nov 2026: Next Steps before the Seller Portal.
    _next = "".join(f"<p>{x}</p>\n" for x in fu.get("next_steps", [
        "With hundreds of thousands of dollars at risk, strategic improvements are critical&mdash;"
        "and a Casey Samson Team specialty.",
        "The right cosmetic improvements can deliver a substantial increase in perceived value at a "
        "fraction of the cost. When the home is complete and pictures are done, the Buyer Portal will "
        "be completed and ready for the buyers."]))
    # Casey, 21 Nov 2026: "At the end of the email show the homes from our
    # track record that sold over list price."
    _over = over_list_table_html(H, p) if fu.get("over_list_table", True) else ""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} — Follow-up email</title></head>
<body style="max-width:900px; margin:24px auto; padding:0 20px; line-height:1.4; font-family:'Times New Roman',Times,serif; font-size:24pt; color:#000;">

<p>{names},</p>

{intro}
<h3 {H}>Where We See Value</h3>
<ul style="margin:0 0 10px;">{vli}</ul>

<h3 {H}>Our Pricing Strategy</h3>
{f"<p>{fu['pool_note']}</p>" if fu.get("pool_note") else ""}
{f"<p>Our target: Buyers searching {areas}.</p>" if areas else ""}
<ol style="margin:0 0 10px;">{sli}</ol>

<p>{fu.get("over_list_note", "Selling over list is not unusual for our team (see below).")} The key is getting
buyers through the door to experience the upgrades and fall in love with the home.</p>

<h3 {H}>Next Steps</h3>
{_next}
<h3 {H}>Your CST Seller Portal&trade;</h3>
<p>Here are the five tools supporting our strategy:</p>
<ol style="margin:0 0 10px;">{tli}</ol>

<p>Together, these tools attract buyers, authenticate value, and strengthen our negotiating position.</p>

<p><i>It&rsquo;s Not a Price, It&rsquo;s a Strategy.&trade;</i></p>

<p>Let us know if you are ready for next steps.</p>

<p style="line-height:1.35;">{first}<br>{team}<br>{phone}</p>

<p>P.S. {fu.get("ps", "Please confirm you received this. Thanks!")}</p>
{_over}
</body></html>
"""
    (out / f"{pre}_Follow_Up_Email.html").write_text(html, encoding="utf-8")
    _write_eml(out, f"{pre}_Follow_Up_Email", html, f'Following up — {p["address"]}', p)
    if not fu:
        note('Follow-up email: no "followup" block -- written from the model alone '
             "(values and ladder); add intro paragraphs after the walk-through.")


def build_strategy_email(p, s, out):
    """The seller's pricing email, in the shape Casey approved on 9 Oct 2026.

    This is the Courtnie letter generalised. It opens on the meeting, hands the
    seller the Roadmap and the Market Update, promises the Buyer Portal, and
    then states the strategy in three blocks: Authenticated Values, The Test,
    Predictive Analysis. Plain throughout — one type size, black, no panels or
    rules. The only tables are invisible, there to right-align the figures.

    Times New Roman at 24pt is deliberate: Casey read and approved it at that
    size, which is why the body runs to 900px rather than the usual 640.
    """
    # Casey, 21 Nov 2026: on a recovery the recovery seller email is the
    # email -- the launch-style Pricing Summary Email is not written.
    if is_recovery(p):
        _old = Path(out) / f'{p["prefix"]}_Pricing_Summary_Email.html'
        for _x in (_old, _old.with_suffix(".eml")):
            if _x.exists():
                _x.unlink()
        note("Pricing Summary email: not written for a recovery -- the recovery seller email replaces it.")
        return
    v, subj = p["values"], p["subject"]
    pre, addr = p["prefix"], p["address"]
    f = strategy_figures(p, s)

    _bp_url = (p.get("buyer_portal") or {}).get("url")
    if _bp_url and _bp_url.rstrip("/") == (site_roadmap_url(p) or "").rstrip("/"):
        note(f"Pricing Summary email: the Buyer Portal url {_bp_url} is the same "
             "address as the Seller Roadmap. The Buyer Portal belongs at "
             f'{SITE_BASE}/buy{site_slug(p)}.')
    rm = site_roadmap_page(p) or (
        f'{p.get("portal_url", "").rstrip("/")}/{pre}_Roadmap.html')
    bp = _bp_url if (p.get("buyer_portal") or {}).get("live") else None
    mk = p.get("market") or {}
    mss = (f'https://cstmarketupdate.netlify.app/{mk["slug"]}.html'
           if mk.get("slug") else None)

    names = p.get("seller_names")
    if not names:
        names = "[Seller Name]"
        note("Pricing Summary email: seller_names not set — greeting left as a "
             "placeholder.")

    def table(head_l, head_r, rows):
        """Borderless, so the figures line up on the right and nothing else shows."""
        t = ('<table cellpadding="0" cellspacing="0" border="0" '
             'style="width:100%; border-collapse:collapse; margin:4px 0 0;">\n')
        if head_l:
            t += (f'  <tr><td style="padding:4px 0;"><i>{head_l}</i></td>'
                  f'<td align="right" style="padding:4px 0;"><i>{head_r}</i></td>'
                  '</tr>\n')
        for label, value in rows:
            t += ('  <tr>'
                  f'<td style="padding:4px 0; vertical-align:top;">{label}</td>'
                  '<td align="right" style="padding:4px 0; vertical-align:top; '
                  f'white-space:nowrap;"><b>{value}</b></td></tr>\n')
        return t + "</table>\n"

    # ---- opening ----------------------------------------------------------
    # The condition praise asserts the home needs no work before it goes on,
    # which is only true where Casey says it is. Off by default.
    _praise = (" We loved your home. We typically need to recommend improvements "
               "before bringing a property to market, so it is a pleasure to see "
               "a home in such excellent condition."
               if p.get("excellent_condition") else "")
    if not p.get("excellent_condition"):
        note('Pricing Summary email: "excellent_condition" not set, so the '
             "condition praise is left out. Add it to the property file for a "
             "home that needs no work before launch.")

    # ---- the two resources -----------------------------------------------
    res = [f'<p style="margin:0 0 6px;"><a href="{rm}">Seller Roadmap&trade;</a> '
           "&mdash; Our complete pricing and marketing strategy, including the "
           "analysis behind our recommendations.</p>"]
    if mss:
        # "Oakton Luxury Market" -> "luxury homes in Oakton"; a market named for
        # the city alone -> just "homes in Oakton".
        _seg = re.sub(r"\bMarket\b", "", mk.get("name", ""))
        _seg = re.sub(re.escape(p["city"]), "", _seg, flags=re.I).strip().lower()
        res.append(f'<p style="margin:0 0 6px;"><a href="{mss}">'
                   f'{mk.get("name", "Market")} Update</a> &mdash; Current market '
                   "activity and trends affecting "
                   f'{_seg + " " if _seg else ""}homes in {p["city"]}.</p>')
    else:
        note("Pricing Summary email: no market slug, so the Market Update link "
             "is left out.")
    _lead = ("Here are two resources to review:" if len(res) > 1
             else "Here is a resource to review:")
    res_html = f'<p>{_lead}</p>\n\n' + "\n\n".join(res) + "\n"

    # ---- the Buyer Portal -------------------------------------------------
    if bp:
        portal_p = (f'<p style="margin-top:16px;">Our <a href="{bp}">Buyer Portal'
                    "</a> is a powerful tool designed to help buyers recognize "
                    "your home&rsquo;s value and give them the confidence to pay "
                    "a premium price.</p>")
    else:
        # No live portal yet, so the seller gets the MacArthur one to look at.
        # Labelled as another home's, so nothing on it reads as theirs.
        portal_p = ('<p style="margin-top:16px;">I will also send you our Buyer '
                    "Portal, a powerful tool designed to help buyers recognize "
                    "your home&rsquo;s value and give them the confidence to pay "
                    "a premium price. Here is "
                    f'<a href="{EXAMPLE_BUYER_SITE}">an example built for '
                    f"{EXAMPLE_BUYER_HOME}</a> so you can see what buyers and "
                    "their agents will see. Yours follows once we have the "
                    "photographs.</p>")

    # ---- Authenticated Values --------------------------------------------
    if v.get("significant_upgrades"):
        values_b = table("Valuation", "Value", [
            ("Customary Value &mdash; Supported by comparable sales",
             money(v.get("customary_unadjusted") or v["customary"])),
            (f"Customary + &#8531; Premium Return &mdash; {money(v['significant_upgrades'])} in upgrades",
             money(v["customary"])),
            ("Premium Value &mdash; 108% of the upgraded Customary, our target", money(v["premium"])),
        ])
    else:
        values_b = table("Valuation", "Value", [
            (f"Dated Value &mdash; As the home stands today", s.dated_display),
            ("Customary Value &mdash; Supported by comparable sales",
             money(v["customary"])),
            ("Premium Value &mdash; Our target", s.premium_display),
        ])

    # ---- The Test ---------------------------------------------------------
    # One Preview price and one Coming Soon price, both picked by the market's
    # control reading rather than offered to the seller as a pair.
    _cons = f["posture"] == "conservative"
    _over_under = "under" if _cons else "over"
    # A hand-set price does not get a formula label — it was not derived from
    # one, and saying it was is a claim the seller could check against the
    # Authenticated Values table above it.
    test_rows = []
    if f["preview"]:
        _pv_basis = ("Set for this home." if f["preview_set"]
                     else "The threshold over Customary Value.")
        test_rows.append(
            ("Preview &mdash; Within two days of signing, with exposure on "
             "Zillow, Homes.com, and Samson"
             f'<div style="margin-top:10px;">{_pv_basis} Preview chatter and '
             "traffic carry into the Coming Soon period.</div>",
             money(f["preview"])))
    test_rows.append(
        ("Coming Soon" if f["coming_soon_set"] else
         f"Coming Soon &mdash; the threshold {_over_under} Customary Value",
         money(f["coming_soon"])))
    test_b = table("Strategy", "Price", test_rows)

    # ---- Predictive Analysis ----------------------------------------------
    pa = ('<p style="margin:0;">Buyer activity during the Preview and Coming '
          "Soon periods will help determine our Active Launch Price.")
    _floor = v.get("price_floor")
    if _floor:
        # Spoken, the way Casey writes it: "$2.5 million", not "$2.50M".
        _m = int(_floor) / 1_000_000
        _spoken = (f"${_m:.2f}".rstrip("0").rstrip(".") + " million" if _m >= 1
                   else money(int(_floor)))
        pa += (" Our strategy is to maintain a minimum launch price of "
               f"{_spoken}.</p>\n")
        pa_extra = ""
    else:
        # No floor set, so the showings ladder carries the Predictive Analysis
        # instead of a one-line minimum.
        pa += "</p>\n"
        pa_extra = table("Showings in week one", "Price", [
            ("6 or more &mdash; hold position", money(s.coming_soon)),
            ("2&ndash;5 &mdash; drop to the next buyer pool",
             money(f["fallback"])),
            ("Low or no showings &mdash; a further adjustment",
             money(f["deep"])),
        ])
        note("Pricing Summary email: no price_floor, so Predictive Analysis "
             "shows the showings ladder instead of a minimum launch price.")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{addr} &mdash; Pricing Strategy</title></head>
<body style="max-width:900px; margin:24px auto; padding:0 20px; color:#000;
 font-family:'Times New Roman',Times,serif; font-size:24pt; line-height:1.45;">

<p>{names},</p>

<p>It was great meeting you today!{_praise}</p>

{res_html}
{portal_p}

<p style="margin-top:20px;">As far as the price goes,</p>

<p><b>It&rsquo;s Not a Price. It&rsquo;s a Strategy.</b></p>

<p>The market ultimately determines the sales price. Our job is to position
your home in the right buyer pool, generate traffic, and create competition
that drives the highest possible value.</p>

<p>Here is a summary of the Casey Samson Team Pricing Strategy for
<b>{addr}</b>.</p>

<p style="margin:22px 0 2px;"><b>Authenticated Values&trade;</b></p>
{values_b}
<p style="margin:22px 0 2px;"><b>The Test &mdash; Preview &amp; Coming Soon</b></p>
{test_b}
<p style="margin:22px 0 2px;"><b>Predictive Analysis</b></p>

{pa}{pa_extra}
<p style="margin:22px 0 2px;"><b>Key Results pushed in Buyer Documents</b></p>
{table("", "", [("Expected Sales Price",
                 f"{abbrev(s.expected_low)}&ndash;{abbrev(s.expected_high)}")])}
<p style="margin-top:22px;">The goal is not simply to put a price on your home.
It is to attract qualified buyers, create competition, and maximize your
return.</p>

<p>Happy to walk through any of this with you.</p>

<p>{signoff(p, full=True)}</p>

</body></html>
"""
    (out / f"{pre}_Pricing_Summary_Email.html").write_text(html, encoding="utf-8")
    _write_eml(out, f"{pre}_Pricing_Summary_Email", html,
               f"{addr} — our pricing strategy", p)



GUIDES = Path(__file__).resolve().parent / "templates" / "guides"
GUIDE_FILES = {"roadmap": ("Seller_Roadmap_Guide.html", "{pre}_Roadmap_Guide.html",
                           "", "Guide to Understanding the Roadmap"),
               "mss": ("Market_Snapshot_Guide.html", "Market_Snapshot_Guide.html",
                       "", "Guide to Understanding the Market Snapshot"),
               "moveup": ("Move_Up_Guide.html", "Move_Up_Guide.html",
                          "", "Guide to Understanding the Move Up Calculator"),
               "buyer": ("Buyer_Portal_Guide.html", "Buyer_Portal_Guide.html",
                         "", "Guide to Understanding the Buyer Portal")}


def copy_guide(kind, out, pre=""):
    """Casey, 21 Nov 2026: attach the Seller Roadmap Guide to every Roadmap and
    the Buyer Portal Guide to every Buyer Portal (templates/guides/)."""
    import shutil
    src, dst, _, _ = GUIDE_FILES[kind]
    dst = dst.format(pre=pre)
    if (GUIDES / src).exists():
        shutil.copy(GUIDES / src, Path(out) / dst)
        return dst
    return None


# Casey, 23 Nov 2026: "take guide to understanding... off the top of roadmap.
# Links are in every section." No longer placed on the Roadmap; kept for reuse.
def _guide_bar(p, kind, root=None):
    """Gold bar under the page header linking to the guide. Absolute link when
    the site address is known, so it also works from the printed PDF."""
    if p.get("guides") is False:
        return ""
    _, dst, ask, link = GUIDE_FILES[kind]
    dst = dst.format(pre=p["prefix"])
    if root is None:
        root = (p.get("portal_url") or "").rstrip("/")
    href = f"{root}/{dst}" if root else dst
    # Casey, 22 Nov 2026: doubled -- "This has to be very obvious".
    # Casey, 21 Nov 2026: "Guide to Understanding the Roadmap" in the header,
    # the same size as The Casey Samson Team letters in the Roadmap hero.
    return (f'<div class="guide-bar" style="background:#231F1A;text-align:center;padding:18px 16px;">'
            f'<a href="{href}" target="_blank" rel="noopener" style="color:#F0E4C4;'
            f'font-size:23px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;'
            f'text-decoration:none;border-bottom:2px solid #B8902F;padding-bottom:3px;">{link}</a></div>\n')


GUIDE_NOTES = {}


def build_roadmap(p, s, out):
    subj = p["subject"]
    addr, city_state = p["address"], f'{p["city"]}, {p["state"]}'
    head = head_of("roadmap.html",
                   f'{addr} — Gold Standard Seller Roadmap™ — The Casey Samson Team',
                   ALERT_CSS + "\n" + RM_BADGE_CSS + "\n" + PS_CSS
                   + "\n" + PRINT_CSS)

    _sig = p["values"].get("significant_upgrades")
    if _sig:
        # Casey, 8 Nov 2026: "When we have a large upgrade Customary Value is
        # first $1.41, then Customary +1/3 Premium Return, $1.51, third is
        # Customary with 1/2 Premium Return, instead of dated customary premium"
        _base = p["values"].get("customary_unadjusted") or p["values"]["customary"]
        tiers = [
            ("Customary Value", "&#9733;&#9734;&#9734;", money(_base), "", [
                "Supported by comparable sales, before the upgrades.",
                "Kitchen and bathrooms updated within ~15 years.",
                "Overall presentation is competitive with comparable homes."]),
            ("Customary + &#8531; Premium Return", "&#9733;&#9733;&#9734;", money(p["values"]["customary"]),
             ' style="border-color:var(--gold-line); box-shadow:0 4px 14px rgba(138,106,46,.08);"', [
                f"<b>Customary Value plus one third of the {money(_sig)} invested in upgrades.</b>",
                "The return buyers reliably pay for a renovation.",
                "The basis for the Coming Soon price."]),
            ("Premium Value", "&#9733;&#9733;&#9733;", money(p["values"]["premium"]), "", [
                "108% of the upgraded Customary Value.",
                "Upgrades, finishes, and craftsmanship exceed the standard.",
                "Reached when the buyer pool competes for the home."]),
        ]
        # Casey's worksheet can name the two returns itself (3106 Whimbrell,
        # 20 Nov 2026: "25% Return Upgrades", "33% Return of Upgrades").
        _ul = p["values"].get("upgrade_labels")
        if _ul:
            _b = _base
            tiers[1] = (_ul[0], tiers[1][1], tiers[1][2], tiers[1][3], [
                f"<b>Customary Value plus {money(p['values']['customary'] - _b)} of the "
                f"{money(_sig)} invested in upgrades.</b>",
                "The return buyers reliably pay for a renovation.",
                "Where the Coming Soon price is set."])
            tiers[2] = (_ul[1], tiers[2][1], tiers[2][2], "", [
                f"<b>Customary Value plus {money(p['values']['premium'] - _b)} of the upgrades.</b>",
                "Upgrades, finishes, and craftsmanship exceed the standard.",
                "Reached when the buyer pool competes for the home."])
    elif s.has_upgrades:
        # Casey, 13 Oct 2026, on 12901 Popes Head: "three values should still
        # be dated, customary and upgraded." The upgrades branch used to drop
        # the Dated tier and split the Premium Range across two cards
        # ("33% Return of Upgrade", "50% of Upgrades"), which gave a different
        # set of three from every other property. Now it is the same three
        # tiers as everywhere else, with Upgraded carrying the range.
        _up_rng = f"{money(s.premium_bottom)} &ndash; {money(s.premium_top)}"
        tiers = [
            ("Dated Value", "&#9733;&#9734;&#9734;", s.dated_display, "", [
                "Kitchen and bathrooms are largely original.",
                "Paint, lighting, hardware, flooring, and finishes are dated.",
                "Overall presentation is below standard."]),
            ("Customary Value", "&#9733;&#9733;&#9734;", money(p["values"]["customary"]),
             ' style="border-color:var(--gold-line); box-shadow:0 4px 14px rgba(138,106,46,.08);"', [
                "Kitchen and bathrooms updated within ~15 years.",
                "Paint, lighting, hardware, flooring, finishes reflect current standard.",
                "Overall presentation is competitive with comparable homes."]),
            ("Upgraded Value", "&#9733;&#9733;&#9733;", _up_rng, "", [
                f'Based on {money(p["values"]["upgrades"])} in extraordinary '
                "upgrades.",
                "Low end returns a third of the spend, high end half of it.",
                "Upgrades recognised by the buyer pool at sale."]),
        ]
    elif not p["values"].get("dated"):
        # Brand-new construction has no meaningful Dated tier.
        note("Roadmap: Dated tier OMITTED — no dated value supplied.")
        tiers = [
            ("Customary Value", "&#9733;&#9733;&#9734;", money(p["values"]["customary"]), "", [
                "Kitchen and bathrooms updated within ~15 years.",
                "Paint, lighting, hardware, flooring, finishes reflect current standard.",
                "Overall presentation is competitive with comparable homes."]),
            ("Premium Value", "&#9733;&#9733;&#9733;", money(p["values"]["premium"]),
             ' style="border-color:var(--gold-line); box-shadow:0 4px 14px rgba(138,106,46,.08);"', [
                "Kitchen and bathrooms updated within ~10 years.",
                "Upgrades, finishes, and craftsmanship exceed the standard.",
                "Overall presentation distinguishes the property from the competition."]),
        ]
    else:
        tiers = [("Dated Value" if s.dated_label == "Dated Value" else s.dated_label,
                  "&#9733;&#9734;&#9734;", s.dated_display, "", [
                      "Kitchen and bathrooms are largely original.",
                      "Paint, lighting, hardware, flooring, and finishes are dated.",
                      "Overall presentation is below standard."]),
                 ("Customary Value", "&#9733;&#9733;&#9734;", money(p["values"]["customary"]),
                  ' style="border-color:var(--gold-line); box-shadow:0 4px 14px rgba(138,106,46,.08);"', [
                      "Kitchen and bathrooms updated within ~15 years.",
                      "Paint, lighting, hardware, flooring, finishes reflect current standard.",
                      "Overall presentation is competitive with comparable homes."]),
                 (s.premium_label, "&#9733;&#9733;&#9733;", s.premium_display, "", [
                     "Kitchen and bathrooms updated within ~10 years.",
                     "Upgrades, finishes, and craftsmanship exceed the standard.",
                     "Overall presentation distinguishes the property from the competition."])]
    # Casey, 29 Oct 2026: "when we go to Authenticated Value you add
    # Customary Value is based on 33% recovery of the $1.5M in improvements!"
    _cn = p["values"].get("customary_note")
    if _cn and not _sig:
        tiers = [(t[0], t[1], t[2], t[3], [f"<b>{_cn}</b>"] + list(t[4]))
                 if t[0] == "Customary Value" else t for t in tiers]
    # Upgrades label renders 2pt larger than the standard tier labels.
    cards = []
    # Casey, 8 Nov 2026: "line up numbers" -- when any tier label wraps to two
    # lines, every label gets two lines' height so the prices sit level.
    _two = any(len(re.sub(r"&[^;]+;", "x", t[0])) > 22 for t in tiers)
    for label, stars, amount, style, bullets in tiers:
        # The section is "Authenticated Prices" now, so the tiers inside it
        # read Price too. Only the printed label changes -- the engine's own
        # "Customary Value" basis labels are untouched.
        label = re.sub(r"\bValue\b", "Price", label)
        big = ' style="font-size:15px;"' if label.startswith("Based on") else ""
        if _two:
            big = (' style="min-height:3.3em;display:flex;align-items:center;justify-content:center;'
                   + ('font-size:15px;' if label.startswith("Based on") else '') + '"')
        cards.append(
            f'      <div class="value-card"{style}>\n'
            f'        <h3{big}>{label}</h3>\n'
            f'        <div class="value-stars">{stars}</div>\n'
            f'        <div class="value-num">{amount}</div>\n'
            "        <ul>\n"
            + "".join(f"          <li>{b}</li>\n" for b in bullets)
            + "        </ul>\n      </div>")

    if p["comps"]["rows"]:
        rm_comps_section = f"""<section>
  <div class="wrap">
    <h2 class="section-title">Appraisal-Quality Comparable Analysis</h2>
    <p class="section-sub">{("Comparable analysis supports a value of " + money(p["values"]["customary_unadjusted"]) + " before improvements, and " + money(p["values"]["customary"]) + " with the upgrades.") if (p["values"].get("significant_upgrades") and p["values"].get("customary_unadjusted")) else ("Comparable analysis supports a value of " + money(p["values"]["customary_unadjusted"]) + ", adjusted " + ("down" if (p["values"].get("adjustment") or {}).get("amount", 0) > 0 else "up") + " to " + money(p["values"]["customary"]) + " for " + (p["values"].get("adjustment") or {}).get("reason", "the adjustment") + ".") if (p["values"].get("customary_unadjusted") and (p["values"].get("adjustment") or {}).get("reason") and "upgrade" not in p["values"]["adjustment"]["reason"]) else ("Comparable analysis supports a value of " + money(p["comps"]["subject_value"]) + " before improvements.") if p["comps"].get("subject_value") else ("Comparable analysis supports the authenticated Customary Value near " + abbrev(p["values"]["customary"]) + ".")}</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Property</th><th>Built</th><th>Finished SF</th><th>Lot</th><th>Assessment</th><th>Sales Price</th><th>Adjusted PPSF</th><th>% of Assessment</th></tr></thead>
        <tbody>
{comp_rows([[addr, subj["built"], subj["sf"], subj["lot"], subj["assessment"], p["comps"].get("subject_sale") or p["comps"].get("subject_value")]], cls="total-row", extra={} if p["comps"].get("subject_sale") else {addr: p["comps"].get("subject_value") or p["values"]["customary"]})}
<!-- Casey, 29 Oct 2026: averages move up under the subject. -->
{comp_rows(p["comps"]["summary"], cls="total-row", extra=p["comps"].get("summary_ppsf") or {})}
{comp_rows(p["comps"]["rows"], extra=p["comps"].get("adjusted") or {}, p=p)}
        </tbody>
      </table>
    </div>
{__import__("market_map").grade_legend(p)}
{comp_gallery(p["comps"]["rows"])}  </div>
</section>
"""
    else:
        rm_comps_section = ""
        note("Roadmap: Appraisal-Quality Comparable Analysis OMITTED — no comps supplied.")

    # With only Customary and Premium, narrow the grid so the pair sits centred
    # instead of leaving an empty third column.
    grid_style = (' style="grid-template-columns:repeat(2,1fr); max-width:520px;"'
                  if len(tiers) == 2 else "")

    avm_section = avm_chart(p)
    if p.get("listing_status") == "recovery":
        # A seller who has sat on the market does not need to be told what
        # Zillow misses. They need the way out first, and the valuation as
        # background underneath it.
        avm_section = ""
        note("Roadmap: online-estimate chart left out of the recovery Roadmap.")

    stat, comp_body, comp_lede = competition_block(p["competition"], p, s)

    alert_html = ""
    # The alert argues for pricing BELOW a major threshold. When a floor has
    # been set at or above that threshold, the argument is one the seller has
    # already declined, so showing it would have the page contradict itself.
    _alert_floor = p["values"].get("price_floor")
    # Casey, 15 Oct 2026: once the price takes the safe haven, the alert is
    # arguing for something already done. Telling a seller priced at
    # $2,149,999 that they sit $49,999 above the $2.15M threshold is simply
    # wrong, so the box comes off the moment the haven is taken.
    _sf = strategy_figures(p, s)
    if s.alert and is_recovery(p):
        # Casey, 16 Nov 2026 (4322 Thomas Brigade): a recovery is priced by
        # its relaunch plan; the Coming Soon threshold alert does not apply.
        note("Roadmap: Major Buyer Threshold alert dropped -- recovery listing.")
        s.alert = None
    if s.alert and _sf.get("safe_haven"):
        note("Roadmap: Major Buyer Threshold alert dropped \u2014 the price "
             f'already took the safe haven under {money(s.alert["major"])}.')
    elif s.alert and _alert_floor and s.alert["major"] <= int(_alert_floor):
        note(f'Roadmap: Major Buyer Threshold alert SUPPRESSED — it argues for '
             f'pricing below {money(s.alert["major"])}, which the '
             f'{money(int(_alert_floor))} floor rules out.')
    elif s.alert:
        alert_html = (
            '\n    <div class="alert-box">\n'
            "      <h3>Major Buyer Threshold Alert</h3>\n"
            f'      <p>The Recommended Coming Soon Price of <b>{money(s.coming_soon)}</b> sits '
            f'<b>{money(s.alert["gap"])} above the {money(s.alert["major"])} major buyer '
            "threshold</b>.</p>\n"
            f'      <p>Pricing below <b>{abbrev(s.alert["major"])}</b> would expose the home to a '
            "materially larger pool of buyers whose searches stop at that threshold, while the "
            "authenticated value continues to support a sale in the Customary-to-Premium range.</p>\n"
            "    </div>\n")
    else:
        note("Roadmap: no Major Buyer Threshold alert — conditions not met.")

    notes_html = ""
    if p.get("notes"):
        paras = "".join(
            f'    <p class="notes-box" style="font-style:normal;">{n}</p>\n' for n in p["notes"])
        notes_html = ('\n    <h3 class="section-title" style="font-size:17px; '
                      'margin-top:34px;">Notes</h3>\n' + paras)

    # Casey, 10 Oct 2026: the two Predictive draw-downs can be set by hand, the
    # same way Preview and Coming Soon are. He walks the major threshold ladder
    # on some properties ($2.5M / $2.25M / $2.15M / $2.0M at Lillards Ford),
    # which the standard grid step cannot express.
    _fb_set = p["values"].get("fallback_override")
    _deep_set = p["values"].get("deep_override")
    _fb = int(_fb_set) if _fb_set else s.fallback
    _deep = int(_deep_set) if _deep_set else s.deep
    if not _deep_set and (_fb_set or _deep >= _fb):
        _deep = deep_after_fallback(_fb)
    _launch_set = p["values"].get("launch_override")
    _launch = int(_launch_set) if _launch_set else s.coming_soon
    if _launch_set and _launch != s.coming_soon:
        note(f"Roadmap: the 5-or-more-showings launch price is set by hand to "
             f"{money(_launch)}, apart from the Coming Soon price "
             f"{money(s.coming_soon)}.")
    if _fb_set:
        note(f"Roadmap: Fall Back price set by hand to {money(_fb)}; the "
             f"calculation gives {money(s.fallback)}.")
    if _deep_set:
        note(f"Roadmap: the deep Predictive position set by hand to "
             f"{money(_deep)}; the calculation gives {money(s.deep)}.")
    if _fb and _deep and _deep >= _fb:
        note(f"PRICING STRATEGY: the deep Predictive position {money(_deep)} is "
             f"not below the Fall Back {money(_fb)}. The ladder has to step "
             "down at every rung.")

    # A property can carry a floor below which no recommended price is shown.
    # It governs the recommendations only -- comps, assessments and competing
    # list prices are facts and stay as they are.
    _floor = p["values"].get("price_floor")
    if _floor:
        _floor = int(_floor)
        if _fb < _floor:
            note(f"Roadmap: the Fall Back computed to {money(_fb)}, below the "
                 f"{money(_floor)} floor set for this property, so it is held "
                 "at the floor.")
            _fb = _floor
        if _deep < _floor:
            note(f"Roadmap: the deep Predictive position computed to {money(_deep)}, "
                 f"below the {money(_floor)} floor, so it is held at the floor.")
            _deep = _floor
    # When the floor IS the launch price there is no price move left, and the
    # three columns must stop pretending otherwise.
    _no_room = bool(_floor) and _fb <= s.coming_soon
    if _no_room:
        note(f"Roadmap: the {money(_floor)} floor equals the launch price, so "
             "Predictive Analysis has no price move left. Columns two and three "
             "now point at condition and marketing rather than a reduction.")

    if _no_room:
        # Both branches below describe a reduction. There isn't one.
        pa_para = (f"The <b>{money(_floor)}</b> floor is the launch price, so there is "
                   "no reduction in this plan. Every lever that remains is on the "
                   "home rather than the number: presentation, photography, and how "
                   "far the marketing reaches. A home that is not drawing traffic at "
                   "its floor is better withdrawn and returned prepared than left to "
                   "sit.")
    elif _fb_set:
        # A hand-set Fall Back has no derivation to describe, so the paragraph
        # states the step that is actually on the page rather than the one the
        # grid would have produced.
        from pricing import MAJOR_THRESHOLDS as _MT
        _step = s.coming_soon - _fb
        _rungs = all(x in _MT for x in (s.coming_soon, _fb, _deep))
        pa_para = (f"A <b>{money(_step)}</b> step. "
                   + ("Each position on this ladder is a major buyer "
                      "threshold, so every reduction moves the home into a "
                      "materially larger pool rather than inching down a grid. "
                      if _rungs else "")
                   + "The reduction adjusts position, not value: the "
                     "authenticated Customary-to-Premium range is unchanged.")
    else:
        # Both tiers are measured off the Coming Soon price, and each is the
        # lower of a flat figure and a percentage. Say which one bound, so the
        # seller can see the arithmetic rather than take the number on faith.
        _s1, _s2 = s.coming_soon - _fb, s.coming_soon - _deep
        pa_para = (
            "Both reductions are measured from the Coming Soon price, not from "
            f"each other &mdash; <b>{money(_s1)}</b> to the Fall Back, "
            f"<b>{money(_s2)}</b> to the deep position. The step is $50,000 and "
            "$100,000, or 5% and 10% of the Coming Soon price where that is "
            "lower, brought down to sit beneath the nearest threshold. The "
            "reduction adjusts position, not value: the authenticated "
            "Customary-to-Premium range is unchanged.")
        if s.pair_passed:
            pa_para += (f" Note that <b>{abbrev(s.pair_passed)}</b> is a major buyer "
                        "threshold sitting just below the Fall Back. If the Fall "
                        "Back also fails to produce showings, moving beneath it "
                        "is the next lever.")
        elif s.alert and s.fallback > s.alert["major"]:
            pa_para += (f" Note that {money(s.fallback)} still sits above the "
                        f"{abbrev(s.alert['major'])} major threshold flagged above, so if the "
                        "Active price also fails to produce showings, moving beneath "
                        f"{abbrev(s.alert['major'])} is the next lever.")


    expected = f"Expected Sales Price: {abbrev(s.expected_low)}&ndash;{abbrev(s.expected_high)}"

    # ---- Predictive Analysis --------------------------------------------
    # Three readings, not one number: the traffic the home draws, how it
    # presents once buyers are inside, and what the market is doing under
    # both. Showings are the first test because they are the only one that
    # can be counted by Wednesday.
    _bad_market, _market_line = market_is_unfavorable(p)

    if _bad_market is True:
        _third_note = (f"{_market_line} Conditions are already working against the "
                       "home, so this column is live rather than hypothetical.")
    elif _bad_market is False:
        _third_note = (f"{_market_line} Conditions are not currently against the home, "
                       "so this column is a contingency rather than a forecast.")
    else:
        _third_note = ("Market conditions are read from the Market Snapshot at the time "
                       "&mdash; not assumed in advance.")

    if _no_room:
        _col2_pts = ("            <li>Not enough traffic to create competition.</li>\n"
                     f"            <li>The price holds at <b>{money(_fb)}</b> "
                     "&mdash; the floor for this home.</li>\n"
                     "            <li>The move is presentation and marketing, "
                     "not price.</li>\n")
        _col3_pts = ("            <li>Traffic has stalled and conditions are "
                     "unfavorable.</li>\n"
                     "            <li>With no price move left, the answer is "
                     "condition, photography and reach.</li>\n"
                     "            <li>Withdrawing and returning prepared beats "
                     "sitting.</li>\n")
    else:
        _col2_pts = ("            <li>Not enough traffic to create competition.</li>\n"
                     "            <li>Move to the next buyer pool.</li>\n")
        # The step is whatever the two figures on the page differ by — not the
        # standard $100,000, which a hand-set ladder need not follow.
        _col3_pts = ("            <li>Traffic has stalled and conditions are "
                     "unfavorable.</li>\n"
                     f"            <li>A further <b>{money(_fb - _deep)}</b> "
                     "adjustment may be due.</li>\n")

    # Casey, 27 Nov 2026: "$2.15 is a major threshold. Drop $50k if 2-5
    # showings, go under $2M if low or no showings. This is too much writing
    # so throw it out." The detail lives in the Guide.
    from pricing import MAJOR_THRESHOLDS as _MTH
    _major_line = (f"{abbrev(_launch + 1)} is a major threshold."
                   if (_launch + 1) in _MTH else "")
    _deep_major = max([t for t in _MTH if t <= _deep + 1], default=0)
    _deep_word = (f"Go under {abbrev(_deep_major)}" if _deep_major and _deep + 1 == _deep_major
                  else f"Drop to {abbrev(_deep)}")
    # Casey, 27 Nov 2026: "If customary has two paths conservative and
    # aggressive, Fall backs need to have 2 as well." The market's own path
    # uses the page's figures (overrides included); the other path follows
    # the same rule from its own Coming Soon: hold at 6+, drop $50K at 2-5,
    # go under the next major threshold with low or no showings.
    from pricing import preview_over_customary as _poc2, increment_for as _inc2, \
        grid_line_at_or_below as _glb2
    def _ladder(cs0):
        fb0 = cs0 - 50_000
        mj = max([t for t in _MTH if t <= fb0], default=0)
        return cs0, fb0, (mj - 1 if mj else fb0 - 50_000)
    _cv2 = int(p["values"]["customary"])
    _mine = (_launch, _fb, _deep)
    if strategy_figures(p, s)["posture"] == "conservative":
        _paths = [("Conservative", _mine, True),
                  ("Aggressive", _ladder(_poc2(_cv2) - 1), False)]
    else:
        _paths = [("Conservative", _ladder(_glb2(_cv2, _inc2(_cv2)) - 1), False),
                  ("Aggressive", _mine, True)]
    def _move_under(fb0, dp0):
        mj = dp0 + 1
        return f"Go under {abbrev(mj)}" if mj in _MTH else f"Drop to {abbrev(dp0)}"
    def _path(name, lad, on):
        l0, f0, d0 = lad
        rows = [(f"{SHOWINGS_FALLBACK_AT + 1} or more showings", "Hold position", l0),
                (f"2&ndash;{SHOWINGS_FALLBACK_AT} showings", f"Drop {abbrev(l0 - f0)}", f0),
                ("Low or no showings", _move_under(f0, d0), d0)]
        return (f'<div class="pp{" on" if on else ""}"><div class="pp-h">{name}</div>'
                + "".join(f'<div class="pp-r"><div class="pp-k">{k}</div><div class="pp-m">{m}</div>'
                          f'<div class="pp-v">{money(v)}</div></div>' for k, m, v in rows)
                + ('<div class="cs-pick">This market</div>' if on else "") + '</div>')
    _major_line = (f"{abbrev(_launch + 1)} is a major threshold."
                   if (_launch + 1) in _MTH else "")
    predictive_block = f"""<section class="pred-sec">
  <div class="wrap">
    <h2 class="test-head">The Launch</h2>
    <h2 class="section-title">Predictive Analysis</h2>
    <p class="section-sub">{_major_line} First-week showings set the next move.</p>
    <div class="pp-wrap">{"".join(_path(n, l, o) for n, l, o in _paths)}</div>
    <p class="section-sub" style="margin-top:14px;">{expected}</p>
  </div>
</section>
<style>.pp-wrap{{display:flex;gap:18px;justify-content:center;flex-wrap:wrap}}
.pp{{flex:1 1 300px;max-width:400px;background:#fff;border:1px solid #E4DCC8;border-radius:10px;padding:16px 18px;opacity:.55;text-align:center}}
.pp.on{{opacity:1;border:2px solid #B8902F}}
.pp-h{{font:700 12px Georgia,serif;letter-spacing:.18em;text-transform:uppercase;color:#71695A;margin-bottom:6px}}
.pp-r{{padding:10px 0;border-top:1px solid #EFE8D8}}
.pp-k{{font:700 11px Georgia,serif;letter-spacing:.12em;text-transform:uppercase;color:#8A6A2E}}
.pp-m{{font:700 15px Georgia,serif;color:#1F2A44;margin:3px 0}}
.pp-v{{font:700 26px 'Playfair Display',Georgia,serif;color:#8A6A2E}}</style>"""

    # ---- Recovery ---------------------------------------------------------
    # A home that has been sitting. The 14 days off market are the test, and
    # the response to it picks the move. Everything else on the Roadmap is
    # unchanged -- this replaces the Predictive Analysis section only.
    recovery_block = ""
    reconcile_block = ""
    _cl = p.get("current_list")
    if p.get("listing_status") == "recovery":
        if not _cl:
            note('Roadmap: recovery portal has no "current_list" on file, so the '
                 "Recovery Strategy and the value reconciliation are both omitted. "
                 "Add the price the home is sitting at and rebuild.")
        else:
            _v = p["values"]
            _r = recovery_prices(p)
            # An upgrades worksheet stores no premium -- it is a range derived
            # from the upgrade spend. Ask the strategy rather than printing a
            # dash where the whole argument depends on the figure.
            _prem = _v.get("premium") or 0
            _prem_show = money(_prem) if _prem else (
                s.premium_display if s.has_upgrades else "&mdash;")
            _prem_top = _prem or (s.premium_top if s.has_upgrades else 0)
            # The seller should be able to see exactly what a buyer sees while
            # the home is off the market and the condition work is under way.
            # Opt-in, same rule as buyer_portal_url(): no link until the
            # buyer portal is actually built and published.
            _bpb = p.get("buyer_portal") or {}
            _bp = _bpb.get("url") if _bpb.get("live") is True else None
            _bp_link = ""
            if _bp:
                _bp_link = (
                    "<!--SEC:cta-start-->\n"
                    '<section class="bp-band">\n  <div class="wrap">\n'
                    '    <a class="bp-cta" href="' + _bp + '" target="_blank" '
                    'rel="noopener">\n'
                    '      <span class="bp-cta-lbl">What Buyers And Their Agents See</span>\n'
                    '      <span class="bp-cta-sub">The same competition, the same '
                    "market, read from the buyer&rsquo;s side of the table.</span>\n"
                    '      <span class="bp-cta-go">Open the Buyer Portal &rarr;</span>\n'
                    '      <span class="bp-cta-url">' + _bp.replace("https://", "")
                    + '</span>\n'
                    "    </a>\n  </div>\n</section>\n"
                    "<!--SEC:cta-end-->\n")
            else:
                note("Roadmap: Buyer Portal band OMITTED from the recovery "
                     "Roadmap — "
                     + ("no url on the buyer_portal block."
                        if not _bpb.get("url") else
                        'the portal is not published yet. Set "live": true '
                        "on the day the page goes up."))

            # Over $2M the move is a threshold move, not a measured cut, and
            # the two columns have to say which rule they are following or the
            # arithmetic will not reconcile for the seller.
            _over_2m = _cl >= 2_000_000
            if _over_2m:
                _soft_rule = ("Buyers shop in bands, so the step is down to the "
                              "next major threshold, not a round number off the list.")
                _hard_why = ("The threshold below that is where the next pool of "
                             "buyers is sitting.")
            else:
                # Casey, 21 Oct 2026: the midpoint rule. The sentence says
                # how far over the launch line the home is, in his terms.
                from pricing import _recovery_rule as _rr21
                _r21 = _rr21(_cl, _v["customary"], _v.get("customary_list"))
                if _r21.get("launch_line") and not _r21.get("warning"):
                    _soft_rule = (f"The home is listed {money(_cl - _r21['launch_line'])} "
                                  f"over the {abbrev(_r21['launch_line'])} it would "
                                  "launch at today, so the first step goes half of "
                                  "that distance rather than a rung off the list.")
                else:
                    _soft_rule = ("A measured reduction &mdash; the lesser of $50,000 "
                                  "and 5% &mdash; is enough to restart it.")
                _hard_why = "That puts the price back in line with the buyer pool."
            # A hand-set price did not come from either rule, so the sentence
            # that names the rule comes out rather than contradicting the
            # figure printed under it.
            _ro = p.get("recovery") or {}
            if _ro.get("soft_override"):
                _soft_rule = ("The step is set against what this pool has "
                              "actually paid, not off a formula.")
            # Casey's own read of the pool at the lower rung, carried verbatim.
            _rn = (p.get("recovery") or {}).get("hard_note")
            if _rn:
                _hard_why = _rn

            # The engine's threshold ladder reads off the premium anchor, which
            # is the valuation, not the pool. On a home that has been sitting,
            # the pool is whatever the competing actives and the actual sales
            # say it is -- and that can sit a whole threshold below.
            _rec = p.get("recovery") or {}
            _pool = _rec.get("buyer_pool") or s.closest_buyer_threshold
            _pool_show = _rec.get("buyer_pool_label") or money(_pool)
            if _rec.get("buyer_pool"):
                note(f"Roadmap: Buyer Threshold set to {money(_pool)} from the "
                     "recovery block, overriding the engine's "
                     f"{money(s.closest_buyer_threshold)} off the premium anchor.")

            _upg = _v.get("upgrades") or 0
            _ev_txt, _worth = recovery_evidence(p, _pool, _upg, _prem_top, _cl)
            _diag = (f'<b>The buyer pool for homes of this age and size is shopping '
                     f'under {abbrev(_pool)}.</b> {_ev_txt}'
                     f'{_worth}. <b>That is not where the buyer pool is.</b> Being '
                     "worth more than the pool will pay is not the same as selling, "
                     "and days on market do not close that distance.")
            _key = _rec.get("key") or (
                "The key is to find the buyer pool and create bidding &mdash; not to "
                "inch toward it. A home priced into the pool, below the homes that "
                "have been sitting in it, is the one that draws more than one buyer "
                "at a time. That is what produces a sale above the list price, and "
                "it is the only mechanism that " + ("recovers the premium the "
                "upgrades earned." if _upg else "recovers the value the home "
                "actually has."))

            GUIDE_NOTES["recovery"] = {"pool": _pool, "list": _cl,
                                       "fb": _r["soft"], "rc": _r["hard"]}
            _cols = ["Customary Value", "Buyer Threshold", "Premium Value",
                     "Current List Price"]
            _vals = [money(_v["customary"]),
                     _pool_show,
                     _prem_show,
                     money(_cl)]
            reconcile_block = f"""<section>
  <div class="wrap">
    <h2 class="section-title">Reconciling Value and Price</h2>
    <p class="section-sub">Here is the problem.</p>
    <div class="table-wrap price-table">
      <table>
        <thead><tr>{"".join(f"<th>{c}</th>" for c in _cols)}</tr></thead>
        <tbody><tr>{"".join(f"<td>{v}</td>" for v in _vals)}</tr></tbody>
      </table>
    </div>
    <p class="price-para">{_diag}</p>
    <p class="price-para"><b>{_key}</b></p>
  </div>
</section>"""

            # Casey, 22 Nov 2026: "recovery strategy need to be put in recovery
            # roadmaps just like regular seller road maps" -- the approved
            # 4-step strategy from the recovery seller email, laid out the way
            # The Test and The Launch are on a standard Roadmap. Fall Back and
            # Rip Cord are the same two prices the email quotes.
            recovery_block = f"""<section class="pred-sec">
  <div class="wrap">
    <h2 class="test-head">The Test</h2>
    <h2 class="section-title">Our 4-Step Recovery Strategy</h2>
    <p class="section-sub">Test buyer interest, reposition the home at the right
    price, and use our marketing tools to generate the strongest possible offer.</p>

    <div class="needle-table">
      <div class="needle-cols three">
        <div class="needle-col">
          <h4>1. Inspect Property and Review Comments</h4>
          <ul>
            <li>Does the property need any updates that can make it more appealing to buyers?</li>
            <li>See Moving the Needle above.</li>
          </ul>
        </div>
        <div class="needle-col">
          <h4>2. Temporarily Off Market</h4>
          <ul>
            <li>Take the home TEMP Off Market.</li>
            <li>Buyers and agents watching the listing may call to find out why.</li>
          </ul>
        </div>
        <div class="needle-col">
          <h4>3. Test Buyer Interest</h4>
          <ul>
            <li>If they call, we explain that the home will return at a lower price.</li>
            <li>This may encourage buyers to make an offer before the reduction.</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="pred-sec">
  <div class="wrap">
    <h2 class="section-title">4. Adjust Price</h2>
    <p class="section-sub"><b>Note:</b> Adjusting price does not mean a lower sales
    price, it means a larger buyer pool. Lower prices usually produce higher prices.</p>

    <div class="needle-table">
      <div class="needle-cols">
        <div class="needle-col">
          <h4>If some buyers call &mdash; Fall Back Price</h4>
          <ul>
            <li>If we receive interest but no acceptable offer, we return to the market at
            {money(_r["soft"])} to get exposure to a larger buyer pool.</li>
          </ul>
          <div class="price-card">
            <div class="rec-label">Fall Back Price</div>
            <div class="rec-price">{money(_r["soft"])}</div>
            <div class="rec-expected">{expected}</div>
          </div>
        </div>
        <div class="needle-col">
          <h4>If no one calls &mdash; Pull the Rip Cord</h4>
          <ul>
            <li>This suggests our price is not close to the buyer pool. We go to
            {money(_r["hard"])} to guarantee the largest buyer pool. Whatever buyers bid
            is what the home is worth at this time.</li>
          </ul>
          <div class="price-card">
            <div class="rec-label">Rip Cord Price</div>
            <div class="rec-price">{money(_r["hard"])}</div>
            <div class="rec-expected">{expected}</div>
          </div>
        </div>
      </div>
    </div>

{_bp_link}  </div>
</section>"""

    pools = " &middot; ".join(abbrev(t) for t in buyer_pools(s.anchor))
    relaunch_block = f"""<section>
  <div class="wrap">
    <h2 class="section-title">Relaunch Strategy</h2>
    <p class="section-sub">The home has already been on the market, so the first move
    is a test rather than a price. Put the property into <b>Temporarily Off Market</b>
    status and use the response as the test.</p>

    <div class="needle-table">
      <div class="needle-cols">
        <div class="needle-col">
          <h4>If 2&ndash;4 buyers or agents call</h4>
          <ul>
            <li>Asking why the property was taken off the market.</li>
            <li>Buyers are watching at this level.</li>
            <li><b>Relaunch at {money(s.coming_soon)}.</b></li>
          </ul>
        </div>
        <div class="needle-col">
          <h4>If no one calls</h4>
          <ul>
            <li>Buyers are not watching at the current level.</li>
            <li>A meaningful reset is needed.</li>
            <li><b>Relaunch at {money(s.fallback)}</b> &mdash; a substantially larger buyer pool.</li>
          </ul>
        </div>
      </div>
    </div>

    <p class="price-para" style="margin-top:20px;">At this price level the major buyer
    pools are <b>{pools}</b>. Position the home where it creates the greatest combination
    of traffic, confidence and competition.</p>
  </div>
</section>"""

    # Casey, 23 Nov 2026: "Add a section in roadmap for buyer Portal that
    # direct links to the Buyer Portal." Recovery Roadmaps already carry the
    # band inside the Recovery Strategy.
    _rm_bp_section = ""
    if p.get("listing_status") != "recovery":
        _rbp = buyer_portal_url(p)
        # Casey, 23 Nov 2026: the card hand-off was "awkward" -- just the
        # words "What the Buyers See / Buyer Portal"; the picture under them
        # (added by property_guides) links to the Sample until this home's
        # own portal is finished.
        _rm_bp_section = (
            '<section class="bp-band">\n  <div class="wrap" style="text-align:center;">\n'
            '    <div class="bp-words" style="display:inline-block;">\n'
            '      <span style="display:block;font:700 13px Georgia,serif;letter-spacing:.22em;'
            'text-transform:uppercase;color:#8A6A2E;">What the Buyers See</span>\n'
            "      <span style=\"display:block;font-family:'Playfair Display',Georgia,serif;font-size:40px;"
            'font-weight:700;color:#1F2A44;line-height:1.15;border-bottom:2px solid #B8902F;'
            'padding-bottom:4px;margin-top:4px;">Buyer Portal</span>\n'
            "    </div>\n  </div>\n</section>\n")
    if p.get("listing_status") == "recovery" and recovery_block:
        next_step_section = reconcile_block + "\n\n" + recovery_block
        note("Roadmap: Recovery Strategy used in place of Predictive Analysis "
             "(listing_status = recovery).")
    elif p.get("listing_status") == "relaunch":
        next_step_section = relaunch_block
        note("Roadmap: Relaunch Strategy used in place of Predictive Analysis "
             "(listing_status = relaunch).")
    else:
        next_step_section = predictive_block
        # Casey, 27 Nov 2026: Marketing and Contract Negotiating follow The Launch.
        import roadmap_sections as _rs
        next_step_section += "\n" + _rs.html(p)
    # With Extraordinary Upgrades, Authenticated Values starts on a new page
    # and Current Competition on the page after it.
    # The price header moved off the Seller Portal nav page and onto the
    # Roadmap, where the pricing argument actually lives. Same two numbers,
    # same labels.
    _b = []
    _is_recovery = p.get("listing_status") == "recovery" and p.get("current_list")
    if _is_recovery:
        # The home is on the market now, so the hero leads with what it is
        # listed at. A "Recommended Coming Soon" price on a listing that has
        # sat for weeks reads as though nothing has happened yet.
        _b.append(("Currently Listed", money(p["current_list"])))
    elif s.coming_soon:
        _b.append(("Recommended Coming Soon", money(s.coming_soon)))
    if s.expected_low and s.expected_high:
        _b.append(("Expected Sale Price",
                   f"{abbrev(s.expected_low)}&ndash;{abbrev(s.expected_high)}"))
    _hero = p.get("hero_photo")
    _src = Path(p.get("asset_dir", "."))
    if not _src.is_absolute():
        _src = HERE / _src
    if _hero and not (_src / _hero).exists():
        _hero = None
    rm_hero_img = f'  <img src="{_hero}" alt="{addr}">' if _hero else ""
    if not _hero:
        note("Roadmap hero photo OMITTED — none on file; the brand gradient is used.")

    if _is_recovery:
        rm_note = ('      <p class="rm-note">RECOVERY IS A THREE-STEP PROCESS: '
                   "INSPECT CONDITION &middot; TEST THE BUYER POOL &middot; "
                   "ANALYZE MARKET.</p>")
    else:
        rm_note = ('      <p class="rm-note">NOTE: THIS IS PRELIMINARY PRICING ONLY. '
                   "FINAL PRICING CAN ONLY BE DETERMINED AFTER A VISUAL INSPECTION OF "
                   "CONDITIONS, UPGRADES AND LOT PREMIUM OR DISCOUNT.</p>")

    # Casey, 23 Nov 2026: replaces "Engineered for a First-Week Sale --
    # Highest Price, Best Terms, Lowest Risk", larger.
    # Casey, 24 Nov 2026: "recovery roadmap header and opening should look
    # just like regular only Recovery Roadmap" -- same tagline, same band.
    rm_tag = ('    <p class="tag" style="font-family:\'Playfair Display\',Georgia,serif;font-size:28px;'
              'font-style:italic;font-weight:700;color:#FFFDF7;margin:12px 0 14px;'
              'text-shadow:0 2px 10px rgba(0,0,0,.6);">Success is a Strategy, not a Price</p>')

    rm_badges = ""
    if _b:
        rm_badges = ('      <div class="rm-badges">'
                     + "".join(f'<div class="rm-badge"><div class="k">{k}</div>'
                               f'<div class="v">{v}</div></div>' for k, v in _b)
                     + "</div>")

    # The forced breaks are tuned for the standard section order. Since
    # 19 Oct the recovery Roadmap leads with the same valuation group in the
    # same order, so they no longer land in the wrong place -- but they still
    # cost a page, and they bought nothing: 512 Seneca Green went to nine
    # pages with a 47-word page two. A recovery Roadmap already runs long, so
    # it keeps letting the valuation group flow.
    upgrade_break = (' style="page-break-before:always;"'
                     if s.has_upgrades and p.get("listing_status") != "recovery"
                     else "")
    if s.has_upgrades:
        # No Dated tier on an upgrades worksheet, so Money at Risk becomes the
        # upgrade return at stake: the top of the range less Customary.
        mar_label = "Upgrade Return at Risk"
        mar_value = money(s.premium_top - p["values"]["customary"])
    elif not p["values"].get("dated"):
        mar_label = "Value at Risk"
        mar_value = money(p["values"]["premium"] - p["values"]["customary"])
    else:
        mar_label, mar_value = "Money at Risk", money(s.money_at_risk)

    # The navy band and the facts card that used to sit on the Seller Portal
    # nav page. Same figures, same labels — the whole header moved here.
    _st, _ab = {}, {}
    _cache = HERE / "market_cache.json"
    if _cache.exists() and p["market"].get("slug"):
        _c = json.loads(_cache.read_text()).get(p["market"]["slug"], {}) or {}
        _st, _ab = _c.get("stats") or {}, _c.get("absorption") or {}
    _v = p.get("values") or {}
    _cols = []
    _top = _v.get("premium") or (s.premium_top if s.has_upgrades else 0)
    if _v.get("customary") and _top:
        _cols.append(("Authenticated Range",
                      f'{money(_v["customary"])} &ndash; {money(_top)}',
                      "Customary to Premium Value&trade;"))
    # The upgrade spend is what earns the premium, so it stands as a headline
    # figure of its own rather than sitting inside a paragraph further down.
    if s.has_upgrades and _v.get("upgrades"):
        _cols.append(("Extraordinary Upgrades", money(_v["upgrades"]),
                      "What this home has already had invested"))
    _cols.append((mar_label, mar_value,
                  f'The return at stake on {money(_v["upgrades"])}'
                  if s.has_upgrades and _v.get("upgrades") else
                  ("Customary to Premium" if not _v.get("dated")
                   else "What mispricing can cost")))
    if _st.get("control"):
        _cols.append((p["market"]["name"].replace(" Market", ""),
                      f'{_st["control"]} Market',
                      _ab.get("note") or f'{_st.get("under_contract", "")} under contract'))
    rm_band = ('<div class="rm-band"><div class="wrap"><div class="rm-cols">'
               + "".join(f'<div class="rm-col"><div class="k">{k}</div>'
                         f'<div class="v">{v}</div><div class="s">{sub}</div></div>'
                         for k, v, sub in _cols)
               + "</div></div></div>")

    _as = [f'Built {subj["built"]}', f'{sf(subj["sf"])} SF']
    if subj.get("assessment"):
        _as.append(f'Assessment {money(subj["assessment"])}')
    else:
        note("Roadmap: Authenticated Prices stat line has no assessment on "
             "file, so it shows Customary straight after the size.")
    if p["values"].get("customary"):
        _as.append(f'Customary {money(p["values"]["customary"])}')
    auth_stats = " &middot; ".join(_as)

    _subj = p.get("subject") or {}
    _facts = []
    if _subj.get("built"):
        _facts.append((_subj["built"], "Year built"))
    if _subj.get("sf"):
        _facts.append((f'{_subj["sf"]:,}', "Above grade SF"))
    if _subj.get("lot"):
        _facts.append((f'{_subj["lot"]:,}', "Lot SF"))
    if _subj.get("assessment"):
        _facts.append((money(_subj["assessment"]), "Assessment"))
    if False:
        pass
    else:
        # Casey, 16 Nov 2026: "on that list it should be customary value
        # Premium Value" -- new listings end the strip with the two values;
        # recoveries keep "If no one calls".
        _vv0 = p["values"]
        if _vv0.get("significant_upgrades") and _vv0.get("upgrade_labels"):
            _facts.append((money(_vv0.get("customary_unadjusted") or _vv0["customary"]), "Customary Value"))
            _facts.append((money(_vv0["premium"]), _vv0["upgrade_labels"][1]))
        else:
            _facts.append((money(_vv0["customary"]), "Customary Value"))
            _facts.append((money(_vv0.get("premium_top") or _vv0["premium"]), "Premium Value"))
    rm_facts = ""
    # Casey, 25 Nov 2026: "Copy maps (dimensions, plats etc) and put them on
    # Roadmap under Moving the Needle" -- the Buyer Portal's Lot section
    # (satellite, street names, house location plat, lot dimensions).
    import zillow_compare as _zc
    _zc_seller = _zc.seller_section(p)
    rm_lot = ""
    _bpl = (p.get("buyer_portal") or {})
    # A Roadmap with no Buyer Portal of its own (the Sample) can carry the lot
    # as roadmap_lot -- Casey, 26 Nov 2026: "it's not in sample".
    if not (_bpl.get("lot") or {}).get("polygon") and (p.get("roadmap_lot") or {}).get("polygon"):
        _bpl = {"lot": p["roadmap_lot"], "display_address": p.get("roadmap_lot_address") or p["address"],
                "asset_dir": p.get("asset_dir")}
    if (_bpl.get("lot") or {}).get("polygon"):
        try:
            import build_buyer_portal as _bbp
            rm_lot = _bbp.lot_map(_bpl, _bpl.get("display_address") or p["address"])
            # Roadmap headings: same title style as Moving the Needle.
            # Casey, 27 Nov 2026: "The Lot Filter".
            rm_lot = (rm_lot.replace('<h2 class="st">The Lot</h2>', '<h2 class="st">Lot Filter</h2>', 1)
                      .replace('<h2 class="st">', '<h2 class="section-title">', 1)
                      .replace('<p class="ss">', '<p class="needle-lede">', 1))
            _tpl = HERE / "templates"
            for _lf in ("leaflet.js", "leaflet.css"):
                if (_tpl / _lf).exists() and not (out / _lf).exists():
                    shutil.copy(_tpl / _lf, out / _lf)
            for _pf in [x for x in (_bpl["lot"].get("plat"), _bpl["lot"].get("plat_view")) if x]:
                for _d in (_bpl.get("asset_dir"), p.get("asset_dir")):
                    if _d and (HERE / _d / _pf).exists():
                        shutil.copy(HERE / _d / _pf, out / _pf)
                        break
        except Exception as _e:
            note(f"Roadmap: lot maps skipped -- {_e}")
    rm_subject = ""
    if True:
        # Casey, 24 Nov 2026: the navy band carries the three steps from the
        # Seller Portal; the home's specs move to a "Subject" strip over the
        # Appraisal-Quality Comparable Analysis.
        # Casey, 24 Nov 2026: no First/Then/Result labels; "Build
        # Confidence" on two lines; the third box is "Inspire Highest and Best
        # Offers" with the Buyer Portal.
        _steps = (("Build<br>Confidence", "In the value and the condition of the home"),
                  ("Create<br>Competition", "Maximum exposure to the largest qualified buyer pool"),
                  ("Inspire Highest<br>and Best Offers", "With the Buyer Portal"))
        rm_facts = ('<div class="rm-band rm-steps"><div class="wrap"><div class="rm-cols">'
                    + "".join(f'<div class="rm-col"><div class="v">{b}</div>'
                              f'<div class="s">{c}</div></div>' for b, c in _steps)
                    + "</div></div></div>")
        _subj4 = _facts[:4]
        # Casey, 27 Nov 2026: "Add 5th index bring up Money at Risk" -- the
        # Subject card ends with it; the box under Net Proceeds is gone.
        if _subj4:
            _subj4 = _subj4 + [(mar_value, mar_label)]
        import schools as _sch
        # Casey, 25 Nov 2026: "when we do a home, bring in schools in the
        # seller roadmap and buyer portal."
        if not _sch.schools_of(p):
            note("Schools: none on file -- add buyer_portal.schools "
                 "[elementary, middle, high] so they show on the Roadmap and Buyer Portal.")
        if _subj4:
            rm_subject = ('<section class="rm-subj"><div class="wrap"><div class="rm-subj-card">'
                          '<div class="rm-subj-t">Subject</div><div class="rm-subj-row">'
                          + "".join(f'<div class="rm-subj-f"><span class="n">{n}</span>'
                                    f'<span class="l">{l}</span></div>' for n, l in _subj4)
                          + "</div>" + _sch.row_html(p) + "</div></div></section>\n")
        _facts = []
    if _facts:
        # Casey, 23 Nov 2026: "Give it the same look" as the Seller Portal --
        # the specs across a full-width navy band, the white CST-vs-market
        # card overlapping its lower edge.
        rm_facts = ('<div class="rm-band rm-specs"><div class="wrap"><div class="rm-cols">'
                    + "".join(f'<div class="rm-col"><div class="k">{l}</div>'
                              f'<div class="v">{n}</div></div>' for n, l in _facts)
                    + "</div></div></div>")

    # Casey, 13 Oct 2026: "Bring price up top like you have, then Since
    # 2019, home values have appreciated 61%..." -- his copy verbatim, with
    # the figures rounded to the nearest $1,000 so the premium equals the
    # difference of the two numbers printed above it.
    # Casey, 16 Oct 2026, the standing Roadmap order: "Appraisal comps come
    # first, Authenticated Values come next, no Reality Check in the
    # Roadmap." So this block is no longer placed on the page -- it is kept
    # because the Pricing Strategy Summary still carries a Reality Check and
    # both read the same pricing.reality_check figures.
    rm_reality = ""
    if _v.get("customary") and not p.get("new_construction"):
        from pricing import reality_check as _rc
        _r = _rc(_v["customary"])

        def pct(x):
            t = f"{x * 100:.2f}".rstrip("0").rstrip(".")
            return f"{t}%"

        rm_reality = (
            '<div class="wrap"><div class="rc-sec">'
            '<h3 class="rc-head">Reality Check</h3>'
            '<div class="rc-card">'
            '<div class="rc-k">Value based on inflation</div>'
            f'<div class="rc-v">{money(_r["inflation"])}</div>'
            '<div class="rc-s">Since 2019, home values have appreciated '
            f'{pct(_r["appreciation"])}, bringing today&rsquo;s average sales '
            f'price to {money(_r["today"])}. Had home values increased at the '
            f'rate of inflation ({pct(_r["inflation_rate"])}), that same home '
            f'would be worth just {money(_r["inflation"])} today.</div>'
            f'<div class="rc-g">That&rsquo;s a {money(_r["premium"])} premium '
            "above inflation-driven appreciation.</div></div>"
            '<p class="rc-note">Today&rsquo;s average buyer makes just '
            f'<b>{pct(_r["affordability_now"])}</b> of the income needed to '
            "buy the average house. In 2019, that number was "
            f'<b>{pct(_r["affordability_2019"])}</b>.</p>'
            "</div></div>")


    # Flag when the subject carries a heavier assessment than the comparable
    # homes it competes with — online, that works against the seller.
    comp_assessments = [r[4] for r in p["comps"]["rows"] if r[4]]
    assessment_alert = ""
    if comp_assessments and p["subject"].get("assessment"):
        avg = sum(comp_assessments) / len(comp_assessments)
        pct = round((p["subject"]["assessment"] / avg - 1) * 100)
        if pct >= 5:
            assessment_alert = (
                '    <div class="alert-box" style="margin-top:22px;">\n'
                f'      <h3>Alert: Assessment is {pct}% higher than average homes '
                'of equal size and age</h3>\n'
                f'      <p>This home is assessed at {money(p["subject"]["assessment"])} '
                f'against an average of {money(round(avg))} across the comparable sales '
                'above. Buyers searching online see the assessment before they see the '
                'home, so the entry price has to overcome that first impression.</p>\n'
                '    </div>\n')
            note(f"Roadmap: assessment alert shown — {pct}% above the comparable average.")
        else:
            note("Roadmap: no assessment alert — subject is not materially above "
                 "the comparable average.")

    if s.has_upgrades:
        strategy_para = (
            f'The <b>Customary Value of {money(p["values"]["customary"])}</b> is the '
            "bedrock of the pricing &mdash; the value the home holds before any "
            f'upgrade return. With {money(p["values"]["upgrades"])} in extraordinary '
            "upgrades, positioning runs off the bottom of the Premium Range at "
            f'<b>{money(s.premium_bottom)}</b>, so the strategy begins at the closest '
            f"major buyer threshold below it &mdash; the <b>{abbrev(s.anchor)} mark</b>.")
    else:
        strategy_para = (
            f"The {s.anchor_basis_label} of <b>{money(s.anchor_basis)}</b> is the basis "
            "for positioning, so the strategy begins at the first buyer threshold below "
            f"it &mdash; the <b>{abbrev(s.closest_buyer_threshold)} mark</b>.")
        if _sf.get("safe_haven"):
            # The paragraph named the grid line the price no longer uses.
            strategy_para = (
                f"The {s.anchor_basis_label} of <b>{money(s.anchor_basis)}</b> "
                "is the basis for positioning. In this market the strategy "
                "takes the closest safe haven beneath it &mdash; the "
                f"<b>{abbrev(_sf['safe_haven'] + 1)} mark</b>, the line "
                "buyers search to.")
    if s.has_upgrades:
        # Customary is the bedrock and stays on the table even though
        # positioning runs off the bottom of the Premium Range.
        threshold_cols = ["Customary Value", "Bottom of Premium Range",
                          "Closest Buyer Threshold"]
        threshold_vals = [money(p["values"]["customary"]), money(s.premium_bottom),
                          money(s.closest_buyer_threshold)]
    else:
        threshold_cols = ["Authenticated Value", "Closest Buyer Threshold"]
        threshold_vals = [money(p["values"]["customary"]),
                          money(s.closest_buyer_threshold)]

    # Casey, 15 Oct 2026: "CLOSEST BUYER THRESHOLD $2.2 should be CLOSEST
    # SAFE HAVEN $2.1499 because buyer market." Where the price took the
    # haven, the table has to name the line the price actually works to --
    # printing the $2.2M grid line next to a $2,149,999 Coming Soon price
    # is the document arguing with itself.
    if _sf.get("safe_haven"):
        threshold_cols[-1] = "Closest Safe Haven"
        threshold_vals[-1] = money(_sf["safe_haven"])

    # ---- The market the strategy is built on ---------------------------
    # Casey, 10 Oct 2026: name who holds control, then the three contract
    # percentages behind that call. These are the figures that decide whether
    # Preview and Coming Soon price under or over the authenticated values,
    # so they belong at the top of the Pricing Strategy section.
    # Standard on every Roadmap, including recovery and relaunch. It renders
    # on whatever the MSS has: the control line needs a control reading, each
    # tile needs its own figure, and the band only disappears when the market
    # has none of the four — which is a gap in the data, not a style choice,
    # so it is logged with the specific remedy.
    _mk = market_posture(p)

    # Casey, 15 Oct 2026: "CST PRICING STRATEGY SHOULD REFLECT MARKET!
    # STRONG BUYERS MARKET REQUIRES CONSERVATIVE CHOICES, POSITIVE MARKET
    # MOMENTUM ALLOWS SELLERS TO BE MORE AGGRESSIVE."
    #
    # The section had the market read taken out of it because Current
    # Competition carries the dashboard now, which left the strategy
    # looking like it came from nowhere. This is the sentence that joins
    # the two: the same control reading that sets the posture, said in
    # terms of what it costs the seller.
    #
    # "Strong" is not a separate band -- it is the bottom of the buyer's
    # band, under 20% under contract, which is the double red flag.
    _uc = _gauge_value(_mk.get("under_contract"))
    _post = _mk.get("posture")
    _mname = _mk.get("name") or "this market"
    if _post == "aggressive":
        _ps_read = (f"Sellers hold the advantage in the {_mname}. Positive "
                    "market momentum allows a more <b>aggressive</b> "
                    "position, so the strategy prices at the first "
                    "threshold <b>above</b> the authenticated values.")
    elif _post == "conservative" and "buyer" in (_mk.get("control") or "").lower():
        _strong = "a strong buyer&rsquo;s market" if (_uc is not None and _uc < 20) \
            else "a buyer&rsquo;s market"
        _ps_read = (f"Buyers control the {_mname}, and {_strong} requires "
                    "<b>conservative</b> choices, so the strategy prices at "
                    "the first threshold <b>under</b> the authenticated "
                    "values rather than testing above them.")
    elif _post == "conservative":
        _ps_read = (f"Neither side controls the {_mname}, so the strategy "
                    "stays <b>conservative</b> and prices at the first "
                    "threshold <b>under</b> the authenticated values.")
    else:
        _ps_read = ""
        note("Roadmap: the Pricing Strategy has no market posture line \u2014 "
             "no control reading on file for this market.")
    posture_line = (f'    <p class="ps-posture">{_ps_read}</p>\n'
                    if _ps_read else "")

    _tiles = [(_mk["under_contract"], "Of listings under contract"),
              (_mk["uc_30"], "Of homes listed in the last 30 days went "
                             "under contract"),
              (_mk["uc_14"], "Went under contract in the last 14 days"),
              (_mk["avg_dom"], "Average days on market")]
    _have = [(val, lbl) for val, lbl in _tiles if val]
    market_band = ""
    if _mk["control"] or _have:
        _line = ""
        if _mk["control"]:
            _who = ("Buyers are in control" if "buyer" in _mk["control"].lower()
                    else "Sellers are in control" if "seller" in _mk["control"].lower()
                    else "Neither side is in control")
            _of = f' of the {_mk["name"]}' if _mk.get("name") else ""
            _line = f'      <p class="mkt-control">{_who}{_of}.</p>\n'
        _cells = "".join(
            f'      <div class="mkt-stat"><div class="mkt-num">{val}</div>'
            f'<div class="mkt-lbl">{lbl}</div></div>\n' for val, lbl in _have)
        _row = (f'      <div class="mkt-row n{len(_have)}">\n{_cells}      </div>\n'
                if _have else "")
        market_band = f'    <div class="mkt-band">\n{_line}{_row}    </div>\n'
        # Only chase missing MSS figures when there is an MSS to chase. A
        # property with no snapshot (Madison, Culpeper) is not missing them.
        if (p.get("market") or {}).get("slug"):
            _gaps = [lbl.lower() for val, lbl in _tiles
                     if not val and lbl != "Average days on market"]
            if not _mk["control"]:
                _gaps.insert(0, "the market control reading")
            if _gaps:
                note("Roadmap: the market band is missing " + "; ".join(_gaps)
                     + " — not in the cached MSS for this market.")
    elif not (p.get("market") or {}).get("slug"):
        note("Roadmap: market band OMITTED — this property has no market slug, "
             "so there is nothing to read the conditions from. Add a "
             '"market" block with a slug to the property file.')
    else:
        note("Roadmap: market band OMITTED — "
             f'{(p.get("market") or {}).get("slug")} is not in '
             "market_cache.json. Refresh the MSS to price off the live market.")

    # ---- Preview -------------------------------------------------------
    # The home goes public before it is live, at the grid line under Premium
    # Value. Recovery and relaunch homes are already on the market, so the
    # section has nothing to say for them.
    preview_section = ""
    # One source for every price on the page: the market's control reading
    # picks the formula, a hand-set override beats it, and the summary page
    # and the seller email read the same dictionary.
    _f = strategy_figures(p, s)
    _cons = _f["posture"] == "conservative"
    if p.get("listing_status") not in ("recovery", "relaunch"):
        from pricing import preview_over_customary as _preview_oc
        # Casey, 13 Oct 2026: Preview is the threshold OVER Customary Value.
        # The Premium-anchored pair is retired, so the caption and the
        # paragraph name Customary — they used to name Premium, which the
        # figure no longer comes from.
        _cust_for_preview = p["values"].get("customary")
        _prem_for_preview = (p["values"].get("premium")
                             or (s.premium_top if s.has_upgrades else 0))
        _pv_override = p["values"].get("preview_override")
        if _pv_override or _cust_for_preview:
            _pv = _f["preview"]
            _calc = _preview_oc(int(_cust_for_preview)) if _cust_for_preview else 0
            _pv_basis = ("Set for this property" if _pv_override else
                         "Threshold %s the Customary Value of %s"
                         % ("under" if _cons else "over",
                            abbrev(int(_cust_for_preview))))
            if _pv_override:
                note(f"Roadmap: Preview price set by hand to {money(_pv)}; the "
                     f"rule gives {money(_calc)}."
                     if _cust_for_preview else
                     f"Roadmap: Preview price set by hand to {money(_pv)}.")
            _pv_para = ("The estimated value shown on Preview is the threshold "
                        "just under Customary Value &mdash; the same price the "
                        "home goes live at. Buyers control this market, so "
                        "there is no premium to ask for first; the figure "
                        "buyers carry with them is the one that works."
                        if _cons else
                        "The estimated value shown on Preview is the threshold "
                        "just over Customary Value &mdash; high enough to set "
                        "expectations, and the figure buyers carry with them "
                        "when the home goes active.")
            # A hand-set Preview can land somewhere the stock sentence does not
            # describe. Say what the figure actually is rather than a sentence
            # the number contradicts.
            if _pv_override and _cust_for_preview:
                if _pv <= int(_cust_for_preview):
                    _pv_para = ("The estimated value shown on Preview is set at "
                                "or under Customary Value &mdash; a conservative "
                                "position chosen for this home.")
                    note(f"Roadmap: the Preview price {money(_pv)} is at or "
                         "BELOW the Customary Value of "
                         f"{money(int(_cust_for_preview))}. The rule calls for "
                         f"{money(_calc)}.")
                elif _pv > _calc:
                    _pv_para = ("The estimated value shown on Preview is set "
                                "above the threshold over Customary Value "
                                "&mdash; a reach position, high enough to anchor "
                                "expectations before the home goes active.")
                    note(f"Roadmap: the Preview price {money(_pv)} is "
                         f"{money(_pv - _calc)} above the rule's "
                         f"{money(_calc)}"
                         + (f", and {money(_pv - _prem_for_preview)} above the "
                            f"Premium Value of {money(_prem_for_preview)}"
                            if _prem_for_preview and _pv > _prem_for_preview
                            else "") + ".")
                else:
                    # set by hand over Customary (e.g. Westford, Casey 9 Nov 2026:
                    # "preview 1.25") -- describe it as the over-Customary figure
                    _pv_para = ("The estimated value shown on Preview is the "
                                "threshold just over Customary Value &mdash; high "
                                "enough to set expectations, and the figure buyers "
                                "carry with them when the home goes active.")
            # Casey, 27 Nov 2026: one line, then the price.
            _pv_basis = ("Set for this property" if _pv_override else
                         f"First threshold under the Premium Value of {abbrev(int(_prem_for_preview))}"
                         if _prem_for_preview else _pv_basis)
            preview_section = f"""<section class="preview-sec">
  <div class="wrap">
    <h2 class="test-head">The Test</h2>
    <h2 class="section-title">Preview</h2>
    <p class="price-para">This is the seller&rsquo;s opportunity to <b>test higher
    values</b> without hurting the marketability of the home.</p>
    <div class="price-card">
      <div class="rec-label">Preview Price</div>
      <div class="rec-price">{money(_pv)}</div>
      <div class="rec-expected">{_pv_basis}</div>
    </div>
  </div>
</section>
"""
        else:
            note("Roadmap: Preview section OMITTED — no premium value to take "
                 "the threshold from.")
    else:
        note(f'Roadmap: Preview section OMITTED — listing_status is '
             f'{p.get("listing_status")}, so the home is already on the market.')

    # ---- Coming Soon ---------------------------------------------------
    # One position, picked by who controls the market. Conservative tests the
    # first threshold UNDER Customary Value; aggressive tests the first one
    # OVER it. A hand-set price beats both.
    _prem_cs = (p["values"].get("premium")
                or (s.premium_top if s.has_upgrades else 0))
    coming_soon_section = ""
    if p.get("listing_status") not in ("recovery", "relaunch") and _prem_cs:
        _cs = _f["coming_soon"]
        _cs_basis = ("Set for this property" if _f["coming_soon_set"] else
                     f"First threshold {'under' if _cons else 'over'} the "
                     f'Customary Value of {abbrev(p["values"]["customary"])}')
        # Casey, 27 Nov 2026: two tags -- Conservative, the first threshold
        # under Customary; Aggressive, the first threshold over. Market
        # dictates strategy; the market's pick is the one marked.
        from pricing import preview_over_customary as _poc, increment_for as _incf, \
            grid_line_at_or_below as _glb
        _cv = int(p["values"]["customary"])
        _cons_p = _cs if _cons else _glb(_cv, _incf(_cv)) - 1
        _agg_p = _cs if not _cons else _poc(_cv) - 1
        def _tag(name, price, rule, on):
            return (f'<div class="cs-card{" on" if on else ""}"><div class="rec-label">{name}</div>'
                    f'<div class="rec-price">{money(price)}</div>'
                    f'<div class="rec-expected">{rule}</div>'
                    + ('<div class="cs-pick">This market</div>' if on else "") + '</div>')
        coming_soon_section = f"""<section class="cs-sec">
  <div class="wrap">
    <h2 class="section-title">Coming Soon</h2>
    <p class="price-para"><b>Market dictates strategy.</b></p>
    <div class="cs-cards two">
      {_tag("Conservative", _cons_p, f"First threshold under the Customary Value of {abbrev(_cv)}", _cons)}
      {_tag("Aggressive", _agg_p, f"First threshold over the Customary Value of {abbrev(_cv)}", not _cons)}
    </div>
  </div>
</section>
<style>.cs-cards.two{{display:flex;gap:18px;justify-content:center;flex-wrap:wrap}}
.cs-cards.two .cs-card{{flex:1 1 260px;max-width:340px;opacity:.55;background:#fff;border:1px solid #E4DCC8;border-radius:10px;padding:18px 16px;text-align:center}}
.cs-cards.two .cs-card.on{{opacity:1;border:2px solid #B8902F}}
.cs-pick{{margin-top:8px;font:700 11px Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:#8A6A2E}}</style>
"""

    _privacy_note = (
        "Sample Recovery Roadmap &mdash; shared with permission as an example "
        "of the Listing Recovery Team&rsquo;s work."
        if p.get("showcase") else
        "This is a private link prepared for the seller of this property "
        "&mdash; please do not share.")
    # Casey, 15 Oct 2026: "MOVING THE NEEDLE, CURRENT COMPETITION, THEN
    # REMOVE [the market band] FROM PRICING STRATEGY. THEN AUTHENTICATED
    # VALUE." The three sections are built here and placed in that order in
    # the template, so the running order is a short list to read rather
    # than a thousand lines of markup to trace.
    #
    # Current Competition carries the CST Market Intelligence dashboard, so
    # it comes before the Pricing Strategy that acts on it: the seller sees
    # the market, then what to do about it, then what the home is worth. A
    # recovery Roadmap is reordered wholesale further down, so there the
    # competition stays in its own marked block and out of this flow.
    # Casey, 17 Nov 2026: the CST Ten Cylinder Pricing Engine opens the
    # authenticated prices on every Roadmap (engine.py).
    import engine as _eng
    # The same reading the Roadmap's hero band prints (the MSS cache), so the
    # filter never quotes a different figure than the top of the page.
    _mp = {}
    try:
        _mp = (json.loads((HERE / "market_cache.json").read_text())
               .get((p.get("market") or {}).get("slug") or "", {}) or {}).get("stats") or {}
    except Exception:
        pass
    if not _mp.get("control"):
        _mp = market_posture(p)
    _eng_kw = dict(coming_soon=(_cs if coming_soon_section else 0),
                   conservative=_cons, stats=_mp,
                   relaunch=(recovery_prices(p).get("soft", 0)
                             if is_recovery(p) and p.get("current_list") else 0))
    # Casey, 27 Nov 2026: the cylinder explanations move to the Guide.
    _engine_html = _eng.panel(p, cards=False, **_eng_kw)
    GUIDE_NOTES["engine_cards"] = _eng.panel(p, image=False, **_eng_kw)
    # Casey, 18 Nov 2026: "add sold for $2.3M over authenticated values". A
    # closed sale ("sold_for") is stamped above the three value cards.
    _sold_html = ""
    if p.get("sold_for"):
        _sfp, _vv = p["sold_for"], p["values"]
        _top = _vv.get("premium_top") or _vv["premium"]
        if _vv["customary"] <= _sfp <= _top:
            _where = (f'within the authenticated range of {abbrev(_vv["customary"])}'
                      f'&ndash;{abbrev(_top)}, {(_sfp / _vv["customary"] - 1) * 100:.1f}% '
                      f'over Customary Value')
        elif _sfp > _top:
            _where = f'{(_sfp / _top - 1) * 100:.1f}% over Premium Value'
        else:
            _where = f'{(1 - _sfp / _vv["customary"]) * 100:.1f}% under Customary Value'
        _sold_html = (
            '    <div class="sold-stamp" style="text-align:center;margin:4px auto 18px;">'
            '<span style="display:inline-block;border:3px solid #2F6B3A;color:#2F6B3A;'
            "border-radius:10px;padding:8px 22px;font-family:'Playfair Display',Georgia,serif;"
            'font-weight:700;font-size:24px;letter-spacing:.06em;transform:rotate(-2deg);'
            f'background:#f3f8f2;">SOLD for {money(_sfp)}</span>'
            f'<div style="margin-top:8px;font-size:14px;color:#2F6B3A;">{_where}</div></div>\n')
    # Casey, 17 Nov 2026: heading "Price Authenticated by CST Pricing Team";
    # label over the three values.
    auth_section = f"""<section{upgrade_break}>
  <div class="wrap">
    <h2 class="section-title">Price Authenticated by CST Pricing Team</h2>
    <p class="section-sub">{auth_stats}</p>
{_engine_html}    <p class="values-label" style="text-align:center;font-family:'Playfair Display',Georgia,serif;font-style:italic;font-size:15px;color:var(--gold-deep,#8A6A2E);margin:6px auto 14px;max-width:760px;line-height:1.45;">Final Values are determined after inspection by a CST Trained Realtor of property condition, upgrades and lot premium/discount.</p>
    <div class="values-grid"{grid_style}>
{chr(10).join(cards)}
    </div>
{_sold_html}{net_proceeds_html(p, tiers)}{value_story_html(p)}  </div>
</section>"""
    pricing_section = f"""<section>
  <div class="wrap">
    <h2 class="section-title">CST Pricing Strategy</h2>
    <p class="section-sub">Based on current market conditions.</p>
{posture_line}    <div class="table-wrap price-table">
      <table>
        <thead><tr>{"".join(f"<th>{c}</th>" for c in threshold_cols)}</tr></thead>
        <tbody><tr>{"".join(f"<td>{v}</td>" for v in threshold_vals)}</tr></tbody>
      </table>
    </div>
    <p class="price-para">{strategy_para}</p>
{alert_html}{notes_html}
    <a class="ps-cta" href="{p["prefix"]}_Pricing_Strategy_Summary.pdf"
       target="_blank" rel="noopener">
      Print the {summary_name(p)}
      <span>{"Authenticated values, the buyer pool, market conditions and both relaunch prices"
             if _is_recovery else
             "Target values, market conditions, Preview, Coming Soon and The Launch"} &mdash; one page</span>
    </a>
  </div>
</section>"""
    # Casey, 27 Nov 2026: "add size and age to listed homes and remove
    # table" -- the numbered list under The Current Market map carries them.
    _mmp = p.get("market_map") or {}
    _list_map_on = bool(_mmp.get("subject") and _mmp.get("listings")
                        and _mmp.get("listings_map", True) is not False)
    comp_section = f"""<section{upgrade_break}>
  <div class="wrap">
    <h2 class="section-title">Market Filter</h2>
    <p class="section-sub" style="margin-top:-4px;">Current Market Conditions</p>
{market_block(p["market"], compact=True)}
<!--RMMl-anchor-->
    {f"""<div class="table-wrap">
      <table>
        <thead><tr><th>Status</th><th>Property</th><th>DOM</th><th>Built</th><th>Finished SF</th><th>Assessment</th><th>List Price</th></tr></thead>
        <tbody>
{comp_body}
        </tbody>
      </table>
    </div>""" if (comp_body and not _list_map_on) else ''}
  </div>
</section>"""
    # Casey, 22 Nov 2026: recovery Roadmaps follow the standard order --
    # Current Competition before the CST Pricing Strategy.
    comp_in_bg = comp_section
    comp_at_end = ""

    # Casey, 23 Nov 2026: "The roadmap header should be The Casey Samson Team
    # Roadmap to Success (address)". The separate team line stays only on
    # private-label builds, where it carries the agent's name and tag.
    # Casey, 24 Nov 2026: the two-line header carries the team (or, on a
    # private label, the agent) itself, so no separate brand line.
    _rm_brandline = ""
    body = f"""<body>

<a class="back" href="index.html">&larr; Back to {addr}</a>
<!-- Casey, 23 Nov 2026: privacy note removed from the Roadmap. -->
<div class="rm-hero">
{rm_hero_img}
  <div class="rm-shade"></div>
  <div class="rm-hero-inner">
    <img class="seal" src="Gold_Standard_Logo.png" alt="Gold Standard Listing">
{_rm_brandline}
    {('<p class="lbl rts"><span class="rts-1">The Casey Samson Team</span>'
      f'<span class="rts-2">{"Recovery Roadmap to Success" if _is_recovery else (p.get("roadmap_title") or "Seller Roadmap to Success")}</span></p>')}
    <h1>{"Address" if is_example_home(p) or p.get("address") == "Sample" else addr}</h1>
    <p class="city">{city_state}</p>
{rm_tag}
  </div>
</div>

{rm_facts}
<!--SEC:bg-start-->
<!--SEC:bg-start-->
{rm_subject}{rm_comps_section}
{auth_section}
<section>
  <div class="wrap">
    <h2 class="section-title">Condition Filter</h2>
    <p class="needle-lede">Strategic improvements return 7 times the investment.</p>
    <p class="section-sub" style="margin-top:-14px;">Buyers do not pay top dollar for dated or DIY homes.</p>
    <div class="needle-frame">
      <div>
        <p class="needle-dir up">Moving the Needle Up</p>
        <div class="needle-table">
          <div class="needle-cols">
            <div class="needle-col">
              <h4>Presentation Improvements</h4>
              <ul>
                <li><b>Fresh designer paint and detailed touch-ups</b></li>
                <li><b>Updated lighting, hardware, and fixtures</b></li>
                <li><b>Flooring and finish refinishing</b></li>
                <li><b>Landscaping and curb-appeal enhancements</b></li>
                <li><b>Targeted kitchen and bathroom improvements</b></li>
              </ul>
            </div>
            <div class="needle-col">
              <h4>Buyer Confidence Improvements</h4>
              <ul>
                <li>Pre-listing home inspection</li>
                <li>Complete seller disclosures</li>
                <li>Authenticated Values&trade; of the property and upgrades</li>
                <li>Premium photography and cinematic video</li>
                <li>Highlight condition, location, and lifestyle</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      <div>
        <p class="needle-dir down">Moving the Needle Down</p>
        <div class="needle-rail">
          <div class="rail-in">
            <h4>What Buyers Discount For</h4>
            <ul>
{needle_down_items(p)}
            </ul>
          </div>
        </div>
      </div>
    </div>
    <p class="needle-note">A roof over 20 years should be replaced by a contractor
    willing to be paid at settlement. The deal killer is removed and the cost is
    recovered.</p>
  </div>
</section>
{rm_lot}
{comp_in_bg}
{pricing_section}

{preview_section}
{coming_soon_section}
<!--SEC:bg-end-->

<!--SEC:next-start-->
{next_step_section}
<!--SEC:next-end-->

<!--SEC:comp-start-->
{comp_at_end}
<!--SEC:comp-end-->
{_rm_bp_section}
{_zc_seller}

<section>
  <div class="wrap team-section">
    <h2 class="section-title" style="margin-bottom:20px;">Virginia's #1 Luxury Real Estate Team</h2>
    {__import__("roadmap_sections").team_photo(p, out)}
    <h3>Home To</h3>
    <ul>
      <li>4 of the Top 7 Listing Agents at Samson Properties &mdash; out of 6,500 agents</li>
      <li>3 of the Top 5 Luxury Selling Agents at Samson Properties</li>
    </ul>
    <h3>2025 Track Record</h3>
    <ul>
      <li>$233 Million in Sales During 2025</li>
      <li>$150 Million in Homes Sold Over $1.5 Million During 2025</li>
      <li>$70 Million Sold and Under Contract Over $2 Million in 2026</li>
    </ul>
    <p class="stat-line" style="margin-top:20px;">97% Success Rate<span class="sep">|</span>Average DOM: 6<span class="sep">|</span>Average $93,000 Over List</p>
    <p class="tagline-close">Results Count&trade;</p>
  </div>
</section>

{footer(p)}
</body>
</html>
"""
    if p.get("listing_status") == "recovery" and comp_at_end:
        body = _recovery_order(body)
    body = re.sub(r"<!--SEC:[a-z-]+-->\n?", "", body)   # layout markers, not content
    (out / f'{p["prefix"]}_Roadmap.html').write_text(head + body)
    if p.get("guides") is not False:
        # Casey, 22 Nov 2026: all four guides live on the seller site, for the
        # "Guides to Understanding CST Tools" row at the top of the portal.
        for _k in ("roadmap", "buyer", "mss", "moveup"):
            copy_guide(_k, out, p["prefix"])


def agent_card(p):
    """The buyer portal's contact card — photo, names, numbers, office —
    reused as the footer of the printable Buyer Pricing. Falls back to a
    plain contact line when there is no card on file."""
    c = (p.get("buyer_portal") or {}).get("contacts") or {}
    if not c.get("lines"):
        return ""
    photo = (f'<img src="{c["photo"]}" alt="">' if c.get("photo") else "")
    rows = "".join(
        f'<div class="ac-row"><b>{n}</b>'
        f'<span class="ac-ph">{ph}</span>'
        f'<span class="ac-sep">|</span>'
        f'<a href="mailto:{em}">{em}</a></div>'
        for n, ph, em in c["lines"])
    office = f'<div class="ac-office">{c["office"]}</div>' if c.get("office") else ""
    return (f'<div class="agent-card">{photo}<div class="ac-body">'
            f'<p class="ac-name">{c.get("names", "")}</p>'
            f'<div class="ac-team">{c.get("team", "")}</div>'
            f"{rows}{office}</div></div>\n")


def buyer_qr_corner(p, on_photo=False):
    """Scan-to-open QR for the printed Buyer Pricing Report, set into the top
    right corner of page one. This is the sheet handed out at open houses, so
    the code is the bridge from paper back to the live buyer portal. Inline
    SVG: prints crisp at any size and needs no asset file beside the PDF."""
    b = p.get("buyer_portal") or {}
    # One shared decision for both surfaces: the Buyer Portal's address on
    # caseysamson.com. Imported rather than copied so the printed report and
    # the web portal can never point to different places.
    try:
        from build_buyer_portal import qr_target
        url = qr_target(p)
    except Exception as e:                            # pragma: no cover
        url = b.get("qr_url") or b.get("url")
        note(f"Buyer Report QR: falling back to the portal URL ({e}).")
    if not url:
        note("Buyer Report: QR OMITTED — no buyer_portal url on file.")
        return ""
    # Same rule as the seller-facing links: no code until there is a page to
    # scan into. A dead QR on a sheet handed out at an open house is worse
    # than no QR, because the buyer finds out in front of the agent.
    if b.get("live") is not True:
        note("Buyer Report: QR OMITTED — the buyer portal is not published "
             'yet. Set "live": true on the day the page goes up.')
        return ""
    if segno is None:
        note("Buyer Report: QR OMITTED — segno is not installed "
             "(python3.12 -m pip install --break-system-packages segno).")
        return ""
    import io
    buf = io.BytesIO()
    segno.make(url, error="m").save(
        buf, kind="svg", scale=1, border=2, dark="#2B2622",
        svgclass=None, lineclass=None, omitsize=True, xmldecl=False, svgns=True)
    svg = buf.getvalue().decode("utf-8").strip()
    cls = "br-qr-corner on-photo" if on_photo else "br-qr-corner"
    return (f'  <div class="{cls}">\n    <div class="bqc-tile">{svg}</div>\n'
            '    <div class="bqc-cap">Scan to View</div>\n  </div>\n')


def footer(p, produced="Produced by The Casey Samson Team", buyer_facing=False):
    """The contact block. A buyer-facing document lists the agents a buyer's
    agent actually calls, from the buyer_portal contacts; everything else
    lists the listing agent. Both carry the copyright line."""
    lines, office = [], ""
    card = agent_card(p) if buyer_facing else ""
    if card:
        return f"""<footer class="card-foot">
  <div class="wrap">
{card}    <div class="copy">&copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </div>
</footer>
"""
    if False:
        pass
    else:
        a = p["agent"]
        bits = [a.get("display") or a["lookup"]]
        if a.get("phone"):
            bits.append(f'<span class="sep">|</span>{a["phone"]}')
        if a.get("email"):
            bits.append(f'<span class="sep">|</span><a href="mailto:{a["email"]}">{a["email"]}</a>')
        lines.append(f'<div class="contact-line">{"".join(bits)}</div>')
    return f"""<footer>
  <div class="wrap">
    <div class="produced">{produced}</div>
{"".join("    " + x + chr(10) for x in lines)}{office}
    <div class="copy">&copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </div>
</footer>
"""


# ---------------------------------------------------------- Buyer Report ----
def walk_to_strip(p, limit=0, notes=False):
    """The Walk To band, condensed for print.

    Same places and times as the Buyer Portal, laid out five across without
    the circular marks — the tiles the page uses are too tall for a document
    fitted to two sides. `limit` caps how many places are shown, and `notes`
    adds each place's one-line description, which the fitter turns on when
    page one would otherwise end short.
    """
    places = ((p.get("buyer_portal") or {}).get("walk_to") or [])
    if not limit or not places:
        return ""
    cells = "".join(
        f'      <div class="br-wt"><span class="g">{WALK_GLYPHS.get(pl.get("kind", ""), "")}</span>'
        f'<span class="n">{pl["name"]}</span>'
        + (f'<span class="d">{pl["note"]}</span>'
           if notes and pl.get("note") else "")
        + f'<span class="m">{pl["minutes"]} min</span></div>\n'
        for pl in places[:limit])
    return ('<section class="br-walk">\n  <div class="wrap">\n'
            '    <h2 class="section-title">Walk To</h2>\n'
            '    <p class="section-sub">Downtown Vienna, on foot from the front door.</p>\n'
            f'    <div class="br-wt-grid">\n{cells}    </div>\n  </div>\n</section>\n')


# Generic category glyphs, matching the Buyer Portal's. Drawn small so they
# sit on the baseline next to the place name rather than above it.
WALK_GLYPHS = {
    k: ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round">{d}</svg>')
    for k, d in {
        "dining": '<path d="M6 3v7a2 2 0 0 0 4 0V3"/><path d="M8 12v9"/>'
                  '<path d="M17 3c-1.7 1.2-2.5 3-2.5 5.2 0 1.7.8 2.8 2.5 2.8"/><path d="M17 11v10"/>',
        "coffee": '<path d="M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/>'
                  '<path d="M17 9h1.6a2.4 2.4 0 0 1 0 4.8H17"/><path d="M7 2v3"/><path d="M11 2v3"/>',
        "grocery": '<path d="M3 7h18l-1.7 11.2a2 2 0 0 1-2 1.8H6.7a2 2 0 0 1-2-1.8z"/>'
                   '<path d="M8.5 7 12 2l3.5 5"/>',
        "books": '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H19v15H5.5A1.5 1.5 0 0 0 4 19.5z"/>'
                 '<path d="M4 19.5A1.5 1.5 0 0 1 5.5 21H19"/>',
        "mail": '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.6 6.8 8.4 6 8.4-6"/>',
        "park": '<path d="M12 3 5.5 14h13z"/><path d="M12 8.5 7.5 16h9z"/><path d="M12 16v5"/>',
        "trail": '<circle cx="5.5" cy="17" r="3"/><circle cx="18.5" cy="17" r="3"/>'
                 '<path d="M8 17h4l4-7"/><path d="M14 10h4"/><path d="M12 17 9.5 9.5H7"/>',
        "civic": '<path d="M3 21h18"/><path d="M4.5 21V9.5L12 4l7.5 5.5V21"/>'
                 '<path d="M9.5 21v-6h5v6"/>',
    }.items()}

BR_WALK_CSS = """
  .br-walk{padding-top:14px !important;}
  .br-wt-grid{display:grid; grid-template-columns:repeat(5,1fr); gap:8px;
    max-width:940px; margin:0 auto;}
  .br-wt{display:flex; flex-direction:column; align-items:center; text-align:center;
    gap:2px; border:1px solid var(--rule); border-radius:6px; padding:9px 6px;
    background:var(--card); break-inside:avoid; page-break-inside:avoid;}
  .br-wt .g{color:var(--gold-deep); line-height:0;}
  .br-wt .g svg{width:16px; height:16px;}
  .br-wt .n{font-family:'Playfair Display',Georgia,serif; font-size:12px; font-weight:700;
    line-height:1.2;}
  .br-wt .d{font-size:9.5px; line-height:1.35; color:var(--muted); margin-top:1px;}
  .br-wt .m{font-size:9px; letter-spacing:.07em; text-transform:uppercase; font-weight:700;
    color:var(--gold-deep); margin-top:auto; padding-top:4px;}
  @media print{ .br-walk{padding:10px 0 !important;}
    .br-wt-grid{break-inside:avoid; page-break-inside:avoid;} }"""


def build_buyer_report(p, s, out, stats=True, balance=False, cover=True, loves=0, walk=0,
                       walk_notes=False, cover_px=0, guide_in_mast=False):
    subj, addr = p["subject"], p["address"]
    # PDF rule: the sub-photo row is stripped from the printed gallery;
    # only the main photo is kept. The web page keeps all of them.
    head = head_of("buyer_report.html",
                   f"{addr} — Buyer Pricing Report — The Casey Samson Team",
                   PRINT_CSS + BR_BANNER_CSS + RM_BADGE_CSS + BR_PRINT_CSS
                   + BR_WALK_CSS
                   # Last in source order so it beats the print default. The
                   # fitter grows the cover to take up whatever page one has
                   # left once everything below it is placed.
                   + (f"\n  @media print{{ .br-cover{{min-height:{cover_px}px;}} }}"
                      if cover_px else ""))
    url = p["listing_url"]

    photos = p.get("photos") or []
    # The lead photo becomes the masthead banner; the rest stay as a gallery.
    mast_photo, rest = (photos[0], photos[1:5]) if photos else (None, [])
    if not photos:
        note("Buyer Report: photo gallery OMITTED — no photos supplied.")

    if rest:
        subs = "".join(f'        <img src="{i}" alt="">\n' for i in rest)
        grid = (' style="grid-template-columns:repeat(4,1fr);"' if len(rest) == 4
                else ' style="grid-template-columns:repeat(2,1fr);"' if len(rest) == 2
                else "")
        gallery = (
            '<section style="padding-top:28px; padding-bottom:0;">\n  <div class="wrap">\n'
            '    <div class="photo-gallery">\n'
            f'      <div class="sub-photos"{grid}>\n{subs}      </div>\n'
            "    </div>\n  </div>\n</section>\n")
    else:
        gallery = ""

    if p["comps"]["rows"]:
        comps_section = f"""<section>
  <div class="wrap">
    <h2 class="section-title">Comparable Property Analysis</h2>
    <p class="section-sub">These qualified comparable properties authenticate the Casey Samson Team value range below.</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Property</th><th>Built</th><th>Finished SF</th><th>Lot</th><th>Assessment</th><th>Sales Price</th></tr></thead>
        <tbody>
{comp_rows([[addr, subj["built"], subj["sf"], subj["lot"], subj["assessment"], None]], cls="total-row")}
{comp_rows(p["comps"]["rows"][:p.get("br_max_comps", 8)], p=p)}
{comp_rows(p["comps"]["summary"], cls="total-row")}
        </tbody>
      </table>
    </div>
{comp_gallery(p["comps"]["rows"][:p.get("br_max_comps", 8)])}  </div>
</section>
"""
    else:
        comps_section = ""
        note("Buyer Report: Comparable Property Analysis OMITTED — no comps supplied.")

    lead_photo = (f'\n<div class="lead-photo"><img src="{mast_photo}" alt="{addr}"></div>\n'
                  if mast_photo else "")
    # The callout shows the short property address but links to the live
    # caseysamson.com listing page whenever one is on file.
    # Show exactly where the link goes. PDF viewers auto-link any text that
    # looks like a web address, so a different visible address would win.
    if p.get("listing_page_url"):
        callout_href = p["listing_page_url"]
        callout_text = re.sub(r"^https?://", "", callout_href).rstrip("/")
        callout_style = ' class="is-url"'
    else:
        callout_href = f"https://www.{url}"
        callout_text = f"www.{url}"
        callout_style = ""

    if s.has_upgrades:
        upgrade_header = (
            '    <h3 style="text-align:center; font-family:\'Playfair Display\',Georgia,serif; '
            'font-size:18px; font-weight:700; color:var(--gold-deep); margin:0 0 20px;">'
            f'Over {money(p["values"]["upgrades"])} in Upgrades</h3>\n')
        # With extraordinary upgrades the buyer's options are the two return
        # scenarios — Customary is not one of them, so it is not shown here.
        hi = ' style="border-color:var(--gold-line); box-shadow:0 4px 14px rgba(138,106,46,.08);"'
        values_cards = f"""      <div class="value-card"{hi}>
        <h3>33% Return of Upgrades</h3>
        <div class="value-num">{money(s.premium_bottom)}</div>
        <ul>
          <li>Kitchen and bathrooms updated within ~10 years.</li>
          <li>Upgrades, finishes, and craftsmanship exceed the standard.</li>
          <li>A third of the upgrade spend recognised at sale.</li>
        </ul>
      </div>
      <div class="value-card"{hi}>
        <h3>50% Return of Upgrades</h3>
        <div class="value-num">{money(s.premium_top)}</div>
        <ul>
          <li>Presentation distinguishes the property from the competition.</li>
          <li>Upgrades fully recognised by the buyer pool.</li>
          <li>Half of the upgrade spend recognised at sale.</li>
        </ul>
      </div>
"""
    else:
        upgrade_header = ""
        values_cards = f"""      <div class="value-card">
        <h3>Customary Value</h3>
        <div class="value-num">{money(p["values"]["customary"])}</div>
        <ul>
          <li>Kitchen and bathrooms updated within ~15 years.</li>
          <li>Paint, lighting, hardware, flooring, finishes reflect current standard.</li>
          <li>Overall presentation is competitive with comparable homes.</li>
        </ul>
      </div>
      <div class="value-card" style="border-color:var(--gold-line); box-shadow:0 4px 14px rgba(138,106,46,.08);">
        <h3>{s.premium_label}</h3>
        <div class="value-num">{s.premium_display}</div>
        <ul>
          <li>Kitchen and bathrooms updated within ~10 years.</li>
          <li>Upgrades, finishes, and craftsmanship exceed the standard.</li>
          <li>Overall presentation distinguishes the property from the competition.</li>
        </ul>
      </div>
"""

    # The printable Buyer Pricing document: condensed header, the headline
    # features, the authenticated pricing and the premiums. Photography lives
    # on the Buyer Portal; this is the page an agent hands across a table.
    _bp = p.get("buyer_portal") or {}
    _hero = p.get("hero_photo")
    _asrc = Path(p.get("asset_dir", "."))
    if not _asrc.is_absolute():
        _asrc = HERE / _asrc
    if _hero and not (_asrc / _hero).exists():
        _hero = None

    # The cover, when it fits: the same photo, price and band the Buyer
    # Portal opens with. The fit pass strips it back if the document spills.
    br_cover = ""
    if cover and _hero:
        _price = (f'<div class="rm-badges"><div class="rm-badge br-price">'
                  f'<div class="v">{money(_bp["list_price"])}</div></div></div>'
                  if _bp.get("list_price") else "")
        _site = (f'<span class="rm-site">{_bp["site"]}</span>'
                 if _bp.get("site") else "")
        # The team is named in the footer and the city is in the comps table,
        # so the cover carries only the address, the price and the site.
        br_cover = f"""<div class="rm-hero br-cover">
  <img src="{_hero}" alt="{addr}">
  <div class="rm-shade"></div>
  <div class="rm-hero-inner">
    <img class="seal" src="Gold_Standard_Logo.png" alt="Gold Standard Listing">
    <div class="br-ttl" style="font-family:'Playfair Display',Georgia,serif;color:#E8C77A;font-weight:700;
      line-height:1.15;margin:4px 0 8px;text-shadow:0 2px 10px rgba(0,0,0,.6);">
      <span style="display:block;font-size:22px;letter-spacing:.06em;">The Casey Samson Team</span>
      <span style="display:block;font-size:30px;color:#FFFDF7;">Buyer Report</span></div>
    <h1>{_bp.get("display_address") or addr}</h1>
    {_price}
    {_site}
  </div>
{buyer_qr_corner(p, on_photo=True)}</div>
"""
    # A stat strip under the header when the page has room for it. The fit
    # pass below drops it first if the document runs past two pages.
    _facts = _bp.get("facts") or []
    br_stats = ""
    if stats and _facts:
        br_stats = ('<div class="wrap"><div class="br-stats">'
                    + "".join(f'<div class="br-stat"><span class="n">{n}</span>'
                              f'<div class="l">{l}</div></div>' for n, l in _facts)
                    + "</div></div>\n")

    _fh = (p.get("buyer_portal") or {}).get("feature_headlines") or []
    br_headlines = ""
    if _fh:
        _blocks = "".join(
            f'      <div class="br-fh"><h3>{x["head"]}</h3>'
            f'<p>{" &middot; ".join(x["sub"])}</p></div>\n' for x in _fh)
        br_headlines = ('<section style="padding-bottom:10px;">\n  <div class="wrap">\n'
                        '    <div class="br-fhs">\n' + _blocks +
                        "    </div>\n  </div>\n</section>\n")
    else:
        note("Buyer Report: headline features OMITTED — none on the buyer_portal "
             "block for this property.")

    _loves = _bp.get("loves") or []
    br_loves = ""
    if loves and _loves:
        _shown = _loves[:loves]
        br_loves = ('<section class="br-loves">\n  <div class="wrap">\n'
                    '    <h2 class="section-title">What the Owners Love</h2>\n'
                    '    <ul class="br-loves-list">\n'
                    + "".join(f"      <li>{x}</li>\n" for x in _shown)
                    + "    </ul>\n  </div>\n</section>\n")

    # The same report as a single printable file. A buyer's agent who wants to
    # put this in front of a client on paper should not have to hunt for it.
    br_pdf = f"""
<section class="br-pdf">
  <div class="wrap">
    <a class="br-pdf-link" href="{p["prefix"]}_Buyer_Report.pdf"
       target="_blank" rel="noopener">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        style="display:inline-block; vertical-align:-2px; margin-right:9px;"
        ><path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6z"/></svg
      >Download this report as a PDF</a>
  </div>
</section>
"""

    # Casey, 22 Nov 2026: "Guide to Understanding the Buyer Report should have
    # a prominent place on Buyer Reports." Absolute link so it works from the
    # printed PDF as well.
    _gr = (seller_host(p) or "").rstrip("/")
    _gh = f"{_gr}/Buyer_Report_Guide.html" if _gr else "Buyer_Report_Guide.html"
    _mast_guide = (f'<a href="{_gh}" style="display:block;margin-top:6px;font:700 22px Georgia,serif;'
                   'color:#8A6A2E;text-decoration:underline;">Guide to Understanding the Buyer Report &rarr;</a>'
                   if p.get("guides") is not False else "")
    # Casey, 23 Nov 2026: "Buyer report Remove guide link on top."
    _br_guide = ("" if True else
        '<style>@media print{.br-guide-s{padding:0!important}.br-guide{margin:6px auto 0!important;padding:6px 12px!important;font-size:25px!important;line-height:1.3!important}.br-guide span{display:inline!important;margin:0 6px!important;font-size:12px!important}}</style>'
        f'<section class="br-guide-s" style="padding:0;"><div class="wrap"><a class="br-guide" href="{_gh}" target="_blank" rel="noopener" '
        'style="display:block;margin:26px auto 4px;max-width:1000px;background:#1F2A44;color:#E8C77A;'
        'text-align:center;text-decoration:none;border-radius:8px;padding:20px 18px;'
        "font:700 38px 'Playfair Display',Georgia,serif;-webkit-print-color-adjust:exact;print-color-adjust:exact;\">"
        '<span style="display:block;font:700 14px Georgia,serif;letter-spacing:.22em;text-transform:uppercase;'
        'color:#C9D2E0;margin-bottom:4px;">New to this report?</span>Guide to Understanding the Buyer Report '
        f'&rarr;<span style="display:block;font:12px Georgia,serif;color:#C9D2E0;margin-top:4px;">{_gh.replace("https://", "")}</span></a></div></section>\n')
    br_masthead = br_cover if br_cover else f"""<header class="masthead">
  <div class="mast-row">
    <div class="mast-left">
      <img src="Gold_Standard_Logo.png" alt="Gold Standard Listing">
      <div class="mast-team">The Casey Samson Team</div>
    </div>
    <div class="mast-mid">
      <p class="addr">{addr}</p>
      <p class="city">{p["city"]}, {p["state"]}</p>
    </div>
    <div class="mast-right"><h1 class="title">Buyer Report</h1>
{buyer_qr_corner(p)}    </div>
  </div>
</header>
"""

    # Casey, 15 Oct 2026: "All Printable buyer Pricing is about headlines,
    # features and updates, and pricing", and "all buyer print needs 2
    # pages". Where the property carries a Features & Updates block, the
    # Premium Rating box says the same things a second time -- MacArthur
    # listed the 2021-2022 remodel, the 2022 paint and the 2007 roof under
    # "Other Upgrades" and again under "Updates & Improvements" -- and the
    # repeat is what pushed the sheet onto a third page.
    #
    # The box stays wherever there is no features block, because without it
    # the sheet would be a comps table and two value cards with nothing
    # about the home on it at all.
    if _bp.get("features"):
        rating = ""
        note("Buyer Report: Premium Rating box dropped — Features & Updates "
             "carries the same ground, and the printable sheet is headlines, "
             "features and updates, and pricing.")
    else:
        rating = premium_rating_block(p, balance=True,
                                      groups=upgrades_only(p))
        if not p.get("premium_rating"):
            note("Buyer Report: Premium Rating placeholder shown — no "
                 "property remarks supplied yet.")

    # Casey, 15 Oct 2026: Features & Updates "should appear on Printable
    # buyer Pricing flier". It is the same block the Buyer Portal carries,
    # from buyer_portal.features, so the sheet a buyer's agent prints says
    # the same things as the page they were sent.
    _feat = _bp.get("features")
    br_features = ""
    if _feat:
        if isinstance(_feat, list):
            _feat = {"Top Features": _feat}
        _cols = "".join(
            f'      <div class="br-fc"><h3>{h}</h3><ul>'
            + "".join(f"<li>{i}</li>" for i in items)
            + "</ul></div>\n" for h, items in _feat.items())
        br_features = (
            '<section class="br-feats">\n  <div class="wrap">\n'
            '    <h2 class="section-title">Features &amp; Updates</h2>\n'
            f'    <div class="br-fcs">\n{_cols}    </div>\n'
            "  </div>\n</section>\n")
    else:
        note("Buyer Report: Features &amp; Updates OMITTED — no \"features\" "
             "on the buyer_portal block.")

    body = f"""<body>

<a class="back" id="backLink" href="index.html" style="display:none;">&larr; Back to {addr}</a>
<script>
  // Show the breadcrumb only when the visitor arrived from inside this
  // portal. Same-origin covers the nav page at the site root, the Roadmap
  // and the Tracker; a direct URL, an emailed link or an outside referrer
  // leaves the seller's portal unreachable from here.
  (function() {{
    try {{
      var ref = document.referrer;
      if (ref && new URL(ref).origin === window.location.origin) {{
        document.getElementById('backLink').style.display = '';
      }}
    }} catch (e) {{ /* no referrer, or unparseable: leave it hidden */ }}
  }})();
</script>

{br_masthead}
{br_stats}{_br_guide}{br_headlines}{walk_to_strip(p, walk, walk_notes)}{comps_section}
<section class="br-values">
  <div class="wrap">
    <h2 class="section-title">Authenticated Values&trade;</h2>
    <p class="section-sub">Built {subj["built"]} &middot; {sf(subj["sf"])} SF &middot; Assessment {money(subj["assessment"])}</p>
{upgrade_header}    <div class="values-grid">
{values_cards}    </div>
{rating}  </div>
</section>

{br_features}{br_loves}{br_pdf}
{footer(p, produced="The Casey Samson Team", buyer_facing=True)}
</body>
</html>
"""
    # Casey, 23 Nov 2026: guide links "more subtle ... off the top and next
    # to each section like roadmap". Absolute, so they work in the PDF too.
    if p.get("guides") is not False:
        import re as _re
        for _t, _sg in (("Comparable Property Analysis", "comparable-property-analysis"),
                        ("Authenticated Values", "authenticated-values")):
            _m = _re.search(r"(<h2[^>]*>)(\s*" + _t + r".*?</h2>)", body, _re.S)
            if _m:
                body = (body[:_m.start()] + _m.group(1)[:-1] + f' id="s-{_sg}">' + _m.group(2)
                        + f'<a class="glink-sub" href="{_gh}#g-{_sg}" target="_blank" rel="noopener">'
                        f"<span>Guide to Understanding {_t} &rarr;</span></a>" + body[_m.end():])
        # Flush right, styled like the guide's "<- Back to" link (Casey).
        head = head.replace("</style>", ".glink-sub{display:block;text-align:center;margin:2px 0 14px;}"
                            ".glink-sub span{font:700 15px Georgia,serif;color:#1F2A44;"
                            "border-bottom:2px solid #B8902F;padding-bottom:2px}"
                            "@media print{.glink-sub{margin:-6px 0 2px;line-height:1.1}.glink-sub span{font-size:10px;border-bottom-width:1px;padding-bottom:0}}</style>", 1)
    (out / f'{p["prefix"]}_Buyer_Report.html').write_text(head + body)


# --------------------------------------------------------- Seller Tracker ----
MK_PRINT_CSS = """
  @media print{
    section{padding:16px 0 !important;}
    header.masthead{padding:18px 0 14px !important;}
    .price-para{margin:8px 0 !important;}
    .section-sub{margin-bottom:12px !important;}
    .needle-table{margin-top:10px !important;}
    .needle-col li{padding:2px 0 !important; line-height:1.35 !important;}
    .needle-col h4{margin:8px 0 4px !important;}
    .price-card{margin:14px auto !important; padding:12px 16px !important;}
    footer{padding:16px 0 18px !important;}
  }"""


def build_marketing(p, s, out):
    """Marketing Your Home as its own page in the portal, sitting with the
    Buyer Pricing Guide rather than inside the Roadmap."""
    addr, city_state = p["address"], f'{p["city"]}, {p["state"]}'
    head = head_of("roadmap.html",
                   f'{addr} — Marketing Your Home — The Casey Samson Team',
                   PRINT_CSS + MK_PRINT_CSS)
    body = f"""<a class="back" href="index.html">&larr; Back to {addr}</a>

<header class="masthead">
  <div class="wrap">
    <img src="Gold_Standard_Logo.png" alt="Gold Standard Listing" style="display:block; width:100px; margin:0 auto 12px;">
    <div class="brandline">The Casey Samson Team</div>
    <h1 class="title">Marketing Your Home</h1>
    <div class="addr-block">
      <p class="addr">{addr}</p>
      <p class="city">{city_state}</p>
    </div>
  </div>
</header>

<section style="padding-bottom:14px;">
  <div class="wrap">
    <p class="section-sub" style="font-size:16px; font-style:italic; margin-top:0;">
    Maximum Exposure. More Buyers. More Competition.</p>

    <p class="price-para">Marketing isn&rsquo;t just about exposure. It&rsquo;s about
    creating competition. The Casey Samson Team&rsquo;s marketing strategy is designed to
    make your home stand out, build anticipation before it hits the market, and attract
    the largest possible pool of qualified buyers.</p>

    <p class="price-para">It begins with <b>professional photography</b>, <b>compelling
    video</b>, and a <b>custom property website</b> designed to showcase your home&rsquo;s
    unique features and give buyers the information they need to feel confident pursuing
    your property.</p>
  </div>
</section>

<section style="padding-top:14px; padding-bottom:14px;">
  <div class="wrap">
    <h2 class="section-title">Pre-Launch Marketing</h2>
    <p class="section-sub">Marketing isn&rsquo;t about reaching the most people. It&rsquo;s
    about reaching the right buyers before your home officially launches.</p>

    <p class="price-para">Our Marketing Director, <b>Julie Hart</b>, oversees production of:</p>

    <div class="needle-table" style="margin-top:14px;">
      <div class="needle-cols">
        <div class="needle-col">
          <h4>Produced for your home</h4>
          <ul>
            <li>Social media campaign, built around your home&rsquo;s target markets</li>
            <li>Custom property website</li>
            <li>Google Ads campaign</li>
            <li>Geofencing to reach buyers in targeted locations</li>
          </ul>
        </div>
        <div class="needle-col">
          <h4>Print</h4>
          <ul>
            <li>Brochures</li>
            <li>Fliers</li>
            <li>Cards to renters and neighbors</li>
            <li><a href="{p['prefix']}_Buyer_Report.html"
            style="color:var(--gold-deep); font-weight:600;">Buyer Pricing Report</a></li>
          </ul>
        </div>
      </div>
    </div>

    <div style="display:flex; align-items:center; gap:26px; margin-top:20px; flex-wrap:wrap;">
      <div style="flex:1; min-width:240px;">
        <p class="price-para" style="text-align:left; margin:0;"><b>You approve every piece
        before the listing goes Coming Soon.</b></p>
        <p class="price-para" style="text-align:left; margin:10px 0 0;">Here is a recent
        social media reel from one of our listings &mdash;
        <a href="https://www.instagram.com/reels/DKVNw1OSQJ5/" target="_blank" rel="noopener"
        style="color:var(--gold-deep); font-weight:600;">watch it here</a>.</p>
      </div>
      <a href="https://www.instagram.com/reels/DKVNw1OSQJ5/" target="_blank" rel="noopener"
         style="flex:0 0 auto;">
        <img src="Marketing_Reel.png" alt="Sample social media reel"
             style="width:150px; height:auto; display:block;">
      </a>
    </div>
  </div>
</section>

<section style="padding-top:14px;">
  <div class="wrap">
    <h2 class="section-title">Building Demand Before Active</h2>
    <p class="section-sub">We use the <b>Coming Soon</b> period to create excitement and
    drive buyers to your home&rsquo;s website through four powerful channels.</p>

    <div class="needle-table">
      <div class="needle-cols">
        <div class="needle-col">
          <h4>Targeted Social Media</h4>
          <ul>
            <li>We place your home in front of qualified buyers locally, nationally and
            internationally, based on demographics, interests, location and online
            behavior.</li>
            <li>We employ one of the top social media marketing professionals in the
            industry, whose full-time job is marketing our listings.</li>
          </ul>
          <h4>Targeted Local Marketing</h4>
          <ul>
            <li>We reach renters, corporate housing communities, relocation buyers and
            families searching specifically within your school district and the
            surrounding communities.</li>
          </ul>
        </div>
        <div class="needle-col">
          <h4>MLS &amp; Realtor&reg; Exposure</h4>
          <ul>
            <li>Coming Soon exposure alerts Realtors and buyers with saved searches,
            creating awareness and directing interested buyers to your custom property
            website before the home becomes Active.</li>
          </ul>
          <h4>Neighborhood Outreach</h4>
          <ul>
            <li>Your neighbors can be some of your home&rsquo;s strongest advocates. We
            engage the surrounding community and encourage them to share the property with
            family, friends and colleagues who may want to move into the
            neighborhood.</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2 class="section-title">The Goal: Create Competition</h2>
    <p class="section-sub">The first days of a listing are often the most important.</p>

    <p class="price-para">Our goal is to concentrate maximum exposure into that critical
    window, generating early interest and bringing the largest possible pool of qualified
    buyers to your home at the same time.</p>

    <div class="price-card" style="margin:22px 0;">
      <div class="rec-label" style="font-size:15px; letter-spacing:.06em; line-height:1.9;
           text-align:center !important; display:block;">
        <span style="white-space:nowrap;">More Exposure &nbsp;&rarr;&nbsp; More Buyers</span>
        &nbsp;&rarr;&nbsp;
        <span style="white-space:nowrap;">More Competition &nbsp;&rarr;&nbsp; <b>Premium Value&trade;</b></span>
      </div>
    </div>

    <p class="price-para">That competition creates urgency, strengthens the seller&rsquo;s
    negotiating position, and gives buyers the confidence to act decisively.</p>

    <p class="price-para" style="margin-top:24px; font-family:'Playfair Display',Georgia,serif;
    font-size:17px; font-style:italic;">We don&rsquo;t just put your home on the market.
    We create a market for your home.</p>

    <p class="price-para" style="margin-top:6px; font-weight:700; color:var(--gold-deep);
    letter-spacing:.04em;">Gold Standard Marketing&trade; &nbsp;|&nbsp; Gold Standard Results&trade;</p>
  </div>
</section>

</section>
{footer(p)}
</body>
</html>
"""
    (out / f'{p["prefix"]}_Marketing.html').write_text(head + body)


def build_tracker(p, s, out):
    """Generate a pre-listing shell — UNLESS the property already has a
    populated tracker. A ratified deal's tracker holds contract data that
    exists nowhere else; never overwrite it with an empty shell."""
    src = p.get("tracker_source")
    if src:
        src = Path(src)
        if not src.exists():
            sys.exit(f"tracker_source {src} not found — refusing to write a blank "
                     "shell over a tracker that is supposed to be populated.")
        text = src.read_text()
        for a, b in (p.get("tracker_replace") or {}).items():
            text = text.replace(a, b)
        (out / f'{p["prefix"]}_Seller_Tracker.html').write_text(text)
        note(f"Seller Tracker copied from {src.name} (populated) — shell NOT generated.")
        return

    # No populated tracker: derive a blank shell from the real template so
    # the Pre-Contract / Post-Contract phase structure is preserved.
    import genericize_tracker as gt

    text = (TPL / "tracker.html").read_text()
    text = gt.scrub(text, address_from="502 Spring St SE, Vienna VA 22180",
                    address_to=f'{p["address"]}, {p["city"]} {p["state_abbr"]} {p["zip"]}'.strip())
    text = text.replace("502 Spring St", p["address"])
    text = text.replace("Vienna, Virginia", f'{p["city"]}, {p["state"]}')
    text = text.replace("cst-sample-tracker-v1", p["storage_key"])

    # Shared with the seller, so the banner names both parties.
    text = text.replace(
        '<div class="internal-note">Internal &mdash; Casey Samson Team only '
        '<span>&middot; not for the seller, the buyers, or the buyer&rsquo;s agent</span></div>',
        '<div class="internal-note">For Internal Use by CST and Seller '
        '<span>&middot; not for use by the buyers or the buyer&rsquo;s agent</span></div>')

    # Clocks stop counting down until there is a contract.
    text = re.sub(r'\s*data-date="[^"]*"', "", text)
    text = re.sub(r'(<div class="cbig"[^>]*>).*?(</div>)',
                  r'\1<span class="pending">&mdash;</span>\2', text, flags=re.S)
    text = re.sub(r'(<div class="cw"[^>]*>).*?(</div>)',
                  r"\1Set on ratification\2", text, flags=re.S)

    # Blank every figure in the post-contract tables.
    def blank_post_tables(m):
        return re.sub(r'(<td class="r">).*?(</td>)',
                      r'\1<span class="pending">&mdash;</span>\2', m.group(0), flags=re.S)
    text = re.sub(r'<div class="table-wrap" data-phase="post">.*?</div>\s*</div>',
                  blank_post_tables, text, flags=re.S)

    # Contract terms, occupancy and the post-contract directory cards.
    text = re.sub(r'(<span class="badge )(?:yes|no|w)(">)[^<]*(</span>)',
                  r'\1w\2Pending\3', text)
    text = re.sub(r'(<div class="od"[^>]*>).*?(</div>)',
                  r'\1<span class="pending">&mdash;</span>\2', text, flags=re.S)
    text = re.sub(r'(<div class="dcard" data-phase="post">\s*<div class="role">[^<]*</div>\s*'
                  r'<div class="nm">).*?(</div>)',
                  r'\1<span class="pending">Not yet under contract</span>\2', text, flags=re.S)

    # Contract-terms rows: the template's text is the Spring St deal (its
    # conveyances, its title company, "not built before 1978"). Blank it.
    def blank_term(m):
        body = m.group(2)
        cell = ('<span class="badge w">Pending</span>' if 'class="badge' in body
                else '<span class="pending">&mdash;</span>')
        return m.group(1) + cell + m.group(3)
    text = re.sub(r'(<tr><td class="k">[^<]*</td><td>)(.*?)(</td></tr>)', blank_term, text, flags=re.S)
    # Loan and deposit sub-lines name the Spring St lender and escrow agent.
    text = re.sub(r'(<td class="k">(?:First trust|Earnest money deposit))<span class="sub">[^<]*</span>', r"\1", text)

    # Phase labels.
    text = re.sub(r'(<p class="subtitle" data-phase="post">).*?(</p>)',
                  r"\1No ratified contract on file\2", text, flags=re.S)
    text = re.sub(r'(<span class="asof" data-phase="post">).*?(</span>)',
                  r"\1Awaiting ratification\2", text, flags=re.S)
    text = re.sub(r'(<span class="asof" data-phase="pre">).*?(</span>)',
                  rf'\1Opened {p["report_date"]}\2', text, flags=re.S)

    # Pre-contract net sheet starts from the recommended Coming Soon price.
    text = re.sub(r'(id="nsList"[^>]*value=")[^"]*(")',
                  rf"\g<1>{s.coming_soon:,}\2", text)

    if "pending{" not in text:
        text = text.replace("</style>",
                            "  .pending{color:var(--muted-2); font-style:italic;}\n</style>")

    (out / f'{p["prefix"]}_Seller_Tracker.html').write_text(text)
    note("Seller Tracker: blank shell derived from the phase-tab template; "
         "all post-contract fields empty until ratification.")


# ---------------------------------------------------------------- Nav page ---
MSS_INDEX = "https://cstmarketupdate.netlify.app/index.html"

DEFAULT_AGENT = {
    "lookup": "Casey C Samson",
    "display": "Casey Samson",
    "phone": "703-508-2535",
    "email": "Casey@caseysamson.com",
}

RESOURCE_VIDEOS = ["How We Price Homes", "How We Prepare Homes",
                   "How We Market Homes", "How We Negotiate Contracts"]


def build_index(p, out):
    """The standard Seller Portal nav page: hero, strategy box, document
    cards, Gateway reports, listing site, resources."""
    s = (TPL / "index.html").read_text()
    head = s.split("<body>")[0]
    head = re.sub(r"<title>.*?</title>",
                  f'<title>{p["address"]} — The Casey Samson Team</title>', head, count=1)

    # Compact banner: logo, title and address sit on the hero image itself
    # rather than stacking beneath it, which halves the header height.
    head = head.replace("</style>", """
  .link-card{padding:24px 28px !important; align-items:flex-start !important;}
  .link-card .link-title{font-size:21px !important; line-height:1.3; margin-top:6px;}
  .link-card .link-tag{font-size:11.5px !important; padding:4px 13px !important;}
  .link-body{font-size:14.5px; color:var(--muted); margin:6px 0 0; line-height:1.55;}
  .link-why{font-size:13.5px; font-weight:700; color:var(--gold-deep); margin:10px 0 0;}
  .link-card .link-arrow{margin-top:8px;}
  .link-card.delta .link-tag{background:#E4F0E8 !important; color:#3E7A55 !important;}
  .link-card.delta{border-left-color:#3E7A55 !important;}
  .link-card.lux .link-tag{background:#F3EAD3 !important; color:#8A6A2E !important;}
  .link-card.lux{border-left-color:#8A6A2E !important;}
  .rest-of-market{text-align:center; margin:-4px 0 18px;}
  .rest-of-market a{font-size:13px; font-weight:700; letter-spacing:.02em;
    color:var(--gold-deep, #8A6A2E); text-decoration:none;}
  .rest-of-market a:hover{text-decoration:underline;}
  .hero{height:auto !important; min-height:230px;}
  .hero > img{position:relative !important; display:block; width:100% !important;
    height:auto !important; min-height:230px; max-height:560px; object-fit:cover; object-position:center;}
  .hero-overlay{
    position:absolute; inset:0; z-index:2;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    text-align:center; padding:14px 20px;
    background:linear-gradient(to bottom, rgba(24,20,14,.34), rgba(24,20,14,.14) 50%, rgba(24,20,14,.42));
  }
  .hero-overlay img{width:62px; margin:0 0 6px; filter:drop-shadow(0 2px 8px rgba(0,0,0,.85));}
  .hero-overlay .brandline{color:#FFF8E8; margin:0 0 2px; font-size:10px; letter-spacing:.2em;
    text-shadow:0 1px 8px rgba(0,0,0,.9);}
  .hero-overlay .portal-label{
    font-family:'Playfair Display',Georgia,serif; font-style:italic; font-weight:600;
    font-size:24px; color:#FFF8E8; margin:0 0 4px; line-height:1;
    text-shadow:0 2px 12px rgba(0,0,0,.85), 0 1px 3px rgba(0,0,0,.7);
  }
  .hero-overlay h1.addr{
    font-family:'Playfair Display',Georgia,serif; font-size:clamp(20px,3vw,27px);
    font-weight:700; color:#FFFDF7; margin:0; line-height:1.15;
    text-shadow:0 2px 12px rgba(0,0,0,.85), 0 1px 3px rgba(0,0,0,.7);
  }
  .hero-overlay p.city{
    color:#EDE6D3; font-size:13px; font-style:italic; margin:2px 0 0;
    text-shadow:0 2px 12px rgba(0,0,0,.85), 0 1px 3px rgba(0,0,0,.7);
  }
  @media (max-width:560px){ .hero{min-height:220px;} .hero > img{min-height:220px;} .hero-overlay img{width:50px;} }
</style>""")

    pre = p["prefix"]
    hero_img = p.get("hero_photo")
    if hero_img:
        hero = (f'  <img src="{hero_img}" alt="{p["address"]}" '
                'style="width:100%; height:100%; object-fit:cover;">')
    else:
        hero = ""
        note("Nav page: hero photo OMITTED — none supplied; gradient placeholder shown.")

    def card(cls, tag, title, desc, href, blank=True, body=None, why=None):
        """Title and tagline on one line in the title font, then an optional
        description and a gold "Why it matters" line."""
        t = ' target="_blank" rel="noopener"' if blank else ""
        line = f"{title} &mdash; {desc}" if desc else title
        extra = ""
        if body:
            extra += f'\n      <p class="link-body">{body}</p>'
        if why:
            extra += f'\n      <p class="link-why">Why it matters: {why}</p>'
        return f"""  <a class="link-card {cls}" href="{href}"{t}>
    <div>
      <span class="link-tag">{tag}</span>
      <div class="link-title">{line}</div>{extra}
    </div>
    <span class="link-arrow">&rarr;</span>
  </a>
"""

    def printlink(href, label):
        return (f'  <a class="print-link" href="{href}" target="_blank" rel="noopener">\n'
                '    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2" style="display:inline-block;"><path d="M6 9V2h12v7"/>'
                '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
                f'<path d="M6 14h12v8H6z"/></svg>{label}\n  </a>\n')

    body = []

    body.append(card("rm", "Seller Roadmap", "Current Seller Roadmap",
                     "The strategy for a first-week sale",
                     f"{pre}_Roadmap.html", blank=False,
                     body="See the pricing, preparation, launch and negotiation plan designed "
                          "to create traffic and competition.",
                     why="Sellers know what happens next and why."))
    # Casey, 11 Oct 2026: "The pricing strategy takes the place of roadmap
    # PDF." The nine-page Roadmap was never a thing anyone printed; the one
    # page is. The Roadmap PDF is still built and still in the folder.
    body.append(printlink(f"{pre}_Pricing_Strategy_Summary.pdf",
                          f"{summary_name(p)} (PDF)"))

    # Once the property has a Buyer Portal it replaces the Buyer Pricing Guide
    # here: the portal carries the same authenticated values plus the photos,
    # video, documents and offer instructions. Until then the Guide stands in.
    # Casey, 10 Oct 2026: the home's own Buyer Portal goes ABOVE the example,
    # and the example is shown either way — it is what the seller is being
    # sold on, not just a stand-in for a missing portal.
    bp_url = buyer_portal_url(p)
    if bp_url:
        body.append(card("br", "Buyer Portal", "Buyer Portal",
                         "The total picture of your home&rsquo;s offering",
                         bp_url,
                         body="Everything a buyer and their agent see &mdash; photography, "
                              "video, authenticated values, disclosures, conveyances and "
                              "the instructions for writing an offer.",
                         why="One place buyers trust means fewer questions and stronger offers."))
        body.append(printlink(f"{pre}_Buyer_Report.pdf", "Printable Buyer Pricing (PDF)"))

    # Casey, 20 Oct 2026: "as soon as a buyer portal is updated with pictures
    # and premiums, remove Example Buyer Portal." It stood beside the real
    # one until today, on the 10 Oct reasoning that the example is what the
    # seller is being sold on. Once the home has its own photographs and
    # premiums that argument is over -- the seller has the real thing, and
    # the example only offers them a click onto somebody else's house.
    _ready = buyer_portal_ready(p)
    if _ready:
        note("Nav page: Example Buyer Portal card REMOVED — this home's own "
             "buyer portal carries its pictures and premiums now.")
    if not is_example_home(p) and not _ready:
        body.append(card("br", "Buyer Portal", "Buyer Portal &mdash; Example",
                     f"What we build for your home &mdash; shown on {EXAMPLE_BUYER_HOME}",
                     EXAMPLE_BUYER_PORTAL,
                     body=f"This is {EXAMPLE_BUYER_HOME}&rsquo;s portal, not yours. It "
                          "shows what a buyer and their agent will see: photography, "
                          "video, authenticated values, disclosures, conveyances and the "
                          "instructions for writing an offer."
                          + ("" if bp_url else " Yours is built once we have the "
                             "photographs and documents for your home."),
                     why="One place buyers trust means fewer questions and stronger offers."))

    # The Local Market Snapshot, fourth, where this property has a pull.
    _mss = local_snapshot_file(p, out)
    if _mss:
        _live = _mss.startswith("http")
        _mname = (p.get("market") or {}).get("name") or "your market"
        body.append(card("mss", "Market Snapshot",
                         _mname if _live else "Local Market Snapshot&trade;",
                         (f"Current conditions in the {_mname}" if _live else
                          "Homes like yours &mdash; by size, age and price range"),
                         _mss,
                         body=("What share of the homes here are under contract, "
                               "how long they have been listed, and which way the "
                               "market is moving." if _live else
                               "What came on the market around you, what went under "
                               "contract, and the price each one launched at."),
                         why="The price you launch at is the price that works."))
    body.append('  <p class="rest-of-market">'
                '<a href="https://cstmarketupdate.netlify.app/#" target="_blank" '
                'rel="noopener">Rest of the Market &rarr;</a></p>')

    # Casey, 15 Oct 2026: the track-record card comes off every seller
    # portal -- the production band at the top and the back of the Pricing
    # Strategy Summary already carry that record. Kept in step with
    # build_index_v2, which drops the same card from the main index.

    body.append(card("mss", "Marketing", "Marketing Your Home",
                     "How we create competition",
                     f"{pre}_Marketing.html", blank=False,
                     body="Professional photography, video and a custom property website, "
                          "then four channels of Coming Soon exposure to reach the largest "
                          "qualified buyer pool.",
                     why="Maximum exposure in the days that matter most."))
    body.append(NEWLINE)

    if p.get("include_tracker", True):
        body.append(card("delta", "Transaction Tracker", "Seller Tracker",
                         "Total visibility from contract to close",
                         f"{pre}_Seller_Tracker.html",
                         body="Every key date, dollar figure, milestone and contact in one "
                              "private place for you and the seller.",
                         why="No guessing, no chasing updates."))


    # The Luxury Experience / Track Record card moved up under the Buyer
    # Portal example. assign_agent.py locates it by its tag text and rewrites
    # the href, which still works from its new position.

    # Links to the property's own market/submarket page, not the MSS index.
    if p["market"].get("slug"):
        _mkt = p["market"].get("name", "Market")
        body.append(card("mss", "Market Snapshot",
                         "Market Snapshot" if not _mss
                         else _mkt if _mkt.endswith("Snapshot") else f"{_mkt} Snapshot",
                         "Know what buyers are doing right now",
                         f'https://cstmarketupdate.netlify.app/{p["market"]["slug"]}.html',
                         body="Current inventory, contracts, absorption and market control "
                              "for the homes you are competing against.",
                         why="Pricing strategy should change when the market changes."))

    listing = listing_page_url(p)
    if listing:
        body.append(card("site", "Listing Website", "View Full Listing",
                         "Photos, details, and more on our site", listing))
    else:
        note("Nav page: Listing Website card OMITTED — no listing_page_url supplied.")

    videos = "\n".join(
        '      <a class="res-item disabled" href="#" onclick="return false;">\n'
        '        <div class="res-row">\n          <span class="res-icon">&#9654;</span>\n'
        f'          <div>\n            <div class="res-title">{v}</div>\n'
        '            <div class="res-note">Video coming soon</div>\n          </div>\n'
        '        </div>\n        <span class="res-arrow">&rarr;</span>\n      </a>'
        for v in RESOURCE_VIDEOS)

    a = p["agent"]
    name = a.get("display") or a["lookup"]
    contact = [name]
    if a.get("phone"):
        contact.append(f'<span class="sep">|</span>{a["phone"]}')
    if a.get("email"):
        contact.append(f'<span class="sep">|</span><a href="mailto:{a["email"]}">{a["email"]}</a>')

    page = f"""<body>

<div class="hero">
{hero}
  <div class="hero-overlay">
    <img src="Gold_Standard_Logo.png" alt="Gold Standard Listing">
    <div class="brandline">The Casey Samson Team</div>
    <p class="portal-label">Seller Portal</p>
    <h1 class="addr">{p["address"]}</h1>
    <p class="city">{p["city"]}, {p["state"]}</p>
  </div>
</div>

<div class="wrap">

  <div class="team-strategy">
    <h3>Casey Samson Team</h3>
    <p class="tagline">Seller Strategy</p>
    <div class="points">
      <span>Build Confidence in Value and Condition</span>
      <span>Create Competition</span>
      <span>Inspire Highest and Best Offers</span>
    </div>
  </div>

{"".join(body)}
  <div class="resources">
    <div class="resources-label">Resources</div>

    <a class="res-item full" href="https://weekly-update.my.canva.site/listing-protocol" target="_blank" rel="noopener">
      <div class="res-row">
        <span class="res-icon">&#9776;</span>
        <div>
          <div class="res-title">Listing Protocol</div>
          <div class="res-note">What to expect, step by step</div>
        </div>
      </div>
      <span class="res-arrow">&rarr;</span>
    </a>

    <div class="res-grid">
{videos}
    </div>
  </div>

  <footer>
    <div class="produced">Produced by The Casey Samson Team</div>
    <div class="contact-line">{"".join(contact)}</div>
    <div class="copy">&copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </footer>
</div>

</body>
</html>
"""
    (out / "index.html").write_text(head + page)




def build_index_dynamic(p, s, out):
    """Variant nav page in the CST Seller Portals marketing style: navy hero
    with the property, then a card grid. Written as index_dynamic.html so it
    can be compared with the current index.html before either is adopted."""
    pre, hero = p["prefix"], p.get("hero_photo")
    a = p["agent"]; name = a.get("display") or a["lookup"]
    listing = listing_page_url(p)
    m = dict(p["market"])
    cache_file = HERE / "market_cache.json"
    if cache_file.exists() and m.get("slug"):
        cached = json.loads(cache_file.read_text()).get(m["slug"], {})
        m.setdefault("keystats", cached.get("keystats"))
    market_url = (f'https://cstmarketupdate.netlify.app/{m["slug"]}.html'
                  if m.get("slug") else None)
    agent_page = re.sub(r"[^a-z0-9]+", "-", a["lookup"].lower()).strip("-") + ".html"

    cards = [
        ("roadmap", "Current Seller Roadmap", "The roadmap is about Strategy not Price",
         "Build confidence, create competition by driving traffic and validate Highest "
         "and Best Value for a first week sale.", f"{pre}_Roadmap.html"),
    ]
    if buyer_portal_url(p):
        cards.append(
            ("buyer", "Buyer Pricing Guide", "Authentication of values and upgrades",
             "The document buyers see. It authenticates your home&rsquo;s value against "
             "the comparable sales and the upgrades that justify a premium.",
             f"{pre}_Buyer_Report.html"))
    # This home's own Buyer Portal when it exists; otherwise one built for
    # another listing, named as such, so the seller sees what is coming.
    _bp = buyer_portal_url(p)
    # Same 20 Oct rule as the main nav page: a portal with its own pictures
    # and premiums does not stand beside somebody else's.
    if _bp or (not is_example_home(p) and not buyer_portal_ready(p)):
        cards.insert(2, ("buyer", "Buyer Portal", "The total picture of your offering",
                     "Everything a buyer and their agent see &mdash; photography, video, "
                     "authenticated values, disclosures, conveyances and the instructions "
                     "for writing an offer.", _bp)
                 if _bp else
                 ("buyer", "Buyer Portal &mdash; Example",
                  f"Built for {EXAMPLE_BUYER_HOME}, not your home",
                  "An example of the portal we prepare: photography, video, authenticated "
                  "values, disclosures and the instructions for writing an offer. Yours "
                  "follows once we have the photographs and documents for your property.",
                  EXAMPLE_BUYER_PORTAL))
    if p.get("include_tracker", True):
        cards.append(("tracker", "Seller Tracker", "Total Visibility from Contract to Close",
                      "Every date, dollar figure and contact for your sale in one place, "
                      "from preparation through settlement.", f"{pre}_Seller_Tracker.html"))
    # Fourth, where this property has a pull of its own.
    _mss = local_snapshot_file(p, out)
    if _mss:
        _live = _mss.startswith("http")
        _mname = (p.get("market") or {}).get("name") or "your market"
        cards.insert(3, ("market",
                         _mname if _live else "Local Market Snapshot&trade;",
                         (f"Current conditions in the {_mname}" if _live else
                          "Homes like yours, by size, age and price range"),
                         ("What share of the homes here are under contract, how "
                          "long they have been listed, and which way the market "
                          "is moving." if _live else
                          "What came on the market around you, what went under "
                          "contract, and the price each one launched at."), _mss))
    # The track-record card is off the seller portal from 15 Oct 2026; see
    # build_index_v2 for why.
    if listing:
        cards.append(("listing", "View Full Listing", "Photos, details and more",
                      "The property page on our site, with the full gallery and details.",
                      listing))
    if market_url:
        cards.append(("market",
                      "Market Snapshot" if not _mss
                      else m["name"] if m["name"].endswith("Snapshot")
                      else f'{m["name"]} Snapshot',
                      "Tracking current market conditions",
                      m.get("keystats") or f'Live conditions in the {m["name"]}.', market_url))
    cards.append(("resources", "Resources", "Tools and guidance at every stage",
                  "The Listing Protocol walks through each stage of the sale.",
                  "https://weekly-update.my.canva.site/listing-protocol"))

    ICONS = {'tracker': '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12l2 2 4-4"/>', 'roadmap': '<path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z"/><path d="M9 3v15M15 6v15"/>', 'buyer': '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>', 'agent': '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2A5 5 0 0 1 21 19"/>', 'listing': '<rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 6l1.5-2h5L16 6"/>', 'resources': '<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5.9 1.2.9 1.9V16h5.4v-.3c0-.7.3-1.4.9-1.9A6 6 0 0 0 12 3z"/>'}
    ICONS["market"] = ICONS["roadmap"]

    tiles = ""
    for key, title, tag, body, href in cards:
        ext = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
        pdf = ""
        if key in ("roadmap", "buyer"):
            stem = f"{pre}_Roadmap" if key == "roadmap" else f"{pre}_Buyer_Report"
            pdf = f'<span class="tile-pdf" data-href="{stem}.pdf">PDF</span>'
        tiles += f'''      <a class="tile" href="{href}"{ext}>
        <div class="tile-top">
          <span class="tile-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{ICONS[key]}</svg></span>
        </div>
        <div class="tile-body">
          <h3>{title}</h3>
          <p class="tile-tag">{tag}</p>
          <p class="tile-note">{body}</p>
          {pdf}
        </div>
      </a>
'''

    contact = " &nbsp;|&nbsp; ".join(x for x in [
        name, a.get("phone"),
        f'<a href="mailto:{a.get("email","")}">{a.get("email","")}</a>' if a.get("email") else ""] if x)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{p["address"]} — Seller Portal — The Casey Samson Team</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,900;1,600&family=Lora:ital,wght@0,400;0,500;0,600&display=swap');
  :root{{--navy:#122135; --navy-2:#1B3049; --bg:#FAF7F0; --card:#FFFFFF;
    --ink:#1C1A16; --muted:#6F6857; --gold:#C9A253; --gold-deep:#8A6A2E; --rule:#E4DCC8;}}
  *{{box-sizing:border-box;}}
  body{{margin:0; background:var(--bg); color:var(--ink); font-family:'Lora',Georgia,serif; line-height:1.6;}}
  .wrap{{max-width:1100px; margin:0 auto; padding:0 28px;}}

  .hero{{position:relative; background:var(--navy); overflow:hidden;}}
  .hero-photo{{position:absolute; inset:0 0 0 46%; }}
  .hero-photo img{{width:100%; height:100%; object-fit:cover;}}
  .hero-photo::after{{content:""; position:absolute; inset:0;
    background:linear-gradient(to right, var(--navy) 6%, rgba(18,33,53,.55) 46%, rgba(18,33,53,.15));}}
  .hero-inner{{position:relative; z-index:2; display:flex; align-items:stretch;
    max-width:1100px; margin:0 auto; padding:34px 28px 30px; gap:28px;}}
  .hero-main{{flex:1; min-width:0;}}
  .hero-eyebrow{{display:flex; align-items:center; gap:14px; color:#EFE6D0;
    font-size:12px; letter-spacing:.22em; text-transform:uppercase; margin-bottom:14px;}}
  .hero-eyebrow .ln{{height:1px; width:78px; background:var(--gold); opacity:.8;}}
  .hero h1{{font-family:'Playfair Display',serif; font-weight:900; margin:0; color:#fff;
    font-size:clamp(30px,4.6vw,52px); line-height:1.02; letter-spacing:-.01em;}}
  .hero h1 .place{{display:block; color:var(--gold); font-weight:700; font-size:.62em; margin-top:6px;}}
  .hero-rule{{width:64px; height:3px; background:var(--gold); margin:20px 0 16px;}}
  .hero p.lede{{color:#E7DFCD; font-size:15.5px; max-width:44ch; margin:0;}}
  .hero-panel{{width:250px; flex:0 0 250px; align-self:center;
    background:rgba(9,18,30,.62); border-left:2px solid var(--gold); padding:20px 22px;}}
  .hero-panel .price-label{{color:#CFC6B2; font-size:12px; letter-spacing:.14em;
    text-transform:uppercase; margin:0 0 4px;}}
  .hero-panel .price{{font-family:'Playfair Display',serif; font-size:31px; font-weight:700;
    color:var(--gold); margin:0; line-height:1.1;}}
  .hero-panel .range{{color:#E7DFCD; font-size:13px; margin:6px 0 0;}}
  .hero-panel .motto{{font-family:'Playfair Display',serif; font-style:italic; color:#fff;
    font-size:16px; line-height:1.35; margin:16px 0 0; border-top:1px solid rgba(201,162,83,.4); padding-top:14px;}}

  .section-head{{text-align:center; padding:38px 0 6px;}}
  .section-head h2{{font-family:'Playfair Display',serif; font-size:23px; font-weight:700;
    margin:0; letter-spacing:.02em;}}
  .section-head p{{color:var(--muted); font-size:14.5px; margin:6px 0 0;}}

  .grid{{display:grid; grid-template-columns:repeat(3,1fr); gap:20px; padding:24px 0 40px;}}
  .tile{{display:flex; flex-direction:column; background:var(--card);
    border:1px solid var(--rule); border-radius:10px; overflow:hidden;
    text-decoration:none; color:inherit; position:relative;}}
  .tile:hover{{border-color:var(--gold); box-shadow:0 6px 18px rgba(18,33,53,.10);}}
  .tile-top{{height:74px; background:linear-gradient(135deg,var(--navy),var(--navy-2)); position:relative;}}
  .tile-icon{{position:absolute; left:20px; bottom:-22px; width:46px; height:46px;
    border-radius:50%; background:var(--gold); color:var(--navy);
    display:flex; align-items:center; justify-content:center; border:3px solid var(--card);}}
  .tile-icon svg{{width:22px; height:22px;}}
  .tile-body{{padding:32px 20px 20px; flex:1;}}
  .tile-body h3{{font-family:'Playfair Display',serif; font-size:17.5px; font-weight:700;
    margin:0; color:var(--navy);}}
  .tile-tag{{font-size:13.5px; font-weight:600; color:var(--gold-deep); margin:3px 0 8px;}}
  .tile-note{{font-size:13.5px; color:var(--muted); margin:0;}}
  .tile-pdf{{display:inline-block; margin-top:12px; font-size:11.5px; font-weight:600;
    color:var(--gold-deep); border:1px solid var(--gold); border-radius:14px; padding:3px 11px;}}

  footer{{background:var(--navy); color:#E7DFCD; text-align:center; padding:26px 0 32px; font-size:14px;}}
  footer a{{color:#E7DFCD;}}
  footer .team{{font-family:'Playfair Display',serif; color:#fff; font-size:17px; margin-bottom:5px;}}
  footer .copy{{font-size:11.5px; color:#A79E8B; margin-top:12px;}}
  a:focus-visible{{outline:2px solid var(--gold); outline-offset:3px;}}

  @media (max-width:900px){{ .grid{{grid-template-columns:repeat(2,1fr);}} }}
  @media (max-width:720px){{
    .hero-photo{{inset:0;}} .hero-inner{{flex-direction:column;}}
    .hero-panel{{width:auto; flex:none;}} .grid{{grid-template-columns:1fr;}}
  }}
</style></head>
<body>

<header class="hero">
  {f'<div class="hero-photo"><img src="{hero}" alt="{p["address"]}"></div>' if hero else ""}
  <div class="hero-inner">
    <div class="hero-main">
      <div class="hero-eyebrow"><span>The Casey Samson Team</span><span class="ln"></span></div>
      <h1>{p["address"]}<span class="place">{p["city"]}, {p["state"]}</span></h1>
      <div class="hero-rule"></div>
      <p class="lede">Your Seller Portal &mdash; strategy, evidence and everything
      buyers will see, all in one place.</p>
    </div>
    <aside class="hero-panel">
      <p class="price-label">Recommended Coming Soon</p>
      <p class="price">{money(s.coming_soon)}</p>
      <p class="range">Expected sale {abbrev(s.expected_low)}&ndash;{abbrev(s.expected_high)}</p>
      <p class="motto">When Buyers Compete,<br>Sellers Win.&trade;</p>
    </aside>
  </div>
</header>

<div class="wrap">
  <div class="section-head">
    <h2>What is in the portal</h2>
    <p>Comprehensive. Customized. Designed for results.</p>
  </div>
  <div class="grid">
{tiles}  </div>
</div>

<footer>
  <div class="wrap">
    <div class="team">The Casey Samson Team</div>
    <div>{contact}</div>
    <div class="copy">&copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </div>
</footer>

<script>
  document.querySelectorAll('.tile-pdf').forEach(function (el) {{
    el.addEventListener('click', function (e) {{
      e.preventDefault(); e.stopPropagation();
      window.open(el.dataset.href, '_blank', 'noopener');
    }});
  }});
</script>
</body></html>
"""
    (out / "index_dynamic.html").write_text(html)



# ------------------------------------------------------------ Seller email ---
SAMPLE_BR = "https://samplesellerportal.netlify.app/Sample_Buyer_Report"
SAMPLE_PORTAL = "https://502macarthur.netlify.app"
SAMPLE_ROADMAP = "https://502macarthur.netlify.app/502_macarthur_roadmap"
SAMPLE_BUYER = EXAMPLE_BUYER_PORTAL
SAMPLE_LISTING = "https://caseysamson.com/listing/502-spring-st-se-vienna-virginia/"
LISTING_PROTOCOL = "https://weekly-update.my.canva.site/listing-protocol"

ANECDOTE = ("Last week a buyer offered $2.15 and when we sent them the "
            '<a href="{br}">Buyer Report</a> they upped their offer $100k and '
            "removed all contingencies.")


def _write_eml(out, stem, html, subject, p, to=""):
    """Write an .eml that opens straight as a draft, with a plain-text
    alternative so HTML-blocked clients still read cleanly."""
    import re as _re
    from email.message import EmailMessage

    import html as _html

    body_only = html.split("<body", 1)[-1].split(">", 1)[-1]
    plain = _re.sub(r'<a href="([^"]+)">(.*?)</a>', r"\2 (\1)", body_only, flags=_re.S)
    # Keep the line structure: <br> and </p> are real breaks in the text.
    plain = _re.sub(r"<li[^>]*>\s*", "\n\u2022 ", plain, flags=_re.I)
    plain = _re.sub(r"<br\s*/?>", "\n", plain, flags=_re.I)
    # Tables (the track record) read as one row per line, cells split by "|".
    plain = _re.sub(r"</t[dh]>\s*(?=<t[dh])", " | ", plain, flags=_re.I)
    plain = _re.sub(r"</tr>", "\n", plain, flags=_re.I)
    plain = _re.sub(r"</p>", "\n\n", plain, flags=_re.I)
    plain = _re.sub(r"<[^>]+>", "", plain)
    plain = _html.unescape(plain)
    plain = "\n".join(l.strip() for l in plain.splitlines())
    plain = _re.sub(r"\n{3,}", "\n\n", plain).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (f'{p["agent"].get("display") or p["agent"]["lookup"]} '
                   f'<{p["agent"].get("email", "")}>')
    msg["To"] = to or ""
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    (out / f"{stem}.eml").write_bytes(bytes(msg))


def market_summary(p, market_url):
    """Headline, sub-headline and key stats for the market, as they appear on
    the live report. Supplied per property — never invented here, because the
    MSS site is regenerated weekly and stale figures are worse than none."""
    m = dict(p["market"])

    # Fall back to the cache written by fetch_market.py, so the emails carry
    # whatever the live report said at the last MSS pull.
    cache_file = HERE / "market_cache.json"
    if cache_file.exists() and not any(
            m.get(k) for k in ("headline", "subheadline", "keystats")):
        cached = json.loads(cache_file.read_text()).get(m.get("slug"))
        if cached:
            for k in ("headline", "subheadline", "keystats"):
                if cached.get(k):
                    m[k] = cached[k]
            note(f'Market summary for {m["name"]} taken from market_cache.json '
                 f'({cached.get("week_of", "week unknown")}) — rerun '
                 "fetch_market.py after each Thursday MSS update.")

    # Just the three facts: which way contracts are moving, how much of the
    # market is under contract, and who that leaves in control. The headline
    # and sub-headline are cached but not printed — they restate the same
    # numbers, and the link carries anyone who wants the full picture.
    if not m.get("keystats"):
        note(f'Emails: no key stats for the {m["name"]} — Market Snapshot shows '
             "the link only. Run fetch_market.py against your MSS build.")
        return f'Current conditions in the {m["name"]}.'

    return m["keystats"]


def market_control_paragraph(p):
    """One paragraph tying the pricing posture to who controls the market:
    conservative in a buyer's market, aggressive in a seller's market.
    Read from the MSS cache, so it changes as the weekly report changes."""
    m = p.get("market") or {}
    if not m.get("slug"):
        return ""
    cache_file = HERE / "market_cache.json"
    stats = {}
    if cache_file.exists():
        stats = (json.loads(cache_file.read_text()).get(m["slug"], {}) or {}).get("stats") or {}
    control = (stats.get("control") or "").lower()
    uc = stats.get("under_contract")
    name = m["name"]
    uc_line = f" &mdash; {uc} of homes are under contract" if uc else ""
    if "buyer" in control:
        body = (f"<b>The {name} is in the control of buyers</b>{uc_line}. In a buyer&rsquo;s "
                "market, pricing needs to be more conservative: buyers have choices and time, "
                "so the entry price has to earn the showings.")
    elif "seller" in control:
        body = (f"<b>The {name} is in the control of sellers</b>{uc_line}. In a seller&rsquo;s "
                "market, pricing can be more aggressive: buyers are competing for limited "
                "inventory.")
    elif "neutral" in control:
        body = (f"<b>The {name} is neutral</b>{uc_line}, so neither side has control. Pricing "
                "should sit right at the value the comparable sales support.")
    else:
        note(f"Emails: no market-control reading cached for {name} — paragraph omitted.")
        return ""
    return f"<p>{body}</p>\n\n"


LORA = "/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf"
LORA_IT = "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf"


def make_banner(p, out):
    """Render the email cover as a flat 2000px image so no mail client can
    reflow or misalign it. Returns (filename, width, height) or None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        note(f"Seller email: banner image skipped ({exc}).")
        return None

    W, H = 2000, 440
    CREAM, GOLD, INK, MUTED = "#F1EBDA", "#C9A253", "#221C14", "#6E6552"
    GOLD_DEEP = "#8A6A2E"

    def font(path, size, weight=None):
        f = ImageFont.truetype(path, size)
        if weight:
            try:
                f.set_variation_by_name(weight)
            except Exception:
                pass
        return f

    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 7], fill=GOLD)

    def centre(text, f, y, fill, tracking=0):
        if tracking:
            widths = [d.textlength(c, font=f) + tracking for c in text]
            x = (W - (sum(widths) - tracking)) / 2
            for c, adv in zip(text, widths):
                d.text((x, y), c, font=f, fill=fill)
                x += adv
        else:
            d.text((W / 2, y), text, font=f, fill=fill, anchor="ma")

    centre("THE CASEY SAMSON TEAM", font(LORA, 30, "Medium"), 52, GOLD_DEEP, tracking=9)
    centre("Seller Portal", font(LORA_IT, 74, "SemiBold"), 104, INK)
    centre(p["address"], font(LORA, 82, "Bold"), 208, INK)
    centre(f'{p["city"]}, {p["state"]}', font(LORA_IT, 36), 318, MUTED)
    centre("Advanced AI with Proven Real Estate Strategy", font(LORA, 34), 376, MUTED)

    name = f'{p["prefix"]}_Banner.png'
    img.save(out / name)
    return name, W, H


def build_email(p, s, out):
    """A copy-and-paste email to send alongside the portal.

    Links are built from the portal's own URL, so they match the files that
    were actually generated. Netlify paths are case-sensitive.
    """
    base = p.get("portal_url")
    if not base:
        note("Seller email: portal_url not set — document links left as "
             "relative paths and will need fixing by hand.")
        base = ""
    base = base.rstrip("/")
    pre = p["prefix"]
    # Explicit .html: extensionless paths only resolve when Netlify's Pretty
    # URLs is enabled on the site, and a dead link in a client email is not
    # worth the tidier URL.
    rm = f"{base}/{pre}_Roadmap.html" if base else f"{pre}_Roadmap.html"
    br = f"{base}/{pre}_Buyer_Report.html" if base else f"{pre}_Buyer_Report.html"
    tracker = f"{base}/{pre}_Seller_Tracker.html" if base else f"{pre}_Seller_Tracker.html"
    marketing = f"{base}/{pre}_Marketing.html" if base else f"{pre}_Marketing.html"
    # agent_page may already carry the .html extension — don't add a second one.
    agent_slug = p.get("agent_page") or (
        re.sub(r"[^a-z0-9]+", "-", p["agent"]["lookup"].lower()).strip("-"))
    agent_file = agent_slug if agent_slug.endswith(".html") else f"{agent_slug}.html"
    agent_page = f"{base}/{agent_file}" if base else agent_file
    market = (f'https://cstmarketupdate.netlify.app/{p["market"]["slug"]}.html'
              if p["market"].get("slug") else None)
    buyer_portal = buyer_portal_url(p)
    _trf = track_record_file(p)
    _trl = f"{base}/{_trf}" if base else _trf
    luxury = _trl if show_luxury(p) else None
    portfolio = None if show_luxury(p) else _trl
    listing = listing_page_url(p) or SAMPLE_LISTING
    names = p.get("seller_names")
    if not names:
        names = "[Seller Name]"
        note("Seller email: seller_names not set — greeting left as a placeholder.")

    sample_portal = p.get("sample_portal_url", SAMPLE_PORTAL)
    control_para = market_control_paragraph(p)

    st = {}
    _cache = HERE / "market_cache.json"
    if _cache.exists() and p["market"].get("slug"):
        st = (json.loads(_cache.read_text()).get(p["market"]["slug"], {}) or {}).get("stats") or {}
    _bits = []
    if st.get("under_contract"):
        _bits.append(f'{st["under_contract"]} homes under contract')
    if st.get("success_rate"):
        _bits.append(f'{st["success_rate"]} of homes sold vs withdrew')
    if st.get("uc_14"):
        _bits.append(f'{st["uc_14"]} 14 Day absorption Rate')
    market_figures = (f'<p>Current {p["market"]["name"].replace(" Market", "")}: '
                      + " / ".join(_bits) + "</p>\n\n") if _bits else ""

    # Approximate figures for the valuation sentence: size to the nearest 100
    # SF above grade, assessment to the nearest $50,000, so the sentence reads
    # as "similar to" rather than implying an exact match.
    sf_ag = f'{round(p["subject"]["sf"] / 100) * 100:,}'
    assessed = f'${round(p["subject"]["assessment"] / 50_000) * 50_000 / 1_000_000:.2f}M'

    rows = [
        ("Gold Standard Roadmap&trade;", rm,
         "Pricing &amp; Strategy",
         "More than a price &mdash; it&rsquo;s a strategy. The Roadmap combines Gold "
         "Standard Pricing with CST proven strategies to give every listing a roadmap "
         "to success."),
        ("Enhanced Property Visualization", None,
         "See the possibilities before making the investment",
         "AI visualization demonstrates how paint, improvements, furnishings and "
         "renovations can enhance buyer appeal and value."),
        (("Buyer Portal", buyer_portal, None,
          "The total picture of your home&rsquo;s offering &mdash; photography, video, "
          "authenticated values, disclosures and the instructions for writing an offer. "
          "Everything a buyer needs to understand the home, recognize its advantages and "
          "pay Premium Value&trade;.")
         if buyer_portal else
         # No portal yet: show one built for another home, said plainly, so the
         # seller sees what is coming without mistaking it for their own.
         ("Buyer Portal &mdash; Example", EXAMPLE_BUYER_PORTAL, None,
          f"An example built for {EXAMPLE_BUYER_HOME}, not your home. It shows the total "
          "picture we prepare &mdash; photography, video, authenticated values, disclosures "
          "and the instructions for writing an offer. Yours follows once we have the "
          "photographs and documents for your property.")),
        ("AI Buyer Targeting", marketing, None,
         "Identify and reach buyers searching for similar homes by size, age and price "
         "&mdash; including buyers looking in more expensive competing markets."),
        ("Seller Tracker", tracker, None,
         "Total visibility from preparation to settlement. Follow important tasks, "
         "deadlines, marketing activity and milestones throughout the entire process."),
        (("Luxury Experience", luxury, None,
          "Every Casey Samson Team sale at $1.5 million and above &mdash; days on market, "
          "original list price and final sale price, straight from MLS Bright.")
         if luxury else
         ("Portfolio Under $1.5M", portfolio, None,
          "Every Casey Samson Team sale under $1.5 million &mdash; days on market, "
          "original list price and final sale price, straight from MLS Bright.")),
        ("Weekly Market Updates", market, None,
         "A clear snapshot of new listings, contracts, sales, competition and pricing "
         "trends keeps sellers informed as the market changes."),
    ]

    rows = [r for r in rows if not (r[0] == "Weekly Market Updates" and not market)]
    items = []
    for title, href, tag, desc in rows:
        head_txt = f'<a href="{href}">{title}</a>' if href else f"<b>{title}</b>"
        if href:
            head_txt = f"<b>{head_txt}</b>"
        if tag:
            head_txt += f" &mdash; {tag}"
        items.append(
            f'  <p style="margin:0 0 14px 0;">{head_txt}<br>'
            f'{desc}</p>')

    portal_link = f'<a href="{base}/">Seller Portal</a>' if base else "Seller Portal"
    banner = make_banner(p, out)
    if banner and base:
        bn, bw, bh = banner
        cover_block = (
            f'<p style="margin:0 0 22px;"><a href="{base}/"><img src="{base}/{bn}" '
            f'alt="The Casey Samson Team Seller Portal — {p["address"]}" '
            f'width="{bw}" height="{bh}" style="display:block; width:100%; '
            'max-width:100%; height:auto; border:0;"></a></p>\n')
    else:
        cover_block = (
            "<p><b>The Casey Samson Team</b><br>\n"
            f"<b>{portal_link}</b><br>\n"
            "Advanced AI with Proven Real Estate Strategy</p>\n")

    # ---- agent-facing variant -------------------------------------------
    agent_rows = rows
    a_items = []
    for title, href, tag, desc in agent_rows:
        h = f'<b><a href="{href}">{title}</a></b>' if href else f"<b>{title}</b>"
        if tag:
            h += f" &mdash; {tag}"
        a_items.append(f'  <p style="margin:0 0 14px 0;">{h}<br>{desc}</p>')

    agent_name = p.get("agent_email_greeting", "[Agent name]")
    agent_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} — Seller Portal, agent email</title></head>
<body style="max-width:660px; margin:24px auto; padding:0 20px;">

<p>{agent_name}:</p>

<p>Here is the <b>{portal_link}</b> for <b>{p["address"]}</b>.</p>

<p>Pricing can only be determined after a visual inspection of the
property, including its condition, upgrades, and overall presentation. However, based
on homes of similar size ({sf_ag} SF AG), age ({p["subject"]["built"]}) and assessment
({assessed}) that have sold within the past 60 days, the estimated value range is
between <b>{money(p['values']['customary'])}</b> and <b>{money(s.expected_high)}</b>, with a
Coming Soon list price of <b>{money(s.coming_soon)}</b>.</p>

{control_para}<p><b>AI ENHANCED. STRATEGY DRIVEN.</b><br>The Casey Samson Team combines advanced AI technology with proven real estate strategy to create better decisions, stronger marketing and better results.</p>

{chr(10).join(a_items)}

<p>Casey</p>

<p><b>AI + CST STRATEGY</b><br>Better Decisions. Better Marketing. Better Results.</p>

</body></html>
"""
    # Casey, 21 Oct 2026: "that realtor email is too strong. Just run the
    # Bethany email for realtors." A sample portal goes to an outside
    # realtor, so it gets the Recovery Email only -- no Agent Email, and any
    # left from an earlier build is removed.
    # Casey, 27 Oct 2026: "you are using old email. I want simpler email to
    # agents." The long Agent Email is retired on every portal unless
    # "old_agent_email": true; agents get the short realtor email instead.
    if p.get("sample") or not p.get("old_agent_email"):
        for _ext in ("html", "eml"):
            (out / f"{pre}_Agent_Email.{_ext}").unlink(missing_ok=True)
        note("Agent Email OMITTED — agents get the short Realtor Email "
             "(00_Realtor_Email) instead.")
    else:
        (out / f"{pre}_Agent_Email.html").write_text(agent_html)
        _write_eml(out, f"{pre}_Agent_Email", agent_html,
                   f'Seller Portal ready — {p["address"]}', p)


    # Short by design: four links and nothing to price against. No range, no
    # coming-soon number — those belong in the Roadmap after the walk-through.
    # The three portal links always point at the MacArthur showcase; only the
    # market link follows the seller's own market.
    sample = p.get("sample_portal_url", SAMPLE_PORTAL)
    sample_rm = p.get("sample_roadmap_url", SAMPLE_ROADMAP)
    sample_bp = p.get("sample_buyer_url", SAMPLE_BUYER)
    mk = p.get("market") or {}
    mss = (f'https://cstmarketupdate.netlify.app/{mk["slug"]}.html'
           if mk.get("slug") else None)
    mss_row = (
        f'<p style="margin:0 0 12px;"><b><a href="{mss}">Market Update</a></b> '
        "&mdash; Keeps you up to date on the market activity affecting the sale "
        "of your home.</p>\n" if mss else "")
    if not mss:
        note("Seller email: Market Update link OMITTED — no market slug on file.")

    # ---- recovery variant ------------------------------------------------
    # A seller who is already listed and sitting does not need the "looking
    # forward to meeting you" letter. They need the number, the reason, and
    # the two pages that show it.
    if p.get("listing_status") == "recovery" and p.get("current_list"):
        _v, _cl = p["values"], p["current_list"]
        _r = recovery_prices(p)
        _rec = p.get("recovery") or {}
        _pool = _rec.get("buyer_pool") or s.closest_buyer_threshold
        _prem_top = _v.get("premium") or (s.premium_top if s.has_upgrades else 0)
        _upg = _v.get("upgrades") or 0
        _ev_txt, _worth = recovery_evidence(p, _pool, _upg, _prem_top, _cl)
        _recovers = ("recovers the premium the upgrades earned" if _upg
                     else "recovers the value the home actually has")
        _hard_extra = _rec.get("email_note", "")
        _rm_url = _rec.get("roadmap_url") or rm
        if not _rec.get("roadmap_url"):
            note('Seller email (recovery): Roadmap link points inside the portal. '
                 'Add "recovery": {"roadmap_url": "..."} once the Roadmap site is '
                 "deployed, so the seller gets the standalone page.")
        _bpb = p.get("buyer_portal") or {}
        _bp = _bpb.get("url") if _bpb.get("live") is True else None
        _bp_row = (
            f'<p style="margin:0 0 12px;"><b><a href="{_bp}">Buyer Portal</a></b> '
            "&mdash; the same competition and market, read from the buyer&rsquo;s "
            "side of the table. This is what buyers and their agents see.</p>\n"
            if _bp else "")
        if not _bp:
            note("Seller email (recovery): Buyer Portal row OMITTED — "
                 + ("no url on file." if not _bpb.get("url") else
                    'the portal is not published yet. Set "live": true on the '
                    "day the page goes up."))

        _html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} &mdash; Recovery Strategy email</title></head>
<body style="max-width:660px; margin:24px auto; padding:0 20px;">

<p>Hi {names},</p>

<p>Here is the recovery strategy for <b>{p["address"]}</b>.</p>

<p><b>The problem is not the home &mdash; it is where the buyer pool is.</b> Buyers
for homes of this age and size are shopping <b>under {abbrev(_pool)}</b>. {_ev_txt}</p>

<p>{_worth}, and we are listed at <b>{money(_cl)}</b>. <b>That is not where the
buyer pool is.</b> Being worth more than the pool will pay is not the same as
selling.</p>

<p><b>The key is to find the pool and create bidding</b> &mdash; not to inch toward
it. A home priced into the pool, below the ones that have been sitting in it, draws
more than one buyer at a time. That is what produces a sale above list, and it is
the only mechanism that {_recovers}.</p>

<p><b>Recovery is a three-step process.</b> The home comes off the market for 14
days while we inspect condition, test the buyer pool and analyze the market. What
those 14 days turn up sets the relaunch price:</p>

<p style="margin:0 0 10px;">&bull; <b>2 to 3 buyers inquire and the market holds</b>
&mdash; relaunch at <b>{money(_r["soft"])}</b>, {_r["soft_basis"]}.</p>

<p style="margin:0 0 18px;">&bull; <b>No one calls</b> &mdash; relaunch at
<b>{money(_r["hard"])}</b> &mdash; {_r["hard_basis"]}{_hard_extra}.</p>

<p>The 14 days are not a pause, they are the work. A home that comes back looking
the same gets read as the same home at a lower price, and the reduction is spent
for nothing.</p>

<p style="margin:0 0 12px;"><b><a href="{_rm_url}">Recovery Roadmap</a></b>
&mdash; the full reconciliation of value against price, the competition, the
market conditions and the strategy behind both numbers.</p>

<p style="margin:0 0 12px;"><b><a href="{base}/{pre}_Pricing_Strategy_Summary.pdf">{summary_name(p)} (PDF)</a></b>
&mdash; the print version: the values, where the buyer pool is, the market and
both relaunch prices, with our track record on the back.</p>

{_bp_row}{mss_row}
<p>Let&rsquo;s talk through it.</p>

<p>{signoff(p)}</p>

</body></html>
"""
        # Casey, 21 Nov 2026: "recovery emails should be same new seller emails.
        # Give instructions to agents at top and email they can copy and paste
        # to seller." The older recovery letter above is kept in _html for
        # reference only; the file the agent opens is the instructions plus
        # the standard seller email, and the .eml draft is the seller email.
        _seller = recovery_seller_email(p, _r)
        _subj = f'Your Listing Recovery Strategy — {p["address"]}'
        (out / f"{pre}_Seller_Email.html").write_text(
            _seller.replace('color:#000;">', 'color:#000;">\n' + agent_instructions(p, _r, _subj), 1),
            encoding="utf-8")
        _write_eml(out, f"{pre}_Seller_Email", _seller, _subj, p)
        return

    # Casey, 25 Nov 2026: "I need the standard emails to sellers to be like
    # the one I just sent" -- the Zunera and Allen email (inquiry_email_html):
    # his wording, Buyer Portal / Sample Portal bullets and the CST Roadmap vs
    # Zillow vs Compass checklist at the bottom instead of the track record.
    # The older standard email below is no longer written.
    html = inquiry_email_html(p)
    _subj = ((p.get("seller_email") or {}).get("subject")
             or (p.get("inquiry_email") or {}).get("subject")
             or f'{p["address"]} — Your Seller Roadmap')
    (out / f"{pre}_Seller_Email.html").write_text(html, encoding="utf-8")
    _write_eml(out, f"{pre}_Seller_Email", html, _subj, p)
    return

    # Casey, 10 Oct 2026: "just say greetings... just have key links... Make
    # this look very short without a lot of bells and whistles. And put each
    # portal link on one line with a brief explanation."
    #
    # Casey, 11 Oct 2026: "Simple email with greetings links to Portal,
    # Roadmap, Buyer Report Luxury track record and the Summary PDF on
    # bottom." So the Portal joins the list, the example and Marketing drop
    # out, and the one-page Pricing Strategy closes it.
    # Casey, 20 Oct 2026: "The links are all wrong. Seller portal street
    # number street name.netlify.app, Buyer portal is
    # buystreetname.netlify.app, you have the rest of the links."
    #
    # Every document in this email lives in the SELLER portal folder, so
    # they all hang off the seller host. This used to run off
    # site_roadmap_url(), which returns the caseysamson.com/market-snapshot
    # path -- an address that only resolves once a redirect is in place, so
    # three of the four links in the seller's email went nowhere.
    #
    # seller_host() derives from the address on every build, which is what
    # keeps the convention from drifting. An explicit portal_url still wins,
    # for a site genuinely published somewhere else, and says so.
    _root = seller_host(p)
    _set = (p.get("portal_url") or "").rstrip("/")
    if _set and _root and _set != _root:
        note(f"Seller email: links point at {_set}, set as portal_url on the "
             f"property file, not the convention address {_root}.")
        _root = _set
    elif not _root:
        _root = _set
    _rm = f"{_root}/{pre}_Roadmap.html" if _root else f"{pre}_Roadmap.html"
    _track = track_record_file(p)

    def _row(href, label, gloss):
        return (f'<p style="margin:0 0 8px;"><a href="{href}">{label}</a> '
                f"&mdash; {gloss}</p>\n")

    # Casey, 20 Oct 2026, wrote this email himself. The copy below is his,
    # word for word -- the opening goal line, the four numbered tools with
    # their descriptions, the closing line and the tagline. Only the links
    # are substituted, because his draft pointed every one of them at
    # 502macarthur.netlify.app as a placeholder.
    #
    # The Buyer Flyer is the printable Buyer Pricing sheet: the two-page
    # document actually left out at the listing and the open house.
    _bp = buyer_portal_url(p)

    # Casey, 20 Oct 2026, on John Marshall: "We are going Coming Soon today
    # at $1.299." His shorthand -- millions to three places, so $1,299,999
    # reads $1.299. Below a million that shape is wrong ($649,999 is not
    # "$0.649"), so those print in full. "launch_line" on the property file
    # replaces the sentence outright.
    def _price_short(v):
        # TRUNCATE, never round: $1,299,999 is "$1.299", not "$1.3".
        # Formatting it with %.3f rounds 1.299999 up to 1.300 and the first
        # build of this line went out reading "$1.3".
        if v < 1_000_000:
            return money(v)
        out = f"{int(v / 1_000) / 1_000:.3f}".rstrip("0")
        return "$" + (out + "0" if out.endswith(".") else out)

    _launch = p.get("launch_line")
    if _launch is None and getattr(s, "coming_soon", None):
        _launch = ("We are going Coming Soon today at "
                   f"{_price_short(int(s.coming_soon))}.")
    if _launch:
        _launch = f"<p>{_launch}</p>\n\n"
        note(f'Seller email: opens with "{re.sub("<[^>]+>", "", _launch).strip()}"'
             ' — it says "today", so send it today or set "launch_line".')
    else:
        _launch = ""

    # Casey, 20 Oct 2026: "Lance and Toria:" -- the sellers by first name,
    # with a colon. Without names on file it stays the generic greeting
    # rather than printing a bracketed placeholder at the top of an email
    # that is otherwise ready to send.
    _greet = p.get("seller_names")
    _greet = f"{_greet}:" if _greet else "Dear Sellers,"
    if not p.get("seller_names"):
        note('Seller email: seller_names not set — greeting is the generic '
             '"Dear Sellers,". Add "seller_names": "Lance and Toria".')

    def _item(n, label, gloss, href=None):
        head = (f'<a href="{href}">{label}</a>' if href else f"<b>{label}</b>")
        return (f'<p style="margin:0 0 10px;">{n}. {head} &mdash; {gloss}</p>\n')

    links = _item(1, "Seller Roadmap&trade;",
                  "Your comprehensive roadmap to a successful listing, from "
                  "preparation and pricing through marketing and settlement.",
                  _rm)
    links += _item(2, f"{summary_name(p)}&trade;",
                   "A summary of our pricing ladder, major buyer thresholds, "
                   "and triggers for adjusting our strategy based on market "
                   "response.",
                   f"{_root}/{pre}_Pricing_Strategy_Summary.pdf")
    # The portal link is opt-in: "live" false means it is not published, and
    # the 11 Oct rule is never ship a dead one. The item stays in the list
    # unlinked rather than coming out, so the seller still sees all four
    # tools and the numbering does not shift under them.
    links += _item(3, "Buyer Portal&trade;",
                   "A powerful marketing tool that showcases your home&rsquo;s "
                   "value, premium features, upgrades, schools, amenities, maps, "
                   "and lifestyle advantages to prospective buyers.",
                   _bp)
    if not _bp:
        note("Seller email: the Buyer Portal is listed but NOT linked — it is "
             'not published yet. Set "live": true the day it goes up.')
    links += _item(4, "Buyer Flyer",
                   "Displayed at the listing and open houses, highlighting your "
                   "home&rsquo;s authenticated values and premiums to help buyers "
                   "understand and appreciate its value.",
                   f"{_root}/{pre}_Buyer_Report.pdf")
    # Casey, 15 Nov 2026: "Seller emails need to include links to their Market
    # Snapshot." Item 5, and the count says five.
    _mk = market_snapshot_url(p)
    if _mk:
        links += _item(5, "Market Snapshot",
                       "Current conditions in your home&rsquo;s market, updated "
                       "every week &mdash; what is selling, how fast, and who is "
                       "in control.", _mk)
    _n_tools = "five" if _mk else "four"

    # Casey, 20 Oct 2026: "and link seller portal." The sentence that
    # introduces the four tools names the portal, so that is where the link
    # goes -- rather than a fifth item under a list he wrote as four.
    # Casey, 20 Oct 2026: "Call it The CST Seller Portal."
    _portal_link = (f'<a href="{_root}">The CST Seller Portal</a>' if _root
                    else "The CST Seller Portal")

    # Casey signed his draft "Casey", not "Casey Samson", and put the number
    # under the team line. Both come off the agent block so a portal listed
    # by somebody else signs in their name and prints their number.
    _ag = p.get("agent") or {}
    _nm = (_ag.get("display") or _ag.get("lookup") or "Casey Samson").strip()
    _first = _nm.split()[0]
    _phone = _ag.get("phone") or "703-508-2535"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} — Seller Portal email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{_greet}</p>

{_launch}<p>Our goal is to maximize the value of your home through strategic
pricing and professional marketing that finds the largest buyer pool.
{_portal_link} brings together {_n_tools} powerful tools designed to achieve a
successful sale:</p>

{links}
<p style="margin-top:22px;">Each tool is designed to attract buyers, build
confidence in your home&rsquo;s value, and help us negotiate the strongest
possible offer.</p>

<p style="margin-top:22px;"><i>It&rsquo;s Not a Price, It&rsquo;s a
Strategy.&trade;</i></p>

<p>If you have any questions do not hesitate to call.</p>

<p>{_first}<br>The Casey Samson Team<br>{_phone}</p>

</body></html>
"""
    # Casey, 20 Nov 2026: the seller email, word for word (first used for
    # 4608 Freedmen and 3106 Whimbrell). Day and time are markers unless the
    # property file carries "meeting"; the signature is the listing agent --
    # the private-label agent on a PL build.
    html = seller_email_v2(p)
    _launch = False
    # The subject has to match the first line. An email that opens "We are
    # going Coming Soon today at $1.299" and arrives titled "Your Seller
    # Portal" buries the one thing the seller is waiting to read.
    _subj = (f'Coming Soon — {p["address"]}' if _launch
             else f'Your Seller Portal — {p["address"]}')
    # Casey, 22 Nov 2026: private-label seller emails carry the same agent
    # instructions as recovery emails -- the agent copies the email below the
    # line and sends it from their own account. The .eml draft stays clean.
    _page = html
    if p.get("private_label"):
        _page = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + agent_instructions(p, None, _subj),
                       html, count=1)
    (out / f"{pre}_Seller_Email.html").write_text(_page, encoding="utf-8")
    _write_eml(out, f"{pre}_Seller_Email", html, _subj, p)




def agent_instructions(p, r, subject):
    """Instructions for the listing agent, above the copy-and-paste seller
    email on a recovery -- Casey's wording, 21 Nov 2026 (6:08 PM)."""
    root = (seller_host(p) or "").rstrip("/")
    pre = p["prefix"]
    rec = p.get("listing_status") == "recovery"
    def a(h, t):
        return f'<a href="{h}">{t}</a>' if h else t
    return f"""<div style="border:2px solid #B8902F;background:#FBF6EA;border-radius:8px;padding:16px 20px;margin:0 0 20px;font-family:Arial,Helvetica,sans-serif;font-size:14pt;line-height:1.45;color:#2b2618;">
<p style="margin:0 0 8px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#8A6A2E;font-size:14pt;">For the agent &mdash; do not send this section</p>
<p style="margin:0 0 6px;"><b>1. Review:</b> {a(root + "/" if root else None, "Seller Portal")}, {a(f"{root}/{pre.lower()}_roadmap" if root else None, "Recovery Roadmap" if rec else "Seller Roadmap")}, and {a(f"{root}/{pre}_Pricing_Strategy_Summary.pdf" if root else None, "Pricing Strategy Summary")}.</p>
<p style="margin:0 0 6px;"><b>2. Personalize:</b> {"Add the seller&rsquo;s name and confirm the pricing recommendations." if rec else "Add the seller&rsquo;s name and confirm the meeting day and time."}</p>
<p style="margin:0 0 6px;"><b>3. Copy:</b> Everything below the line into a new email.</p>
<p style="margin:0;"><b>4. Send:</b> From your own email. Your signature is included.</p>
</div>
<p style="margin:0 0 22px;text-align:center;color:#8A6A2E;font:14pt Arial,sans-serif;letter-spacing:.15em;">&#9986; &mdash;&mdash;&mdash; COPY BELOW THIS LINE &mdash;&mdash;&mdash;</p>
"""


def recovery_seller_email(p, r):
    """Casey's recovery (PL) seller email (steps revised 22 Nov 2026: Inspect,
    TEMP Off, Test, Adjust Price with Fall Back / Rip Cord sub-steps), 21 Nov 2026 (6:15 PM), word for word:
    the agent box at 14pt, the email at 24pt Times New Roman.
    Fall Back = r["soft"], Rip Cord = r["hard"] -- the two relaunch prices on
    the Recovery Roadmap. Signature: the listing agent (PL agent on a PL)."""
    pre = p["prefix"]
    root = (seller_host(p) or "").rstrip("/")
    bp = (buyer_portal_url(p) or "").rstrip("/")
    slug = (p.get("market") or {}).get("slug") or ""
    mkt = f"https://cstmarketupdate.netlify.app/{slug.lower()}" if slug else None
    pl = p.get("private_label") or {}
    ag = p.get("agent") or {}
    full = pl.get("name") or ag.get("display") or "Agent"
    title = re.sub(r"\s*&middot;\s*Licensed.*$", "", pl.get("title") or ag.get("title") or "REALTOR&reg;")
    phone = pl.get("phone") or ag.get("phone") or "Phone"
    names = p.get("seller_names") or "(Seller Name)"
    fb, rc = money(r["soft"]), money(r["hard"])
    def a(h, t):
        return f'<a href="{h}">{t}</a>' if h else t
    items = [
        (f"{root}/{pre.lower()}_roadmap" if root else None, "Seller Roadmap&trade;",
         "Authenticated home values, pricing strategy, and marketing plan based on comparable sales."),
        (bp + "/" if bp else None, "Buyer Portal&trade;",
         "Showcases your home&rsquo;s value, upgrades, and neighborhood advantages."),
        (f"{root}/{pre}_Buyer_Report.pdf" if root else None, "Buyer Flyer",
         "Helps buyers understand your home&rsquo;s value during showings."),
        (mkt, "Market Snapshot", "Weekly market conditions showing buyer demand and competition."),
    ]
    li = "".join(f'<p style="margin:0 0 8px;">{i}. {a(u, n)} &mdash; {d}</p>\n'
                 for i, (u, n, d) in enumerate(items, 1))
    H = 'style="margin:26px 0 10px;font-size:24pt;font-weight:700;"'
    S = 'style="margin:18px 0 2px;"'
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} — Recovery seller email</title></head>
<body style="max-width:900px; margin:24px auto; padding:0 20px; line-height:1.4; font-family:'Times New Roman',Times,serif; font-size:24pt; color:#000;">

<p>Hi {names},</p>

<p>It was nice speaking with you. Here is our Listing Recovery Strategy to attract more buyers and
secure the best possible offer.</p>

<h3 {H}>Our 4-Step Recovery Strategy</h3>

<p {S}><b>1. Inspect Property and Review Comments</b></p>
<p style="margin-top:0;">Does the property need any updates that can make it more appealing to buyers?</p>

<p {S}><b>2. Temporarily Off Market</b></p>
<p style="margin-top:0;">Take the home TEMP Off Market. Buyers and agents watching the listing may call to find out why.</p>

<p {S}><b>3. Test Buyer Interest</b></p>
<p style="margin-top:0;">If they call, we explain that the home will return at a lower price. This may encourage buyers
to make an offer before the reduction.</p>

<p {S}><b>4. Adjust Price</b></p>
<p style="margin-top:0;"><b>Note:</b> Adjusting price does not mean a lower sales price, it means a larger
buyer pool. Lower prices usually produce higher prices (see below).</p>
<p style="margin:0 0 2px 1.2em;"><i>If some buyers call &mdash; Fall Back Price, {fb}</i></p>
<p style="margin:0 0 14px 1.2em;">If we receive interest but no acceptable offer, we return to the market at {fb} to
get exposure to a larger buyer pool.</p>
<p style="margin:0 0 2px 1.2em;"><i>If no one calls &mdash; Pull the Rip Cord, {rc}</i></p>
<p style="margin:0 0 14px 1.2em;">This suggests our price is not close to the buyer pool. We go to {rc} to
guarantee the largest buyer pool. Whatever buyers bid is what the home is worth at this time.</p>

<h3 {H}>Your CST Seller Portal&trade; Assets</h3>

<p>Your {a(root + "/" if root else None, "Seller Portal")} includes four tools to support our strategy:</p>

{li}
<p><b>Our Goal:</b> Test buyer interest, reposition the home at the right price, and use our
marketing tools to generate the strongest possible offer.</p>

<p><i>It&rsquo;s Not a Price, It&rsquo;s a Strategy.&trade;</i></p>

<p>We can review everything when we meet.</p>

<p style="line-height:1.4;">{full}<br>{phone}<br>{title} &middot; Samson Properties</p>

{over_list_table_html(H, p)}
</body></html>
"""

def seller_email_v2(p):
    """Casey's seller email (20 Nov 2026; revised 22 Nov 2026 -- The Standard
    paragraph, Buyer Portal premium line, no tagline line). Links follow the published site:
    the Roadmap as its lowercase page name without .html, the Market Snapshot
    as cstmarketupdate.netlify.app/<market slug, lowercase>."""
    pre = p["prefix"]
    root = (seller_host(p) or "").rstrip("/")
    bp = (buyer_portal_url(p) or "").rstrip("/")
    slug = (p.get("market") or {}).get("slug") or ""
    mkt = f"https://cstmarketupdate.netlify.app/{slug.lower()}" if slug else None
    pl = p.get("private_label") or {}
    ag = p.get("agent") or {}
    full = pl.get("name") or ag.get("display") or "Listing agent full name"
    first = full.split()[0] if full and " " in full else full
    title = re.sub(r"\s*&middot;\s*Licensed.*$", "", pl.get("title") or ag.get("title") or "REALTOR&reg;")
    phone = pl.get("phone") or ag.get("phone") or "Agent Phone"
    names = p.get("seller_names") or "(Seller name)"
    when = p.get("meeting") or "(day) at (time)"
    # Casey, 22 Nov 2026 (Leigh, 9002 Lupine Den): "We look forward to seeing
    # you tomorrow at 9." -- no "on" before a relative day.
    _on = "" if re.match(r"(tomorrow|today|tonight|this|next)\b", when.lower()) else "on "
    # The Standard paragraph is CST's record; on a private label it is named
    # as CST's so the branding pass never hands it to the agent.
    _std = "The CST Standard is" if pl else "The Standard for the Casey Samson Team is"

    def a(href, text):
        return f'<a href="{href}">{text}</a>' if href else text
    items = [
        (f"{root}/{pre.lower()}_roadmap" if root else None, "Seller Roadmap&trade;",
         "Your comprehensive roadmap to a successful listing, from preparation and pricing "
         "through marketing and settlement. <b>Note: Pricing is only based on appraisal quality "
         "comps of similar size, age, location and time. This is only Preliminary Pricing. "
         "Final Pricing will be determined after an inspection and conversation with you about "
         "the home&rsquo;s condition, upgrades, neighborhood comps that may not show up on appraisers&rsquo; "
         "searches and analysis of market condition.</b>"),  # Casey, 20 Nov 2026: bold
        (f"{root}/{pre}_Pricing_Strategy_Summary.pdf" if root else None, "Pricing Strategy Summary&trade;",
         "A summary of our preliminary pricing ladder, major buyer thresholds, and triggers for "
         "adjusting our strategy based on market response. Getting the highest value is not "
         "about price, it&rsquo;s about a strategy of testing markets to find the buyer pool "
         "that delivers the highest and best contracts (see below). 95% of our sales avoid "
         "home inspection and financing contingencies."),
        (bp + "/" if bp else None, "Buyer Portal&trade;",
         "A powerful marketing tool that showcases your home&rsquo;s value, premium features, "
         "upgrades, schools, amenities, maps, and lifestyle advantages to prospective buyers. "
         "It authenticates premium values and gives the buyer confidence it&rsquo;s OK to pay "
         "Premium Pricing."),
        (f"{root}/{pre}_Buyer_Report.pdf" if root else None, "Buyer Flyer",
         "Displayed at the listing and open houses, highlighting your home&rsquo;s authenticated "
         "values and premiums to help buyers understand and appreciate its value."),
        (mkt, "Market Snapshot",
         "Current conditions in your home&rsquo;s market, updated every week &mdash; what is "
         "selling, how fast, and who is in control."),
    ]
    li = "".join(f'<p style="margin:0 0 10px;">{i}. {a(u, n)} &mdash; {d}</p>\n'
                 for i, (u, n, d) in enumerate(items, 1))
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} — Seller email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{names}:</p>

<p>We look forward to seeing you {_on}{when}.</p>

<p>{_std} to sell in an average of 6 days, create competition for the home, receive highest and
best offers with no contingencies, and give our sellers flexibility on moving preferences. The Pricing and Selling Strategy, outlined in our
{a(root + "/" if root else None, "Seller Portal")}, shows how we use five powerful tools to do it.</p>

{li}
<p>Each tool is designed to attract buyers, build confidence in your home&rsquo;s value, and help
us negotiate the strongest possible offer.</p>

<p>We can review when we meet.</p>

<p>{first}</p>

<p style="line-height:1.4;">{full}<br>{title} &middot; Samson Properties<br>{phone}</p>

{over_list_table_html(p=p)}
</body></html>
"""

def build_recovery_agent_email(p, s, out):
    """Outreach to the listing agent of a recovery listing.

    Casey, 20 Oct 2026, wrote this email himself -- subject "Additional
    Resources for Samson Listings". Same day, 6:30 PM, he replaced the
    opening two paragraphs with "We prepare these tools to help agents
    with listings in need." 6:39 PM: new copy for items 1, 2 and 4. / "Here is the CST Seller Portal for ...". The copy is his, word for word; only the
    agent's name, the address and the five links are filled in. It goes out
    from Casey, not from whoever holds the listing, so the sign-off and the
    From line are his whatever the property's agent block says.

    "listing_agent_name" on the property file is the greeting ("Hi Ferris,").
    """
    pre = p["prefix"]
    root = (seller_host(p) or (p.get("portal_url") or "")).rstrip("/")
    link = lambda f: f"{root}/{f}" if root else f
    bp = buyer_portal_url(p) or buyer_host(p)
    name = (p.get("listing_agent_name") or "").strip()
    greet = f"Hi {name}," if name else "Hi,"
    if not name:
        note('Recovery agent email: listing_agent_name not set — greeting is '
             'a bare "Hi,". Add "listing_agent_name": "Ferris".')
    addr = p["address"]

    def a(href, text):
        return f'<a href="{href}">{text}</a>' if href else text

    # Casey, 22 Oct 2026: new realtor email, "New Recovery tools for Samson
    # Properties listings" -- his copy, word for word; only the greeting,
    # address and links are filled in.
    if not bp:
        note("Recovery agent email: no Buyer Portal address could be derived — "
             "item 3 is not linked.")
    _bpa = a(bp + "/" if bp else None, "Buyer Portal&trade;")
    html_rec = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{addr} — recovery realtor email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{greet}</p>

<p>In the first nine months of 2026, over $1 BILLION in Samson Properties
Virginia listings were taken off the market unsold. Once a listing exceeds 30
days on the market, its chance of failure increases by 435%.</p>

<p><b>Samson Properties is changing the game.</b></p>

<p>By combining the power of AI with the proven pricing and marketing
strategies of a $300M Samson team&mdash;boasting a 97% success rate and an
average of just 6 days on market&mdash;we&rsquo;re giving Samson agents powerful
tools to recover struggling listings.</p>

<p>These tools can change the trajectory of a listing.</p>

<p style="margin-top:22px;"><b>Introducing the CST Seller Portal&trade;</b></p>

<p>Here is a customized {a(root + "/" if root else None, "CST Seller Portal")} for
{addr}, bringing together four powerful resources:</p>

<p style="margin:0 0 10px;">1. {a(link(f"{pre}_Roadmap.html"), "Seller Roadmap&trade;")} &mdash;
Evaluates pricing, market conditions, and opportunities while laying out a
clear roadmap to success.</p>
<p style="margin:0 0 10px;">2. {a(link(f"{pre}_Pricing_Strategy_Summary.pdf"), "Pricing Strategy Summary&trade;")}
&mdash; A concise, proven pricing strategy built around buyer thresholds, market
response, and our track record of results.</p>
<p style="margin:0 0 10px;">3. {_bpa} &mdash; A powerful marketing tool
showcasing the home&rsquo;s value, upgrades, schools, amenities, and location
advantages&mdash;giving buyers more reasons to choose the property.</p>
<p style="margin:0 0 10px;">4. {a(link(f"{pre}_Buyer_Report.pdf"), "Buyer Flyer")} &mdash; A
professional summary of the Buyer Portal for showings and open houses,
reinforcing the home&rsquo;s value and the agent&rsquo;s efforts to achieve the
highest possible price. Sellers love it!</p>

<p style="margin-top:22px;"><b>A Fresh Strategy Can Make All the Difference</b></p>

<p>Every home and every market is different. Sometimes all a listing needs is
a fresh perspective, smarter pricing, or stronger marketing to get it sold.</p>

<p>We&rsquo;ve created this temporary Seller Portal as a sample of what&rsquo;s
possible for your listing. We will be conducting Listing workshops so Samson
Realtors can sharpen their shills using today&rsquo;s tools.</p>

<p>If you&rsquo;d like to activate these tools and incorporate them into your
marketing, we&rsquo;re <a href="https://workwithcst.netlify.app/">happy to help</a>.</p>

<p>If not, we hope they provide a fresh perspective or inspire a new
strategy.</p>

<p><i>It&rsquo;s Not a Price, It&rsquo;s a Strategy.&trade;</i></p>

<p>Good luck!<br>Casey<br>The Casey Samson Team<br>703-508-2535</p>

</body></html>
"""
    # Casey, 22 Oct 2026: "Seller email on Regular Portals" -- the realtor
    # email for a sample portal on a listing that is NOT a recovery. His copy
    # word for word; the opening paragraph's figures are this portal's own
    # market, read from the MSS the same way the Summary's gauges are.
    _mk = market_posture(p)
    _mname = (p.get("market") or {}).get("name") or ""
    _mm = re.match(r"(.+?)\s+(Family|Luxury)\s+Market", _mname)
    _mtxt = (f"{_mm.group(1)}&rsquo;s {_mm.group(2)} Home market" if _mm
             else (_mname or "this market"))
    _sr = _gauge_value(_mk.get("success_rate"))
    _wd = f"{100 - round(_sr)}%" if _sr is not None else None
    _dom, _u14 = _mk.get("avg_dom"), _mk.get("uc_14")
    if not (_wd and _dom and _u14):
        note("Realtor email (regular): market figures missing -- "
             f"withdrawn {_wd}, DOM {_dom}, 14-day {_u14}. Check the MSS cache.")
    html_reg = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{addr} — realtor email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{greet}</p>

<p>In {_mtxt}, {_wd} of listings withdraw unsold, with an average of {_dom}
days on market. Only {_u14} have gone under contract in the last 14 days.</p>

<p><b>This is a market that demands a strategy that works.</b></p>

<p>The Casey Samson Team has achieved a 97% listing success rate, an average
of just 6 days on market, and an average of $93,000 over list price.</p>

<p>We&rsquo;ve combined our proven pricing and marketing strategies with
powerful AI tools to help Sellers build a Roadmap&trade; to success, and
strengthen buyer confidence in the property.</p>

<p style="margin-top:22px;"><b>Introducing the CST Seller Portal&trade;</b></p>

<p>We&rsquo;ve created a customized {a(root + "/" if root else None, "CST Seller Portal")}
for {addr}, bringing together four powerful resources:</p>

<p style="margin:0 0 10px;">1. {a(link(f"{pre}_Roadmap.html"), "Seller Roadmap&trade;")} &mdash;
Analyzes pricing, competition, market conditions, and opportunities to
establish a clear path to success.</p>
<p style="margin:0 0 10px;">2. {a(link(f"{pre}_Pricing_Strategy_Summary.pdf"), "Pricing Strategy Summary&trade;")}
&mdash; A proven pricing strategy built around buyer thresholds, market
response, and a roadmap for making the right adjustments.</p>
<p style="margin:0 0 10px;">3. {_bpa} &mdash; Showcases the home&rsquo;s value,
upgrades, schools, amenities, and location advantages, giving buyers more
reasons to choose the property.</p>
<p style="margin:0 0 10px;">4. {a(link(f"{pre}_Buyer_Report.pdf"), "Buyer Flyer")} &mdash; A
professional summary for showings and open houses that reinforces the
home&rsquo;s value and the agent&rsquo;s marketing efforts. Sellers love it!</p>

<p style="margin-top:22px;"><b>A Fresh Strategy Can Make All the Difference</b></p>

<p>Every home and every market is different. Sometimes a fresh perspective,
smarter pricing, or better marketing is all it takes to turn a listing
around.</p>

<p>We&rsquo;ve created this temporary Seller Portal to demonstrate what&rsquo;s
possible for your listing.</p>

<p>We&rsquo;re also introducing Listing Strategy Workshops to help Samson
agents sharpen their skills and put today&rsquo;s most powerful AI, pricing,
and marketing tools to work.</p>

<p>If you&rsquo;d like to activate these tools for your listing, we&rsquo;re
<a href="https://workwithcst.netlify.app/">happy to help</a>.</p>

<p>If not, we hope they provide a fresh perspective or inspire a new
strategy.</p>

<p><i>It&rsquo;s Not a Price, It&rsquo;s a Strategy.&trade;</i></p>

<p>Good luck!<br>Casey<br>The Casey Samson Team<br>703-508-2535</p>

</body></html>
"""
    _is_rec = p.get("listing_status") == "recovery"
    # Casey, 16 Nov 2026 (4322 Thomas Brigade): "recovery emails should be more
    # like this" -- Here are the problems (from the recovery request), a look at
    # the portals, the advice, "Hope this helps."
    _probs = [x for x in ((p.get("recovery") or {}).get("problems") or []) if x]
    _rv = recovery_prices(p) if (_is_rec and p.get("current_list")) else {"soft": 0}
    _street = re.sub(r"^\d+[A-Za-z]?\s+", "", addr)
    if _is_rec and _probs:
        _pl = "".join(f'<p style="margin:0 0 8px;">{i}. {x}</p>\n' for i, x in enumerate(_probs, 1))
        html_rec = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{addr} — recovery realtor email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{greet}</p>

<p>Here are the problems:</p>
{_pl}
<p style="margin-top:18px;">Here is a look at the {a(root + "/" if root else None, "Seller")} and {_bpa.replace("Buyer Portal&trade;", "Buyer Portals")} for {_street}.</p>

<p><b>Advice:</b></p>
<ul style="margin-top:0;">
<li>Go temp off.</li>
<li>In one week, drop to {money(_rv["soft"]) if _rv.get("soft") else "the relaunch price"} &mdash; where it should have started, per the {a(link(f"{pre}_Roadmap.html"), "Seller Roadmap&trade;")}.</li>
<li>Show the seller the {_bpa} &mdash; what buyers will see.</li>
<li>Print the {a(link(f"{pre}_Buyer_Report.pdf"), "Buyer Flyer")} and have it at the listing when buyers walk in.</li>
</ul>

<p>Hope this helps.</p>

<p>Casey<br>The Casey Samson Team<br>703-508-2535</p>

</body></html>
"""
    elif _is_rec:
        note("Recovery email: no problems on file (recovery.problems) -- using "
             "the general recovery wording. Casey provides the problems.")
    html = html_rec if _is_rec else html_reg
    # Casey, 21 Oct 2026: "bring realtor email on top so I don't need to go
    # looking for it" -- 00_ sorts it first in the folder.
    _stem = f"00_Realtor_Email_{pre}"
    for _ext in ("html", "eml"):
        (out / f"{pre}_Recovery_Email.{_ext}").unlink(missing_ok=True)
    # Casey, 21 Oct 2026: "put Realtor email address on top so I can just
    # copy and paste". The HTML copy gets a To / Subject box above the body;
    # the .eml carries them as real headers, so the box is not in it.
    _ag = p.get("agent") or {}
    _to = p.get("listing_agent_email") or (
        "" if (_ag.get("lookup") or "").lower().startswith("casey")
        else (_ag.get("email") or ""))
    _subj = (f"{addr} — a few thoughts" if (_is_rec and _probs)
             else "New Recovery tools for Samson Properties listings" if _is_rec
             else p.get("realtor_email_subject")
             or "New Listing tools for Samson Properties listings")
    if not _to:
        note('Realtor email: no address on file -- add "listing_agent_email".')
    _box = ('<div style="max-width:620px;margin:24px auto 0;padding:12px 16px;'
            'border:1px dashed #D3B978;border-radius:6px;background:#FAF7F0;'
            'font:14px/1.6 Georgia,serif;color:#221C14;">'
            '<div><b>To:</b> <span style="user-select:all;">'
            f'{_to or "(no address on file)"}</span></div>'
            f'<div><b>Subject:</b> <span style="user-select:all;">{_subj}</span></div>'
            '<div style="font-size:12px;color:#71695A;margin-top:4px;">'
            'Copy the address and subject from here; copy the email from '
            '&ldquo;Hi&rdquo; down.</div></div>\n')
    (out / f"{_stem}.html").write_text(
        html.replace(f"<p>{greet}</p>", _box + f"<p>{greet}</p>", 1),
        encoding="utf-8")
    casey = dict(p, agent={"lookup": "Casey Samson", "display": "Casey Samson",
                           "email": "casey@caseysamson.com"})
    _write_eml(out, _stem, html, _subj, casey, to=_to)


def build_prelisting_seller_email(p, s, out):
    """Email to the sellers before the listing appointment.

    Casey, 22 Oct 2026, on 2838 Cedar ("Seller email", Peter and Hanna,
    Friday at 10:30). His copy, word for word; only the names, the meeting
    time, the address and the links are filled in. Property file:

        "prelisting_email": {
            "seller_names": "Peter and Hanna",
            "meeting": "Friday at 10:30",
            "meeting_day": "Friday",          -- optional, closing line
            "to": "peter@example.com",         -- optional
            "subject": "..."                    -- optional
        }
    """
    cfg = p.get("prelisting_email") or {}
    pre = p["prefix"]
    root = (seller_host(p) or (p.get("portal_url") or "")).rstrip("/")
    link = lambda f: f"{root}/{f}" if root else f
    bp = buyer_portal_url(p) or buyer_host(p)
    names = (cfg.get("seller_names") or p.get("seller_names") or "").strip()
    greet = f"Hi {names}," if names else "Hi,"
    meeting = (cfg.get("meeting") or "").strip()
    day = (cfg.get("meeting_day") or (meeting.split(" at ")[0] if meeting else "")).strip()
    if not meeting:
        note('Pre-listing seller email: "meeting" not set -- first line reads '
             '"on (meeting)". Add "meeting": "Friday at 10:30".')
    addr = p["address"]
    # Casey, 13 Nov 2026 wording; 15 Nov 2026: every seller email links the
    # home's Market Snapshot ("five tools") and carries the preliminary note.
    _mkt = market_snapshot_url(p)

    def a(href, text):
        return f'<a href="{href}">{text}</a>' if href else text

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{addr} — pre-listing seller email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{names or "(Seller name)"},</p>

<p>I look forward to seeing you and the home at {meeting or "(time) (day)"}.</p>

<p>I&rsquo;ve prepared your {a(root + "/" if root else None, "CST Seller Portal")} for {addr}.</p>

<p>At the top, you&rsquo;ll see how The Casey Samson Team&rsquo;s verified results
compare to the rest of the market. Our success comes from having a clear
strategy before we list.</p>

<p>Your portal includes {"five" if _mkt else "four"} tools:</p>

<p style="margin:0 0 10px;">1. {a(link(f"{pre}_Roadmap.html"), "Seller Roadmap&trade;")} &ndash;
Your home&rsquo;s value, competition, market conditions, and recommended pricing
strategy. I&rsquo;ll finalize the pricing after seeing your home.</p>
<p style="margin:0 0 10px;">2. {a(link(f"{pre}_Pricing_Strategy_Summary.pdf"), "Pricing Strategy Summary&trade;")}
&ndash; How we position your home to attract buyers and maximize your sales price.</p>
<p style="margin:0 0 10px;">3. {a(bp + "/" if bp else None, "Buyer Portal&trade;")} &ndash; Showcases your
home&rsquo;s features, upgrades, and location to help buyers recognize its value.</p>
<p style="margin:0 0 10px;">4. {a(link(f"{pre}_Buyer_Report.pdf"), "Buyer Flyer")} &ndash; A simple
summary of your home&rsquo;s value for buyers and their agents.</p>
{(f'<p style="margin:0 0 10px;">5. {a(_mkt, "Market Snapshot")} &ndash; Current market '
  f'conditions for your home&rsquo;s market, updated every week.</p>') if _mkt else ""}

<p>Please note: the pricing in your portal is preliminary. Final pricing is set
only after I see your home&rsquo;s condition, upgrades, and lot premium or
discount.</p>

<p>Our goal is simple: Build buyer confidence, create competition, and achieve top dollar.</p>

<p>See you at {meeting or "(time)"}!</p>

<p>Casey</p>

</body></html>
"""
    _stem = f"00_Seller_Email_{pre}"
    _to = cfg.get("to") or ""
    _subj = cfg.get("subject") or f"A preliminary look at the strategy for {addr}"
    _box = ('<div style="max-width:620px;margin:24px auto 0;padding:12px 16px;'
            'border:1px dashed #D3B978;border-radius:6px;background:#FAF7F0;'
            'font:14px/1.6 Georgia,serif;color:#221C14;">'
            '<div><b>To:</b> <span style="user-select:all;">'
            f'{_to or "(no address on file)"}</span></div>'
            f'<div><b>Subject:</b> <span style="user-select:all;">{_subj}</span></div>'
            '<div style="font-size:12px;color:#71695A;margin-top:4px;">'
            'Copy the address and subject from here; copy the email from '
            '&ldquo;Hi&rdquo; down.</div></div>\n')
    (out / f"{_stem}.html").write_text(
        html.replace(f"<p>{greet}</p>", _box + f"<p>{greet}</p>", 1),
        encoding="utf-8")
    casey = dict(p, agent={"lookup": "Casey Samson", "display": "Casey Samson",
                           "email": "casey@caseysamson.com"})
    _write_eml(out, _stem, html, _subj, casey, to=_to)


def build_inquiry_email(p, s, out):
    html = inquiry_email_html(p)
    cfg = p.get("inquiry_email") or {}
    pre = p["prefix"]
    stem = f"{pre}_Potential_Seller_Email"
    subj = cfg.get("subject") or f"{p['address']} — Your Seller Roadmap"
    (out / f"{stem}.html").write_text(html, encoding="utf-8")
    _write_eml(out, stem, html, subj, p, to=cfg.get("to") or "")


def inquiry_email_html(p):
    """Potential seller email -- the reply to a seller inquiry (Casey, 24 Nov
    2026, on 2159 Bonaventure for Zunera and Allen). The first of the three
    seller emails: potential seller (inquiry) -> pre-meeting
    (build_prelisting_seller_email) -> post-meeting. His copy, word for word;
    the names, links and the home's own issue paragraph are filled in.
    Property file (all optional):

        "inquiry_email": {
            "seller_names": "Zunera and Allen",
            "issue": "Your home has a unique issue: ...",   -- one paragraph
            "to": "...", "subject": "..."
        }
    """
    cfg = p.get("inquiry_email") or {}
    pre = p["prefix"]
    root = (seller_host(p) or (p.get("portal_url") or "")).rstrip("/")
    roadmap = f"{root}/{pre.lower()}_roadmap" if root else f"{pre}_Roadmap.html"
    bp = buyer_portal_url(p) or buyer_host(p)
    mkt = market_snapshot_url(p)
    mk_name = re.sub(r"\s*Market$", "", ((p.get("market") or {}).get("name") or "").strip())
    names = (cfg.get("seller_names") or p.get("seller_names") or "").strip()
    addr = p["address"]
    ag = p.get("agent") or {}
    a = lambda href, text: f'<a href="{href}">{text}</a>' if href else text
    vienna = (p.get("city") or "").strip().lower() == "vienna"
    if not vienna:
        note("Potential seller email: the home is not in Vienna, so the "
             "\"over $150M per year in Vienna\" sentence is left out.")
    issue = (cfg.get("issue") or (p.get("seller_email") or {}).get("issue") or "").strip()
    # Casey, 25 Nov 2026 -- the email as he wrote it for Zunera and Allen:
    # Buyer Portal and Sample Portal as bullets, no Market Snapshot line, and
    # "CST vs Zillow vs Compass at bottom instead of track record".
    sample_url = cfg.get("sample_url") or SAMPLE_PORTAL_EMAIL
    sample = "" if buyer_portal_ready(p) else (
        f'  <li>{a(sample_url, "Sample Portal")} when we have all of the pictures and features</li>\n')
    import zillow_compare as _zc
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{addr} — potential seller email</title></head>
<body style="max-width:620px; margin:24px auto; padding:0 20px; line-height:1.5;">

<p>{names or "(Seller names)"},</p>

<p>Thanks for reaching out.</p>

<p>The Casey Samson Team, Virginia&rsquo;s #1 Luxury Team, is based out of Vienna.{" We do over $150M per year in Vienna, mostly over $1.5M." if vienna else ""}</p>

<p>The Standard for the Casey Samson Team is to sell in an average of 6 days, at highest and best
offers with no contingencies. The Pricing and Selling Strategy, outlined in our {a(roadmap, "Seller Roadmap&trade;")} make that happen regardless of market conditions. You can review before we meet.</p>

<p><b>Note:</b> Pricing in the Roadmap is based on appraisal quality comps of similar size, age,
location and time. This is only Preliminary Pricing. Final Pricing will be determined after an
inspection and conversation with you about the home&rsquo;s condition, upgrades, neighborhood comps
that may not show up on appraisers&rsquo; searches and analysis of market condition.</p>
{f"<p>{issue}</p>" if issue else ""}
<p>We can review when we meet.</p>

<p>Our Buyer Portal does a great job of Authenticating Values</p>

<ul>
  <li>{a(bp + "/" if bp else None, "Buyer Portal")} for {addr}</li>
{sample}</ul>

<p>Let me know what some good days and times to meet</p>

<p>{(ag.get("display") or ag.get("lookup") or "Casey").split()[0]}</p>

<p>{ag.get("display") or ag.get("lookup") or "Casey Samson"}<br>
REALTOR&reg; &middot; Samson Properties<br>
{ag.get("phone") or "703-508-2535"}</p>

{_zc.email_html(p, root)}
</body></html>
"""
    # One line per paragraph, so the plain-text copy does not wrap mid-sentence.
    return re.sub(r"(?<=[^>\n])\n(?=[^<\n])", " ", html)


def build_withdrawn_email(p, s, out):
    """Prospecting email to the listing agent of a withdrawn or expired
    listing: here is the portal we ran, and the strategy it lays out."""
    base = (p.get("portal_url") or "").rstrip("/")
    pre = p["prefix"]
    link = lambda f: f"{base}/{f}" if base else f
    m = dict(p["market"])
    cache_file = HERE / "market_cache.json"
    if cache_file.exists() and m.get("slug"):
        m.setdefault("keystats", json.loads(cache_file.read_text()).get(m["slug"], {}).get("keystats"))
    market_url = (f'https://cstmarketupdate.netlify.app/{m["slug"]}.html' if m.get("slug") else None)
    agent_slug = re.sub(r"[^a-z0-9]+", "-", p["agent"]["lookup"].lower()).strip("-")
    sf_ag = f'{round(p["subject"]["sf"] / 100) * 100:,}'
    assessed = f'${round(p["subject"]["assessment"] / 50_000) * 50_000:,.0f}'
    opener = p.get("withdrawn_opener") or f'I saw that {p["address"]} came off the market.'
    greeting = p.get("withdrawn_greeting", "[Name]")

    rows = [
        ("Current Seller Roadmap", link(f"{pre}_Roadmap.html"), None,
         "The roadmap is about Strategy not Price: Build confidence, create competition "
         "by driving traffic and validate Highest and Best Value for a first week sale."),
        ("Buyer Pricing Guide", link(f"{pre}_Buyer_Report.html"),
         "Authentication of values and upgrades",
         "The document buyers see. Send me the seller&rsquo;s updates and upgrades and I "
         "will build out the Premium Rating."),
        ("Seller Tracker", link(f"{pre}_Seller_Tracker.html"),
         "Total Visibility from Contract to Close",
         "Every date, dollar figure and contact for the sale in one place. It is marked "
         "for you and the seller only &mdash; not for the buyers or the buyer&rsquo;s agent."),
        ("Agent Track Record", link(f"{agent_slug}.html"),
         "Results count! Each agent has a rating",
         "My verified MLS Bright performance &mdash; listings taken, success rate and "
         "average days on market, graded."),
    ]
    if market_url:
        rows.append(("Market Snapshot", market_url, "Tracking Current Market Conditions",
                     m.get("keystats") or f'Current conditions in the {m["name"]}.'))
    rows.append(("Sample Listing Page", SAMPLE_LISTING, None,
                 "What the property page on our site looks like, with the full gallery and details."))
    rows.append(("Resources", LISTING_PROTOCOL, None,
                 "The Listing Protocol walks the seller through each stage of the sale."))

    items = []
    for title, href, tag, desc in rows:
        h = f'<b><a href="{href}">{title}</a></b>' + (f" &mdash; {tag}" if tag else "")
        items.append(f'  <p style="margin:0 0 14px 0;">{h}<br>{desc}</p>')

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{p["address"]} — withdrawn listing email</title></head>
<body style="max-width:660px; margin:24px auto; padding:0 20px;">

<p>{greeting}:</p>

<p>{opener}</p>

<p>I ran a <b><a href="{base}/">Seller Portal</a></b> for it. Based on homes of similar size
({sf_ag} SF AG), age ({p["subject"]["built"]}) and assessment ({assessed}) that have sold
within 1 mile in the past 60 days, this would have been the strategy:</p>

<ul style="margin:0 0 16px 0;">
  <li>Coming Soon list price of <b>{money(s.coming_soon)}</b>, with a fall back to
  <b>{money(s.fallback)}</b> if it tests poorly.</li>
  <li>Estimated value range between <b>{money(p["values"]["customary"])}</b> and
  <b>{money(s.expected_high)}</b>.</li>
</ul>

{market_control_paragraph(p)}<p>The portal emphasizes: <b>It&rsquo;s not about Price, it&rsquo;s about Strategy.</b></p>

<p><b>What is in the portal:</b></p>

{chr(10).join(items)}

<p>Casey</p>

</body></html>
"""
    (out / f"{pre}_Withdrawn_Email.html").write_text(html)
    _write_eml(out, f"{pre}_Withdrawn_Email", html,
               f'{p["address"]} — the strategy I would have used', p)


# -------------------------------------------------------------------- main ---
def _pdf_pages(path):
    import subprocess
    try:
        r = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def _pdf_page1_has(path, text):
    """True when `text` appears on the first page. The fitter uses it to
    tell 'the cover grew' from 'the cover pushed the band onto page two'."""
    import subprocess
    try:
        r = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(path), "-"],
                           capture_output=True, text=True)
        return text.lower() in r.stdout.lower()
    except Exception:
        return False


def render_one_pdf(out, stem):
    import newhome as _nh
    _nh.apply_dir(out)   # Casey, 13 Nov 2026: new-build wording before paper
    import asyncio
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as pw:
            exe = os.environ.get("CST_CHROME") or next(
                (str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")),
                None)
            br = await pw.chromium.launch(executable_path=exe) if exe \
                else await pw.chromium.launch()
            pg = await br.new_page()
            await pg.goto((out / f"{stem}.html").resolve().as_uri())
            await pg.wait_for_timeout(1000)
            await pg.pdf(path=str(out / f"{stem}.pdf"), format="Letter",
                         print_background=True,
                         margin={"top": "0.4in", "bottom": "0.4in",
                                 "left": "0.4in", "right": "0.4in"})
            await br.close()

    asyncio.run(go())


def fit_buyer_report(p, s, out):
    """Two pages, front and back, as full as they will go.

    First find a layout that fits at all — cover, stat strip, balanced
    upgrade columns, and the Walk To band where the property has one — then
    pour in as many of the owners' own favourite things as the page will
    take, by binary search on the count.

    Walk To is held through the whole ladder and only dropped if nothing
    fits with it: a property carrying one usually has it because the
    location is the story.
    """
    stem = f'{p["prefix"]}_Buyer_Report'
    _bp = p.get("buyer_portal") or {}
    n_loves = len(_bp.get("loves") or [])
    n_walk = len(_bp.get("walk_to") or [])

    def pages(**kw):
        build_buyer_report(p, s, out, **kw)
        if p.get("private_label"):   # Casey, 9 Nov 2026: private label
            import private_label as _pl
            _f = out / f"{stem}.html"
            _f.write_text(_pl.apply(_f.read_text(encoding="utf-8"), p["private_label"], _f.name)[0],
                          encoding="utf-8")
        render_one_pdf(out, stem)
        return _pdf_pages(out / f"{stem}.pdf") or 99

    base, label = None, ""
    # Casey, 22 Nov 2026: the Buyer Report Guide band is prominent; only on
    # the tightest layout does it shrink to a line in the masthead.
    ladder = [(True, True, "full cover", False),
              (True, False, "cover without the stat strip", False),
              (False, True, "condensed header", False)]
    # (Casey, 23 Nov 2026: the guide band and masthead link are gone; the
    # guide links sit beside each section, so the fourth rung went with them.)
    for cover, stats, lbl, gm in ladder:
        kw = dict(stats=stats, balance=True, cover=cover, guide_in_mast=gm)
        if pages(loves=0, walk=0, **kw) > 2:
            continue                       # this rung does not fit at all
        # It fits bare, so find the most Walk To places it will carry. The
        # band wants whole rows of five, so the search steps in fives and
        # then falls back to whatever odd number still fits.
        fit_walk = 0
        for n in [x for x in (n_walk, 10, 5) if x and x <= n_walk]:
            if pages(loves=0, walk=n, **kw) <= 2:
                fit_walk = n
                break
        # Keep the roomiest rung that fits, not the last one tried: a rung
        # further down the ladder is a tighter layout, so it only wins by
        # carrying more of the band.
        if base is None or fit_walk > base["walk"]:
            base, label = dict(walk=fit_walk, **kw), lbl
        if base["walk"] == n_walk:
            break                          # nothing tighter can do better
    if base is None:
        note("Buyer Pricing runs past two pages even at the tightest setting.")
        return
    if n_walk and not base["walk"]:
        label += ", Walk To dropped"

    # Page one ends with the Walk To band, and nothing below it can move up
    # past the break, so leftover room there is only fillable by the band
    # itself. Give each place its one-line description when it still fits.
    if base["walk"] and pages(loves=0, walk_notes=True, **base) <= 2:
        base["walk_notes"] = True
        label += ", Walk To with descriptions"

    # Largest number of "what the owners love" lines that still fits.
    lo, hi, best = 0, n_loves, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid == 0:
            lo = 1
            continue
        if pages(loves=mid, **base) <= 2:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if best != n_loves or label != "full cover":
        note(f"Buyer Pricing fitted to two pages: {label}, "
             f"{best} of {n_loves} owner favourites"
             + (f", {base['walk']} of {n_walk} Walk To places" if n_walk else "") + ".")
    # Finally, take up whatever page one has left. Everything below the Walk
    # To band is pinned to page two, so the only thing that can grow into
    # that space is the cover photo — until it grows far enough to push the
    # band over, at which point the previous height was the right one.
    grown = 0
    if base.get("walk") and base.get("cover"):
        px = 290
        while px < 560:
            trial = px + 24
            if pages(loves=best, cover_px=trial, **base) > 2 or \
                    not _pdf_page1_has(out / f"{stem}.pdf", "Walk To"):
                break
            px, grown = trial, trial
    if grown:
        base["cover_px"] = grown
        note(f"Buyer Pricing: cover grown to {grown}px to fill page one.")

    if pages(loves=best, **base) > 2:      # leave the file at the fitted state
        note("Buyer Pricing: final render spilled unexpectedly.")


def render_pdfs(out, prefix):
    import newhome as _nh
    _nh.apply_dir(out)
    import asyncio
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as pw:
            _exe = os.environ.get("CST_CHROME") or next(
                (str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")),
                None)
            b = await pw.chromium.launch(executable_path=_exe) if _exe \
                else await pw.chromium.launch()
            pg = await b.new_page()
            # The Marketing plan is web-only, and the Buyer Report is fitted
            # to two pages separately by fit_buyer_report.
            # The Pricing Strategy is a one-sheet document with type sized
            # to be read at arm's length, so it gets narrower margins than
            # the Roadmap to buy back the room.
            for stem, m in ((f"{prefix}_Roadmap", "0.4in"),
                            (f"{prefix}_Pricing_Strategy_Summary", "0.3in")):
                await pg.goto((out / f"{stem}.html").resolve().as_uri())
                await pg.wait_for_timeout(1200)
                await pg.pdf(path=str(out / f"{stem}.pdf"), format="Letter",
                             print_background=True,
                             margin={"top": m, "bottom": m,
                                     "left": m, "right": m})
            await b.close()

    asyncio.run(go())



def net_proceeds_html(p, tiers):
    """Casey, 21 Nov 2026: estimated Seller Net Proceeds under the Authenticated
    Values, using the Seller Tracker net sheet costs: commission (listing % +
    buyer %) x price, Grantor's Tax price x 0.003, settlement $855, deed $175,
    admin $345. "The contract price is not coming in at the estimates, so start
    with the middle number and let them fill in the actual number": one Sales
    Price fill-in, prefilled with the middle price card, with the price cards
    as quick buttons. Opt-in per property with "net_proceeds": true (or a dict
    overriding listing_pct, buyer_pct, settlement, deed, admin)."""
    cfg = p.get("net_proceeds")
    if not cfg:
        return ""
    cfg = cfg if isinstance(cfg, dict) else {}
    lp, bp = cfg.get("listing_pct", 2.5), cfg.get("buyer_pct", 2.5)
    flat = cfg.get("settlement", 855) + cfg.get("deed", 175) + cfg.get("admin", 345)
    cols = []
    for label, _st, amount, _sty, _b in tiers:
        m = re.search(r"\$([0-9][0-9,]*)", re.sub(r"<[^>]+>", "", amount))
        if m:
            cols.append((re.sub(r"\bValue\b", "Price", label), int(m.group(1).replace(",", ""))))
    if not cols:
        return ""
    mid = cols[len(cols) // 2]
    price = mid[1]
    # Casey, 27 Nov 2026: "Once we give Sales Price or contract price insert
    # that into seller net sheet." A sale beats a contract beats the estimate.
    _lead = f"Estimated at the {mid[0]}. Once a contract comes in, enter the contract price and the net recalculates."
    if p.get("sold_for"):
        price = int(p["sold_for"])
        _lead = f"At the sales price of {money(price)}."
    elif p.get("contract_price"):
        price = int(p["contract_price"])
        _lead = f"At the contract price of {money(price)}."
    comm, tax = price * (lp + bp) / 100, price * 0.003
    # Casey, 21 Nov 2026: "the quick buttons are immaterial once contracts
    # come in. They are estimates, contract prices are certain." No buttons.
    return f"""    <div class="net-proceeds" style="margin:26px auto 6px;max-width:640px;">
      <h3 style="text-align:center;font-family:'Playfair Display',Georgia,serif;font-size:22px;margin:0 0 4px;">Estimated Seller Net Proceeds</h3>
      <p style="text-align:center;font-size:14px;color:#6b6252;margin:0 0 12px;">{_lead}</p>
      <div class="table-wrap"><table>
        <tbody>
<tr><td class="k">Sales Price</td><td class="r"><input type="text" inputmode="numeric" id="npIn" value="{money(price)}" aria-label="Sales price" style="width:9.5em;text-align:right;font:inherit;font-weight:700;padding:6px 10px;border:1px solid #cdb98a;border-radius:6px;background:#fffdf6;color:#1d1a14;"></td></tr>
<tr><td class="k">Total Commission ({lp:g}% listing + {bp:g}% buyer)</td><td class="r" id="np0">&minus;{money(round(comm))}</td></tr>
<tr><td class="k">Grantor&rsquo;s Tax (0.3%)</td><td class="r" id="np1">&minus;{money(round(tax))}</td></tr>
<tr><td class="k">Settlement, Deed Preparation &amp; Admin</td><td class="r">&minus;{money(flat)}</td></tr>
<tr class="total-row" style="font-weight:700;"><td class="k">Estimated Net Proceeds</td><td class="r" id="np2">{money(round(price - comm - tax - flat))}</td></tr>
        </tbody>
      </table></div>
      <p style="font-size:12.5px;color:#7a705e;margin:10px 0 0;text-align:center;">Before the loan payoff, tax and utility prorations, and the regional recordation fees on the Title Company&rsquo;s settlement statement. Total commission shown at {lp + bp:g}%; your listing agreement governs.</p>
      <style>@media print{{#npIn{{border:none!important;background:none!important;}}}}</style>
      <script>
      (function(){{
        var LP={lp}, BP={bp}, FLAT={flat};
        var el=document.getElementById('npIn'); if(!el) return;
        function num(v){{var n=parseFloat(String(v).replace(/[^0-9.]/g,''));return isFinite(n)?n:0;}}
        function money(n){{return '$'+Math.round(n).toLocaleString('en-US');}}
        function set(id,t){{var e=document.getElementById(id);if(e)e.textContent=t;}}
        function calc(){{
          var pr=num(el.value), comm=pr*(LP+BP)/100, tax=pr*0.003;
          set('np0','\u2212'+money(comm)); set('np1','\u2212'+money(tax)); set('np2', money(pr-comm-tax-FLAT));
        }}
        el.addEventListener('input',calc);
        el.addEventListener('blur',function(){{el.value=money(num(el.value));calc();}});
      }})();
      </script>
    </div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("property_json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    p = json.loads(Path(args.property_json).read_text())
    import private_label as _plr; _plr.resolve(p)
    import newhome as _nh0
    _nh0.ON = bool(p.get("new_construction"))
    # Casey's hand-set values, folded in before anything is computed. A file
    # with no "overrides" block comes through here untouched.
    import overrides as _ov
    _ov.apply(p, note)
    p.setdefault("prefix", re.sub(r"[^A-Za-z0-9]+", "_", p["address"]).strip("_"))
    p.setdefault("listing_url",
                 re.sub(r"[^A-Za-z0-9]", "", p["address"]) + ".com")
    p.setdefault("storage_key", "cst-" + p["prefix"].lower() + "-tracker-v1")
    # A property can be run with no market snapshot at all. Normalise the block
    # once here so every downstream reader sees an empty dict rather than a
    # missing key -- each of them already degrades correctly on a missing slug.
    if not isinstance(p.get("market"), dict):
        p["market"] = {}
    p.setdefault("agent", dict(DEFAULT_AGENT))
    import market_compare as _mc
    _mc.build(p, note)
    # Casey, 7 Nov 2026: model-priced comps table -- Customary on the subject
    # row, each comp's PPSF adjusted for age and size.
    from pricing_model import fill_comp_table as _fct
    _fct(p)

    v = p["values"]
    s = compute(dated=v["dated"], customary=v["customary"],
                customary_list=v["customary_list"], premium=v.get("premium", 0),
                upgrades=v.get("upgrades", 0), discount=v.get("discount", 0),
                discount_reason=v.get("discount_reason", ""),
                coming_soon_override=v.get("coming_soon_override"))

    out = Path(args.out or (HERE / "output" / p["prefix"]))
    out.mkdir(parents=True, exist_ok=True)

    # First, so the Roadmap's Current Market Conditions, the Pricing Strategy
    # Summary's market tiles and the posture that sets Preview and Coming Soon
    # all read this property's own market.
    model_competition_rows(p)
    build_local_snapshot(p, out, note=note, buyer_url=buyer_portal_url(p))
    # Casey, 1 Nov 2026 (702 Ware): "Ware St has coming soon at $1.749 then
    # if more than 5 showings you have $1.799. You never go up from Coming
    # Soon." When the buyer's-market safe haven moves Coming Soon, every page
    # -- Roadmap, launch ladder, email -- carries the moved price, not just
    # the Pricing Strategy Summary.
    _sf0 = strategy_figures(p, s)
    if _sf0.get("safe_haven"):
        s.coming_soon = _sf0["coming_soon"]
        s.fallback = _sf0["fallback"]
        s.deep = _sf0["deep"]
    build_roadmap(p, s, out)
    (out / "_guide_notes.json").write_text(json.dumps(GUIDE_NOTES), encoding="utf-8")
    build_strategy_summary(p, s, out)
    build_strategy_email(p, s, out)
    build_followup_email(p, s, out)
    build_buyer_report(p, s, out)
    build_marketing(p, s, out)
    build_tracker(p, s, out)
    build_index(p, out)
    # The nav page the seller opens is the v2 design; the original card
    # stack is kept alongside it as index_classic.html.
    (out / "index.html").rename(out / "index_classic.html")
    # Casey, 21 Nov 2026: Move Up (or Down) Calculator gets its own channel.
    import move_up as _mu
    (out / f"{p['prefix']}_Move_Up.html").write_text(_mu.page(p), encoding="utf-8")
    from build_index_v2 import build_index_v2
    build_index_v2(p, s, out)
    build_index_dynamic(p, s, out)
    # Casey, 27 Oct 2026: Contract Analytics on the seller portal page.
    # Casey, 29 Oct 2026: "Take this section out" -- "contract_analytics_on_portal": false keeps the data but leaves the table off.
    import market_map as _mm0
    _mm0.add_mss_map(p, out, note=note)
    if p.get("market_map"):
        # Casey, 31 Oct 2026: maps on the Roadmap, not the portal page.
        import market_map as _mm
        p["_sold_gauges"] = sold_gauges(p)
        _mm.add_to_roadmap(p, out, note=note)
    if p.get("contract_analytics") and p.get("contract_analytics_on_portal", True):
        import contract_analytics as _ca
        _ca.add_to_index(p, out, note=note)
    # Casey, 28 Oct 2026: the Contract Summary page, linked under the Roadmap.
    if p.get("contract_summary"):
        import contract_summary as _cs
        _cs.build(p, out, note=note)
        _cs.link_on_index(p, out)
    build_email(p, s, out)
    if p.get("listing_status") in ("withdrawn", "expired"):
        build_withdrawn_email(p, s, out)
    # Casey, 20 Oct 2026: recovery listings get his "Additional Resources
    # for Samson Listings" email to the listing agent.
    # Casey, 21 Oct 2026, on 1324 Towlston (built as a new listing): "need
    # emails for towlston" -- "recovery_email": true builds it on any portal.
    # Casey, 27 Oct 2026: the short realtor email on every portal.
    build_recovery_agent_email(p, s, out)
    # Casey, 22 Oct 2026: pre-listing email to the sellers (2838 Cedar).
    # Casey, 24 Nov 2026: three seller emails -- potential seller (inquiry),
    # pre-meeting, post-meeting. The potential seller email goes with every
    # listing that is not already on the market with someone else.
    if p.get("inquiry_email") or p.get("listing_status") not in ("recovery", "withdrawn", "expired", "relaunch"):
        build_inquiry_email(p, s, out)
    if p.get("prelisting_email"):
        build_prelisting_seller_email(p, s, out)
    # Both sites ship an index.html, so each folder says out loud which
    # Netlify site it belongs to — dropping one on the other's site silently
    # replaces a live page.
    (out / "DEPLOY.txt").write_text(
        "SELLER PORTAL  —  private, for the seller\n"
        f'{p["address"]}, {p["city"]}, {p["state"]}\n\n'
        f'Deploy this folder to:  {seller_host(p) or "(no slug from the address)"}\n\n'
        "Do NOT deploy this folder to the Buyer Portal site"
        + (f'\n({buyer_portal_url(p)})\n' if buyer_portal_url(p) else "\n")
        + "\nThis folder contains the Roadmap, the Marketing plan, the Seller\n"
          "Tracker and the pricing strategy. It is not for buyers.\n")
    _c = (p.get("buyer_portal") or {}).get("contacts") or {}
    if _c.get("photo"):
        _bs = Path((p.get("buyer_portal") or {}).get("asset_dir", "."))
        if not _bs.is_absolute():
            _bs = HERE / _bs
        if (_bs / _c["photo"]).exists():
            shutil.copy(_bs / _c["photo"], out / _c["photo"])
        else:
            note(f'Agent card photo MISSING: {_c["photo"]} not found in {_bs}.')
    shutil.copy(TPL / "Gold_Standard_Logo.png", out / "Gold_Standard_Logo.png")
    import engine as _eng
    if _eng.enabled(p) and (TPL / _eng.IMG).exists():
        shutil.copy(TPL / _eng.IMG, out / _eng.IMG)
    shutil.copy(TPL / "Marketing_Reel.png", out / "Marketing_Reel.png")
    _trf = track_record_file(p)
    if (TPL / _trf).exists():
        shutil.copy(TPL / _trf, out / _trf)
    else:
        note(f"Track record page MISSING: templates/{_trf} is not there, so "
             "the portal has no track record to link.")
    # Sweep out any OTHER track-record page left behind by an earlier build.
    # The output folder is never cleaned, so a property that switched records
    # kept shipping the old one — an orphan file the seller could still open,
    # showing a different set of sales from the rest of the portal.
    for _old in TRACK_RECORD_COPY:
        if _old != _trf and (out / _old).exists():
            (out / _old).unlink()
            note(f"Removed stale {_old} from the portal — this property now "
                 f"runs on {_trf}.")
    # The example Buyer Pricing Report rides along so the button on the
    # Buyer Portal — Example card opens a real file. Once that card is gone
    # (20 Oct: pictures and premiums on the home's own portal) nothing links
    # to it, so it comes out -- it is another listing's 854 KB document
    # sitting in this seller's folder with no way to reach it, and a copy
    # left behind from an earlier build has to be swept too.
    _ex_pdf = TPL / EXAMPLE_BUYER_PDF
    if buyer_portal_ready(p):
        _stale = out / EXAMPLE_BUYER_PDF
        if _stale.exists():
            _stale.unlink()
            note(f"Removed {EXAMPLE_BUYER_PDF} from the portal — the example "
                 "card is gone, so nothing linked to it.")
    elif _ex_pdf.exists():
        shutil.copy(_ex_pdf, out / EXAMPLE_BUYER_PDF)
    elif True:
        note(f"Example Buyer Report MISSING: templates/{EXAMPLE_BUYER_PDF} is "
             "not there, so the button on the example card would 404. Copy "
             f"{EXAMPLE_BUYER_HOME}'s Buyer Report into templates/ and rebuild.")

    # Copy any referenced image assets in from the property's asset folder.
    comp_pics = [r[7] for r in p["comps"]["rows"] if len(r) > 7 and r[7]]
    wanted = [x for x in ([p.get("hero_photo")] + (p.get("photos") or [])
                          + comp_pics) if x]
    if wanted:
        src_dir = Path(p.get("asset_dir", "."))
        for fn in wanted:
            src = src_dir / fn
            if src.exists():
                shutil.copy(src, out / fn)
            else:
                note(f"Asset MISSING: {fn} not found in {src_dir} — the page will "
                     "reference a broken image until you add it.")
    # Casey, 19 Oct 2026: a 72-hour preview carries its expiry on every page
    # until the realtor pays. Stamped after the documents are written and
    # before the PDFs are rendered, so the mark is in the printed sheets too.
    # fit_buyer_report rewrites its own HTML while fitting pages, so that one
    # is stamped again afterwards and its PDF re-rendered from the stamped
    # file. The mark is a fixed layer and changes no pagination.
    # Casey, 19 Oct 2026: an unpaid portal carries "Sample, Property of Casey
    # Samson Team" across the seller portal, the Summary and the Buyer
    # Report. Marked when "sample" is set and actively stripped when it is
    # not, so clearing the field and rebuilding always produces the paid
    # version — including pages this build only copies rather than rewrites.
    _sample = bool(p.get("sample"))
    _text = p.get("sample_text", watermark.TEXT)
    watermark.apply_folder(out, _sample, _text, note=note)
    # Marker circles go on before the PDFs are printed, so the Pricing
    # Strategy Summary PDF and the Roadmap PDF carry them too (Casey, 8 Nov).
    try:
        from marker_circle import apply_dir as _mk0
        _mk0(out)
    except Exception as _e:
        print(f"\n  !! marker circles not applied before PDFs: {_e}")
    # Casey, 9 Nov 2026: private label -- another agent, powered by CST Pricing.
    if p.get("private_label"):
        import private_label as _pl
        _pl.apply_dir(out, p["private_label"])
        _pl.add_letterhead(out, p["private_label"])
    if not args.no_pdf:
        render_pdfs(out, p["prefix"])
        fit_buyer_report(p, s, out)
        # fit_buyer_report rewrites its own HTML while fitting pages, so the
        # mark is reapplied and its PDF re-rendered from the marked file.
        _br = out / f'{p["prefix"]}_Buyer_Report.html'
        if _sample and _br.exists():
            _br.write_text(watermark.stamp(
                watermark.unstamp(_br.read_text(encoding="utf-8")), True, _text),
                encoding="utf-8")
            render_one_pdf(out, f'{p["prefix"]}_Buyer_Report')
        # Both locks go on last. The no-print CSS empties the page at the
        # printer, and Chrome renders these PDFs through that same path, so
        # stamping it in any earlier would have produced blank PDFs.
        watermark.lock_pdfs(out, _sample, p["prefix"], note=note)
    watermark.lock_print(out, _sample, note=note)
    # Casey, 21 Oct 2026: "When 3 days goes by, I want to Disable all links."
    # Last of all, after the PDFs, so no PDF is ever rendered from a page
    # whose clock has run out.
    # Casey, 21 Oct 2026: market sections follow the weekly MSS live. Added
    # after the PDFs, so a PDF is always the figures it was built with.
    _nl = add_live_loader(out)
    if _nl:
        note(f"Live market: {_nl} page(s) follow {LIVE_FEED} -- the weekly "
             "MSS refresh updates them without a rebuild. Prices do not move.")
    elif (p.get("market") or {}).get("slug"):
        note("Live market: OFF -- this portal's figures are not the MSS's own "
             "(a Local Market Snapshot, or no cached report), so they stay as built.")
    import expiry
    expiry.apply_folder(out, expiry.deadline(p, args.property_json, note=note),
                        note=note)
    print(f"\n{p['address']} -> {out}")
    print(f"  anchor basis    {s.anchor_basis_label} {money(s.anchor_basis)}")
    print(f"  coming soon     {money(s.coming_soon)}  (grid line {money(s.anchor)})")
    print(f"  fall back       {money(s.fallback)}"
          f"{'  [threshold pair]' if s.fallback_is_pair else '  [standard step]'}")
    print(f"  expected sale   {abbrev(s.expected_low)}-{abbrev(s.expected_high)}")
    print(f"  money at risk   {money(s.money_at_risk)}")
    print(f"  alert           " + (f"{money(s.alert['major'])}, gap {money(s.alert['gap'])}"
                                   if s.alert else "none"))
    for w in s.warnings:
        print(f"\n  !! {w}")
    if NOTICES:
        print("\n  Omissions:")
        for m in NOTICES:
            print(f"    - {m}")
    # Casey, 8 Nov 2026: marker circle around the 74% and the 30-day number.
    try:
        from marker_circle import apply_dir as _mk
        _mk(out)
    except Exception as _e:
        print(f"\n  !! marker circles not applied: {_e}")
    if p.get("private_label"):
        import private_label as _pl
        _n, _left = _pl.apply_dir(out, p["private_label"])
        _pl.copy_assets(out, p["private_label"])
        _lh = _pl.add_letterhead(out, p["private_label"])
        print(f"\n  private label    {_pl._brand(p['private_label'])}, {_pl.TAG} ({_n} pages, letterhead on {_lh})")
        for _f, _l in _left.items():
            print(f"    !! team name still on {_f}: {_l[:3]}")
    # Casey, 13 Nov 2026: new-construction wording on every page.
    import newhome as _nh1
    _nh1.apply_dir(out)
    # Casey, 14 Nov 2026: "Save to my phone" / "Text me this link" bar on the
    # seller index and the Roadmap. On by default; off on the Sample.
    if p.get("save_bar", not p.get("sample")) and "samplesellerportal" not in (p.get("portal_url") or ""):
        try:
            import bookmark as _bm
            _bm.apply(out, p, seller_host(p) or p.get("portal_url"), note=note)
        except Exception as _e:
            print(f"\n  !! save bar not applied: {_e}")
    # Casey, 7 Nov 2026: "When you are doing recovery or new listing generate
    # a spreadsheet with your math." Every property priced with the model
    # (a "pricing_model" block) gets its Pricing Engine workbook in the folder.
    if p.get("pricing_model"):
        try:
            from pricing_sheet import build as _ps
            # Kept beside the site folder, not in it, so the math is never
            # published to Netlify with the portal.
            _x = Path(out).parent / f'{p["prefix"]}_Pricing_Math.xlsx'
            _ps(p, str(_x))
            print(f"  pricing math    {_x.name}")
        except Exception as _e:
            print(f"\n  !! Pricing math workbook NOT built: {_e}")
    print("\n  Next: python3 assign_agent.py \"<Agent Name>\" " + str(out))


if __name__ == "__main__":
    main()
    # Casey, 22 Nov 2026: "when I create a portal, lets create the guides as
    # well" -- each portal gets its own four guides from its own pages.
    try:
        import json as _j, property_guides as _pg
        _a = [x for x in sys.argv[1:] if x.endswith(".json")]
        if _a:
            _made = _pg.build(_j.loads(Path(_a[0]).read_text()), ("roadmap", "mss", "moveup", "buyer"))
            print("  Guides:", ", ".join(_made) or "none")
    except Exception as _e:
        print("  Guides: skipped --", _e)
    # Casey, 24 Nov 2026: town home markets link to the town home MSS.
    try:
        import json as _j, townhome_mss as _th
        _a = [x for x in sys.argv[1:] if x.endswith(".json")]
        if _a:
            _fx = _th.fix_outputs(_j.loads(Path(_a[0]).read_text()))
            if _fx:
                print(f"  Town home MSS: links pointed at {_th.TH_SITE} in {len(set(_fx))} file(s)")
    except Exception as _e:
        print("  Town home MSS: skipped --", _e)

    # Casey, 26 Nov 2026: every home is saved to GitHub after each build.
    try:
        import save_to_github as _sg
        _a = [x for x in sys.argv[1:] if x.endswith(".json")]
        if _a:
            _sg.save(_a[0], "seller build")
    except Exception as _e:
        print("  !!! GitHub save skipped --", _e)
