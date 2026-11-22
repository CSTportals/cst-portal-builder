#!/usr/bin/env python3
"""Per-property guides (Casey, 22 Nov 2026: "when I create a portal, lets
create the guides as well").

Each portal gets its own four guides, built from screenshots of ITS pages and
written with ITS numbers:

    <prefix>_Roadmap_Guide.html     from output/<prefix>/<prefix>_Roadmap.html
    Buyer_Portal_Guide.html         from output/<prefix>_Buyer/index.html
    Market_Snapshot_Guide.html      from mss_pages/<market slug>.html
    Move_Up_Guide.html              from output/<prefix>/<prefix>_Move_Up.html

The guides are written into the seller site (and the Buyer Portal Guide into
both buyer sites), replacing the generic copies. Maps are left out of the
screenshots: map tiles do not load in the build workspace.

    python3 property_guides.py properties/X.json
"""
import base64
import io
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
TPL = ROOT / "templates" / "guides" / "Buyer_Portal_Guide.html"
FOOT = "The Casey Samson Team &middot; 703-508-2535 &middot; Casey@caseysamson.com"


def money(x):
    return f"${int(round(x)):,}"


def _head(title):
    s = TPL.read_text(encoding="utf-8")
    head = s[:s.index("</style></head>")]
    return re.sub(r"<title>.*?</title>", f"<title>{title}</title>", head, count=1, flags=re.S)


