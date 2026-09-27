#!/usr/bin/env python3
"""Fetch the latest news from official and community sources into www/data/live.json.

Used by server.py (POST /api/refresh) and runnable on its own:
    python3 server/refresh.py

Only the Python standard library is needed. Items arrive in English; if the optional
Claude translation step is available (see translate.py) it adds the Arabic text later.
"""
import concurrent.futures as cf
import datetime as dt
import hashlib
import html
import json
import os
import re
import threading
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from email.utils import parsedate_to_datetime

import translate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW = os.path.join(ROOT, "www")
LIVE_PATH = os.path.join(WWW, "data", "live.json")
BASE_PATH = os.path.join(WWW, "data", "news-data.js")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36 MarsadNews/1.0")
WINDOW_DAYS = 92
TIMEOUT = 15
MAX_PER_TAB = 200

AI_WORDS = ["AI", "A.I.", "artificial intelligence", "Copilot", "model", "agent", "LLM", "Llama",
            "Meta AI", "machine learning", "inference", "Gemini", "GPT", "Claude", "generative",
            "superintelligence", "neural"]

# Every source is either the developer's own channel ("official") or a community channel ("community").
SOURCES = [
    # Once Human
    dict(id="oh-steam", tab="once-human", kind="steam", sourceType="official", sourceName="Once Human — Steam News",
         url="https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=2139460&count=40&maxlength=0&feeds=steam_community_announcements",
         appid=2139460, limit=25),
    dict(id="oh-reddit", tab="once-human", kind="rss", sourceType="community", sourceName="r/OnceHumanOfficial",
         url="https://www.reddit.com/r/OnceHumanOfficial/top/.rss?t=week", limit=4, reddit=True,
         keywords=["patch", "update", "event", "scenario", "season", "maintenance", "announce", "roadmap", "collab",
                   "server", "hotfix", "mobile", "PS5", "Xbox", "anniversary", "dev ", "devs", "leak", "new "]),
    # Star Citizen
    dict(id="sc-commlink", tab="star-citizen", kind="rsi", sourceType="official", sourceName="RSI Comm-Link",
         url="https://robertsspaceindustries.com/api/hub/getCommlinkItems", limit=30, pages=3),
    dict(id="sc-reddit", tab="star-citizen", kind="rss", sourceType="community", sourceName="r/starcitizen",
         url="https://www.reddit.com/r/starcitizen/top/.rss?t=week", limit=4, reddit=True,
         keywords=["patch", "PTU", "Evocati", "Alpha", "update", "event", "Free Fly", "CitizenCon", "IAE", "Invictus",
                   "roadmap", "ISC", "SCL", "Squadron 42", "SQ42", "CIG", "announce", "release", "leak", "Chris Roberts"]),
    # AI tools
    dict(id="openai", tab="ai", kind="rss", sourceType="official", sourceName="OpenAI News", company="OpenAI",
         url="https://openai.com/news/rss.xml", limit=12,
         onlyCategories=["Product", "Research", "Safety", "Company", "Global Affairs", "Publication", "Release"]),
    dict(id="anthropic", tab="ai", kind="anthropic", sourceType="official", sourceName="Anthropic Newsroom", company="Anthropic",
         url="https://www.anthropic.com/news", limit=10),
    dict(id="deepmind", tab="ai", kind="rss", sourceType="official", sourceName="Google DeepMind Blog", company="Google",
         url="https://deepmind.google/blog/rss.xml", limit=8),
    dict(id="google-ai", tab="ai", kind="rss", sourceType="official", sourceName="Google Blog — AI", company="Google",
         url="https://blog.google/technology/ai/rss/", limit=8),
    dict(id="microsoft", tab="ai", kind="rss", sourceType="official", sourceName="Official Microsoft Blog", company="Microsoft",
         url="https://blogs.microsoft.com/feed/", limit=6, keywords=AI_WORDS),
    dict(id="meta", tab="ai", kind="rss", sourceType="official", sourceName="Meta Newsroom", company="Meta",
         url="https://about.fb.com/news/feed/", limit=6, keywords=AI_WORDS + ["glasses", "Connect"]),
    dict(id="apple", tab="ai", kind="rss", sourceType="official", sourceName="Apple Newsroom", company="Apple",
         url="https://www.apple.com/newsroom/rss-feed.rss", limit=4,
         keywords=["Apple Intelligence", "AI", "Siri", "machine learning"]),
    dict(id="nvidia", tab="ai", kind="rss", sourceType="official", sourceName="NVIDIA Blog", company="NVIDIA",
         url="https://blogs.nvidia.com/feed/", limit=6, keywords=AI_WORDS, defaultType="hardware"),
    dict(id="huggingface", tab="ai", kind="rss", sourceType="official", sourceName="Hugging Face Blog", company="Hugging Face",
         url="https://huggingface.co/blog/feed.xml", limit=5),
    dict(id="github", tab="ai", kind="rss", sourceType="official", sourceName="GitHub Changelog", company="GitHub",
         url="https://github.blog/changelog/feed/", limit=8, keywords=["Copilot", "AI", "agent", "model", "MCP"],
         defaultType="coding"),
    dict(id="cursor", tab="ai", kind="rss", sourceType="official", sourceName="Cursor Changelog", company="Anysphere",
         tool="Cursor", url="https://cursor.com/changelog/rss.xml", limit=5, defaultType="coding"),
    dict(id="hn", tab="ai", kind="hn", sourceType="community", sourceName="Hacker News",
         url="https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI&numericFilters=points%3E250&hitsPerPage=40",
         limit=6),
    dict(id="localllama", tab="ai", kind="rss", sourceType="community", sourceName="r/LocalLLaMA",
         url="https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week", limit=4, reddit=True),
]

