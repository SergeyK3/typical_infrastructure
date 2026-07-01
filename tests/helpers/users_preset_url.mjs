/**
 * Regression checks for /users preset URL and role label logic (Stage 2A).
 * Mirrors static/users/index.html client-side filter helpers.
 */

const ROLE_UI_LABELS = {
  admin: 'Администратор организации',
  system_admin: 'Глобальный администратор',
  developer: 'Разработчик платформы',
  hr: 'Кадры',
  manager: 'Руководитель',
  employee: 'Сотрудник',
};

function roleDisplayName(code, apiName) {
  if (!code) return apiName || '—';
  return ROLE_UI_LABELS[code] || apiName || code;
}

function normalizePresetUrl(search) {
  const p = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  if (p.get('preset') !== 'org-admins' || !p.has('role_code')) {
    return search.startsWith('?') ? search : (search ? `?${search}` : '');
  }
  p.delete('role_code');
  const qs = p.toString();
  return qs ? `?${qs}` : '';
}

function readFiltersFromUrl(search) {
  const p = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const preset = (p.get('preset') || '').trim();
  let roleCode = (p.get('role_code') || '').trim();
  if (preset === 'org-admins' && !roleCode) roleCode = 'admin';
  return { preset, roleCode };
}

function syncUrlFromFilters(filters, urlPreset) {
  const params = new URLSearchParams();
  let preset = urlPreset;
  if (preset === 'org-admins') {
    if (filters.roleCode && filters.roleCode !== 'admin') {
      preset = '';
    } else {
      params.set('preset', 'org-admins');
    }
  }
  if (filters.clientId) params.set('client_id', filters.clientId);
  if (filters.roleCode && preset !== 'org-admins') params.set('role_code', filters.roleCode);
  if (filters.status) params.set('status', filters.status);
  const qs = params.toString();
  return '/users' + (qs ? `?${qs}` : '');
}

function runChecks() {
  const failures = [];

  function assert(name, condition) {
    if (!condition) failures.push(name);
  }

  assert(
    'normalize strips role_code',
    normalizePresetUrl('?preset=org-admins&role_code=admin') === '?preset=org-admins',
  );
  assert(
    'readFilters infers admin role for preset',
    readFiltersFromUrl('?preset=org-admins').roleCode === 'admin',
  );
  assert(
    'sync keeps preset without role_code',
    syncUrlFromFilters({ clientId: '', roleCode: 'admin', status: '' }, 'org-admins')
      === '/users?preset=org-admins',
  );
  assert(
    'sync omits role_code in address bar for preset',
    !syncUrlFromFilters({ clientId: '', roleCode: 'admin', status: '' }, 'org-admins').includes('role_code='),
  );
  assert(
    'localized admin role label',
    roleDisplayName('admin', 'Administrator') === 'Администратор организации',
  );
  assert(
    'localized label beats raw Administrator in table rendering',
    roleDisplayName('admin', 'Administrator') !== 'Administrator',
  );

  if (failures.length) {
    process.stderr.write(`FAIL: ${failures.join(', ')}\n`);
    process.exit(1);
  }
  process.stdout.write('ok\n');
}

runChecks();
