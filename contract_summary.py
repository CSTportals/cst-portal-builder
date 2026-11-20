#!/usr/bin/env python3
"""Contract Summary -- the Contract Analyzer, as a page in the seller portal.

Casey, 28 Oct 2026, on 2583 Vintage Crest: "I need it as HTML and content
it to Seller portal for under road map." The page is
<prefix>_Contract_Summary.html in the seller folder, linked from the Seller
Roadmap card on the portal page. Everything on it comes from the property
file's "contract_summary" block -- the offer terms as written in the
contract, the net sheet inputs, the deadlines, and the Market Detail rows.
The Market Snapshot is the Roadmap's own Current Market Conditions panel,
captured from the built Roadmap so the two always match.

    "contract_summary": {
      "as_of": "Wednesday, October 28, 2026",
      "lead": "...",
      "offer": [["Sales price", "$2,499,000, full list price"], ...],
      "net": {"price": 2499000, "buyer_pct": 2.5, "listing_pct": 2.5, "grantor_pct": 0.3,
              "settlement": 855, "deed": 175, "admin": 345, "other": 0,
              "rentback": {"days": 62, "per_day": 540}, "note": "..."},
      "deadlines": ["**Day 5:** ...", ...], "deadlines_lead": "...",
      "snapshot_note": "...",
      "local": {"lead": "...", "rows": [{status, address, dom, built, sf, lot,
                 assessment, list, value}], "subject": {...}, "note": "..."},
      "trend": {"headline": "...", "lead": "...", "rows": [[...]], "note": "..."}
    }
"""
import html as _h
import re
from pathlib import Path


def _m(v, sign=False):
    if v in (None, ""):
        return "&mdash;"
    s = f"${abs(v):,.0f}"
    if sign:
        return ("+" if v > 0 else "&minus;" if v < 0 else "") + s
    return ("&minus;" if v < 0 else "") + s


