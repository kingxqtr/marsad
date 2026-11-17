#!/usr/bin/env python3
"""Validate the report data and build the final self-contained HTML page.

  python3 build_report.py work/<ship>.json --out work/<ship>-report.html
  python3 build_report.py work/<ship>.json --out work/<ship>-report.html --share-url https://claude.ai/artifact/XXXX

1. Checks the data: no TODO left, mandatory items present, damage sums, ordnance
   counts, prices, image sections. Errors stop the build (use --force to override).
2. Downloads each image "url" once (cached beside the data file), shrinks it to
   WebP and embeds it as a data: URI, so the page works as an Artifact and as a file.
3. Removes "_" notes, sets the share link, injects everything into assets/template.html.

Standard library only; Pillow is used for image shrinking when available.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import mimetypes
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "template.html")
SECTIONS = {"hero", "verdict", "prices", "loadout", "damage", "weapons", "rearm", "costs", "upgrades", "mobility",
            "specs", "cargo", "opinions"}
errors, warnings = [], []


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def walk(o, path=""):
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, dict):
        for k, v in o.items():
            if not str(k).startswith("_"):
                yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")


def validate(data):
    meta = data.get("meta") or {}
    for k in ("game_version", "verified_on"):
        if not meta.get(k):
            errors.append(f"meta.{k} مفقود.")
    if abs((num(meta.get("fx_qar_per_usd")) or 3.64) - 3.64) > 1e-9:
        warnings.append("سعر صرف الريال ليس 3.64؛ تأكد أن الربط تغيّر فعلًا.")
    ships = data.get("ships") or []
    if not ships:
        errors.append("لا توجد سفينة في الملف.")
    for s in ships:
        P = f"[{s.get('variant') or s.get('name')}] "
        for k in ("name", "status", "manufacturer"):
            if not s.get(k):
                errors.append(P + f"الحقل {k} مفقود.")
        todos = [(p, t) for p, t in walk(s) if "TODO" in t]
        for p, t in todos[:15]:
            errors.append(P + f"نص غير مكتمل في {p}: {t[:80]}")
        if len(todos) > 15:
            errors.append(P + f"... و{len(todos) - 15} حقل TODO آخر.")
        ig = (s.get("prices") or {}).get("ingame") or {}
        if num(ig.get("buy_auec")) is None and ig.get("available") is not False and not ig.get("note"):
            errors.append(P + "سعر الشراء داخل اللعبة: اكتب السعر أو available:false أو note.")
        if not (s.get("loadout") or {}).get("delivery"):
            errors.append(P + "loadout.delivery مفقود: هل تأتي معبأة؟")
        for x in (s.get("loadout") or {}).get("delivery") or []:
            if str(x.get("a")).lower() not in ("yes", "no", "partial", "unknown", "na"):
                warnings.append(P + f"جواب التسليم «{x.get('a')}» ليس yes/no/partial/unknown/na.")
        dm = s.get("damage") or {}
        pd, cd, td = num((dm.get("pilot") or {}).get("dps")), num((dm.get("crew") or {}).get("dps")), num((dm.get("total") or {}).get("dps"))
        if None not in (pd, cd, td) and td and abs(pd + cd - td) > 1:
            errors.append(P + f"الضرر: الطيار {pd} + الطاقم {cd} لا يساوي الإجمالي {td}.")
        st = [x for x in dm.get("stations") or [] if x.get("kind") != "pdc"]
        if st and td and abs(sum(num(x.get("dps")) or 0 for x in st) - td) > 2:
            warnings.append(P + "مجموع المحطات (بدون PDC) لا يطابق الإجمالي.")
        for o in s.get("ordnance") or []:
            if (num(o.get("loaded")) or 0) > (num(o.get("max")) or 0):
                errors.append(P + f"المقذوف {o.get('name')}: المحمّل أكبر من السعة.")
        for p in (s.get("prices") or {}).get("pledge") or []:
            if p.get("usd") is not None and (num(p.get("usd")) is None or num(p["usd"]) < 0):
                errors.append(P + f"سعر غير صالح في {p.get('label')}.")
        if not any(p.get("kind") == "warbond" for p in (s.get("prices") or {}).get("pledge") or []):
            warnings.append(P + "لا يوجد سطر Warbond في الأسعار (اكتب usd:null مع ملاحظة إن لم يوجد عرض).")
        secs = [im.get("section") for im in s.get("images") or []]
        for sec in secs:
            if sec not in SECTIONS:
                warnings.append(P + f"صورة بقسم غير معروف «{sec}».")
        if "hero" not in secs:
            warnings.append(P + "لا توجد صورة للمقدمة hero.")
        for p, t in walk(s):
            if re.search(r"https?://", t) and not p.startswith("images"):
                warnings.append(P + f"رابط داخل نص ({p}); الروابط مكانها قائمة المصادر.")
    if len(ships) > 1 and not (data.get("comparison") or {}).get("winners"):
        warnings.append("مقارنة بدون comparison.winners.")


def fetch(url, cache):
    os.makedirs(cache, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    for f in os.listdir(cache):
        if f.startswith(key):
            with open(os.path.join(cache, f), "rb") as fh:
                return fh.read(), mimetypes.guess_type(f)[0] or "image/jpeg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sc-ship-report/3.0 (image fetch)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data, mime = r.read(), (r.headers.get("Content-Type") or "image/jpeg").split(";")[0]
    except Exception as e:
        warnings.append(f"تعذر تنزيل صورة: {url} ({e})")
        return None
    with open(os.path.join(cache, key + (mimetypes.guess_extension(mime) or ".img")), "wb") as fh:
        fh.write(data)
    return data, mime


def shrink(data, mime, max_w, q):
    try:
        from PIL import Image  # type: ignore
        im = Image.open(io.BytesIO(data))
        im.load()
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=q, method=5)
        return out.getvalue(), "image/webp"
    except Exception:
        return data, mime


def embed(data, base, max_w, q, do_fetch):
    total = 0
    for s in data.get("ships") or []:
        kept = []
        for im in s.get("images") or []:
            src, blob = im.get("src"), None
            if src and src.startswith("data:"):
                kept.append(im)
                total += len(src)
                continue
            if src and not src.startswith("http"):
                p = src if os.path.isabs(src) else os.path.join(base, src)
                if os.path.exists(p):
                    with open(p, "rb") as fh:
                        blob = (fh.read(), mimetypes.guess_type(p)[0] or "image/jpeg")
            url = im.get("url") or (src if src and src.startswith("http") else None)
            if blob is None and url and do_fetch:
                blob = fetch(url, os.path.join(base, ".image-cache"))
            if not blob:
                continue
            b, mime = shrink(blob[0], blob[1], max_w, q)
            uri = f"data:{mime};base64," + base64.b64encode(b).decode()
            total += len(uri)
            kept.append({**{k: v for k, v in im.items() if k != "url"}, "src": uri})
        s["images"] = kept
    return total


def strip_notes(o):
    if isinstance(o, dict):
        return {k: strip_notes(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip_notes(x) for x in o]
    return o


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data")
    ap.add_argument("--out")
    ap.add_argument("--share-url", help="the published Artifact link, shown in the share panel")
    ap.add_argument("--template", default=TEMPLATE)
    ap.add_argument("--max-width", type=int, default=1600)
    ap.add_argument("--quality", type=int, default=78)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--check", action="store_true", help="validate only")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as fh:
        data = json.load(fh)
    validate(data)
    for w in warnings:
        print("تحذير:", w)
    for e in errors:
        print("خطأ:", e)
    if a.check:
        print(f"تحذيرات: {len(warnings)} · أخطاء: {len(errors)}")
        sys.exit(1 if errors else 0)
    if errors and not a.force:
        print(f"\nتوقف البناء: {len(errors)} خطأ.")
        sys.exit(1)
    data = strip_notes(data)
    if a.share_url:
        data.setdefault("meta", {})["share_url"] = a.share_url
    elif not (data.get("meta") or {}).get("share_url"):
        print("ملاحظة: لا يوجد رابط مشاركة بعد. انشر الصفحة، ثم أعد البناء مع --share-url والنشر على الرابط نفسه.")
    img = embed(data, os.path.dirname(os.path.abspath(a.data)), a.max_width, a.quality, not a.no_fetch)
    names = [s.get("variant") or s.get("name") for s in data["ships"]]
    title = ("تقرير " + names[0]) if len(names) == 1 else " × ".join(names)
    desc = (f"تقرير {names[0]} في Star Citizen: الأسعار، التجهيز الافتراضي، ضرر الطيار والطاقم، التعبئة، التكاليف والترقيات."
            if len(names) == 1 else f"مقارنة {' و'.join(names)} في Star Citizen.")
    with open(a.template, encoding="utf-8") as fh:
        tpl = fh.read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
    html = tpl.replace("__REPORT_TITLE__", title).replace("__REPORT_DESC__", desc.replace('"', "'")).replace("__REPORT_DATA__", payload)
    out = a.out or os.path.splitext(a.data)[0] + "-report.html"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    size = len(html.encode())
    print(f"\nتم البناء: {out}\nالحجم: {size / 1e6:.2f} MB (الصور {img / 1e6:.2f} MB) · تحذيرات {len(warnings)} · أخطاء {len(errors)}")
    if size > 15.5e6:
        print("خطأ: أكبر من حد 16MB؛ قلّل الصور.")
        sys.exit(1)


if __name__ == "__main__":
    main()
