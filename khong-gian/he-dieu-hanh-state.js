(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.BDSGOSState = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';

  const token = value => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,120}$/.test(value);
  const identity = value => typeof value === 'string' && value.length <= 160 ? value : '';

  // Chỉ phân loại địa chỉ cho trình duyệt phía khách; không phân giải DNS hay gọi proxy.
  function normalizeAddress(value) {
    if (typeof value !== 'string') return null;
    const input = value.trim();
    if (!input || input.length > 2048 || /[\u0000-\u001f\u007f\\]/.test(input)) return null;
    const explicitScheme = /^[a-z][a-z0-9+.-]*:/i.test(input);
    const looksLikeUrl = explicitScheme || /^[^\s/]+\.[^\s/]+(?:[/?#]|$)/.test(input) || input.startsWith('//');
    if (!looksLikeUrl) {
      if (/^(?:localhost|[\w-]+\.(?:local|lan|internal|home))(?::\d+)?(?:[/?#]|$)/i.test(input) || /^\d+(?:[/?#]|$)/.test(input) || input.includes('@')) return null;
      return { kind: 'search', query: input };
    }
    if (explicitScheme && !/^https:\/\//i.test(input)) return null;
    let url;
    try { url = new URL(explicitScheme ? input : `https://${input.replace(/^\/\//, '')}`); } catch (_) { return null; }
    const rawAuthority = (explicitScheme ? input.replace(/^https:\/\//i, '') : input.replace(/^\/\//, '')).split(/[/?#]/)[0];
    if (url.protocol !== 'https:' || url.username || url.password || rawAuthority.includes('%') || (url.port && url.port !== '443')) return null;
    const host = url.hostname.toLowerCase().replace(/\.$/, '');
    // Từ chối mọi địa chỉ IP (kể cả dạng rút gọn/mã hoá) để không mở mạng nội bộ.
    if (!host.includes('.') || /^[\d.]+$/.test(host) || host.includes(':') || !/^[a-z0-9.-]+$/.test(host)) return null;
    const labels = host.split('.');
    if (labels.some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return null;
    if (!/^[a-z]{2,63}$|^xn--[a-z0-9-]+$/.test(labels[labels.length - 1])) return null;
    if (/(?:^|\.)(?:localhost|local|localdomain|lan|internal|intranet|corp|private|home|test|invalid|example|onion|arpa|alt)$/.test(host) || /(?:^|\.)home\.arpa$/.test(host)) return null;
    url.hostname = host;
    return { kind: 'url', url: url.href };
  }

  function create(options = {}) {
    if (!options || typeof options !== 'object' || !Array.isArray(options.apps)) throw new TypeError('Cần danh mục ứng dụng.');
    const maxSessions = options.maxSessions === undefined ? 8 : options.maxSessions;
    if (!Number.isInteger(maxSessions) || maxSessions < 1 || maxSessions > 8) throw new TypeError('Giới hạn phiên từ 1 đến 8.');
    const apps = new Map();
    for (const app of options.apps) {
      if (!app || !token(app.id) || apps.has(app.id) || !['internal', 'browser', 'external'].includes(app.kind)) throw new TypeError('Ứng dụng không hợp lệ.');
      if (app.kind === 'internal' && (typeof app.route !== 'string' || !/^#[a-zA-Z0-9_-]+$/.test(app.route))) throw new TypeError('Đường dẫn nội bộ không hợp lệ.');
      if (app.kind === 'external' && normalizeAddress(app.url)?.kind !== 'url') throw new TypeError('Địa chỉ ứng dụng không hợp lệ.');
      apps.set(app.id, true);
    }
    let identityId = options.identityId === undefined ? 'guest' : identity(options.identityId);
    let sessions = [];
    let mru = [];
    let activeSessionId = null;
    let serial = 0;
    const usedIds = new Set();

    function snapshot() {
      return { version: 1, identityId, activeSessionId, sessions: sessions.map(session => ({ ...session })), mru: [...mru] };
    }
    function activate(id) {
      const session = sessions.find(item => item.id === id);
      if (!session) return null;
      sessions.forEach(item => { if (item.status === 'active') item.status = 'background'; });
      session.status = 'active';
      activeSessionId = id;
      mru = [id, ...mru.filter(item => item !== id)];
      return snapshot();
    }
    function nextActive() {
      activeSessionId = null;
      const next = mru.find(id => sessions.some(item => item.id === id && item.status !== 'minimized'));
      if (next) activate(next);
    }
    function open(appId, config = {}) {
      if (!apps.has(appId) || !config || typeof config !== 'object') return null;
      if (config.newInstance !== true) {
        const existing = mru.map(id => sessions.find(item => item.id === id)).find(item => item?.appId === appId);
        if (existing) {
          activate(existing.id);
          return { ...sessions.find(item => item.id === existing.id) };
        }
      }
      if (sessions.length >= maxSessions) return null;
      let id;
      if (typeof options.idFactory === 'function') id = options.idFactory();
      else if (typeof globalThis.crypto?.randomUUID === 'function') id = globalThis.crypto.randomUUID();
      else {
        do { id = `session-${++serial}`; } while (usedIds.has(id));
      }
      if (!token(id) || usedIds.has(id)) return null;
      usedIds.add(id);
      sessions.push({ id, appId, status: 'background' });
      activate(id);
      return { ...sessions.find(item => item.id === id) };
    }
    function minimize(id) {
      const session = sessions.find(item => item.id === id);
      if (!session) return null;
      session.status = 'minimized';
      if (activeSessionId === id) nextActive();
      return snapshot();
    }
    function close(id) {
      if (!sessions.some(item => item.id === id)) return null;
      sessions = sessions.filter(item => item.id !== id);
      mru = mru.filter(item => item !== id);
      if (activeSessionId === id) nextActive();
      return snapshot();
    }
    function resetIdentity(value = '') {
      identityId = identity(value);
      sessions = [];
      mru = [];
      activeSessionId = null;
      return snapshot();
    }
    // Dữ liệu khôi phục không được thay danh mục, URL, danh tính hay nội dung ứng dụng.
    function restore(saved) {
      sessions = [];
      mru = [];
      activeSessionId = null;
      if (!saved || typeof saved !== 'object' || saved.version !== 1 || saved.identityId !== identityId || !Array.isArray(saved.sessions)) return snapshot();
      const seen = new Set();
      for (const item of saved.sessions.slice(0, 100)) {
        if (sessions.length === maxSessions) break;
        if (!item || !token(item.id) || seen.has(item.id) || !apps.has(item.appId) || !['active', 'background', 'minimized'].includes(item.status)) continue;
        seen.add(item.id);
        usedIds.add(item.id);
        sessions.push({ id: item.id, appId: item.appId, status: item.status === 'minimized' ? 'minimized' : 'background' });
      }
      if (Array.isArray(saved.mru)) mru = [...new Set(saved.mru.filter(id => seen.has(id)))];
      mru.push(...sessions.map(item => item.id).filter(id => !mru.includes(id)));
      const active = sessions.find(item => item.id === saved.activeSessionId && item.status !== 'minimized');
      if (active) activate(active.id);
      return snapshot();
    }
    return Object.freeze({ open, activate, minimize, close, snapshot, restore, resetIdentity });
  }
  function createReadBroker({ getIdentity, maxConcurrent = 2 } = {}) {
    if (typeof getIdentity !== 'function' || !Number.isInteger(maxConcurrent) || maxConcurrent < 1 || maxConcurrent > 8) throw new TypeError('Cấu hình hàng đợi đọc không hợp lệ.');
    const reads = new Map();
    const queue = [];
    let generation = 0;
    let active = 0;
    const changed = () => new Error('Phiên tài khoản đã thay đổi. Hãy mở lại ứng dụng.');
    const valid = item => item.generation === generation && item.actor === getIdentity();
    function drain() {
      while (active < maxConcurrent && queue.length) {
        const item = queue.shift();
        active++;
        Promise.resolve().then(() => {
          if (!valid(item)) throw changed();
          return item.load();
        }).then(value => {
          if (!valid(item)) throw changed();
          // Chụp JSON ngay khi loader trả về để các cửa sổ không chia sẻ dữ liệu mutable.
          return JSON.stringify(value);
        }).then(json => finish(item, null, json), error => finish(item, error));
      }
    }
    function finish(item, error, json) {
      if (reads.get(item.key) === item) reads.delete(item.key);
      active--;
      if (error) item.reject(error);
      else item.resolve(json);
      drain();
    }
    function read(key, actor, load) {
      if (typeof key !== 'string' || !key.trim() || key.length > 256 || /[\u0000-\u001f\u007f]/.test(key) || typeof actor !== 'string' || !actor || actor.length > 160 || typeof load !== 'function') return Promise.reject(new TypeError('Yêu cầu đọc không hợp lệ.'));
      if (actor !== getIdentity()) return Promise.reject(changed());
      const fullKey = JSON.stringify([actor, key]);
      let item = reads.get(fullKey);
      if (!item) {
        if (queue.length >= 64) return Promise.reject(new Error('Hàng đợi đọc đã đầy. Hãy thử lại.'));
        item = { key: fullKey, actor, load, generation };
        item.promise = new Promise((resolve, reject) => { item.resolve = resolve; item.reject = reject; });
        reads.set(fullKey, item);
        queue.push(item);
        drain();
      }
      return item.promise.then(json => {
        if (!valid(item)) throw changed();
        return JSON.parse(json);
      });
    }
    function reset() {
      generation++;
      queue.length = 0;
      for (const item of reads.values()) item.reject(changed());
      reads.clear();
    }
    return Object.freeze({ read, reset });
  }
  return Object.freeze({ create, normalizeAddress, createReadBroker });
});
