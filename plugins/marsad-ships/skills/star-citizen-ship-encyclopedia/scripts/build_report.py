#!/usr/bin/env python3
"""Validate a ship-report data file and build the final HTML page.

  python3 build_report.py work/polaris.json --out work/polaris-report.html

What it does
  1. Checks the data against the report rules (mandatory items, DPS sums,
     ordnance counts, prices, links, section coverage) and prints ERRORS and
     WARNINGS. Errors stop the build unless --force is given.
  2. Downloads every image that has a "url" (once, cached next to the data
     file), shrinks it, and embeds it as a data: URI so the page is a single
     self-contained file that works as an Artifact (external images are blocked
     there) and as a plain file.
  3. Injects the data into assets/report-template.html and writes the page.

Only the standard library is required; Pillow is used for resizing when present.
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
TEMPLATE = os.path.join(HERE, "..", "assets", "report-template.html")
UA = "sc-ship-report/2.0 (image fetch)"
FX_PEG = 3.64
SECTIONS = ["uses", "identity", "weapons", "dps", "durability", "mobility", "components", "cargo",
            "pricing", "opinions", "rearm", "summary"]
SECTION_AR = {"uses": "1 الاستخدامات", "identity": "2 التعريف", "weapons": "3 الأسلحة", "dps": "4 DPS",
              "durability": "5 التحمل", "mobility": "6 الوقود والحركة", "components": "7 المكونات",
              "cargo": "8 الحمولة", "pricing": "9 الأسعار", "opinions": "10 آراء اللاعبين",
              "rearm": "11 دليل التعبئة", "summary": "الخلاصة"}
IMAGE_SECTIONS = {"hero"} | set(SECTIONS)

errors: list[str] = []
warnings: list[str] = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def empty(v):
    return v is None or v == "" or v == [] or v == {}


# ---------------------------------------------------------------- validation

def walk_strings(o, path=""):
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_strings(v, f"{path}[{i}]")


def validate(data: dict):
    meta = data.get("meta") or {}
    if empty(meta.get("game_version")):
        err("meta.game_version مفقود: اكتب إصدار LIVE الحالي (مثل Alpha 4.10.3 LIVE).")
    if empty(meta.get("verified_on")):
        err("meta.verified_on مفقود: اكتب تاريخ التحقق YYYY-MM-DD.")
    fx = num(meta.get("fx_qar_per_usd")) or FX_PEG
    if abs(fx - FX_PEG) > 1e-9:
        warn(f"meta.fx_qar_per_usd = {fx} يختلف عن سعر الربط 3.64؛ تأكد أن الربط تغيّر فعلًا.")

    ships = data.get("ships") or []
    if not ships:
        err("ships فارغة: لا توجد سفينة في الملف.")
        return
    if len(ships) > 1:
        comp = data.get("comparison") or {}
        if empty(comp.get("winners")):
            warn("وضع المقارنة بلا comparison.winners (جدول الفائز في كل استخدام).")

    for idx, s in enumerate(ships):
        tag = s.get("variant") or s.get("name") or f"ship[{idx}]"
        P = f"[{tag}] "
        for k in ("name", "manufacturer", "status"):
            if empty(s.get(k)):
                err(P + f"الحقل {k} مفقود.")
        for sec in SECTIONS:
            if empty(s.get(sec)):
                warn(P + f"القسم {SECTION_AR[sec]} فارغ؛ سيظهر بعبارة «لا توجد معلومات مؤكدة». اكتب «غير منطبق» داخله إن كان لا ينطبق.")
        if len(s.get("hero_stats") or []) < 6:
            warn(P + "hero_stats أقل من 6 أرقام للمقدمة.")

        # mandatory: in-game price
        ig = (s.get("pricing") or {}).get("ingame")
        if ig is None:
            err(P + "pricing.ingame مفقود — سعر الشراء داخل اللعبة بند إلزامي (اكتب السعر أو available:false أو note).")
        elif num(ig.get("buy_auec")) is None and ig.get("available") is not False and empty(ig.get("note")):
            err(P + "pricing.ingame بلا سعر ولا available:false ولا note تشرح عدم التأكد.")

        # mandatory: ammo state on delivery
        rq = (s.get("rearm") or {}).get("delivery_qa") or []
        if not rq:
            err(P + "rearm.delivery_qa مفقود — حالة الأسلحة والذخيرة عند الاستلام بند إلزامي.")
        for x in rq:
            if str(x.get("a", "")).lower() not in ("yes", "no", "partial", "unknown"):
                warn(P + f"delivery_qa: الإجابة «{x.get('a')}» ليست yes/no/partial/unknown في سؤال «{x.get('q')}».")

        # pricing values
        for o in (s.get("pricing") or {}).get("pledge") or []:
            u = num(o.get("usd"))
            if u is None or u < 0:
                err(P + f"pricing.pledge «{o.get('label')}»: usd غير صالح ({o.get('usd')}).")
            if "qar" in o and u is not None and abs(num(o["qar"]) - u * fx) > 0.5:
                err(P + f"pricing.pledge «{o.get('label')}»: QAR {o['qar']} ≠ USD × {fx}. احذف حقل qar، الصفحة تحسبه.")

        # DPS consistency
        d = s.get("dps") or {}
        po, co, to = num(d.get("pilot_only")), num(d.get("crew_only")), num(d.get("total"))
        if None not in (po, co, to) and to > 0 and abs(po + co - to) / to > 0.01:
            warn(P + f"DPS: الطيار {po:g} + الطاقم {co:g} = {po + co:g} لا يساوي الإجمالي {to:g}. راجع تكرار الجمع أو أسلحة يتحكم فيها أكثر من مقعد.")
        st = [x for x in d.get("stations") or [] if num(x.get("dps")) is not None]
        if st and to:
            s_all = sum(num(x["dps"]) for x in st)
            s_nopdc = sum(num(x["dps"]) for x in st if x.get("kind") != "pdc")
            if min(abs(s_all - to), abs(s_nopdc - to)) / to > 0.02:
                warn(P + f"DPS: مجموع المحطات {s_all:g} (بدون PDC {s_nopdc:g}) لا يطابق الإجمالي {to:g}.")
        pil = [x for x in st if x.get("kind") == "pilot"]
        if po is not None and pil and abs(sum(num(x["dps"]) for x in pil) - po) > 1:
            warn(P + "DPS: محطة الطيار في stations لا تساوي pilot_only.")

        # ordnance counts
        for o in (s.get("weapons") or {}).get("ordnance") or []:
            ld, mx, sv = num(o.get("loaded")), num(o.get("max")), num(o.get("salvo"))
            if ld is not None and mx is not None and ld > mx:
                err(P + f"ordnance «{o.get('name')}»: المحمّل {ld:g} أكبر من السعة القصوى {mx:g}.")
            if sv is not None and ld is not None and sv > ld > 0:
                warn(P + f"ordnance «{o.get('name')}»: الرشقة {sv:g} أكبر من المحمّل {ld:g}.")
            if str(o.get("comes_with_ship", "")).lower() not in ("yes", "no", "partial", "unknown"):
                warn(P + f"ordnance «{o.get('name')}»: comes_with_ship يجب أن يكون yes/no/partial/unknown.")

        # weapons need explicit ammo state
        for w in (s.get("weapons") or {}).get("mounts") or []:
            a = w.get("ammo") or {}
            if a.get("needs_refill") not in (True, False):
                warn(P + f"سلاح «{w.get('name')}»: ammo.needs_refill غير محدد (true/false).")

        # quantum calculator inputs
        q = ((s.get("mobility") or {}).get("quantum") or {})
        cap = num(((s.get("mobility") or {}).get("fuel") or {}).get("quantum_scu"))
        drives = [x for x in q.get("drives") or [] if num(x.get("fuel_rate"))]
        if s.get("status", "").lower().startswith("flight") and (cap is None or not drives):
            warn(P + "حاسبة الكوانتم لن تعمل: يلزم mobility.fuel.quantum_scu و mobility.quantum.drives[].fuel_rate.")
        if cap and drives and num(q.get("range_gm")):
            stock = next((x for x in drives if x.get("stock")), drives[0])
            calc = cap / num(stock["fuel_rate"])
            if abs(calc - num(q["range_gm"])) / calc > 0.03:
                warn(P + f"مدى الكوانتم {q['range_gm']} Gm لا يطابق السعة ÷ المعدل = {calc:.1f} Gm.")

        # images
        secs = {}
        for im in s.get("images") or []:
            sec = im.get("section")
            if sec not in IMAGE_SECTIONS:
                warn(P + f"صورة بقسم غير معروف «{sec}»؛ الأقسام: {', '.join(sorted(IMAGE_SECTIONS))}.")
            secs[sec] = secs.get(sec, 0) + 1
            if empty(im.get("url")) and empty(im.get("src")):
                err(P + "صورة بلا url ولا src.")
        if "hero" not in secs:
            warn(P + "لا توجد صورة للمقدمة (section: hero).")

        # no source links inside the page (rule from v1.1.0) and no unfinished TODOs
        todos = 0
        for path, text in walk_strings(s):
            if path.startswith("_") or path.startswith("images"):
                continue
            if re.search(r"https?://", text):
                warn(P + f"رابط داخل نص التقرير ({path}). القاعدة: لا روابط ولا أسماء مصادر في الصفحة.")
            if "TODO" in text:
                todos += 1
                if todos <= 12:
                    err(P + f"نص غير مكتمل TODO في {path}: {text[:90]}")
        if todos > 12:
            err(P + f"... و{todos - 12} حقل TODO آخر.")

    if not errors and not warnings:
        print("التحقق: لا أخطاء ولا تحذيرات.")


# ---------------------------------------------------------------- images

def fetch(url: str, cache_dir: str) -> tuple[bytes, str] | None:
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    for f in os.listdir(cache_dir):
        if f.startswith(key):
            with open(os.path.join(cache_dir, f), "rb") as fh:
                return fh.read(), mimetypes.guess_type(f)[0] or "image/jpeg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            mime = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    except Exception as e:
        warn(f"تعذر تنزيل الصورة: {url} ({e}). ستُنشر الصفحة بدونها.")
        return None
    ext = mimetypes.guess_extension(mime) or ".img"
    with open(os.path.join(cache_dir, key + ext), "wb") as fh:
        fh.write(data)
    return data, mime


def shrink(data: bytes, mime: str, max_w: int, quality: int) -> tuple[bytes, str]:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return data, mime
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        if im.width > max_w:
            h = round(im.height * max_w / im.width)
            im = im.resize((max_w, h), Image.LANCZOS)
        out = io.BytesIO()
        if im.mode == "RGBA":
            im.save(out, "WEBP", quality=quality, method=5)
        else:
            im.save(out, "WEBP", quality=quality, method=5)
        b = out.getvalue()
        return (b, "image/webp") if len(b) < len(data) or im.width >= max_w else (data, mime)
    except Exception as e:
        warn(f"تعذر ضغط صورة ({e}); استُخدمت كما هي.")
        return data, mime


def embed_images(data: dict, base_dir: str, max_w: int, quality: int, do_fetch: bool):
    cache = os.path.join(base_dir, ".image-cache")
    total = 0
    for s in data.get("ships") or []:
        kept = []
        for im in s.get("images") or []:
            src = im.get("src")
            blob = None
            if src and src.startswith("data:"):
                kept.append(im)
                total += len(src)
                continue
            if src and not re.match(r"https?://", src):
                p = src if os.path.isabs(src) else os.path.join(base_dir, src)
                if os.path.exists(p):
                    with open(p, "rb") as fh:
                        blob = (fh.read(), mimetypes.guess_type(p)[0] or "image/jpeg")
                else:
                    warn(f"ملف الصورة غير موجود: {p}")
            url = im.get("url") or (src if src and re.match(r"https?://", src) else None)
            if blob is None and url and do_fetch:
                blob = fetch(url, cache)
            if blob is None:
                continue
            b, mime = shrink(blob[0], blob[1], max_w, quality)
            uri = f"data:{mime};base64," + base64.b64encode(b).decode()
            total += len(uri)
            new = {k: v for k, v in im.items() if k != "url"}
            new["src"] = uri
            kept.append(new)
        s["images"] = kept
    return total


# ---------------------------------------------------------------- build

def build(args):
    with open(args.data, encoding="utf-8") as fh:
        data = json.load(fh)
    validate(data)
    for w in warnings:
        print("تحذير:", w)
    for e in errors:
        print("خطأ:", e)
    if errors and not args.force:
        print(f"\nتوقف البناء: {len(errors)} خطأ. صحّحها أو استخدم --force.")
        sys.exit(1)

    base = os.path.dirname(os.path.abspath(args.data))
    img_bytes = embed_images(data, base, args.max_width, args.quality, not args.no_fetch)

    ships = data["ships"]
    for sh in ships:
        for k in [k for k in sh if k.startswith("_")]:
            del sh[k]
    names = [s.get("variant") or s.get("name") for s in ships]
    title = ("تقرير " + names[0]) if len(ships) == 1 else " × ".join(names)
    desc = (f"تقرير شامل بالعربية عن {names[0]} في Star Citizen: الأسلحة والضرر والوقود والأسعار ودليل التعبئة."
            if len(ships) == 1 else f"مقارنة شاملة بين {' و'.join(names)} في Star Citizen.")

    with open(args.template, encoding="utf-8") as fh:
        tpl = fh.read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/").replace("<!--", "<\\!--")
    html = (tpl.replace("__REPORT_TITLE__", title)
               .replace("__REPORT_DESC__", desc.replace('"', "'"))
               .replace("__REPORT_DATA__", payload))
    out = args.out or os.path.splitext(args.data)[0] + "-report.html"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    size = len(html.encode("utf-8"))
    print(f"\nتم البناء: {out}")
    print(f"الحجم: {size / 1e6:.2f} MB (الصور {img_bytes / 1e6:.2f} MB) · صور مضمّنة: {sum(len(s.get('images') or []) for s in ships)}")
    if size > 15.5e6:
        print("خطأ: الصفحة تتجاوز حد 16MB للـArtifact. قلّل الصور أو --max-width.")
        sys.exit(1)
    if size > 12e6:
        print("تحذير: الصفحة كبيرة؛ قلّل عدد الصور أو جودتها.")
    print(f"تحذيرات: {len(warnings)} · أخطاء: {len(errors)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", help="ship report JSON (see references/data-schema.md)")
    ap.add_argument("--out", help="output .html path (default: <data>-report.html)")
    ap.add_argument("--template", default=TEMPLATE)
    ap.add_argument("--max-width", type=int, default=1600, help="max image width in px (default 1600)")
    ap.add_argument("--quality", type=int, default=78, help="WebP quality (default 78)")
    ap.add_argument("--no-fetch", action="store_true", help="do not download image URLs")
    ap.add_argument("--check", action="store_true", help="validate only, do not build")
    ap.add_argument("--force", action="store_true", help="build even when errors are found")
    a = ap.parse_args()
    if a.check:
        with open(a.data, encoding="utf-8") as fh:
            validate(json.load(fh))
        for w in warnings:
            print("تحذير:", w)
        for e in errors:
            print("خطأ:", e)
        print(f"تحذيرات: {len(warnings)} · أخطاء: {len(errors)}")
        sys.exit(1 if errors else 0)
    build(a)


if __name__ == "__main__":
    main()
