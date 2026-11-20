#!/usr/bin/env python3
""""What It Takes to Win" -- the buyer portal's offer calculator.

Casey, 25 Oct 2026: "can you build this for our buyer portal". Compare any
two prices side by side: what the buyer pays each month and brings to
closing to move from one offer to another, with the appraisal gap a buyer
covers in cash when the winning price runs past the appraisal.

On the property file, buyer_portal.win_calc (everything optional):

    "win_calc": {
      "lender": "CrossCountry Mortgage",     -- default: the sponsor's name
      "title": "Cardinal Title",
      "rate": 7.60, "rate_label": "MND average, 10/23/26",
      "down_pct": 20,
      "monthly_taxes": 1974,                 -- else assessment x tax_rate / 12
      "tax_rate": 1.1535,                    -- % of assessment, per year
      "ins_hoa": 625,                        -- per month
      "lender_fees": 2539,
      "title_base": 1519, "title_pct": 0.9811,   -- title & recording = base + % of price
      "escrows": 12423, "prepaid_days": 15       -- prepaids = escrows + days of interest
    }

The closing-cost model is an estimate the buyer can see is an estimate;
title_base / title_pct should come from Cardinal's own rate card.
"""
import html as _h
import json

DEFAULTS = {
    "title": "Cardinal Title",
    "rate": 7.60, "rate_label": "MND average, 10/23/26",
    "down_pct": 20, "tax_rate": 1.1535, "ins_hoa": 625, "lender_fees": 2539,
    "title_base": 1519, "title_pct": 0.9811, "escrows": 12423, "prepaid_days": 15,
}


def settings(p, b):
    c = dict(DEFAULTS)
    c.update(b.get("win_calc") or {})
    sp = b.get("sponsor") or {}
    c.setdefault("lender", c.get("lender") or sp.get("name") or "")
    v, subj = p["values"], p["subject"]
    if not c.get("monthly_taxes"):
        c["monthly_taxes"] = round((subj.get("assessment") or 0) * c["tax_rate"] / 100 / 12)
    c["prices"] = {
        "customary": int(v["customary"]),
        "premium": int(v["premium"]),
        "list": int(b.get("list_price") or p.get("current_list") or 0) or None,
    }
    return c


