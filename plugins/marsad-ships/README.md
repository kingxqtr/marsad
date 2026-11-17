# مرصد السفن — Marsad Ships (3.0.0)

إضافة (Plugin) واحدة فيها مهارة (Skill) واحدة اسمها `ship-report`. اكتب اسم أي سفينة أو مركبة في Star Citizen، فيجهز Claude تقريرًا عربيًا تفاعليًا محدّثًا لآخر إصدار LIVE وينشره صفحة قابلة للمشاركة.

## التثبيت (اختر طريقة واحدة)

**Claude Code (الويب أو الطرفية):**
```
/plugin marketplace add kingxqtr/marsad
/plugin install marsad-ships@marsad
```

**Claude Cowork:** افتح `dist/marsad-ships.plugin` في محادثة Cowork واضغط زر التثبيت.

**claude.ai (المهارة وحدها):** ارفع `dist/ship-report.zip` من إعدادات المهارات (Skills).

ثبّت بطريقة واحدة فقط، وتأكد أن المهارة القديمة `star-citizen-ship-encyclopedia` محذوفة، حتى لا تعمل نسختان معًا.

## الاستخدام
- اكتب اسم السفينة فقط: `Carrack` أو `قلاديوس` أو `تقرير عن Perseus`.
- للمقارنة: `قارن Perseus مع Hammerhead`.
- لسؤال سريع: «كم ضرر الطيار وحده في Gladius؟» فتأتيك إجابة نصية.
- لتحديث تقرير قديم: «حدّث تقرير Carrack».

## محتوى كل تقرير
الخلاصة (وحدك / مع الطاقم / كم تكلف) · الأسعار Standard وWarbond بالضريبة وبدونها بالدولار والريال القطري وaUEC · التجهيز الافتراضي عند الشراء وهل يأتي معبأ · ضرر الطيار وحده والطاقم والإجمالي · الأسلحة والذخيرة · التعبئة وتكاليفها · حاسبة التكاليف الشاملة · مخطط الترقيات · حاسبة الوقود الكمي · المواصفات · الحمولة · آراء اللاعبين · ما تغيّر في آخر الإصدارات · المصادر · زر مشاركة (رابط، ملخص للواتساب، QR) · وضع فاتح وداكن.

## البنية
```
marsad-ships/
├── .claude-plugin/plugin.json, icon.png
└── skills/ship-report/
    ├── SKILL.md
    ├── scripts/   sc_data.py (بيانات حية) · make_report.py (يحسب التقرير) · build_report.py (يتحقق ويبني الصفحة)
    ├── assets/    template.html (التصميم والحاسبات)
    └── references/ research.md · data-format.md
```
مصادر البيانات: Star Citizen Wiki API (ملفات اللعبة الحالية)، RSI Ship Matrix ومتجر RSI، UEX (أسعار aUEC والوقود والذخيرة والمسافات)، وملاحظات آخر الإصدارات.
