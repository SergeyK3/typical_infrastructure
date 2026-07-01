/**
 * UX hardening for local «Добавить аккаунт» modal — Stage 2G.
 * Mirrors server policies (app/auth/policies.py) without changing RBAC.
 */
(function (global) {
  'use strict';

  var PLATFORM_ONLY_ROLE_CODES = ['system_admin', 'developer'];
  var ORG_ASSIGNABLE_ROLE_CODES = ['admin', 'hr', 'manager', 'employee'];

  var MSG_EMPLOYEE_HAS_ACCOUNT = 'Для выбранного сотрудника уже существует учётная запись.';
  var MSG_LOGIN_EXISTS = 'Пользователь с таким логином уже существует.';
  var MSG_FILL_REQUIRED = 'Заполните сотрудника, логин и пароль';

  var RU_TO_LAT = [
    ['щ', 'shch'], ['ш', 'sh'], ['ч', 'ch'], ['ц', 'ts'], ['ю', 'yu'], ['я', 'ya'],
    ['ё', 'e'], ['ж', 'zh'], ['х', 'kh'], ['ъ', ''], ['ь', ''],
    ['а', 'a'], ['б', 'b'], ['в', 'v'], ['г', 'g'], ['д', 'd'], ['е', 'e'],
    ['з', 'z'], ['и', 'i'], ['й', 'y'], ['к', 'k'], ['л', 'l'], ['м', 'm'],
    ['н', 'n'], ['о', 'o'], ['п', 'p'], ['р', 'r'], ['с', 's'], ['т', 't'],
    ['у', 'u'], ['ф', 'f'], ['ы', 'y'], ['э', 'e'],
  ];

  function normalizeLogin(value) {
    return String(value == null ? '' : value).trim().toLowerCase();
  }

  function transliterateRu(text) {
    var s = String(text == null ? '' : text).toLowerCase();
    var out = '';
    for (var i = 0; i < s.length; i++) {
      var ch = s.charAt(i);
      var mapped = null;
      for (var j = 0; j < RU_TO_LAT.length; j++) {
        var pair = RU_TO_LAT[j];
        if (s.indexOf(pair[0], i) === i) {
          mapped = pair[1];
          i += pair[0].length - 1;
          break;
        }
      }
      if (mapped !== null) out += mapped;
      else if (/[a-z0-9]/.test(ch)) out += ch;
    }
    return out.replace(/[^a-z0-9]+/g, '');
  }

  function loginFromEmail(email) {
    var raw = String(email == null ? '' : email).trim();
    var at = raw.indexOf('@');
    if (at <= 0) return '';
    var local = raw.slice(0, at).toLowerCase().replace(/[^a-z0-9._-]/g, '');
    return local.length >= 2 ? local : '';
  }

  function loginSet(existingLogins) {
    var set = Object.create(null);
    (existingLogins || []).forEach(function (login) {
      var key = normalizeLogin(login);
      if (key) set[key] = true;
    });
    return set;
  }

  function loginTaken(login, existingLogins) {
    var key = normalizeLogin(login);
    if (!key) return false;
    return !!loginSet(existingLogins)[key];
  }

  function filterRolesForAccountForm(roles, isGlobalAdmin) {
    var list = Array.isArray(roles) ? roles.slice() : [];
    if (isGlobalAdmin) return list;
    return list.filter(function (role) {
      return ORG_ASSIGNABLE_ROLE_CODES.indexOf(role.code) !== -1;
    });
  }

  function isPlatformRoleCode(code) {
    return PLATFORM_ONLY_ROLE_CODES.indexOf(String(code || '')) !== -1;
  }

  function employeeHasAccount(employee) {
    return !!(employee && employee.account_id);
  }

  function findEmployeeById(employees, employeeId) {
    var id = String(employeeId || '').trim();
    if (!id) return null;
    return (employees || []).find(function (e) {
      return e && e.id === id;
    }) || null;
  }

  function suggestLogin(employee, existingLogins) {
    if (!employee) return '';
    var taken = loginSet(existingLogins);
    function isTaken(candidate) {
      var key = normalizeLogin(candidate);
      return key && taken[key];
    }

    var base = loginFromEmail(employee.email);
    if (!base) base = transliterateRu(employee.last_name);
    if (!base && employee.first_name) base = transliterateRu(employee.first_name);
    if (!base) return '';

    if (!isTaken(base)) return base;

    var initial = transliterateRu(employee.first_name).charAt(0);
    if (initial) {
      var dotted = base + '.' + initial;
      if (!isTaken(dotted)) return dotted;
    }
    return base;
  }

  function validateAccountCreateForm(input) {
    input = input || {};
    var employeeId = String(input.employeeId || '').trim();
    var login = String(input.login || '').trim();
    var password = String(input.password || '');
    var employee = input.employee || findEmployeeById(input.employees, employeeId);

    if (!employeeId || !login || !password) {
      return { ok: false, error: MSG_FILL_REQUIRED, field: 'form' };
    }
    if (employeeHasAccount(employee)) {
      return { ok: false, error: MSG_EMPLOYEE_HAS_ACCOUNT, field: 'employee' };
    }
    if (loginTaken(login, input.existingLogins)) {
      return { ok: false, error: MSG_LOGIN_EXISTS, field: 'login' };
    }
    return { ok: true, error: '', field: '' };
  }

  function employeeAccountHint(employee) {
    return employeeHasAccount(employee) ? MSG_EMPLOYEE_HAS_ACCOUNT : '';
  }

  function loginDuplicateHint(login, existingLogins) {
    return loginTaken(login, existingLogins) ? MSG_LOGIN_EXISTS : '';
  }

  var api = {
    PLATFORM_ONLY_ROLE_CODES: PLATFORM_ONLY_ROLE_CODES,
    ORG_ASSIGNABLE_ROLE_CODES: ORG_ASSIGNABLE_ROLE_CODES,
    MSG_EMPLOYEE_HAS_ACCOUNT: MSG_EMPLOYEE_HAS_ACCOUNT,
    MSG_LOGIN_EXISTS: MSG_LOGIN_EXISTS,
    MSG_FILL_REQUIRED: MSG_FILL_REQUIRED,
    transliterateRu: transliterateRu,
    loginFromEmail: loginFromEmail,
    loginTaken: loginTaken,
    filterRolesForAccountForm: filterRolesForAccountForm,
    isPlatformRoleCode: isPlatformRoleCode,
    employeeHasAccount: employeeHasAccount,
    findEmployeeById: findEmployeeById,
    suggestLogin: suggestLogin,
    validateAccountCreateForm: validateAccountCreateForm,
    employeeAccountHint: employeeAccountHint,
    loginDuplicateHint: loginDuplicateHint,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  global.AccountCreateForm = api;
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
