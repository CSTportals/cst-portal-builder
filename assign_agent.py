#!/usr/bin/env python3
"""
assign_agent.py — point a Seller Portal at a listing agent from the
Samson agent database.

    python3 assign_agent.py "Ferris B Eways" /home/claude/mastery
    python3 assign_agent.py "Casey C Samson" ./portal --display "Casey Samson" --phone 703-508-2535

What it does, in the portal folder:
  1. Looks the agent up in agent_lookup.json (exact, then case-insensitive,
     then unique substring). Refuses on ambiguity rather than guessing.
  2. Copies agents/<slug>.html into the portal as the Agent Track Record page.
  3. Rewrites the Agent Track Record row on index.html to that page.
  4. Rewrites the .contact-line footer in every portal HTML file.
  5. Rewrites the Listing Agent card in the Seller Tracker directory.

Scope discipline: it only touches the contact line, the track-record row,
and the tracker's listing-agent card. Brand lines, logos, the CST team
section and all pricing content are left alone.
"""

import json
import re
import shutil
import sys
from pathlib import Path

DB = Path("/home/claude/agentdb")


# Casey is the default agent, so his preferred display name and phone are
# applied automatically — no flags needed.
AGENT_DEFAULTS = {
    "Casey C Samson": {"display": "Casey Samson", "phone": "703-508-2535"},
}


def find_agent(name):
    lookup = json.loads((DB / "agent_lookup.json").read_text())
    if name in lookup:
        return name, lookup[name]
    low = {k.lower(): k for k in lookup}
    if name.lower() in low:
        k = low[name.lower()]
        return k, lookup[k]
    hits = [k for k in lookup if name.lower() in k.lower()]
    if len(hits) == 1:
        return hits[0], lookup[hits[0]]
    if not hits:
        sys.exit(f"No agent matching {name!r} in the database.")
    sys.exit(f"{name!r} is ambiguous — matches: {', '.join(sorted(hits))}")


def agent_email(page: Path):
    m = re.search(r"mailto:([^\"?]+)", page.read_text())
    return m.group(1) if m else None


def contact_line(name, email, phone):
    parts = [name]
    parts.append(f"<span class=\"sep\">|</span>{phone}" if phone else
                 "<span class=\"sep\">|</span>Samson Properties")
    if email:
        parts.append(f"<span class=\"sep\">|</span><a href=\"mailto:{email}\">{email}</a>")
    return "".join(parts)


def main():
    args = sys.argv[1:]
    display = phone = None
    for flag, var in (("--display", "display"), ("--phone", "phone")):
        if flag in args:
            i = args.index(flag)
            val = args[i + 1]
            args = args[:i] + args[i + 2:]
            if var == "display":
                display = val
            else:
                phone = val
    if len(args) < 2:
        sys.exit(__doc__)
    raw_name, portal = args[0], Path(args[1])

    name, rec = find_agent(raw_name)
    lookup_name = name
    defaults = AGENT_DEFAULTS.get(lookup_name, {})
    display = display or defaults.get("display")
    phone = phone or defaults.get("phone")
    if display:
        name = display
    slug, state = rec["slug"], rec.get("state", "")
    src = DB / "agents" / f"{slug}.html"
    if not src.exists():
        sys.exit(f"Database has {name} but no page at {src}")

    dest_name = f"{slug}.html"
    shutil.copy(src, portal / dest_name)
    email = agent_email(src)
    shown = name if name == lookup_name else f"{name} (db: {lookup_name})"
    print(f"{shown} ({state}) -> {dest_name}   email: {email or 'none on file'}"
          f"   phone: {phone or 'none given'}")

    # --- 1. footer contact line, every portal page -----------------------
    new_line = contact_line(name, email, phone)
    for f in sorted(portal.glob("*.html")):
        if f.name == dest_name:
            continue
        s = f.read_text()
        s2, n = re.subn(
            r'(<div class="contact-line">).*?(</div>)',
            lambda m: m.group(1) + new_line + m.group(2),
            s, flags=re.S)
        if n:
            f.write_text(s2)
            print(f"  contact line  -> {f.name} ({n})")

    # --- 2. Agent Track Record row on the nav page ----------------------
    idx = portal / "index.html"
    if idx.exists():
        s = idx.read_text()
        # Rewrite the href on the one <a class="row"> block that contains
        # the AGENT PERFORMANCE tag — anchored on the block, not a lookahead,
        # so it works no matter which agent the portal pointed at before.
        def fix_row(m):
            block = m.group(0)
            if "AGENT PERFORMANCE" not in block.upper():
                return block
            block = re.sub(r'href="[^"]*"', f'href="{dest_name}"', block, count=1)
            block = re.sub(r'(<div class="row-title">)[^<]*(</div>)',
                           lambda t: t.group(1) + name + " &mdash; Agent Track Record" + t.group(2),
                           block, count=1)
            # link-card markup keeps its own title text; only the href moves.
            return block

        s, n = re.subn(r'<a class="(?:row|link-card)[^"]*".*?</a>', fix_row, s, flags=re.S)
        if 'AGENT PERFORMANCE' in s.upper() and f'href="{dest_name}"' in s:
            idx.write_text(s)
            print(f"  track-record row -> index.html")
        elif "AGENT PERFORMANCE" not in s.upper():
            print("  note: index.html has no Agent Track Record card (the standard "
                  "portal has none) — nav page left unchanged.")
        else:
            sys.exit("Found an AGENT PERFORMANCE row but could not rewrite it — aborting.")

    # --- 3. Seller Tracker directory card -------------------------------
    for f in portal.glob("*Tracker*.html"):
        s = f.read_text()
        card = (
            '<div class="role">Listing Agent</div>\n'
            f'        <div class="nm">{name}</div>\n'
            '        <div class="org">Samson Properties</div>\n'
        )
        if phone:
            card += f'        <a href="tel:+1{phone.replace("-", "")}">{phone}</a>\n'
        if email:
            card += f'        <a href="mailto:{email}">{email}</a>\n'
        s2, n = re.subn(
            r'<div class="role">Listing Agent</div>.*?(?=</div>\s*<div class="dcard">)',
            lambda m: card + "      ", s, flags=re.S)
        if n:
            f.write_text(s2)
            print(f"  listing-agent card -> {f.name}")


if __name__ == "__main__":
    main()
