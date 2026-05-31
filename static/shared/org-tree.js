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

  function buildOrgMenuItems(n, opts) {
    opts = opts || {};
    const menuItems = [];
    if (n.unit_type === 'department') {
      menuItems.push({ action: 'add-section', label: 'Создать секцию' });
    }
    if (n.code !== 'company') {
      menuItems.push({ action: 'rename', label: 'Изменить' });
    }
    if (n.unit_type === 'department' || n.unit_type === 'section') {
      menuItems.push({ action: 'clone', label: 'Копировать', title: 'Копировать в этом шаблоне' });
    }
    if (opts.copyToTemplate && n.code !== 'company') {
      menuItems.push({ action: 'copy-to-template', label: 'В шаблон', title: 'Скопировать в другой шаблон' });
    }
    if (opts.toGlobal && n.code !== 'company') {
      menuItems.push({ action: 'to-global', label: 'В шаблон', title: 'Скопировать в глобальный шаблон' });
    }
    if (n.code !== 'company') {
      menuItems.push({ action: 'delete', label: 'Удалить', danger: true });
    }
    return menuItems;
  }

  function renderOrgActionsDropdown(n, opts) {
    const CRA = global.CatalogRowActions;
    const items = buildOrgMenuItems(n, opts);
    if (!CRA) return '<span class="meta">—</span>';
    return CRA.render(items, {
      rowKey: n.id,
      size: 'sm',
      attrs: { id: n.id, unitCode: n.code, unitType: n.unit_type || '' },
    });
  }

  function segmentDisplayHtml(n) {
    const eff = n.effective_segment_code || n.segment_code || '';
    if (!eff) return '<span class="meta">—</span>';
    if (n.unit_type === 'department') return '<code>' + escapeHtml(eff) + '</code>';
    return '<code>' + escapeHtml(eff) + '</code> <span class="meta" title="наследуется от отделения">↳</span>';
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

  function renderOrgTableActionsCell(n, opts) {
    return renderOrgActionsDropdown(n, opts);
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
          '<td class="td-segment">' +
          segmentDisplayHtml(n) +
          '</td>' +
          '<td class="td-sort num">' +
          escapeHtml(String(n.sort_order != null ? n.sort_order : 0)) +
          '</td>' +
          '<td class="td-actions">' +
          renderOrgTableActionsCell(n, opts) +
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
      '<th>Сегмент</th>' +
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
              : '') +
            ((n.effective_segment_code || n.segment_code)
              ? ' <span class="unit-type" title="Сегмент деятельности">{seg:' + escapeHtml(n.effective_segment_code || n.segment_code) + '}</span>'
              : '') +
            extraBadges(n);
          const menuHtml = renderOrgMenuHtml(n, opts);
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
            renderOrgActionsDropdown(n, opts) +
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

  function bindOrgTreeActions(container, onAction) {
    if (!container) return;
    const CRA = global.CatalogRowActions;
    if (!CRA) return;
    CRA.bind(container, function (action, wrap) {
      if (!wrap || !onAction) return;
      const id = wrap.dataset.id;
      if (!id) return;
      const nodeEl = container.querySelector('[data-unit-id="' + id + '"]');
      const node = nodeEl
        ? {
            id: id,
            code: nodeEl.dataset.unitCode || wrap.dataset.unitCode,
            unit_type: nodeEl.dataset.unitType || wrap.dataset.unitType,
          }
        : { id: id, code: wrap.dataset.unitCode, unit_type: wrap.dataset.unitType };
      onAction(action, node);
    });
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
