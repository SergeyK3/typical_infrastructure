/**
 * UI helpers for «Психологические тестирования»: сворачиваемый блок бота и каскадные фильтры.
 */
(function (global) {
  'use strict';

  var BOT_INFO_COLLAPSED_KEY = 'psychTestingBotInfoCollapsed';

  function readBotInfoCollapsed(storage) {
    try {
      return storage.getItem(BOT_INFO_COLLAPSED_KEY) === '1';
    } catch (_) {
      return false;
    }
  }

  function writeBotInfoCollapsed(storage, collapsed) {
    try {
      storage.setItem(BOT_INFO_COLLAPSED_KEY, collapsed ? '1' : '0');
    } catch (_) { /* ignore */ }
  }

  function applyBotInfoCollapsed(dom, collapsed) {
    if (!dom || !dom.block) return;
    dom.block.classList.toggle('is-collapsed', !!collapsed);
    if (dom.details) dom.details.hidden = !!collapsed;
    if (dom.toggleBtn) {
      dom.toggleBtn.textContent = collapsed ? 'Развернуть' : 'Свернуть';
    }
  }

  function wireBotInfoToggle(dom, storage) {
    storage = storage || (typeof localStorage !== 'undefined' ? localStorage : null);
    if (!dom || !dom.block || !dom.toggleBtn || !storage) return;
    applyBotInfoCollapsed(dom, readBotInfoCollapsed(storage));
    dom.toggleBtn.addEventListener('click', function () {
      var next = !dom.block.classList.contains('is-collapsed');
      writeBotInfoCollapsed(storage, next);
      applyBotInfoCollapsed(dom, next);
    });
  }

  function departmentOrgUnits(orgUnits) {
    return (orgUnits || []).filter(function (u) {
      return u && u.is_active !== false && u.unit_type === 'department';
    });
  }

  function logGroupLabel(code) {
    var c = String(code || '').trim();
    return c || '';
  }

  function collectLogGroups(orgUnits) {
    var seen = Object.create(null);
    var out = [];
    departmentOrgUnits(orgUnits).forEach(function (u) {
      var g = String(u.effective_log_group || '').trim();
      if (!g || seen[g]) return;
      seen[g] = true;
      out.push({ value: g, label: logGroupLabel(g) });
    });
    out.sort(function (a, b) {
      return a.label.localeCompare(b.label, 'ru');
    });
    return out;
  }

  function filterDepartments(orgUnits, logGroup) {
    var list = departmentOrgUnits(orgUnits);
    var g = String(logGroup || '').trim();
    if (!g) return list.slice();
    return list.filter(function (u) {
      return String(u.effective_log_group || '').trim() === g;
    });
  }

  function filterPositions(positions, orgUnitId) {
    var list = (positions || []).filter(function (p) {
      return p && p.is_active !== false;
    });
    var ou = String(orgUnitId || '').trim();
    if (!ou) return list.slice();
    return list.filter(function (p) {
      return String(p.org_unit_id || '') === ou;
    });
  }

  function employeesWithTelegram(employees) {
    return (employees || []).filter(function (e) {
      return e && String(e.telegram_id || '').trim();
    });
  }

  function filterEmployees(employees, positionId, orgUnitId) {
    var list = employeesWithTelegram(employees);
    var pid = String(positionId || '').trim();
    var ouid = String(orgUnitId || '').trim();
    if (pid) {
      return list.filter(function (e) {
        return String(e.position_id || '') === pid;
      });
    }
    if (ouid) {
      return list.filter(function (e) {
        return String(e.org_unit_id || '') === ouid;
      });
    }
    return list.slice();
  }

  function formatEmployeeName(e) {
    return [e.last_name, e.first_name, e.middle_name].filter(Boolean).join(' ');
  }

  function buildSelectOptions(items, placeholder, emptyMessage) {
    if (!items.length && emptyMessage) {
      return {
        html: '<option value="">' + emptyMessage + '</option>',
        hasSelectable: false,
      };
    }
    var html = '<option value="">' + placeholder + '</option>';
    items.forEach(function (it) {
      html +=
        '<option value="' + String(it.value).replace(/"/g, '&quot;') + '">' + it.label + '</option>';
    });
    return { html: html, hasSelectable: items.length > 0 };
  }

  function isAssignEnabled(employeeId, testId) {
    return !!(String(employeeId || '').trim() && String(testId || '').trim());
  }

  /**
   * @param {object} state — { logGroup, orgUnitId, positionId, employeeId, testId }
   * @param {object} data — { orgUnits, positions, employees }
   */
  function cascadeFilterState(state, data) {
    state = state || {};
    data = data || {};
    var orgUnits = data.orgUnits || [];
    var positions = data.positions || [];
    var employees = data.employees || [];

    var logGroups = collectLogGroups(orgUnits);
    var departments = filterDepartments(orgUnits, state.logGroup);
    var posList = filterPositions(positions, state.orgUnitId);
    var empList = filterEmployees(employees, state.positionId, state.orgUnitId);

    return {
      logGroups: logGroups,
      departments: departments,
      positions: posList,
      employees: empList,
      assignEnabled: isAssignEnabled(state.employeeId, state.testId),
    };
  }

  /**
   * Сброс нижних уровней при изменении верхнего фильтра.
   * @param {'logGroup'|'orgUnitId'|'positionId'} changed
   */
  function resetCascadeOnChange(changed) {
    var next = { logGroup: '', orgUnitId: '', positionId: '', employeeId: '' };
    if (changed === 'logGroup') return next;
    if (changed === 'orgUnitId') {
      next.logGroup = arguments[1] || '';
      return next;
    }
    if (changed === 'positionId') {
      next.logGroup = arguments[1] || '';
      next.orgUnitId = arguments[2] || '';
      return next;
    }
    return next;
  }

  var api = {
    BOT_INFO_COLLAPSED_KEY: BOT_INFO_COLLAPSED_KEY,
    readBotInfoCollapsed: readBotInfoCollapsed,
    writeBotInfoCollapsed: writeBotInfoCollapsed,
    applyBotInfoCollapsed: applyBotInfoCollapsed,
    wireBotInfoToggle: wireBotInfoToggle,
    collectLogGroups: collectLogGroups,
    filterDepartments: filterDepartments,
    filterPositions: filterPositions,
    filterEmployees: filterEmployees,
    employeesWithTelegram: employeesWithTelegram,
    formatEmployeeName: formatEmployeeName,
    buildSelectOptions: buildSelectOptions,
    isAssignEnabled: isAssignEnabled,
    cascadeFilterState: cascadeFilterState,
    resetCascadeOnChange: resetCascadeOnChange,
    logGroupLabel: logGroupLabel,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  global.PsychTestingUi = api;
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