_run_lock = threading.Lock()
_file_lock = threading.RLock()
_state = {"lastRefresh": None, "sources": []}


# ---------------------------------------------------------------- helpers

def now_utc():
    return dt.datetime.now(dt.timezone.utc)


MAX_BODY = 8_000_000
MAX_UNZIPPED = 20_000_000


def http_get(url, data=None, headers=None, retries=1):
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.8", "Accept-Encoding": "gzip"}
    h.update(headers or {})
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(MAX_BODY)
                if r.headers.get("Content-Encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
                    unzip = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    raw = unzip.decompress(raw, MAX_UNZIPPED)
                    if unzip.unconsumed_tail:
                        raise ValueError("response too large")
            return raw.decode("utf-8", "replace").lstrip("﻿ \r\n\t")
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 404) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == retries:
                raise
        time.sleep(1.5)


def strip_html(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s or "")
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|h[1-6]|li|ul|ol|blockquote|figure)>", "\n\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return tidy(html.unescape(s))


def strip_bbcode(s):
    s = re.sub(r"(?is)\[img[^\]]*\].*?\[/img\]", " ", s or "")
    s = re.sub(r"\{STEAM_CLAN_IMAGE\}\S*", " ", s)
    s = re.sub(r"(?is)\[previewyoutube[^\]]*\].*?\[/previewyoutube\]", " ", s)
    s = re.sub(r"(?is)\[url=[^\]]*\](.*?)\[/url\]", r"\1", s)
    s = re.sub(r"(?i)\[\*\]", "\n- ", s)
    s = re.sub(r"(?i)\[/?(h[1-6]|p)(?:[= ][^\]]*)?\]", "\n\n", s)
    s = re.sub(r"(?i)\[br\]", "\n", s)
    s = re.sub(r"\[/?[a-zA-Z0-9]+(?:[= ][^\]]*)?\]", " ", s)
    return tidy(html.unescape(strip_html(s)))


