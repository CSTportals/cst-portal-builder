"""Marketing and Contract Negotiating sections on the Seller Roadmap.

Casey, 27 Nov 2026: "Add Marketing section and Contract negotiating section
I will edit those." Shown on the Sample until the wording is final; a
property turns them on with "roadmap_sections": true. The text below is a
placeholder -- replace it with Casey's wording.
"""

SECTIONS = [
    ("Marketing", "How the home reaches every qualified buyer.",
     ["Casey&rsquo;s marketing plan goes here."]),
    ("Contract Negotiating", "Turning interest into the strongest contract.",
     ["Casey&rsquo;s contract negotiating plan goes here."]),
]


def enabled(p):
    return bool(p.get("roadmap_sections") or p.get("prefix") == "Sample")


def html(p):
    if not enabled(p):
        return ""
    out = ""
    for title, sub, paras in SECTIONS:
        out += ('<section><div class="wrap">'
                f'<h2 class="section-title">{title}</h2>'
                f'<p class="section-sub">{sub}</p>'
                + "".join(f'<p class="price-para">{x}</p>' for x in paras)
                + '</div></section>\n')
    return out
