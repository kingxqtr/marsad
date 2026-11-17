# ملف بيانات التقرير — marsad-ships/2

ملف JSON واحد يقرؤه القالب. المسودة من `draft_report.py` تملأ معظمه؛ هذا المرجع يشرح معنى كل حقل.
نموذج كامل حقيقي: `assets/example-report.json`.

قواعد عامة:
- النصوص بالعربية، وأسماء السفن والأسلحة والمكونات والمصطلحات بالإنجليزية داخلها. ابدأ كل نص بكلمة عربية متى أمكن.
- الأرقام أرقامًا (`145` لا `"145 m/s"`) في الحقول الرقمية؛ الوحدات يضيفها القالب.
- `null` أو حذف الحقل = غير معروف. الصفر `0` = القيمة صفر فعلًا. «غير منطبق» يُكتب نصًا.
- `tag`: `"official"` (CIG) أو `"community"` (Erkul / SPViewer / Wiki / UEX / Spectrum). لا قيم أخرى.
- الحقول التي تبدأ بـ`_` ملاحظات لك وتُحذف قبل النشر.
- القيم في `yes/no/partial/unknown` تظهر شارات ملونة: نعم / لا / جزئيًا / لم أتمكن من التأكيد.

## meta
| الحقل | المعنى |
|---|---|
| `schema` | `"marsad-ships/2"` |
| `game_version` | مثل `"Alpha 4.10.3 LIVE"` — إلزامي |
| `build` | رقم البناء مثل `"13165946"` |
| `verified_on` | تاريخ التحقق `YYYY-MM-DD` — إلزامي |
| `fx_qar_per_usd` | `3.64` (سعر الربط الرسمي) |
| `gallery_url` / `gallery_label` | زر «افتح المعرض الرسمي للسفينة» — الرابط الوحيد المسموح في الصفحة |
| `show_sources` | `false` افتراضيًا؛ `true` فقط إذا طلب المستخدم إظهار المراجع |
| `sources` | `[{label, url}]` للتوثيق الداخلي |

## ships[] — سفينة واحدة = تقرير، سفينتان أو أكثر = مقارنة

### الهوية العامة
`id`, `name`, `variant` (النسخة المحددة)، `manufacturer`, `manufacturer_code`, `status` (`Flight Ready` / `In Production` / `Concept`)، `role_ar` (الدور بالعربية)، `role_en`, `career_en`, `size_en`, `tagline` (جملة تعريفية).
`sections_tag`: وسم افتراضي لكل قسم `{identity, weapons, dps, durability, mobility, components, cargo}` يظهر سطرًا في آخر القسم، فلا تكرر الوسم على كل صف.

### hero_stats — ستة أرقام المقدمة
`[{label, value, unit?, decimals?}]`. اختر أهم ستة أرقام لهذه السفينة (مثلًا Hull، Shield، ضرر الطيار، ضرر الطاقم، مدى الكوانتم، والرقم المميز: توربيدات أو حمولة أو تعدين).

### quick_specs (اختياري)
إن تُرك فارغًا يبني القالب البطاقة تلقائيًا من بقية الحقول (وهو المفضّل).

### images
`[{url | src, section, caption, kind}]`
- `section`: `hero, uses, identity, weapons, dps, durability, mobility, components, cargo, pricing, opinions, rearm, summary`.
- `url` رابط صورة رسمية؛ البناء ينزلها ويضغطها ويضمّنها. `src` لملف محلي.
- `kind`: `official` أو `concept`.

### uses — القسم 1
`primary`, `secondary[]`, `best_for[]`, `excels[]`, `limited[]`, `solo[]`, `crew_needed[]`, `strengths[]`, `weaknesses[]`, `limits[]`, `notes[]`
`ratings[]`: `[{axis, score (0–10), why}]` — 5 إلى 8 محاور ثابتة الأسماء بين السفن عند المقارنة. تُعرض «تقييمًا وظيفيًا» لا أرقامًا من اللعبة.

### identity — القسم 2
- `rows[]`: `{k, v, tag}` — الاسم الكامل، الشركة، الفئة، الحجم، الأبعاد، الكتلة، الطاقم الرسمي، التشغيل العملي، الحالة.
- `dims`: `{length, beam, height}` بالمتر (رسمية من Ship Matrix إن وُجدت).
- `mass_kg`.
- `crew`: `{min, max, recommended}` — `min` و`max` الرسميان، `recommended` للتشغيل الكامل. لا تضع رقم «يطير بفرد واحد» في `min`؛ اكتبه في `rows`.
- `playable`: هل تعمل فعليًا في LIVE.
- `notes[]`.

### weapons — القسم 3
- `summary`: فقرة تلخص التسليح الأصلي.
- `mounts[]` (كل سلاح أو مجموعة متطابقة في نفس المكان):
  `name, manufacturer, category (Laser Repeater / Laser Cannon / Ballistic Cannon / Ballistic Gatling / Distortion ... ), damage_type (Energy / Ballistic / Distortion), count, size, mount_size, location, mount (Fixed / Gimbal / Manned Turret / Remote Turret / PDC), station, stock, sold_separately, swappable, bespoke (yes/no/unknown), control {pilot, copilot, turret, auto} (true/false/"unknown"), alpha, rpm, dps_each, range_m, speed_mps, capacitor, regen, tag`
  `ammo`: `{needs_refill (true/false — إلزامي), capacity, kind (energy/ballistic/distortion), refill (طريقة التعبئة أو الشحن), cost_auec, cost_note}`
