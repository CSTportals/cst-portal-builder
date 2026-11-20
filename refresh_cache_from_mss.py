"""Refresh market_cache.json from saved MSS pages (mss_pages/). Rebuilt
19 Nov 2026: the live MSS site is not reachable from the build machine, so
each weekly MSS package's pages are copied into mss_pages/ and read here."""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).parent

def txt(s):
    s = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    import html
    return re.sub(r'\s+', ' ', html.unescape(s))

def grab(t, pat):
    m = re.search(pat, t)
    return m.group(1) if m else None

def parse(path):
    t = txt(path.read_text(encoding="utf-8", errors="ignore"))
    head = grab(t, r'Current Market Conditions (\w+ Control the [^.]*? Market|[^.]*? Market is Neutral)')
    cap = grab(t, r"((?:BUYER|SELLER)[’']S MARKET[^0-9]*?FLAG|NEUTRAL MARKET[^0-9]*?FLAG|BALANCED MARKET)")
    read = grab(t, r'FLAG (\d+% of the homes listed in the last 30 days went under contract[^.]*\.)')
    st = {
        "under_contract": grab(t, r'Total Homes Under Contract (\d+%)'),
        "uc_30": grab(t, r'Under Contract \(Last 30 Days\) (\d+%)'),
        "avg_dom": grab(t, r'Days on Market, Active & Under Contract (\d+)'),
        "success_rate": grab(t, r'Sold or Withdrawn in the Last 90 Days.*?Success Rate (\d+%)'),
        "uc_14": grab(t, r'and (\d+%) of the listin\w* here went under contract in the last 14 days'),
    }
    ctl = None
    if head:
        ctl = "Buyer's" if head.startswith("Buyers") else "Seller's" if head.startswith("Sellers") else "Neutral"
    st["control"] = ctl
    asof = grab(t, r'AS OF ([A-Z]+ \d+, \d{4})')
    return {k: v for k, v in st.items() if v}, head, cap, read, asof

def main():
    cache_f = HERE / "market_cache.json"
    cache = json.loads(cache_f.read_text())
    n = 0
    for f in sorted((HERE / "mss_pages").glob("*_Market_Snapshot.html")):
        slug = f.stem
        st, head, cap, read, asof = parse(f)
        if not st.get("under_contract"):
            continue
        e = cache.setdefault(slug, {})
        old = e.get("stats") or {}
        old.update(st)
        e["stats"] = old
        if head:
            e["headline"] = head
            c = e.setdefault("conditions", {})
            c["headline"] = head
            if cap: c["capsule"] = cap
            if read: c["read"] = read
            if asof: c["meta"] = re.sub(r"AS OF .*", f"AS OF {asof}", c.get("meta", "")) or f"AS OF {asof}"
            c["stats"] = [[st.get("success_rate", ""), "Success rate"],
                          [st.get("under_contract", ""), "Under contract"],
                          [st.get("avg_dom", ""), "Days on market, active and pending"],
                          [st.get("uc_30", ""), "Under contract on homes listed 30 days"]] + (
                          [[st["uc_14"], "Of all listings, under contract in 14 days"]] if st.get("uc_14") else [])
            if c.get("capsule"):
                c["flags"] = 2 if "DOUBLE" in c["capsule"] else 1
        e["refreshed_from"] = f"mss_pages ({asof or 'Nov 11, 2026'})"
        n += 1
    cache_f.write_text(json.dumps(cache, indent=1))
    print(f"refreshed {n} markets")

if __name__ == "__main__":
    main()
