// route: /static/shared/theme.js | UI theme: dark (default) | light (+ print via CSS)
(function () {
  'use strict';

  var STORAGE_KEY = 'ui-theme:v1';
  var VALID = { dark: true, light: true };

  function themeFromUrl() {
    try {
      var t = new URLSearchParams(window.location.search).get('theme');
      return VALID[t] ? t : null;
    } catch (_) {
      return null;
    }
  }

  function readStoredTheme() {
    try {
      var t = localStorage.getItem(STORAGE_KEY);
      return VALID[t] ? t : null;
    } catch (_) {
      return null;
    }
  }

  function persistTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (_) {}
  }

  function applyTheme(theme, options) {
    var opts = options || {};
    var next = VALID[theme] ? theme : 'dark';
    var root = document.documentElement;
    root.setAttribute('data-theme', next);
    root.style.colorScheme = next === 'light' ? 'light' : 'dark';
    if (opts.persist !== false) persistTheme(next);
    updateToggleLabels(next);
    if (typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(new CustomEvent('ui-theme-change', { detail: { theme: next } }));
    }
    return next;
  }

  function currentTheme() {
    var t = document.documentElement.getAttribute('data-theme');
    return VALID[t] ? t : 'dark';
  }

  function toggleTheme() {
    return applyTheme(currentTheme() === 'light' ? 'dark' : 'light');
  }

  function updateToggleLabels(theme) {
    var isLight = theme === 'light';
    document.querySelectorAll('[data-ui-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', isLight ? 'true' : 'false');
      btn.title = isLight ? 'Тёмная тема' : 'Светлая тема (скрины и печать)';
      var label = btn.querySelector('[data-ui-theme-label]');
      if (label) label.textContent = isLight ? 'Тёмная тема' : 'Светлая тема';
      var icon = btn.querySelector('[data-ui-theme-icon]');
      if (icon) icon.textContent = isLight ? '☀' : '◐';
    });
  }

  function mountToggle(sidebar) {
    if (!sidebar || sidebar.querySelector('[data-ui-theme-toggle]')) return;
    var bar = document.createElement('div');
    bar.className = 'sidebar-theme-bar';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Тема интерфейса');
    bar.innerHTML =
      '<button type="button" class="ui-theme-toggle" data-ui-theme-toggle aria-pressed="false">' +
      '<span class="ui-theme-toggle-icon" data-ui-theme-icon aria-hidden="true">◐</span>' +
      '<span class="ui-theme-toggle-label" data-ui-theme-label>Светлая тема</span>' +
      '</button>';
    sidebar.appendChild(bar);
    bar.querySelector('[data-ui-theme-toggle]').addEventListener('click', function () {
      toggleTheme();
    });
    updateToggleLabels(currentTheme());
  }

  function mountAllSidebars() {
    document.querySelectorAll('.sidebar').forEach(mountToggle);
  }

  function observeWorkspaceSidebar() {
    var ws = document.getElementById('workspaceSidebar');
    if (!ws || ws.__uiThemeObserved) return;
    ws.__uiThemeObserved = true;
    if (typeof MutationObserver === 'undefined') return;
    new MutationObserver(function () {
      mountToggle(ws);
    }).observe(ws, { childList: true });
  }

  function initFromEnvDefault() {
    var urlTheme = themeFromUrl();
    if (urlTheme) {
      applyTheme(urlTheme);
      return;
    }
    var stored = readStoredTheme();
    if (stored) {
      applyTheme(stored, { persist: false });
      return;
    }
    applyTheme('dark', { persist: false });
    if (typeof fetch !== 'function') return;
    fetch('/api/ui-config', { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (cfg) {
        if (!cfg || readStoredTheme() || themeFromUrl()) return;
        var def = cfg.default_theme;
        if (VALID[def] && def !== currentTheme()) applyTheme(def, { persist: false });
        if (cfg.theme_switch === false) {
          document.querySelectorAll('.sidebar-theme-bar').forEach(function (el) {
            el.hidden = true;
          });
        }
      })
      .catch(function () {});
  }

  initFromEnvDefault();

  window.UiTheme = {
    get: currentTheme,
    apply: applyTheme,
    toggle: toggleTheme,
    mountToggle: mountToggle,
    mountAllSidebars: mountAllSidebars,
  };

  function onReady() {
    mountAllSidebars();
    observeWorkspaceSidebar();
    updateToggleLabels(currentTheme());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }
})();
