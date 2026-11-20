#!/usr/bin/env python3
"""Build a track-record page from an MLS export of closed sales.

Casey, 12 Oct 2026: "use this as Casey Samson Track record under 3500 and
compare to Market under 3500", then "let do the over 3500 for lieuvin and
vintage crest."

Writes templates/Track_Record_{Under,Over}_3500.html in the same shape as the two
existing portfolio pages, so portfolio_stats() and track_record_back() read
it without changes: a .hero of six figures, a .note sentence, and a
six-column table of the sales.

    python3 make_track_record.py under
    python3 make_track_record.py over
"""
import csv
import re
from pathlib import Path

from dom_rule import best_dom, dom_label

import sys

UP = Path("/root/.claude/uploads/557e4176-277c-5186-9084-0a79189e9847")
TPL = Path("templates")
MODEL = TPL / "Portfolio_Under_1_5M.html"
LIMIT = 3500

# Two sets, same shape. "over" is the record for a Lieuvin or a Vintage
# Crest; "under" is the one John Marshall runs on.
SIDE = (sys.argv[1] if len(sys.argv) > 1 else "under").lower()
if SIDE not in ("under", "over"):
    raise SystemExit('usage: make_track_record.py [under|over]')
SRC = UP / ("1f327fce-Casey_under_3500.csv" if SIDE == "under"
            else "c7d8c56e-casey_over_3500.csv")
OUT = TPL / f"Track_Record_{SIDE.capitalize()}_3500.html"
WORD = "under" if SIDE == "under" else "over"

money = lambda x: float(re.sub(r"[^0-9.]", "", x or "") or 0) or None
digits = lambda x: int(re.sub(r"[^0-9]", "", x or "") or 0)
cash = lambda v: "$" + format(int(round(v)), ",")

rows = []
for c in csv.reader(SRC.open(encoding="utf-8", errors="replace")):
    if len(c) < 17 or c[2].strip() != "CLS":
        continue
    close, olp, sf = money(c[9]), money(c[14]), digits(c[16])
    if not (close and olp):
        continue
    if (sf >= LIMIT) if SIDE == "under" else (sf < LIMIT):
        continue
    rows.append({"address": c[4].strip(), "city": c[5].strip(),
                 "dom": digits(c[3]), "close": close, "olp": olp, "sf": sf})
rows.sort(key=lambda r: -r["close"])

n = len(rows)
vol = sum(r["close"] for r in rows)
olp_sum = sum(r["olp"] for r in rows)
dom, dom_k, dom_n = best_dom(r["dom"] for r in rows)
week = sum(1 for r in rows if r["dom"] <= 7)
above = sum(1 for r in rows if r["close"] > r["olp"])
pos = sum(r["close"] - r["olp"] for r in rows if r["close"] > r["olp"])
lo = min(r["close"] for r in rows)
hi = max(r["close"] for r in rows)

stats = [
    (f"{n}", f"Homes sold {WORD} 3,500 SF"),
    (cash(vol), "In total volume"),
    (f"{dom:.1f}", dom_label(dom_k, dom_n)),
    (f"{vol / olp_sum * 100:.1f}%", "Of original list price"),
    (f"{round(week / n * 100)}%", f"Sold in the first week ({week} of {n})"),
    (f"{round(above / n * 100)}%", f"Sold above list price ({above} of {n})"),
]

model = MODEL.read_text(encoding="utf-8")
s = model

s = re.sub(r"<title>.*?</title>",
           f"<title>Casey Samson Team &mdash; Track Record "
           f"{WORD.capitalize()} 3,500 SF</title>",
           s, count=1, flags=re.S)
s = re.sub(r"<h1>.*?</h1>", f"<h1>Track Record {WORD.capitalize()} 3,500 SF</h1>", s,
           count=1, flags=re.S)
s = re.sub(r'<p class="subtitle">.*?</p>',
           f'<p class="subtitle">Homes sold from {cash(lo)} to {cash(hi)} '
           f"&mdash; every Casey Samson Team sale {WORD} 3,500 finished "
           "square feet</p>", s, count=1, flags=re.S)

band = "\n".join(
    f'    <div><span class="n">{v}</span><span class="l">{l}</span></div>'
    for v, l in stats)
s = re.sub(r'(<div class="hero">\n).*?(\n  </div>)',
           lambda m: m.group(1) + band + m.group(2), s, count=1, flags=re.S)

note = (f"<b>{n} homes, {cash(vol)} in volume.</b> {week} of {n} went under "
        f"contract within a week and {above} of {n} closed above the asking "
        f"price &mdash; averaging <b>{vol / olp_sum * 100:.1f}% of original "
        f"list</b>, or <b>{cash(pos)} above asking</b> across those sales.")
s = re.sub(r'(<div class="note[^"]*">).*?(</div>)',
           lambda m: m.group(1) + note + m.group(2), s, count=1, flags=re.S)

s = re.sub(r"<h2[^>]*>The Homes.*?</h2>",
           f'<h2 class="sect">The Homes <span class="hint">({n} sales, '
           "highest price first)</span></h2>", s, count=1, flags=re.S)

body = "".join(
    f'<tr><td class="addr">{r["address"]}</td><td>{r["city"]}</td>'
    f'<td class="n">{r["dom"]}</td><td class="n">{cash(r["olp"])}</td>'
    f'<td class="n sp">{cash(r["close"])}</td>'
    f'<td class="n over">'
    + ("+" if r["close"] >= r["olp"] else "$-")
    + (cash(r["close"] - r["olp"]) if r["close"] >= r["olp"]
       else format(int(olp_ := r["olp"] - r["close"]), ","))
    + "</td></tr>" for r in rows)
s = re.sub(r"<tbody>.*?</tbody>", f"<tbody>{body}</tbody>", s, count=1,
           flags=re.S)

OUT.write_text(s, encoding="utf-8")
print(f"wrote {OUT}  ({n} sales)")
for v, l in stats:
    print(f"   {v:>14}  {l}")
print(f"   cities: {', '.join(sorted({r['city'] for r in rows}))}")
