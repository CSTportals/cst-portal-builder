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
6. Town home MSS package (csttownhomes.netlify.app, same page names): copy its
   *_Market_Snapshot.html pages into mss_pages_townhome/, save its map_embed.html as
   templates/MSS_Map_Townhome.html (keep the ?seg=/resize snippet), run
   `python3 refresh_cache_from_mss.py` (caches them as TH_<page>), commit.
   A town home property uses "market": {"slug": "TH_<page>"}; see townhome_mss.py.

## Rules for working in this repo
- This repo IS the builder. Never keep builder changes only in the workspace.
- Commit and push after every change to code, templates, property files or photos:
  `git add -A && git commit -m "<what changed>" && git -c push.negotiate=true push`
- If /home/claude/pbc2 is missing at session start, clone this repo there
  (`git clone --depth 1 https://github.com/CSTportals/cst-portal-builder /home/claude/pbc2`)
  before building anything.
