/** Account employee picker — Stage 2F frontend tests */

import { createRequire } from 'node:module';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const psych = require('../../static/shared/psych-testing-ui.js');
const picker = require('../../static/shared/account-employee-picker.js');

function orgUnits() {
  return [
    {
      id: 'ou-clin',
      unit_type: 'department',
      name: 'Polyclinic',
      code: 'POLY',
      effective_log_group: 'clinical',
      effective_log_group_name: 'Клинические',
      is_active: true,
    },
    {
      id: 'ou-adm',
      unit_type: 'department',
      name: 'Administration',
      code: 'ADM',
      effective_log_group: 'admin',
      effective_log_group_name: 'Административные',
      is_active: true,
    },
  ];
}

function positions() {
  return [
    { id: 'pos-doc', org_unit_id: 'ou-clin', code: 'DOC', name: 'Doctor', is_active: true },
    { id: 'pos-hr', org_unit_id: 'ou-adm', code: 'HR', name: 'HR Manager', is_active: true },
  ];
}

function employees() {
  return [
    {
      id: 'e1',
      last_name: 'Иванов',
      first_name: 'Иван',
      middle_name: 'Иванович',
      org_unit_id: 'ou-clin',
      position_id: 'pos-doc',
      email: 'ivanov@example.com',
    },
    {
      id: 'e2',
      last_name: 'Петров',
      first_name: 'Пётр',
      org_unit_id: 'ou-adm',
      position_id: 'pos-hr',
      email: null,
    },
    {
      id: 'e3',
      last_name: 'Сидорова',
      first_name: 'Анна',
      org_unit_id: 'ou-clin',
      position_id: 'pos-doc',
      email: 'sid@example.com',
    },
  ];
}

{
  assert.equal(picker.matchesNameQuery(employees()[0], 'иван'), true);
  assert.equal(picker.matchesNameQuery(employees()[0], 'ИВАНОВ'), true);
  assert.equal(picker.matchesNameQuery(employees()[0], 'петр'), false);
}

{
  const resolved = picker.resolvePicker(
    { logGroup: 'clinical', orgUnitId: '', positionId: '', nameQuery: '' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.equal(resolved.departments.length, 1);
  assert.equal(resolved.departments[0].id, 'ou-clin');
  assert.deepEqual(
    resolved.employees.map((e) => e.id).sort(),
    ['e1', 'e3']
  );
}

{
  const resolved = picker.resolvePicker(
    { logGroup: '', orgUnitId: 'ou-adm', positionId: '', nameQuery: '' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.deepEqual(resolved.employees.map((e) => e.id), ['e2']);
  assert.equal(resolved.positions.length, 1);
  assert.equal(resolved.positions[0].id, 'pos-hr');
}

{
  const resolved = picker.resolvePicker(
    { logGroup: '', orgUnitId: 'ou-clin', positionId: 'pos-doc', nameQuery: '' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.deepEqual(resolved.employees.map((e) => e.id).sort(), ['e1', 'e3']);
}

{
  const resolved = picker.resolvePicker(
    { logGroup: 'admin', orgUnitId: '', positionId: '', nameQuery: 'петр' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.deepEqual(resolved.employees.map((e) => e.id), ['e2']);
}

{
  const resolved = picker.resolvePicker(
    { logGroup: 'clinical', orgUnitId: '', positionId: '', nameQuery: 'zzz' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.equal(resolved.employees.length, 0);
  assert.equal(picker.employeeEmptyMessage(resolved, psych), picker.EMPTY_EMPLOYEES_MSG);
}

{
  const resolved = picker.resolvePicker(
    { logGroup: '', orgUnitId: '', positionId: '', nameQuery: '', employeeId: 'e2' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.equal(resolved.employeeId, 'e2');

  const filteredOut = picker.resolvePicker(
    { logGroup: 'clinical', orgUnitId: '', positionId: '', nameQuery: '', employeeId: 'e2' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.equal(filteredOut.employeeId, '');
}

{
  const reset = picker.resetOnChange('logGroup', {
    logGroup: 'clinical',
    orgUnitId: 'ou-clin',
    positionId: 'pos-doc',
    nameQuery: 'ив',
    employeeId: 'e1',
  });
  assert.equal(reset.orgUnitId, '');
  assert.equal(reset.positionId, '');
  assert.equal(reset.employeeId, '');
  assert.equal(reset.logGroup, 'clinical');
  assert.equal(reset.nameQuery, 'ив');
}

{
  const resolved = picker.resolvePicker(
    { logGroup: '', orgUnitId: '', positionId: '', nameQuery: '' },
    { orgUnits: orgUnits(), positions: positions(), employees: employees() },
    psych
  );
  assert.equal(resolved.employees.length, 3);
  assert.equal(resolved.hasActiveFilters, false);
  assert.equal(picker.formatEmployeeOptionLabel(employees()[0]), 'Иванов Иван Иванович (ivanov@example.com)');
}

console.log('test_account_employee_picker.mjs: all passed');
