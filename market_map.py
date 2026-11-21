#!/usr/bin/env python3
"""Roadmap maps -- the current market and the solds, priced against value.

Casey, 31 Oct 2026, on 10315 Mountington: "Show subject then actives in red
with Address, List price and amount under or over Customary Value in
thousands." Then: "Take current map off the portal and move to Roadmap under
Current conditions and add A/C and pending. Also have a map just like it of
the solds under table."

p["market_map"]:
    {"subject": [lat, lng],
     "listings": [{"address", "status": "Active"|"Active Under Contract"|"Pending",
                   "list", "lat", "lng"}, ...],
     "solds":    [{"address", "sale", "lat", "lng"}, ...]}
Every coordinate is a Google Places record. Over/under = price minus
Customary Value, to the nearest $1K. The maps are screen-only; the printed
Roadmap keeps its tables.
"""
import json
import re

MSS_EMBED = "https://caseysamson.com/market-snapshot/cstmarketsnapshot/map_embed.html"

COLORS = {"Active": "#B3261E", "Active Under Contract": "#C8701E", "Pending": "#2F6B3A", "Sold": "#1E3557"}
SHORT = {"Active": "Active", "Active Under Contract": "A/C", "Pending": "Pending", "Sold": "Sold"}
# Casey, 13 Nov 2026: "the current conditions map should have DOM and say
# active pending or contingent."
LIST_WORD = {"Active": "Active", "Active Under Contract": "Contingent", "Pending": "Pending"}

# Casey, 13 Nov 2026: "In the sales comps, there should be red if properties
# sold in over 30 days or under 95% of list price, yellow if 8-30 days or
# 95-100% of LP, green if sold in less than 7 days over list price." The worse
# reading wins. Index 0 red, 1 yellow, 2 green.
SOLD_GRADE = (("red", "#B3261E", "Over 30 days or under 95% of original list"),
              ("yellow", "#D9A52B", "8&ndash;30 days or under 99% of original list"),
              ("green", "#2F6B3A", "7 days or less and 99% or more of original list"))
# Casey, 21 Nov 2026: yellow = 8-30 days or under 99% of original list;
# red = over 30 days or under 95%. Green is what is left: 7 days or less
# at 99%+ of original list.


def sold_grade(dom, sale, lp):
    r = sale / lp if lp else 1
    g_dom = 0 if dom > 30 else (1 if dom > 7 else 2)
    g_pct = 0 if r < 0.95 else (1 if r < 0.99 else 2)
    return min(g_dom, g_pct)


def _k(x):
    k = int(abs(x) / 1000 + 0.5)
    return ("+" if x > 0 else "&minus;" if x < 0 else "") + f"${k:,}K"


