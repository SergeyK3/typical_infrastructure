/**
 * Поле ввода с keyword-поиском и выпадающим списком (один контрол вместо search + select).
 */
(function (global) {
  'use strict';

  const instances = new Map();

  function defaultEscapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function itemMatches(item, query) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return true;
    if (String(item.label || '').toLowerCase().includes(q)) return true;
    if (String(item.title || '').toLowerCase().includes(q)) return true;
    return (item.keywords || []).some((k) => String(k || '').toLowerCase().includes(q));
  }

  function findItem(state, value) {
    return (state.items || []).find((it) => it.value === value);
  }

  function selectItem(state, value, opts) {
    opts = opts || {};
    const item = value ? findItem(state, value) : null;
    state.hiddenEl.value = item ? item.value : '';
    if (item) {
      state.inputEl.value = item.displayValue != null ? item.displayValue : item.label;
    } else if (opts.clearInput) {
      state.inputEl.value = '';
    }
    state.listEl.hidden = true;
    if (typeof state.onSelect === 'function') state.onSelect(item ? item.value : '', item);
  }

  function renderList(state) {
    const esc = state.escapeHtml || defaultEscapeHtml;
    const q = state.inputEl.value.trim();
    let filtered = (state.items || []).filter((it) => itemMatches(it, q));
    filtered.sort((a, b) =>
      String(a.label || '').localeCompare(String(b.label || ''), 'ru')
    );
    if (filtered.length > 150) filtered = filtered.slice(0, 150);
    if (!filtered.length) {
      state.listEl.innerHTML =
        '<div class="filter-combobox-empty">' + esc('— ничего не найдено —') + '</div>';
    } else {
      state.listEl.innerHTML = filtered.map((it) =>
        '<button type="button" class="filter-combobox-option" data-value="' + esc(it.value) +
        '" title="' + esc(it.title || it.label) + '">' + esc(it.label) + '</button>'
      ).join('');
      state.listEl.querySelectorAll('.filter-combobox-option').forEach((btn) => {
        btn.addEventListener('mousedown', (e) => {
          e.preventDefault();
          selectItem(state, btn.dataset.value);
        });
      });
    }
    state.listEl.hidden = false;
  }

  function wire(state) {
    if (state.wired) return;
    state.inputEl.addEventListener('focus', () => renderList(state));
    state.inputEl.addEventListener('input', () => {
      state.hiddenEl.value = '';
      clearTimeout(state.timer);
      state.timer = setTimeout(() => renderList(state), 80);
    });
    state.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') state.listEl.hidden = true;
    });
    document.addEventListener('click', (e) => {
      if (!state.root.contains(e.target)) state.listEl.hidden = true;
    });
    state.wired = true;
  }

  function mount(opts) {
    const hiddenEl = document.getElementById(opts.hiddenId);
    const inputEl = document.getElementById(opts.inputId);
    if (!hiddenEl || !inputEl) return null;
    const listEl = opts.listId
      ? document.getElementById(opts.listId)
      : inputEl.parentElement && inputEl.parentElement.querySelector('.filter-combobox-list');
    if (!listEl) return null;
    const state = {
      hiddenId: opts.hiddenId,
      hiddenEl,
      inputEl,
      listEl,
      root: inputEl.closest('.filter-combobox') || inputEl.parentElement,
      items: opts.items || [],
      onSelect: opts.onSelect,
      escapeHtml: opts.escapeHtml || defaultEscapeHtml,
      wired: false,
    };
    if (opts.placeholder) inputEl.placeholder = opts.placeholder;
    wire(state);
    instances.set(opts.hiddenId, state);
    setItems(opts.hiddenId, state.items, opts.selectedValue, { clearInput: true });
    return state;
  }

  function ensure(opts) {
    if (instances.has(opts.hiddenId)) {
      const state = instances.get(opts.hiddenId);
      if (opts.placeholder) state.inputEl.placeholder = opts.placeholder;
      setItems(opts.hiddenId, opts.items || state.items, opts.selectedValue, { clearInput: !opts.selectedValue });
      return state;
    }
    return mount(opts);
  }

  function setItems(hiddenId, items, selectedValue, opts) {
    const state = instances.get(hiddenId);
    if (!state) return;
    state.items = items || [];
    if (selectedValue !== undefined) {
      selectItem(state, selectedValue || '', opts || {});
    }
  }

  function getValue(hiddenId) {
    const el = document.getElementById(hiddenId);
    return el ? el.value : '';
  }

  function clear(hiddenId) {
    const state = instances.get(hiddenId);
    if (!state) return;
    selectItem(state, '', { clearInput: true });
  }

  global.FilterCombobox = {
    mount,
    ensure,
    setItems,
    getValue,
    clear,
    itemMatches,
  };
})(typeof window !== 'undefined' ? window : globalThis);
