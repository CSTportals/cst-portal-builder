#!/usr/bin/env python3
"""Make the standalone Portfolio pages say what the Pricing Strategy back page says.

Casey, 12 Oct 2026: "lets go to Portfolio under $1.5 or over $1.5. Use the
same track record you use with Pricing Strategy Summary."

The back page of the Pricing Strategy Summary carries six figures, drops
median DOM / average sale price / per-square-foot, and counts homes that sold
STRICTLY above list. The standalone pages still carried eleven figures and
the looser "at or above asking price", which counts the homes that sold at
list exactly — 6 of 41 under $1.5M, 9 of 36 over. Both pages are now
computed from the same rows by the same rules, so they cannot disagree.

    python3 sync_portfolio.py
"""
import re
from pathlib import Path

TPL = Path("templates")
FILES = {
    "Portfolio_Under_1_5M.html": "Under $1.5M",
    "Luxury_Experience.html": "Over $1.5M",
}


def num(x):
    d = re.sub(r"[^0-9-]", "", x or "")
    return int(d) if d else 0


def rows_of(html):
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    out = []
    for r in re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S):
        c = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(c) < 8:
            continue
        txt = [re.sub(r"<[^>]+>", "", x).strip() for x in c]
        out.append({"status": txt[0], "address": txt[1], "city": txt[2],
                    "dom": num(txt[3]), "sf": txt[4], "olp": num(txt[5]),
                    "sp": num(txt[6]), "over": num(txt[7]),
                    "over_txt": txt[7], "olp_txt": txt[5], "sp_txt": txt[6]})
    return out


def stats(rows, label):
    n = len(rows)
    vol = sum(r["sp"] for r in rows)
    olp = sum(r["olp"] for r in rows)
    dom = sum(r["dom"] for r in rows) / n
    week = sum(1 for r in rows if r["dom"] <= 7)
    above = sum(1 for r in rows if r["over"] > 0)
    return [
        (f"{n}", f"Homes sold {label.lower().replace('$1.5m', '$1.5M')}"),
        (f"${vol:,}", "In total volume"),
        (f"{dom:.1f}", "Avg days on market"),
        (f"{vol / olp * 100:.1f}%", "Of original list price"),
        (f"{round(week / n * 100)}%", f"Sold in the first week ({week} of {n})"),
        (f"{round(above / n * 100)}%", f"Sold above list price ({above} of {n})"),
    ]


for fn, label in FILES.items():
    f = TPL / fn
    s = f.read_text(encoding="utf-8")
    rows = rows_of(s)
    st = stats(rows, label)
    n = len(rows)
    week = sum(1 for r in rows if r["dom"] <= 7)
    above = sum(1 for r in rows if r["over"] > 0)
    pos = sum(r["over"] for r in rows if r["over"] > 0)
    vol = sum(r["sp"] for r in rows)
    pct = vol / sum(r["olp"] for r in rows) * 100

    # ---- the stat band: six figures, in the back page's order ----------
    band = "\n".join(
        f'    <div><span class="n">{v}</span><span class="l">{l}</span></div>'
        for v, l in st)
    s = re.sub(r'(<div class="hero">\n).*?(\n  </div>)',
               lambda m: m.group(1) + band + m.group(2), s, count=1, flags=re.S)

    # ---- the sentence under it, counting strictly above ----------------
    new_note = (f"<b>{n} homes, ${vol:,} in volume.</b> {week} of {n} went "
                f"under contract within a week and {above} of {n} closed "
                f"above the asking price &mdash; averaging <b>{pct:.1f}% of "
                f"original list</b>, or <b>${pos:,} above asking</b> across "
                "those sales.")
    s = re.sub(r'(<div class="note[^"]*">).*?(</div>)',
               lambda m: m.group(1) + new_note + m.group(2), s, count=1,
               flags=re.S)

    # ---- the table: the back page's six columns ------------------------
    head = ("<thead><tr><th>Address</th><th>City</th><th>DOM</th>"
            "<th>Original List</th><th>Sale Price</th><th>Over Asking</th>"
            "</tr></thead>")
    s = re.sub(r"<thead>.*?</thead>", head, s, count=1, flags=re.S)
    body = "".join(
        f'<tr><td class="addr">{r["address"]}</td><td>{r["city"]}</td>'
        f'<td class="n">{r["dom"]}</td><td class="n">{r["olp_txt"]}</td>'
        f'<td class="n sp">{r["sp_txt"]}</td>'
        f'<td class="n over">{r["over_txt"]}</td></tr>' for r in rows)
    s = re.sub(r"<tbody>.*?</tbody>", f"<tbody>{body}</tbody>", s, count=1,
               flags=re.S)

    f.write_text(s, encoding="utf-8")
    print(f"{fn}")
    for v, l in st:
        print(f"    {v:>14}  {l}")
