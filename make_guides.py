#!/usr/bin/env python3
"""Build the CST guide pages (Casey, 22 Nov 2026: "Guides to Understanding
CST Tools" -- Seller Roadmap, Buyer Portal, Market Snapshot, Move Up Buyers).

The Seller Roadmap and Buyer Portal guides were written by hand earlier and
live in templates/guides/. This script writes the other two in the same
style from screenshots:

    python3 make_guides.py <screenshot_dir>

<screenshot_dir> holds mss/{s0,success,momentum,ytd,advantage}.png and
mu/{closed,math}.png.
"""
import base64
import io
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent / "templates" / "guides"
STYLE = Path(OUT / "Buyer_Portal_Guide.html").read_text(encoding="utf-8")
HEAD = STYLE[:STYLE.index("</style></head>")]


def emb(path):
    im = Image.open(path).convert("RGB")
    if im.width > 1400:
        im = im.resize((1400, int(im.height * 1400 / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82, optimize=True)
    return base64.b64encode(b.getvalue()).decode()


def page(title, lede, sections, footer):
    cards = ""
    for k, (img, t, sub, ps) in enumerate(sections, 1):
        cards += (f'<section class="g"><div class="n">{k}</div><div class="txt"><h2>{t}</h2>'
                  f'<p class="sub">{sub}</p>' + "".join(f"<p>{x}</p>" for x in ps) + "</div>"
                  f'<figure><img src="data:image/jpeg;base64,{emb(img)}" alt="{t}"></figure></section>\n')
    head = HEAD.replace("<title>", "<title>").split("<title>")[0] + f"<title>{title} &mdash; The Casey Samson Team</title>" + HEAD.split("</title>", 1)[1]
    return (head + "</style></head><body>\n"
            '<header><div class="k">The Casey Samson Team &mdash; The Gold Standard of Pricing Strategy</div>'
            f"<h1>{title}</h1><p>{lede}</p></header>\n<main>\n{cards}</main>\n"
            f"<footer><b>Questions?</b>{footer}</footer>\n</body></html>")


def main(d):
    d = Path(d)
    foot = "The Casey Samson Team &middot; 703-508-2535 &middot; Casey@caseysamson.com"
    mss = [
        (d / "mss/s0.png", "Who Controls the Market", "The headline answers it in one line",
         ["Every Market Snapshot opens with the answer: <b>buyers</b>, <b>sellers</b> or <b>neutral</b>. "
          "The flag under it tells you how strongly.",
          "The line beneath gives the two numbers behind the call: how many homes listed in the last 30 "
          "days went under contract, and how many went under contract in the last two weeks.",
          "Updated every week, so you see the market your home is selling into today, not last spring."]),
        (d / "mss/success.png", "How Homes Are Selling", "Success rate, days on market and price to list",
         ["<b>Success Rate</b> is the share of homes that sold rather than coming off the market unsold.",
          "<b>Days on Market</b> and <b>Sale Price to List Price</b> show how fast homes sold and how close "
          "to their asking price. The gauges run red to green, so you can read them at a glance.",
          "Below them are the most recent sales and withdrawals, colored the same way."]),
        (d / "mss/momentum.png", "Where the Market Is Heading", "Momentum: what is happening right now",
         ["<b>Momentum</b> looks at the homes still on the market: how many are under contract, how many "
          "of the last 30 days&rsquo; listings already have a buyer, and how long the rest have waited.",
          "This is the reading that tells us whether to price conservatively, at the first threshold under "
          "your home&rsquo;s value, or to test above it."]),
        (d / "mss/ytd.png", "The Year So Far", "Inventory, sales and success rate against last year",
         ["Year-to-date inventory and sales compared with last year, and the share of this year&rsquo;s "
          "listings that have sold.",
          "The bar underneath places the market on a single scale from <b>Buyers</b> to <b>Sellers</b>."]),
        (d / "mss/advantage.png", "Market Conditions Change. Winning Strategies Don&rsquo;t.&trade;",
         "The Casey Samson Team against the rest of the market",
         ["Every Market Snapshot ends with the CST track record side by side with the rest of the market: "
          "success rate, days on market, price to list, and the share sold in the first 10 days and above list.",
          "Whatever the market is doing, the strategy is what moves your result."]),
    ]
    (OUT / "Market_Snapshot_Guide.html").write_text(page(
        "Your Market Snapshot Guide",
        "What each part of the weekly CST Market Snapshot tells you, and how to read it.", mss, foot),
        encoding="utf-8")
    mu = [
        (d / "mu/closed.png", "Sell, Then Buy", "Two columns, the answers on top",
         ["<b>Sell:</b> enter what you expect your current home to sell for and what you still owe. "
          "The calculator shows your <b>walk out the door proceeds</b>.",
          "<b>Buy:</b> enter the price of your next home. Your proceeds become the down payment, after "
          "lender, title and closing costs. Add any extra cash in <b>Additional down payment</b>.",
          "The three monthly payments use a <b>2-1 buydown</b>: two points lower in Year 1, one point lower "
          "in Year 2, then the full rate for Years 3&ndash;30. Each includes taxes, insurance and HOA."]),
        (d / "mu/math.png", "The Math", "Tap the arrow to see every number",
         ["Under each column, the <b>Math</b> arrow opens the full calculation: commission, Grantor&rsquo;s "
          "Tax and fees on the sale; lender fees, title, prepaids and the buydown on the purchase; the loan "
          "amount, taxes and insurance.",
          "The note rate and who pays the buydown can be changed there. A warning appears if the down "
          "payment falls under 20%, since mortgage insurance is not included.",
          "Estimates for planning only. Your lender&rsquo;s Loan Estimate is the final word."]),
    ]
    (OUT / "Move_Up_Guide.html").write_text(page(
        "Your Move Up Calculator Guide",
        "How to see what your current home puts toward your next one, and what the payment looks like.",
        mu, foot), encoding="utf-8")
    print("wrote", OUT / "Market_Snapshot_Guide.html", OUT / "Move_Up_Guide.html")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/work/guide")
