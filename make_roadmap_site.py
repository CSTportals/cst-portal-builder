#!/usr/bin/env python3.12
"""Package one portal page as a standalone one-page site.

Recovery portals go out as the Roadmap alone, and a Buyer Report is often sent
on its own to a buyer's agent. Either way the page needs to stand by itself
rather than as one page inside the portal: it becomes index.html, the
"Back to ..." link is dropped because there is no nav page to go back to, and
only the assets the page actually references are carried across.

    python3.12 make_roadmap_site.py 41057_Haybine
    python3.12 make_roadmap_site.py 6032_Erinblair Buyer_Report
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"


KINDS = {
    "Roadmap": ("SELLER ROADMAP", "index.html is the Roadmap."),
    "Buyer_Report": ("BUYER PRICING REPORT  —  public, for buyers and their agents",
                     "index.html is the Buyer Report."),
}


def build(prefix, kind="Roadmap", dest=None):
    src = OUT / prefix
    page = src / f"{prefix}_{kind}.html"
    if not page.exists():
        sys.exit(f"no {kind} at {page}")

    html = page.read_text(encoding="utf-8")
    # The back link points at the portal's nav page, which is not in this zip.
    html = re.sub(r'<a class="back"[^>]*>.*?</a>\s*', "", html, flags=re.S)

    _slug = prefix if kind == "Roadmap" else f"{prefix}_{kind}"
    site = Path(dest or (HERE / "_site" / _slug))
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)
    (site / "index.html").write_text(html, encoding="utf-8")

    # Only what the page still references, plus the printable.
    wanted = {r for r in re.findall(r'(?:src|href)="([^"]+)"', html)
              if not r.startswith(("http", "#", "mailto", "tel", "data:"))}
    wanted.add(f"{prefix}_{kind}.pdf")
    carried, missing = [], []
    for name in sorted(wanted):
        f = src / name
        if f.exists():
            shutil.copy(f, site / name)
            carried.append(name)
        else:
            missing.append(name)

    _head, _what = KINDS.get(kind, (kind.upper(), f"index.html is the {kind}."))
    (site / "DEPLOY.txt").write_text(
        f"{_head}  —  standalone one-page site\n"
        f"{prefix.replace('_', ' ')}\n\n"
        f"{_what} Drop this folder on its own Netlify site.\n"
        "It carries no tracker, emails or pricing nav page.\n",
        encoding="utf-8")

    zpath = Path(f"{site}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(site.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(site))
    return zpath, carried, missing


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    z, carried, missing = build(sys.argv[1],
                                sys.argv[2] if len(sys.argv) > 2 else "Roadmap")
    print(f"{z}  ({z.stat().st_size/1024:.0f} KB)")
    print("  carried:", ", ".join(carried) or "nothing")
    if missing:
        print("  MISSING:", ", ".join(missing))
