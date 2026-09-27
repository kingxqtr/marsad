#!/bin/bash
# One-time: publish Marsad on GitHub Pages (run by نشر-الموقع.command)
cd "$(dirname "$0")/.." || exit 1
GH="$HOME/.marsad-tools/gh"
[ -x "$GH" ] || GH="$(command -v gh)"
if [ -z "$GH" ] || [ ! -x "$GH" ]; then
  echo "أداة GitHub (gh) غير موجودة على الجهاز. اطلب من Claude تنزيلها أولاً."
  read -r -p "اضغط Enter للإغلاق"
  exit 1
fi
REPO_NAME="${1:-marsad}"
SITE_DIR="$HOME/marsad-site"
pause_exit() { echo "$1"; read -r -p "اضغط Enter للإغلاق"; exit 1; }

echo "=== نشر موقع المرصد على الإنترنت ==="
echo

# 1) Sign in to GitHub in the browser (with permission to publish the hourly update workflow)
if ! "$GH" auth status -h github.com >/dev/null 2>&1; then
  echo "بيطلع لك رمز من 8 خانات، وبعدها يفتح GitHub في المتصفح:"
  echo "  انسخ الرمز، والصقه في صفحة GitHub، ثم اضغط Authorize."
  echo
  "$GH" auth login -h github.com -p https -w -s workflow || pause_exit "ما تم تسجيل الدخول. حاول مرة ثانية."
else
  "$GH" auth refresh -h github.com -s workflow >/dev/null 2>&1 || true
fi
"$GH" auth setup-git -h github.com >/dev/null 2>&1
USER_NAME="$("$GH" api user -q .login)" || pause_exit "تعذّر قراءة اسم الحساب."
echo "مسجّل باسم: $USER_NAME"
echo

# 2) Prepare the local copy of the public site (outside iCloud)
python3 scripts/build_data.py >/dev/null || pause_exit "تعذّر تجهيز الأخبار."
mkdir -p "$SITE_DIR"
[ -d "$SITE_DIR/.git" ] || git -C "$SITE_DIR" init -q -b main
git -C "$SITE_DIR" config user.name "$USER_NAME"
git -C "$SITE_DIR" config user.email "$USER_NAME@users.noreply.github.com"
python3 scripts/publish_site.py --prepare >/dev/null || pause_exit "تعذّر تجهيز الملفات."

# 3) Create the public repository once, turn on GitHub Pages, and upload
if ! "$GH" repo view "$USER_NAME/$REPO_NAME" >/dev/null 2>&1; then
  "$GH" repo create "$REPO_NAME" --public \
    --description "المرصد — أخبار Once Human وStar Citizen وأدوات الذكاء الاصطناعي" >/dev/null \
    || pause_exit "تعذّر إنشاء المستودع $REPO_NAME."
fi
enable_pages() {
  "$GH" api -X POST "repos/$USER_NAME/$REPO_NAME/pages" -f build_type=workflow >/dev/null 2>&1 \
    || "$GH" api -X PUT "repos/$USER_NAME/$REPO_NAME/pages" -f build_type=workflow >/dev/null 2>&1
}
enable_pages
git -C "$SITE_DIR" remote remove origin 2>/dev/null
git -C "$SITE_DIR" remote add origin "https://github.com/$USER_NAME/$REPO_NAME.git"
git -C "$SITE_DIR" push -q -u origin main || pause_exit "تعذّر رفع الملفات إلى GitHub."
enable_pages
sleep 3
"$GH" workflow run site.yml -R "$USER_NAME/$REPO_NAME" >/dev/null 2>&1 || true

echo
echo "تم. الموقع العام يكون جاهز خلال دقيقتين على:"
echo "   https://$USER_NAME.github.io/$REPO_NAME/"
echo "ومن الحين كل تحديث ينشر عليه تلقائياً."
echo
read -r -p "اضغط Enter للإغلاق"
