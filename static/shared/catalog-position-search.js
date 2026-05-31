/**
 * Поиск по должности (код + название) в шапках таблиц справочников.
 */
(function (global) {
  'use strict';

  function normalizeCode(code) {
    return String(code || '').trim();
  }

  function findEntry(map, code) {
    const c = normalizeCode(code);
    if (!c) return null;
    if (map[c]) return map[c];
    const lower = c.toLowerCase();
    for (const key of Object.keys(map)) {
      if (key.toLowerCase() === lower) return map[key];
    }
    return null;
  }

  function buildPositionNameMap(catalogItems) {
    const map = Object.create(null);
    (catalogItems || []).forEach((p) => {
      const code = normalizeCode(p.position_code || p.code);
      if (!code) return;
      map[code] = {
        nameRu: String(p.position_name_ru || p.name || '').trim(),
        nameEn: String(p.position_name_en || '').trim(),
        catalogCode: String(p.position_catalog_code || '').trim(),
      };
    });
    return map;
  }

  function positionDisplayName(map, code, fallback) {
    const entry = findEntry(map, code);
    if (entry && entry.nameRu) return entry.nameRu;
    return fallback !== undefined ? fallback : (normalizeCode(code) || '—');
  }

  function matchesPositionKeyword(map, code, query, extraFields) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return true;
    const c = normalizeCode(code);
    if (c.toLowerCase().includes(q)) return true;
    const entry = findEntry(map, c);
    if (entry) {
      if (entry.nameRu.toLowerCase().includes(q)) return true;
      if (entry.nameEn.toLowerCase().includes(q)) return true;
      if (entry.catalogCode && entry.catalogCode.toLowerCase().includes(q)) return true;
    }
    return (extraFields || []).some((v) => String(v || '').toLowerCase().includes(q));
  }

  function matchesAnyKeyword(fields, query) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return true;
    return (fields || []).some((v) => String(v || '').toLowerCase().includes(q));
  }

  function wireSearch(input, callback) {
    if (!input || typeof callback !== 'function') return;
    let timer;
    const run = () => {
      clearTimeout(timer);
      timer = setTimeout(callback, 160);
    };
    input.addEventListener('input', run);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        clearTimeout(timer);
        callback();
      }
    });
  }

  global.CatalogPositionSearch = {
    buildPositionNameMap,
    positionDisplayName,
    matchesPositionKeyword,
    matchesAnyKeyword,
    wireSearch,
  };
})(typeof window !== 'undefined' ? window : globalThis);
