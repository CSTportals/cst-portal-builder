"""Private label: portals presented under another agent's name, powered by
CST Pricing (Casey, 9 Nov 2026: "we are going to be private labeling for
agents. Instead of Casey Samson Team it will be another agent powered by CST
Pricing").

Casey's answers, 9 Nov 2026:
  - track record stays CST's, labeled as CST ("CST Pricing Results");
  - a "Powered by CST Pricing" tag sits under the agent's name wherever the
    team name stood as a brand (headers, footers, title bars);
  - Gold Standard(TM) names and the seal stay; the copyright stays with
    The Casey Samson Team LLC (it is CST's work and its protection).

Property file:
    "private_label": {"name": "Jane Agent", "team": "Jane Agent Group",
                      "phone": "703-555-0100", "email": "jane@example.com",
                      "website": "janeagent.com", "office": "Samson Properties"}
Only "name" is required; "team" (if given) is the brand line, otherwise the
name is. Contact fields replace Casey's wherever they appear.

apply_dir(folder, pl) rewrites every page in an output folder; the builders
call it before the PDFs are printed and again at the end.
"""
import re
from pathlib import Path

TAG = "Powered by CST Pricing"
CST = "CST Pricing"
SKIP = ("00_Realtor_Email",)            # the realtor email is CST talking to agents
CST_PAGES = ("Track_Record", "CST_Resales", "Portfolio", "MSS_Map")   # CST's record / CST's stats

_CSS = ('<style id="pl-css">.pl-tag{display:block;font-size:.58em;letter-spacing:.16em;'
        'text-transform:uppercase;opacity:.82;margin-top:.35em;font-weight:600}</style>')

_KEEP = [r"The Casey Samson Team LLC", r"CST-FP [^>]*?\(c\) The Casey Samson Team LLC"]


AGENTS = Path(__file__).resolve().parent / "pl_agents.json"


def resolve(p):
    """Casey, 20 Nov 2026: PL agents are saved once as tags in pl_agents.json.
    "private_label": "ferris_eways" (or {"tag": ..., overrides}) expands to the
    full block in place; a full dict with no tag passes through unchanged."""
    import json
    pl = p.get("private_label")
    if not pl:
        return p
    tag = pl if isinstance(pl, str) else pl.get("tag")
    if tag:
        reg = json.loads(AGENTS.read_text(encoding="utf-8"))
        if tag not in reg:
            raise SystemExit(f"private_label tag '{tag}' not in pl_agents.json "
                             f"(known: {', '.join(k for k in reg if not k.startswith('_'))})")
        full = dict(reg[tag])
        if isinstance(pl, dict):
            full.update({k: v for k, v in pl.items() if k != "tag"})
        full["tag"] = tag
        p["private_label"] = full
    return p


def _brand(pl):
    return pl.get("team") or pl["name"]


def apply(html, pl, fname=""):
    if any(fname.startswith(s) for s in SKIP):
        return html, 0
    before = html
    brand = _brand(pl)
    # protect the copyright and fingerprint
    kept = {}
    def _hold(m):
        k = f"\x00{len(kept)}\x00"
        kept[k] = m.group(0)
        return k
    for pat in _KEEP:
        html = re.sub(pat, _hold, html)

    if any(fname.startswith(s) for s in CST_PAGES):
        # CST's own record and market stats: label them CST, not the agent
        html = re.sub(r"(?:[Tt]he )?Casey Samson Team", CST, html)
    else:
        # CST-labeled items on the agent's pages
        for a, b in [
            # the track-record band title stays CST's (Casey, 15 Nov 2026)
            ("The Casey Samson Team &mdash; The Gold Standard of Listing Strategies",
             f"{CST} &mdash; The Gold Standard of Listing Strategies"),
            ("The Casey Samson Team &mdash; $1.5 million", f"{CST} Results &mdash; $1.5 million"),
            ("The Casey Samson Team &mdash; Track Record", f"{CST} &mdash; Track Record"),
            ("Casey Samson Team &mdash; Track Record", f"{CST} &mdash; Track Record"),
            ("Authenticated by the Casey Samson Team", f"Authenticated by {CST}"),
            ("authenticate the Casey Samson Team value range", f"authenticate the {CST} value range"),
            ("summary of the Casey Samson Team Pricing Strategy", f"summary of the {CST} Strategy"),
            ("The Casey Samson Team (CST) is a seven-agent", f"{CST} is backed by the Casey&#32;Samson Team (CST), a seven-agent"),
            # (&#32; keeps the running-text swap below from turning CST's
            # own name into the agent's -- Themis read "backed by Ferris
            # Eways (CST), a seven-agent team". Caught 23 Nov 2026.)
        ]:
            html = html.replace(a, b)
        # title bar
        html = re.sub(r"(?:[Tt]he )?Casey Samson Team(</title>)", f"{brand} &middot; {TAG}\\1", html)
        # attributes (alt, meta description): plain text only
        html = re.sub(r'((?:alt|content|aria-label|title)="[^"]*?)(?:[Tt]he )?Casey Samson Team',
                      lambda m: m.group(1) + brand, html)
        # "Produced by ..."
        html = html.replace("Produced by The Casey Samson Team", f"Produced by {brand} &middot; {TAG}")
        # the team name standing alone as a brand line -> agent + tag
        html = re.sub(r">\s*(?:[Tt]he )?Casey Samson Team\s*<",
                      f'>{brand}<span class="pl-tag">{TAG}</span><', html)
        # everything else in running text
        html = re.sub(r"(?:[Tt]he )?Casey Samson Team", brand, html)
        # CSS for the tag
        if 'class="pl-tag"' in html and 'id="pl-css"' not in html:
            html = html.replace("</head>", _CSS + "</head>", 1)
        # Casey, 19 Nov 2026: "Make PL name bigger in seller portal."
        if ('class="label">Seller Portal' in html and 'class="brandline"' in html
                and 'id="pl-big"' not in html):
            html = html.replace("</head>", '<style id="pl-big">.hero .brandline{font-size:26px;'
                                'letter-spacing:.12em;line-height:1.25;margin-bottom:6px}'
                                '.hero .brandline .pl-tag{font-size:12px;letter-spacing:.2em;'
                                'margin-top:.45em}</style></head>', 1)

    # contacts, only when the agent is someone else
    if pl["name"] != "Casey Samson":
        html = re.sub(r"Casey Samson(?! Team)", pl["name"], html)
    for old, key in (("703-508-2535", "phone"), ("703.508.2535", "phone"),
                     ("Casey@caseysamson.com", "email"), ("casey@caseysamson.com", "email")):
        if pl.get(key):
            html = html.replace(old, pl[key])
    if pl.get("website") and pl["website"] != "caseysamson.com":
        html = re.sub(r"(?<![/\w.])caseysamson\.com(?![/\w])", pl["website"], html)

    for k, v in kept.items():
        html = html.replace(k, v)
    return html, int(html != before)


