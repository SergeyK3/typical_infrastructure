/**
 * Shared org tree rendering and context menu helpers (global + client workspace).
 */
(function (global) {
  'use strict';

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function parseApiErrorText(text) {
    try {
      const j = JSON.parse(text);
      if (j && j.error) return j.error.message || j.error.code || text;
      if (j && j.detail) {
        if (typeof j.detail === 'string') return j.detail;
        if (j.detail.message) return j.detail.message;
        if (j.detail.code) return j.detail.code;
      }
    } catch (_) {}
    return text;
  }

  function unitTypeLabel(unitType) {
    if (unitType === 'company') return 'компания';
    if (unitType === 'department') return 'отделение';
    if (unitType === 'section') return 'секция';
    return unitType || 'узел';
  }

  function renderOrgUnitNameHtml(name, unitType) {
    const text = escapeHtml(name);
    if (unitType === 'department') {
      return '<strong class="org-ou-name--department">' + text + '</strong>';
    }
    return text;
  }

  function supportsLogGroup(unitType) {
    return unitType === 'department' || unitType === 'section';
  }

  function buildOrgMenuItems(n) {
    const menuItems = [];
    if (n.unit_type === 'department') {
      menuItems.push({ action: 'add-section', label: 'Создать секцию' });
      menuItems.push({ action: 'clone', label: 'Копировать' });
    }
    if (n.unit_type === 'section') {
      menuItems.push({ action: 'clone', label: 'Копировать' });
    }
    if (n.code !== 'company') {
      menuItems.push({ action: 'rename', label: 'Изменить' });
      menuItems.push({ action: 'delete', label: 'Удалить', danger: true });
    }
    return menuItems;
  }

  function renderOrgMenuHtml(n) {
    return buildOrgMenuItems(n)
      .map(function (m) {
        return (
          '<button type="button" class="org-ctx-item' +
          (m.danger ? ' org-ctx-item--danger' : '') +
          '" data-action="' +
          m.action +
          '" data-id="' +
          escapeHtml(n.id) +
          '">' +
          escapeHtml(m.label) +
          '</button>'
        );
      })
      .join('');
  }

  function renderOrgActionsCell(n) {
    if (!buildOrgMenuItems(n).length) return '<span class="meta">—</span>';
    return (
      '<span class="org-row-actions">' +
      '<button type="button" class="btn btn-sm btn-secondary org-menu-btn" data-id="' +
      escapeHtml(n.id) +
      '" title="Действия">⋯</button>' +
      '<div class="org-ctx-menu hidden" data-for="' +
      escapeHtml(n.id) +
      '">' +
      renderOrgMenuHtml(n) +
      '</div></span>'
    );
  }

  function compareOrgRowsLogGroup(a, b) {
    const la = (a.log_group || '').trim();
    const lb = (b.log_group || '').trim();
    if (!la && !lb) return a.code.localeCompare(b.code, 'ru');
    if (!la) return 1;
    if (!lb) return -1;
    const g = la.localeCompare(lb, 'ru');
    return g !== 0 ? g : a.code.localeCompare(b.code, 'ru');
  }

  function sortOrgTableRows(rows, mode) {
    const list = (rows || []).slice();
    if (mode === 'sort_order') {
      list.sort(function (a, b) {
        const so = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
        return so !== 0 ? so : a.code.localeCompare(b.code, 'ru');
      });
      return list;
    }
    if (mode === 'log_group') {
      list.sort(compareOrgRowsLogGroup);
      return list;
    }
    return list;
  }

  function renderOrgTableActionsCell(n) {
    if (n.code === 'company') return '<span class="meta">—</span>';
    const id = escapeHtml(n.id);
    const parts = [
      '<button type="button" class="btn btn-sm btn-secondary org-act-btn" data-action="rename" data-id="' +
        id +
        '" title="Изменить">Изм.</button>',
    ];
    if (n.unit_type === 'department') {
      parts.push(
        '<button type="button" class="btn btn-sm btn-secondary org-act-btn" data-action="clone" data-id="' +
          id +
          '" title="Копировать отделение">Коп.</button>'
      );
    }
    parts.push(
      '<button type="button" class="btn btn-sm btn-danger org-act-btn" data-action="delete" data-id="' +
        id +
        '" title="Удалить">Уд.</button>'
    );
    return '<span class="org-table-actions">' + parts.join('') + '</span>';
  }

  function renderOrgTableActionsCell(n) {
    const parts = [];
    if (n.code !== 'company') {
      parts.push(
        '<button type="button" class="btn btn-sm btn-secondary org-act-btn" data-action="rename" data-id="' +
          escapeHtml(n.id) +
          '" title="Изменить">Изм.</button>'
      );
    }
    if (n.unit_type === 'department' || n.unit_type === 'section') {
      parts.push(
        '<button type="button" class="btn btn-sm btn-secondary org-act-btn" data-action="clone" data-id="' +
          escapeHtml(n.id) +
          '" title="Копировать">Коп.</button>'
      );
    }
    if (n.code !== 'company') {
      parts.push(
        '<button type="button" class="btn btn-sm btn-danger org-act-btn" data-action="delete" data-id="' +
          escapeHtml(n.id) +
          '" title="Удалить">Уд.</button>'
      );
    }
    if (!parts.length) return '<span class="meta">—</span>';
    return '<span class="org-table-actions">' + parts.join('') + '</span>';
  }

  /**
   * @param {Array} rows
   * @param {string} mode — tree | sort_order | log_group
   */
  function sortOrgTableRows(rows, mode) {
    const list = (rows || []).slice();
    if (mode === 'sort_order') {
      return list.sort(function (a, b) {
        const sa = a.sort_order != null ? a.sort_order : 0;
        const sb = b.sort_order != null ? b.sort_order : 0;
        return sa - sb || String(a.code).localeCompare(String(b.code));
      });
    }
    if (mode === 'log_group') {
      function lgKey(n) {
        if (supportsLogGroup(n.unit_type) && n.log_group) return String(n.log_group).toLowerCase();
        return '\uffff';
      }
      return list.sort(function (a, b) {
        const cmp = lgKey(a).localeCompare(lgKey(b));
        return cmp || String(a.code).localeCompare(String(b.code));
      });
    }
    return list;
  }

  /**
   * @param {object} opts
   * @param {Array} opts.rows — плоский список узлов (порядок как в дереве)
   */
  function renderOrgTableHtml(opts) {
    const rows = opts.rows || [];
    const body = rows
      .map(function (n) {
        const lg =
          supportsLogGroup(n.unit_type) && n.log_group
            ? escapeHtml(n.log_group)
            : '<span class="meta">—</span>';
        return (
          '<tr data-unit-id="' +
          escapeHtml(n.id) +
          '" data-unit-type="' +
          escapeHtml(n.unit_type || '') +
          '" data-unit-code="' +
          escapeHtml(n.code) +
          '">' +
          '<td class="td-code"><code>' +
          escapeHtml(n.code) +
          '</code></td>' +
          '<td class="td-name">' +
          renderOrgUnitNameHtml(n.name, n.unit_type) +
          '</td>' +
          '<td class="td-parent">' +
          (n.parent_code
            ? '<code>' + escapeHtml(n.parent_code) + '</code>'
            : '<span class="meta">—</span>') +
          '</td>' +
          '<td>' +
          escapeHtml(unitTypeLabel(n.unit_type)) +
          '</td>' +
          '<td class="td-log-group">' +
          lg +
          '</td>' +
          '<td class="td-sort num">' +
          escapeHtml(String(n.sort_order != null ? n.sort_order : 0)) +
          '</td>' +
          '<td class="td-actions">' +
          renderOrgTableActionsCell(n) +
          '</td></tr>'
        );
      })
      .join('');
    return (
      '<div class="org-table-wrap">' +
      '<table class="org-data-table">' +
      '<thead><tr>' +
      '<th>Код узла</th>' +
      '<th>Название</th>' +
      '<th>Код родителя</th>' +
      '<th>Тип</th>' +
      '<th>Лог. группа</th>' +
      '<th class="num">Сорт.</th>' +
      '<th class="th-actions">Действия</th>' +
      '</tr></thead><tbody>' +
      body +
      '</tbody></table></div>'
    );
  }

  /**
   * @param {object} opts
   * @param {Array} opts.nodes
   * @param {function} opts.onAction - (action, node) => void
   * @param {function} [opts.extraBadges] - (node) => string HTML
   */
  function renderOrgTreeHtml(opts) {
    const extraBadges = opts.extraBadges || function () { return ''; };

    function render(nodes, level) {
      if (!nodes || !nodes.length) return '';
      return nodes
        .map(function (n) {
          const ch = render(n.children || [], level + 1);
          const type = unitTypeLabel(n.unit_type);
          const badges =
            (supportsLogGroup(n.unit_type) && n.log_group
              ? ' <span class="unit-type" title="Логическая группа">[' + escapeHtml(n.log_group) + ']</span>'
              : '') + extraBadges(n);
          const menuHtml = renderOrgMenuHtml(n);
          const row =
            '<div class="tree-row">' +
            '<span class="code">' +
            escapeHtml(n.code) +
            '</span> <span>' +
            renderOrgUnitNameHtml(n.name, n.unit_type) +
            '</span> <span class="unit-type">(' +
            escapeHtml(type) +
            ')</span>' +
            badges +
            '<span class="card-actions">' +
            renderOrgActionsCell(n) +
            '</span></div>';
          return (
            '<div class="tree-item" data-unit-id="' +
            escapeHtml(n.id) +
            '" data-unit-type="' +
            escapeHtml(n.unit_type || '') +
            '" data-unit-code="' +
            escapeHtml(n.code) +
            '">' +
            row +
            (ch ? '<div class="tree-node">' + ch + '</div>' : '') +
            '</div>'
          );
        })
        .join('');
    }

    return render(opts.nodes || [], 0);
  }

  var activeOrgMenuContainer = null;
  var orgMenuOutsideListenerReady = false;

  function closeAllOrgMenus() {
    if (!activeOrgMenuContainer) return;
    activeOrgMenuContainer.querySelectorAll('.org-ctx-menu').forEach(function (m) {
      m.classList.add('hidden');
    });
  }

  function ensureOrgMenuOutsideListener() {
    if (orgMenuOutsideListenerReady) return;
    orgMenuOutsideListenerReady = true;
    document.addEventListener('click', function (e) {
      if (document.querySelector('.modal.show')) return;
      if (e.target.closest('.org-row-actions')) return;
      closeAllOrgMenus();
    });
  }

  function bindOrgTreeActions(container, onAction) {
    if (!container) return;
    ensureOrgMenuOutsideListener();
    activeOrgMenuContainer = container;
    if (container._orgTreeClickHandler) {
      container.removeEventListener('click', container._orgTreeClickHandler);
    }
    container._orgTreeClickHandler = function (e) {
      const menuBtn = e.target.closest('.org-menu-btn');
      if (menuBtn) {
        e.stopPropagation();
        const id = menuBtn.dataset.id;
        const menu = container.querySelector('.org-ctx-menu[data-for="' + id + '"]');
        container.querySelectorAll('.org-ctx-menu').forEach(function (m) {
          if (m !== menu) m.classList.add('hidden');
        });
        if (menu) menu.classList.toggle('hidden');
        return;
      }
      const item = e.target.closest('.org-ctx-item, .org-act-btn');
      if (!item) return;
      e.preventDefault();
      e.stopPropagation();
      const id = item.dataset.id;
      const action = item.dataset.action;
      const nodeEl = container.querySelector('[data-unit-id="' + id + '"]');
      const node = nodeEl
        ? {
            id: id,
            code: nodeEl.dataset.unitCode,
            unit_type: nodeEl.dataset.unitType,
          }
        : { id: id };
      if (onAction) onAction(action, node);
      closeAllOrgMenus();
    };
    container.addEventListener('click', container._orgTreeClickHandler);
  }

  global.OrgTreeShared = {
    escapeHtml: escapeHtml,
    parseApiErrorText: parseApiErrorText,
    unitTypeLabel: unitTypeLabel,
    renderOrgUnitNameHtml: renderOrgUnitNameHtml,
    renderOrgTreeHtml: renderOrgTreeHtml,
    renderOrgTableHtml: renderOrgTableHtml,
    sortOrgTableRows: sortOrgTableRows,
    bindOrgTreeActions: bindOrgTreeActions,
  };
})(typeof window !== 'undefined' ? window : globalThis);
