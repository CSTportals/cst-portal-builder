#!/usr/bin/env python3
"""Derive a buyer portal's Amenities section from its own locator-map pins.

Casey, 12 Oct 2026: "All buyer portals should have amenities and maps."

Two portals had a verified map but no Amenities block. The pins already carry
name, descriptor and coordinates, so the distances are computed here with the
same haversine-plus-road-factor the map uses — the two can never disagree,
and nothing new is sourced or guessed.

    python3 add_amenities.py properties/117a_park.json
"""
import json
import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

# Which pins go in which card, per property. Written out rather than inferred
# from keywords: two properties is not worth a classifier that would quietly
# file a restaurant under Schools.
GROUPS = {
    "117A_Park": [
        ("Walk to Town", ["Town Green", "Vienna Inn", "Caffè Amouri",
                          "Evelyn Rose", "Bards Alley", "Roberto’s"]),
        ("Every Day", ["Whole Foods", "Community Center", "Post Office"]),
    ],
    "9854_Lieuvin": [
        ("Getting Around", ["Spring Hill Metro"]),
        ("Every Day", ["Whole Foods, The Boro", "Tysons Galleria",
                       "Roots Cafe", "Starbucks", "801 Chophouse",
                       "Caboose Brewing"]),
        ("Parks, Schools and Town", ["Wolf Trap National Park",
                                     "Wolftrap Elementary", "Town Green"]),
    ],
}
LEDE = {
    "117A_Park": "Vienna&rsquo;s town green, its restaurants and its shops are "
                 "a walk from the front door, not a drive.",
    "9854_Lieuvin": "Tysons is ten minutes east and Wolf Trap ten minutes "
                    "south, with the Silver Line between them.",
}


def road_miles(clat, clng, lat, lng):
    """Straight line with the same 1.30 road factor the map applies."""
    la1, lo1, la2, lo2 = map(radians, (clat, clng, lat, lng))
    d = 2 * asin(sqrt(sin((la2 - la1) / 2) ** 2
                      + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2))
    return 3958.8 * d * 1.30


def distance_value(mi):
    """What the Amenities row should carry, matching the map's own call.

    The map decides walk-or-drive at 15 minutes on foot; a bare mileage would
    make amenities_section print "1 min" for everything inside half a mile,
    which is both useless and a different answer from the pin beside it.
    drive_time() passes a written-out label straight through, so walkable
    places carry the walk and everything else carries miles for it to convert.
    """
    walk = max(1, round(mi / 3.0 * 60))          # 3 mph on foot
    if walk <= 15:
        return f"{walk} min walk", round(mi, 2)
    return round(mi, 2), round(mi, 2)


def main(path):
    f = Path(path)
    p = json.loads(f.read_text())
    pre, b = p["prefix"], p["buyer_portal"]
    lm = b.get("locator_map")
    if not lm or not lm.get("pins"):
        print(f"{pre}: no locator_map pins — nothing to derive from.")
        return 1
    if pre not in GROUPS:
        print(f"{pre}: no grouping defined in GROUPS.")
        return 1

    by_name = {pin["name"]: pin for pin in lm["pins"]}
    c = lm["center"]
    groups, used, missing = [], set(), []
    for title, names in GROUPS[pre]:
        items = []
        for n in names:
            pin = by_name.get(n)
            if not pin:
                missing.append(n)
                continue
            used.add(n)
            mi = road_miles(c["lat"], c["lng"], pin["lat"], pin["lng"])
            shown, sort_mi = distance_value(mi)
            items.append(([n, pin.get("sub", ""), shown], sort_mi))
        items = [r for r, _ in sorted(items, key=lambda x: x[1])]
        if items:
            groups.append({"title": title, "items": items})

    if missing:
        print(f"  !! named in GROUPS but not on the map: {', '.join(missing)}")
    left = [n for n in by_name if n not in used]
    if left:
        print(f"  !! map pins left out of the amenities: {', '.join(left)}")

    b["amenities"] = groups
    b["amenities_lede"] = LEDE[pre]
    f.write_text(json.dumps(p, indent=1, ensure_ascii=False))
    n = sum(len(g["items"]) for g in groups)
    print(f"{pre}: {len(groups)} cards, {n} places, distances computed "
          "from the map's own coordinates.")
    for g in groups:
        print(f"   {g['title']}: "
              + ", ".join(f"{i[0]} ({i[2]})" for i in g["items"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