def tidy(s):
    s = s.replace("\r", "")
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clip(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for mark in ("\n\n", ". ", "\n"):
        i = cut.rfind(mark)
        if i > limit * 0.5:
            return cut[: i + (1 if mark == ". " else 0)].strip() + " …"
    return cut.rsplit(" ", 1)[0].strip() + " …"


def first_sentences(text, limit=240):
    flat = re.sub(r"\s+", " ", (text or "").replace("- ", " ")).strip()
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    i = cut.rfind(". ")
    return (cut[: i + 1] if i > 60 else cut.rsplit(" ", 1)[0] + " …").strip()


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        d = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", value)
            if not m:
                return None
            d = dt.datetime.fromisoformat(m.group(1))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


_PROFANITY = re.compile(r"\b(f+u+c+k\w*|shit\w*|bitch\w*|cunt\w*|asshole\w*|bastard\w*|dick\w*|wtf)\b", re.I)


def mask_profanity(s):
    return _PROFANITY.sub(lambda m: m.group(0)[0] + "***", s or "")


def keyword_match(text, keywords):
    if not keywords:
        return True
    for kw in keywords:
        if kw.isupper() and len(kw) <= 4:
            if re.search(r"(?<![A-Za-z])" + re.escape(kw) + r"(?![A-Za-z])", text):
                return True
        elif kw.lower() in text.lower():
            return True
    return False


_TRACKING = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|igshid|si|source)$", re.I)


