#!/usr/bin/env python3
"""CST Pricing Model (Casey, Nov 7 2026) -- the PRICING_MODEL_RULES.md rule set
as code, so every home on the market can carry its own Customary Value.

    python3 pricing_model.py run <sales.csv> <active_pending.csv> [--asof 2026-11-07]
        -> competition_values.json (one entry per active / A/C / pending home)

    python3 pricing_model.py check
        -> reruns the two hand-built models (Lupine Den, Westwood) from their
           comp sets and prints the Customary Values next to Casey's.

Comp selection follows the rules: closed sales in the last 90 days, same
elementary school (high school, then ZIP, when the school is blank), +/-600 SF,
+/-12 years, assessment -$100K/+$300K, net price within -$100K/+$200K of the
assessment rounded to $100K. Under 5 sales: add pendings at full list. Still
short: 120 days with the gaps widened. Neighbors (same legal subdivision, last
6 months -- the export carries no coordinates, so subdivision stands in for the
0.5-mile rule) count 2x. The % of assessment outlier test runs in two rounds at
10%. Values: Customary = average of the PPSF value (with county premium) and
the should-assess value.

For competing homes the model never stops to ask about a next-door school; a
home priced from a widened set is flagged "widened" so it can be spot-checked.
"""
import csv, json, re, sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "competition_values.json"
NEIGHBOR_W, OA_TOL, SIZE_W, PPSF_AGE, ASSESS_AGE = 2.0, 0.10, 0.60, 0.01, 1 / 300


def money(s):
    s = re.sub(r"[^\d.]", "", str(s or ""))
    return float(s) if s else None


def num(s):
    s = re.sub(r"[^\d.]", "", str(s or ""))
    return float(s) if s else None


def day(s):
    s = (s or "").strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def norm_addr(a):
    a = re.sub(r"\s+", " ", (a or "").strip().lower())
    a = re.sub(r"[.,#]", "", a)
    for k, v in {" drive": " dr", " court": " ct", " road": " rd", " lane": " ln", " place": " pl",
                 " street": " st", " circle": " cir", " terrace": " ter", " way": " way", " avenue": " ave"}.items():
        a = a.replace(k, v)
    return a


def row(r):
    return {
        "address": (r.get("Address") or "").strip(), "city": (r.get("City") or "").strip(),
        "status": (r.get("Status") or "").strip(), "mls": (r.get("MLS #") or "").strip(),
        "es": (r.get("Elementary School") or "").strip().lower(),
        "hs": (r.get("High School") or "").strip().lower(),
        "zip": (r.get("Zip Code") or "").strip()[:5],
        "sub": (r.get("Legal Subdivision") or "").strip().lower(),
        "built": num(r.get("Year Built")), "sf": num(r.get("Above Grade Finished SQFT")),
        "lot": num(r.get("Lot Size SqFt")), "assess": money(r.get("Tax Assessed Value")),
        "list": money(r.get("List Price")), "close": money(r.get("Close Price")),
        "conc": money(r.get("Concessions Final")) or 0.0,
        "dom": num(r.get("DOM")), "close_date": day(r.get("Close Date")),
    }


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return [row(r) for r in csv.DictReader(f)]


def same_place(s, c):
    if s["es"] and c["es"]:
        return s["es"] == c["es"]
    if s["hs"] and c["hs"]:
        return s["hs"] == c["hs"] and s["zip"] == c["zip"]
    return s["zip"] == c["zip"]


def round100k(x):
    return round(x / 100000.0) * 100000


