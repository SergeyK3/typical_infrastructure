/**
 * Выбор подразделения с keyword-поиском (код, название, сегмент, путь в дереве).
 */
(function (global) {
  'use strict';

  function formatUnitSelf(u) {
    return String(u.code || '').trim() +
      (u.name ? ' — ' + String(u.name).trim() : '');
  }

  function rootPathLabels(units) {
    return (units || [])
      .filter((u) => u && !u.parent_id)
      .map(formatUnitSelf)
      .filter(Boolean);
  }

  /** Путь для отображения: без корневого «company — Компания / …». */
  function displayPath(fullPath, rootLabels) {
    const path = String(fullPath || '').trim();
    if (!path) return '';
    for (const root of rootLabels || []) {
      const prefix = root + ' / ';
      if (path.startsWith(prefix)) return path.slice(prefix.length);
    }
    return path;
  }

  function buildPaths(units) {
    const byId = Object.create(null);
    (units || []).forEach((u) => {
      if (u && u.id) byId[u.id] = u;
    });
    const paths = Object.create(null);
    function walk(id) {
      if (paths[id]) return paths[id];
      const u = byId[id];
      if (!u) return '';
      const self = formatUnitSelf(u);
      if (u.parent_id && byId[u.parent_id]) {
        paths[id] = walk(u.parent_id) + ' / ' + self;
      } else {
        paths[id] = self;
      }
      return paths[id];
    }
    (units || []).forEach((u) => {
      if (u.id) walk(u.id);
    });
    return paths;
  }

  function matchUnit(u, path, query) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return true;
    const fields = [
      u.code,
      u.name,
      u.unit_type,
      u.segment_code,
      u.effective_segment_code,
      u.catalog_source_code,
      path,
    ];
    return fields.some((f) => String(f || '').toLowerCase().includes(q));
  }

  function defaultEscapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function fillSelect(selectEl, units, options) {
    if (!selectEl) return;
    options = options || {};
    const paths = options.paths || buildPaths(units);
    const rootLabels = options.rootLabels || rootPathLabels(units);
    const query = options.query || '';
    const selectedId = options.selectedId != null ? options.selectedId : (selectEl.value || '');
    const escapeHtml = options.escapeHtml || defaultEscapeHtml;
    let list = (units || []).slice();
    if (options.activeOnly !== false) {
      list = list.filter((u) => u.is_active !== false);
    }
    list = list.filter((u) => matchUnit(u, paths[u.id] || '', query));
    list.sort((a, b) =>
      (paths[a.id] || a.code || '').localeCompare(paths[b.id] || b.code || '', 'ru')
    );
    if (!list.length) {
      selectEl.innerHTML =
        '<option value="">' + escapeHtml('— ничего не найдено —') + '</option>';
      selectEl.value = '';
      return;
    }
    selectEl.innerHTML = list.map((u) => {
      const path = paths[u.id] || formatUnitSelf(u);
      const typeHint =
        u.unit_type && u.unit_type !== 'department' ? ' [' + u.unit_type + ']' : '';
      const seg = u.effective_segment_code || u.segment_code;
      const segHint = seg ? ' · ' + seg : '';
      const fullLabel = path + typeHint + segHint;
      const shortLabel = displayPath(fullLabel, rootLabels);
      return (
        '<option value="' + escapeHtml(u.id) + '" title="' + escapeHtml(fullLabel) + '">' +
        escapeHtml(shortLabel) +
        '</option>'
      );
    }).join('');
    if (selectedId && list.some((u) => u.id === selectedId)) {
      selectEl.value = selectedId;
    }
  }

  const wiredSearches = new WeakSet();

  function unitsToComboboxItems(units, options) {
    options = options || {};
    const paths = options.paths || buildPaths(units);
    const rootLabels = options.rootLabels || rootPathLabels(units);
    let list = (units || []).slice();
    if (options.activeOnly !== false) {
      list = list.filter((u) => u.is_active !== false);
    }
    return list.map((u) => {
      const path = paths[u.id] || formatUnitSelf(u);
      const typeHint =
        u.unit_type && u.unit_type !== 'department' ? ' [' + u.unit_type + ']' : '';
      const seg = u.effective_segment_code || u.segment_code;
      const segHint = seg ? ' · ' + seg : '';
      const fullLabel = path + typeHint + segHint;
      const shortLabel = displayPath(fullLabel, rootLabels);
      return {
        value: u.id,
        label: shortLabel,
        title: fullLabel,
        displayValue: shortLabel,
        keywords: [
          u.code,
          u.name,
          u.unit_type,
          u.segment_code,
          u.effective_segment_code,
          u.catalog_source_code,
          path,
          fullLabel,
        ],
      };
    });
  }

  function populateField(opts) {
    if (!global.FilterCombobox) return;
    const units = opts.units || [];
    const items = unitsToComboboxItems(units, opts);
    FilterCombobox.ensure({
      hiddenId: opts.hiddenId,
      inputId: opts.inputId,
      listId: opts.listId,
      items,
      selectedValue: opts.selectedValue || '',
      placeholder: opts.placeholder || 'Введите код, название или сегмент…',
      escapeHtml: opts.escapeHtml,
    });
  }

  /** @deprecated используйте populateField */
  function populate(selectId, searchId, units, selectedId, escapeHtml) {
    const selectEl =
      typeof selectId === 'string' ? document.getElementById(selectId) : selectId;
    const searchEl =
      typeof searchId === 'string' ? document.getElementById(searchId) : searchId;
    if (!selectEl) return;
    const paths = buildPaths(units);
    const rootLabels = rootPathLabels(units);
    const esc = escapeHtml || defaultEscapeHtml;
    if (searchEl) searchEl.value = '';
    fillSelect(selectEl, units, { paths, rootLabels, selectedId, escapeHtml: esc });
    if (!searchEl) return;
    if (!wiredSearches.has(searchEl)) {
      let timer;
      searchEl.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          fillSelect(selectEl, units, {
            paths,
            rootLabels,
            query: searchEl.value,
            selectedId: selectEl.value,
            escapeHtml: esc,
          });
        }, 120);
      });
      wiredSearches.add(searchEl);
    }
  }

  global.OrgUnitPicker = {
    buildPaths,
    rootPathLabels,
    displayPath,
    matchUnit,
    unitsToComboboxItems,
    fillSelect,
    populate,
    populateField,
  };
})(typeof window !== 'undefined' ? window : globalThis);
