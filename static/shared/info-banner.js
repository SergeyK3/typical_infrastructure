/**
 * Collapsible informational banner for admin sections (Global / Local Admin UX).
 * Persists collapsed state in localStorage; expanded on first visit.
 */
(function (global) {
  'use strict';

  var STORAGE_PREFIX = 'infoBanner.collapsed.';

  var PRESETS = {
    globalAdminAccounts: {
      id: 'globalAdmin.accounts',
      title: 'Назначение раздела',
      summary: 'В этом разделе отображаются все учётные записи организаций и платформенные аккаунты.',
      bodyHtml:
        '<ul class="info-banner-list">'
        + '<li>учётные записи сотрудников организаций создаются и сопровождаются локальными администраторами;</li>'
        + '<li>Global Admin осуществляет централизованный контроль, аудит и сопровождение учётных записей организаций;</li>'
        + '<li>платформенные аккаунты используются только для администрирования платформы (Global Admin, преемник, делегирование полномочий, аварийный доступ).</li>'
        + '</ul>',
    },
    localAdminAccounts: {
      id: 'localAdmin.accounts',
      title: 'Назначение раздела',
      summary: 'В этом разделе локальный администратор управляет доступом сотрудников своей организации.',
      bodyHtml:
        '<p>Здесь создаются и сопровождаются учётные записи сотрудников, назначаются роли доступа, выполняется блокировка и восстановление доступа.</p>'
        + '<p>Кадровые сведения сотрудников изменяются только в разделе «Сотрудники».</p>',
    },
  };

  function storageKey(id) {
    return STORAGE_PREFIX + String(id || '').trim();
  }

  function readCollapsed(storage, id) {
    try {
      return storage.getItem(storageKey(id)) === '1';
    } catch (_) {
      return false;
    }
  }

  function writeCollapsed(storage, id, collapsed) {
    try {
      storage.setItem(storageKey(id), collapsed ? '1' : '0');
    } catch (_) { /* ignore */ }
  }

  function applyCollapsed(dom, collapsed) {
    if (!dom || !dom.root) return;
    dom.root.classList.toggle('is-collapsed', !!collapsed);
    if (dom.details) dom.details.hidden = !!collapsed;
    if (dom.toggleBtn) {
      dom.toggleBtn.textContent = collapsed ? 'Развернуть' : 'Свернуть';
      dom.toggleBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }
  }

  function createBannerDom(options) {
    var title = options.title || 'Назначение раздела';
    var summary = options.summary || '';
    var bodyHtml = options.bodyHtml || '';

    var root = document.createElement('div');
    root.className = 'info-banner';
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', title);

    var header = document.createElement('div');
    header.className = 'info-banner-header';

    var headerText = document.createElement('div');
    headerText.className = 'info-banner-header-text';

    var heading = document.createElement('h3');
    heading.className = 'info-banner-title';
    heading.textContent = title;
    headerText.appendChild(heading);

    if (summary) {
      var summaryEl = document.createElement('p');
      summaryEl.className = 'info-banner-summary';
      summaryEl.textContent = summary;
      headerText.appendChild(summaryEl);
    }

    var toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'btn btn-secondary btn-sm info-banner-toggle';
    toggleBtn.textContent = 'Свернуть';
    toggleBtn.setAttribute('aria-expanded', 'true');

    header.appendChild(headerText);
    header.appendChild(toggleBtn);
    root.appendChild(header);

    var details = null;
    if (bodyHtml) {
      details = document.createElement('div');
      details.className = 'info-banner-details';
      details.innerHTML = bodyHtml;
      root.appendChild(details);
    }

    return { root: root, details: details, toggleBtn: toggleBtn, id: options.id };
  }

  function mount(options) {
    var container = options && options.container;
    var id = options && options.id;
    if (!container || !id) return null;

    var dom = createBannerDom(options);
    var storage = options.storage || (typeof localStorage !== 'undefined' ? localStorage : null);

    if (options.insertBefore) {
      container.insertBefore(dom.root, options.insertBefore);
    } else {
      container.appendChild(dom.root);
    }

    if (dom.toggleBtn && storage && dom.details) {
      applyCollapsed(dom, readCollapsed(storage, id));
      dom.toggleBtn.addEventListener('click', function () {
        var next = !dom.root.classList.contains('is-collapsed');
        writeCollapsed(storage, id, next);
        applyCollapsed(dom, next);
      });
    } else if (dom.toggleBtn && !dom.details) {
      dom.toggleBtn.hidden = true;
    }

    return dom;
  }

  function mountPreset(container, presetKey, opts) {
    opts = opts || {};
    var preset = PRESETS[presetKey];
    if (!preset || !container) return null;
    return mount(Object.assign({}, preset, opts, { container: container }));
  }

  var api = {
    STORAGE_PREFIX: STORAGE_PREFIX,
    PRESETS: PRESETS,
    storageKey: storageKey,
    readCollapsed: readCollapsed,
    writeCollapsed: writeCollapsed,
    applyCollapsed: applyCollapsed,
    mount: mount,
    mountPreset: mountPreset,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  global.InfoBanner = api;
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
