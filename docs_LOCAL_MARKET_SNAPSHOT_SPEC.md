# Local Market Snapshot™ — build spec

Hand this to the Seller Portal work. It is self-contained: nothing here
depends on the MSS sandbox.

---

## What it is

A **Local Market Snapshot™** answers "how is the market for homes like
*this one*". It is not a city report. The pull is bounded by **area, size,
age and price range** around a subject listing, so a seller sees the homes
they are actually competing with rather than every home in the city.

It is the page behind the **Market Snapshot** card in that property's
Seller Portal. One per listing.

It looks exactly like a city Market Snapshot — same stylesheet, masthead,
flag, headline, three key stats, footer — because a seller who also browses
the public site should not feel handed a different document.

---

## Input

One MLS export of the surrounding homes. Tab-delimited or CSV. Required
columns, named exactly as the MLS exports them:

| Column | Used for |
|---|---|
| `MLS #` | row is real / de-duplication |
| `Status` | ACT, A/C, PND, CLS, C/S, WTH, EXP, CNL, T/O |
| `Listing Entry Date` | the 30-day cohort |
| `Agreement of Sale/Signed Lease Date` | the 14-day figure, and the pre-sold test |
| `DOM` | days on market |
| `List Price` / `Original List Price` | price bands, reductions |
| `Above Grade Finished SQFT` | the size bound |
| `Year Built` | the age bound |
| `Tax Assessed Value` | asking-vs-assessed |
| `City Name` (or `City`) | the area bound |

The pull itself defines the criteria line in the subtitle — read the
min/max of size, year and price off the data rather than typing them in.
If the bounds are typed by hand they will eventually disagree with the
rows, and the page will be wrong in a way nobody notices.

---

## The rules

These are the same rules the MSS uses. Keep them identical, or the Local
Market Snapshot and the public site will tell one seller two stories.

**Reference date** = the date the pull was run.

**The cohort** = homes whose `Listing Entry Date` is **8 to 38 days** before
the reference date. Under 8 days a listing has not had time to answer; a
week-old listing with no contract is not a failure.

**Two exclusions, both from numerator *and* denominator:**

1. **Coming Soon** (`Status == "C/S"`). Not on the market yet.
2. **Pre-sold** — any row whose agreement date is **on or before** its
   listing entry date. A home cannot go under contract before it is for
   sale. These are new construction, pocket listings and office exclusives
   entered into the MLS to record a sale that was already done, plus
   relisted properties carrying an old contract date. Left in, every one is
   an automatic win: they were 6% of listings region-wide but a far larger
   share of contracts, and they put Vienna Luxury at 67% when the homes
   that actually competed were at 55%.

**30 DAY** = cohort rows with `Status` in {`CLS`, `PND`, `A/C`} ÷ cohort.

**14 DAY** = those whose agreement date falls within 14 days of the
reference date ÷ **the same cohort**. Both percentages share one
denominator, so the 14-day figure is part of the 30-day figure and can
never exceed it — thirty days holds two fourteen-day periods. Assert this.

**Flag bands**, read off the 30-day:

| 30 day | Flag |
|---|---|
| over 50% | Double Green — Launch |
| 41–50% | Green — Clear to Launch |
| 31–40% | Yellow — Proceed with Care |
| 21–30% | Red Flag — Hold |
| 20% or under | Double Red — Do Not Launch |

