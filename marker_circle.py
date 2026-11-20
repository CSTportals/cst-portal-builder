"""Hand-drawn marker circle around the numbers Casey wants buyers and
sellers to notice (Casey, 8 Nov 2026): "make it look like we drew a circle
around a number with a magic marker like the 74% in our track record and the
% of listings sold of the homes listed in the last 30 days".

apply(html) wraps those numbers in <span class="mk"> and adds the CSS once.
"""
import re
import urllib.parse

# A loose, slightly-overshooting loop, like a marker stroke that doesn't
# quite close where it started.
_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" preserveAspectRatio="none">'
        '<path d="M150 14 C118 2 52 4 22 26 C2 41 6 72 40 85 C80 99 152 96 182 74 '
        'C203 58 196 26 160 14 C132 5 96 8 74 12" fill="none" stroke="#C8202E" stroke-width="4.2" '
        'stroke-linecap="round" stroke-linejoin="round" opacity=".88"/></svg>')
_URI = "data:image/svg+xml," + urllib.parse.quote(_SVG)

CSS = ("<style id=\"mk-css\">.mk{position:relative;display:inline-block;padding:0 .14em;z-index:0}"
       ".mk::after{content:'';position:absolute;left:-.42em;right:-.42em;top:-.36em;bottom:-.36em;"
       f"background:url(\"{_URI}\") no-repeat center/100% 100%;pointer-events:none;z-index:-1;"
       "transform:rotate(-3deg)}"
       "@media print{.mk::after{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style>")

PATTERNS = [
    # team track record: "Sold above list price (25 of 34)" -- seller portal band
    (r'(<span class="n">)([^<]+?)(</span><div class="l">Sold above list price \()', 2),
    # same cell on the Pricing Strategy Summary
    (r'(<span class="tr-n">)([^<]+?)(</span><span class="tr-l">Sold above list price \()', 2),
    # market conditions: % of homes listed in the last 30 days that went under contract
    (r'(<div class="cmi-n">)([^<]+?)(</div><div class="cmi-d">Of homes listed in the last 30 days)', 2),
    (r'(</svg>)(\d+%)(</div><div class="ps-tile-t">Under Contract \(Last 30 Days\))', 2),
]


def apply(html):
    n = 0
    for pat, _ in PATTERNS:
        html, k = re.subn(pat, lambda m: f'{m.group(1)}<span class="mk">{m.group(2)}</span>{m.group(3)}', html)
        n += k
    if n and 'id="mk-css"' not in html:
        html = html.replace("</head>", CSS + "\n</head>", 1)
    return html, n


def apply_dir(folder):
    from pathlib import Path
    total = 0
    for f in Path(folder).glob("*.html"):
        t = f.read_text()
        t2, n = apply(t)
        if n:
            f.write_text(t2)
            total += n
    return total
