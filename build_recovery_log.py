#!/usr/bin/env python3.12
"""Spreadsheet of every agent we have produced a recovery portal for.

Casey, 21 Oct 2026: "We will need to produce a spreadsheet of agents we have
produced recovery portals for. Spreadsheet includes: Listing agent, address,
phone, email, date of creation."

Read straight off properties/*.json, so it is never retyped:

    python3.12 build_recovery_log.py            # -> output/CST_Recovery_Portals.xlsx

A property is on the list when "listing_status" is "recovery" and the listing
agent is someone other than Casey. Fields used:
    agent.display / agent.phone / agent.email   (the listing agent)
    listing_agent_name / listing_agent_email    (used when agent is not set)
    created  (YYYY-MM-DD), else report_date      -> Date of Creation
    sample_issued (+72h, or "expires")           -> Links Expire
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

HEAD = ["Listing Agent", "Address", "Phone", "Email", "Date of Creation",
        "City", "Seller Portal", "Links Expire", "Notes"]


def created_date(p):
    if p.get("created"):
        return datetime.fromisoformat(p["created"]).date()
    rd = p.get("report_date")
    if rd:
        try:
            return datetime.strptime(rd, "%A, %B %d, %Y").date()
        except ValueError:
            pass
    return None


def expires(p):
    if not p.get("sample"):
        return None
    if p.get("expires"):
        return datetime.fromisoformat(p["expires"]).replace(tzinfo=None)
    if p.get("sample_issued"):
        return (datetime.fromisoformat(p["sample_issued"])
                + timedelta(hours=p.get("sample_hours") or 72)).replace(tzinfo=None)
    return None


def rows():
    out = []
    for f in sorted((HERE / "properties").glob("*.json")):
        p = json.loads(f.read_text())
        if p.get("listing_status") != "recovery":
            continue
        a = p.get("agent") or {}
        is_casey = (a.get("lookup") or "").lower().startswith("casey")
        name = (a.get("display") if not is_casey else None) or p.get("listing_agent_name")
        if not name:
            continue                      # Casey's own listing, not an agent's
        phone = "" if is_casey else (a.get("phone") or "")
        email = p.get("listing_agent_email") or ("" if is_casey else a.get("email") or "")
        missing = [k for k, v in (("last name", " " in name),
                                  ("phone", phone), ("email", email)) if not v]
        notes = p.get("log_note") or (
            "Not on file: " + ", ".join(missing) if missing else "")
        out.append([name, p["address"], phone, email, created_date(p),
                    p.get("city", ""), (p.get("portal_url") or "").replace("https://", ""),
                    expires(p), notes])
    out.sort(key=lambda r: (r[4] or datetime.min.date()), reverse=True)
    return out


def main():
    data = rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "Recovery Portals"
    f_all = "Arial"
    ws["A1"] = "Recovery Portals — Listing Agents"
    ws["A1"].font = Font(name=f_all, size=14, bold=True, color="221C14")
    ws["A2"] = (f"The Casey Samson Team · {len(data)} portals · built from the "
                f"property files {datetime.now():%B %-d, %Y}")
    ws["A2"].font = Font(name=f_all, size=9, italic=True, color="71695A")
    hdr = 4
    thin = Side(style="thin", color="E4DCC8")
    for i, h in enumerate(HEAD, 1):
        c = ws.cell(row=hdr, column=i, value=h)
        c.font = Font(name=f_all, size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="8A6A2E")
        c.alignment = Alignment(horizontal="left" if i in (1, 2, 4, 7, 9) else "center",
                                vertical="center")
    for r, row in enumerate(data, hdr + 1):
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.font = Font(name=f_all, size=10)
            c.border = Border(bottom=thin)
            c.alignment = Alignment(horizontal="left" if i in (1, 2, 4, 7, 9) else "center",
                                    vertical="center", wrap_text=(i == 9))
            if i == 5 and v:
                c.number_format = "mm/dd/yyyy"
            if i == 8 and v:
                c.number_format = "mm/dd/yyyy h:mm AM/PM"
            if i == 8 and not v:
                c.value = "—"
    last = hdr + len(data)
    ws.cell(row=last + 2, column=1, value="Total portals").font = Font(name=f_all, size=10, bold=True)
    ws.cell(row=last + 2, column=2, value=f"=COUNTA(B{hdr+1}:B{last})").font = Font(name=f_all, size=10, bold=True)
    note = ws.cell(row=last + 3, column=1,
                   value="Date of Creation is the portal's build date on its property file "
                         "(\"created\", else the report date). Links Expire is 72 hours "
                         "after a sample portal was issued; \"—\" means not a sample.")
    note.font = Font(name=f_all, size=8, italic=True, color="71695A")
    widths = [22, 26, 16, 30, 16, 14, 30, 20, 34]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=hdr + 1, column=1)
    ws.auto_filter.ref = f"A{hdr}:{get_column_letter(len(HEAD))}{last}"
    dest = HERE / "output" / "CST_Recovery_Portals.xlsx"
    dest.parent.mkdir(exist_ok=True)
    wb.save(dest)
    print(f"{len(data)} portals -> {dest}")
    for r in data:
        print("  ", r[0], "|", r[1], "|", r[2] or "-", "|", r[3] or "-", "|", r[4])


if __name__ == "__main__":
    main()
