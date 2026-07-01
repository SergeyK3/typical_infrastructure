/**
 * Каскадные фильтры выбора сотрудника для модалки «Добавить аккаунт» (Stage 2F).
 * Оргструктура — через PsychTestingUi; сотрудники — все (не только с Telegram).
 */
(function (global) {
  'use strict';

  var EMPTY_EMPLOYEES_MSG = 'Сотрудники не найдены';
  var PLACEHOLDER_EMPLOYEE = '— выберите сотрудника —';
  var PLACEHOLDER_LOG_GROUP = '— группа отделений —';
  var PLACEHOLDER_DEPARTMENT = '— отделение —';
  var PLACEHOLDER_POSITION = '— должность —';
  var PLACEHOLDER_NAME = 'Фамилия, имя…';

  function getPsychUi() {
    return global.PsychTestingUi || null;
  }

  function normalizeQuery(value) {
    return String(value == null ? '' : value).trim().toLowerCase();
  }

  function formatEmployeeName(employee) {
    if (!employee) return '';
    return [employee.last_name, employee.first_name, employee.middle_name].filter(Boolean).join(' ');
  }

  function formatEmployeeOptionLabel(employee) {
    var name = formatEmployeeName(employee);
    var email = String(employee && employee.email || '').trim();
    return email ? name + ' (' + email + ')' : name;
  }

  function matchesNameQuery(employee, query) {
    var q = normalizeQuery(query);
    if (!q) return true;
    var full = normalizeQuery(formatEmployeeName(employee));
    if (full.indexOf(q) !== -1) return true;
    var parts = [employee.last_name, employee.first_name, employee.middle_name].map(normalizeQuery);
    return parts.some(function (part) {
      return part && part.indexOf(q) !== -1;
    });
  }

  function filterEmployeesByOrg(employees, positionId, orgUnitId) {
    var list = (employees || []).slice();
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
    return list;
  }

  function filterEmployeesByLogGroup(employees, orgUnits, logGroup, psychUi) {
    psychUi = psychUi || getPsychUi();
    if (!psychUi || !logGroup || psychUi.isAllLogGroup(logGroup)) {
      return (employees || []).slice();
    }
    var allowedIds = Object.create(null);
    psychUi.filterDepartments(orgUnits || [], logGroup).forEach(function (u) {
      if (u && u.id) allowedIds[u.id] = true;
    });
    return (employees || []).filter(function (e) {
      return !!allowedIds[String(e.org_unit_id || '')];
    });
  }

  /**
   * @param {object} state — { logGroup, orgUnitId, positionId, nameQuery, employeeId }
   * @param {object} data — { orgUnits, positions, employees }
   */
  function resolvePicker(state, data, psychUi) {
    state = state || {};
    data = data || {};
    psychUi = psychUi || getPsychUi();
    if (!psychUi) {
      throw new Error('PsychTestingUi is required');
    }

    var orgUnits = data.orgUnits || [];
    var positions = data.positions || [];
    var employees = data.employees || [];

    var logGroups = psychUi.collectLogGroups(orgUnits);
    var resolvedLogGroup = psychUi.defaultLogGroupSelection(logGroups, state.logGroup);
    var filterState = Object.assign({}, state, { logGroup: resolvedLogGroup });

    var departments = psychUi.filterDepartments(orgUnits, filterState.logGroup);
    var posList = psychUi.filterPositions(positions, filterState.orgUnitId);

    var empList = filterEmployeesByOrg(employees, filterState.positionId, filterState.orgUnitId);
    empList = filterEmployeesByLogGroup(empList, orgUnits, filterState.logGroup, psychUi);
    empList = empList.filter(function (e) {
      return matchesNameQuery(e, filterState.nameQuery);
    });

    var selectedEmployeeId = String(state.employeeId || '').trim();
    var validEmployeeId =
      selectedEmployeeId &&
      empList.some(function (e) {
        return e.id === selectedEmployeeId;
      })
        ? selectedEmployeeId
        : '';

    return {
      logGroups: logGroups,
      departments: departments,
      positions: posList,
      employees: empList,
      resolvedLogGroup: resolvedLogGroup,
      employeeId: validEmployeeId,
      hasActiveFilters: !!(
        normalizeQuery(filterState.nameQuery) ||
        (filterState.logGroup && !psychUi.isAllLogGroup(filterState.logGroup)) ||
        filterState.orgUnitId ||
        filterState.positionId
      ),
    };
  }

  function resetOnChange(changed, current) {
    current = current || {};
    if (changed === 'logGroup') {
      return {
        logGroup: current.logGroup || '',
        orgUnitId: '',
        positionId: '',
        nameQuery: current.nameQuery || '',
        employeeId: '',
      };
    }
    if (changed === 'orgUnitId') {
      return {
        logGroup: current.logGroup || '',
        orgUnitId: current.orgUnitId || '',
        positionId: '',
        nameQuery: current.nameQuery || '',
        employeeId: '',
      };
    }
    if (changed === 'positionId') {
      return {
        logGroup: current.logGroup || '',
        orgUnitId: current.orgUnitId || '',
        positionId: current.positionId || '',
        nameQuery: current.nameQuery || '',
        employeeId: '',
      };
    }
    if (changed === 'nameQuery') {
      return Object.assign({}, current);
    }
    return Object.assign({}, current);
  }

  function employeeEmptyMessage(resolved, psychUi) {
    psychUi = psychUi || getPsychUi();
    if (!resolved.employees.length) {
      if (resolved.hasActiveFilters) return EMPTY_EMPLOYEES_MSG;
      return 'Нет сотрудников';
    }
    return null;
  }

  var api = {
    EMPTY_EMPLOYEES_MSG: EMPTY_EMPLOYEES_MSG,
    PLACEHOLDER_EMPLOYEE: PLACEHOLDER_EMPLOYEE,
    PLACEHOLDER_LOG_GROUP: PLACEHOLDER_LOG_GROUP,
    PLACEHOLDER_DEPARTMENT: PLACEHOLDER_DEPARTMENT,
    PLACEHOLDER_POSITION: PLACEHOLDER_POSITION,
    PLACEHOLDER_NAME: PLACEHOLDER_NAME,
    formatEmployeeName: formatEmployeeName,
    formatEmployeeOptionLabel: formatEmployeeOptionLabel,
    matchesNameQuery: matchesNameQuery,
    filterEmployeesByOrg: filterEmployeesByOrg,
    filterEmployeesByLogGroup: filterEmployeesByLogGroup,
    resolvePicker: resolvePicker,
    resetOnChange: resetOnChange,
    employeeEmptyMessage: employeeEmptyMessage,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  global.AccountEmployeePicker = api;
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
