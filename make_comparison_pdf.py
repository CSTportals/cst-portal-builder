"""Standalone CST vs Zillow vs Compass comparison PDF.

Casey, 25 Nov 2026: "Creat comparison PDF alone". Page 1: the seller
checklist with the 7.01% off-market Zestimate callout; page 2: the buyer
checklist. Rows come from zillow_compare.py so the PDF and the portals match.

    python3 make_comparison_pdf.py   ->  output/CST_vs_Zillow_vs_Compass.pdf
"""
import base64, os
import zillow_compare as zc

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output", "CST_vs_Zillow_vs_Compass.pdf")
LOGO = os.path.join(HERE, "output", "Sample", "Gold_Standard_Logo.png")
EXAMPLE_HOME = 2_000_000


def page(title, sub, inner):
    logo = ""
    if os.path.exists(LOGO):
        logo = ('<img class="logo" src="data:image/png;base64,'
                + base64.b64encode(open(LOGO, "rb").read()).decode() + '">')
    return (f'<div class="pg"><header>{logo}<div class="team">THE CASEY SAMSON TEAM</div>'
            '<div class="tag">The Gold Standard of Pricing Strategy</div></header>'
            f'<h1>{title}</h1><p class="sub">{sub}</p>{inner}'
            '<footer>The Casey Samson Team &middot; Samson Properties &middot; 703.508.2535 &middot; Casey@caseysamson.com</footer></div>')


def build():
    callout = zc.error_callout({"values": {"customary": EXAMPLE_HOME}})
    seller = page("CST Roadmap vs Zillow vs Compass",
                  "What sellers get from us, from Zillow, and from Compass.",
                  callout + zc._table(zc.SELLER_ROWS, "CST Roadmap"))
    buyer = page("CST Buyer Portal vs Zillow vs Compass",
                 "What buyers get from our Buyer Portal, from Zillow, and from Compass.",
                 zc._table(zc.BUYER_ROWS, "CST Buyer Portal"))
    css = zc.CSS + """
@page{size:Letter;margin:0}
body{margin:0;background:#FAF7F0;font-family:Georgia,serif;color:#1F2A44}
.pg{width:8.5in;height:11in;box-sizing:border-box;padding:.35in .7in .55in;position:relative;page-break-after:always;background:#FAF7F0}
.pg:last-child{page-break-after:auto}
header{text-align:center;border-bottom:1.5px solid #C9A961;padding-bottom:10px}
.logo{height:40px;display:block;margin:0 auto 4px}
.team{font:700 15px Georgia,serif;letter-spacing:.28em;color:#1F2A44}
.tag{font:italic 12.5px Georgia,serif;color:#8A6A2E;margin-top:2px}
h1{font:700 23px Georgia,serif;text-align:center;margin:10px 0 2px}
.sub{text-align:center;font-size:13.5px;color:#5A5446;margin:0}
.zx{margin-top:10px;padding:10px 20px}.zx .big{font-size:32px;margin:4px 0 0}.zx .sub{font-size:13.5px}.zx .usd{font-size:15.5px;margin-top:5px}.zx .why{font-size:11.5px;margin-top:6px}
.zc{margin-top:10px}.zc td{padding:4px 10px;font-size:13px}.zc .y,.zc .n{width:18px;height:18px;line-height:18px;font-size:12px}.zc .n{line-height:15px}.zc th{padding:7px 8px;font-size:10.5px}.zc-foot{font-size:10px;margin-top:6px}
footer{position:absolute;bottom:.35in;left:0;right:0;text-align:center;font:11px Georgia,serif;color:#71695A}
"""
    html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{seller}{buyer}</body></html>'
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html, wait_until="load")
        pg.pdf(path=OUT, format="Letter", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    print("PDF", OUT)


if __name__ == "__main__":
    build()
