#!/usr/bin/env python3
"""Move Up Calculator.

Casey, 21 Nov 2026 (sketch): Current Home -- Value, Outstanding debt, Walk
out the door proceeds, the math -- then New Home -- Price, bring in the
proceeds minus lender / buyer costs, additional down payment -- PMT. Rate is
a 2-1 buydown: Year 1 at note rate - 2, Year 2 at note - 1, Year 3+ at note.

Seller side uses the Seller Net Proceeds costs (commission %, Grantor's Tax
0.3%, settlement $855 + deed $175 + admin $345). Buyer side uses the lender
and title model from the "What It Takes to Win" calculator (win_calc.py).

    python3 move_up.py properties/X.json     -> output/<prefix>/<prefix>_Move_Up.html

Optional property-file block "move_up": {"rate": 7.50, "rate_label": "...",
"new_price": 2900000, "debt": 0, "listing_pct": 2.5, "buyer_pct": 2.5,
"buydown_paid_by": "seller"} -- everything has a default.
"""
import html as _h
import json
import sys
from pathlib import Path

import win_calc

DEFAULTS = {
    "rate": 7.50, "rate_label": "MND 30-yr jumbo, 11/18/26",
    "listing_pct": 2.5, "buyer_pct": 2.5, "seller_flat": 855 + 175 + 345,
    "debt": 0, "buydown_paid_by": "seller",
}


def settings(p):
    c = dict(DEFAULTS)
    for k in ("lender_fees", "title_base", "title_pct", "escrows", "prepaid_days",
              "tax_rate", "ins_hoa", "down_pct"):
        c[k] = win_calc.DEFAULTS[k]
    c.update(((p.get("buyer_portal") or {}).get("win_calc") or {}))
    c.update(p.get("move_up") or {})
    v = p["values"]
    c["values"] = {"dated": int(v.get("dated") or 0), "customary": int(v["customary"]),
                   "premium": int(v["premium"])}
    # Quick-pick buttons match the Roadmap's price cards (Whimbrell-style
    # upgrade tiers show Customary, then the two upgrade-return prices).
    ul = v.get("upgrade_labels")
    if ul and v.get("customary_unadjusted"):
        c["picks"] = [("Customary", int(v["customary_unadjusted"])),
                      (ul[0], int(v["customary"])), (ul[1], int(v["premium"]))]
    else:
        c["picks"] = [(t, c["values"][k]) for k, t in
                      (("dated", "Dated"), ("customary", "Customary"), ("premium", "Premium"))
                      if c["values"][k]]
    c.setdefault("value", c["values"]["customary"])
    c.setdefault("new_price", int(round(c["value"] * 1.35, -4)))
    return c


