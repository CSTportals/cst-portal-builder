"""The CST Ten Cylinder Pricing Engine panel for the Seller Roadmap.

Casey, 17 Nov 2026: integrate the Ten Cylinder Pricing Engine graphic into
the Authenticated Prices model; "the price engine section should be on every
roadmap." Cylinders 1-6 are the standard, performed on every home; 7-10 are
used when applicable. Two filters -- Market Condition and Threshold -- turn the
authenticated value into the price.

Each card shows what that factor read for THIS home, from the property file.
Nothing is invented: a cylinder with nothing to work on says "Not applied" /
"Not firing". Cards show the EVIDENCE (ratios, ranges, $/SF), not a dollar
value per cylinder, and cylinders 3 and 4 read exactly what the comp table
prints.

Overrides: "engine": {"8": "text", "8_firing": true, "filter": "...",
"threshold": "..."}. "engine_panel": false turns the panel off.
"""
import re
from pricing import money, abbrev, reality_check

IMG = "CST_Pricing_Engine.jpg"

# Casey's 17 Nov 2026 (09:37) graphic order.
NAMES = ["Age &amp; Size", "Price Range", "PPSF Adjuster",
         "Assessment Adjustment", "Anomaly Adjustment", "Inflation Cylinder",
         "Neighborhood", "Premium or Discount (from Purchase)",
         "Extraordinary Improvement Adjustment", "Detriments Adjustment"]


def enabled(p):
    return bool(p.get("engine_panel", True))


def _rows(p):
    c = p.get("comps") or {}
    rows = c.get("rows") if isinstance(c, dict) else c
    out = []
    for r in rows or []:
        try:
            addr, built, sf, lot, assess, price = r[:6]
            out.append(dict(addr=addr, built=int(built), sf=float(sf),
                            assess=float(assess or 0), price=float(price)))
        except (ValueError, TypeError):
            continue
    return out


def _summary(p, word):
    c = p.get("comps") or {}
    for r in (c.get("summary") if isinstance(c, dict) else None) or []:
        if word.lower() in str(r[0]).lower():
            return r
    return None


def _schools(p):
    for col in p.get("premium_rating") or []:
        for blk in col:
            if isinstance(blk, dict) and blk.get("label") == "Schools":
                return blk.get("items") or []
    return []


