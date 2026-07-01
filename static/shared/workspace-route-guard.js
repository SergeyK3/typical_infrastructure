// route: /static/shared/workspace-route-guard.js | file: static/shared/workspace-route-guard.js
(function () {
  var PLATFORM_PATH = /^\/(?:users|clients|org-admins|wizard|global|regulations)(?:\/|$)/;

  function isClientWorkspacePath(pathname) {
    return /^\/client\/[^/]+/.test(pathname || '');
  }

  function forceHardNavigation() {
    window.location.assign(window.location.pathname + window.location.search + window.location.hash);
  }

  if (!isClientWorkspacePath(window.location.pathname)) {
    if (PLATFORM_PATH.test(window.location.pathname)) {
      forceHardNavigation();
    } else if (document.getElementById('workspaceSidebar')) {
      window.location.replace('/clients');
    }
    return;
  }

  window.addEventListener('pageshow', function () {
    if (PLATFORM_PATH.test(window.location.pathname)) {
      forceHardNavigation();
    }
  });

  window.addEventListener('popstate', function () {
    if (PLATFORM_PATH.test(window.location.pathname)) {
      forceHardNavigation();
    }
  });
})();
