"""Optional step: write the Arabic + English title, summary and details of auto-fetched items with Claude.

Turned on when the `anthropic` package is installed (python3 -m pip install anthropic) and Claude API
credentials are available (ANTHROPIC_API_KEY, or a profile from `ant auth login`). Without it the site
still refreshes; new items simply show their English source text until translated.

Environment:
    MARSAD_TRANSLATE=0     turn the step off
    MARSAD_MODEL=<id>      model to use (default claude-opus-5)
"""
import json
import os
import threading

MODEL = os.environ.get("MARSAD_MODEL", "claude-opus-5")
BATCH = 6
MAX_PER_RUN = 36

TAB_TYPES = {
    "once-human": ["update", "scenario", "event", "collab", "platform", "announcement", "community"],
    "star-citizen": ["patch", "event", "ship", "squadron42", "development", "community"],
    "ai": ["model", "product", "coding", "media", "business", "policy", "hardware"],
}
ALL_TYPES = sorted({t for types in TAB_TYPES.values() for t in types})

_LANG_BLOCK = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "summary": {"type": "string"}, "details": {"type": "string"}},
    "required": ["title", "summary", "details"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ALL_TYPES},
                    "ar": _LANG_BLOCK,
                    "en": _LANG_BLOCK,
                },
                "required": ["id", "type", "ar", "en"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

PROMPT = """You write the entries of a bilingual (Arabic + English) news feed read mostly in the Gulf region. \
The feed has three sections: the game Once Human, the game Star Citizen, and AI tools.

For every source item below, write:
- en.title: at most 90 characters, factual, no clickbait, no trailing period.
- en.summary: the one- or two-sentence brief shown on the card, at most 240 characters.
- en.details: the full story shown when the reader taps "Details": 300–1,000 characters in 2–4 short paragraphs \
separated by a blank line; lines that start with "- " become bullet points (useful for patch notes).
- ar: the same three fields in clear Modern Standard Arabic news style. Keep names of games, products, models \
and companies in Latin script inside the Arabic text.
- type: the best category for the item's section — once-human: update, scenario, event, collab, platform, \
announcement, community; star-citizen: patch, event, ship, squadron42, development, community; ai: model, \
product, coding, media, business, policy, hardware.

Rules:
- Use only facts stated in the item's text and title. Never add facts, numbers, dates or context that are not there. \
If the text is short, keep the details short.
- Write in your own words; do not copy sentences from the source.
- For community items (sourceType "community"), make clear it is a community post or discussion.
- Return every id exactly once.

Items (JSON):
"""

_lock = threading.Lock()
_thread = None
_last_error = None


def status():
    """off | no_sdk | no_key | error | ready"""
    if os.environ.get("MARSAD_TRANSLATE", "1") == "0":
        return "off"
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return "no_sdk"
    if _last_error == "auth":
        return "no_key"
    if _last_error and _last_error != "rate_limited":
        return "error"
    has_env = any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"))
    has_profile = os.path.isdir(os.path.expanduser("~/.config/anthropic"))
    return "ready" if (has_env or has_profile) else "no_key"


def last_error():
    return _last_error


def is_running():
    return _thread is not None and _thread.is_alive()


def start_background(load, save, file_lock):
    """Translate pending items in a background thread. Returns True if work is running."""
    global _thread
    if status() != "ready":
        return False
    with _lock:
        if is_running():
            return True
        if not any(not i.get("translated") and not i.get("translateFailed") for i in load()["items"]):
            return False
        _thread = threading.Thread(target=_work, args=(load, save, file_lock), daemon=True)
        _thread.start()
        return True


def _valid(x, tab):
    if not isinstance(x, dict) or not isinstance(x.get("id"), str):
        return False
    for lang in ("ar", "en"):
        b = x.get(lang) or {}
        if not (isinstance(b.get("title"), str) and b["title"].strip() and isinstance(b.get("summary"), str)):
            return False
    return True


def _translate(client, batch):
    payload = [{
        "id": i["id"], "section": i["tab"], "source": i["sourceName"], "sourceType": i["sourceType"],
        "date": i["date"], "title": i.get("originalTitle", ""), "text": (i.get("en") or {}).get("details", "")[:3000],
    } for i in batch]
    params = dict(
        model=MODEL,
        max_tokens=32000,
        messages=[{"role": "user", "content": PROMPT + json.dumps(payload, ensure_ascii=False)}],
    )
    output_config = {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
    attempts = [
        # Server-side fallback: if a safety classifier declines, the API retries on Anthropic's recommended model.
        lambda: client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                            output_config=output_config, **params),
        # Older SDKs (the newest one pip offers on Python 3.9 is older) may not know these parameters.
        lambda: client.messages.stream(output_config=output_config, **params),
        lambda: client.messages.stream(extra_body={"output_config": output_config}, **params),
    ]
    stream_ctx = None
    for make in attempts:
        try:
            stream_ctx = make()
            break
        except TypeError:
            continue
    if stream_ctx is None:
        raise RuntimeError("the installed anthropic package is too old; run: python3 -m pip install -U anthropic")
    with stream_ctx as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        return {}
    # After a fallback the answer can continue across several text blocks, so read them all together.
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(text)
    tabs = {i["id"]: i["tab"] for i in batch}
    return {x["id"]: x for x in data.get("items", []) if x.get("id") in tabs and _valid(x, tabs[x["id"]])}


def _work(load, save, file_lock):
    global _last_error
    try:
        _run(load, save, file_lock)
    except Exception as e:  # never die silently: record it so /api/status reports it
        _last_error = f"unexpected: {type(e).__name__}: {str(e)[:160]}"


def _run(load, save, file_lock):
    global _last_error
    import anthropic

    try:
        client = anthropic.Anthropic()
    except Exception:  # no usable credentials
        _last_error = "auth"
        return

    def attempt(items):
        try:
            return _translate(client, items)
        except ValueError:  # the reply wasn't valid JSON (e.g. cut short)
            return {}

    done = 0
    while done < MAX_PER_RUN:
        pending = [i for i in load()["items"] if not i.get("translated") and not i.get("translateFailed")]
        if not pending:
            break
        batch = pending[:BATCH]
        try:
            result = attempt(batch)
            # One problem story shouldn't keep the rest of its batch in English: retry the missing ones alone.
            if len(batch) > 1:
                for item in batch:
                    if item["id"] not in result:
                        result.update(attempt([item]))
            _last_error = None
        except anthropic.AuthenticationError:
            _last_error = "auth"
            break
        except anthropic.RateLimitError:
            _last_error = "rate_limited"
            break
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            _last_error = f"api: {str(e)[:160]}"
            break
        ids = {i["id"] for i in batch}
        with file_lock:
            live = load()
            for it in live["items"]:
                if it["id"] in result:
                    r = result[it["id"]]
                    it["ar"] = {k: r["ar"][k].strip() for k in ("title", "summary", "details")}
                    it["en"] = {k: r["en"][k].strip() for k in ("title", "summary", "details")}
                    if r.get("type") in TAB_TYPES.get(it["tab"], []):
                        it["type"] = r["type"]
                    it["translated"] = True
                elif it["id"] in ids:
                    it["translateFailed"] = True
            save(live)
        done += len(batch)