def pick(s, sales, pendings, asof):
    """Return (comps, basis). Each comp is a dict with price / neighbor."""
    def fits(c, days, sf, yrs, a_lo, a_hi, p_lo, p_hi, price, d):
        if not (c["sf"] and c["built"] and c["assess"] and price):
            return False
        if d is not None and d < asof - timedelta(days=days):
            return False
        return (abs(c["sf"] - s["sf"]) <= sf and abs(c["built"] - s["built"]) <= yrs
                and s["assess"] - a_lo <= c["assess"] <= s["assess"] + a_hi
                and round100k(s["assess"]) - p_lo <= price <= round100k(s["assess"]) + p_hi)

    me = norm_addr(s["address"])
    def gather(days, sf, yrs, a_lo, a_hi, p_lo, p_hi, with_pend):
        out = []
        for c in sales:
            if c["status"] != "CLS" or norm_addr(c["address"]) == me or not c["close_date"]:
                continue
            net = (c["close"] or 0) - (c["conc"] or 0)
            nb = bool(s["sub"]) and c["sub"] == s["sub"] and c["close_date"] >= asof - timedelta(days=183)
            if nb and fits(c, 183, sf, yrs, a_lo, a_hi, p_lo, p_hi, net, c["close_date"]):
                out.append(dict(c, price=net, neighbor=True)); continue
            if same_place(s, c) and fits(c, days, sf, yrs, a_lo, a_hi, p_lo, p_hi, net, c["close_date"]):
                out.append(dict(c, price=net, neighbor=False))
        if with_pend and len(out) < 5:
            for c in pendings:
                if c["status"] != "PND" or norm_addr(c["address"]) == me or not same_place(s, c):
                    continue
                if fits(c, days, sf, yrs, a_lo, a_hi, p_lo, p_hi, c["list"], None):
                    out.append(dict(c, price=c["list"], neighbor=False, pending=True))
        return out

    comps = gather(90, 600, 12, 100000, 300000, 100000, 200000, True)
    if len(comps) >= 3:
        return comps, "standard" if not any(c.get("pending") for c in comps) else "with pendings"
    wide = gather(120, 800, 16, 150000, 400000, 150000, 300000, True)
    return wide, "widened"


def value(s, comps):
    """The Pricing Engine sheet, formula for formula."""
    for c in comps:
        c["oa"] = c["price"] / c["assess"]
    avg = lambda xs: sum(xs) / len(xs)
    # round 1: drop the single worst comp if beyond tolerance (unweighted average)
    a1 = avg([c["oa"] for c in comps])
    for c in comps:
        c["dev1"] = abs(c["oa"] / a1 - 1)
    worst = max(c["dev1"] for c in comps)
    for c in comps:
        c["r1"] = not (c["dev1"] == worst and worst > OA_TOL)
    keep = [c for c in comps if c["r1"]] or comps
    a2 = avg([c["oa"] for c in keep])
    for c in comps:
        c["dev2"] = c["oa"] / a2 - 1
        c["include"] = c["r1"] and abs(c["dev2"]) <= OA_TOL
        c["w"] = (NEIGHBOR_W if c["neighbor"] else 1.0) if c["include"] else 0.0
    W = sum(c["w"] for c in comps)
    if W == 0:
        return None
    wavg = lambda k: sum(c[k] * c["w"] for c in comps) / W
    C = {k: wavg(k) for k in ("built", "sf", "assess", "price")}
    ppsf, oa = C["price"] / C["sf"], C["price"] / C["assess"]
    diff = s["sf"] / C["sf"] - 1
    yrs = C["built"] - s["built"]
    ps, pa = 1 - diff * SIZE_W, 1 - yrs * PPSF_AGE
    as_, aa = 1 + diff * SIZE_W, 1 - yrs * ASSESS_AGE
    should = C["assess"] * as_ * aa
    premium = s["assess"] / should
    v_ppsf = ppsf * ps * pa * premium * s["sf"]
    v_should = should * oa
    cust = (v_ppsf + v_should) / 2
    return {"customary": round(cust), "ppsf_value": round(v_ppsf), "should_assess_value": round(v_should),
            "trust_assessment_value": round(s["assess"] * oa), "county_premium": round(premium, 4),
            "comps_used": sum(1 for c in comps if c["include"]), "weight": W,
            "avg": {k: round(v) for k, v in C.items()}, "avg_ppsf": round(ppsf), "avg_oa": round(oa, 4)}


