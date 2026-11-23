"""Put a property's photos back into assets/ from any portal zip or folder.

    python3 harvest_photos.py <zip-or-folder> [...]

Casey, 23 Nov 2026: "I can't go back and rebuild every buyer portal with
pictures. How do we store them." Photos live in assets/<prefix>/ (and
assets/<prefix>/buyer/) in this repo, committed with everything else. Homes
built before the repo existed never had theirs committed; a downloaded copy
of the live site (or any old portal zip) carries them, and this puts every
file a property file asks for back where the builder looks. Commit after.
"""
import json, os, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def wanted():
    out = {}
    for f in (ROOT / "properties").glob("*.json"):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(p, dict) or "prefix" not in p:
            continue
        b = p.get("buyer_portal") or {}
        ad = ROOT / (p.get("asset_dir") or f"assets/{p['prefix']}")
        bad = ROOT / (b.get("asset_dir") or f"{p.get('asset_dir') or 'assets/' + p['prefix']}/buyer")
        main = set(p.get("photos") or []) | ({p["hero_photo"]} if p.get("hero_photo") else set())
        buy = {g[0] for g in (b.get("gallery") or [])} | ({b["hero_photo"]} if b.get("hero_photo") else set())
        c = b.get("contacts") or {}
        if c.get("photo"):
            buy.add(c["photo"])
        for d in b.get("documents") or []:
            buy.add(d[0])
        for n in main:
            out.setdefault(n, []).append(ad)
        for n in buy:
            out.setdefault(n, []).append(bad)
    return out


def sources(paths):
    for s in paths:
        s = Path(s)
        if s.is_dir():
            for f in s.rglob("*"):
                if f.is_file():
                    yield f.name, f.read_bytes
        elif zipfile.is_zipfile(s):
            z = zipfile.ZipFile(s)
            for i in z.namelist():
                if not i.endswith("/"):
                    yield os.path.basename(i), (lambda i=i, z=z: z.read(i))


def main(paths):
    want, n = wanted(), 0
    for name, read in sources(paths):
        for dest in want.get(name, []):
            if not (dest / name).exists():
                dest.mkdir(parents=True, exist_ok=True)
                (dest / name).write_bytes(read())
                print("  +", (dest / name).relative_to(ROOT))
                n += 1
    print(f"{n} file(s) restored. Now: git add -A && git commit && git push")


if __name__ == "__main__":
    main(sys.argv[1:])
