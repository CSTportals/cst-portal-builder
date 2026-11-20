#!/usr/bin/env python3
"""Reprice a property file from the comp ladder (pricing_model.ladder) and
write the comps, values, market map solds, snapshot rows and the
pricing_model block the Pricing Math workbook reads.

    from ladder_apply import apply
    apply("properties/9311_talisman.json", subject_es="wolftrap", city="Vienna",
          xy=(38.91, -77.26), locate={"502 macarthur ave ne": (lat, lng), ...})
"""
import glob
import json
from datetime import date

import pricing_model as pm

SALES = lambda: pm.load(glob.glob('/mnt/user-data/attachments/*/*Sales_withdrawn.csv')[0])
ACTIVE = lambda: pm.load(glob.glob('/mnt/user-data/attachments/*/*active_pending.csv')[0])


def apply(path, subject_es, city, xy, locate, aliases=(), asof=date(2026, 11, 7), upgrades=None,
          subject_label=None):
    p = json.load(open(path))
    sj = p["subject"]
    s = {"address": p["address"], "sub": p.get("subdivision", ""), "built": sj["built"], "sf": sj["sf"],
         "assess": sj["assessment"]}
    if p.get("subdivision") is None:
        s["sub"] = (p.get("pricing_model") or {}).get("sub", "")
    S, A = SALES(), ACTIVE()
    P = [c for c in A if c["status"] == "PND"]
    loc = lambda a: locate.get(a.lower())
    level, comps, v = pm.ladder(s, S, P, asof, subject_es, xy, city, aliases=aliases, locate=loc)
    if not v or v["comps_used"] < pm.MIN_COMPS:
        return level, None, comps
    comps.sort(key=lambda c: (c["mi"] is None, c["mi"] or 0))
    rs = pm.GREATSCHOOLS.get(subject_es)
    rows, pmc, solds, snap = [], [], [], []
    for c in comps:
        es, r = c["es"], pm.GREATSCHOOLS.get(c["es"])
        name = c["address"].replace("Macarthur", "MacArthur")
        pend = c["status"] == "PND"
        when = ("pending; counted at full list" if pend else
                f"closed {c['close_date'].strftime('%-m/%-d/%y')}"
                + (f"; net of ${c['conc']:,.0f} concessions" if c["conc"] else ""))
        adj = ""
        if es not in (subject_es, *aliases) and r != rs:
            adj = (f" School-adjusted {(rs - r) * 2.5:+.1f}% ({es.title()} {r} vs "
                   f"{subject_es.title()} {rs}) from ${c['raw']:,.0f}.")
        mi = f"{c['mi']:.1f} mi away" if c["mi"] is not None else "location not found (1x, not mapped)"
        if not c["include"]:
            tail = f" EXCLUDED: {c['excluded_for']}."
        elif c.get("best"):
            tail = " Best comp: closest on size, age, assessment and school (2x)."
        else:
            tail = f" Weight {c['w']:.2f} by distance."
        if c.get("kept_close"):
            tail += f" Kept: within 1/2 mile ({c['kept_close']})."
        note = f"{es.title() or 'School not listed'} ES (GreatSchools {r}), {mi}; {when}.{adj}{tail}"
        w = 2 if c.get("best") else (pm.NEIGHBOR_W if c["neighbor"] else round(c["dist_w"], 6))
        pmc.append([name, int(c["dom"] or 0), int(c["built"]), int(c["sf"]), int(c["lot"] or 0),
                    int(c["assess"]), c["list"], round(c["price"]), w, note]
                   + ([round(c["mi"], 3)] if c["mi"] is not None else []))
        if c["include"]:
            rows.append([name, int(c["built"]), int(c["sf"]), int(c["lot"] or 0), int(c["assess"]),
                         round(c["price"])])
            xy_c = loc(c["address"])
            if xy_c:
                solds.append({"address": name, "sale": int(round(c["raw"])),
                              "status": "Pending" if pend else "Sold", "lat": xy_c[0], "lng": xy_c[1]})
            snap.append(["PND" if pend else "CLS", name, int(c["dom"] or 0),
                         int(c["list"]) if pend else None, None if pend else int(round(c["raw"]))])
    inc = [c for c in comps if c["include"]]
    W = sum(c["w"] for c in inc)
    lot = round(sum((c["lot"] or 0) * c["w"] for c in inc) / W)
    cu = v["customary"]
    vals = p["values"]
    for k in ("customary_unadjusted", "significant_upgrades", "customary_note", "adjustment"):
        vals.pop(k, None)
    vals.update(customary=cu, customary_list=cu, dated=round(cu * 0.9), premium=round(cu * 1.08), upgrades=0)
    if upgrades:
        pm.apply_upgrades(vals, upgrades)
        vals["adjustment"] = {"amount": -round(upgrades / 3), "reason": f"one third of ${upgrades:,.0f} in upgrades"}
    vals["worksheet_note"] = (f"{date.today():%-d %b %Y}: CST Pricing Model comp ladder -- {level}. "
                              f"{v['comps_used']} comps." + (f" Upgrades ${upgrades:,.0f}." if upgrades else ""))
    lab = f"Weighted Average &mdash; {v['comps_used']} sales"
    p["comps"] = {"rows": rows, "summary": [[lab, round(v["avg"]["built"]), v["avg"]["sf"], lot,
                                              v["avg"]["assess"], v["avg"]["price"]]],
                  "summary_ppsf": {}, "subject_value": vals["customary"]}
    keep = [r for r in (p.get("market_snapshot") or {}).get("rows", []) if r[0] not in ("CLS", "PND")]
    p.setdefault("market_snapshot", {"label": p.get("market", {}).get("name", ""),
                                     "source": "Bright MLS, Nov 7, 2026."})["rows"] = snap + keep
    p["market_map"]["solds"] = solds
    p["market_map"]["subject"] = list(xy)
    lo, hi = sj["assessment"] * (1 - pm.SP_UNDER), sj["assessment"] * (1 + pm.SP_OVER)
    p["pricing_model"] = {
        "ignore_list": True, "list": None, "comps": pmc,
        "source": (f"Comps: Bright MLS, Nov 7 2026 export. Comp ladder ({level}): standing = 90 days, own school, "
                   f"built +/-12 yrs, SF +/-600; expansion 1 = 120 days, +/-15 yrs, +/-750 SF, + closest comparable "
                   f"school; expansion 2 = whole town, school-adjusted 2.5% per GreatSchools point. Sale price "
                   f"10% under to 30% over the subject's assessment (${lo:,.0f} to ${hi:,.0f}). Net = close minus "
                   f"concessions. Exclusions: under 100% of assessment, over 20% above the norm, lot over 40% "
                   f"under average; within 1/2 mile always stays. Weights: best comp 2x, others 2x at the door to "
                   f"1x at 2+ miles. List price ignored.")}
    json.dump(p, open(path, "w"), indent=1)
    return level, v, comps
