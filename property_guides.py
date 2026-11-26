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


def slug(t):
    import html as _h
    t = _h.unescape(re.sub("<[^>]+>", "", t)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def _target(links, t):
    """The portal section a guide section explains: links maps a guide-title
    prefix to the portal heading prefix (or 'css:...' for a block with no
    heading)."""
    plain = slug(t)
    for k, v in (links or {}).items():
        if k != "*" and plain.startswith(slug(k)):
            return v
    return (links or {}).get("*")


BACK_CSS = (
            ".avx{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:14px 0 0}"
            ".avx .c{background:#fff;border:1px solid #E4DCC8;border-radius:10px;padding:16px 18px}"
            ".avx .c.mid{border-color:#B8902F;box-shadow:0 4px 14px rgba(138,106,46,.10)}"
            ".avx .k{font:700 12px Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:#71695A}"
            ".avx .st{color:#B8902F;font-size:15px;margin:2px 0 6px}"
            ".avx .row{display:flex;gap:14px;align-items:flex-start}"
            ".avx .v{font:700 24px 'Playfair Display',Georgia,serif;color:#8A6A2E;white-space:nowrap}"
            ".avx .d{font-size:14.5px;line-height:1.5;color:#3a332a;margin:0}"
            ".avx-risk{margin:16px auto 0;max-width:640px;background:#F3EAD3;border:1px solid #D9C79A;border-radius:10px;"
            "padding:14px 20px;display:flex;gap:18px;align-items:center}"
            ".avx-risk .v{font:700 24px 'Playfair Display',Georgia,serif;color:#8A6A2E;white-space:nowrap}"
            "@media(max-width:820px){.avx{grid-template-columns:1fr}}"
            ".gback{display:inline-block;margin-top:14px;font:700 15px Georgia,serif;color:#1F2A44;"
            "text-decoration:none;border-bottom:2px solid #B8902F;padding-bottom:2px}"
            ".gback:hover{color:#8A6A2E}"
            ".gtop{display:inline-block;margin-top:14px;font:700 15px Georgia,serif;color:#F0E4C4;"
            "text-decoration:none;border-bottom:2px solid #B8902F;padding-bottom:2px}")


def _page(title, lede, sections, brand, links=None, back=None):
    """links / back (Casey, 23 Nov 2026): every guide section the portal links
    to gets an id, and a "Back to <portal>" link to that section of the
    portal. back = (label, href placeholder) -- the href is filled per site."""
    cards = ""
    for k, sec in enumerate([s for s in sections if s[0]], 1):
        png, t, sub, ps = sec[:4]
        extra = sec[4] if len(sec) > 4 else ""
        if isinstance(png, tuple) and png[0] == "HTML":
            tg = _target(links, t) if back else None
            tg = tg[7:] if tg and tg.startswith("anchor:") else tg
            sid = f' id="g-{slug(tg)}"' if tg else ""
            bl = (f'<a class="gback" href="__BACK__#s-{slug(tg)}">&larr; Back to {back}</a>' if tg else
                  (f'<a class="gback" href="__BACK__">&larr; Back to {back}</a>' if back else ""))
            cards += (f'<section class="g wide"{sid}><div class="n">{k}</div><div class="txt" style="max-width:none;">'
                      f'<h2>{t}</h2><p class="sub">{sub}</p>' + "".join(f"<p>{x}</p>" for x in ps)
                      + png[1] + bl + "</div></section>\n")
            continue
        tg = _target(links, t) if back else None
        tg = tg[7:] if tg and tg.startswith("anchor:") else tg
        sid = f' id="g-{slug(tg)}"' if tg else ""
        bl = (f'<a class="gback" href="__BACK__#s-{slug(tg)}">&larr; Back to {back}</a>' if tg else
              (f'<a class="gback" href="__BACK__">&larr; Back to {back}</a>' if back else ""))
        cards += (f'<section class="g"{sid}><div class="n">{k}</div><div class="txt"><h2>{t}</h2>'
                  f'<p class="sub">{sub}</p>' + "".join(f"<p>{x}</p>" for x in ps) + bl + "</div>"
                  f'<figure><img src="data:image/jpeg;base64,{_emb(png)}" alt="{re.sub("<[^>]+>", "", t)}"></figure>'
                  + (f'<div class="gx" style="grid-column:1/-1;flex-basis:100%;width:100%;">{extra}</div>' if extra else "")
                  + '</section>\n')
    top = f'<br><a class="gtop" href="__BACK__">&larr; Back to {back}</a>' if back else ""
    return (_head(f"{title} &mdash; {brand}") + BACK_CSS + "</style></head><body>\n"
            f'<header><div class="k">{brand}</div><h1>{title}</h1><p>{lede}</p>{top}</header>\n'
            f"<main>\n{cards}</main>\n<footer><b>Questions?</b>{FOOT}</footer>\n</body></html>")


ROADMAP_LINKS = {
    "Appraisal-Quality": "Appraisal-Quality Comparable Analysis",
    "Price Authenticated": "Price Authenticated",
    "Authenticated Values": "css:values-grid",
    "Moving the Needle": "Moving the Needle",
    "Current Competition": "Current Competition",
    "CST Pricing Strategy": "CST Pricing Strategy",
    "Preview": "Preview",
    "Coming Soon": "Coming Soon",
    "Predictive Analysis": "Predictive Analysis",
    "Reconciling Value": "Reconciling Value",
    "Our 4-Step": "Our 4-Step",
    "4. Adjust Price": "4. Adjust Price",
}
def _rm_links(p):
    if p.get("strategy_track_record"):
        # the track record lives in the CST Pricing Strategy guide section,
        # retitled "CST Strategy and Track Record"
        return {"CST Strategy and Track Record": "CST Pricing Strategy", **ROADMAP_LINKS}
    return ROADMAP_LINKS


BR_LINKS = {
    "Comparable Property Analysis": "Comparable Property Analysis",
    "Authenticated Values": "Authenticated Values",
}
BUYER_LINKS = {
    "Headlines": "css:pitch",
    "Authenticated Values": "Authenticated Values",
    "Price Authenticated": "Authenticated Values",
    "See the Home": "See the Home",
    "The Home": "The Home",
    "Features": "Features",
    "What the Owners Love": "What the Owners Love",
    "The Neighborhood": "Amenities and Transportation",
    "Property Documents": "Property Documents",
    "Writing an Offer": "Writing an Offer",
    "The Lot": "The Lot",
    "Move Up Calculator": "Move Up Calculator",
}

# Casey, 23 Nov 2026 (permanent): centred under the heading -- "all you have
# to do is center Guide to understand". Earlier: "flush right with an arrow just like the link 'back'
# is flush left with arrow back. They should look alike." Same type, colour
# and gold underline as the guide's "<- Back to" link (.gback).
GLINK_STYLE = ("font:700 15px Georgia,serif;color:#1F2A44;text-decoration:none;"
               "border-bottom:2px solid #B8902F;padding-bottom:2px;")
GLINK = ('<div class="glink-row" data-glink="{s}" style="text-align:center;margin:4px 0 16px;">'
         '<a href="{href}#g-{s}" target="_blank" rel="noopener" style="' + GLINK_STYLE + '">'
         'Understanding {name} &rarr;</a></div>')   # Casey, 26 Nov 2026: drop "Guide to" on Roadmap and Buyer Portal


def inject_links(page, guide_href, links):
    """Casey, 23 Nov 2026: every portal section the guide explains links to
    its guide section, and gets the id the guide's "Back to" link lands on.
    Safe to run twice."""
    import html as _h
    if not page.exists():
        return 0
    h = page.read_text(encoding="utf-8")
    n, done = 0, set()
    for target in dict.fromkeys(links.values()):
        anchor_only = target.startswith("anchor:")
        if anchor_only:
            target = target[7:]
        sg = slug(target)
        if sg in done or f'data-glink="{sg}"' in h:
            continue
        if target.startswith("css:"):
            cls = target[4:]
            m = re.search(r'<(?:section|div) class="' + cls + r'[^"]*"[^>]*>', h)
            if not m:
                continue
            name = {"pitch": "the Headlines", "values-grid": "Authenticated Values",
                    "trk": "Strategy Track Record"}.get(cls, cls.title())
            tag = m.group(0)
            new = tag if " id=" in tag else tag[:-1] + f' id="s-{sg}">'
            link = GLINK.format(s=sg, href=guide_href, name=name).replace(
                'style="text-align:center;margin:4px 0 16px;"', 'style="text-align:center;margin:0 0 14px;"')
            if cls == "pitch":
                h = h[:m.start()] + new + link + h[m.end():]
            elif cls == "trk":
                # Casey, 25 Nov 2026: the Strategy Track Record link sits
                # "down at CST Pricing Strategy" -- right under that section's
                # own guide link; the guide's Back link lands there too.
                k = h.find('data-glink="cst-pricing-strategy"')
                if k < 0:
                    continue
                k = h.find("</div>", k) + 6
                h = (h[:k] + f'<a id="s-{sg}" style="position:relative;top:-70px;"></a>'
                     + link.replace("margin:0 0 14px;", "margin:-6px 0 16px;") + h[k:])
            else:   # the link sits just above the block it explains
                h = h[:m.start()] + link + new + h[m.end():]
        else:
            hit = None
            for m in re.finditer(r"<h2([^>]*)>(.*?)</h2>", h, re.S):
                if slug(m.group(2)).startswith(sg):
                    hit = m
                    break
            if not hit:
                continue
            attrs = hit.group(1)
            m_id = re.search(r'\bid="([^"]+)"', attrs)
            if m_id:   # keep the page's own id; add ours as an anchor
                anchor = f'<a id="s-{sg}" style="position:relative;top:-70px;"></a>'
                head = anchor + hit.group(0)
            else:
                head = f'<h2{attrs} id="s-{sg}">{hit.group(2)}</h2>'
            if anchor_only:   # the "Back to" landing spot, no guide link
                h = h[:hit.start()] + head + h[hit.end():]
                done.add(sg)
                n += 1
                continue
            name = _h.unescape(re.sub("<[^>]+>", "", hit.group(2))).strip()
            name = re.sub(r"[\u2122\u00ae]", "", name).strip()
            # The guide's own id is keyed to the guide section's target
            link = GLINK.format(s=sg, href=guide_href, name=_h.escape(name))
            h = h[:hit.start()] + head + link + h[hit.end():]
        done.add(sg)
        n += 1
    page.write_text(h, encoding="utf-8")
    return n


def _shots(page_url, wanted, viewport=(1280, 900), before=None, max_h=1500, hide_maps=False):
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
        if hide_maps:
            pg.add_style_tag(content=".leaflet-container,.rmm-map,#locmap,.locmap,.mss-map,[id*=map]{display:none!important}"
                                     " .rmm-key,.locmap-arrows{display:none!important}")
            pg.wait_for_timeout(300)
        else:
            # Casey, 22 Nov 2026: the guide must show the section as the
            # seller sees it -- map included. Give the tiles time to arrive.
            try:
                pg.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            pg.wait_for_timeout(1200)
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
        el = pg.query_selector("section.trk .facts")
        if el:
            out["_trk"] = el.screenshot()
        el = pg.query_selector("section.pitch")
        if el:
            out["_headlines"] = el.screenshot()
        el = pg.query_selector(".values-grid")
        if el:
            box = el.bounding_box()
            lab = pg.query_selector(".values-label")
            y0 = lab.bounding_box()["y"] - 10 if lab else box["y"] - 10
            risk = pg.query_selector(".money-at-risk")
            y1 = (risk.bounding_box()["y"] + risk.bounding_box()["height"]) if risk else box["y"] + box["height"]
            out["_values"] = pg.screenshot(full_page=True, clip={
                "x": max(box["x"] - 30, 0), "y": max(y0, 0),
                "width": min(box["width"] + 60, viewport[0]), "height": y1 - y0 + 24})
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
    sh = _shots(page.as_uri(), names, max_h=2600)
    _nf = s_dir / "_guide_notes.json"
    notes = json.loads(_nf.read_text()) if _nf.exists() else {}
    cs = v.get("coming_soon_override") or v.get("customary")
    fb, dp = v.get("fallback_override"), v.get("deep_override")
    addr = p["address"]
    secs = [
        (sh.get("_top"), f"{addr} | CST Seller Roadmap&trade;", "Your plan, start to finish",
         ["Your Seller Roadmap&trade; outlines the proven pricing and marketing strategies that have made "
          "The Casey Samson Team&rsquo;s listings the Gold Standard against which other listings are judged.",
          "The Roadmap includes:"
          "<ul style=\"margin:8px 0 0 1.1em;padding:0;\">"
          "<li><b>Authenticated Pricing&trade;</b> &mdash; Establishing Customary to Premium Value and a "
          "strategic list price.</li>"
          "<li><b>Current Market Conditions</b> &mdash; Understanding buyer demand, competition, and market "
          "trends.</li>"
          "<li><b>Moving the Needle</b> &mdash; Recommendations to maximize your home&rsquo;s appeal and "
          "achieve top dollar.</li>"
          "<li><b>The Test&trade;</b> &mdash; Our proven Preview and Coming Soon strategy to identify the "
          "strongest buyer pool and position your home for a successful sale.</li></ul>",
          "<b>Our goal:</b> Sell your home in the first week at the highest possible price."]),
        (sh.get(names[0]), "Appraisal-Quality Comparable Analysis", "The sales an appraiser would use",
         [f"Your home sits at the top of the table, built {p['subject'].get('built')}, "
          f"{p['subject'].get('sf'):,} square feet, with the average of the comparable sales right under it.",
          "Each comparable is a real closed sale of similar size, age, location and time, so the price holds "
          "up when the buyer&rsquo;s lender orders the appraisal.",
          # Casey, 23 Nov 2026: say what the colours mean (market_map.SOLD_GRADE).
          "<b>What the colors mean.</b> Each numbered sale on the map is colored by how it sold, measured "
          "against its original list price:"
          '<ul style="margin:6px 0 0 1.1em;padding:0;">'
          '<li><b style="color:#2F6B3A;">Green</b> &mdash; sold in 7 days or less, at 99% or more of '
          "original list.</li>"
          '<li><b style="color:#B8860B;">Yellow</b> &mdash; took 8 to 30 days, or sold under 99% of '
          "original list.</li>"
          '<li><b style="color:#B3261E;">Red</b> &mdash; took over 30 days, or sold under 95% of '
          "original list.</li></ul>"
          "The black star is your home."]),
        (sh.get(names[1]), "Price Authenticated by the CST Pricing Team", "The pricing engine",
         ["Cylinders 1&ndash;6 run on every home: age and size, price range, price per square foot, "
          "assessment, market anomalies and inflation. Cylinders 7&ndash;10 fire only when they apply:",
          # Casey, 23 Nov 2026: each of (7) (8) (9) (10) on its own line.
          "<b>Neighborhood (7)</b> analyzes neighborhood sales over the past 5 years.",
          "<b>Premium/Discount (8)</b> compares whether the seller paid a premium or a discount at the time "
          "of purchase.",
          "<b>Extraordinary Upgrades (9)</b> applies when upgrades have been made that move the needle to a "
          "different price range.",
          "<b>Detriment (10)</b> is an adjustment for issues with the lot or functionality.",
          f"Your values: <b>Dated {money(v['dated'])}</b>, <b>Customary {money(v['customary'])}</b>, "
          f"<b>Premium {money(v['premium'])}</b>. CST listings are listed at the first threshold under "
          "Customary Value, and historically sell between Customary and Premium Values (sometimes more) "
          "within 6 days."]),
        # Casey, 23 Nov 2026: "another section for Authenticated Value breaking
        # down definitions for each, with cross links".
        # Casey, 23 Nov 2026: the three values across, each definition next to
        # its number, Money at Risk below.
        (("HTML",
          '<div class="avx">'
          f'<div class="c"><div class="k">Dated Price</div><div class="st">&#9733;&#9734;&#9734;</div>'
          f'<div class="row"><div class="v">{money(v["dated"])}</div><p class="d">The home as it stands if it '
          'has not been updated: kitchen and bathrooms largely original; paint, lighting, hardware, flooring '
          'and finishes dated; presentation below standard.</p></div></div>'
          f'<div class="c mid"><div class="k">Customary Price</div><div class="st">&#9733;&#9733;&#9734;</div>'
          f'<div class="row"><div class="v">{money(v["customary"])}</div><p class="d">What a home of this size '
          'and age has sold for in the past 90 days: kitchen and bathrooms updated within about 15 years; '
          'finishes at today&rsquo;s standard; presentation competitive with comparable homes. The pricing '
          'strategy starts here.</p></div></div>'
          f'<div class="c"><div class="k">Premium Price</div><div class="st">&#9733;&#9733;&#9733;</div>'
          f'<div class="row"><div class="v">{money(v["premium"])}</div><p class="d">What premium homes with '
          'superior finishes and presentation command: kitchen and bathrooms updated within about 10 years; '
          'upgrades and craftsmanship above the standard; presentation that sets the home apart.</p></div></div>'
          '</div>'
          f'<div class="avx-risk"><div><div class="k" style="font:700 12px Georgia,serif;letter-spacing:.14em;'
          f'text-transform:uppercase;color:#71695A;">Money at Risk</div><div class="v">{money(v["premium"] - v["dated"])}</div></div>'
          '<p class="d" style="margin:0;font-size:14.5px;line-height:1.5;">The distance from Dated to Premium: '
          'the value that can be lost to overpricing or poor preparation, and won back by Moving the Needle.</p></div>'
          # Casey, 23 Nov 2026: replaces "Historically, CST listings sell between...".
          '<p style="text-align:center;margin:16px auto 0;max-width:820px;">This is where professional Realtors add '
          'real value. Strategic, cost-effective cosmetic improvements can significantly increase a home&rsquo;s '
          'market value, generating returns far greater than the investment.</p>'),
         "Authenticated Values&trade;", "Dated, Customary and Premium &mdash; what each one means",
         ["Three values, one for each condition a home can be in. Final values are set after a trained "
          "Realtor inspects the home&rsquo;s condition, upgrades and lot premium or discount."]),
        (sh.get(names[2]), "Moving the Needle&trade; Guide", "What raises the price, and what lowers it",
         ["With hundreds of thousands of dollars at risk, strategic improvements are critical&mdash;and a "
          "Casey Samson Team specialty.",
          "The right cosmetic improvements can deliver a substantial increase in perceived value at a "
          "fraction of the cost."]),
        (sh.get(names[3]), "Current Competition", "Who you are up against",
         ["Understanding the competition is only half the equation. We measure Market Strength, Buyer "
          "Demand, and Market Momentum to determine whether buyers are actively purchasing homes&mdash;and, "
          "more importantly, which price ranges have the strongest buyer pools.",
          f"Our strategy is to position {addr} where buyer demand is strongest and launch when market "
          "conditions offer the best opportunity for success.",
          "<b>We don&rsquo;t just put homes on the market. We make sure the buyers are there when we "
          "launch.</b>"] + ([notes["uc30"]] if notes.get("uc30") else [])),
        (sh.get(names[4]), "CST Pricing Strategy", "Where the price goes, and why",
         [f"The strategy places the home at the first buyer threshold under its Customary Value of "
          f"{money(v['customary'])}, so it shows up for every buyer searching that range."]),
        (sh.get(names[5]), "Preview", "The home goes public before it goes live",
         ["Within two days of a signed Listing Agreement the home is posted on Preview with photographs and "
          "property information on Zillow, Homes.com, Samson Properties and more."]),
        (sh.get(names[6]), "Coming Soon", f"Full marketing at {money(cs)}",
         [f"The home goes on the MLS as Coming Soon at {money(cs)}, with full photography and marketing."]),
        (sh.get(names[7]), "Predictive Analysis&trade; Sets the Price", "The first week decides the next move",
         ["Our proven track record is built on monitoring buyer activity and responding decisively. Arriving "
          "at the right price is a science, not guesswork.",
          "<ul style=\"margin:0 0 0 1.1em;padding:0;\">"
          "<li><b>5+ Scheduled Showings:</b> Hold the price. We&rsquo;ve reached an active buyer pool.</li>"
          + (f"<li><b>1&ndash;4 Showings:</b> Adjust to {money(fb)} to attract a stronger buyer pool.</li>" if fb else "")
          + (f"<li><b>0 Showings &mdash; Pull the Rip Cord:</b> Move immediately to {money(dp)} to reach a new "
             "buyer pool.</li>" if dp else "")
          + "</ul>",
          "Every price is established in advance. We let buyer activity dictate our next move, eliminating "
          "surprises and protecting momentum."]),
    ]
    # Casey, 25 Nov 2026: "The strategy should have a section in Guide that
    # says Strategy Track Record (arrow). Show the track record comparison at
    # top of roadmap, then under it the track record you were using at the
    # bottom of the emails showing homes selling over list" -- "just show on
    # Sample". Opt in with "strategy_track_record": true.
    # Casey, 25 Nov 2026: CST Pricing Strategy and the Strategy Track Record
    # are one guide section -- the strategy, then right under it, same
    # section, "CST Strategy Track Record" (track record comparison, then CST
    # homes sold over list). One guide link on the Roadmap.
    if p.get("strategy_track_record") and sh.get("_trk"):
        try:
            from build_portal import over_list_table_html as _olt
            _tbl = _olt(p=p)
        except Exception:
            _tbl = ""
        import base64 as _b64
        _img = (f'<img src="data:image/png;base64,{_b64.b64encode(sh["_trk"]).decode()}" '
                'alt="CST track record vs the market" style="width:100%;max-width:980px;display:block;'
                'margin:10px auto 18px;border:1px solid #E4DCC8;border-radius:10px;">')
        _x = ('<h3 style="margin:28px 0 4px;text-align:center;font:700 24px \'Playfair Display\',Georgia,serif;'
              'color:#1F2A44;border-top:1px solid #E4DCC8;padding-top:24px;">CST Strategy Track Record</h3>'
              '<p style="text-align:center;margin:0 0 6px;color:#5A5446;">The strategy works &mdash; '
              'here is the proof: CST&rsquo;s verified MLS Bright results against the rest of the market, '
              'then CST homes that sold over list price.</p>'
              + _img + '<div style="max-width:820px;margin:0 auto;">' + _tbl + "</div>")
        for _k, _sec in enumerate(secs):
            if _sec[0] and _sec[1] == "CST Pricing Strategy":
                # Casey, 25 Nov 2026: "Title should be CST Strategy and Track record"
                secs[_k] = (_sec[0], "CST Strategy and Track Record") + tuple(_sec[2:4]) + (_x,)
                break
    rec = notes.get("recovery")
    if rec:
        secs = _recovery_roadmap_secs(p, page, secs, rec)
    return _page("Your Seller Roadmap Guide",
                 f"{addr} &mdash; what each part of your Gold Standard Seller Roadmap&trade; shows you.",
                 secs, _brand(p), links=_rm_links(p), back="Roadmap")


def _recovery_roadmap_secs(p, page, secs, rec):
    """Casey, 22 Nov 2026: a recovery Roadmap has no Preview, Coming Soon or
    Predictive Analysis -- it has Reconciling Value and Price and the 4-step
    Recovery Strategy, and the guide explains those instead."""
    v = p["values"]
    pool, cl, fb, rc = rec["pool"], rec["list"], rec["fb"], rec["rc"]
    sh = _shots(page.as_uri(), ["Reconciling Value", "Our 4-Step", "4. Adjust Price"])
    top = secs[0]
    top = (top[0], top[1], top[2], [t.replace(
        "<li><b>The Test&trade;</b> &mdash; Our proven Preview and Coming Soon strategy to identify the "
        "strongest buyer pool and position your home for a successful sale.</li>",
        "<li><b>Recovery Strategy</b> &mdash; Our 4-step plan to test buyer interest, reposition the home "
        "at the right price, and generate the strongest possible offer.</li>").replace(
        "Sell your home in the first week at the highest possible price.",
        "Find the buyer pool and create competition for your home.") for t in top[3]])
    keep = [top] + [x for x in secs[1:] if x[1] not in (
        "Preview", "Coming Soon", "Predictive Analysis&trade; Sets the Price")]
    keep += [
        (sh.get("Reconciling Value"), "Reconciling Value and Price", "Here is the problem",
         ["This table puts four numbers side by side: what the home is worth (<b>Customary</b> and "
          "<b>Premium Values</b>), where buyers are shopping (the <b>Buyer Threshold</b>), and where the home "
          "is listed today (the <b>Current List Price</b>).",
          f"Your home is listed at <b>{money(cl)}</b>. Buyers for homes of this age and size are shopping "
          f"under <b>{money(pool)}</b>. The competing active listings and the recent sales underneath the "
          "table show where that pool actually is.",
          "A home can be worth more than the buyer pool will pay&mdash;but value alone does not sell a home. "
          "Buyers do, and days on market do not close that distance.",
          "<b>The key is to find the buyer pool and create bidding&mdash;not to inch toward it.</b> A home "
          "priced into the pool, below the homes that have been sitting in it, draws more than one buyer at "
          "a time. That competition is what produces a sale above the list price."]),
        (sh.get("Our 4-Step"), "Our 4-Step Recovery Strategy", "Steps 1&ndash;3: prepare and test",
         ["<b>1. Inspect Property and Review Comments.</b> We walk the home and read every showing comment. "
          "If an update would make it more appealing to buyers, it is done now&mdash;see Moving the Needle.",
          "<b>2. Temporarily Off Market.</b> The home goes TEMP Off Market. Buyers and agents who have been "
          "watching it often call to find out why.",
          "<b>3. Test Buyer Interest.</b> When they call, we explain the home will return at a lower price. "
          "That can bring an offer before the reduction&mdash;and how many call tells us where the buyer "
          "pool is."]),
        (sh.get("4. Adjust Price"), "4. Adjust Price", "A larger buyer pool, not a lower sales price",
         ["Adjusting price does not mean a lower sales price, it means a larger buyer pool. Lower prices "
          "usually produce higher prices, because more buyers compete for the same home.",
          "<ul style=\"margin:0 0 0 1.1em;padding:0;\">"
          f"<li><b>If some buyers call &mdash; Fall Back Price, {money(fb)}:</b> buyers are close. If no "
          "acceptable offer comes, we return at this price to reach a larger buyer pool.</li>"
          f"<li><b>If no one calls &mdash; Pull the Rip Cord, {money(rc)}:</b> the price is not close to the "
          "buyer pool. This price guarantees the largest buyer pool, and whatever buyers bid is what the "
          "home is worth at this time.</li></ul>",
          "Both prices are set in advance. The calls during the test decide which one we use."]),
    ]
    return keep


def _lot_png(page):
    """The Lot section on the given Buyer Portal, on its Lot dimensions view
    (street tiles load where aerial tiles may not)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1280, "height": 900})
            pg.goto(page.as_uri(), wait_until="load")
            el = pg.query_selector("section.lotsec")
            if not el:
                b.close()
                return None
            btn = pg.query_selector('.lot-tabs button[data-v="d"]')
            if btn:
                btn.click()
            try:
                pg.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            pg.wait_for_timeout(1500)
            png = el.screenshot()
            b.close()
            return png
    except Exception:
        return None


def _map_png():
    """The Sample's neighborhood map with its list, from Casey's screenshot
    (map tiles do not load in the build workspace)."""
    f = ROOT / "templates" / "guides" / "img" / "sample_neighborhood_map.png"
    return f.read_bytes() if f.exists() else None


def _engine_png():
    """The Pricing Engine section of the Sample Roadmap."""
    page = ROOT / "output" / "Sample" / "Sample_Roadmap.html"
    if not page.exists():
        return None
    return _shots(page.as_uri(), ["Price Authenticated"], max_h=1100).get("Price Authenticated")


def buyer_guide(p, b_dir):
    """Casey, 22 Nov 2026: "Rebuild buyer portal guide based on Sample Buyer
    portal" -- the screenshots come from the full Sample Buyer Portal (502
    MacArthur), so every section of a finished Buyer Portal is shown, while
    the text carries THIS home's current figures."""
    # Casey, 23 Nov 2026: "Completeness of report dictates." Until this
    # home's Buyer Portal is finished (photos and features), the guide is the
    # Sample's guide -- its pictures and its figures. Once it is finished the
    # guide is built from this home's own portal and figures.
    sample = ROOT / "output" / SAMPLE_BUYER[0] / "index.html"
    done = _bp_finished(p) or not sample.exists()
    page = (b_dir / "index.html") if done else sample
    if not page.exists():
        return None
    home = p
    if not done:
        import private_label as _pl
        p = json.loads((ROOT / "properties" / "502_macarthur.json").read_text(encoding="utf-8"))
        _pl.resolve(p)
    v = p["values"]
    names = ["Authenticated Values", "See the Home", "The Home", "Features", "What the Owners Love",
             "Amenities and Transportation", "Property Documents", "Writing an Offer", "Move Up Calculator"]
    sh = _shots(page.as_uri(), names,
                before="(()=>{var a=document.getElementById('muVal'),d=document.getElementById('muDebt');"
                       "if(a){a.value='$1,200,000';d.value='$400,000';"
                       "['muVal','muDebt'].forEach(i=>document.getElementById(i).dispatchEvent(new Event('input')));}})()")
    addr = (p.get("buyer_portal") or {}).get("display_address") or p["address"]
    secs = [
        (sh.get("_top"), "Your First Look", addr,
         ["The front door to everything you need to know about the home: photography, values, documents and "
          "how to write an offer, all in one place.",
          "Tap <b>Pricing Report</b> for the printable Buyer Report. Scan the <b>QR code</b> to put "
          "this portal on your phone.",
          '<a class="gback" href="Buyer_Report_Guide.html" style="border-bottom-width:2px;">'
          "Guide to Understanding the Buyer Report &rarr;</a>"]),
        (sh.get("_headlines"), "Headlines", "What matters most",
         ["Headlines identify the most important things buyers need to know about the home."]),
        (sh.get(names[0]), "Authenticated Values&trade;", "How the price was set",
         [_lp_line(p),
          f"<b>Customary Value</b> is {money(v['customary'])} for a home of this size and age that has sold in "
          f"the past 90 days. <b>Premium Value</b> of {money(v['premium'])} is what premium homes with superior "
          "finishes and presentation command.",
          "Historically, CST listings sell between Customary and Premium Values (sometimes more)."]),
        (_engine_png(), "Price Authenticated by the CST Pricing Team", "The pricing engine",
         ["The value of this home was not pulled from an online estimate. The CST Pricing Team authenticates it "
          "by hand, through ten tests.",
          "Cylinders 1&ndash;6 run on every home: age and size, price range, price per square foot, assessment, "
          "market anomalies and inflation. Cylinders 7&ndash;10 fire only when they apply:",
          "<b>Neighborhood (7)</b> analyzes neighborhood sales over the past 5 years. "
          "<b>Premium/Discount (8)</b> compares whether the seller paid a premium or a discount at the time of "
          "purchase. <b>Extraordinary Upgrades (9)</b> applies when upgrades have been made that move the needle "
          "to a different price range. <b>Detriment (10)</b> is an adjustment for issues with the lot or "
          "functionality.",
          "That is why you can have confidence in the Customary and Premium Values above."]),
        (sh.get(names[1]), "See the Home", "The photography",
         ["The full gallery of the home. Tap any photo to see it large."]),
        (sh.get(names[2]), "The Home &mdash; We Are More Than a Pretty Face", "Home Preparation Is the Key to a Gold Standard Listing&trade;",
         ["Every Casey Samson Team listing undergoes a thorough pre-market inspection of major systems and "
          "potential problem areas, including heating and cooling, appliances, electrical systems, roof, "
          "foundation, and mold.",
          "Identified issues are addressed before the home goes live, minimizing surprises, strengthening buyer "
          "confidence, and protecting the sale price.",
          "<b>Our goal: Resolve inspection issues before contract negotiations&mdash;not during them.</b>"]),
        (sh.get(names[3]), "Features &amp; Updates", "What is inside, and what is new",
         ["Every feature, and every major update with the year it was done."]),
        (sh.get(names[4]), "What the Owners Love", "In their own words",
         ["The things the owners will miss most about living here."]),
        # Casey, 23 Nov 2026: The Lot -- four aerial views with lot lines.
        (_lot_png(page), "The Lot", "The property from above, four ways",
         ["Four views of the lot with the property lines drawn in gold. Tap a button above the map to switch.",
          "<b>Satellite</b> &mdash; a close aerial photo framed on the lot: the house, the yard, the trees and "
          "how far the lot runs.",
          "<b>With street names</b> &mdash; a step back, so you can see the street and the homes on either side.",
          "<b>Neighborhood</b> &mdash; the lot within the whole neighborhood: nearby streets, cul-de-sacs and open "
          "space.",
          "<b>Lot dimensions</b> &mdash; a clean street map with the length of each side in feet and a scale bar.",
          "The lot lines and dimensions come from the county parcel map and are approximate; the recorded plat "
          "is the official boundary."]),
        ((sh.get(names[5]) if done else None) or _map_png() or sh.get(names[5]),
         "The Neighborhood &mdash; Amenities &amp; Transportation",
         "More Than a Home. A Community and a Lifestyle.",
         ["Buyers aren&rsquo;t just purchasing a home. They&rsquo;re investing in a community, a lifestyle, and "
          "everything the surrounding area offers.",
          f"{p['address']} puts buyers in {_town(p)}, "
          + ("recognized by Travel + Leisure as one of America&rsquo;s best small towns, " if _town(p) == "Vienna" else "")
          + "with exceptional parks, restaurants, shopping, schools, and convenient access to Metro, airports, "
          "and major employment centers.",
          "The interactive map highlights the amenities, attractions, and transportation options that make this "
          "location so desirable, with estimated walking and driving times.",
          f"<b>We&rsquo;re not just selling the home. We&rsquo;re selling the {_town(p)} lifestyle.</b>"]),
        (sh.get(names[6]), "Property Documents", "Everything to review before an offer",
         ["Disclosures, the floor plan, the survey and the other documents a buyer needs."]),
        (sh.get(names[7]), "Writing an Offer", "How to make yours the strongest",
         ["What the sellers are looking for, and how to put your best offer forward."]),
        (sh.get(names[8]), "Move Up Calculator", "What your current home puts toward this one",
         ["Enter your current home&rsquo;s price and what you owe. Your walk out the door proceeds become the "
          "down payment, after closing costs.",
          f"Switch between <b>Customary</b> ({money(v['customary'])}) and <b>Premium</b> "
          f"({money(v['premium'])}) to see the payment difference. Tap <b>Math</b> for every number."]),
    ]
    lede = (f"{addr} &mdash; what each part of the portal shows you, and how to use it." if done else
            f"A finished Buyer Portal, {addr} &mdash; what each part shows you, and how to use it. "
            f"The portal for {home.get('buyer_portal', {}).get('display_address') or home['address']} "
            "fills in the same way as the home is prepared.")
    return _page("Your Buyer Portal Guide" if done else "Buyer Portal Guide &mdash; Sample",
                 lede, secs, _brand(home), links=BUYER_LINKS, back="Buyer Portal")