def _emb(png):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width > 1400:
        im = im.resize((1400, int(im.height * 1400 / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=80, optimize=True)
    return base64.b64encode(b.getvalue()).decode()


def _page(title, lede, sections, brand):
    cards = ""
    for k, (png, t, sub, ps) in enumerate([s for s in sections if s[0]], 1):
        cards += (f'<section class="g"><div class="n">{k}</div><div class="txt"><h2>{t}</h2>'
                  f'<p class="sub">{sub}</p>' + "".join(f"<p>{x}</p>" for x in ps) + "</div>"
                  f'<figure><img src="data:image/jpeg;base64,{_emb(png)}" alt="{re.sub("<[^>]+>", "", t)}"></figure></section>\n')
    return (_head(f"{title} &mdash; {brand}") + "</style></head><body>\n"
            f'<header><div class="k">{brand}</div><h1>{title}</h1><p>{lede}</p></header>\n'
            f"<main>\n{cards}</main>\n<footer><b>Questions?</b>{FOOT}</footer>\n</body></html>")


def _shots(page_url, wanted, viewport=(1280, 900), before=None, max_h=1500):
    """Screenshot each section that starts with an <h2> in `wanted`, down to
    the next <h2>. Returns {heading: png bytes} for the ones found. Leaflet
    maps inside a section are hidden first."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": viewport[0], "height": viewport[1]}, device_scale_factor=1.25)
        pg.goto(page_url)
        pg.wait_for_timeout(1500)
        if before:
            pg.evaluate(before)
            pg.wait_for_timeout(300)
        pg.add_style_tag(content=".leaflet-container,.rmm-map,#locmap,.locmap,.mss-map,[id*=map]{display:none!important}"
                                 " .rmm-key,.locmap-arrows{display:none!important}")
        pg.wait_for_timeout(300)
        H = pg.evaluate("document.documentElement.scrollHeight")
        tops = pg.evaluate("""() => [...document.querySelectorAll('h1,h2')].map(e =>
            [e.textContent.trim(), e.getBoundingClientRect().top + scrollY])""")
        ys = sorted(y for _, y in tops)
        for name in wanted:
            hit = [y for t, y in tops if t.lower().startswith(name.lower())]
            if not hit:
                continue
            y0 = hit[0]
            nxt = [y for y in ys if y > y0 + 5]
            y1 = min(nxt[0] if nxt else H, y0 + max_h)
            out[name] = pg.screenshot(full_page=True, clip={"x": 0, "y": max(0, y0 - 40),
                                                            "width": viewport[0], "height": y1 - y0 + 30})
        out["_top"] = pg.screenshot()
        b.close()
    return out


def roadmap_guide(p, s_dir):
    pre = p["prefix"]
    v = p["values"]
    page = s_dir / f"{pre}_Roadmap.html"
    if not page.exists():
        return None
    names = ["Appraisal-Quality Comparable Analysis", "Price Authenticated", "Moving the Needle",
             "Current Competition", "CST Pricing Strategy", "Preview", "Coming Soon", "Predictive Analysis"]
    sh = _shots(page.as_uri(), names)
    _nf = s_dir / "_guide_notes.json"
    notes = json.loads(_nf.read_text()) if _nf.exists() else {}
    cs = v.get("coming_soon_override") or v.get("customary")
    fb, dp = v.get("fallback_override"), v.get("deep_override")
    addr = p["address"]
    secs = [
        (sh.get("_top"), "Your Roadmap at a Glance", addr,
         [f"The top of your Roadmap carries the plan for {addr}: the recommended price, the expected sale "
          "price and the authenticated range from Customary to Premium Value.",
          "Pricing is preliminary until a trained Realtor has walked the home. Final values depend on "
          "condition, upgrades and any lot premium or discount."]),
        (sh.get(names[0]), "Appraisal-Quality Comparable Analysis", "The sales an appraiser would use",
         [f"Your home sits at the top of the table, built {p['subject'].get('built')}, "
          f"{p['subject'].get('sf'):,} square feet, with the average of the comparable sales right under it.",
          "Each comparable is a real closed sale of similar size, age, location and time, so the price holds "
          "up when the buyer&rsquo;s lender orders the appraisal."]),
        (sh.get(names[1]), "Price Authenticated by the CST Pricing Team", "The pricing engine",
         ["Cylinders 1&ndash;6 run on every home: age and size, price range, price per square foot, "
          "assessment, market anomalies and inflation. Cylinders 7&ndash;10 fire only when they apply:",
          "<b>Neighborhood (7)</b> analyzes neighborhood sales over the past 5 years. "
          "<b>Premium/Discount (8)</b> compares whether the seller paid a premium or a discount at the time "
          "of purchase. <b>Extraordinary Upgrades (9)</b> applies when upgrades have been made that move the "
          "needle to a different price range. <b>Detriment (10)</b> is an adjustment for issues with the lot "
          "or functionality.",
          f"Your values: <b>Dated {money(v['dated'])}</b>, <b>Customary {money(v['customary'])}</b>, "
          f"<b>Premium {money(v['premium'])}</b>. Historically, CST listings sell between Customary and "
          "Premium Values. Sometimes more."]),
        (sh.get(names[2]), "Moving the Needle&trade; Guide", "What raises the price, and what lowers it",
         ["With hundreds of thousands of dollars at risk, strategic improvements are critical&mdash;and a "
          "Casey Samson Team specialty.",
          "The right cosmetic improvements can deliver a substantial increase in perceived value at a "
          "fraction of the cost."]),
        (sh.get(names[3]), "Current Competition", "Who you are up against",
         [f"Every home {addr} is competing with today, and how the market is moving: the share under "
          "contract, Market Strength and Market Momentum."] + ([notes["uc30"]] if notes.get("uc30") else [])),
        (sh.get(names[4]), "CST Pricing Strategy", "Where the price goes, and why",
         [f"The strategy places the home at the first buyer threshold under its Customary Value of "
          f"{money(v['customary'])}, so it shows up for every buyer searching that range."]),
        (sh.get(names[5]), "Preview", "The home goes public before it goes live",
         ["Within two days of a signed Listing Agreement the home is posted on Preview with photographs and "
          "property information on Zillow, Homes.com, Samson Properties and more."]),
        (sh.get(names[6]), "Coming Soon", f"Full marketing at {money(cs)}",
         [f"The home goes on the MLS as Coming Soon at {money(cs)}, with full photography and marketing."]),
        (sh.get(names[7]), "Predictive Analysis Sets the Price", "The first week decides the next move",
         ["<b>Five or more showings:</b> hold the price."
          + (f" <b>Fewer than five:</b> move to {money(fb)}." if fb else "")
          + (f" <b>Pulling the Rip Cord, 0 showings:</b> {money(dp)}." if dp else ""),
          "Every price is set in advance, so there are no surprises."]),
    ]
    return _page("Your Seller Roadmap Guide",
                 f"{addr} &mdash; what each part of your Gold Standard Seller Roadmap&trade; shows you.",
                 secs, _brand(p))


def buyer_guide(p, b_dir):
    page = b_dir / "index.html"
    if not page.exists():
        return None
    v = p["values"]
    names = ["Authenticated Values", "Market Snapshot", "Amenities and Transportation", "Move Up Calculator"]
    sh = _shots(page.as_uri(), names,
                before="(()=>{var a=document.getElementById('muVal'),d=document.getElementById('muDebt');"
                       "if(a){a.value='$1,200,000';d.value='$400,000';"
                       "['muVal','muDebt'].forEach(i=>document.getElementById(i).dispatchEvent(new Event('input')));}})()")
    addr = (p.get("buyer_portal") or {}).get("display_address") or p["address"]
    secs = [
        (sh.get("_top"), "Your First Look", addr,
         ["The front door to everything you need to know about the home: photography, values, documents and "
          "how to write an offer, all in one place.",
          "Tap <b>Pricing Report</b> for the printable Buyer Pricing Report. Scan the <b>QR code</b> to put "
          "this portal on your phone."]),
        (sh.get(names[0]), "Authenticated Values&trade;", "How the price was set",
         [_lp_line(p),
          f"<b>Customary Value {money(v['customary'])}</b> is what a home of this standard commands. "
          f"<b>Premium Value {money(v['premium'])}</b> is what it commands when upgrades, finishes and "
          "presentation exceed the standard.",
          "Historically, CST listings sell between Customary and Premium Values (sometimes more)."]),
        (sh.get(names[1]), "Market Snapshot", "Every home it is competing with",
         ["Every home on the market against this one, and what each is asking, so you can compare value."]),
        (sh.get(names[2]), "Amenities and Transportation", "How far everything is",
         ["Drive times to schools, shopping, dining, parks, the Metro and the airports."]),
        (sh.get(names[3]), "Move Up Calculator", "What your current home puts toward this one",
         ["Enter your current home&rsquo;s price and what you owe. Your walk out the door proceeds become the "
          "down payment, after closing costs.",
          "Switch between <b>Customary</b> and <b>Premium</b> to see the payment difference. Tap <b>Math</b> "
          "for every number."]),
    ]
    return _page("Your Buyer Portal Guide",
                 f"{addr} &mdash; what each part of the portal shows you, and how to use it.", secs, _brand(p))


def _lp_line(p):
    """Casey, 22 Nov 2026: "The List Price reflects where the largest Buyer
    Pool is for this home." """
    return "The List Price reflects where the largest Buyer Pool is for this home."


def buyer_report_guide(p, s_dir):
    """Casey, 22 Nov 2026: a Guide to Understanding the Buyer Report, linked
    prominently from the report itself."""
    page = s_dir / f"{p['prefix']}_Buyer_Report.html"
    if not page.exists():
        return None
    v = p["values"]
    names = ["Comparable Property Analysis", "Authenticated Values"]
    sh = _shots(page.as_uri(), names)
    secs = [
        (sh.get("_top"), "The Buyer Pricing Report", p["address"],
         ["A one-page summary for buyers and their agents: the home, the sales that authenticate its value, "
          "and the value range itself. It is displayed at the listing and at open houses, and prints as a PDF."]),
        (sh.get(names[0]), "Comparable Property Analysis", "The sales behind the value",
         ["Each comparable is a real closed sale of similar size, age, location and time &mdash; the same tests "
          "an appraiser applies &mdash; with the averages by age and size and by price range.",
          "Compare the home&rsquo;s year built, size and lot with the sales to see where it stands."]),
        (sh.get(names[1]), "Authenticated Values&trade;", "What the home is worth",
         [_lp_line(p),
          f"<b>Customary Value {money(v['customary'])}</b> is what a home of this standard commands. "
          f"<b>Premium Value {money(v['premium'])}</b> is what it commands when upgrades, finishes and "
          "presentation exceed the standard.",
          "Historically, CST listings sell between Customary and Premium Values (sometimes more)."]),
    ]
    return _page("Guide to Understanding the Buyer Report",
                 f"{p['address']} &mdash; what each part of the Buyer Pricing Report tells you.", secs, _brand(p))


def mss_guide(p):
    slug = (p.get("market") or {}).get("slug")
    page = ROOT / "mss_pages" / f"{slug}.html" if slug else None
    if not page or not page.exists():
        return None
    mk = re.sub(r"\s*Market$", "", (p.get("market") or {}).get("name", "your market"))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1.25)
        pg.goto(page.as_uri())
        pg.wait_for_timeout(1500)
        pg.add_style_tag(content=".leaflet-container,[id*=map]{display:none!important}")
        pg.wait_for_timeout(300)
        tops = pg.evaluate("""() => [...document.querySelectorAll('h1,h2')].map(e => e.getBoundingClientRect().top + scrollY)""")
        H = pg.evaluate("document.documentElement.scrollHeight")
        ys = sorted(tops) + [H]
        shots = []
        for i in range(len(ys) - 1):
            y0, y1 = max(0, ys[i] - 40), min(ys[i + 1], ys[i] + 1300)
            shots.append(pg.screenshot(full_page=True, clip={"x": 0, "y": y0, "width": 1280, "height": y1 - y0}))
        b.close()
    text = [
        ("Who Controls the Market", "The headline answers it in one line",
         [f"The {mk} Market Snapshot opens with the answer: buyers, sellers or neutral, and the two numbers "
          "behind the call. Updated every week."]),
        ("How Homes Are Selling", "Success rate, days on market and price to list",
         ["Success rate, days on market and sale price to list price for the last 90 days, read red to green, "
          "with the most recent sales and withdrawals below."]),
        ("Where the Market Is Heading", "Momentum: what is happening right now",
         ["How many homes are under contract now, how many of the last 30 days&rsquo; listings already have a "
          "buyer, and how long the rest have waited. This sets how conservatively we price."]),
        ("The Year So Far", "Against last year",
         ["Year-to-date inventory, sales and success rate, placed on one scale from Buyers to Sellers, then the "
          "CST track record side by side with the rest of the market."]),
    ]
    secs = [(shots[i] if i < len(shots) else None, *text[i]) for i in range(len(text))]
    return _page("Your Market Snapshot Guide",
                 f"The {mk} Market Snapshot &mdash; what each part tells you, and how to read it.", secs, _brand(p))


def moveup_guide(p, s_dir):
    page = s_dir / f"{p['prefix']}_Move_Up.html"
    if not page.exists():
        return None
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=1.25)
        pg.goto(page.as_uri())
        pg.wait_for_timeout(800)
        closed = pg.screenshot(full_page=True)
        for a in pg.query_selector_all(".mu-arrow"):
            a.click()
        pg.wait_for_timeout(300)
        math = pg.screenshot(full_page=True)
        walk = pg.inner_text("#muWalk")
        b.close()
    v = p["values"]
    secs = [
        (closed, "Sell, Then Buy", "Your home on the left, your next one on the right",
         [f"The Sell side starts at your home&rsquo;s values: tap Dated, Customary or Premium, or type a "
          f"contract price. At {money(v.get('customary_unadjusted') or v['customary'])} with no debt, you "
          f"would walk out the door with about {walk}.",
          "Enter what you owe and your next home&rsquo;s price. The three payments use a 2-1 buydown."]),
        (math, "The Math", "Tap the arrow to see every number",
         ["Commission, Grantor&rsquo;s Tax and fees on the sale; lender fees, title, prepaids and the buydown on "
          "the purchase; the loan amount, taxes and insurance. Estimates for planning only."]),
    ]
    return _page("Your Move Up (or Down) Calculator Guide",
                 f"{p['address']} &mdash; what your sale puts toward your next home.", secs, _brand(p))


