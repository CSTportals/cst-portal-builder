"""Us vs Zillow checklist.

Casey, 25 Nov 2026: "We should have a comparison between our Buyer and seller
portals of what we deliver to sellers and buyers and what Zillow delivers" ...
"Should be side by side check list. 5 words Us vs them checkboxes".

Shown when the property file has "zillow_compare": true (Sample first, per
the hold policy). Seller rows go on the Roadmap, buyer rows on the Buyer
Portal. Rows Zillow also delivers are checked for Zillow too -- an honest
list is more persuasive than a rigged one.
"""

# (row, Zillow has it, Compass has it). CST has every row.
# Compass (25 Nov 2026, compass.com/sell, /concierge, Compass One): its
# 3-Phased Marketing Strategy (Private Exclusive -> Coming Soon -> public) is a
# pre-market price test, and Concierge fronts improvement costs with the agent
# choosing the services -- both get Compass checks. Its pricing is "validated"
# by agent feedback across its network, not a pricing engine.
SELLER_ROWS = [
    # Casey, 25 Nov 2026: "add Verified Track record of Strategy" -- first item.
    ("Verified Track Record of Strategy", False, False),
    # Casey, 25 Nov 2026: split -- Zillow is the rub with Compass. Zillow
    # will not display listings first hidden in a private network (a Compass
    # Private Exclusive), so the row is worded "from day one" (checked
    # 25 Nov 2026: Compass dropped its suit in March 2026; Zillow's standards
    # still exclude listings previously hidden from the public).
    ("On Zillow from day one", True, False),
    ("Listed on the MLS", True, True),
    ("Pricing Engine, not agent opinions", False, False),
    # Casey, 25 Nov 2026: replaces "Customary and Premium Values" and
    # "Predictive Analysis sets the price". The 4th value is CST's own box:
    # CST does NOT use computer-generated pricing.
    ("Authenticated Values by Professionals", False, False),
    ("Premium Values", False, False),
    ("Computer-generated pricing", True, True, False, True),   # 5th: a negative -- checks in red
    ("Price changes set in advance", False, False),
    # Casey, 25 Nov 2026: split the test row. Our Preview goes to the
    # entire market (Zillow shows it too); a Compass Private Exclusive is
    # held inside Compass's own network. Coming Soon: all three.
    ("Preview to Entire Market", True, False),
    ("Coming Soon", True, True),
    ("Moving the Needle improvement plan", False, True),
    ("Market Snapshot for your segment", False, False),
    ("Market Momentum", False, False),
    ("Guide to Understanding Indexes", False, False),
    ("Competing homes mapped and measured", False, False),
    ("Neighborhood amenities", False, False),
    ("Distances to transportation hubs", False, False),
    ("Utility providers and phone numbers", False, False),   # Casey, 26 Nov 2026
    ("Buyer Showcase", False, False),
    ("County plat and lot dimensions", False, False),
    ("Custom website for your home", False, False),
]

BUYER_ROWS = [
    ("Photos, price and listing details", True, True),
    ("GreatSchools ratings for each school", True, True),
    ("Authenticated Values by Professionals", False, False),
    ("Premium Values", False, False),
    ("Computer-generated pricing", True, True, False, True),   # 5th: a negative -- checks in red
    ("Comps colored by over/under list", False, False),
    ("Competing homes mapped and measured", False, False),
    ("Market strength for this segment", False, False),
    ("Neighborhood amenities", False, False),
    ("Distances to transportation hubs", False, False),
    # Casey, 26 Nov 2026: Zillow and Compass show MLS utility types (gas
    # heat, public sewer), not the providers or how to reach them.
    ("Utility providers and phone numbers", False, False),
    ("County plat and lot dimensions", False, False),
]

FOOT = ("Zillow: a standard listing page and Zestimate. Compass: its 3-Phased "
        "Marketing Strategy, Concierge and Compass One, as published on compass.com. "
        "Zestimate error rates: zillow.com/zestimate, nationwide medians.")

