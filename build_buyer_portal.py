#!/usr/bin/env python3
"""
build_buyer_portal.py — the public, buyer-facing portal for a listing.

    python3.12 build_buyer_portal.py properties/9082_best_bower.json

This is deliberately a SEPARATE SITE from the Seller Portal. The seller
portal carries pricing strategy, money at risk and the seller's own tracker;
none of that belongs in front of a buyer, and a buyer-facing URL sitting in
the same folder is one guess away from the private pages. So this writes to
output/<Prefix>_Buyer/ and copies in only what a buyer or a buyer's agent
should see.

Everything on the page comes from the "buyer_portal" block on the property
JSON. Nothing is invented: a section whose data is absent is left out and
reported at the end, the same discipline the seller pipeline uses.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import watermark

try:
    import segno
except ImportError:                                   # pragma: no cover
    segno = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_portal import buyer_host as _buyer_host  # noqa: E402
from build_portal import buyer_portal_url as _buyer_url  # noqa: E402

HERE = Path(__file__).resolve().parent
TPL = HERE / "templates"
NOTICES = []



# Full-size viewer for the gallery: click or tap a photo, then arrows,
# swipe, Esc or a click outside the picture to move or close.
GALLERY_LIGHTBOX = """<div class="lb" id="lb" role="dialog" aria-modal="true" aria-label="Photo">
  <button class="lb-x" type="button" aria-label="Close">&times;</button>
  <button class="lb-p" type="button" aria-label="Previous">&lsaquo;</button>
  <figure><img id="lb-img" alt=""><figcaption id="lb-cap"></figcaption></figure>
  <button class="lb-n" type="button" aria-label="Next">&rsaquo;</button>
</div>
<script>
(function(){
  var tiles=[].slice.call(document.querySelectorAll('.gal .gal-frame'));
  var lb=document.getElementById('lb'), im=document.getElementById('lb-img'),
      cap=document.getElementById('lb-cap'), cur=0, x0=null;
  if(!tiles.length||!lb) return;
  function show(i){ cur=(i+tiles.length)%tiles.length;
    var t=tiles[cur].querySelector('img'); im.src=t.src; im.alt=t.alt;
    cap.textContent=tiles[cur].parentNode.querySelector('figcaption').textContent; }
  function open(i){ show(i); lb.classList.add('open'); document.body.style.overflow='hidden'; }
  function close(){ lb.classList.remove('open'); document.body.style.overflow=''; tiles[cur].focus(); }
  tiles.forEach(function(t,i){ t.addEventListener('click',function(){ open(i); }); });
  lb.querySelector('.lb-x').onclick=close;
  lb.querySelector('.lb-p').onclick=function(e){ e.stopPropagation(); show(cur-1); };
  lb.querySelector('.lb-n').onclick=function(e){ e.stopPropagation(); show(cur+1); };
  lb.addEventListener('click',function(e){ if(e.target===lb) close(); });
  document.addEventListener('keydown',function(e){ if(!lb.classList.contains('open')) return;
    if(e.key==='Escape') close(); if(e.key==='ArrowLeft') show(cur-1); if(e.key==='ArrowRight') show(cur+1); });
  lb.addEventListener('touchstart',function(e){ x0=e.touches[0].clientX; },{passive:true});
  lb.addEventListener('touchend',function(e){ if(x0===null) return;
    var dx=e.changedTouches[0].clientX-x0; if(Math.abs(dx)>40) show(cur+(dx<0?1:-1)); x0=null; });
})();
</script>
"""

def _buyer_note(v):
    """The buyer portal is buyer facing (Casey, 8 Nov 2026): for a large
    upgrade it says "Over $300,000 in upgrades", never how the upgrade return
    was worked out. Other adjustment notes are seller-side only."""
    if v.get("significant_upgrades"):
        return f"Over ${v['significant_upgrades']:,.0f} in upgrades."
    return ""


def note(msg):
    NOTICES.append(msg)


def money(n):
    return f"${n:,.0f}"


CSS = """
/* ---- Pending stamp -------------------------------------------------
   Casey, 14 Oct 2026: "Make it in red and look like someone stamped it."
   A rubber stamp reads as applied AFTER the page was printed: rotated off
   true, a heavy double rule, letterforms spaced out, and slightly
   transparent so the ink looks absorbed rather than drawn. No drop shadow --
   shadows make it read as a sticker sitting on top. */
.stamp-wrap{display:flex; justify-content:center; margin:30px 0 6px;}
.stamp{--ink:#B3261E; display:inline-flex; flex-direction:column;
  align-items:center; gap:3px; padding:13px 30px 11px;
  border:4px double var(--ink); border-radius:7px; color:var(--ink);
  font-family:'Playfair Display',Georgia,serif; font-weight:700;
  text-transform:uppercase; letter-spacing:.14em; line-height:1.12;
  transform:rotate(-6deg); opacity:.88; text-align:center;
  background:rgba(179,38,30,.045);}
.stamp .stamp-l{font-size:26px; white-space:nowrap;}
.stamp .stamp-l + .stamp-l{font-size:13px; letter-spacing:.11em; opacity:.95;
  white-space:nowrap;}
@media (max-width:620px){
  .stamp{padding:10px 14px 9px;} .stamp .stamp-l{font-size:16px;}
  .stamp .stamp-l + .stamp-l{font-size:9.5px; letter-spacing:.06em;}
}
@media print{ .stamp{opacity:1;} }

:root{
  --bg:#FAF7F0; --card:#FFFFFF; --banner:#F1EBDA; --ink:#221C14;
  --muted:#71695A; --muted-2:#968972; --gold:#A5813B; --gold-deep:#8A6A2E;
  --gold-line:#D3B978; --rule:#E4DCC8; --navy:#1B2233;
  --sh-black:rgba(0,0,0,.86); --sh-gutter:154px;
}
*{box-sizing:border-box;}
body{margin:0; background:var(--bg); color:var(--ink);
  font-family:'Lora',Georgia,serif; line-height:1.6; -webkit-font-smoothing:antialiased;}
.wrap{max-width:1040px; margin:0 auto; padding:0 26px;}
img{max-width:100%;}

/* ---- hero ---- */
.hero{position:relative; min-height:520px; display:flex; align-items:flex-end; overflow:hidden;}
.hero.noshot{min-height:0;}  /* Casey, 20 Nov 2026: compact hero with no photo */
.hero.noshot .hero-inner{padding:44px 0 34px;}
.hero > img{position:absolute; inset:0; width:100%; height:100%; object-fit:cover;}
.hero-shade{position:absolute; inset:0;
  background:linear-gradient(to bottom, rgba(12,10,6,.45) 0%, rgba(12,10,6,.10) 38%, rgba(12,10,6,.80) 100%);}
.hero-inner{position:relative; z-index:2; width:100%; padding:40px 0 34px; text-align:center;}
.hero-inner img.seal{width:66px; display:block; margin:0 auto 12px;
  filter:drop-shadow(0 2px 8px rgba(0,0,0,.6));}
.hero .brandline{letter-spacing:.24em; font-size:11.5px; font-weight:700; color:#F0E4C4;
  text-transform:uppercase; text-shadow:0 2px 10px rgba(0,0,0,.8);}
/* Casey, 24 Nov 2026: balanced like the Roadmap -- title centred on the
   photo, The Casey Samson Team larger. */
.hero:not(.noshot){align-items:center;}
.hero:not(.noshot) .hero-shade{background:radial-gradient(ellipse 70% 65% at 50% 50%,
  rgba(12,10,6,.60) 0%, rgba(12,10,6,.36) 60%, rgba(12,10,6,.28) 100%);}
