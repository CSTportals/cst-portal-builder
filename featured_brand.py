"""CASEY SAMSON Team Gold Standard Featured Home / Featured Estate.

Casey, 26 Nov 2026 (trying a new brand for the Buyer Portal):
  - Full title: "CASEY SAMSON Team Gold Standard Featured Home".
  - List price over $1,995,000 is a Featured Estate; abbreviation
    "CST Featured Estate" (and "CST Featured Home").
  - Cinzel throughout the header. Featured Home: ivory, dark gold, charcoal.
    Featured Estate: black, metallic gold, ivory.
  - Tagline: "The Home. The Lifestyle. The Value."
Opt in per home with buyer_portal.featured_brand: true (trial).
"""

ESTATE_OVER = 1_995_000
# Cinzel ships with the site (assets/fonts, SIL Open Font License) so it shows
# even where Google Fonts is blocked.
FONT = "".join(
    "@font-face{font-family:'Cinzel';font-style:normal;font-weight:%d;font-display:swap;"
    "src:url('fonts/cinzel-latin-%d-normal.woff2') format('woff2')}" % (w, w) for w in (500, 600, 700))


def copy_fonts(out):
    import shutil
    from pathlib import Path
    src = Path(__file__).resolve().parent / "assets" / "fonts"
    dst = Path(out) / "fonts"
    dst.mkdir(exist_ok=True)
    for f in src.glob("cinzel-*.woff2"):
        shutil.copy(f, dst / f.name)


def enabled(b):
    return bool((b or {}).get("featured_brand"))


def tier(b):
    lp = (b or {}).get("list_price") or 0
    return "Estate" if lp > ESTATE_OVER else "Home"


def short_name(b):
    return f"CST Featured {tier(b)}"


def full_name(b):
    return f"CASEY SAMSON Team Gold Standard Featured {tier(b)}"


CSS = """
.fb{display:inline-block;margin:0 auto 18px;padding:26px 44px 22px;border:2px solid;border-radius:14px;
  font-family:'Cinzel',Georgia,serif;text-align:center;max-width:92%;box-sizing:border-box}
.fb .t{font-size:15px;font-weight:600;letter-spacing:.22em;text-transform:uppercase}
.fb .g{font-size:46px;font-weight:700;letter-spacing:.06em;line-height:1.05;margin-top:10px}
.fb .f{font-size:36px;font-weight:600;letter-spacing:.09em;line-height:1.1}
.fb hr{border:0;border-top:1.5px solid;margin:16px auto 12px;width:100%}
.fb .l{font-size:15px;letter-spacing:.06em}
.fb.home{background:rgba(250,247,240,.94);border-color:#C2A877;color:#2B2B2B}
.fb.home .g{color:#8C7040}.fb.home hr{border-color:#B89A62}.fb.home .l{color:#4A4740}
.fb.estate{background:rgba(18,18,18,.86);border-color:#B8975A;color:#F5EFE2}
.fb.estate .g{color:#C9A96B;background:linear-gradient(180deg,#E3CB92 0%,#C4A46A 55%,#9C7C45 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.fb.estate hr{border-color:#B8975A}.fb.estate .l{color:#E8E0CF}
@media(max-width:640px){.fb{padding:18px 18px 16px}.fb .t{font-size:11px}.fb .g{font-size:28px}
  .fb .f{font-size:22px}.fb .l{font-size:12px}}
"""


def block(b):
    t = tier(b)
    return (f'<div class="fb {t.lower()}"><div class="t">CASEY SAMSON TEAM</div>'
            f'<div class="g">GOLD STANDARD</div><div class="f">FEATURED {t.upper()}</div>'
            '<hr><div class="l">The Home. The Lifestyle. The Value.</div></div>')
