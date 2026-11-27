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


NEGOTIATION = {
    "title": "Negotiation", "eyebrow": "Expertise", "sub": "Close on the Seller&rsquo;s Terms",
    "intro": ["Creating buyer competition is only the beginning. If we&rsquo;ve done our job, your home will "
              "receive multiple offers, and that&rsquo;s when our negotiation strategy delivers the greatest value.",
              "There are two types of offers:"],
    "items": [("Offers with escalation clauses benefit buyers.", "They allow buyers to submit a lower offer with "
               "the option to increase it only if necessary. Many listing agents still accept escalation "
               "clauses. We do not."),
              ("Highest and Best Offers benefit sellers.", "Buyers are asked to submit their strongest offer "
               "upfront, often resulting in one or two offers $25,000 to $75,000 higher than the next closest "
               "buyer. It also encourages buyers to remove contingencies such as home inspections and "
               "appraisals, creating a stronger and more certain contract.")],
    "after": "Beyond price, we carefully evaluate every contract, including contingencies, down payment, "
             "financing, the experience of the buyer&rsquo;s agent and lender, and rent back options.",
    "close": "Our goal isn&rsquo;t simply to accept the highest offer. It&rsquo;s to secure the strongest "
             "contract with the least amount of risk, on your terms.",
}

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
    return CSS + _marketing(MARKETING) + _sec(NEGOTIATION)


def team_photo(p, out):
    """Casey, 27 Nov 2026: the team photo, at the top of the team section."""
    if not (enabled(p) and TEAM_PHOTO.exists()):
        return ""
    shutil.copy(TEAM_PHOTO, Path(out) / TEAM_PHOTO.name)
    return f'<img class="rs-team" src="{TEAM_PHOTO.name}" alt="The Casey Samson Team">'
