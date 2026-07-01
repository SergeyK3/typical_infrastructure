/** Account create form hardening — Stage 2G */

import { createRequire } from 'node:module';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const form = require('../../static/shared/account-create-form.js');

const employee = {
  id: 'e1',
  last_name: 'Иванов',
  first_name: 'Иван',
  email: 'ivanov@example.com',
  account_id: null,
};

const employeeWithAccount = {
  id: 'e2',
  last_name: 'Петров',
  first_name: 'Пётр',
  account_id: 'acc-1',
  account_login: 'petrov',
};

{
  assert.equal(form.transliterateRu('Иванов'), 'ivanov');
  assert.equal(form.loginFromEmail('ivanov@example.com'), 'ivanov');
  assert.equal(form.suggestLogin(employee, []), 'ivanov');
  assert.equal(form.suggestLogin(employee, ['ivanov']), 'ivanov.i');
}

{
  assert.equal(form.employeeHasAccount(employeeWithAccount), true);
  assert.equal(form.employeeAccountHint(employeeWithAccount), form.MSG_EMPLOYEE_HAS_ACCOUNT);
  const validation = form.validateAccountCreateForm({
    employeeId: 'e2',
    login: 'petrov2',
    password: 'Secret123!',
    employee: employeeWithAccount,
    existingLogins: [],
  });
  assert.equal(validation.ok, false);
  assert.equal(validation.error, form.MSG_EMPLOYEE_HAS_ACCOUNT);
}

{
  assert.equal(form.loginTaken('Ivanov', ['ivanov']), true);
  assert.equal(form.loginDuplicateHint('ivanov', ['ivanov']), form.MSG_LOGIN_EXISTS);
  const validation = form.validateAccountCreateForm({
    employeeId: 'e1',
    login: 'ivanov',
    password: 'Secret123!',
    employee,
    existingLogins: ['ivanov'],
  });
  assert.equal(validation.ok, false);
  assert.equal(validation.error, form.MSG_LOGIN_EXISTS);
}

{
  const allRoles = [
    { code: 'admin', name: 'Org admin' },
    { code: 'system_admin', name: 'Platform system administrator' },
    { code: 'developer', name: 'Platform developer' },
    { code: 'employee', name: 'Employee' },
  ];
  const localRoles = form.filterRolesForAccountForm(allRoles, false);
  assert.deepEqual(localRoles.map((r) => r.code), ['admin', 'employee']);
  assert.equal(form.isPlatformRoleCode('system_admin'), true);
  const globalRoles = form.filterRolesForAccountForm(allRoles, true);
  assert.equal(globalRoles.length, 4);
}

{
  const ok = form.validateAccountCreateForm({
    employeeId: 'e1',
    login: 'new_user',
    password: 'Secret123!',
    employee,
    existingLogins: ['ivanov'],
  });
  assert.equal(ok.ok, true);
}

console.log('test_account_create_form.mjs: all passed');
