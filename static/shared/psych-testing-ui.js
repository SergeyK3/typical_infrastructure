/**
 * UI helpers for «Психологические тестирования»: сворачиваемый блок бота и каскадные фильтры.
 */
(function (global) {
  'use strict';

  var BOT_INFO_COLLAPSED_KEY = 'psychTestingBotInfoCollapsed';
  /** Синтетическая группа: все отделения (нет log_group в данных или явный выбор). */
  var LOG_GROUP_ALL = '__all__';
  /** Синтетическая группа: отделения без effective_log_group при смешанных данных. */
  var LOG_GROUP_UNGROUPED = '__ungrouped__';
  var LABEL_LOG_GROUP_ALL = 'Все отделения';
  var LABEL_LOG_GROUP_UNGROUPED = 'Без группы';

  function normalizeLogGroupValue(raw) {
    return String(raw || '').trim();
  }

  function isAllLogGroup(logGroup) {
    var g = normalizeLogGroupValue(logGroup);
    return !g || g === LOG_GROUP_ALL;
  }

  function departmentLogGroup(u) {
    return normalizeLogGroupValue(u && u.effective_log_group);
  }

  function departmentLogGroupName(u) {
    return normalizeLogGroupValue(u && u.effective_log_group_name);
  }

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

  function logGroupLabel(code, orgUnits) {
    var c = normalizeLogGroupValue(code);
    if (!c) return '';
    var depts = departmentOrgUnits(orgUnits || []);
    for (var i = 0; i < depts.length; i++) {
      if (departmentLogGroup(depts[i]) === c) {
        var name = departmentLogGroupName(depts[i]);
        if (name) return name;
      }
    }
    return c;
  }

  function collectLogGroups(orgUnits) {
    var depts = departmentOrgUnits(orgUnits);
    var seen = Object.create(null);
    var grouped = [];
    var hasUngrouped = false;

    depts.forEach(function (u) {
      var g = departmentLogGroup(u);
      if (!g) {
        hasUngrouped = true;
        return;
      }
      if (seen[g]) return;
      seen[g] = true;
      var label = departmentLogGroupName(u) || g;
      grouped.push({ value: g, label: label });
    });
    grouped.sort(function (a, b) {
      return a.label.localeCompare(b.label, 'ru');
    });

    if (!grouped.length) {
      return [{ value: LOG_GROUP_ALL, label: LABEL_LOG_GROUP_ALL }];
    }
    if (hasUngrouped) {
      grouped.push({ value: LOG_GROUP_UNGROUPED, label: LABEL_LOG_GROUP_UNGROUPED });
    }
    return grouped;
  }

  function filterDepartments(orgUnits, logGroup) {
    var list = departmentOrgUnits(orgUnits);
    var g = normalizeLogGroupValue(logGroup);
    if (!g || g === LOG_GROUP_ALL) return list.slice();
    if (g === LOG_GROUP_UNGROUPED) {
      return list.filter(function (u) {
        return !departmentLogGroup(u);
      });
    }
    return list.filter(function (u) {
      return departmentLogGroup(u) === g;
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

  function defaultLogGroupSelection(logGroups, current) {
    var cur = normalizeLogGroupValue(current);
    if (cur && logGroups.some(function (g) { return g.value === cur; })) return cur;
    if (logGroups.length === 1 && logGroups[0].value === LOG_GROUP_ALL) {
      return LOG_GROUP_ALL;
    }
    return '';
  }

  var api = {
    BOT_INFO_COLLAPSED_KEY: BOT_INFO_COLLAPSED_KEY,
    LOG_GROUP_ALL: LOG_GROUP_ALL,
    LOG_GROUP_UNGROUPED: LOG_GROUP_UNGROUPED,
    LABEL_LOG_GROUP_ALL: LABEL_LOG_GROUP_ALL,
    LABEL_LOG_GROUP_UNGROUPED: LABEL_LOG_GROUP_UNGROUPED,
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
    isAllLogGroup: isAllLogGroup,
    defaultLogGroupSelection: defaultLogGroupSelection,
    cascadeFilterState: cascadeFilterState,
    resetCascadeOnChange: resetCascadeOnChange,
    logGroupLabel: logGroupLabel,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  global.PsychTestingUi = api;
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
