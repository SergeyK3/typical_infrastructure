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

  function skillAssessmentWorkspaceHref(ctx) {
    return ctx && ctx.clientId
      ? '/api/skill-assessment/workspace?client_id=' + encodeURIComponent(ctx.clientId)
      : '/api/skill-assessment/workspace';
  }

  const groups = [
    { id: 'platform', label: 'Typical Infrastructure', level: 'platform', order: 10 },
    { id: 'globalCatalogs', label: 'Глобальные справочники', level: 'platform', order: 20 },
    { id: 'organizationCore', label: 'Справочники организации', level: 'organization', order: 30 },
    { id: 'organizationAdmin', label: 'Администрирование', level: 'organization', order: 35 },
    { id: 'hrPluginModules', label: 'HR-МОДУЛИ', level: 'module', order: 50 },
  ];

  const platformNavigation = [
    { id: 'platform.clients', label: 'Клиенты', level: 'platform', groupId: 'platform', href: '/clients', order: 10, requiresGlobalAdmin: true },
    { id: 'platform.orgAdmins', label: 'Админы организаций', level: 'platform', groupId: 'platform', href: '/org-admins', order: 15, requiresGlobalAdmin: true },
    { id: 'platform.users', label: 'Пользователи', level: 'platform', groupId: 'platform', href: '/users', order: 20, requiresGlobalAdmin: true },
    { id: 'platform.onboarding', label: 'Мастер onboarding', level: 'platform', groupId: 'platform', href: '/wizard', order: 30, requiresGlobalAdmin: true },
    { id: 'globalCatalogs.overview', label: 'Обзор', level: 'platform', groupId: 'globalCatalogs', href: '/global', order: 10, requiresGlobalAdmin: true },
    { id: 'globalCatalogs.templateOrg', label: 'Типовая оргструктура', level: 'platform', groupId: 'globalCatalogs', href: '/global/template-org', order: 20, requiresGlobalAdmin: true },
    { id: 'globalCatalogs.positions', label: 'Типовые должности', level: 'platform', groupId: 'globalCatalogs', href: '/global/positions', order: 30, requiresGlobalAdmin: true },
    {
      id: 'globalCatalogs.regulations',
      label: 'Типовые регламенты',
      level: 'platform',
      groupId: 'globalCatalogs',
      href: regulationsHref,
      order: 40,
      elementId: 'topNavRegulations',
      title: 'Общесистемный нормативный реестр',
      requiresGlobalAdmin: true,
    },
    { id: 'globalCatalogs.kpi', label: 'Типовые KPI', level: 'platform', groupId: 'globalCatalogs', href: '/global/kpi', order: 50, requiresGlobalAdmin: true },
    { id: 'globalCatalogs.skills', label: 'Типовые навыки', level: 'platform', groupId: 'globalCatalogs', href: '/global/skills', order: 60, requiresGlobalAdmin: true },
    { id: 'developerTools.api', label: 'API', level: 'platform', groupId: 'globalCatalogs', href: '/docs', order: 70, className: 'api-link', requiresGlobalAdmin: true },
  ];

  const organizationNavigation = [
    { id: 'organization.orgUnits', label: 'Локальные подразделения', level: 'organization', groupId: 'organizationCore', tab: 'org', order: 10 },
    { id: 'organization.positions', label: 'Локальные должности', level: 'organization', groupId: 'organizationCore', tab: 'positions', order: 20 },
    { id: 'organization.regulations', label: 'Локальные регламенты', level: 'organization', groupId: 'organizationCore', tab: 'client-regs', order: 30 },
    { id: 'organization.kpi', label: 'Локальные KPI', level: 'organization', groupId: 'organizationCore', tab: 'local-kpi', order: 40 },
    { id: 'organization.skills', label: 'Локальные навыки', level: 'organization', groupId: 'organizationCore', tab: 'local-skills', order: 50 },
    { id: 'organization.employees', label: 'Сотрудники', level: 'organization', groupId: 'organizationCore', tab: 'employees', order: 60 },
  ];

  const organizationAdminNavigation = [
    { id: 'organization.accounts', label: 'Аккаунты', level: 'organization', groupId: 'organizationAdmin', tab: 'accounts', order: 10 },
  ];

  const moduleNavigation = [];

  const hrModuleVisibilityDefaults = {
    'hr.psychTesting': true,
    'hr.learning': true,
    'hr.attestations': true,
    'hr.adminAssignments': true,
    'hr.disciplinaryActions': true,
    'hr.certificates': true,
    'hr.aiAssistants': true,
    'hr.documentFlow': true,
    'hr.compliance': true,
    'hr.medicalCheckups': true,
    'hr.accreditations': true,
    'hr.analytics': true,
  };

  const organizationModuleVisibility = {
    version: 1,
    defaults: hrModuleVisibilityDefaults,
    clientCodes: {},
    clients: {},
  };

  function mergeVisibility(base, override) {
    return Object.assign({}, base || {}, override || {});
  }

  function getOrganizationModuleVisibility(ctx) {
    const context = ctx || {};
    const config = organizationModuleVisibility || {};
    const clientCode = context.clientCode || (context.organization && context.organization.code) || '';
    const clientId = context.clientId || (context.organization && context.organization.clientId) || '';
    return mergeVisibility(
      mergeVisibility(config.defaults, config.clientCodes && config.clientCodes[clientCode]),
      config.clients && config.clients[clientId]
    );
  }

  const DISCONNECTED_HR_MODULE_TITLE = 'Модуль пока не подключён';
  const disconnectedHrModuleClass = 'sidebar-item-muted sidebar-item-disabled';

  const hrModuleNavigation = [
    {
      id: 'hr.psychTesting',
      label: 'Психологические тестирования',
      level: 'module',
      groupId: 'hrPluginModules',
      tab: 'psych-testing',
      href: clientTabHref('psych-testing'),
      order: 10,
      requiresClient: true,
      visibilityKey: 'hr.psychTesting',
      className: 'sidebar-item-prominent',
      title: 'Подключён модуль психологического тестирования (Telegram + JSON-сессии)',
    },
    { id: 'hr.learning', label: 'Обучение', level: 'module', groupId: 'hrPluginModules', tab: 'learning', href: clientTabHref('learning'), order: 20, requiresClient: true, visibilityKey: 'hr.learning', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    {
      id: 'hr.attestations',
      label: 'Аттестации',
      level: 'module',
      groupId: 'hrPluginModules',
      href: skillAssessmentWorkspaceHref,
      order: 30,
      requiresClient: true,
      visibilityKey: 'hr.attestations',
      className: 'sidebar-item-prominent',
      title: 'Подключён модуль опросов по регламентам',
      isActive: function (ctx) {
        return ctx && ctx.currentPath === '/api/skill-assessment/workspace';
      },
    },
    { id: 'hr.adminAssignments', label: 'Адм назначения', level: 'module', groupId: 'hrPluginModules', tab: 'admin-assignments', href: clientTabHref('admin-assignments'), order: 40, requiresClient: true, visibilityKey: 'hr.adminAssignments', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.disciplinaryActions', label: 'Дисциплинарные поощрения и взыскания', level: 'module', groupId: 'hrPluginModules', tab: 'disciplinary-actions', href: clientTabHref('disciplinary-actions'), order: 50, requiresClient: true, visibilityKey: 'hr.disciplinaryActions', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.certificates', label: 'Сертификаты', level: 'module', groupId: 'hrPluginModules', tab: 'certificates', href: clientTabHref('certificates'), order: 60, requiresClient: true, visibilityKey: 'hr.certificates', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.aiAssistants', label: 'AI-ассистенты', level: 'module', groupId: 'hrPluginModules', tab: 'ai-assistants', href: clientTabHref('ai-assistants'), order: 70, requiresClient: true, visibilityKey: 'hr.aiAssistants', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.documentFlow', label: 'Документооборот', level: 'module', groupId: 'hrPluginModules', tab: 'document-flow', href: clientTabHref('document-flow'), order: 80, requiresClient: true, visibilityKey: 'hr.documentFlow', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.compliance', label: 'Комплаенс', level: 'module', groupId: 'hrPluginModules', tab: 'compliance', href: clientTabHref('compliance'), order: 90, requiresClient: true, visibilityKey: 'hr.compliance', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.medicalCheckups', label: 'Медосмотры', level: 'module', groupId: 'hrPluginModules', tab: 'medical-checkups', href: clientTabHref('medical-checkups'), order: 100, requiresClient: true, visibilityKey: 'hr.medicalCheckups', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.accreditations', label: 'Аккредитации', level: 'module', groupId: 'hrPluginModules', tab: 'accreditations', href: clientTabHref('accreditations'), order: 110, requiresClient: true, visibilityKey: 'hr.accreditations', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
    { id: 'hr.analytics', label: 'Аналитика', level: 'module', groupId: 'hrPluginModules', tab: 'analytics', href: clientTabHref('analytics'), order: 120, requiresClient: true, visibilityKey: 'hr.analytics', className: disconnectedHrModuleClass, title: DISCONNECTED_HR_MODULE_TITLE },
  ];

  const moduleRegistry = [
    {
      id: 'hr.core',
      label: 'Базовый HR-контур',
      defaultEnabled: true,
      items: [],
    },
  ];

  function getDefaultActiveModules() {
    return moduleRegistry.filter((m) => m.defaultEnabled).map((m) => m.id);
  }

  window.SidebarRegistry = {
    groups,
    platformNavigation,
    organizationNavigation,
    organizationAdminNavigation,
    moduleNavigation,
    hrModuleNavigation,
    moduleRegistry,
    organizationModuleVisibility,
    getDefaultActiveModules,
    getOrganizationModuleVisibility,
  };
})();
