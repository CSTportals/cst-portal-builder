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
    python3 move_up.py --standalone          -> output/Move_Up_Calculator/index.html (no property)

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


def buyer_price(p):
    b = p.get("buyer_portal") or {}
    v = p["values"]
    return int(b.get("list_price") or p.get("current_list") or v.get("coming_soon_override")
               or v.get("customary_list") or v["customary"])


def section(p, brand_line="", mode="seller"):
    """mode "seller": Sell = this home (Seller Portal channel, titled Move Up
    (or Down) Calculator). mode "buyer": Buy = this home at its asking price,
    Sell = the buyer's own home, left for them to fill in (Buyer Portal)."""
    # mode "standalone": Casey, 21 Nov 2026 -- the stand-alone buyer
    # calculator references none of our homes: no address, no values, both
    # prices left for the buyer to fill in.
    alone = mode == "standalone"
    if alone:
        p = {"values": {"customary": 0, "premium": 0}}
    c = settings(p)
    buyer = mode in ("buyer", "standalone")
    bpicks = ""
    if alone:
        c["new_price"] = 0
        c["picks"] = []
    elif buyer:
        # Casey, 21 Nov 2026: purchase starts at Customary, with a toggle to
        # Premium so the buyer sees the payment difference between the two.
        v = p["values"]
        c["new_price"] = int(v["customary"])
        c["picks"] = []
        bpicks = "".join(
            f'<button type="button" class="mu-q mu-qb{" on" if k == "customary" else ""}" data-v="{int(v[k])}">{t} {"$" + format(int(v[k]), ",")}</button>'
            for k, t in (("customary", "Customary"), ("premium", "Premium")))
    title = "Move Up Calculator" if buyer else "Move Up (or Down) Calculator"
    c["cust"] = int(p["values"]["customary"]) if (buyer and not alone) else 0
    data = json.dumps({k: c[k] for k in (
        "listing_pct", "buyer_pct", "seller_flat", "lender_fees", "title_base", "title_pct",
        "escrows", "prepaid_days", "tax_rate", "ins_hoa", "values", "cust")})
    m = lambda x: f"${int(x):,}"
    addr = _h.escape(p.get("address") or "your home")
    vbtn = "".join(f'<button type="button" class="mu-q" data-v="{val}">{_h.escape(t)}</button>'
                   for t, val in c["picks"])
    return f"""<section class="mu" id="move-up"><div class="mu-wrap">
{f'<div class="mu-brand">{brand_line}</div>' if brand_line else ''}
<h2 class="mu-t">{title}</h2>
<p class="mu-s">{"What your current home puts toward your next one, and what the monthly payment looks like." if alone else f"What your current home puts toward {addr}, and what the monthly payment looks like." if buyer else f"What {addr} puts in your pocket, and what it does for the payment on your next home."}</p>
<div class="mu-cols">
 <div class="mu-col">
  <h3>Sell</h3>
  <label><span>Sales price</span><input id="muVal" class="mu-in" value="{'' if buyer else m(c['value'])}" placeholder="Your current home&rsquo;s price">{f'<i class="mu-qs">{vbtn}</i>' if vbtn else ''}</label>
  <label><span>Debt</span><input id="muDebt" class="mu-in" value="{m(c['debt'])}"><i>Mortgage payoff and any equity line</i></label>
  <div class="mu-out"><span>Walk out the door proceeds</span><b id="muWalk"></b></div>
  <button type="button" class="mu-arrow" aria-expanded="false" aria-controls="muMathS"><em>Math</em></button>
  <div class="mu-math-wrap" id="muMathS" hidden>
  <table class="mu-math">
   <tr><td>Sales price</td><td id="muV1"></td></tr>
   <tr><td>Commission (<span id="muCp"></span>%)</td><td id="muComm"></td></tr>
   <tr><td>Grantor&rsquo;s Tax (0.3%)</td><td id="muTax"></td></tr>
   <tr><td>Settlement, deed &amp; admin</td><td id="muFlat"></td></tr>
   <tr><td>Debt</td><td id="muD1"></td></tr>
   <tr class="tot"><td>Walk out the door proceeds</td><td id="muW2"></td></tr>
  </table>
  </div>
 </div>
 <div class="mu-col">
  <h3>Buy</h3>
  <label><span>Purchase price{f" &middot; {addr}" if (buyer and not alone) else ""}</span><input id="muNew" class="mu-in" value="{m(c['new_price']) if c['new_price'] else ''}" placeholder="Your next home&rsquo;s price">{f'<i class="mu-qs">{bpicks}</i>' if bpicks else ''}</label>
  <div class="mu-kv"><span>Down payment from proceeds</span><b id="muDfp"></b></div>
  <label><span>Additional down payment</span><input id="muAdd" class="mu-in" value="$0"><i>Cash beyond the sale proceeds</i></label>
  <div class="mu-pmt-h">Monthly payments &middot; 2-1 buydown</div>
  <div class="mu-pmt">
   <div><span>Year 1</span><small id="muR1"></small><b id="muY1"></b></div>
   <div><span>Year 2</span><small id="muR2"></small><b id="muY2"></b></div>
   <div><span>Year 3&ndash;30</span><small id="muR3"></small><b id="muY3"></b></div>
  </div>
  <p class="mu-delta" id="muDelta"></p>
  <button type="button" class="mu-arrow" aria-expanded="false" aria-controls="muMathB"><em>Math</em></button>
  <div class="mu-math-wrap" id="muMathB" hidden>
  <label><span>Note rate, 30-yr fixed</span><input id="muRate" class="mu-in" type="number" step="0.05" min="2" max="15" value="{c['rate']}"><i>{_h.escape(c['rate_label'])} &middot; Year 1 at note &minus; 2, Year 2 at note &minus; 1</i></label>
  <label><span>Buydown paid by</span><select id="muBy" class="mu-in"><option value="seller"{' selected' if c['buydown_paid_by'] == 'seller' else ''}>New home&rsquo;s seller (concession)</option><option value="buyer"{' selected' if c['buydown_paid_by'] == 'buyer' else ''}>You, at closing</option></select></label>
  <table class="mu-math">
   <tr><td>Walk out the door proceeds</td><td id="muP1"></td></tr>
   <tr><td>Lender fees</td><td id="muLf"></td></tr>
   <tr><td>Title &amp; recording</td><td id="muTi"></td></tr>
   <tr><td>Prepaids &amp; escrows</td><td id="muPre"></td></tr>
   <tr><td>2-1 buydown</td><td id="muBd"></td></tr>
   <tr class="tot"><td>Down payment from proceeds</td><td id="muDfp2"></td></tr>
   <tr><td>Additional down payment</td><td id="muA1"></td></tr>
   <tr class="tot"><td>Total down payment (<span id="muDp"></span>)</td><td id="muDown"></td></tr>
   <tr><td>Loan amount</td><td id="muLoan"></td></tr>
   <tr><td>Property taxes</td><td id="muTx"></td></tr>
   <tr><td>Insurance &amp; HOA</td><td id="muIns"></td></tr>
  </table>
  </div>
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
.mu-qb.on{{background:#1F2A44;color:#fff;border-color:#1F2A44;}}
.mu-delta{{text-align:center;font:600 13.5px system-ui,sans-serif;color:#8A6A2E;margin:10px 0 0;min-height:1em;}}
.mu-q{{font:600 12px system-ui,sans-serif;border:1px solid #cdb98a;background:#f6efdf;color:#6f5526;border-radius:14px;padding:4px 10px;cursor:pointer;}}
.mu-math{{width:100%;border-collapse:collapse;font-size:14.5px;margin-top:6px;}}
.mu-math td{{padding:6px 2px;border-bottom:1px solid #efe7d6;}} .mu-math td:last-child{{text-align:right;white-space:nowrap;}}
.mu-math tr.tot td{{font-weight:700;border-top:2px solid #cdb98a;}}
.mu-arrow{{display:block;margin:18px auto 6px;border:none;background:none;cursor:pointer;position:relative;width:110px;height:72px;padding:0;}}
.mu-arrow:before{{content:"";position:absolute;left:29px;top:0;width:52px;height:34px;background:#2E5D7E;}}
.mu-arrow:after{{content:"";position:absolute;left:0;top:32px;border-left:55px solid transparent;border-right:55px solid transparent;border-top:40px solid #2E5D7E;transition:transform .2s;}}
.mu-arrow em{{position:absolute;left:0;right:0;top:11px;z-index:2;font:700 13px system-ui,sans-serif;letter-spacing:.08em;color:#fff;font-style:normal;text-transform:uppercase;}}
.mu-arrow:hover:before{{background:#244b67;}} .mu-arrow:hover:after{{border-top-color:#244b67;}}
.mu-math-wrap{{margin-top:6px;}}
.mu-kv{{display:flex;justify-content:space-between;align-items:baseline;background:#f6efdf;border:1px solid #e6dcc6;border-radius:8px;padding:12px 14px;margin:0 0 12px;}}
.mu-kv span{{font:700 11px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#6b6252;}}
.mu-kv b{{font:700 22px 'Playfair Display',Georgia,serif;}}
.mu-pmt-h{{font:700 11px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#6b6252;margin:4px 0 6px;}}
.mu-out{{background:#1F2A44;color:#fff;border-radius:8px;padding:16px;text-align:center;}}
.mu-out span{{display:block;font:700 11.5px system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#d8c08a;}}
.mu-out b{{font:700 32px 'Playfair Display',Georgia,serif;}}
.mu-pmt{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}}
.mu-pmt div{{background:#1F2A44;color:#fff;border-radius:8px;padding:12px 8px;text-align:center;}}
.mu-pmt div:last-child{{background:#2E5D7E;}}
.mu-pmt span{{display:block;font:700 11px system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#d8c08a;}}
.mu-pmt small{{display:block;font:12px system-ui,sans-serif;color:#c9d2e0;margin:2px 0 4px;}}
.mu-pmt b{{font:700 22px 'Playfair Display',Georgia,serif;}}
.mu-warn{{text-align:center;color:#B3261E;font-weight:700;min-height:1em;margin:16px 0 0;}}
.mu-note{{text-align:center;font:11.5px/1.5 system-ui,sans-serif;color:#8a8170;margin:14px auto 0;max-width:820px;}}
@media (max-width:760px){{.mu-cols{{grid-template-columns:1fr;}}}}
@media print{{.mu-math-wrap{{display:block!important;}} .mu-arrow{{display:none;}} .mu-qb.on{{background:#1F2A44;color:#fff;border-color:#1F2A44;}}
.mu-delta{{text-align:center;font:600 13.5px system-ui,sans-serif;color:#8A6A2E;margin:10px 0 0;min-height:1em;}}
.mu-q{{display:none;}} .mu-in{{border:none;background:none;padding-left:0;}}}}
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
  var walk=val?val-comm-tax-flat-debt:0;
  $('muCp').textContent=cp; $('muV1').textContent=m(val); $('muComm').textContent=neg(comm);
  $('muTax').textContent=neg(tax); $('muFlat').textContent=neg(flat); $('muD1').textContent=neg(debt);
  $('muWalk').textContent=m(walk); $('muW2').textContent=m(walk);
  var price=num($('muNew').value), add=num($('muAdd').value), rate=parseFloat($('muRate').value)||0;
  var byBuyer=$('muBy').value==='buyer', lf=C.lender_fees;
  function buy(price){{
    var title=C.title_base+price*C.title_pct/100;
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
    return {{title:title,pre:pre,bd:bd,down:down,loan:loan,tx:tx,oth:oth,
      y1:pmt(loan,Math.max(rate-2,0))+oth, y2:pmt(loan,Math.max(rate-1,0))+oth, y3:pmt(loan,rate)+oth}};
  }}
  var B=buy(price), title=B.title, pre=B.pre, bd=B.bd, down=B.down, loan=B.loan, tx=B.tx, oth=B.oth;
  document.querySelectorAll('.mu-qb').forEach(function(q){{q.classList.toggle('on', +q.getAttribute('data-v')===Math.round(price));}});
  var dl='';
  if(C.cust && val && Math.round(price)!==C.cust){{
    var K=buy(C.cust), d1=B.y1-K.y1, d3=B.y3-K.y3, sg=function(x){{return (x>=0?'+':'\u2212')+m(Math.abs(x));}};
    dl=(price>C.cust?'Over':'Under')+' Customary by '+m(Math.abs(price-C.cust))+': '+sg(d1)+'/mo in Year 1, '+sg(d3)+'/mo from Year 3';
  }}
  $('muDelta').textContent=dl;
  $('muP1').textContent=m(Math.max(0,walk)); $('muLf').textContent=neg(lf); $('muTi').textContent=neg(title);
  $('muPre').textContent=neg(pre);
  $('muBd').textContent=byBuyer?neg(bd):'$0 ('+m(bd)+' paid by seller)';
  $('muA1').textContent=m(add); var dfp=down-add; $('muDfp').textContent=m(dfp); $('muDfp2').textContent=m(dfp);
  $('muTx').textContent=m(tx)+'/mo'; $('muIns').textContent=m(C.ins_hoa)+'/mo'; $('muDown').textContent=m(down); $('muLoan').textContent=m(loan);
  $('muDp').textContent=(price?(down/price*100).toFixed(1):'0')+'% of price';
  var r1=Math.max(rate-2,0), r2=Math.max(rate-1,0);
  $('muR1').textContent=r1.toFixed(2)+'%'; $('muR2').textContent=r2.toFixed(2)+'%'; $('muR3').textContent=rate.toFixed(2)+'%';
  $('muY1').textContent=m(B.y1); $('muY2').textContent=m(B.y2); $('muY3').textContent=m(B.y3);
  if(!price){{ ['muDfp','muDfp2','muDown','muLoan','muY1','muY2','muY3'].forEach(function(i){{$(i).textContent='\u2014';}}); $('muDp').textContent='\u2014'; }}
  if(!val){{ ['muDfp','muDfp2','muDown','muLoan','muY1','muY2','muY3'].forEach(function(i){{$(i).textContent='\u2014';}}); $('muWalk').textContent='\u2014'; $('muW2').textContent='\u2014'; $('muDp').textContent='\u2014'; }}
  var w='';
  if(!val) w='Enter your current home\u2019s sales price and debt to see your proceeds.';
  else if(!price) w='Enter your next home\u2019s purchase price to see the payments.';
  else if(walk<0) w='The sale does not cover the outstanding debt.';
  else if(price && down<0) w='Proceeds do not cover the buyer closing costs.';
  else if(price && down/price<0.2) w='Under 20% down: expect mortgage insurance, not included above.';
  $('muWarn').textContent=w;
}}
document.querySelectorAll('.mu-in').forEach(function(e){{e.addEventListener('input',run);e.addEventListener('change',run);
  if(e.id!=='muRate'&&e.tagName==='INPUT') e.addEventListener('blur',function(){{if(e.value!=='')e.value=m(num(e.value));}});}});
document.querySelectorAll('.mu-q').forEach(function(b){{b.addEventListener('click',function(){{$(b.classList.contains('mu-qb')?'muNew':'muVal').value=m(+b.getAttribute('data-v'));run();}});}});
document.querySelectorAll('.mu-arrow').forEach(function(a){{a.addEventListener('click',function(){{
  var w=$(a.getAttribute('aria-controls')), open=w.hidden; w.hidden=!open; a.setAttribute('aria-expanded',open);}});}});
run();
}})();
</script>
"""


