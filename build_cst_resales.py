#!/usr/bin/env python3
"""Build templates/CST_Resales.html from the MLS Bright resale export.

Casey, 18 Oct 2026: "for Pricing strategy back page use this track record on
all summaries."

One record, every summary. The page this writes is the only source the
Pricing Strategy Summary's back page reads, so the figures a seller sees on
any property's sheet are the same figures, pulled from the same export.

    python3 build_cst_resales.py [data/CST_Resales.xlsx]

Rules, all of them deliberate:

The four standing rules from 12 Oct 2026 -- "we will stay with these rules on
all Casey Samson transactions" -- apply here unchanged:

* Closed sales only. An A/C or pending listing is not a sale, however firm
  the contract. The export's three under-contract rows (1717 Macon St, 502
  MacArthur Ave NE, 24138 Bryce Ridge Ct) and its one expired row are held
  out, and the build prints which ones so nothing goes missing quietly.
* Days on market is the best 90% -- sorted ascending, slowest tenth dropped,
  via dom_rule.best_dom, which is the same trim the market side gets. The
  tile says so: "Avg days on market (best 90%, 42 of 47)". A trimmed average
  that does not say it is trimmed is the one thing this figure must not be.
* Over asking is measured against the ORIGINAL list price, strictly greater.
  The export carries its own over-asking column measured off the reduced
  list, which hides a price cut: 1007 Ware St reads +$150,000 that way and
  -$100,000 the honest way. A sale at list exactly does not count as above.
* Days on market is DOM, not CDOM -- days this listing took, not days the
  property has been shopped across listings.

Re-run it whenever a fresh export lands. Nothing here is typed by hand.
"""
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import openpyxl

from dom_rule import best_dom, dom_label

HERE = Path(__file__).resolve().parent
TPL = HERE / "templates"
OUT = TPL / "CST_Resales.html"
SRC = HERE / "data" / "CST_Resales.xlsx"

# Closed only. The 12 Oct 2026 rule names the case: "An A/C or pending
# listing is not a sale -- e.g. 1717 Macon St is excluded until it settles."
SOLD = {"CLS", "CLOSED"}
# Success rate counts listings, not sales, so it needs the other two groups
# as well: a home under contract is a listing that worked, one that was
# withdrawn, expired or cancelled is one that did not.
UNDER_CONTRACT = {"A/C", "PND", "ACT UNDER CONTRACT", "PENDING"}
UNSOLD = {"WTH", "EXP", "CNL", "WITHDRAWN", "EXPIRED", "CANCELLED"}


def money(n):
    return f"${n:,.0f}"


def over_txt(n):
    """+$125,000 or $-15,000 -- the form the back page already parses."""
    return f"+{money(n)}" if n >= 0 else f"$-{abs(n):,.0f}"


def short(n):
    """$1,430,000 -> $1.43M. The band title has one line to say the range."""
    m = n / 1_000_000
    return f"${m:.2f}M".replace("0M", "M") if m < 10 else f"${m:.1f}M"


