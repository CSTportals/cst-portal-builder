"""Marketing and Negotiation sections on the Seller Roadmap, after The Launch.

Casey, 27 Nov 2026: "Add Marketing section and Contract negotiating section"
-- wording is Casey's, same day. Shown on the Sample; a property turns them on
with "roadmap_sections": true.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).parent
TEAM_PHOTO = HERE / "assets" / "team" / "CST_Team.jpg"

# Casey, 27 Nov 2026 (second draft): four numbered, equal panels in the
# Roadmap's gold, with a graphic.
MARKETING = {
    "title": "Marketing", "eyebrow": "Creating Competition for Your Home",
    "intro": ["Effective marketing is not simply about advertising your home. It is about creating "
              "competition among the largest pool of qualified buyers.",
              "Our Gold Standard Marketing Strategy begins with professional photography, compelling video "
              "and a custom property website designed to showcase your home&rsquo;s unique features, "
              "authenticated value and the lifestyle it offers."],
    "channels_head": "Four Channels of Exposure",
    "channels_lead": "During the Coming Soon period, we build anticipation and drive prospective buyers to "
                     "your home&rsquo;s custom website through four targeted marketing channels:",
    "channels": [
        ("geo", "Targeted Social Media", "Using geofencing, we reach buyers searching in more expensive "
         "markets who may recognize exceptional value in your home and be willing to pay a premium."),
        ("mls", "MLS Exposure", "We reach Realtors and buyers with established search criteria, generating "
         "early interest before your home officially enters the market."),
        ("local", "Targeted Local Marketing", "We reach renters, corporate housing communities and buyers "
         "specifically searching within your school district and surrounding market."),
        ("hood", "Neighborhood Outreach", "Your neighbors are often your community&rsquo;s greatest "
         "ambassadors, connecting us with friends, family and colleagues who may already want to live "
         "in your neighborhood."),
    ],
    "close_head": "Maximum Exposure. Maximum Competition.",
    "close": "The most valuable days on the market are the first few. Our strategy is designed to capitalize "
             "on those days by building buyer confidence, creating urgency and generating competition that "
             "inspires buyers to pay Premium Value&trade;.",
}

_S = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    # a target with rings: geofencing
    "geo": f'<svg viewBox="0 0 40 40" {_S}><circle cx="20" cy="20" r="15"/><circle cx="20" cy="20" r="9"/>'
           '<circle cx="20" cy="20" r="3" fill="currentColor"/><path d="M20 2v6M20 32v6M2 20h6M32 20h6"/></svg>',
    # a search lens over a listing card: saved searches
    "mls": f'<svg viewBox="0 0 40 40" {_S}><rect x="5" y="6" width="22" height="26" rx="2"/>'
           '<path d="M10 13h12M10 18h12M10 23h7"/><circle cx="27" cy="27" r="6"/><path d="M31.5 31.5L36 36"/></svg>',
    # a map pin on a school roof line: local
    "local": f'<svg viewBox="0 0 40 40" {_S}><path d="M20 36s-11-10-11-19a11 11 0 0 1 22 0c0 9-11 19-11 19z"/>'
             '<path d="M14 18l6-5 6 5M16 17v5h8v-5"/></svg>',
    # three houses: neighbors
    "hood": f'<svg viewBox="0 0 40 40" {_S}><path d="M3 20l6-5 6 5v12H3z"/><path d="M14 17l6-6 6 6v15H14z"/>'
            '<path d="M25 20l6-5 6 5v12H25z"/><path d="M18 32v-6h4v6"/></svg>',
}


def _flow():
    """Four channels -> the home's website -> competition -> Premium Value."""
    steps = [("4", "Channels"), ("&#8962;", "Your Home&rsquo;s Website"),
             ("&#8644;", "Buyer Competition"), ("&#9733;", "Premium Value&trade;")]
    out = ""
    for k, (g, t) in enumerate(steps):
        out += (f'<div class="mk-step"><div class="mk-dot">{g}</div><div class="mk-st">{t}</div></div>'
                + ('<div class="mk-arr" aria-hidden="true"></div>' if k < len(steps) - 1 else ""))
    return f'<div class="mk-flow">{out}</div>'


