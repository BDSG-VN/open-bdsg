"use strict";
(() => {
  // Chỉ giữ mã đơn vị trong tab; dữ liệu và quyền luôn đọc lại từ máy chủ.
  let mode = 'legacy', actorId = 'guest', systemAdmin = false, apps = [], units = [], selected = null;
  let status = 'idle', error = '', generation = 0, loadVersion = 0, booted = false, actorRole = '', bootVersion = 0;
  let parentUnit = null, parentToken = null;
  const hooks = new Set();
  const child = window.location.pathname === '/workspace.html' && window.parent !== window;
  if (child) { parentUnit = window.parent.BDSGUnit || null; parentToken = parentUnit?.capture() || null; }
  const initialParent = parentUnit?.snapshot() || null;
  const storageKey = () => 'bdsg-unit-selection:' + encodeURIComponent(actorId);
  const copy = value => value ? {...value} : null;
  const contextKey = () => mode === 'legacy' ? actorId : JSON.stringify([actorId, selected?.id || null, selected?.epoch ?? null, selected?.revision ?? null]);
  function snapshot() {
    return {mode,actorId,systemAdmin,apps:[...apps],units:units.map(copy),selected:copy(selected),status,error,generation};
  }
  function emit(type, reason) { window.dispatchEvent(new window.CustomEvent(type,{detail:{...snapshot(),reason}})); }
  function changed(previous, reason) {
    if (previous !== contextKey()) { generation++; emit('bdsg-unit-changed',reason); }
    emit('bdsg-unit-list-changed',reason);
  }
  function remember() {
    try { if (selected) window.sessionStorage.setItem(storageKey(),selected.id); else window.sessionStorage.removeItem(storageKey()); } catch (_) {}
  }
  function parentCurrent() { return !parentUnit || parentUnit.current(parentToken); }
  function capture() { return Object.freeze({key:contextKey(),generation,actorId}); }
  function current(token) { return !!token && token.key === contextKey() && token.generation === generation && token.actorId === actorId && parentCurrent(); }
  const fail = () => new Error('Phạm vi đơn vị đã thay đổi. Hãy mở lại ứng dụng.');
  function unscoped(path) {
    const route = String(path).split('?')[0];
    return ['/api/me','/api/catalogue','/api/login','/api/logout','/api/ready','/api/health'].includes(route)
      || route.startsWith('/api/auth/') || route === '/api/sessions' || route.startsWith('/api/sessions/')
      || route === '/api/units' || route.startsWith('/api/units/');
  }
  function headers(path) {
    if (unscoped(path)) return {};
    if (!parentCurrent()) throw fail();
    if (!booted) throw new Error('Đang xác minh phạm vi đơn vị.');
    if (mode === 'legacy') return {};
    if (!selected || status !== 'ready') throw new Error('Hãy chọn đơn vị trước khi làm việc.');
    return {'X-BDSG-Unit':selected.id,'X-BDSG-Unit-Epoch':String(selected.epoch),'X-BDSG-Unit-Revision':String(selected.revision)};
  }
  async function refresh(options = {}) {
    if (child) {
      // Lỗi quyền trong cửa sổ con phải gỡ cả phạm vi cha, trước khi đọc lại danh sách.
      if (options.invalidate) {
        if (parentUnit && parentCurrent()) await parentUnit.refresh({invalidate:true});
        return snapshot();
      }
      if (!parentCurrent()) throw fail();
      return snapshot();
    }
    if (mode !== 'units' || actorId === 'guest') return snapshot();
    if (options.invalidate) {
      const previous = contextKey(); selected = null; remember(); status = 'loading'; changed(previous,'invalidated');
    }
    const version = ++loadVersion, actor = actorId;
    status = 'loading'; error = ''; emit('bdsg-unit-list-changed','loading');
    try {
      const response = await window.fetch('/api/units',{credentials:'same-origin',headers:{'X-BDSG-Actor':actor}});
      const data = await response.json();
      if (version !== loadVersion || actor !== actorId) return snapshot();
      if (!response.ok || !Array.isArray(data.units)) throw new Error(data.error || 'Chưa đọc được danh sách đơn vị.');
      const previous = contextKey();
      units = data.units.filter(row => row && typeof row.id === 'string' && typeof row.name === 'string'
        && ['admin','member'].includes(row.role) && Number.isSafeInteger(row.epoch) && row.epoch > 0
        && Number.isSafeInteger(row.revision) && row.revision > 0).map(row => ({id:row.id,name:row.name,role:row.role,epoch:row.epoch,revision:row.revision}));
      if (selected) selected = units.find(row => row.id === selected.id) || null;
      status = 'ready'; remember(); changed(previous, selected ? 'refreshed' : 'membership');
      return snapshot();
    } catch (cause) {
      if (version !== loadVersion || actor !== actorId) return snapshot();
      const previous = contextKey(); selected = null; units = []; remember(); status = 'error'; error = cause.message;
      changed(previous,'unavailable'); return snapshot();
    }
  }
  async function boot(me) {
    const bootTicket = ++bootVersion;
    if (child && booted) {
      if (!parentCurrent() || (me.user?.id || 'guest') !== actorId) throw fail();
      return snapshot();
    }
    const previous = contextKey(), nextActor = me.user?.id || 'guest';
    const sameActor = booted && actorId === nextActor && mode === (me.workspace?.mode === 'units' ? 'units' : 'legacy');
    loadVersion++; actorId = nextActor; actorRole = me.user?.role || '';
    mode = me.workspace?.mode === 'units' ? 'units' : 'legacy'; systemAdmin = me.workspace?.system_admin === true;
    apps = Array.isArray(me.workspace?.apps) ? [...me.workspace.apps] : [];
    if (!sameActor) { units = []; selected = null; }
    booted = true; status = 'ready'; error = '';
    if (child) {
      if (!parentUnit || !parentCurrent()) throw fail();
      const initial = initialParent;
      if (initial.actorId !== actorId || initial.mode !== mode) throw fail();
      units = initial.units.map(copy); selected = copy(initial.selected);
      // Trạng thái tải của cha chỉ tạm thời; phạm vi đã chụp vẫn có hàng rào thế hệ và metadata máy chủ.
      status = selected && initial.status === 'loading' ? 'ready' : initial.status;
      changed(previous,'boot'); return snapshot();
    }
    changed(previous,'boot');
    if (mode === 'units' && actorId !== 'guest') {
      let stored = null;
      if (!sameActor) { try { stored = window.sessionStorage.getItem(storageKey()); } catch (_) {} }
      await refresh();
      if (bootTicket !== bootVersion) return snapshot();
      if (stored && status === 'ready') {
        const row = units.find(item => item.id === stored);
        if (row) { const before = contextKey(); selected = row; remember(); changed(before,'restored'); }
      }
    }
    return snapshot();
  }
  async function switchTo(id) {
    if (child || !parentCurrent()) throw fail();
    const row = units.find(item => item.id === id);
    if (mode !== 'units' || status !== 'ready' || !row) throw new Error('Anh chưa có tư cách thành viên trong đơn vị này.');
    if (selected?.id === id) return snapshot();
    const token = capture();
    for (const hook of hooks) { if (await hook(copy(row),copy(selected)) === false) return snapshot(); }
    if (!current(token)) throw fail();
    const previous = contextKey(); selected = row; remember(); changed(previous,'selected'); return snapshot();
  }
  window.BDSGUnit = Object.freeze({boot,snapshot,contextKey,capture,current,headers,switchTo,refresh,
    beforeSwitch(fn) { hooks.add(fn); return () => hooks.delete(fn); },
    canAdmin() { return parentCurrent() && (mode === 'legacy' ? actorRole === 'quan-tri' : status === 'ready' && selected?.role === 'admin'); }
  });
})();
