#!/usr/bin/env python3
"""The 72-hour preview: every link goes dead three days after the portal is issued.

Casey, 21 Oct 2026: "When 3 days goes by, I want to Disable all links."

A sample portal (``"sample": true`` on the property file) is issued with a
clock. The first build stamps ``"sample_issued"`` on the property file, and
every later build reads it back, so a rebuild never restarts the clock.
Seventy-two hours after that moment, every page in the seller folder and the
buyer folder:

  * switches off every link -- no href, no click, faded;
  * switches off the photo viewer and every button;
  * puts a bar across the top: "This preview expired on <date>." plus one
    working line to Casey, so the agent still knows who to call.

Settings on the property file:

    "sample": true                      -- turns the clock on
    "sample_issued": "2026-10-21T08:14:00-04:00"   -- written by the first build
    "sample_hours": 72                  -- optional, the length of the preview
    "expires": "2026-10-30T17:00:00-04:00"  -- optional, a hand-set end instead
    "expires": false                    -- optional, no clock on a sample

Clear "sample" (the portal is paid for) and rebuild: the clock comes off
every page, the same way the sample mark does.

WHAT THIS IS, AND WHAT IT IS NOT

It runs in the reader's browser, against the reader's clock. It stops the
portal working for anyone who opens it the ordinary way, which is everyone
it is sent to. It does NOT stop someone who already downloaded a PDF, who
types a PDF's address in directly, or who strips the script out of a saved
copy. Taking a site down for good is done in Netlify, not here.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MARKER = "cst-exp"
ET = ZoneInfo("America/New_York")
HOURS = 72

_BLOCK_RE = re.compile(r"<!--cst-exp-->.*?<!--/cst-exp-->", re.S)


def deadline(p, prop_path=None, note=print):
    """When this portal's links go dead, or None for no clock.

    Writes "sample_issued" back to the property file the first time, so the
    clock is set once and survives every rebuild.
    """
    if not p.get("sample"):
        return None
    exp = p.get("expires")
    if exp is False:
        note('Expiry: OFF — "expires": false on a sample portal.')
        return None
    if exp:
        return datetime.fromisoformat(exp)
    issued = p.get("sample_issued")
    if not issued:
        now = datetime.now(ET).replace(second=0, microsecond=0)
        issued = now.isoformat()
        p["sample_issued"] = issued
        if prop_path:
            raw = json.loads(Path(prop_path).read_text())
            raw["sample_issued"] = issued
            Path(prop_path).write_text(json.dumps(raw, indent=1, ensure_ascii=False))
            note(f"Expiry: clock started — sample_issued {issued} written to "
                 f"{Path(prop_path).name}. Rebuilds keep this time.")
    hours = p.get("sample_hours") or HOURS
    return datetime.fromisoformat(issued) + timedelta(hours=hours)


def _label(dt):
    d = dt.astimezone(ET)
    hour = d.strftime("%I:%M %p").lstrip("0")
    return f'{d.strftime("%A, %B")} {d.day}, {d.year} at {hour}'


def block(dt):
    """The script and bar dropped in before </body>."""
    iso = dt.isoformat()
    when = _label(dt)
    return f"""<!--cst-exp--><script id="{MARKER}">
(function(){{
  var END=Date.parse("{iso}");
  if(isNaN(END)||Date.now()<END) return;
  function off(){{
    var css=document.createElement('style');
    css.textContent='a.cst-dead{{pointer-events:none!important;cursor:default!important;opacity:.45;text-decoration:none!important}}'
      +'#cst-exp-bar{{position:sticky;top:0;z-index:4000;background:#221C14;color:#F1EBDA;'
      +'text-align:center;font:600 14px/1.45 Georgia,serif;padding:12px 16px;letter-spacing:.02em}}'
      +'#cst-exp-bar a{{color:#D3B978;white-space:nowrap}}'
      +'.gal-frame,button{{pointer-events:none!important;cursor:default!important}}'
      +'div.feat:has(a.cst-dead),.card:has(a.cst-dead){{opacity:.45}}'
      +'div.feat a.cst-dead,.card a.cst-dead{{opacity:1}}';
    document.head.appendChild(css);
    [].forEach.call(document.querySelectorAll('a'),function(a){{
      if(a.closest('#cst-exp-bar')) return;
      a.removeAttribute('href'); a.removeAttribute('target'); a.removeAttribute('onclick');
      a.setAttribute('aria-disabled','true'); a.setAttribute('tabindex','-1');
      a.classList.add('cst-dead');
    }});
    [].forEach.call(document.querySelectorAll('button,input,select,textarea'),function(b){{
      b.disabled=true;
    }});
    var bar=document.createElement('div'); bar.id='cst-exp-bar';
    bar.innerHTML='This preview expired on {when}. To activate it, call Casey Samson at '
      +'<a href="tel:7035082535">703-508-2535</a> or email '
      +'<a href="mailto:casey@caseysamson.com">casey@caseysamson.com</a>.';
    document.body.insertBefore(bar, document.body.firstChild);
    document.addEventListener('click',function(e){{
      var a=e.target.closest&&e.target.closest('a');
      if(a&&!a.closest('#cst-exp-bar')){{e.preventDefault();e.stopPropagation();}}
    }},true);
  }}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',off); else off();
}})();
</script><!--/cst-exp-->"""


def stamp(html, dt):
    """Put the clock on one page (or take it off when dt is None)."""
    html = _BLOCK_RE.sub("", html)
    if dt is None:
        return html
    if "</body>" in html:
        return html.replace("</body>", block(dt) + "\n</body>", 1)
    return html + block(dt)


def apply_folder(out, dt, note=print):
    """Every .html page in a built portal folder gets the clock, or loses it."""
    n = 0
    for f in sorted(Path(out).glob("*.html")):
        if "_Email" in f.name:   # incl. 00_Realtor_Email_<pre>.html
            continue   # email bodies are pasted into mail, not served
        old = f.read_text(encoding="utf-8")
        new = stamp(old, dt)
        if new != old:
            f.write_text(new, encoding="utf-8")
        n += 1
    if dt is None:
        return
    note(f"Expiry: all links on {n} pages in {Path(out).name} go dead at "
         f"{_label(dt)}. PDFs already downloaded, or opened "
         "by typing their address, are not affected.")
