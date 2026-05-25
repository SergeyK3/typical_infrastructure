/**
 * Единый контекст редактирования глобального bundle (template_code).
 * Сохраняет выбор в localStorage и ?template_code= для всех страниц справочников.
 */
(function (global) {
  const STORAGE_KEY = 'typical_global_edit_template_code';
  const URL_PARAM = 'template_code';

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, '&#39;');
  }

  function readFromUrl() {
    try {
      const v = new URLSearchParams(global.location.search).get(URL_PARAM);
      return v && String(v).trim() ? String(v).trim() : null;
    } catch (_) {
      return null;
    }
  }

  function getGlobalEditTemplateCode(fallback) {
    const fb = (fallback || 'default').trim() || 'default';
    const fromUrl = readFromUrl();
    if (fromUrl) {
      try {
        global.localStorage.setItem(STORAGE_KEY, fromUrl);
      } catch (_) {}
      return fromUrl;
    }
    try {
      const stored = global.localStorage.getItem(STORAGE_KEY);
      if (stored && String(stored).trim()) return String(stored).trim();
    } catch (_) {}
    return fb;
  }

  function setGlobalEditTemplateCode(code) {
    const c = (code && String(code).trim()) || 'default';
    try {
      global.localStorage.setItem(STORAGE_KEY, c);
    } catch (_) {}
    return c;
  }

  function syncUrl(code, options) {
    const opts = options || {};
    const c = setGlobalEditTemplateCode(code);
    if (opts.replaceState === false) return c;
    try {
      const url = new URL(global.location.href);
      url.searchParams.set(URL_PARAM, c);
      global.history.replaceState(null, '', url.pathname + url.search + url.hash);
    } catch (_) {}
    return c;
  }

  function withTemplateQuery(href, code) {
    const c = code || getGlobalEditTemplateCode();
    const base = String(href || '');
    const hashIdx = base.indexOf('#');
    const hash = hashIdx >= 0 ? base.slice(hashIdx) : '';
    const pathQuery = hashIdx >= 0 ? base.slice(0, hashIdx) : base;
    const qIdx = pathQuery.indexOf('?');
    const path = qIdx >= 0 ? pathQuery.slice(0, qIdx) : pathQuery;
    const params = new URLSearchParams(qIdx >= 0 ? pathQuery.slice(qIdx + 1) : '');
    params.set(URL_PARAM, c);
    const qs = params.toString();
    return path + (qs ? '?' + qs : '') + hash;
  }

  function formatTemplateOptionLabel(t) {
    const name = t.name || t.code;
    const code = t.code;
    const ver = t.version != null ? ' — v' + t.version : '';
    const arch = t.status === 'archived' ? ' [архив]' : '';
    if (name !== code) return name + ' (' + code + ')' + ver + arch;
    return name + ver + arch;
  }

  async function fetchEnterpriseTemplates(includeArchived) {
    const r = await fetch(
      '/api/enterprise-templates?include_archived=' + (includeArchived !== false ? 'true' : 'false')
    );
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  function resolveTemplateCode(rows, preferred, fallback) {
    const fb = (fallback || 'default').trim() || 'default';
    const pref = (preferred || '').trim();
    if (pref && rows.some((t) => t.code === pref)) return pref;
    if (rows.some((t) => t.code === fb)) return fb;
    return rows[0] ? rows[0].code : fb;
  }

  /**
   * Заполняет <select>, восстанавливает сохранённый шаблон, вешает onchange с persist.
   * @returns {Promise<string>} выбранный template_code
   */
  async function bindTemplateSelect(selectEl, options) {
    const opts = options || {};
    const fallback = opts.fallback || 'default';
    const rows = await fetchEnterpriseTemplates(opts.includeArchived !== false);
    let code = resolveTemplateCode(rows, getGlobalEditTemplateCode(fallback), fallback);
    selectEl.innerHTML = rows
      .map(
        (t) =>
          '<option value="' +
          escapeAttr(t.code) +
          '">' +
          escapeHtml(formatTemplateOptionLabel(t)) +
          '</option>'
      )
      .join('');
    selectEl.value = code;
    setGlobalEditTemplateCode(code);
    syncUrl(code);
    renderEditHint(opts.hintId, selectEl);
    selectEl.onchange = () => {
      code = setGlobalEditTemplateCode(selectEl.value);
      syncUrl(code);
      renderEditHint(opts.hintId, selectEl);
      if (typeof opts.onChange === 'function') opts.onChange(code);
    };
    return code;
  }

  function renderEditHint(hintId, selectEl) {
    const el = document.getElementById(hintId || 'globalEditTemplateHint');
    if (!el) return;
    const code =
      selectEl && selectEl.value
        ? String(selectEl.value).trim()
        : getGlobalEditTemplateCode();
    el.textContent =
      'Редактируется шаблон «' +
      code +
      '» — выбор сохраняется при переходе между глобальными справочниками.';
  }

  function applyTemplateLinks(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-global-template-link]').forEach((a) => {
      const href = a.getAttribute('href');
      if (!href) return;
      a.setAttribute('href', withTemplateQuery(href));
    });
  }

  global.GlobalTemplateContext = {
    STORAGE_KEY,
    URL_PARAM,
    getGlobalEditTemplateCode,
    setGlobalEditTemplateCode,
    syncUrl,
    withTemplateQuery,
    formatTemplateOptionLabel,
    fetchEnterpriseTemplates,
    resolveTemplateCode,
    bindTemplateSelect,
    renderEditHint,
    applyTemplateLinks,
  };
})(window);
