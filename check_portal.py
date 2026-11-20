#!/usr/bin/env python3.12
"""Standing-rules check for every portal this system builds.

Casey, 17 Oct 2026: "We have had some inconsistencies with picture in
headers, missing amenities and maps, ordering issues. Any way we could lock
it down so these issues happen less often?"

Every rule that has had to be fixed by hand is an assertion here. Run it
after a build and it either prints a clean line for the property or names
exactly what is missing, so a portal cannot quietly ship without its hero
photo, its amenities, its map, its links, or in the wrong section order.

    python3.12 check_portal.py                 # every property
    python3.12 check_portal.py 344_hites       # one, by prefix or file

Exit code is 1 when anything FAILS, so it can gate a batch build.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"


def _load(path):
    """A property file as the builders see it — overrides folded in.

    Any tool that reads a property file has to apply the overrides, or it
    checks a different property than the one that gets built. This was not
    hypothetical: 6029 Erinblair moved its buyer address into an `overrides`
    block and the collision check immediately reported a conflict that the
    build itself had already resolved.

    Silent here: the build log is where overrides are announced, and a check
    that reprints them buries the findings.
    """
    import overrides as ov
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    ov.apply(p, note=lambda _m: None)
    return p


def _address_clash(p):
    """Another property that deploys its buyer portal to the same address.

    One name per street makes the buyer namespace thin, and the protocol doc
    has warned since 10 Oct 2026 that two properties on the same street
    "would collide silently and one would serve the other's portal."
    6029 and 6032 Erinblair Loop were the first real pair and nothing
    checked for it, so the check exists now instead of the warning.

    Compares the address each portal is actually published to, so a pair
    that collides by convention passes once one of them carries an override.
    Returns (that property's street address, the shared URL) or None.
    """
    import build_portal as bp

    def addr_of(q):
        qb = q.get("buyer_portal") or {}
        return ((qb.get("deploy_to") or qb.get("url") or "").rstrip("/")
                or (f"https://{bp.buyer_slug(q)}.netlify.app"
                    if bp.buyer_slug(q) else None))

    mine, me = addr_of(p), (p.get("address") or "").strip().lower()
    if not mine:
        return None
    for f in sorted((HERE / "properties").glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            q = _load(f)
        except Exception:                                   # noqa: BLE001
            continue
        if (q.get("address") or "").strip().lower() == me:
            continue
        if addr_of(q) == mine:
            return (q.get("address") or f.stem, mine)
    return None

# The Roadmap order Casey locked down on 16 Oct 2026. Comparables first,
# Authenticated Values next, no Reality Check, then the needle, the
# competition, the strategy, and the Test at the end.
ROADMAP_ORDER = [
    "Appraisal-Quality Comparable Analysis",
    "Price Authenticated by CST Pricing Team",
    "Moving the Needle&trade;",
    "Current Competition",
    "CST Pricing Strategy",
    "The Test",
    "Preview",
    "Coming Soon",
]
# Casey, 19 Oct 2026: "Recovery roadmap should still have customary and
# premium pages over before Recovery strategy." Same valuation group, in the
# same order, with the two recovery sections where Predictive Analysis would
# be -- and Current Competition held back to sit under them, because the
# Buyer Portal card belongs straight after the competition.
RECOVERY_ROADMAP_ORDER = [
    "Appraisal-Quality Comparable Analysis",
    "Price Authenticated by CST Pricing Team",
    "Moving the Needle&trade;",
    "CST Pricing Strategy",
    "Reconciling Value and Price",
    "Recovery Strategy",
    "Current Competition",
]
# The one-page sheet keeps Reality Check at the bottom, after the prices.
SUMMARY_ORDER = [
    "Authenticated Values Based on Appraisal-Quality Comparables",
    "Current Market Conditions",
    "Preview",
    "Coming Soon",
    "The Launch",
    "Reality Check",
]


class Report:
    def __init__(self, name):
        self.name, self.fail, self.warn = name, [], []

    def bad(self, msg):
        self.fail.append(msg)

    def soft(self, msg):
        self.warn.append(msg)

    def check(self, cond, msg, hard=True):
        if not cond:
            (self.bad if hard else self.soft)(msg)
        return bool(cond)


def pages(pdf):
    try:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                             text=True).stdout
        m = re.search(r"^Pages:\s+(\d+)", out, re.M)
        return int(m.group(1)) if m else None
    except OSError:
        return None


def headings(html, classes):
    pat = r'class="(?:%s)"[^>]*>([^<]+)<' % "|".join(classes)
    return [h.strip() for h in re.findall(pat, html)]


def first_threshold_under(customary):
    inc = 25_000 if customary < 500_000 else 50_000
    return (int(customary) // inc) * inc - 1


def check_property(path):
    p = _load(path)
    pre = p.get("prefix") or Path(path).stem
    r = Report(pre)
    b = p.get("buyer_portal") or {}
    assets = HERE / (p.get("asset_dir") or "")
    sell = OUT / pre
    buy = OUT / f"{pre}_Buyer"

    # ---- the header photo, in BOTH places it is read from ---------------
    hero = p.get("hero_photo")
    if r.check(hero, "no hero_photo at the property root — the seller "
                     "portal, Roadmap, Pricing Summary and Buyer Report "
                     "cover all read it from there, not from buyer_portal"):
        r.check((assets / hero).exists(),
                f"hero_photo {hero} is not in {p.get('asset_dir')}")
    # The buyer page falls back to the property's own hero, so only a
    # property with neither is actually headerless.
    bhero = b.get("hero_photo") or hero
    if b:
        if r.check(bhero, "no hero photo anywhere — the buyer page header "
                          "will be a blank gradient"):
            bdir = HERE / (b.get("asset_dir") or p.get("asset_dir") or "")
            r.check((bdir / bhero).exists() or (assets / bhero).exists(),
                    f"the buyer portal's hero {bhero} is not in "
                    f"{bdir.name} or {assets.name}")

    # ---- the buyer portal's standing sections ---------------------------
    if b:
        ams = b.get("amenities") or []
        titles = [g.get("title") for g in ams]
        r.check(ams, "no Amenities and Transportation on the buyer portal")
        for want in ("Dining", "Shopping", "Getting Around"):
            r.check(any(want in (t or "") for t in titles),
                    f"Amenities is missing its {want} group", hard=False)
        for g in ams:
            n = len(g.get("items") or [])
            r.check(n >= 3, f'Amenities group "{g.get("title")}" has only '
                            f"{n} entries — the standard is 6", hard=False)

        lm = b.get("locator_map") or {}
        if r.check(lm, "no locator_map — The Neighborhood map will not "
                       "render on the buyer portal"):
            r.check(lm.get("center", {}).get("lat"),
                    "locator_map has no center coordinate")
            pins = lm.get("pins") or []
            r.check(len(pins) >= 6,
                    f"locator_map has only {len(pins)} pins", hard=False)
            for q in pins:
                if not (q.get("lat") and q.get("lng")):
                    r.bad(f'map pin "{q.get("name")}" has no coordinate')
            # A pin with no "min" is fine on the property file: the builder
            # computes the time from the coordinates and logs that it did.
            # What matters is that the built key carries times, checked below.

        r.check(b.get("schools"), "no schools on the buyer portal", hard=False)
        r.check(b.get("snapshot"), "no Market Snapshot block on the buyer "
                                   "portal", hard=False)
        r.check(b.get("facts"), "no facts strip on the buyer portal")

        # Casey, 20 Oct 2026: "Totally renovated is the most important
        # headline of any listing. Make it the lead headline when you see
        # it." So a portal that says renovated ANYWHERE but does not lead
        # with it is burying the strongest thing it has to say.
        _fh = b.get("feature_headlines") or []
        if _fh:
            _txt = json.dumps([b.get("features"), b.get("highlights"),
                               b.get("headline"), _fh[1:]]).lower()
            if "renovat" in _txt and "renovat" not in _fh[0]["head"].lower():
                r.soft("this home reads as renovated but the lead headline is "
                       f'"{_fh[0]["head"]}" — Totally Renovated goes first')

        # ---- the two portals linking to each other ----------------------
        r.check(p.get("portal_url"),
                "no portal_url — the buyer portal and the Local Market "
                "Snapshot have nothing to link back to")
        r.check(b.get("live") is True,
                'buyer_portal "live" is not true, so the seller portal shows '
                "the example link instead of this home's buyer portal",
                hard=False)

        # ---- the buyer address can only belong to one house ---------------
        # One name per street makes the namespace thin, and the protocol doc
        # has warned since 10 Oct that two properties on the same street
        # "would collide silently and one would serve the other's portal."
        # 6029 and 6032 Erinblair Loop are the first real pair, and nothing
        # checked for it — so the check exists now rather than the warning.
        # The test is the address each portal ACTUALLY deploys to, not the
        # slug: a pair that collides by convention is fine once one of them
        # carries an override, which is how 6029 Erinblair was settled.
        _clash = _address_clash(p)
        if _clash:
            r.check(False,
                    f"buyer address {_clash[1]} is also {_clash[0]}'s — one "
                    "of these portals would serve the other. Set "
                    '"deploy_to" and "url" on one of them.')

    # ---- the pricing rule -----------------------------------------------
    v = p.get("values") or {}
    if v.get("customary") and not v.get("coming_soon_override"):
        want = first_threshold_under(v["customary"])
        f = sell / f"{pre}_Pricing_Strategy_Summary.html"
        if f.exists():
            h = f.read_text(encoding="utf-8")
            m = re.search(r"Coming Soon Price.*?ps-v\">\$([\d,]+)<", h, re.S)
            if m:
                got = int(m.group(1).replace(",", ""))
                # A buyer's market may take the safe haven, which is lower.
                r.check(got <= want,
                        f"Coming Soon is ${got:,}, above the first threshold "
                        f"under Customary Value (${want:,}) — the 16 Oct "
                        "institutional rule allows no exceptions")

    # ---- the built documents --------------------------------------------
    rm = sell / f"{pre}_Roadmap.html"
    if rm.exists():
        h = rm.read_text(encoding="utf-8")
        # Casey, 31 Oct 2026: "Make these maps a part of every seller roadmap."
        _mm = p.get("market_map") or {}
        r.check(bool(_mm.get("solds")) and 'id="rmmSold"' in h,
                "Roadmap has no Comparable Sales map -- add market_map.solds "
                "(Google Places coordinates + each home's own Customary Value)",
                hard=not (p.get("buyer_portal") or {}).get("sponsor"))
        # Casey, 2 Nov 2026: "All seller portals need maps for comps and
        # competition."
        r.check(bool(_mm.get("listings")) and 'id="rmmList"' in h,
                "Roadmap has no competition map -- add market_map.listings "
                "(actives, A/C and pending, each with its own Customary Value)",
                hard=not (p.get("buyer_portal") or {}).get("sponsor"))
        # Casey, 13 Nov 2026: comps colored red / yellow / green, which needs
        # each sold's DOM and list price; listings only Active, A/C, Pending.
        _sp = (p.get("buyer_portal") or {}).get("sponsor")
        _nocol = [a.get("address") for a in _mm.get("solds") or []
                  if a.get("dom") is None or not a.get("list")]
        r.check(not _nocol, "Comparable Sales map: no DOM / list price for "
                + ", ".join(map(str, _nocol)) + " -- those pins cannot be colored",
                hard=not _sp)
        _bad = [f'{a.get("address")} ({a.get("status")})' for a in _mm.get("listings") or []
                if a.get("status") not in ("Active", "Active Under Contract", "Pending", "Coming Soon")]
        r.check(not _bad, "Current Market map: status must be Active, Active Under "
                "Contract (A/C) or Pending -- " + ", ".join(_bad), hard=not _sp)
        # Casey, 13 Nov 2026: every new listing ships the Sample Buyer Portal
        # tile (until the home has a real gallery) and a small buyer portal.
        try:
            from build_portal import buyer_portal_ready, is_example_home
            _ix = sell / "index.html"
            if (p.get("buyer_portal") and not _sp and not is_example_home(p)
                    and not buyer_portal_ready(p) and _ix.exists()):
                r.check("samplebuyerportal" in _ix.read_text(encoding="utf-8"),
                        "Seller portal has no Sample Buyer Portal tile")
            if p.get("buyer_portal") and not _sp and not is_example_home(p):
                r.check((sell.parent / f"{pre}_Buyer_Small" / "index.html").exists(),
                        "no small buyer portal -- run build_buyer_portal.py (it "
                        "writes <prefix>_Buyer_Small beside the full one)")
        except ImportError:
            pass
        secs = headings(h, ["section-title", "rc-head", "test-head"])
        r.check("Reality Check" not in secs,
                "the Roadmap still carries a Reality Check — it came off on "
                "16 Oct")
        rec = p.get("listing_status") == "recovery"
        order = RECOVERY_ROADMAP_ORDER if rec else ROADMAP_ORDER
        want = [s for s in order if s in secs]
        got = [s for s in secs if s in order]
        r.check(got == want,
                f"{'recovery ' if rec else ''}Roadmap sections are out of "
                "order: " + " / ".join(x.replace("&trade;", "") for x in got))
        if rec:
            for must in ("Reconciling Value and Price", "Recovery Strategy"):
                r.check(must in secs,
                        f"recovery Roadmap has no {must} section")
        if "Appraisal-Quality Comparable Analysis" not in secs:
            r.soft("no comparable analysis on the Roadmap — no comps on "
                   "the property file")
    else:
        r.soft("no Roadmap built yet")

    # Casey, 17 Oct 2026: every market update carries four gauges — % under
    # contract and average days on market, then the 30 day and 14 day reads.
    for doc, cls in ((f"{pre}_Roadmap.html", "cmi-t"),
                     (f"{pre}_Pricing_Strategy_Summary.html", "ps-tile-t"),
                     (f"{pre}_Local_Market_Snapshot.html", "cmi-t")):
        f = sell / doc
        if f.exists() and "cmi-wrap" in f.read_text(encoding="utf-8"):
            n = f.read_text(encoding="utf-8").count(f'class="{cls}"')
            # Four since 17 Oct; five once the market carries the success
            # rate the October 12 MSS added. Fewer than four is the fault.
            r.check(n in (4, 5),
                    f"{doc} market update shows {n} gauges, not four or five",
                    hard=False)

    ps = sell / f"{pre}_Pricing_Strategy_Summary.html"
    if ps.exists():
        secs = headings(ps.read_text(encoding="utf-8"),
                        ["ps-head", "ps-head ps-center"])
        if p.get("listing_status") != "recovery":
            want = [s for s in SUMMARY_ORDER if s in secs]
            got = [s for s in secs if s in SUMMARY_ORDER]
            r.check(got == want,
                    "Pricing Summary sections are out of order: "
                    + " / ".join(got))
            r.check(secs and secs[-1] == "Reality Check",
                    "Reality Check is not the last section on the Pricing "
                    "Summary", hard=False)

    # Casey, 18 Oct 2026: "For Pricing strategy back page use this track
    # record on all summaries." One record, every sheet — so a Summary whose
    # back page carries some other track record is a build that missed.
    if ps.exists():
        h = ps.read_text(encoding="utf-8")
        if "tr-band-t" in h:
            # The band is titled "Track Record Comparison" from 18 Oct, so
            # the title no longer says WHICH record is in the table. Count
            # the rows against the record page instead: that is the fact the
            # check exists to protect, and it survives a rename.
            src = HERE / "templates" / "CST_Resales.html"
            want = None
            if src.exists():
                # Body rows only: the <thead> carries a <tr> of its own.
                body = re.search(r"<tbody>(.*?)</tbody>",
                                 src.read_text(encoding="utf-8"), re.S)
                want = len(re.findall(r"<tr>", body.group(1))) if body else None
            got = len(re.findall(r'<tr><td class="tr-a"', h))
            r.check(want is None or got == want,
                    f"the Pricing Summary back page has {got} sales, the CST "
                    f"resale record has {want} — rebuild this property")

    for doc, limit in ((f"{pre}_Buyer_Report.pdf", 2),
                       (f"{pre}_Pricing_Strategy_Summary.pdf", 2)):
        f = sell / doc
        if f.exists():
            n = pages(f)
            r.check(n is None or n <= limit,
                    f"{doc} is {n} pages — the limit is {limit}")

    # ---- the buyer portal's copy of the printable report ----------------
    if b.get("pricing_pdf"):
        a, c = sell / b["pricing_pdf"], buy / b["pricing_pdf"]
        if a.exists() and c.exists() and b.get("sponsor"):
            # A sponsored portal carries its own sponsor-branded render of
            # the report; it must just be newer than the seller's.
            r.check(c.stat().st_mtime >= a.stat().st_mtime,
                    "the sponsored Buyer Report in the buyer portal is older "
                    "than the seller's -- rebuild the buyer portal")
            r.check(pages(c) is None or pages(c) <= 2,
                    f"sponsored Buyer Report is {pages(c)} pages -- the limit is 2")
        elif a.exists() and c.exists():
            r.check(a.read_bytes() == c.read_bytes(),
                    "the Buyer Report inside the buyer portal is NOT the one "
                    "in the seller folder — rebuild the seller portal first, "
                    "then the buyer portal")
        elif a.exists() and not c.exists():
            r.soft("buyer portal has not been built since the report was")

    # ---- the buyer page actually carries its sections --------------------
    bi = buy / "index.html"
    if bi.exists():
        h = bi.read_text(encoding="utf-8")
        if 'id="locmap"' in h:
            r.check(re.search(r'class="locmap-key"', h)
                    and re.search(r"\d+\s*min", h),
                    "the neighborhood map key carries no times")
        for needle, what in (("am-block", "Amenities and Transportation"),
                             ('id="locmap"', "The Neighborhood map"),
                             ("class=\"comps snap\"", "Market Snapshot")):
            r.check(needle in h, f"buyer portal has no {what} section",
                    hard=False)
        r.check("hero" not in h or bhero is None or bhero in h
                or "data:image" in h,
                "buyer portal header has no photo", hard=False)
    elif b:
        r.soft("buyer portal has not been built yet")
    return r


def main(argv):
    want = argv[1:] or None
    files = sorted((HERE / "properties").glob("*.json"))
    files = [f for f in files if not f.name.startswith("_")]
    if want:
        keys = {w.lower().removesuffix(".json") for w in want}
        files = [f for f in files
                 if f.stem.lower() in keys
                 or json.loads(f.read_text()).get("prefix", "").lower()
                 in keys]
        if not files:
            print("no property matched", ", ".join(want))
            return 2

    bad = 0
    for f in files:
        try:
            r = check_property(f)
        except Exception as e:                       # noqa: BLE001
            print(f"✗ {f.stem}: check itself failed — "
                  f"{type(e).__name__}: {e}")
            bad += 1
            continue
        if r.fail:
            bad += 1
            print(f"✗ {r.name}")
            for m in r.fail:
                print(f"    FAIL  {m}")
            for m in r.warn:
                print(f"    note  {m}")
        elif r.warn:
            print(f"✓ {r.name}")
            for m in r.warn:
                print(f"    note  {m}")
        else:
            print(f"✓ {r.name}")
    print(f"\n{len(files) - bad} of {len(files)} clean.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
