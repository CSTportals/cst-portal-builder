"""
pricing.py — The Casey Samson Team Gold Standard pricing rules, in code.

Everything here comes from the project's pricing rules document. Where a rule
was ambiguous, the code follows the reading noted in the comment AND raises a
warning so a human checks it, rather than silently picking an interpretation.

Nothing in this module formats HTML. It takes worksheet numbers in and returns
a Strategy object out.
"""

from dataclasses import dataclass, field

# Major buyer thresholds. Used ONLY by the alert check — never for the
# "Closest Buyer Threshold" cell in the CST Pricing Strategy table, which
# always shows the plain grid line. Conflating the two is the single most
# common error this module exists to prevent.
# Casey, 15 Oct 2026: "Safe havens are $500K, $750K, $1M, $1.25M, $1.5,
# $1.75, $2M, $2.15, $2.25, $2.5M, $2.75, $3M, $3.25, $3.5M, $3.75, $4M."
# These are the lines buyers actually search to, which is why a price just
# above one is the worst place on the grid.
SAFE_HAVENS = [500_000, 750_000, 1_000_000, 1_250_000, 1_500_000, 1_750_000,
               2_000_000, 2_150_000, 2_250_000, 2_500_000, 2_750_000,
               3_000_000, 3_250_000, 3_500_000, 3_750_000, 4_000_000]
MAJOR_THRESHOLDS = SAFE_HAVENS          # the name the alert check uses


# Casey, 15 Oct 2026: "MacArthur in a buyer market should take safe haven at
# $2.15, i.e. normally $2.199 but safe haven is under closest major threshold
# only $50K away. Prices should be safe haven under major thresholds if they
# are $50K away."
#
# A price sitting just ABOVE a major threshold is the worst place on the
# grid: it is outside every search that stops at that threshold and it buys
# nothing for the money. MacArthur at $2,199,999 misses everyone searching to
# $2.15M for the sake of $50,000. Stepping under the threshold hands back
# that $50,000 and collects the whole pool beneath it.
#
# Only in a conservative market. Where sellers are in control the point is to
# test above the authenticated value, not to buy a bigger pool.
SAFE_HAVEN_REACH = 50_000


def safe_haven(price):
    """The price just under the closest major threshold, when the given
    price sits within reach above one. None when it does not apply.

    A price already at or under a major threshold is left alone: it is
    already in the safe haven.
    """
    if not price:
        return None
    below = [t for t in MAJOR_THRESHOLDS if t <= price]
    if not below:
        return None
    major = max(below)
    gap = price - (major - 1)
    if 0 < gap <= SAFE_HAVEN_REACH:
        return major - 1
    return None


def draw_downs(coming_soon):
    """The two Predictive Analysis steps under a Coming Soon price.

    Casey, 10 Oct 2026: "5 or fewer $50k or 5% under coming soon, fewer than
    3 showings $100,000 or 10% whichever is lower." Both tiers measure from
    the COMING SOON price, not from each other -- the deep tier used to
    cascade off the fall back, which cut it twice.

    "If it is a % then it still must be below $25k or $50k thresholds --
    $451,249 is $450." So a percentage step that lands mid-grid drops to the
    grid line beneath it, less $1. A step that already sits just under a
    threshold is left alone; rounding those would cut a second time. A step
    is "clean" when it lands the same distance under a grid line as the
    Coming Soon price does. $1,199,999 is $1 under $1.2M, so $1,149,999 is
    $1 under $1.15M and needs no help; a hand-set $1,799,000 is $1,000 under
    $1.8M, so $1,749,000 is right too. Only a percentage step that lands
    mid-grid gets pulled down. Snapping on the raw -$1 test alone cut
    Woodrow by $99,001 and Lillards Ford by $50,001.

    Lifted out of compute() so the ladder can be rebuilt whenever the
    Coming Soon price moves -- the safe haven step does exactly that.
    """
    offset = grid_line_at_or_above(
        coming_soon, increment_for(coming_soon)) - coming_soon

    def snap(x):
        i = increment_for(x)
        if grid_line_at_or_above(x, i) - x == offset:
            return x
        return grid_line_at_or_below(x, i) - 1

    return {"fallback": snap(coming_soon - min(50_000,
                                               round(coming_soon * 0.05))),
            "deep": snap(coming_soon - min(100_000,
                                           round(coming_soon * 0.10)))}