def read(path):
    """Returns (closed rows, rows left out, Casey's success tally).

    The success tally has to be counted here rather than off the table
    below, because the listings that did NOT sell are exactly the ones the
    table leaves out.
    """
    ws = openpyxl.load_workbook(path, data_only=True)["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    idx = {h: i for i, h in enumerate(rows[0]) if h}
    out, dropped, won, taken = [], [], 0, 0
    for r in rows[1:]:
        if not r[idx["MLS #"]]:
            continue
        g = lambda k: r[idx[k]]                              # noqa: E731
        status = str(g("Status") or "").strip().upper()
        sp, olp = g("Close Price"), g("Original List Price")
        if "casey" in str(g("List Agent Full Name") or "").lower():
            if status in SOLD | UNDER_CONTRACT | UNSOLD:
                taken += 1
                won += status in SOLD | UNDER_CONTRACT
        if status not in SOLD:
            dropped.append((g("Address"), status or "no status",
                            "under contract, not settled"
                            if sp is not None else "not a sale"))
            continue
        if sp is None or olp is None:
            dropped.append((g("Address"), status, "no close or list price"))
            continue
        agent = str(g("List Agent Full Name") or "").strip()
        out.append({
            "mls": g("MLS #"),
            "status": status,
            "agent": agent,
            "casey": "casey" in agent.lower(),
            "address": str(g("Address")).strip(),
            "city": str(g("City")).strip().replace("Mclean", "McLean"),
            "dom": int(g("DOM") or 0),
            "olp": int(olp),
            "sp": int(sp),
            "over": int(sp) - int(olp),
            "close": g("Close Date"),
            "sf": g("Above Grade Finished SQFT"),
        })
    return out, dropped, (won, taken)


def build(rows, success):
    """The band, split two ways.

    Casey, 18 Oct 2026: "Use all for total sales and total volume. Just
    display and use performance stats for Casey Samson listing agent."

    So the first two figures count the whole team's resales and the last four
    count only the homes Casey listed himself. Every performance tile says
    which set it is measuring, because two bases in one band is exactly the
    thing a reader will otherwise get wrong.
    """
    rows = sorted(rows, key=lambda r: -r["sp"])
    n = len(rows)
    vol = sum(r["sp"] for r in rows)

    cs = [r for r in rows if r["casey"]]
    cn = len(cs)
    # Casey, 18 Oct 2026: "Replace Homes sold with Success rate." Of the
    # listings he took, the share that sold or went under contract. It needs
    # the ones that did NOT sell, so it is counted over `taken` -- every row
    # of the export with his name on it, including the expired one -- not
    # over the closed rows this page tabulates.
    won, taken = success
    succ = round(won / taken * 100) if taken else None
    # The trimmed average, from the one definition both sides share.
    dom, kept, total = best_dom(r["dom"] for r in cs)
    week = sum(1 for r in cs if r["dom"] <= 7)
    above = sum(1 for r in cs if r["over"] > 0)
    pos = sum(r["over"] for r in cs if r["over"] > 0)
    pct = sum(r["sp"] for r in cs) / sum(r["olp"] for r in cs) * 100
    lo, hi = min(r["sp"] for r in rows), max(r["sp"] for r in rows)

    dates = [r["close"] for r in rows if r["close"]]
    span = (f'{min(dates):%B %Y} to {max(dates):%B %Y}' if dates else "")

    # Every tile names its set, in the same place, with the same separator.
    # Two bases in one band only works if the reader never has to guess which
    # one a figure is counting.
    # Casey, 18 Oct 2026: "Let's move Volume first, then success rate." The
    # team total leads; the market's name sits under it, so every figure the
    # market answers starts in the second column.
    stats = [
        (money(vol), "In total volume &mdash; team"),
        (f"{succ}%" if succ is not None else "&mdash;",
         f"Success rate ({won} of {taken} listings) &mdash; Casey"),
        (f"{dom:.1f}", f"{dom_label(kept, total)} &mdash; Casey"),
        (f"{pct:.1f}%", "Of original list price &mdash; Casey"),
        (f"{round(week / cn * 100)}%",
         f"Sold in the first week ({week} of {cn}) &mdash; Casey"),
        (f"{round(above / cn * 100)}%",
         f"Sold above list price ({above} of {cn}) &mdash; Casey"),
    ]

    note = (f"<b>{n} homes, {money(vol)} in volume across the team.</b> "
            f"Of the {cn} Casey listed himself, {week} went under contract "
            f"within a week and {above} closed above the asking price "
            f"&mdash; averaging <b>{pct:.1f}% of original list</b>, or "
            f"<b>{money(pos)} above asking</b> across those sales.")

    band = "\n".join(
        f'    <div><span class="n">{v}</span><span class="l">{l}</span></div>'
        for v, l in stats)
    # The seventh cell, Listed by, is for this page only: it is what makes
    # "47 sold" and "23 of 34 above list" legible as one table. The Pricing
    # Summary's back page reads the first six cells of each row and ignores
    # anything after them, so the printed sheet keeps its six columns.
    body = "".join(
        f'<tr><td class="addr">{r["address"]}</td><td>{r["city"]}</td>'
        f'<td class="n">{r["dom"]}</td><td class="n">{money(r["olp"])}</td>'
        f'<td class="n sp">{money(r["sp"])}</td>'
        f'<td class="n over">{over_txt(r["over"])}</td>'
        f'<td class="agent">{"Casey Samson" if r["casey"] else r["agent"]}'
        "</td></tr>" for r in rows)

    subtitle = (f"{short(lo)} to {short(hi)} &mdash; {n} resales"
                + (f", {span}" if span else ""))
    foot = (f"Closed sales only. Totals cover all {n} team resales; the "
            f"performance figures are the {cn} homes Casey listed himself. "
            "Over asking is measured against the original list price, so a "
            "home that was reduced before it sold shows the reduction. "
            "Click any column heading to sort.")
    return stats, note, band, body, subtitle, foot, n


PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Casey Samson Team &mdash; Resale Track Record</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="The Casey Samson Team's resale track record \
in Northern Virginia -- days on market, original list price and final sale \
price. Sourced from MLS Bright.">
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;900&family=Lora:wght@400;600&display=swap');
:root{--bg:#F7F3E9;--card:#FFF;--ink:#2B2620;--muted:#7A7264;--gold-deep:#8A6A2E;--gold-line:#D9C79A;--rule:#E4DCC8;--banner:#F3EAD3;--black:#000;--gold-bright:#D3B060;}
*{box-sizing:border-box;} body{margin:0;background:var(--bg);color:var(--ink);font-family:'Lora',Georgia,serif;}
.wrap{max-width:1080px;margin:0 auto;padding:0 26px;}
header{background:var(--black);border-bottom:3px solid var(--gold-bright);padding:44px 0 32px;text-align:center;}
.kicker{font-family:'Playfair Display',Georgia,serif;font-size:13px;font-weight:700;letter-spacing:.12em;color:var(--gold-bright);text-transform:uppercase;margin:0 0 8px;}
h1{font-family:'Playfair Display',Georgia,serif;font-size:40px;font-weight:900;margin:0 0 8px;color:#fff;}
.subtitle{font-size:15px;color:#CFC6B4;font-style:italic;margin:0;}
.source-line{font-size:11px;color:var(--gold-bright);text-transform:uppercase;letter-spacing:.06em;margin:10px 0 0;}
.hero{background:var(--card);border:2px solid var(--gold-deep);border-radius:12px;margin:28px 0 14px;padding:24px;display:grid;grid-template-columns:repeat(3,1fr);text-align:center;gap:20px 14px;}@media (max-width:640px){.hero{grid-template-columns:repeat(2,1fr);}}
.hero .n{font-family:'Playfair Display',Georgia,serif;font-size:32px;font-weight:900;color:var(--gold-deep);display:block;line-height:1.1;}
.hero .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-top:5px;}
.note{background:var(--banner);border:1px solid var(--gold-line);border-radius:8px;padding:14px 22px;margin:0 0 20px;font-size:13px;color:var(--muted);line-height:1.8;text-align:center;}
.note b{color:var(--ink);}
.tier{font-family:'Playfair Display',Georgia,serif;font-size:24px;font-weight:700;margin:34px 0 10px;padding-bottom:8px;border-bottom:2px solid var(--gold-line);text-align:center;}
.tier span{font-size:14px;font-weight:400;color:var(--muted);font-style:italic;}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin-bottom:10px;}
thead th{background:var(--banner);border-bottom:2px solid var(--gold-line);border-top:1px solid var(--gold-line);padding:9px 7px;text-align:center;font-size:9.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:700;cursor:pointer;}
tbody td{padding:8px 7px;border-bottom:1px solid var(--rule);}
tbody tr:nth-child(even){background:#FCFAF4;}
td.n{text-align:center;font-variant-numeric:tabular-nums;}
td.addr{font-weight:700;} td.sp{font-weight:700;}
td.agent{font-size:11px;color:var(--muted);white-space:nowrap;}
.back{display:block;padding:13px 26px;font-size:13px;color:var(--muted);text-decoration:none;background:var(--card);border-bottom:1px solid var(--rule);}
.back:hover{color:var(--gold-deep);}
footer{background:var(--black);border-top:3px solid var(--gold-bright);padding:22px 0;text-align:center;font-size:12px;color:#9A9284;margin-top:34px;}
</style></head><body>
<a class="back" id="backLink" href="index.html" style="display:none;">&larr; Back to Seller Portal</a>
<script>
  (function(){var r=document.referrer;
    if(r&&(r.indexOf('index.html')!==-1||r.indexOf('Roadmap.html')!==-1||/\\/$/.test(r)))
      document.getElementById('backLink').style.display='';})();
</script>
<header>
  <div class="kicker">The Casey Samson Team</div>
  <h1>Resale Track Record</h1>
  <p class="subtitle">@@SUBTITLE@@</p>
  <p class="source-line">Source: MLS Bright</p>
</header>
<div class="wrap">
  <div class="hero">
@@BAND@@
  </div>
  <div class="note">@@NOTE@@</div>

  <div class="tier">The Homes <span>(@@N@@ sales, highest price first)</span></div>
  <table><thead><tr><th>Address</th><th>City</th><th>DOM</th><th>Original List</th><th>Sale Price</th><th>Over Asking</th><th>Listed by</th></tr></thead>
  <tbody>@@BODY@@</tbody></table>
  <p class="note" style="margin-top:4px;">@@FOOT@@</p>
</div>
<footer>The Casey Samson Team &middot; Casey Samson &middot; 703-508-2535 &middot; Casey@caseysamson.com<br>&copy; @@YEAR@@ The Casey Samson Team LLC. All Rights Reserved.</footer>
<script>
document.querySelectorAll('table').forEach(t=>t.querySelectorAll('thead th').forEach((h0,i)=>h0.addEventListener('click',()=>{
  const tb=t.querySelector('tbody'),rows=[...tb.rows],asc=!h0.classList.contains('a');
  t.querySelectorAll('th').forEach(h=>h.classList.remove('a'));if(asc)h0.classList.add('a');
  const v=r=>{const x=r.children[i].innerText.trim();const nn=parseFloat(x.replace(/[^0-9.\\-]/g,''));return isNaN(nn)?x:nn;};
  rows.sort((a,b)=>{const x=v(a),y=v(b);return (typeof x==='number'?x-y:String(x).localeCompare(y))*(asc?1:-1);});
  rows.forEach(r=>tb.appendChild(r));
})));
</script>
</body></html>
"""


def main(argv):
    src = Path(argv[1]) if len(argv) > 1 else SRC
    rows, dropped, success = read(src)
    stats, note, band, body, subtitle, foot, n = build(rows, success)
    page = PAGE
    for token, value in (("@@SUBTITLE@@", subtitle), ("@@BAND@@", band),
                         ("@@NOTE@@", note), ("@@BODY@@", body),
                         ("@@FOOT@@", foot), ("@@N@@", str(n)),
                         ("@@YEAR@@", str(datetime.now().year))):
        page = page.replace(token, value)
    OUT.write_text(page, encoding="utf-8")
    print(f"{OUT.relative_to(HERE)}  ({n} closed sales)")
    for v, l in stats:
        print(f"    {v:>14}  {l}")
    if dropped:
        print("\n  Left out of the record:")
        for a, s, why in dropped:
            print(f"    {a} ({s}) -- {why}")
    cut = [r for r in rows if r["over"] < 0]
    if cut:
        print(f"\n  {len(cut)} closed under the ORIGINAL list price:")
        for r in cut:
            print(f"    {r['address']:28} {money(r['olp'])} -> "
                  f"{money(r['sp'])}  ({money(r['over'])})")
    top = Counter(r["city"] for r in rows).most_common(5)
    print("\n  Towns:", ", ".join(f"{c} {k}" for c, k in top))


if __name__ == "__main__":
    main(sys.argv)
