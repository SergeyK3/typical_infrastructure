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

  /**
   * @param {object} opts
   * @param {Array} opts.nodes
   * @param {function} opts.onAction - (action, node) => void
   * @param {function} [opts.extraBadges] - (node) => string HTML
   */
  function renderOrgTreeHtml(opts) {
    const onAction = opts.onAction || function () {};
    const extraBadges = opts.extraBadges || function () { return ''; };

    function render(nodes, level) {
      if (!nodes || !nodes.length) return '';
      return nodes
        .map(function (n) {
          const ch = render(n.children || [], level + 1);
          const type = unitTypeLabel(n.unit_type);
          const badges = extraBadges(n);
          const menuItems = [];
          if (n.unit_type === 'department') {
            menuItems.push({ action: 'add-section', label: 'Создать секцию' });
            menuItems.push({ action: 'clone', label: 'Копировать' });
          }
          if (n.unit_type === 'section') {
            menuItems.push({ action: 'clone-section', label: 'Копировать секцию' });
          }
          if (n.code !== 'company') {
            menuItems.push({ action: 'rename', label: 'Переименовать' });
            menuItems.push({ action: 'delete', label: 'Удалить', danger: true });
          }
          const menuHtml = menuItems
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
          const row =
            '<div class="tree-row">' +
            '<span class="code">' +
            escapeHtml(n.code) +
            '</span> <span>' +
            escapeHtml(n.name) +
            '</span> <span class="unit-type">(' +
            escapeHtml(type) +
            ')</span>' +
            badges +
            '<span class="card-actions org-row-actions">' +
            '<button type="button" class="btn btn-sm btn-secondary org-menu-btn" data-id="' +
            escapeHtml(n.id) +
            '" title="Действия">⋯</button>' +
            '<div class="org-ctx-menu hidden" data-for="' +
            escapeHtml(n.id) +
            '">' +
            menuHtml +
            '</div></span></div>';
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
    container.querySelectorAll('.org-menu-btn').forEach(function (btn) {
      btn.onclick = function (e) {
        e.stopPropagation();
        const id = btn.dataset.id;
        const menu = container.querySelector('.org-ctx-menu[data-for="' + id + '"]');
        container.querySelectorAll('.org-ctx-menu').forEach(function (m) {
          if (m !== menu) m.classList.add('hidden');
        });
        if (menu) menu.classList.toggle('hidden');
      };
    });
    container.querySelectorAll('.org-ctx-item').forEach(function (item) {
      item.onclick = function (e) {
        e.stopPropagation();
        const id = item.dataset.id;
        const action = item.dataset.action;
        const nodeEl = container.querySelector('.tree-item[data-unit-id="' + id + '"]');
        const node = nodeEl
          ? {
              id: id,
              code: nodeEl.dataset.unitCode,
              unit_type: nodeEl.dataset.unitType,
            }
          : { id: id };
        container.querySelectorAll('.org-ctx-menu').forEach(function (m) {
          m.classList.add('hidden');
        });
        if (onAction) onAction(action, node);
      };
    });
    document.addEventListener('click', function closeMenus() {
      container.querySelectorAll('.org-ctx-menu').forEach(function (m) {
        m.classList.add('hidden');
      });
    }, { once: true });
  }

  global.OrgTreeShared = {
    escapeHtml: escapeHtml,
    parseApiErrorText: parseApiErrorText,
    unitTypeLabel: unitTypeLabel,
    renderOrgTreeHtml: renderOrgTreeHtml,
    bindOrgTreeActions: bindOrgTreeActions,
  };
})(typeof window !== 'undefined' ? window : globalThis);