def norm_url(u):
    """Comparable form of a link: no scheme, no "www.", no fragment or tracking parameters.
    The rest of the query stays, because it can be the whole identity (news.ycombinator.com/item?id=…)."""
    u = (u or "").strip()
    try:
        p = urllib.parse.urlsplit(u)
    except ValueError:
        return u.lower()
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    query = sorted((k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not _TRACKING.match(k))
    out = host + p.path.rstrip("/")
    return out + ("?" + urllib.parse.urlencode(query) if query else "")


def norm_title(t):
    return re.sub(r"[^a-z0-9؀-ۿ]+", " ", (t or "").lower()).strip()


def title_key(t):
    """Title-based duplicate key, only for titles specific enough to identify one story."""
    n = norm_title(t)
    return "t:" + n if len(n.split()) >= 5 else None


def item_keys(url, title):
    keys = {"u:" + norm_url(url)}
    tk = title_key(title)
    if tk:
        keys.add(tk)
    return keys


def item_id(url):
    return "auto-" + hashlib.sha1(norm_url(url).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- classification

def classify(tab, title, text, src):
    t = f"{title} {text[:400]}".lower()
    if src.get("sourceType") == "community" and tab != "ai":
        return "community"
    if tab == "once-human":
        if re.search(r"patch|bug fix|hotfix|maintenance|optimi[sz]ation|version \d|update notes|\d+\.\d+\.\d+", t):
            return "update"
        if re.search(r"scenario|season|new server|server launch", t):
            return "scenario"
        if re.search(r"collab|crossover|x once human", t):
            return "collab"
        if re.search(r"mobile|ps5|playstation|xbox|console|cross-?play|epic games", t):
            return "platform"
        if re.search(r"event|festival|anniversary|livestream|giveaway|contest|halloween|christmas|login reward", t):
            return "event"
        return "announcement"
    if tab == "star-citizen":
        # Decide on the headline first; the body often mentions the patch a ship ships with.
        for text_ in (title.lower(), t):
            if re.search(r"squadron 42|squadron42|sq42", text_):
                return "squadron42"
            if re.search(r"alpha \d|patch notes|hotfix|\bptu\b|evocati|live release", text_):
                return "patch"
            if re.search(r"^q&a|aegis|anvil|drake|\bmisc\b|origin \d|argo|aopoa|esperia|banu|"
                         r"consolidated outland|tumbril|greycat|mirai|gatac|kruger|\bship\b|concept sale|vehicle", text_):
                return "ship"
            if re.search(r"free fly|invictus|\biae\b|citizencon|expo|festival|luminalia|bar citizen|pirate week|\bevent\b", text_):
                return "event"
            if re.search(r"roadmap|this week in star citizen|inside star citizen|star citizen live|monthly report|"
                         r"letter from the chairman|engineering|development", text_):
                return "development"
        return "development"
    # ai
    if src.get("defaultType") in ("coding",):
        return "coding"
    if re.search(r"funding|acquir|acquisition|partnership|invest|raises|valuation|earnings|revenue", t):
        return "business"
    if re.search(r"policy|regulat|\blaw\b|government|court|lawsuit|security council|election|safety framework", t):
        return "policy"
    if re.search(r"\bgpt-?\d|gemini \d|claude [a-z]*\s?\d|llama \d|qwen|deepseek|mistral|new model|\bmodel\b.*(release|launch)|introducing .*model|open-weight|benchmark", t):
        return "model"
    if re.search(r"image|video|music|audio|voice|3d|design", t):
        return "media"
    if re.search(r"\bcode\b|coding|developer|\bapi\b|\bsdk\b|copilot|\bide\b|github|codex", t):
        return "coding"
    if src.get("defaultType"):
        return src["defaultType"]
    if re.search(r"chip|gpu|data cent|hardware|device|glasses|supercomputer", t):
        return "hardware"
    return "product"


def make_item(src, title, url, date, text, extra=None):
    title = tidy(html.unescape(title or ""))
    text = tidy(text or "")
    it = {
        "id": item_id(url),
        "tab": src["tab"],
        # The day as seen where this Mac is (the reader's time zone), plus the exact moment.
        "date": date.astimezone().strftime("%Y-%m-%d"),
        "publishedAt": date.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "type": classify(src["tab"], title, text, src),
        "importance": 1,
        "sourceType": src["sourceType"],
        "sourceName": src["sourceName"],
        "url": url,
        "originalTitle": title,
        "en": {"title": title, "summary": first_sentences(text or title), "details": clip(text, 1500)},
        "translated": False,
        "fetchedAt": now_utc().isoformat(timespec="seconds"),
    }
    if src.get("company"):
        it["company"] = src["company"]
    if src.get("tool"):
        it["tool"] = src["tool"]
    if extra:
        it.update(extra)
    return it


# ---------------------------------------------------------------- source fetchers

def fetch_steam(src):
    data = json.loads(http_get(src["url"]))
    out = []
    for n in data.get("appnews", {}).get("newsitems", []):
        stamp = int(n.get("date") or 0)
        if not stamp:
            continue
        date = dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
        url = f"https://store.steampowered.com/news/app/{src['appid']}/view/{n.get('gid')}"
        out.append(make_item(src, n.get("title", ""), url, date, strip_bbcode(n.get("contents", ""))))
    return out


def _text(el, *names):
    for name in names:
        child = el.find(name)
        if child is not None and (child.text or "").strip():
            return child.text
    return ""


def fetch_rss(src):
    body = http_get(src["url"])
    if not body.startswith("<"):
        raise ValueError("feed did not return XML")
    if "<!ENTITY" in body:  # no entity tricks from a misbehaving feed
        raise ValueError("feed declares XML entities")
    root = ET.fromstring(body.encode("utf-8"))
    atom = "{http://www.w3.org/2005/Atom}"
    content_ns = "{http://purl.org/rss/1.0/modules/content/}encoded"
    out = []
    items = root.findall(".//item")
    if items:
        for it in items:
            title = _text(it, "title")
            link = _text(it, "link").strip()
            cats = [c.text.strip() for c in it.findall("category") if c.text]
            if src.get("onlyCategories") and not any(c in src["onlyCategories"] for c in cats):
                continue  # e.g. OpenAI customer stories carry no category or "Startup"
            desc = _text(it, content_ns, "description")
            date = parse_date(_text(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date"))
            out.append((title, link, date, strip_html(desc)))
    else:
        for e in root.findall(f"{atom}entry"):
            title = _text(e, f"{atom}title")
            link_el = e.find(f"{atom}link[@rel='alternate']")
            if link_el is None:
                link_el = e.find(f"{atom}link")
            link = link_el.get("href") if link_el is not None else ""
            desc = _text(e, f"{atom}content", f"{atom}summary")
            date = parse_date(_text(e, f"{atom}published", f"{atom}updated"))
            out.append((title, link, date, strip_html(desc)))
    result = []
    for title, link, date, text in out:
        if not (title and link and date):
            continue
        if src.get("keywords") and not keyword_match(f"{title} {text[:600]}", src["keywords"]):
            continue
        if src.get("reddit"):
            text = re.sub(r"submitted by\s+/u/\S+.*$", "", text, flags=re.S).strip()
            text = re.sub(r"\[link\]\s*\[comments\]\s*$", "", text).strip()
            text = f"Community post on {src['sourceName']}.\n\n{mask_profanity(text)}".strip()
            title = mask_profanity(title)
        result.append(make_item(src, title, link, date, text))
    return result


_AGO = re.compile(r"(\d+|an?|one)\s+(minute|hour|day|week|month|year)s?\s+ago", re.I)


def ago_to_date(text):
    m = _AGO.search(text or "")
    now = now_utc()
    if not m:
        return now if re.search(r"just now|moments? ago|seconds? ago", text or "", re.I) else None
    n = 1 if m.group(1).lower() in ("a", "an", "one") else int(m.group(1))
    unit = m.group(2).lower()
    days = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
    if unit == "hour":
        return now - dt.timedelta(hours=n)
    return now - dt.timedelta(days=days)


def fetch_rsi(src):
    out = []
    for page in range(1, src.get("pages", 1) + 1):
        payload = json.dumps({"channel": "", "series": "", "type": "", "text": "", "sort": "publish_new", "page": page}).encode()
        data = json.loads(http_get(src["url"], payload, {"Content-Type": "application/json", "Accept": "application/json"}))
        blocks = (data.get("data") or "").split('<a class="content-block2')[1:]
        if not blocks:
            break
        for b in blocks:
            href = re.search(r'href="([^"]+)"', b)
            title = re.search(r'<div class="title[^"]*">(.*?)</div>', b, re.S)
            ago = re.search(r'class="time_ago">.*?<span class="value">(.*?)</span>', b, re.S)
            body = re.search(r'<div class="body">(.*?)</div>', b, re.S)
            if not (href and title):
                continue
            date = ago_to_date(ago.group(1) if ago else "")
            if not date:
                continue
            url = "https://robertsspaceindustries.com" + href.group(1).replace("\\/", "/")
            out.append(make_item(src, strip_html(title.group(1)), url, date, strip_html(body.group(1) if body else "")))
    return out


_ANTHROPIC_CATEGORIES = {"announcements", "product", "policy", "science", "research", "societal impacts",
                         "interpretability", "alignment", "economic research", "news", "case study", "event"}


def fetch_anthropic(src):
    page = http_get(src["url"])
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(/news/[a-z0-9-]+)"[^>]*>(.*?)</a>', page, re.S):
        path = m.group(1)
        if path in seen:
            continue
        inner = re.sub(r"<[^>]+>", "|", m.group(2))
        parts = [html.unescape(p).strip() for p in inner.split("|")]
        parts = [p for p in parts if p]
        date = None
        rest = []
        for p in parts:
            dm = re.fullmatch(r"([A-Z][a-z]{2,8})\.? (\d{1,2}, \d{4})", p)
            if dm and not date:
                try:
                    date = dt.datetime.strptime(f"{dm.group(1)[:3]} {dm.group(2)}", "%b %d, %Y").replace(tzinfo=dt.timezone.utc)
                except ValueError:
                    date = None
            elif p.lower() not in _ANTHROPIC_CATEGORIES and p.lower() != "category" and p.lower() != "title":
                rest.append(p)
        if not date or not rest:
            continue
        title = max(rest, key=len)
        desc = [p for p in rest if p != title]
        seen.add(path)
        out.append(make_item(src, title, "https://www.anthropic.com" + path, date, " ".join(desc)))
    return out


def fetch_hn(src):
    data = json.loads(http_get(src["url"]))
    out = []
    for hit in data.get("hits", []):
        title = hit.get("title") or ""
        if not keyword_match(title, ["AI", "LLM", "GPT", "Claude", "Gemini", "model", "agent", "OpenAI", "Anthropic", "DeepSeek", "Qwen", "Llama"]):
            continue
        date = parse_date(hit.get("created_at"))
        if not date:
            continue
        url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        points, comments = hit.get("points") or 0, hit.get("num_comments") or 0
        text = f"Community discussion on Hacker News ({points} points, {comments} comments)."
        out.append(make_item(src, title, url, date, text))
    return out


FETCHERS = {"steam": fetch_steam, "rss": fetch_rss, "rsi": fetch_rsi, "anthropic": fetch_anthropic, "hn": fetch_hn}


def fetch_source(src):
    t0 = time.time()
    try:
        items = FETCHERS[src["kind"]](src)
        cutoff = now_utc() - dt.timedelta(days=WINDOW_DAYS)
        items = [i for i in items if i["date"] >= cutoff.strftime("%Y-%m-%d")]
        items.sort(key=lambda i: i["date"], reverse=True)
        items = items[: src.get("limit", 10)]
        return {"id": src["id"], "ok": True, "count": len(items), "ms": int((time.time() - t0) * 1000)}, items
    except Exception as e:  # one broken feed must never sink the whole refresh
        msg = getattr(e, "reason", None) or str(e) or type(e).__name__
        if isinstance(e, urllib.error.HTTPError):
            msg = f"HTTP {e.code}"
        return {"id": src["id"], "ok": False, "count": 0, "error": str(msg)[:160]}, []


# ---------------------------------------------------------------- storage

def load_live():
    with _file_lock:
        try:
            with open(LIVE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    data.setdefault("items", [])
    data.setdefault("updatedAt", None)
    return data


def save_live(data):
    with _file_lock:
        folder = os.path.dirname(LIVE_PATH)
        os.makedirs(folder, exist_ok=True)
        # A unique temp file, so a second process writing at the same moment can't mix the two.
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=folder, suffix=".tmp", delete=False) as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            tmp = f.name
        os.replace(tmp, LIVE_PATH)


def curated_info():
    """URLs/titles already covered by the researched bilingual data, and the last day that data covers.

    Auto-fetched items are only added from that day on: older stories were already reviewed by hand."""
    keys = set()
    try:
        with open(BASE_PATH, encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (OSError, ValueError):
        return keys, None
    covered_to = (data.get("coverage") or {}).get("to")
    for tab in (data.get("tabs") or {}).values():
        for it in tab.get("news", []) + tab.get("upcoming", []):
            keys |= item_keys(it.get("url"), it.get("originalTitle") or (it.get("en") or {}).get("title"))
    return keys, covered_to


# ---------------------------------------------------------------- main entry points

def status():
    live = load_live()
    pending = sum(1 for i in live["items"] if not i.get("translated"))
    return {
        "server": True,
        "lastRefresh": _state["lastRefresh"],
        "liveUpdatedAt": live.get("updatedAt"),
        "liveItems": len(live["items"]),
        "untranslated": pending,
        "translate": translate.status(),
        "translating": translate.is_running(),
        "sources": _state["sources"],
    }


RUN_BUDGET = 60        # seconds for all sources together
MIN_GAP = 60           # a refresh within this many seconds of the last one reuses its result
_last_result = {"at": 0.0, "result": None}


def _cached_result(**extra):
    res = dict(_last_result["result"] or {"ok": True, "added": 0, "failed": [], "sources": _state["sources"]})
    res.update({"added": 0, "live": load_live(), "translating": translate.is_running()}, **extra)
    return res


def run():
    """Fetch every source, merge new items into live.json and start translation if available."""
    if time.time() - _last_result["at"] < MIN_GAP and _last_result["result"]:
        return _cached_result(recent=True)
    if not _run_lock.acquire(blocking=False):
        # Another refresh is running: wait for it (with a limit) and report its result.
        if _run_lock.acquire(timeout=RUN_BUDGET + 30):
            _run_lock.release()
        return _cached_result()
    try:
        started = now_utc()
        deadline = time.time() + RUN_BUDGET
        regular = [s for s in SOURCES if not s.get("reddit") and not s.get("disabled")]
        reddit = [s for s in SOURCES if s.get("reddit") and not s.get("disabled")]
        results, fetched = [], []
        pool = cf.ThreadPoolExecutor(max_workers=8)
        futures = {pool.submit(fetch_source, s): s for s in regular}
        done, late = cf.wait(futures, timeout=RUN_BUDGET)
        for fut in done:
            report, items = fut.result()
            results.append(report)
            fetched.extend(items)
        for fut in late:  # a stalled source is reported, not waited for
            results.append({"id": futures[fut]["id"], "ok": False, "count": 0, "error": "timed out"})
        pool.shutdown(wait=False)
        for i, src in enumerate(reddit):  # Reddit rate-limits bursts, so go one at a time
            if time.time() > deadline:
                results.append({"id": src["id"], "ok": False, "count": 0, "error": "skipped (time budget)"})
                continue
            if i:
                time.sleep(2)
            report, items = fetch_source(src)
            results.append(report)
            fetched.extend(items)

        skip, covered_to = curated_info()
        with _file_lock:
            live = load_live()
            by_id = {i["id"]: i for i in live["items"]}
            seen = set(skip)
            for i in by_id.values():
                seen |= item_keys(i["url"], i.get("originalTitle"))
            added = 0
            for it in fetched:
                if covered_to and it["date"] < covered_to:
                    continue
                keys = item_keys(it["url"], it["originalTitle"])
                if it["id"] in by_id:
                    old = by_id[it["id"]]
                    if not old.get("translated") and old.get("url") == it["url"]:
                        old["en"] = it["en"]  # refresh the English text while untranslated
                    continue
                if keys & seen:
                    continue
                seen |= keys
                by_id[it["id"]] = it
                added += 1
            cutoff = (now_utc() - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
            if covered_to and covered_to > cutoff:
                cutoff = covered_to  # anything older is covered by the researched data
            items = [i for i in by_id.values() if i["date"] >= cutoff and
                     not (item_keys(i["url"], i.get("originalTitle")) & skip)]
            items.sort(key=lambda i: (i["date"], i.get("fetchedAt", "")), reverse=True)
            per_tab = {}
            kept = []
            for i in items:
                per_tab[i["tab"]] = per_tab.get(i["tab"], 0) + 1
                if per_tab[i["tab"]] <= MAX_PER_TAB:
                    kept.append(i)
            live = {"updatedAt": now_utc().isoformat(timespec="seconds"), "items": kept}
            save_live(live)

        _state["lastRefresh"] = started.isoformat(timespec="seconds")
        _state["sources"] = results
        translating = translate.start_background(load_live, save_live, _file_lock)
        optional = {s["id"] for s in SOURCES if s.get("reddit")}  # Reddit often rate-limits; don't alarm the reader
        failed = [r["id"] for r in results if not r["ok"] and r["id"] not in optional]
        required = [s for s in regular]
        result = {"ok": True, "added": added, "failed": failed, "sources": results, "live": live,
                  "translating": translating, "offline": len(failed) >= len(required)}
        _last_result.update(at=time.time(), result={k: v for k, v in result.items() if k != "live"})
        return result
    finally:
        _run_lock.release()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Fetch the latest news from the official and community sources.")
    ap.add_argument("--out", help="write the items here instead of www/data/live.json (e.g. build/leads.json)")
    cli = ap.parse_args()
    if cli.out:
        LIVE_PATH = os.path.abspath(cli.out)
    res = run()
    for r in res["sources"]:
        print(f"{'OK ' if r['ok'] else 'ERR'} {r['id']:12} {r.get('count', 0):3d} {r.get('error', '')}")
    print(f"\nNew items: {res['added']} · total live items: {len(res['live']['items'])}")
    if res["translating"]:
        print("Translating new items with Claude in the background…")
        while translate.is_running():
            time.sleep(2)
        print("Translation finished.")
    else:
        print("Translation:", translate.status())