def _town(p):
    return (p.get("city") or "Northern Virginia").strip()


def _lp_line(p):
    """Casey, 22 Nov 2026: "The List Price reflects where the largest Buyer
    Pool is for this home." """
    return ("The List Price reflects where The Casey Samson Team test found the largest Buyer Pool is "
            "for this home.")


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
        (sh.get("_top"), "The Buyer Report", p["address"],
         ["A one-page summary for buyers and their agents: the home, the sales that authenticate its value, "
          "and the value range itself. It is displayed at the listing and at open houses, and prints as a PDF."]),
        (sh.get(names[0]), "Comparable Property Analysis", "The sales behind the value",
         ["Each comparable is a real closed sale of similar size, age, location and time &mdash; the same tests "
          "an appraiser applies &mdash; with the averages by age and size and by price range.",
          "Compare the home&rsquo;s year built, size and lot with the sales to see where it stands."]),
        (sh.get(names[1]), "Authenticated Values&trade;", "What the home is worth",
         [_lp_line(p),
          f"<b>Customary Value</b> is {money(v['customary'])} for a home of this size and age that has sold in "
          f"the past 90 days. <b>Premium Value</b> of {money(v['premium'])} is what premium homes with superior "
          "finishes and presentation command.",
          "Historically, CST listings sell between Customary and Premium Values (sometimes more)."]),
    ]
    return _page("Guide to Understanding the Buyer Report",
                 f"{p['address']} &mdash; what each part of the Buyer Report tells you.", secs, _brand(p),
                 links=BR_LINKS, back="Buyer Report")