- `ordnance[]` (صواريخ / توربيدات / قنابل):
  `kind (torpedo/missile/bomb), name, manufacturer, size, launchers, per_launcher, loaded (المحمّل فعليًا), max (السعة القصوى), reserve, salvo, damage_each, damage_type, guidance, range_m, lock_time_s, speed_mps, control, comes_with_ship (yes/no/partial/unknown), needs_purchase, first_fill, reload_in_combat, unit_price_auec, shop, tag`
- `countermeasures[]`: `{name, kind (decoy/noise), count}`
- `mistakes[]` (اختياري، وإلا يعرض القالب الأخطاء الثلاثة الشائعة)، `notes[]`.

### dps — القسم 4
- `stations[]`: `{id, label, kind (pilot/copilot/turret/remote/pdc), dps, sustained, crew, on?, auto?}` — كل محطة مرة واحدة فقط.
- `pilot_only`, `crew_only` (دون الطيار ودون PDC), `total` (= الطيار + الطاقم), `crew_for_total`, `burst`, `sustained`, `vs_shield`, `vs_hull`, `distortion`.
- `ordnance[]`: `{name, each, salvo_damage, total}` — جدول منفصل لا يُجمع مع DPS.
- `formula[]`: أسطر المعادلة والمدخلات بالإنجليزية.
- `caveats[]`: ما يؤثر على الضرر الفعلي.

### durability — القسم 5
`hull_hp`, `vital {part, hp}`, `shield {hp, faces (Quadrant/Bubble/Front-Back), regen_per_s, regen_time_s, delay_s | delay_note, stop_note, generators[]}`, `armor {physical, energy, distortion, thermal (مضاعِفات الضرر: 0.75 = يصل 75%), notes}`, `rows[]`, `weak_points[]`, `defenses[]`, `notes[]`.

### mobility — القسم 6
- `speeds {scm, nav, max, boost_fwd, boost_back}`, `accel {zero_to_scm_s, zero_to_max_s, scm_to_zero_s, max_to_zero_s}`, `rotation {pitch, yaw, roll, pitch_boost, yaw_boost, roll_boost}` (درجة/ث).
- `fuel {hydrogen_scu, quantum_scu, scoop, refuel_others, qt_price_auec, h2_price_auec}`.
- `quantum {stock, range_gm, drives[], routes[]}`:
  - `drives[]`: `{name, manufacturer, size, grade, class, speed_mps, spool_s, cooldown_s, fuel_rate (SCU لكل Gm), accel1, accel2, stock (true للأصلي), price_auec}` — تشغّل حاسبة الوقود.
  - `routes[]`: `{sys, a, b, gm}` رحلات جاهزة بين الكواكب.
- `rows[]`, `notes[]`.

### components — القسم 7
`[{type, name, manufacturer, count, size, class, grade, perf, swappable, stock, note, tag}]` و`components_notes[]`.

### cargo — القسم 8
`scu`, `max_box`, `rows[]`, `hangar {rows[], fits[], note}`, `facilities[] {k, v, state (works/partial/planned/unknown/no)}`, `medical {tier, beds}`, `notes[]`.

### pricing — القسم 9
- `pledge[]`: `{label, usd, kind (standalone/warbond/package/ccu/upgrade/module/weapon), available (true/false), note}` — لا تكتب الريال؛ الصفحة تحسبه.
- `default_option`: رقم الخيار الافتراضي في الحاسبة.
- `availability`: التوفر الحالي وتاريخه.
- `tax_note`, `tax_presets[] {label, rate}` (اختياري؛ للقالب قائمة افتراضية خليجية).
- `ingame` (إلزامي): `{buy_auec, available (true/false/null), where[], rent[] {price_auec, days, where}, version_note, note}`.
- `running[]`: `{k, auec | v, note}`.
- `insurance {claim_min, expedite_min, expedite_auec, note}`, `loaners[]`, `notes[]`.

### opinions — القسم 10
`praised[]`, `criticized[]`, `combat`, `solo`, `crew`, `usability`, `bugs[] {title, status, note}`, `satisfaction {score, label}`, `period`, `notes[]`. اذكر تاريخ كل رأي وعدد التصويتات إن وُجد.

### rearm — القسم 11 (الأجزاء التسعة في `references/rearm-guide.md`)
`delivery_qa[] {q, a (yes/no/partial/unknown), note}` (إلزامي)، `delivery_table[] {name, size, included, loaded, max, reserve, to_buy}`، `cases[] {case, result}` (الحالات الخمس)، `check_steps[]`، `auto {best[], steps[] {title, text} (15 نقطة), notes[]}`، `purchase {items[] {name, size, type, unit_auec, qty, shop, location}, steps[], diff[] {k, v}}`، `install_steps[]`، `manual {supported, steps[], notes[]}`، `final_table[] {weapon, comes, buy, refill, max, method, cost}`، `troubleshooting[] {problem, fix}`، `best_way[] {q, a}`.

### summary و unverified
`summary {verdict, score (0–10 وظيفي), readiness, pros[], cons[], best_uses[], for_whom, extras[], key_costs[]}`
`unverified[]`: كل ما لم يتأكد، جملة لكل بند.

## comparison (للمقارنة فقط)
`{winners[] {use, winner, why}, fairness, notes[]}` — راجع `references/comparison.md`.
