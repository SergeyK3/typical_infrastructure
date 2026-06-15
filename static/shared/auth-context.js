// route: /static/shared/auth-context.js | file: static/shared/auth-context.js
(function () {
  let cachedMe = null;
  let loadPromise = null;

  function normalizeMe(data) {
    if (!data || typeof data !== 'object') return null;
    return {
      accountId: data.account_id || '',
      login: data.login || '',
      roles: Array.isArray(data.roles) ? data.roles.slice() : [],
      clientId: data.client_id || '',
      isSystem: !!data.is_system,
      isGlobalAdmin: !!data.is_global_admin,
      isOrgAdmin: !!data.is_org_admin,
      allowedClients: Array.isArray(data.allowed_clients) ? data.allowed_clients.slice() : [],
    };
  }

  async function load(force) {
    if (!force && cachedMe) return cachedMe;
    if (!force && loadPromise) return loadPromise;
    loadPromise = fetch('/api/auth/me', { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) {
          cachedMe = null;
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        cachedMe = normalizeMe(data);
        return cachedMe;
      })
      .catch(function () {
        cachedMe = null;
        return null;
      })
      .finally(function () {
        loadPromise = null;
      });
    return loadPromise;
  }

  function getMe() {
    return cachedMe;
  }

  function clear() {
    cachedMe = null;
    loadPromise = null;
  }

  window.AuthContext = {
    load: load,
    getMe: getMe,
    clear: clear,
    isGlobalAdmin: function () {
      return !!(cachedMe && cachedMe.isGlobalAdmin);
    },
    isOrgAdmin: function () {
      return !!(cachedMe && cachedMe.isOrgAdmin);
    },
  };
})();
