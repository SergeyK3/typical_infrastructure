/**
 * Единый dropdown «Действия ▾» для строк справочников (глобальных и локальных).
 */
(function (global) {
  'use strict';

  function escapeHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, '&#39;');
  }

  var PRESETS = {
    globalCatalog: [
      { action: 'edit', label: 'Изменить' },
      { action: 'clone', label: 'Копировать' },
      { action: 'copy-to-template', label: 'В шаблон', title: 'В другой шаблон' },
      { action: 'delete', label: 'Удалить', danger: true },
    ],
    editDelete: [
      { action: 'edit', label: 'Изменить' },
      { action: 'delete', label: 'Удалить', danger: true },
    ],
    localPosition: [
      { action: 'assign', label: 'Назначить' },
      { action: 'edit', label: 'Изменить' },
      { action: 'clone', label: 'Копировать', title: 'Добавить ещё одну ставку (код _2, _3…)' },
      { action: 'to-global', label: 'В шаблон', title: 'Скопировать в глобальный шаблон' },
      { action: 'delete', label: 'Удалить', danger: true },
    ],
    localSkill: [
      { action: 'edit', label: 'Изменить' },
      { action: 'clone', label: 'Дублировать', title: 'Создать копию строки навыка' },
      { action: 'to-global', label: 'В шаблон', title: 'Копировать в глобальный справочник' },
      { action: 'delete', label: 'Удалить', danger: true },
    ],
    clientRegulation: [
      { action: 'open', label: 'Открыть' },
      { action: 'edit', label: 'Изменить' },
      { action: 'to-global', label: 'В шаблон', title: 'Скопировать в глобальный шаблон' },
    ],
    localKpiStandalone: [
      { action: 'edit', label: 'Изменить' },
      { action: 'to-global', label: 'В шаблон', title: 'Скопировать в глобальный шаблон' },
      { action: 'delete', label: 'Удалить', danger: true },
    ],
    localKpiRegulation: [
      { action: 'open', label: 'Открыть' },
      { action: 'to-global', label: 'В шаблон', title: 'Скопировать в глобальный шаблон' },
      { action: 'sync', label: 'Синхронизировать', title: 'Добавить из глобального регламента только отсутствующие KPI и инструкции (существующие не меняются)' },
    ],
  };

  var openMenuWrap = null;
  var outsideReady = false;

  function closeAllMenus() {
    document.querySelectorAll('.cra-menu:not(.hidden)').forEach(function (menu) {
      menu.classList.add('hidden');
      var toggle = menu.parentElement && menu.parentElement.querySelector('.cra-toggle');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    });
    openMenuWrap = null;
  }

  function ensureOutsideListener() {
    if (outsideReady) return;
    outsideReady = true;
    document.addEventListener('click', function (e) {
      if (document.querySelector('.modal.show')) return;
      if (e.target.closest('.cra-wrap')) return;
      closeAllMenus();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAllMenus();
    });
  }

  /**
   * @param {Array<{action:string,label:string,title?:string,danger?:boolean,primary?:boolean}>} items
   * @param {{rowKey?:string,attrs?:object,size?:'sm'|'md',label?:string}} [options]
   */
  function render(items, options) {
    if (!items || !items.length) return '<span class="meta">—</span>';
    var opts = options || {};
    var uid = opts.rowKey || ('cra-' + Math.random().toString(36).slice(2, 10));
    var attrs = opts.attrs || {};
    var attrStr = ' data-cra-key="' + escapeAttr(uid) + '"';
    Object.keys(attrs).forEach(function (key) {
      var val = attrs[key];
      if (val == null || val === '') return;
      var attrName = key.replace(/([A-Z])/g, '-$1').toLowerCase().replace(/^-/, '');
      attrStr += ' data-' + escapeAttr(attrName) + '="' + escapeAttr(String(val)) + '"';
    });
    var sizeClass = opts.size === 'sm' ? ' btn-sm' : '';
    var toggleLabel = opts.label || 'Действия ▾';
    var menuItems = items
      .map(function (m) {
        return (
          '<button type="button" class="cra-item' +
          (m.danger ? ' cra-item--danger' : '') +
          (m.primary ? ' cra-item--primary' : '') +
          '" role="menuitem" data-action="' +
          escapeAttr(m.action) +
          '"' +
          (m.title ? ' title="' + escapeAttr(m.title) + '"' : '') +
          '>' +
          escapeHtml(m.label) +
          '</button>'
        );
      })
      .join('');
    return (
      '<span class="cra-wrap row-actions"' +
      attrStr +
      '>' +
      '<button type="button" class="btn btn-secondary cra-toggle' +
      sizeClass +
      '" aria-haspopup="true" aria-expanded="false">' +
      escapeHtml(toggleLabel) +
      '</button>' +
      '<div class="cra-menu hidden" role="menu">' +
      menuItems +
      '</div></span>'
    );
  }

  function preset(name, attrs, options) {
    var items = PRESETS[name];
    if (!items) return '<span class="meta">—</span>';
    var opts = Object.assign({}, options || {}, { attrs: attrs || (options && options.attrs) });
    return render(items, opts);
  }

  function bind(container, handler) {
    if (!container || typeof handler !== 'function') return;
    ensureOutsideListener();
    if (container._craHandler) {
      container.removeEventListener('click', container._craHandler);
    }
    container._craHandler = function (e) {
      var toggle = e.target.closest('.cra-toggle');
      if (toggle) {
        e.stopPropagation();
        var wrap = toggle.closest('.cra-wrap');
        var menu = wrap && wrap.querySelector('.cra-menu');
        if (!menu) return;
        var wasOpen = openMenuWrap === wrap && !menu.classList.contains('hidden');
        closeAllMenus();
        if (!wasOpen) {
          menu.classList.remove('hidden');
          toggle.setAttribute('aria-expanded', 'true');
          openMenuWrap = wrap;
        }
        return;
      }
      var item = e.target.closest('.cra-item');
      if (!item) return;
      e.preventDefault();
      e.stopPropagation();
      var wrapEl = item.closest('.cra-wrap');
      closeAllMenus();
      handler(item.dataset.action, wrapEl, item, e);
    };
    container.addEventListener('click', container._craHandler);
  }

  global.CatalogRowActions = {
    PRESETS: PRESETS,
    render: render,
    preset: preset,
    bind: bind,
    closeAll: closeAllMenus,
  };
})(typeof window !== 'undefined' ? window : globalThis);