def _map(p, mid, title, items, kind):
    mm = p["market_map"]
    cv = p["values"]["customary"]
    lat, lng = mm["subject"]
    pins = []
    for i, a in enumerate(items):
        st = a.get("status", "Sold")
        price = a.get("sale") if kind == "sold" else a.get("list")
        # Casey, 31 Oct 2026: "Each home has their own customary value ...
        # see if it sold under or over it's Customary." With a home's own
        # value on file the difference is against it; otherwise the subject's.
        # No figure from the subject's Customary any more: comparing another
        # home to this one's value is the reading Casey corrected. Without its
        # own Customary the pin shows the price alone.
        own = a.get("customary")
        if not own and kind != "sold":
            # Casey, 7 Nov 2026: every active / under-contract home priced with
            # the CST Pricing Model (pricing_model.py run). Thin sets (<3 comps)
            # stay off the map.
            try:
                from pricing_model import lookup
                hit = lookup(a["address"])
                if hit and hit.get("customary") and not hit.get("thin"):
                    own = hit["customary"]; a["customary"] = own
            except Exception:
                pass
        if own:
            d = price - own
            word = "over" if d > 0 else "under" if d < 0 else "at"
            vs = (f'<br><span style="color:{"#2F6B3A" if d > 0 else "#B3261E"}">'
                  f'{_k(d)} {word} its Customary</span>')
        else:
            vs = ""
        col = COLORS.get(st, "#B3261E")
        # Casey, 13 Nov 2026: current-market pins show their DOM and are
        # colored by it (7 or less green, 8-30 yellow, over 30 red) -- "truman
        # in the current market can not be green if DOM is 96". 17 Nov 2026
        # (15100 Heather Mill): "There are 3 active and 1 a/c on too long so 4
        # reds." An Active home has no contract, so it is red whatever its DOM;
        # the bands grade only homes that went under contract.
        if kind != "sold":
            if a.get("dom") is None:
                for c in p.get("competition") or []:
                    if c.get("address") == a["address"] and c.get("dom") is not None:
                        a["dom"] = c["dom"]
            if a.get("dom") is not None:
                vs = f'<br>{a["dom"]} day{"s" if a["dom"] != 1 else ""} on market' + vs
                g = 0 if a["dom"] > 30 else (1 if a["dom"] > 7 else 2)
                if st == "Active":
                    g = 0
                a["_grade"] = g
                col = SOLD_GRADE[g][1]
        # Casey, 13 Nov 2026: "% under or over list price should be under or
        # over Orig list price, not LP." Original list drives color and label;
        # the current list is only a fallback and says so.
        _base = a.get("orig_list") or a.get("list")
        if kind == "sold" and a.get("dom") is not None and _base:
            g = sold_grade(a["dom"], price, _base)
            a["_grade"] = g
            col = SOLD_GRADE[g][1]
            _w = "original list" if a.get("orig_list") else "list"
            vs = (f'<br>{a["dom"]} day{"s" if a["dom"] != 1 else ""} &middot; '
                  f'{price / _base * 100:.1f}% of {_w} ${_base:,}') + vs
        pins.append({"lat": a["lat"], "lng": a["lng"], "n": i + 1, "c": col,
                     "t": f'<b>{a["address"]}</b><br>{(LIST_WORD if kind != "sold" else SHORT).get(st, st)} &middot; ${price:,}{vs}',
                     "dir": a.get("dir", ["right", "left", "top", "bottom"][i % 4]),
                     "off": a.get("off")})
    seen = []
    for a in items:
        st = a.get("status", "Sold")
        if st not in seen:
            seen.append(st)
    legend = "".join(f'<span><i style="background:{COLORS.get(s, "#B3261E")}"></i>{LIST_WORD.get(s, s) if kind != "sold" else s}</span>' for s in seen)
    if kind != "sold" and any("_grade" in a for a in items):
        LIST_GRADE = ("Active (no contract) or over 30 days on market",
                      "Under contract in 8&ndash;30 days",
                      "Under contract in 7 days or less")
        legend = "".join(f'<span><i style="background:{SOLD_GRADE[g][1]}"></i>{LIST_GRADE[g]}</span>'
                         for g in (2, 1, 0) if any(a.get("_grade") == g for a in items))
    if kind == "sold" and any("_grade" in a for a in items):
        legend = "".join(f'<span><i style="background:{SOLD_GRADE[g][1]}"></i>{SOLD_GRADE[g][2]}</span>'
                         for g in (2, 1, 0) if any(a.get("_grade") == g for a in items))
    key = "".join(f'<li><span class="rmm-kn" style="background:{q["c"]}">{q["n"]}</span><span>{q["t"]}</span></li>' for q in pins)
    data = {"s": [lat, lng], "sl": p["address"], "sv": f"Customary Value ${cv:,}", "pins": pins,
            "sdir": mm.get("subject_dir_solds" if kind == "sold" else "subject_dir", "left")}
    return f"""<div class="rmm"><div class="rmm-h">{title}</div>
<div class="rmm-map" id="{mid}"></div>
<ol class="rmm-key">{key}</ol>
<div class="rmm-leg"><span><i style="background:#221C14"></i>Subject</span>{legend}<span class="rmm-note">{"Sale price" if kind == "sold" else "List price"}{" &middot; over or under each home&rsquo;s own Customary Value" if any(a.get("customary") for a in items) else ""}</span></div></div>
<script>window.addEventListener('load',function(){{var D={json.dumps(data)};
if(!window.L||!document.getElementById('{mid}'))return;
var OFF={{right:[14,0],left:[-14,0],top:[0,-14],bottom:[0,14]}};
var m=L.map('{mid}',{{scrollWheelZoom:false}}).setView(D.s,14);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}}).addTo(m);
var pts=[D.s], items=[];
items.push({{ll:D.s,html:"<div class='rmm-pin' style='background:#221C14'>&#9733;</div>",t:"<b>"+D.sl+"</b><br>"+D.sv,dir:D.sdir,cls:'rmm-lab rmm-lab-s',z:1000}});
D.pins.forEach(function(p){{pts.push([p.lat,p.lng]);
 items.push({{ll:[p.lat,p.lng],html:"<div class='rmm-pin' style='background:"+p.c+"'>"+p.n+"</div>",t:p.t,dir:p.dir,off:p.off,cls:'rmm-lab',z:0}});}});
var mks=items.map(function(it){{return L.marker(it.ll,{{icon:L.divIcon({{className:'',html:it.html,iconSize:[24,24],iconAnchor:[12,12]}}),zIndexOffset:it.z}}).addTo(m);}});
m.fitBounds(L.latLngBounds(pts),{{padding:[55,75]}});
// Casey, 31 Oct 2026: labels must not cover each other. Each label tries its
// preferred side, then the others, and keeps the first that is clear of every
// placed label and pin (or the least-covered one).
function place(){{
  var box=document.getElementById('{mid}').getBoundingClientRect();
  var pinR=mks.map(function(k){{var e=k.getElement().getBoundingClientRect();return [e.left-2,e.top-2,e.right+2,e.bottom+2];}});
  var placed=[];
  function ov(a,b){{var w=Math.min(a[2],b[2])-Math.max(a[0],b[0]),h=Math.min(a[3],b[3])-Math.max(a[1],b[1]);return w>0&&h>0?w*h:0;}}
  items.forEach(function(it,i){{
    var order=[it.dir,'right','left','top','bottom'].filter(function(d,j,a){{return a.indexOf(d)===j;}});
    var best=null;
    for(var k=0;k<order.length;k++){{var d=order[k];
      mks[i].unbindTooltip();
      mks[i].bindTooltip(it.t,{{permanent:true,direction:d,offset:(k===0&&it.off)?it.off:OFF[d],className:it.cls}}).openTooltip();
      var e=mks[i].getTooltip().getElement().getBoundingClientRect(), r=[e.left,e.top,e.right,e.bottom];
      var cost=0; placed.forEach(function(q){{cost+=ov(r,q);}}); pinR.forEach(function(q,j){{if(j!==i)cost+=ov(r,q);}});
      if(r[0]<box.left||r[2]>box.right||r[1]<box.top||r[3]>box.bottom)cost+=5000;
      if(!best||cost<best.c)best={{d:d,c:cost,r:r,k:k}};
      if(cost===0)break;}}
    // A label that cannot sit clear of the others is left off the map: the
    // numbered key under the map carries it. The subject always keeps its.
    if(best.c>0&&i>0){{mks[i].unbindTooltip();mks[i].bindTooltip(it.t,{{direction:'top',className:it.cls}});return;}}
    if(best.d!==d){{mks[i].unbindTooltip();mks[i].bindTooltip(it.t,{{permanent:true,direction:best.d,offset:(best.k===0&&it.off)?it.off:OFF[best.d],className:it.cls}}).openTooltip();}}
    placed.push(best.r);
  }});
}}
place(); m.on('zoomend',place);}});</script>
"""


