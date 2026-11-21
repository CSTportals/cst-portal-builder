"""Compass overlay for every portal map.

Casey, 21 Nov 2026: "moving forward add Compass so people know what direction
the home is facing." All maps are north-up, so the compass is a fixed overlay
(top right of the map). When the property file says which way the front of
the home faces -- "facing": "SE" (or "southeast", or degrees, 0 = north) at
the property root -- a gold "Front" needle points that way and a caption
reads "Front of the home faces Southeast".
"""

NAMES = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
ABBR = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def bearing(facing):
    if facing in (None, ""):
        return None
    if isinstance(facing, (int, float)):
        return float(facing) % 360
    f = str(facing).strip().lower().replace("-", "").replace(" ", "")
    for i, (n, a) in enumerate(zip(NAMES, ABBR)):
        if f in (n.lower(), a.lower()):
            return i * 45.0
    try:
        return float(f) % 360
    except ValueError:
        return None


def name(b):
    return NAMES[int((b + 22.5) // 45) % 8]


def html(facing=None, size=74):
    b = bearing(facing)
    front = ""
    cap = ""
    if b is not None:
        front = (f'<g transform="rotate({b:g} 50 50)"><line x1="50" y1="50" x2="50" y2="14" '
                 'stroke="#B8902F" stroke-width="5" stroke-linecap="round"/>'
                 '<polygon points="50,6 42,20 58,20" fill="#B8902F"/></g>')
        cap = (f'<div style="margin-top:4px;font:700 10.5px/1.25 system-ui,sans-serif;color:#6f5526;'
               f'background:rgba(255,253,246,.94);border:1px solid #d9c9a3;border-radius:10px;padding:3px 7px;'
               f'text-align:center;white-space:nowrap;">Front faces {name(b)}</div>')
    svg = (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">'
           '<circle cx="50" cy="50" r="46" fill="rgba(255,253,246,.94)" stroke="#d9c9a3" stroke-width="2"/>'
           '<polygon points="50,12 44,50 56,50" fill="#B3261E"/>'
           '<polygon points="50,88 44,50 56,50" fill="#9A9487"/>'
           '<circle cx="50" cy="50" r="4" fill="#1F2A44"/>'
           f'{front}'
           '</svg>')
    return (f'<div class="map-compass" title="Map faces north" style="position:absolute;top:10px;right:10px;'
            f'z-index:800;pointer-events:none;display:flex;flex-direction:column;align-items:center;">'
            f'<div style="font:700 13px Georgia,serif;color:#B3261E;line-height:1;margin-bottom:2px;'
            f'text-shadow:0 0 3px #fff,0 0 3px #fff;">N</div>{svg}{cap}</div>')
