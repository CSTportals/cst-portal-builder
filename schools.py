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


def row_html(p, cls="sch-row"):
    s = schools_of(p)
    if not s:
        return ""
    cells = "".join(f'<div class="sch"><span class="sl">{lab}</span><span class="sn">{_short(n)}</span></div>'
                    for lab, n in s)
    return f'<div class="{cls}">{cells}</div>'


CSS = (".sch-row{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 0;margin-top:10px;"
       "padding-top:10px;border-top:1px solid #E4DCC8}"
       ".sch-row .sch{flex:1 1 160px;text-align:center;padding:2px 8px}"
       ".sch-row .sl{display:block;font:700 10.5px Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:#8A6A2E}"
       ".sch-row .sn{display:block;font-family:'Playfair Display',Georgia,serif;font-size:18px;font-weight:700;color:#1F2A44}")
