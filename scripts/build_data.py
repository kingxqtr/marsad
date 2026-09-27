#!/usr/bin/env python3
"""Build the site's news data from the researched source files.

    python3 scripts/build_data.py [--from 2026-06-27] [--to 2026-09-27]

--to defaults to today and --from to three months earlier, so old stories age out on their own.

Reads   data/research/*.json         the original research, one file per topic
        data/research/daily/*.json   daily update files, applied in date order
        Each file: {"topic", "news": [...], "upcoming": [...], "removeNews": [ids], "removeUpcoming": [ids]}.
        An item whose id already exists replaces the earlier version.
Writes  www/data/news-data.js  (loaded by the website)
        data/news.json         (same content as plain JSON, for other apps such as the phone app)
        data/first-seen.json   (when each story first appeared; drives "new since your last visit")
"""
import argparse
import calendar
import datetime as dt
import glob
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "data", "research")
OUT_JS = os.path.join(ROOT, "www", "data", "news-data.js")
OUT_JSON = os.path.join(ROOT, "data", "news.json")
FIRST_SEEN = os.path.join(ROOT, "data", "first-seen.json")

TAB_TYPES = {
    "once-human": ["update", "scenario", "event", "collab", "platform", "announcement", "community"],
    "star-citizen": ["patch", "event", "ship", "squadron42", "development", "community"],
    "ai": ["model", "product", "coding", "media", "business", "policy", "hardware"],
}
FALLBACK_TYPE = {"once-human": "announcement", "star-citizen": "development", "ai": "product"}
ALIASES = {
    "once-human": {"patch": "update", "hotfix": "update", "season": "scenario", "release": "platform"},
    "star-citizen": {"update": "patch", "hotfix": "patch", "release": "patch", "squadron-42": "squadron42", "sq42": "squadron42"},
    "ai": {"release": "product", "event": "product", "tool": "product", "agents": "product", "funding": "business",
           "research": "model", "regulation": "policy", "legal": "policy", "chips": "hardware", "image": "media",
           "video": "media", "audio": "media"},
}
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def tab_for(topic):
    return "ai" if topic.startswith("ai") else topic


def clean(s):
    return re.sub(r"[ \t]+\n", "\n", str(s or "")).strip()


def lang_block(b, upcoming):
    b = b if isinstance(b, dict) else {}
    out = {
        "title": re.sub(r"[.。]$", "", clean(b.get("title"))),
        "summary": clean(b.get("summary")),
        "details": clean(b.get("details")) or clean(b.get("summary")),
    }
    if upcoming:
        for k in ("location", "dateNote"):
            if clean(b.get(k)):
                out[k] = clean(b.get(k))
    return out


def slug(s):
    return re.sub(r"[^a-z0-9-]+", "-", str(s).lower()).strip("-")[:80] or "item"


def norm_title(t):
    return set(re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower()).split())


def normalize(raw, tab, upcoming, warnings, where):
    if not isinstance(raw, dict):
        warnings.append(f"{where}: not an object")
        return None
    date = str(raw.get("date") or "")
    url = str(raw.get("url") or "")
    if not ISO.match(date):
        warnings.append(f"{where}: bad date {date!r}")
        return None
    if not re.match(r"^https?://", url):
        warnings.append(f"{where}: bad url {url!r}")
        return None
    ar, en = lang_block(raw.get("ar"), upcoming), lang_block(raw.get("en"), upcoming)
    if not ar["title"] and not en["title"]:
        warnings.append(f"{where}: no title")
        return None
    t = str(raw.get("type") or "").strip().lower()
    allowed = TAB_TYPES[tab] + (["event", "release"] if upcoming else [])
    if t not in allowed:
        t = ALIASES[tab].get(t, t)
    if t not in allowed:
        warnings.append(f"{where}: type {raw.get('type')!r} -> {FALLBACK_TYPE[tab]}")
        t = FALLBACK_TYPE[tab]
    try:
        importance = max(1, min(3, int(raw.get("importance") or 1)))
    except (TypeError, ValueError):
        importance = 1
    item = {
        "id": slug(raw.get("id") or f"{tab}-{date}-{en['title'] or ar['title']}"),
        "date": date,
        "type": t,
        "importance": importance,
        "sourceType": "community" if raw.get("sourceType") == "community" else "official",
        "sourceName": clean(raw.get("sourceName")) or re.sub(r"^https?://(www\.)?([^/]+).*$", r"\2", url),
        "url": url,
        "originalTitle": clean(raw.get("originalTitle")),
    }
    for k in ("company", "tool"):
        if clean(raw.get(k)):
            item[k] = clean(raw.get(k))
    if upcoming:
        end = raw.get("endDate")
        if end and ISO.match(str(end)) and str(end) >= date:
            item["endDate"] = str(end)
        item["dateConfidence"] = "expected" if raw.get("dateConfidence") == "expected" else "confirmed"
    item["ar"] = ar if ar["title"] else dict(en)
    item["en"] = en if en["title"] else dict(ar)
    return item


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def same_story(a, b):
    """Two entries about the same story. One announcement page can carry several stories,
    so a shared link alone isn't enough: the written titles must overlap too."""
    days = abs((dt.date.fromisoformat(a["date"]) - dt.date.fromisoformat(b["date"])).days)
    if days > 3:
        return False
    written = jaccard(norm_title(a["en"]["title"]), norm_title(b["en"]["title"]))
    if a["url"].rstrip("/").lower() == b["url"].rstrip("/").lower():
        return written >= 0.3
    if days == 0 and written >= 0.4:  # e.g. the same conference found by two researchers
        return True
    original = jaccard(norm_title(a["originalTitle"]), norm_title(b["originalTitle"]))
    return written >= 0.7 or (original >= 0.8 and a["originalTitle"] != "")


