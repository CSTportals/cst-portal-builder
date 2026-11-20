"""Save-and-share bar on the Seller Portal and the Seller Roadmap.

Casey, 13 Nov 2026: "Is there something you could add that would encourage
them to bookmark the portal or roadmap" -- then "add 1 and 3 to courthouse":

  1. "Save to your Home Screen": a slim bar with the steps for the device
     the seller is on (iPhone, Android, computer), plus a home-screen icon
     (the gold seal) and a short name, so a saved portal sits beside their
     apps. Hidden once dismissed or when already opened from the home screen.
  3. "Text me this link": sends the page's published address to themselves
     by text (phone) or email (computer), or the share sheet where offered.

The bar links the published address (seller_host), never location.href, so
a copy opened from a file or a forwarded preview still sends the real link.
Screen only: @media print hides it, so the PDFs never carry it.

apply(out, p, url) is idempotent: it strips an earlier bar before adding.
"""
import json
import re
from pathlib import Path

PAGES = ("index.html", "_Roadmap.html")

CSS = """<style id="cst-save-css">
.cst-save{background:#221C14;color:#F1EBDA;font:500 14px/1.45 'Lora',Georgia,serif;position:relative;z-index:50}
.cst-save .w{max-width:1040px;margin:0 auto;padding:10px 44px 10px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px}
.cst-save b{color:#D3B978;font-weight:600}
.cst-save .msg{flex:1 1 260px}
.cst-save .how{display:none;flex-basis:100%;font-size:13px;color:#E4DCC8}
.cst-save.open .how{display:block}
.cst-save button{font:600 12.5px/1 'Lora',Georgia,serif;letter-spacing:.04em;border-radius:999px;padding:8px 14px;cursor:pointer;white-space:nowrap}
.cst-save .b1{background:#D3B978;color:#221C14;border:1px solid #D3B978}
.cst-save .b2{background:transparent;color:#F1EBDA;border:1px solid #8A6A2E}
.cst-save .x{position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:0;color:#B8AE98;font-size:20px;padding:4px 8px;line-height:1}
.cst-save .ok{display:none;font-size:13px;color:#D3B978}
@media print{.cst-save{display:none!important}}
</style>"""

BAR = """<div class="cst-save" id="cstSave" role="region" aria-label="Save this page">
<div class="w">
<span class="msg"><b>&#9733; Save your {what}</b> &mdash; it&rsquo;s your home&rsquo;s live plan, and the market data updates every week.</span>
<button type="button" class="b1" id="cstSaveHow">Save to my phone</button>
<button type="button" class="b2" id="cstSaveSend">Text me this link</button>
<span class="ok" id="cstSaveOk"></span>
<div class="how" id="cstSaveSteps"></div>
</div>
<button type="button" class="x" id="cstSaveX" aria-label="Hide">&times;</button>
</div>
<script>(function(){{
var URL_={url}, NAME={name}, KEY="cst-save-hidden-"+{slug};
var bar=document.getElementById('cstSave'); if(!bar)return;
function get(){{try{{return localStorage.getItem(KEY);}}catch(e){{return null;}}}}
function put(v){{try{{localStorage.setItem(KEY,v);}}catch(e){{}}}}
var standalone=(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone;
if(standalone||get()==='1'){{bar.style.display='none';return;}}
var ua=navigator.userAgent||'', ios=/iPhone|iPad|iPod/.test(ua)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1),
    android=/Android/.test(ua), phone=ios||android, mac=/Mac/.test(navigator.platform||ua);
var how=document.getElementById('cstSaveHow'), steps=document.getElementById('cstSaveSteps');
if(!phone)how.textContent='Bookmark this page';
var deferred=null;
window.addEventListener('beforeinstallprompt',function(e){{e.preventDefault();deferred=e;}});
how.addEventListener('click',function(){{
  if(deferred){{deferred.prompt();deferred=null;return;}}
  steps.innerHTML= ios ? 'On iPhone or iPad: tap the <b>Share</b> button (the square with the arrow), scroll down, and tap <b>Add to Home Screen</b>. Your portal appears beside your apps as &ldquo;'+NAME+'&rdquo;.'
    : android ? 'On Android: tap the <b>&#8942;</b> menu at the top right, then <b>Add to Home screen</b>. Your portal appears beside your apps as &ldquo;'+NAME+'&rdquo;.'
    : 'Press <b>'+(mac?'&#8984; Command + D':'Ctrl + D')+'</b> to bookmark this page, or use <b>Text me this link</b> to put it on your phone.';
  bar.classList.toggle('open');
}});
document.getElementById('cstSaveSend').addEventListener('click',function(){{
  var body='My Seller Portal for '+NAME+': '+URL_;
  if(navigator.share&&phone){{navigator.share({{title:NAME+' Seller Portal',text:body,url:URL_}}).catch(function(){{}});return;}}
  location.href= phone ? (ios?'sms:&body=':'sms:?body=')+encodeURIComponent(body)
    : 'mailto:?subject='+encodeURIComponent('My Seller Portal: '+NAME)+'&body='+encodeURIComponent(body);
}});
document.getElementById('cstSaveX').addEventListener('click',function(){{bar.style.display='none';put('1');}});
}})();</script>
"""


