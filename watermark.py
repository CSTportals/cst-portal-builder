#!/usr/bin/env python3
"""The sample mark: "Sample, Property of Casey Samson Team".

Casey, 19 Oct 2026: "Instead of expire, write 'Sample, Property of Casey
Samson Team' once in the middle of Seller portal, Summary, buyer portal,
buyer summary."

Set "sample" on the property file and those four documents carry the mark.
Clear it and rebuild and they are clean -- actively clean, because removal
strips the mark rather than relying on the file being rewritten.

    "sample": true

One line, centred, drawn in a fixed layer over the page. It takes part in
no layout, so nothing moves and nothing repaginates: the Summary is two
pages marked or unmarked, and the Buyer Report still fits its two.

WHAT THIS IS, AND WHAT IT IS NOT

It is a visible claim on the work. Anyone who opens, screenshots, prints or
forwards the portal sees whose it is, which is what makes an unpaid copy
awkward to pass off as finished work.

It is NOT protection. These are HTML files on someone else's computer, and
anyone who opens one in a text editor can delete the block. If a preview
has to actually stop working, that has to happen where the file is served
-- a site taken down, or a password -- not inside the file.
"""
import re

MARKER = "cst-wm"          # so a second pass does not stamp a page twice

TEXT = "Sample, Property of Casey Samson Team"

# The four Casey named. Everything else in the folder is left alone: the
# Roadmap, the Marketing plan, the Tracker, the emails, the Local Market
# Snapshot. Matched on the tail of the filename, so the property prefix
# does not have to be passed in.
SELLER_PAGES = ("index.html",
                "_Pricing_Strategy_Summary.html",
                "_Buyer_Report.html")


def wanted(name):
    """Does this file in a seller portal folder carry the mark?"""
    # index_classic.html and index_dynamic.html are alternates the seller is
    # not sent, so only the portal page itself is marked.
    return name == "index.html" or any(
        name.endswith(s) for s in SELLER_PAGES if s.startswith("_"))


def block(text=TEXT):
    """The style and markup to drop in before </body>."""
    # One line, centred, in a fixed layer above the page and below nothing
    # that matters: pointer-events:none so it never intercepts a click.
    #
    # print-color-adjust:exact or the browser drops the tint when printing,
    # which would hand back a clean PDF -- the one thing this must not do.
    # Casey, 19 Oct 2026: "I do like the message on top." So both -- the gold
    # bar a reader meets before anything else, and the one line across the
    # middle that survives a screenshot of any part of the page.
    css = """
  .cst-wm{position:fixed; inset:0; z-index:9000; pointer-events:none;
    display:flex; align-items:center; justify-content:center;
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  .cst-wm i{font-family:'Playfair Display',Georgia,serif; font-weight:700;
    letter-spacing:.1em; text-transform:uppercase; text-align:center;
    color:rgba(138,106,46,.16); transform:rotate(-24deg); font-style:normal;
    line-height:1.12;
    /* The buyer portal opens on a full-bleed photo, and gold at this
       weight vanished into a dark one. The pale halo carries the letters
       over a dark image without showing on the cream pages. */
    text-shadow:0 0 3px rgba(255,253,247,.40);}
  /* Two lines, Casey 19 Oct: the word alone, then whose it is. The first
     line carries the weight, so it is set larger than the second. */
  .cst-wm i s{display:block; text-decoration:none; white-space:nowrap;}
  .cst-wm i s.one{font-size:clamp(34px,7vw,86px); letter-spacing:.16em;}
  .cst-wm i s.two{font-size:clamp(15px,2.7vw,32px); letter-spacing:.09em;}
  .cst-wm b{position:fixed; top:0; left:0; right:0; padding:7px 14px;
    background:#8A6A2E; color:#FFFDF7; text-align:center; font-weight:700;
    font-size:11.5px; letter-spacing:.14em; text-transform:uppercase;
    font-family:'Lora',Georgia,serif;
    -webkit-print-color-adjust:exact; print-color-adjust:exact;}
  /* Screen only. Padding the body in print pushed the Buyer Report onto a
     third page -- a mark that repaginates the document is not a mark, it is
     an edit. In print the bar sits in the sheet's own top margin instead,
     so every page is where it was. */
  @media screen{ body{padding-top:30px;} }
  @media print{
    .cst-wm i{color:rgba(138,106,46,.17);}
    .cst-wm i s.one{font-size:58px;} .cst-wm i s.two{font-size:21px;}
    .cst-wm b{padding:4px 14px; font-size:9px;}
  }
"""
    one, two = split(text)
    return (f"<style>{css}</style>\n"
            f'<div class="cst-wm" aria-hidden="true">'
            f"<b>{text}</b>"
            f'<i><s class="one">{one}</s><s class="two">{two}</s></i>'
            "</div>\n")


def split(text=TEXT):
    """"Sample, Property of Casey Samson Team" -> the two lines.

    Splits on the first comma, which is where Casey wrote the break. Text
    with no comma goes on one line rather than being broken somewhere he
    did not ask for.
    """
    head, sep, tail = text.partition(",")
    return (head.strip(), tail.strip()) if sep else (text.strip(), "")


def stamp(html, on=True, text=TEXT):
    """Return `html` with the mark in it, or unchanged if already stamped."""
    if not on or MARKER in html:
        return html
    mark = block(text)
    if "</body>" in html:
        return html.replace("</body>", mark + "</body>", 1)
    return html + mark