CSS = """
.zc{max-width:640px;margin:22px auto 0;background:#fff;border:1px solid #E5DDC9;border-radius:10px;overflow:hidden}
.zc table{width:100%;min-width:0!important;border-collapse:collapse;font-family:Georgia,serif;table-layout:auto}
.zc th{line-height:1.3;background:#1F2A44;color:#fff;font:700 12px Georgia,serif;letter-spacing:.14em;text-transform:uppercase;padding:12px 10px}
.zc th:first-child{text-align:left;padding-left:20px}
.zc th.cst{color:#E9C77B}
.zc td{padding:11px 10px;border-top:1px solid #EFE9DA;font-size:15.5px;color:#1F2A44}
.zc td:first-child{padding-left:20px;text-align:left}
.zc td.c{text-align:center;width:86px}
.zc tr:nth-child(even) td{background:#FBF8F1}
.zc .y{display:inline-block;width:22px;height:22px;border-radius:4px;background:#8A6A2E;color:#fff;font:700 15px/22px Arial,sans-serif}
.zc .y.bad{background:#B3261E}
.zc .n{display:inline-block;width:22px;height:22px;border-radius:4px;border:1.5px solid #C9C1AE;color:#B5AD9A;font:400 14px/19px Arial,sans-serif}
.zx{max-width:640px;margin:18px auto 0;background:#1F2A44;color:#fff;border-radius:10px;padding:22px 26px;text-align:center}
.zx .k{font:700 11px Georgia,serif;letter-spacing:.18em;text-transform:uppercase;color:#E9C77B}
.zx .big{font:700 46px/1.1 'Playfair Display',Georgia,serif;color:#fff;margin:8px 0 2px}
.zx .sub{font:16px Georgia,serif;color:#E8E2D3}
.zx .usd{font:700 19px Georgia,serif;color:#E9C77B;margin-top:10px}
.zx .why{font:italic 13.5px/1.5 Georgia,serif;color:#C9C3B4;margin-top:12px}
.zc-foot{max-width:640px;margin:10px auto 0;text-align:center;font:italic 11.5px Georgia,serif;color:#71695A}
@media(max-width:560px){.zc td{font-size:13.5px;padding:10px 6px}.zc td:first-child{padding-left:12px}.zc th:first-child{padding-left:12px}.zc th{padding:10px 4px}.zc td.c{width:52px;padding-left:4px;padding-right:4px}.zc th{font-size:10.5px;letter-spacing:.08em}}
"""


def _table(rows, us="CST"):
    y = '<span class="y">&#10003;</span>'
    n = '<span class="n">&ndash;</span>'
    r = '<span class="y bad">&#10003;</span>'
    def _row(t, z, c, us=True, bad=False):
        # Casey, 25 Nov 2026: "mark computer generated pricing boxes with red"
        k = r if bad else y
        return (f'<tr><td>{t}</td><td class="c">{k if us else n}</td><td class="c">{k if z else n}</td>'
                f'<td class="c">{k if c else n}</td></tr>')
    body = "".join(_row(*r) for r in rows)
    return ('<div class="zc"><table><thead><tr><th>What You Get</th>'
            f'<th class="cst">{us}</th><th>Zillow</th><th>Compass</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div><p class="zc-foot">{FOOT}</p>')


PRINT_PDF = "CST_Roadmap_vs_Zillow_vs_Compass.pdf"   # copied into every seller site
OFF_MKT = 7.01   # zillow.com/zestimate, nationwide median error, off-market homes
ON_MKT = 1.83    # same page, on-market homes


def _customary(p):
    v = (p.get("values") or {}).get("customary")
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def error_callout(p):
    """Casey, 25 Nov 2026: "The fair comparison for a seller is the 7%
    off-market figure. this is important to emphasize." A seller checks Zillow
    BEFORE listing, when the Zestimate is the off-market one. The 1.83%
    on-market figure looks good only because the Zestimate leans on the list
    price once there is one."""
    cv = _customary(p)
    usd = ""
    if cv:
        miss = round(cv * OFF_MKT / 100 / 1000) * 1000
        usd = (f'<div class="usd">On a ${round(cv, -4):,.0f} home, that is ${miss:,.0f} '
               f'too high or too low.</div>')
    return ('<div class="zx"><div class="k">AI Can Not Price Your Home</div>'
            f'<div class="big">{OFF_MKT:.2f}%</div>'
            '<div class="sub">Zillow&rsquo;s own median Zestimate error for homes not on the market</div>'
            f'{usd}'
            f'<div class="why">Zillow advertises {ON_MKT:.2f}% for listed homes &mdash; because once a home is listed, '
            'the Zestimate leans on the list price. The list price is the decision you are making. '
            'That is what we authenticate.</div></div>')


def enabled(p, b=None):
    return bool(p.get("zillow_compare") or (b or {}).get("zillow_compare"))


