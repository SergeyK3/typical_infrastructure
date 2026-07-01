// route: /static/shared/platform-sidebar-init.js | file: static/shared/platform-sidebar-init.js
(function () {
  function boot() {
    var opts = window.__platformSidebarOptions || {};
    if (!opts.rootId) opts.rootId = 'platformSidebar';
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
