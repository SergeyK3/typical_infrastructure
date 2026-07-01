/** Frontend unit tests for info-banner.js (Node ESM). */

import { createRequire } from 'node:module';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const banner = require('../../static/shared/info-banner.js');

function mockStorage(initial) {
  const map = new Map(Object.entries(initial || {}));
  return {
    getItem(k) {
      return map.has(k) ? map.get(k) : null;
    },
    setItem(k, v) {
      map.set(k, String(v));
    },
  };
}

// --- collapse persistence ---

{
  const storage = mockStorage({});
  const id = 'globalAdmin.accounts';
  assert.equal(banner.readCollapsed(storage, id), false, 'first visit expanded');
  banner.writeCollapsed(storage, id, true);
  assert.equal(banner.readCollapsed(storage, id), true, 'collapsed persisted');
  banner.writeCollapsed(storage, id, false);
  assert.equal(banner.readCollapsed(storage, id), false, 'expanded again');
}

{
  assert.equal(
    banner.storageKey('globalAdmin.accounts'),
    'infoBanner.collapsed.globalAdmin.accounts',
  );
}

// --- apply collapsed DOM ---

{
  const root = {
    classList: {
      _v: new Set(),
      toggle(c, on) {
        on ? this._v.add(c) : this._v.delete(c);
      },
      contains(c) {
        return this._v.has(c);
      },
    },
  };
  const details = { hidden: false };
  const toggleBtn = { textContent: '', setAttribute() {} };

  banner.applyCollapsed({ root, details, toggleBtn }, true);
  assert.equal(details.hidden, true);
  assert.equal(toggleBtn.textContent, 'Развернуть');

  banner.applyCollapsed({ root, details, toggleBtn }, false);
  assert.equal(details.hidden, false);
  assert.equal(toggleBtn.textContent, 'Свернуть');
}

// --- presets ---

{
  assert.ok(banner.PRESETS.globalAdminAccounts.summary.includes('платформенные аккаунты'));
  assert.ok(banner.PRESETS.localAdminAccounts.bodyHtml.includes('Сотрудники'));
}

console.log('test_info_banner.mjs: all passed');
