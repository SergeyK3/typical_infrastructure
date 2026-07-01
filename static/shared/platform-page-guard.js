// route: /static/shared/platform-page-guard.js | file: static/shared/platform-page-guard.js
(function () {
  var expected = document.body && document.body.getAttribute('data-platform-page');
  if (!expected) return;

  function hasWorkspaceDom() {
    return !!(
      document.getElementById('workspaceSidebar')
      || document.getElementById('clientSelector')
      || document.getElementById('panel-employees')
    );
  }

  function recoverPlatformPage() {
    var target = window.location.pathname + window.location.search + window.location.hash;
    window.location.replace(target);
  }

  if (hasWorkspaceDom()) {
    recoverPlatformPage();
    return;
  }

  window.addEventListener('pageshow', function (ev) {
    if (hasWorkspaceDom()) {
      recoverPlatformPage();
      return;
    }
    if (ev.persisted) {
      window.location.reload();
    }
  });
})();
