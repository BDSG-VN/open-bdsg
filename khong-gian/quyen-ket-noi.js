"use strict";
(() => {
  const tools = {'nen_tang.danh_sach':'Xem danh mục nền tảng','nen_tang.ket_noi':'Xem trạng thái kết nối','mo_dun.danh_sach':'Xem mô-đun',
    'du_an.danh_sach':'Xem dự án','cong_viec.danh_sach':'Xem danh sách công việc','cong_viec.chi_tiet':'Xem chi tiết công việc',
    'cong_viec.tao':'Tạo công việc','cong_viec.tiep_tuc':'Tiếp tục công việc','cong_viec.dung':'Dừng công việc'};
  const taskTools = new Set(['cong_viec.tao','cong_viec.tiep_tuc','cong_viec.dung']);
  let host = null, revision = 0, tab = 'grants', rows = [], form = null, projects = [], modules = [], secret = '', busy = false, projectNames = new Map();
  const unit = () => window.BDSGUnit;
  const when = value => new Date(value*1000).toLocaleString('vi-VN');
  function clearSecret() { secret = ''; host?.querySelector('#connection-once')?.remove(); }
  function reset() { revision++; clearSecret(); if (host?.isConnected) host.replaceChildren(); host = null; rows = []; projects = []; modules = []; projectNames.clear(); form = null; busy = false; }
  function capture() { return {revision,actor:state.user?.id,scope:unit().capture()}; }
  function current(token) { return host?.isConnected && token.revision === revision && token.actor === state.user?.id && state.view === 'account' && unit().current(token.scope); }
  const choice = (name,value,title,detail='') => `<label class="connection-choice"><input type="checkbox" name="${esc(name)}" value="${esc(value)}"><span>${esc(title)}${detail ? `<small>${esc(detail)}</small>` : ''}</span></label>`;
  const chosen = name => [...host.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
  function notice(message,error=false) { const el = host?.querySelector('#connection-message'); if (el) {el.textContent = message; el.setAttribute('role',error?'alert':'status');} }
  function render(message='',error=false) {
    if (!host?.isConnected) return;
    const scope = unit().snapshot(), clients = tab === 'clients', selected = scope.selected;
    host.innerHTML = `<h2>Quyền kết nối ứng dụng</h2><p class="sessions-note">Các quyền này độc lập với phiên đăng nhập web. Đăng xuất web không thay thế thu hồi kết nối.</p>
      <div class="connection-tabs" role="group" aria-label="Loại quyền kết nối"><button type="button" class="button" data-connection-tab="grants" aria-pressed="${!clients}">Quyền trong đơn vị</button>${scope.systemAdmin?`<button type="button" class="button" data-connection-tab="clients" aria-pressed="${clients}">Ứng dụng OAuth</button>`:''}</div>
      <p id="connection-message" class="connection-message" role="${error?'alert':'status'}">${esc(message)}</p>
      <div class="connection-heading"><p class="sessions-note">${clients?'Chủ quản đăng ký trần công cụ; từng người dùng vẫn phải chấp thuận.':selected?esc(selected.name)+' · '+esc(scope.actorId):'Chọn đơn vị làm việc để xem hoặc cấp quyền của mình.'}</p><div class="connection-actions"><button type="button" class="button secondary" id="connection-refresh">Làm mới</button>${clients||selected?`<button type="button" class="button" id="connection-new">${clients?'Đăng ký ứng dụng':'Cấp khóa kết nối'}</button>`:''}</div></div>
      ${secret?`<section class="connection-secret" id="connection-once"><h3>Khóa chỉ được trả một lần</h3><p>Lưu khóa ở nơi riêng. Đóng phần này hoặc chuyển ứng dụng sẽ xóa khóa khỏi màn hình; danh sách không xem lại được khóa.</p><label for="connection-key">Khóa kết nối vừa cấp</label><input id="connection-key" type="password" readonly autocomplete="off" value="${esc(secret)}"><div class="connection-actions"><button type="button" class="button" id="connection-copy">Sao chép khóa</button><button type="button" class="button secondary" id="connection-hide">Đã lưu, đóng khóa</button></div></section>`:''}
      ${form?formHTML(clients):''}
      <ul class="connection-list">${rows.map(rowHTML).join('')}</ul>
      ${!rows.length&&!busy?'<p class="sessions-note">Chưa có mục nào trong phạm vi đang xem.</p>':''}`;
    host.querySelectorAll('[data-connection-tab]').forEach(button=>button.onclick=()=>load(button.dataset.connectionTab));
    host.querySelector('#connection-refresh').onclick=()=>load(tab);
    host.querySelector('#connection-new')?.addEventListener('click',()=>openForm());
    host.querySelectorAll('[data-connection-revoke]').forEach(button=>button.onclick=()=>revoke(button.dataset.connectionRevoke));
    host.querySelector('#connection-hide')?.addEventListener('click',()=>clearSecret());
    host.querySelector('#connection-copy')?.addEventListener('click',async()=>{
      const token=capture(); if (!secret || !current(token)) return;
      try { await navigator.clipboard.writeText(secret); if(current(token)) notice('Đã sao chép. Khóa đã sao chép vẫn nằm trong bộ nhớ tạm của thiết bị.'); }
      catch (_) {if(current(token)) notice('Chưa sao chép được. Hãy cho phép sao chép trên trình duyệt rồi thử lại.',true);}
    });
    host.querySelector('#connection-cancel')?.addEventListener('click',()=>{form=null;projects=[];modules=[];render();});
    host.querySelector('#connection-form')?.addEventListener('submit',submit);
    host.querySelectorAll('input[name=tool],#connection-ai').forEach(input=>input.onchange=updateProfile);
    host.querySelectorAll('button,input,textarea,select').forEach(el=>el.disabled=busy);
  }
  function rowHTML(row) {
    const clients=tab==='clients';
    let details=clients?`<p class="connection-id">${esc(row.id)}</p><p class="sessions-note">${row.redirect_uris.map(esc).join('<br>')}</p><p class="sessions-note">Trần công cụ: ${row.allowed_tools.map(name=>esc(tools[name]||name)).join(', ')}</p>`:
      `<p class="sessions-note">${esc(row.owner)} · ${row.credential_type==='oauth_access_token'?'OAuth':'Khóa cấp riêng'} · ${row.project_count} phạm vi dự án</p><p class="sessions-note">${row.tools.map(name=>esc(tools[name]||name)).join(', ')}</p><p class="sessions-note">Hết hạn: <time>${esc(when(row.expires))}</time></p>`;
    if(!clients&&Array.isArray(row.project_ids))details+=`<p class="sessions-note">Phạm vi: ${row.project_ids.map(id=>esc(id ? projectNames.get(id)||'Dự án đã chọn (chưa đọc được tên)' : 'Công việc độc lập')).join(', ')||'Chỉ danh mục'}</p>`;
    if(!clients&&row.task_profile){
      details+=`<p class="sessions-note">AI: ${row.task_profile.allow_ai?'Đã cấp quyền dùng AI của đơn vị':'Chưa cấp quyền AI'}</p>`;
      for(const [key,label] of [['module_reads','Đọc'],['module_drafts','Lập đề xuất']])for(const [platform,names] of Object.entries(row.task_profile[key]||{}))details+=`<p class="sessions-note">${label} · ${esc(platform)}: ${names.map(esc).join(', ')}</p>`;
    }
    const status=!row.enabled?'Đã thu hồi':row.issuer_current===false?'Cần cấp lại sau phục hồi':row.expired?'Đã hết hạn':clients?'Cho phép xin quyền':'Đang được cấp';
    return `<li><h3>${esc(row.name)}</h3>${details}<p class="sessions-note">${status}</p>${row.enabled?`<button type="button" class="button sessions-danger" data-connection-revoke="${esc(row.id)}">${clients?'Ngắt ứng dụng':'Thu hồi quyền'}<span class="visually-hidden"> ${esc(row.name)}</span></button>`:''}</li>`;
  }
  function formHTML(clients) {
    return `<form class="connection-form" id="connection-form"><h3>${clients?'Đăng ký ứng dụng OAuth':'Cấp khóa theo quyền của mình'}</h3><label for="connection-name">Tên để nhận biết</label><input id="connection-name" name="name" required maxlength="80" autocomplete="off">
      ${clients?`<label for="connection-redirects">Địa chỉ quay lại đã đăng ký</label><textarea id="connection-redirects" name="redirects" rows="3" required spellcheck="false"></textarea><p class="sessions-note">Mỗi dòng một URL HTTPS, hoặc địa chỉ loopback có cổng cho ứng dụng trên thiết bị. Phải khớp chính xác với cấu hình ứng dụng.</p>`:`<label for="connection-client">Mã ứng dụng để nhận biết</label><input id="connection-client" name="client" required maxlength="80" autocomplete="off"><p class="sessions-note">Đây là nhãn của khóa cấp riêng, không xác minh danh tính thiết bị.</p>`}
      <fieldset><legend>${clients?'Trần công cụ ứng dụng được xin':'Công cụ được cấp'}</legend>${Object.entries(tools).map(([name,title])=>choice('tool',name,title,name)).join('')}</fieldset>
      ${clients?'':`<fieldset><legend>Phạm vi dự án</legend>${projects.map(row=>choice('project',row.id,row.name)).join('')}${choice('project','','Công việc độc lập','Công việc không thuộc dự án.')}</fieldset>
      <section id="connection-task-profile" hidden><h4>Quyền cho công việc</h4><label class="connection-choice"><input id="connection-ai" type="checkbox"><span>Cho phép dùng AI của đơn vị<small>AI có thể phát sinh chi phí và gửi ngữ cảnh được cấp cho nhà cung cấp mô hình.</small></span></label><p class="sessions-note">Mặc định chỉ chạy quy trình danh mục. Agent không được tự duyệt hoặc ghi trực tiếp.</p><div id="connection-modules" hidden>${modules.map((row,index)=>`<fieldset><legend>${esc(state.products?.find(item=>item.id===row.platform_id)?.name||row.platform_id)}</legend>${(row.read_tools||[]).map(name=>choice('read-'+index,name,'Đọc · '+name)).join('')}${(row.proposal_tools||[]).map(name=>choice('draft-'+index,name,'Đề xuất · '+name,'Mỗi nội dung ghi vẫn cần người có quyền dự án duyệt riêng.')).join('')}</fieldset>`).join('')||'<p class="sessions-note">Chưa có công cụ nền tảng đã xác minh để cấp.</p>'}</div></section>
      <label for="connection-duration">Thời hạn khóa</label><select id="connection-duration" name="duration"><option value="900">15 phút</option><option value="3600">1 giờ</option><option value="28800">8 giờ</option><option value="86400">24 giờ</option></select>`}
      <div class="connection-actions"><button type="submit" class="button">${clients?'Đăng ký':'Cấp khóa đã chọn'}</button><button type="button" class="button secondary" id="connection-cancel">Hủy</button></div></form>`;
  }
  function updateProfile() {
    const active=chosen('tool').some(name=>taskTools.has(name)), profile=host.querySelector('#connection-task-profile');
    if(!profile)return;
    profile.hidden=!active;
    if(!active)host.querySelector('#connection-ai').checked=false;
    const allow=active&&host.querySelector('#connection-ai').checked;
    host.querySelector('#connection-modules').hidden=!allow;
    if(!allow)host.querySelectorAll('#connection-modules input').forEach(input=>input.checked=false);
  }
  async function load(next=tab) {
    revision++; clearSecret(); tab=next; form=null;projects=[];modules=[];rows=[];busy=true;
    const token=capture();render('Đang đọc quyền kết nối…');
    try {
      if(tab==='grants'&&!unit().snapshot().selected){busy=false;render();return;}
      const [result,visible]=await Promise.all([api(tab==='clients'?'/api/oauth/clients':'/api/mcp/grants'),
        tab==='grants'?tool('du_an.danh_sach').then(result=>result.projects).catch(()=>[]):Promise.resolve([])]);
      if(!current(token))return;
      projectNames=new Map(visible.map(row=>[row.id,row.name]));
      const items=tab==='clients'?result.clients:result.grants; if(!Array.isArray(items))throw Error('Invalid list');rows=items;
      busy=false;render();
    }catch(_){if(current(token)){busy=false;render('Chưa đọc được danh sách. Kiểm tra tài khoản và kết nối rồi làm mới.',true);}}
  }
  async function openForm() {
    if(busy)return;revision++;clearSecret();form=null;busy=true;const token=capture();render('Đang đọc phạm vi có thể cấp…');
    try {
      if(tab==='grants'){
        const result=await Promise.all([tool('du_an.danh_sach'),tool('nen_tang.ket_noi')]);
        if(!current(token))return;
        projects=result[0].projects.filter(row=>!row.archived);modules=result[1].connections;projectNames=new Map(projects.map(row=>[row.id,row.name]));
      }
      if(!current(token))return;busy=false;form=true;render();host.querySelector('#connection-name').focus();
    }catch(_){if(current(token)){busy=false;render('Chưa đọc được phạm vi cấp quyền. Làm mới rồi thử lại.',true);}}
  }
  async function submit(event) {
    event.preventDefault();if(busy)return;const clients=tab==='clients',formEl=event.target;
    const selectedTools=chosen('tool');if(!selectedTools.length){notice('Chọn ít nhất một công cụ.',true);return;}
    let body={name:formEl.elements.name.value.trim()};
    if(clients){body.redirect_uris=formEl.elements.redirects.value.split(/\r?\n/).map(value=>value.trim()).filter(Boolean);body.allowed_tools=selectedTools;}
    else{
      body={...body,client_id:formEl.elements.client.value.trim(),tools:selectedTools,project_ids:chosen('project'),expires_in:Number(formEl.elements.duration.value)};
      if(selectedTools.some(name=>name.startsWith('cong_viec.')||name.startsWith('du_an.'))&&!body.project_ids.length){notice('Chọn phạm vi dự án cho công cụ đã chọn.',true);return;}
      if(selectedTools.some(name=>taskTools.has(name))){
        body.task_profile={allow_ai:host.querySelector('#connection-ai').checked,module_reads:{},module_drafts:{}};
        if(body.task_profile.allow_ai)modules.forEach((row,index)=>{const reads=chosen('read-'+index),drafts=chosen('draft-'+index);if(reads.length)body.task_profile.module_reads[row.platform_id]=reads;if(drafts.length)body.task_profile.module_drafts[row.platform_id]=drafts;});
      }
    }
    revision++;clearSecret();const token=capture();busy=true;host.querySelectorAll('button,input,textarea,select').forEach(el=>el.disabled=true);notice('Đang lưu quyền đã chọn…');
    try{
      const result=await api(clients?'/api/oauth/clients':'/api/mcp/grants',{method:'POST',body:JSON.stringify(body)});
      if(!current(token))return;
      form=null;projects=[];modules=[];
      if(clients){rows.unshift({id:result.id,name:result.name,redirect_uris:result.redirect_uris,allowed_tools:result.allowed_tools,enabled:result.enabled,issuer_current:true});}
      else{secret=result.credential;delete result.credential;rows.unshift(result);}
      busy=false;render(clients?'Đã đăng ký ứng dụng. Chưa cấp quyền dữ liệu cho người dùng.':'Đã cấp khóa theo phạm vi đã chọn. Lưu khóa trước khi đóng.');
    }catch(error){if(current(token)){
      busy=false;
      const rejected=['invalid_request','invalid_client_metadata','invalid_redirect_uri','invalid_scope','write_gate_closed'].includes(error.message);
      if(rejected){
        host.querySelectorAll('button,input,textarea,select').forEach(el=>el.disabled=false);
        notice(error.message==='write_gate_closed'?'Việc cấp thêm quyền đang tạm đóng. Anh vẫn có thể hủy biểu mẫu và thu hồi quyền đã cấp.':clients?'Chưa đăng ký. Kiểm tra tên, địa chỉ quay lại và trần công cụ rồi gửi lại.':'Chưa cấp khóa. Kiểm tra tên, công cụ và phạm vi dự án rồi gửi lại.',true);
      }else{form=null;projects=[];modules=[];render('Chưa xác minh được kết quả lưu. Làm mới danh sách trước khi cấp lại để tránh tạo trùng.',true);}
    }}
  }
  async function revoke(id) {
    if(busy)return;const row=rows.find(item=>item.id===id);if(!row)return;
    if(!confirm(tab==='clients'?`Ngắt ứng dụng “${row.name}”? Mã đang chờ và quyền OAuth đã cấp của ứng dụng sẽ không dùng tiếp được.`:`Thu hồi quyền “${row.name}”? Ứng dụng sẽ cần được cấp lại quyền.`))return;
    revision++;clearSecret();form=null;const token=capture();busy=true;render('Đang thu hồi quyền…');
    try{
      await api(tab==='clients'?'/api/oauth/clients/disable':'/api/mcp/grants/revoke',{method:'POST',body:JSON.stringify({id})});
      if(current(token))await load(tab);
    }catch(_){if(current(token)){busy=false;render('Chưa xác minh được kết quả thu hồi. Làm mới để kiểm tra lại.',true);}}
  }
  function suspend(){revision++;clearSecret();form=null;projects=[];modules=[];busy=false;if(host?.isConnected)render('Đã đóng phần cấp khóa. Làm mới để tiếp tục.');}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)suspend();});
  window.addEventListener('message',event=>{if(event.source===parent&&event.origin===location.origin&&event.data?.type==='bdsg-os-visibility'&&event.data.visible===false)suspend();});
  window.addEventListener('pagehide',reset);
  window.BDSGConnections=Object.freeze({mount(element){reset();host=element;tab='grants';load();},reset});
})();
