"""Marketing and Negotiation sections on the Seller Roadmap, after The Launch.

Casey, 27 Nov 2026: "Add Marketing section and Contract negotiating section"
-- wording is Casey's, same day. Shown on the Sample; a property turns them on
with "roadmap_sections": true.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).parent
TEAM_PHOTO = HERE / "assets" / "team" / "CST_Team.jpg"

MARKETING = {
    "title": "Marketing", "eyebrow": "Your Home",
    "intro": ["Marketing is how we create competition. It begins with professional photography, "
              "compelling video, and a custom property website designed to showcase your home&rsquo;s "
              "unique features and attract the largest qualified buyer pool.",
              "We use the Coming Soon period to build excitement and drive buyers to your home&rsquo;s "
              "website in four ways:"],
    "items": [("Targeted Social Media", "reaches qualified buyers locally, nationally, and internationally "
               "based on demographics, interests, and online behavior."),
              ("MLS Exposure", "instantly notifies Realtors and buyers with saved searches, directing them "
               "to your home&rsquo;s custom website."),
              ("Targeted Local Marketing", "reaches renters, corporate housing communities, and buyers "
               "searching for homes in your school district."),
              ("Neighborhood Outreach", "engages your neighbors, who are often the biggest advocates for the "
               "community and an important source of referrals to family, friends, and colleagues.")],
    "close": "Our goal is simple: create maximum exposure during the most important days on the market. "
             "By generating early interest and attracting the largest pool of qualified buyers, we create the "
             "confidence and competition that inspire buyers to pay Premium Value&trade;.",
}

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
    return CSS + _sec(MARKETING) + _sec(NEGOTIATION)


def team_photo(p, out):
    """Casey, 27 Nov 2026: the team photo, at the top of the team section."""
    if not (enabled(p) and TEAM_PHOTO.exists()):
        return ""
    shutil.copy(TEAM_PHOTO, Path(out) / TEAM_PHOTO.name)
    return f'<img class="rs-team" src="{TEAM_PHOTO.name}" alt="The Casey Samson Team">'
