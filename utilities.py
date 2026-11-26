"""Utilities card for the Buyer Portal.

Casey, 26 Nov 2026: "can you find utilities for a listings like power gas
cable etc." -- "yes in the buyer portal for sample". Shown under the facts
card (with the schools) when buyer_portal.utilities is set:
    [[service, provider, phone, note], ...]
note "confirm" marks a provider the seller still needs to confirm.
"""

CSS = """
.util{max-width:880px;margin:16px auto 0;background:#fff;border:1px solid #E5DDC9;border-radius:12px;padding:16px 20px 10px}
.util h3{margin:0 0 8px;text-align:center;font:600 12px Georgia,serif;letter-spacing:.2em;text-transform:uppercase;color:#8A6A2E}
.util table{width:100%;border-collapse:collapse;font:15px Georgia,serif;color:#1F2A44}
.util td{padding:7px 6px;border-top:1px solid #EFE9DA;vertical-align:top}
.util tr:first-child td{border-top:0}
.util td.s{font:600 11.5px Georgia,serif;letter-spacing:.12em;text-transform:uppercase;color:#71695A;width:26%;padding-top:9px}
.util td.p b{font-weight:700}
.util td.t{text-align:right;white-space:nowrap;color:#1F2A44}
.util td.t a{color:#1F2A44;text-decoration:none;border-bottom:1px solid #C9A961}
.util .c{display:inline-block;margin-left:6px;font:italic 12px Georgia,serif;color:#9A7B3F}
.util .src{text-align:center;font:italic 11.5px Georgia,serif;color:#71695A;margin:8px 0 2px}
@media(max-width:560px){.util{padding:14px 12px 8px}.util table{font-size:14px}.util td{padding:7px 4px}.util td.s{width:28%;font-size:10.5px;letter-spacing:.06em}.util td.t{font-size:13px}.util .c{display:block;margin:2px 0 0}}
"""


def card(b):
    rows = (b or {}).get("utilities") or []
    if not rows:
        return ""
    body = ""
    for r in rows:
        svc, prov, phone = r[0], r[1], (r[2] if len(r) > 2 else "")
        note = r[3] if len(r) > 3 else ""
        tel = "".join(ch for ch in phone if ch.isdigit())
        ph = f'<a href="tel:{tel}">{phone}</a>' if tel else phone
        c = '<span class="c">confirm with seller</span>' if note == "confirm" else (
            f'<span class="c">{note}</span>' if note else "")
        body += f'<tr><td class="s">{svc}</td><td class="p"><b>{prov}</b>{c}</td><td class="t">{ph}</td></tr>'
    src = (b.get("utilities_source") or "")
    return (f'<style>{CSS}</style><div class="util"><h3>Utilities</h3><table>{body}</table>'
            + (f'<p class="src">{src}</p>' if src else "") + "</div>")