def mss_guide(p):
    slug = (p.get("market") or {}).get("slug")
    import townhome_mss as _th
    page = _th.mss_page(slug)
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
                 f"The {mk} Market Snapshot &mdash; what each part tells you, and how to read it.", secs, _brand(p), links=GUIDES_ROW, back="Seller Portal")


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
                 f"{p['address']} &mdash; what your sale puts toward your next home.", secs, _brand(p), links=GUIDES_ROW, back="Seller Portal")


def _brand(p):
    pl = p.get("private_label") or {}
    if pl:
        return f"{pl.get('team_name') or pl.get('name')} &middot; Powered by CST Pricing"
    return "The Casey Samson Team &mdash; The Gold Standard of Pricing Strategy"


def track_record_to_roadmap(index, rm):
    """Casey, 23 Nov 2026: "Take track record comparison on Portal and put on
    Roadmap." The same card the Seller Portal shows -- the team row over the
    local market row -- copied as built, right under the Roadmap hero."""
    if not (index.exists() and rm.exists()):
        return False
    ih, h = index.read_text(encoding="utf-8"), rm.read_text(encoding="utf-8")
    if 'class="trk"' in h:
        return False
    i = ih.find('<div class="wrap"><div class="facts">')
    j = ih.find('class="facts-note"', i)
    j = ih.find("</div>", j) + len("</div>") if j > 0 else -1
    if i < 0 or j < 0:
        return False
    card = ih[i:j]
    src = (ROOT / "build_index_v2.py").read_text(encoding="utf-8")
    a, b = src.find("/* facts card"), src.find("section{padding:46px 0;}")
    css = src[a:b] if a > 0 and b > a else ""
    css = re.sub(r"(^|\n|\})\s*(\.fact)", r"\1 .trk \2", css)
    # Overlaps the navy specs band above it, as on the Seller Portal.
    block = ('<style>.trk{--card:#FFFFFF;--rule:#E4DCC8;--ink:#221C14;--muted:#71695A;--muted-2:#968972;'
             "--gold-deep:#8A6A2E;padding:0 0 34px;border-top:none!important;}" + css + "</style>\n"
             f'<section class="trk">{card}</section>\n')
    # Right under the navy band (it overlaps the band's edge), ahead of the
    # Subject strip when there is one.
    k = h.find('<section class="rm-subj"')
    if k < 0:
        k = h.find("Appraisal-Quality Comparable Analysis")
        k = h.rfind("<section", 0, k) if k > 0 else -1
    if k < 0:
        return False
    rm.write_text(h[:k] + block + h[k:], encoding="utf-8")
    return True


