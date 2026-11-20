"""
Regression tests. Every case here is a worked example from the rules doc or a
package already built and reviewed. If a rule change breaks one of these,
that is the signal to stop and check with Casey, not to edit the expectation.

    python3 test_pricing.py
"""

from pricing import compute, abbrev

FAILS = []


def check(label, got, want):
    if got != want:
        FAILS.append(f"{label}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------- 502 Spring St
# Rules doc: "$2.15M is not a special case for the initial price."
# Coming Soon $2,149,999, NO alert, fall back uses the 2.15M->2M pair.
s = compute(dated=1_944_924, customary=2_161_027,
            customary_list=2_299_091, premium=2_333_909)
check("502 Spring coming soon", s.coming_soon, 2_149_999)
check("502 Spring threshold cell", s.closest_buyer_threshold, 2_150_000)
check("502 Spring alert", s.alert, None)
# Casey, 10 Oct 2026: the tier rule replaced the threshold pair. $2,149,999
# less $50,000 (lower than 5%) is $2,099,999; the old pair jumped to
# $1,999,999, through the $2M threshold. The pass-over is warned about.
check("502 Spring fallback", s.fallback, 2_099_999)
check("502 Spring deep", s.deep, 2_049_999)
check("502 Spring pair used", s.fallback_is_pair, False)
check("502 Spring pair passed", s.pair_passed, 2_000_000)
check("502 Spring money at risk", s.money_at_risk, 388_985)
check("502 Spring expected", (abbrev(s.expected_low), abbrev(s.expected_high)),
      ("$2.16M", "$2.33M"))

# ------------------------------------------------------- 1870 Hunter Mill Rd
# Rules doc corrected example: table shows the $50K grid line $1,600,000,
# NOT the $1.5M major threshold. Coming Soon stays $1,599,999.
s = compute(dated=1_400_000, customary=1_638_006,
            customary_list=1_700_000, premium=1_800_000)
check("Hunter Mill coming soon", s.coming_soon, 1_599_999)
check("Hunter Mill threshold cell", s.closest_buyer_threshold, 1_600_000)
check("Hunter Mill alert major", s.alert["major"] if s.alert else None, 1_500_000)
check("Hunter Mill alert gap", s.alert["gap"] if s.alert else None, 99_999)

# ------------------------------------------------------- 25226 Mastery Place
# Gap to the $750K major is $149,999 — outside the $100K ceiling for the
# sub-$2M band, so no alert. Standard $50K step on the fall back.
s = compute(dated=848_895, customary=943_216,
            customary_list=971_826, premium=1_018_674)
check("Mastery coming soon", s.coming_soon, 899_999)
check("Mastery basis", s.anchor_basis_label, "Customary Value")
check("Mastery alert", s.alert, None)
check("Mastery fallback", s.fallback, 849_999)
check("Mastery money at risk", s.money_at_risk, 169_779)
check("Mastery expected", (abbrev(s.expected_low), abbrev(s.expected_high)),
      ("$943K", "$1.02M"))

# ----------------------------------------------------- 502 MacArthur (first PM)
s = compute(dated=2_019_881, customary=2_244_313,
            customary_list=2_238_213, premium=2_423_858)
check("MacArthur v1 coming soon", s.coming_soon, 2_199_999)
# Casey, 10 Oct 2026: the anchor is Customary Value, not the lower of Value and
# List Price. MacArthur's two figures round to the same grid line, so the price
# is unchanged here and only the label moves — see 403 John Marshall below for
# the case where the rule actually shifts the launch.
check("MacArthur v1 basis", s.anchor_basis_label, "Customary Value")
check("MacArthur v1 alert major", s.alert["major"] if s.alert else None, 2_150_000)
check("MacArthur v1 alert gap", s.alert["gap"] if s.alert else None, 49_999)
check("MacArthur v1 fallback", s.fallback, 2_149_999)
check("MacArthur v1 money at risk", s.money_at_risk, 403_977)

# ---------------------------------------------------- 502 MacArthur (revised PM)
# NOTE: expectation changed when $2,250,000 was added to MAJOR_THRESHOLDS
# (Casey, 19 Sep 2026 — "the major buyer pools are $2M, $2.15M, $2.25M and
# $2.5M"). The anchor grid line $2,250,000 is now itself a major threshold,
# so no alert fires. Previously it flagged $2,150,000 at a $99,999 gap.
s = compute(dated=2_038_500, customary=2_265_000,
            customary_list=2_258_844, premium=2_446_200)
check("MacArthur v2 coming soon", s.coming_soon, 2_249_999)
check("MacArthur v2 threshold cell", s.closest_buyer_threshold, 2_250_000)
check("MacArthur v2 alert", s.alert, None)
check("MacArthur v2 fallback", s.fallback, 2_199_999)
check("MacArthur v2 money at risk", s.money_at_risk, 407_700)
check("MacArthur v2 expected", (abbrev(s.expected_low), abbrev(s.expected_high)),
      ("$2.27M", "$2.45M"))

# ------------------------------------------------------- Extraordinary Upgrades
# Rules doc example: Premium Range $2,503,817-$2,758,817 anchors off the
# bottom -> $2.5M major threshold -> Coming Soon $2,499,999.
s = compute(dated=2_000_000, customary=2_333_000,
            customary_list=2_400_000, premium=0, upgrades=515_000)
check("Upgrades coming soon", s.coming_soon, 2_499_999)
check("Upgrades basis label", s.anchor_basis_label, "bottom of the Premium Range")
check("Upgrades premium label",
      s.premium_label, "Based on $515,000 in Upgrades the Premium Range is")
check("Upgrades fallback is pair", s.fallback_is_pair, False)
check("Upgrades fallback", s.fallback, 2_449_999)
check("Upgrades deep", s.deep, 2_399_999)

# ------------------------------------------------------------- Under $500,000
# $25K increments for both the anchor and the fall back step.
s = compute(dated=380_000, customary=432_000,
            customary_list=440_000, premium=470_000)
check("Sub-500K coming soon", s.coming_soon, 424_999)
check("Sub-500K fallback", s.fallback, 399_999)

# ------------------------------------------------------------------- Discounts
s = compute(dated=0, customary=1_200_000, customary_list=1_250_000,
            premium=1_320_000, discount=100_000, discount_reason="busy road")
check("Discount coming soon", s.coming_soon, 1_099_999)
check("Discount warns", len(s.warnings), 2)   # + the pair pass-over

# --------------------------------------------------------------- abbreviations
check("abbrev 943216", abbrev(943_216), "$943K")
check("abbrev 1018674", abbrev(1_018_674), "$1.02M")
check("abbrev 2161027", abbrev(2_161_027), "$2.16M")


# --------------------------------------------- 403 John Marshall (anchor rule)
# Customary List Price $1,170,381 sits a grid line below Customary Value
# $1,226,855. Under the old "lower of the two" anchor this launched at
# $1,149,999; the rule is the first threshold under Customary Value, so it is
# $1,199,999.
s = compute(dated=1_104_169, customary=1_226_855,
            customary_list=1_170_381, premium=1_325_003)
check("John Marshall coming soon", s.coming_soon, 1_199_999)
check("John Marshall basis", s.anchor_basis_label, "Customary Value")

# ------------------------------------------------- Preview over Customary Value
# Casey, 13 Oct 2026: "Preview is first Threshold over Customary, Coming Soon
# is first threshold under Customary then progression based on performance."
# Preview no longer keys off Premium Value.
from pricing import preview_over_customary as _poc

check("JM preview", _poc(1_226_855), 1_250_000)
check("Vintage Crest preview", _poc(2_650_335), 2_700_000)
check("Lieuvin preview", _poc(2_549_793), 2_550_000)
check("Woodrow preview", _poc(1_803_711), 1_850_000)
# Exactly on a grid line steps one increment up -- a price equal to Customary
# is not over it.
check("preview on a grid line", _poc(1_800_000), 1_850_000)
# Under $500,000 the increment is $25K, not $50K.
check("preview under 500k", _poc(483_142), 500_000)
check("preview on a 25k line", _poc(475_000), 500_000)
# Preview must sit above Coming Soon: the two bracket Customary.
for _c in (1_226_855, 2_650_335, 483_142, 1_800_000):
    _s = compute(dated=int(_c * 0.9), customary=_c,
                 customary_list=_c, premium=int(_c * 1.08))
    check(f"preview above coming soon @ {_c}", _poc(_c) > _s.coming_soon, True)

if FAILS:
    print(f"{len(FAILS)} FAILED\n")
    for f in FAILS:
        print("  " + f)
    raise SystemExit(1)
print("All pricing checks passed.")