def _md(t):
    """**bold** -> <b>, the only inline markup the block uses."""
    t = _h.escape(t, quote=False).replace("&amp;mdash;", "&mdash;").replace("&amp;minus;", "&minus;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def _table(head, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    body = ""
    for r in rows:
        kind = ""
        if isinstance(r, dict):
            kind, r = r.get("cls", ""), r["cells"]
        body += f'<tr class="{kind}">' + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return (f'<div class="tw"><table class="t {cls}"><thead><tr>{th}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def snapshot_image(out, pre, note=print):
    """Capture the Roadmap's Current Market Conditions panel."""
    road = out / f"{pre}_Roadmap.html"
    img = out / f"{pre}_Market_Snapshot.png"
    if not road.exists():
        note("Contract Summary: no Roadmap built, so no Market Snapshot image.")
        return None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            pg = b.new_page(viewport={"width": 1000, "height": 1200}, device_scale_factor=2)
            pg.goto(road.resolve().as_uri())
            pg.wait_for_timeout(1200)
            el = pg.query_selector(".mc")
            if not el:
                b.close()
                note("Contract Summary: the Roadmap has no market panel.")
                return None
            el.screenshot(path=str(img))
            b.close()
        return img.name
    except Exception as e:                                  # noqa: BLE001
        note(f"Contract Summary: market panel not captured ({type(e).__name__}).")
        return None


def build(p, out, note=print):
    cs = p.get("contract_summary")
    if not cs:
        return
    pre, addr = p["prefix"], p["address"]
    sec = []
    # ---- The Offer
    sec.append('<section><h2>The Offer</h2>'
               + _table(["Term", "Contract"], [[f"<b>{_md(k)}</b>", _md(v)] for k, v in cs["offer"]], "kv")
               + "</section>")
    # ---- Seller Net (Casey's net sheet)
    n = cs["net"]
    price = n["price"]
    comm = price * (n["buyer_pct"] + n["listing_pct"]) / 100
    grant = price * n["grantor_pct"] / 100
    fees = n["settlement"] + n["deed"] + n["admin"] + n.get("other", 0)
    net = price - comm - grant - fees
    rows = [["Sales price", _m(price)],
            ["Buyer commission", f'{n["buyer_pct"]:g}%'],
            [f'Total commission ({n["buyer_pct"]:g}% buyer + {n["listing_pct"]:g}% listing)', _m(-comm)],
            ["Grantor&rsquo;s tax", _m(-grant)],
            ["Settlement fee", _m(-n["settlement"])],
            ["Deed preparation", _m(-n["deed"])],
            ["Admin fee", _m(-n["admin"])],
            ["Other concessions", _m(-n.get("other", 0)) if n.get("other") else "$0"],
            {"cls": "tot", "cells": ["Seller net sheet", _m(net)]}]
    lead = f"At {_m(price)} the sellers net {_m(net)}"
    rb = n.get("rentback")
    if rb:
        charge = rb["days"] * rb["per_day"]
        rows += [[f'Rent-back occupancy charge, {rb["days"]} days at {_m(rb["per_day"])}', _m(-charge)],
                 {"cls": "tot", "cells": ["Net after rent-back", _m(net - charge)]}]
        lead += f", or {_m(net - charge)} after the rent-back charge"
    lead += ", less their mortgage payoff."
    sec.append(f'<section><h2>Seller Net</h2><p class="lede">{lead}</p>'
               + _table(["Seller net sheet", "Amount"], rows, "kv net")
               + (f'<p class="note">{_md(n["note"])}</p>' if n.get("note") else "") + "</section>")
    # ---- Deadlines
    items = "".join(f"<li>{_md(d)}</li>" for d in cs.get("deadlines", []))
    sec.append(f'<section><h2>Contingency Deadlines</h2>'
               f'<p class="lede">{_md(cs.get("deadlines_lead", ""))}</p><ol class="dl">{items}</ol></section>')
    # ---- Market Snapshot
    img = snapshot_image(out, pre, note)
    if img:
        sec.append(f'<section><h2>Market Snapshot</h2>'
                   f'<img class="mc-img" src="{img}" alt="Current Market Conditions">'
                   f'<p class="note">{_md(cs.get("snapshot_note", ""))}</p></section>')
    # ---- Local Market
    lo = cs.get("local")
    if lo:
        head = ["Status", "Address", "DOM", "Year built", "Size (SF)", "Lot (SF)", "Assessment",
                "List price", "APPSF", "Value", "Above or below value"]

        def cells(r, label=None):
            v = r.get("value")
            return [label or _h.escape(r.get("status", "")), _h.escape(r["address"]),
                    f'{r["dom"]:,.0f}', f'{r["built"]:.0f}', f'{r["sf"]:,.0f}',
                    f'{r["lot"]:,.0f}' if r.get("lot") else "&mdash;", _m(r.get("assessment")),
                    _m(r.get("list")), _m(v / r["sf"]) if v and r.get("sf") else "&mdash;",
                    _m(v), _m(r["list"] - v, sign=True) if v and r.get("list") else "&mdash;"]
        rws = [cells(r) for r in lo["rows"]]
        k = len(lo["rows"])
        avg = lambda key: sum(r[key] for r in lo["rows"] if r.get(key)) / max(1, len([r for r in lo["rows"] if r.get(key)]))
        a = {key: avg(key) for key in ("dom", "built", "sf", "lot", "assessment", "list", "value")}
        a_cells = cells({**a, "address": ""}, f"Average, {k} homes")
        a_cells[8] = _m(sum(r["value"] / r["sf"] for r in lo["rows"]) / k)
        a_cells[10] = _m(sum(r["list"] - r["value"] for r in lo["rows"]) / k, sign=True)
        rws.append({"cls": "tot", "cells": a_cells})
        rws.append({"cls": "subj", "cells": cells(lo["subject"], "Subject")})
        trend = cs.get("trend")
        tr = ""
        if trend:
            tr = (f'<p class="lede trend">{_md(trend["headline"])} {_md(trend.get("lead", ""))}</p>'
                  + _table(trend["head"], [r if isinstance(r, dict) else [_md(str(c)) for c in r]
                                           for r in trend["rows"]], "trend-t")
                  + (f'<p class="note">{_md(trend["note"])}</p>' if trend.get("note") else ""))
        sec.append(f'<section><h2>Local Market</h2><p class="lede">{_md(lo.get("lead", ""))}</p>'
                   + _table(head, rws, "wide")
                   + (f'<p class="note">{_md(lo["note"])}</p>' if lo.get("note") else "") + tr + "</section>")
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_h.escape(addr)} &mdash; Contract Summary</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap');
:root{{--bg:#FAF7F0;--card:#FFFFFF;--banner:#F1EBDA;--ink:#221C14;--muted:#71695A;--gold:#A5813B;
  --gold-deep:#8A6A2E;--gold-line:#D3B978;--rule:#E4DCC8;--navy:#1B2233;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Lora',Georgia,serif;font-size:15.5px;line-height:1.55;}}
.top{{background:var(--navy);color:#F1EBDA;text-align:center;padding:30px 16px 26px;}}
.top .eb{{font-size:11.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--gold-line);font-weight:700;}}
.top h1{{font-family:'Playfair Display',Georgia,serif;font-size:34px;margin:8px 0 4px;color:#fff;}}
.top .sub{{font-style:italic;color:#CFC7B6;}}
.top a{{color:var(--gold-line);font-size:13px;}}
.wrap{{max-width:1080px;margin:0 auto;padding:10px max(16px,env(safe-area-inset-right,0px)) 50px max(16px,env(safe-area-inset-left,0px));}}
.intro{{max-width:760px;margin:30px auto 0;text-align:center;font-size:16.5px;}}
section{{margin-top:44px;}}
h2{{font-family:'Playfair Display',Georgia,serif;font-size:26px;text-align:center;margin:0 0 10px;}}
.lede{{max-width:820px;margin:0 auto 18px;text-align:center;color:var(--muted);}}
.lede.trend{{margin-top:34px;color:var(--ink);}}
.tw{{overflow-x:auto;border:1px solid var(--rule);border-radius:10px;background:var(--card);}}
.t{{width:100%;border-collapse:collapse;font-size:14px;}}
.t.wide{{min-width:980px;}} .t.trend-t{{min-width:640px;}}
.t th{{background:var(--banner);font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  font-weight:600;padding:14px 12px;border-bottom:1px solid var(--gold-line);text-align:center;}}
.t td{{padding:11px 12px;text-align:center;border-bottom:1px solid var(--rule);}}
.t:not(.kv) td{{white-space:nowrap;}}
.t th:first-child,.t td:first-child{{text-align:left;padding-left:18px;}}
.t.kv td:last-child{{text-align:left;}} .t.net td:last-child{{text-align:right;padding-right:22px;white-space:nowrap;}}
.t.net th:last-child{{text-align:right;padding-right:22px;}}
.t.kv td:first-child{{width:30%;}}
.t tbody tr:nth-child(even) td{{background:#FBF8F1;}}
.t tr.tot td{{background:var(--banner)!important;font-weight:700;border-top:2px solid var(--gold-line);}}
.t tr.subj td{{background:#fff!important;font-weight:700;color:var(--gold-deep);}}
.dl{{max-width:820px;margin:0 auto;padding-left:22px;}} .dl li{{margin:0 0 9px;}}
.mc-img{{display:block;width:100%;max-width:820px;margin:8px auto 0;border-radius:10px;}}
.note{{font-size:12.5px;color:var(--muted);max-width:900px;margin:12px auto 0;text-align:center;}}
footer{{text-align:center;font-size:12px;color:var(--muted);padding:26px 16px 40px;border-top:1px solid var(--rule);}}
@media (max-width:600px){{.top h1{{font-size:26px;}} h2{{font-size:22px;}}}}
</style></head><body>
<div class="top"><div class="eb">The Casey Samson Team &middot; Contract Summary</div>
<h1>{_h.escape(addr)}</h1><div class="sub">{_h.escape(p["city"])}, {_h.escape(p["state"])} &middot; {_h.escape(cs.get("as_of", ""))}</div>
<div style="margin-top:10px"><a href="index.html">&larr; Back to the Seller Portal</a></div></div>
<div class="wrap"><p class="intro">{_md(cs.get("lead", ""))}</p>
{"".join(sec)}
</div>
<footer>&copy; 2026 The Casey Samson Team LLC. All Rights Reserved. Estimates for discussion; final figures come from the settlement statement.</footer>
</body></html>
"""
    (out / f"{pre}_Contract_Summary.html").write_text(page, encoding="utf-8")
    note(f"Contract Summary: {pre}_Contract_Summary.html written and linked under the Seller Roadmap.")


def link_on_index(p, out):
    """A Contract Summary button inside the Seller Roadmap card."""
    if not p.get("contract_summary"):
        return
    f = out / "index.html"
    if not f.exists():
        return
    h = f.read_text(encoding="utf-8")
    h = re.sub(r'<a class="feat-pdf cs-link".*?</a>', "", h, flags=re.S)
    pre = p["prefix"]
    btn = (f'<a class="feat-pdf cs-link" href="{pre}_Contract_Summary.html"><svg width="13" height="13" '
           'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16'
           'a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></svg>Contract Summary'
           '<span class="pdf-tag">New</span></a>')
    key = f'href="{pre}_Pricing_Strategy_Summary.pdf"'
    i = h.find(key)
    if i < 0:
        return
    j = h.find("</a>", i) + 4
    f.write_text(h[:j] + btn + h[j:], encoding="utf-8")