GUIDES_ROW = {"*": "anchor:Guides to Understanding CST Tools"}

# Casey, 23 Nov 2026: seller sites at <address>.netlify.app, buyer portals at
# buy<street>.netlify.app -- the Sample's buyer portal is buymacarthur.
SAMPLE_BUYER = ("502_MacArthur_Buyer", "https://buymacarthur.netlify.app", "502 MacArthur Ave NE")


def _bp_finished(p):
    """The home's own Buyer Portal is finished once its photography and
    headlines are in (or the property file says so)."""
    bp = p.get("buyer_portal") or {}
    if "finished" in bp:
        return bool(bp["finished"])
    # One rule everywhere: the same test that retires the Example card on the
    # Seller Portal.
    from build_portal import buyer_portal_ready
    return buyer_portal_ready(p)


def _portal_top(page, out):
    """The top of a Buyer Portal -- hero, facts and the headlines -- as the
    buyer first sees it."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(page.as_uri(), wait_until="load")
        pg.wait_for_timeout(900)
        bottom = pg.evaluate("""() => { const e = document.querySelector('section.pitch');
            return e ? e.getBoundingClientRect().bottom + scrollY + 20 : 1500; }""")
        png = pg.screenshot(full_page=True, clip={"x": 0, "y": 0, "width": 1280,
                                                  "height": min(max(bottom, 900), 2300)})
        b.close()
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im = im.resize((1000, int(im.height * 1000 / 1280)), Image.LANCZOS)
    im.save(out, "JPEG", quality=82, optimize=True)


def buyer_preview_to_roadmap(p, s_dir, b_dir):
    """Casey, 23 Nov 2026: the Roadmap's Buyer Portal section promotes the
    portal with a picture of it. Until this home's portal is finished it
    toggles between this home's portal (headers in place, details to come)
    and the finished Sample; once the home's portal is finished the Sample
    is replaced by it."""
    rm = s_dir / f"{p['prefix']}_Roadmap.html"
    home = b_dir / "index.html"
    # Casey, 23 Nov 2026: the link is constant -- the Sample until this
    # home's portal has its pictures and features, then this home's. A home
    # with no buyer portal of its own (the Sample itself, a new listing not
    # yet built) still gets the Sample.
    if not rm.exists():
        return False
    h = rm.read_text(encoding="utf-8")
    h = re.sub(r"<!--BPV-->.*?<!--/BPV-->\n?", "", h, flags=re.S)
    m = re.search(r'<div class="bp-words".*?</div>', h, re.S)
    if not m:
        return False
    url = ((p.get("buyer_portal") or {}).get("url") or "").rstrip("/")
    # Casey, 23 Nov 2026: "Remove options ... to go to Subject or sample.
    # Completeness of report dictates." One picture: the Sample until this
    # home's portal is finished, then this home's portal.
    # Casey, 25 Nov 2026: "At the bottom on roadmap is the property buyer
    # portal (what there is of it)" -- this home's portal whenever it exists.
    done = home.exists()
    unfinished = not _bp_finished(p)
    sample = ROOT / "output" / SAMPLE_BUYER[0] / "index.html"
    if not done and not sample.exists():
        if not home.exists():
            return False
        done = True
    for old_jpg in ("bp_preview_home.jpg", "bp_preview_sample.jpg"):
        (s_dir / old_jpg).unlink(missing_ok=True)
    if done:
        _portal_top(home, s_dir / "bp_preview_home.jpg")
        shot = (f'<a class="bpv-shot on" href="{url}" target="_blank" rel="noopener">'
                '<img src="bp_preview_home.jpg" alt="This home&rsquo;s Buyer Portal"></a>')
        cap = ('<p class="bpv-cap">This home&rsquo;s Buyer Portal so far &mdash; photos and features are added '
               f'as the home is prepared. Tap to open it, or <a href="{SAMPLE_BUYER[1]}" target="_blank" rel="noopener">'
               'see a completed Buyer Portal</a>.</p>' if unfinished else
               '<p class="bpv-cap">This home&rsquo;s Buyer Portal &mdash; tap to open it.</p>')
    else:
        _portal_top(sample, s_dir / "bp_preview_sample.jpg")
        shot = (f'<a class="bpv-shot on" href="{SAMPLE_BUYER[1]}" target="_blank" rel="noopener">'
                f'<img src="bp_preview_sample.jpg" alt="Sample Buyer Portal, {SAMPLE_BUYER[2]}"></a>')
        cap = (f'<p class="bpv-cap">A finished Buyer Portal: {SAMPLE_BUYER[2]}, sold for $2,300,000. '
               'This home&rsquo;s portal fills in the same way as the home is prepared.</p>')
    tabs, shots = "", shot
    block = ("<!--BPV-->\n<style>"
             ".bpv{max-width:900px;margin:26px auto 0;text-align:center}"
             ".bpv-tabs{display:inline-flex;border:1px solid #B8902F;border-radius:22px;overflow:hidden;margin-bottom:14px}"
             ".bpv-tabs button{font:700 14px Georgia,serif;letter-spacing:.04em;padding:9px 22px;border:0;"
             "background:#FFFDF7;color:#1F2A44;cursor:pointer}"
             ".bpv-tabs button.on{background:#1F2A44;color:#E8C77A}"
             ".bpv-frame{border:1px solid #D9CBA6;border-radius:10px;overflow:hidden;box-shadow:0 10px 30px rgba(40,30,10,.18);"
             "max-height:620px;overflow-y:auto;background:#fff}"
             ".bpv-shot{display:none}.bpv-shot.on{display:block}.bpv-shot img{display:block;width:100%;height:auto}"
             ".bpv-cap{font-size:14px;color:#71695A;font-style:italic;margin:12px 0 0}"
             "@media print{.bpv-frame{max-height:none}.bpv-tabs{display:none}}"
             "</style>\n"
             f'<div class="bpv">{tabs}<div class="bpv-frame">{shots}</div>{cap}</div>\n'
             "<script>(function(){var r=document.querySelector('.bpv');if(!r)return;"
             "r.querySelectorAll('.bpv-tabs button').forEach(function(b){b.onclick=function(){var v=b.dataset.v;"
             "r.querySelectorAll('[data-v]').forEach(function(e){var on=e.dataset.v===v;"
             "if(e.tagName==='P'){e.hidden=!on}else{e.classList.toggle('on',on)}});};});})();</script>\n"
             "<!--/BPV-->\n")
    h = h[:m.end()] + "\n" + block + h[m.end():]
    rm.write_text(h, encoding="utf-8")
    return True


def roadmap_first(p, s_dir):
    """Casey, 23 Nov 2026: "make the Roadmap the first page that comes up,
    not the portal." The site's front door (index.html) is the Roadmap; the
    Seller Portal moves to portal.html, and every link that meant the portal
    -- "Back to <address>", the guides' "Back to Seller Portal", the emails'
    Seller Portal links -- now points there. Safe to run after every build."""
    rm = s_dir / f"{p['prefix']}_Roadmap.html"
    idx, portal = s_dir / "index.html", s_dir / "portal.html"
    if not rm.exists():
        return False
    if idx.exists() and 'class="feat-hit"' in idx.read_text(encoding="utf-8"):
        idx.replace(portal)          # a fresh Seller Portal from this build
    if not portal.exists():
        return False
    root = (p.get("portal_url") or "").rstrip("/")
    def fix(t):
        n = t.replace('href="index.html', 'href="portal.html')
        if root:
            n = n.replace(f'href="{root}/"', f'href="{root}/portal.html"').replace(
                f'href="{root}"', f'href="{root}/portal.html"')
        return n

    for f in s_dir.glob("*.html"):
        if f.name == "index.html":
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        if fix(t) != t:
            f.write_text(fix(t), encoding="utf-8")
    # The .eml drafts are quoted-printable: decode, fix, re-encode.
    import email
    from email import policy
    for f in s_dir.glob("*.eml"):
        msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
        changed = False
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                t = part.get_content()
                if fix(t) != t:
                    part.set_content(fix(t), subtype="html", cte="quoted-printable")
                    changed = True
        if changed:
            f.write_bytes(msg.as_bytes(policy=policy.default))
    idx.write_text(rm.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def build(p, which=("roadmap", "mss", "moveup", "buyer")):
    import private_label as _pl
    _pl.resolve(p)
    pre = p["prefix"]
    s_dir = ROOT / "output" / pre
    b_dir = ROOT / "output" / f"{pre}_Buyer"
    made = []
    rm = s_dir / f"{pre}_Roadmap.html"
    # The track record card goes onto the Roadmap first, so the guide can
    # show it and link from it (Strategy Track Record, 25 Nov 2026).
    if "roadmap" in which:
        track_record_to_roadmap(s_dir / "index.html", rm)
    if "roadmap" in which and (h := roadmap_guide(p, s_dir)):
        (s_dir / f"{pre}_Roadmap_Guide.html").write_text(h.replace("__BACK__", rm.name), encoding="utf-8")
        made.append("roadmap")
        inject_links(rm, f"{pre}_Roadmap_Guide.html", _rm_links(p))
        if p.get("strategy_track_record"):
            _t = rm.read_text(encoding="utf-8").replace(
                "Understanding CST Pricing Strategy &rarr;",
                "Understanding CST Strategy and Track Record &rarr;")
            rm.write_text(_t, encoding="utf-8")
    if "roadmap" in which or "buyer" in which:
        try:
            buyer_preview_to_roadmap(p, s_dir, b_dir)
        except Exception as e:  # a preview must never stop a build
            print("  buyer preview skipped:", e)
    (s_dir / "_guide_notes.json").unlink(missing_ok=True)   # build-time only, not for the site
    if "mss" in which and (h := mss_guide(p)):
        (s_dir / "Market_Snapshot_Guide.html").write_text(h.replace("__BACK__", "index.html"), encoding="utf-8")
        made.append("market snapshot")
    if "moveup" in which and (h := moveup_guide(p, s_dir)):
        (s_dir / "Move_Up_Guide.html").write_text(h.replace("__BACK__", "index.html"), encoding="utf-8")
        made.append("move up")
    if "mss" in which or "moveup" in which:
        inject_links(s_dir / "index.html", "", GUIDES_ROW)
    if "roadmap" in which and (h := buyer_report_guide(p, s_dir)):
        for d in (s_dir, b_dir, ROOT / "output" / f"{pre}_Buyer_Small"):
            if d.exists():
                _br = f"{pre}_Buyer_Report.html"
                if not (d / _br).exists():
                    _br = f"{pre}_Buyer_Report.pdf"
                (d / "Buyer_Report_Guide.html").write_text(h.replace("__BACK__", _br), encoding="utf-8")
        made.append("buyer report")
    if "buyer" in which and (h := buyer_guide(p, b_dir)):
        bp_url = ((p.get("buyer_portal") or {}).get("url") or "").rstrip("/")
        for d in (s_dir, b_dir, ROOT / "output" / f"{pre}_Buyer_Small"):
            if d.exists():
                # From the buyer sites "Back to Buyer Portal" is the page next
                # door; from the seller site it is the published portal.
                # From the seller site, "Back to Buyer Portal" must never land on
                # the seller site's own front page (the Roadmap): it goes to this
                # home's buyer portal, or to the Sample's when there is none.
                back = "index.html" if d != s_dir else (bp_url or SAMPLE_BUYER[1]) + "/"
                (d / "Buyer_Portal_Guide.html").write_text(h.replace("__BACK__", back), encoding="utf-8")
                if d != s_dir:
                    inject_links(d / "index.html", "Buyer_Portal_Guide.html", BUYER_LINKS)
        made.append("buyer portal")
    # The switch happens on a seller build; a buyer-only build just keeps an
    # already-switched site's front-door copy of the Roadmap current.
    if p.get("roadmap_first", True) and ("roadmap" in which or (s_dir / "portal.html").exists()):
        try:
            roadmap_first(p, s_dir)
        except Exception as e:  # never stop a build over the front door
            print("  roadmap-first skipped:", e)
    return made


if __name__ == "__main__":
    prop = json.loads(Path(sys.argv[1]).read_text())
    print("guides:", ", ".join(build(prop)) or "none")
