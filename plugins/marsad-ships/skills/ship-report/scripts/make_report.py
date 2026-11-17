#!/usr/bin/env python3
"""Turn sc_data.py facts into the report data file (schema marsad-ships/3).

  python3 make_report.py work/<ship>-facts.json --out work/<ship>.json

Everything that can be computed is computed here: default loadout with
"comes loaded / needs refill / how / cost", solo vs crew vs total damage,
weapons, ordnance, rearm cost breakdown, cost-calculator inputs, upgrade slots
with ranked options, prices (standard vs warbond), specs, patch watch.
Only the narrative needs a human pass: every such field starts with "TODO".
build_report.py refuses to build while a TODO remains. Keys starting with "_"
are notes for the writer and are dropped from the page.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from statistics import median

TODO = "TODO"
FX = 3.64

# Game rules that hold for Alpha 4.8 -> 4.10.3 (official patch notes). Re-check
# them against facts["patches"]["system_changes"] on every report.
RULES = {
    "since": "4.8",
    "energy": "سلاح طاقة: لا يحتاج ذخيرة، يشحن تلقائيًا من مكثف أسلحة السفينة.",
    "ballistic": "ذخيرة باليستية: تُملأ بخدمة Restock في المدن والمحطات، أو في حظيرة سفينة مضيفة.",
    "ordnance": "مقذوفات: تُعوَّض بخدمة Restock، أو تُشترى من متجر أسلحة السفن وتُركَّب.",
    "first_delivery": "التسليم الأول يأتي بالتجهيز الافتراضي للمصنع كما في بيانات اللعبة.",
    "after_claim": "منذ 4.8: الذخيرة والصواريخ والتوربيدات لا تعود مع الاستدعاء بالتأمين؛ نفّذ Restock بعد كل استدعاء.",
    "snapshot": "لقطة التجهيز في ASOP تحفظ الأسلحة والمكونات ولا تحفظ الذخيرة والصواريخ.",
}
STATUS = {"flight-ready": "Flight Ready", "in-concept": "Concept", "in-production": "In Production"}
COMP_LABEL = {"PowerPlant": "Power Plant", "Cooler": "Cooler", "Shield": "Shield Generator", "QuantumDrive": "Quantum Drive",
              "JumpDrive": "Jump Drive", "Radar": "Radar", "LifeSupportGenerator": "Life Support", "FuelTank": "Hydrogen Tank",
              "QuantumFuelTank": "Quantum Tank", "TractorBeam": "Tractor Beam", "SelfDestruct": "Self Destruct",
              "WeaponMining": "Mining Laser", "SalvageHead": "Salvage Head", "QuantumInterdictionGenerator": "Quantum Interdiction"}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def r(v, n=1):
    v = num(v)
    return None if v is None else round(v, n)


def human(cls):
    if not cls:
        return None
    s = re.sub(r"^[A-Z]{3,4}_[A-Za-z0-9]+?_", "", cls).replace("SCItem_", "").replace("_", " ").strip()
    rep = {"Turret Side Right": "البرج الجانبي الأيمن", "Turret Side Left": "البرج الجانبي الأيسر", "Turret Top Right": "البرج العلوي الأيمن",
           "Turret Top Left": "البرج العلوي الأيسر", "Turret Front": "البرج الأمامي", "Turret Rear": "البرج الخلفي",
           "Remote Turret RearBottom": "البرج الخلفي السفلي (عن بُعد)", "Remote Turret RearTop": "البرج الخلفي العلوي (عن بُعد)",
           "Turret Top": "البرج العلوي", "Turret Bottom": "البرج السفلي", "Turret Nose": "برج المقدمة"}
    if "PDC" in s:
        return "أبراج الدفاع النقطي (آلية)"
    return rep.get(s, s)


def version_label(v):
    m = re.match(r"(\d+\.\d+(?:\.\d+)?)-([A-Z]+)\.?(\d+)?", v or "")
    return (f"Alpha {m.group(1)} {m.group(2)}", m.group(3)) if m else (v, None)


def make(f, today):
    i, d, m = f["identity"], f["durability"], f["mobility"]
    off = f.get("official") or {}
    wi, oi = f.get("weapon_items") or {}, f.get("ordnance_items") or {}
    gv, build = version_label(f.get("game_version"))
    patches = f.get("patches") or {}
    live = patches.get("latest_live") or {}
    unverified, checks = [], []
    sc = f.get("service_commodities") or {}
    fuel = f.get("fuel_prices") or {}

    # ------------------------------------------------ stations (turrets) and damage split
    turrets = f.get("turrets") or {}
    # a gun is crew-operated only when it sits in a turret the game lists as manned/remote/pdc;
    # gimbal mounts on fighters look like turrets in the port tree but belong to the pilot
    turret_hps = {t.get("hardpoint") for rows in turrets.values() for t in rows}
    stations, station_of = [], {}
    pilot = {"id": "pilot", "label": "الطيار", "kind": "pilot", "dps": 0.0, "sustained": 0.0, "crew": 1, "parts": []}
    for g in f.get("guns") or []:
        if g["root_port"] not in turret_hps:
            w = wi.get(g["uuid"], {})
            pilot["dps"] += (num(w.get("dps")) or 0) * g["count"]
            pilot["sustained"] += (num(w.get("sustained")) or 0) * g["count"]
            pilot["parts"].append(f"{g['count']}× {g['name']}")
            station_of[g["root_port"]] = "pilot"
    pdc = {"id": "pdc", "label": "الدفاع النقطي PDC", "kind": "pdc", "dps": 0.0, "sustained": 0.0, "crew": 0, "auto": True, "count": 0}
    n = 0
    for kind, rows in turrets.items():
        for t in rows:
            dps = num(t.get("dps")) or 0
            if not dps:
                continue
            where = human(t.get("class_name")) or t.get("hardpoint")
            if kind == "pdc":
                pdc["dps"] += dps
                pdc["sustained"] += num(t.get("sustained")) or 0
                pdc["count"] += 1
                station_of[t.get("hardpoint")] = "pdc"
            elif t.get("pilot_slaveable"):
                pilot["dps"] += dps
                pilot["sustained"] += num(t.get("sustained")) or 0
                pilot["parts"].append(f"{where} (يربطه الطيار بمقعده)")
                station_of[t.get("hardpoint")] = "pilot"
            else:
                n += 1
                sid = f"st{n}"
                stations.append({"id": sid, "label": where, "kind": "remote" if kind == "remote" else "turret",
                                 "dps": round(dps, 1), "sustained": r(t.get("sustained")), "crew": 1,
                                 "weapons": f"{len(t.get('weapons') or [])}× {(t.get('weapons') or ['?'])[0]}"})
                station_of[t.get("hardpoint")] = sid
    pilot["dps"], pilot["sustained"] = round(pilot["dps"], 1), round(pilot["sustained"], 1)
    pilot["label"] = "الطيار" + (f" — {'، '.join(pilot['parts'])}" if pilot["parts"] else " (لا أسلحة يتحكم فيها)")
    crew_dps = round(sum(s["dps"] for s in stations), 1)
    crew_sus = round(sum(s["sustained"] or 0 for s in stations), 1)
    all_stations = [pilot] + stations + ([{**pdc, "dps": round(pdc["dps"], 1), "sustained": round(pdc["sustained"], 1),
                                           "label": f"الدفاع النقطي PDC (×{pdc['count']}، آلي)"}] if pdc["count"] else [])
    ws = f.get("weaponry_summary") or {}
    if num(ws.get("pilot_dps")) is not None and abs((num(ws.get("pilot_dps")) or 0) - pilot["dps"]) > 1:
        checks.append(f"ضرر الطيار المحسوب {pilot['dps']} يختلف عن pilot_dps في الويكي {ws.get('pilot_dps')}؛ راجع ربط الأبراج بالطيار.")

    # ------------------------------------------------ weapons (grouped by name + location)
    weapons = {}
    for g in f.get("guns") or []:
        w = wi.get(g["uuid"], {})
        loc_turret = next((t for rows in turrets.values() for t in rows if t.get("hardpoint") == g["root_port"]), None)
        loc = human(loc_turret.get("class_name")) if loc_turret else ("الطيار (ثابت)" if g["root_port"] not in turret_hps else g["root_port"])
        st = station_of.get(g["root_port"], "pilot" if g["root_port"] not in turret_hps else None)
        key = (g["name"], loc)
        ammo = num(w.get("ammo")) or 0
        if key not in weapons:
            weapons[key] = {
                "name": g["name"], "manufacturer": w.get("manufacturer"), "type": w.get("weapon_type"),
                "damage_kind": w.get("damage_kind"), "size": g["size"], "count": 0, "location": loc, "station": st,
                "alpha": r(w.get("alpha")), "rpm": w.get("rpm"), "dps_each": r(w.get("dps")), "sustained_each": r(w.get("sustained")),
                "range_m": w.get("range_m"), "speed_mps": w.get("speed_mps"), "ammo": int(ammo) if ammo else 0,
                "needs_refill": ammo > 0, "refill": RULES["ballistic"] if ammo > 0 else RULES["energy"],
                "ammo_commodity": f"Ship Ammunition - Size {g['size']}" if ammo > 0 else None,
                "ammo_price_per_scu": (sc.get("ammo_per_scu") or {}).get(str(g["size"])) if ammo > 0 else None,
                "price_auec": w.get("price_auec"), "buy_where": w.get("buy_where"),
                "swappable": bool(g["editable"]), "bespoke": not g["editable"] or not w.get("price_auec"),
                "time_to_empty_s": round(ammo / (num(w.get("rpm")) / 60), 0) if ammo and num(w.get("rpm")) else None,
            }
        weapons[key]["count"] += g["count"]
    weapons = list(weapons.values())

    # ------------------------------------------------ ordnance
    ords = {}
    for g in f.get("ordnance") or []:
        o = oi.get(g["uuid"], {})
        if g["name"] not in ords:
            sub = (o.get("sub_type") or g.get("type") or "").lower()
            ords[g["name"]] = {
                "kind": "torpedo" if "torpedo" in sub else "bomb" if "bomb" in sub else "missile", "name": g["name"],
                "manufacturer": o.get("manufacturer"), "size": g["size"], "launchers": 0, "per_launcher": g["count"],
                "loaded": 0, "max": 0, "damage_each": o.get("damage"),
                "guidance": {"Infrared": "IR حراري", "Electromagnetic": "EM كهرومغناطيسي", "CrossSection": "CS مقطع عرضي"}.get(o.get("signal"), o.get("signal")),
                "lock_range_m": o.get("lock_range_m"), "speed_mps": o.get("speed_mps"), "salvo": 1,
                "control": TODO + ": من يطلقه (الطيار / مساعد الطيار / محطة)", "unit_price_auec": o.get("price_auec"),
                "buy_where": o.get("buy_where"), "swappable": bool(g["editable"]),
            }
        x = ords[g["name"]]
        x["launchers"] += 1
        x["loaded"] += g["count"]
        x["max"] += g["count"]
    ordnance = list(ords.values())
    for o in ordnance:
        o["full_refill_auec"] = round((o["unit_price_auec"] or 0) * o["max"]) if o["unit_price_auec"] else None
    if ordnance:
        checks.append("عدد الرشقة salvo لكل مقذوف افتراضيًا 1؛ عدّله إن كانت السفينة تطلق أكثر من مقذوف دفعة واحدة.")

    # ------------------------------------------------ default loadout at purchase
    loadout = []
    for w in weapons:
        loadout.append({"group": "weapon", "name": w["name"], "detail": f"{w['location']} · {w['type'] or ''} · S{w['size']}",
                        "count": w["count"], "installed": "yes", "loaded": "yes" if w["needs_refill"] else "na",
                        "needs_refill": "yes" if w["needs_refill"] else "no", "refill": w["refill"],
                        "unit_price_auec": w["price_auec"], "refill_cost": "حسب SCU الذخيرة" if w["needs_refill"] else "لا شيء"})
    for o in ordnance:
        loadout.append({"group": o["kind"], "name": o["name"], "detail": f"{o['launchers']} قاذف × {o['per_launcher']} · S{o['size']}",
                        "count": o["max"], "installed": "yes", "loaded": "partial", "needs_refill": "yes", "refill": RULES["ordnance"],
                        "unit_price_auec": o["unit_price_auec"], "refill_cost": o["full_refill_auec"]})
    for cm in f.get("countermeasures") or []:
        loadout.append({"group": "countermeasure", "name": cm["name"], "detail": f"إجراء مضاد · S{cm['size']}", "count": cm["count"],
                        "installed": "yes", "loaded": "partial", "needs_refill": "yes", "refill": "Restock من خدمات الهبوط.",
                        "unit_price_auec": None, "refill_cost": "حسب SCU"})
    components = []
    for c in f.get("components") or []:
        if "PLACEHOLDER" in (c["name"] or ""):
            continue
        components.append({"type": COMP_LABEL.get(c["type"], c["type"]), "name": c["name"] if not (c["name"] or "").startswith("radr_") else f"Radar S{c['size']}",
                           "manufacturer": c["manufacturer"], "count": c["count"], "size": c["size"], "grade": c["grade"],
                           "class": c["class"], "swappable": bool(c["editable"])})
        loadout.append({"group": "component", "name": components[-1]["name"], "detail": f"مكوّن {components[-1]['type']} · S{c['size']} {c['grade'] or ''}",
                        "count": c["count"], "installed": "yes", "loaded": "na", "needs_refill": "no", "refill": "—",
                        "unit_price_auec": None, "refill_cost": "—"})
    has_ammo = any(w["needs_refill"] for w in weapons)
    delivery = [
        {"q": "هل تأتي بكل أسلحتها مركبة؟", "a": "yes", "note": "نعم، بالتجهيز الافتراضي للمصنع (الجدول أعلاه)."},
        {"q": "هل أسلحة الطاقة جاهزة فورًا؟", "a": "yes" if any(not w["needs_refill"] for w in weapons) else "na", "note": "تشحن من مكثف السفينة، لا تحتاج تعبئة."},
        {"q": "هل الذخيرة الباليستية ممتلئة؟", "a": "partial" if has_ammo else "na", "note": "ممتلئة في التسليم الأول، ولا تعود مع الاستدعاء بالتأمين." if has_ammo else "لا توجد أسلحة باليستية."},
        {"q": "هل تأتي الصواريخ والتوربيدات معبأة؟", "a": "partial" if ordnance else "na", "note": ("محمّلة في التجهيز الافتراضي (التسليم الأول)، ولا تعود بعد الاستدعاء بالتأمين." if ordnance else "لا تحمل مقذوفات.")},
        {"q": "هل أحتاج أشتري مقذوفات قبل أول قتال؟", "a": "no" if ordnance else "na", "note": "لا في التسليم الأول عادة؛ افحص العدادات. نعم بعد الاستخدام أو بعد كل استدعاء."},
        {"q": "هل يوجد مخزون احتياطي؟", "a": TODO, "note": TODO + ": هل للسفينة مخزن احتياطي أو تحميل يدوي من الشحن؟"},
    ]
    checks.append("أجوبة التسليم مبنية على قواعد 4.8–4.10.3؛ راجع patch_watch للتأكد أن شيئًا لم يتغير.")

    # ------------------------------------------------ upgrades
    cat = f.get("upgrade_catalogs") or {}
    slots = []
    for g in f.get("guns") or []:
        if not g["editable"]:
            continue
        size = str(g["port_size"] or g["size"])
        st = station_of.get(g["root_port"], "pilot" if g["root_port"] not in turret_hps else None)
        loc_turret = next((t for rows in turrets.values() for t in rows if t.get("hardpoint") == g["root_port"]), None)
        loc = human(loc_turret.get("class_name")) if loc_turret else ("الطيار (ثابت)" if g["root_port"] not in turret_hps else g["root_port"])
        key = f"{loc}|{size}|{g['name']}"
        slot = next((s for s in slots if s["key"] == key), None)
        if slot:
            slot["count"] += g["count"]
            continue
        stock = wi.get(g["uuid"], {})
        opts = []
        for o in cat.get("guns", {}).get(size, []):
            opts.append({"name": o["name"], "type": o["weapon_type"], "damage_kind": o["damage_kind"], "dps": r(o["dps"]),
                         "sustained": r(o["sustained"]), "range_m": o["range_m"], "ammo": int(o["ammo"] or 0),
                         "price_auec": o["price_auec"], "buy_where": o["buy_where"]})
        if not any(o["name"] == stock.get("name") for o in opts):
            opts.append({"name": stock.get("name"), "type": stock.get("weapon_type"), "damage_kind": stock.get("damage_kind"),
                         "dps": r(stock.get("dps")), "sustained": r(stock.get("sustained")), "range_m": stock.get("range_m"),
                         "ammo": int(stock.get("ammo") or 0), "price_auec": stock.get("price_auec"), "buy_where": stock.get("buy_where")})
        sdps = num(stock.get("dps")) or 0
        better = [o for o in opts if (o["dps"] or 0) > sdps and o["price_auec"]]
        tags = {}
        if better:
            tags[max(better, key=lambda o: o["dps"])["name"]] = "الأقوى"
            bv = max(better, key=lambda o: (o["dps"] - sdps) / o["price_auec"])
            tags.setdefault(bv["name"], "الأوفر")
            bal = [o for o in better if o["damage_kind"] == "Ballistic"]
            if bal:
                tags.setdefault(max(bal, key=lambda o: o["dps"])["name"], "أقوى باليستي")
        for o in opts:
            o["tag"] = tags.get(o["name"])
        slots.append({"key": key, "label": f"{loc} — S{size}", "station": st, "size": int(size), "count": g["count"],
                      "stock": stock.get("name"), "stock_dps": r(sdps), "options": sorted(opts, key=lambda o: -(o["dps"] or 0))})
    ord_opts = []
    for o in ordnance:
        if not o["swappable"]:
            continue
        rows = [x for x in cat.get("ordnance", {}).get(str(o["size"]), []) if "Ground" not in (x.get("sub_type") or "")]
        if o["kind"] == "torpedo":
            rows = [x for x in rows if (x.get("sub_type") or "").lower() == "torpedo"]
        elif o["kind"] == "missile":
            rows = [x for x in rows if (x.get("sub_type") or "").lower() == "missile"]
        dm = median([x["damage"] for x in rows]) if rows else 0
        opts = [{"name": x["name"], "damage": x["damage"], "guidance": x.get("signal"), "price_auec": x["price_auec"],
                 "buy_where": x["buy_where"], "suspect": bool(dm and x["damage"] > 5 * dm)} for x in rows]
        if any(x["suspect"] for x in opts):
            checks.append(f"خيار مقذوف بضرر غير منطقي لحجم S{o['size']} (موسوم suspect)؛ تحقق منه أو احذفه.")
        ord_opts.append({"for": o["name"], "kind": o["kind"], "size": o["size"], "count": o["max"],
                         "stock_damage": o["damage_each"], "stock_price": o["unit_price_auec"], "options": opts})
    comp_opts = []
    for k, rows in (cat.get("components") or {}).items():
        t, s = k.split(":")
        stock = next((c for c in components if c["type"] == COMP_LABEL.get(t, t) and str(c["size"]) == s), None)
        comp_opts.append({"type": COMP_LABEL.get(t, t), "size": int(s), "stock": stock["name"] if stock else None,
                          "options": [{"name": x["name"], "grade": x["grade"], "class": x["class"], "stat": x["stat"],
                                       "price_auec": x["price_auec"], "buy_where": x["buy_where"]} for x in rows]})

    # ------------------------------------------------ quantum
    q = m.get("quantum") or {}
    qd = f.get("quantum_drive") or {}
    stock_qd = qd.get("stock") or {}
    drives = []
    for a in [stock_qd] + [x for x in qd.get("alternatives") or [] if x.get("name") != stock_qd.get("name")]:
        if a and a.get("fuel_rate"):
            drives.append({**{k: a.get(k) for k in ("name", "manufacturer", "size", "grade", "class", "speed_mps", "spool_s",
                                                    "cooldown_s", "fuel_rate", "accel1", "accel2", "price_auec", "buy_where")},
                           "stock": a is stock_qd})
    qcap, h2cap = num(q.get("quantum_fuel_capacity")), num((m.get("hydrogen") or {}).get("capacity"))
    qprice, h2price = (fuel.get("quantum") or {}), (fuel.get("hydrogen") or {})

    # ------------------------------------------------ prices
    skus = [s for s in f["pledge"].get("skus") or [] if s.get("source") == "pledge_store" and s.get("price")]
    std = [s for s in skus if not s.get("is_warbond") and not s.get("is_package")]
    wb = [s for s in skus if s.get("is_warbond") and not s.get("is_package")]
    pk = [s for s in skus if s.get("is_package")]
    def best(rows):
        av = [s for s in rows if s.get("available")]
        return (min(av, key=lambda s: s["price"]) if av else (max(rows, key=lambda s: s.get("imported_at") or "") if rows else None))
    pledge = []
    s1, s2 = best(std), best(wb)
    if s1:
        pledge.append({"label": "عادي Standard", "kind": "standard", "usd": s1.get("discounted_price") or s1["price"], "available": bool(s1.get("available")),
                       "note": "معروض في متجر RSI الآن" if s1.get("available") else "غير معروض الآن"})
    elif f["pledge"].get("msrp_usd"):
        pledge.append({"label": "عادي Standard", "kind": "standard", "usd": f["pledge"]["msrp_usd"], "available": None, "note": "سعر القائمة MSRP"})
    if s2:
        pledge.append({"label": "Warbond", "kind": "warbond", "usd": s2.get("discounted_price") or s2["price"], "available": bool(s2.get("available")),
                       "note": "معروض الآن" if s2.get("available") else "يظهر في العروض فقط"})
    else:
        pledge.append({"label": "Warbond", "kind": "warbond", "usd": None, "available": False, "note": "لا يوجد عرض Warbond مسجل لهذه السفينة"})
    for s in pk[:2]:
        pledge.append({"label": f"حزمة: {s['title']}", "kind": "package", "usd": s["price"], "available": bool(s.get("available")), "note": None})
    orig = f["pledge"].get("original") or {}
    history = [x for x in ({"label": "السعر الأصلي عند الطرح", "usd": orig.get("original_pledge_price")},
                           {"label": "Warbond الأصلي عند الطرح", "usd": orig.get("original_warbond_price")}) if x["usd"]]
    u = f.get("uex") or {}
    buy, rent = u.get("buy") or [], u.get("rent") or []
    ingame = {"buy_auec": buy[0]["price_auec"] if buy else None, "available": True if buy else None,
              "where": [f"{b['terminal']}" + (f" — {b['location']}" if b.get("location") else "") for b in buy[:4]],
              "rent": [{"price_auec": x["price_auec"], "days": 1, "where": x["terminal"]} for x in rent[:4]],
              "note": None if buy else TODO + ": لا يوجد سعر aUEC في UEX؛ اكتب هل هي غير متاحة للشراء داخل اللعبة أم لم يُسجَّل سعرها."}

    # ------------------------------------------------ rearm costs and calculator inputs
    rearm_costs = []
    for o in ordnance:
        if o["unit_price_auec"]:
            rearm_costs.append({"item": o["name"], "qty": o["max"], "unit": "قطعة", "unit_price_auec": o["unit_price_auec"],
                                "total_auec": o["full_refill_auec"], "note": f"أرخص متجر: {o['buy_where']}"})
    for w in weapons:
        if w["needs_refill"] and w["ammo_price_per_scu"]:
            rearm_costs.append({"item": f"ذخيرة {w['name']} (Ship Ammunition S{w['size']})", "qty": None, "unit": "SCU",
                                "unit_price_auec": w["ammo_price_per_scu"], "total_auec": None, "note": f"{w['ammo']:,} طلقة لكل سلاح؛ الكمية بالـSCU تظهر في شاشة Restock"})
    if sc.get("decoy_per_scu"):
        rearm_costs.append({"item": "Decoy / Flares", "qty": None, "unit": "SCU", "unit_price_auec": sc["decoy_per_scu"], "total_auec": None, "note": "سعر مادة الخدمة"})
    if sc.get("noise_per_scu"):
        rearm_costs.append({"item": "Noise / Chaff", "qty": None, "unit": "SCU", "unit_price_auec": sc["noise_per_scu"], "total_auec": None, "note": "سعر مادة الخدمة"})
    weapon_value = sum((w["price_auec"] or 0) * w["count"] for w in weapons)

    calc = {
        "ordnance": [{"name": o["name"], "max": o["max"], "unit_price_auec": o["unit_price_auec"]} for o in ordnance if o["unit_price_auec"]],
        "ammo": [{"name": w["name"], "size": w["size"], "price_per_scu": w["ammo_price_per_scu"]} for w in weapons if w["needs_refill"] and w["ammo_price_per_scu"]],
        "cm": {"decoy_per_scu": sc.get("decoy_per_scu"), "noise_per_scu": sc.get("noise_per_scu")},
        "rmc_per_scu": sc.get("rmc_per_scu"),
        "fuel": {"qt_capacity": qcap, "qt_avg": qprice.get("avg"), "qt_min": qprice.get("min"),
                 "h2_capacity": h2cap, "h2_avg": h2price.get("avg"), "h2_min": h2price.get("min"),
                 "qt_cheapest": qprice.get("cheapest"), "h2_cheapest": h2price.get("cheapest")},
        "insurance": {"claim_min": r((f.get("insurance") or {}).get("claim_time")), "expedite_min": r((f.get("insurance") or {}).get("expedite_time")),
                      "expedite_auec": (f.get("insurance") or {}).get("expedite_cost")},
        "weapons": [{"name": w["name"], "count": w["count"], "price_auec": w["price_auec"]} for w in weapons if w["price_auec"]],
        "presets": [
            {"id": "mission", "label": "مهمة قتالية واحدة", "rearms": 1, "trips": 2, "h2": 1, "claims": 0, "ammo_scu": 1, "cm_scu": 0},
            {"id": "week", "label": "أسبوع لعب", "rearms": 4, "trips": 12, "h2": 3, "claims": 1, "ammo_scu": 4, "cm_scu": 1},
            {"id": "month", "label": "شهر لعب", "rearms": 15, "trips": 45, "h2": 10, "claims": 3, "ammo_scu": 15, "cm_scu": 3},
        ],
    }

    # ------------------------------------------------ specs
    dim = i.get("dimension_m") or {}
    crew = i.get("crew") or {}
    seat = i.get("seating") or {}
    armor = d.get("armor") or {}
    sp, ag = m.get("speed") or {}, m.get("agility") or {}
    med_beds = sum((seat.get("medical_beds") or {}).values()) if isinstance(seat.get("medical_beds"), dict) else None
    specs = [
        {"k": "الشركة المصنعة", "v": f"{i.get('manufacturer')} ({i.get('manufacturer_code')})", "src": "official"},
        {"k": "الفئة والدور", "v": f"{i.get('career')} · {i.get('role')}", "src": "official"},
        {"k": "الحجم", "v": f"{(i.get('size') or '').title()} (Size {i.get('size_class')})", "src": "game"},
        {"k": "الأبعاد ط × ع × ر", "v": (f"{off.get('length')} × {off.get('beam')} × {off.get('height')} m" if off.get("length") else f"{dim.get('length')} × {dim.get('width')} × {dim.get('height')} m"), "src": "official" if off.get("length") else "game"},
        {"k": "الكتلة", "v": f"{int(i.get('mass_kg') or 0):,} kg" if i.get("mass_kg") else None, "src": "game"},
        {"k": "الطاقم الرسمي", "v": f"{off.get('min_crew', crew.get('min'))} – {off.get('max_crew', crew.get('max'))}", "src": "official"},
        {"k": "الحمولة", "v": f"{f['cargo'].get('scu')} SCU في شبكة اللعبة" + (f" · {off.get('cargocapacity')} SCU رسميًا" if off.get("cargocapacity") not in (None, f["cargo"].get("scu")) else ""), "src": "game"},
        {"k": "الحالة", "v": STATUS.get(i.get("status"), i.get("status")) + (f" — أُضيفت في {i.get('added_in')}" if i.get("added_in") else ""), "src": "official"},
        {"k": "المستشفى", "v": f"{i.get('max_medical_tier')} · {med_beds} أسرّة" if i.get("max_medical_tier") else None, "src": "game"},
        {"k": "الأسرّة", "v": seat.get("beds"), "src": "game"},
    ]
    specs = [x for x in specs if x["v"] not in (None, "", "None")]

    images = []
    rsi_imgs = (off.get("images") or [])
    if rsi_imgs:
        images.append({"url": rsi_imgs[0], "section": "hero", "caption": f"{i['name']} — صورة RSI الرسمية", "kind": "official"})

    pw = [{"version": x["version"], "date": x["date"], "upcoming": x.get("upcoming"), "text": x["text"]} for x in patches.get("ship_mentions") or []]
    sysch = [{"version": x["version"], "text": x["text"]} for x in patches.get("system_changes") or []]

    ship = {
        "id": i.get("slug"), "name": i["name"], "variant": i["name"], "manufacturer": i.get("manufacturer"),
        "manufacturer_code": i.get("manufacturer_code"), "status": STATUS.get(i.get("status"), i.get("status")),
        "role_ar": TODO, "role_en": i.get("role"), "career_en": i.get("career"), "size_en": (i.get("size") or "").title(),
        "tagline": TODO,
        "images": images,
        "verdict": {"headline": TODO, "solo": TODO + ": ماذا تستطيع وحدك بهذه السفينة؟", "crew": TODO + ": ماذا تضيف الطاقم؟",
                    "for_whom": TODO, "best_for": [TODO], "pros": [TODO], "cons": [TODO], "score": None},
        "prices": {"pledge": pledge, "history": history, "ingame": ingame, "availability": TODO,
                   "store_checked": max((s.get("imported_at") or "" for s in skus), default="")[:10] or None},
        "loadout": {"items": loadout, "delivery": delivery, "after_claim": RULES["after_claim"], "snapshot": RULES["snapshot"],
                    "first_steps": [
                        "افحص عدادات الأسلحة والمقذوفات في أول استدعاء.",
                        "احفظ لقطة التجهيز Snapshot من طرفية ASOP بعد أي تعديل (لا تشمل الذخيرة والصواريخ).",
                        "اعرف أقرب موقع يقدم Restock ويقبل حجم السفينة قبل أول مهمة.",
                        "بعد أي استدعاء بالتأمين نفّذ Restock قبل القتال.",
                    ]},
        "damage": {"pilot": {"dps": pilot["dps"], "sustained": pilot["sustained"], "parts": pilot["parts"]},
                   "crew": {"dps": crew_dps, "sustained": crew_sus, "stations": len(stations)},
                   "total": {"dps": round(pilot["dps"] + crew_dps, 1), "sustained": round(pilot["sustained"] + crew_sus, 1),
                             "people": 1 + len(stations)},
                   "pdc": {"dps": round(pdc["dps"], 1), "count": pdc["count"]},
                   "stations": all_stations,
                   "ordnance": [{"name": o["name"], "each": o["damage_each"], "salvo": o["salvo"], "loaded": o["loaded"],
                                 "total": (o["damage_each"] or 0) * o["loaded"]} for o in ordnance],
                   "formula": ["DPS = damage per shot × RPM ÷ 60 × weapons",
                               f"Total = Pilot {pilot['dps']:,} + Crew {crew_dps:,} = {round(pilot['dps'] + crew_dps, 1):,}",
                               f"PDC {round(pdc['dps'], 1):,} automatic — not added"],
                   "notes": []},
        "weapons": weapons, "ordnance": ordnance,
        "rearm": {"steps": [
            {"t": "اختر الموقع", "d": f"مدينة أو محطة فيها حظيرة أو منصة تقبل حجم السفينة ({(i.get('size') or '').title()})."},
            {"t": "اطلب الهبوط", "d": "اطلب الهبوط من ATC وانتظر رقم الحظيرة أو المنصة."},
            {"t": "ابقَ في مقعدك", "d": "اطلب الخدمة وأنت جالس داخل السفينة."},
            {"t": "افتح الخدمات", "d": "mobiGlas ← Vehicle Maintenance Services ← تبويب Landing Services."},
            {"t": "Restock", "d": "اختر الذخيرة والصواريخ والتوربيدات والإجراءات المضادة الناقصة."},
            {"t": "راجع التكلفة", "d": "تظهر التكلفة بالـaUEC قبل التأكيد. اختيار Repair يوقف بقية الخدمات حتى ينتهي."},
            {"t": "أكّد وانتظر", "d": "راقب التقدم حتى تكتمل الخدمة."},
            {"t": "تحقق", "d": "افحص العدادات ثم اطلب الإقلاع."}],
            "where": [TODO + ": أفضل أماكن التعبئة لهذه السفينة (حجم الحظيرة، المحطات التي تخدمها)"]
                     + [f"{o['name']}: {o['buy_where']}" for o in ordnance if o.get("buy_where")],
            "manual": {"supported": "unknown", "text": TODO + ": هل يمكن تحميل المقذوفات يدويًا (Tractor Beam) في هذه السفينة؟"},
            "costs": rearm_costs, "full_ordnance_auec": sum(o["full_refill_auec"] or 0 for o in ordnance),
            "troubleshooting": [
                {"p": "خيار Restock لا يظهر", "f": "تأكد أنك جالس في السفينة وأن الموقع يخدم حجمها، ثم أعد فتح Vehicle Maintenance Services."},
                {"p": "رفض ATC الهبوط", "f": "الموقع لا يملك حظيرة بحجم السفينة؛ اختر موقعًا آخر."},
                {"p": "المقذوفات لم تعد بعد الاستدعاء", "f": "سلوك متوقع منذ 4.8؛ نفّذ Restock."}]},
        "costs": {"calc": calc, "weapon_value_auec": weapon_value or None},
        "upgrades": {"slots": slots, "ordnance": ord_opts, "components": comp_opts,
                     "notes": ["الخيارات بنفس حجم الفتحة ومتاحة في المتاجر حسب UEX؛ فتحات Bespoke لا تُستبدل.",
                               "الحاسبة لا تحسب حدود الطاقة والحرارة؛ أسلحة الطاقة القوية قد تفرغ المكثف أسرع.",
                               "الأسلحة الباليستية تحتاج ذخيرة وتكلفة تعبئة؛ أسلحة الطاقة لا."]},
        "mobility": {"speeds": {"scm": sp.get("scm"), "max": sp.get("max"), "boost_fwd": sp.get("boost_forward")},
                     "accel": {"zero_to_scm_s": sp.get("zero_to_scm"), "zero_to_max_s": sp.get("zero_to_max")},
                     "rotation": {"pitch": ag.get("pitch"), "yaw": ag.get("yaw"), "roll": ag.get("roll"),
                                  "pitch_boost": ag.get("pitch_boosted"), "yaw_boost": ag.get("yaw_boosted"), "roll_boost": ag.get("roll_boosted")},
                     "fuel": {"quantum_scu": qcap, "hydrogen_scu": h2cap},
                     "quantum": {"range_gm": r((q.get("quantum_range") or 0) / 1e9), "drives": drives, "routes": f.get("routes") or []}},
        "durability": {"hull_hp": d.get("hull_hp"), "vital": d.get("vital"),
                       "shield": {"hp": d.get("shield_hp"), "faces": d.get("shield_faces"), "regen": d.get("shield_regen"), "regen_time": r(d.get("shield_regen_time"))},
                       "armor": {"physical": armor.get("damage_physical"), "energy": armor.get("damage_energy"),
                                 "distortion": armor.get("damage_distortion"), "hp": armor.get("health")}},
        "specs": specs, "components": components,
        "cargo": {"scu": f["cargo"].get("scu"), "official_scu": off.get("cargocapacity"), "max_box": f["cargo"].get("max_box"),
                  "hangar": TODO + ": هل فيها حظيرة؟ وما أكبر سفينة تستوعبها (رسميًا)؟", "facilities": []},
        "opinions": {"praised": [TODO], "criticized": [TODO], "period": TODO, "notes": []},
        "patch_watch": pw, "system_changes": sysch,
        "unverified": unverified,
        "_checks": checks,
        "_image_candidates": f.get("image_candidates") or [],
    }
    meta = {
        "schema": "marsad-ships/3", "game_version": gv, "build": build, "patch_date": live.get("date"),
        "upcoming": sorted({x["version"] for x in patches.get("upcoming") or []}, key=lambda v: tuple(int(t) for t in re.findall(r"\d+", v)))[:1],
        "verified_on": today, "fx_qar_per_usd": FX, "share_url": None,
        "gallery_url": i.get("pledge_url"),
        "sources": [{"label": "بيانات اللعبة — Star Citizen Wiki API", "url": f["sources"].get("wiki_api")},
                    {"label": "RSI Ship Matrix (رسمي)", "url": "https://robertsspaceindustries.com/ship-matrix/index"},
                    {"label": "صفحة السفينة في متجر RSI", "url": f["sources"].get("rsi_page")},
                    {"label": "UEX — أسعار aUEC والوقود", "url": "https://uexcorp.space"},
                    {"label": "سياسة الضرائب في متجر RSI", "url": "https://support.robertsspaceindustries.com/hc/en-us/articles/360051914473-Taxes-and-the-RSI-Pledge-Store"}]
                   + ([{"label": f"ملاحظات الإصدار {live.get('version')}", "url": "https://starcitizen.tools/" + live["title"].replace(" ", "_")}] if live.get("title") else []),
    }
    return {"meta": meta, "ships": [ship]}


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
    s = data["ships"][0]
    txt = json.dumps(data, ensure_ascii=False)
    print(f"report data -> {a.out}")
    print(f"TODO to write: {txt.count(TODO)} | weapons {len(s['weapons'])} | ordnance {len(s['ordnance'])} | stations {len(s['damage']['stations'])} | upgrade slots {len(s['upgrades']['slots'])}")
    print(f"damage: pilot {s['damage']['pilot']['dps']:,} | crew {s['damage']['crew']['dps']:,} | total {s['damage']['total']['dps']:,} ({s['damage']['total']['people']} people) | PDC {s['damage']['pdc']['dps']:,}")
    for c in s["_checks"]:
        print("  check:", c)


if __name__ == "__main__":
    main()