STYLE = """<link rel="stylesheet" href="leaflet.css">
<script src="leaflet.js"></script>
<style>
.rmm{margin:26px 0 8px;}
.rmm-h{font:600 15px 'Playfair Display',Georgia,serif;text-align:center;margin-bottom:10px;}
.rmm-map{height:440px;border:1px solid var(--rule,#E4DCC8);border-radius:10px;background:#EAE6DE;}
.rmm-leg{display:flex;flex-wrap:wrap;gap:6px 18px;justify-content:center;margin-top:10px;font-size:12.5px;color:#71695A;}
.rmm-leg i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px;vertical-align:-1px;}
.rmm-note{font-style:italic;}
.rmm-map .leaflet-tooltip-pane{z-index:590;}  /* pins sit on top of labels, never under them */
.rmm-key{list-style:none;padding:0;margin:12px 0 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px 16px;font-size:12.5px;line-height:1.35;}
.rmm-key li{display:flex;gap:8px;align-items:flex-start;}
.rmm-kn{flex:0 0 20px;height:20px;border-radius:50%;color:#fff;font:700 11px/20px Georgia,serif;text-align:center;}
.rmm-pin{color:#fff;border:2px solid #fff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;
  justify-content:center;font:700 12px Georgia,serif;box-shadow:0 1px 4px rgba(0,0,0,.35);}
.leaflet-tooltip.rmm-lab{background:#fff;border:1px solid #CFC6B2;color:#221C14;font:500 12px/1.35 'Lora',Georgia,serif;
  padding:5px 8px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.18);}
.leaflet-tooltip.rmm-lab-s{border:1.5px solid #221C14;}
@media print{.rmm{display:none;}}
</style>
"""


