// route: /static/shared/sidebar-registry.js | file: static/shared/sidebar-registry.js
(function () {
  function regulationsHref(ctx) {
    return ctx && ctx.clientId
      ? '/regulations?from_client=' + encodeURIComponent(ctx.clientId)
      : '/regulations';
  }

  function clientTabHref(tab) {
    return function (ctx) {
      return ctx && ctx.clientId
        ? '/client/' + encodeURIComponent(ctx.clientId) + '#' + encodeURIComponent(tab)
        : '#';
    };
  }

  const groups = [
    { id: 'platform', label: 'Typical Infrastructure', level: 'platform', order: 10 },
    { id: 'globalCatalogs', label: 'Глобальные справочники', level: 'platform', order: 20 },
    { id: 'organizationCore', label: 'Справочники организации', level: 'organization', order: 30 },
    { id: 'hrModules', label: 'Приложения', level: 'module', order: 40 },
    { id: 'hrPluginModules', label: 'HR-МОДУЛИ', level: 'module', order: 50 },
  ];

  const platformNavigation = [
    { id: 'platform.clients', label: 'Клиенты', level: 'platform', groupId: 'platform', href: '/clients', order: 10 },
    { id: 'platform.users', label: 'Пользователи', level: 'platform', groupId: 'platform', href: '/users', order: 20 },
    { id: 'platform.onboarding', label: 'Мастер onboarding', level: 'platform', groupId: 'platform', href: '/wizard', order: 30 },
    { id: 'globalCatalogs.overview', label: 'Обзор', level: 'platform', groupId: 'globalCatalogs', href: '/global', order: 10 },
    { id: 'globalCatalogs.templateOrg', label: 'Типовая оргструктура', level: 'platform', groupId: 'globalCatalogs', href: '/global/template-org', order: 20 },
    { id: 'globalCatalogs.positions', label: 'Типовые должности', level: 'platform', groupId: 'globalCatalogs', href: '/global/positions', order: 30 },
    { id: 'globalCatalogs.kpi', label: 'Типовые KPI', level: 'platform', groupId: 'globalCatalogs', href: '/global/kpi', order: 40 },
    {
      id: 'globalCatalogs.regulations',
      label: 'Типовые регламенты',
      level: 'platform',
      groupId: 'globalCatalogs',
      href: regulationsHref,
      order: 50,
      elementId: 'topNavRegulations',
      title: 'Общесистемный нормативный реестр',
    },
    { id: 'developerTools.api', label: 'API', level: 'platform', groupId: 'globalCatalogs', href: '/docs', order: 60, className: 'api-link' },
  ];

  const organizationNavigation = [
    { id: 'organization.orgUnits', label: 'Подразделения', level: 'organization', groupId: 'organizationCore', tab: 'org', order: 10 },
    { id: 'organization.positions', label: 'Должности', level: 'organization', groupId: 'organizationCore', tab: 'positions', order: 20 },
  ];

  const moduleNavigation = [
    { id: 'hr.regulations', label: 'Регламенты и KPI', level: 'module', groupId: 'hrModules', tab: 'client-regs', order: 10, requiresModule: 'hr.core' },
    { id: 'hr.employees', label: 'Сотрудники', level: 'module', groupId: 'hrModules', tab: 'employees', order: 20, requiresModule: 'hr.core' },
    { id: 'hr.accounts', label: 'Аккаунты', level: 'module', groupId: 'hrModules', tab: 'accounts', order: 30, requiresModule: 'hr.core' },
  ];

  const hrModuleNavigation = [
    { id: 'hr.psychTesting', label: 'Психологические тестирования', level: 'module', groupId: 'hrPluginModules', tab: 'psych-testing', href: clientTabHref('psych-testing'), order: 10, requiresClient: true },
    { id: 'hr.learning', label: 'Обучение', level: 'module', groupId: 'hrPluginModules', tab: 'learning', href: clientTabHref('learning'), order: 20, requiresClient: true },
    { id: 'hr.attestations', label: 'Аттестации', level: 'module', groupId: 'hrPluginModules', tab: 'attestations', href: clientTabHref('attestations'), order: 30, requiresClient: true },
  ];

  const moduleRegistry = [
    {
      id: 'hr.core',
      label: 'Базовый HR-контур',
      defaultEnabled: true,
      items: ['hr.regulations', 'hr.employees', 'hr.accounts'],
    },
  ];

  function getDefaultActiveModules() {
    return moduleRegistry.filter((m) => m.defaultEnabled).map((m) => m.id);
  }

  window.SidebarRegistry = {
    groups,
    platformNavigation,
    organizationNavigation,
    moduleNavigation,
    hrModuleNavigation,
    moduleRegistry,
    getDefaultActiveModules,
  };
})();
