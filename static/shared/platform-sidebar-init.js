// route: /static/shared/platform-sidebar-init.js | file: static/shared/platform-sidebar-init.js
(function () {
  var booted = false;

  function applyAuthOptions(opts) {
    if (window.AuthContext && typeof window.AuthContext.isGlobalAdmin === 'function') {
      opts.isGlobalAdmin = window.AuthContext.isGlobalAdmin();
    }
    if (window.AuthContext && typeof window.AuthContext.isOrgAdmin === 'function') {
      opts.isOrgAdmin = window.AuthContext.isOrgAdmin();
    }
    return opts;
  }

  function boot() {
    if (booted) return;
    booted = true;
    var opts = window.__platformSidebarOptions || {};
    if (!opts.rootId) opts.rootId = 'platformSidebar';
    opts.currentPath = window.location.pathname;
    applyAuthOptions(opts);
    if (window.SidebarRenderer && typeof window.SidebarRenderer.renderPlatformSidebar === 'function') {
      window.SidebarRenderer.renderPlatformSidebar(opts);
    }
  }

  if (window.AuthContext && typeof window.AuthContext.load === 'function') {
    window.AuthContext.load().finally(boot);
  } else {
    boot();
  }
})();
