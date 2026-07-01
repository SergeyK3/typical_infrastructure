/** Sidebar organization block label layout — Stage 2E.1 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHARED = path.resolve(__dirname, '../../static/shared');

function createElement(tag) {
  const node = {
    tagName: String(tag || '').toUpperCase(),
    className: '',
    textContent: '',
    title: '',
    hidden: false,
    children: [],
    dataset: {},
    style: {},
    classList: {
      _classes: new Set(),
      add(...names) {
        names.forEach((n) => this._classes.add(n));
        node.className = [...this._classes].join(' ');
      },
      toggle(name, force) {
        if (force === true) this.add(name);
        else if (force === false) this._classes.delete(name);
        else if (this._classes.has(name)) this._classes.delete(name);
        else this.add(name);
        node.className = [...this._classes].join(' ');
      },
      contains(name) {
        return this._classes.has(name);
      },
      remove(...names) {
        names.forEach((n) => this._classes.delete(n));
        node.className = [...this._classes].join(' ');
      },
    },
    setAttribute(name, value) {
      if (name === 'aria-live') node._ariaLive = value;
      if (name === 'aria-expanded') node._ariaExpanded = value;
      if (name === 'aria-controls') node._ariaControls = value;
    },
    appendChild(child) {
      node.children.push(child);
      return child;
    },
  };
  return node;
}

function findByClass(node, className) {
  if (!node) return null;
  if (node.className && node.className.split(/\s+/).includes(className)) return node;
  for (const child of node.children || []) {
    const hit = findByClass(child, className);
    if (hit) return hit;
  }
  return null;
}

function buildSandbox() {
  const root = createElement('aside');
  root.id = 'workspaceSidebar';
  root.classList.remove = function (...names) {
    names.forEach((n) => this._classes.delete(n));
    root.className = [...this._classes].join(' ');
  };
  const sandbox = {
    window: null,
    document: {
      getElementById(id) {
        return id === 'workspaceSidebar' ? root : null;
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
    location: { pathname: '/client/c1', hash: '#accounts', origin: 'http://127.0.0.1:8100', search: '' },
    console,
  };
  sandbox.window = sandbox;
  return { sandbox, root };
}

function runScript(filename, sandbox) {
  const code = fs.readFileSync(path.join(SHARED, filename), 'utf8');
  vm.runInNewContext(code, sandbox, { filename });
}

{
  const { sandbox, root } = buildSandbox();
  runScript('sidebar-registry.js', sandbox);
  runScript('client-display.js', sandbox);
  runScript('sidebar.js', sandbox);

  sandbox.window.UiTheme = { mountToggle() {} };

  sandbox.window.SidebarRenderer.renderWorkspaceSidebar({
    rootId: 'workspaceSidebar',
    context: {
      currentPath: '/client/c1',
      currentHash: '#accounts',
      clientId: 'c1',
      clientName: 'ММЦ',
      clientFullName: 'Многопрофильный медицинский центр г. Астаны',
      clientCode: 'mmc',
      activeTab: 'accounts',
      focusMode: 'organization',
    },
  });

  const nameEl = findByClass(root, 'sidebar-organization-name');
  const fullEl = findByClass(root, 'sidebar-organization-full-name');
  const metaEl = findByClass(root, 'sidebar-organization-meta');

  assert.equal(nameEl.textContent, 'ММЦ');
  assert.equal(nameEl.title, 'Многопрофильный медицинский центр г. Астаны');
  assert.equal(fullEl.textContent, 'Многопрофильный медицинский центр г. Астаны');
  assert.equal(metaEl.textContent, 'Код: mmc');
}

{
  const { sandbox, root } = buildSandbox();
  runScript('sidebar-registry.js', sandbox);
  runScript('client-display.js', sandbox);
  runScript('sidebar.js', sandbox);

  sandbox.window.UiTheme = { mountToggle() {} };

  sandbox.window.SidebarRenderer.renderWorkspaceSidebar({
    rootId: 'workspaceSidebar',
    context: {
      currentPath: '/client/c2',
      clientId: 'c2',
      clientName: 'Full Organization Only',
      clientFullName: 'Full Organization Only',
      clientCode: 'fullorg',
      activeTab: 'org',
      focusMode: 'organization',
    },
  });

  const nameEl = findByClass(root, 'sidebar-organization-name');
  const fullEl = findByClass(root, 'sidebar-organization-full-name');
  const metaEl = findByClass(root, 'sidebar-organization-meta');

  assert.equal(nameEl.textContent, 'Full Organization Only');
  assert.equal(nameEl.title, '');
  assert.equal(fullEl, null, 'no duplicate full-name line when compact equals full');
  assert.equal(metaEl.textContent, 'Код: fullorg');
}

console.log('test_sidebar_organization_label.mjs: all passed');
