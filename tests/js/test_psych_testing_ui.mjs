/**

 * Frontend unit tests for psych-testing-ui.js (Node ESM).

 */

import { createRequire } from 'node:module';

import assert from 'node:assert/strict';



const require = createRequire(import.meta.url);

const ui = require('../../static/shared/psych-testing-ui.js');



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



function sampleOrgUnits() {

  return [

    { id: 'ou-hr', unit_type: 'department', name: 'HR', effective_log_group: 'hr_ops', is_active: true },

    { id: 'ou-adm', unit_type: 'department', name: 'ADM', effective_log_group: 'admin', is_active: true },

    { id: 'ou-hr2', unit_type: 'department', name: 'HR2', effective_log_group: 'hr_ops', is_active: true },

  ];

}



function sampleMedicalOrgUnits() {

  return [

    {

      id: 'ou-clin',

      unit_type: 'department',

      name: 'Polyclinic',

      effective_log_group: 'clinical',

      effective_log_group_name: 'Клинические',

      is_active: true,

    },

    {

      id: 'ou-para',

      unit_type: 'department',

      name: 'Lab',

      effective_log_group: 'paraclinical',

      effective_log_group_name: 'Параклинические',

      is_active: true,

    },

    {

      id: 'ou-admin',

      unit_type: 'department',

      name: 'Admin',

      effective_log_group: 'admin_household',

      effective_log_group_name: 'Административно-хозяйственные',

      is_active: true,

    },

  ];

}



function sampleOrgUnitsNoGroups() {

  return [

    { id: 'ou-hr', unit_type: 'department', name: 'HR', effective_log_group: null, is_active: true },

    { id: 'ou-adm', unit_type: 'department', name: 'ADM', is_active: true },

  ];

}



function sampleOrgUnitsMixed() {

  return [

    { id: 'ou-hr', unit_type: 'department', name: 'HR', effective_log_group: 'hr_ops', is_active: true },

    { id: 'ou-adm', unit_type: 'department', name: 'ADM', effective_log_group: null, is_active: true },

    { id: 'ou-sales', unit_type: 'department', name: 'Sales', is_active: true },

  ];

}



function samplePositions() {

  return [

    { id: 'pos-1', org_unit_id: 'ou-hr', code: 'HR_GEN', name: 'HR Generalist', is_active: true },

    { id: 'pos-2', org_unit_id: 'ou-adm', code: 'DIR', name: 'Director', is_active: true },

  ];

}



function sampleEmployees() {

  return [

    { id: 'e1', org_unit_id: 'ou-hr', position_id: 'pos-1', last_name: 'Ivanov', first_name: 'I', telegram_id: '111' },

    { id: 'e2', org_unit_id: 'ou-adm', position_id: 'pos-2', last_name: 'Petrov', first_name: 'P', telegram_id: '' },

    { id: 'e3', org_unit_id: 'ou-hr', position_id: 'pos-1', last_name: 'Sidorov', first_name: 'S', telegram_id: '222' },

  ];

}



// --- bot info collapse ---

{

  const storage = mockStorage({});

  assert.equal(ui.readBotInfoCollapsed(storage), false, 'first visit expanded');

  ui.writeBotInfoCollapsed(storage, true);

  assert.equal(ui.readBotInfoCollapsed(storage), true, 'collapsed persisted');

  ui.writeBotInfoCollapsed(storage, false);

  assert.equal(ui.readBotInfoCollapsed(storage), false, 'expanded again');

}



{

  const block = { classList: { _v: new Set(), toggle(c, on) { on ? this._v.add(c) : this._v.delete(c); }, contains(c) { return this._v.has(c); } } };

  const details = { hidden: false };

  const toggleBtn = { textContent: '' };

  ui.applyBotInfoCollapsed({ block, details, toggleBtn }, true);

  assert.equal(details.hidden, true);

  assert.equal(toggleBtn.textContent, 'Развернуть');

  ui.applyBotInfoCollapsed({ block, details, toggleBtn }, false);

  assert.equal(details.hidden, false);

  assert.equal(toggleBtn.textContent, 'Свернуть');

}



// --- cascade filters ---

{

  const reset = ui.resetCascadeOnChange('logGroup');

  assert.deepEqual(reset, { logGroup: '', orgUnitId: '', positionId: '', employeeId: '' });

}



{

  const reset = ui.resetCascadeOnChange('orgUnitId', 'hr_ops');

  assert.equal(reset.logGroup, 'hr_ops');

  assert.equal(reset.orgUnitId, '');

  assert.equal(reset.positionId, '');

  assert.equal(reset.employeeId, '');

}



{

  const reset = ui.resetCascadeOnChange('positionId', 'hr_ops', 'ou-hr');

  assert.equal(reset.logGroup, 'hr_ops');

  assert.equal(reset.orgUnitId, 'ou-hr');

  assert.equal(reset.positionId, '');

  assert.equal(reset.employeeId, '');

}