def three_months_before(d):
    """Same day three months earlier, clamped to the month's last day (31 May -> 28/29 Feb)."""
    y, m = (d.year, d.month - 3) if d.month > 3 else (d.year - 1, d.month + 9)
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def write_atomic(path, text):
    """Write via a temp file so a reader (the running server) never sees a half-written file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    today = dt.date.today()
    ap.add_argument("--from", dest="date_from", default=None)
    ap.add_argument("--to", dest="date_to", default=today.isoformat())
    args = ap.parse_args()
    date_to = dt.date.fromisoformat(args.date_to)
    date_from = dt.date.fromisoformat(args.date_from) if args.date_from else three_months_before(date_to)

    # The original research files first, then the daily update files in date order.
    # A later file replaces an item with the same id, and may list ids to drop.
    by_id = {t: {"news": {}, "upcoming": {}} for t in TAB_TYPES}
    warnings = []
    files = sorted(glob.glob(os.path.join(SRC_DIR, "*.json"))) + sorted(glob.glob(os.path.join(SRC_DIR, "daily", "*.json")))
    if not files:
        sys.exit(f"No research files in {SRC_DIR}")
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Removals apply at this point in the sequence, so a later file can bring an item back.
        for kind, key in (("news", "removeNews"), ("upcoming", "removeUpcoming")):
            for rid in data.get(key) or []:
                hit = [t for t in by_id if by_id[t][kind].pop(slug(rid), None) is not None]
                if not hit:
                    warnings.append(f"{os.path.basename(path)}: {key} id {rid!r} matched nothing")
        topic = data.get("topic") or os.path.splitext(os.path.basename(path))[0]
        tab = tab_for(topic)
        if tab not in by_id:
            warnings.append(f"{path}: unknown topic {topic!r}")
            continue
        for kind in ("news", "upcoming"):
            for n, raw in enumerate(data.get(kind) or []):
                it = normalize(raw, tab, kind == "upcoming", warnings, f"{os.path.basename(path)} {kind}[{n}]")
                if it:
                    by_id[tab][kind][it["id"]] = it
    tabs = {t: {k: list(v.values()) for k, v in kinds.items()} for t, kinds in by_id.items()}

    seen_ids = set()
    stats = {}
    for tab, d in tabs.items():
        news = [i for i in d["news"] if date_from.isoformat() <= i["date"] <= date_to.isoformat()]
        dropped = len(d["news"]) - len(news)
        if dropped:
            print(f"{tab}: {dropped} story/stories older than {date_from} left the 3-month window")
        news.sort(key=lambda i: (i["date"], i["importance"], len(i["ar"]["details"])), reverse=True)
        kept = []
        for it in news:
            dup = next((k for k in kept if same_story(k, it)), None)
            if dup:
                warnings.append(f"{tab}: duplicate dropped: {it['id']} (same as {dup['id']})")
                continue
            kept.append(it)
        ups = [i for i in d["upcoming"] if (i.get("endDate") or i["date"]) >= date_to.isoformat()]
        ups.sort(key=lambda i: i["date"])
        up_kept = []
        for it in ups:
            if any(same_story(k, it) for k in up_kept):
                continue
            up_kept.append(it)
        for it in kept + up_kept:
            base, n = it["id"], 2
            while it["id"] in seen_ids:
                it["id"] = f"{base}-{n}"
                n += 1
            seen_ids.add(it["id"])
        d["news"], d["upcoming"] = kept, up_kept
        months = {}
        for i in kept:
            months[i["date"][:7]] = months.get(i["date"][:7], 0) + 1
        stats[tab] = {"news": len(kept), "upcoming": len(up_kept), "months": dict(sorted(months.items())),
                      "community": sum(1 for i in kept if i["sourceType"] == "community")}

    # Remember when each story first appeared, so the site can mark what's new since a reader's last visit.
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        with open(FIRST_SEEN, encoding="utf-8") as f:
            first_seen = json.load(f)
    except (OSError, ValueError):
        first_seen = {}
    # A story can't be "added" after the end of the day it was published: that keeps a first build (or a
    # backfilled story) from marking everything as new for returning readers.
    for d in tabs.values():
        for it in d["news"] + d["upcoming"]:
            end_of_day = it["date"] + "T23:59:59+00:00" if it in d["news"] else now
            it["addedAt"] = first_seen[it["id"]] = min(first_seen.get(it["id"], now), end_of_day)
    write_atomic(FIRST_SEEN, json.dumps(first_seen, ensure_ascii=False, indent=0, sort_keys=True))

    out = {
        "version": 1,
        "updatedAt": now,
        "coverage": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "tabs": tabs,
    }
    write_atomic(OUT_JS, "/* Generated by scripts/build_data.py from data/research/*.json — edit those and rebuild. */\n"
                 + "window.NEWS_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    write_atomic(OUT_JSON, json.dumps(out, ensure_ascii=False, indent=1))

    for tab, s in stats.items():
        print(f"{tab:13} news={s['news']:3d} (community {s['community']}) upcoming={s['upcoming']:2d} months={s['months']}")
    if warnings:
        print(f"\n{len(warnings)} note(s):")
        for w in warnings:
            print("  -", w)
    print(f"\nWrote {os.path.relpath(OUT_JS, ROOT)} ({os.path.getsize(OUT_JS) // 1024} KB)")


if __name__ == "__main__":
    main()