def leftovers(html):
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", html, flags=re.S)
    return [m for m in re.findall(r"[^>]{0,30}Casey Samson Team[^<]{0,20}", body)
            if "LLC" not in m]


def apply_dir(folder, pl):
    n, left = 0, {}
    for f in Path(folder).glob("*.html"):
        t = f.read_text(encoding="utf-8")
        t2, k = apply(t, pl, f.name)
        if k:
            f.write_text(t2, encoding="utf-8")
            n += 1
        if not any(f.name.startswith(s) for s in SKIP + CST_PAGES):
            lo = leftovers(t2)
            if lo:
                left[f.name] = lo
    return n, left


def copy_assets(out, pl):
    """The agent's logo (pl["logo"], a file path) into the folder, if given."""
    import shutil
    src = pl.get("logo")
    if src and Path(src).exists():
        shutil.copy(src, Path(out) / Path(src).name)
        return Path(src).name
    return None


def letterhead(pl):
    """Casey, 15 Nov 2026: the agent's letterhead ("From the desk of ...") is
    the signature line at the bottom of the seller portal and the Roadmap."""
    lines = [pl.get("team_name") or "", pl.get("title") or "REALTOR&reg;",
             pl.get("office") or "Samson Properties", pl.get("address") or ""]
    contact = " &middot; ".join(x for x in (
        f'Cell: {pl["phone"]}' if pl.get("phone") else "",
        f'Office: {pl["office_phone"]}' if pl.get("office_phone") else "") if x)
    web = " &middot; ".join(x for x in (
        f'<a href="mailto:{pl["email"]}">{pl["email"]}</a>' if pl.get("email") else "",
        f'<a href="https://{pl["website"]}">{pl["website"]}</a>' if pl.get("website") else "",
        pl.get("extra") or "") if x)
    acc = "".join(f"<div>{x}</div>" for x in pl.get("accolades") or [])
    acc = (f'<div style="margin-top:10px;font-size:13px;color:#4A4234;">{acc}</div>' if acc else "")
    tail = "".join(x for x in (
        f'<div style="margin-top:8px;font-style:italic;">{pl["closing"]}</div>' if pl.get("closing") else "",
        f'<div><a href="{pl["review_url"]}">Please leave a kind review</a></div>' if pl.get("review_url") else ""))
    logo = (f'<img src="{Path(pl["logo"]).name}" alt="{_brand(pl)}" style="max-height:60px;margin-bottom:8px;"><br>'
            if pl.get("logo") else "")
    return ('<div id="pl-letterhead" style="max-width:760px;margin:30px auto 24px;padding:18px 22px;'
            'border-top:2px solid #D3B978;text-align:center;font:14px/1.6 Lora,Georgia,serif;color:#221C14;">'
            f'{logo}<div style="font-style:italic;color:#71695A;">From the desk of</div>'
            f'<div style="font:600 20px \'Playfair Display\',Georgia,serif;">{pl["name"]}</div>'
            + "".join(f"<div>{x}</div>" for x in lines if x)
            + (f"<div>{contact}</div>" if contact else "")
            + (f"<div>{web}</div>" if web else "")
            + acc + tail
            + f'<div style="margin-top:8px;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#8A6A2E;">{TAG}</div>'
            '</div>')


def add_letterhead(folder, pl):
    n = 0
    for f in Path(folder).glob("*.html"):
        if not (f.name == "index.html" or f.name.endswith("_Roadmap.html")):
            continue
        t = f.read_text(encoding="utf-8")
        t = re.sub(r'<div id="pl-letterhead".*?</div></div>', "", t, flags=re.S)
        i = t.rfind("</body>")
        if i > 0:
            f.write_text(t[:i] + letterhead(pl) + "\n" + t[i:], encoding="utf-8")
            n += 1
    return n
