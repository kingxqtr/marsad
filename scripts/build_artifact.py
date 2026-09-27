#!/usr/bin/env python3
"""Package www/ as a hosted claude.ai Artifact page.

    python3 scripts/build_artifact.py            # writes build/artifact/
    python3 scripts/build_artifact.py --out /path/to/folder

The artifact host wraps the page in its own <html>/<head>/<body>, so this drops those tags,
the charset/viewport meta and every tag marked data-standalone (manifest, icons, theme-color).
The published copy has no refresh server: its Refresh button reloads the latest published data.
"""
import argparse
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW = os.path.join(ROOT, "www")
FILES = ["assets/styles.css", "assets/app.js", "data/news-data.js"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "artifact"))
    ap.add_argument("--with-live", action="store_true", help="also publish www/data/live.json")
    args = ap.parse_args()

    with open(os.path.join(WWW, "index.html"), encoding="utf-8") as f:
        page = f.read()
    page = re.sub(r"(?i)<!doctype html>\s*", "", page)
    page = re.sub(r"(?i)</?(html|head|body)\b[^>]*>\s*", "", page)
    page = re.sub(r'(?i)<meta (charset|name="viewport")[^>]*>\s*', "", page)
    page = re.sub(r"(?im)^[ \t]*<[^>\n]*\bdata-standalone\b[^>\n]*>[ \t]*\n", "", page)

    os.makedirs(os.path.join(args.out, "assets"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "data"), exist_ok=True)
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page.strip() + "\n")
    for rel in FILES:
        shutil.copyfile(os.path.join(WWW, rel), os.path.join(args.out, rel))
    live_out = os.path.join(args.out, "data", "live.json")
    live_src = os.path.join(WWW, "data", "live.json")
    if args.with_live and os.path.exists(live_src):
        shutil.copyfile(live_src, live_out)
    else:
        with open(live_out, "w", encoding="utf-8") as f:
            json.dump({"updatedAt": None, "items": []}, f)
    out = os.path.abspath(args.out)
    print("\n".join(os.path.join(out, rel) for rel in ["index.html"] + FILES + ["data/live.json"]))


if __name__ == "__main__":
    main()
