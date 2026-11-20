# Seller Portal Builder

Build a complete Seller Portal from one JSON file of worksheet numbers.

## Run

```bash
python3 test_pricing.py                              # always run this first
python3 build_portal.py properties/502_macarthur.json
python3 assign_agent.py "Casey C Samson" output/502_MacArthur \
        --display "Casey Samson" --phone 703-508-2535
```

Output lands in `output/<prefix>/` — deploy that folder to Netlify as-is.
Every internal link is relative.

Flags: `--out <dir>` to write elsewhere, `--no-pdf` to skip PDF rendering
(much faster while you are iterating on the data).

## Files

| File | What it is |
|---|---|
| `pricing.py` | The pricing rules, in code. The only place dollar logic lives. |
| `test_pricing.py` | Regression tests — every worked example on record. |
| `build_portal.py` | Generates the four documents from a property JSON. |
| `assign_agent.py` | Points a built portal at a listing agent. |
| `templates/` | The four sample HTML files. Only their CSS is used. |
| `properties/` | One JSON per property. |

## Restyling

`build_portal.py` lifts the `<head>` — all CSS — live from `templates/*.html`
and generates only the `<body>`. To restyle every future portal, edit the CSS
in the template files. Do not edit generated output; it gets overwritten.

## The standard portal

The nav page follows the 502 Spring St portal: hero photo, Seller Strategy box,
Roadmap card + PDF, the buyer-report caption line, Buyer Report card + PDF, the
three Gateway reports (Absorption Rate, % Under Contract, Inventory vs Sales),
the listing website, then the Resources block.

There is **no Agent Track Record card** in the standard portal, so
`assign_agent.py` only rewrites the footer contact line and the Tracker's
listing-agent card there. The Seller Tracker card is **not** standard either —
it is included by default because it was asked for; set `"include_tracker":
false` to drop it.

Set `hero_photo` and `listing_page_url` per property. Images are copied from
`asset_dir`; a referenced file that is not there is reported, not silently
skipped.

## What the builder will not do

Sections with no data are **omitted, never filled with placeholders**:

- No market stats → the market heading still links to the live report, but no
  stats table prints.
- No absorption figures → no zone strip.
- No photos → no gallery at all.
- No remarks → no Premium Rating block.
- No notes → no Notes section.

Every omission is listed at the end of the run. Read that output — a missing
section is silent in the document but never silent in the console.

## The pricing rules it encodes

Anchoring runs off the **lower** of Customary Value and Customary List Price,
down to the nearest grid line ($50K, or $25K under $500,000), minus $1.

With **Extraordinary Upgrades**, Premium becomes a range (Customary + 33% to
Customary + 50% of upgrades) and anchoring runs off the closest *major*
threshold under the bottom of that range. With a **Discount**, Dated becomes a
range and anchoring runs off the 100%-of-discount figure.

**Two different threshold numbers, and they must not be conflated.** The
"Closest Buyer Threshold" cell in the Pricing Strategy table always shows the
plain grid line. The major-threshold list is used *only* by the alert check.
The alert fires when Coming Soon sits $10K–$100K above the nearest major
(sub-$2M) or $10K–$150K (over $2M) — and never when the anchor grid line is
itself a major threshold, because $2.15M is not a special case for the initial
price.

**Predictive Analysis** takes the standard grid step down, except for three
specific pairs: $1.1M→$1M, $2.15M→$2M, $2.5M→$2.35M. This is a list, not a
formula. Add to `FALLBACK_PAIRS` in `pricing.py` when a new pair is confirmed,
and add a test.

## Adding a rule

Change `pricing.py`, add a case to `test_pricing.py`, run the tests. If an
existing test breaks, stop — that means the change contradicts a package
already reviewed and sent. Check before editing the expectation.

## Known ambiguity

The rules doc calls the 100%-of-discount figure the "top" of the Dated Range
even though it is numerically the lower number. The code follows the printed
order and **raises a warning** on every discount property so it gets checked
by hand. Resolve this properly the next time a real discount property comes up.