def _marketing(d):
    panels = "".join(
        f'<div class="mk-p"><div class="mk-n">{n:02d}</div><div class="mk-i">{ICONS[k]}</div>'
        f'<h4>{t}</h4><p>{x}</p></div>'
        for n, (k, t, x) in enumerate(d["channels"], 1))
    return ('<section class="rs-sec rs-mkt"><div class="wrap">'
            f'<h2 class="section-title">{d["title"]}</h2><div class="rs-eb">{d["eyebrow"]}</div>'
            '<div class="rs-body">' + "".join(f"<p>{x}</p>" for x in d["intro"]) + '</div>'
            + _flow()
            + f'<h3 class="mk-h">{d["channels_head"]}</h3><p class="mk-lead">{d["channels_lead"]}</p>'
            f'<div class="mk-grid">{panels}</div>'
            f'<h3 class="mk-h mk-close-h">{d["close_head"]}</h3>'
            f'<div class="rs-body"><p class="mk-close">{d["close"]}</p></div>'
            '</div></section>\n')


# Casey, 27 Nov 2026 (second draft): dressed up like Marketing, with The CST
# Standard as a three-column gold table.
NEGOTIATION = {
    "title": "Negotiation", "eyebrow": "Expertise", "sub": "Close on the Seller&rsquo;s Terms",
    "intro": "Creating buyer competition is only the beginning. When our pricing, preparation and marketing "
             "strategies generate multiple offers, our negotiation expertise converts that competition into "
             "maximum value for the seller.",
    "approaches_head": "Two Approaches to Multiple Offers",
    "approaches": [
        ("no", "Escalation Clauses", "Favor the Buyer",
         "Escalation clauses allow buyers to submit a lower offer and increase their price only when necessary "
         "to outbid the competition. While many listing agents accept escalation clauses, <b>we do not</b>."),
        ("yes", "Highest and Best", "Favors the Seller",
         "By asking buyers to submit their strongest offer upfront, we often generate one or two offers "
         "$25,000 to $75,000 above the next closest offer. This strategy also encourages buyers to eliminate "
         "home inspection and appraisal contingencies, strengthening the contract and reducing the "
         "seller&rsquo;s risk."),
    ],
    "eval_head": "Evaluating the Entire Contract",
    "eval_lead": "Price is only one component of a successful negotiation. We carefully evaluate every offer based on:",
    "eval": ["Purchase price and net proceeds", "Contingencies and financial risk", "Financing and down payment",
             "Experience of the buyer&rsquo;s agent",
             # Casey, 27 Nov 2026: the lender gets its own check.
             "Lender &mdash; Top 5 Correspondent lenders preferred",
             "Settlement date and rent-back options"],
    "standard": [("80%", "Sell in Under 10 Days"), ("74%", "Sell Above List Price"),
                 ("90%", "No Home Inspection Contingency")],
    "standard_foot": "Maximum Value. Minimum Risk. On Your Terms.",
    "standard_note": "These results reflect a proven strategy, not simply favorable market conditions.",
    "close_head": "Maximum Value. Minimum Risk.",
    "close": "Our goal is not simply to secure the highest offer. It is to secure the strongest contract, at "
             "the highest possible price, with the least amount of risk &mdash; on the seller&rsquo;s terms.",
}

_MARK = {"yes": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" '
                'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
         "no": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" '
               'stroke-linecap="round"><path d="M7 7l10 10M17 7L7 17"/></svg>'}


def _negotiation(d):
    appr = "".join(
        f'<div class="ng-a ng-{k}"><div class="ng-mk">{_MARK[k]}</div><h4>{t}</h4>'
        f'<div class="ng-who">{w}</div><p>{x}</p></div>' for k, t, w, x in d["approaches"])
    ev = "".join(f'<li><span class="ng-ck">{_MARK["yes"]}</span>{x}</li>' for x in d["eval"])
    std = ('<table class="ng-std"><thead><tr><th colspan="3">The CST Standard</th></tr></thead><tbody><tr>'
           + "".join(f'<td><div class="n">{n}</div><div class="l">{l}</div></td>' for n, l in d["standard"])
           + f'</tr></tbody><tfoot><tr><td colspan="3">{d["standard_foot"]}</td></tr></tfoot></table>')
    return ('<section class="rs-sec rs-neg"><div class="wrap">'
            f'<h2 class="section-title">{d["title"]}</h2><div class="rs-eb">{d["eyebrow"]}</div>'
            f'<p class="rs-sub">{d["sub"]}</p>'
            f'<div class="rs-body"><p>{d["intro"]}</p></div>'
            f'<h3 class="mk-h">{d["approaches_head"]}</h3><div class="ng-grid">{appr}</div>'
            f'<h3 class="mk-h">{d["eval_head"]}</h3><p class="mk-lead">{d["eval_lead"]}</p>'
            f'<ul class="ng-ev">{ev}</ul>'
            f'{std}<p class="ng-note">{d["standard_note"]}</p>'
            f'<h3 class="mk-h mk-close-h">{d["close_head"]}</h3>'
            f'<div class="rs-body"><p class="mk-close">{d["close"]}</p></div>'
            '</div></section>\n')


