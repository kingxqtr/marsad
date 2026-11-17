# المرصد — Marsad

أخبار Once Human وStar Citizen وأدوات الذكاء الاصطناعي من المصادر الرسمية والمجتمع، بالعربية والإنجليزية.
الموقع: https://kingxqtr.github.io/marsad/

## كيف يعمل (كله في السحابة، بدون الحاجة لأي جهاز)
- **كل 10 دقائق:** GitHub Actions يجلب أحدث العناصر من المصادر الرسمية والمجتمع (`server/refresh.py`) ويعيد نشر الموقع.
- **كل ساعة:** مهمة Claude السحابية (Routine) تبحث وتتحقق وتكتب الأخبار بالعربي والإنجليزي حسب `CLOUD_TASK.md`، ثم تعيد بناء البيانات (`scripts/build_data.py`) وترفعها هنا، فيتحدث الموقع تلقائياً.
- **زر «تحديث» في الموقع:** يجلب فوراً أحدث نسخة من الأخبار الموجودة في السحابة، دون انتظار الفحص التلقائي الذي تجريه الصفحة كل ساعة.

## Layout
- `www/` — the website (GitHub Pages).
- `data/` — research files (`data/research/`, daily updates in `data/research/daily/`) and the built `news.json`.
- `scripts/` — `build_data.py` builds `www/data/news-data.js`; `build_artifact.py` builds the claude.ai copy.
- `server/` — feed fetcher (`refresh.py`), optional translator and local server.
- `.github/workflows/site.yml` — the 10-minute feed refresh, merge of the routine's `claude/**` branches, and Pages deploy.
- `CLOUD_TASK.md` — the instructions the hourly Claude cloud routine follows.
