"""Save a home to GitHub after every build.

Casey, 26 Nov 2026: "I am going to be updating folders weeks if not months
later. How do we keep files from falling apart" -- "moving forward will all
homes be saved by Github". The workspace is wiped between sessions; GitHub is
the only copy that lasts. After each build this commits the home's property
file, its photos and the private-label registry, and pushes. It never fails
the build: if the push cannot go through it says so loudly.
"""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent


def _git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True)


def save(prop_path, what="build"):
    prop = Path(prop_path).resolve()
    try:
        p = json.loads(prop.read_text())
    except Exception:
        return
    paths = [str(prop.relative_to(REPO))]
    for k in ("asset_dir",):
        if p.get(k) and (REPO / p[k]).exists():
            paths.append(p[k])
    b = p.get("buyer_portal") or {}
    if b.get("asset_dir") and (REPO / b["asset_dir"]).exists():
        paths.append(b["asset_dir"])
    for extra in ("pl_agents.json", "assets/brands", "assets/fonts"):
        if (REPO / extra).exists():
            paths.append(extra)
    _git("add", "--", *paths)
    if not _git("diff", "--cached", "--quiet").returncode:
        print(f"  GitHub: {p.get('prefix')} already saved")
    else:
        msg = (f"{p.get('prefix')}: save property file and photos ({what})\n\n"
               "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
        _git("commit", "-q", "-m", msg)
    r = _git("-c", "push.negotiate=true", "push", "-q")
    ahead = _git("rev-list", "--count", "@{u}..HEAD").stdout.strip()
    if r.returncode or (ahead and ahead != "0"):
        print("  !!! GitHub: NOT SAVED -- push failed; run "
              "`git -c push.negotiate=true push` before the session ends")
    else:
        print(f"  GitHub: {p.get('prefix')} saved")