CSS = """<style>
.rs-sec .rs-eb{text-align:center;font:700 12px Georgia,serif;letter-spacing:.24em;text-transform:uppercase;color:#8A6A2E;margin:-6px 0 6px}
.rs-sec .rs-sub{text-align:center;font:italic 600 19px Georgia,serif;color:#1F2A44;margin:0 0 14px}
.rs-sec .rs-body{max-width:760px;margin:0 auto}
.rs-sec .rs-body p{font-size:16px;line-height:1.6;margin:0 0 12px}
.rs-sec ul.rs-list{list-style:none;padding:0;margin:6px 0 16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.rs-sec ul.rs-list li{background:#fff;border:1px solid #E4DCC8;border-left:3px solid #B8902F;border-radius:8px;padding:12px 14px;font-size:15px;line-height:1.5}
.rs-sec .rs-close{font-weight:700;color:#1F2A44;text-align:center;margin-top:6px!important}
.mk-flow{display:flex;align-items:flex-start;justify-content:center;gap:0;margin:18px auto 26px;max-width:820px;flex-wrap:wrap}
.mk-step{display:flex;flex-direction:column;align-items:center;width:150px;text-align:center}
.mk-dot{width:54px;height:54px;border-radius:50%;background:#1F2A44;color:#E9C77B;border:2px solid #B8902F;display:flex;align-items:center;justify-content:center;font:700 22px Georgia,serif}
.mk-st{font:700 12px Georgia,serif;letter-spacing:.08em;text-transform:uppercase;color:#1F2A44;margin-top:8px;line-height:1.3}
.mk-arr{flex:0 0 34px;height:2px;background:#B8902F;position:relative;margin-top:26px}
.mk-arr:after{content:"";position:absolute;right:-1px;top:-4px;border:5px solid transparent;border-left:7px solid #B8902F;border-right:0}
.mk-h{text-align:center;font:700 22px 'Playfair Display',Georgia,serif;color:#1F2A44;margin:10px 0 6px}
.mk-lead{text-align:center;max-width:720px;margin:0 auto 18px;font-size:16px;line-height:1.6}
.mk-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:0 auto 26px}
.mk-p{background:#fff;border:1px solid #E4DCC8;border-top:4px solid #B8902F;border-radius:10px;padding:18px 16px 16px;text-align:center;display:flex;flex-direction:column}
.mk-n{font:700 30px 'Playfair Display',Georgia,serif;color:#B8902F;line-height:1}
.mk-i{width:44px;height:44px;margin:10px auto 6px;color:#1F2A44}.mk-i svg{width:100%;height:100%}
.mk-p h4{font:700 14px Georgia,serif;letter-spacing:.06em;text-transform:uppercase;color:#1F2A44;margin:4px 0 8px}
.mk-p p{font-size:14.5px;line-height:1.5;margin:0;color:#3d372c}
.mk-close-h{margin-top:4px}.mk-close{text-align:center;font-size:16.5px}
@media(max-width:900px){.mk-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.mk-grid{grid-template-columns:1fr}.mk-step{width:120px}.mk-arr{display:none}}
.ng-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:6px auto 26px;max-width:900px}
.ng-a{background:#fff;border:1px solid #E4DCC8;border-radius:10px;padding:20px 20px 16px;text-align:center;position:relative}
.ng-a.ng-yes{border:2px solid #B8902F}
.ng-mk{width:40px;height:40px;border-radius:50%;margin:0 auto 8px;display:flex;align-items:center;justify-content:center}
.ng-mk svg{width:22px;height:22px}
.ng-no .ng-mk{background:#F4E9E7;color:#B3261E}.ng-yes .ng-mk{background:#1F2A44;color:#E9C77B}
.ng-a h4{font:700 18px 'Playfair Display',Georgia,serif;color:#1F2A44;margin:0}
.ng-who{font:700 11.5px Georgia,serif;letter-spacing:.16em;text-transform:uppercase;margin:4px 0 10px}
.ng-no .ng-who{color:#B3261E}.ng-yes .ng-who{color:#8A6A2E}
.ng-a p{font-size:15px;line-height:1.55;margin:0;color:#3d372c}
.ng-ev{list-style:none;padding:0;margin:0 auto 28px;max-width:900px;display:grid;grid-template-columns:1fr 1fr;gap:10px 22px}
.ng-ev li{display:flex;align-items:center;gap:10px;font-size:15.5px;background:#fff;border:1px solid #E4DCC8;border-radius:8px;padding:10px 12px}
.ng-ck{flex:0 0 24px;height:24px;border-radius:5px;background:#8A6A2E;color:#fff;display:flex;align-items:center;justify-content:center}.ng-ck svg{width:15px;height:15px}
.ng-std{width:100%;max-width:900px;margin:0 auto;border-collapse:collapse;background:#fff;border:1px solid #E4DCC8;border-radius:12px;overflow:hidden;table-layout:fixed}
.ng-std th{font:700 20px Georgia,serif;letter-spacing:.12em;text-transform:uppercase;color:#1F2A44;padding:20px 10px 16px;border-bottom:1.5px solid #B8902F;background:#fff}
.ng-std td{text-align:center;padding:22px 10px;vertical-align:top}
.ng-std tbody td+td{border-left:1px solid #EFE8D8}
.ng-std .n{font:700 44px 'Playfair Display',Georgia,serif;color:#B8902F;line-height:1}
.ng-std .l{font:600 15px Georgia,serif;color:#1F2A44;margin-top:8px}
.ng-std tfoot td{border-top:1.5px solid #B8902F;font:italic 17px Georgia,serif;color:#1F2A44;padding:16px 10px}
.ng-note{text-align:center;font:italic 14px Georgia,serif;color:#71695A;margin:10px 0 18px}
.ng-std,.ng-std th,.ng-std td{min-width:0!important}.ng-std{width:100%!important;display:table!important}
@media(max-width:700px){.ng-std td{padding:16px 4px}.ng-grid,.ng-ev{grid-template-columns:1fr}.ng-std .n{font-size:32px}.ng-std .l{font-size:13px}.ng-std th{font-size:16px}}
.rs-team{display:block;width:100%;max-width:860px;margin:6px auto 22px;border-radius:10px;border:1px solid #E4DCC8}
</style>"""