def _brand(p):
    pl = p.get("private_label") or {}
    if pl:
        return f"{pl.get('team_name') or pl.get('name')} &middot; Powered by CST Pricing"
    return "The Casey Samson Team &mdash; The Gold Standard of Pricing Strategy"


def build(p, which=("roadmap", "mss", "moveup", "buyer")):
    import private_label as _pl
    _pl.resolve(p)
    pre = p["prefix"]
    s_dir = ROOT / "output" / pre
    b_dir = ROOT / "output" / f"{pre}_Buyer"
    made = []
    if "roadmap" in which and (h := roadmap_guide(p, s_dir)):
        (s_dir / f"{pre}_Roadmap_Guide.html").write_text(h, encoding="utf-8"); made.append("roadmap")
    (s_dir / "_guide_notes.json").unlink(missing_ok=True)   # build-time only, not for the site
    if "mss" in which and (h := mss_guide(p)):
        (s_dir / "Market_Snapshot_Guide.html").write_text(h, encoding="utf-8"); made.append("market snapshot")
    if "moveup" in which and (h := moveup_guide(p, s_dir)):
        (s_dir / "Move_Up_Guide.html").write_text(h, encoding="utf-8"); made.append("move up")
    if "roadmap" in which and (h := buyer_report_guide(p, s_dir)):
        for d in (s_dir, b_dir, ROOT / "output" / f"{pre}_Buyer_Small"):
            if d.exists():
                (d / "Buyer_Report_Guide.html").write_text(h, encoding="utf-8")
        made.append("buyer report")
    if "buyer" in which and (h := buyer_guide(p, b_dir)):
        for d in (s_dir, b_dir, ROOT / "output" / f"{pre}_Buyer_Small"):
            if d.exists():
                (d / "Buyer_Portal_Guide.html").write_text(h, encoding="utf-8")
        made.append("buyer portal")
    return made


if __name__ == "__main__":
    prop = json.loads(Path(sys.argv[1]).read_text())
    print("guides:", ", ".join(build(prop)) or "none")