**Momentum** — improving when the last 14 days produced more than half the
month: `p14 > p30 / 2`. (Open question Casey has not settled: at *exactly*
half, the market is holding pace, and his own vocabulary has "holding
steady". Today it prints "retreating".)

**Thin samples** — under 5 listings in the cohort, state the counts in the
headline instead of the percentage. "Double Green, 100%" off one
neighbour's sale is not something to put in front of a seller. With exactly
one listing: "The Only Home Listed in the Past 30 Days Is Under Contract".

**Whole-inventory % under contract** = {`CLS`,`PND`,`A/C`} ÷ every row. Use
his control bands: under 40% buyers are in control, over 60% sellers are,
40–60% neither.

**Price bands** — split the pull into three and give each one listings,
under contract, % UC, median DOM, and months of supply (unsold ÷ contracts
per month). This is usually the real finding: a single percentage averages
bands that behave nothing alike.

---

## Caveats the page must state about itself

An active-and-pending pull has **no closed sales and no withdrawn or
expired listings**, so it reads lower than the MSS cohort, which counts
closings as contracts and failures in the denominator. Say so on the page.
Vienna Luxury read 54% on the MSS and 43% on the pull for the same week —
neither wrong, different populations.

Also state the sample size and what one more or one fewer contract would
do to the percentage. At 7 homes that is ±14 points.

---

## Page structure

Identical to a city Market Snapshot:

```
backbar          ← Back to Your Portal   |   Look Before You Launch →
masthead         seal / brandline / h1 "Local Market Snapshot™"
                 subtitle: the property address
                 subtitle: City · 3,609–8,113 SF · Built 1975–2027 · $2.1M–$4.5M
                 weekof pill: As of <date>
section 1        eyebrow "Current Market Conditions"
                 h2.headline  flag + "...Flying a <Flag> with <30d>% of Listed
                              Homes in the Past 30 Days Going Under Contract"
                 p.subhead    "<14d>% went under contract in the last 14 days
                              — this market is <advancing|retreating>."
                 div.keystats three tiles: 30 day / 14 day / % of all inventory
                 p.narrative  the counts in a sentence
section 2        div.chart-card "The Local Market"
                 two chart-col: "Went Under Contract" vs "For Sale Past 90 Days"
                 rows: homes, median price, price cuts, contracts within 5 days,
                       $/sf, asking vs assessed
section 3        table-wrap: the price band table
                 p.narrative × 2: the finding, then the caveats
footer           the standard MSS footer
```

Take the `<head>`, backbar and footer **from a live city snapshot page** at
build time rather than copying them into the script. That is what keeps the
styling from drifting, and it is why this page needs no stylesheet of its
own. Two things must be overridden after copying:

- the `<title>`, which will say the source page's name
- the backbar link, which will point at the source city — it should go back
  to that property's portal

Strip the zero-width characters from the copied footer; they are the source
page's fingerprint and are not this page's.

---

## Seller Portal integration

In every Seller Portal, under **Market Snapshot**:

```html
<a class="link-card mss" href="<SLUG>_Local_Market_Snapshot.html">
  <div>
    <span class="link-tag">Market Snapshot</span>
    <div class="link-title">Local Market Snapshot&trade;</div>
    <div class="link-desc">Homes like yours &mdash; by size, age and price range</div>
  </div>
  <span class="link-arrow">&rarr;</span>
</a>
<p class="rest-of-market">
  <a href="https://cstmarketupdate.netlify.app/#">Rest of the Market &rarr;</a>
</p>
```

```css
.rest-of-market{text-align:center; margin:-4px 0 18px;}
.rest-of-market a{font-size:13px; font-weight:700; letter-spacing:.02em;
  color:var(--gold-deep, #8A6A2E); text-decoration:none;}
.rest-of-market a:hover{text-decoration:underline;}
```

**"Rest of the Market"** goes on every portal — it leads to the public MSS
Navigator, which is current whether or not this property has been pulled.
The **card above it only goes where that property's own pull exists**.
Pointing a seller at another property's comps would be worse than no card.

Two things to know about the portals as they stand:

- `2708_Valestra_Cir_Nav.html` and `9932_Clearfield_Ave_Nav.html` both have
  a market card pointing at **`Delta_Force.html`**, a Gateway report retired
  when the Early Warning system replaced it. That card is the slot this one
  takes.
- Neither property has a comparable pull yet. They need one each before
  their card can be added.

---

## Worked example

`502_Macarthur_Ave_Local_Market_Snapshot.html`, from a 22-row Vienna pull
run 2026-10-14. Criteria: Vienna · 3,609–8,113 SF · built 1975–2027 ·
$2.1M–$4.5M.

- 30 day **43%** (3 of 7) → **Green Flag**
- 14 day **14%** → retreating
- whole inventory **23%** under contract (5 of 22)
- 17 actives, median 99 days on market

| Price band | Listings | Under contract | % UC | Median days | Supply |
|---|---|---|---|---|---|
| Under $2.3M | 9 | 4 | 44% | 52 | 1.2 mo |
| $2.3M–$3.0M | 4 | 0 | 0% | 33 | — |
| $3.0M and up | 9 | 1 | 11% | 195 | 8.0 mo |

The two findings worth carrying into the seller conversation:

**The price you launch at is the price that works.** None of the 5 homes
under contract had ever cut. 10 of the 17 still for sale have cut, by an
average of 6.6%, and are still sitting. 3 of the 5 contracts came in five
days or less.

**Buyers are capped on total dollars, not on value.** The homes going under
contract ask a *higher* price per square foot — $566 against $506 for homes
past 90 days. Asking against assessed: 1.15x sells, 1.30x sits.

Note the middle band gets **no colour dot** even at 0%. All four of those
listings are a median of 33 days old and have not had time to answer; a red
dot would contradict the caveat printed further down the same page.
