/**
 * Compact organization labels — PROJ-ACCESS-ADMIN Stage 2E.
 * Rule: short_name if set, else name, else code, else id.
 */
(function (global) {
  'use strict';

  function strip(value) {
    return String(value == null ? '' : value).trim();
  }

  function fullLabel(client) {
    if (!client) return '';
    return strip(client.name) || strip(client.code) || strip(client.id);
  }

  function compactLabel(client) {
    if (!client) return '';
    var short = strip(client.short_name);
    if (short) return short;
    return fullLabel(client);
  }

  function labelTitle(client) {
    if (!client) return '';
    var short = strip(client.short_name);
    var full = strip(client.name);
    if (short && full && short !== full) return full;
    return '';
  }

  /** User row from GET /api/users (client_name + client_short_name). */
  function compactLabelFromUserRow(row) {
    if (!row) return '';
    var short = strip(row.client_short_name);
    if (short) return short;
    return strip(row.client_name) || strip(row.client_id);
  }

  function labelTitleFromUserRow(row) {
    if (!row) return '';
    var short = strip(row.client_short_name);
    var full = strip(row.client_name);
    if (short && full && short !== full) return full;
    return '';
  }

  function escapeAttr(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  }

  function titleAttr(clientOrRow, fromUserRow) {
    var title = fromUserRow ? labelTitleFromUserRow(clientOrRow) : labelTitle(clientOrRow);
    return title ? ' title="' + escapeAttr(title) + '"' : '';
  }

  var api = {
    strip: strip,
    fullLabel: fullLabel,
    compactLabel: compactLabel,
    labelTitle: labelTitle,
    compactLabelFromUserRow: compactLabelFromUserRow,
    labelTitleFromUserRow: labelTitleFromUserRow,
    titleAttr: titleAttr,
    escapeAttr: escapeAttr,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  global.ClientDisplay = api;
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
