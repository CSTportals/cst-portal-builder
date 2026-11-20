# Portal production — read this first

This zip is the portal builder. Unzip it and it runs; it was verified from a
clean directory before being sent.

```bash
cd portal_builder
python3.12 build_portal.py properties/<property>.json      # seller portal FIRST
python3.12 build_buyer_portal.py properties/<property>.json # then buyer portal
python3.12 check_portal.py <property>                       # standing rules
```

**python3.12, not python3.** The builders use nested f-strings that 3.11
cannot parse. `distutils-precedence.pth` prints a harmless traceback on
every run — ignore it.

**Seller portal before buyer portal, always.** The buyer portal copies the
Buyer Report PDF out of the seller folder, so the other order ships a stale
one. `check_portal.py` catches it.

## What is in here

| | |
|---|---|
| `*.py` | the builders, the pricing engine, the checker |
| `properties/*.json` | one file per property — the whole input |
| `templates/` | page shells, the logo, the track record, the example Buyer Report |
| `data/`, `market_pulls/` | the CST resale record and the MLS exports |
| `market_cache.json` | the MSS figures every portal reads |

**Not in here: `assets/`, `output/`, `_site/`** — photos and built portals,
640 MB of them. A new property brings its own photos. To rebuild an existing
one, its `assets/<Prefix>/` folder has to come across too.

## To build a property

Everything a portal needs is on its own JSON file. Copy the nearest existing
property, change the values, build. `properties/6029_erinblair.json` is a
good new listing; `properties/39014_hughesville.json` is a good recovery.

## To hand-set anything

One block, no code change — see `overrides.py`:

```json
"overrides": {
  "coming_soon":  1099999,
  "recovery.soft": 674900,
  "buyer_url":    "https://buyerinblair2.netlify.app"
}
```

Delete a line to go back to the rule. Every one prints in the build log with
what it replaced.

## The launch email

Every property builds `<prefix>_Seller_Email.eml` — the Coming Soon email in
Casey's own words, with the four tool links wired to this property. Two
fields on the property file finish it:

```json
"seller_names": "Lance and Toria",
"overrides": { "coming_soon": 1299999 }
```

Those produce the greeting and the line *"We are going Coming Soon today at
$1.299."* The build log warns that the line says "today". Full rules in the
project doc `seller-emails.md`.

## Rules that changed 19-20 October

- `overrides` block — hand-set any value or link, no code change
- recovery Roadmap leads with the valuation, not the strategy
- `recovery.soft` / `recovery.hard` override the relaunch prices
- the Example Buyer Portal card drops once a portal has pictures and premiums
- "Totally Renovated" is the lead headline whenever it applies
- the seller email is rewritten, and its links run off the netlify hosts

## The rules live in the project, not in here

The "gold standard" project carries the standing rules as docs — pricing,
section order, the track record, the sample mark, portal addresses. A
conversation in that project already has them. This zip is only the code.