def cylinders(p, coming_soon=0, conservative=True, stats=None, relaunch=0):
    v, s = p["values"], p.get("subject", {})
    rows = _rows(p)
    new = bool(p.get("new_construction"))
    c = p.get("comps") or {}
    a = _summary(p, "Age")
    # Computed in this order, placed by the graphic's order at the end.
    age = pr = pp = asm = nb = prem = infl = anom = extra = detr = None

    t = f'Your home: built {s.get("built", "&ndash;")}, {int(s.get("sf", 0)):,} SF.'
    if a:
        t += f" Age &amp; size comps average built {a[1]}, {int(a[2]):,} SF."
    age = (True, t)

    if rows:
        lo, hi = min(r["price"] for r in rows), max(r["price"] for r in rows)
        prs = _summary(p, "Price")
        pr = (True, f"Comparables sold {money(lo)}&ndash;{money(hi)}"
                    + (f" (average {money(prs[5])})." if prs else "."))
    else:
        pr = (False, "Not firing &mdash; no comparable sales on file.")

    a_ppsf = a_pct = None
    if a:
        e = (c.get("summary_ppsf") or {}).get(a[0]) if isinstance(c, dict) else None
        adj = e.get("ppsf") if isinstance(e, dict) else None
        a_ppsf = adj or (a[5] / a[2] if a[2] else None)
        a_pct = a[5] / a[4] * 100 if a[4] else None
    sv = (c.get("subject_value") if isinstance(c, dict) else None) or v["customary"]
    sp = sv / s["sf"] if s.get("sf") else None
    if sp:
        pp = (True, f"Your home at Customary Value: ${sp:,.0f} per SF"
                    + (f"; age &amp; size comps ${a_ppsf:,.0f} per SF, adjusted for size and age."
                       if a_ppsf else ", adjusted for size and age."))
    else:
        pp = (False, "Not firing &mdash; no square footage on file.")

    if new or not s.get("assessment"):
        asm = (False, "Not firing &mdash; new construction has no settled assessment.")
    else:
        asm = (True, f'Customary Value is {sv / s["assessment"] * 100:.0f}% of your '
                     f'{money(s["assessment"])} assessment'
                     + (f"; age &amp; size comps sold at {a_pct:.0f}%." if a_pct else "."))

    sch = _schools(p)
    nb = (True, f'{len(rows)} comparables from {p.get("subdivision") or p.get("city", "the area")}'
                + (f'; schools: {", ".join(x.replace(" School", "") for x in sch[:3])}.' if sch else "."))

    vs_step = next((st for st in (p.get("value_story") or {}).get("steps", [])
                    if re.search(r"discount|premium", st.get("head", ""), re.I)), None)
    if vs_step:
        prem = (True, f'{vs_step["head"]} {vs_step["figure"]}: '
                      f'{vs_step["text"].split(". ")[0].rstrip(".")}.')
    else:
        prem = (False, "Not applied &mdash; no premium or discount from purchase "
                       "carried into today&rsquo;s value.")

    if new:
        infl = (False, "Not firing &mdash; new construction is priced against today&rsquo;s builds.")
    else:
        rc = reality_check(v.get("customary_unadjusted") or v["customary"])
        infl = (True, "Market appreciation since 2019 measured against inflation: "
                      f'inflation alone would put this home at {abbrev(rc["inflation"])}.')

    an = p.get("anomalies") or (c.get("anomalies") if isinstance(c, dict) else None) or []
    anom = ((True, "Adjusted for: " + "; ".join(an) + ".") if an else
            (True, "Tested: no market irregularities among the comparables required an adjustment."))

    up = (v.get("customary") or 0) - (v.get("customary_unadjusted") or v.get("customary") or 0)
    extra = ((True, f"Improvements beyond the comps add {money(up)} to Customary Value.") if up > 0 else
             (False, "Not firing &mdash; no improvements beyond what the comparables already carry."))

    probs = (p.get("recovery") or {}).get("problems") or []
    adj = v.get("adjustment") or {}
    if adj.get("amount", 0) > 0:
        detr = (True, v.get("customary_note") or f'Customary Value adjusted down {money(adj["amount"])} for {adj.get("reason", "")}.')
    elif probs:
        detr = (True, f"{len(probs)} issues identified &mdash; see the recovery plan.")
    else:
        detr = (False, "Not firing &mdash; no condition, functional or external issues identified.")

    out = [age, pr, pp, asm, anom, infl, nb, prem, extra, detr]
    ov = p.get("engine") or {}
    out = [(ov.get(f"{i}_firing", f), ov.get(str(i), t)) for i, (f, t) in enumerate(out, 1)]

    m, st = p.get("market") or {}, stats or {}
    name = m.get("name", "Local market")
    if st.get("control"):
        mkt = (f'{name}: {st["control"]} Market'
               + (f', {st["under_contract"]} of homes under contract.' if st.get("under_contract") else "."))
    else:
        mkt = f'{name}: {m.get("subhead", "").rstrip(".")}.'
    thr = ""
    if relaunch and not coming_soon:
        mkt += " Strategy: <b>relaunch</b> &mdash; reposition the listing to the buyers it has missed."
        band = relaunch + 1 if relaunch % 1000 == 999 else 0
        thr = (f"Relaunch at <b>{money(relaunch)}</b>"
               + (f", just under the {money(band)} search band" if band else "")
               + f" &mdash; placing the home in front of the buyers shopping under its "
                 f"current list price of {money(p['current_list'])}.")
    elif (p.get("values") or {}).get("coming_soon_override"):
        mkt += (f" Strategy: <b>set by the CST Pricing Team</b> &mdash; "
                f"{'conservative' if conservative else 'aggressive'} market, priced for this home.")
    else:
        mkt += (" Strategy: <b>conservative</b> &mdash; price under Customary Value to draw the "
                "first-week buyer." if conservative else
                " Strategy: <b>aggressive</b> &mdash; buyers are competing, so price over Customary Value.")
    if coming_soon:
        band = coming_soon + 1 if coming_soon % 1000 == 999 else 0
        _side = "under" if coming_soon < v["customary"] else "over"
        if ov.get("hand_set") or (p.get("values") or {}).get("coming_soon_override"):
            thr = (f"Coming Soon at <b>{money(coming_soon)}</b>"
                   + (f", just under the {money(band)} search band" if band else "")
                   + f" &mdash; set by the CST Pricing Team {_side} the Customary Value of "
                     f'{abbrev(v["customary"])}, at the price point buyers in this range search.')
        else:
            thr = (f"Coming Soon at <b>{money(coming_soon)}</b>"
                   + (f", just under the {money(band)} search band" if band else "")
                   + f" &mdash; the first buyer threshold {_side} the "
                     f'Customary Value of {abbrev(v["customary"])}, so the home shows up in the '
                     f"searches of every buyer shopping that range.")
    return out, (ov.get("filter", mkt), ov.get("threshold", thr))


