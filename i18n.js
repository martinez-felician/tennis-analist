/* Tennis Analyst — translation engine (English <-> Spanish)
 *
 * The app is written in English. Spanish lives in i18n-es.js as a dictionary keyed by the
 * English text (window.TA_ES) plus regex patterns for strings with numbers/names
 * (window.TA_ES_PATTERNS). This file walks the DOM, translates matching text/attributes and
 * keeps doing so when the app inserts new content, so pages and scripts need almost no changes.
 *
 * Language: saved choice (localStorage 'ta-lang') -> browser language (es* => Spanish) -> English.
 * Use window.t('English text') for strings that are not shown in the DOM (alert, confirm...).
 */
(function () {
  'use strict';
  var KEY = 'ta-lang';
  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  var lang = 'en';

  function detect() {
    try {
      var saved = localStorage.getItem(KEY);
      if (saved === 'es' || saved === 'en') return saved;
    } catch (e) {}
    var nav = (navigator.languages && navigator.languages[0]) || navigator.language || 'en';
    return /^es/i.test(nav) ? 'es' : 'en';
  }
  lang = detect();

  function dict() { return window.TA_ES || {}; }
  function patterns() { return window.TA_ES_PATTERNS || []; }

  // Translate one English string (whitespace at the ends is kept).
  function translate(str) {
    if (lang !== 'es' || !str) return str;
    var lead = str.match(/^\s*/)[0];
    var trail = str.match(/\s*$/)[0];
    var core = str.trim().replace(/\s+/g, ' ');
    if (!core) return str;
    var d = dict();
    if (Object.prototype.hasOwnProperty.call(d, core)) return lead + d[core] + trail;
    var p = patterns();
    for (var i = 0; i < p.length; i++) {
      var m = core.match(p[i][0]);
      if (m) return lead + p[i][1].apply(null, m.slice(1).concat([translate])) + trail;
    }
    if (core.indexOf('·') >= 0) {
      var out = core.split('·').map(function (x) {
        var tx = x.trim();
        return tx ? translate(tx) : '';
      }).join(' · ').replace(/^ · /, '· ').replace(/ · $/, ' ·');
      if (out.replace(/\s/g, '') !== core.replace(/\s/g, '')) return lead + out + trail;
    }
    return str;
  }
  window.t = translate;
  window.getLang = function () { return lang; };

  // ---- DOM walking ----
  var textRecs = new WeakMap();   // text node -> {orig, last}
  var attrRecs = new WeakMap();   // element -> {attr: {orig, last}}

  function skipEl(el) {
    if (!el || el.nodeType !== 1) return false;
    var tag = el.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA' || tag === 'CODE') return true;
    return el.hasAttribute && el.hasAttribute('data-no-i18n');
  }
  function inSkipped(node) {
    for (var el = node.nodeType === 1 ? node : node.parentNode; el; el = el.parentNode) {
      if (skipEl(el)) return true;
    }
    return false;
  }

  function doText(node) {
    var cur = node.nodeValue;
    var rec = textRecs.get(node);
    if (rec && cur !== rec.last) rec = null;          // the app rewrote it: new original
    var orig = rec ? rec.orig : cur;
    var want = lang === 'es' ? translate(orig) : orig;
    if (want !== cur) node.nodeValue = want;
    if (want !== orig) textRecs.set(node, { orig: orig, last: want });
    else textRecs.delete(node);
  }

  function doAttrs(el) {
    var recs = attrRecs.get(el) || {};
    var changed = false;
    ATTRS.forEach(function (a) {
      if (!el.hasAttribute(a)) return;
      var cur = el.getAttribute(a);
      var rec = recs[a];
      if (rec && cur !== rec.last) rec = null;
      var orig = rec ? rec.orig : cur;
      var want = lang === 'es' ? translate(orig) : orig;
      if (want !== cur) el.setAttribute(a, want);
      if (want !== orig) { recs[a] = { orig: orig, last: want }; changed = true; }
      else delete recs[a];
    });
    if (changed) attrRecs.set(el, recs); else attrRecs.delete(el);
  }

  function walk(root) {
    if (!root || inSkipped(root)) return;
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1) return;
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1 && skipEl(n)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    doAttrs(root);
    var n;
    while ((n = tw.nextNode())) {
      if (n.nodeType === 3) doText(n); else doAttrs(n);
    }
  }

  var titleOrig = null;
  function doTitle() {
    if (titleOrig === null || document.title !== (lang === 'es' ? translate(titleOrig) : titleOrig)) {
      if (titleOrig === null || document.title !== titleOrig) titleOrig = document.title;
    }
    var want = lang === 'es' ? translate(titleOrig) : titleOrig;
    if (document.title !== want) document.title = want;
  }

  var observer = null;
  function observe() {
    if (observer) observer.disconnect();
    observer = new MutationObserver(function (records) {
      observer.disconnect();
      try {
        records.forEach(function (r) {
          if (r.type === 'characterData') { if (!inSkipped(r.target)) doText(r.target); }
          else if (r.type === 'attributes') { if (!inSkipped(r.target)) doAttrs(r.target); }
          else r.addedNodes.forEach(function (n) { walk(n); });
        });
      } finally { connect(); }
    });
    connect();
  }
  function connect() {
    observer.observe(document.documentElement, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTRS
    });
  }

  function applyAll() {
    if (observer) observer.disconnect();
    walk(document.body);
    doTitle();
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-lang-toggle]').forEach(paintToggle);
    if (observer) connect();
  }

  // ---- Language toggle (EN | ES) ----
  function paintToggle(btn) {
    btn.innerHTML = '<span class="' + (lang === 'en' ? 'on' : '') + '">EN</span><span class="' +
      (lang === 'es' ? 'on' : '') + '">ES</span>';
    btn.setAttribute('aria-label', lang === 'es' ? 'Cambiar idioma' : 'Change language');
  }
  function setLang(l) {
    if (l !== 'en' && l !== 'es') return;
    lang = l;
    try { localStorage.setItem(KEY, l); } catch (e) {}
    applyAll();
    document.dispatchEvent(new CustomEvent('ta-lang-change', { detail: l }));
  }
  window.setLang = setLang;

  function injectToggles() {
    document.querySelectorAll('[data-lang-slot]').forEach(function (slot) {
      if (slot.querySelector('[data-lang-toggle]')) return;
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'lang-toggle';
      b.setAttribute('data-lang-toggle', '');
      b.addEventListener('click', function () { setLang(lang === 'es' ? 'en' : 'es'); });
      slot.appendChild(b);
      paintToggle(b);
    });
  }

  function init() {
    injectToggles();
    applyAll();
    observe();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
