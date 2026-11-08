/**
 * Jeevan Setu — Multilingual Language Manager for Attendant Portal
 * Provides language switching, persistence (localStorage + sessionStorage + backend sync),
 * dynamic DOM translation, placeholder interpolation, and accessible UI widgets.
 */

(function(window) {
  'use strict';

  var STORAGE_KEY = 'jeevan_setu_attendant_lang';
  var DEFAULT_LANG = 'en';

  var SUPPORTED_LANGUAGES = [
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ' },
    { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी' },
    { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்' },
    { code: 'te', name: 'Telugu', nativeName: 'తెలుగు' },
    { code: 'ml', name: 'Malayalam', nativeName: 'മലയാളം' }
  ];

  var LanguageManager = {
    supportedLanguages: SUPPORTED_LANGUAGES,
    currentLang: DEFAULT_LANG,
    isInitialized: false,

    init: function() {
      if (this.isInitialized) return;
      
      // 1. Resolve preferred language from URL param -> localStorage -> sessionStorage -> default
      var resolvedLang = DEFAULT_LANG;
      try {
        var urlParams = new URLSearchParams(window.location.search);
        var urlLang = urlParams.get('lang');
        if (urlLang && this.isSupported(urlLang)) {
          resolvedLang = urlLang;
        } else {
          var local = localStorage.getItem(STORAGE_KEY);
          var session = sessionStorage.getItem(STORAGE_KEY);
          if (local && this.isSupported(local)) {
            resolvedLang = local;
          } else if (session && this.isSupported(session)) {
            resolvedLang = session;
          }
        }
      } catch (e) {
        console.warn('[LanguageManager] Storage access error:', e);
      }

      this.currentLang = resolvedLang;
      this.isInitialized = true;

      // Update HTML lang attribute
      if (document.documentElement) {
        document.documentElement.lang = this.currentLang;
      }

      // Check backend for stored preferences if token is available
      this.syncFromBackend();

      // Translate DOM on initial load
      this.translateDOM();

      // Auto-inject/bind any language selector placeholders
      this.bindSelectors();

      // Listen for dynamic DOM additions
      var self = this;
      if (typeof MutationObserver !== 'undefined') {
        var observer = new MutationObserver(function(mutations) {
          var shouldTranslate = false;
          for (var i = 0; i < mutations.length; i++) {
            if (mutations[i].addedNodes.length > 0) {
              shouldTranslate = true;
              break;
            }
          }
          if (shouldTranslate) {
            self.translateDOM();
          }
        });
        if (document.body) {
          observer.observe(document.body, { childList: true, subtree: true });
        }
      }
    },

    isSupported: function(code) {
      if (!code) return false;
      code = String(code).toLowerCase().trim();
      for (var i = 0; i < SUPPORTED_LANGUAGES.length; i++) {
        if (SUPPORTED_LANGUAGES[i].code === code) return true;
      }
      return false;
    },

    getLanguage: function() {
      return this.currentLang;
    },

    getLanguages: function() {
      return SUPPORTED_LANGUAGES;
    },

    setLanguage: function(langCode, persist) {
      if (typeof persist === 'undefined') persist = true;
      if (!this.isSupported(langCode)) {
        console.warn('[LanguageManager] Unsupported language code:', langCode);
        return;
      }

      var prevLang = this.currentLang;
      this.currentLang = langCode;

      if (document.documentElement) {
        document.documentElement.lang = langCode;
      }

      // 1. Client-side Persistence (localStorage + sessionStorage)
      if (persist) {
        try {
          localStorage.setItem(STORAGE_KEY, langCode);
          sessionStorage.setItem(STORAGE_KEY, langCode);
        } catch (e) {
          console.warn('[LanguageManager] Could not persist to storage:', e);
        }
      }

      // 2. Synchronize to Backend Preferences API
      this.syncToBackend(langCode);

      // 3. Update all UI selector elements
      var selectors = document.querySelectorAll('.attendant-language-select, #attendant-language-select');
      for (var i = 0; i < selectors.length; i++) {
        if (selectors[i].value !== langCode) {
          selectors[i].value = langCode;
        }
      }

      // 4. Translate all registered DOM elements
      this.translateDOM();

      // 5. Fire custom event for dynamic components to re-render
      try {
        var event = new CustomEvent('languageChanged', {
          detail: { language: langCode, previousLanguage: prevLang }
        });
        window.dispatchEvent(event);
      } catch (e) {
        // Fallback for older browsers
        var evt = document.createEvent('CustomEvent');
        evt.initCustomEvent('languageChanged', true, true, { language: langCode, previousLanguage: prevLang });
        window.dispatchEvent(evt);
      }
    },

    t: function(key, params) {
      if (!key) return '';
      var dicts = window.JEEVAN_SETU_TRANSLATIONS || {};
      var langDict = dicts[this.currentLang] || {};
      var fallbackDict = dicts[DEFAULT_LANG] || {};

      var text = langDict[key];
      if (typeof text === 'undefined') {
        text = fallbackDict[key];
      }
      if (typeof text === 'undefined') {
        text = key; // graceful fallback to raw key
      }

      // Parameter replacement: {paramName}
      if (params && typeof params === 'object') {
        for (var p in params) {
          if (Object.prototype.hasOwnProperty.call(params, p)) {
            var val = params[p] !== null && params[p] !== undefined ? params[p] : '';
            text = text.replace(new RegExp('\\{' + p + '\\}', 'g'), val);
          }
        }
      }

      return text;
    },

    translateDOM: function(root) {
      root = root || document;

      // 1. textContent translation
      var elements = root.querySelectorAll('[data-i18n]');
      for (var i = 0; i < elements.length; i++) {
        var el = elements[i];
        var key = el.getAttribute('data-i18n');
        if (key) {
          var params = {};
          var paramsAttr = el.getAttribute('data-i18n-params');
          if (paramsAttr) {
            try {
              params = JSON.parse(paramsAttr);
            } catch(e) {}
          }
          var translated = this.t(key, params);
          if (el.hasAttribute('data-i18n-html')) {
            el.innerHTML = translated;
          } else {
            el.textContent = translated;
          }
        }
      }

      // 2. Placeholder translation
      var placeholders = root.querySelectorAll('[data-i18n-placeholder]');
      for (var j = 0; j < placeholders.length; j++) {
        var pel = placeholders[j];
        var pkey = pel.getAttribute('data-i18n-placeholder');
        if (pkey) {
          pel.setAttribute('placeholder', this.t(pkey));
        }
      }

      // 3. Title translation
      var titles = root.querySelectorAll('[data-i18n-title]');
      for (var k = 0; k < titles.length; k++) {
        var tel = titles[k];
        var tkey = tel.getAttribute('data-i18n-title');
        if (tkey) {
          tel.setAttribute('title', this.t(tkey));
        }
      }

      // 4. Aria-label translation
      var arias = root.querySelectorAll('[data-i18n-aria-label]');
      for (var m = 0; m < arias.length; m++) {
        var ael = arias[m];
        var akey = ael.getAttribute('data-i18n-aria-label');
        if (akey) {
          ael.setAttribute('aria-label', this.t(akey));
        }
      }
    },

    bindSelectors: function() {
      var self = this;
      var selectors = document.querySelectorAll('.attendant-language-select, #attendant-language-select');
      for (var i = 0; i < selectors.length; i++) {
        var sel = selectors[i];
        sel.value = self.currentLang;
        sel.removeEventListener('change', self._handleSelectorChange);
        sel.addEventListener('change', function(e) {
          self.setLanguage(e.target.value);
        });
      }
    },

    createSelectorWidget: function(variant) {
      variant = variant || 'light';
      var isDark = variant === 'dark';

      var container = document.createElement('div');
      container.className = 'relative inline-flex items-center language-selector-wrapper';

      var iconColor = isDark ? 'text-blue-300' : 'text-primary';
      var bgClass = isDark 
        ? 'bg-blue-900/40 hover:bg-blue-900/60 text-blue-100 border-blue-400/30' 
        : 'bg-blue-50/90 hover:bg-blue-100/80 text-blue-900 border-blue-200';

      var html = '<div class="flex items-center gap-1.5 px-2.5 py-1 rounded-full border ' + bgClass + ' transition-all shadow-xs cursor-pointer focus-within:ring-2 focus-within:ring-primary/40">' +
        '<span class="material-symbols-outlined text-[15px] ' + iconColor + ' shrink-0 select-none pointer-events-none">language</span>' +
        '<select aria-label="Select Language" class="attendant-language-select bg-transparent text-[11px] font-bold text-inherit border-none outline-none focus:ring-0 p-0 pr-1 cursor-pointer appearance-none">';

      for (var i = 0; i < SUPPORTED_LANGUAGES.length; i++) {
        var lang = SUPPORTED_LANGUAGES[i];
        var isSelected = lang.code === this.currentLang ? ' selected' : '';
        html += '<option value="' + lang.code + '"' + isSelected + ' class="bg-white text-slate-900 text-xs py-1">' +
          lang.nativeName + ' (' + lang.name + ')' +
          '</option>';
      }

      html += '</select>' +
        '<span class="material-symbols-outlined text-[14px] ' + iconColor + ' shrink-0 select-none pointer-events-none -ml-0.5">expand_more</span>' +
        '</div>';

      container.innerHTML = html;

      var selectEl = container.querySelector('select');
      var self = this;
      if (selectEl) {
        selectEl.addEventListener('change', function(e) {
          self.setLanguage(e.target.value);
        });
      }

      return container;
    },

    syncFromBackend: async function() {
      try {
        var token = sessionStorage.getItem('jeevan_setu_token') || localStorage.getItem('jeevan_setu_token') || '';
        if (!token) return;

        var res = await fetch('/api/v1/attendant/preferences', {
          headers: { 'Authorization': 'Bearer ' + token }
        });
        if (res.ok) {
          var data = await res.json();
          var backendLang = data.preferences && data.preferences.language;
          if (backendLang && this.isSupported(backendLang) && backendLang !== this.currentLang) {
            // Apply language from account
            this.setLanguage(backendLang, true);
          }
        }
      } catch (e) {
        // Silent fallback to local storage
      }
    },

    syncToBackend: async function(langCode) {
      try {
        var token = sessionStorage.getItem('jeevan_setu_token') || localStorage.getItem('jeevan_setu_token') || '';
        if (!token) return;

        await fetch('/api/v1/attendant/preferences', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          },
          body: JSON.stringify({ language: langCode })
        });
      } catch (e) {
        // Non-blocking
      }
    }
  };

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      LanguageManager.init();
    });
  } else {
    LanguageManager.init();
  }

  window.LanguageManager = LanguageManager;
  window.t = function(key, params) {
    return LanguageManager.t(key, params);
  };

})(window);