CSS = """
.eng{margin:6px 0 34px}
.eng-img{width:100%;border-radius:10px;display:block}
.eng-lede{font-style:italic;color:#5a5346;margin:14px 0 18px;text-align:center}
.eng-grid{display:grid;gap:10px}.eng-6{grid-template-columns:repeat(3,1fr)}.eng-4{grid-template-columns:repeat(4,1fr)}
.eng-g{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#8a6a2e;margin:14px 0 7px}
.eng-c{border:1px solid #d8cba8;border-radius:10px;padding:10px 11px;background:#fffdf7;font-size:12.5px;line-height:1.4}
.eng-c.off{background:#f4f2ee;color:#8b857a;border-color:#e2ddd3}
.eng-n{display:inline-block;width:22px;height:22px;border-radius:50%;background:#b08d3c;color:#fff;font-weight:700;
  text-align:center;line-height:22px;font-size:12px;margin-right:6px}
.eng-c.off .eng-n{background:#b9b3a7}
.eng-h{font-weight:700;font-size:12px;letter-spacing:.03em;text-transform:uppercase;color:#1c2a44;margin-bottom:5px}
.eng-c.off .eng-h{color:#8b857a}
.eng-fs{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}
.eng-dx{margin:16px 0 0;border:2px solid #B08A3E;border-left-width:6px;border-radius:10px;background:#FFF8E8;padding:14px 18px;}
.eng-dx-h{font-family:'Playfair Display',Georgia,serif;font-weight:700;color:#1F2A44;font-size:16px;margin-bottom:6px;display:flex;align-items:center;gap:10px;}
.eng-dx p{margin:0;font-size:15px;line-height:1.55;color:#221C14;}
.eng-dx-flag{margin-top:6px;font-size:12px;font-weight:700;color:#8A6A2E;letter-spacing:.02em;}
.eng-f{border-radius:10px;background:#1c2a44;color:#f3e6c4;padding:13px 16px;font-size:14px;line-height:1.5;
  text-align:center;break-inside:avoid;page-break-inside:avoid}
.eng-f b{color:#fff}
.eng-fl{font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:12px;color:#d9b866;display:block;margin-bottom:3px}
@media(max-width:820px){.eng-6,.eng-4{grid-template-columns:repeat(2,1fr)}.eng-fs{grid-template-columns:1fr}}
@media print{
  section:has(.eng){break-before:page;page-break-before:always}
  .eng{margin:0 0 14px}
  .eng-fs,.eng-grid{break-inside:avoid;page-break-inside:avoid}
  .eng-img{max-height:2.6in;width:auto;margin:0 auto}
  .eng-lede{margin:8px 0 10px;font-size:12px}
  .eng-grid{gap:6px}.eng-g{margin:8px 0 4px;font-size:9.5px}
  .eng-c{padding:6px 9px;font-size:10.5px;line-height:1.3}.eng-h{font-size:10.5px;margin-bottom:3px}
  .eng-fs{gap:6px;margin-top:8px;grid-template-columns:1fr}
  .eng-f{padding:9px 12px;font-size:11.5px}
}
"""


def panel(p, coming_soon=0, conservative=True, stats=None, relaunch=0):
    if not enabled(p):
        return ""
    cyl, (mkt, thr) = cylinders(p, coming_soon, conservative, stats, relaunch)

    # Casey, 24 Nov 2026 (11040 Heathland): a cylinder's own diagnosis of
    # this home, in his words, shown under the engine and flagged on the
    # card.  "engine_diagnosis": {"4": "This home has a unique issue: ..."}
    diag = {str(k): v for k, v in (p.get("engine_diagnosis") or {}).items() if v}

    def card(i, f, t):
        if str(i) in diag:
            t += '<div class="eng-dx-flag">Diagnosis below &darr;</div>'
            f = True
        return (f'<div class="eng-c{"" if f else " off"}"><div class="eng-h">'
                f'<span class="eng-n">{i}</span>{NAMES[i-1]}</div>{t}</div>')
    core = "".join(card(i, f, t) for i, (f, t) in enumerate(cyl[:6], 1))
    case = "".join(card(i, f, t) for i, (f, t) in enumerate(cyl[6:], 7))
    filt = f'<div class="eng-f"><span class="eng-fl">Market Condition Filter</span>{mkt}</div>'
    if thr:
        filt += f'<div class="eng-f"><span class="eng-fl">Threshold Filter</span>{thr}</div>'
    dx = "".join(
        f'<div class="eng-dx"><div class="eng-dx-h"><span class="eng-n">{k}</span>'
        f'Pricing Engine Diagnosis &middot; Cylinder {k}, {NAMES[int(k)-1]}</div>'
        f'<p>{v}</p></div>' for k, v in sorted(diag.items(), key=lambda kv: int(kv[0])))
    return (f'<style>{CSS}</style><div class="eng">'
            f'<img class="eng-img" src="{IMG}" alt="The CST Ten Cylinder Pricing Engine">'
            f'<p class="eng-lede">Cylinders 1&ndash;6 are the standard, performed on every home; '
            f'cylinders 7&ndash;10 are used when applicable. Two filters then turn the '
            f'authenticated value into the price.</p>'
            f'<div class="eng-g">Standard &mdash; cylinders 1&ndash;6</div>'
            f'<div class="eng-grid eng-6">{core}</div>'
            f'<div class="eng-g">When applicable &mdash; cylinders 7&ndash;10</div>'
            f'<div class="eng-grid eng-4">{case}</div>'
            f'<div class="eng-fs">{filt}</div>{dx}</div>\n')