def add_to_roadmap(p, out, note=print):
    from pathlib import Path
    import shutil
    mm = p.get("market_map")
    if not mm:
        return
    if not mm.get("subject"):
        # Never a guessed pin: the maps wait for the home's own coordinates.
        note("Roadmap maps HELD -- market_map.subject has no coordinates yet.")
        return
    f = Path(out) / f'{p["prefix"]}_Roadmap.html'
    if not f.exists():
        return
    tpl = Path(__file__).parent / "templates"
    for lf in ("leaflet.js", "leaflet.css"):
        if (tpl / lf).exists():
            shutil.copy(tpl / lf, Path(out) / lf)
    h = f.read_text(encoding="utf-8")
    h = re.sub(r'<!--RMM[a-z]*-->.*?<!--/RMM[a-z]*-->\n?', "", h, flags=re.S)
    done = []
    # Solds: under the comps table.
    if mm.get("solds"):
        i = h.find("Appraisal-Quality Comparable Analysis</h2>")
        j = h.find("</table>", i)
        j = h.find("</div>", j) + len("</div>") if j > 0 else -1
        if i > 0 and j > 0:
            blk = "<!--RMMs-->" + _map(p, "rmmSold", "Comparable Sales", [dict(a, status="Sold") for a in mm["solds"]], "sold") + "<!--/RMMs-->\n"
            h = h[:j] + "\n" + blk + h[j:]
            done.append(f'{len(mm["solds"])} solds under the comps')
    # Listings: under the Current Competition table (Casey, 31 Oct 2026:
    # "Move current market map under table").
    # Casey, 1 Nov 2026 took it off ("too much stuff"); Casey, 2 Nov 2026:
    # "Moving forward, All seller portals need maps for comps and
    # competition." On by default again; "listings_map": false leaves it off.
    if mm.get("listings") and mm.get("listings_map", True) is not False:
        i = h.find("Current Competition</h2>")
        j = h.find("</table>", i)
        j = h.find("</div>", j) if j > 0 else -1
        if i > 0 and j > 0:
            j += len("</div>")
            blk = "<!--RMMl-->" + _map(p, "rmmList", "The Current Market", mm["listings"], "list") + "<!--/RMMl-->\n"
            h = h[:j] + "\n" + blk + h[j:]
            done.append(f'{len(mm["listings"])} listings under the Current Competition table')
    if done:
        h = h.replace("</head>", "<!--RMMcss-->" + STYLE + "<!--/RMMcss-->\n</head>", 1)
        f.write_text(h, encoding="utf-8")
        note("Roadmap maps: " + "; ".join(done) + ".")


