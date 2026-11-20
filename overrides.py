#!/usr/bin/env python3.12
"""One place to hand-set anything on a property, without new code.

Casey, 19 Oct 2026: *"isn't there a simple way to just override things like
values or links that you don't have to go through a complicated process"* and
*"anything to make it quicker without messing anything else up."*

Before this there were SEVEN hand-set fields -- preview_override,
coming_soon_override, fallback_override, deep_override, launch_override, and
the recovery pair added the same morning -- each wired into three or four
places. Every new one was a code change, which is the opposite of quick.

    "overrides": {
      "coming_soon":      1099999,
      "recovery.soft":     674900,
      "buyer_portal.url": "https://buyerinblair2.netlify.app",
      "market.name":      "Haymarket Family Market",
      "subject.sf":          4086
    }

HOW IT WORKS, AND WHY IT IS SAFE

This is a patch on the property dict, applied once at load, BEFORE anything
is computed. It changes no calculation and no template. A short name is
translated to the hand-set field that already existed and is already tested
-- "coming_soon" writes values.coming_soon_override -- so every override
travels the code path it travelled yesterday. A dotted path writes straight
into the file's own structure.

That is the whole mechanism. Nothing downstream knows this module exists,
which is exactly why it cannot break anything that was working: a property
with no "overrides" block comes out of here byte-for-byte unchanged.

WHAT IT CANNOT DO

Only values the engine reads off the property file, or that already have a
hand-set field. A figure computed in several places with no single home
cannot be overridden until it has one -- that is a separate job, done per
case (recovery got its chokepoint on 19 Oct).
"""

# Short name -> where it actually lives. These are the fields that already
# existed; the alias only saves having to remember which block each sits in.
ALIASES = {
    # the five prices, all read inside one function in build_portal
    "preview":        "values.preview_override",
    "coming_soon":    "values.coming_soon_override",
    "comingsoon":     "values.coming_soon_override",
    "fallback":       "values.fallback_override",
    "fall_back":      "values.fallback_override",
    "deep":           "values.deep_override",
    "launch":         "values.launch_override",
    # the two relaunch prices on a recovery
    "recovery.soft":  "recovery.soft_override",
    "recovery.hard":  "recovery.hard_override",
    "soft":           "recovery.soft_override",
    "hard":           "recovery.hard_override",
    "buyer_pool":     "recovery.buyer_pool",
    # the links that have bitten us
    "buyer_url":      "buyer_portal.url",
    "buyer_deploy":   "buyer_portal.deploy_to",
    "portal_url":     "portal_url",
    "listing_url":    "listing_url",
}

# A path whose parent block is one of these is a normal part of a property
# file. Anything else is probably a typo, and a silently ignored typo is the
# failure this whole module exists to avoid.
KNOWN_BLOCKS = {"values", "subject", "market", "buyer_portal", "recovery",
                "comps", "local_snapshot", "market_local", "agent"}


def _dig(d, path):
    """The value at a dotted path, or None."""
    for k in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _put(d, path, value):
    """Set a dotted path, making the blocks along the way."""
    keys = path.split(".")
    for k in keys[:-1]:
        nxt = d.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            d[k] = nxt
        d = nxt
    d[keys[-1]] = value


def apply(p, note=print):
    """Fold `p["overrides"]` into `p`. Returns how many were applied.

    Every one is announced with what it replaced, because an override that
    nobody can see in the log is how a page ends up quoting a number no rule
    produced and nobody remembers setting.
    """
    over = p.get("overrides")
    if not over:
        return 0
    if not isinstance(over, dict):
        note('Overrides: "overrides" is not a block of settings — ignored. '
             'It should read "overrides": {"coming_soon": 1099999}.')
        return 0

    n = 0
    for key, value in over.items():
        path = ALIASES.get(str(key).strip().lower(), str(key).strip())
        head = path.split(".")[0]

        # A typo lands somewhere harmless and does nothing, so say so loudly
        # rather than letting the build look like it worked.
        if "." in path and head not in KNOWN_BLOCKS:
            note(f'Overrides: "{key}" was NOT applied — "{head}" is not a '
                 "block on a property file. Known blocks: "
                 + ", ".join(sorted(KNOWN_BLOCKS)) + ".")
            continue
        if "." not in path and path not in p and path not in ALIASES.values():
            note(f'Overrides: "{key}" sets a top-level field that is not on '
                 "this property file. Applied, but check the spelling.")

        was = _dig(p, path)
        _put(p, path, value)
        n += 1
        note(f'Override: {path} = {value!r}'
             + (f" (was {was!r})" if was is not None else " (was not set)")
             + (f' — written as "{key}"' if key != path else ""))
    if n:
        note(f"Overrides: {n} hand-set value{'s' if n != 1 else ''} on this "
             "property. Each one beats the rule that would otherwise compute "
             "it; remove it from the overrides block to go back to the rule.")
    return n
