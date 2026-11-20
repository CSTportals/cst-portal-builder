"""Typeset the three Woodrow documents — content taken verbatim from Casey's
.pages/.numbers originals — as branded PDFs the buyer portal can link."""
import asyncio, glob
from pathlib import Path
from playwright.async_api import async_playwright

EXE = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")[0]
OUT = Path("/home/claude/portal_builder/assets/9945_Woodrow/buyer")
LOGO = "/home/claude/portal_builder/templates/Gold_Standard_Logo.png"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');
*{box-sizing:border-box;}
body{margin:0;font-family:'Lora',Georgia,serif;color:#221C14;line-height:1.38;font-size:10.5pt;}
.page{padding:0 0 10pt;}
header{text-align:center;border-bottom:1px solid #D3B978;padding-bottom:9pt;margin-bottom:12pt;}
header img{width:54px;display:block;margin:0 auto 8pt;}
.brand{letter-spacing:.2em;font-size:8pt;font-weight:600;color:#8A6A2E;text-transform:uppercase;}
h1{font-family:'Playfair Display',Georgia,serif;font-size:17pt;font-weight:700;margin:6pt 0 2pt;}
.addr{font-size:10.5pt;color:#71695A;margin:0;}
h2{font-family:'Playfair Display',Georgia,serif;font-size:10.5pt;font-weight:700;color:#8A6A2E;
  text-transform:uppercase;letter-spacing:.06em;margin:11pt 0 5pt;border-bottom:1px solid #E4DCC8;
  padding-bottom:2pt;page-break-after:avoid;}
ul{margin:0;padding-left:16pt;} li{margin-bottom:2pt;}
ol{margin:0;padding-left:18pt;}
p{margin:0 0 7pt;}
.small{font-size:9pt;color:#71695A;}
.foot{margin-top:9pt;border-top:1px solid #E4DCC8;padding-top:8pt;text-align:center;
  font-size:8.5pt;color:#71695A;font-style:italic;}
table.conv{width:100%;border-collapse:collapse;font-size:9.5pt;margin-bottom:8pt;}
table.conv td{border:1px solid #E4DCC8;padding:2.2pt 5pt;}
table.conv td.y{width:16pt;text-align:center;font-weight:700;color:#8A6A2E;}
.util td{border:none;padding:2pt 6pt 2pt 0;font-size:10pt;}
.kv{width:100%;border-collapse:collapse;font-size:10.5pt;}
.kv td{border-bottom:1px solid #E4DCC8;padding:5pt 0;vertical-align:top;}
.kv td.k{width:150pt;font-weight:600;color:#71695A;}
"""

def head(title, addr="9945 Woodrow Street, Vienna, VA 22181"):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="page"><header><img src="file://{LOGO}">
<div class="brand">The Casey Samson Team</div><h1>{title}</h1><p class="addr">{addr}</p></header>"""

DISC = ('<div class="foot">All information on this listing is provided by the seller to '
        'The Casey Samson Team, but is subject to errors and omissions and should not be '
        'relied upon without verification.</div></div></body></html>')

# ---------------- hot sheet ----------------
hot = head("Hot Sheet") + """
<h2>Top Features</h2><ul>
<li>Brand new custom designed home built by Sekas</li>
<li>6 bedrooms and 6.5 bathrooms on 3 levels</li>
<li>4 car garage</li>
<li>10 foot ceilings on main level</li>
<li>Main level owner&rsquo;s suite and upper level additional owner&rsquo;s suite</li>
<li>9 foot ceilings on upper level and lower level</li>
<li>Backing to parkland</li>
<li>Heated screened-in porch</li></ul>
<h2>Schools</h2><ul>
<li>Westbriar Elementary School</li><li>Kilmer Middle School</li><li>Marshall High School</li></ul>
<h2>Features</h2><ul>
<li>HOA: $260/Annually. Includes park maintenance, social events and architectural control</li>
<li>Induction cooktop</li><li>Two ovens</li>
<li>Environmentally safer than gas, the trending easy to clean induction cooktop heats food faster than gas</li>
<li>42&Prime; built-in KitchenAid French Door Refrigerator</li>
<li>Adjacent to trailhead that leads to Wolftrap amphitheater</li>
<li>Exterior walls are all 2x6 construction with foam insulation</li>
<li>Public sewer, water and gas</li>
<li>6,527 finished square feet</li><li>0.47 acre lot</li></ul>
<h2>Favorite Things</h2><ol>
<li>Land / neighborhood</li><li>Schools</li><li>Floor plan</li><li>Character</li></ol>
""" + DISC

# ---------------- offer instructions ----------------
offer = head("Offer Instructions") + """
<h2>Offers</h2><ul>
<li>Highest and Best offers will be reviewed after 12 noon on Monday, October 12th</li>
<li>Please add all documents in one PDF</li>
<li>Please no escalation clause</li>
<li>Submit offers to morgan@caseysamson.com and colbysmyth@gmail.com</li>
<li>Deliveries in contract to morgan@caseysamson.com and colbysmyth@gmail.com</li>
<li>Documents needed for the offer are included in MLS</li></ul>
<h2>Seller&rsquo;s Preferred Settlement</h2><ul>
<li>Settle 30 days</li><li>No rent back needed</li></ul>
<h2>Preferred Vendors</h2>
<table class="kv">
<tr><td class="k">Title company</td><td>Cardinal Title Group &mdash; secure, local and convenient with over 30 offices</td></tr>
<tr><td class="k">Correspondent lender</td><td>Mike Filan, Branch Manager at CrossCountry Mortgage<br>mike.filan@ccm.com &middot; 703.899.8720</td></tr>
<tr><td class="k">Lender letter</td><td>Must be current and include the lender&rsquo;s direct phone number and email. Banks are not preferred.</td></tr>
</table>
<h2>Contract Submission Summary</h2>
<p>When you submit a contract you <b>must</b> summarize the below items in your email:</p>
<ul style="column-count:2;column-gap:26pt;">
<li>Buyer name</li><li>Agent name</li><li>Lender</li><li>Settlement date</li>
<li>Down payment</li><li>Deposit</li><li>Home sale contingency</li><li>Other terms</li>
<li>Offer price</li><li>Buyer commissions</li><li>Other concessions</li></ul>
<h2 style="margin-top:9pt;">Agent Info for Contract</h2>
<p class="small" style="margin-bottom:2pt;">Kevin Samson / Morgan Samson / Colby Smyth &middot;
301210 / 3296187 / 3029499 &middot; SAMP1<br>
703-609-1745 morgan@caseysamson.com &nbsp;or&nbsp; 703-597-2428 colbysmyth@gmail.com<br>
Samson Properties, 14291 Park Meadow Dr Suite 500, Chantilly, VA 20151</p>
""" + DISC

# ---------------- conveyances ----------------
ITEMS = [
    ("X","Alarm System"),("X","Built-in Microwave"),("X","Ceiling Fan"),("","Central Vacuum"),
    ("X","Clothes Dryer"),("X","Clothes Washer"),("X","Cooktop"),("","Dishwasher"),
    ("X","Disposer"),("","Electronic Air Filter"),("X","Fireplace Screen/Door"),
    ("","Freezer"),("","Furnace Humidifier"),("X","Garage Opener"),("X","&nbsp;&nbsp;w/ remote"),
    ("X","Gas Log"),("","Hot Tub, Equip. &amp; Cover"),("","Intercom"),("","Playground Equipment"),
    ("","Pool, Equip. &amp; Cover"),("X","Refrigerator"),("X","&nbsp;&nbsp;w/ ice maker"),
    ("","Satellite Dish"),("","Storage Shed"),("X","Stove or Range"),("","Trash Compactor"),
    ("X","Wall Oven"),("","Water Treatment System"),("","Window A/C Unit"),("","Window Fan"),
    ("X","Window Treatments"),("","Wood Stove"),
]
cells = ""
for i in range(0, len(ITEMS), 3):
    row = ITEMS[i:i+3]
    tds = "".join(f'<td class="y">{y}</td><td>{n}</td>' for y, n in row)
    tds += '<td class="y"></td><td></td>' * (3 - len(row))
    cells += f"<tr>{tds}</tr>"

conv = head("Conveyances") + f"""
<p class="small"><b>PERSONAL PROPERTY, FIXTURES.</b> The Property includes the following
existing personal property and fixtures: built-in heating and central air conditioning
equipment, plumbing and lighting fixtures, attic and exhaust fans, storm windows, storm
doors, screens, installed wall-to-wall carpeting, smoke and heat detectors, TV antennas,
exterior trees, and shrubs. Unless otherwise agreed to in writing, all surface or wall
mounted electronic components/devices <b>do not convey</b>. If more than one of the item
conveys, the number of items is noted.</p>
<h2>Items marked X are currently installed or offered</h2>
<table class="conv">{cells}</table>
<h2>Leased Items</h2>
<p class="small">Any leased items, systems or service contracts (including, but not limited
to, fuel tanks, water treatment systems, lawn contracts, security system monitoring, and
satellite contracts) <b>do not convey</b> absent an express written agreement by Purchaser
and Seller. None are listed for this property.</p>
<h2>Utilities</h2>
<table class="util">
<tr><td><b>Water supply</b></td><td>Public</td></tr>
<tr><td><b>Sewage disposal</b></td><td>Public</td></tr>
<tr><td><b>Hot water</b></td><td>Gas</td></tr>
<tr><td><b>Air conditioning</b></td><td>Electric</td></tr>
<tr><td><b>Heating</b></td><td>Gas</td></tr>
</table>
<div class="foot">All information presented in this brochure is believed to be accurate,
but is subject to errors and omissions and should not be relied upon without verification.</div>
</div></body></html>"""

DOCS = [("WD_Hot_Sheet.pdf", hot), ("WD_Offer_Instructions.pdf", offer),
        ("WD_Conveyances.pdf", conv)]

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=EXE)
        pg = await b.new_page()
        for name, html in DOCS:
            Path(f"/tmp/wdoc/{name}.html").write_text(html)
            await pg.goto(f"file:///tmp/wdoc/{name}.html")
            await pg.wait_for_timeout(1200)
            await pg.pdf(path=str(OUT / name), format="Letter", print_background=True,
                         margin={"top":"0.45in","bottom":"0.4in","left":"0.6in","right":"0.6in"})
            print("wrote", OUT / name)
        await b.close()

asyncio.run(main())