def add_mss_map(p, out, note=print):
    """Casey, 1 Nov 2026: "I would like to add this map above the seller
    roadmap" -- the MSS region map (Under Contract by Town, Family and
    Luxury, from MSS_Map_Section_Handoff.zip). It sits at the top of the
    Roadmap in its own frame, so its styles and the Roadmap's cannot touch.
    The page is templates/MSS_Map.html, this week's figures; rebuild it from
    templates/mss_map_handoff/builders when the MSS refreshes.
    "mss_map": false on a property leaves it off."""
    from pathlib import Path
    import shutil
    # Casey, 1 Nov 2026 (later the same day): "take this out of Road maps".
    # Off by default now; "mss_map": "local" or "live" on a property puts it
    # back for that one.
    if not p.get("mss_map"):
        return
    src = Path(__file__).parent / "templates" / "MSS_Map.html"
    f = Path(out) / f'{p["prefix"]}_Roadmap.html'
    if not (src.exists() and f.exists()):
        return
    # Casey, 1 Nov 2026: the map is served live from the MSS (map_embed.html,
    # updated with every Wednesday publish). "mss_map": "local" falls back to
    # the saved copy in templates/MSS_Map.html.
    live = p.get("mss_map") == "live"
    if not live:
        shutil.copy(src, Path(out) / "MSS_Map.html")
    # Opens on the listing's own segment: Luxury or Family, read off its
    # market ("Oakton Luxury Market"); "mss_segment" on the property overrides.
    seg = p.get("mss_segment") or ("Luxury" if "luxury" in ((p.get("market") or {}).get("name") or "").lower() else "Family")
    h = f.read_text(encoding="utf-8")
    h = re.sub(r'<!--MSSMAP-->.*?<!--/MSSMAP-->\n?', "", h, flags=re.S)
    src_url = (f"{MSS_EMBED}?seg={seg}" if live else f"MSS_Map.html?seg={seg}")
    height = "900px"   # the MSS embed fills its frame; 900 is its size   # MSS side: 900 keeps every label clear
    blk = ('<!--MSSMAP--><section class="mssmap-sec"><div class="wrap">'
           f'<iframe id="mssMapFrame" src="{src_url}" title="Northern Virginia market map" '
           f'style="width:100%;height:{height};border:0;display:block;" loading="lazy"></iframe>'
           '</div></section>\n<style>.mssmap-sec{padding:26px 0 6px;}@media print{.mssmap-sec{display:none;}}</style>\n'
           '<script>window.addEventListener("message",function(e){var d=e.data||{};'
           'if(d.cstMssMap){var fr=document.getElementById("mssMapFrame");if(fr)fr.style.height=(d.cstMssMap+4)+"px";}});</script>'
           '<!--/MSSMAP-->\n')
    at = h.find("</header>")
    at = at + len("</header>") if at > 0 else h.find("<section")
    if at < 0:
        note("MSS map: no place found on the Roadmap.")
        return
    f.write_text(h[:at] + "\n" + blk + h[at:], encoding="utf-8")
    note(f"MSS map: {'live from ' + MSS_EMBED if live else 'saved copy'} at the top of the Roadmap, opening on {seg}.")


def portal_mss_block(p, out):
    """The MSS region map for the Seller Portal nav page, after Marketing Your
    Home (Casey, 2 Nov 2026). Saved copy, so it works before the MSS embed is
    published; "mss_map": "live" frames the MSS's own page instead."""
    from pathlib import Path
    import shutil
    src = Path(__file__).parent / "templates" / "MSS_Map.html"
    live = p.get("mss_map") == "live"
    if not live:
        if not src.exists():
            return ""
        shutil.copy(src, Path(out) / "MSS_Map.html")
    seg = p.get("mss_segment") or ("Luxury" if "luxury" in ((p.get("market") or {}).get("name") or "").lower() else "Family")
    src_url = (f"{MSS_EMBED}?seg={seg}" if live else f"MSS_Map.html?seg={seg}")
    height = "900px"   # the MSS embed fills its frame; 900 is its size
    return ('<section class="mssmap-sec" style="margin:8px 0 18px;">'
            f'<iframe id="mssMapFrame" src="{src_url}" title="Northern Virginia market map" '
            f'style="width:100%;height:{height};border:0;display:block;" loading="lazy"></iframe></section>'
            '<style>@media print{.mssmap-sec{display:none;}}</style>'
            '<script>window.addEventListener("message",function(e){var d=e.data||{};'
            'if(d.cstMssMap){var fr=document.getElementById("mssMapFrame");if(fr)fr.style.height=(d.cstMssMap+4)+"px";}});</script>')