def closest_safe_haven(price):
    """The safe haven at or below a price, as a price: the line less $1.

    None below the bottom of the list.
    """
    below = [t for t in SAFE_HAVENS if t <= price]
    return max(below) - 1 if below else None


def buyer_pools(anchor, count=3):
    """The buyer pools bracketing a price: the major below, then the majors
    at and above it. Used by the relaunch strategy to show where the larger
    pools sit relative to the current position."""
    below = [t for t in MAJOR_THRESHOLDS if t < anchor]
    above = [t for t in MAJOR_THRESHOLDS if t >= anchor][:count]
    return ([below[-1]] if below else []) + above

# Predictive Analysis exception pairs, keyed by the anchor grid line.
# A growing list of SPECIFIC pairs — deliberately not a formula.
FALLBACK_PAIRS = {
    1_100_000: 1_000_000,
    2_150_000: 2_000_000,
    2_500_000: 2_350_000,
}

# Upgrades only count as "extraordinary" above this figure; below it the
# property is priced as a standard Dated / Customary / Premium property.
UPGRADE_MINIMUM = 200_000

UPGRADE_BOTTOM = 0.33
UPGRADE_TOP = 0.50
DISCOUNT_FULL = 1.00
DISCOUNT_HALF = 0.50


def increment_for(amount):
    """$25K steps under $500,000, $50K at or above."""
    return 25_000 if amount < 500_000 else 50_000


def preview_price(premium):
    """The Preview price: the grid line immediately BELOW Premium Value.

    "Threshold" here means the plain grid line the Pricing Strategy table
    already uses, not MAJOR_THRESHOLDS -- the comment at the top of this file
    exists because conflating the two is the easy mistake. When Premium lands
    exactly on a grid line, the Preview price steps one below it, since a
    price equal to Premium is not under it.
    """
    premium = int(premium)
    inc = increment_for(premium)
    line = grid_line_at_or_below(premium, inc)
    return line - inc if line == premium else line


def preview_over_customary(customary):
    """The Preview price: the first grid line strictly OVER Customary Value.

    Casey, 13 Oct 2026: "Rule for Pricing Strategy Summary Preview is first
    Threshold over Customary, Coming Soon is first threshold under Customary
    then progression based on performance."

    This replaces the Premium-anchored pair below. Preview and Coming Soon now
    bracket Customary Value from either side, and the Predictive ladder is the
    progression.

    "Threshold" is the plain grid line -- $25K under $500,000, $50K at or above
    -- not MAJOR_THRESHOLDS, the same convention the rest of the page uses.
    Customary exactly on a grid line steps one increment up, since a price
    equal to Customary is not over it.
    """
    customary = int(customary)
    inc = increment_for(customary)
    line = grid_line_at_or_above(customary, inc)
    return line + inc if line == customary else line


def preview_price_above(premium):
    """Aggressive market: the grid line immediately ABOVE Premium Value.

    The mirror of preview_price(). Sellers are in control, so the Preview
    figure reaches over Premium rather than sitting under it. Premium exactly
    on a grid line steps one up, for the same reason the conservative version
    steps one down.
    """
    premium = int(premium)
    inc = increment_for(premium)
    line = grid_line_at_or_above(premium, inc)
    return line + inc if line == premium else line


