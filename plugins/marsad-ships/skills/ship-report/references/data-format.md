# ملف بيانات التقرير — marsad-ships/3

`make_report.py` ينشئ الملف كاملًا تقريبًا. هذا شرح الحقول التي قد تحتاج تعديلها. الحقول التي تبدأ بـ`_` ملاحظات لك وتُحذف عند البناء.

## meta
`game_version`, `build`, `patch_date`, `upcoming[]`, `verified_on`, `fx_qar_per_usd` (3.64), `share_url` (يضيفه `--share-url`), `gallery_url`, `sources[] {label, url}`.

## ships[] — سفينة واحدة = تقرير، أكثر = مقارنة
- `role_ar`, `tagline`, `status`, `size_en`, `career_en`, `role_en`.
- `images[] {url, section, caption, kind}` — `section` أحد: hero, verdict, prices, loadout, damage, weapons, rearm, costs, upgrades, mobility, specs, cargo, opinions.
- `verdict {headline, solo, crew, for_whom, best_for[], pros[], cons[], score}`.
- `prices {pledge[] {label, kind: standard|warbond|package, usd, available, note}, history[], ingame {buy_auec, available, where[], rent[], note}, availability, store_checked}` — الأسعار بالدولار فقط؛ الريال والضريبة تحسبهما الصفحة. سطر Warbond يبقى حتى لو `usd: null` مع ملاحظة.
- `loadout {items[], delivery[] {q, a: yes|no|partial|unknown|na, note}, after_claim, snapshot, first_steps[]}`.
- `damage {pilot, crew, total, pdc, stations[], ordnance[], formula[], notes[]}` — `total = pilot + crew`، وPDC خارج الإجمالي.
- `weapons[]`, `ordnance[] {..., control, salvo, unit_price_auec, full_refill_auec}`.
- `rearm {steps[] {t, d}, where[], manual {supported, text}, costs[], full_ordnance_auec, troubleshooting[]}`.
- `costs {calc {...}, weapon_value_auec}` — مدخلات حاسبة التكاليف، ومنها `presets` (سيناريوهات قابلة للتعديل).
- `upgrades {slots[], ordnance[], components[], notes[]}`.
- `mobility`, `durability`, `specs[] {k, v, src: official|game|community}`, `components[]`, `cargo`, `opinions`, `patch_watch[]`, `system_changes[]`, `unverified[]`.

## comparison (للمقارنة)
`{winners[] {use, winner, why}, notes[]}`.
