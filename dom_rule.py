"""How days on market is averaged, in one place.

Casey, 12 Oct 2026: "the calculation for DOM is DOM of best 80% of the sales
... that eliminates a few bad eggs", then "only exclude the last 10% of DOM."

Sort ascending, drop the slowest 10%, average the rest. The cut is rounded
to the nearest whole sale, so 37 sales keep 33 and 527 keep 474.

This lives on its own because the figure is published twice — the team's
number and the market's — and the comparison is only honest if both are
trimmed the same way. A copy of the arithmetic in each builder is a copy
that can drift.
"""

BEST_SHARE = 0.90


def best_dom(doms, share=BEST_SHARE):
    """Average DOM over the fastest `share` of the sales.

    Returns (average, kept, total). A set of fewer than two sales is
    returned untrimmed — there is no tail to cut.
    """
    d = sorted(int(x) for x in doms)
    n = len(d)
    if not n:
        return None, 0, 0
    k = max(1, int(round(n * share)))
    keep = d[:k]
    return sum(keep) / k, k, n


def dom_label(kept, total, share=BEST_SHARE):
    """The tile label, which has to say that the figure is trimmed.

    "Avg days on market" over a trimmed set would overstate the result
    without saying so, which is the one thing this figure must not do.
    """
    if kept >= total:
        return "Avg days on market"
    return f"Avg days on market (best {round(share * 100)}%, {kept} of {total})"