.hero:not(.noshot) .hero-inner img.seal{width:84px; margin-bottom:14px;}
.hero .brandline{font-family:'Playfair Display',Georgia,serif; font-size:clamp(26px,3.6vw,40px);
  letter-spacing:.12em; color:#E8C77A; line-height:1.1;}
@media (max-width:600px){ .hero .brandline{font-size:22px; letter-spacing:.08em;} }
.hero h1{font-family:'Playfair Display',Georgia,serif; font-weight:700; color:#FFFDF7;
  font-size:clamp(28px,4.4vw,46px); margin:8px 0 2px; line-height:1.1;
  text-shadow:0 2px 14px rgba(0,0,0,.85);}
.hero .city{color:#EDE6D3; font-style:italic; font-size:15px; margin:0 0 16px;
  text-shadow:0 2px 12px rgba(0,0,0,.8);}
.hero .price{display:inline-block; font-family:'Playfair Display',Georgia,serif;
  font-size:clamp(22px,3vw,30px); font-weight:700; color:#FFFDF7; letter-spacing:.01em;
  border:1px solid rgba(240,228,196,.75); border-radius:4px; padding:7px 22px;
  background:rgba(12,10,6,.42); text-shadow:0 2px 10px rgba(0,0,0,.7);}
.hero .site, .hero span.site{display:block; margin-top:14px; font-size:12.5px; letter-spacing:.14em;
  text-transform:uppercase; color:#F0E4C4; text-decoration:none; font-weight:700;
  text-shadow:0 2px 10px rgba(0,0,0,.8);}
.hero .site:hover{text-decoration:underline;}

/* ---- alert band ---- */
.band{background:var(--navy); color:#F6F1E3; padding:22px 0 52px;}
.band .cols{display:flex; gap:0; flex-wrap:wrap; justify-content:center; text-align:center;}
.band .col{flex:1 1 300px; padding:6px 26px;}
.band .col + .col{border-left:1px solid rgba(240,228,196,.25);}
.band .lbl{font-size:10.5px; letter-spacing:.16em; text-transform:uppercase;
  color:#D3B060; font-weight:700; margin-bottom:5px;}
.band .val{font-family:'Playfair Display',Georgia,serif; font-size:19px; font-weight:700;}
.band .sub{font-size:12.5px; color:#BFB7A5; margin-top:3px;}
/* Casey, 15 Oct 2026: "you can also make open house bigger." When the Open
   House is the only column it is the notice, not a footnote beside the
   deadlines, so it gets the room. */
.band .col.oh{flex:1 1 100%; padding-top:10px;}
.band .col.oh .lbl{font-size:12px; letter-spacing:.2em; margin-bottom:8px;}
.band .col.oh .val{font-size:30px; line-height:1.2;}
.band .col.oh .sub{font-size:14px; margin-top:7px;}
@media (max-width:620px){ .band .col.oh .val{font-size:23px;} }
/* The co-listing agents, named in the band so a buyer's agent does not have
   to scroll to the footer to find out who to call. */
.band-contacts{display:flex; flex-wrap:wrap; justify-content:center;
  gap:6px 30px; margin-top:9px;}
.band .bcon{display:inline-flex; align-items:baseline; gap:10px;
  font-size:12.5px; color:#BFB7A5; white-space:nowrap;}
.band .bcon b{color:#F6F1E3; font-weight:700;}
.band .bcon a{color:#BFB7A5; text-decoration:none;
  border-bottom:1px solid rgba(240,228,196,.28);}
.band .bcon a:hover{color:#F6F1E3; border-bottom-color:#F6F1E3;}
@media (max-width:620px){
  .band-contacts{gap:8px 0;}
  .band .bcon{flex-direction:column; gap:1px; width:100%;}
}
@media (max-width:700px){ .band .col + .col{border-left:none; border-top:1px solid rgba(240,228,196,.25); margin-top:14px; padding-top:16px;} }

/* ---- facts ---- */
.facts{display:flex; flex-wrap:wrap; justify-content:center; gap:0;
  background:var(--card); border:1px solid var(--rule); border-radius:8px;
  margin:-28px auto 0; position:relative; z-index:3; max-width:980px;
  box-shadow:0 8px 26px rgba(60,45,10,.09); padding:18px 10px;}
.fact{flex:1 1 110px; text-align:center; padding:6px 10px;}
.fact .n{font-family:'Playfair Display',Georgia,serif; font-size:23px; font-weight:700;
  color:var(--gold-deep); display:block; line-height:1.15;}
.fact .l{font-size:10.5px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); margin-top:3px;}

section{padding:46px 0;}
section + section{border-top:1px solid var(--rule);}
h2.st{font-family:'Playfair Display',Georgia,serif; font-size:24px; font-weight:600;
  text-align:center; margin:0 0 8px;}
p.ss{text-align:center; color:var(--muted); font-size:14.5px; max-width:640px;
  margin:0 auto 26px;}
p.lede{max-width:760px; margin:0 auto; font-size:16px; text-align:center;}
p.builder{max-width:760px; margin:16px auto 0; text-align:center; font-size:14px;
  font-style:italic; color:var(--muted-2);}


/* ---- hook + highlights (replaces the long narrative) ---- */
.pitch{padding:40px 0 36px;}
.hook{font-family:'Playfair Display',Georgia,serif; font-style:italic; font-weight:600;
  font-size:clamp(21px,2.9vw,31px); line-height:1.3; text-align:center;
  max-width:820px; margin:0 auto; color:var(--ink);}
.hl{display:flex; flex-wrap:wrap; justify-content:center; align-items:center;
  gap:0; margin:24px auto 0; max-width:900px;}
.hl span{font-size:12px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--gold-deep); padding:0 18px;}
.hl span + span{border-left:1px solid var(--gold-line);}
@media (max-width:700px){ .hl span{padding:5px 14px;} .hl span + span{border-left:none;} }


/* ---- feature headlines (replaces the narrative) ---- */
.feats{display:grid; grid-template-columns:1fr 1fr; gap:26px 44px; max-width:900px;
  margin:0 auto;}
.feat-h{border-top:2px solid var(--gold-line); padding-top:14px;}
.feat-h h3{font-family:'Playfair Display',Georgia,serif; font-size:21px; font-weight:700;
  margin:0 0 7px; line-height:1.25; color:var(--ink);}
.feat-h p{margin:0; font-size:13.5px; color:var(--muted); line-height:1.65;}
.feat-h p .sep{color:var(--gold-line); margin:0 7px;}
@media (max-width:700px){ .feats{grid-template-columns:1fr; gap:22px;} }

/* ---- video ---- */
.videos{display:flex; gap:22px; justify-content:center; flex-wrap:wrap;}
.vid{flex:0 1 330px; text-align:center;}
.vid video{width:100%; border-radius:10px; display:block; background:#12100C;
  box-shadow:0 6px 22px rgba(60,45,10,.14);}
.vid .cap{font-size:11.5px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--gold-deep); font-weight:700; margin-top:10px;}

.site-cta{text-align:center; margin:26px auto 0;}
.site-cta a{display:inline-block; font-family:'Playfair Display',Georgia,serif;
  font-size:16px; font-weight:700; color:var(--gold-deep); text-decoration:none;
  border:1px solid var(--gold-line); border-radius:4px; padding:11px 26px;
  background:var(--card); box-shadow:0 2px 8px rgba(60,45,10,.06);}
.site-cta a:hover{background:var(--banner);}
.site-cta .sub{font-size:12.5px; color:var(--muted); margin-top:9px;}

/* ---- gallery ---- */
.snap-lede{text-align:center; max-width:720px; margin:0 auto 18px;}
.mu-sec .wrap{max-width:1160px;}
.mu-more{text-align:center; margin:20px 0 0; font-size:14px;}
.mu-more a{color:var(--gold-deep); border-bottom:1px solid var(--gold-line);
  text-decoration:none;}
.snap-pill{display:inline-block; min-width:42px; padding:2px 7px; border-radius:11px;
  font-size:11px; font-weight:700; letter-spacing:.06em;}
.snap-pill.act{background:#E8F1E8; color:#1B7A3D;}
.snap-pill.ac{background:#F7EFD6; color:#8A6A2E;}
.snap-pill.cls{background:#EDE7DA; color:#5B5345;}
.snap-pill.off{background:#F3E7E5; color:#9A4B3F;}
.snap-legend{text-align:center; font-size:12px; color:var(--muted); margin:12px 0 0;}
.snap-legend b{color:var(--ink); letter-spacing:.04em;}
.gal{display:grid; grid-template-columns:repeat(3,1fr); gap:14px;}
.gal figure{margin:0;}
.gal .gal-frame{display:block; overflow:hidden; border-radius:6px; cursor:zoom-in;
  padding:0; border:0; background:none; width:100%;}
.gal img{width:100%; aspect-ratio:3/2; object-fit:cover; border-radius:6px; display:block;
  transition:transform .45s ease;}
@media (hover:hover){ .gal .gal-frame:hover img{transform:scale(1.08);} }
.gal .gal-frame:focus-visible{outline:2px solid var(--gold-deep); outline-offset:3px;}
/* Casey, 20 Oct 2026: "can pictures enlarge on mouse over". Hover zooms the
   tile; a click (or a tap on a phone, which has no hover) opens it full size. */
.lb{position:fixed; inset:0; z-index:2000; display:none; align-items:center;
  justify-content:center; background:rgba(20,16,12,.97); padding:56px 64px;}
.lb.open{display:flex;}
.lb figure{margin:0; max-width:100%; max-height:100%; text-align:center;}
.lb img{max-width:100%; max-height:calc(100vh - 140px); border-radius:6px;
  box-shadow:0 10px 40px rgba(0,0,0,.5);}
.lb figcaption{color:#F1EBDA; font-size:14px; margin-top:12px;}
.lb button{position:absolute; background:rgba(255,255,255,.12); color:#fff; border:0;
  width:46px; height:46px; border-radius:50%; font-size:26px; line-height:46px;
  cursor:pointer;}
.lb button:hover{background:rgba(255,255,255,.25);}
.lb .lb-x{top:44px; right:16px;}
.lb .lb-p{left:14px; top:50%; transform:translateY(-50%);}
.lb .lb-n{right:14px; top:50%; transform:translateY(-50%);}
@media (max-width:560px){ .lb{padding:56px 10px;} .lb .lb-p,.lb .lb-n{top:auto; bottom:14px; transform:none;} }
.gal figcaption{font-size:12px; color:var(--muted); margin-top:6px; text-align:center;}
@media (max-width:860px){ .gal{grid-template-columns:repeat(2,1fr);} }
@media (max-width:560px){ .gal{grid-template-columns:1fr;} }

/* ---- two-column lists ---- */
.two{display:grid; grid-template-columns:1fr 1fr; gap:0 36px; max-width:900px; margin:0 auto;}
.two > div{padding:0 4px;}
.two h3, .one h3{font-family:'Playfair Display',Georgia,serif; font-size:12.5px;
  letter-spacing:.09em; text-transform:uppercase; color:var(--gold-deep);
  font-weight:700; margin:0 0 10px;}
.two ul, .one ul{list-style:none; margin:0; padding:0; font-size:14.5px;}
.two li, .one li{padding:7px 0 7px 18px; border-bottom:1px dotted var(--rule); position:relative;}
.two li:before, .one li:before{content:"\\2022"; color:var(--gold-line); position:absolute; left:2px;}
.two li:last-child, .one li:last-child{border-bottom:none;}
@media (max-width:700px){ .two{grid-template-columns:1fr;} .two > div + div{margin-top:26px;} }
.one{max-width:760px; margin:0 auto;}

.subgrid{display:grid; grid-template-columns:repeat(3,1fr); gap:24px; max-width:900px;
  margin:30px auto 0;}
.subgrid > div{background:var(--card); border:1px solid var(--rule); border-radius:8px;
  padding:20px 22px;}
.subgrid p{margin:0; font-size:14px; color:var(--muted);}
@media (max-width:760px){ .subgrid{grid-template-columns:1fr;} }

.am-block{margin:42px 0 0; padding-top:36px; border-top:1px solid var(--rule);}
.am-block.am-solo{margin:0; padding-top:0; border-top:none;}
.am-block h2.st{margin-bottom:8px;}
.am-note{text-align:center; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted-2); margin:18px 0 0;}
.am-grid{display:grid; grid-template-columns:repeat(3,1fr); gap:16px; max-width:1000px;
  margin:0 auto;}
.am-card{background:var(--card); border:1px solid var(--rule); border-radius:10px;
  border-top:3px solid var(--gold-deep); padding:20px 22px;}
.am-card h3{font-size:10.5px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--gold-deep); margin:0 0 12px; font-weight:700;}
.am-row{display:flex; justify-content:space-between; align-items:baseline; gap:12px;
  padding:7px 0; border-top:1px solid var(--rule);}
.am-row:first-of-type{border-top:none; padding-top:0;}
.am-n{font-family:'Playfair Display',Georgia,serif; font-size:15px; font-weight:700;
  line-height:1.25;}
.am-s{display:block; font-family:'Lora',Georgia,serif; font-size:11.5px; font-weight:400;
  color:var(--muted); margin-top:1px;}
.am-d{flex:none; font-size:12px; font-weight:700; color:var(--gold-deep); white-space:nowrap;}
@media (max-width:820px){ .am-grid{grid-template-columns:1fr;} }


/* ---- walk to ---- */
.wt-grid{display:grid; grid-template-columns:repeat(5,1fr); gap:14px; max-width:980px;
  margin:0 auto;}
.wt{background:var(--card); border:1px solid var(--rule); border-radius:10px;
  padding:20px 12px 16px; text-align:center;
  display:flex; flex-direction:column; align-items:center;}
.wt-mark{width:52px; height:52px; border-radius:50%; background:var(--banner);
  border:1px solid var(--gold-line); display:flex; align-items:center; justify-content:center;
  color:var(--gold-deep); margin-bottom:12px; overflow:hidden; flex:none;}
.wt-mark svg{width:25px; height:25px;}
.wt-mark img{width:100%; height:100%; object-fit:contain; padding:7px; box-sizing:border-box;}
.wt-t{font-family:'Playfair Display',Georgia,serif; font-size:15px; font-weight:700;
  line-height:1.25;}
.wt-n{font-size:11.5px; color:var(--muted); margin-top:4px; line-height:1.35;}
.wt-m{font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; font-weight:700;
  color:var(--gold-deep); margin-top:auto; padding-top:10px;}
@media (max-width:900px){ .wt-grid{grid-template-columns:repeat(3,1fr);} }

/* ---- production band ---- */
.pr-grid{display:grid; grid-template-columns:repeat(6,1fr); gap:10px;
  max-width:940px; margin:0 auto;}
.pr-t{background:var(--card); border:1px solid var(--rule);
  border-top:3px solid var(--gold-deep); border-radius:8px;
  padding:16px 10px 14px; text-align:center;}
.pr-t .n{font-family:'Playfair Display',Georgia,serif; font-size:21px;
  font-weight:700; color:var(--gold-deep); display:block; line-height:1.15;}
.pr-t .l{font-size:10.5px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); margin-top:5px; line-height:1.35;}
@media (max-width:860px){ .pr-grid{grid-template-columns:repeat(3,1fr);} }
@media (max-width:480px){ .pr-grid{grid-template-columns:repeat(2,1fr);} }

@media (max-width:560px){ .wt-grid{grid-template-columns:repeat(2,1fr);} }

/* ---- city press ---- */
.press{max-width:720px; margin:0 auto; background:var(--card);
  border:1px solid var(--rule); border-top:3px solid var(--gold-deep);
  border-radius:10px; padding:26px 28px; text-align:center;
  box-shadow:0 2px 8px rgba(60,45,10,.05);}
.press .pk{font-size:10.5px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--gold-deep); font-weight:700;}
.press .ph{font-family:'Playfair Display',Georgia,serif; font-size:26px;
  font-weight:700; margin:12px 0 0; line-height:1.3; max-width:620px;
  margin-left:auto; margin-right:auto; text-wrap:balance;}
.press .pub{font-family:'Lora',Georgia,serif; font-style:italic; font-size:15px;
  color:var(--muted); margin:10px 0 0; line-height:1.5;}
.press .pub::before{content:"— ";}
.press .pn{font-size:13.5px; color:var(--muted); margin:10px 0 0; line-height:1.65;}
.press a.pl{display:inline-block; margin-top:18px; font-size:12.5px; font-weight:700;
  letter-spacing:.07em; text-transform:uppercase; color:var(--gold-deep);
  text-decoration:none; border:1px solid var(--gold-line); border-radius:4px;
  padding:10px 24px; background:var(--bg);}
.press a.pl:hover{background:var(--banner);}
@media print{ .press a.pl{border:none; padding:0; background:none;
  text-decoration:underline;} }

/* ---- documents ---- */
.docs{display:grid; grid-template-columns:repeat(2,1fr); gap:14px; max-width:900px; margin:0 auto;}
.doc{display:flex; align-items:center; gap:14px; background:var(--card);
  border:1px solid var(--rule); border-left:4px solid var(--gold-deep); border-radius:8px;
  padding:16px 18px; text-decoration:none; color:inherit;
  box-shadow:0 2px 8px rgba(60,45,10,.05);}
.doc:hover{border-color:var(--gold-line); border-left-color:var(--gold-deep);
  box-shadow:0 5px 16px rgba(60,45,10,.11);}
.doc svg{flex:none; color:var(--gold-deep);}
.doc .t{font-family:'Playfair Display',Georgia,serif; font-weight:700; font-size:16px;}
.doc .d{font-size:12.5px; color:var(--muted); margin-top:2px;}
@media (max-width:700px){ .docs{grid-template-columns:1fr;} }

/* ---- offer terms ---- */
.terms{max-width:780px; margin:0 auto; border:1px solid var(--rule); border-radius:8px;
  overflow:hidden; background:var(--card);}
.terms .row{display:flex; gap:0; border-bottom:1px solid var(--rule); font-size:14px;}
.terms .row:last-child{border-bottom:none;}
.terms .row:nth-child(even){background:#FBF8F1;}
.terms .k{flex:0 0 220px; padding:11px 18px; font-weight:700; color:var(--muted);
  font-size:12px; letter-spacing:.04em; text-transform:uppercase;
  border-right:1px solid var(--rule);}
.terms .v{padding:11px 18px;}
@media (max-width:620px){ .terms .row{flex-direction:column;} .terms .k{flex:none; border-right:none; padding-bottom:0;} }
.chips{display:flex; flex-wrap:wrap; gap:8px; justify-content:center; max-width:780px;
  margin:22px auto 0;}
.chip{background:var(--banner); border:1px solid var(--gold-line); border-radius:14px;
  padding:5px 14px; font-size:12.5px; color:var(--gold-deep); font-weight:600;}

/* ---- caseysamson.com site header ----
   Black, carrying a little transparency so the cream page warms it slightly
   rather than printing as flat #000. Everything is centred on the page axis:
   the utility line, then the seal and wordmark, then the nav. The side
   padding is symmetric (the QR column is reserved on BOTH sides) so centred
   really is centred and the nav can never run under the code. */
.site-bar{background:var(--sh-black); color:#CFC7B6; text-align:center;
  font-size:12.5px; letter-spacing:.04em; padding:7px 22px;}
.site-bar a{color:#CFC7B6; text-decoration:none;}
.site-bar a:hover{color:#E4D5A8;}
.site-bar .sb-sep{margin:0 10px; color:#6A6253;}
.site-head{background:var(--sh-black); display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:13px;
  padding:16px var(--sh-gutter); text-align:center;}
.site-head .sh-logo{display:flex; align-items:center; justify-content:center;
  gap:11px; flex:none; text-decoration:none;}
.site-head .sh-logo img{width:38px; height:auto; display:block;}
.site-head .sh-logo span{font-family:'Playfair Display',Georgia,serif;
  font-size:15px; font-weight:700; letter-spacing:.16em; text-transform:uppercase;
  color:#E8DFC9; white-space:nowrap;}
.site-head .sh-nav{display:flex; flex-wrap:wrap; justify-content:center;
  gap:4px 20px;}
.site-head .sh-nav a{color:#CFC7B6; text-decoration:none; font-size:12.5px;
  font-weight:600; letter-spacing:.06em; text-transform:uppercase;
  padding:4px 0; border-bottom:1px solid transparent;}
.site-head .sh-nav a:hover{color:#fff; border-bottom-color:var(--gold);}
/* Casey, 21 Nov 2026: replaces The Nightmare Before Christmas; same size as
   The Casey Samson Team letters. */
.site-head .sh-guide{font-family:'Playfair Display',Georgia,serif;
  font-size:15px; font-weight:700; letter-spacing:.16em; text-transform:uppercase;
  color:#E8DFC9; text-decoration:none; border-bottom:1px solid var(--gold); padding-bottom:2px;}
.site-head .sh-guide:hover{color:#fff;}
@media (max-width:900px){
  .site-head{gap:11px; padding:12px 96px;}
  .site-head .sh-nav{gap:2px 14px;}
  .site-head .sh-nav a{font-size:11px; letter-spacing:.04em;}
  .site-head .sh-logo span{font-size:13px; letter-spacing:.1em;}
  .site-head .sh-guide{font-size:13px; letter-spacing:.1em;}
  .site-bar{padding:6px 14px; font-size:11.5px;}
}
@media print{ .site-bar, .site-head{display:none;} }

/* ---- locator map ---- */
.locmap{position:relative; max-width:1000px; margin:0 auto; border-radius:10px;
  overflow:hidden; border:1px solid var(--gold-line);}
#locmap{height:560px; width:100%; background:#EAE7DF; z-index:1;}
.locmap .leaflet-container{font-family:Georgia,serif; background:#EAE7DF;}
.locmap .mk{background:none; border:none;}
.locmap .mk .mk-num{display:flex; align-items:center; justify-content:center;
  width:26px; height:26px; border-radius:50%; background:var(--gold-deep);
  color:#fff; font-size:13px; font-weight:700; border:2.5px solid #fff;
  box-shadow:0 1px 5px rgba(0,0,0,.4); font-family:Georgia,serif;}
.locmap .mk-home .mk-dot{display:block; width:20px; height:20px; border-radius:50%;
  background:#B3261E; border:3px solid #fff; box-shadow:0 1px 6px rgba(0,0,0,.45);}
.locmap .mk-home .mk-lab{position:absolute; left:27px; top:-1px; white-space:nowrap;
  font-size:13.5px; font-weight:700; color:#2B2622; background:rgba(255,253,248,.92);
  border-radius:3px; padding:2px 7px; box-shadow:0 1px 4px rgba(0,0,0,.18);}
/* arrows for everything beyond the frame */
.locmap-arrows{position:absolute; inset:0; z-index:500; pointer-events:none;}
.locmap-arrows .lma{position:absolute; transform:translate(-50%,-50%);
  display:flex; align-items:center; gap:8px; background:rgba(255,253,248,.94);
  border:1px solid var(--gold-line); border-radius:22px; padding:6px 13px;
  box-shadow:0 2px 9px rgba(60,45,10,.2);}
.locmap-arrows .lma-ar{display:block; width:17px; height:17px; color:var(--gold-deep);}
.locmap-arrows .lma-ar svg{width:17px; height:17px; display:block;}
.locmap-arrows .lma-tx{display:flex; flex-direction:column; line-height:1.25;}
.locmap-arrows .lma-tx b{font-size:12.5px; color:#2B2622; white-space:nowrap;}
.locmap-arrows .lma-tx i{font-size:11px; font-style:normal; color:var(--muted);
  white-space:nowrap;}
/* numbered key under the map */
.locmap-key{list-style:none; max-width:1000px; margin:16px auto 0; padding:0;
  display:grid; grid-template-columns:repeat(3,1fr); gap:9px 26px;}
.locmap-key li{display:flex; align-items:baseline; gap:9px; font-size:13.5px;}
.locmap-key .k-n{flex:none; width:21px; height:21px; border-radius:50%;
  background:var(--gold-deep); color:#fff; font-size:11.5px; font-weight:700;
  display:flex; align-items:center; justify-content:center; transform:translateY(3px);}
.locmap-key .k-t{flex:1 1 auto; display:flex; flex-direction:column;}
.locmap-key .k-t i{font-style:normal; font-size:11.5px; color:var(--muted);}
.locmap-key .k-m{flex:none; font-size:12px; font-weight:700; color:var(--gold-deep);}
.locmap-note{text-align:center; font-size:11.5px; letter-spacing:.07em;
  text-transform:uppercase; color:var(--muted-2); margin:14px 0 0;}
@media (max-width:860px){ .locmap-key{grid-template-columns:repeat(2,1fr);} }
@media (max-width:560px){ #locmap{height:400px;}
  .locmap-key{grid-template-columns:1fr;}
  .locmap-arrows .lma{padding:4px 9px;}
  .locmap-arrows .lma-tx b{font-size:11px;}
  .locmap-arrows .lma-tx i{font-size:10px;} }

/* ---- scan-to-view QR, lower right of the site header ---- */
.hero-qr{position:absolute; right:22px; top:50%; transform:translateY(-50%);
  z-index:4; text-align:center; width:112px;}
.hero-qr .hqr-tile{width:112px; height:112px; background:#fff; border-radius:5px;
  padding:6px; box-sizing:border-box; box-shadow:0 2px 10px rgba(0,0,0,.28);}
.hero-qr .hqr-tile svg{width:100%; height:100%; display:block;
  shape-rendering:crispEdges;}
.hero-qr .hqr-cap{margin-top:5px; font-size:8.5px; font-weight:700;
  letter-spacing:.12em; text-transform:uppercase; color:#CFC7B6;}
/* The header is tall enough that the 112px tile sits inside the bar rather
   than hanging over the hero photo -- 112px is the floor at which this URL
   still scans. The gutter is reserved on both sides, so the code sits in the
   right-hand one without pulling the centred content off axis. */
.site-head{position:relative; min-height:146px; box-sizing:border-box;}
/* ---- Buyer Pricing Report, mirroring the QR in the left-hand gutter ---- */
.hero-pdf{position:absolute; left:22px; top:50%; transform:translateY(-50%);
  z-index:4; text-align:center; width:112px; text-decoration:none;
  display:block;}
.hero-pdf .hpdf-tile{display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:5px; width:112px; height:112px; background:#fff;
  border-radius:5px; padding:6px; box-sizing:border-box;
  box-shadow:0 2px 10px rgba(0,0,0,.28); color:var(--gold-deep);
  transition:background .15s, color .15s, box-shadow .15s;}
.hero-pdf .hpdf-tile svg{width:34px; height:34px; display:block;}
.hero-pdf .hpdf-t{font-family:'Playfair Display',Georgia,serif; font-size:13px;
  font-weight:700; line-height:1.1; letter-spacing:.01em;}
.hero-pdf .hpdf-cap{display:block; margin-top:5px; font-size:8.5px;
  font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  color:#CFC7B6;}
.hero-pdf:hover .hpdf-tile{background:var(--gold-deep); color:#FFFDF7;
  box-shadow:0 5px 18px rgba(0,0,0,.4);}
@media (max-width:900px){
  .site-head{min-height:96px;}
  .hero-qr{right:12px; width:74px;}
  .hero-qr .hqr-tile{width:74px; height:74px; padding:4px;}
  .hero-qr .hqr-cap{display:none;}
  .hero-pdf{left:12px; width:74px;}
  .hero-pdf .hpdf-tile{width:74px; height:74px; padding:4px; gap:3px;}
  .hero-pdf .hpdf-tile svg{width:22px; height:22px;}
  .hero-pdf .hpdf-t{font-size:10px;}
  .hero-pdf .hpdf-cap{display:none;}
}

/* ---- contact ---- */
.contact{display:flex; align-items:center; gap:30px; max-width:840px; margin:0 auto;
  background:var(--card); border:1px solid var(--gold-line); border-radius:10px;
  padding:26px 30px; box-shadow:0 6px 20px rgba(60,45,10,.08);}
.contact img{width:190px; border-radius:8px; flex:none; display:block;}
.contact .nm{font-family:'Playfair Display',Georgia,serif; font-size:23px; font-weight:700;
  margin:0 0 2px;}
.contact .tm{font-size:12.5px; letter-spacing:.08em; text-transform:uppercase;
  color:var(--gold-deep); font-weight:700; margin-bottom:14px;}
.contact .ln{font-size:14.5px; margin-bottom:4px;}
.contact .ln b{display:inline-block; min-width:128px;}
.contact a{color:inherit;}
.contact .office{font-size:12.5px; color:var(--muted); margin-top:12px;}
/* No agent photo: nothing to sit beside, so the card centres on itself and
   each agent gets their name over their own number. */
.contact.solo{flex-direction:column; text-align:center; max-width:620px;}
.contact.solo .ln{margin-bottom:9px;}
.contact.solo .ln b{display:block; min-width:0; margin-bottom:1px;}
@media (max-width:700px){ .contact{flex-direction:column; text-align:center;}
  .contact .ln b{display:block; min-width:0;} }

footer{text-align:center; padding:36px 0 50px; background:var(--banner);
  border-top:1px solid var(--gold-line);}
footer .produced{font-weight:700; font-size:14.5px; margin-bottom:4px;}
footer .contact-line{font-weight:700; font-size:13.5px;}
footer .contact-line a{color:inherit; text-decoration:none;}
footer .contact-line .sep{font-weight:400; color:var(--muted-2); margin:0 8px;}
footer .contact-line + .contact-line{margin-top:3px;}
footer .foot-office{font-size:12px; color:var(--muted); margin-top:9px;}
footer .copy{font-size:11.5px; color:var(--muted); margin-top:14px; max-width:720px;
  margin-left:auto; margin-right:auto; line-height:1.7;}

/* ---- authenticated values ---- */
.tablewrap{max-width:860px; margin:0 auto 28px; overflow-x:auto;
  border:1px solid var(--rule); border-radius:6px; background:var(--card);}
table.comps{width:100%; border-collapse:collapse; font-size:13.5px; min-width:560px;}
table.comps thead th{background:var(--banner); text-align:center; font-weight:600;
  font-size:10.5px; letter-spacing:.04em; text-transform:uppercase; color:var(--muted);
  padding:11px 12px; border-bottom:1px solid var(--gold-line);}
table.comps tbody td{padding:10px 12px; border-bottom:1px solid var(--rule);
  text-align:center; font-variant-numeric:tabular-nums;}
table.comps tbody tr:nth-child(even){background:#FBF8F1;}
table.comps tbody tr:last-child td{border-bottom:none;}
table.comps tbody tr.total-row td{font-weight:700; background:var(--banner);}
table.comps td.addr-cell{text-align:left; font-weight:600;}
.values-grid{display:grid; grid-template-columns:repeat(2,1fr); gap:24px;
  max-width:640px; margin:0 auto;}
@media (max-width:560px){.values-grid{grid-template-columns:1fr;}}
.value-card{background:var(--card); border:1px solid var(--rule); border-radius:8px;
  padding:24px 20px; text-align:center;}
.value-card h3{font-size:13px; font-weight:700; letter-spacing:.04em;
  text-transform:uppercase; color:var(--muted); margin:0 0 10px;}
.value-num{font-family:'Playfair Display',Georgia,serif; font-size:30px; font-weight:700;
  color:var(--gold-deep); margin-bottom:14px;}
.value-card ul{text-align:left; font-size:12.5px; color:var(--muted); margin:0; padding-left:18px;}
.value-card li{margin-bottom:6px;}
.value-print{text-align:center; margin:26px 0 0;}
.pdf-btn{display:inline-grid; grid-template-columns:auto 1fr;
  grid-template-rows:auto auto; column-gap:11px; row-gap:2px;
  align-items:center; text-align:left; max-width:420px;
  padding:14px 24px; border:1.5px solid var(--gold-deep); border-radius:10px;
  background:var(--banner); color:var(--gold-deep); text-decoration:none;
  box-shadow:0 2px 10px rgba(60,45,10,.07);
  transition:background .15s, color .15s, box-shadow .15s;}
.pdf-btn svg{grid-row:1 / span 2; flex:none;}
.pdf-btn-t{font-family:'Playfair Display',Georgia,serif; font-size:16px;
  font-weight:700; line-height:1.15;}
.pdf-btn-s{font-size:12px; line-height:1.35; color:var(--muted);}
.pdf-btn:hover{background:var(--gold-deep); color:#FFFDF7;
  box-shadow:0 7px 20px rgba(60,45,10,.16);}
.pdf-btn:hover .pdf-btn-s{color:rgba(255,253,247,.82);}
@media (max-width:520px){ .pdf-btn{padding:12px 16px;} }
.value-basis{margin:6px 0 0; font-size:11.5px; font-weight:700;
  letter-spacing:.05em; text-transform:uppercase; color:var(--gold-deep);}
.value-foot{max-width:700px; margin:26px auto 0; text-align:center; font-size:14px;
  color:var(--muted-2); font-style:italic;}
"""

PDF_ICON = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.7"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
            '<path d="M14 2v6h6"/></svg>')
WEB_ICON = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
            '<path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z"/></svg>')


# Category marks for the Walk To tiles. These are generic glyphs, not any
# business's logo: a fork, a cup, a book. A place can carry its own image
# instead by giving a "logo" filename in the walk_to entry, which the tile
# then shows in place of the glyph.
def _wt(path, extra=""):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{path}{extra}</svg>')


WALK_ICONS = {
    "dining": _wt('<path d="M6 3v7a2 2 0 0 0 2 2 2 2 0 0 0 2-2V3"/><path d="M8 12v9"/>'
                  '<path d="M17 3c-1.7 1.2-2.5 3-2.5 5.2 0 1.7.8 2.8 2.5 2.8"/><path d="M17 11v10"/>'),
    "coffee": _wt('<path d="M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/>'
                  '<path d="M17 9h1.6a2.4 2.4 0 0 1 0 4.8H17"/><path d="M7 2v3"/><path d="M11 2v3"/>'),
    "grocery": _wt('<path d="M3 7h18l-1.7 11.2a2 2 0 0 1-2 1.8H6.7a2 2 0 0 1-2-1.8z"/>'
                   '<path d="M8.5 7 12 2l3.5 5"/><path d="M9.5 11.5v4"/><path d="M14.5 11.5v4"/>'),
    "books": _wt('<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H19v15H5.5A1.5 1.5 0 0 0 4 19.5z"/>'
                 '<path d="M4 19.5A1.5 1.5 0 0 1 5.5 21H19"/><path d="M9 7h6"/>'),
    "mail": _wt('<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.6 6.8 8.4 6 8.4-6"/>'),
    "park": _wt('<path d="M12 3 5.5 14h13z"/><path d="M12 8.5 7.5 16h9z"/><path d="M12 16v5"/>'),
    "trail": _wt('<circle cx="5.5" cy="17" r="3"/><circle cx="18.5" cy="17" r="3"/>'
                 '<path d="M8 17h4l4-7"/><path d="M14 10h4"/><path d="M12 17 9.5 9.5H7"/>'),
    "civic": _wt('<path d="M3 21h18"/><path d="M4.5 21V9.5L12 4l7.5 5.5V21"/>'
                 '<path d="M9.5 21v-6h5v6"/>'),
}


AMENITIES_NOTE = "Typical drive times in normal traffic."

# Distance is what the data carries; time is what a buyer thinks in. The
# conversion is by road type, because a mile of Maple Avenue and a mile of
# the Dulles Toll Road are not the same mile:
#   under 1.5 mi   town streets and lights        ~20 mph
#   1.5 to 5 mi    suburban arterials             ~25 mph
#   5 to 25 mi     toll road and interstate       ~35 mph
#   over 25 mi     long interstate run            ~45 mph
SITE_NAV = [
    ("Home", "https://caseysamson.com/"),
    ("Preview", "https://caseysamson.com/portfolio/coming-soon-to-coming-soon/"),
    ("Introduction", "https://caseysamson.com/introduction-new/"),
    ("Buyers", "https://caseysamson.com/buying/"),
    ("Sellers", "https://caseysamson.com/listing-with-our-team/"),
    ("Market Snapshot", "https://cstmarketupdate.netlify.app/"),
    ("Blog", "https://caseysamson.com/category/blog/"),
    ("Portfolio", "https://caseysamson.com/portfolio/"),
    ("Real Housed", "https://caseysamson.com/podcast/real-housed/"),
]
SITE_PHONE = "703.508.2535"
SITE_EMAIL = "Casey@caseysamson.com"


def hero_pdf_tile(b):
    """The Buyer Pricing Report, as a tile mirroring the QR in the header.

    Casey, 12 Oct 2026: "on the buyer portal put white box same size and same
    position as QR code on upper left that is a link to Buyer pricing report."
    The right-hand gutter of the header holds the scan-to-view QR; the left
    gutter was empty. Same 112px white tile, same vertical centring, so the
    two read as a pair.
    """
    pdf = b.get("pricing_pdf")
    if not pdf:
        note("Header Buyer Pricing Report tile OMITTED — no pricing_pdf on "
             "the buyer_portal block.")
        return ""
    return (
        f'  <a class="hero-pdf" href="{pdf}" target="_blank" rel="noopener">\n'
        '    <span class="hpdf-tile">'
        '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" '
        'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M29 5H13a4 4 0 0 0-4 4v30a4 4 0 0 0 4 4h22a4 4 0 0 0 '
        '4-4V15z"/><polyline points="29 5 29 15 39 15"/>'
        '<line x1="24" y1="36" x2="24" y2="23"/>'
        '<polyline points="18 30 24 36 30 30"/></svg>'
        '<span class="hpdf-t">Pricing<br>Report</span></span>\n'
        '    <span class="hpdf-cap">Open the PDF</span>\n  </a>\n')


def site_header(qr="", pdf="", guide=""):
    """The caseysamson.com header, rebuilt above the property hero so a buyer
    landing on a listing site is plainly on a Casey Samson Team page: black
    utility bar with the phone and email, then the seal and the site nav."""
    nav = "".join(
        f'<a href="{href}" target="_blank" rel="noopener">{txt}</a>'
        for txt, href in SITE_NAV)
    return (
        '<div class="site-bar">\n'
        f'  <a href="tel:+1.{SITE_PHONE}">{SITE_PHONE}</a>'
        '<span class="sb-sep">&middot;</span>'
        f'<a href="mailto:{SITE_EMAIL}">{SITE_EMAIL}</a>\n'
        '</div>\n'
        '<header class="site-head">\n'
        '  <a class="sh-logo" href="https://caseysamson.com/" target="_blank" '
        'rel="noopener">'
        '<img src="Gold_Standard_Logo.png" alt="The Casey Samson Team">'
        '<span>The Casey Samson Team</span></a>\n'
        f'  <nav class="sh-nav">{nav}</nav>\n'
        # Casey, 24 Nov 2026: the guide link comes out of the header -- the
        # section links run throughout the page.
        + '' +
        f'{pdf}{qr}'
        '</header>\n')


def apply_sponsor(html, sp, out):
    """Put the portal under a sponsor's name.

    Casey, 22 Oct 2026, on 6700 Clifton: "make it look like it is from
    Atlantic Coastal" -- "they are sponsoring us to provide it for their
    realtor." The sponsor takes the top bar, the header and the hero seal;
    the listing agent and listing brokerage stay exactly where they were
    (the listing has to be advertised under its own brokerage), and the
    footer says who prepared it. On the property file, buyer_portal block:

        "sponsor": {
          "name": "Atlantic Coast Mortgage",
          "tagline": "Presented by",             -- optional
          "logo": "assets/.../logo.png",         -- optional, else a wordmark
          "phone": "...", "email": "...", "website": "https://...",
          "contact": "Loan officer name",        -- optional
          "color": "#0B3A63", "accent": "#C8A24A" -- optional
        }
    """
    import html as _h
    tag = sp.get("tagline") or "Presented by"
    color = sp.get("color") or "#14365C"
    accent = sp.get("accent") or "#C9A54B"
    # Casey, 23 Oct 2026: "add cardinal title as a sponsor make Atlantic
    # Coastal larger" -- the lead sponsor's mark is the big one; any
    # "co_sponsors" sit beside it, smaller.
    def _mark(s_, h, idx):
        nm = _h.escape(s_["name"])
        img = ""
        lg = s_.get("logo") or ""
        sty = (f'style="height:{h}px;width:auto;display:block;background:#fff;'
               f'padding:{max(6, h//8)}px {max(12, h//4)}px;border-radius:8px;"')
        if lg.startswith("http"):
            img = f'<img src="{lg}" alt="{nm}" {sty}>'
            note(f"Sponsor: {s_['name']} logo loads from their website -- attach "
                 "the file to make the portal self-contained.")
        elif lg:
            src = HERE / lg
            if src.exists():
                dst = f"sponsor_logo{idx or ''}{src.suffix}"
                shutil.copy(src, out / dst)
                # Every sponsor gets the same white box. A wide wordmark
                # (CrossCountry's is 6.6:1) is set shorter inside it so the
                # boxes match and the art is not stretched past its pixels.
                try:
                    from PIL import Image as _I
                    _w, _hh = _I.open(src).size
                except Exception:          # noqa: BLE001
                    _w, _hh = 1, 1
                ih = h if _w / max(_hh, 1) < 4 else round(h * 0.55)
                vp = max(6, h // 8) + (h - ih) // 2
                img = (f'<img src="{dst}" alt="{nm}" style="height:{ih}px;width:auto;'
                       f'display:block;background:#fff;padding:{vp}px {max(12, h//4)}px;'
                       'border-radius:8px;box-sizing:content-box;">')
            else:
                note(f"Sponsor: logo {lg} not found -- using a wordmark.")
        else:
            note(f"Sponsor: no logo on file for {s_['name']} -- using a wordmark.")
        if not img:
            img = (f'<span style="font-family:Playfair Display,Georgia,serif;'
                   f'font-size:{round(h*0.4)}px;font-weight:700;letter-spacing:.12em;'
                   f'text-transform:uppercase;color:#fff;white-space:nowrap;">{nm}</span>')
        if s_.get("website"):
            img = (f'<a href="{s_["website"]}" target="_blank" rel="noopener" '
                   f'style="text-decoration:none;">{img}</a>')
        return img
    cos = sp.get("co_sponsors") or []
    mark = _mark(sp, 64, 0)
    if cos:
        mark = (f'<div style="display:flex;align-items:center;justify-content:center;'
                f'flex-wrap:wrap;gap:14px 26px;">{mark}'
                + "".join(_mark(c, 64, i + 1) for i, c in enumerate(cos)) + "</div>")
    names = [sp["name"]] + [c["name"] for c in cos]
    name = (" and ".join(names) if len(names) < 3
            else ", ".join(names[:-1]) + " and " + names[-1])
    bits = [x for x in (sp.get("contact"),
                        f'<a href="tel:{re.sub(r"[^0-9+]", "", sp["phone"])}">{sp["phone"]}</a>' if sp.get("phone") else "",
                        f'<a href="mailto:{sp["email"]}">{sp["email"]}</a>' if sp.get("email") else "",
                        (f'<a href="{sp["map"]}" target="_blank" rel="noopener">{_h.escape(sp["address"])}</a>'
                         if sp.get("map") else _h.escape(sp["address"])) if sp.get("address") else "") if x]
    if sp.get("bar_label"):
        bits.insert(0, f'<b style="letter-spacing:.14em;text-transform:uppercase;font-size:11px;">'
                       f'{_h.escape(sp["bar_label"])}</b>')
    bar = ('<div class="site-bar">' + ('<span class="sb-sep">&middot;</span>'.join(bits)
                                       if bits else f'{tag} {_h.escape(name)}') + '</div>\n')
    head_re = re.compile(r'<div class="site-bar">.*?</header>\n', re.S)
    m = head_re.search(html)
    if not m:
        note("Sponsor: site header not found -- sponsor header not applied.")
        return html
    old = m.group(0)
    # The Pricing Report tile and the QR sit after the nav; they stay.
    tail = old.split("</nav>", 1)[-1].replace("</header>\n", "") if "</nav>" in old else ""
    head = (bar + '<header class="site-head sponsor-head">\n'
            f'  <div class="sp-tag">{tag}</div>\n  <div class="sp-mark">{mark}</div>\n'
            f'{tail}</header>\n')
    html = html.replace(old, head, 1)
    css = (f'<style>.site-bar,.site-head.sponsor-head{{background:{color};}}'
           f'.site-bar a{{color:#fff;}}'
           f'.sponsor-head{{flex-direction:column;align-items:center;gap:6px;}}'
           f'.sponsor-head .sp-tag{{font-size:11px;letter-spacing:.24em;text-transform:uppercase;'
           f'color:{accent};font-weight:700;}}'
           f':root{{--gold:{accent};--gold-deep:{color};--gold-line:{accent};}}</style>')
    html = html.replace("</head>", css + "</head>", 1)
    # Hero: the sponsor's mark in place of the team seal.
    html = html.replace(
        '<img class="seal" src="Gold_Standard_Logo.png" alt="The Casey Samson Team">\n'
        '    <div class="brandline">The Casey Samson Team</div>',
        f'<div class="brandline">{tag} {_h.escape(name)}</div>', 1)
    # Casey, 22 Oct 2026: "This is a sponsored buyer portal. Remove CASEY
    # SAMSON team stats and info. Leave Copyright." -- the team band, the
    # team name in the title, description and disclaimer all go; only the
    # copyright line keeps the team's name.
    html = html.replace(
        '<div class="produced">The Casey Samson Team</div>',
        f'<div class="produced">{tag} {_h.escape(name)}</div>', 1)
    html = re.sub(r'<section><div class="wrap"><h2 class="st">The Casey Samson Team</h2>.*?</section>\n?',
                  "", html, count=1, flags=re.S)
    html = html.replace("&mdash; The Casey Samson Team</title>",
                        f"&mdash; {tag} {_h.escape(name)}</title>", 1)
    html = html.replace("offered by The Casey Samson Team.",
                        f"{tag} {_h.escape(name)}.", 1)
    # Casey, 24 Oct 2026, on 502 MacArthur: "Add this to the bottom of the
    # buyer portal: Sponsored by Mike Filan ..." -- a sponsor card above the
    # footer, his lines word for word. buyer_portal.sponsor.sponsored_by:
    #   {"heading": "Sponsored by", "name": "...", "title": "...",
    #    "lines": [["M", "703.899.8720"], ["W", "mikefilanteam.com"], ...]}
    sb = sp.get("sponsored_by")
    if sb:
        def _val(k, v):
            e = _h.escape(v)
            if k in ("M", "D", "P", "O"):
                return f'<a href="tel:{re.sub(r"[^0-9]", "", v)}">{e}</a>'
            if k == "E":
                return f'<a href="mailto:{v}">{e}</a>'
            if k == "W":
                return f'<a href="https://{v.split("://")[-1]}" target="_blank" rel="noopener">{e}</a>'
            return e
        rows = "".join(f'<div class="sb-l"><b>{_h.escape(k)}</b> {_val(k, v)}</div>'
                       for k, v in sb.get("lines", []))
        card = ('<section class="sb-card"><div class="wrap">'
                f'<div class="sb-h">{_h.escape(sb.get("heading") or "Sponsored by")}</div>'
                f'<div class="sb-n">{_h.escape(sb["name"])}</div>'
                + (f'<div class="sb-t">{_h.escape(sb["title"])}</div>' if sb.get("title") else "")
                + f'<div class="sb-ls">{rows}</div></div></section>\n')
        html = html.replace("<footer>", card + "<footer>", 1)
        html = html.replace("</head>", (
            '<style>.sb-card{text-align:center;padding:34px 0 30px;border-top:1px solid var(--rule);}'
            '.sb-h{font-size:11.5px;letter-spacing:.22em;text-transform:uppercase;font-weight:700;'
            'color:var(--gold-deep);margin-bottom:8px;}'
            '.sb-n{font-family:"Playfair Display",Georgia,serif;font-size:24px;font-weight:700;}'
            '.sb-t{font-size:14px;color:var(--muted);margin-top:2px;}'
            '.sb-ls{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 22px;margin-top:14px;font-size:14.5px;}'
            '.sb-l b{color:var(--gold-deep);margin-right:4px;}'
            '.sb-l a{color:inherit;text-decoration:none;border-bottom:1px solid var(--gold-line);}'
            '</style></head>'), 1)
    html = html.replace("provided by the seller to The Casey Samson Team and",
                        "provided by the seller and", 1)
    # The listing team's own name and Casey's footer line are team info too;
    # the listing agents and Samson Properties stay.
    html = html.replace("The Casey Samson Team &middot; Samson Properties",
                        "Samson Properties")
    html = re.sub(r'<div class="contact-line">Casey Samson<span class="sep">.*?</div>\s*',
                  "", html, count=1, flags=re.S)
    left = [m for m in re.findall(r"Casey Samson[^<]{0,30}",
                                  re.sub(r"<script.*?</script>|<style.*?</style>", "",
                                         html, flags=re.S))
            if "LLC. All Rights" not in m]
    if left:
        note(f"Sponsor: team name still on the page: {left[:3]}")
    note(f"Sponsor: portal presented by {name}. Listing agent and brokerage unchanged.")
    return html


def partner_band(tp, out):
    """Partner logos and the contract lender, right under the header.

    Casey, 24 Oct 2026, on 2583 Vintage Crest: "Add this [Guild Mortgage]
    and cardinal to the top of Vintage crest buyer portal. Lender for
    contract is ..." The team's own header and pages are untouched -- this
    is not a sponsored portal; it only adds the partners. buyer_portal:

        "top_partners": {
          "logos": [["Guild Mortgage", "assets/sponsors/guild_mortgage_logo.png"],
                    ["Cardinal Title Group", "assets/sponsors/cardinal_title_logo.png"]],
          "lender": {"label": "Lender for contract", "name": "...",
                     "company": "Guild Mortgage", "address": "...", "map": "https://...",
                     "email": "...", "phone": "(703) 623-7857"}
        }
    """
    import html as _h
    cells = []
    for i, (nm, path) in enumerate(tp.get("logos", [])):
        src = HERE / path
        if not src.exists():
            note(f"Partner band: logo {path} not found -- {nm} left out.")
            continue
        dst = f"partner_logo{i + 1}{src.suffix}"
        shutil.copy(src, out / dst)
        try:
            from PIL import Image as _I
            w, hh = _I.open(src).size
        except Exception:                      # noqa: BLE001
            w, hh = 1, 1
        H = 56
        ih = H if w / max(hh, 1) < 4 else round(H * 0.55)
        vp = 8 + (H - ih) // 2
        cells.append(f'<img src="{dst}" alt="{_h.escape(nm)}" style="height:{ih}px;width:auto;'
                     f'display:block;background:#fff;padding:{vp}px 16px;border-radius:8px;'
                     'box-sizing:content-box;box-shadow:0 1px 6px rgba(0,0,0,.12);">')
    ld = tp.get("lender") or {}
    lend = ""
    if ld:
        bits = []
        if ld.get("name"):
            bits.append(f'<b>{_h.escape(ld["name"])}</b>')
        if ld.get("company"):
            bits.append(_h.escape(ld["company"]))
        if ld.get("address"):
            a = _h.escape(ld["address"])
            bits.append(f'<a href="{ld["map"]}" target="_blank" rel="noopener">{a}</a>'
                        if ld.get("map") else a)
        if ld.get("email"):
            bits.append(f'<a href="mailto:{ld["email"]}">{_h.escape(ld["email"])}</a>')
        if ld.get("phone"):
            bits.append(f'<a href="tel:{re.sub(r"[^0-9]", "", ld["phone"])}">{_h.escape(ld["phone"])}</a>')
        lend = (f'<div class="pb-lbl">{_h.escape(ld.get("label") or "Lender for contract")}</div>'
                f'<div class="pb-ln">{"<span class=pb-sep>&middot;</span>".join(bits)}</div>')
    return ('<style>.partner-band{background:#F1EBDA;border-bottom:1px solid var(--gold-line);'
            'padding:16px 16px 14px;text-align:center;}'
            '.partner-band .pb-logos{display:flex;flex-wrap:wrap;justify-content:center;gap:12px 22px;}'
            '.partner-band .pb-lbl{font-size:11px;letter-spacing:.22em;text-transform:uppercase;'
            'font-weight:700;color:var(--gold-deep);margin-top:12px;}'
            '.partner-band .pb-ln{font-size:14px;margin-top:4px;line-height:1.6;}'
            '.partner-band .pb-ln a{color:inherit;border-bottom:1px solid var(--gold-line);text-decoration:none;}'
            '.partner-band .pb-sep{color:var(--muted-2);margin:0 9px;}'
            '@media print{.partner-band{display:none;}}</style>\n'
            f'<div class="partner-band"><div class="pb-logos">{"".join(cells)}</div>{lend}</div>\n')


def sponsor_names(sp):
    names = [sp["name"]] + [c["name"] for c in (sp.get("co_sponsors") or [])]
    return (" and ".join(names) if len(names) < 3
            else ", ".join(names[:-1]) + " and " + names[-1])


def sponsored_report(p, b, src_pdf, out):
    """The buyer portal's own copy of the Buyer Pricing Report, under the
    sponsor's name.

    Casey, 23 Oct 2026: "On Buyer Sponsored portals just do Buyer not
    seller." The seller portal's report is left exactly as the seller
    pipeline built it; this renders a second copy, from the same HTML, for
    the buyer portal only: no team masthead, seal or team wording, no
    sample mark, print lock or clock -- the sponsor has paid for it.
    """
    import html as _h
    import expiry
    from build_portal import render_one_pdf
    sp = b["sponsor"]
    seller_out = src_pdf.parent
    src_html = src_pdf.with_suffix(".html")
    if not src_html.exists():
        shutil.copy(src_pdf, out / b["pricing_pdf"])
        note("Sponsored report: no HTML beside the seller's PDF -- copied the "
             "team version unchanged.")
        return
    t = src_html.read_text(encoding="utf-8")
    t = watermark.unstamp(t)
    t = re.sub(r'<style class="cst-nopr">.*?</style>\s*', "", t, flags=re.S)
    t = expiry.stamp(t, None)
    nm = _h.escape(sponsor_names(sp))
    tag = sp.get("tagline") or "Presented by"
    t = re.sub(r'<img src="Gold_Standard_Logo.png" alt="Gold Standard Listing">\s*'
               r'<div class="mast-team">The Casey Samson Team</div>',
               f'<div class="mast-team">{tag} {nm}</div>', t, count=1)
    t = t.replace("authenticate the Casey Samson Team value range",
                  "authenticate the value range")
    t = re.sub(r'<div class="produced">[^<]*Casey Samson Team</div>',
               f'<div class="produced">{tag} {nm}</div>', t)
    t = t.replace("The Casey Samson Team &middot; ", "").replace(
        " &middot; The Casey Samson Team", "")
    t = re.sub(r"— The Casey Samson Team</title>", f"— {tag} {nm}</title>", t)
    stem = "_sponsored_" + src_pdf.stem
    tmp = seller_out / f"{stem}.html"
    tmp.write_text(t, encoding="utf-8")
    try:
        render_one_pdf(seller_out, stem)
        shutil.move(str(seller_out / f"{stem}.pdf"), str(out / b["pricing_pdf"]))
    finally:
        tmp.unlink(missing_ok=True)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    left = [m for m in re.findall(r"Casey Samson[^<]{0,30}", body)
            if "LLC. All Rights" not in m]
    if left:
        note(f"Sponsored report: team name still shows: {left[:3]}")
    note(f"Sponsored report: {b['pricing_pdf']} rendered for the buyer portal "
         "only, under the sponsor. The seller portal's copy is unchanged.")


SITE_LISTING_BASE = "https://caseysamson.com/market-snapshot"
_STREET_TYPES = {"st","street","ave","avenue","dr","drive","ter","terrace","ct",
                 "court","rd","road","ln","lane","way","pl","place","cir",
                 "circle","blvd","boulevard","pkwy","parkway","trl","trail",
                 "loop"}
_QUADRANTS = {"ne","nw","se","sw","n","s","e","w"}


def address_slug(p):
    """9854 Lieuvin Ct -> 9854lieuvin. Street number and street name only."""
    words = re.sub(r"[^A-Za-z0-9 ]", "", p.get("address", "")).split()
    keep = [w for w in words
            if w.lower() not in _STREET_TYPES and w.lower() not in _QUADRANTS]
    return "".join(keep).lower()


def buyer_portal_url(p):
    """The Buyer Portal's own address: buy<number><street>. Properties that
    were deployed before this convention keep whatever url their file names."""
    b = p.get("buyer_portal") or {}
    if b.get("url"):
        return b["url"]
    slug = address_slug(p)
    return f"https://buy{slug}.netlify.app" if slug else None


def qr_target(p):
    """The single answer to "where does a QR code point?"

    Casey, 12 Oct 2026: "QR codes on buyer pricing print outs need to go to
    buystreetname.netlify.app" — the Netlify host, not the caseysamson.com
    path, because a printed code outlives the redirect that would make the
    pretty address work. _buyer_host() honours a deploy_to override, so a
    site published under another name still gets a code that resolves.

    An explicit qr_url on the property file still wins. Both the web portal
    and the printed Buyer Report read this, so the two cannot drift apart.
    """
    b = p.get("buyer_portal") or {}
    return (b.get("qr_url") or _buyer_host(p) or site_listing_url(p)
            or b.get("url"))


def site_listing_url(p):
    """Where this listing lives on caseysamson.com: the street number and
    street name run together, no suffix, no quadrant, lower case.
    502 MacArthur Ave NE -> /market-snapshot/502macarthur"""
    if p.get("site_listing_url"):
        return p["site_listing_url"]
    slug = address_slug(p)
    return f"{SITE_LISTING_BASE}/{slug}" if slug else None


def qr_block(b, p=None):
    """A scan-to-keep QR above the footer. The SVG is inlined rather than
    written as a file so the published page needs nothing external and the
    code survives a print to paper. segno is a build-time dependency only."""
    # The QR sends people to the listing page on caseysamson.com, not
    # to the netlify deploy target.
    url = qr_target(p) if p else (b.get("qr_url") or b.get("url"))
    if not url:
        note("Buyer portal: QR OMITTED — no url on the buyer_portal block.")
        return ""
    if segno is None:
        note("Buyer portal: QR OMITTED — segno is not installed "
             "(python3.12 -m pip install --break-system-packages segno).")
        return ""

    # Error correction M: survives a logo-free print and a phone camera at an
    # angle, without pushing the module count up the way H would.
    import io
    buf = io.BytesIO()
    segno.make(url, error="m").save(
        buf, kind="svg", scale=1, border=2, dark="#2B2622",
        svgclass=None, lineclass=None, omitsize=True, xmldecl=False, svgns=True)
    svg = buf.getvalue().decode("utf-8").strip()
    # Let CSS size it; the generator's own width/height would pin it to pixels.
    svg = re.sub(r'<svg([^>]*?)>', r'<svg\1 preserveAspectRatio="xMidYMid meet">',
                 svg, count=1)

    return (
        '  <div class="hero-qr">\n'
        f'    <div class="hqr-tile">{svg}</div>\n'
        '    <div class="hqr-cap">Scan to View</div>\n  </div>\n')


def lot_map(b, addr):
    """Casey, 23 Nov 2026: the lot from above, four ways -- satellite with lot
    lines, satellite with street names, neighborhood aerial, and a street map
    with the dimensions of each side. Lot lines come from the county parcel
    layer (approximate; the recorded plat is the official boundary)."""
    lot = b.get("lot") or {}
    poly = lot.get("polygon") or []
    if len(poly) < 3:
        return ""
    import json as _j, math as _m
    def _ft(a, c):
        la = _m.radians((a[0] + c[0]) / 2)
        dx = _m.radians(c[1] - a[1]) * 6371008.8 * _m.cos(la)
        dy = _m.radians(c[0] - a[0]) * 6371008.8
        return round(_m.hypot(dx, dy) * 3.28084)
    # Curved frontages come as many tiny segments: label the straight runs.
    # Simplify the outline (Douglas-Peucker, ~1.5 m) and label sides of 15 ft
    # or more, so a cul-de-sac curve reads as one chord, not a dozen labels.
    def _xy(q):
        la = _m.radians(poly[0][0])
        return (_m.radians(q[1]) * 6371008.8 * _m.cos(la), _m.radians(q[0]) * 6371008.8)
    def _dp(pts, tol):
        if len(pts) < 3:
            return pts
        a, c = _xy(pts[0]), _xy(pts[-1])
        dx, dy = c[0] - a[0], c[1] - a[1]
        L2 = dx * dx + dy * dy or 1e-9
        best, bi = 0, 0
        for i in range(1, len(pts) - 1):
            p_ = _xy(pts[i])
            t_ = max(0, min(1, ((p_[0] - a[0]) * dx + (p_[1] - a[1]) * dy) / L2))
            d_ = _m.hypot(p_[0] - a[0] - t_ * dx, p_[1] - a[1] - t_ * dy)
            if d_ > best:
                best, bi = d_, i
        if best <= tol:
            return [pts[0], pts[-1]]
        return _dp(pts[:bi + 1], tol)[:-1] + _dp(pts[bi:], tol)
    ring = poly + [poly[0]]
    simp = _dp(ring, 1.5)[:-1] if len(poly) > 4 else poly
    sides = []
    for i in range(len(simp)):
        a, c = simp[i], simp[(i + 1) % len(simp)]
        ft = _ft(a, c)
        if ft >= 15:
            sides.append([(a[0] + c[0]) / 2, (a[1] + c[1]) / 2, ft])
    area = lot.get("area_sf")
    note = (f'County parcel {lot["pin"]}' if lot.get("pin") else "County parcel") + (
        f', about {int(round(float(area))):,} square feet' if area else "") + (
        ". Lot lines and dimensions are approximate, from the county parcel map; "
        "the recorded plat is the official boundary.")
    D = _j.dumps({"lot": poly, "sides": sides, "label": addr})
    tabs = [("a", "Satellite"), ("b", "With street names"), ("c", "Neighborhood"), ("d", "Lot dimensions")]
    # Casey, 24 Nov 2026: "If you can identify which is the plat, replace one
    # of the maps with the plat. Leave the map with dimensions." The house
    # location plat from the county zoning file takes the Neighborhood tab.
    plat = lot.get("plat")
    plat_html = ""
    if plat:
        tabs[2] = ("p", "House Location Plat")
        src = (lot.get("plat_source") or "").strip()
        view = lot.get("plat_view") or plat   # the drawing; the link opens the whole plat
        plat_html = (f'<a href="{plat}" target="_blank" rel="noopener" title="Open the full plat">'
                     f'<img src="{view}" alt="House location plat, {addr}"></a>'
                     + (f'<div class="lot-plat-src">{src}</div>' if src else ""))
        note = note.replace("the recorded plat is the official boundary.",
                            "the recorded plat is the official boundary (see House Location Plat; click it for the full signed plat).")
    return (
        '<section class="lotsec"><div class="wrap">'
        '<h2 class="st">The Lot</h2>'
        '<p class="ss">The property from above, with the lot lines drawn in gold.</p>'
        '<div class="lot-tabs" role="tablist">'
        + "".join(f'<button type="button" role="tab" data-v="{k}"{" class=on" if i == 0 else ""}>{t}</button>'
                  for i, (k, t) in enumerate(tabs)) +
        '</div><div class="lot-frame">'
        + "".join(f'<div class="lot-map{" on" if i == 0 else ""}{" lot-plat" if k == "p" else ""}" id="lot-{k}">'
                  f'{plat_html if k == "p" else ""}</div>' for i, (k, _) in enumerate(tabs)) +
        f'</div><p class="lot-note">{note}</p></div></section>\n'
        '<style>.lotsec .lot-tabs{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:6px 0 14px}'
        '.lotsec .lot-tabs button{font:700 14px Georgia,serif;letter-spacing:.03em;padding:9px 18px;border-radius:22px;'
        'border:1px solid #B8902F;background:#FFFDF7;color:#1F2A44;cursor:pointer}'
        '.lotsec .lot-tabs button.on{background:#1F2A44;color:#E8C77A}'
        '.lotsec .lot-frame{position:relative;max-width:1000px;margin:0 auto;border-radius:10px;overflow:hidden;'
        'border:1px solid #D9CBA6;box-shadow:0 10px 28px rgba(31,42,68,.12)}'
        '.lotsec .lot-map{height:520px;display:none}.lotsec .lot-map.on{display:block}'
        '.lotsec .lot-note{text-align:center;font-size:13.5px;color:#71695A;font-style:italic;margin:12px auto 0;max-width:760px}'
        '.lotsec .lot-lbl{background:#1F2A44;color:#E8C77A;border:0;font:700 13px Georgia,serif;padding:4px 9px;border-radius:4px;box-shadow:none}'
        '.lotsec .lot-dim{background:#fff;color:#1F2A44;border:1px solid #8A6A2E;font:700 13px Georgia,serif;padding:2px 7px;border-radius:4px;box-shadow:none}'
        '.lotsec .lot-lbl:before,.lotsec .lot-dim:before{display:none}'
        '.lotsec .lot-plat{background:#fff;overflow:auto;text-align:center;position:relative}'
        '.lotsec .lot-plat img{height:100%;width:auto;max-width:100%;object-fit:contain;cursor:zoom-in;display:inline-block}'
        '.lotsec .lot-plat-src{position:absolute;left:0;right:0;bottom:0;background:rgba(31,42,68,.85);color:#E8C77A;'
        'font:12px Georgia,serif;padding:5px 10px}'
        '@media(max-width:600px){.lotsec .lot-map{height:380px}}</style>\n'
        '<link rel="stylesheet" href="leaflet.css">\n<script src="leaflet.js"></script>\n'
        '<script>\n(function(){var D=' + D + ';\n'
        'if(!window.L)return;var made={};\n'
        'var IMG="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",'
        'ROADS="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",'
        'REF="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",'
        'ATT="Imagery &copy; Esri, Maxar, Earthstar Geographics";\n'
        'function t(u,a){return L.tileLayer(u,{maxZoom:21,maxNativeZoom:19,attribution:a||""});}\n'
        'var V={a:{layers:function(){return[t(IMG,ATT)]},fit:true},'
        'b:{layers:function(){return[t(IMG,ATT),t(ROADS),t(REF)]},zoom:18},'
        'c:{layers:function(){return[t(IMG,ATT),t(ROADS)]},zoom:17},'
        'd:{layers:function(){return[L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:21,maxNativeZoom:19,'
        'attribution:"&copy; OpenStreetMap contributors"})]},fit:true,dims:true}};\n'
        'function make(k){if(!V[k])return;if(made[k]){made[k].invalidateSize();return;}var v=V[k];\n'
        ' var m=L.map("lot-"+k,{scrollWheelZoom:false,zoomSnap:.25});m.setView(D.lot[0],v.zoom||19);\n'
        ' v.layers().forEach(function(l){l.addTo(m)});\n'
        ' var dim=!!v.dims;L.polygon(D.lot,{color:dim?"#8A6A2E":"#E8C77A",weight:4,fillColor:dim?"#B8902F":"#E8C77A",'
        'fillOpacity:dim?.16:.12}).addTo(m).bindTooltip(D.label,{permanent:true,direction:"center",className:"lot-lbl"});\n'
        ' if(dim)D.sides.forEach(function(s){L.tooltip({permanent:true,direction:"center",className:"lot-dim"})'
        '.setLatLng([s[0],s[1]]).setContent(s[2]+" ft").addTo(m);});\n'
        ' L.control.scale({imperial:true,metric:false}).addTo(m);\n'
        ' if(v.fit)m.fitBounds(D.lot,{padding:[60,60]});else m.setView(L.polygon(D.lot).getBounds().getCenter(),v.zoom);\n'
        ' made[k]=m;}\n'
        'var bt=document.querySelectorAll(".lot-tabs button");\n'
        'bt.forEach(function(b){b.addEventListener("click",function(){var k=b.dataset.v;\n'
        ' bt.forEach(function(x){x.classList.toggle("on",x===b)});\n'
        ' document.querySelectorAll(".lot-map").forEach(function(d){d.classList.toggle("on",d.id==="lot-"+k)});\n'
        ' make(k);});});\n'
        'make("a");})();\n</script>\n')


def locator_map(b):
    import compass as _compass
    """A real street map of the neighbourhood: Leaflet over OpenStreetMap
    tiles, with a pin on every place inside the walk radius and an arrow at
    the frame edge for everything beyond it. The tiles are fetched by the
    buyer's browser, so the page needs no build-time map access and no
    image is baked in. Attribution is required and is rendered by Leaflet."""
    m = b.get("locator_map")
    if not m:
        return ""
    pins = m.get("pins") or []
    if not pins or not m.get("center"):
        note("Buyer portal: locator map OMITTED — needs center and pins.")
        return ""

    # Times are derived here from the coordinates, not trusted from the file:
    # a stored "20 min walk" for somewhere a mile away is accurate and useless,
    # because nobody walks it. Anything over WALK_MAX minutes on foot is a
    # drive, and the figure is recomputed either way so the map can never
    # disagree with the Amenities section above it.
    from math import radians, sin, cos, asin, sqrt
    WALK_MAX = 15
    clat_, clng_ = m["center"]["lat"], m["center"]["lng"]
    for _p in pins:
        la1, lo1, la2, lo2 = map(radians, (clat_, clng_, _p["lat"], _p["lng"]))
        d = 2 * asin(sqrt(sin((la2 - la1) / 2) ** 2
                          + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2))
        road = 3958.8 * d * 1.30                      # straight line + roads
        w = max(1, round(road / 3.0 * 60))            # 3 mph on foot
        if w <= WALK_MAX:
            mode, mins = "walk", w
        else:
            mph = (20 if road < 1.5 else 25 if road <= 5
                   else 35 if road <= 25 else 45)
            mode, mins = "drive", max(2, round(road / mph * 60))
        if (_p.get("mode"), _p.get("min")) != (mode, mins):
            note(f'Buyer portal map: {_p["name"]} recomputed to {mins} min '
                 f'{mode} (file said {_p.get("min")} min {_p.get("mode")}).')
        _p["mode"], _p["min"] = mode, mins
    arrows = m.get("arrows") or []
    radius_mi = float(m.get("radius_mi", 1.0))
    clat, clng = m["center"]["lat"], m["center"]["lng"]

    data = json.dumps({
        "center": [clat, clng],
        "label": m["center"].get("label", ""),
        "radius": radius_mi * 1609.34,
        "pins": [{"lat": p["lat"], "lng": p["lng"], "name": p["name"],
                  "sub": p.get("sub", ""), "min": p.get("min"),
                  "mode": p.get("mode", "walk")} for p in pins],
        "arrows": [{"brg": a[0], "lines": a[1]} for a in arrows],
    }, separators=(",", ":"))

    # The numbered pins carry no text on the map itself, so the key below it
    # is what names them. Order must match the marker order exactly.
    legend = "".join(
        f'<li><span class="k-n">{i+1}</span>'
        f'<span class="k-t"><b>{p["name"]}</b>'
        + (f'<i>{p["sub"]}</i>' if p.get("sub") else "")
        + '</span>'
        + (f'<span class="k-m">{p["min"]} min'
           + ('' if p.get("mode", "walk") == "walk" else ' drive')
           + '</span>' if p.get("min") else "")
        + '</li>'
        for i, p in enumerate(pins))
    lede = f'<p class="ss">{m["lede"]}</p>' if m.get("lede") else ""
    return (
        '<section><div class="wrap">'
        f'<h2 class="st">{m.get("title", "The Neighborhood")}</h2>{lede}'
        '<div class="locmap"><div id="locmap" role="application" '
        'aria-label="Neighbourhood map"></div>'
        '<div class="locmap-arrows" id="locmapArrows" aria-hidden="true"></div>'
        + _compass.html(m.get("facing") or b.get("facing") or b.get("_facing")) +
        '</div>'
        f'<ol class="locmap-key">{legend}</ol>'
        '<p class="locmap-note">Walking times on foot. Drive times in normal '
        'traffic.</p></div></section>\n'
        '<link rel="stylesheet" href="leaflet.css">\n'
        '<script src="leaflet.js"></script>\n'
        '<script>\n'
        f'(function(){{var D={data};\n'
        'if(!window.L||!document.getElementById("locmap"))return;\n'
        'var map=L.map("locmap",{scrollWheelZoom:false,zoomControl:true});\n'
        '// A view must exist before any layer is added, or Leaflet throws.\n'
        'map.setView(D.center,15);\n'
        'L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,\n'
        '  attribution:"&copy; OpenStreetMap contributors"}).addTo(map);\n'
        'L.control.scale({imperial:true,metric:false}).addTo(map);\n'
        'var pts=[D.center];\n'
        'var marks=[];\n'
        'D.pins.forEach(function(p,i){\n'
        '  pts.push([p.lat,p.lng]);\n'
        '  var mk=L.marker([p.lat,p.lng],{icon:L.divIcon({className:"mk",\n'
        '    html:"<span class=\'mk-num\'>"+(i+1)+"</span>",\n'
        '    iconSize:[26,26],iconAnchor:[13,13]}),title:p.name}).addTo(map)\n'
        '   .bindPopup("<b>"+p.name+"</b>"+(p.sub?"<br>"+p.sub:"")+\n'
        '     (p.min?"<br><b>"+p.min+" min "+p.mode+"</b>":""));\n'
        '  mk._home=L.latLng(p.lat,p.lng); marks.push(mk);\n'
        '});\n'
        '// Several of these sit within a few metres of each other, so at any\n'
        '// useful zoom their pins overlap. Push them apart in screen space and\n'
        '// redo it whenever the zoom changes.\n'
        'function declutter(){\n'
        '  var R=30, pt=marks.map(function(m){return map.latLngToLayerPoint(m._home);});\n'
        '  for(var it=0;it<80;it++){ var moved=false;\n'
        '    for(var i=0;i<pt.length;i++){ for(var j=i+1;j<pt.length;j++){\n'
        '      var dx=pt[j].x-pt[i].x, dy=pt[j].y-pt[i].y;\n'
        '      var d=Math.sqrt(dx*dx+dy*dy)||0.01;\n'
        '      if(d<R){ var k=(R-d)/2/d; pt[i].x-=dx*k; pt[i].y-=dy*k;\n'
        '               pt[j].x+=dx*k; pt[j].y+=dy*k; moved=true; }\n'
        '    }}\n'
        '    if(!moved) break; }\n'
        '  marks.forEach(function(m,i){ m.setLatLng(map.layerPointToLatLng(pt[i])); });\n'
        '}\n'
        'L.marker(D.center,{icon:L.divIcon({className:"mk mk-home",\n'
        '  html:"<span class=\'mk-dot\'></span><span class=\'mk-lab\'>"+D.label+"</span>",\n'
        '  iconSize:[20,20],iconAnchor:[10,10]}),zIndexOffset:1000}).addTo(map)\n'
        ' .bindPopup("<b>"+D.label+"</b>");\n'
        '// Frame the walkable cluster: at a full one-mile view these pins sit\n'
        '// on top of each other and nothing is readable.\n'
        'map.fitBounds(L.latLngBounds(pts),{padding:[55,55],maxZoom:17});\n'
        'declutter(); map.on("zoomend",declutter);\n'
        'var box=document.getElementById("locmapArrows");\n'
        'D.arrows.forEach(function(a){\n'
        '  var r=a.brg*Math.PI/180, dx=Math.sin(r), dy=-Math.cos(r), t=1e9;\n'
        '  if(dx>0)t=Math.min(t,0.41/dx); if(dx<0)t=Math.min(t,-0.41/dx);\n'
        '  if(dy>0)t=Math.min(t,0.40/dy); if(dy<0)t=Math.min(t,-0.40/dy);\n'
        '  var el=document.createElement("div"); el.className="lma";\n'
        '  el.style.left=(50+dx*t*100)+"%"; el.style.top=(50+dy*t*100)+"%";\n'
        '  el.innerHTML="<span class=\'lma-ar\'><svg viewBox=\'0 0 24 24\' "+\n'
        '    "style=\'transform:rotate("+a.brg+"deg)\'><path d=\'M12 3 L12 20\' "+\n'
        '    "stroke=\'currentColor\' stroke-width=\'2.4\' stroke-linecap=\'round\'/>"+\n'
        '    "<path d=\'M12 2 L18 11 L6 11 Z\' fill=\'currentColor\'/></svg></span>"+\n'
        '    "<span class=\'lma-tx\'><b>"+a.lines[0]+"</b>"+\n'
        '    (a.lines[1]?"<i>"+a.lines[1]+"</i>":"")+"</span>";\n'
        '  box.appendChild(el);\n'
        '});\n'
        # Arrows are placed by bearing alone, so two destinations in nearly
        # the same direction (DC and Tysons, say) land on top of each other.
        # Push overlapping chips apart vertically, inside the frame.
        'var chips=[].slice.call(box.children);\n'
        'function spread(){\n'
        '  var h=box.clientHeight||1;\n'
        '  for(var pass=0;pass<30;pass++){\n'
        '    var moved=false;\n'
        '    for(var i=0;i<chips.length;i++){for(var j=i+1;j<chips.length;j++){\n'
        '      var a=chips[i].getBoundingClientRect(),b=chips[j].getBoundingClientRect();\n'
        '      if(a.right<=b.left+2||b.right<=a.left+2||'
        'a.bottom<=b.top+2||b.bottom<=a.top+2)continue;\n'
        '      var ac=(a.top+a.bottom)/2,bc=(b.top+b.bottom)/2;\n'
        '      var step=((a.height+b.height)/2-Math.abs(ac-bc))/2+3;\n'
        '      var d=step/h*100, s=(ac<=bc)?-1:1;\n'
        '      var ta=parseFloat(chips[i].style.top)+s*d;\n'
        '      var tb=parseFloat(chips[j].style.top)-s*d;\n'
        '      chips[i].style.top=Math.max(5,Math.min(95,ta))+"%";\n'
        '      chips[j].style.top=Math.max(5,Math.min(95,tb))+"%";\n'
        '      moved=true;\n'
        '    }}\n'
        '    if(!moved)break;\n'
        '  }\n'
        '}\n'
        'spread(); map.on("zoomend",spread);\n'
        '})();\n'
        '</script>\n')


def drive_time(miles):
    try:
        m = float(str(miles).replace("mi", "").strip())
    except ValueError:
        # Already a written-out time ("9 min walk"). Somewhere close enough to
        # walk would otherwise print a useless "1 min" drive, so an explicit
        # label passes straight through.
        return str(miles)
    mph = 20 if m < 1.5 else (25 if m <= 5 else (35 if m <= 25 else 45))
    mins = max(1, round(m / mph * 60))
    return f"{mins} min"


def amenities_section(b):
    """Amenities and transportation, grouped: what is close and how far.

    Each group is {"title", "items": [[name, sub, distance], ...]}. Distances
    are straight-line from the property with a road factor applied, which is
    why the note calls them approximate.
    """
    # Casey, 14 Oct 2026, on 117A Park: "no need for amenities on this one, we
    # have a walk to section and map." A walkable property says the same thing
    # twice otherwise. The groups stay on the property file so the section can
    # be turned back on without re-researching every distance.
    if b.get("show_amenities") is False:
        note("Amenities and Transportation OMITTED by "
             '"show_amenities": false — the Walk To section and the '
             "neighborhood map cover the same ground. The amenity groups are "
             "still on the property file.")
        return ""
    groups = b.get("amenities") or []
    if not groups:
        return ""
    cards = []
    for g in groups:
        rows = "".join(
            f'<div class="am-row"><div class="am-n">{n}'
            + (f'<span class="am-s">{sub}</span>' if sub else "")
            + f'</div><div class="am-d">{drive_time(d)}</div></div>'
            for n, sub, d in g["items"])
        cards.append(f'<div class="am-card"><h3>{g["title"]}</h3>{rows}</div>')
    lede = b.get("amenities_lede") or "What is close, and how far."
    return ('<div class="am-block">'
            '<h2 class="st">Amenities and Transportation</h2>'
            f'<p class="ss">{lede}</p>'
            f'<div class="am-grid">{"".join(cards)}</div>'
            f'<p class="am-note">{AMENITIES_NOTE}</p>'
            '</div>')


def walk_to_section(b):
    """"Walk To" — downtown Vienna on foot from the front door.

    Each entry is {"name", "note", "minutes", "kind"} plus an optional
    "logo" image filename. Where a property has no pricing model to show,
    this is what carries the location story instead.
    """
    places = b.get("walk_to") or []
    if not places:
        return ""
    tiles = []
    for pl in places:
        if pl.get("logo"):
            mark = f'<img src="{pl["logo"]}" alt="{pl["name"]}" loading="lazy">'
        else:
            mark = WALK_ICONS.get(pl.get("kind", ""), WALK_ICONS["civic"])
        note_html = f'<div class="wt-n">{pl["note"]}</div>' if pl.get("note") else ""
        tiles.append(f'<div class="wt"><div class="wt-mark">{mark}</div>'
                     f'<div class="wt-t">{pl["name"]}</div>{note_html}'
                     f'<div class="wt-m">{pl["minutes"]} min walk</div></div>')
    lede = b.get("walk_to_lede") or ("Downtown Vienna starts at the front door. "
                                     "Every walk below is from this address.")
    return (f'<section><div class="wrap"><h2 class="st">Walk To</h2>'
            f'<p class="ss">{lede}</p>'
            f'<div class="wt-grid">{"".join(tiles)}</div></div></section>\n')


# Casey, 15 Oct 2026: "this link should be on every Vienna Buyer Portal."
# Keyed on the property's city so it lands by itself from here on rather than
# having to be remembered property by property. Other towns get added here as
# they earn a mention; any one property can override the entry with "press" on
# buyer_portal, or set "press": false to leave the band off.
_TL_VIENNA = {
    "kicker": "The Neighborhood, In The Press",
    # Casey's wording, 15 Oct 2026.
    "headline": "Vienna is rated #1 Best Suburb to Live in the USA",
    "pub": "Travel + Leisure Magazine",
    "url": "https://www.travelandleisure.com/best-suburbs-to-live-in-usa-12150032",
    "cta": "Read the article",
}

# Casey, 15 Oct 2026: "All Vienna and Oakton Buyer portals should show this."
# Oakton runs the same band, Vienna headline and all -- the two adjoin and
# much of Oakton carries a Vienna mailing address.
CITY_PRESS = {
    "Vienna": _TL_VIENNA,
    "Oakton": _TL_VIENNA,
}


def city_press_section(p, b):
    """A press mention for the town the home is in.

    The entry is looked up in CITY_PRESS by the property's city, so a Vienna
    portal carries the Travel + Leisure ranking without the property file
    saying anything about it. The claim leads and the magazine is credited
    under it, with the article itself one click away.
    """
    pr = b.get("press")
    if pr is False:
        note('City press band OMITTED by "press": false.')
        return ""
    if not pr:
        pr = CITY_PRESS.get((p.get("city") or "").strip())
    if not pr:
        return ""
    head = pr.get("headline") or pr.get("title") or ""
    cred = f'<p class="pub">{pr["pub"]}</p>' if pr.get("pub") else ""
    blurb = f'<p class="pn">{pr["note"]}</p>' if pr.get("note") else ""
    cta = ""
    if pr.get("url"):
        cta = (f'<a class="pl" href="{pr["url"]}" target="_blank" rel="noopener">'
               f'{pr.get("cta", "Read the article")}</a>')
    return ('<section><div class="wrap"><div class="press">'
            f'<div class="pk">{pr.get("kicker", "As Seen In")}</div>'
            f'<p class="ph">{head}</p>{cred}{blurb}{cta}'
            '</div></div></section>\n')


def production_section(p, b):
    """The Casey Samson Team production band.

    Casey, 15 Oct 2026: "Update MacArthur seller and buyer portals and add
    new production bar." The figures live in build_index_v2 so the seller
    portal, the buyer portal and the Working With CST flyer all quote one
    set. A buyer's agent reading this page is deciding whether to bring an
    offer here, and the record is part of that answer.

    "production": false on buyer_portal leaves the band off.
    """
    if b.get("production") is False:
        note('Production band OMITTED by "production": false.')
        return ""
    try:
        from build_index_v2 import production_rows as _pr
        rows = _pr(p)
    except ImportError:
        note("Production band OMITTED — build_index_v2 is not importable, "
             "so there are no figures to quote.")
        return ""
    tiles = "".join(f'<div class="pr-t"><span class="n">{n}</span>'
                    f'<div class="l">{l}</div></div>' for n, l in rows)
    return ('<section><div class="wrap">'
            '<h2 class="st">The Casey Samson Team</h2>'
            '<p class="ss">The Gold Standard of Pricing Strategy. Source: MLS Bright.</p>'
            f'<div class="pr-grid">{tiles}</div>'
            '</div></section>\n')


def _sf(v):
    return f"{v:,.0f}" if v else "&mdash;"


def _lot(v):
    return f"{v:,.0f}" if v else "&mdash;"   # Casey, 29 Oct 2026: "take out SF on lot"


def market_update_section(p, b, out):
    """Casey, 16 Oct 2026: "Add local market update."

    The CST Market Intelligence(TM) dashboard the Seller Roadmap and the
    Local Market Snapshot carry, on the buyer page as well: what the market
    this home competes in is doing, in four gauges, with the full snapshot
    one click away. Built by running the property's own Local Market
    Snapshot into this folder, so the page and the gauges can never quote
    different figures.
    """
    if not (p.get("local_snapshot") or {}).get("rows") \
            and not (p.get("local_snapshot") or {}).get("pull"):
        return ""
    from local_snapshot import build_local_snapshot, LMS_CMI_CSS  # noqa
    from build_portal import cmi_dashboard, GAUGE_CSS             # noqa
    from build_portal import canonical_stats                      # noqa

    name = build_local_snapshot(p, out, note=note,
                                buyer_url=b.get("url") or "")
    c = ((p.get("market") or {}).get("conditions")) or {}
    if not c.get("stats"):
        # With "conditions": "market" on the local_snapshot block the page is
        # built but hands nothing back, because the city report is the better
        # read. The dashboard then comes from that report's cached figures.
        slug = (p.get("market") or {}).get("slug")
        cf = HERE / "market_cache.json"
        if slug and cf.exists():
            c = (json.loads(cf.read_text()).get(slug, {}) or {}).get(
                "conditions") or {}
    if not c.get("stats"):
        return ""
    sub = f'<p class="lede snap-lede">{c["sub"]}</p>' if c.get("sub") else ""
    more = ""
    if name:
        more = ('<p class="mu-more"><a href="%s" target="_blank" '
                'rel="noopener">See the full Market Snapshot &rarr;</a></p>'
                % name)
    return (f'<section class="mu-sec"><div class="wrap">'
            f'<style>{GAUGE_CSS}{LMS_CMI_CSS}</style>'
            f'<h2 class="st">Local Market Update</h2>{sub}'
            f'<div class="lms-cmi">'
            f'{cmi_dashboard(canonical_stats(p.get("market") or {}, c), c, wide=True)}'
            f'</div>{more}</div></section>\n')


SNAP_STATUS = {
    "ACT": ("Active", "act"), "A/C": ("Active under Contract", "ac"),
    "PND": ("Pending", "ac"), "CLS": ("Closed", "cls"),
    "WTH": ("Withdrawn", "off"), "EXP": ("Expired", "off"),
    "CNL": ("Cancelled", "off"), "TEMP": ("Temporarily Off Market", "off"),
}


def snapshot_section(p, b):
    """Casey, 16 Oct 2026: "Add a snapshot section to the Buyer Portal that
    shows the ACT, A/C, WTH and EXP with all the information up to the list
    price."

    The homes this one is actually competing with, as the market sees them:
    status, address, days on market, age, size, lot, assessment and what
    each one is asking. The columns stop at the list price on purpose --
    everything past it on the pricing model (the computed value, the gap,
    price per foot) is the team's own work and does not belong on a public
    page.
    """
    s = b.get("snapshot") or {}
    rows = s.get("rows") or []
    if not rows:
        return ""
    head = ("<thead><tr><th>Status</th><th>Address</th><th>DOM</th>"
            "<th>Built</th><th>Above Grade SF</th><th>Lot</th>"
            "<th>Assessment</th><th>List Price</th></tr></thead>")
    body, seen = [], []
    for r in rows:
        st, addr, dom, built, sf, lot, assess, lp = (list(r) + [None] * 8)[:8]
        code = str(st or "").upper().strip()
        label, cls = SNAP_STATUS.get(code, (code.title(), "off"))
        if label not in seen:
            seen.append(label)
        body.append(
            f'<tr><td><span class="snap-pill {cls}" title="{label}">{code}'
            f'</span></td><td class="addr-cell">{addr}</td>'
            f'<td>{dom if dom is not None else "&mdash;"}</td>'
            f'<td>{built or "&mdash;"}</td><td>{_sf(sf)}</td><td>{_lot(lot)}</td>'
            f'<td>{money(assess) if assess else "&mdash;"}</td>'
            f'<td><b>{money(lp) if lp else "&mdash;"}</b></td></tr>')
    legend = " &middot; ".join(
        f'<b>{c}</b> {SNAP_STATUS[c][0]}' for c in SNAP_STATUS
        if SNAP_STATUS[c][0] in seen)
    lede = (f'<p class="lede snap-lede">{s["lede"]}</p>' if s.get("lede")
            else "")
    return (f'<section><div class="wrap"><h2 class="st">'
            f'{s.get("title") or "Market Snapshot"}</h2>{lede}'
            f'<div class="tablewrap"><table class="comps snap">{head}'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="snap-legend">{legend}</p></div></section>\n')


def values_section(p, b):
    """Authenticated Values — the same comparable table and the Customary /
    Premium cards the Buyer Pricing Report carries, restated on the portal so
    a buyer sees the values alongside the photos rather than only inside a
    linked report. Built from the property's own comps and values: with
    neither on file the whole section is left out."""
    v = p.get("values") or {}
    comps = p.get("comps") or {}
    if not (v.get("customary") and (v.get("premium") or v.get("upgrades"))):
        note("Authenticated Values OMITTED — no customary value, and no premium "
             "or upgrades figure to derive one from.")
        return ""

    # A property priced off Extraordinary Upgrades carries no stored premium:
    # it is a RANGE derived from the upgrade spend. Ask the pricing engine
    # rather than restating the rule here, so the portal and the Roadmap can
    # never disagree about what the Premium Value is.
    from pricing import compute as _compute
    _s = _compute(dated=v.get("dated") or 0,
                  customary=v["customary"],
                  customary_list=v.get("customary_list") or v["customary"],
                  premium=v.get("premium") or 0,
                  upgrades=v.get("upgrades") or 0,
                  discount=v.get("discount") or 0)
    premium_display = _s.premium_display

    subj = p.get("subject") or {}
    table = ""
    if comps.get("rows"):
        head = ("<thead><tr><th>Property</th><th>Built</th><th>Above Grade SF</th>"
                "<th>Lot</th><th>Assessment</th><th>Sales Price</th></tr></thead>")
        body = []
        if subj:
            body.append(
                f'<tr class="total-row"><td class="addr-cell">{b.get("display_address") or p["address"]}</td>'
                f'<td>{subj.get("built", "&mdash;")}</td><td>{_sf(subj.get("sf"))}</td>'
                f'<td>{_lot(subj.get("lot"))}</td><td>{money(subj["assessment"]) if subj.get("assessment") else "&mdash;"}</td>'
                f"<td>&mdash;</td></tr>")
        # A whole-town comp set can run past a dozen homes; the buyer table
        # (and its 2-page PDF) shows the closest 8. The weighted average row
        # still covers every comp.
        _cap = b.get("max_comps", 8)
        for r in comps["rows"][:_cap]:
            addr, built, sf, lot, assess, sale = (list(r) + [None] * 6)[:6]
            body.append(f'<tr><td class="addr-cell">{addr}</td><td>{built}</td>'
                        f"<td>{_sf(sf)}</td><td>{_lot(lot)}</td>"
                        f"<td>{money(assess) if assess else '&mdash;'}</td>"
                        f"<td><b>{money(sale) if sale else '&mdash;'}</b></td></tr>")
        for r in comps.get("summary", []):
            addr, built, sf, lot, assess, sale = (list(r) + [None] * 6)[:6]
            body.append(f'<tr class="total-row"><td class="addr-cell">{addr}</td>'
                        f"<td>{built}</td><td>{_sf(sf)}</td><td>{_lot(lot)}</td>"
                        f"<td>{money(assess) if assess else '&mdash;'}</td>"
                        f"<td>{money(sale) if sale else '&mdash;'}</td></tr>")
        table = (f'<div class="tablewrap"><table class="comps">{head}'
                 f'<tbody>{"".join(body)}</tbody></table></div>')
    else:
        note("Comparable table OMITTED from Authenticated Values — no comps on file.")

    meta = []
    if subj.get("built"):
        meta.append(f'Built {subj["built"]}')
    if subj.get("sf"):
        # "Above grade" only earns its place next to the comparable table,
        # where it reconciles with the marketed finished-SF figure.
        meta.append(f'{_sf(subj["sf"])} SF above grade' if table else f'{_sf(subj["sf"])} SF')
    if subj.get("assessment"):
        meta.append(f'Assessment {money(subj["assessment"])}')
    meta = " &middot; ".join(meta)

    cards = (
        '<div class="values-grid">'
        '<div class="value-card"><h3>Customary Value</h3>'
        f'<div class="value-num">{money(v["customary"])}</div><ul>'
        "<li>Kitchen and bathrooms updated within ~15 years.</li>"
        "<li>Paint, lighting, hardware, flooring and finishes reflect the current standard.</li>"
        "<li>Overall presentation is competitive with comparable homes.</li></ul></div>"
        '<div class="value-card" style="border-color:var(--gold-line); '
        'box-shadow:0 4px 14px rgba(138,106,46,.08);"><h3>Premium Value</h3>'
        f'<div class="value-num">{premium_display}</div>'
        + (f'<p class="value-basis">Based on {money(v["upgrades"])} in '
           "extraordinary upgrades</p>" if v.get("upgrades") else "")
        + '<ul>'
        "<li>Kitchen and bathrooms updated within ~10 years.</li>"
        "<li>Upgrades, finishes and craftsmanship exceed the standard.</li>"
        "<li>Overall presentation distinguishes the property from the competition.</li>"
        "</ul></div></div>")

    # The printable Buyer Pricing document: condensed header, headlines,
    # authenticated pricing and premiums, on two pages.
    # Casey, 11 Oct 2026: "the buyer portal PDF needs to be a obvious link on
    # the buyer portals." It was a small underlined caption under the value
    # cards, which read as a footnote. It is a button now, with the document
    # named and a line saying what is in it, so a buyer's agent cannot miss
    # the one page that carries the authenticated values.
    pr = ""
    if b.get("pricing_pdf"):
        pr = (f'<div class="value-print"><a class="pdf-btn" '
              f'href="{b["pricing_pdf"]}" target="_blank" rel="noopener">'
              '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" '
              'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 '
              '0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 '
              '20 8"/><line x1="12" y1="18" x2="12" y2="12"/>'
              '<polyline points="9 15 12 18 15 15"/></svg>'
              '<span class="pdf-btn-t">Buyer Pricing Report</span>'
              '<span class="pdf-btn-s">The authenticated values and the '
              'comparable sales behind them &mdash; PDF</span></a></div>')

    # The price is not always below the Customary Value -- a home priced into
    # its Premium Range sits above it -- so the sentence is written to match
    # where the price actually falls rather than asserting a discount.
    foot = ""
    if b.get("list_price"):
        _lp = b["list_price"]
        if _lp < v["customary"]:
            _claim = ("below the authenticated Customary Value of "
                      f'{money(v["customary"])}')
        elif _lp <= _s.expected_high:
            _basis = (f' earned by {money(v["upgrades"])} in extraordinary upgrades'
                      if v.get("upgrades") else "")
            _claim = (f'against an authenticated Customary Value of {money(v["customary"])} '
                      f'and a Premium Value of {premium_display}{_basis}')
        else:
            _claim = f"above the authenticated Premium Value of {premium_display}"
        foot = (f'<p class="value-foot">Offered at {money(_lp)} '
                f'&mdash; {_claim}.</p>')

    lede = ("Every valuation is developed by the CST Pricing Team from qualified "
            "comparable sales &mdash; not generated by an online estimate." if table else
            "Every valuation is developed by the CST Pricing Team &mdash; not generated "
            "by an online estimate.")
    # Casey, 14 Oct 2026, on 502 MacArthur: "Can you update the portal with
    # Pending-well over List price under the valuation ... Make it in red and
    # look like someone stamped it with PENDING OVER LIST IN 4 DAYS!"
    #
    # Driven by a "stamp" block so any property can carry one, and nothing
    # appears unless the property file says so. The text is whatever is on
    # file -- it is a claim about a live transaction, so it is never derived
    # or assembled here.
    stamp = ""
    _st = b.get("stamp")
    if not _st and b.get("sold_for"):
        _sfp = b["sold_for"]
        _top = v.get("premium_top") or v["premium"]
        if v["customary"] <= _sfp <= _top:
            _where = f'{(_sfp / v["customary"] - 1) * 100:.1f}% over Customary Value'
        elif _sfp > _top:
            _where = f'{(_sfp / _top - 1) * 100:.1f}% over Premium Value'
        else:
            _where = f'{(1 - _sfp / v["customary"]) * 100:.1f}% under Customary Value'
        _st = [f'SOLD {money(_sfp)}', _where]
        if b.get("list_price") and _sfp > b["list_price"]:
            _st[1] = f'{(_sfp / b["list_price"] - 1) * 100:.1f}% over list &middot; ' + _where
        foot = ""
    if _st:
        _lines = _st if isinstance(_st, list) else [_st]
        _body = "".join(f'<span class="stamp-l">{t}</span>' for t in _lines)
        stamp = f'<div class="stamp-wrap"><div class="stamp">{_body}</div></div>'

    # Casey, 25 Oct 2026: "need values authenticated by over Casey Samson
    # team" -- a line over the heading naming who authenticated them.
    # Sponsored portals carry no team info, so they leave it off unless
    # "authenticated_by" is set on the buyer_portal block.
    _ab = b.get("authenticated_by")
    if _ab is None:
        _ab = "" if b.get("sponsor") else "Authenticated by the Casey Samson Team"
    _abl = (f'<div class="auth-by" style="text-align:center;font-size:12px;letter-spacing:.2em;'
            f'text-transform:uppercase;font-weight:700;color:var(--gold-deep);margin-bottom:8px;">{_ab}</div>'
            if _ab else "")
    # Casey, 25 Oct 2026: the team's credentials under that line, word for
    # word. "authenticated_by_note" on the buyer_portal block overrides it.
    _abn = b.get("authenticated_by_note")
    if _abn is None and _ab:
        _abn = ("The Casey Samson Team (CST) is a seven-agent real estate team with over "
                "$300 million in MLS-documented production over a 365-day period. 50% of CST "
                "listings sell in the first week, with 74% selling over list price.")
        # (Casey, 24 Nov 2026: 50% first week, 74% over list.)
    if _abn:
        _abl += (f'<p class="auth-note" style="text-align:center;max-width:760px;margin:0 auto 14px;'
                 f'font-size:14.5px;line-height:1.55;color:var(--ink);">{_abn}</p>')
    return (f'<section><div class="wrap">{_abl}<h2 class="st">Authenticated Values&trade;</h2>'
            f'<p class="ss">{lede}{" " + meta if meta else ""}</p>'
            f"{table}{cards}" + (f'<p class="ss" style="margin-top:14px;"><b>{_buyer_note(v)}</b></p>' if _buyer_note(v) else "") + f"{pr}{stamp}{foot}" + _cst_history(b) + "</div></section>\n")


def _cst_history(b):
    """Casey, 21 Nov 2026: at the bottom of Authenticated Values -- "Historically,
    CST Listings sell between Customary and Premium Values. Sometimes More."
    "cst_history": false on the buyer_portal block leaves it off."""
    if b.get("cst_history") is False:
        return ""
    return ('<p class="cst-history" style="text-align:center;max-width:760px;margin:18px auto 0;'
            "font-family:'Playfair Display',Georgia,serif;font-style:italic;font-size:18px;"
            'color:var(--gold-deep);line-height:1.45;">Historically, CST listings sell between '
            'Customary and Premium Values. Sometimes more.</p>')


DISCLOSURE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Seller Disclosures &mdash; {addr}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');
:root{{--bg:#FAF7F0;--card:#FFF;--banner:#F1EBDA;--ink:#221C14;--muted:#71695A;
  --muted-2:#968972;--gold-deep:#8A6A2E;--gold-line:#D3B978;--rule:#E4DCC8;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Lora',Georgia,serif;line-height:1.6;}}
.wrap{{max-width:780px;margin:0 auto;padding:0 26px;}}
a.back{{display:block;padding:13px 26px;font-size:13px;color:var(--muted);
  text-decoration:none;background:var(--card);border-bottom:1px solid var(--rule);}}
a.back:hover{{color:var(--gold-deep);}}
header{{background:var(--banner);border-bottom:1px solid var(--gold-line);
  padding:36px 0 30px;text-align:center;}}
header img{{width:64px;display:block;margin:0 auto 12px;}}
.brandline{{letter-spacing:.22em;font-size:11.5px;font-weight:600;color:var(--gold-deep);
  text-transform:uppercase;margin-bottom:10px;}}
h1{{font-family:'Playfair Display',Georgia,serif;font-size:29px;font-weight:700;margin:0 0 6px;}}
.addr{{font-size:15px;color:var(--muted);margin:0;}}
.pending{{background:#F3EAD3;border:1px solid var(--gold-line);border-radius:8px;
  padding:18px 24px;margin:34px 0 0;text-align:center;font-size:15px;}}
.pending b{{color:var(--gold-deep);}}
section{{padding:34px 0;}}
h2{{font-family:'Playfair Display',Georgia,serif;font-size:20px;font-weight:600;
  text-align:center;margin:0 0 6px;}}
p.sub{{text-align:center;color:var(--muted);font-size:14px;margin:0 0 26px;}}
.item{{background:var(--card);border:1px solid var(--rule);border-left:4px solid var(--gold-deep);
  border-radius:8px;padding:16px 20px;margin-bottom:12px;}}
.item .t{{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:16px;}}
.item .d{{font-size:13.5px;color:var(--muted);margin-top:3px;}}
.ask{{text-align:center;font-size:15px;margin:30px 0 0;}}
.ask a{{color:var(--gold-deep);}}
footer{{text-align:center;padding:34px 0 46px;background:var(--banner);
  border-top:1px solid var(--gold-line);margin-top:30px;}}
footer .produced{{font-weight:700;font-size:14px;margin-bottom:4px;}}
footer .copy{{font-size:11.5px;color:var(--muted);margin-top:12px;line-height:1.7;}}
</style>
</head>
<body>
<a class="back" href="index.html">&larr; Back to {addr}</a>
<header>
  <img src="Gold_Standard_Logo.png" alt="The Casey Samson Team">
  <div class="brandline">The Casey Samson Team</div>
  <h1>Seller Disclosures</h1>
  <p class="addr">{addr}, {city}, {state}</p>
</header>
<div class="wrap">
{pending}
<section>
  <h2>What Is Disclosed</h2>
  <p class="sub">The documents below make up the disclosure package for this home.</p>
{items}
</section>
<p class="ask">Need a copy before the deadline? Email
<a href="mailto:{email}">{email}</a> or call {phone} and we will send it the same day.</p>
</div>
<footer>
  <div class="wrap">
    <div class="produced">The Casey Samson Team</div>
    <div>Casey Samson &middot; 703-508-2535 &middot; Casey@caseysamson.com</div>
    <div class="copy">Virginia is a caveat emptor state. The seller makes no representations
    about the condition of the property beyond those required by law, and buyers are
    encouraged to obtain their own inspections. This page summarises what is provided;
    it is not itself a disclosure and does not replace any signed document.<br>
    &copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </div>
</footer>
</body>
</html>
"""


def disclosures_file(b):
    """The page name the documents list points at, so each property keeps its
    own prefix (BB_, MC_, …) rather than a hard-coded one."""
    for href, _, _ in b.get("documents", []):
        if href.endswith("Disclosures.html"):
            return href
    return "Disclosures.html"


def build_disclosures(p, b, out):
    """A standing Disclosures page so the link works from day one. It states
    what the package contains and how to get it; it never stands in for a
    signed disclosure, and invents no answers on the seller's behalf. Point
    "file" at the real PDF once it is signed and this page steps aside."""
    d = b.get("disclosures")
    if not d:
        return
    if d.get("file"):
        return          # a real document is on file; nothing to generate
    items = "".join(f'<div class="item"><div class="t">{t}</div>'
                    f'<div class="d">{desc}</div></div>' for t, desc in d.get("items", []))
    pending = ""
    if d.get("pending", True):
        pending = ('<div class="pending"><b>The signed packet is being assembled.</b><br>'
                   "Disclosures are delivered through MLS and are available on request "
                   "&mdash; ask and we will send them straight over.</div>")
    c = b.get("contacts") or {}
    first = (c.get("lines") or [["The Casey Samson Team", "703-508-2535",
                                 "Casey@caseysamson.com"]])[0]
    (out / disclosures_file(b)).write_text(DISCLOSURE_PAGE.format(
        addr=b.get("display_address") or p["address"], city=p["city"], state=p["state"],
        pending=pending, items=items, email=first[2], phone=first[1]))


def build(p, out):
    b = p.get("buyer_portal")
    if not b:
        sys.exit('This property has no "buyer_portal" block — nothing to build.')

    addr = b.get("display_address") or p["address"]
    city, state = p["city"], p["state"]
    pre = p["prefix"]

    # ---- hero ----------------------------------------------------------
    hero = b.get("hero_photo") or p.get("hero_photo")
    hero_img = (f'  <img src="{hero}" alt="{addr}">' if hero else "")
    if hero and not b.get("hero_photo"):
        note(f"Hero photo inherited from the Seller Portal ({hero}).")
    elif not hero:
        note("Hero photo OMITTED — none on the buyer_portal block or the property.")

    price = (f'<span class="price">{money(b["list_price"])}</span>'
             if b.get("list_price") else "")
    # Casey, 24 Nov 2026: "Add sold $1.383M on John Marshall buyer". A closed
    # sale ("sold_for" on the buyer_portal block) replaces the offered price.
    if b.get("sold_for"):
        price = f'<span class="price">Sold {money(b["sold_for"])}</span>'

    if not b.get("list_price"):
        note("Offered price OMITTED — no list_price in the buyer_portal block.")

    site = b.get("site")
    # Without a working destination the site name is shown as plain text —
    # a hero link to "#" is a dead link on a public page.
    if site and b.get("site_url"):
        site_link = (f'<a class="site" href="{b["site_url"]}" target="_blank" '
                     f'rel="noopener">{site}</a>')
    elif site:
        site_link = f'<span class="site">{site}</span>'
        note(f"Hero site name shown as plain text — no site_url on file for {site}.")
    else:
        site_link = ""

    # ---- open house / offer band ---------------------------------------
    cols = []

    # On a property Casey does not list, "contacts" stays HIS team -- he is
    # the one offering showings at the foot of the page -- and the listing
    # brokerage's people go in "listing_contacts", which is what this band
    # names. Using "contacts" here would have put the listing agents under
    # Casey's own "we would be glad to show you the home".
    #
    # Hoisted above the columns so the Open House can carry the same contacts
    # the Contract Deadlines column does. It also closes a latent hole: _one
    # used to be defined only when there were contact lines, so a property
    # with a buyer_agent and no lines raised NameError.
    _lines = (((b.get("listing_contacts") or {}).get("lines"))
              or ((b.get("contacts") or {}).get("lines")) or [])

    def _one(nm, ph, em):
        # A contact with no phone on file prints the name and email rather
        # than an empty tel: link that dials nothing.
        bits = [f"<b>{nm}</b>"]
        if (ph or "").strip():
            bits.append(f'<a href="tel:+1{re.sub(r"[^0-9]", "", ph)}">{ph}</a>')
        else:
            note(f"Band contacts: no phone on file for {nm}, so only the "
                 "email is shown.")
        if (em or "").strip():
            bits.append(f'<a href="mailto:{em}">{em}</a>')
        return f'<span class="bcon">{"".join(bits)}</span>'

    def _band_contacts():
        if not _lines:
            return ""
        return ('<div class="band-contacts">'
                + "".join(_one(*ln[:3]) for ln in _lines) + "</div>")

    oh = b.get("open_house")
    if oh:
        # Casey, 15 Oct 2026, on 117A Park: "bring co agent contact info under
        # or call for a private showing." Where the Open House has replaced
        # the Contract Deadlines column, it has to carry the names too, or the
        # banner loses every route to a person. Where both columns show, the
        # deadlines column already names them and repeating it is noise.
        _solo = b.get("show_deadlines") is False and not b.get("offer_deadline")
        _oh_con = _band_contacts() if _solo else ""
        cols.append(f'<div class="col{" oh" if _solo else ""}">'
                    f'<div class="lbl">Open House</div>'
                    f'<div class="val">{oh["when"]}</div>'
                    f'<div class="sub">{oh.get("note", "")}</div>'
                    f'{_oh_con}</div>')
    else:
        note("Open House band OMITTED — no open_house on file.")
    # Casey, 12 Oct 2026: "Monday deadlines to Contact Co Listings Agent for
    # contract Deadlines." A published deadline goes stale the moment it
    # passes, and a buyer's agent reading it a week later is reading a date
    # that already happened. So the default is to send them to the people
    # who actually know, who are named in the contact block below. A property
    # that genuinely wants a date published still sets offer_deadline.
    od = b.get("offer_deadline")
    if od:
        cols.append(f'<div class="col"><div class="lbl">Offers Reviewed</div>'
                    f'<div class="val">{od["when"]}</div>'
                    f'<div class="sub">{od.get("note", "")}</div></div>')
        note(f'Offer deadline PUBLISHED as "{od["when"]}" — the standing line '
             "is to send agents to the co-listing agent instead. Remove "
             '"offer_deadline" from the property file to use it.')
    else:
        # Casey, 12 Oct 2026: "you can bring in co listing agents phone and
        # email on banner from bottom of page." Same contacts the footer
        # block carries, so a buyer's agent does not have to scroll to find
        # out who to call. Phone and email are live links.
        if _lines:
            sub = _band_contacts()
        else:
            sub = '<div class="sub">Names and numbers below.</div>'
            note("Contract Deadlines band: no contacts on the buyer_portal "
                 "block, so it cannot name the co-listing agent.")
        # Casey, 13 Oct 2026, on 10015 Saddle Rd: the home is listed by
        # another brokerage and he is representing a buyer on it. The page
        # carries Casey Samson Team branding because it is his work for his
        # buyer -- so it has to name the listing brokerage outright, or a
        # buyer's agent landing on it would read the branding as the listing.
        # Casey, 13 Oct 2026: "Put buyer agent info up top ... no listing
        # agent info on bottom when we are buyers." On a property we do not
        # list, the band names OUR agent -- the person this buyer calls --
        # and the listing brokerage is credited in the footer as a plain
        # attribution, not as contact details.
        if b.get("buyer_agent"):
            _ba = b["buyer_agent"]
            _who = _one(_ba.get("name", ""), _ba.get("phone", ""),
                        _ba.get("email", ""))
            cols.append('<div class="col"><div class="lbl">Your Agent</div>'
                        '<div class="val">Questions or a Private Showing</div>'
                        f'<div class="band-contacts">{_who}</div></div>')
        elif b.get("show_deadlines") is False:
            # Casey, 15 Oct 2026, on 117A Park: "Replace contract deadlines on
            # just Park buyer portal with Open House." The band holds two
            # columns, so suppressing this one is what makes the Open House
            # replace it rather than sit beside it. The co-listing agents are
            # still named in the contact block at the foot of the page.
            note('Contract Deadlines band OMITTED by "show_deadlines": false. '
                 "The Open House takes that slot; the co-listing agents are "
                 "still named at the foot of the page.")
        else:
            cols.append('<div class="col"><div class="lbl">Contract Deadlines'
                        '</div><div class="val">Contact the '
                        + (b.get("deadline_contact_label")
                           or ("Listing Agent" if b.get("sponsor") else "Co-Listing Agent"))
                        + '</div>' + sub + "</div>")
    band = (f'<div class="band"><div class="wrap"><div class="cols">\n'
            + "\n".join(cols) + "\n</div></div></div>\n") if cols else ""

    # Casey, 25 Nov 2026: "At the top of new portal, put visible link to
    # completed buyer portal once information has been gathered." Until this
    # home's portal has its photos and features, a bar at the top links to a
    # finished one (the Sample).
    wip_bar = ""
    try:
        from build_portal import buyer_portal_ready as _bpr, EXAMPLE_BUYER_PORTAL as _ex
        _own = (b.get("url") or "").rstrip("/")
        if not (_bpr(p) or b.get("finished")) and _own.rstrip("/") != _ex.rstrip("/"):
            wip_bar = ('<div style="background:#1F2A44;color:#F3EBD8;text-align:center;padding:12px 16px;'
                       'font:15px/1.45 Georgia,serif;border-bottom:3px solid #B8902F">'
                       'This Buyer Portal is being built &mdash; photos and features are added as the home is prepared. '
                       f'<a href="{_ex}" target="_blank" rel="noopener" style="color:#E8C77A;font-weight:700;'
                       'text-decoration:underline;text-underline-offset:3px;white-space:nowrap">'
                       'See a completed Buyer Portal &rarr;</a></div>')
    except Exception:
        pass

    # ---- quick facts ----------------------------------------------------
    facts = ""
    if b.get("facts"):
        cells = "".join(f'<div class="fact"><span class="n">{n}</span>'
                        f'<div class="l">{l}</div></div>' for n, l in b["facts"])
        import schools as _sch
        _sr = _sch.row_html(p, buyer=True)
        facts = (f'<div class="wrap"><div class="facts">{cells}'
                 + (f'<style>{_sch.CSS}.facts .sch-row{{flex:1 1 100%;margin:8px 10px 0}}</style>{_sr}' if _sr else "")
                 + '</div></div>\n')

    # ---- description ----------------------------------------------------
    # One line that sells, then the handful of things worth saying out loud.
    # A full paragraph is only used when no headline is supplied — buyers skim,
    # and the photos and the values do the rest of the arguing.
    desc = ""
    builder = (f'<p class="builder">{b["builder_line"]}</p>'
               if b.get("builder_line") else "")
    if b.get("feature_headlines"):
        # Headline features, each with its own supporting line. Replaces the
        # narrative outright: a buyer scanning gets the four things that
        # matter without reading a paragraph.
        sep = '<span class="sep">&middot;</span>'
        blocks = "".join(
            f'<div class="feat-h"><h3>{fh["head"]}</h3>'
            f'<p>{sep.join(fh["sub"])}</p></div>'
            for fh in b["feature_headlines"])
        # Casey, 5 Nov 2026 (Valhalla): the tagline can sit over the three
        # headline features -- "feature_hook" on the buyer_portal block.
        _hook = (f'<p class="hook">{b["feature_hook"]}</p>' if b.get("feature_hook") else "")
        desc = (f'<section class="pitch"><div class="wrap">{_hook}'
                f'<div class="feats">{blocks}</div>{builder}</div></section>\n')
    elif b.get("headline"):
        hl = ""
        if b.get("highlights"):
            hl = ('<div class="hl">'
                  + "".join(f"<span>{h}</span>" for h in b["highlights"])
                  + "</div>")
        desc = (f'<section class="pitch"><div class="wrap">'
                f'<p class="hook">{b["headline"]}</p>{hl}{builder}</div></section>\n')
    elif b.get("description"):
        note("Long-form description shown — no headline on file. Add \"headline\" and "
             "\"highlights\" to the buyer_portal block for the short version.")
        desc = (f'<section style="padding-top:38px;"><div class="wrap">'
                f'<p class="lede">{b["description"]}</p>{builder}</div></section>\n')

    # ---- video ----------------------------------------------------------
    video = ""
    if b.get("videos"):
        vs = "".join(
            f'<div class="vid"><video controls preload="metadata" playsinline '
            f'poster="{v["poster"]}"><source src="{v["file"]}" type="video/mp4">'
            f'</video><div class="cap">{v["label"]}</div></div>'
            for v in b["videos"])
        cta = ""
        if b.get("listing_page_url"):
            cta = (f'<div class="site-cta"><a href="{b["listing_page_url"]}" target="_blank" '
                   f'rel="noopener">View the Full Listing &rarr;</a>'
                   f'<div class="sub">Full gallery, details and floor plans on '
                   f'caseysamson.com</div></div>')
        else:
            note("Full Listing link OMITTED — no listing_page_url in the buyer_portal block.")
        video = (f'<section><div class="wrap"><h2 class="st">See the Home</h2>'
                 f'<p class="ss">Take the tour, then come see it in person.</p>'
                 f'<div class="videos">{vs}</div>{cta}</div></section>\n')
    else:
        note("Video tour OMITTED — no videos on file.")
        # No video does not mean no "See the Home": the custom website link
        # lives in this section and has to survive on its own.
        if b.get("listing_page_url"):
            video = (f'<section><div class="wrap"><h2 class="st">See the Home</h2>'
                     f'<p class="ss">The full gallery, details and floor plans are on our '
                     f'site.</p><div class="site-cta">'
                     f'<a href="{b["listing_page_url"]}" target="_blank" rel="noopener">'
                     f'View the Full Listing &rarr;</a>'
                     f'<div class="sub">caseysamson.com</div></div></div></section>\n')
        else:
            note("Full Listing link OMITTED — no listing_page_url in the buyer_portal block.")

    # ---- gallery --------------------------------------------------------
    gallery = ""
    if b.get("gallery"):
        figs = "".join(f'<figure><button type="button" class="gal-frame" data-i="{i}" '
                       f'aria-label="Enlarge: {re.sub("<[^>]+>", "", c)}">'
                       f'<img src="{f}" alt="{c}" loading="lazy"></button>'
                       f'<figcaption>{c}</figcaption></figure>'
                       for i, (f, c) in enumerate(b["gallery"]))
        gallery = (f'<section><div class="wrap"><h2 class="st">The Home</h2>'
                   f'<div class="gal">{figs}</div></div></section>\n'
                   + GALLERY_LIGHTBOX)
    else:
        note("Photo gallery OMITTED — no gallery on file.")

    values = values_section(p, b)
    snap = snapshot_section(p, b)
    # Casey, 25 Oct 2026: "market updates are seller portals not buyer" --
    # the Local Market Update stays on the seller side only.
    mkt = ""

    # ---- features -------------------------------------------------------
    features = ""
    if b.get("features"):
        # Normally {heading: [item, ...]}. A bare list is accepted too and
        # filed under one heading -- it used to raise AttributeError and
        # take the whole build down over a property-file shape.
        _feat = b["features"]
        if isinstance(_feat, list):
            _feat = {"Top Features": _feat}
            note('buyer_portal "features" was supplied as a plain list, so '
                 'it is shown under one "Top Features" heading. Use '
                 "{heading: [items]} to group it.")
        blocks = "".join(
            f'<div><h3>{h}</h3><ul>' + "".join(f"<li>{i}</li>" for i in items) + "</ul></div>"
            for h, items in _feat.items())
        features = (f'<section><div class="wrap"><h2 class="st">Features &amp; Updates</h2>'
                    f'<div class="two">{blocks}</div></div></section>\n')

    # ---- what the owners love + schools + details -----------------------
    loves = ""
    if b.get("loves"):
        li = "".join(f"<li>{x}</li>" for x in b["loves"])
        sub = []
        if b.get("schools"):
            sub.append('<div><h3>Schools</h3><p>' + "<br>".join(b["schools"]) + "</p></div>")
        if b.get("hoa_includes"):
            sub.append(f'<div><h3>HOA Includes</h3><p>{b["hoa_includes"]}</p></div>')
        if b.get("utilities"):
            sub.append(f'<div><h3>Utilities</h3><p>{b["utilities"]}</p></div>')
        subgrid = f'<div class="subgrid">{"".join(sub)}</div>' if sub else ""
        loves = (f'<section><div class="wrap"><h2 class="st">What the Owners Love</h2>'
                 f'<p class="ss">In their own words.</p>'
                 f'<div class="one"><ul>{li}</ul></div>'
                 f'{amenities_section(b)}{subgrid}</div></section>\n')

    # Casey, 12 Oct 2026: "All New buyer portals should have table with comps,
    # Customary and premium Values, on top, then pictures and premiums then
    # amenities and link from Seller portal."
    #
    # So the page argues the price before it sells the house: the comparable
    # sales and the two authenticated values come straight after the headline,
    # then the photography and the premium features, then what is nearby.
    # Authenticated Values used to sit next to last, after a buyer's agent had
    # already scrolled past everything.

    # Amenities normally nests inside What the Owners Love, above Schools.
    # With no owner quotes there is no section to nest in, so it stands alone.
    if not b.get("loves"):
        am = amenities_section(b)
        if am:
            loves = ('<section><div class="wrap">'
                     + am.replace('class="am-block"', 'class="am-block am-solo"')
                     + '</div></section>\n')

    walkto = walk_to_section(b)
    # Casey, 30 Oct 2026: "on Buyer analysis (BA), like mountington, do not
    # bring in Vienna 1 or Questions or private showing." A BA portal --
    # "buyer_analysis": true on buyer_portal -- is for another brokerage's
    # listing: no city press band and no showing/contact card.
    _ba = bool(b.get("buyer_analysis"))
    press = "" if _ba else city_press_section(p, b)
    prod = production_section(p, b)

    # ---- documents ------------------------------------------------------
    docs = ""
    if b.get("documents"):
        items = []
        for href, title, blurb in b["documents"]:
            icon = PDF_ICON if href.lower().endswith(".pdf") else WEB_ICON
            items.append(f'<a class="doc" href="{href}" target="_blank" rel="noopener">'
                         f'{icon}<div><div class="t">{title}</div>'
                         f'<div class="d">{blurb}</div></div></a>')
        note_line = (f'<p class="ss" style="margin-top:22px;">{b["showing_note"]}</p>'
                     if b.get("showing_note") else "")
        docs = (f'<section><div class="wrap"><h2 class="st">Property Documents</h2>'
                f'<p class="ss">Everything you need to review the home and write an offer.</p>'
                f'<div class="docs">{"".join(items)}</div>{note_line}</div></section>\n')

    # ---- offer terms ----------------------------------------------------
    offers = ""
    if b.get("offer_terms"):
        rows = "".join(f'<div class="row"><div class="k">{k}</div>'
                       f'<div class="v">{v}</div></div>' for k, v in b["offer_terms"])
        chips = ""
        if b.get("offer_summary"):
            chips = ('<p class="ss" style="margin:26px auto 0;">Please summarise these in '
                     'your submission email:</p><div class="chips">'
                     + "".join(f'<span class="chip">{c}</span>' for c in b["offer_summary"])
                     + "</div>")
        offers = (f'<section><div class="wrap"><h2 class="st">Writing an Offer</h2>'
                  + ('<p class="ss">For buyer agents. The full instructions are in the '
                     'documents above and in MLS.</p>' if b.get("documents") else
                     '<p class="ss">For buyer agents. The full instructions are in MLS.</p>')
                  + f'<div class="terms">{rows}</div>{chips}</div></section>\n')

    # Casey, 31 Oct 2026: the Current Market map under the comps.
    import market_map as _mm
    mktmap = ""   # Casey, 31 Oct 2026: the Current Market map is seller-portal only.
    if mktmap and not b.get("locator_map"):
        mktmap = '<link rel="stylesheet" href="leaflet.css">\n<script src="leaflet.js"></script>\n' + mktmap

    # ---- what it takes to win -------------------------------------------
    # Casey, 25 Oct 2026: the offer calculator. On sponsored portals (the
    # lender and Cardinal are its whole point) unless "win_calc": false; on
    # any other portal when "win_calc" is set.
    wincalc = ""
    # Casey, 21 Nov 2026: Move Up Calculator at the bottom of every Buyer Portal.
    import move_up as _mu
    moveup = "" if b.get("move_up") is False else _mu.section(p, mode="buyer")
    if b.get("sponsor") or b.get("win_calc"):
        import win_calc as _wc
        wincalc = _wc.html(p, b)
        if wincalc:
            _wc.write_function(out)

    # ---- contact --------------------------------------------------------
    qr = qr_block(b, p)
    # Casey, 21 Nov 2026: Buyer Portal Guide on every Buyer Portal, linked
    # from the header where The Nightmare Before Christmas used to be.
    _host = (_buyer_host(p) or "").rstrip("/")
    _guide = "" if p.get("guides") is False else (f"{_host}/Buyer_Portal_Guide.html" if _host else "Buyer_Portal_Guide.html")
    site_head = site_header(qr, hero_pdf_tile(b), _guide)
    b.setdefault("_facing", p.get("facing"))
    locmap = locator_map(b)
    # With a Current Market map, the neighbourhood map moves up beside it --
    # "Maps under the comps".
    locmap_top, locmap_low = (locmap, "") if mktmap else ("", locmap)
    lotmap = lot_map(b, b.get("display_address") or p["address"])

    contact = ""
    c = b.get("contacts")
    if c and not _ba:
        photo = (f'<img src="{c["photo"]}" alt="{re.sub("&[a-z]+;", "and", c["names"])}">'
                 if c.get("photo") else "")
        # A single agent whose name is already the card heading does not need
        # it repeated on the line below it.
        _rows = c.get("lines", [])
        _drop = len(_rows) == 1 and _rows[0][0].strip() == c["names"].strip()
        # The separator belongs between two things. An agent with no phone on
        # file was printing a bare "| email" with nothing to its left.
        def _ln(n, ph, em):
            parts = []
            if (ph or "").strip():
                parts.append(ph)
            if (em or "").strip():
                parts.append(f'<a href="mailto:{em}">{em}</a>')
            sep = ' <span style="color:var(--muted-2);">|</span> '
            head = "" if _drop else f"<b>{n}</b> "
            return f'<div class="ln">{head}{sep.join(parts)}</div>'
        lines = "".join(_ln(*r[:3]) for r in _rows)
        office = f'<div class="office">{c["office"]}</div>' if c.get("office") else ""
        contact = (f'<section><div class="wrap"><h2 class="st">Questions? Private Showing?</h2>'
                   f'<p class="ss">If you are not already working with a Realtor, we would be '
                   f'glad to show you the home.</p>'
                   f'<div class="contact{"" if photo else " solo"}">{photo}<div>'
                   f'<p class="nm">{c["names"]}</p><div class="tm">{c["team"]}</div>'
                   f'{lines}{office}</div></div></div></section>\n')

    # "The Casey Samson Team" above this line is the brand and never moves.
    # The name beneath it is a person with a direct number, so it follows the
    # listing agent — Casey, 12 Oct 2026: "Take me off Haybine." It was
    # hardcoded to Casey, which also named him on Mastery and Flynnsbrooke,
    # whose listing agents are somebody else.
    _ag = p.get("agent") or {}
    _an = (_ag.get("display") or _ag.get("lookup") or "").strip()
    if _an and _an != "Casey Samson":
        _bits = [_an]
        if (_ag.get("phone") or "").strip():
            _bits.append(_ag["phone"])
        else:
            note(f"Footer: no phone on file for {_an}, so the footer line "
                 "carries the name and email only.")
        if (_ag.get("email") or "").strip():
            _bits.append(f'<a href="mailto:{_ag["email"]}">{_ag["email"]}</a>')
        _foot_line = ('    <div class="contact-line">'
                      + '<span class="sep">|</span>'.join(_bits) + "</div>")
    else:
        _foot_line = ('    <div class="contact-line">Casey Samson'
                      '<span class="sep">|</span>703-508-2535'
                      '<span class="sep">|</span>'
                      '<a href="mailto:Casey@caseysamson.com">'
                      "Casey@caseysamson.com</a></div>")
    foot_agents = "\n".join([
        _foot_line,
        '    <div class="foot-office">Samson Properties &middot; Northern Virginia</div>',
    ])

    disclaimer = ("All information is provided by the seller to The Casey Samson Team and is "
                  "believed to be accurate, but is subject to errors and omissions and should "
                  "not be relied upon without verification. If your home is listed with another "
                  "broker this is not intended as a solicitation.")
    # Casey represents the buyer on this one. The page carries Casey Samson
    # Team branding, so it states whose listing it is -- a one-line credit,
    # no names or numbers, so it is attribution rather than the listing
    # agent's contact details.
    if b.get("listed_by"):
        disclaimer = (f'This home is listed by {b["listed_by"]}. The Casey '
                      "Samson Team represents the buyer. " + disclaimer)

    # Casey, 13 Nov 2026: "when you first generate a portal, you need to
    # include small buyer portal because this buyer portal is not complete."
    # The small page carries only what a first build always has -- the photo,
    # the facts, the description, the values, the features, how to make an
    # offer, contact and financing -- and drops every section that waits on
    # MLS photos, maps, amenities or documents.
    if SMALL:
        mktmap = locmap_top = locmap_low = lotmap = snap = mkt = video = loves = walkto = press = prod = docs = ""
        if len(b.get("gallery") or []) < 4:
            gallery = ""

    html = f"""<!-- BUYER PORTAL (public) — {addr}. Deploy to {b.get("url", "(url not set)")} -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{addr}, {city} &mdash; The Casey Samson Team</title>
<meta name="description" content="{addr}, {city}, {state}. {''.join(f'{n} bedrooms, ' for n, l in (b.get('facts') or []) if 'bed' in str(l).lower())[:40]}offered by The Casey Samson Team.">
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap');
{CSS}
</style>
</head>
<body>

{site_head}
{wip_bar}
<div class="hero{' noshot' if not hero_img.strip() else ''}">
{hero_img}
  <div class="hero-shade"></div>
  <div class="hero-inner">
    <img class="seal" src="Gold_Standard_Logo.png" alt="The Casey Samson Team">
    <div class="brandline">The Casey Samson Team</div>
    <h1>{addr}</h1>
    <p class="city">{city}, {state}</p>
    {price}
    {site_link}
  </div>
</div>

{band}{facts}{desc}{values}{mktmap}{locmap_top}{snap}{mkt}{video}{gallery}{features}{lotmap}{loves}{walkto}{locmap_low}{press}{prod}{docs}{offers}{contact}{wincalc}{moveup}
<footer>
  <div class="wrap">
    <div class="produced">The Casey Samson Team</div>
{foot_agents}
    <div class="copy">{disclaimer}<br>&copy; 2026 The Casey Samson Team LLC. All Rights Reserved.</div>
  </div>
</footer>

</body>
</html>
"""
    # Casey, 19 Oct 2026: the sample mark goes on the buyer portal too --
    # it is the page a realtor is most likely to forward before paying.
    _sp = b.get("sponsor")
    if _sp:
        html = apply_sponsor(html, _sp, out)
    if b.get("top_partners"):
        html = html.replace("</header>\n", "</header>\n" + partner_band(b["top_partners"], out), 1)
    # Casey, 23 Oct 2026: "Again this is a Sponsored Buyer Portal" -- paid
    # for by the sponsor, so no sample mark and no 72-hour clock.
    _sample = bool(p.get("sample")) and not _sp
    html = watermark.stamp(html, _sample,
                           p.get("sample_text") or ("Sample" if _sp else watermark.TEXT))
    if _sample:
        _pb = watermark.print_block()
        if _sp:   # sponsored: the print notice names no team either
            _pb = re.sub(r"\\2014 \\A Property of \\\s*the Casey Samson Team ", "", _pb)
        html = html.replace("</body>", _pb + "</body>", 1)
    if p.get("private_label"):   # Casey, 9 Nov 2026: private label
        import private_label as _pl
        html, _ = _pl.apply(html, p["private_label"], "index.html")
        _pl.copy_assets(out, p["private_label"])
        for _l in _pl.leftovers(html)[:3]:
            note(f"Private label: team name still on the buyer page: {_l}")
    (out / "index.html").write_text(html)
    # Casey, 21 Oct 2026: the 72-hour preview clock, same as the seller
    # portal, read off the same "sample_issued" so both die together.
    import expiry
    expiry.apply_folder(out, None if _sp else expiry.deadline(p, PROP_PATH, note=note),
                        note=note)
    if _sp:
        note("Sponsored: no sample mark and no expiry on the buyer portal.")


PROP_PATH = None
SMALL = False   # Casey, 13 Nov 2026: the small buyer portal pass


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: build_buyer_portal.py properties/<property>.json [--out DIR]")
    global PROP_PATH
    PROP_PATH = sys.argv[1]
    p = json.loads(Path(sys.argv[1]).read_text())
    import private_label as _plr; _plr.resolve(p)
    # The same hand-set values the seller portal reads, so the two portals
    # can never disagree about a price or a link.
    import overrides as _ov
    _ov.apply(p, note)
    p.setdefault("prefix", re.sub(r"[^A-Za-z0-9]+", "_", p["address"]).strip("_"))
    b = p.get("buyer_portal") or {}

    out = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "--out" \
        else HERE / "output" / f'{p["prefix"]}_Buyer'
    out.mkdir(parents=True, exist_ok=True)

    build(p, out)
    build_disclosures(p, b, out)

    # Assets: photos, videos and PDFs named in the block, plus the seal.
    (out / "DEPLOY.txt").write_text(
        "BUYER PORTAL  —  public, for buyers and their agents\n"
        f'{b.get("display_address") or p["address"]}, {p["city"]}, {p["state"]}\n\n'
        f"Published at:           {_buyer_url(p) or '(none)'}\n"
        f'Deploy this folder to:  {_buyer_host(p) or b.get("deploy_to") or "(no slug)"}\n\n'
        "Do NOT deploy this folder to the Seller Portal site"
        + (f'\n({p.get("portal_url")})\n' if p.get("portal_url") else "\n")
        + "\nThis folder is public. It carries no pricing strategy, no money at\n"
          "risk and no seller tracker.\n")
    shutil.copy(TPL / "Gold_Standard_Logo.png", out / "Gold_Standard_Logo.png")
    for _plat in [x for x in ((b.get("lot") or {}).get("plat"), (b.get("lot") or {}).get("plat_view")) if x]:
        _ps = HERE / (b.get("asset_dir") or p.get("asset_dir") or "") / _plat
        if _ps.exists():
            shutil.copy(_ps, out / _plat)
        else:
            note(f"Buyer portal: plat image {_plat} not found in the asset folder.")
    if p.get("guides") is not False:
        import build_portal as _bp2
        _bp2.copy_guide("buyer", out)
    # Leaflet is vendored rather than pulled from a CDN: the portal keeps
    # working if the CDN is blocked, and the version never shifts underneath
    # a live listing. Only copied when the property actually has a map.
    if (b.get("locator_map") or {}).get("pins"):
        for _lf in ("leaflet.js", "leaflet.css"):
            if (TPL / _lf).exists():
                shutil.copy(TPL / _lf, out / _lf)
            else:
                note(f"Buyer portal: {_lf} missing from templates/ — the map "
                     "will not render until it is restored.")
    # One photo folder per property: the buyer block only needs its own
    # asset_dir when its images live somewhere other than the seller's.
    src = Path(b.get("asset_dir") or p.get("asset_dir") or ".")
    if not src.is_absolute():
        src = HERE / src
    wanted = [b.get("hero_photo")]
    # The inherited hero lives in the seller's asset folder, not the buyer's.
    if not b.get("hero_photo") and p.get("hero_photo"):
        sdir = Path(p.get("asset_dir", "."))
        if not sdir.is_absolute():
            sdir = HERE / sdir
        sf = sdir / p["hero_photo"]
        if sf.exists():
            shutil.copy(sf, out / p["hero_photo"])
    wanted += [f for f, _ in b.get("gallery", [])]
    for v in b.get("videos", []):
        wanted += [v.get("file"), v.get("poster")]
    wanted += [h for h, _, _ in b.get("documents", []) if h.lower().endswith(".pdf")]
    if (b.get("contacts") or {}).get("photo"):
        wanted.append(b["contacts"]["photo"])
    for fn in [x for x in wanted if x]:
        f = src / fn
        if f.exists():
            shutil.copy(f, out / fn)
        else:
            note(f"Asset MISSING: {fn} not found in {src} — the page will reference "
                 "a broken file until you add it.")

    if b.get("pricing_pdf"):
        _src = HERE / "output" / p["prefix"] / b["pricing_pdf"]
        if _src.exists() and b.get("sponsor"):
            sponsored_report(p, b, _src, out)
        elif _src.exists():
            shutil.copy(_src, out / b["pricing_pdf"])
            # Casey, 16 Oct 2026: "Not sure why the Vintage Buyer Report is
            # still not fixed in the buyer portal." It was copied here before
            # build_portal.py had regenerated it, so the portal carried the
            # previous version of a document that had in fact been rebuilt.
            # Nothing in the copy itself can tell: the only evidence is that
            # the report is older than the property file it is built from.
            _pf = Path(getattr(p, "_source_file", "")
                       or HERE / "properties" / f'{p["prefix"].lower()}.json')
            if _pf.exists() and _src.stat().st_mtime < _pf.stat().st_mtime:
                note(f'Printable Buyer Pricing is STALE: {b["pricing_pdf"]} '
                     "is older than the property file, so the portal is "
                     "carrying a report built from earlier data. Run "
                     "build_portal.py first, then re-run this.")
        else:
            note(f'Printable Buyer Pricing MISSING: {b["pricing_pdf"]} is not in '
                 f'{_src.parent} — build the seller portal first, then re-run this.')

    # The Buyer Pricing Report is the one seller-pipeline document that is
    # meant for buyers, so it is copied across rather than linked back into
    # the private portal.
    seller_out = HERE / "output" / p["prefix"]
    for href, _, _ in b.get("documents", []):
        if href.lower().endswith(".html") and not href.endswith("Disclosures.html"):
            f = seller_out / href
            if f.exists():
                shutil.copy(f, out / href)
                stem = Path(href).stem
                for extra in (f"{stem}.pdf", "Gold_Standard_Logo.png"):
                    if (seller_out / extra).exists():
                        shutil.copy(seller_out / extra, out / extra)
            else:
                note(f"Linked page MISSING: {href} is not in {seller_out} — build the "
                     "seller portal first, then re-run this.")

    print(f"\n{p['address']} buyer portal -> {out}")
    print(f"  offered at      {money(b['list_price']) if b.get('list_price') else '(none)'}")
    print(f"  photos          {len(b.get('gallery', []))}")
    print(f"  videos          {len(b.get('videos', []))}")
    print(f"  documents       {len(b.get('documents', []))}")
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"  site size       {total / 1_048_576:.1f} MB")
    if NOTICES:
        print("\n  Omissions:")
        for m in NOTICES:
            print(f"    - {m}")
    # Casey, 13 Nov 2026: every first build includes a small buyer portal,
    # because the full buyer portal is not complete at first build. Same
    # page with the sections that wait on photos, maps and documents taken
    # out, written beside the full one as <prefix>_Buyer_Small.
    global SMALL
    if not SMALL and not (len(sys.argv) > 3 and sys.argv[2] == "--out"):
        small = out.parent / f'{p["prefix"]}_Buyer_Small'
        if small.exists():
            shutil.rmtree(small)
        shutil.copytree(out, small)
        SMALL = True
        build(p, small)
        SMALL = False
        print(f"  small portal    {small}")


if __name__ == "__main__":
    main()
    # Casey, 22 Nov 2026: "when I create a portal, lets create the guides as
    # well" -- each portal gets its own four guides from its own pages.
    try:
        import json as _j, property_guides as _pg
        _a = [x for x in sys.argv[1:] if x.endswith(".json")]
        if _a:
            _made = _pg.build(_j.loads(Path(_a[0]).read_text()), ("buyer",))
            print("  Guides:", ", ".join(_made) or "none")
    except Exception as _e:
        print("  Guides: skipped --", _e)
    # Casey, 24 Nov 2026: town home markets link to the town home MSS.
    try:
        import json as _j, townhome_mss as _th
        _a = [x for x in sys.argv[1:] if x.endswith(".json")]
        if _a:
            _fx = _th.fix_outputs(_j.loads(Path(_a[0]).read_text()))
            if _fx:
                print(f"  Town home MSS: links pointed at {_th.TH_SITE} in {len(set(_fx))} file(s)")
    except Exception as _e:
        print("  Town home MSS: skipped --", _e)
