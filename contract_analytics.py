#!/usr/bin/env python3
"""Contract Analytics -- the subject against the current market, on the
seller portal.

Casey, 27 Oct 2026, on 2583 Vintage Crest: "add the 'contract analytics'
just like this [the Authenticated Values comps table] to seller portal."
One table: the subject on top, then the market by group (closed, active /
coming soon, withdrawn / expired), each group closed by its average row.

Property file:

    "contract_analytics": {
      "as_of": "Tuesday, October 27, 2026",
      "subject": {"dom": 5, "list": 2499000},          -- built/sf/lot/assessment default to "subject"
      "groups": [
        {"name": "Closed", "rows": [
           {"status": "CLS", "address": "10507 Oakton", "dom": 5, "built": 2005,
            "sf": 6550, "lot": 90274, "assessment": 2295760, "list": 2600000, "sale": 2600000}, ...]},
        ...],
      "notes": ["Left out: ..."]
    }

Price is the sale price for a closed home and the list price otherwise;
$/SF uses that price. Blank figures (watermark) drop out of the averages.
"""
import html as _h


def _m(v):
    return "&mdash;" if v in (None, "") else f"${v:,.0f}"


def _n(v, suffix=""):
    return "&mdash;" if v in (None, "") else f"{v:,.0f}{suffix}"


def _avg(vals):
    vals = [v for v in vals if v not in (None, "")]
    return sum(vals) / len(vals) if vals else None


def _price(r):
    return r.get("sale") or r.get("list")


def _row(cells, cls=""):
    return (f'<tr{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>'
            + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")


def _cells(label, status, r):
    pr = _price(r)
    psf = pr / r["sf"] if pr and r.get("sf") else None
    return [label, status, _n(r.get("dom")), _n(r.get("built"), "").replace(",", ""),
            _n(r.get("sf")), _n(r.get("lot"), " SF"), _m(r.get("assessment")),
            _m(pr), _m(psf)]


def section(p):
    ca = p.get("contract_analytics")
    if not ca:
        return ""
    subj = dict(p.get("subject") or {})
    subj.update(ca.get("subject") or {})
    head = ["Property", "Status", "DOM", "Built", "Above grade SF", "Lot",
            "Assessment", "Price", "$/SF"]
    body = [_row(_cells(_h.escape(p["address"]), "Subject", subj), "subj")]
    for g in ca.get("groups", []):
        rows = g.get("rows", [])
        body.append(f'<tr class="grp"><td colspan="9">{_h.escape(g["name"])}</td></tr>')
        for r in rows:
            body.append(_row(_cells(_h.escape(r["address"]), _h.escape(r.get("status", "")), r)))
        a = {k: _avg([r.get(k) for r in rows]) for k in ("dom", "built", "sf", "lot", "assessment")}
        a["list"] = _avg([_price(r) for r in rows])
        psfs = [(_price(r) / r["sf"]) for r in rows if _price(r) and r.get("sf")]
        cells = _cells(f'{_h.escape(g["name"])} Average &mdash; {len(rows)}', "", a)
        cells[8] = _m(_avg(psfs))
        body.append(_row(cells, "avg"))
    notes = "".join(f"<li>{n}</li>" for n in ca.get("notes", []))
    as_of = ca.get("as_of", "")
    meta = (f'Built {subj.get("built")} &middot; {subj.get("sf", 0):,} SF above grade '
            f'&middot; Assessment {_m(subj.get("assessment"))} &middot; '
            f'Listed {_m(subj.get("list"))}'
            + (f' &middot; {subj["dom"]} days on market' if subj.get("dom") is not None else ""))
    return f"""<section class="ca" id="contract-analytics"><div class="wrap">
<h2 class="st">Contract Analytics</h2>
<p class="ss ca-lede">How the home stacks up against the current market{f" as of {as_of}" if as_of else ""} &mdash; closed sales, the competition, and the listings that did not sell. {meta}</p>
<div class="ca-tw"><table class="ca-t"><thead><tr>{"".join(f"<th>{c}</th>" for c in head)}</tr></thead>
<tbody>{"".join(body)}</tbody></table></div>
{f'<ul class="ca-notes">{notes}</ul>' if notes else ""}
</div></section>
<style>
.ca{{padding:56px 0;}}
.ca .ca-lede{{max-width:820px;margin-left:auto;margin-right:auto;text-align:center;}}
.ca-tw{{overflow-x:auto;border:1px solid var(--rule);border-radius:10px;margin-top:26px;background:var(--card,#fff);}}
.ca-t{{width:100%;border-collapse:collapse;font-size:14px;min-width:820px;}}
.ca-t thead th{{background:var(--banner);font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);font-weight:600;padding:16px 12px;border-bottom:1px solid var(--gold-line);text-align:center;}}
.ca-t td{{padding:12px;text-align:center;border-bottom:1px solid var(--rule);white-space:nowrap;letter-spacing:.03em;}}
.ca-t td:first-child,.ca-t th:first-child{{text-align:left;padding-left:20px;}}
.ca-t td:first-child{{font-weight:600;letter-spacing:.02em;}}
.ca-t td:last-child,.ca-t td:nth-child(8){{font-weight:700;}}
.ca-t tbody tr:nth-child(even) td{{background:#FBF8F1;}}
.ca-t tr.subj td,.ca-t tr.avg td{{background:var(--banner)!important;font-weight:700;}}
.ca-t tr.grp td{{background:#fff!important;text-align:left;padding:14px 20px 6px;font-size:11.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--gold-deep);font-weight:700;border-bottom:none;}}
.ca-notes{{font-size:12px;color:var(--muted);margin:14px 0 0;padding-left:18px;line-height:1.6;}}
</style>
"""


def add_to_index(p, out, note=print):
    """Drop the section into the seller portal page, before "Track the Sale"."""
    sec = section(p)
    f = out / "index.html"
    if not sec or not f.exists():
        return
    h = f.read_text(encoding="utf-8")
    import re
    h = re.sub(r'<section class="ca" id="contract-analytics">.*?</style>\n', "", h, flags=re.S)
    anchor = h.find('<h2 class="st">Track the Sale')
    at = h.rfind("<section", 0, anchor) if anchor > 0 else h.find("<footer")
    if at < 0:
        note("Contract Analytics: no place found on the seller portal page.")
        return
    f.write_text(h[:at] + sec + h[at:], encoding="utf-8")
    note("Contract Analytics: table added to the seller portal page.")