def _icons(out, short):
    """Home-screen icon (the gold seal on cream) and the web manifest."""
    from PIL import Image
    src = Path(__file__).parent / "templates" / "Gold_Standard_Logo.png"
    if not src.exists():
        return False
    seal = Image.open(src).convert("RGBA")
    for size, name in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        bg = Image.new("RGBA", (size, size), (34, 28, 20, 255))
        s = seal.resize((int(size * .78),) * 2, Image.LANCZOS)
        bg.alpha_composite(s, ((size - s.width) // 2, (size - s.height) // 2))
        bg.convert("RGB").save(Path(out) / name)
    (Path(out) / "site.webmanifest").write_text(json.dumps({
        "name": f"{short} Seller Portal", "short_name": short, "start_url": "./",
        "display": "browser", "background_color": "#FAF7F0", "theme_color": "#221C14",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=1))
    return True


def apply(out, p, url, note=print):
    out = Path(out)
    if not url:
        note("Save bar OMITTED -- no published address for the Seller Portal.")
        return 0
    short = p.get("bookmark_name") or p["address"].replace(" Road", " Rd")
    short = re.sub(r"\s+(Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|St|Street|Ave|Avenue|Way|Pl|Place|Cir|Circle|Ter|Terrace)$", "", short)
    has_icons = _icons(out, short)
    head = (f'<link rel="apple-touch-icon" href="apple-touch-icon.png">'
            f'<link rel="manifest" href="site.webmanifest">'
            f'<meta name="apple-mobile-web-app-title" content="{short}">'
            f'<meta name="theme-color" content="#221C14">') if has_icons else ""
    root = url.rstrip("/")
    n = 0
    for f in out.glob("*.html"):
        if not (f.name == "index.html" or f.name.endswith("_Roadmap.html")):
            continue
        h = f.read_text(encoding="utf-8")
        h = re.sub(r'<style id="cst-save-css">.*?</style>|<!--cst-save-head-->.*?<!--/cst-save-head-->|'
                   r'<!--cst-save-->.*?<!--/cst-save-->\n?', "", h, flags=re.S)
        page = root + "/" if f.name == "index.html" else f"{root}/{f.name}"
        what = "Seller Portal" if f.name == "index.html" else "Seller Roadmap"
        bar = BAR.format(what=what, url=json.dumps(page), name=json.dumps(short),
                         slug=json.dumps(p["prefix"]))
        h = h.replace("</head>", f"<!--cst-save-head-->{head}{CSS}<!--/cst-save-head-->\n</head>", 1)
        h = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n<!--cst-save-->" + bar + "<!--/cst-save-->\n", h, count=1)
        f.write_text(h, encoding="utf-8")
        n += 1
    note(f"Save bar (save to phone + text me this link) on {n} page(s); icon name \"{short}\".")
    return n