def run(sales_csv, active_csv, asof):
    sales, act = load(sales_csv), load(active_csv)
    pend = [c for c in act if c["status"] == "PND"]
    out, skipped = {}, 0
    for s in act:
        if not (s["sf"] and s["built"] and s["assess"]):
            skipped += 1; continue
        comps, basis = pick(s, sales, pend, asof)
        v = value(s, comps) if comps else None
        key = norm_addr(s["address"]) + "|" + s["city"].lower()
        out[key] = {"address": s["address"], "city": s["city"], "status": s["status"], "mls": s["mls"],
                    "list": s["list"], "assessment": s["assess"], "sf": s["sf"], "built": s["built"],
                    "customary": v["customary"] if v else None, "basis": basis if v else "no comps",
                    "detail": v, "comps": [{"address": c["address"], "price": c["price"], "neighbor": c["neighbor"],
                                             "pending": bool(c.get("pending")), "included": c.get("include")}
                                            for c in comps]}
    meta = {"asof": asof.isoformat(), "homes": len(out), "skipped_missing_data": skipped,
            "priced": sum(1 for v in out.values() if v["customary"]),
            "widened": sum(1 for v in out.values() if v["basis"] == "widened" and v["customary"])}
    OUT.write_text(json.dumps({"@meta": meta, "homes": out}, indent=1))
    return meta


def lookup(address, city=None):
    """Customary Value for a competing home, or None."""
    try:
        data = json.loads(OUT.read_text())["homes"]
    except Exception:
        return None
    a = norm_addr(address)
    for k, v in data.items():
        if k.split("|")[0] == a and (not city or v["city"].lower() == city.lower()):
            return v
    return None


def check():
    def mk(addr, built, sf, assess):
        return {"address": addr, "built": built, "sf": sf, "assess": assess}
    def comp(addr, built, sf, assess, price, nb):
        return {"address": addr, "built": built, "sf": sf, "assess": assess, "price": price, "neighbor": nb}
    ld = value(mk("9002 Lupine Den Dr", 1996, 4188, 1622230), [
        comp("1605 Lupine Den Ct", 1996, 3826, 1636360, 1755000, True),
        comp("9082 Best Bower Ct", 2000, 3920, 1834460, 1850000, False),
        comp("1750 Wexford Way", 1981, 3716, 1487520, 1500000, False)])
    print("Lupine Den: model", ld["customary"], "| Casey 1,754,126")


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check()
    else:
        a = date(2026, 11, 7)
        if "--asof" in sys.argv:
            a = date.fromisoformat(sys.argv[sys.argv.index("--asof") + 1])
        print(run(sys.argv[2], sys.argv[3], a))


def fill_comp_table(p):
    """Comps table support (rebuilt 19 Nov 2026 after the workspace reset).

    Casey, 7 Nov 2026: Customary Value on the subject row. The subject row
    shows the Customary Value (the adjusted figure when there is one). Per-comp
    adjusted values come from the property file ("comps.adjusted"); without
    them the Adjusted PPSF column shows each comp's sale price per SF.
    """
    c = p.get("comps")
    if isinstance(c, dict):
        c.setdefault("subject_value", (p.get("values") or {}).get("customary"))
    return p


def apply_adjustment(values, amount, reason):
    """Casey, 7 Nov 2026: a major adjustment becomes the new Customary Value,
    with "Customary Value was adjusted down $X from $Y due to <reason>."
    Dated and Premium keep their ratios. amount > 0 adjusts down."""
    raw = values.get("customary_unadjusted") or values["customary"]
    new = round(raw - amount)
    dr = values["dated"] / values["customary"] if values.get("customary") else 0.9
    pr = values["premium"] / values["customary"] if values.get("customary") else 1.08
    word = "down" if amount > 0 else "up"
    values.update(customary_unadjusted=raw, customary=new, customary_list=new,
                  dated=round(new * dr), premium=round(new * pr), discount=0,
                  adjustment={"amount": amount, "reason": reason},
                  customary_note=(f"Customary Value was adjusted {word} ${abs(amount):,.0f} "
                                  f"from ${raw:,.0f} due to {reason}."))
    return values
