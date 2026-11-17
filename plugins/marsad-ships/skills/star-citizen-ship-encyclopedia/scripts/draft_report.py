#!/usr/bin/env python3
"""Turn the facts file from fetch_ship.py into a draft report data file.

  python3 draft_report.py work/polaris-facts.json --out work/polaris.json

Every number that the APIs provide is copied by code (specs, weapons, turrets,
ordnance, DPS stations, shields, armor, fuel, quantum drives and routes,
components, cargo, pledge SKUs, aUEC prices, insurance). Everything that needs
research or judgement is left as a string starting with "TODO" - build_report.py
refuses to build while any TODO remains. Fields prefixed with "_" are notes for
the writer and are stripped from the published page.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re

TODO = "TODO"

TYPE_LABEL = {
    "PowerPlant": "Power Plant", "Cooler": "Cooler", "Shield": "Shield Generator", "QuantumDrive": "Quantum Drive",
    "JumpDrive": "Jump Drive", "Radar": "Radar", "LifeSupportGenerator": "Life Support", "FuelTank": "Hydrogen Fuel Tank",
    "QuantumFuelTank": "Quantum Fuel Tank", "FuelIntake": "Fuel Intake", "TractorBeam": "Tractor Beam",
    "SelfDestruct": "Self Destruct", "WeaponMining": "Mining Laser", "SalvageHead": "Salvage Head",
    "QuantumInterdictionGenerator": "Quantum Interdiction", "EMP": "EMP", "Scanner": "Scanner",
}
STATUS = {"flight-ready": "Flight Ready", "in-concept": "Concept", "in-production": "In Production"}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def r1(v, n=1):
    v = num(v)
    return None if v is None else round(v, n)


def dmg_kind(w):
    dt_ = (w.get("dps_by_type") or {})
    best = max(dt_.items(), key=lambda kv: kv[1] or 0)[0] if dt_ else None
    return {"energy": "Energy", "physical": "Ballistic", "distortion": "Distortion", "thermal": "Thermal"}.get(best, None)


def ammo_kind(w):
    k = dmg_kind(w)
    return {"Energy": "energy", "Ballistic": "ballistic", "Distortion": "distortion"}.get(k, "energy")


def humanize(cls):
    if not cls:
        return None
    s = re.sub(r"^[A-Z]{3,4}_[A-Za-z0-9]+?_", "", cls)
    s = s.replace("SCItem_", "").replace("_", " ")
    return s.strip()


def version_bits(v):
    m = re.match(r"(\d+\.\d+(?:\.\d+)?)-([A-Z]+)\.?(\d+)?", v or "")
    if not m:
        return v, None
    return f"Alpha {m.group(1)} {m.group(2)}", m.group(3)


def make(f: dict, today: str):
    i, d, m, c = f["identity"], f["durability"], f["mobility"], f["cargo"]
    wi, oi = f.get("weapon_items") or {}, f.get("ordnance_items") or {}
    gv, build = version_bits(f.get("game_version"))
    unverified = []

    # ---------------- weapons from turrets + pilot weapons
    by_name = {w["name"]: w for w in wi.values()}
    mounts, stations = [], []
    pilot_rows = [g for g in f.get("weapons_mounted") or [] if not g.get("in_turret")]
    pilot_dps = 0.0
    for g in pilot_rows:
        w = wi.get(g["uuid"], {})
        pilot_dps += (num(w.get("dps_burst")) or 0) * g["count"]
    groups = {"manned": ("برج مأهول", "turret", "Manned Turret"), "remote": ("برج عن بُعد", "remote", "Remote Turret"),
              "pdc": ("دفاع نقطي PDC", "pdc", "PDC (automatic)")}
    for g in pilot_rows:
        w = wi.get(g["uuid"], {})
        mounts.append(mount_row(w, g["count"], "الطيار", "Fixed / Gimbal — " + TODO, g.get("root_port"), {"pilot": True, "copilot": False, "turret": False, "auto": False}))
    pdc_dps, pdc_n = 0.0, 0
    slaved = []
    for kind, rows in (f.get("turrets") or {}).items():
        label, skind, mount = groups.get(kind, ("برج", "turret", "Turret"))
        for idx, t in enumerate(rows):
            names = t.get("weapons") or []
            if not names:
                continue
            cnt = {}
            for n in names:
                cnt[n] = cnt.get(n, 0) + 1
            where = humanize(t.get("class_name")) or t.get("hardpoint")
            for n, k in cnt.items():
                w = by_name.get(n, {"name": n})
                ctl = {"pilot": False, "copilot": False, "turret": kind != "pdc", "auto": kind == "pdc"}
                mounts.append(mount_row(w, k, f"{label}: {where}", mount, where, ctl, t.get("size")))
            dps = num(t.get("dps_total")) or 0
            if kind == "pdc":
                pdc_dps += dps
                pdc_n += 1
            elif t.get("is_pilot_slaveable"):
                # the pilot can slave this turret: it counts for the pilot, never twice
                slaved.append({"where": where, "dps": dps, "sustained": num(t.get("sustained_dps_total")) or 0})
            else:
                stations.append({"id": f"{skind}{idx + 1}", "label": f"{label}: {where}", "kind": skind, "dps": round(dps, 1),
                                 "sustained": r1(t.get("sustained_dps_total")), "crew": 1})
    merged = {}
    for mrow in mounts:
        key = (mrow["name"], mrow["location"], mrow["mount"])
        if key in merged:
            merged[key]["count"] += mrow["count"]
        else:
            merged[key] = mrow
    mounts = list(merged.values())
    if pdc_n:
        stations.append({"id": "pdc", "label": f"الدفاع النقطي PDC (×{pdc_n})", "kind": "pdc", "dps": round(pdc_dps, 1), "crew": 0, "auto": True})
    pilot_label = "الطيار"
    if slaved:
        pilot_dps += sum(x["dps"] for x in slaved)
        pilot_label = "الطيار (يربط " + "، ".join(x["where"] for x in slaved) + " بمقعده)"
        unverified.append(f"{TODO}: الطيار يحقق ضرره عبر برج قابل للربط is_pilot_slaveable ({', '.join(x['where'] for x in slaved)}). "
                          "اذكر أن مشغل البرج أو الطيار يستخدمه وليس الاثنان معًا، وتحقق من زاوية تغطيته.")
    stations.insert(0, {"id": "pilot", "label": pilot_label, "kind": "pilot", "dps": round(pilot_dps, 1), "crew": 1})

    ws = f.get("weaponry_summary") or {}
    if num(ws.get("pilot_dps")) and abs((num(ws.get("pilot_dps")) or 0) - pilot_dps) > 1:
        unverified.append(f"{TODO}: الويكي يعطي pilot_dps = {ws.get('pilot_dps')} بينما مجموع أسلحة الطيار المباشرة = {round(pilot_dps, 1)}. "
                          "تحقق من الأبراج التي يتحكم فيها الطيار (Erkul / SPViewer / صفحة الويكي) وعدّل محطة الطيار.")
    crew_only = round(sum(s["dps"] for s in stations if s["kind"] not in ("pilot", "pdc")), 1)

    # ---------------- ordnance
    ord_rows = {}
    for g in f.get("ordnance_loaded") or []:
        o = oi.get(g["uuid"], {})
        key = g["name"]
        if key not in ord_rows:
            sub = (o.get("sub_type") or g.get("type") or "").lower()
            kind = "torpedo" if "torpedo" in sub else "bomb" if "bomb" in sub else "missile"
            shops = o.get("shop_prices") or []
            sig = {"Infrared": "IR (حراري)", "Electromagnetic": "EM (كهرومغناطيسي)", "CrossSection": "CS (المقطع)"}.get(o.get("signal_type"), o.get("signal_type"))
            ord_rows[key] = {
                "kind": kind, "name": g["name"], "manufacturer": next((x["value"] for x in (o.get("description_data") or []) if x.get("name") == "Manufacturer"), g.get("manufacturer")),
                "size": g.get("size"), "launchers": 0, "per_launcher": None, "loaded": 0, "max": 0, "reserve": 0, "salvo": 1,
                "damage_each": o.get("damage_total"), "damage_type": "Physical (انفجاري)" if (o.get("damage_map") or {}).get("physical") else "Explosive",
                "guidance": sig, "range_m": o.get("lock_range_max_m"), "lock_time_s": o.get("lock_time_s"), "speed_mps": o.get("speed_mps"),
                "control": TODO + " — من يطلق (الطيار / مساعد الطيار / محطة التوربيدات)",
                "comes_with_ship": "unknown", "needs_purchase": TODO, "first_fill": TODO, "reload_in_combat": TODO,
                "unit_price_auec": shops[0]["price_auec"] if shops else None,
                "shop": (shops[0]["terminal"] + " — " + (shops[0].get("location") or "")) if shops else None,
                "tag": "community",
            }
        r = ord_rows[key]
        r["launchers"] += 1
        r["loaded"] += g["count"]
        r["max"] += g["count"]
        r["per_launcher"] = g["count"] if r["per_launcher"] in (None, g["count"]) else r["per_launcher"]
    ordnance = list(ord_rows.values())
    if ordnance:
        unverified.append(f"{TODO}: تأكيد أن السفينة تُسلَّم بالمقذوفات محمّلة (loaded = max) وعدد الرشقة salvo وجود مخزون احتياطي.")

    # ---------------- components
    comps = []
    for g in f.get("components") or []:
        if "PLACEHOLDER" in (g.get("name") or ""):
            continue
        comps.append({"type": TYPE_LABEL.get(g["type"], g["type"]), "name": g["name"], "manufacturer": g.get("manufacturer"),
                      "count": g["count"], "size": g.get("size"), "class": g.get("class"), "grade": g.get("grade"),
                      "perf": None, "swappable": None, "stock": True, "tag": "community"})
    shield_gens = [{"name": x["name"], "manufacturer": x["manufacturer"], "size": x["size"], "count": x["count"], "grade": x["grade"]}
                   for x in comps if x["type"] == "Shield Generator"]

    # ---------------- quantum
    q = f.get("quantum_drive") or {}
    stock = q.get("stock") or {}
    drives = []
    for a in [stock] + [x for x in q.get("same_size_alternatives") or [] if x.get("name") != stock.get("name")]:
        if not a or not a.get("fuel_rate_scu_per_gm"):
            continue
        price = (a.get("uex_prices") or [{}])[0].get("price_auec") if a.get("uex_prices") else None
        drives.append({"name": a["name"], "manufacturer": a.get("manufacturer"), "size": a.get("size"), "grade": a.get("grade"),
                       "class": a.get("class"), "speed_mps": a.get("speed_mps"), "spool_s": a.get("spool_s"),
                       "cooldown_s": a.get("cooldown_s"), "fuel_rate": a.get("fuel_rate_scu_per_gm"),
                       "accel1": a.get("accel_stage1"), "accel2": a.get("accel_stage2"), "stock": a is stock, "price_auec": price})
    qd = m.get("quantum") or {}
    fp = f.get("fuel_prices") or {}
    qt_price = (fp.get("quantum") or {}).get("avg")
    h2_price = (fp.get("hydrogen") or {}).get("avg")
    qcap = num(qd.get("quantum_fuel_capacity"))
    h2cap = num((m.get("hydrogen") or {}).get("capacity"))

    sp, ag = m.get("speed") or {}, m.get("agility") or {}
    dim = i.get("dimension_m") or {}
    crew = i.get("crew") or {}
    seat = i.get("seating") or {}
    beds_med = sum((seat.get("medical_beds") or {}).values()) if isinstance(seat.get("medical_beds"), dict) else None
    armor = d.get("armor") or {}

    # ---------------- pricing
    seen, pledge = set(), []
    for s in f["pledge"].get("skus") or []:
        if s.get("source") != "pledge_store":
            continue
        url = s.get("url") or ""
        kind = "package" if s.get("is_package") else "warbond" if s.get("is_warbond") else "ccu" if "/Upgrades/" in url else "standalone"
        label = {"package": "حزمة: " + s["title"], "warbond": "Warbond", "ccu": "هدف ترقية CCU", "standalone": "سفينة مستقلة Standalone"}[kind]
        if kind == "standalone" and s["title"] != i["name"]:
            label += " — " + s["title"]
        key = (label, s.get("price"))
        if key in seen or s.get("price") is None:
            continue
        seen.add(key)
        pledge.append({"label": label, "usd": s.get("discounted_price") or s["price"], "kind": kind, "available": bool(s.get("available")), "note": None})
    pledge.sort(key=lambda x: (not x["available"], x["kind"] != "standalone", x["usd"]))
    u = f.get("uex") or {}
    buy, rent = u.get("purchase") or [], u.get("rental") or []
    ingame = {"buy_auec": buy[0]["price_auec"] if buy else None,
              "available": True if buy else None,
              "where": [f"{b['terminal']} — {b.get('location') or ''} {('(' + b['system'] + ')') if b.get('system') else ''}".strip() for b in buy[:4]],
              "rent": [{"price_auec": r["price_auec"], "days": 1, "where": f"{r['terminal']} — {r.get('location') or ''}"} for r in rent[:3]],
              "version_note": f"بيانات UEX · {buy[0].get('game_version')}" if buy else None,
              "note": None if buy else f"{TODO}: UEX والويكي لا يعرضان سعر شراء داخل اللعبة؛ تحقق هل هي غير متاحة أم لم تُسجَّل، واكتب النتيجة."}
    ins = f.get("insurance") or {}
    running = []
    if qcap and qt_price:
        running.append({"k": "تعبئة خزان الكوانتم كاملًا", "auec": round(qcap * qt_price), "note": f"السعة {qcap:g} SCU × متوسط السعر {qt_price:,} aUEC لكل SCU"})
    if h2cap and h2_price:
        running.append({"k": "تعبئة خزان الهيدروجين كاملًا", "auec": round(h2cap * h2_price), "note": f"السعة {h2cap:g} SCU × متوسط السعر {h2_price:,} aUEC لكل SCU"})
    for o in ordnance:
        if o.get("unit_price_auec") and o.get("max"):
            running.append({"k": f"تعويض {o['name']} من الصفر", "auec": round(o["unit_price_auec"] * o["max"]), "note": f"سعر المتجر: {o['max']} × {o['unit_price_auec']:,} aUEC"})
    if ins.get("expedite_cost"):
        running.append({"k": "استدعاء سريع Expedite", "auec": ins.get("expedite_cost"), "note": "عند فقدان السفينة"})

    # ---------------- images
    cands = f.get("image_candidates") or []
    hero = (f.get("api_images") or [{}])[0].get("original_url") if f.get("api_images") else None
    hero_thumb = None
    for cnd in cands:
        if hero and cnd.get("original") and cnd["original"].split("?")[0] == hero.split("?")[0]:
            hero_thumb = cnd["url"]
    off = f.get("official") or {}
    rsi_imgs = off.get("images") or []
    if rsi_imgs:
        images = [{"url": rsi_imgs[0], "section": "hero", "caption": f"{TODO}: وصف الصورة الرسمية", "kind": "official"}]
    else:
        images = [{"url": hero_thumb or hero, "section": "hero", "caption": f"{TODO}: وصف الصورة", "kind": "official"}] if (hero_thumb or hero) else []

    total = round(pilot_dps + crew_only, 1)
    ship = {
        "id": i.get("slug"), "name": i["name"], "variant": i["name"], "manufacturer": i.get("manufacturer"),
        "manufacturer_code": i.get("manufacturer_code"), "status": STATUS.get(i.get("production_status"), i.get("production_status")),
        "role_ar": TODO, "role_en": i.get("role"), "career_en": i.get("career"), "size_en": (i.get("size") or "").title() or None,
        "tagline": TODO,
        "sections_tag": {"identity": "community", "weapons": "community", "dps": "community", "durability": "community",
                         "mobility": "community", "components": "community", "cargo": "community"},
        "hero_stats": [
            {"label": "Hull HP", "value": d.get("hull_hp")},
            {"label": "Shield HP", "value": d.get("shield_hp")},
            {"label": "ضرر الطيار وحده DPS", "value": round(pilot_dps)},
            {"label": "الطيار والطاقم DPS", "value": round(total)},
            {"label": "مدى الكوانتم", "value": r1((qd.get("quantum_range") or 0) / 1e9), "unit": "Gm", "decimals": 1},
            {"label": "الحمولة", "value": c.get("scu"), "unit": "SCU"},
        ],
        "images": images,
        "uses": {"primary": TODO, "secondary": [TODO], "best_for": [TODO], "excels": [TODO], "limited": [TODO],
                 "solo": [TODO], "crew_needed": [TODO], "strengths": [TODO], "weaknesses": [TODO], "limits": [TODO],
                 "ratings": [{"axis": a, "score": None, "why": TODO} for a in ("القتال", "الدفاع", "الشحن", "الاستكشاف", "اللعب الفردي", "العمل مع طاقم")]},
        "identity": {
            "rows": [
                {"k": "الاسم الكامل", "v": i.get("game_name"), "tag": "community"},
                {"k": "الشركة المصنعة", "v": f"{i.get('manufacturer')} ({i.get('manufacturer_code')})", "tag": "official"},
                {"k": "الفئة والدور", "v": f"{i.get('career')} · {i.get('role')}", "tag": "official"},
                {"k": "الحجم", "v": f"{(i.get('size') or '').title()} (Size {i.get('size_class')})"},
                {"k": "الأبعاد ط × ع × ر", "v": (f"{off.get('length')} × {off.get('beam')} × {off.get('height')} m" if off.get("length") else f"{dim.get('length')} × {dim.get('width')} × {dim.get('height')} m"), "tag": "official" if off.get("length") else "community"},
                {"k": "الحمولة الرسمية مقابل شبكة اللعبة", "v": (f"{off.get('cargocapacity')} SCU رسميًا · {c.get('scu')} SCU في شبكة الشحن داخل اللعبة" if off.get("cargocapacity") not in (None, c.get("scu")) else None)},
                {"k": "الكتلة", "v": f"{int(i.get('mass_kg') or 0):,} kg" if i.get("mass_kg") else None},
                {"k": "الطاقم الأدنى / الأقصى", "v": f"{crew.get('min')} / {crew.get('max')}"},
                {"k": "الحالة", "v": STATUS.get(i.get("production_status"), i.get("production_status")), "tag": "official"},
                {"k": "أُضيفت في إصدار", "v": (f["pledge"].get("curated") or {}).get("added_in_version")},
            ],
            "dims": {"length": dim.get("length"), "beam": dim.get("width"), "height": dim.get("height")},
            "mass_kg": i.get("mass_kg"),
            "crew": {"min": crew.get("min"), "max": crew.get("max"), "recommended": crew.get("min")},
            "playable": TODO + " — هل يمكن استخدامها فعليًا في LIVE؟",
            "notes": [],
        },
        "weapons": {"summary": TODO, "mounts": mounts, "ordnance": ordnance,
                    "countermeasures": [{"name": x["name"], "kind": "noise" if "noise" in (x["name"] or "").lower() else "decoy", "count": x["count"]} for x in d.get("countermeasures") or []],
                    "notes": []},
        "dps": {"stations": stations, "pilot_only": round(pilot_dps, 1), "crew_only": crew_only, "total": total,
                "crew_for_total": sum(1 for s in stations if s["kind"] not in ("pdc",) and s["dps"] > 0),
                "burst": total, "sustained": r1(sum(x["sustained"] for x in slaved) + sum((num(wi.get(g["uuid"], {}).get("dps_sustained_60s")) or 0) * g["count"] for g in pilot_rows) + sum(num(s.get("sustained")) or 0 for s in stations if s["kind"] not in ("pilot", "pdc"))),
                "distortion": None,
                "ordnance": [{"name": o["name"], "each": o["damage_each"], "salvo_damage": (o["damage_each"] or 0) * (o["salvo"] or 1), "total": (o["damage_each"] or 0) * (o["loaded"] or 0)} for o in ordnance],
                "formula": ["DPS = damage per shot × RPM ÷ 60 × weapon count", f"Total = pilot {round(pilot_dps, 1)} + crew {crew_only} = {total}"],
                "caveats": [TODO]},
        "durability": {
            "hull_hp": d.get("hull_hp"),
            "shield": {"hp": d.get("shield_hp"), "faces": d.get("shield_face_type"), "regen_per_s": d.get("shield_regen_per_s"),
                       "regen_time_s": d.get("shield_regen_time_s"), "generators": shield_gens},
            "armor": {"physical": armor.get("damage_physical"), "energy": armor.get("damage_energy"),
                      "distortion": armor.get("damage_distortion"), "thermal": armor.get("damage_thermal"),
                      "notes": f"صحة الدروع {armor.get('health'):,} HP؛ مضاعِف إشارات IR/EM/CS = {armor.get('signal_infrared')}" if armor.get("health") else None},
            "rows": [], "weak_points": [TODO], "defenses": [], "notes": [],
        },
        "mobility": {
            "speeds": {"scm": sp.get("scm"), "max": sp.get("max"), "boost_fwd": sp.get("boost_forward"), "boost_back": sp.get("boost_backward")},
            "accel": {"zero_to_scm_s": sp.get("zero_to_scm"), "zero_to_max_s": sp.get("zero_to_max"), "scm_to_zero_s": sp.get("scm_to_zero"), "max_to_zero_s": sp.get("max_to_zero")},
            "rotation": {"pitch": ag.get("pitch"), "yaw": ag.get("yaw"), "roll": ag.get("roll"), "pitch_boost": ag.get("pitch_boosted"), "yaw_boost": ag.get("yaw_boosted"), "roll_boost": ag.get("roll_boosted")},
            "fuel": {"hydrogen_scu": h2cap, "quantum_scu": qcap, "scoop": TODO, "refuel_others": TODO, "qt_price_auec": qt_price, "h2_price_auec": h2_price},
            "quantum": {"stock": stock.get("name"), "drives": drives, "range_gm": r1((qd.get("quantum_range") or 0) / 1e9), "routes": f.get("routes") or []},
            "rows": [], "notes": [],
        },
        "components": comps,
        "components_notes": [],
        "cargo": {
            "scu": c.get("scu"), "max_box": f"{(c.get('limits') or {}).get('max_scu_box')} SCU" if (c.get("limits") or {}).get("max_scu_box") else None,
            "rows": [
                {"k": "شبكات الشحن", "v": " + ".join(f"{g['scu']} SCU" for g in c.get("grids") or []) or None},
                {"k": "التخزين الشخصي", "v": f"{(num(c.get('personal_inventory_uscu')) or 0) / 1e6:g} SCU" if c.get("personal_inventory_uscu") else None},
                {"k": "حوامل الأسلحة", "v": f"{(c.get('weapon_storage') or {}).get('lockers')} خزائن · {(c.get('weapon_storage') or {}).get('slots_rifle')} بندقية · {(c.get('weapon_storage') or {}).get('slots_pistol')} مسدس" if c.get("weapon_storage") else None},
                {"k": "الأسرّة", "v": seat.get("beds")},
            ],
            "hangar": {"rows": [], "fits": []},
            "facilities": [],
            "medical": {"tier": i.get("max_medical_tier"), "beds": beds_med},
            "notes": [],
        },
        "pricing": {"pledge": pledge, "default_option": 0, "availability": TODO, "tax_note": None, "ingame": ingame, "running": running,
                    "insurance": {"claim_min": ins.get("claim_time"), "expedite_min": ins.get("expedite_time"), "expedite_auec": ins.get("expedite_cost")},
                    "loaners": f.get("loaners") or [], "notes": []},
        "opinions": {"praised": [TODO], "criticized": [TODO], "combat": TODO, "solo": TODO, "crew": TODO, "usability": TODO,
                     "bugs": [], "satisfaction": {"score": None, "label": "الرضا العام"}, "period": TODO, "notes": []},
        "rearm": {
            "delivery_qa": [{"q": q_, "a": "unknown", "note": TODO} for q_ in (
                "هل تأتي بجميع أسلحتها؟", "هل الأسلحة مركبة وجاهزة؟", "هل تأتي الصواريخ؟", "هل تأتي التوربيدات؟", "هل تأتي القنابل؟",
                "هل الذخيرة الباليستية ممتلئة عند الاستلام؟", "هل القواذف موجودة والمقذوفات غائبة؟", "هل أحتاج شراء الصواريخ أو التوربيدات منفصلة؟",
                "هل تصلح للقتال فور الاستلام؟", "هل يوجد مخزون احتياطي؟")],
            "delivery_table": [{"name": o["name"], "size": o["size"], "included": o["max"], "loaded": o["loaded"], "max": o["max"], "reserve": o["reserve"], "to_buy": 0} for o in ordnance],
            "cases": [{"case": x, "result": TODO} for x in ("الاستلام الأول بعد الشراء من RSI", "الاستلام الأول بعد الشراء داخل اللعبة", "الاستدعاء بعد الفقدان عبر التأمين Claim", "إعادة التعبئة بعد الاستخدام", "تركيب أسلحة أو صواريخ مختلفة عن التجهيز الأصلي")],
            "check_steps": [TODO],
            "auto": {"best": [TODO], "steps": [TODO], "notes": []},
            "purchase": {"items": [{"name": o["name"], "size": o["size"], "type": o["kind"], "unit_auec": o["unit_price_auec"], "qty": o["max"], "shop": (o.get("shop") or "").split(" — ")[0] or None, "location": (o.get("shop") or " — ").split(" — ")[-1] or None} for o in ordnance],
                         "steps": [TODO], "diff": [{"k": "شراء السلاح", "v": TODO}, {"k": "شراء الذخيرة", "v": TODO}, {"k": "تركيب المقذوف", "v": TODO}, {"k": "تعبئة السلاح", "v": TODO}]},
            "install_steps": [TODO],
            "manual": {"supported": "unknown", "steps": [], "notes": [TODO]},
            "final_table": [{"weapon": w["name"], "comes": "yes", "buy": "no", "refill": "yes" if (w.get("ammo") or {}).get("needs_refill") else "no",
                             "max": str((w.get("ammo") or {}).get("capacity") or "—"), "method": TODO, "cost": TODO} for w in mounts]
                           + [{"weapon": o["name"], "comes": "unknown", "buy": "unknown", "refill": "yes", "max": str(o["max"]), "method": TODO, "cost": f"{o['unit_price_auec']:,} aUEC للقطعة" if o.get("unit_price_auec") else TODO} for o in ordnance],
            "troubleshooting": [{"problem": TODO, "fix": TODO}],
            "best_way": [{"q": q_, "a": TODO} for q_ in ("أفضل طريقة للتعبئة؟", "أسرع طريقة؟", "الأقل تكلفة؟", "هل أشتري الذخيرة مسبقًا؟", "هل يكفي Rearm؟", "هل أستطيع وحدي؟", "هل هي جاهزة للقتال مباشرة بعد الشراء؟", "ما أول شيء أفعله؟")],
        },
        "summary": {"best_uses": [TODO], "pros": [TODO], "cons": [TODO], "for_whom": TODO, "readiness": TODO, "extras": [TODO], "key_costs": [TODO], "verdict": TODO, "score": None},
        "unverified": unverified,
        "_image_candidates": [{"hint": "RSI official " + str(n + 1), "url": u, "size": "store"} for n, u in enumerate(rsi_imgs)]
                             + [{"hint": x["hint"], "url": x["url"], "size": f"{x['width']}x{x['height']}"} for x in cands],
        "_facts_notes": [f"wiki pilot_dps={ws.get('pilot_dps')} turret_dps={ws.get('turret_dps')} (turret_dps includes PDC in the wiki)",
                         "loaded/max for ordnance are equal by default: verify",
                         "remove TODO strings or the build fails"],
    }
    data = {
        "meta": {"schema": "marsad-ships/2", "game_version": gv, "build": build, "verified_on": today,
                 "fx_qar_per_usd": 3.64, "gallery_url": i.get("pledge_url"), "gallery_label": "افتح المعرض الرسمي للسفينة",
                 "show_sources": False,
                 "sources": [{"label": "Star Citizen Wiki API", "url": f["sources"].get("wiki_api")}, {"label": "Star Citizen Wiki", "url": f["sources"].get("wiki_page")}, {"label": "UEX", "url": "https://uexcorp.space"}]},
        "ships": [ship],
    }
    return data


def mount_row(w, count, station, mount, location, ctl, mount_size=None):
    cap = num(w.get("ammo_capacity"))
    kind = ammo_kind(w)
    needs = bool(cap and cap > 0)
    return {
        "name": w.get("name"), "manufacturer": w.get("manufacturer"), "category": w.get("weapon_type"),
        "damage_type": dmg_kind(w), "count": count, "size": w.get("size"), "mount_size": mount_size, "location": location,
        "mount": mount, "station": station, "stock": True, "sold_separately": None, "swappable": None, "bespoke": None,
        "control": ctl, "alpha": r1(w.get("damage_per_shot")), "rpm": w.get("rpm"), "dps_each": r1(w.get("dps_burst")),
        "range_m": w.get("range_m"), "speed_mps": w.get("projectile_speed"),
        "ammo": {"needs_refill": needs, "capacity": cap if needs else None, "kind": "ballistic" if needs else kind,
                 "refill": TODO if needs else "لا يحتاج ذخيرة: يُشحن من طاقة السفينة (المكثف يتجدد تلقائيًا).",
                 "cost_auec": None},
        "capacitor": None, "regen": None, "tag": "community",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("facts")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    with open(a.facts, encoding="utf-8") as fh:
        f = json.load(fh)
    data = make(f, a.date)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    s = json.dumps(data, ensure_ascii=False)
    print(f"draft -> {a.out} | TODO remaining: {s.count(TODO)} | mounts {len(data['ships'][0]['weapons']['mounts'])} | ordnance {len(data['ships'][0]['weapons']['ordnance'])} | stations {len(data['ships'][0]['dps']['stations'])} | routes {len(data['ships'][0]['mobility']['quantum']['routes'])}")


if __name__ == "__main__":
    main()
