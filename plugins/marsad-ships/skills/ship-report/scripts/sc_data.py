#!/usr/bin/env python3
"""Collect every fact the ship report needs, from live sources, in one run.

  python3 sc_data.py "<ship name>" --out work/<ship>-facts.json

Sources (read-only, no keys):
  * Star Citizen Wiki API v2  - current LIVE game-file data: specs, hardpoints,
    weapons, turrets, DPS, ordnance, shields, armor, fuel, quantum, insurance,
    RSI store SKUs, images, plus item catalogs used for upgrade options.
  * RSI Ship Matrix           - official dimensions, crew, cargo, speeds, images.
  * UEX 2.0                   - aUEC ship buy/rent prices, fuel prices per SCU,
    ship-service commodities (ammunition per size, countermeasures, RMC),
    distances between orbits in Gm.
  * Star Citizen Wiki pages   - latest LIVE patch, the upcoming patch, and every
    patch-note line that mentions this ship.

Exit codes: 0 ok, 2 unknown/ambiguous name (candidates printed), 1 error.
Standard library only.
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
WIKI = "https://starcitizen.tools"
UEX = "https://api.uexcorp.space/2.0"
RSI_MATRIX = "https://robertsspaceindustries.com/ship-matrix/index"
UA = "sc-ship-report/3.0 (research script)"
TIMEOUT = 45
_cache: dict[str, object] = {}

MAIN_ORBITS = {
    "Stanton": ["Hurston", "Crusader", "ArcCorp", "MicroTech", "Pyro Gateway (Stanton system)",
                "Nyx Gateway (Stanton system)", "Terra Gateway (Stanton system)", "Magnus Gateway (Stanton system)"],
    "Pyro": ["Pyro I", "Monox", "Bloom", "Pyro IV", "Pyro V", "Terminus", "Stanton Gateway (Pyro system)", "Nyx Gateway (Pyro system)"],
    "Nyx": ["Delamar", "Stanton Gateway (Nyx system)", "Pyro Gateway (Nyx system)"],
}
KEEP_TYPES = {
    "WeaponGun", "Turret", "TurretBase", "MissileLauncher", "Missile", "BombLauncher", "Bomb", "WeaponDefensive",
    "PowerPlant", "Cooler", "Shield", "QuantumDrive", "Radar", "LifeSupportGenerator", "FuelTank", "QuantumFuelTank",
    "FuelIntake", "WeaponMining", "TractorBeam", "SalvageHead", "SalvageModifier", "ToolArm", "UtilityTurret", "EMP",
    "QuantumInterdictionGenerator", "Scanner", "MiningModifier", "SelfDestruct", "JumpDrive",
}
UPGRADABLE_COMPONENTS = ("Shield", "PowerPlant", "Cooler", "QuantumDrive", "Radar")


# ------------------------------------------------------------------ http

def get_json(url, params=None, retries=2, method="GET", body=None):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    key = url + (json.dumps(body) if body else "")
    if key in _cache:
        return _cache[key]
    last = None
    for attempt in range(retries + 1):
        try:
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(url, data=data, method=method, headers={
                "User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                out = json.loads(r.read().decode("utf-8"))
                _cache[key] = out
                return out
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                _cache[key] = None
                return None
            last = e
        except Exception as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    print(f"  ! request failed: {url} ({last})", file=sys.stderr)
    return None


def en(v):
    if isinstance(v, dict):
        return v.get("en_EN") or next(iter(v.values()), None)
    return v


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def r1(v, n=1):
    v = num(v)
    return None if v is None else round(v, n)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def cheapest(uex_prices):
    rows = (uex_prices or {}).get("purchase") or []
    rows = [r for r in rows if (r.get("price_buy") or 0) > 0]
    if not rows:
        return None, None, []
    rows.sort(key=lambda r: r["price_buy"])
    def where(r):
        loc = r.get("starmap_location") or {}
        sysn = loc.get("star_system_name")
        return f"{r.get('terminal_name')}" + (f" ({sysn})" if sysn else "")
    return rows[0]["price_buy"], where(rows[0]), [{"price": r["price_buy"], "where": where(r)} for r in rows[:4]]


# ------------------------------------------------------------------ vehicle lookup

def resolve_vehicle(name):
    direct = get_json(f"{WIKI_API}/vehicles/{urllib.parse.quote(name)}")
    if direct and direct.get("data") and direct["data"].get("version"):
        return direct["data"], direct.get("meta", {}), []
    rows = []
    for q in dict.fromkeys([name, name.split()[-1] if " " in name else name]):
        found = get_json(f"{WIKI_API}/vehicles", {"filter[name]": q, "limit": 40}) or {}
        rows += [r for r in (found.get("data") or []) if r.get("slug") not in {x.get("slug") for x in rows}]
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
        d = direct["data"]
        d["_no_game_data"] = True
        return d, direct.get("meta", {}), []
    return None, {}, [f"{r.get('name')}  (slug: {r.get('slug')}, version: {r.get('version')})" for r in (loose or versioned or rows)]


# ------------------------------------------------------------------ ports

def walk_ports(ports, parent="", out=None, depth=0, ancestors=(), root=""):
    out = [] if out is None else out
    for p in ports or []:
        ei = p.get("equipped_item") or {}
        t = ei.get("type") or p.get("type")
        top = root or p.get("name") or ""
        if ei and t in KEEP_TYPES:
            man = ei.get("manufacturer") or {}
            out.append({
                "port": p.get("name"), "parent": parent, "root_port": top,
                "in_turret": any(a[0] in ("Turret", "TurretBase", "UtilityTurret") for a in ancestors),
                "port_size": (p.get("sizes") or {}).get("max"), "editable": bool(p.get("editable")),
                "type": t, "sub_type": ei.get("sub_type"), "name": ei.get("name"), "class_name": ei.get("class_name"),
                "uuid": ei.get("uuid"), "size": ei.get("size"), "grade": ei.get("grade"), "class": ei.get("class"),
                "manufacturer": man.get("name"), "depth": depth,
            })
        walk_ports(p.get("ports"), p.get("name") or parent, out, depth + 1, ancestors + (((t or ""), (ei.get("class_name") or "")),), top)
    return out


def group(rows, keys):
    agg = {}
    for r in rows:
        k = tuple(r.get(x) for x in keys)
        if k not in agg:
            agg[k] = {x: r.get(x) for x in keys}
            agg[k]["count"] = 0
            agg[k]["ports"] = []
        agg[k]["count"] += 1
        agg[k]["ports"].append(r.get("port"))
    return list(agg.values())


# ------------------------------------------------------------------ items

def item(uuid):
    return (get_json(f"{WIKI_API}/items/{uuid}") or {}).get("data") or {}


def items_parallel(uuids):
    out = {}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(item, u): u for u in uuids if u}
        for f in cf.as_completed(futs):
            out[futs[f]] = f.result()
    return out


def slim_weapon(it):
    vw = it.get("vehicle_weapon") or {}
    am = it.get("ammunition") or {}
    dmg = vw.get("damage") or {}
    dps_t = dmg.get("dps") or {}
    kind = max(dps_t.items(), key=lambda kv: kv[1] or 0)[0] if dps_t else None
    price, where, shops = cheapest(it.get("uex_prices"))
    man = it.get("manufacturer") or {}
    return {
        "name": it.get("name"), "uuid": it.get("uuid"), "size": it.get("size"), "manufacturer": man.get("name"),
        "weapon_type": vw.get("type"), "damage_kind": {"energy": "Energy", "physical": "Ballistic", "distortion": "Distortion"}.get(kind, kind),
        "alpha": vw.get("damage_per_shot"), "rpm": vw.get("rpm"), "dps": dmg.get("burst"), "sustained": dmg.get("sustained_60s"),
        "range_m": vw.get("range") or am.get("range"), "speed_mps": am.get("speed"),
        "ammo": vw.get("capacity") or am.get("capacity") or 0, "price_auec": price, "buy_where": where, "shops": shops,
        "base_variant": it.get("is_base_variant", True), "class_name": it.get("class_name"),
    }


def slim_missile(it):
    m = it.get("missile") or it.get("bomb") or {}
    flight = m.get("flight") or {}
    price, where, shops = cheapest(it.get("uex_prices"))
    manf = next((x.get("value") for x in it.get("description_data") or [] if x.get("name") == "Manufacturer"), None)
    return {
        "name": it.get("name"), "uuid": it.get("uuid"), "size": it.get("size"), "sub_type": it.get("sub_type"),
        "manufacturer": manf or (it.get("manufacturer") or {}).get("name"), "damage": m.get("damage_total"),
        "damage_map": m.get("damage_map"), "signal": m.get("signal_type"), "lock_range_m": m.get("lock_range_max"),
        "lock_time_s": m.get("lock_time"), "speed_mps": m.get("speed"), "flight_range_m": flight.get("range"),
        "price_auec": price, "buy_where": where, "shops": shops, "base_variant": it.get("is_base_variant", True),
    }


def slim_qd(it):
    q = it.get("quantum_drive") or {}
    sj = q.get("standard_jump") or {}
    price, where, _ = cheapest(it.get("uex_prices"))
    man = it.get("manufacturer") or {}
    return {"name": it.get("name"), "uuid": it.get("uuid"), "size": it.get("size"), "grade": it.get("grade"),
            "class": it.get("class"), "manufacturer": man.get("name"), "fuel_rate": q.get("quantum_fuel_requirement"),
            "speed_mps": sj.get("drive_speed"), "spool_s": sj.get("spool_up_time"), "cooldown_s": sj.get("cooldown_time"),
            "accel1": sj.get("stage_one_accel_rate"), "accel2": sj.get("stage_two_accel_rate"),
            "price_auec": price, "buy_where": where}


def slim_component(it):
    price, where, _ = cheapest(it.get("uex_prices"))
    man = it.get("manufacturer") or {}
    stat = None
    sh = it.get("shield") or {}
    if sh:
        stat = f"{int(sh.get('max_health') or 0):,} HP · regen {int(sh.get('regen_rate') or 0):,}/s"
    return {"name": it.get("name"), "uuid": it.get("uuid"), "type": it.get("type"), "size": it.get("size"),
            "grade": it.get("grade"), "class": it.get("class"), "manufacturer": man.get("name"), "stat": stat,
            "shield_hp": sh.get("max_health"), "shield_regen": sh.get("regen_rate"),
            "price_auec": price, "buy_where": where, "base_variant": it.get("is_base_variant", True)}


def catalog(type_, size, slim):
    d = get_json(f"{WIKI_API}/items", {"filter[type]": type_, "filter[size]": size, "limit": 150}) or {}
    return [slim(r) for r in d.get("data") or []]


def weapon_catalog(size):
    rows = catalog("WeaponGun", size, slim_weapon)
    rows = [r for r in rows if r["price_auec"] and r["weapon_type"] and "Rocket" not in (r["weapon_type"] or "")
            and r["dps"]]
    rows.sort(key=lambda r: -(r["dps"] or 0))
    return rows


def missile_catalog(size):
    rows = [r for r in catalog("Missile", size, slim_missile) if r["price_auec"] and r["damage"]]
    rows.sort(key=lambda r: -(r["damage"] or 0))
    return rows


def component_catalog(type_, size):
    rows = [r for r in catalog(type_, size, slim_component) if r["price_auec"]]
    return rows


# ------------------------------------------------------------------ official / uex

def rsi_matrix(v):
    rows = (get_json(RSI_MATRIX) or {}).get("data") or []
    keys = {norm(v.get("name")), norm(v.get("shipmatrix_name") or ""), norm((v.get("game_name") or "").split(" ", 1)[-1])}
    keys.discard("")
    pick = next((r for r in rows if norm(r.get("name")) in keys), None)
    if not pick:
        return None
    imgs = []
    for m in pick.get("media") or []:
        im = m.get("images") or {}
        u = im.get("store_slideshow_large") or im.get("slideshow_wide") or m.get("source_url")
        if u:
            imgs.append(u if u.startswith("http") else "https://robertsspaceindustries.com" + u)
    out = {k: pick.get(k) for k in ("name", "length", "beam", "height", "mass", "cargocapacity", "min_crew", "max_crew",
                                     "scm_speed", "afterburner_speed", "pitch_max", "yaw_max", "roll_max",
                                     "production_status", "size", "type", "focus", "url")}
    if out.get("url") and not out["url"].startswith("http"):
        out["url"] = "https://robertsspaceindustries.com" + out["url"]
    out["images"] = imgs
    return out


def uex_vehicle(v):
    lst = (get_json(f"{UEX}/vehicles") or {}).get("data") or []
    for r in lst:
        if v.get("uuid") and r.get("uuid") == v.get("uuid"):
            return r
    key = norm(v.get("name"))
    return next((r for r in lst if key and key in (norm(r.get("name")), norm(r.get("name_full")))), None)


def uex_ship_prices(vid):
    def slim(rows, k):
        out = [{"price_auec": r.get(k), "terminal": r.get("terminal_name"),
                "location": r.get("city_name") or r.get("space_station_name") or r.get("outpost_name") or r.get("poi_name"),
                "system": r.get("star_system_name"), "game_version": r.get("game_version")} for r in rows if r.get(k)]
        return sorted(out, key=lambda x: x["price_auec"])
    buy = (get_json(f"{UEX}/vehicles_purchases_prices", {"id_vehicle": vid}) or {}).get("data") or []
    rent = (get_json(f"{UEX}/vehicles_rentals_prices", {"id_vehicle": vid}) or {}).get("data") or []
    return slim(buy, "price_buy"), slim(rent, "price_rent")


def uex_fuel():
    rows = (get_json(f"{UEX}/fuel_prices_all") or {}).get("data") or []
    out = {}
    for name, key in (("Quantum Fuel", "quantum"), ("Hydrogen Fuel", "hydrogen")):
        rs = [r for r in rows if r.get("commodity_name") == name and (r.get("price_buy") or 0) > 0]
        if rs:
            p = [r["price_buy"] for r in rs]
            best = sorted(rs, key=lambda r: r["price_buy"])[:5]
            out[key] = {"min": min(p), "avg": round(mean(p)), "max": max(p), "terminals": len(rs),
                        "cheapest": [{"where": r.get("terminal_name"), "price": r["price_buy"]} for r in best]}
    return out


def uex_service_commodities():
    rows = (get_json(f"{UEX}/commodities") or {}).get("data") or []
    out = {"ammo_per_scu": {}, "decoy_per_scu": None, "noise_per_scu": None, "rmc_per_scu": None}
    for r in rows:
        n = r.get("name") or ""
        m = re.match(r"Ship Ammunition - Size (\d+)", n)
        if m and r.get("price_buy"):
            out["ammo_per_scu"][m.group(1)] = r["price_buy"]
        elif n == "Ship Decoy Countermeasures":
            out["decoy_per_scu"] = r.get("price_buy") or None
        elif n == "Ship Noise Countermeasures":
            out["noise_per_scu"] = r.get("price_buy") or None
        elif n.startswith("Recycled Material Composite"):
            out["rmc_per_scu"] = r.get("price_buy") or None
    return out


def uex_routes():
    systems = (get_json(f"{UEX}/star_systems") or {}).get("data") or []
    ids = {s["name"]: s["id"] for s in systems if s.get("name") in MAIN_ORBITS}
    raw = []
    for sname, sid in ids.items():
        for r in (get_json(f"{UEX}/orbits_distances", {"id_star_system": sid}) or {}).get("data") or []:
            gm = num(r.get("distance"))
            if gm:
                raw.append({"from": r.get("orbit_origin_name"), "to": r.get("orbit_destination_name"), "gm": gm, "v": r.get("game_version")})
    def ver(v):
        return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3]) or (0,)
    best = {}
    for sysn, names in MAIN_ORBITS.items():
        for r in raw:
            if r["from"] in names and r["to"] in names and r["from"] != r["to"]:
                k = (sysn,) + tuple(sorted((r["from"], r["to"])))
                if k not in best or ver(r["v"]) > ver(best[k]["v"]):
                    best[k] = r
    order = list(MAIN_ORBITS)
    fix = lambda n: "microTech" if n == "MicroTech" else n
    return [{"sys": k[0], "a": fix(k[1]), "b": fix(k[2]), "gm": r["gm"]} for k, r in
            sorted(best.items(), key=lambda kv: (order.index(kv[0][0]), kv[0][1], kv[0][2]))]


# ------------------------------------------------------------------ wiki pages: images + patches

SKIP_IMG = re.compile(r"(?i)(icon|logo|\.svg$|manufacturer|insignia|badge|flag|signature|placeholder)")


def wiki_images(page, limit=70):
    q = get_json(f"{WIKI}/api.php", {"action": "query", "prop": "images", "titles": page, "imlimit": 500, "format": "json"}) or {}
    titles = [im["title"] for p in (q.get("query") or {}).get("pages", {}).values() for im in p.get("images") or []
              if not SKIP_IMG.search(im.get("title", ""))][:limit]
    out = []
    for i in range(0, len(titles), 40):
        info = get_json(f"{WIKI}/api.php", {"action": "query", "prop": "imageinfo", "titles": "|".join(titles[i:i + 40]),
                                            "format": "json", "iiprop": "url|size", "iiurlwidth": 1600}) or {}
        for p in (info.get("query") or {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            if ii and (ii.get("width") or 0) >= 500:
                t = p.get("title", "").replace("File:", "")
                out.append({"hint": re.sub(r"[_\-]+", " ", t.rsplit(".", 1)[0]), "url": ii.get("thumburl") or ii.get("url"),
                            "size": f"{ii.get('width')}x{ii.get('height')}"})
    return sorted(out, key=lambda x: x["hint"].lower())


def wikitext(page):
    d = get_json(f"{WIKI}/api.php", {"action": "parse", "page": page, "prop": "wikitext", "format": "json", "redirects": 1}) or {}
    return ((d.get("parse") or {}).get("wikitext") or {}).get("*", "")


def clean_wiki(s):
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^/]*/>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+ ([^\]]+)\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return re.sub(r"\s+", " ", s).strip(" *:-")


def patch_info(ship_names, generic_kw=("restock", "rearm", "landing services", "vehicle maintenance", "insurance", "claim",
                                        "ordnance", "torpedo", "missile", "ammunition", "quantum fuel", "ship weapons")):
    titles = set()
    for major in ("4", "5", "6"):
        d = get_json(f"{WIKI}/api.php", {"action": "query", "list": "prefixsearch", "pssearch": f"Update:Star Citizen Alpha {major}.",
                                         "pslimit": 100, "format": "json"}) or {}
        titles |= {p["title"] for p in (d.get("query") or {}).get("prefixsearch", [])}
    vers = []
    for t in titles:
        m = re.search(r"Alpha (\d+)\.(\d+)(?:\.(\d+))?$", t)
        if m:
            vers.append(((int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)), t))
    vers.sort(reverse=True)
    pages = []
    for v, t in vers[:9]:
        txt = wikitext(t)
        if txt.startswith("#REDIRECT"):
            continue
        box = dict(re.findall(r"\|\s*(version|build|date|upcoming)\s*=\s*([^\n|]*)", txt[:800]))
        pages.append({"title": t, "version": box.get("version", ".".join(map(str, v))).strip(), "build": box.get("build", "").strip(),
                      "date": box.get("date", "").strip(), "upcoming": box.get("upcoming", "").strip().lower() == "yes", "text": txt})
    released = [p for p in pages if not p["upcoming"] and p["date"]]
    upcoming = [p for p in pages if p["upcoming"]]
    names = [n for n in dict.fromkeys(ship_names) if n and len(n) > 2]
    mentions, generic = [], []
    for p in released[:6] + upcoming[:1]:
        for line in p["text"].split("\n"):
            if not line.strip().startswith(("*", "#", "|")) and len(line) < 40:
                continue
            low = line.lower()
            if any(re.search(r"\b" + re.escape(n.lower()) + r"\b", low) for n in names):
                c = clean_wiki(line)
                if 15 < len(c) < 600:
                    mentions.append({"version": p["version"], "date": p["date"], "upcoming": p["upcoming"], "text": c})
            elif p in released[:2] and any(k in low for k in generic_kw):
                c = clean_wiki(line)
                if 25 < len(c) < 400 and len(generic) < 16:
                    generic.append({"version": p["version"], "date": p["date"], "text": c})
    latest = released[0] if released else None
    return {
        "latest_live": {k: latest[k] for k in ("version", "build", "date", "title")} if latest else None,
        "upcoming": [{k: p[k] for k in ("version", "title")} for p in upcoming],
        "recent": [{k: p[k] for k in ("version", "date", "title")} for p in released[:6]],
        "ship_mentions": mentions[:30],
        "system_changes": generic,
    }


# ------------------------------------------------------------------ assemble

def build(name, with_uex=True, with_images=True, with_patches=True):
    v, meta, cands = resolve_vehicle(name)
    if not v:
        return None, cands
    ports = walk_ports(v.get("ports"))
    guns = [r for r in ports if r["type"] == "WeaponGun"]
    ords = [r for r in ports if r["type"] in ("Missile", "Bomb")]
    racks = [r for r in ports if r["type"] in ("MissileLauncher", "BombLauncher")]
    cms = [r for r in ports if r["type"] == "WeaponDefensive"]
    comps = [r for r in ports if r["type"] not in ("WeaponGun", "Missile", "Bomb", "MissileLauncher", "BombLauncher",
                                                   "WeaponDefensive", "Turret", "TurretBase")]
    qd_port = next((r for r in ports if r["type"] == "QuantumDrive"), None)
    det = items_parallel({r["uuid"] for r in guns + ords} | ({qd_port["uuid"]} if qd_port else set()))

    weapon_items = {u: slim_weapon(det[u]) for u in {r["uuid"] for r in guns} if det.get(u)}
    ordnance_items = {u: slim_missile(det[u]) for u in {r["uuid"] for r in ords} if det.get(u)}

    # turrets as the game groups them
    turrets = {}
    for kind, rows in (v.get("turrets") or {}).items():
        turrets[kind] = [{"name": t.get("display_name"), "class_name": t.get("class_name"), "hardpoint": t.get("hardpoint_name"),
                          "size": t.get("size"), "mount_count": t.get("mount_count"), "weapon_sizes": t.get("weapon_sizes"),
                          "dps": t.get("dps_total"), "sustained": t.get("sustained_dps_total"), "alpha": t.get("alpha_total"),
                          "pilot_slaveable": bool(t.get("is_pilot_slaveable")), "weapons": [w.get("name") for w in t.get("weapons") or []]}
                         for t in rows or []]

    # upgrade catalogs for editable slots
    gun_sizes = sorted({r["port_size"] or r["size"] for r in guns if r["editable"]} - {None})
    ord_sizes = sorted({r["size"] for r in ords if r["editable"]} - {None})
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        gcat = dict(zip(gun_sizes, ex.map(weapon_catalog, gun_sizes)))
        ocat = dict(zip(ord_sizes, ex.map(missile_catalog, ord_sizes)))
    comp_cat = {}
    for c in comps:
        if c["type"] in UPGRADABLE_COMPONENTS and c["type"] != "QuantumDrive" and c["editable"] and c["size"]:
            comp_cat.setdefault(f"{c['type']}:{c['size']}", component_catalog(c["type"], c["size"]))

    q = dict(v.get("quantum") or {})
    stock_qd = slim_qd(det.get(qd_port["uuid"]) or {}) if qd_port else None
    alts = []
    if qd_port and qd_port.get("size"):
        d = get_json(f"{WIKI_API}/items", {"filter[type]": "QuantumDrive", "filter[size]": qd_port["size"], "limit": 60}) or {}
        alts = [slim_qd(r) for r in d.get("data") or []]
        alts = [a for a in alts if a["fuel_rate"]]
        alts.sort(key=lambda a: -(a["speed_mps"] or 0))

    shield = v.get("shield") or {}
    i = v
    facts = {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "query": name,
        "game_version": v.get("version") or (meta.get("resource") or {}).get("version"),
        "game_data": not v.get("_no_game_data"),
        "identity": {
            "name": i.get("name"), "game_name": i.get("game_name"), "slug": i.get("slug"),
            "manufacturer": (i.get("manufacturer") or {}).get("name"), "manufacturer_code": (i.get("manufacturer") or {}).get("code"),
            "career": i.get("career"), "role": i.get("role"), "size": en(i.get("size")), "size_class": i.get("size_class"),
            "status": en(i.get("production_status")), "description": en(i.get("description")),
            "dimension_m": i.get("dimension"), "mass_kg": i.get("mass_total") or i.get("mass"), "crew": i.get("crew"),
            "seating": i.get("seating"), "max_medical_tier": i.get("max_medical_tier"), "is_vehicle": i.get("is_vehicle"),
            "pledge_url": i.get("pledge_url"), "wiki_page": (i.get("curated_data") or {}).get("page_url"),
            "added_in": (i.get("curated_data") or {}).get("added_in_version"),
        },
        "official": rsi_matrix(v),
        "cargo": {"scu": i.get("cargo_capacity"), "grids": [g.get("scu") for g in i.get("cargo_grids") or []],
                  "max_box": (i.get("cargo_limits") or {}).get("max_scu_box"), "personal_uscu": i.get("vehicle_inventory"),
                  "weapon_storage": i.get("weapon_storage")},
        "durability": {"hull_hp": i.get("health"), "shield_hp": shield.get("hp") or i.get("shield_hp"),
                       "shield_faces": shield.get("face_type") or i.get("shield_face_type"),
                       "shield_regen": shield.get("regeneration"), "shield_regen_time": shield.get("regeneration_time"),
                       "armor": i.get("armor"),
                       "vital": next(({"part": c.get("name"), "hp": c.get("damage_max")} for p in i.get("parts") or []
                                      for c in (p.get("children") or [])[:1] if c.get("damage_max")), None)},
        "mobility": {"speed": i.get("speed"), "agility": i.get("agility"), "hydrogen": i.get("fuel"), "quantum": q},
        "weaponry_summary": i.get("weaponry"),
        "turrets": turrets,
        "guns": group(guns, ["name", "size", "port_size", "root_port", "in_turret", "editable", "uuid"]),
        "weapon_items": weapon_items,
        "racks": group(racks, ["name", "size", "port", "editable"]),
        "ordnance": group(ords, ["name", "size", "type", "parent", "editable", "uuid"]),
        "ordnance_items": ordnance_items,
        "countermeasures": group(cms, ["name", "size"]),
        "components": group(comps, ["type", "name", "size", "grade", "class", "manufacturer", "editable"]),
        "quantum_drive": {"stock": stock_qd, "alternatives": alts, "capacity_scu": q.get("quantum_fuel_capacity")},
        "upgrade_catalogs": {"guns": {str(k): v_ for k, v_ in gcat.items()}, "ordnance": {str(k): v_ for k, v_ in ocat.items()},
                             "components": comp_cat},
        "insurance": i.get("insurance"),
        "loaners": [x.get("name") for x in i.get("loaner") or []],
        "pledge": {"msrp_usd": i.get("msrp"), "warbond_usd": i.get("warbond_price"),
                   "skus": [{k: s.get(k) for k in ("title", "price", "discounted_price", "is_warbond", "is_package", "available", "source", "url", "imported_at")}
                            for s in i.get("skus") or []],
                   "original": {k: (i.get("curated_data") or {}).get(k) for k in ("original_pledge_price", "original_warbond_price", "pledge_availability")}},
        "api_images": i.get("images"),
        "sources": {"wiki_api": f"{WIKI_API}/vehicles/{i.get('slug')}", "wiki_page": (i.get("curated_data") or {}).get("page_url"),
                    "rsi_page": i.get("pledge_url")},
    }
    if with_uex:
        uv = uex_vehicle(v)
        buy, rent = uex_ship_prices(uv["id"]) if uv else ([], [])
        facts["uex"] = {"vehicle_id": uv["id"] if uv else None, "buy": buy, "rent": rent}
        facts["fuel_prices"] = uex_fuel()
        facts["service_commodities"] = uex_service_commodities()
        facts["routes"] = uex_routes()
    if with_images:
        page = (facts["identity"].get("wiki_page") or "").rsplit("/", 1)[-1] or v.get("name")
        rsi = [{"hint": f"RSI official {n + 1}", "url": u, "size": "store"} for n, u in enumerate((facts.get("official") or {}).get("images") or [])]
        facts["image_candidates"] = rsi + wiki_images(urllib.parse.unquote(page))
    if with_patches:
        names = [v.get("name"), (v.get("game_name") or "").split(" ", 1)[-1]]
        facts["patches"] = patch_info(names)
    return facts, []


def fmt(n, d=0):
    try:
        return f"{float(n):,.{d}f}"
    except (TypeError, ValueError):
        return "—"


def summary(f):
    i, d, m = f["identity"], f["durability"], f["mobility"]
    sp, q, w = m.get("speed") or {}, m.get("quantum") or {}, f.get("weaponry_summary") or {}
    o, p = f.get("official") or {}, f.get("patches") or {}
    L = [f"== {i['name']} ({i['manufacturer']}) | game data {f['game_version']} | fetched {f['fetched_at']}"]
    lv = p.get("latest_live") or {}
    L.append(f"latest LIVE patch: {lv.get('version')} ({lv.get('date')}, {lv.get('build')}) | upcoming: {[u['version'] for u in p.get('upcoming') or []]}")
    if lv.get("build") and f["game_version"] and lv["build"] != f["game_version"]:
        L.append(f"!! WARNING: game data {f['game_version']} differs from latest LIVE build {lv['build']} — check what changed.")
    if not f.get("game_data", True):
        L.append("!! NO GAME-FILE DATA: concept or matrix-only ship; figures are design targets.")
    L.append(f"role {i.get('career')}/{i.get('role')} | size {i.get('size')} | status {i.get('status')} | added {i.get('added_in')}")
    if o:
        L.append(f"OFFICIAL: L{o.get('length')} B{o.get('beam')} H{o.get('height')} | cargo {o.get('cargocapacity')} | crew {o.get('min_crew')}-{o.get('max_crew')} | SCM {o.get('scm_speed')} max {o.get('afterburner_speed')}")
    L.append(f"hull {fmt(d.get('hull_hp'))} | shield {fmt(d.get('shield_hp'))} ({d.get('shield_faces')}) | SCM {sp.get('scm')} max {sp.get('max')} | QT fuel {q.get('quantum_fuel_capacity')} SCU range {fmt((q.get('quantum_range') or 0) / 1e9, 1)} Gm")
    L.append(f"wiki DPS: pilot {w.get('pilot_dps')} | turrets(+PDC) {w.get('turret_dps')}")
    for g in f["guns"]:
        wi = f["weapon_items"].get(g["uuid"], {})
        L.append(f"  gun {g['count']}x {g['name']} S{g['size']} [{wi.get('weapon_type')}] dps {wi.get('dps')} ammo {wi.get('ammo')} {'turret' if g['in_turret'] else 'pilot?'} editable={g['editable']} price={wi.get('price_auec')}")
    for kind, rows in (f.get("turrets") or {}).items():
        for t in rows:
            L.append(f"  turret[{kind}] {t['class_name']} dps {t['dps']} slaveable={t['pilot_slaveable']} {t['weapons'][:2]}")
    for g in f["ordnance"]:
        oi = f["ordnance_items"].get(g["uuid"], {})
        L.append(f"  ordnance {g['count']}x {g['name']} S{g['size']} dmg {oi.get('damage')} price {oi.get('price_auec')} in {g['parent']}")
    for c in f["components"]:
        L.append(f"  comp {c['count']}x {c['type']}: {c['name']} S{c['size']} {c['grade'] or ''} editable={c['editable']}")
    uc = f["upgrade_catalogs"]
    L.append(f"upgrade options: guns {[(k, len(v)) for k, v in uc['guns'].items()]} | ordnance {[(k, len(v)) for k, v in uc['ordnance'].items()]} | components {[(k, len(v)) for k, v in uc['components'].items()]}")
    u = f.get("uex") or {}
    L.append(f"in-game buy {u.get('buy', [])[:3]} | rent {u.get('rent', [])[:3]}")
    L.append(f"fuel {f.get('fuel_prices', {})} | services {f.get('service_commodities', {})}")
    L.append(f"pledge msrp ${f['pledge'].get('msrp_usd')} | " + "; ".join(f"{s['title']} ${s['price']} wb={s['is_warbond']} avail={s['available']}" for s in f['pledge']['skus'] if s.get('source') == 'pledge_store'))
    L.append(f"patch mentions of this ship: {len(p.get('ship_mentions') or [])} | system changes: {len(p.get('system_changes') or [])}")
    for mnt in (p.get("ship_mentions") or [])[:12]:
        L.append(f"  [{mnt['version']}] {mnt['text'][:150]}")
    L.append(f"routes {len(f.get('routes') or [])} | images {len(f.get('image_candidates') or [])}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--out")
    ap.add_argument("--no-uex", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-patches", action="store_true")
    a = ap.parse_args()
    facts, cands = build(a.name, not a.no_uex, not a.no_images, not a.no_patches)
    if not facts:
        print(f"No exact match for '{a.name}'.")
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
