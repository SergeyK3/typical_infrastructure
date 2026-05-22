// route: /static/shared/sidebar.js | file: static/shared/sidebar.js
(function () {
  const NEW_FOCUS_KEY = 'sidebarFocus:v1';
  const LEGACY_WORKSPACE_FOCUS_KEY = 'workspaceSidebarFocus';
  const SECTION_STATE_KEY = 'sidebarSections:v1';

  function registry() {
    return window.SidebarRegistry || {
      groups: [],
      platformNavigation: [],
      organizationNavigation: [],
      moduleNavigation: [],
      hrModuleNavigation: [],
      getDefaultActiveModules: function () { return ['hr.core']; },
    };
  }

  function normalizeFocusMode(mode) {
    if (mode === 'organization' || mode === 'org') return 'organization';
    if (mode === 'modules' || mode === 'apps') return 'modules';
    return 'full';
  }

  function legacyFocusMode(mode) {
    const normalized = normalizeFocusMode(mode);
    if (normalized === 'organization') return 'org';
    if (normalized === 'modules') return 'apps';
    return 'full';
  }

  function readStoredFocus() {
    try {
      const nextValue = localStorage.getItem(NEW_FOCUS_KEY);
      if (nextValue === 'full' || nextValue === 'organization' || nextValue === 'modules') return nextValue;
      const legacyValue = localStorage.getItem(LEGACY_WORKSPACE_FOCUS_KEY);
      if (legacyValue === 'full' || legacyValue === 'org' || legacyValue === 'apps') return normalizeFocusMode(legacyValue);
    } catch (_) {}
    return 'organization';
  }

  function persistFocus(mode) {
    const normalized = normalizeFocusMode(mode);
    try {
      localStorage.setItem(NEW_FOCUS_KEY, normalized);
      localStorage.setItem(LEGACY_WORKSPACE_FOCUS_KEY, legacyFocusMode(normalized));
    } catch (_) {}
  }

  function normalizeCollapsedSections(value) {
    return Array.isArray(value) ? value.filter(Boolean) : [];
  }

  function readStoredSections() {
    try {
      const raw = localStorage.getItem(SECTION_STATE_KEY);
      if (!raw) return [];
      return normalizeCollapsedSections(JSON.parse(raw).collapsed);
    } catch (_) {}
    return [];
  }

  function persistSections(collapsedSections) {
    try {
      localStorage.setItem(SECTION_STATE_KEY, JSON.stringify({ collapsed: normalizeCollapsedSections(collapsedSections) }));
    } catch (_) {}
  }

  function normalizeModuleVisibility(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return Object.assign({}, value);
  }

  function currentTabFromHash(hashValue, pathValue) {
    const path = pathValue || window.location.pathname || '';
    if (!/^\/client(?:\/|$)/.test(path)) return '';
    const hash = (hashValue || '').replace(/^#/, '');
    const routedTabs = [
      'positions', 'client-regs', 'local-kpi', 'local-skills', 'employees', 'accounts',
      'psych-testing', 'learning', 'attestations', 'admin-assignments', 'disciplinary-actions',
      'certificates', 'ai-assistants', 'document-flow', 'compliance', 'medical-checkups',
      'accreditations', 'analytics',
    ];
    return routedTabs.includes(hash) ? hash : 'org';
  }

  function currentTabFromLocation() {
    return currentTabFromHash(window.location.hash || '', window.location.pathname);
  }

  function readClientIdFromPath(pathValue) {
    const path = pathValue || window.location.pathname || '';
    const m = path.match(/^\/client\/([^/]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function hasOwn(obj, key) {
    return Object.prototype.hasOwnProperty.call(obj || {}, key);
  }

  function clientSnapshot(client) {
    if (!client) return null;
    return {
      id: client.id || '',
      name: client.name || '',
      code: client.code || '',
    };
  }

  function resolveModuleVisibility(context, source) {
    const reg = registry();
    let visibility = {};
    try {
      if (typeof reg.getOrganizationModuleVisibility === 'function') {
        visibility = normalizeModuleVisibility(reg.getOrganizationModuleVisibility(context));
      }
    } catch (_) {
      visibility = {};
    }
    return Object.assign(visibility, normalizeModuleVisibility(source && source.moduleVisibility));
  }

  const SidebarContext = (function () {
    let state = {};

    function defaultActiveModules() {
      const reg = registry();
      return reg.getDefaultActiveModules ? reg.getDefaultActiveModules() : ['hr.core'];
    }

    function contextFromSource(raw) {
      const source = raw || {};
      const currentPath = hasOwn(source, 'currentPath') && source.currentPath != null
        ? source.currentPath
        : (state.currentPath || window.location.pathname);
      const currentHash = hasOwn(source, 'currentHash') && source.currentHash != null
        ? source.currentHash
        : (state.currentHash || window.location.hash || '');
      const urlClientId = readClientIdFromPath(currentPath);
      const activeModules = Array.isArray(source.activeModules) && source.activeModules.length
        ? source.activeModules
        : (Array.isArray(state.activeModules) && state.activeModules.length ? state.activeModules : defaultActiveModules());
      const collapsedSections = hasOwn(source, 'collapsedSections')
        ? normalizeCollapsedSections(source.collapsedSections)
        : (Array.isArray(state.collapsedSections) ? state.collapsedSections : readStoredSections());
      const activeTab = hasOwn(source, 'activeTab') && source.activeTab != null
        ? source.activeTab
        : (state.activeTab || currentTabFromHash(currentHash, currentPath));
      const focusMode = normalizeFocusMode(
        hasOwn(source, 'focusMode') && source.focusMode != null ? source.focusMode : (state.focusMode || readStoredFocus())
      );
      const clientId = hasOwn(source, 'clientId') && source.clientId != null
        ? source.clientId
        : (state.clientId || urlClientId || '');
      const clientName = hasOwn(source, 'clientName') && source.clientName != null ? source.clientName : (state.clientName || '');
      const clientCode = hasOwn(source, 'clientCode') && source.clientCode != null ? source.clientCode : (state.clientCode || '');
      const organization = {
        clientId: clientId || '',
        name: clientName || '',
        code: clientCode || '',
      };
      const moduleVisibility = resolveModuleVisibility({
        currentPath,
        currentHash,
        clientId: clientId || '',
        clientName: clientName || '',
        clientCode: clientCode || '',
        organization,
      }, source);

      return {
        currentPath,
        currentHash,
        clientId: clientId || '',
        clientName: clientName || '',
        clientCode: clientCode || '',
        organization,
        activeTab,
        activeModules,
        moduleVisibility,
        collapsedSections,
        focusMode,
        fallbackReason: source.fallbackReason || '',
      };
    }

    function getState() {
      return Object.assign({}, state, {
        organization: Object.assign({}, state.organization || {}),
        activeModules: (state.activeModules || []).slice(),
        moduleVisibility: Object.assign({}, state.moduleVisibility || {}),
        collapsedSections: (state.collapsedSections || []).slice(),
      });
    }

    function commit(next, options) {
      state = next;
      if (!options || options.persistFocus !== false) persistFocus(state.focusMode);
      return getState();
    }

    function resolveContext(raw, options) {
      return commit(contextFromSource(raw), options || { persistFocus: false });
    }

    function update(partial, options) {
      const patch = partial || {};
      const next = Object.assign({}, state, patch);
      if (!hasOwn(patch, 'moduleVisibility')) delete next.moduleVisibility;
      return resolveContext(next, options);
    }

    function resolveOrganization(options) {
      const opts = options || {};
      const clients = Array.isArray(opts.clients) ? opts.clients : [];
      const requestedClientId = hasOwn(opts, 'requestedClientId')
        ? opts.requestedClientId
        : (hasOwn(opts, 'clientId') ? opts.clientId : (state.clientId || readClientIdFromPath(opts.currentPath)));
      let selected = null;
      let fallbackReason = '';

      if (requestedClientId) {
        selected = clients.find((client) => client && client.id === requestedClientId) || null;
        if (!selected) fallbackReason = 'stale-client';
      } else if (opts.fallbackToFirst !== false && clients.length) {
        selected = clients[0];
        fallbackReason = 'missing-client';
      }

      const snapshot = clientSnapshot(selected);
      const context = resolveContext({
        currentPath: opts.currentPath,
        currentHash: opts.currentHash,
        clientId: snapshot ? snapshot.id : '',
        clientName: snapshot ? snapshot.name : '',
        clientCode: snapshot ? snapshot.code : '',
        activeTab: opts.activeTab,
        focusMode: opts.focusMode,
        fallbackReason,
      }, { persistFocus: false });

      return {
        client: selected,
        clientId: context.clientId,
        context,
        fallbackReason,
      };
    }

    function isSectionCollapsed(sectionId) {
      return normalizeCollapsedSections(state.collapsedSections).includes(sectionId);
    }

    function setSectionCollapsed(sectionId, collapsed) {
      if (!sectionId) return getState();
      const sections = normalizeCollapsedSections(state.collapsedSections);
      const exists = sections.includes(sectionId);
      const nextSections = collapsed && !exists
        ? sections.concat(sectionId)
        : sections.filter((id) => id !== sectionId);
      const nextState = update({ collapsedSections: nextSections }, { persistFocus: false });
      persistSections(nextState.collapsedSections);
      return nextState;
    }

    function toggleSection(sectionId) {
      return setSectionCollapsed(sectionId, !isSectionCollapsed(sectionId));
    }

    return {
      NEW_FOCUS_KEY,
      LEGACY_WORKSPACE_FOCUS_KEY,
      SECTION_STATE_KEY,
      normalizeFocusMode,
      legacyFocusMode,
      readClientIdFromPath,
      currentTabFromLocation,
      resolveContext,
      resolveOrganization,
      update,
      getState,
      isSectionCollapsed,
      setSectionCollapsed,
      toggleSection,
      getStoredFocus: function (options) {
        const mode = readStoredFocus();
        return options && options.legacy ? legacyFocusMode(mode) : mode;
      },
    };
  })();

  function buildContext(raw) {
    return SidebarContext.resolveContext(raw, { persistFocus: false });
  }

  function resolveHref(item, ctx) {
    if (typeof item.href === 'function') return item.href(ctx);
    return item.href || '#';
  }

  function isItemVisible(item, ctx) {
    if (item.requiresClient && !ctx.clientId) return false;
    if (item.requiresModule && !ctx.activeModules.includes(item.requiresModule)) return false;
    if (item.visibilityKey && ctx.moduleVisibility && ctx.moduleVisibility[item.visibilityKey] === false) return false;
    if (typeof item.isVisible === 'function') return item.isVisible(ctx);
    return true;
  }

  function isItemActive(item, ctx) {
    if (typeof item.isActive === 'function') return item.isActive(ctx);
    if (item.tab) return item.tab === ctx.activeTab;
    if (!item.href || typeof item.href === 'function') return false;
    return ctx.currentPath === item.href;
  }

  function createItem(item, ctx) {
    const a = document.createElement('a');
    a.className = 'sidebar-item' + (item.className ? ' ' + item.className : '');
    if (item.elementId) a.id = item.elementId;
    if (item.id) a.dataset.navId = item.id;
    if (item.title) a.title = item.title;
    if (item.tab) {
      a.href = resolveHref(item, ctx);
      a.dataset.tab = item.tab;
    } else {
      a.href = resolveHref(item, ctx);
    }
    if (isItemActive(item, ctx)) a.classList.add('active');
    a.textContent = item.label;
    return a;
  }

  function visibleItems(items, ctx) {
    return sorted(items).filter((item) => isItemVisible(item, ctx));
  }

  function findNavigationItemByTab(tab) {
    const reg = registry();
    return []
      .concat(reg.organizationNavigation || [], reg.moduleNavigation || [], reg.hrModuleNavigation || [])
      .find((item) => item && item.tab === tab) || null;
  }

  function isTabVisible(tab, rawContext) {
    const item = findNavigationItemByTab(tab);
    if (!item) return true;
    const ctx = buildContext(rawContext || SidebarContext.getState());
    return isItemVisible(item, ctx);
  }

  function hasActiveItem(items, ctx) {
    return visibleItems(items, ctx).some((item) => isItemActive(item, ctx));
  }

  function createSectionLabel(text) {
    const label = document.createElement('div');
    label.className = 'sidebar-section-label';
    label.textContent = text;
    return label;
  }

  function createOrganizationSummary(ctx) {
    const card = document.createElement('div');
    card.className = 'sidebar-organization' + (ctx.clientId ? ' selected' : ' missing');
    card.setAttribute('aria-live', 'polite');

    const eyebrow = document.createElement('div');
    eyebrow.className = 'sidebar-organization-eyebrow';
    eyebrow.textContent = 'Выбранная организация';
    card.appendChild(eyebrow);

    const name = document.createElement('div');
    name.className = 'sidebar-organization-name';
    name.textContent = ctx.clientName || (ctx.clientId ? ctx.clientId : 'Не выбрана');
    card.appendChild(name);

    const meta = document.createElement('div');
    meta.className = 'sidebar-organization-meta';
    meta.textContent = ctx.clientCode || (ctx.clientId ? 'ID: ' + ctx.clientId : 'Навигация доступна без контекста');
    card.appendChild(meta);

    return card;
  }

  function createCollapsibleSection(group, items, ctx, options) {
    const opts = options || {};
    const section = document.createElement('div');
    const sectionId = group.id;
    const bodyId = 'sidebar-section-body-' + sectionId;
    const collapsed = ctx.collapsedSections.includes(sectionId);
    const active = hasActiveItem(items, ctx);

    section.className = 'sidebar-section sidebar-section-' + sectionId;
    if (collapsed) section.classList.add('collapsed');
    if (active) section.classList.add('active');
    section.dataset.sidebarSection = sectionId;

    const header = document.createElement('button');
    header.type = 'button';
    header.className = 'sidebar-section-toggle' + (opts.headerClass ? ' ' + opts.headerClass : '');
    header.dataset.sidebarSectionToggle = sectionId;
    if (opts.focusMode) header.dataset.focusMode = opts.focusMode;
    header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    header.setAttribute('aria-controls', bodyId);
    header.title = collapsed ? 'Развернуть раздел' : 'Свернуть раздел';

    const chevron = document.createElement('span');
    chevron.className = 'sidebar-section-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = collapsed ? '▸' : '▾';
    header.appendChild(chevron);

    const label = document.createElement('span');
    label.className = 'sidebar-section-title';
    label.textContent = group.label;
    header.appendChild(label);
    section.appendChild(header);

    if (opts.hint) section.appendChild(opts.hint);

    const body = document.createElement('div');
    body.className = 'sidebar-section-body';
    body.id = bodyId;
    body.hidden = collapsed;
    renderItems(body, items, ctx);
    section.appendChild(body);

    return section;
  }

  function sorted(items) {
    return (items || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
  }

  function renderItems(parent, items, ctx) {
    visibleItems(items, ctx).forEach((item) => {
      parent.appendChild(createItem(item, ctx));
    });
  }

  function groupById(groups, id) {
    return groups.find((group) => group.id === id) || { id, label: id };
  }

  function applyWorkspaceSidebarFocus(mode, options) {
    const root = document.getElementById((options && options.rootId) || 'workspaceSidebar');
    const btn = document.getElementById('btnWorkspaceSidebarExpand');
    const normalized = normalizeFocusMode(mode);
    if (!root) return;
    root.classList.remove('sidebar-focus-org', 'sidebar-focus-apps');
    if (normalized === 'organization') root.classList.add('sidebar-focus-org');
    if (normalized === 'modules') root.classList.add('sidebar-focus-apps');
    if (btn) btn.hidden = normalized === 'full';
    SidebarContext.update({ focusMode: normalized }, { persistFocus: !options || options.persist !== false });
  }

  function applySectionCollapsed(root, sectionId, collapsed) {
    if (!root || !sectionId) return;
    const section = root.querySelector('[data-sidebar-section="' + sectionId + '"]');
    const toggle = root.querySelector('[data-sidebar-section-toggle="' + sectionId + '"]');
    if (!section || !toggle) return;
    const body = section.querySelector('.sidebar-section-body');
    section.classList.toggle('collapsed', collapsed);
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    toggle.title = collapsed ? 'Развернуть раздел' : 'Свернуть раздел';
    const chevron = toggle.querySelector('.sidebar-section-chevron');
    if (chevron) chevron.textContent = collapsed ? '▸' : '▾';
    if (body) body.hidden = collapsed;
  }

  function toggleWorkspaceSidebarSection(sectionId, options) {
    const root = document.getElementById((options && options.rootId) || 'workspaceSidebar');
    const nextState = SidebarContext.toggleSection(sectionId);
    applySectionCollapsed(root, sectionId, nextState.collapsedSections.includes(sectionId));
    return nextState;
  }

  function renderWorkspaceSidebar(options) {
    const opts = options || {};
    const root = document.getElementById(opts.rootId || 'workspaceSidebar');
    if (!root) return null;
    const reg = registry();
    const ctx = buildContext(opts.context || opts);
    const groups = reg.groups || [];

    root.innerHTML = '';
    root.classList.add('sidebar', 'workspace-sidebar');

    const expand = document.createElement('button');
    expand.type = 'button';
    expand.className = 'sidebar-expand-full';
    expand.id = 'btnWorkspaceSidebarExpand';
    expand.hidden = true;
    expand.title = 'Показать глобальное меню и полный список разделов';
    expand.textContent = '▴ Полное меню';
    root.appendChild(expand);

    const top = document.createElement('div');
    top.className = 'sidebar-top';
    top.appendChild(createCollapsibleSection(
      groupById(groups, 'platform'),
      (reg.platformNavigation || []).filter((item) => item.groupId === 'platform'),
      ctx,
      { headerClass: 'sidebar-brand', focusMode: 'full' }
    ));
    top.appendChild(createCollapsibleSection(
      groupById(groups, 'globalCatalogs'),
      (reg.platformNavigation || []).filter((item) => item.groupId === 'globalCatalogs'),
      ctx,
      { focusMode: 'full' }
    ));
    root.appendChild(top);

    const middle = document.createElement('div');
    middle.className = 'sidebar-middle';
    middle.appendChild(createOrganizationSummary(ctx));
    const hint = document.createElement('div');
    hint.className = 'sidebar-muted';
    hint.style.fontSize = '0.78rem';
    hint.style.margin = '-0.35rem 0 0.5rem 0';
    hint.style.lineHeight = '1.35';
    hint.innerHTML = 'Просмотр и правки в разрезе <strong>выбранной</strong> организации';
    middle.appendChild(createCollapsibleSection(
      groupById(groups, 'organizationCore'),
      reg.organizationNavigation,
      ctx,
      { hint, focusMode: 'organization' }
    ));
    root.appendChild(middle);

    const divider = document.createElement('div');
    divider.className = 'sidebar-divider';
    divider.setAttribute('aria-hidden', 'true');
    root.appendChild(divider);

    const moduleItems = visibleItems(reg.moduleNavigation, ctx);
    const hrPluginItems = visibleItems(reg.hrModuleNavigation, ctx);
    if (moduleItems.length || hrPluginItems.length) {
      const apps = document.createElement('div');
      apps.className = 'sidebar-apps';
      apps.id = 'sidebarApps';
      apps.setAttribute('role', 'region');
      apps.setAttribute('aria-label', 'Дополнительные модули');
      if (moduleItems.length) {
        apps.appendChild(createCollapsibleSection(
          groupById(groups, 'hrModules'),
          reg.moduleNavigation,
          ctx,
          { focusMode: 'modules' }
        ));
      }
      if (hrPluginItems.length) {
        apps.appendChild(createCollapsibleSection(
          groupById(groups, 'hrPluginModules'),
          reg.hrModuleNavigation,
          ctx,
          { focusMode: 'modules' }
        ));
      }
      root.appendChild(apps);
    }

    applyWorkspaceSidebarFocus(ctx.focusMode, { persist: false });
    if (window.UiTheme) window.UiTheme.mountToggle(root);
    return ctx;
  }

  window.SidebarContext = SidebarContext;
  window.SidebarRenderer = {
    NEW_FOCUS_KEY,
    LEGACY_WORKSPACE_FOCUS_KEY,
    SECTION_STATE_KEY,
    normalizeFocusMode,
    legacyFocusMode,
    getContext: SidebarContext.getState,
    updateContext: SidebarContext.update,
    toggleWorkspaceSidebarSection,
    isTabVisible,
    getStoredWorkspaceSidebarFocus: function (options) {
      return SidebarContext.getStoredFocus(options);
    },
    applyWorkspaceSidebarFocus,
    renderWorkspaceSidebar,
  };
})();