{

  const deps = ui.filterDepartments(sampleOrgUnits(), 'hr_ops');

  assert.equal(deps.length, 2);

  assert.ok(deps.every((d) => d.effective_log_group === 'hr_ops'));

}



// --- medical log group labels from API ---

{

  const groups = ui.collectLogGroups(sampleMedicalOrgUnits());

  assert.equal(groups.length, 3);

  const byValue = Object.fromEntries(groups.map((g) => [g.value, g.label]));

  assert.equal(byValue.clinical, 'Клинические');

  assert.equal(byValue.paraclinical, 'Параклинические');

  assert.equal(byValue.admin_household, 'Административно-хозяйственные');

}



{

  const opts = ui.buildSelectOptions(

    ui.collectLogGroups(sampleMedicalOrgUnits()),

    '— группа отделений —',

    null

  );

  assert.match(opts.html, /value="clinical">Клинические<\/option>/);

  assert.match(opts.html, /value="paraclinical">Параклинические<\/option>/);

  assert.match(opts.html, /value="admin_household">Административно-хозяйственные<\/option>/);

  assert.doesNotMatch(opts.html, />clinical</);

  assert.doesNotMatch(opts.html, />paraclinical</);

  assert.doesNotMatch(opts.html, />admin_household</);

}



{

  const medical = sampleMedicalOrgUnits();

  assert.equal(ui.logGroupLabel('clinical', medical), 'Клинические');

  assert.equal(ui.logGroupLabel('paraclinical', medical), 'Параклинические');

  assert.equal(ui.logGroupLabel('admin_household', medical), 'Административно-хозяйственные');

}



// --- no log groups: synthetic "Все отделения" ---

{

  const groups = ui.collectLogGroups(sampleOrgUnitsNoGroups());

  assert.equal(groups.length, 1);

  assert.equal(groups[0].value, ui.LOG_GROUP_ALL);

  assert.equal(groups[0].label, ui.LABEL_LOG_GROUP_ALL);

}



{

  const picked = ui.defaultLogGroupSelection(

    ui.collectLogGroups(sampleOrgUnitsNoGroups()),

    ''

  );

  assert.equal(picked, ui.LOG_GROUP_ALL);

}



{

  const deps = ui.filterDepartments(sampleOrgUnitsNoGroups(), ui.LOG_GROUP_ALL);

  assert.equal(deps.length, 2);

}



{

  const deps = ui.filterDepartments(sampleOrgUnitsNoGroups(), '');

  assert.equal(deps.length, 2);

}



// --- mixed grouped / ungrouped ---

{

  const groups = ui.collectLogGroups(sampleOrgUnitsMixed());

  assert.ok(groups.some((g) => g.value === 'hr_ops'));

  assert.ok(groups.some((g) => g.value === ui.LOG_GROUP_UNGROUPED));

  assert.equal(groups.find((g) => g.value === ui.LOG_GROUP_UNGROUPED).label, ui.LABEL_LOG_GROUP_UNGROUPED);

}



{

  const ungrouped = ui.filterDepartments(sampleOrgUnitsMixed(), ui.LOG_GROUP_UNGROUPED);

  assert.equal(ungrouped.length, 2);

  assert.ok(ungrouped.every((d) => !String(d.effective_log_group || '').trim()));

}



{

  const pos = ui.filterPositions(samplePositions(), 'ou-hr');

  assert.equal(pos.length, 1);

  assert.equal(pos[0].id, 'pos-1');

}



{

  const emps = ui.filterEmployees(sampleEmployees(), 'pos-1', 'ou-hr');

  assert.equal(emps.length, 2);

  assert.ok(emps.every((e) => e.position_id === 'pos-1'));

  assert.ok(emps.every((e) => String(e.telegram_id || '').trim()));

}



{

  const cascade = ui.cascadeFilterState(

    { logGroup: 'hr_ops', orgUnitId: 'ou-hr', positionId: 'pos-1', employeeId: '', testId: '' },

    { orgUnits: sampleOrgUnits(), positions: samplePositions(), employees: sampleEmployees() }

  );

  assert.equal(cascade.employees.length, 2);

  assert.equal(cascade.assignEnabled, false);

}



{

  const cascade = ui.cascadeFilterState(

    {

      logGroup: ui.LOG_GROUP_ALL,

      orgUnitId: 'ou-hr',

      positionId: 'pos-1',

      employeeId: 'e1',

      testId: 'mbti',

    },

    { orgUnits: sampleOrgUnitsNoGroups(), positions: samplePositions(), employees: sampleEmployees() }

  );

  assert.equal(cascade.departments.length, 2);

  assert.equal(cascade.employees.length, 2);

  assert.equal(cascade.assignEnabled, true);

}



// --- assign button ---

assert.equal(ui.isAssignEnabled('', 'mbti'), false);

assert.equal(ui.isAssignEnabled('e1', ''), false);

assert.equal(ui.isAssignEnabled('e1', 'mbti'), true);



console.log('test_psych_testing_ui.mjs: all passed');