def grid_line_at_or_below(amount, increment):
    return (int(amount) // increment) * increment


def grid_line_at_or_above(amount, increment):
    return -((-int(amount)) // increment) * increment


@dataclass
class Strategy:
    coming_soon: int
    computed_coming_soon: int   # the threshold-under-Customary price, before any override
    coming_soon_above: int      # the threshold-OVER-Customary price, for a seller's market
    anchor: int                 # the grid line Coming Soon sits $1 below
    closest_buyer_threshold: int  # what the Pricing Strategy TABLE shows
    anchor_basis: int           # the value anchoring ran off
    anchor_basis_label: str
    fallback: int
    fallback_is_pair: bool
    deep: int                   # the fewer-than-3-showings tier
    pair_passed: int | None     # major threshold the old pair reached, if any
    expected_low: int
    expected_high: int
    money_at_risk: int
    alert: dict | None          # None when no alert fires
    dated_display: str
    premium_display: str
    premium_label: str
    dated_label: str
    warnings: list = field(default_factory=list)
    premium_bottom: int = 0
    premium_top: int = 0
    has_upgrades: bool = False


def money(v):
    return f"${v:,.0f}"


def abbrev(v):
    """$943,216 -> $943K ; $2,446,200 -> $2.45M"""
    if v < 1_000_000:
        return f"${round(v / 1_000):,}K"
    return f"${v / 1_000_000:.2f}M"


def compute(dated, customary, customary_list=None, premium=0,
            upgrades=0, discount=0, discount_reason="", coming_soon_override=None):
    """
    dated / customary / customary_list / premium: worksheet dollar figures.
    upgrades: Extraordinary Upgrades dollar amount (0 if none).
    discount: Functional Issues dollar amount (0 if none).

    Upgrades and discounts are mutually exclusive in every example seen so
    far; if both arrive, we warn loudly rather than guess at the interaction.
    """
    warnings = []

    # A worksheet that carries no Customary List Price anchors off the
    # Customary Value alone. Do not press another figure into that slot.
    if customary_list in (None, 0):
        customary_list = customary

    if upgrades and 0 < upgrades <= UPGRADE_MINIMUM:
        warnings.append(
            f"Upgrades of {money(upgrades)} are at or below the "
            f"{money(UPGRADE_MINIMUM)} extraordinary threshold, so the property "
            "was priced as a standard Dated / Customary / Premium property.")
        upgrades = 0

    if upgrades and discount:
        warnings.append(
            "Worksheet has BOTH Extraordinary Upgrades and a Functional Issues "
            "discount. No rule covers the combination — upgrades were applied "
            "and the discount ignored. Verify by hand before sending.")

    # ---- Premium tier: single value, or a range when Upgrades are present ----
    if upgrades:
        premium_bottom = round(customary + UPGRADE_BOTTOM * upgrades)
        premium_top = round(customary + UPGRADE_TOP * upgrades)
        premium_display = f"{money(premium_bottom)} &ndash; {money(premium_top)}"
        premium_label = f"Based on {money(upgrades)} in Upgrades the Premium Range is"
        premium_high = premium_top
    else:
        premium_bottom = premium_top = premium_high = premium
        premium_display = money(premium)
        premium_label = "Premium Value"

    # ---- Dated tier: single value, or a range when a Discount is present ----
    # Rules doc labels these "top" and "bottom", but the 100%-of-discount
    # number is numerically LOWER than the 50% number, and the label prints
    # them in that order. We follow the printed order and warn.
    if discount:
        dated_full = round(customary - DISCOUNT_FULL * discount)
        dated_half = round(customary - DISCOUNT_HALF * discount)
        dated_display = f"{money(dated_full)} &ndash; {money(dated_half)}"
        reason = f" ({discount_reason})" if discount_reason else ""
        dated_label = (f"Based on {money(discount)} in Discounts{reason} "
                       f"the Dated Range is")
        dated_low = dated_full
        warnings.append(
            "Discount factor applied. The rules doc calls the 100%-of-discount "
            f"number the range 'top' ({money(dated_full)}) even though it is the "
            f"lower figure; anchoring ran off it. Confirm this is intended.")
    else:
        dated_low = dated_full = dated_half = dated
        dated_display = money(dated)
        dated_label = "Dated Value"

    # ---- What anchoring runs off -------------------------------------------
    if upgrades:
        # Closest MAJOR threshold under the bottom of the Premium Range.
        basis = premium_bottom
        basis_label = "bottom of the Premium Range"
        candidates = [t for t in MAJOR_THRESHOLDS if t <= basis]
        if not candidates:
            raise ValueError(
                f"No major threshold at or below {money(basis)} — "
                "property is below the $750,000 floor of the major list.")
        anchor = max(candidates)
        inc = increment_for(basis)
    elif discount:
        # Closest threshold under the top number of the Dated Range.
        basis = dated_full
        basis_label = "top of the Dated Range"
        inc = increment_for(basis)
        anchor = grid_line_at_or_below(basis, inc)
    else:
        # Standard: lower of Customary Value and Customary List Price.
        # Casey, 10 Oct 2026, on 403 John Marshall: "1.149 is not the first
        # threshold under $1.23, $1.199 is."
        #
        # The rule he set with the market-condition model is "Coming Soon in
        # conservative market first threshold under Customary Value" — the
        # authenticated value, full stop. It used to anchor on the LOWER of
        # Customary Value and Customary List Price, which quietly dropped the
        # launch a grid line whenever the list evidence came in under the
        # value. Customary Value is the basis now; Customary List Price stays
        # on the worksheet as evidence but no longer sets the price.
        basis, basis_label = customary, "Customary Value"
        inc = increment_for(basis)
        anchor = grid_line_at_or_below(basis, inc)

    coming_soon = anchor - 1
    computed_coming_soon = coming_soon

    # Casey, 10 Oct 2026: the market picks the formula. In a conservative
    # market (buyers or neutral in control) Coming Soon tests the first
    # threshold UNDER the anchoring basis — that is `computed_coming_soon`
    # above. In an aggressive market (sellers in control) it tests the first
    # threshold OVER it. Both run off the same basis and the same -$1
    # convention, so the two readings can never drift apart.
    _line_above = grid_line_at_or_above(basis, inc)
    if _line_above == anchor:          # basis sat exactly on a grid line
        _line_above += inc
    coming_soon_above = _line_above - 1

    # A manual Coming Soon price overrides the calculation. Everything
    # downstream — the threshold cell, the alert check and the fall back —
    # is then recomputed from the override, so the document stays internally
    # consistent rather than mixing a hand-set price with derived figures.
    if coming_soon_override:
        computed = coming_soon
        coming_soon = int(coming_soon_override)
        # A hand-set price is positioned just UNDER a round number
        # ($1,899,999 under $1.9M, $1,799,000 under $1.8M), so the grid line
        # it anchors to is the one at or above it — not the one below, which
        # would put the fall back two steps down instead of one.
        anchor = grid_line_at_or_above(coming_soon, inc)
        if coming_soon != computed:
            warnings.append(
                f"Coming Soon price set by hand to {money(coming_soon)}; the "
                f"calculation gives {money(computed)}. Threshold, alert and fall "
                "back were all recomputed from the override.")

    # ---- Major Buyer Threshold alert ---------------------------------------
    # Skipped entirely when the anchor grid line is ITSELF a major threshold:
    # $2.15M is not a special case for the initial price.
    alert = None
    if anchor not in MAJOR_THRESHOLDS:
        below = [t for t in MAJOR_THRESHOLDS if t <= coming_soon]
        if below:
            major = max(below)
            gap = coming_soon - major
            ceiling = 150_000 if coming_soon > 2_000_000 else 100_000
            if 10_000 < gap <= ceiling:
                alert = {"major": major, "gap": gap}

    # ---- Predictive Analysis draw-downs ------------------------------------
    # Casey, 10 Oct 2026: "5 or fewer $50k or 5% under coming soon, fewer than
    # 3 showings $100,000 or 10% whichever is lower." Both tiers measure from
    # the COMING SOON price, not from each other — the deep tier used to
    # cascade off the fall back, which cut it twice.
    #
    # "If it is a % then it still must be below $25k or $50k thresholds —
    # $451,249 is $450." So a percentage step that lands mid-grid drops to the
    # grid line beneath it, less $1. A step that already sits just under a
    # threshold is left alone; rounding those would cut a second time.
    # A step is "clean" when it lands the same distance under a grid line as
    # the Coming Soon price does. $1,199,999 is $1 under $1.2M, so $1,149,999
    # is $1 under $1.15M and needs no help; a hand-set $1,799,000 is $1,000
    # under $1.8M, so $1,749,000 is right too. Only a percentage step that
    # lands mid-grid gets pulled down. Snapping on the raw -$1 test alone cut
    # Woodrow by $99,001 and Lillards Ford by $50,001.
    fallback = draw_downs(coming_soon)["fallback"]
    deep = draw_downs(coming_soon)["deep"]

    # The flat rule replaces the old threshold-pair jump. Where a pair existed
    # it reached through a major threshold into a materially larger pool, and
    # the flat step no longer does, so say which properties that affects
    # rather than letting the behaviour disappear quietly.
    fallback_is_pair = False
    pair_passed = None
    if anchor in FALLBACK_PAIRS:
        _was = FALLBACK_PAIRS[anchor] - 1
        if _was < fallback:
            pair_passed = _was + 1
            warnings.append(
                f"Fall Back is {money(fallback)} under the tier rule. The old "
                f"threshold pair for {money(anchor)} went to {money(_was)}, "
                f"through the {money(_was + 1)} major threshold. The tier rule "
                "stops above it.")

    return Strategy(

        computed_coming_soon=computed_coming_soon,
        coming_soon_above=coming_soon_above,
        coming_soon=coming_soon,
        anchor=anchor,
        closest_buyer_threshold=anchor,
        anchor_basis=basis,
        anchor_basis_label=basis_label,
        fallback=fallback,
        fallback_is_pair=fallback_is_pair,
        deep=deep,
        pair_passed=pair_passed,
        expected_low=customary,
        expected_high=premium_high,
        money_at_risk=premium_high - dated_low,
        alert=alert,
        dated_display=dated_display,
        premium_display=premium_display,
        premium_label=premium_label,
        dated_label=dated_label,
        warnings=warnings,
        premium_bottom=premium_bottom,
        premium_top=premium_top,
        has_upgrades=bool(upgrades),
    )


# ---- Recovery: a home that has been sitting on the market ----------------
# Major thresholds used when a stalled home is over $2M. Deliberately NOT the
# MAJOR_THRESHOLDS list above: recovery runs further up the scale, so $2.75M
# and $3M are in and everything under $2M is out.
# Casey, 21 Oct 2026: "Major threshold are $1.15M then $1M, $2.15 fall back
# is $2.15 then fall back is $2M." $1.15M sits between $1.25M and $1M exactly
# as $2.15M sits between $2.25M and $2M.
RECOVERY_THRESHOLDS = [1_000_000, 1_150_000, 1_250_000, 1_500_000, 1_750_000,
                       2_000_000, 2_150_000, 2_250_000, 2_500_000, 2_750_000,
                       3_000_000]

# Both moves are "X or Y%, whichever is LESS" -- the smaller reduction. The
# dollar figure governs the larger listings and the percentage protects the
# smaller ones from an oversized cut. On a $1.25M listing: some calls takes
# the lesser of $50,000 and 5% ($62,499), so $50,000, showing $1.20M; no
# calls takes the lesser of $100,000 and 10% ($124,998), so $100,000, which
# lands just under the buyer pool at the Customary Value.
SOFT_CUT, SOFT_CUT_PCT = 50_000, 0.05     # 2 to 3 inquiries
# How far beneath the grid line the relaunch price sits. Casey, 15 Oct
# 2026, chose $100: $400,000 becomes $399,900 and $375,000 becomes
# $374,900.
UNDER_THRESHOLD = 100
HARD_CUT, HARD_CUT_PCT = 100_000, 0.10    # nobody calls, under $2M


def _recovery_rule_legacy(current_list, customary, customary_list=None):
    """PRE-21-OCTOBER rule. Reached only when a home is listed at or below
    its launch line (guard 3 of `_recovery_rule`).

    The two moves available after the 14-day Temporarily Off Market test.

    The rule itself. Call `recovery()` below, which adds the overrides.

    soft  — 2 or more calls and a favourable market: the lesser of $50,000
            and 3% of list.
    hard  — nobody calls. Over $2M the price goes BELOW the nearest recovery
            threshold under the list; under $2M a home that is $100,000 or
            more over its authenticated value drops $100,000 below list.
            A home that is over by less than that reconciles to the
            authenticated list price instead of inventing a bigger cut.
    """
    customary_list = customary_list or customary
    gap = current_list - customary                      # over the value
    soft_cut = min(SOFT_CUT, round(current_list * SOFT_CUT_PCT))
    soft = current_list - soft_cut
    soft_basis = f"a {money(soft_cut)} reduction"

    # Casey, 15 Oct 2026: "2-3 inquires, Buyers are watching recommendation
    # is always under closest threshold, first threshold of $50,000 or 5%
    # whichever is lower." So the measured cut only picks the neighbourhood;
    # the price itself drops to the first grid line at or below it and sits
    # UNDER_THRESHOLD beneath that line. On a $424,980 listing: 5% is
    # $21,249, which lands at $403,731, so the grid line is $400,000 and the
    # price is $399,900. The next rung down carries the deep move: $375,000,
    # so $374,900. This governs every price now, not only the $2M and over
    # ladder it used to.
    def _closest_line(price):
        """The grid line nearest the price, above or below.

        Nearest, not the one below: a cut that already lands $20 under a
        threshold is already under it, and stepping down again would
        recommend a cut twice the size the rule calls for. On a $1,249,980
        listing the 5% step reaches $1,199,980, which is $20 under $1.2M —
        that is the threshold to sit beneath, not $1.15M.
        """
        inc = increment_for(price)
        hi = grid_line_at_or_above(price, inc)
        lo = hi - inc if hi > price else hi
        return hi if (hi - price) <= (price - lo) else lo

    _line = _closest_line(soft)
    if _line - UNDER_THRESHOLD > 0:
        soft = _line - UNDER_THRESHOLD
        soft_cut = current_list - soft
        soft_basis = f"under the {abbrev(_line)} threshold"
        _d_line = _line - increment_for(_line - 1)
        _hard = _d_line - UNDER_THRESHOLD
        if 0 < _hard < soft:
            return {"gap": gap, "soft_cut": soft_cut, "soft": soft,
                    "soft_basis": soft_basis,
                    "hard_cut": current_list - _hard, "hard": _hard,
                    "hard_basis": f"under the next threshold at "
                                  f"{abbrev(_d_line)}",
                    "over_pct": (gap / customary * 100) if customary else 0}

    # The "nobody calls" move has to be DEEPER than the measured one, or the
    # page recommends a bigger cut for the better outcome. So the threshold
    # search runs below the soft price, not below the list: a home listed just
    # over a rung would otherwise land a dollar under it and read as a
    # smaller move than the 3% step.
    _hard_cut = min(HARD_CUT, round(current_list * HARD_CUT_PCT))
    if current_list >= 2_000_000:
        # Over $2M the ladder governs BOTH moves, not just the deep one. A
        # flat $50,000 off a $2.25M listing lands at $2.199M, which is no
        # buyer's search band; the rungs are where the pools actually sit.
        below = [t for t in RECOVERY_THRESHOLDS if 2_000_000 <= t < current_list]
        if below:
            _t = max(below)
            soft, soft_cut = _t - 1, current_list - (_t - 1)
            soft_basis = f"under the {abbrev(_t)} threshold"
            deeper = [t for t in RECOVERY_THRESHOLDS if 2_000_000 <= t < soft]
            if deeper:
                _d = max(deeper)
                hard = _d - 1
                hard_basis = f"under the next major threshold at {abbrev(_d)}"
            else:
                hard = soft - _hard_cut
                hard_basis = f"{money(_hard_cut)} below the threshold"
        else:
            hard, hard_basis = (current_list - _hard_cut,
                                f"{money(_hard_cut)} below list")
    else:
        # Under $2M, nobody calling: $100,000 off the list (or 10% if that is
        # less), which is what puts the price back in line with the pool.
        hard, hard_basis = (current_list - _hard_cut,
                            f"{money(_hard_cut)} off the list")

    if hard >= soft:                       # never recommend a shallower cut
        hard, hard_basis = min(hard, soft - 1), hard_basis + " (capped below the measured move)"

    return {"gap": gap, "soft_cut": soft_cut, "soft": soft,
            "soft_basis": soft_basis,
            "hard_cut": current_list - hard,
            "hard": hard, "hard_basis": hard_basis,
            "over_pct": (gap / customary * 100) if customary else 0}


def _nearest_line(price):
    """The grid line nearest `price`, above or below (ties go up)."""
    inc = increment_for(price)
    lo = grid_line_at_or_below(price, inc)
    hi = lo if lo == price else lo + inc
    return hi if (hi - price) <= (price - lo) else lo


RECOVERY_STEP = 50_000


def _recovery_rule(current_list, customary, customary_list=None):
    """The two relaunch prices after the 14-day Temporarily Off Market test.

    Casey, 7 Nov 2026 (9311 Talisman, $2,099,900 -> $1.99 -> $1.95): "It is
    $50k if 2-3 call unless there is a major threshold like $1M, 1.25M, 1.5M,
    1.75, 2M, 2.15, 2.25, 2.5 is within 50k. If no-one calls an additional
    50k unless you are within 50k of major threshold."

      2 to 3 call: list - $50K. If a major threshold sits within $50K under
        that price, drop to just under the threshold instead.
      No one calls: a further $50K off the 2-to-3 price, same threshold test.
    Replaces the 21 Oct ladder / midpoint rule (kept below as
    `_recovery_rule_oct21`), which went $1.999 -> $1.75 on Talisman.
    """
    gap = current_list - customary
    base = {"gap": gap, "over_pct": (gap / customary * 100) if customary else 0,
            "launch_line": None, "over_launch_pct": None, "ladder": False,
            "warning": None}

    def step(frm, what):
        cand = frm - RECOVERY_STEP
        near = [t for t in SAFE_HAVENS if cand - RECOVERY_STEP <= t <= cand]
        if near:
            t = max(near)
            return t - UNDER_THRESHOLD, f"under the {abbrev(t)} major threshold"
        return cand, f"{money(RECOVERY_STEP)} {what}"

    soft, soft_basis = step(current_list, "off the list")
    hard, hard_basis = step(soft, "below that")
    return dict(base, soft=soft, soft_cut=current_list - soft, soft_basis=soft_basis,
                hard=hard, hard_cut=current_list - hard, hard_basis=hard_basis)


def _recovery_rule_oct21(current_list, customary, customary_list=None):
    """The two relaunch prices after the 14-day Temporarily Off Market test.

    Casey, 21 Oct 2026: "When a home's customary price is so much lower than
    list price ($250k Winstead) reduction in temp off period needs to be more
    dramatic." Two regimes:

    $2M and over -- the ladder. 2 to 3 call: under the rung below the list.
    No one calls: under the rung below that. $2.25M -> $2.15M -> $2M.

    Under $2M -- the midpoint. The yardstick is the LAUNCH LINE: the first
    grid line under Customary Value (the lower of Customary Value and
    Customary List Price, the same anchor Coming Soon uses).
      2 to 3 call: the grid line nearest halfway between list and Customary.
      No one calls, gap to the launch line under 10%: the first line under
        Customary Value. Over 10%: the line closest to Customary Value.
    Guards: (1) a first drop at or above the list steps down a rung; (2) the
    no-calls price is forced below the 2-to-3 price; (3) a home listed at or
    below its launch line has no price to give back -- the legacy rule runs
    and `warning` says so. Every price sits UNDER_THRESHOLD under its line.
    """
    customary_list = customary_list or customary
    gap = current_list - customary
    base = {"gap": gap, "over_pct": (gap / customary * 100) if customary else 0,
            "launch_line": None, "over_launch_pct": None, "ladder": False,
            "warning": None}

    if current_list >= 2_000_000:
        below = [t for t in RECOVERY_THRESHOLDS if t < current_list]
        if len(below) >= 2:
            r1, r2 = below[-1], below[-2]
            soft, hard = r1 - UNDER_THRESHOLD, r2 - UNDER_THRESHOLD
            return dict(base, ladder=True, soft=soft, soft_cut=current_list - soft,
                        soft_basis=f"under the {abbrev(r1)} threshold",
                        hard=hard, hard_cut=current_list - hard,
                        hard_basis=f"under the next major threshold at {abbrev(r2)}")

    anchor = min(customary, customary_list)
    launch = grid_line_at_or_below(anchor, increment_for(anchor))
    if current_list <= launch:
        out = _recovery_rule_legacy(current_list, customary, customary_list)
        out.update({k: v for k, v in base.items() if k not in out})
        out["launch_line"] = launch
        out["warning"] = (f"Listed at or below the {abbrev(launch)} it would "
                          "launch at today -- this home's problem is not its "
                          "price. The pre-21-October rule was used.")
        return out

    over = current_list - launch
    pct = over / launch * 100
    mid = (current_list + customary) / 2
    l1 = _nearest_line(mid)
    soft_basis = "halfway between the list and Customary Value"
    if l1 >= current_list:                                   # guard 1
        l1 -= increment_for(l1 - 1)
        soft_basis = "the threshold under the list"
    if pct < 10:
        l2 = grid_line_at_or_below(customary, increment_for(customary))
        if l2 == customary:
            l2 -= increment_for(customary - 1)
        hard_basis = "under Customary Value"
    else:
        l2 = _nearest_line(customary)
        hard_basis = "at the threshold closest to Customary Value"
    while l2 >= l1:                                           # guard 2
        l2 -= increment_for(l2 - 1)
        hard_basis = f"under the next threshold at {abbrev(l2)}"
    soft, hard = l1 - UNDER_THRESHOLD, l2 - UNDER_THRESHOLD
    return dict(base, launch_line=launch, over_launch_pct=pct,
                soft=soft, soft_cut=current_list - soft,
                soft_basis=soft_basis,
                hard=hard, hard_cut=current_list - hard, hard_basis=hard_basis)


def recovery(current_list, customary, customary_list=None,
             soft_override=None, hard_override=None, exact=False):
    """`_recovery_rule`, with Casey's hand-set relaunch prices on top.

    `soft_override` / `hard_override` come from `recovery.soft_override` and
    `recovery.hard_override` on the property file and beat the rule outright,
    the same way `preview_override` and `coming_soon_override` do. The basis
    then says the price was set for this home rather than claiming a formula
    it did not come from.

    They exist because the rule is tuned for a home listed well ABOVE its
    authenticated value. 39014 Hughesville was over by $25,400 (3.8%, the
    smallest gap of any recovery on file) and the rule still produced
    $649,900 and $599,900 -- the deep move below the home's own Dated value
    and $50,100 under the cheapest closed comp. Casey set $675K and $650K.

    This is a WRAPPER rather than a branch inside the rule because the rule
    has an early return on the threshold-pair path; an override applied at
    the foot of the function was silently skipped on exactly the properties
    that take that path, which is most of them.
    """
    out = _recovery_rule(current_list, customary, customary_list)

    # A price written as a round threshold -- "$675k", "$650" -- takes the
    # house convention and sits UNDER_THRESHOLD beneath the line, because
    # that is where every other CST price sits and a pool shopping "under
    # $675,000" is not reached by listing AT $675,000. A price that is
    # already off the line (say $674,500) is used exactly as given.
    def _set(x):
        x = int(x)
        # "exact": Casey named the price to the dollar (4322 Thomas Brigade,
        # 16 Nov 2026: "599,000 is recovery price") -- use it as written.
        if exact:
            return x
        return x - UNDER_THRESHOLD if x % 1_000 == 0 else x

    if soft_override:
        out["soft"] = _set(soft_override)
        out["soft_cut"] = current_list - out["soft"]
        out["soft_basis"] = "set for this home"
    if hard_override:
        out["hard"] = _set(hard_override)
        out["hard_cut"] = current_list - out["hard"]
        out["hard_basis"] = "set for this home"
    return out

# ---------------------------------------------------------------- Reality Check
# Casey, 13 Oct 2026: "Under money at risk, I want to put in Reality check
# section" -> "Affordability is a foot note, Appreciation is a new number for
# calculation" -> "Pull value based on inflation. That is a test we are
# running" -> "Inflation seems more logical because interest rates are not
# calculated in, plus $1.051 seems more logical than 913."
#
# So the published figure is the INFLATION value, computed by working back
# through the appreciation and forward by inflation:
#
#     2019 value   = customary / (1 + appreciation)
#     today, if it had only tracked inflation
#                  = 2019 value * (1 + inflation)
#
# The earlier version subtracted the percentage-point gap from today's value
# (customary * 65%). That is not the same operation and ran ~$178K low on a
# $1.3M home, widening with price.
#
# Affordability stays a footnote in Casey's own words and is deliberately
# NOT turned into a value.
# Casey's reason is the right one: the 68% figure moves with mortgage rates
# as well as price, so pricing off it charges the whole rate shock to the
# seller's home. The inflation figure compares price to price.
BUYER_AFFORDABILITY = 0.682     # average buyer's income vs. what the average home needs, today
AFFORDABILITY_2019 = 1.03       # the same measure in 2019 -- the footnote's whole point
APPRECIATION_SINCE_2019 = 0.61  # how far homes have run
INFLATION_SINCE_2019 = 0.3017  # how far everything else has -- Casey, 13 Oct 2026:
                               # "The accurate Inflation rate since 2019 is 30.17"


def reality_check(customary):
    """What the home would be worth if it had only tracked inflation.

        base_2019 = customary / (1 + 0.61)
        value     = base_2019 * (1 + 0.26)

    Casey, 13 Oct 2026, supplied the copy with rounded figures. His note
    rounded the two numbers differently ($1,340,000 and $1,051,000), so the
    premium between them could not be derived from either rule. Everything
    here rounds to the nearest $1,000 and the premium is the difference of
    the two ROUNDED figures -- a seller who subtracts what is on the page
    gets the number that is on the page.
    """
    customary = int(customary)
    base_2019 = customary / (1 + APPRECIATION_SINCE_2019)
    infl = base_2019 * (1 + INFLATION_SINCE_2019)
    k = lambda v: int(round(v / 1_000.0)) * 1_000
    today_r, infl_r = k(customary), k(infl)
    return {
        "today": today_r,
        "inflation": infl_r,
        "premium": today_r - infl_r,
        "inflation_exact": round(infl),
        "base_2019": round(base_2019),
        "appreciation": APPRECIATION_SINCE_2019,
        "inflation_rate": INFLATION_SINCE_2019,
        "affordability_now": BUYER_AFFORDABILITY,
        "affordability_2019": AFFORDABILITY_2019,
    }
