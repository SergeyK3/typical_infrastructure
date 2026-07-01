/** Frontend unit tests for client-display.js (Node ESM). */

import { createRequire } from 'node:module';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const cd = require('../../static/shared/client-display.js');

const fullClient = {
  name: 'Многопрофильный медицинский центр г. Астаны',
  short_name: 'ММЦ',
  code: 'mmc',
  id: 'c1',
};

{
  assert.equal(cd.compactLabel(fullClient), 'ММЦ');
  assert.equal(cd.fullLabel(fullClient), 'Многопрофильный медицинский центр г. Астаны');
  assert.equal(cd.labelTitle(fullClient), 'Многопрофильный медицинский центр г. Астаны');
}

{
  const c = { name: 'Full Only', short_name: null, code: 'fo', id: 'c2' };
  assert.equal(cd.compactLabel(c), 'Full Only');
  assert.equal(cd.labelTitle(c), '');
}

{
  const c = { name: 'Full Only', short_name: '   ', code: 'fo', id: 'c2' };
  assert.equal(cd.compactLabel(c), 'Full Only');
}

{
  const row = {
    client_name: 'Многопрофильный медицинский центр г. Астаны',
    client_short_name: 'ММЦ',
    client_id: 'c1',
  };
  assert.equal(cd.compactLabelFromUserRow(row), 'ММЦ');
  assert.equal(cd.labelTitleFromUserRow(row), 'Многопрофильный медицинский центр г. Астаны');
}

{
  assert.match(cd.titleAttr(fullClient), /title="Многопрофильный медицинский центр г\. Астаны"/);
  assert.equal(cd.titleAttr({ name: 'Same', short_name: 'Same' }), '');
}

console.log('test_client_display.mjs: all passed');
