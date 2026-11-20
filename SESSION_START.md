# Session start (every session, before building anything)

The build workspace can be reset between sessions. This repository is the
source of truth for the CST portal builder.

1. Clone or pull this repo into /home/claude/pbc2.
2. `pip install segno` if missing; build with `python3` (has Pillow + Playwright).
3. Build:  python3 build_portal.py properties/X.json
           python3 build_buyer_portal.py properties/X.json   (also writes <prefix>_Buyer_Small)
           python3 check_portal.py <stem>
4. After EVERY builder change: commit and push here.
5. New MSS package each week: copy its *_Market_Snapshot.html pages into mss_pages/,
   run `python3 refresh_cache_from_mss.py`, swap templates/MSS_Map.html, commit.
