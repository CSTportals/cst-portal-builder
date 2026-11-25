"""Casey, 25 Nov 2026: "the first thing people need to see is elementary,
intermediate and high school. Put it in same box but under size, age,
assessment etc. on both roadmap and buyer portal."

Source: the property's buyer_portal "schools" list (elementary, middle, high
in that order; extra lines such as AAP centers are ignored here), or a
top-level "schools" dict {"elementary": ..., "middle": ..., "high": ...}.
"""
import re

LEVELS = (("elementary", "Elementary"), ("middle", "Middle"), ("high", "High"))


def _short(name):
    return re.sub(r"\s+(Elementary|Middle|High)(\s+School)?\s*$", "", name.strip(), flags=re.I) or name


def schools_of(p):
    """[(label, school name)] for elementary, middle, high -- whatever is known."""
    d = p.get("schools") if isinstance(p.get("schools"), dict) else None
    out = []
    if d:
        for k, lab in LEVELS:
            if d.get(k):
                out.append((lab, d[k]))
        return out
    lst = [x for x in ((p.get("buyer_portal") or {}).get("schools") or []) if isinstance(x, str)]
    for k, lab in LEVELS:
        hit = next((x for x in lst if re.search(rf"\b{k}\b", x, re.I) and ":" not in x
                    and "private" not in x.lower()), None)
        if hit:
            out.append((lab, hit))
    return out


def ratings_of(p):
    """Casey, 25 Nov 2026: GreatSchools ratings, from GreatSchools itself.
    buyer_portal.school_ratings: {"<school name as listed>": 10, ...}."""
    return (p.get("buyer_portal") or {}).get("school_ratings") or {}


def row_html(p, cls="sch-row"):
    s = schools_of(p)
    if not s:
        return ""
    r = ratings_of(p)
    def _rt(n):
        v = r.get(n) or r.get(_short(n))
        return f'<span class="sr">GreatSchools {v}/10</span>' if v else ""
    cells = "".join(f'<div class="sch"><span class="sl">{lab}</span><span class="sn">{_short(n)}</span>{_rt(n)}</div>'
                    for lab, n in s)
    src = ""
    if r:
        yr = (p.get("buyer_portal") or {}).get("school_ratings_year") or ""
        src = f'<div class="sch-src">GreatSchools ratings{(" &middot; " + str(yr)) if yr else ""}</div>'
    return f'<div class="{cls}">{cells}{src}</div>'


CSS = (".sch-row{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 0;margin-top:10px;"
       "padding-top:10px;border-top:1px solid #E4DCC8}"
       ".sch-row .sch{flex:1 1 160px;text-align:center;padding:2px 8px}"
       ".sch-row .sl{display:block;font:700 10.5px Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:#8A6A2E}"
       ".sch-row .sn{display:block;font-family:'Playfair Display',Georgia,serif;font-size:18px;font-weight:700;color:#1F2A44}"
       ".sch-row .sr{display:block;font:600 12.5px Georgia,serif;color:#8A6A2E;margin-top:2px}"
       ".sch-row .sch-src{flex:1 1 100%;text-align:center;font:italic 11px Georgia,serif;color:#71695A;margin-top:4px}")
