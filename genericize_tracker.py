#!/usr/bin/env python3
"""
genericize_tracker.py — strip real participant data out of a live Seller
Tracker so it can be used as a Sample.

    python3 genericize_tracker.py \\
        /mnt/user-data/uploads/502_Spring_St_Tracker_5.html \\
        templates/sample_tracker.html

Standing rule: a sample document may name Casey Samson and The Casey Samson
Team, and nobody else. Every other person, brokerage, lender, title company,
phone number, email, MLS ID and NMLS ID comes out.

Deal terms — dates, dollar figures, contract clauses — are KEPT, because they
are what makes the sample worth showing.

Run this again whenever the live tracker is updated; do not hand-edit the
output, or the next refresh silently loses the scrubbing.
"""

import re
import sys
from pathlib import Path

# Real value -> replacement. Order matters: longest/most specific first.
PEOPLE = [
    ("Monica S. Tencate", "The Seller"),
    ("Zachary &amp; Alexandra Isakowitz", "The Buyers"),
    ("the Isakowitzes", "the Buyers"),
    ("Isakowitzes", "Buyers"),
    ("Isakowitz", "Buyer"),
    ("Zachary & Alexandra Isakowitz", "The Buyers"),
    ("Kelly Samson", "The Listing Agent"),
    ("Joan Reimann", "The Buyer's Agent"),
    ("James Gaudiosi", "The Lender"),
    ("Monica", "the Seller"),
    ("Joan", "the Buyer's Agent"),
]

ORGS = [
    ("Corcoran McEnearney", "the Buyer's Brokerage"),
    ("Atlantic Coast Mortgage", "the Lender"),
    ("TheReimannGroup.com", "the Buyer's Brokerage"),
    ("RGS Title", "the Title Company"),
    ("RGS", "the Title Company"),
]

# Licence identifiers, in whatever form they appear.
IDS = [
    (r"&middot;\s*MLS\s*\d+", ""),
    (r"\bMLS\s*\d+", ""),
    (r"&middot;\s*NMLS\s*\d+", ""),
    (r"\bNMLS\s*\d+", ""),
]


def scrub(html, address_from=None, address_to=None):
    out = html

    if address_from and address_to:
        out = out.replace(address_from, address_to)

    for a, b in PEOPLE + ORGS:
        out = out.replace(a, b)

    for pat, rep in IDS:
        out = re.sub(pat, rep, out)

    # Drop tel:/mailto: anchors, except Casey's own.
    def drop_link(m):
        return "" if "caseysamson.com" not in m.group(0).lower() else m.group(0)

    out = re.sub(r'<a\s+href="(?:tel:|mailto:)[^"]*"[^>]*>.*?</a>\s*',
                 drop_link, out, flags=re.S | re.I)

    # Any bare phone number or email left in the markup.
    out = re.sub(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "", out)
    out = re.sub(r"\b[\w.+-]+@(?!caseysamson\.com)[\w.-]+\.\w+\b", "", out)

    # Tidy artefacts the substitutions leave behind.
    out = re.sub(r"\bthe the\b", "the", out)
    out = re.sub(r'(<div class="org">)\s*the Lender\s*(</div>)',
                 r"\1Mortgage lender\2", out)
    out = out.replace("the the Lender", "the lender's")

    # Tidy the empty org lines the removals leave behind.
    out = re.sub(r'(<div class="org">)\s*(&middot;)?\s*(</div>)', r"\1Details withheld\3", out)
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, dest = Path(sys.argv[1]), Path(sys.argv[2])
    html = src.read_text()
    out = scrub(html, address_from="502 Spring St SE, Vienna VA 22180",
                address_to="Sample, Vienna VA 22180")
    out = out.replace("502 Spring St", "Sample")
    dest.write_text(out)

    # Report anything that still looks like real contact data.
    leaks = []
    for needle, _ in PEOPLE + ORGS:
        if needle in out:
            leaks.append(needle)
    if re.search(r"@(?!caseysamson\.com)[\w.-]+\.\w+", out):
        leaks.append("an email address")
    if re.search(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", out):
        leaks.append("a phone number")

    print(f"{src.name} -> {dest}")
    if leaks:
        print("  !! STILL PRESENT: " + ", ".join(leaks))
        sys.exit(1)
    print("  clean: no third-party names, orgs, phones, emails or licence IDs")


if __name__ == "__main__":
    main()
