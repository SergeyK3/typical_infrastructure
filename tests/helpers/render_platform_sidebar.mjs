/**
 * Render platform sidebar HTML in Node (no browser) for regression tests.
 * Mirrors browser flow: registry + sidebar renderer + AuthContext + init options.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const SHARED = path.join(ROOT, 'static', 'shared');

function createElement(tag) {
  const node = {
    tagName: String(tag || '').toUpperCase(),
    className: '',
    id: '',
    href: '',
    title: '',
    innerHTML: '',
    textContent: '',
    hidden: false,
    dataset: {},
    children: [],
    classList: {
      _classes: new Set(),
      add(...names) {
        names.forEach((n) => this._classes.add(n));
        node.className = [...this._classes].join(' ');
      },
      contains(name) {
        return this._classes.has(name);
      },
      remove(...names) {
        names.forEach((n) => this._classes.delete(n));
        node.className = [...this._classes].join(' ');
      },
      toggle(name, force) {
        if (force === true) this.add(name);
        else if (force === false) this.remove(name);
        else if (this._classes.has(name)) this.remove(name);
        else this.add(name);
      },
    },
    setAttribute(name, value) {
      if (name === 'id') node.id = value;
      if (name === 'aria-expanded') node._ariaExpanded = value;
      if (name === 'aria-controls') node._ariaControls = value;
      if (name === 'aria-live') node._ariaLive = value;
    },
    getAttribute(name) {
      if (name === 'aria-expanded') return node._ariaExpanded;
      if (name === 'aria-controls') return node._ariaControls;
      return null;
    },
    appendChild(child) {
      node.children.push(child);
      child.parentNode = node;
      return child;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
  return node;
}

function serializeNode(node) {
  if (!node) return '';
  if (node.tagName === 'A') {
    const cls = node.className ? ` class="${node.className}"` : '';
    const href = node.href ? ` href="${node.href}"` : '';
    const id = node.id ? ` id="${node.id}"` : '';
    const dataNav = node.dataset.navId ? ` data-nav-id="${node.dataset.navId}"` : '';
    return `<a${id}${href}${cls}${dataNav}>${node.textContent || ''}</a>`;
  }
  const tag = (node.tagName || 'div').toLowerCase();
  const cls = node.className ? ` class="${node.className}"` : '';
  const id = node.id ? ` id="${node.id}"` : '';
  const inner = node.children.map(serializeNode).join('');
  return `<${tag}${id}${cls}>${inner}</${tag}>`;
}

function buildSandbox(options) {
  const roots = new Map();
  const root = createElement('aside');
  root.id = options.rootId || 'platformSidebar';
  roots.set(root.id, root);

  const sandbox = {
    window: null,
    document: {
      getElementById(id) {
        return roots.get(id) || null;
      },
      createElement(tag) {
        return createElement(tag);
      },
    },
    localStorage: {
      _data: {},
      getItem(key) {
        return Object.prototype.hasOwnProperty.call(this._data, key) ? this._data[key] : null;
      },
      setItem(key, value) {
        this._data[key] = String(value);
      },
    },
    location: {
      pathname: options.currentPath || '/users',
      hash: '',
      origin: 'http://127.0.0.1:8100',
      search: options.locationSearch || '',
    },
    console,
  };
  sandbox.window = sandbox;
  return { sandbox, root };
}

function runScript(filename, sandbox) {
  const code = fs.readFileSync(path.join(SHARED, filename), 'utf8');
  vm.runInNewContext(code, sandbox, { filename });
}

export function renderPlatformSidebarHtml(options = {}) {
  const { sandbox, root } = buildSandbox(options);
  sandbox.window.__platformSidebarOptions = {
    rootId: 'platformSidebar',
    bottomHintHtml: options.bottomHintHtml || '',
  };
  sandbox.window.UiTheme = { mountToggle() {} };

  const authMe = options.authMe ?? null;
  sandbox.window.AuthContext = {
    cached: authMe,
    load() {
      return Promise.resolve(authMe);
    },
    getMe() {
      return authMe;
    },
    isGlobalAdmin() {
      return !!(authMe && authMe.isGlobalAdmin);
    },
    isOrgAdmin() {
      return !!(authMe && authMe.isOrgAdmin);
    },
  };

  runScript('sidebar-registry.js', sandbox);
  runScript('sidebar.js', sandbox);

  const boot = `
    (function () {
      var opts = window.__platformSidebarOptions || {};
      if (!opts.rootId) opts.rootId = 'platformSidebar';
      opts.currentPath = ${JSON.stringify(options.currentPath || '/users')};
      if (window.AuthContext && typeof window.AuthContext.isGlobalAdmin === 'function') {
        opts.isGlobalAdmin = window.AuthContext.isGlobalAdmin();
      }
      if (window.AuthContext && typeof window.AuthContext.isOrgAdmin === 'function') {
        opts.isOrgAdmin = window.AuthContext.isOrgAdmin();
      }
      window.SidebarRenderer.renderPlatformSidebar(opts);
    })();
  `;
  vm.runInNewContext(boot, sandbox);

  return serializeNode(root);
}

function parseArgs(argv) {
  const out = {
    currentPath: '/users',
    isGlobalAdmin: true,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--path' && argv[i + 1]) {
      out.currentPath = argv[++i];
    } else if (arg === '--no-global-admin') {
      out.isGlobalAdmin = false;
    }
  }
  return out;
}

if (process.argv[1] && process.argv[1].endsWith('render_platform_sidebar.mjs')) {
  const args = parseArgs(process.argv);
  const html = renderPlatformSidebarHtml({
    currentPath: args.currentPath,
    authMe: args.isGlobalAdmin
      ? { isGlobalAdmin: true, isOrgAdmin: false }
      : null,
  });
  process.stdout.write(html);
}