def html(p, b):
    if b.get("win_calc") is False:
        return ""
    c = settings(p, b)
    pr = c["prices"]
    lender, title = _h.escape(c["lender"]), _h.escape(c["title"])
    brand = " &middot; ".join(x for x in (
        f"Financing by {lender}" if lender else "",
        f"Closing costs by {title}" if title else "") if x)
    opts = [("customary", "Customary Value"), ("premium", "Premium Value")]
    if pr["list"]:
        opts.append(("list", "List Price"))
    sel_from = "".join(f'<option value="{k}"{" selected" if k == "premium" else ""}>{t}</option>'
                       for k, t in opts)
    sel_app = ('<option value="offer" selected>At the offer price</option>'
               + "".join(f'<option value="{k}">{t}</option>' for k, t in opts))
    start = pr["list"] or pr["premium"]
    data = json.dumps({k: c[k] for k in (
        "rate", "down_pct", "monthly_taxes", "ins_hoa", "lender_fees",
        "title_base", "title_pct", "escrows", "prepaid_days", "prices")})
    return f"""<section class="wc" id="what-it-takes"><div class="wrap">
<div class="wc-brand">{brand}</div>
<h2 class="st">What It Takes to Win</h2>
<p class="ss">Compare any two prices side by side. See exactly how much more the buyer pays each month and brings to closing to move from one offer to another.</p>
<div class="wc-in">
  <label><span>Compare from</span><select id="wcFrom">{sel_from}</select></label>
  <label><span>Winning offer price</span><input id="wcOffer" type="text" inputmode="numeric" value="${start:,}"><i>Type the escalation or best-and-final number</i></label>
  <label><span>Down payment %</span><input id="wcDown" type="number" min="3" max="100" step="1" value="{c['down_pct']}"><i>Of price or appraisal, whichever is lower</i></label>
  <label><span>Rate, 30-yr fixed jumbo</span><input id="wcRate" type="number" min="1" max="15" step="0.05" value="{c['rate']}"><i>{_h.escape(c['rate_label'])}</i></label>
  <label><span>Appraisal comes in at</span><select id="wcApp">{sel_app}</select><i>Choose Premium to see appraisal-gap cash</i></label>
</div>
<div class="wc-cmp">
  <div class="wc-card"><div class="wc-k" id="wcAName">Premium Value</div><div class="wc-p" id="wcAPrice"></div>
    <div class="wc-r"><span>Monthly payment</span><b id="wcAMo"></b></div><div class="wc-r"><span>Cash to close</span><b id="wcACash"></b></div></div>
  <div class="wc-vs">vs.</div>
  <div class="wc-card wc-win"><div class="wc-k">Winning offer</div><div class="wc-p" id="wcBPrice"></div>
    <div class="wc-r"><span>Monthly payment</span><b id="wcBMo"></b></div><div class="wc-r"><span>Cash to close</span><b id="wcBCash"></b></div></div>
  <div class="wc-card wc-diff"><div class="wc-k">Price difference</div><div class="wc-p" id="wcDPrice"></div>
    <div class="wc-r"><span>Monthly payment</span><b id="wcDMo"></b></div><div class="wc-r"><span>Cash to close</span><b id="wcDCash"></b></div></div>
</div>
<p class="wc-say" id="wcSay"></p>
<div class="wc-tw"><table class="wc-t" id="wcTable"></table></div>
<h3 class="wc-h3">Cash to close at each price</h3>
<p class="ss" style="margin-top:0;">Above the appraised value, every extra dollar comes from the buyer&rsquo;s pocket.</p>
<div id="wcBars" class="wc-bars"></div>
<div class="wc-leg"><span><i style="background:var(--gold-deep)"></i>Down payment</span><span><i style="background:#B4472F"></i>Appraisal gap</span><span><i style="background:var(--gold-line)"></i>Title &amp; recording{f" ({title})" if title else ""}</span><span><i style="background:#9A9487"></i>Lender fees, prepaids &amp; escrows</span></div>
<p class="wc-note">Estimates for comparison only, not a loan offer or a settlement statement. Taxes ${c['monthly_taxes']:,}/mo and insurance &amp; HOA ${c['ins_hoa']:,}/mo held level at every price. Ask {lender or "your lender"} for a Loan Estimate.</p>
</div></section>
<style>
.wc{{padding:56px 0;border-top:1px solid var(--rule);}}
.wc-brand{{text-align:center;font-size:11.5px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;color:var(--gold-deep);margin-bottom:10px;}}
.wc-in{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px 18px;margin:26px 0 22px;}}
.wc-in label{{display:flex;flex-direction:column;gap:5px;font-size:12px;}}
.wc-in label span{{letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--muted);font-size:11px;}}
.wc-in input,.wc-in select{{font:600 16px Georgia,serif;padding:10px 12px;border:1px solid var(--gold-line);border-radius:6px;background:#fff;color:var(--ink);width:100%;box-sizing:border-box;}}
.wc-in i{{font-style:normal;color:var(--muted-2);font-size:11.5px;}}
.wc-cmp{{display:grid;grid-template-columns:1fr auto 1fr 1fr;gap:14px;align-items:stretch;}}
.wc-card{{background:#fff;border:1px solid var(--rule);border-top:3px solid var(--gold-deep);border-radius:8px;padding:16px 18px;}}
.wc-win{{border-top-color:#B4472F;}} .wc-diff{{background:var(--banner);}}
.wc-k{{font-size:11px;letter-spacing:.16em;text-transform:uppercase;font-weight:700;color:var(--muted);}}
.wc-p{{font:700 26px Georgia,serif;margin:4px 0 10px;color:var(--ink);}}
.wc-r{{display:flex;justify-content:space-between;font-size:13.5px;padding:3px 0;border-top:1px solid var(--rule);}}
.wc-vs{{align-self:center;font:italic 18px Georgia,serif;color:var(--muted);}}
.wc-say{{text-align:center;font-size:15px;margin:18px auto 24px;max-width:760px;}}
.wc-tw{{overflow-x:auto;}}
.wc-t{{width:100%;border-collapse:collapse;font-size:13.5px;min-width:560px;}}
.wc-t th,.wc-t td{{padding:7px 10px;text-align:right;border-bottom:1px solid var(--rule);white-space:nowrap;}}
.wc-t th:first-child,.wc-t td:first-child{{text-align:left;}}
.wc-t thead th{{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold-deep);}}
.wc-t tr.tot td{{font-weight:700;border-top:2px solid var(--gold-line);}} .wc-t tr.vs td{{color:var(--muted);font-size:12.5px;}}
.wc-h3{{font:700 19px Georgia,serif;text-align:center;margin:36px 0 6px;}}
.wc-bars{{display:flex;flex-direction:column;gap:12px;margin-top:16px;}}
.wc-bar{{display:grid;grid-template-columns:170px 1fr 92px;gap:12px;align-items:center;font-size:13px;}}
.wc-bar .lb b{{display:block;font-size:12px;color:var(--muted);font-weight:600;}}
.wc-bar .tr{{display:flex;height:22px;border-radius:4px;overflow:hidden;background:var(--rule);}}
.wc-bar .tr i{{display:block;height:100%;}} .wc-bar .am{{text-align:right;font-weight:700;}}
.wc-leg{{display:flex;flex-wrap:wrap;gap:8px 20px;justify-content:center;margin-top:14px;font-size:12px;color:var(--muted);}}
.wc-leg i{{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:6px;vertical-align:-1px;}}
.wc-note{{text-align:center;font-size:11.5px;color:var(--muted-2);margin-top:18px;}}
@media (max-width:760px){{.wc-cmp{{grid-template-columns:1fr;}} .wc-vs{{text-align:center;}} .wc-bar{{grid-template-columns:110px 1fr 80px;}}}}
@media print{{.wc{{display:none;}}}}
</style>
<script>
(function(){{
var C={data};
var $=function(i){{return document.getElementById(i);}};
var NAMES={{customary:'Customary Value',premium:'Premium Value',list:'List price'}};
function num(s){{return Math.round(parseFloat(String(s).replace(/[^0-9.]/g,''))||0);}}
function m(x){{return (x<0?'\\u2212':'')+'$'+Math.abs(Math.round(x)).toLocaleString('en-US');}}
function sm(x){{return x===0?'\\u2014':(x>0?'+':'')+m(x);}}
function calc(price,appKey,down,rate){{
  var app=appKey==='offer'?price:(C.prices[appKey]||price);
  var base=Math.min(price,app), gap=Math.max(0,price-app);
  var dp=base*down/100, loan=base-dp, r=rate/100/12;
  var pi=r?loan*r/(1-Math.pow(1+r,-360)):loan/360;
  var mo=pi+C.monthly_taxes+C.ins_hoa;
  var title=C.title_base+price*C.title_pct/100;
  var pre=C.escrows+loan*rate/100*C.prepaid_days/365;
  return {{price:price,dp:dp,gap:gap,loan:loan,pi:pi,mo:mo,title:title,lf:C.lender_fees,pre:pre,
          cash:dp+gap+title+C.lender_fees+pre}};
}}
function run(){{
  var down=parseFloat($('wcDown').value)||20, rate=parseFloat($('wcRate').value)||C.rate;
  var appKey=$('wcApp').value, fromKey=$('wcFrom').value, offer=num($('wcOffer').value);
  var A=calc(C.prices[fromKey],appKey,down,rate), B=calc(offer,appKey,down,rate);
  $('wcAName').textContent=NAMES[fromKey];
  $('wcAPrice').textContent=m(A.price); $('wcAMo').textContent=m(A.mo); $('wcACash').textContent=m(A.cash);
  $('wcBPrice').textContent=m(B.price); $('wcBMo').textContent=m(B.mo); $('wcBCash').textContent=m(B.cash);
  $('wcDPrice').textContent=sm(B.price-A.price); $('wcDMo').textContent=sm(B.mo-A.mo); $('wcDCash').textContent=sm(B.cash-A.cash);
  var up=B.price>=A.price, dm=Math.abs(B.mo-A.mo), dc=Math.abs(B.cash-A.cash);
  $('wcSay').innerHTML='Moving from '+NAMES[fromKey].toLowerCase()+' ('+m(A.price)+') to '+m(B.price)+' costs the buyer <b>'+m(dm)+' '+(up?'more':'less')+'</b> per month and <b>'+m(dc)+' '+(up?'more':'less')+'</b> at closing.';
  var cols=[['Customary','customary'],['Premium','premium']];
  if(C.prices.list) cols.push(['List price','list']);
  cols.push(['Winning offer',null]);
  var R=cols.map(function(c){{return c[1]?calc(C.prices[c[1]],appKey,down,rate):B;}});
  var P=calc(C.prices.premium,appKey,down,rate);
  var rows=[['Offer price','price'],['Down payment','dp'],['Appraisal gap','gap'],['Loan amount','loan'],
    ['Principal &amp; interest','pi'],['Property taxes',null,C.monthly_taxes],['Insurance &amp; HOA',null,C.ins_hoa],
    ['Monthly payment','mo','tot'],['vs. Premium Value','mo','vs'],
    ['Title &amp; recording','title'],['Lender fees','lf'],['Prepaids &amp; escrows','pre'],
    ['Cash to close','cash','tot'],['vs. Premium Value','cash','vs']];
  var h='<thead><tr><th></th>'+cols.map(function(c){{return '<th>'+c[0]+'</th>';}}).join('')+'</tr></thead><tbody>';
  rows.forEach(function(rw){{
    var cls=rw[2]==='tot'?' class="tot"':rw[2]==='vs'?' class="vs"':'';
    h+='<tr'+cls+'><td>'+rw[0]+'</td>'+R.map(function(x,i){{
      if(rw[1]===null) return '<td>'+m(rw[2])+'</td>';
      if(rw[2]==='vs') return '<td>'+(cols[i][1]==='premium'?'\\u2014':sm(x[rw[1]]-P[rw[1]]))+'</td>';
      return '<td>'+m(x[rw[1]])+'</td>';}}).join('')+'</tr>';
  }});
  $('wcTable').innerHTML=h+'</tbody>';
  var mx=Math.max.apply(null,R.map(function(x){{return x.cash;}}));
  $('wcBars').innerHTML=R.map(function(x,i){{
    var nm=cols[i][1]?NAMES[cols[i][1]]:'Winning offer';
    function seg(v,c){{return v>0?'<i style="width:'+(v/mx*100)+'%;background:'+c+'"></i>':'';}}
    return '<div class="wc-bar"><div class="lb">'+nm+'<b>'+m(x.price)+'</b></div><div class="tr">'
      +seg(x.dp,'var(--gold-deep)')+seg(x.gap,'#B4472F')+seg(x.title,'var(--gold-line)')+seg(x.lf+x.pre,'#9A9487')
      +'</div><div class="am">'+m(x.cash)+'</div></div>';}}).join('');
}}
['wcFrom','wcOffer','wcDown','wcRate','wcApp'].forEach(function(i){{$(i).addEventListener('input',run);$(i).addEventListener('change',run);}});
$('wcOffer').addEventListener('blur',function(){{var v=num(this.value);if(v)this.value='$'+v.toLocaleString('en-US');}});
run();
}})();
</script>
"""
