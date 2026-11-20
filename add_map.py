#!/usr/bin/env python3
"""Add a locator map and amenities to a buyer portal from verified places.

Casey, 12 Oct 2026: "All buyer portals should have amenities and maps."

Every coordinate below was looked up and sourced; nothing is interpolated,
averaged or inferred from a neighbouring place. Walk/drive times and the
amenity distances are computed from these coordinates by the same formula
the map itself uses, so the two can never disagree.

    python3 add_map.py 403_John_Marshall
"""
import json
import sys
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from pathlib import Path

# name, descriptor, lat, lng, amenity card ("" keeps it off the list)
DATA = {
    # 10015 Saddle Rd, Vienna (Carriage Hill). Casey, 13 Oct 2026: "add
    # amenities and maps."
    #
    # STILL MISSING: Flint Hill Elementary (2444 Flint Hill Rd) and Thoreau
    # Middle, this property's own elementary and middle schools. No reachable
    # source publishes their coordinates -- the state school profile gives the
    # address only, and the GNIS "Flint Hill" entry is a summit in Franklin
    # County. They are the two pins worth sourcing next; nothing here is
    # estimated in their place.
    #
    # Every pin below is a coordinate already verified for another Vienna
    # portal, reused here rather than re-sourced.
    "10015_Saddle": {
        # Verified 13 Oct 2026 from the property's own listing page geo
        # metadata (meta-ICBM / geo.position), which also confirms the 1.11
        # acre lot and the Flint Hill / Thoreau / Madison school assignment
        # Casey's remarks give.
        "center": (38.9184896, -77.2927599, "10015 Saddle Rd"),
        "title": "The Neighborhood",
        "lede": "Downtown Vienna&rsquo;s restaurants, coffee and the Town "
                "Green are a few minutes south, with Madison High just beyond "
                "them. The arrow points to everything past the edge of the "
                "map.",
        "amen_lede": "Downtown Vienna is a short drive south, and Madison "
                     "High is on the way there.",
        # NOT PINNED, and not estimated in their place:
        #   Clarks Crossing Park and the W&OD Trail access that Carriage Hill
        #     actually adjoins. The only verified W&OD coordinate on file is
        #     the Mill St NE access downtown, 1.83 road miles away -- pinning
        #     that would put "1.8 mi" against a trail Casey's own remarks say
        #     the neighbourhood backs onto. Wrong in the worst direction, so
        #     it is left out until the Clarks Crossing access is sourced.
        #   Flint Hill Elementary (2444 Flint Hill Rd) and Thoreau Middle,
        #     this property's own elementary and middle schools. No reachable
        #     source publishes their coordinates.
        # Every pin below is a coordinate already verified for another Vienna
        # portal, reused here rather than re-sourced.
        "pins": [
            ("James Madison High School", "Fairfax County Public Schools",
             38.8961219, -77.2788162, "Schools and Parks"),
            ("Evelyn Rose", "Tasting menu on Church St NW",
             38.9020805, -77.2670056, "Downtown Vienna"),
            ("Caff&egrave; Amouri", "Coffee roaster on Church St",
             38.9024734, -77.2657028, "Downtown Vienna"),
            ("Vienna Town Green", "Concerts, markets, Viva Vienna",
             38.9029410, -77.2641239, "Downtown Vienna"),
            ("Vienna Inn", "The 1960 town institution",
             38.9022013, -77.2647713, "Downtown Vienna"),
            ("Whole Foods", "143 Maple Ave E",
             38.9022469, -77.2626957, "Every Day"),
            ("Giant Food", "359 Maple Ave E",
             38.9053633, -77.2580414, "Every Day"),
            ("Vienna Community Center", "Classes, gym and programs",
             38.9008267, -77.2603307, "Every Day"),
        ],
        "arrows": [((38.8775790, -77.2724610), "Vienna Metro", "Orange Line")],
    },
    # 702 Ware St SW, Vienna (Town of Vienna). Casey, 30 Oct 2026: "Need
    # amenities, maps". Every coordinate from Google Places, 30 Oct 2026 --
    # the house itself from its own Places street-address record.
    # 10315 Mountington Ct, Vienna (Tamarack). Casey, 30 Oct 2026: "Need
    # buyer portal". Every coordinate from Google Places, 30 Oct 2026.
    "10315_Mountington": {
        "center": (38.9327839, -77.3032968, "10315 Mountington Ct"),
        "title": "The Neighborhood",
        "lede": "The W&amp;OD Trail crosses Hunter Mill Road at the end of "
                "the street, with Hunter Mill Swim &amp; Racquet just north. "
                "The arrows point to everything past the edge of the map.",
        "amen_lede": "The W&amp;OD Trail at the end of the street, the Silver "
                     "Line ten minutes north, and downtown Vienna and Reston "
                     "Town Center either way.",
        "pins": [
            ("W&amp;OD Trail", "Trail crossing at Hunter Mill Rd",
             38.9327137, -77.3050308, "Parks and Recreation"),
            ("Hunter Mill Swim &amp; Racquet", "Neighborhood pool and tennis",
             38.942627, -77.3070604, "Parks and Recreation"),
            ("Oakton Shopping Center", "Giant, CVS and restaurants",
             38.883081, -77.2998168, "Shopping"),
            ("Luciano Italian", "Family Italian in Oakton",
             38.881201, -77.3020175, "Family Dining"),
            ("Wiehle-Reston East Metro", "Silver Line",
             38.947762, -77.3401002, "Getting Around"),
        ],
        "arrows": [((38.9020805, -77.2670056), "Downtown Vienna", "Maple Ave dining"),
                   ((38.9589096, -77.3614631), "Reston Town Center", "Shops and dining"),
                   ((38.917017, -77.2228361), "Tysons Corner Center", "Shopping"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        "extra": [("Fine Dining", "Evelyn Rose", "Tasting menu, Church St NW", 38.9020805, -77.2670056),
                  ("Fine Dining", "Cafe Renaissance", "French, Glyndon St SE", 38.9041085, -77.2604861),
                  ("Fine Dining", "The Maple Room", "Steaks and seafood, Maple Ave W", 38.8964444, -77.2722695),
                  ("Fine Dining", "Ristorante Bonaroti", "Italian, Maple Ave E", 38.9089849, -77.2564496),
                  ("Family Dining", "The Virginian Restaurant", "Classic diner, Vienna", 38.9041519, -77.2602158),
                  ("Family Dining", "Artie&rsquo;s", "American, Fairfax", 38.8623584, -77.2773561),
                  ("Shopping", "Reston Town Center", "Shops, dining and events", 38.9589096, -77.3614631),
                  ("Shopping", "Tysons Corner Center", "Regional mall", 38.917017, -77.2228361),
                  ("Getting Around", "Vienna Metro", "Orange Line", 38.877579, -77.272461),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },
    "9719_Cinnamon_Creek": {
        "center": (38.9431145, -77.2803541, "9719 Cinnamon Creek Dr"),
        "title": "The Neighborhood",
        "lede": "Meadowlark Botanical Gardens is around the corner and a "
                "wooded trail runs to Wolf Trap; the Silver Line, Tysons and "
                "downtown Vienna are each a short drive. The arrows point to "
                "everything past the edge of the map.",
        "amen_lede": "Meadowlark Gardens around the corner, a trail to Wolf "
                     "Trap, and the Silver Line, Tysons and downtown Vienna a "
                     "few minutes away.",
        "pins": [
            ("Meadowlark Botanical Gardens", "Gardens, trails and the koi pond",
             38.9380317, -77.2819304, "Parks and Recreation"),
            ("Wolf Trap National Park", "Filene Center concerts and trails",
             38.9383676, -77.264695, "Parks and Recreation"),
            ("Hunter Mill Swim &amp; Racquet", "Neighborhood pool and tennis",
             38.942627, -77.3070604, "Parks and Recreation"),
            ("W&amp;OD Trail", "Trail crossing at Hunter Mill Rd",
             38.9327137, -77.3050308, "Parks and Recreation"),
            ("Spring Hill Metro", "Silver Line",
             38.928776, -77.241455, "Getting Around"),
            ("Wiehle-Reston East Metro", "Silver Line",
             38.947762, -77.3401002, "Getting Around"),
            ("Whole Foods, The Boro", "Shops, dining and cinema",
             38.924755, -77.2334584, "Shopping"),
            ("Roots Cafe", "Coffee &middot; Old Dominion Dr",
             38.9523465, -77.2246768, "Family Dining"),
        ],
        "arrows": [((38.9020805, -77.2670056), "Downtown Vienna", "Maple Ave dining"),
                   ((38.9589096, -77.3614631), "Reston Town Center", "Shops and dining"),
                   ((38.917017, -77.2228361), "Tysons Corner Center", "Shopping"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        "extra": [("Fine Dining", "Evelyn Rose", "Tasting menu, Church St NW", 38.9020805, -77.2670056),
                  ("Fine Dining", "Cafe Renaissance", "French, Glyndon St SE", 38.9041085, -77.2604861),
                  ("Fine Dining", "The Maple Room", "Steaks and seafood, Maple Ave W", 38.8964444, -77.2722695),
                  ("Fine Dining", "Ristorante Bonaroti", "Italian, Maple Ave E", 38.9089849, -77.2564496),
                  ("Family Dining", "Vienna Inn", "The 1960 town institution", 38.9022013, -77.2647713),
                  ("Family Dining", "The Virginian Restaurant", "Classic diner, Vienna", 38.9041519, -77.2602158),
                  ("Shopping", "Reston Town Center", "Shops, dining and events", 38.9589096, -77.3614631),
                  ("Shopping", "Tysons Corner Center", "Regional mall", 38.917017, -77.2228361),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },
    "1531_Windstone": {
        "center": (38.9487022, -77.2944461, "1531 Windstone Dr"),
        "title": "The Neighborhood",
        "lede": "Five private acres off Browns Mill Road, backing to the "
                "Difficult Run parkland, with Meadowlark Gardens, Wolf Trap "
                "and the Silver Line each a few minutes away. The arrows point "
                "to everything past the edge of the map.",
        "amen_lede": "Parkland out back, Meadowlark Gardens and Wolf Trap "
                     "minutes away, and Tysons, Reston and downtown Vienna an "
                     "easy drive.",
        "pins": [
            ("Meadowlark Botanical Gardens", "Gardens, trails and the koi pond",
             38.9380317, -77.2819304, "Parks and Recreation"),
            ("Wolf Trap National Park", "Filene Center concerts and trails",
             38.9383676, -77.264695, "Parks and Recreation"),
            ("Hunter Mill Swim &amp; Racquet", "Neighborhood pool and tennis",
             38.942627, -77.3070604, "Parks and Recreation"),
            ("W&amp;OD Trail", "Trail crossing at Hunter Mill Rd",
             38.9327137, -77.3050308, "Parks and Recreation"),
            ("Spring Hill Metro", "Silver Line",
             38.928776, -77.241455, "Getting Around"),
            ("Wiehle-Reston East Metro", "Silver Line",
             38.947762, -77.3401002, "Getting Around"),
            ("Whole Foods, The Boro", "Shops, dining and cinema",
             38.924755, -77.2334584, "Shopping"),
            ("Roots Cafe", "Coffee &middot; Old Dominion Dr",
             38.9523465, -77.2246768, "Family Dining"),
        ],
        "arrows": [((38.9020805, -77.2670056), "Downtown Vienna", "Maple Ave dining"),
                   ((38.9589096, -77.3614631), "Reston Town Center", "Shops and dining"),
                   ((38.917017, -77.2228361), "Tysons Corner Center", "Shopping"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        "extra": [("Fine Dining", "Evelyn Rose", "Tasting menu, Church St NW", 38.9020805, -77.2670056),
                  ("Fine Dining", "Cafe Renaissance", "French, Glyndon St SE", 38.9041085, -77.2604861),
                  ("Fine Dining", "The Maple Room", "Steaks and seafood, Maple Ave W", 38.8964444, -77.2722695),
                  ("Fine Dining", "Ristorante Bonaroti", "Italian, Maple Ave E", 38.9089849, -77.2564496),
                  ("Family Dining", "Vienna Inn", "The 1960 town institution", 38.9022013, -77.2647713),
                  ("Family Dining", "The Virginian Restaurant", "Classic diner, Vienna", 38.9041519, -77.2602158),
                  ("Shopping", "Reston Town Center", "Shops, dining and events", 38.9589096, -77.3614631),
                  ("Shopping", "Tysons Corner Center", "Regional mall", 38.917017, -77.2228361),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },
    "4861_Autumn_Glory": {
        "center": (38.8611912, -77.4213424, "4861 Autumn Glory Way"),
        "title": "The Neighborhood",
        "lede": "Ellanor C. Lawrence Park is at the end of the neighborhood, "
                "with Wegmans and the Route 50 shops a few minutes north and "
                "Fairfax Corner east. The arrows point to everything past the "
                "edge of the map.",
        "amen_lede": "A 650-acre park next door, Wegmans and the Route 50 "
                     "corridor minutes away, and Dulles International a short "
                     "drive north.",
        "pins": [
            ("Ellanor C. Lawrence Park", "Trails, pond and the Walney visitor center",
             38.8609445, -77.4306907, "Parks and Recreation"),
            ("Wegmans", "Newbrook Dr, Chantilly",
             38.877681, -77.443842, "Shopping"),
            ("Greenbriar Town Center", "Giant and neighborhood shops",
             38.8795278, -77.3984838, "Shopping"),
            ("Lazy Dog Restaurant &amp; Bar", "Family &middot; American, Newbrook Dr",
             38.8773378, -77.4410868, "Family Dining"),
            ("Farmside Kitchen", "Family &middot; farm-to-table bowls",
             38.8765402, -77.4416687, "Family Dining"),
            ("The Capital Grille", "Steaks &middot; Fair Lakes Promenade",
             38.86028, -77.36602, "Fine Dining"),
        ],
        "arrows": [((38.857595, -77.358925), "Fairfax Corner", "Shops, dining, cinema"),
                   ((38.9109189, -77.4442075), "Udvar-Hazy Center", "Air and Space Museum"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        "extra": [("Fine Dining", "Elyse", "Tasting menu, Fairfax Blvd", 38.8549006, -77.3175016),
                  ("Fine Dining", "2941 Restaurant", "Fairview Park, Falls Church", 38.869599, -77.2151868),
                  ("Family Dining", "Silver Diner", "South Riding, Route 50", 38.912255, -77.4786),
                  ("Shopping", "Fairfax Corner", "Shops, dining and cinema", 38.857595, -77.358925),
                  ("Shopping", "Franklin Farm Village Center", "Groceries and services", 38.9084252, -77.4070076),
                  ("Parks and Recreation", "Cox Farms", "Fall festival and market", 38.8823765, -77.4900082),
                  ("Parks and Recreation", "Udvar-Hazy Center", "Smithsonian Air and Space", 38.9109189, -77.4442075),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },
    "1416_Rosewood_Hill": {
        "center": (38.9566783, -77.2895427, "1416 Rosewood Hill Dr"),
        "title": "The Neighborhood",
        "lede": "Meadowlark Botanical Gardens and Wolf Trap are a few "
                "minutes south; the Silver Line, Tysons and "
                "downtown Vienna are each a short drive. The arrows point to "
                "everything past the edge of the map.",
        "amen_lede": "Meadowlark Gardens and Wolf Trap "
                     "minutes away, and the Silver Line, Tysons and downtown Vienna a "
                     "few minutes away.",
        "pins": [
            ("Meadowlark Botanical Gardens", "Gardens, trails and the koi pond",
             38.9380317, -77.2819304, "Parks and Recreation"),
            ("Wolf Trap National Park", "Filene Center concerts and trails",
             38.9383676, -77.264695, "Parks and Recreation"),
            ("Hunter Mill Swim &amp; Racquet", "Neighborhood pool and tennis",
             38.942627, -77.3070604, "Parks and Recreation"),
            ("W&amp;OD Trail", "Trail crossing at Hunter Mill Rd",
             38.9327137, -77.3050308, "Parks and Recreation"),
            ("Spring Hill Metro", "Silver Line",
             38.928776, -77.241455, "Getting Around"),
            ("Wiehle-Reston East Metro", "Silver Line",
             38.947762, -77.3401002, "Getting Around"),
            ("Whole Foods, The Boro", "Shops, dining and cinema",
             38.924755, -77.2334584, "Shopping"),
            ("Roots Cafe", "Coffee &middot; Old Dominion Dr",
             38.9523465, -77.2246768, "Family Dining"),
        ],
        "arrows": [((38.9020805, -77.2670056), "Downtown Vienna", "Maple Ave dining"),
                   ((38.9589096, -77.3614631), "Reston Town Center", "Shops and dining"),
                   ((38.917017, -77.2228361), "Tysons Corner Center", "Shopping"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        "extra": [("Fine Dining", "Evelyn Rose", "Tasting menu, Church St NW", 38.9020805, -77.2670056),
                  ("Fine Dining", "Cafe Renaissance", "French, Glyndon St SE", 38.9041085, -77.2604861),
                  ("Fine Dining", "The Maple Room", "Steaks and seafood, Maple Ave W", 38.8964444, -77.2722695),
                  ("Fine Dining", "Ristorante Bonaroti", "Italian, Maple Ave E", 38.9089849, -77.2564496),
                  ("Family Dining", "Vienna Inn", "The 1960 town institution", 38.9022013, -77.2647713),
                  ("Family Dining", "The Virginian Restaurant", "Classic diner, Vienna", 38.9041519, -77.2602158),
                  ("Shopping", "Reston Town Center", "Shops, dining and events", 38.9589096, -77.3614631),
                  ("Shopping", "Tysons Corner Center", "Regional mall", 38.917017, -77.2228361),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },    "15095_Valhalla": {
        "center": (38.8385541, -77.6397842, "15095 Valhalla Ct"),
        "title": "The Neighborhood",
        "lede": "Dominion Valley Country Club is around the corner and the "
                "Town of Haymarket a few minutes south, with Wegmans and "
                "Virginia Gateway just past it. The arrows point to everything "
                "past the edge of the map.",
        "amen_lede": "The country club around the corner, the Town of "
                     "Haymarket a few minutes away, and I-66 and Route 29 "
                     "for the drive east.",
        "pins": [
            ("Dominion Valley Country Club", "Arnold Palmer golf, pool and fitness",
             38.840535, -77.6419155, "Parks and Recreation"),
            ("Haymarket Iceplex", "Two rinks, Washington St",
             38.8125705, -77.6400865, "Parks and Recreation"),
            ("Giuseppe&rsquo;s", "Family &middot; Italian, Washington St",
             38.813343, -77.6381454, "Family Dining"),
            ("Hidden Julles", "Family &middot; brunch and caf&eacute;",
             38.8121559, -77.6358834, "Family Dining"),
            ("Bull Run Mountains Preserve", "Trails and streams",
             38.8250633, -77.6985289, "Parks and Recreation"),
        ],
        "arrows": [((38.784336, -77.653277), "Wegmans", "Gainesville"),
                   ((38.7948622, -77.6067255), "Virginia Gateway", "Shops, dining, cinema"),
                   ((38.8185193, -77.5374564), "Manassas Battlefield", "National park"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        "extra": [("Shopping", "Wegmans", "Stonewall Shops, Gainesville", 38.784336, -77.653277),
                  ("Shopping", "Virginia Gateway", "Shops, dining and cinema", 38.7948622, -77.6067255),
                  ("Family Dining", "Ghosted Concepts", "Chicken sandwiches, Washington St", 38.8100665, -77.6290684),
                  ("Parks and Recreation", "Manassas National Battlefield", "Trails and history", 38.8185193, -77.5374564),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },
    "702_Ware": {
        "center": (38.890035, -77.2661446, "702 Ware St SW"),
        "title": "The Neighborhood",
        "lede": "Meadow Lane Park is around the corner and Marshall Road "
                "Elementary a short walk south; Maple Avenue&rsquo;s "
                "restaurants and shops and the Vienna Metro are a few minutes "
                "either way. The arrows point to everything past the edge of "
                "the map.",
        "amen_lede": "A park around the corner, the elementary school a walk "
                     "away, and downtown Vienna and the Orange Line a few "
                     "minutes from the door.",
        "pins": [
            ("Meadow Lane Park", "Fenced playground and pavilion",
             38.8923922, -77.267275, "Schools and Parks"),
            ("Marshall Road Elementary School", "Fairfax County Public Schools",
             38.8821062, -77.2665128, "Schools and Parks"),
            ("Thoreau Middle School", "Fairfax County Public Schools",
             38.8888367, -77.2410077, "Schools and Parks"),
            ("James Madison High School", "Fairfax County Public Schools",
             38.8961219, -77.2788162, "Schools and Parks"),
            ("Evelyn Rose", "Tasting menu on Church St NW",
             38.9020805, -77.2670056, "Fine Dining"),
            ("The Maple Room", "Steaks and seafood, 377 Maple Ave W",
             38.8964444, -77.2722695, "Fine Dining"),
            ("Cafe Renaissance", "French, 163 Glyndon St SE",
             38.9041085, -77.2604861, "Fine Dining"),
            ("Ristorante Bonaroti", "Italian, 428 Maple Ave E",
             38.9089849, -77.2564496, "Fine Dining"),
            ("Carnegie Diner &amp; Cafe", "Breakfast to dessert, 501 Maple Ave W",
             38.8946929, -77.2744012, "Family Dining"),
            ("Vienna Inn", "The 1960 town institution",
             38.9022013, -77.2647713, "Family Dining"),
            ("Bear Branch Tavern", "Brunch and patio, 133 Maple Ave E",
             38.9020863, -77.2637567, "Family Dining"),
            ("The Virginian Restaurant", "Classic diner breakfasts",
             38.9041519, -77.2602158, "Family Dining"),
            ("Vienna Plaza", "Shops and pharmacy on Maple Ave W",
             38.8975042, -77.2695645, "Shopping"),
            ("Vienna Shopping Center", "Restaurants, gym and services",
             38.9005429, -77.2656106, "Shopping"),
            ("Whole Foods", "143 Maple Ave E",
             38.9022469, -77.2626957, "Shopping"),
            ("Vienna Metro", "Orange Line",
             38.8775790, -77.2724610, "Getting Around"),
        ],
        "arrows": [((38.872778, -77.2294333), "Mosaic District", "Shops and dining"),
                   ((38.917017, -77.2228361), "Tysons Corner Center", "Shopping"),
                   ((38.9522483, -77.4578886), "Dulles International", "IAD"),
                   ((38.8501079, -77.039176), "Reagan National", "DCA"),
                   ((38.897419, -77.006226), "Washington, DC", "Union Station")],
        # Off the map but on the Amenities cards: (card, name, sub, lat, lng)
        "extra": [("Shopping", "Mosaic District", "Shops, dining and cinema", 38.872778, -77.2294333),
                  ("Shopping", "Tysons Corner Center", "Regional mall", 38.917017, -77.2228361),
                  ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
                  ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
                  ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
    },
    "403_John_Marshall": {
        "center": (38.91280, -77.26903, "403 John Marshall Dr NE"),
        "title": "The Neighborhood",
        "lede": "Wolftrap Elementary is a few streets away and the W&amp;OD "
                "Trail is a short walk south; downtown Vienna, the Town Green "
                "and Maple Avenue sit just beyond it. The arrows point to "
                "everything past the edge of the map.",
        "amen_lede": "The schools are close, the trail is closer, and "
                     "downtown Vienna is a walk rather than a drive.",
        "pins": [
            ("Wolftrap Elementary School", "Fairfax County Public Schools",
             38.9175151, -77.2663853, "Schools and Parks"),
            ("Glyndon Park", "Ballfields, tennis and playground",
             38.9088500, -77.2635884, "Schools and Parks"),
            ("Kilmer Middle School", "Fairfax County Public Schools",
             38.9041263, -77.2252470, "Schools and Parks"),
            ("James Madison High School", "Fairfax County Public Schools",
             38.8961219, -77.2788162, "Schools and Parks"),
            ("W&amp;OD Trail", "Trail access at Mill St NE",
             38.9076431, -77.2705930, "Every Day"),
            ("Vienna Town Green", "Concerts, markets, Viva Vienna",
             38.9029410, -77.2641239, "Every Day"),
            ("Giant Food", "359 Maple Ave E",
             38.9053633, -77.2580414, "Every Day"),
            ("Vienna Community Center", "Courts, classes, town events",
             38.9008267, -77.2603307, "Every Day"),
            ("Vienna Metro", "Orange Line terminus",
             38.8775790, -77.2724610, "Getting Around"),
        ],
        # Far enough to be an arrow at the frame edge rather than a pin.
        "arrows": [((38.8833985, -77.2280196), "Dunn Loring Metro",
                    "Orange Line"),
                   ((38.8854738, -77.2760481), "Nottoway Park",
                    "Fairfax County park")],
    },
    "41923_Hogan_Forest": {
        "center": (38.910752, -77.553768, "41923 Hogan Forest Ter"),
        "title": "The Neighborhood",
        "lede": "South 620 sits off Braddock Road with Pinebrook Elementary "
                "at the end of the street. The Stone Ridge village centre, "
                "the library and the commuter lot are all about two miles "
                "north. The arrows point to everything beyond the map.",
        "amen_lede": "Pinebrook Elementary is a walk from the door and "
                     "everything else is inside ten minutes.",
        "pins": [
            ("Pinebrook Elementary School", "Loudoun County Public Schools",
             38.912398, -77.556211, "Schools and Parks"),
            ("Gum Spring Middle School", "Loudoun County Public Schools",
             38.924784, -77.546945, "Schools and Parks"),
            ("John Champe High School", "Loudoun County Public Schools",
             38.932283, -77.565883, "Schools and Parks"),
            ("Conklin Community Park", "Fields, tennis and bike trails",
             38.908428, -77.524504, "Schools and Parks"),
            ("Gum Spring Library", "Loudoun County Public Library",
             38.937533, -77.545641, "Every Day"),
            ("Harris Teeter", "Stone Ridge Village Center",
             38.939354, -77.549094, "Every Day"),
            ("Dulles South Park &amp; Ride", "Commuter bus to DC and Tysons",
             38.938442, -77.550030, "Getting Around"),
            ("Hal &amp; Berni Hanson Regional Park", "Regional park and trails",
             38.971819, -77.548977, "Schools and Parks"),
        ],
        "arrows": [((38.952126, -77.448695), "Dulles International", "IAD"),
                   ((39.005099, -77.491313), "Ashburn Metro", "Silver Line")],
    },
}
DATA["4608_Freedmen"] = {
    # 4608 Freedmen Ln, Dominion Valley Country Club, Haymarket. 19 Nov 2026.
    # Every coordinate verified via places search 19 Nov 2026.
    "center": (38.8569847, -77.641149, "4608 Freedmen Ln"),
    "title": "The Neighborhood",
    "lede": "Dominion Valley Country Club, with the club and golf course a short drive south and "
            "Haymarket, Gainesville and I-66 minutes away. The arrows point to everything past the "
            "edge of the map.",
    "amen_lede": "The Dominion Valley club, golf and pools close by, groceries and shopping in "
                 "Haymarket and Gainesville, and I-66 and Dulles for the commute.",
    "pins": [
        ("Dominion Valley Country Club", "Golf, pools and fitness", 38.840535, -77.6419155, "Parks and Recreation"),
        ("Battlefield High School", "Prince William County Public Schools", 38.8453326, -77.6298068, ""),
        ("UVA Health Haymarket Medical Center", "Hospital and ER", 38.820752, -77.6425481, ""),
        ("Town of Haymarket", "Historic town center", 38.8127387, -77.6365857, ""),
    ],
    "arrows": [((38.807738, -77.611557), "Harris Teeter", "Gainesville"),
               ((38.784336, -77.653277), "Wegmans", "Gainesville"),
               ((38.7948622, -77.6067255), "Virginia Gateway", "Shopping and dining"),
               ((38.8288884, -77.4982777), "The Winery at Bull Run", "Centreville"),
               ((38.9522483, -77.4578886), "Dulles International", "IAD"),
               ((38.897419, -77.006226), "Washington, DC", "Union Station")],
    "extra": [("Shopping", "Harris Teeter", "Gainesville", 38.807738, -77.611557),
              ("Shopping", "Wegmans", "Gainesville", 38.784336, -77.653277),
              ("Shopping", "Virginia Gateway", "Shopping and dining", 38.7948622, -77.6067255),
              ("Family Dining", "Virginia Gateway restaurants", "Gainesville", 38.7948622, -77.6067255),
              ("Parks and Recreation", "The Winery at Bull Run", "Centreville", 38.8288884, -77.4982777),
              ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
              ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
              ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
}
DATA["3106_Whimbrell"] = {
    # 3106 Whimbrell Ct, Willow Creek Estates, Oakton. 20 Nov 2026.
    # Coordinates verified via places search 20 Nov 2026.
    "center": (38.8863007, -77.3240967, "3106 Whimbrell Ct"),
    "title": "The Neighborhood",
    "lede": "Willow Creek Estates in Oakton, with Flint Hill School a mile away, the Oakton schools close "
            "by, and Fairfax Corner, Mosaic and Tysons a short drive. The arrows point to everything past "
            "the edge of the map.",
    "amen_lede": "Waples Mill Elementary and Flint Hill School nearby, Fairfax Corner and Wegmans for "
                 "dining and groceries, and the Vienna Metro and I-66 for the commute.",
    "pins": [
        ("Flint Hill School", "Private JK&ndash;12, about a mile", 38.8702797, -77.3197133, ""),
        ("Waples Mill Elementary School", "Fairfax County Public Schools", 38.8762924, -77.3447978, ""),
        ("Oakton High School", "Fairfax County Public Schools", 38.8774554, -77.2822231, ""),
        ("Vienna/Fairfax-GMU Metro", "Orange Line", 38.87782, -77.2713545, "Getting Around"),
    ],
    "arrows": [((38.857595, -77.358925), "Fairfax Corner", "Dining and shopping"),
               ((38.851101, -77.347696), "Wegmans", "Fairfax"),
               ((38.872778, -77.2294333), "Mosaic District", "Dining and shopping"),
               ((38.917017, -77.2228361), "Tysons Corner Center", "Shopping"),
               ((38.9522483, -77.4578886), "Dulles International", "IAD"),
               ((38.897419, -77.006226), "Washington, DC", "Union Station")],
    "extra": [("Shopping", "Fairfax Corner", "Dining and shopping", 38.857595, -77.358925),
              ("Shopping", "Wegmans", "Fairfax", 38.851101, -77.347696),
              ("Shopping", "Tysons Corner Center", "Shopping", 38.917017, -77.2228361),
              ("Fine Dining", "Mosaic District", "Restaurants", 38.872778, -77.2294333),
              ("Getting Around", "Vienna/Fairfax-GMU Metro", "Orange Line", 38.87782, -77.2713545),
              ("Getting Around", "Dulles International", "IAD", 38.9522483, -77.4578886),
              ("Getting Around", "Reagan National", "DCA", 38.8501079, -77.039176),
              ("Getting Around", "Washington, DC", "Union Station", 38.897419, -77.006226)],
}
CARD_ORDER = ["Getting Around", "Fine Dining", "Family Dining", "Shopping",
              "Downtown Vienna", "Every Day", "Schools and Parks", "Parks and Recreation", "Walk to Town"]


def road_miles(a, b):
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    d = 2 * asin(sqrt(sin((la2 - la1) / 2) ** 2
                      + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2))
    return 3958.8 * d * 1.30


def bearing(a, b):
    la1, la2 = radians(a[0]), radians(b[0])
    dlo = radians(b[1] - a[1])
    return round((degrees(atan2(sin(dlo) * cos(la2),
                                cos(la1) * sin(la2)
                                - sin(la1) * cos(la2) * cos(dlo))) + 360) % 360,
                 1)


def label(mi):
    walk = max(1, round(mi / 3.0 * 60))
    return f"{walk} min walk" if walk <= 15 else round(mi, 2)


def drive_mins(mi):
    mph = 20 if mi < 1.5 else (25 if mi <= 5 else (35 if mi <= 25 else 45))
    return max(2, round(mi / mph * 60))


def main(pre):
    d = DATA[pre]
    f = Path("properties") / (pre.lower().replace("_", "_") + ".json")
    matches = list(Path("properties").glob("*.json"))
    f = next(x for x in matches
             if json.loads(x.read_text()).get("prefix") == pre)
    p = json.loads(f.read_text())
    clat, clng, clabel = d["center"]
    c = (clat, clng)

    pins, cards = [], {}
    for name, sub, lat, lng, card in d["pins"]:
        pins.append({"name": name, "sub": sub, "lat": lat, "lng": lng})
        if card:
            mi = road_miles(c, (lat, lng))
            cards.setdefault(card, []).append(([name, sub, label(mi)], mi))

    for card, name, sub, lat, lng in d.get("extra", []):
        mi = road_miles(c, (lat, lng))
        cards.setdefault(card, []).append(([name, sub, round(mi, 2)], mi))

    arrows = []
    for (lat, lng), name, sub in d["arrows"]:
        mi = road_miles(c, (lat, lng))
        arrows.append([bearing(c, (lat, lng)),
                       [name, f"{sub} &middot; {drive_mins(mi)} min"]])

    b = p["buyer_portal"]
    b["locator_map"] = {
        "title": d["title"], "lede": d["lede"],
        "center": {"lat": clat, "lng": clng, "label": clabel},
        "pins": pins, "arrows": arrows,
    }
    b["amenities_lede"] = d["amen_lede"]
    b["amenities"] = [
        {"title": t,
         "items": [r for r, _ in sorted(cards[t], key=lambda x: x[1])]}
        for t in CARD_ORDER if t in cards]
    f.write_text(json.dumps(p, indent=1, ensure_ascii=False))

    print(f"{pre}: {len(pins)} pins, {len(arrows)} arrows, "
          f"{sum(len(v) for v in cards.values())} amenities")
    for t in CARD_ORDER:
        if t in cards:
            print(f"   {t}: " + ", ".join(
                f"{r[0]} ({r[2]})" for r, _ in sorted(cards[t],
                                                      key=lambda x: x[1])))
    for br, (nm, sb) in arrows:
        print(f"   arrow {br:>5}deg  {nm} — {sb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