def section(p, brand_line=""):
    c = settings(p)
    data = json.dumps({k: c[k] for k in (
        "listing_pct", "buyer_pct", "seller_flat", "lender_fees", "title_base", "title_pct",
        "escrows", "prepaid_days", "tax_rate", "ins_hoa", "values")})
    m = lambda x: f"${int(x):,}"
    addr = _h.escape(p.get("address") or "your home")
    vbtn = "".join(f'<button type="button" class="mu-q" data-v="{val}">{_h.escape(t)}</button>'
                   for t, val in c["picks"])
    return f"""<section class="mu" id="move-up"><div class="mu-wrap">
{f'<div class="mu-brand">{brand_line}</div>' if brand_line else ''}
<h2 class="mu-t">Move Up Calculator</h2>
<p class="mu-s">What {addr} puts in your pocket, and what it does for the payment on your next home.</p>
<div class="mu-cols">
 <div class="mu-col">
  <h3>Current Home</h3>
  <label><span>Value</span><input id="muVal" class="mu-in" value="{m(c['value'])}"><i class="mu-qs">{vbtn}</i></label>
  <label><span>Outstanding debt</span><input id="muDebt" class="mu-in" value="{m(c['debt'])}"><i>Mortgage payoff and any equity line</i></label>
  <table class="mu-math">
   <tr><td>Value</td><td id="muV1"></td></tr>
   <tr><td>Commission (<span id="muCp"></span>%)</td><td id="muComm"></td></tr>
   <tr><td>Grantor&rsquo;s Tax (0.3%)</td><td id="muTax"></td></tr>
   <tr><td>Settlement, deed &amp; admin</td><td id="muFlat"></td></tr>
   <tr><td>Outstanding debt</td><td id="muD1"></td></tr>
  </table>
  <div class="mu-arrow" aria-hidden="true"></div>
  <div class="mu-out"><span>Walk out the door proceeds</span><b id="muWalk"></b></div>
 </div>
 <div class="mu-col">
  <h3>New Home</h3>
  <label><span>New home price</span><input id="muNew" class="mu-in" value="{m(c['new_price'])}"></label>
  <label><span>Additional down payment</span><input id="muAdd" class="mu-in" value="$0"><i>Cash beyond the sale proceeds</i></label>
  <label><span>Note rate, 30-yr fixed</span><input id="muRate" class="mu-in" type="number" step="0.05" min="2" max="15" value="{c['rate']}"><i>{_h.escape(c['rate_label'])} &middot; 2-1 buydown</i></label>
  <label><span>Buydown paid by</span><select id="muBy" class="mu-in"><option value="seller"{' selected' if c['buydown_paid_by'] == 'seller' else ''}>New home&rsquo;s seller (concession)</option><option value="buyer"{' selected' if c['buydown_paid_by'] == 'buyer' else ''}>You, at closing</option></select></label>
  <table class="mu-math">
   <tr><td>Proceeds brought in</td><td id="muP1"></td></tr>
   <tr><td>Lender fees</td><td id="muLf"></td></tr>
   <tr><td>Title &amp; recording</td><td id="muTi"></td></tr>
   <tr><td>Prepaids &amp; escrows</td><td id="muPre"></td></tr>
   <tr id="muBdRow"><td>2-1 buydown</td><td id="muBd"></td></tr>
   <tr><td>Additional down payment</td><td id="muA1"></td></tr>
   <tr class="tot"><td>Down payment (<span id="muDp"></span>)</td><td id="muDown"></td></tr>
   <tr><td>Loan amount</td><td id="muLoan"></td></tr>
  </table>
  <div class="mu-arrow" aria-hidden="true"></div>
  <div class="mu-pmt">
   <div><span>Year 1</span><small id="muR1"></small><b id="muY1"></b></div>
   <div><span>Year 2</span><small id="muR2"></small><b id="muY2"></b></div>
   <div><span>Year 3&ndash;30</span><small id="muR3"></small><b id="muY3"></b></div>
  </div>
  <p class="mu-pi" id="muPi"></p>
 </div>
</div>
<p class="mu-warn" id="muWarn"></p>
<p class="mu-note">Estimates for planning only, not a loan offer or a settlement statement. Payments include principal &amp; interest, property taxes at {c['tax_rate']}% of price, and insurance &amp; HOA ${c['ins_hoa']:,}/mo. Seller costs exclude prorations and the regional recordation fees; buyer costs are estimates from our lender and title partners. Ask your lender for a Loan Estimate.</p>
</div></section>
<style>
.mu{{padding:48px 0;border-top:1px solid #e6dcc6;font-family:Georgia,serif;color:#1d1a14;}}
.mu-wrap{{max-width:1040px;margin:0 auto;padding:0 20px;}}
.mu-brand{{text-align:center;font:700 11.5px/1 system-ui,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:#8A6A2E;margin-bottom:10px;}}
.mu-t{{text-align:center;font:700 32px 'Playfair Display',Georgia,serif;margin:0 0 6px;}}
.mu-s{{text-align:center;color:#6b6252;margin:0 0 26px;}}
.mu-cols{{display:grid;grid-template-columns:1fr 1fr;gap:28px;}}
.mu-col{{background:#fff;border:1px solid #e6dcc6;border-top:4px solid #1F2A44;border-radius:10px;padding:20px 22px;display:flex;flex-direction:column;}}
.mu-col h3{{font:700 21px 'Playfair Display',Georgia,serif;margin:0 0 14px;text-align:center;}}
.mu-col label{{display:flex;flex-direction:column;gap:4px;margin-bottom:12px;}}
.mu-col label span{{font:700 11px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#6b6252;}}
.mu-col label i{{font:12px system-ui,sans-serif;color:#8a8170;font-style:normal;}}
.mu-in{{font:600 17px Georgia,serif;padding:9px 12px;border:1px solid #cdb98a;border-radius:6px;background:#fffdf6;color:#1d1a14;width:100%;box-sizing:border-box;}}
.mu-qs{{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;}}
.mu-q{{font:600 12px system-ui,sans-serif;border:1px solid #cdb98a;background:#f6efdf;color:#6f5526;border-radius:14px;padding:4px 10px;cursor:pointer;}}
.mu-math{{width:100%;border-collapse:collapse;font-size:14.5px;margin-top:6px;}}
.mu-math td{{padding:6px 2px;border-bottom:1px solid #efe7d6;}} .mu-math td:last-child{{text-align:right;white-space:nowrap;}}
.mu-math tr.tot td{{font-weight:700;border-top:2px solid #cdb98a;}}
.mu-arrow{{width:0;height:0;margin:16px auto 12px;border-left:26px solid transparent;border-right:26px solid transparent;border-top:26px solid #2E5D7E;position:relative;}}
.mu-arrow:before{{content:"";position:absolute;left:-9px;top:-46px;width:18px;height:22px;background:#2E5D7E;}}
.mu-out{{background:#1F2A44;color:#fff;border-radius:8px;padding:16px;text-align:center;}}
.mu-out span{{display:block;font:700 11.5px system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#d8c08a;}}
.mu-out b{{font:700 32px 'Playfair Display',Georgia,serif;}}
.mu-pmt{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}}
.mu-pmt div{{background:#1F2A44;color:#fff;border-radius:8px;padding:12px 8px;text-align:center;}}
.mu-pmt div:last-child{{background:#2E5D7E;}}
.mu-pmt span{{display:block;font:700 11px system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#d8c08a;}}
.mu-pmt small{{display:block;font:12px system-ui,sans-serif;color:#c9d2e0;margin:2px 0 4px;}}
.mu-pmt b{{font:700 22px 'Playfair Display',Georgia,serif;}}
.mu-pi{{text-align:center;font:12.5px system-ui,sans-serif;color:#6b6252;margin:10px 0 0;}}
.mu-warn{{text-align:center;color:#B3261E;font-weight:700;min-height:1em;margin:16px 0 0;}}
.mu-note{{text-align:center;font:11.5px/1.5 system-ui,sans-serif;color:#8a8170;margin:14px auto 0;max-width:820px;}}
@media (max-width:760px){{.mu-cols{{grid-template-columns:1fr;}}}}
@media print{{.mu-q{{display:none;}} .mu-in{{border:none;background:none;padding-left:0;}}}}
</style>
<script>
(function(){{
var C={data};
var $=function(i){{return document.getElementById(i);}};
function num(s){{var n=parseFloat(String(s).replace(/[^0-9.]/g,''));return isFinite(n)?n:0;}}
function m(x){{return (x<0?'\\u2212':'')+'$'+Math.abs(Math.round(x)).toLocaleString('en-US');}}
function neg(x){{return x?'\\u2212'+m(x):'$0';}}
function pmt(loan,rate){{var r=rate/100/12;return r>0?loan*r/(1-Math.pow(1+r,-360)):loan/360;}}
function run(){{
  var val=num($('muVal').value), debt=num($('muDebt').value);
  var cp=C.listing_pct+C.buyer_pct, comm=val*cp/100, tax=val*0.003, flat=C.seller_flat;
  var walk=val-comm-tax-flat-debt;
  $('muCp').textContent=cp; $('muV1').textContent=m(val); $('muComm').textContent=neg(comm);
  $('muTax').textContent=neg(tax); $('muFlat').textContent=neg(flat); $('muD1').textContent=neg(debt);
  $('muWalk').textContent=m(walk);
  var price=num($('muNew').value), add=num($('muAdd').value), rate=parseFloat($('muRate').value)||0;
  var byBuyer=$('muBy').value==='buyer';
  var title=C.title_base+price*C.title_pct/100, lf=C.lender_fees;
  // Down payment and loan solve together: prepaid interest and the buydown both depend on the loan.
  var loan=price*0.8, bd=0, pre=0, down=0;
  for(var k=0;k<6;k++){{
    pre=C.escrows+loan*rate/100*C.prepaid_days/365;
    var p0=pmt(loan,rate);
    bd=12*(p0-pmt(loan,Math.max(rate-2,0)))+12*(p0-pmt(loan,Math.max(rate-1,0)));
    down=Math.max(0,walk)-lf-title-pre-(byBuyer?bd:0)+add;
    loan=Math.max(0,price-down);
  }}
  var tx=price*C.tax_rate/100/12, oth=tx+C.ins_hoa;
  $('muP1').textContent=m(Math.max(0,walk)); $('muLf').textContent=neg(lf); $('muTi').textContent=neg(title);
  $('muPre').textContent=neg(pre);
  $('muBd').textContent=byBuyer?neg(bd):m(bd)+' paid by seller';
  $('muA1').textContent=m(add); $('muDown').textContent=m(down); $('muLoan').textContent=m(loan);
  $('muDp').textContent=(price?(down/price*100).toFixed(1):'0')+'% of price';
  var r1=Math.max(rate-2,0), r2=Math.max(rate-1,0);
  $('muR1').textContent=r1.toFixed(2)+'%'; $('muR2').textContent=r2.toFixed(2)+'%'; $('muR3').textContent=rate.toFixed(2)+'%';
  $('muY1').textContent=m(pmt(loan,r1)+oth); $('muY2').textContent=m(pmt(loan,r2)+oth); $('muY3').textContent=m(pmt(loan,rate)+oth);
  $('muPi').textContent='Each payment includes taxes '+m(tx)+'/mo and insurance & HOA '+m(C.ins_hoa)+'/mo. Buydown cost '+m(bd)+'.';
  var w='';
  if(walk<0) w='The sale does not cover the outstanding debt.';
  else if(price && down<0) w='Proceeds do not cover the buyer closing costs.';
  else if(price && down/price<0.2) w='Under 20% down: expect mortgage insurance, not included above.';
  $('muWarn').textContent=w;
}}
document.querySelectorAll('.mu-in').forEach(function(e){{e.addEventListener('input',run);e.addEventListener('change',run);
  if(e.id!=='muRate'&&e.tagName==='INPUT') e.addEventListener('blur',function(){{e.value=m(num(e.value));}});}});
document.querySelectorAll('.mu-q').forEach(function(b){{b.addEventListener('click',function(){{$('muVal').value=m(+b.getAttribute('data-v'));run();}});}});
run();
}})();
</script>
"""


def page(p):
    import private_label as _pl
    _pl.resolve(p)
    pl = p.get("private_label") or {}
    brand = (f'{_h.escape(pl.get("team_name") or pl.get("name", ""))} &middot; Powered by CST Pricing'
             if pl else "The Casey Samson Team &mdash; The Gold Standard of Pricing Strategy")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Move Up Calculator &mdash; {_h.escape(p.get('address', ''))}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#FAF6EE;}} .mu{{border-top:none;}}</style></head><body>
{section(p, brand)}
</body></html>"""


if __name__ == "__main__":
    p = json.loads(Path(sys.argv[1]).read_text())
    out = Path(__file__).resolve().parent / "output" / p["prefix"]
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{p['prefix']}_Move_Up.html"
    f.write_text(page(p), encoding="utf-8")
    print(f)
