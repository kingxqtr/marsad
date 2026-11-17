#!/usr/bin/env python3
"""Collect the raw facts for one Star Citizen ship before writing a report.

Sources (both read-only, no key needed):
  * Star Citizen Wiki API v2 (api.star-citizen.wiki) - data extracted from the
    current LIVE game files: specs, hardpoints, weapons, DPS, shields, fuel,
    quantum drive, insurance, pledge-store SKUs and images.
  * UEX 2.0 API (api.uexcorp.space) - in-game aUEC buy/rent prices, fuel prices
    per SCU and distances between orbits in Gm.

Usage:
  python3 fetch_ship.py "Polaris" --out work/polaris-facts.json
  python3 fetch_ship.py "Idris-M" --out work/idris.json --no-images

Exit codes: 0 ok, 2 ambiguous/unknown name (candidates are printed), 1 error.
Only the Python standard library is used.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from statistics import mean

WIKI_API = "https://api.star-citizen.wiki/api/v2"
WIKI_SITE = "https://starcitizen.tools"
UEX_API = "https://api.uexcorp.space/2.0"
UA = "sc-ship-report/2.0 (research script)"
TIMEOUT = 40
LIVE_SYSTEMS = ("Stanton", "Pyro", "Nyx")

_cache: dict[str, object] = {}


# ---------------------------------------------------------------- http helpers

def get_json(url: str, params: dict | None = None, retries: int = 2):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    if url in _cache:
        return _cache[url]
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8"))
                _cache[url] = data
                return data
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                _cache[url] = None
                return None
            last = e
        except Exception as e:  # network hiccup
            last = e
        time.sleep(1.5 * (attempt + 1))
    print(f"  ! request failed: {url} ({last})", file=sys.stderr)
    return None


def en(v):
    """Pick the English text from a {en_EN: ...} map, or return the value."""
    if isinstance(v, dict):
        return v.get("en_EN") or next(iter(v.values()), None)
    return v


def rnd(v, n=1):
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return None


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ------------------------------------------------------------- vehicle lookup

def resolve_vehicle(name: str):
    """Return (vehicle_data, meta, candidates)."""
    direct = get_json(f"{WIKI_API}/vehicles/{urllib.parse.quote(name)}")
    if direct and direct.get("data") and direct["data"].get("version"):
        return direct["data"], direct.get("meta", {}), []
    rows = []
    for q in dict.fromkeys([name, name.split()[-1] if " " in name else name]):
        found = get_json(f"{WIKI_API}/vehicles", {"filter[name]": q, "limit": 40}) or {}
        rows += [r for r in (found.get("data") or []) if r.get("slug") not in {x.get("slug") for x in rows}]
    # records with a game-data version come from the current game files; prefer them
    versioned = [r for r in rows if r.get("version")]
    key, tokens = norm(name), [norm(t) for t in name.split() if norm(t)]
    exact = [r for r in versioned if key in (norm(r.get("name")), norm(r.get("game_name")), norm(r.get("slug")))]
    loose = [r for r in versioned if all(t in norm((r.get("game_name") or "") + (r.get("name") or "")) for t in tokens)]
    pick = exact[0] if len(exact) == 1 else (loose[0] if len(loose) == 1 else None)
    if pick and pick.get("slug"):
        full = get_json(f"{WIKI_API}/vehicles/{pick['slug']}") or {}
        if full.get("data"):
            return full["data"], full.get("meta", {}), []
    if not versioned and direct and direct.get("data"):
        # concept or matrix-only ship: no game files yet
        d = direct["data"]
        d["_no_game_data"] = True
        return d, direct.get("meta", {}), []
    cands = [f"{r.get('name')}  (slug: {r.get('slug')}, version: {r.get('version')})" for r in (loose or versioned or rows)]
    return None, {}, cands


# ------------------------------------------------------------- port walking

KEEP_TYPES = {
    "WeaponGun", "Turret", "TurretBase", "MissileLauncher", "Missile", "BombLauncher", "Bomb",
    "WeaponDefensive", "PowerPlant", "Cooler", "Shield", "QuantumDrive", "Radar", "LifeSupportGenerator",
    "FuelTank", "QuantumFuelTank", "FuelIntake", "WeaponMining", "TractorBeam", "SalvageHead",
    "SalvageModifier", "ToolArm", "UtilityTurret", "EMP", "QuantumInterdictionGenerator", "Scanner",
    "MiningModifier", "SelfDestruct", "WeaponRegenPool", "JumpDrive",
}


def walk_ports(ports, parent="", out=None, depth=0, ancestors=(), root=""):
    out = [] if out is None else out
    for p in ports or []:
        ei = p.get("equipped_item") or {}
        t = ei.get("type") or p.get("type")
        top = root or p.get("name") or ""
        if ei and t in KEEP_TYPES:
            man = ei.get("manufacturer") or {}
            out.append({
                "port": p.get("name"),
                "parent": parent,
                "root_port": top,
                "in_turret": any(a[0] in ("Turret", "TurretBase", "UtilityTurret") for a in ancestors),
                "turret_class": next((a[1] for a in reversed(ancestors) if a[0] in ("Turret", "TurretBase", "UtilityTurret")), None),
                "port_type": p.get("type"),
                "port_size": (p.get("sizes") or {}).get("max"),
                "editable": p.get("editable"),
                "type": t,
                "sub_type": ei.get("sub_type"),
                "name": ei.get("name"),
                "class_name": ei.get("class_name"),
                "uuid": ei.get("uuid"),
                "size": ei.get("size"),
                "grade": ei.get("grade"),
                "class": ei.get("class"),
                "manufacturer": man.get("name"),
                "manufacturer_code": man.get("code"),
                "depth": depth,
            })
        child_anc = ancestors + (((t or ""), (ei.get("class_name") or "")),)
        walk_ports(p.get("ports"), p.get("name") or parent, out, depth + 1, child_anc, top)
    return out


def group_count(rows, keys):
    agg: dict[tuple, dict] = {}
    for r in rows:
        k = tuple(r.get(x) for x in keys)
        if k not in agg:
            agg[k] = {x: r.get(x) for x in keys}
            agg[k]["count"] = 0
            agg[k]["ports"] = []
        agg[k]["count"] += 1
        agg[k]["ports"].append(r.get("port"))
    return list(agg.values())


# ------------------------------------------------------------- item details

def item_details(uuid: str):
    d = get_json(f"{WIKI_API}/items/{uuid}") or {}
    return d.get("data") or {}


def slim_weapon(it: dict) -> dict:
    vw = it.get("vehicle_weapon") or {}
    am = it.get("ammunition") or {}
    dmg = vw.get("damage") or {}
    modes = vw.get("modes") or []
    return {
        "weapon_class": vw.get("class"),
        "weapon_type": vw.get("type"),          # Laser Repeater, Ballistic Cannon, ...
        "damage_per_shot": vw.get("damage_per_shot"),
        "damages": vw.get("damages"),            # [{type, name: energy|physical|distortion, damage}]
        "rpm": vw.get("rpm"),
        "range_m": vw.get("range") or am.get("range"),
        "projectile_speed": am.get("speed"),
        "ammo_capacity": vw.get("capacity") or am.get("capacity"),   # 0 = energy weapon (no ammo)
        "regeneration": vw.get("regeneration"),
        "dps_burst": dmg.get("burst"),
        "dps_sustained_60s": dmg.get("sustained_60s"),
        "dps_by_type": dmg.get("dps"),
        "alpha": dmg.get("alpha_total"),
        "max_damage_before_empty": dmg.get("max") or dmg.get("maximum"),
        "modes": [{k: m.get(k) for k in ("mode", "rpm", "pellets_per_shot", "ammo_per_shot", "damage_per_second")} for m in modes],
    }


def slim_missile(it: dict) -> dict:
    m = {}
    for key in ("missile", "bomb", "ordnance"):
        if isinstance(it.get(key), dict):
            m = it[key]
            break
    flight = m.get("flight") or {}
    return {
        "sub_type": it.get("sub_type"),                       # Torpedo / Missile / Bomb
        "damage_total": m.get("damage_total"),
        "damage_map": m.get("damage_map"),
        "signal_type": m.get("signal_type"),                  # Infrared / Electromagnetic / CrossSection
        "lock_time_s": m.get("lock_time"),
        "lock_range_max_m": m.get("lock_range_max"),
        "lock_range_min_m": m.get("lock_range_min"),
        "speed_mps": m.get("speed"),
        "flight_range_m": flight.get("range"),
        "explosion_radius_m": [m.get("explosion_radius_min"), m.get("explosion_radius_max")],
        "cluster_size": m.get("cluster_size"),
        "description": en(it.get("description")),
        "description_data": it.get("description_data"),
    }


def slim_qd(it: dict) -> dict:
    q = it.get("quantum_drive") or {}
    sj = q.get("standard_jump") or {}
    man = it.get("manufacturer") or {}
    return {
        "name": it.get("name"),
        "uuid": it.get("uuid"),
        "size": it.get("size"),
        "grade": it.get("grade"),
        "class": it.get("class"),
        "manufacturer": man.get("name"),
        "manufacturer_code": man.get("code"),
        "fuel_rate_scu_per_gm": q.get("quantum_fuel_requirement"),
        "speed_mps": sj.get("drive_speed"),
        "spool_s": sj.get("spool_up_time"),
        "cooldown_s": sj.get("cooldown_time"),
        "accel_stage1": sj.get("stage_one_accel_rate"),
        "accel_stage2": sj.get("stage_two_accel_rate"),
        "uex_prices": slim_uex_item_prices(it.get("uex_prices")),
    }


def slim_uex_item_prices(up):
    rows = (up or {}).get("purchase") or []
    out = []
    for r in rows:
        loc = r.get("starmap_location") or {}
        out.append({
            "price_auec": r.get("price_buy"),
            "terminal": r.get("terminal_name"),
            "location": loc.get("name"),
            "system": loc.get("star_system_name"),
            "game_version": r.get("game_version"),
            "updated": r.get("date_updated"),
        })
    out.sort(key=lambda x: (x["price_auec"] or 1e18))
    return out


def details_for(uuids):
    res = {}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(item_details, u): u for u in uuids if u}
        for f in cf.as_completed(futs):
            res[futs[f]] = f.result()
    return res


def qd_alternatives(size):
    d = get_json(f"{WIKI_API}/items", {"filter[type]": "QuantumDrive", "filter[size]": size, "limit": 60}) or {}
    rows = d.get("data") or []
    alts = [slim_qd(r) for r in rows]
    alts = [a for a in alts if a.get("fuel_rate_scu_per_gm")]
    alts.sort(key=lambda a: (-(a.get("speed_mps") or 0)))
    return alts


# ------------------------------------------------------------- RSI ship matrix (official)

def rsi_ship_matrix(v):
    """Official figures published by CIG on the RSI Ship Matrix."""
    d = get_json("https://robertsspaceindustries.com/ship-matrix/index") or {}
    rows = d.get("data") or []
    keys = {norm(v.get("name")), norm(v.get("shipmatrix_name") or ""), norm((v.get("game_name") or "").split(" ", 1)[-1])}
    keys.discard("")
    pick = next((r for r in rows if norm(r.get("name")) in keys), None)
    if not pick:
        return None
    imgs = []
    for m in pick.get("media") or []:
        im = m.get("images") or {}
        url = im.get("store_slideshow_large") or im.get("slideshow_wide") or m.get("source_url")
        if url:
            imgs.append(url if url.startswith("http") else "https://robertsspaceindustries.com" + url)
    keep = ("name", "length", "beam", "height", "mass", "cargocapacity", "min_crew", "max_crew", "scm_speed",
            "afterburner_speed", "pitch_max", "yaw_max", "roll_max", "production_status", "production_note", "size",
            "type", "focus", "description", "url", "time_modified")
    out = {k: pick.get(k) for k in keep}
    out["manufacturer"] = (pick.get("manufacturer") or {}).get("name")
    out["images"] = imgs
    if out.get("url") and not out["url"].startswith("http"):
        out["url"] = "https://robertsspaceindustries.com" + out["url"]
    return out


# ------------------------------------------------------------- UEX

def uex_vehicle(v):
    lst = (get_json(f"{UEX_API}/vehicles") or {}).get("data") or []
    uuid = v.get("uuid")
    for r in lst:
        if uuid and r.get("uuid") == uuid:
            return r
    key = norm(v.get("name"))
    for r in lst:
        if key and key in (norm(r.get("name")), norm(r.get("name_full"))):
            return r
    return None


def uex_prices_for_vehicle(vid):
    buy = (get_json(f"{UEX_API}/vehicles_purchases_prices", {"id_vehicle": vid}) or {}).get("data") or []
    rent = (get_json(f"{UEX_API}/vehicles_rentals_prices", {"id_vehicle": vid}) or {}).get("data") or []

    def slim(rows, price_key):
        out = []
        for r in rows:
            out.append({
                "price_auec": r.get(price_key),
                "terminal": r.get("terminal_name"),
                "location": r.get("city_name") or r.get("space_station_name") or r.get("outpost_name") or r.get("poi_name"),
                "planet": r.get("planet_name") or r.get("moon_name"),
                "system": r.get("star_system_name"),
                "game_version": r.get("game_version"),
            })
        return sorted(out, key=lambda x: x["price_auec"] or 1e18)
    return slim(buy, "price_buy"), slim(rent, "price_rent")


def uex_fuel():
    rows = (get_json(f"{UEX_API}/fuel_prices_all") or {}).get("data") or []
    out = {}
    for name in ("Quantum Fuel", "Hydrogen Fuel"):
        rs = [r for r in rows if r.get("commodity_name") == name and (r.get("price_buy") or 0) > 0]
        if not rs:
            continue
        prices = [r["price_buy"] for r in rs]
        cheapest = sorted(rs, key=lambda r: r["price_buy"])[:6]
        out["quantum" if name.startswith("Quantum") else "hydrogen"] = {
            "unit": "aUEC per SCU",
            "min": min(prices), "avg": round(mean(prices)), "max": max(prices), "terminals": len(rs),
            "cheapest": [{"terminal": r.get("terminal_name"), "price": r.get("price_buy")} for r in cheapest],
        }
    return out


def uex_distances():
    systems = (get_json(f"{UEX_API}/star_systems") or {}).get("data") or []
    ids = {s["name"]: s["id"] for s in systems if s.get("name") in LIVE_SYSTEMS}
    out = []
    for sname, sid in ids.items():
        rows = (get_json(f"{UEX_API}/orbits_distances", {"id_star_system": sid}) or {}).get("data") or []
        for r in rows:
            try:
                gm = float(r.get("distance"))
            except (TypeError, ValueError):
                continue
            out.append({
                "system": r.get("star_system_origin_name") or sname,
                "from": r.get("orbit_origin_name"),
                "to": r.get("orbit_destination_name"),
                "to_system": r.get("star_system_destination_name"),
                "gm": gm,
                "game_version": r.get("game_version"),
            })
    return out


MAIN_ORBITS = {
    "Stanton": ["Hurston", "Crusader", "ArcCorp", "MicroTech", "Pyro Gateway (Stanton system)",
                "Nyx Gateway (Stanton system)", "Terra Gateway (Stanton system)", "Magnus Gateway (Stanton system)"],
    "Pyro": ["Pyro I", "Monox", "Bloom", "Pyro IV", "Pyro V", "Terminus", "Stanton Gateway (Pyro system)",
             "Nyx Gateway (Pyro system)"],
    "Nyx": ["Delamar", "Stanton Gateway (Nyx system)", "Pyro Gateway (Nyx system)"],
}


def _ver(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3]) or (0,)


def routes_from_distances(rows):
    """Planet/gateway pairs inside one system, newest game version wins, deduplicated."""
    best = {}
    for sysname, names in MAIN_ORBITS.items():
        for r in rows:
            a, b = r.get("from"), r.get("to")
            if a in names and b in names and a != b:
                key = (sysname,) + tuple(sorted((a, b)))
                if key not in best or _ver(r.get("game_version")) > _ver(best[key].get("game_version")):
                    best[key] = r
    out = []
    order = list(MAIN_ORBITS)
    for (sysname, a, b), r in sorted(best.items(), key=lambda kv: (order.index(kv[0][0]), kv[0][1], kv[0][2])):
        fix = lambda n: "microTech" if n == "MicroTech" else n
        out.append({"sys": sysname, "a": fix(a), "b": fix(b), "gm": r["gm"], "v": r.get("game_version")})
    return out


# ------------------------------------------------------------- images

SKIP_IMG = re.compile(r"(?i)(icon|logo|\.svg$|manufacturer|insignia|badge|flag|signature|placeholder|comm-link)")


def wiki_images(page_title: str, limit: int = 60):
    q = get_json(f"{WIKI_SITE}/api.php", {
        "action": "query", "prop": "images", "titles": page_title, "imlimit": 500, "format": "json",
    }) or {}
    titles = []
    for p in (q.get("query") or {}).get("pages", {}).values():
        for im in p.get("images") or []:
            t = im.get("title", "")
            if t and not SKIP_IMG.search(t):
                titles.append(t)
    out = []
    for i in range(0, len(titles[:limit]), 40):
        chunk = titles[i:i + 40]
        info = get_json(f"{WIKI_SITE}/api.php", {
            "action": "query", "prop": "imageinfo", "titles": "|".join(chunk), "format": "json",
            "iiprop": "url|size|mime", "iiurlwidth": 1600,
        }) or {}
        for p in (info.get("query") or {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii or (ii.get("width") or 0) < 500:
                continue
            title = p.get("title", "")
            out.append({
                "title": title.replace("File:", ""),
                "hint": re.sub(r"[_\-]+", " ", title.replace("File:", "").rsplit(".", 1)[0]),
                "url": ii.get("thumburl") or ii.get("url"),
                "original": ii.get("url"),
                "width": ii.get("width"), "height": ii.get("height"),
                "page": ii.get("descriptionurl"),
            })
    out.sort(key=lambda x: x["title"].lower())
    return out


# ------------------------------------------------------------- main assembly

def build_facts(name: str, with_uex=True, with_images=True):
    v, meta, cands = resolve_vehicle(name)
    if not v:
        return None, cands

    ports = walk_ports(v.get("ports"))
    weapons = [r for r in ports if r["type"] == "WeaponGun"]
    missiles = [r for r in ports if r["type"] in ("Missile", "Bomb")]
    racks = [r for r in ports if r["type"] in ("MissileLauncher", "BombLauncher")]
    cms = [r for r in ports if r["type"] == "WeaponDefensive"]
    comps = [r for r in ports if r["type"] not in ("WeaponGun", "Missile", "Bomb", "MissileLauncher", "BombLauncher",
                                                   "WeaponDefensive", "Turret", "TurretBase")]

    uuids = {r["uuid"] for r in weapons + missiles}
    qd_port = next((r for r in ports if r["type"] == "QuantumDrive"), None)
    if qd_port:
        uuids.add(qd_port["uuid"])
    det = details_for(uuids)

    weapon_items = {}
    for r in weapons:
        it = det.get(r["uuid"]) or {}
        weapon_items[r["uuid"]] = {"name": r["name"], "size": r["size"], "manufacturer": r["manufacturer"],
                                   **slim_weapon(it), "shop_prices": slim_uex_item_prices(it.get("uex_prices"))}
    ordnance_items = {}
    for r in missiles:
        it = det.get(r["uuid"]) or {}
        ordnance_items[r["uuid"]] = {"name": r["name"], "size": r["size"], "type": r["type"],
                                     "manufacturer": r["manufacturer"], **slim_missile(it),
                                     "shop_prices": slim_uex_item_prices(it.get("uex_prices"))}

    quantum = dict(v.get("quantum") or {})
    stock_qd = slim_qd(det.get(qd_port["uuid"]) or {}) if qd_port else None
    alts = qd_alternatives(qd_port["size"]) if qd_port and qd_port.get("size") else []
    cap = quantum.get("quantum_fuel_capacity")
    if stock_qd and cap and stock_qd.get("fuel_rate_scu_per_gm"):
        stock_qd["range_gm_full_tank"] = rnd(cap / stock_qd["fuel_rate_scu_per_gm"], 1)
    for a in alts:
        if cap and a.get("fuel_rate_scu_per_gm"):
            a["range_gm_full_tank"] = rnd(cap / a["fuel_rate_scu_per_gm"], 1)

    turrets = v.get("turrets") or {}
    turret_groups = {}
    for kind, rows in turrets.items():
        turret_groups[kind] = [{
            "name": t.get("display_name"), "class_name": t.get("class_name"), "hardpoint": t.get("hardpoint_name"),
            "size": t.get("size"), "mount_count": t.get("mount_count"), "weapon_sizes": t.get("weapon_sizes"),
            "dps_total": t.get("dps_total"), "sustained_dps_total": t.get("sustained_dps_total"),
            "alpha_total": t.get("alpha_total"), "is_pilot_slaveable": t.get("is_pilot_slaveable"),
            "weapons": [w.get("name") for w in (t.get("weapons") or [])],
        } for t in rows or []]

    shield = v.get("shield") or {}
    facts = {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "query": name,
        "game_version": v.get("version") or (meta.get("resource") or {}).get("version"),
        "game_data": not v.get("_no_game_data"),
        "wiki_updated_at": v.get("updated_at"),
        "identity": {
            "name": v.get("name"), "game_name": v.get("game_name"), "slug": v.get("slug"),
            "manufacturer": (v.get("manufacturer") or {}).get("name"),
            "manufacturer_code": (v.get("manufacturer") or {}).get("code"),
            "career": v.get("career"), "role": v.get("role"), "type": en(v.get("type")),
            "foci": [en(f) for f in v.get("foci") or []],
            "size": en(v.get("size")), "size_class": v.get("size_class"),
            "production_status": en(v.get("production_status")), "production_note": en(v.get("production_note")),
            "description": en(v.get("description")),
            "dimension_m": v.get("dimension"), "mass_kg": v.get("mass_total") or v.get("mass"),
            "crew": v.get("crew"), "seating": v.get("seating"), "max_medical_tier": v.get("max_medical_tier"),
            "is_spaceship": v.get("is_spaceship"), "is_vehicle": v.get("is_vehicle"),
            "pledge_url": v.get("pledge_url"), "wiki_page": (v.get("curated_data") or {}).get("page_url"),
        },
        "cargo": {
            "scu": v.get("cargo_capacity"), "ore_scu": v.get("ore_capacity"),
            "grids": [{k: g.get(k) for k in ("scu", "width", "height", "length", "max_scu_box", "open", "external")}
                      for g in v.get("cargo_grids") or []],
            "limits": v.get("cargo_limits"),
            "personal_inventory_uscu": v.get("vehicle_inventory"),
            "weapon_storage": v.get("weapon_storage"),
        },
        "durability": {
            "hull_hp": v.get("health"),
            "shield_hp": shield.get("hp") or v.get("shield_hp"),
            "shield_face_type": shield.get("face_type") or v.get("shield_face_type"),
            "shield_regen_per_s": shield.get("regeneration"),
            "shield_regen_time_s": shield.get("regeneration_time"),
            "shield_resistance": shield.get("resistance"),
            "armor": v.get("armor"),
            "penetration_multiplier": v.get("penetration_multiplier"),
            "damage_limits": v.get("damage_limits"),
            "countermeasures": group_count(cms, ["name", "size"]),
            "parts_top": [{"name": p.get("name"), "hp": p.get("damage_max") or p.get("health")}
                          for p in (v.get("parts") or [])][:25],
        },
        "mobility": {
            "speed": v.get("speed"), "agility": v.get("agility"), "afterburner": v.get("afterburner"),
            "propulsion": v.get("propulsion"),
            "hydrogen": v.get("fuel"),
            "quantum": quantum,
            "quantum_note": "quantum_range is in metres; port_olisar_to_arccorp_fuel looks like 1/1000 SCU",
        },
        "weaponry_summary": v.get("weaponry"),
        "weapon_snapshot": v.get("weapon_snapshot"),
        "turrets": turret_groups,
        "weapons_mounted": group_count(weapons, ["name", "size", "manufacturer", "root_port", "in_turret", "uuid"]),
        "weapon_items": weapon_items,
        "ordnance_racks": group_count(racks, ["name", "size", "type", "port"]),
        "ordnance_loaded": group_count(missiles, ["name", "size", "type", "parent", "uuid"]),
        "ordnance_items": ordnance_items,
        "components": group_count(comps, ["type", "name", "size", "grade", "class", "manufacturer"]),
        "quantum_drive": {"stock": stock_qd, "same_size_alternatives": alts, "fuel_capacity_scu": cap,
                          "formula": "fuel_SCU = distance_Gm x fuel_rate_scu_per_gm ; range_Gm = capacity / rate"},
        "insurance": v.get("insurance"),
        "loaners": [l.get("name") for l in v.get("loaner") or []],
        "pledge": {
            "msrp_usd": v.get("msrp"), "warbond_usd": v.get("warbond_price"),
            "skus": [{k: s.get(k) for k in ("title", "price", "discounted_price", "is_warbond", "is_package", "available", "source", "url", "imported_at")}
                     for s in v.get("skus") or []],
            "curated": {k: (v.get("curated_data") or {}).get(k) for k in (
                "original_pledge_price", "original_warbond_price", "added_in_version", "concept_date",
                "pledge_availability", "brochure_url", "qa_urls", "presentation_urls")},
        },
        "wiki_uex_prices": v.get("uex_prices"),
        "api_images": v.get("images"),
        "sources": {"wiki_api": f"{WIKI_API}/vehicles/{v.get('slug')}", "wiki_page": (v.get('curated_data') or {}).get('page_url')},
    }

    facts["official"] = rsi_ship_matrix(v)

    if with_uex:
        uv = uex_vehicle(v)
        if uv:
            buy, rent = uex_prices_for_vehicle(uv["id"])
            facts["uex"] = {"vehicle_id": uv["id"], "name_full": uv.get("name_full"),
                            "fuel_quantum": uv.get("fuel_quantum"), "fuel_hydrogen": uv.get("fuel_hydrogen"),
                            "purchase": buy, "rental": rent}
        else:
            facts["uex"] = {"vehicle_id": None, "purchase": [], "rental": []}
        facts["fuel_prices"] = uex_fuel()
        facts["distances_gm"] = uex_distances()
        facts["routes"] = routes_from_distances(facts["distances_gm"])

    if with_images:
        page = (facts["identity"].get("wiki_page") or "").rsplit("/", 1)[-1] or v.get("name")
        facts["image_candidates"] = wiki_images(urllib.parse.unquote(page))
    return facts, []


def fmt(n, d=0):
    if n is None:
        return "—"
    try:
        return f"{float(n):,.{d}f}"
    except (TypeError, ValueError):
        return str(n)


def summary(f: dict) -> str:
    i, d, m = f["identity"], f["durability"], f["mobility"]
    sp, q, w = m.get("speed") or {}, m.get("quantum") or {}, f.get("weaponry_summary") or {}
    qd = (f.get("quantum_drive") or {}).get("stock") or {}
    L = []
    L.append(f"== {i['name']} ({i['manufacturer']}) | game data {f['game_version']} | fetched {f['fetched_at']}")
    if not f.get("game_data", True):
        L.append("!! NO GAME-FILE DATA: concept or matrix-only ship. Figures are design targets, not in-game performance.")
    L.append(f"role {i.get('career')}/{i.get('role')} | size {i.get('size')} | status {i.get('production_status')}")
    o = f.get("official") or {}
    if o:
        L.append(f"OFFICIAL ship matrix: L{o.get('length')} B{o.get('beam')} H{o.get('height')} m | cargo {o.get('cargocapacity')} SCU | crew {o.get('min_crew')}-{o.get('max_crew')} | SCM {o.get('scm_speed')} | max {o.get('afterburner_speed')} | p/y/r {o.get('pitch_max')}/{o.get('yaw_max')}/{o.get('roll_max')} | images {len(o.get('images') or [])}")
    else:
        L.append("OFFICIAL ship matrix: no match (concept-only or renamed ship)")
    dim = i.get("dimension_m") or {}
    L.append(f"dims L{dim.get('length')} W{dim.get('width')} H{dim.get('height')} m | mass {fmt(i.get('mass_kg'))} kg | crew {i.get('crew')}")
    L.append(f"hull {fmt(d.get('hull_hp'))} HP | shield {fmt(d.get('shield_hp'))} HP ({d.get('shield_face_type')}) regen {fmt(d.get('shield_regen_per_s'))}/s")
    L.append(f"speed SCM {sp.get('scm')} | max {sp.get('max')} | boost fwd {sp.get('boost_forward')} m/s | agility {m.get('agility')}")
    L.append(f"H2 fuel {(m.get('hydrogen') or {}).get('capacity')} | QT fuel {q.get('quantum_fuel_capacity')} SCU | QT range {fmt((q.get('quantum_range') or 0)/1e9,1)} Gm | QT speed {fmt((q.get('quantum_speed') or 0)/1e6,1)} Mm/s")
    if qd:
        L.append(f"stock QD {qd.get('name')} S{qd.get('size')} {qd.get('grade')} {qd.get('class')} | rate {qd.get('fuel_rate_scu_per_gm')} SCU/Gm | spool {qd.get('spool_s')} s | alternatives {len(f['quantum_drive']['same_size_alternatives'])}")
    L.append(f"DPS pilot {w.get('pilot_dps')} (sustained {w.get('pilot_sustained_dps')}) | turrets {w.get('turret_dps')} (sustained {w.get('turret_sustained_dps')}) | missile dmg total {fmt(w.get('total_missile_damage'))}")
    L.append("weapons mounted:")
    for g in f["weapons_mounted"]:
        wi = f["weapon_items"].get(g["uuid"], {})
        L.append(f"  {g['count']}x {g['name']} S{g['size']} [{wi.get('weapon_type')}] dps/each {wi.get('dps_burst')} ammo {wi.get('ammo_capacity')} on {g['root_port']} {'(turret)' if g['in_turret'] else '(pilot/fixed?)'}")
    for kind, rows in (f.get("turrets") or {}).items():
        for t in rows:
            L.append(f"  turret[{kind}] {t['class_name']} S{t['size']} x{t['mount_count']} dps {t['dps_total']} weapons {t['weapons'][:4]}")
    L.append("ordnance loaded:")
    for g in f["ordnance_loaded"]:
        L.append(f"  {g['count']}x {g['name']} S{g['size']} ({g['type']}) in {g['parent']}")
    for r in f["ordnance_racks"]:
        L.append(f"  rack {r['name']} S{r['size']} at {r['port']}")
    L.append("components:")
    for c in f["components"]:
        L.append(f"  {c['count']}x {c['type']}: {c['name']} S{c['size']} {c['grade'] or ''} {c['class'] or ''} ({c['manufacturer']})")
    ins = f.get("insurance") or {}
    L.append(f"insurance claim {ins.get('claim_time')} min | expedite {ins.get('expedite_time')} min for {fmt(ins.get('expedite_cost'))} aUEC | loaners {f.get('loaners')}")
    p = f["pledge"]
    L.append(f"pledge msrp ${p.get('msrp_usd')} | curated {p.get('curated')}")
    for s in p["skus"]:
        L.append(f"  sku {s['title']} ${s['price']} warbond={s['is_warbond']} available={s['available']} ({s['source']})")
    u = f.get("uex") or {}
    if u:
        L.append(f"UEX buy {u.get('purchase')[:4]} | rent {u.get('rental')[:4]}")
    fp = f.get("fuel_prices") or {}
    for k, v in fp.items():
        L.append(f"fuel {k}: min {v['min']} avg {v['avg']} max {v['max']} aUEC/SCU at {v['terminals']} terminals")
    L.append(f"distance pairs: {len(f.get('distances_gm') or [])} | calculator routes: {len(f.get('routes') or [])} | image candidates: {len(f.get('image_candidates') or [])}")
    for im in (f.get("image_candidates") or [])[:40]:
        L.append(f"  img: {im['hint']}  ({im['width']}x{im['height']})")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="ship name as written in the game, e.g. Polaris, 890 Jump, Idris-M")
    ap.add_argument("--out", default=None, help="write the full facts JSON here")
    ap.add_argument("--no-uex", action="store_true", help="skip UEX prices, fuel prices and distances")
    ap.add_argument("--no-images", action="store_true", help="skip the wiki image list")
    a = ap.parse_args()

    facts, cands = build_facts(a.name, with_uex=not a.no_uex, with_images=not a.no_images)
    if not facts:
        print(f"No exact match for '{a.name}'.")
        if cands:
            print("Candidates (re-run with the exact name or slug):")
            for c in cands:
                print("  -", c)
        sys.exit(2)
    out = a.out or f"{facts['identity']['slug'] or 'ship'}-facts.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(facts, fh, ensure_ascii=False, indent=1)
    print(summary(facts))
    print(f"\nfull facts -> {out}")


if __name__ == "__main__":
    main()
