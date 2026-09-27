/* المرصد — app logic (no dependencies).
   Data: window.NEWS_DATA (curated, bilingual) + live items from the refresh server (api/live) or data/live.json. */
(function () {
  'use strict';

  var TAB_IDS = ['once-human', 'star-citizen', 'ai'];
  var PAGE_SIZE = 20;
  var NEW_DAYS = 3;
  var UPCOMING_COUNT = 6;
  var STALE_DAYS = 7;

  var TYPE_ORDER = {
    'once-human': ['update', 'scenario', 'event', 'collab', 'platform', 'announcement', 'community'],
    'star-citizen': ['patch', 'event', 'ship', 'squadron42', 'development', 'community'],
    'ai': ['model', 'product', 'coding', 'media', 'business', 'policy', 'hardware']
  };

  function arDays(n) {
    var m = n % 100;
    if (m >= 3 && m <= 10) return 'أيام';
    if (m >= 11 && m <= 99) return 'يوماً';
    return 'يوم';
  }

  var STR = {
    ar: {
      dir: 'rtl',
      brand: 'المرصد',
      tagline: 'أخبار من المصادر الرسمية والمجتمع',
      skip: 'تخطَّ إلى الأخبار',
      nav: 'الأقسام',
      refresh: 'تحديث',
      refreshing: 'جارٍ التحديث…',
      refreshTip: {
        server: 'جلب آخر الأخبار الآن من المصادر الرسمية والمجتمع',
        'static': 'تحميل أحدث نسخة منشورة من الأخبار',
        file: 'إعادة تحميل ملف الأخبار',
        unknown: 'تحديث الأخبار'
      },
      langBtn: 'EN',
      langLabel: 'Switch to English',
      toDark: 'تفعيل الوضع الداكن',
      toLight: 'تفعيل الوضع الفاتح',
      tabs: { 'once-human': 'ونس هيومن', 'star-citizen': 'ستار سيتيزن', ai: 'أدوات الذكاء الاصطناعي' },
      tabsShort: { 'once-human': 'ونس هيومن', 'star-citizen': 'ستار سيتيزن', ai: 'الذكاء الاصطناعي' },
      eyebrow: { 'once-human': 'Once Human', 'star-citizen': 'Star Citizen · Squadron 42', ai: 'AI Tools' },
      desc: {
        'once-human': 'لعبة البقاء في العالم المفتوح من استوديو Starry Studio، مع آخر التحديثات والسيناريوهات والفعاليات والتعاونات.',
        'star-citizen': 'لعبة الفضاء من استوديو Cloud Imperium Games، مع أخبار Squadron 42 والتحديثات والسفن والفعاليات.',
        ai: 'كل جديد أدوات الذكاء الاصطناعي: النماذج والمساعدات، والبرمجة، والأدوات الإبداعية، والشركات والتنظيم.'
      },
      statNews: 'الأخبار',
      statUpcoming: 'قادم',
      statUpdated: 'آخر تحديث',
      upcoming: 'القادم',
      upcomingSub: 'أقرب 6 فعاليات وإصدارات قادمة',
      upEmpty: 'لا توجد فعاليات قادمة معلنة حالياً.',
      latest: 'آخر الأخبار',
      latestSub: function (a, b) { return 'من الأحدث إلى الأقدم · ' + a + ' – ' + b; },
      search: 'ابحث في الأخبار…',
      sourceFilter: 'المصدر',
      typeFilter: 'النوع',
      companyFilter: 'الشركة',
      all: 'الكل',
      official: 'رسمي',
      community: 'مجتمع',
      details: 'التفاصيل',
      copy: 'نسخ',
      share: 'مشاركة',
      original: 'الخبر الأصلي',
      close: 'إغلاق',
      copied: 'تم نسخ الخبر',
      linkCopied: 'تم نسخ الرابط',
      copyFailed: 'تعذّر النسخ تلقائياً — حدّد النص وانسخه يدوياً',
      shareTitle: 'مشاركة الخبر',
      shareDevice: 'مشاركة من الجهاز',
      copyLink: 'نسخ الرابط',
      copyNews: 'نسخ الخبر',
      more: function (n) { return 'عرض المزيد (' + n + ')'; },
      empty: 'لا توجد أخبار تطابق البحث أو الفلاتر.',
      clear: 'مسح الفلاتر',
      today: 'اليوم',
      tomorrow: 'غداً',
      now: 'الآن',
      live: 'جارية',
      inDays: function (n) { return n === 0 ? 'اليوم' : n === 1 ? 'غداً' : n === 2 ? 'بعد يومين' : 'بعد ' + n + ' ' + arDays(n); },
      endsIn: function (n) { return n === 0 ? 'تنتهي اليوم' : n === 1 ? 'تنتهي غداً' : n === 2 ? 'تنتهي بعد يومين' : 'تنتهي بعد ' + n + ' ' + arDays(n); },
      unit: function (n) { return n === 2 ? 'يومان' : arDays(n); },
      confirmed: 'موعد مؤكد',
      expected: 'موعد متوقع',
      featured: 'أبرز',
      fresh: 'جديد',
      sourceLine: function (name, kind) { return 'المصدر: ' + name + ' (' + kind + ')'; },
      sourceLabel: 'المصدر:',
      autoNote: 'جُلب هذا الخبر تلقائياً من المصدر، والنص المعروض مقتطف منه. اقرأه كاملاً من الرابط الأصلي.',
      autoNoteEn: 'جُلب هذا الخبر تلقائياً من المصدر ولم تُكتب نسخته العربية بعد، لذلك يظهر بالإنجليزية.',
      added: function (n) { return n === 1 ? 'أُضيف خبر جديد واحد' : n === 2 ? 'أُضيف خبران جديدان' : 'أُضيف ' + n + ' ' + (n % 100 >= 3 && n % 100 <= 10 ? 'أخبار جديدة' : 'خبراً جديداً'); },
      noNew: 'لا توجد أخبار جديدة الآن — كل شيء محدَّث',
      staticDone: 'تم تحميل أحدث نسخة منشورة من الأخبار',
      fileHint: 'للتحديث المباشر من المصادر شغّل الموقع عبر ملف start.command',
      refreshFailed: 'تعذّر التحديث الآن. تأكد من الاتصال وحاول مرة أخرى.',
      partial: function (n) { return 'لم يستجب ' + (n === 1 ? 'مصدر واحد' : n === 2 ? 'مصدران' : n + ' ' + (n % 100 >= 3 && n % 100 <= 10 ? 'مصادر' : 'مصدراً')); },
      offline: 'تعذّر الوصول إلى المصادر الآن. تأكد من اتصال الإنترنت وحاول مرة أخرى.',
      savedTemp: 'حُفظ الخبر مؤقتاً — هذا المتصفح لا يسمح بالحفظ الدائم',
      results: function (n) { return n === 0 ? 'لا توجد نتائج' : n === 1 ? 'خبر واحد' : n === 2 ? 'خبران' : n + ' ' + (n % 100 >= 3 && n % 100 <= 10 ? 'أخبار' : 'خبراً'); },
      tentative: '(موعد متوقع) ',
      comma: '، ',
      coverage: function (a, b, u) { return 'فترة التغطية: ' + a + ' – ' + b + '. آخر تحديث للبيانات: ' + u + '.'; },
      mode: {
        server: 'وضع مباشر: زر «تحديث» يجلب الأخبار من المصادر الرسمية والمجتمع فوراً.',
        'static': 'نسخة منشورة: زر «تحديث» يحمّل أحدث نسخة من الأخبار.',
        file: 'نسخة محلية: لتفعيل التحديث المباشر شغّل start.command.',
        unknown: ''
      },
      hourly: 'والصفحة تتحقق من الأخبار الجديدة تلقائياً كل ساعة.',
      save: 'حفظ',
      savedBtn: 'محفوظ',
      unsave: 'إزالة من المحفوظة',
      savedOn: 'حُفظ الخبر في «المحفوظة»',
      savedOff: 'أُزيل الخبر من «المحفوظة»',
      savedFilter: 'المحفوظة',
      savedEmpty: 'لا توجد أخبار محفوظة في هذا القسم بعد. اضغط رمز الحفظ أعلى أي خبر لتجده هنا.',
      calendar: 'التقويم',
      calendarTitle: 'إضافة إلى التقويم',
      googleCal: 'Google Calendar',
      icsCal: 'Apple أو Outlook',
      icsDone: 'تم تنزيل ملف التقويم، افتحه لإضافة الموعد',
      around: 'نحو ',
      newSince: function (n) { return n + ' ' + (n === 1 ? 'خبر جديد' : n === 2 ? 'خبران جديدان' : n % 100 >= 3 && n % 100 <= 10 ? 'أخبار جديدة' : 'خبراً جديداً') + ' منذ زيارتك الأخيرة'; },
      translate: {
        ready: 'كتابة النص العربي للأخبار الجديدة: مفعّلة.',
        running: 'جارٍ كتابة النص العربي للأخبار الجديدة…',
        no_sdk: 'الأخبار الجديدة تظهر بالإنجليزية حتى تُفعَّل الترجمة (راجع README).',
        no_key: 'الأخبار الجديدة تظهر بالإنجليزية حتى تُضاف مفاتيح Claude API (راجع README).'
      },
      stale: function (d) { return 'آخر تحديث للأخبار كان قبل ' + (d === 2 ? 'يومين' : d + ' ' + arDays(d)) + '. اضغط «تحديث» لجلب الجديد.'; },
      staleStatic: function (d) { return 'آخر تحديث للأخبار كان قبل ' + (d === 2 ? 'يومين' : d + ' ' + arDays(d)) + '، ويبدو أن التحديث التلقائي متوقف.'; },
      loadError: 'تعذّر تحميل ملف الأخبار (data/news-data.js).',
      types: {
        update: 'تحديث', scenario: 'سيناريو', event: 'فعالية', collab: 'تعاون', platform: 'منصات',
        announcement: 'إعلان', community: 'مجتمع اللاعبين', patch: 'تحديث اللعبة', ship: 'سفن ومركبات',
        squadron42: 'Squadron 42', development: 'تطوير', model: 'نماذج', product: 'منتجات وميزات',
        coding: 'برمجة', media: 'أدوات إبداعية', business: 'أعمال واستثمار', policy: 'تنظيم وقضايا',
        hardware: 'رقائق وأجهزة', release: 'إطلاق', other: 'أخرى'
      }
    },
    en: {
      dir: 'ltr',
      brand: 'Marsad',
      tagline: 'News from official and community sources',
      skip: 'Skip to news',
      nav: 'Sections',
      refresh: 'Refresh',
      refreshing: 'Refreshing…',
      refreshTip: {
        server: 'Fetch the latest news now from official and community sources',
        'static': 'Load the latest published news',
        file: 'Reload the news file',
        unknown: 'Refresh news'
      },
      langBtn: 'ع',
      langLabel: 'التبديل إلى العربية',
      toDark: 'Switch to dark mode',
      toLight: 'Switch to light mode',
      tabs: { 'once-human': 'Once Human', 'star-citizen': 'Star Citizen', ai: 'AI Tools' },
      tabsShort: { 'once-human': 'Once Human', 'star-citizen': 'Star Citizen', ai: 'AI Tools' },
      eyebrow: { 'once-human': 'ونس هيومن', 'star-citizen': 'ستار سيتيزن', ai: 'أدوات الذكاء الاصطناعي' },
      desc: {
        'once-human': 'The open-world survival game from Starry Studio: updates, scenarios, events and collaborations.',
        'star-citizen': 'Cloud Imperium Games’ space sim: patches, ships, events and Squadron 42 news.',
        ai: 'Everything new in AI tools: models and assistants, coding, creative tools, companies and regulation.'
      },
      statNews: 'News',
      statUpcoming: 'Upcoming',
      statUpdated: 'Updated',
      upcoming: 'Coming up',
      upcomingSub: 'The next 6 events and releases',
      upEmpty: 'No announced upcoming events right now.',
      latest: 'Latest news',
      latestSub: function (a, b) { return 'Newest first · ' + a + ' – ' + b; },
      search: 'Search news…',
      sourceFilter: 'Source',
      typeFilter: 'Type',
      companyFilter: 'Company',
      all: 'All',
      official: 'Official',
      community: 'Community',
      details: 'Details',
      copy: 'Copy',
      share: 'Share',
      original: 'Original',
      close: 'Close',
      copied: 'News copied',
      linkCopied: 'Link copied',
      copyFailed: 'Couldn’t copy automatically — select the text and copy it',
      shareTitle: 'Share this story',
      shareDevice: 'Share from device',
      copyLink: 'Copy link',
      copyNews: 'Copy story',
      more: function (n) { return 'Show more (' + n + ')'; },
      empty: 'No news matches your search or filters.',
      clear: 'Clear filters',
      today: 'Today',
      tomorrow: 'Tomorrow',
      now: 'Now',
      live: 'Live',
      inDays: function (n) { return n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : 'In ' + n + ' days'; },
      endsIn: function (n) { return n === 0 ? 'Ends today' : n === 1 ? 'Ends tomorrow' : 'Ends in ' + n + ' days'; },
      unit: function (n) { return n === 1 ? 'day' : 'days'; },
      confirmed: 'Confirmed date',
      expected: 'Expected date',
      featured: 'Top story',
      fresh: 'New',
      sourceLine: function (name, kind) { return 'Source: ' + name + ' (' + kind + ')'; },
      sourceLabel: 'Source:',
      autoNote: 'Fetched automatically from the source; the text shown is an excerpt. Read the full story at the original link.',
      autoNoteEn: 'Fetched automatically from the source.',
      added: function (n) { return n === 1 ? '1 new story added' : n + ' new stories added'; },
      noNew: 'No new stories right now — you’re up to date',
      staticDone: 'Loaded the latest published news',
      fileHint: 'To refresh live from the sources, start the site with start.command',
      refreshFailed: 'Couldn’t refresh right now. Check your connection and try again.',
      partial: function (n) { return n === 1 ? '1 source didn’t respond' : n + ' sources didn’t respond'; },
      offline: 'Couldn’t reach the sources right now. Check your internet connection and try again.',
      savedTemp: 'Saved for this session only — this browser doesn’t allow saving permanently',
      results: function (n) { return n === 0 ? 'No results' : n === 1 ? '1 story' : n + ' stories'; },
      tentative: '(expected) ',
      comma: ', ',
      coverage: function (a, b, u) { return 'Coverage: ' + a + ' – ' + b + '. Data last updated: ' + u + '.'; },
      mode: {
        server: 'Live mode: Refresh pulls news from official and community sources right away.',
        'static': 'Published copy: Refresh loads the latest published news.',
        file: 'Local copy: start start.command to enable live refresh.',
        unknown: ''
      },
      hourly: 'The page also checks for new stories every hour.',
      save: 'Save',
      savedBtn: 'Saved',
      unsave: 'Remove from saved',
      savedOn: 'Story saved',
      savedOff: 'Removed from saved',
      savedFilter: 'Saved',
      savedEmpty: 'No saved stories in this section yet. Tap the bookmark on any story to keep it here.',
      calendar: 'Calendar',
      calendarTitle: 'Add to calendar',
      googleCal: 'Google Calendar',
      icsCal: 'Apple or Outlook',
      icsDone: 'Calendar file downloaded — open it to add the event',
      around: 'Around ',
      newSince: function (n) { return n + ' new ' + (n === 1 ? 'story' : 'stories') + ' since your last visit'; },
      translate: {
        ready: 'Arabic text for new stories: on.',
        running: 'Writing the Arabic text for new stories…',
        no_sdk: 'New stories stay in English until translation is set up (see README).',
        no_key: 'New stories stay in English until Claude API keys are added (see README).'
      },
      stale: function (d) { return 'The news was last updated ' + d + ' days ago. Press Refresh to get the latest.'; },
      staleStatic: function (d) { return 'The news was last updated ' + d + ' days ago; the automatic update seems to be paused.'; },
      loadError: 'Couldn’t load the news file (data/news-data.js).',
      types: {
        update: 'Update', scenario: 'Scenario', event: 'Event', collab: 'Collab', platform: 'Platforms',
        announcement: 'Announcement', community: 'Player community', patch: 'Patch', ship: 'Ships & vehicles',
        squadron42: 'Squadron 42', development: 'Development', model: 'Models', product: 'Products & features',
        coding: 'Coding', media: 'Creative tools', business: 'Business', policy: 'Policy & legal',
        hardware: 'Chips & devices', release: 'Release', other: 'Other'
      }
    }
  };

  /* ---------- state ---------- */

  var state = {
    lang: 'ar',
    tab: 'once-human',
    filter: { type: 'all', source: 'all', company: 'all', q: '' },
    visible: PAGE_SIZE,
    live: [],
    liveUpdatedAt: null,
    mode: 'unknown',
    refreshing: false,
    fresh: new Set(),
    current: null,
    server: null,
    saved: new Set(),
    showSaved: false,
    prevVisit: null
  };

  function S() { return STR[state.lang]; }

  // Returns false when this browser won't keep data (private mode, blocked storage).
  var store = {
    get: function (k) { try { return window.localStorage.getItem('marsad:' + k); } catch (e) { return null; } },
    set: function (k, v) {
      try { window.localStorage.setItem('marsad:' + k, v); return window.localStorage.getItem('marsad:' + k) === v; }
      catch (e) { return false; }
    }
  };

  /* ---------- per-reader memory: saved stories and the previous visit (this browser only) ---------- */

  // Saved stories keep a small copy of themselves, so they stay readable after leaving the 3-month window.
  function loadSaved() {
    state.savedItems = {};
    try {
      var a = JSON.parse(store.get('savedItems') || '{}');
      if (a && typeof a === 'object' && !Array.isArray(a)) {
        Object.keys(a).forEach(function (id) { if (validItem(a[id])) state.savedItems[id] = a[id]; });
      }
      var ids = JSON.parse(store.get('saved') || '[]');  // older format: ids only
      if (Array.isArray(ids)) ids.forEach(function (id) { if (typeof id === 'string' && !state.savedItems[id]) state.savedItems[id] = { id: id }; });
    } catch (e) { /* start empty */ }
    state.saved = new Set(Object.keys(state.savedItems));
  }
  function snapshot(it) {
    var s = { id: it.id, tab: it.tab || state.tab, date: it.date, type: it.type, importance: it.importance,
      sourceType: it.sourceType, sourceName: it.sourceName, url: it.url, company: it.company, tool: it.tool, auto: it.auto,
      translated: it.translated };
    ['ar', 'en'].forEach(function (l) { if (it[l]) s[l] = { title: it[l].title, summary: it[l].summary, details: it[l].details }; });
    return s;
  }
  function toggleSaved(it) {
    var on = !state.saved.has(it.id);
    if (on) { state.saved.add(it.id); state.savedItems[it.id] = snapshot(it); }
    else { state.saved.delete(it.id); delete state.savedItems[it.id]; }
    var kept = store.set('savedItems', JSON.stringify(state.savedItems));
    document.querySelectorAll('[data-save]').forEach(function (b) {
      if (b.getAttribute('data-save') === it.id) paintSave(b, on);
    });
    toast(on ? (kept ? S().savedOn : S().savedTemp) : S().savedOff);
    if (state.showSaved && !on) keepFocus(function () { renderFeed(newsFor(state.tab)); }, 'saved-toggle');
    paintSavedToggle();
  }
  function paintSave(btn, on) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.setAttribute('aria-label', on ? S().unsave : S().save);
    btn.title = on ? S().unsave : S().save;
    btn.querySelector('use').setAttribute('href', on ? '#i-bookmark-on' : '#i-bookmark');
    var label = btn.querySelector('.btn__label');
    if (label) label.textContent = on ? S().savedBtn : S().save;
  }
  function saveButton(it, cls) {
    var b = h('button', { type: 'button', class: cls || 'save', 'data-save': it.id, 'data-fk': 'save:' + it.id, onclick: function () { toggleSaved(it); } }, icon('bookmark'));
    paintSave(b, state.saved.has(it.id));
    return b;
  }

  // The previous visit stays fixed for this whole browsing session, so reloading doesn't clear the "new" marks.
  // "Last seen" is written whenever the page is hidden, and coming back after 30 minutes starts a new visit
  // (phone tabs stay open for weeks).
  var NEW_VISIT_MS = 30 * 60 * 1000;
  function initVisit(fresh) {
    var prev = null;
    try {
      prev = fresh ? null : window.sessionStorage.getItem('marsad:prevVisit');
      if (prev === null) {
        prev = window.localStorage.getItem('marsad:lastVisit') || '';
        window.sessionStorage.setItem('marsad:prevVisit', prev);
      }
      window.localStorage.setItem('marsad:lastVisit', new Date().toISOString());
    } catch (e) { prev = null; }
    var d = prev ? new Date(prev) : null;
    state.prevVisit = d && !isNaN(d) ? d : null;
  }
  function markSeen() {
    try { window.localStorage.setItem('marsad:lastVisit', new Date().toISOString()); } catch (e) { /* ignore */ }
  }
  // "New": added since the reader's previous visit; for a first visit, published in the last few days.
  function isNew(it) {
    if (state.prevVisit) {
      var t = it.addedAt || it.fetchedAt;
      return !!t && new Date(t) > state.prevVisit;
    }
    var age = dayDiff(todayStart(), parseDay(it.date));
    return age >= 0 && age <= NEW_DAYS;
  }

  /* ---------- DOM helpers ---------- */

  function $(id) { return document.getElementById(id); }

  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v == null || v === false) return;
        if (k === 'class') el.className = v;
        else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? '' : v);
      });
    }
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function append(el, kid) {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { append(el, k); }); return; }
    el.append(kid instanceof Node ? kid : String(kid));
  }
  function icon(name, cls) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'ico' + (cls ? ' ' + cls : ''));
    svg.setAttribute('aria-hidden', 'true');
    var use = document.createElementNS(ns, 'use');
    use.setAttribute('href', '#i-' + name);
    svg.appendChild(use);
    return svg;
  }
  // replaceChildren() would print null/undefined as text, so drop them first.
  function setKids(node, kids) { node.replaceChildren.apply(node, kids.filter(function (k) { return k != null && k !== false; })); }
  function dirOf(lang) { return lang === 'ar' ? 'rtl' : 'ltr'; }
  function safeUrl(u) { return typeof u === 'string' && /^https?:\/\//i.test(u) ? u : null; }

  /* ---------- dates ---------- */

  function locale() { return state.lang === 'ar' ? 'ar-u-nu-latn' : 'en-GB'; }
  var fmtCache = {};
  function fmt(key, opts) {
    var k = state.lang + key;
    if (!fmtCache[k]) fmtCache[k] = new Intl.DateTimeFormat(locale(), opts);
    return fmtCache[k];
  }
  function parseDay(s) {
    var p = String(s || '').split('-');
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2] || 1));
  }
  function todayStart() { var n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }
  function dayDiff(a, b) { return Math.round((a - b) / 86400000); }
  // Same day three months earlier, clamped to that month's last day (31 May -> 28/29 Feb), like the build script.
  function windowStart() {
    var t = todayStart();
    var last = new Date(t.getFullYear(), t.getMonth() - 2, 0).getDate();
    return new Date(t.getFullYear(), t.getMonth() - 3, Math.min(t.getDate(), last));
  }
  function localDay(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return null;
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function fmtDate(d, withWeekday) {
    var date = d instanceof Date ? d : parseDay(d);
    return withWeekday
      ? fmt('dw', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(date)
      : fmt('d', { day: 'numeric', month: 'long', year: 'numeric' }).format(date);
  }
  function fmtShort(d) { return fmt('ds', { day: 'numeric', month: 'short' }).format(parseDay(d)); }
  function fmtMonth(key) { return fmt('m', { month: 'long', year: 'numeric' }).format(parseDay(key + '-01')); }
  function fmtRange(a, b) {
    if (!b || b === a) return fmtDate(a, true);
    var f = fmt('d', { day: 'numeric', month: 'long', year: 'numeric' });
    try { return f.formatRange(parseDay(a), parseDay(b)); } catch (e) { return fmtDate(a) + ' – ' + fmtDate(b); }
  }
  function fmtNum(n) { return new Intl.NumberFormat(locale()).format(n); }
  function rtf() { return new Intl.RelativeTimeFormat(locale(), { numeric: 'auto' }); }
  function relDays(d) {
    var diff = dayDiff(parseDay(d), todayStart());
    var a = Math.abs(diff);
    if (a < 7) return rtf().format(diff, 'day');
    if (a < 30) return rtf().format(Math.round(diff / 7), 'week');
    return rtf().format(Math.round(diff / 30), 'month');
  }
  function relTime(date) {
    var diff = (date - new Date()) / 1000;
    var a = Math.abs(diff);
    if (a < 60) return rtf().format(0, 'second');
    if (a < 3600) return rtf().format(Math.round(diff / 60), 'minute');
    if (a < 86400) return rtf().format(Math.round(diff / 3600), 'hour');
    return rtf().format(Math.round(diff / 86400), 'day');
  }
  function countdown(it) {
    var t = todayStart();
    var toStart = dayDiff(parseDay(it.date), t);
    var toEnd = dayDiff(parseDay(it.endDate || it.date), t);
    if (toStart > 0) return { kind: 'future', n: toStart };
    if (toEnd >= 0) return { kind: toStart === 0 && toEnd === 0 ? 'today' : 'ongoing', n: toEnd };
    return { kind: 'past', n: toEnd };
  }
  function countdownText(cd) {
    if (cd.kind === 'future') return S().inDays(cd.n);
    if (cd.kind === 'today') return S().today;
    return S().live + ' · ' + S().endsIn(cd.n);
  }

  /* ---------- data ---------- */

  var ISO = /^\d{4}-\d{2}-\d{2}$/;
  function validItem(it) {
    return it && typeof it.id === 'string' && ISO.test(it.date || '') && safeUrl(it.url) &&
      ((it.ar && it.ar.title) || (it.en && it.en.title));
  }
  function base() { return window.NEWS_DATA || null; }
  function tabData(tab) {
    var b = base();
    var t = b && b.tabs && b.tabs[tab];
    return { news: (t && t.news || []).filter(validItem), upcoming: (t && t.upcoming || []).filter(validItem) };
  }
  // Same rules as server/refresh.py: keep the query (it can be the whole identity, e.g. …/item?id=123),
  // drop only tracking parameters; title keys only for titles specific enough to name one story.
  var TRACKING = /^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|igshid|si|source)$/i;
  function normUrl(u) {
    var m = String(u).match(/^[a-z]+:\/\/([^/?#]*)([^?#]*)(\?[^#]*)?/i);
    if (!m) return String(u).toLowerCase();
    var host = m[1].toLowerCase().replace(/^www\./, '');
    var query = (m[3] || '').slice(1).split('&').filter(function (p) { return p && !TRACKING.test(p.split('=')[0]); }).sort();
    return host + m[2].replace(/\/+$/, '') + (query.length ? '?' + query.join('&') : '');
  }
  function normTitle(t) { return String(t).toLowerCase().replace(/[^a-z0-9؀-ۿ]+/g, ' ').trim(); }
  function itemKeys(it) {
    var k = ['u:' + normUrl(it.url)];
    var t = normTitle(it.originalTitle || (it.en && it.en.title) || '');
    if (t.split(' ').length >= 5) k.push('t:' + t);
    return k;
  }

  var cache = {};
  function newsFor(tab) {
    if (cache[tab]) return cache[tab];
    var out = [];
    var seen = new Set();
    tabData(tab).news.forEach(function (it) { itemKeys(it).forEach(function (k) { seen.add(k); }); out.push(it); });
    state.live.forEach(function (it) {
      if (it.tab !== tab || !validItem(it)) return;
      var keys = itemKeys(it);
      if (keys.some(function (k) { return seen.has(k); })) return;
      keys.forEach(function (k) { seen.add(k); });
      out.push(it);
    });
    var from = windowStart();
    var until = new Date(todayStart().getTime() + 2 * 86400000);
    out = out.filter(function (it) { var d = parseDay(it.date); return d >= from && d < until; });
    out.sort(function (a, b) {
      return b.date < a.date ? -1 : b.date > a.date ? 1 : (b.importance || 1) - (a.importance || 1);
    });
    cache[tab] = out;
    return out;
  }
  function invalidate() { cache = {}; }

  // Up to 2 running events that end within 3 weeks, then the soonest future ones; 6 in total.
  // Long-running events only fill leftover slots.
  function upcomingFor(tab) {
    var list = tabData(tab).upcoming.map(function (it) { return { it: it, cd: countdown(it) }; })
      .filter(function (x) { return x.cd.kind !== 'past'; });
    var byN = function (a, b) { return a.cd.n - b.cd.n; };
    var future = list.filter(function (x) { return x.cd.kind === 'future'; }).sort(byN);
    var current = list.filter(function (x) { return x.cd.kind !== 'future'; }).sort(byN);
    var endingSoon = current.filter(function (x) { return x.cd.n <= 21; }).slice(0, 2);
    var pick = endingSoon.concat(future.slice(0, UPCOMING_COUNT - endingSoon.length));
    if (pick.length < UPCOMING_COUNT) {
      pick = pick.concat(current.filter(function (x) { return endingSoon.indexOf(x) === -1; })
        .slice(0, UPCOMING_COUNT - pick.length));
    }
    return pick;
  }

  function loc(it) {
    var want = state.lang;
    var other = want === 'ar' ? 'en' : 'ar';
    var b = it[want];
    var untranslated = it.auto && it.translated === false;
    if (b && b.title && !(untranslated && want === 'ar')) return Object.assign({ lang: want }, b);
    var o = it[other];
    if (o && o.title) return Object.assign({ lang: other }, o);
    if (b && b.title) return Object.assign({ lang: 'en' }, b);
    return { lang: 'en', title: it.originalTitle || '', summary: '', details: '' };
  }

  function normSearch(s) {
    return String(s || '').toLowerCase()
      .replace(/[ً-ْـ]/g, '')
      .replace(/[إأآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
      .replace(/\s+/g, ' ').trim();
  }
  function searchText(it) {
    if (!it._s) {
      var parts = [it.originalTitle, it.sourceName, it.company, it.tool];
      ['ar', 'en'].forEach(function (l) { if (it[l]) parts.push(it[l].title, it[l].summary, it[l].details); });
      it._s = normSearch(parts.filter(Boolean).join(' '));
    }
    return it._s;
  }
  // The Saved view also shows saved stories that have since left the 3-month window (from their saved copy).
  function withSaved(all) {
    if (!state.showSaved) return all;
    var have = new Set(all.map(function (it) { return it.id; }));
    var extra = Object.keys(state.savedItems).map(function (id) { return state.savedItems[id]; })
      .filter(function (it) { return it.tab === state.tab && !have.has(it.id) && validItem(it); });
    return extra.length ? all.concat(extra).sort(function (a, b) { return b.date < a.date ? -1 : b.date > a.date ? 1 : 0; }) : all;
  }
  // skip: the facet whose own chips are being counted, so each chip shows what clicking it would give.
  function filtered(all, skip) {
    var f = state.filter;
    var q = normSearch(f.q);
    return withSaved(all).filter(function (it) {
      return (!state.showSaved || state.saved.has(it.id)) &&
        (skip === 'type' || f.type === 'all' || it.type === f.type) &&
        (f.source === 'all' || (it.sourceType === 'community' ? 'community' : 'official') === f.source) &&
        (skip === 'company' || f.company === 'all' || it.company === f.company) &&
        (!q || searchText(it).indexOf(q) !== -1);
    });
  }
  function typeLabel(t) { return S().types[t] || (t ? t.charAt(0).toUpperCase() + t.slice(1) : S().types.other); }
  function dataUpdatedAt() {
    var d = [];
    var b = base();
    if (b && b.updatedAt) d.push(new Date(b.updatedAt));
    if (state.liveUpdatedAt) d.push(new Date(state.liveUpdatedAt));
    d = d.filter(function (x) { return !isNaN(x); });
    return d.length ? new Date(Math.max.apply(null, d)) : null;
  }

  /* ---------- rendering ---------- */

  var el = {};

  function render() {
    invalidate();
    renderChrome();
    var all = newsFor(state.tab);
    var up = upcomingFor(state.tab);
    renderIntro(all, up);
    renderUpcoming(up);
    renderFilters(all);
    renderFeed(all);
    renderFooter();
  }

  function renderChrome() {
    var s = S();
    var root = document.documentElement;
    root.lang = state.lang;
    root.dir = s.dir;
    document.title = s.brand;
    document.querySelectorAll('[data-i18n]').forEach(function (node) {
      var v = s[node.getAttribute('data-i18n')];
      if (typeof v === 'string') node.textContent = v;
    });
    el.tabbar.setAttribute('aria-label', s.nav);
    TAB_IDS.forEach(function (t) {
      var btn = $('tab-' + t);
      var selected = t === state.tab;
      btn.setAttribute('aria-selected', selected ? 'true' : 'false');
      btn.tabIndex = selected ? 0 : -1;
      btn.querySelector('.tab__label').textContent = window.matchMedia('(max-width: 719px)').matches ? s.tabsShort[t] : s.tabs[t];
      // Badge: stories added since this reader's previous visit (only once we know when that was).
      var n = state.prevVisit ? newsFor(t).filter(isNew).length : 0;
      var badge = btn.querySelector('.tab__badge');
      badge.hidden = !n;
      badge.textContent = n > 99 ? '99+' : fmtNum(n);
      btn.title = n ? s.tabs[t] + ' — ' + s.newSince(n) : s.tabs[t];
      btn.setAttribute('aria-label', n ? s.tabs[t] + s.comma + s.newSince(n) : s.tabs[t]);
    });
    paintSavedToggle();
    el.panel.setAttribute('aria-labelledby', 'tab-' + state.tab);
    el.brand.setAttribute('href', '#' + state.tab);
    el.q.placeholder = s.search;
    el.q.setAttribute('aria-label', s.search);
    el.langBtn.textContent = s.langBtn;
    el.langBtn.setAttribute('lang', state.lang === 'ar' ? 'en' : 'ar');
    el.langBtn.setAttribute('aria-label', s.langLabel);
    el.langBtn.title = s.langLabel;
    var dark = effectiveTheme() === 'dark';
    el.themeBtn.querySelector('use').setAttribute('href', dark ? '#i-sun' : '#i-moon');
    el.themeBtn.setAttribute('aria-label', dark ? s.toLight : s.toDark);
    el.themeBtn.title = dark ? s.toLight : s.toDark;
    paintRefresh();
    $('d-close').setAttribute('aria-label', s.close);
    $('s-close').setAttribute('aria-label', s.close);
  }

  function renderIntro(all, up) {
    var s = S();
    el.eyebrow.textContent = s.eyebrow[state.tab];
    el.eyebrow.setAttribute('lang', state.lang === 'ar' ? 'en' : 'ar');
    el.introTitle.textContent = s.tabs[state.tab];
    el.introDesc.textContent = s.desc[state.tab];
    var upd = dataUpdatedAt();
    el.stats.replaceChildren(
      stat(s.statNews, fmtNum(all.length)),
      stat(s.statUpcoming, fmtNum(up.length)),
      stat(s.statUpdated, upd ? relTime(upd) : '—', true)
    );
    var staleDays = upd ? dayDiff(todayStart(), new Date(upd.getFullYear(), upd.getMonth(), upd.getDate())) : 0;
    if (!base()) {
      el.notice.hidden = false;
      el.noticeText.textContent = s.loadError;
    } else if (staleDays >= STALE_DAYS) {
      el.notice.hidden = false;
      el.noticeText.textContent = state.mode === 'static' ? s.staleStatic(staleDays) : s.stale(staleDays);
    } else {
      el.notice.hidden = true;
    }
  }
  function stat(label, value, small) {
    return h('div', { class: 'stat' }, h('dt', null, label), h('dd', { class: small ? 'stat__small' : null }, value));
  }

  function renderUpcoming(list) {
    el.upGrid.replaceChildren();
    if (!list.length) {
      el.upGrid.append(h('li', { class: 'up-empty' }, S().upEmpty));
      return;
    }
    list.forEach(function (x) { el.upGrid.append(upCard(x.it, x.cd)); });
  }

  // Estimated dates are shown as estimates: "Around 7 October 2026", or just the month when it's far off.
  function whenText(it) {
    if (it.dateConfidence !== 'expected') return fmtRange(it.date, it.endDate);
    var far = dayDiff(parseDay(it.date), todayStart()) > 60;
    return S().around + (far ? fmtMonth(it.date.slice(0, 7)) : fmtDate(it.date));
  }

  function upCard(it, cd) {
    var s = S();
    var b = loc(it);
    var expected = it.dateConfidence === 'expected';
    var approx = expected ? '~' : '';
    var tile = h('div', { class: 'up__tile', 'aria-hidden': 'true' });
    if (cd.kind === 'future' && cd.n === 2 && state.lang === 'ar' && !expected) {
      tile.append(h('span', { class: 'up__unit' }, 'بعد'), h('span', { class: 'up__word' }, 'يومين'));
    } else if (cd.kind === 'future' && (cd.n >= 2 || state.lang === 'en' || expected)) {
      tile.append(h('span', { class: 'up__num' }, approx + fmtNum(cd.n)), h('span', { class: 'up__unit' }, s.unit(cd.n)));
    } else if (cd.kind === 'future') {
      tile.append(h('span', { class: 'up__word' }, s.tomorrow));
    } else if (cd.kind === 'today') {
      tile.append(h('span', { class: 'up__word' }, s.today));
    } else {
      tile.append(h('span', { class: 'up__word' }, s.now), h('span', { class: 'up__unit' }, s.live));
    }
    var body = h('div', { class: 'up__body' },
      h('p', { class: 'up__date' }, icon('cal'), h('span', null, whenText(it)),
        h('span', { class: 'sr-only' }, ' — ' + countdownText(cd))),
      h('div', { class: 'up__chips' },
        h('span', { class: 'chip chip--type' }, typeLabel(it.type)),
        h('span', { class: 'chip ' + (expected ? 'chip--expected' : 'chip--confirmed') },
          icon(expected ? 'clock' : 'check'), expected ? s.expected : s.confirmed)),
      h('h3', { class: 'up__title', lang: b.lang, dir: dirOf(b.lang) },
        h('button', { type: 'button', 'data-fk': 'title:' + it.id, onclick: function () { openDetails(it, 'upcoming'); } }, b.title)),
      b.summary ? h('p', { class: 'up__summary', lang: b.lang, dir: dirOf(b.lang) }, b.summary) : null,
      b.location ? h('p', { class: 'up__loc' }, icon('pin'), h('span', null, b.location)) : null
    );
    return h('li', { class: 'up' + (expected ? ' up--expected' : ''), id: 'u-' + it.id }, tile, body, actions(it, 'upcoming'));
  }

  function actions(it, kind) {
    var s = S();
    var url = safeUrl(it.url);
    return h('div', { class: 'item__actions' },
      h('button', { type: 'button', class: 'btn btn--text', 'data-fk': 'details:' + it.id, onclick: function () { openDetails(it, kind); } },
        s.details, icon('arrow', 'ico--sm flip-rtl')),
      h('button', { type: 'button', class: 'act', 'data-fk': 'copy:' + it.id, 'aria-label': s.copy, title: s.copy, onclick: function () { copyItem(it); } },
        icon('copy'), h('span', null, s.copy)),
      h('button', { type: 'button', class: 'act', 'data-fk': 'share:' + it.id, 'aria-label': s.share, title: s.share, onclick: function () { openShare(it); } },
        icon('share'), h('span', null, s.share)),
      kind === 'upcoming' ? h('button', { type: 'button', class: 'act', 'data-fk': 'cal:' + it.id, 'aria-label': s.calendarTitle, title: s.calendarTitle, onclick: function () { openCalendar(it); } },
        icon('cal-plus'), h('span', null, s.calendar)) : null,
      url ? h('a', { class: 'act', 'data-fk': 'orig:' + it.id, href: url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': s.original, title: s.original },
        icon('external'), h('span', null, s.original)) : null
    );
  }

  function sourceChip(it) {
    var kind = it.sourceType === 'community' ? 'community' : 'official';
    return h('span', { class: 'chip chip--' + kind, title: it.sourceName || '' },
      icon(kind), h('span', { class: 'chip__text' }, S()[kind] + (it.sourceName ? ' · ' + it.sourceName : '')));
  }

  function renderFilters(all) {
    var s = S();
    var f = state.filter;
    el.sourceSeg.querySelectorAll('[data-source]').forEach(function (btn) {
      btn.setAttribute('aria-checked', btn.getAttribute('data-source') === f.source ? 'true' : 'false');
    });
    el.sourceSeg.querySelectorAll('[data-source]').forEach(function (btn) {
      btn.tabIndex = btn.getAttribute('data-source') === f.source ? 0 : -1;
    });

    // Chips list every type in the tab; each count is what clicking that chip would show with the other filters.
    var inTab = {};
    all.forEach(function (it) { inTab[it.type] = true; });
    if (f.type !== 'all' && !inTab[f.type]) f.type = 'all';
    var typeBase = filtered(all, 'type');
    var counts = {};
    typeBase.forEach(function (it) { counts[it.type] = (counts[it.type] || 0) + 1; });
    var order = (TYPE_ORDER[state.tab] || []).filter(function (t) { return inTab[t]; });
    Object.keys(inTab).forEach(function (t) { if (order.indexOf(t) === -1) order.push(t); });
    el.typeChips.replaceChildren(fchip(s.all, typeBase.length, f.type === 'all', function () { setFilter('type', 'all'); }, 'type:all'));
    order.forEach(function (t) {
      el.typeChips.append(fchip(typeLabel(t), counts[t] || 0, f.type === t, function () { setFilter('type', t); }, 'type:' + t));
    });

    var showCompany = state.tab === 'ai';
    el.companyGroup.hidden = !showCompany;
    if (showCompany) {
      var tabCompanies = {};
      all.forEach(function (it) { if (it.company) tabCompanies[it.company] = (tabCompanies[it.company] || 0) + 1; });
      var companyBase = filtered(all, 'company');
      var cc = {};
      companyBase.forEach(function (it) { if (it.company) cc[it.company] = (cc[it.company] || 0) + 1; });
      var top = Object.keys(tabCompanies).sort(function (a, b) { return tabCompanies[b] - tabCompanies[a] || a.localeCompare(b); }).slice(0, 14);
      if (f.company !== 'all' && top.indexOf(f.company) === -1) top.push(f.company);
      el.companyChips.replaceChildren(fchip(s.all, companyBase.length, f.company === 'all', function () { setFilter('company', 'all'); }, 'company:all'));
      top.forEach(function (c) {
        el.companyChips.append(fchip(c, cc[c] || 0, f.company === c, function () { setFilter('company', c); }, 'company:' + c));
      });
    } else {
      f.company = 'all';
    }
  }
  function fchip(label, count, pressed, onclick, key) {
    return h('button', { type: 'button', class: 'fchip', 'aria-pressed': pressed ? 'true' : 'false', 'data-fk': key, onclick: onclick },
      h('span', null, label), h('span', { class: 'fchip__count' }, fmtNum(count)));
  }
  function setFilter(key, value) {
    state.filter[key] = value;
    state.visible = PAGE_SIZE;
    var all = newsFor(state.tab);
    keepFocus(function () { renderFilters(all); renderFeed(all); });
    announce();
  }

  // Re-rendering replaces buttons; put keyboard focus back on the same control afterwards.
  function keepFocus(fn, fallbackId) {
    var a = document.activeElement;
    var key = a && a.getAttribute ? a.getAttribute('data-fk') : null;
    fn();
    var target = null;
    if (key) {
      var sel = window.CSS && CSS.escape ? CSS.escape(key) : key.replace(/["\\]/g, '\\$&');
      target = document.querySelector('[data-fk="' + sel + '"]');
    }
    if (!target && fallbackId && a && a !== document.body && !document.contains(a)) target = $(fallbackId);
    if (target && target !== document.activeElement) {
      try { target.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
    }
  }
  // A short "N stories" for screen readers after a search or filter change (the list itself isn't announced).
  var announceTimer = null;
  function announce() {
    clearTimeout(announceTimer);
    announceTimer = setTimeout(function () {
      el.feedStatus.textContent = S().results(filtered(newsFor(state.tab)).length);
    }, 400);
  }

  function renderFeed(all) {
    var s = S();
    var list = filtered(all);
    var shown = list.slice(0, state.visible);
    el.newsSub.textContent = s.latestSub(fmtDate(windowStart()), fmtDate(todayStart()));
    el.feed.replaceChildren();
    if (!list.length) {
      var onlySaved = state.showSaved && !state.filter.q && state.filter.type === 'all' &&
        state.filter.source === 'all' && state.filter.company === 'all';
      el.feed.append(h('div', { class: 'empty' }, h('p', null, onlySaved ? s.savedEmpty : s.empty),
        h('button', { type: 'button', class: 'btn', onclick: clearFilters }, s.clear)));
      el.more.hidden = true;
      return;
    }
    var monthCounts = {};
    list.forEach(function (it) { var k = it.date.slice(0, 7); monthCounts[k] = (monthCounts[k] || 0) + 1; });
    var groups = [];
    shown.forEach(function (it) {
      var k = it.date.slice(0, 7);
      if (!groups.length || groups[groups.length - 1].key !== k) groups.push({ key: k, items: [] });
      groups[groups.length - 1].items.push(it);
    });
    groups.forEach(function (g) {
      el.feed.append(h('section', { class: 'month' },
        h('h3', { class: 'month__head' }, h('span', null, fmtMonth(g.key)), h('span', { class: 'month__count' }, fmtNum(monthCounts[g.key]))),
        h('ol', { class: 'items' }, g.items.map(newsItem))));
    });
    var rest = list.length - shown.length;
    el.more.hidden = rest <= 0;
    if (rest > 0) el.more.textContent = s.more(fmtNum(rest));
  }

  function newsItem(it) {
    var s = S();
    var b = loc(it);
    var featured = (it.importance || 1) >= 3;
    var li = h('li', { class: 'item' + (featured ? ' item--featured' : '') + (state.fresh.has(it.id) ? ' is-fresh' : ''), id: 'n-' + it.id },
      saveButton(it),
      h('div', { class: 'item__meta' },
        featured ? h('span', { class: 'chip chip--featured' }, s.featured) : null,
        isNew(it) ? h('span', { class: 'chip chip--new' }, s.fresh) : null,
        h('time', { class: 'item__date', datetime: it.date, title: fmtDate(it.date, true) }, fmtShort(it.date)),
        h('span', { class: 'item__sep', 'aria-hidden': 'true' }),
        h('span', null, relDays(it.date)),
        it.type === 'community' && it.sourceType === 'community' ? null : h('span', { class: 'chip chip--type' }, typeLabel(it.type)),
        sourceChip(it),
        it.company ? h('span', { class: 'chip chip--company', lang: 'en' }, it.company) : null,
        b.lang !== state.lang ? h('span', { class: 'chip chip--lang', lang: 'en' }, b.lang.toUpperCase()) : null
      ),
      h('h3', { class: 'item__title', lang: b.lang, dir: dirOf(b.lang) },
        h('button', { type: 'button', 'data-fk': 'title:' + it.id, onclick: function () { openDetails(it, 'news'); } }, b.title)),
      b.summary ? h('p', { class: 'item__summary', lang: b.lang, dir: dirOf(b.lang) }, b.summary) : null,
      actions(it, 'news')
    );
    return li;
  }

  function renderFooter() {
    var s = S();
    var b = base();
    var upd = dataUpdatedAt();
    el.footCoverage.textContent = s.coverage(fmtDate(windowStart()), fmtDate(todayStart()), upd ? fmtDate(upd) : '—');
    var modeText = s.mode[state.mode] || '';
    if (modeText) modeText += ' ' + s.hourly;
    if (state.mode === 'server' && state.server) {
      var tr = state.server.translating ? 'running' : state.server.translate;
      if (s.translate[tr]) modeText += ' ' + s.translate[tr];
    }
    el.footMode.textContent = modeText;
    el.modeDot.setAttribute('data-mode', state.mode);
    el.modeDot.hidden = !s.mode[state.mode];
    if (!b) el.footCoverage.textContent = s.loadError;
  }

  function paintRefresh() {
    var s = S();
    el.refresh.classList.toggle('is-loading', state.refreshing);
    el.refresh.disabled = state.refreshing;
    el.refresh.setAttribute('aria-busy', state.refreshing ? 'true' : 'false');
    // On phones the label stays short (the spinning icon shows progress) so the header doesn't overflow.
    var phone = window.matchMedia('(max-width: 719px)').matches;
    el.refresh.querySelector('.btn__label').textContent = state.refreshing && !phone ? s.refreshing : s.refresh;
    el.refresh.setAttribute('aria-label', state.refreshing ? s.refreshing : s.refresh);
    el.refresh.title = s.refreshTip[state.mode] || s.refresh;
  }

  function clearFilters() {
    state.filter = { type: 'all', source: 'all', company: 'all', q: '' };
    state.showSaved = false;
    el.q.value = '';
    state.visible = PAGE_SIZE;
    render();
  }

  function paintSavedToggle() {
    var n = newsFor(state.tab).filter(function (it) { return state.saved.has(it.id); }).length;
    el.savedToggle.setAttribute('aria-pressed', state.showSaved ? 'true' : 'false');
    el.savedToggle.querySelector('use').setAttribute('href', state.showSaved ? '#i-bookmark-on' : '#i-bookmark');
    el.savedLabel.textContent = S().savedFilter;
    el.savedCount.textContent = fmtNum(n);
  }

  /* ---------- details ---------- */

  // Paragraphs are separated by blank lines; lines starting with "- " become bullet points.
  function renderProse(container, text) {
    container.replaceChildren();
    String(text || '').replace(/\r/g, '').split(/\n\s*\n/).forEach(function (block) {
      var ul = null;
      var para = null;
      block.split('\n').forEach(function (raw) {
        var line = raw.trim();
        if (!line) return;
        var m = line.match(/^[-•*]\s+(.*)$/);
        if (m) {
          para = null;
          if (!ul) { ul = h('ul'); container.append(ul); }
          ul.append(h('li', null, m[1]));
        } else {
          ul = null;
          if (para) para.append(' ' + line);
          else { para = h('p', null, line); container.append(para); }
        }
      });
    });
  }

  function openDetails(it, kind) {
    state.current = { it: it, kind: kind };
    fillDetails();
    showDialog(el.details);
    setHash('n-' + it.id);
  }

  function fillDetails() {
    if (!state.current) return;
    var s = S();
    var it = state.current.it;
    var kind = state.current.kind;
    var b = loc(it);
    var expected = it.dateConfidence === 'expected';
    setKids(el.dMeta, [
      (it.importance || 1) >= 3 ? h('span', { class: 'chip chip--featured' }, s.featured) : null,
      h('span', { class: 'chip chip--type' }, typeLabel(it.type)),
      sourceChip(it),
      it.company ? h('span', { class: 'chip chip--company', lang: 'en' }, it.company) : null,
      kind === 'upcoming' ? h('span', { class: 'chip ' + (expected ? 'chip--expected' : 'chip--confirmed') },
        icon(expected ? 'clock' : 'check'), expected ? s.expected : s.confirmed) : null
    ]);
    el.dTitle.textContent = b.title;
    el.dTitle.setAttribute('lang', b.lang);
    el.dTitle.setAttribute('dir', dirOf(b.lang));

    var when = [];
    if (kind === 'upcoming') {
      when.push(h('span', null, icon('cal'), whenText(it)));
      var cd = countdown(it);
      if (cd.kind !== 'past') when.push(h('span', null, icon('clock'), countdownText(cd)));
      if (b.location) when.push(h('span', null, icon('pin'), b.location));
    } else {
      when.push(h('span', null, icon('cal'), h('time', { datetime: it.date }, fmtDate(it.date, true))));
      when.push(h('span', null, icon('clock'), relDays(it.date)));
    }
    setKids(el.dWhen, when);

    el.dLede.textContent = b.summary || '';
    el.dLede.hidden = !b.summary;
    el.dLede.setAttribute('lang', b.lang);
    el.dLede.setAttribute('dir', dirOf(b.lang));
    renderProse(el.dBody, b.details || '');
    el.dBody.hidden = !b.details;
    el.dBody.setAttribute('lang', b.lang);
    el.dBody.setAttribute('dir', dirOf(b.lang));

    var notes = [];
    if (b.dateNote) notes.push(b.dateNote);
    if (it.auto) notes.push(b.lang !== state.lang ? s.autoNoteEn : s.autoNote);
    el.dNote.textContent = notes.join(' ');
    el.dNote.hidden = !notes.length;

    var url = safeUrl(it.url);
    var kindLabel = it.sourceType === 'community' ? s.community : s.official;
    el.dSource.replaceChildren(s.sourceLabel + ' ',
      url ? h('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, it.sourceName || url) : (it.sourceName || ''),
      ' (' + kindLabel + ')');

    var extra;
    if (kind === 'upcoming') {
      extra = h('button', { type: 'button', class: 'btn', onclick: function () { openCalendar(it); } }, icon('cal-plus'), s.calendar);
    } else {
      extra = h('button', { type: 'button', class: 'btn', 'data-save': it.id, onclick: function () { toggleSaved(it); } },
        icon('bookmark'), h('span', { class: 'btn__label' }));
      paintSave(extra, state.saved.has(it.id));
    }
    setKids(el.dActions, [
      h('button', { type: 'button', class: 'btn', onclick: function () { copyItem(it); } }, icon('copy'), s.copy),
      h('button', { type: 'button', class: 'btn', onclick: function () { openShare(it); } }, icon('share'), s.share),
      extra,
      url ? h('a', { class: 'btn btn--primary', href: url, target: '_blank', rel: 'noopener noreferrer' }, icon('external'), s.original) : null
    ]);
  }

  /* ---------- dialogs ---------- */

  var lastFocus = null;
  function showDialog(dlg) {
    if (!dlg.open) lastFocus = document.activeElement;
    if (typeof dlg.showModal === 'function') { if (!dlg.open) dlg.showModal(); }
    else dlg.setAttribute('open', '');
    document.body.classList.add('has-dialog');
    var body = dlg.querySelector('.sheet__body');
    if (body) body.scrollTop = 0;
  }
  function closeDialog(dlg) {
    if (!dlg.open) return;
    if (typeof dlg.close === 'function') dlg.close();
    else { dlg.removeAttribute('open'); onDialogClose(dlg); }
  }
  function onDialogClose(dlg) {
    if (!el.details.open && !el.share.open) document.body.classList.remove('has-dialog');
    if (dlg === el.details) {
      state.current = null;
      setHash(state.tab);
    }
    if (lastFocus && document.contains(lastFocus) && !el.details.open) {
      try { lastFocus.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
    }
  }

  /* ---------- copy & share ---------- */

  function shareText(it) {
    var s = S();
    var b = loc(it);
    var kind = it.sourceType === 'community' ? s.community : s.official;
    return [b.title, b.summary, s.sourceLine(it.sourceName || '', kind) + '\n' + it.url].filter(Boolean).join('\n\n');
  }
  function copyItem(it) { copyText(shareText(it), S().copied); }
  function copyText(text, okMsg) {
    var done = function (ok) { toast(ok ? okMsg : S().copyFailed); };
    // Older browsers and plain-http pages (e.g. a phone on the home Wi-Fi) have no clipboard API.
    // iPhones only select text in an editable field, so the helper field isn't read-only.
    var fallback = function () {
      var back = document.activeElement;
      var ta = h('textarea', { 'aria-hidden': 'true' });
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.top = '0';
      ta.style.opacity = '0';
      ta.style.fontSize = '16px';  // stops iOS from zooming in
      (el.share.open ? el.share : el.details.open ? el.details : document.body).append(ta);
      ta.focus();
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.remove();
      if (back && back.focus) { try { back.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
      done(ok);
    };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
        return;
      }
    } catch (e) { /* fall through */ }
    fallback();
  }

  function canNativeShare() {
    var top = true;
    try { top = window.self === window.top; } catch (e) { top = false; }
    return top && typeof navigator.share === 'function';
  }
  function openShare(it) {
    var s = S();
    var b = loc(it);
    var url = safeUrl(it.url) || '';
    var enc = encodeURIComponent;
    el.sTitle.textContent = s.shareTitle;
    el.sHeadline.textContent = b.title;
    el.sHeadline.setAttribute('lang', b.lang);
    el.sHeadline.setAttribute('dir', dirOf(b.lang));
    var opts = [];
    if (canNativeShare()) {
      opts.push(h('button', { type: 'button', class: 'share__opt', onclick: function () {
        navigator.share({ title: b.title, text: b.summary || b.title, url: url })
          .then(function () { closeDialog(el.share); }, function () { /* dismissed */ });
      } }, icon('device'), s.shareDevice));
    }
    opts.push(
      h('a', { class: 'share__opt', href: 'https://wa.me/?text=' + enc(b.title + '\n' + url), target: '_blank', rel: 'noopener noreferrer' }, icon('wa'), 'WhatsApp'),
      h('a', { class: 'share__opt', href: 'https://t.me/share/url?url=' + enc(url) + '&text=' + enc(b.title), target: '_blank', rel: 'noopener noreferrer' }, icon('tg'), 'Telegram'),
      h('a', { class: 'share__opt', href: 'https://x.com/intent/post?text=' + enc(b.title) + '&url=' + enc(url), target: '_blank', rel: 'noopener noreferrer' }, icon('x'), 'X'),
      h('a', { class: 'share__opt', href: 'https://www.facebook.com/sharer/sharer.php?u=' + enc(url), target: '_blank', rel: 'noopener noreferrer' }, icon('fb'), 'Facebook'),
      h('button', { type: 'button', class: 'share__opt', onclick: function () { copyText(url, s.linkCopied); } }, icon('link'), s.copyLink),
      h('button', { type: 'button', class: 'share__opt', onclick: function () { copyText(shareText(it), s.copied); } }, icon('copy'), s.copyNews)
    );
    setKids(el.sGrid, opts);
    showDialog(el.share);
  }

  /* ---------- add to calendar ---------- */

  function ymd(d) {
    return d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
  }
  // All-day event; calendars expect the end date to be the day after the last day.
  function calRange(it) {
    var end = parseDay(it.endDate || it.date);
    return [ymd(parseDay(it.date)), ymd(new Date(end.getFullYear(), end.getMonth(), end.getDate() + 1))];
  }
  function calDetails(it) {
    var b = loc(it);
    return [b.summary, b.dateNote, it.url].filter(Boolean).join('\n\n');
  }
  function calTitle(it) {
    return (it.dateConfidence === 'expected' ? S().tentative : '') + loc(it).title;
  }
  function googleCalUrl(it) {
    var b = loc(it);
    var r = calRange(it);
    var enc = encodeURIComponent;
    return 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=' + enc(calTitle(it)) +
      '&dates=' + r[0] + '/' + r[1] + '&details=' + enc(calDetails(it)) + (b.location ? '&location=' + enc(b.location) : '');
  }
  function icsEscape(s) {
    return String(s || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');
  }
  // iCalendar lines are folded at 75 bytes (Arabic letters take 2 bytes each).
  function icsFold(line) {
    var encoder = new TextEncoder();
    var out = [];
    var cur = '';
    var bytes = 0;
    Array.from(line).forEach(function (ch) {
      var n = encoder.encode(ch).length;
      if (bytes + n > 73) { out.push(cur); cur = ' ' + ch; bytes = 1 + n; } else { cur += ch; bytes += n; }
    });
    out.push(cur);
    return out.join('\r\n');
  }
  function icsText(it) {
    var b = loc(it);
    var r = calRange(it);
    var stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
    return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Marsad//News//AR', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
      'BEGIN:VEVENT', 'UID:' + it.id + '@marsad', 'DTSTAMP:' + stamp,
      'DTSTART;VALUE=DATE:' + r[0], 'DTEND;VALUE=DATE:' + r[1],
      'SUMMARY:' + icsEscape(calTitle(it)), 'DESCRIPTION:' + icsEscape(calDetails(it)),
      it.dateConfidence === 'expected' ? 'STATUS:TENTATIVE' : 'STATUS:CONFIRMED',
      b.location ? 'LOCATION:' + icsEscape(b.location) : null, 'URL:' + (safeUrl(it.url) || ''),
      'END:VEVENT', 'END:VCALENDAR'].filter(Boolean).map(icsFold).join('\r\n') + '\r\n';
  }
  // Pages inside the claude.ai viewer can't start downloads, so the .ics option only shows elsewhere.
  function canDownload() {
    try { return window.self === window.top; } catch (e) { return false; }
  }
  function downloadIcs(it) {
    var blob = new Blob([icsText(it)], { type: 'text/calendar;charset=utf-8' });
    var a = h('a', { href: URL.createObjectURL(blob), download: it.id + '.ics' });
    document.body.append(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
    toast(S().icsDone);
  }
  function openCalendar(it) {
    var s = S();
    var b = loc(it);
    el.sTitle.textContent = s.calendarTitle;
    setKids(el.sHeadline, [b.title, h('span', { class: 'share__when' }, whenText(it))]);
    el.sHeadline.setAttribute('lang', b.lang);
    el.sHeadline.setAttribute('dir', dirOf(b.lang));
    var opts = [h('a', { class: 'share__opt', href: googleCalUrl(it), target: '_blank', rel: 'noopener noreferrer' }, icon('cal-plus'), s.googleCal)];
    if (canDownload()) {
      opts.push(h('button', { type: 'button', class: 'share__opt', onclick: function () { downloadIcs(it); closeDialog(el.share); } },
        icon('cal'), s.icsCal));
    }
    setKids(el.sGrid, opts);
    showDialog(el.share);
  }

  var toastTimer = null;
  function toast(msg) {
    var host = el.share.open ? el.share : el.details.open ? el.details : document.body;
    if (el.toast.parentNode !== host) host.append(el.toast);
    el.toast.textContent = msg;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.hidden = true; }, 3600);
  }

  /* ---------- theme, language, tabs, hash ---------- */

  function effectiveTheme() {
    var attr = document.documentElement.getAttribute('data-theme');
    if (attr === 'dark' || attr === 'light') return attr;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function toggleTheme() {
    var next = effectiveTheme() === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    store.set('theme', next);
    // Keep the phone's browser bar in the chosen theme too.
    document.querySelectorAll('meta[name="theme-color"]').forEach(function (m) {
      m.removeAttribute('media');
      m.setAttribute('content', next === 'dark' ? '#0a0e15' : '#eef1f5');
    });
    renderChrome();
  }
  function setLang(l) {
    state.lang = l === 'en' ? 'en' : 'ar';
    store.set('lang', state.lang);
    fmtCache = {};
    render();
    if (el.details.open) fillDetails();
    if (el.share.open) closeDialog(el.share);
  }
  function setTab(tab, fromHash) {
    if (TAB_IDS.indexOf(tab) === -1) return;
    var changed = tab !== state.tab;
    state.tab = tab;
    store.set('tab', tab);
    document.body.setAttribute('data-tab', tab);
    if (changed) {
      state.filter.type = 'all';
      state.filter.company = 'all';
      state.filter.q = '';
      state.showSaved = false;
      el.q.value = '';
      state.visible = PAGE_SIZE;
    }
    if (!fromHash) setHash(tab);
    render();
    if (changed) window.scrollTo(0, 0);
  }
  function setHash(v) {
    try { history.replaceState(null, '', '#' + v); } catch (e) { /* not allowed here */ }
  }
  function readHash() {
    try { return decodeURIComponent((window.location.hash || '').slice(1)); } catch (e) { return ''; }
  }
  function findItem(id) {
    for (var i = 0; i < TAB_IDS.length; i++) {
      var t = TAB_IDS[i];
      var n = newsFor(t).filter(function (x) { return x.id === id; })[0];
      if (n) return { tab: t, it: n, kind: 'news' };
      var u = tabData(t).upcoming.filter(function (x) { return x.id === id; })[0];
      if (u) return { tab: t, it: u, kind: 'upcoming' };
    }
    return null;
  }
  function applyHash() {
    var v = readHash();
    if (TAB_IDS.indexOf(v) !== -1) {
      if (el.details.open) closeDialog(el.details);
      if (v !== state.tab) setTab(v, true);
      return;
    }
    if (v.slice(0, 2) === 'n-') {
      var found = findItem(v.slice(2));
      if (!found) return;
      if (found.tab !== state.tab) setTab(found.tab, true);
      openDetails(found.it, found.kind);
    }
  }

  /* ---------- refresh ---------- */

  function detectMode() {
    if (window.location.protocol === 'file:') return Promise.resolve('file');
    // The refresh server only ever runs on this Mac or the home network; public copies
    // (GitHub Pages, claude.ai) don't need to ask for it.
    var host = window.location.hostname;
    var local = /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || host === '[::1]' || /\.local$/.test(host);
    if (!local) return Promise.resolve('static');
    return fetch('api/status', { cache: 'no-store', headers: { Accept: 'application/json' } })
      .then(function (r) {
        var ct = r.headers.get('content-type') || '';
        if (!r.ok || ct.indexOf('application/json') === -1) return 'static';
        return r.json().then(function (j) {
          if (j && j.server === true) { state.server = j; return 'server'; }
          return 'static';
        });
      })
      .catch(function () { return 'static'; });
  }

  // While the server writes Arabic/English text for new items, pick the results up as they land.
  var pollTimer = null;
  function liveSig() {
    return state.live.length + ':' + state.live.filter(function (i) { return i.translated; }).length;
  }
  // Keeps checking, more slowly over time, until the server says it has finished (or after 45 minutes).
  function startPoll() {
    if (pollTimer || state.mode !== 'server') return;
    var delay = 8000;
    var started = Date.now();
    var tick = function () {
      var before = liveSig();
      fetch('api/status', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (st) {
          state.server = st;
          return loadLive().then(function () {
            if (liveSig() !== before) keepFocus(function () { render(); if (el.details.open) fillDetails(); });
            if (!st.translating || Date.now() - started > 45 * 60 * 1000) { pollTimer = null; renderFooter(); return; }
            delay = Math.min(delay * 1.5, 60000);
            pollTimer = setTimeout(tick, delay);
          });
        })
        .catch(function () { pollTimer = null; renderFooter(); });
    };
    pollTimer = setTimeout(tick, delay);
  }
  function applyLive(j) {
    if (!j || !Array.isArray(j.items)) return;
    state.live = j.items.filter(function (it) { return validItem(it) && TAB_IDS.indexOf(it.tab) !== -1; })
      .map(function (it) {
        // The exact publish time is kept too; derive the day in this reader's own time zone.
        var day = it.publishedAt ? localDay(it.publishedAt) : null;
        return Object.assign({ auto: true }, it, day ? { date: day } : null);
      });
    state.liveUpdatedAt = j.updatedAt || null;
  }
  function loadLive() {
    var url = state.mode === 'server' ? 'api/live' : 'data/live.json';
    return fetch(url + '?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j) applyLive(j); return !!j; })
      .catch(function () { return false; });
  }
  function reloadBase() {
    return new Promise(function (resolve) {
      var sc = document.createElement('script');
      sc.src = 'data/news-data.js?v=' + Date.now();
      sc.onload = function () { sc.remove(); resolve(true); };
      sc.onerror = function () { sc.remove(); resolve(false); };
      document.body.append(sc);
    });
  }
  function allIds() {
    var ids = [];
    TAB_IDS.forEach(function (t) {
      newsFor(t).forEach(function (it) { ids.push(it.id); });
      tabData(t).upcoming.forEach(function (it) { ids.push(it.id); });
    });
    return ids;
  }
  /* ---------- hourly check while the page is open ---------- */

  var AUTO_CHECK_MS = 60 * 60 * 1000;
  var lastCheck = Date.now();
  function autoCheck() {
    if (state.refreshing) return;
    lastCheck = Date.now();
    renderedDay = todayStart().getTime();
    var before = new Set(allIds());
    var status = state.mode === 'server'
      ? fetch('api/status', { cache: 'no-store' }).then(function (r) { return r.json(); })
        .then(function (st) { state.server = st; }).catch(function () { /* keep the last status */ })
      : Promise.resolve();
    status
      .then(reloadBase)
      .then(function () { return state.mode === 'file' ? null : loadLive(); })
      .then(function () {
        invalidate();
        var added = allIds().filter(function (id) { return !before.has(id); });
        if (added.length) state.fresh = new Set(added);
        // Re-render quietly (corrections, "today"/"yesterday", countdowns), keeping the reader's focus.
        keepFocus(function () { render(); if (el.details.open) fillDetails(); });
        if (added.length) {
          toast(S().added(added.length));
          setTimeout(function () { state.fresh = new Set(); }, 3000);
        }
        if (state.server && state.server.translating) startPoll();
      });
  }
  var renderedDay = 0;
  var hiddenAt = 0;
  function startAutoCheck() {
    renderedDay = todayStart().getTime();
    var due = function () { return Date.now() - lastCheck >= AUTO_CHECK_MS || todayStart().getTime() !== renderedDay; };
    setInterval(function () { if (!document.hidden && due()) autoCheck(); }, 60 * 1000);
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { hiddenAt = Date.now(); markSeen(); return; }
      if (hiddenAt && Date.now() - hiddenAt > NEW_VISIT_MS) {
        initVisit(true);  // back after a while: a new visit, so "new" means new since you last looked
        keepFocus(render);
      }
      if (due()) autoCheck();
    });
    window.addEventListener('pagehide', markSeen);
  }

  function refresh() {
    if (state.refreshing) return;
    lastCheck = Date.now();
    state.refreshing = true;
    paintRefresh();
    invalidate();
    var before = new Set(allIds());
    var failed = 0;
    var offline = false;
    var job;
    if (state.mode === 'server') {
      job = fetch('api/refresh', { method: 'POST', cache: 'no-store', headers: { Accept: 'application/json', 'X-Marsad': '1' } })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (!res.ok || !res.j || !res.j.ok) throw new Error('refresh failed');
          applyLive(res.j.live);
          failed = (res.j.failed || []).length;
          offline = !!res.j.offline;
          if (state.server) state.server.translating = !!res.j.translating;
          if (res.j.translating) startPoll();
          return reloadBase();
        });
    } else {
      job = reloadBase().then(function (ok) {
        if (!ok) throw new Error('reload failed');  // offline phone, or the file is missing
        return state.mode === 'static' ? loadLive() : null;
      });
    }
    job.then(function () {
      invalidate();
      var added = allIds().filter(function (id) { return !before.has(id); });
      state.fresh = new Set(added);
      state.refreshing = false;
      keepFocus(render);
      var msg;
      if (offline) msg = S().offline;
      else if (added.length) msg = S().added(added.length);
      else if (state.mode === 'server') msg = S().noNew;
      else if (state.mode === 'file') msg = S().fileHint;
      else msg = S().staticDone;
      if (failed && !offline) msg += ' · ' + S().partial(failed);
      toast(msg);
      setTimeout(function () { state.fresh = new Set(); }, 3000);
    }).catch(function () {
      state.refreshing = false;
      paintRefresh();
      toast(S().refreshFailed);
    });
  }

  /* ---------- wiring ---------- */

  function bind() {
    el = {
      main: $('main'), panel: $('panel'), feedStatus: $('feed-status'), brand: $('brand'), tabbar: $('tabbar'), refresh: $('refresh-btn'), langBtn: $('lang-btn'), themeBtn: $('theme-btn'),
      eyebrow: $('intro-eyebrow'), introTitle: $('intro-title'), introDesc: $('intro-desc'), stats: $('stats'),
      notice: $('notice'), noticeText: $('notice-text'), upGrid: $('up-grid'), newsSub: $('news-sub'),
      q: $('q'), sourceSeg: $('source-seg'), typeChips: $('type-chips'), companyGroup: $('company-group'), companyChips: $('company-chips'),
      feed: $('feed'), more: $('more-btn'), footCoverage: $('foot-coverage'), footMode: $('foot-mode'), modeDot: $('mode-dot'),
      details: $('details'), dMeta: $('d-meta'), dTitle: $('d-title'), dWhen: $('d-when'), dLede: $('d-lede'), dBody: $('d-body'),
      dNote: $('d-note'), dSource: $('d-source'), dActions: $('d-actions'),
      share: $('share'), sTitle: $('s-title'), sHeadline: $('s-headline'), sGrid: $('s-grid'), toast: $('toast'),
      savedToggle: $('saved-toggle'), savedLabel: $('saved-label'), savedCount: $('saved-count')
    };
    el.savedToggle.addEventListener('click', function () {
      state.showSaved = !state.showSaved;
      state.visible = PAGE_SIZE;
      var all = newsFor(state.tab);
      renderFilters(all);
      renderFeed(all);
      paintSavedToggle();
      announce();
    });

    TAB_IDS.forEach(function (t) {
      $('tab-' + t).addEventListener('click', function () { setTab(t); });
    });
    $('tablist').addEventListener('keydown', function (e) {
      var i = TAB_IDS.indexOf(state.tab);
      var rtl = state.lang === 'ar';
      var next = null;
      if (e.key === 'ArrowRight') next = rtl ? i - 1 : i + 1;
      else if (e.key === 'ArrowLeft') next = rtl ? i + 1 : i - 1;
      else if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = TAB_IDS.length - 1;
      if (next === null) return;
      e.preventDefault();
      next = (next + TAB_IDS.length) % TAB_IDS.length;
      setTab(TAB_IDS[next]);
      $('tab-' + TAB_IDS[next]).focus();
    });
    el.brand.addEventListener('click', function (e) { e.preventDefault(); setTab(state.tab); window.scrollTo(0, 0); });
    el.refresh.addEventListener('click', refresh);
    el.langBtn.addEventListener('click', function () { setLang(state.lang === 'ar' ? 'en' : 'ar'); });
    el.themeBtn.addEventListener('click', toggleTheme);

    var qTimer = null;
    el.q.addEventListener('input', function () {
      clearTimeout(qTimer);
      qTimer = setTimeout(function () {
        state.filter.q = el.q.value;
        state.visible = PAGE_SIZE;
        var all = newsFor(state.tab);
        renderFilters(all);
        renderFeed(all);
        announce();
      }, 160);
    });
    el.sourceSeg.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-source]');
      if (!btn) return;
      setFilter('source', btn.getAttribute('data-source'));
      btn.focus();
    });
    // Radio group keys: arrows move the choice (mirrored in Arabic).
    el.sourceSeg.addEventListener('keydown', function (e) {
      var opts = ['all', 'official', 'community'];
      var i = opts.indexOf(state.filter.source);
      var rtl = state.lang === 'ar';
      var step = e.key === 'ArrowRight' ? (rtl ? -1 : 1) : e.key === 'ArrowLeft' ? (rtl ? 1 : -1)
        : e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      var next = opts[(i + step + opts.length) % opts.length];
      setFilter('source', next);
      el.sourceSeg.querySelector('[data-source="' + next + '"]').focus();
    });
    el.more.addEventListener('click', function () {
      var first = filtered(newsFor(state.tab))[state.visible];
      state.visible += PAGE_SIZE;
      renderFeed(newsFor(state.tab));
      // Continue reading where the new stories start.
      var target = first && document.querySelector('[data-fk="title:' + (window.CSS && CSS.escape ? CSS.escape(first.id) : first.id) + '"]');
      if (target) target.focus();
    });

    [el.details, el.share].forEach(function (dlg) {
      dlg.addEventListener('close', function () { onDialogClose(dlg); });
      // Close from the backdrop only when the press also started there (not after selecting text).
      dlg.addEventListener('pointerdown', function (e) { dlg._downOnBackdrop = e.target === dlg; });
      dlg.addEventListener('click', function (e) {
        if (e.target === dlg && dlg._downOnBackdrop !== false) closeDialog(dlg);
        dlg._downOnBackdrop = null;
      });
    });
    $('d-close').addEventListener('click', function () { closeDialog(el.details); });
    $('s-close').addEventListener('click', function () { closeDialog(el.share); });

    window.addEventListener('hashchange', applyHash);
    var mq = window.matchMedia('(max-width: 719px)');
    var onMq = function () { renderChrome(); };
    if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
    var dm = window.matchMedia('(prefers-color-scheme: dark)');
    if (dm.addEventListener) dm.addEventListener('change', onMq);
  }

  function init() {
    state.lang = store.get('lang') === 'en' ? 'en' : 'ar';
    loadSaved();
    initVisit();
    var hv = readHash();
    var storedTab = store.get('tab');
    state.tab = TAB_IDS.indexOf(hv) !== -1 ? hv : (TAB_IDS.indexOf(storedTab) !== -1 ? storedTab : 'once-human');
    document.body.setAttribute('data-tab', state.tab);
    bind();
    render();
    if (hv.slice(0, 2) === 'n-') applyHash();
    detectMode().then(function (mode) {
      state.mode = mode;
      return mode === 'file' ? null : loadLive();
    }).then(function () {
      render();
      if (el.details.open) fillDetails();
      else if (readHash().slice(0, 2) === 'n-') applyHash();  // a link to an auto-fetched story
      if (state.server && state.server.translating) startPoll();
      startAutoCheck();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
