"use strict";
(() => {
  const $ = id => document.getElementById(id), unit = window.BDSGUnit;
  const labels = {'nen_tang.danh_sach':'Xem danh mục nền tảng','nen_tang.ket_noi':'Xem trạng thái kết nối',
    'mo_dun.danh_sach':'Xem mô-đun','du_an.danh_sach':'Xem dự án được chọn','cong_viec.danh_sach':'Xem danh sách công việc',
    'cong_viec.chi_tiet':'Xem chi tiết công việc','cong_viec.tao':'Tạo công việc','cong_viec.tiep_tuc':'Tiếp tục công việc','cong_viec.dung':'Dừng công việc'};
  const params = new URLSearchParams(location.hash.slice(1));
  let request = params.get('request'), actor = null, bound = null, expires = 0, generation = 0, busy = false, checking = null;
  if (params.size !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(request || '')) request = null;
  function message(text, error = false) { $('message').textContent = text; $('message').className = error ? 'error' : ''; $('message').setAttribute('role',error ? 'alert' : 'status'); }
  function lock(value) { busy = value; $('consent').setAttribute('aria-busy',String(value)); document.querySelectorAll('button,input,select').forEach(el => el.disabled = value); }
  function clearPermissions() { $('tools').replaceChildren(); $('projects').replaceChildren(); $('permission-form').hidden = true; $('client-name').textContent = ''; $('bound-identity').textContent = ''; }
  function stop(text) {
    generation++; request = null; bound = null; expires = 0; clearPermissions();
    $('unit-panel').hidden = true; $('login-panel').hidden = true; $('retry').hidden = true;
    history.replaceState(null,'',location.pathname); message(text,true);
    $('message').tabIndex = -1; $('message').focus();
  }
  function alive(ticket) { return ticket === generation && request; }
  async function api(path, body, scoped = false) {
    const headers = {'Content-Type':'application/json'};
    if (actor) headers['X-BDSG-Actor'] = actor.id;
    if (scoped) Object.assign(headers,unit.headers(path));
    const response = await fetch(path,{method:body === undefined ? 'GET' : 'POST',credentials:'same-origin',cache:'no-store',headers,
      ...(body === undefined ? {} : {body:JSON.stringify(body)})});
    const data = await response.json();
    if (!response.ok) {
      if ([401,409].includes(response.status) || data.error === 'context_changed') stop('Tài khoản hoặc quyền đã thay đổi. Hãy bắt đầu kết nối lại từ ứng dụng.');
      const error = new Error(data.error || 'Chưa hoàn tất yêu cầu.'); error.status = response.status; throw error;
    }
    return data;
  }
  function choice(container, name, value, title, detail = '') {
    const label = document.createElement('label'); label.className = 'choice';
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = name; input.value = value;
    const span = document.createElement('span'); span.textContent = title;
    if (detail) { const small = document.createElement('small'); small.textContent = detail; span.append(small); }
    label.append(input,span); $(container).append(label);
  }
  async function boot() {
    if (!request) { stop('Yêu cầu kết nối không hợp lệ. Hãy mở lại kết nối từ ứng dụng.'); return; }
    const ticket = generation; lock(true); $('retry').hidden = true; message('Đang xác minh phiên BDSG…');
    try {
      const me = await api('/api/me'); if (!alive(ticket)) return;
      actor = me.user;
      if (me.workspace?.mode !== 'units') { stop('Kết nối theo đơn vị chưa được bật trên bản này.'); return; }
      await unit.boot(me); if (!alive(ticket)) return;
      $('login-panel').hidden = !!actor; $('unit-panel').hidden = !actor;
      if (!actor) { message('Đăng nhập để chọn đơn vị cấp quyền.'); return; }
      const state = unit.snapshot();
      if (state.status !== 'ready') throw new Error('Chưa đọc được quyền đơn vị.');
      $('identity').textContent = actor.name+' · '+actor.id;
      $('unit').replaceChildren(new Option('Chọn đơn vị…',''));
      state.units.forEach(row => $('unit').add(new Option(row.name,row.id)));
      message(state.units.length ? 'Chọn đơn vị trước khi xem yêu cầu của ứng dụng.' : 'Tài khoản này chưa là thành viên đơn vị. Anh có thể đổi tài khoản.');
    } catch (_) { if (alive(ticket)) { message('Chưa xác minh được kết nối. Kiểm tra mạng rồi thử lại.',true); $('retry').hidden = false; } }
    finally { lock(false); }
  }
  $('login-form').onsubmit = async event => {
    event.preventDefault(); if (busy || !request) return;
    const ticket = generation; lock(true);
    try { await api('/api/login',{username:$('username').value,password:$('password').value}); if (alive(ticket)) await boot(); }
    catch (_) { if (alive(ticket)) message('Chưa đăng nhập được. Kiểm tra tên đăng nhập, mật khẩu và thử lại.',true); }
    finally { $('password').value = ''; lock(false); }
  };
  $('inspect').onclick = async () => {
    if (busy || !request || !$('unit').value) { if (!busy) message('Anh cần chọn một đơn vị.',true); return; }
    const ticket = generation; lock(true); message('Đang đọc yêu cầu và phạm vi dự án…');
    try {
      await unit.switchTo($('unit').value); if (!alive(ticket)) return;
      const capture = unit.capture();
      const result = await api('/api/oauth/bind',{request},true); if (!alive(ticket) || !unit.current(capture)) return;
      // Bind trước khi đọc dự án để đổi quyền không tạo biểu mẫu dưới ngữ cảnh khác.
      bound = capture; expires = result.expires;
      const projects = await api('/api/tools',{name:'du_an.danh_sach',arguments:{}},true);
      if (!alive(ticket) || !unit.current(capture)) return;
      if (!projects.ok || !Array.isArray(projects.ket_qua?.projects)) throw new Error('Chưa đọc được dự án.');
      clearPermissions(); $('client-name').textContent = result.client.name;
      $('bound-identity').textContent = actor.name+' · '+unit.snapshot().selected.name;
      result.tools.forEach(tool => choice('tools','tool',tool,labels[tool] || tool,tool));
      projects.ket_qua.projects.filter(row => !row.archived).forEach(row => choice('projects','project',row.id,row.name));
      choice('projects','project','','Công việc độc lập','Công việc không thuộc một dự án.');
      $('deadline').textContent = 'Chấp thuận trước '+new Date(expires*1000).toLocaleTimeString('vi-VN')+'.';
      $('unit-panel').hidden = true; $('permission-form').hidden = false;
      message('Chưa có quyền nào được cấp. Anh kiểm tra và chọn trước khi cho phép.');
      $('app-title').tabIndex = -1; $('app-title').focus();
    } catch (_) { if (alive(ticket)) { clearPermissions(); message('Chưa đọc được yêu cầu. Nếu yêu cầu đã hết hạn, hãy kết nối lại từ ứng dụng.',true); $('retry').hidden = false; } }
    finally { lock(false); }
  };
  function verifyContext() {
    if (checking) return checking;
    if (!bound || !request) return Promise.resolve();
    checking = (async () => {
      const me = await api('/api/me');
      if (!request) return;
      if (me.user?.id !== actor.id) { stop('Phiên đăng nhập đã thay đổi. Hãy bắt đầu kết nối lại từ ứng dụng.'); return; }
      await unit.refresh();
      if (bound && !unit.current(bound)) stop('Quyền đơn vị đã thay đổi. Hãy bắt đầu kết nối lại từ ứng dụng.');
    })().finally(() => { checking = null; });
    return checking;
  }
  async function decide(approve) {
    if (busy || !bound || !request) return;
    const ticket = generation, body = {request,approve};
    if (approve) {
      const tools = [...document.querySelectorAll('input[name=tool]:checked')].map(el => el.value);
      const project_ids = [...document.querySelectorAll('input[name=project]:checked')].map(el => el.value);
      if (!tools.length) { message('Chọn ít nhất một công cụ hoặc từ chối kết nối.',true); return; }
      if (tools.some(tool => tool.startsWith('du_an.') || tool.startsWith('cong_viec.')) && !project_ids.length) { message('Chọn phạm vi dự án cho các công cụ đã chọn.',true); return; }
      body.selection = {tools,project_ids,expires_in:Number($('duration').value)};
      if (tools.some(tool => ['cong_viec.tao','cong_viec.tiep_tuc','cong_viec.dung'].includes(tool))) body.selection.task_profile = {allow_ai:false};
    }
    lock(true); message(approve ? 'Đang cấp quyền đã chọn…' : 'Đang từ chối kết nối…');
    let submitted = false;
    try {
      await verifyContext(); if (!alive(ticket) || !unit.current(bound)) return;
      submitted = true; const result = await api('/api/oauth/decide',body,true);
      if (!alive(ticket) || !unit.current(bound)) return;
      await verifyContext(); if (!alive(ticket)) return;
      const target = new URL(result.redirect_uri);
      if (target.protocol !== 'https:' && !(target.protocol === 'http:' && ['127.0.0.1','[::1]'].includes(target.hostname))) throw new Error('Địa chỉ quay lại không hợp lệ.');
      clearPermissions(); history.replaceState(null,'',location.pathname); request = null; bound = null;
      message(approve ? 'Đã cấp quyền. Đang quay lại ứng dụng…' : 'Đã từ chối. Đang quay lại ứng dụng…');
      location.replace(target.href);
    } catch (_) {
      if (alive(ticket)) {
        if (submitted) stop('Chưa xác minh được kết quả chấp thuận. Không gửi lại tự động; hãy kiểm tra kết nối đã cấp hoặc bắt đầu lại từ ứng dụng.');
        else message('Chưa xác minh được quyền hiện tại. Kiểm tra mạng rồi thử lại.',true);
      }
    } finally { lock(false); }
  }
  $('permission-form').onsubmit = event => { event.preventDefault(); decide(true); };
  $('deny').onclick = () => decide(false);
  $('logout').onclick = async () => { if (busy) return; lock(true); try { await api('/api/logout',{}); stop('Đã đăng xuất. Hãy bắt đầu kết nối lại bằng tài khoản anh muốn dùng.'); } catch (_) { message('Chưa đăng xuất được. Kiểm tra mạng rồi thử lại.',true); } finally { lock(false); } };
  $('retry').onclick = () => { if (bound) stop('Yêu cầu đã gắn với phiên duyệt. Hãy bắt đầu kết nối lại từ ứng dụng.'); else boot(); };
  window.addEventListener('bdsg-unit-changed',() => { if (bound && !unit.current(bound)) stop('Đơn vị hoặc quyền đã thay đổi. Hãy bắt đầu kết nối lại từ ứng dụng.'); });
  window.addEventListener('focus',() => { verifyContext().catch(() => message('Chưa xác minh lại được phiên. Kiểm tra mạng trước khi chấp thuận.',true)); });
  window.setInterval(() => { if (request && expires && Date.now() >= expires*1000) stop('Yêu cầu đã hết hạn. Hãy bắt đầu kết nối lại từ ứng dụng.'); },1000);
  boot();
})();