def standalone_page():
    """The stand-alone buyer Move Up Calculator -- no property, no values."""
    brand = "The Casey Samson Team &mdash; The Gold Standard of Listing Strategies"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Move Up Calculator &mdash; The Casey Samson Team</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#FAF6EE;}} .mu{{border-top:none;}}</style></head><body>
{section(None, brand, mode="standalone")}
</body></html>"""


def page(p):
    import private_label as _pl
    _pl.resolve(p)
    pl = p.get("private_label") or {}
    brand = (f'{_h.escape(pl.get("team_name") or pl.get("name", ""))} &middot; Powered by CST Pricing'
             if pl else "The Casey Samson Team &mdash; The Gold Standard of Listing Strategies")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Move Up (or Down) Calculator &mdash; {_h.escape(p.get('address', ''))}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#FAF6EE;}} .mu{{border-top:none;}}</style></head><body>
{section(p, brand)}
</body></html>"""


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--standalone":
        out = Path(__file__).resolve().parent / "output" / "Move_Up_Calculator"
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(standalone_page(), encoding="utf-8")
        print(out / "index.html")
        sys.exit(0)
    p = json.loads(Path(sys.argv[1]).read_text())
    out = Path(__file__).resolve().parent / "output" / p["prefix"]
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{p['prefix']}_Move_Up.html"
    f.write_text(page(p), encoding="utf-8")
    print(f)
