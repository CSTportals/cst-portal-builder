"""Town home Market Snapshot support (Casey, 24 Nov 2026: "Townhome MSS").

The town home MSS is published at csttownhomes.netlify.app and uses the same
page names as the detached MSS (cstmarketupdate.netlify.app). So:

  * its weekly pages are saved in mss_pages_townhome/ (not mss_pages/);
  * refresh_cache_from_mss.py caches them under "TH_" + page name;
  * a town home property points its market block at that key, e.g.
        "market": {"name": "Prince William County Town Home Market",
                   "slug": "TH_Prince_William_County_Market_Snapshot"}
  * at the end of each build, fix_outputs() rewrites the Market Snapshot links
    the builder wrote for the detached site to the town home site.

Weekly update: copy the town home package's *_Market_Snapshot.html pages into
mss_pages_townhome/, save its map_embed.html as templates/MSS_Map_Townhome.html
(keep the ?seg= / resize snippet), run refresh_cache_from_mss.py, commit.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TH_SITE = "https://csttownhomes.netlify.app"
DETACHED_SITE = "https://cstmarketupdate.netlify.app"
PREFIX = "TH_"


def is_th_slug(slug):
    return bool(slug) and str(slug).upper().startswith(PREFIX)


def is_th(p):
    return is_th_slug(((p or {}).get("market") or {}).get("slug"))


def page_name(slug):
    """The page's own name on the town home site / in mss_pages_townhome."""
    return slug[len(PREFIX):] if is_th_slug(slug) else slug


def mss_page(slug):
    """Saved MSS page for a market key, from the right package folder."""
    if not slug:
        return None
    if is_th_slug(slug):
        return HERE / "mss_pages_townhome" / f"{page_name(slug)}.html"
    return HERE / "mss_pages" / f"{slug}.html"


def map_template(p):
    t = "MSS_Map_Townhome.html" if is_th(p) else "MSS_Map.html"
    return HERE / "templates" / t


_TH_LINK = re.compile(r"https://cstmarketupdate\.netlify\.app/th_([A-Za-z0-9_]+?)(?:\.html)?(?=[\"'#?\s<)&]|$)",
                      re.I)


def fix_text(s):
    s = _TH_LINK.sub(lambda m: f"{TH_SITE}/{m.group(1).lower()}", s)
    # The general MSS links (navigator, home page) go to the town home site.
    s = s.replace(f"{DETACHED_SITE}/index.html", f"{TH_SITE}/")
    s = s.replace(f"{DETACHED_SITE}/#", f"{TH_SITE}/#")
    s = re.sub(re.escape(DETACHED_SITE) + r"/(?=[\"'\s<])", TH_SITE + "/", s)
    return s


def fix_outputs(p, out_root=None):
    """Point every Market Snapshot link in this property's sites at the town
    home MSS. No-op for a detached market. Returns the files changed."""
    if not is_th(p):
        return []
    root = Path(out_root) if out_root else HERE / "output"
    pre = p.get("prefix", "")
    changed = []
    for d in (root / pre, root / f"{pre}_Buyer", root / f"{pre}_Buyer_Small"):
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() not in (".html", ".eml", ".txt", ".js", ".toml"):
                continue
            if f.suffix.lower() == ".eml":
                if _fix_eml(f):
                    changed.append(f.name)
                continue
            s = f.read_text(encoding="utf-8", errors="ignore")
            n = fix_text(s)
            if n != s:
                f.write_text(n, encoding="utf-8")
                changed.append(f.name)
    return changed


def _fix_eml(f):
    """Emails are quoted-printable, so links wrap across lines; decode each
    text part, fix it and write it back."""
    import email
    from email import policy
    msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
    hit = False
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.is_multipart():
            continue
        s = part.get_content()
        n = fix_text(s)
        if n != s:
            part.set_content(n, subtype=part.get_content_subtype(), charset="utf-8",
                             cte="quoted-printable")
            hit = True
    if hit:
        f.write_bytes(msg.as_bytes(policy=policy.default))
    return hit