def enabled(p):
    return bool(p.get("roadmap_sections") or p.get("prefix") == "Sample")


def _sec(d):
    li = "".join(f"<li><b>{k}</b> {v}</li>" for k, v in d["items"])
    return ('<section class="rs-sec"><div class="wrap">'
            f'<h2 class="section-title">{d["title"]}</h2><div class="rs-eb">{d["eyebrow"]}</div>'
            + (f'<p class="rs-sub">{d["sub"]}</p>' if d.get("sub") else "")
            + '<div class="rs-body">' + "".join(f"<p>{x}</p>" for x in d["intro"])
            + f'<ul class="rs-list">{li}</ul>'
            + (f'<p>{d["after"]}</p>' if d.get("after") else "")
            + f'<p class="rs-close">{d["close"]}</p></div></div></section>\n')


def html(p):
    if not enabled(p):
        return ""
    return CSS + _marketing(MARKETING) + _negotiation(NEGOTIATION)


def team_photo(p, out):
    """Casey, 27 Nov 2026: the team photo, at the top of the team section."""
    if not (enabled(p) and TEAM_PHOTO.exists()):
        return ""
    shutil.copy(TEAM_PHOTO, Path(out) / TEAM_PHOTO.name)
    return f'<img class="rs-team" src="{TEAM_PHOTO.name}" alt="The Casey Samson Team">'
