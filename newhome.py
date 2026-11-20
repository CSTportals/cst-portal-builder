"""New-construction wording (Casey, 13 Nov 2026, 606 Meadow Ln SW: "New Home
portal").

The Dated / Customary / Premium cards describe a resale ("kitchen and
bathrooms are largely original", "updated within ~15 years"). On a brand-new
home those sentences are wrong, so a property with "new_construction": true
gets new-build wording in their place. Applied to every page before the PDFs
print and again at the end, so screen and paper match.
"""
from pathlib import Path

REPL = [
    ("Kitchen and bathrooms are largely original.", "Base builder package with few or no options."),
    ("Paint, lighting, hardware, flooring, and finishes are dated.",
     "Finishes below the new homes it competes with."),
    ("Overall presentation is below standard.", "Presentation below the competing new construction."),
    ("Kitchen and bathrooms updated within ~15 years.", "Finishes and options in line with the new homes that sold nearby."),
    ("Paint, lighting, hardware, flooring, finishes reflect current standard.",
     "Brand-new systems, roof and mechanicals."),
    ("Paint, lighting, hardware, flooring, and finishes reflect current standard.",
     "Brand-new systems, roof and mechanicals."),
    ("Overall presentation is competitive with comparable homes.",
     "Competitive with comparable new construction."),
    ("Kitchen and bathrooms updated within ~10 years.", "Builder upgrades and options beyond the standard package."),
    ("Upgrades, finishes, and craftsmanship exceed the standard.",
     "Finishes and craftsmanship exceed the competing new builds."),
]

ON = False   # set by build_portal.main for a new-construction property


def text(h):
    for a, b in REPL:
        h = h.replace(a, b)
    return h


def apply_file(f):
    f = Path(f)
    if ON and f.exists():
        t = f.read_text(encoding="utf-8")
        t2 = text(t)
        if t2 != t:
            f.write_text(t2, encoding="utf-8")


def apply_dir(out):
    for f in Path(out).glob("*.html"):
        apply_file(f)