def _applies(rows, p, buyer=False):
    """Drop rows this home cannot back up (Casey's rule: the checklist must be
    true for the page it sits on): no plat on file -> no plat row; on the
    Buyer Portal, schools hidden (all under 7, or none) -> no GreatSchools row."""
    b = p.get("buyer_portal") or {}
    has_plat = bool((b.get("lot") or {}).get("plat") or (p.get("lot") or {}).get("plat"))
    out = []
    for r in rows:
        t = r[0].lower()
        if "plat" in t and not has_plat:
            continue
        if buyer and "utility" in t and not b.get("utilities"):
            continue
        if buyer and "greatschools" in t:
            try:
                import schools as _s
                if not _s.row_html(p, buyer=True):
                    continue
            except Exception:
                pass
        out.append(r)
    return out


def seller_section(p):
    if not enabled(p):
        return ""
    return (f'<style>{CSS}</style><section><div class="wrap">'
            '<h2 class="section-title">CST Roadmap vs Zillow vs Compass</h2>'
            '<p class="needle-lede" style="text-align:center">What sellers get from us, from Zillow, and from Compass.</p>'
            f'{error_callout(p)}{_table(_applies(SELLER_ROWS, p), "CST Roadmap")}'
            # Casey, 25 Nov 2026: "add link to the bottom so people can print Comparison"
            f'<p style="text-align:center;margin:14px 0 0;"><a href="{PRINT_PDF}" target="_blank" rel="noopener" '
            'style="font:700 15px Georgia,serif;color:#1F2A44;text-decoration:none;border-bottom:2px solid #B8902F;'
            'padding-bottom:2px;">Print the Comparison (PDF) &rarr;</a></p>'
            '</div></section>\n')


def buyer_section(p, b):
    if not enabled(p, b):
        return ""
    return (f'<style>{CSS}</style><section><div class="wrap">'
            '<h2 class="st">CST Buyer Portal vs Zillow vs Compass</h2>'
            '<p class="ss">What buyers get from this portal, from Zillow, and from Compass.</p>'
            f'{_table(_applies(BUYER_ROWS, p, buyer=True), "CST Buyer Portal")}</div></section>\n')


def email_html(p, root=None):
    """Casey, 25 Nov 2026: the potential seller email ends with "CST vs Zillow
    vs Compass at bottom instead of track record". Inline styles only, so it
    survives mail clients; the plain-text copy reads it row by row."""
    cv = _customary(p)
    usd = ""
    if cv:
        miss = round(cv * OFF_MKT / 100 / 1000) * 1000
        usd = f" On a ${round(cv, -4):,.0f} home, that is ${miss:,.0f} too high or too low."
    th = 'style="padding:7px 8px;background:#1F2A44;color:#fff;font-size:12px;letter-spacing:.06em;text-align:center;"'
    th0 = 'style="padding:7px 8px;background:#1F2A44;color:#fff;font-size:12px;letter-spacing:.06em;text-align:left;"'
    td = 'style="padding:5px 8px;border-bottom:1px solid #E5DDC9;"'
    tc = 'style="padding:5px 8px;border-bottom:1px solid #E5DDC9;text-align:center;font-weight:700;"'
    def mark(on, bad=False):
        if not on:
            return '<span style="color:#B5AD9A;">&ndash;</span>'
        return f'<span style="color:{"#B3261E" if bad else "#8A6A2E"};">&#10003;</span>'
    body = ""
    for r in _applies(SELLER_ROWS, p):
        t, z, c = r[:3]
        us = r[3] if len(r) > 3 else True
        bad = r[4] if len(r) > 4 else False
        body += (f"<tr><td {td}>{t}</td><td {tc}>{mark(us, bad)}</td>"
                 f"<td {tc}>{mark(z, bad)}</td><td {tc}>{mark(c, bad)}</td></tr>")
    return (f'<h3 style="margin:28px 0 6px;">CST Roadmap vs Zillow vs Compass</h3>\n'
            f'<p style="margin:0 0 10px;"><b style="color:#B3261E;">AI Can Not Price Your Home.</b> '
            f"Zillow&rsquo;s own median Zestimate error for homes not on the market is {OFF_MKT:.2f}%.{usd}</p>\n"
            '<table style="border-collapse:collapse;width:100%;font-size:14px;font-family:inherit;">'
            f"<tr><th {th0}>What You Get</th><th {th}>CST Roadmap</th><th {th}>Zillow</th><th {th}>Compass</th></tr>"
            f"{body}</table>\n"
            f'<p style="font-size:11px;color:#71695A;">{FOOT}</p>\n'
            + (f'<p><a href="{root.rstrip("/")}/{PRINT_PDF}">Print the Comparison (PDF)</a></p>\n' if root else ""))