def unstamp(html):
    """Take the mark back out of one page."""
    if MARKER not in html:
        return html
    html = re.sub(r"<style>\s*\n?\s*\.cst-wm\{.*?</style>\s*", "", html,
                  flags=re.S)
    return re.sub(r'<div class="cst-wm".*?</div>\s*', "", html, flags=re.S)


NOPRINT = "cst-nopr"
# pikepdf needs an owner password to set permissions at all. It is not a
# secret -- it is what Casey uses to lift the lock on a PDF by hand if he
# ever needs to (qpdf --decrypt --password=... in.pdf out.pdf).
PDF_OWNER = "CST-sample"


def print_block():
    """CSS that empties the page when it is sent to a printer.

    Applied only AFTER this build has rendered its own PDFs -- Chrome makes
    those through the same print path, so stamping this in first would have
    produced blank PDFs.
    """
    return """
<style class="cst-nopr">
  @media print{
    html body > *{display:none !important;}
    html body{padding:0 !important;}
    html body::before{display:block; content:"Sample \\2014 \\A Property of \\
the Casey Samson Team \\A\\A This preview is not licensed for printing.";
      white-space:pre; text-align:center; padding-top:34vh;
      font-family:Georgia,serif; font-size:18px; letter-spacing:.08em;
      color:#8A6A2E;}
  }
</style>
"""


def lock_print(out, on, note=print):
    """Add or remove the no-print rule on the marked pages."""
    from pathlib import Path
    n = 0
    for f in sorted(Path(out).glob("*.html")):
        t = f.read_text(encoding="utf-8")
        has = NOPRINT in t
        if on and wanted(f.name) and MARKER in t and not has:
            s = t.replace("</body>", print_block() + "</body>", 1) \
                if "</body>" in t else t + print_block()
        elif has and not (on and wanted(f.name)):
            s = re.sub(r'<style class="cst-nopr">.*?</style>\s*', "", t,
                       flags=re.S)
        else:
            continue
        f.write_text(s, encoding="utf-8")
        n += 1
    if n and on:
        note(f"Printing blocked on {n} sample page"
             f"{'s' if n != 1 else ''} — a print comes out as a notice "
             "instead of the document.")
    return n


def lock_pdfs(out, on, prefix, note=print):
    """Set or clear the no-print permission on the sample PDFs.

    A CSS rule cannot reach a PDF, so the two printable documents get the
    real thing: the PDF permission flag that says printing is not allowed.
    Readers honour it; it is not a lock a determined person cannot pick,
    and the file still opens for anyone.
    """
    from pathlib import Path
    try:
        import pikepdf
    except ImportError:
        note("Sample PDFs NOT locked — pikepdf is not installed, so the "
             "printing permission could not be set. The pages carry the "
             "mark, but the PDFs can be printed.")
        return 0
    # This property's own two printable documents, by name. Matching on the
    # tail alone caught the example Buyer Report that rides along in every
    # seller portal -- 502 MacArthur's, copied in from templates to make the
    # example card open a real file. That one is meant to be opened and
    # printed; locking it defeats the point of shipping it.
    mine = {f"{prefix}_Pricing_Strategy_Summary.pdf",
            f"{prefix}_Buyer_Report.pdf"}
    n = 0
    for f in sorted(Path(out).glob("*.pdf")):
        if f.name not in mine:
            continue
        try:
            with pikepdf.open(f, password=PDF_OWNER if on else "",
                              allow_overwriting_input=True) as pdf:
                if on:
                    pdf.save(f, encryption=pikepdf.Encryption(
                        owner=PDF_OWNER, user="",
                        allow=pikepdf.Permissions(
                            print_lowres=False, print_highres=False,
                            extract=False, modify_assembly=False,
                            modify_annotation=False, modify_form=False,
                            modify_other=False)))
                else:
                    pdf.save(f)                       # saved without it
            n += 1
        except Exception as e:                        # noqa: BLE001
            note(f"Could not set the printing permission on {f.name} "
                 f"({type(e).__name__}) — it is printable.")
    if n and on:
        note(f"Printing disallowed on {n} sample PDF"
             f"{'s' if n != 1 else ''}. Most readers honour the flag; it is "
             "a deterrent, not a lock. To lift it by hand: "
             f"qpdf --decrypt --password={PDF_OWNER} in.pdf out.pdf")
    return n


def apply_folder(out, on, text=TEXT, note=print):
    """Mark the four named pages, or strip the mark from every page.

    Removal sweeps the whole folder rather than the four, because a page
    marked under an earlier rule has to come clean too, and because not
    every file is rewritten on every build -- the agent track-record page is
    copied in, and a copied page keeps whatever was stamped on it last time.
    That is how an unmarked rebuild could otherwise still ship a marked page.
    """
    from pathlib import Path
    n = 0
    for f in sorted(Path(out).glob("*.html")):
        t = f.read_text(encoding="utf-8")
        s = stamp(t, True, text) if (on and wanted(f.name)) else unstamp(t)
        if s != t:
            f.write_text(s, encoding="utf-8")
            n += 1
    if n and on:
        note(f'Sample mark on {n} page{"s" if n != 1 else ""}: "{text}". '
             'Clear "sample" on the property file and rebuild to remove it. '
             "The mark is visible, not enforcement — anyone with the file "
             "can delete it.")
    elif n:
        note(f'Removed the sample mark from {n} page'
             f'{"s" if n != 1 else ""} — this build is the paid version.')
    return n
