#!/usr/bin/env python3
"""Copy the site into the public GitHub repository and push it (GitHub Pages).

    python3 scripts/publish_site.py             # normal use (the hourly update runs this)
    python3 scripts/publish_site.py --prepare   # copy + commit only (used by the first-time setup)

The repository lives outside iCloud (default ~/marsad-site, or set MARSAD_SITE_REPO) because
iCloud syncing and Git don't mix well. Until the one-time setup (نشر-الموقع.command) has been run,
this prints a note and does nothing.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.expanduser(os.environ.get("MARSAD_SITE_REPO", "~/marsad-site"))
COPY = [
    ("www", "www"),
    ("server/refresh.py", "server/refresh.py"),
    ("server/translate.py", "server/translate.py"),
    ("deploy/site.yml", ".github/workflows/site.yml"),
    ("deploy/README.md", "README.md"),
]
# In the repository the hourly GitHub job owns live.json; the Mac's own copy stays local.
SKIP = {os.path.join("www", "data", "live.json")}
EMPTY_LIVE = '{"updatedAt": null, "items": []}\n'


def git(*args, check=True, timeout=120):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")  # never wait for a password prompt
    return subprocess.run(["git", "-C", REPO] + list(args), check=check, capture_output=True,
                          text=True, timeout=timeout, env=env)


def is_set_up():
    if not os.path.isdir(os.path.join(REPO, ".git")):
        return False
    return git("remote", "get-url", "origin", check=False).returncode == 0


def copy_files():
    for src, dst in COPY:
        s = os.path.join(ROOT, src)
        if os.path.isfile(s):
            os.makedirs(os.path.dirname(os.path.join(REPO, dst)), exist_ok=True)
            shutil.copy2(s, os.path.join(REPO, dst))
            continue
        for base, dirs, files in os.walk(s):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for name in files:
                if name.startswith(".") or name.endswith((".tmp", ".pyc")):
                    continue
                full = os.path.join(base, name)
                if os.path.relpath(full, ROOT) in SKIP:
                    continue
                target = os.path.join(REPO, dst, os.path.relpath(full, s))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(full, target)
    live = os.path.join(REPO, "www", "data", "live.json")
    if not os.path.exists(live):
        with open(live, "w", encoding="utf-8") as f:
            f.write(EMPTY_LIVE)


def commit():
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    git("commit", "-q", "-m", "Update news")
    return True


def main():
    prepare = "--prepare" in sys.argv
    if not prepare and not is_set_up():
        print("الموقع العام غير مُعدّ بعد (شغّل نشر-الموقع.command مرة وحدة) — public site not set up yet; skipping.")
        return 0
    os.makedirs(REPO, exist_ok=True)
    try:
        if not prepare:
            git("pull", "-q", "--rebase", "--autostash", "origin", "main", check=False)  # the hourly job's commits
        copy_files()
        changed = commit()
        if prepare:
            print("Prepared", REPO)
            return 0
        if not changed and git("status", "-sb", check=False).stdout.find("ahead") == -1:
            print("Public site already up to date.")
            return 0
        push = git("push", "-q", "origin", "HEAD:main", check=False)
        if push.returncode != 0:
            print("Couldn't push to GitHub:", (push.stderr or push.stdout).strip()[:400])
            return 1
        print("Public site updated (GitHub Pages redeploys in a minute or two).")
        return 0
    except subprocess.TimeoutExpired:
        print("Git took too long; try again later.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
