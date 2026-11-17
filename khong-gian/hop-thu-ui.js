"use strict";
(() => {
  let host=null, version=0, contacts=[], messages=[], peer='', status='idle';
  let reading=false, sending=false, notice='', unknown=false;
  const drafts=new Map(), unit=()=>window.BDSGUnit;
  const visible=()=>location.hash==='#agents'&&window.BDSGAppVisible!==false&&!document.hidden;
  const capture=()=>({version,scope:unit().capture(),peer});
  const current=t=>t.version===version&&unit().current(t.scope)&&visible()&&host?.isConnected;
  const own=()=>unit().snapshot().actorId;
  const when=v=>new Date(v*1000).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'});
  function reset(){
    version++; contacts=[];messages=[];drafts.clear();peer='';status='idle';
    reading=sending=unknown=false;notice='';host?.replaceChildren();host=null;
  }
  function paint(){
    if(!host?.isConnected)return;
    const active=document.activeElement, editing=active?.id==='unit-mail-draft';
    const selection=editing?[active.selectionStart,active.selectionEnd]:null;
    const target=contacts.find(r=>r.id===peer);
    const rows=messages.filter(r=>(r.sender===own()&&r.recipient===peer)||(r.sender===peer&&r.recipient===own()));
    host.innerHTML=`<header class="unit-mail-heading"><div><h1>Thông điệp</h1><p>Trao đổi riêng với thành viên trong đơn vị đang chọn.</p></div><button class="button secondary" id="unit-mail-refresh" ${reading?'disabled':''}>Làm mới hộp thư</button></header>
      ${notice?`<p class="unit-mail-notice" role="status">${esc(notice)}</p>`:''}
      <div class="unit-mail-layout"><section class="unit-mail-people" aria-label="Thành viên đơn vị"><h2>Người đối thoại</h2>
      ${status==='loading'?'<p role="status">Đang đọc danh bạ và thông điệp…</p>':status==='error'?'<p>Chưa đọc được hộp thư. Hãy làm mới để thử lại.</p>':contacts.map(r=>`<button type="button" data-mail-peer="${esc(r.id)}" aria-pressed="${r.id===peer}"><strong>${esc(r.id===own()?'Ghi chú cho mình':r.name)}</strong><small>${r.id===own()?'Chỉ mình bạn đọc':'Thành viên đơn vị'}</small></button>`).join('')||'<p>Chưa có người đối thoại trong đơn vị này.</p>'}</section>
      <section class="unit-mail-conversation" aria-label="Nội dung trao đổi"><h2>${esc(target?.id===own()?'Ghi chú cho mình':target?.name||'Chọn người đối thoại')}</h2>
      <div id="unit-mail-messages" class="unit-mail-messages" role="log" aria-live="polite" aria-label="Thông điệp gần đây">
      ${status==='ready'&&target?rows.map(r=>`<article class="unit-mail-message ${r.sender===own()?'unit-mail-mine':''}"><small>${esc(r.sender===own()?'Bạn':target.name)} · <time datetime="${new Date(r.created*1000).toISOString()}">${esc(when(r.created))}</time></small><p>${esc(r.body)}</p></article>`).join('')||'<p class="unit-mail-empty">Chưa có thông điệp. Viết lời nhắn đầu tiên bên dưới.</p>':'<p class="unit-mail-empty">Thông điệp sẽ hiện sau khi xác minh hộp thư.</p>'}</div>
      <form id="unit-mail-form"><label for="unit-mail-draft">${peer===own()?'Nội dung ghi chú':'Nội dung thông điệp'}</label><textarea id="unit-mail-draft" rows="3" maxlength="4000" required ${status!=='ready'||!target||sending||unknown?'disabled':''}>${esc(drafts.get(peer)||'')}</textarea><div class="unit-mail-send"><p>Chỉ bên gửi và bên nhận đọc được trong đơn vị này.</p><button class="button" type="submit" ${status!=='ready'||!target||sending||unknown?'disabled':''}>${sending?'Đang gửi…':'Gửi thông điệp'}</button></div></form></section></div>`;
    host.querySelector('#unit-mail-refresh').onclick=()=>load(true);
    host.querySelectorAll('[data-mail-peer]').forEach(b=>b.onclick=()=>{
      if(sending||unknown){notice='Hãy làm mới và kiểm tra lần gửi vừa rồi trước khi chuyển người đối thoại.';paint();return;}
      peer=b.dataset.mailPeer;notice='';paint();
    });
    host.querySelector('#unit-mail-draft').oninput=e=>drafts.set(peer,e.target.value);
    host.querySelector('#unit-mail-form').onsubmit=send;
    if(editing&&!host.querySelector('#unit-mail-draft').disabled){
      const field=host.querySelector('#unit-mail-draft');field.focus({preventScroll:true});field.setSelectionRange(...selection);
    }
  }
  async function invoke(name,args={}){
    const r=await api('/api/tools',{method:'POST',body:JSON.stringify({name,arguments:args})});
    if(!r.ok)throw Object.assign(new Error(r.ly_do||'Yêu cầu chưa được chấp nhận.'),{knownRejected:true});
    return r.ket_qua;
  }
  async function load(manual=false){
    if(reading||sending||!visible())return;
    const token=capture();reading=true;
    if(status!=='ready'){status='loading';paint();}
    try{
      const [directory,inbox]=await Promise.all([invoke('agent.danh_sach'),invoke('agent.doc_hop_thu')]);
      if(!current(token))return;
      contacts=directory.agents;messages=inbox.messages;
      if(!contacts.some(r=>r.id===peer)){drafts.clear();peer=contacts.find(r=>r.id!==own())?.id||contacts[0]?.id||'';}
      status='ready';if(manual){unknown=false;notice='Đã đọc hộp thư mới nhất. Kiểm tra nội dung trước khi gửi lại.';}
    }catch(error){
      if(!current(token))return;
      contacts=[];messages=[];status='error';notice='Chưa đọc được hộp thư. Kiểm tra đơn vị và kết nối rồi làm mới.';
    }finally{if(current(token)){reading=false;paint();}}
  }
  async function send(event){
    event.preventDefault();
    if(sending||unknown||status!=='ready'||!peer||!visible())return;
    const body=(drafts.get(peer)||'').trim();
    if(!body||body.length>4000){notice='Nội dung cần từ 1 đến 4000 ký tự.';paint();return;}
    const token=capture();sending=true;notice='';paint();
    try{
      await invoke('agent.gui_tin',{recipient:peer,body});
      if(!current(token)||token.peer!==peer)return;
      drafts.delete(peer);notice='Đã giao thông điệp vào hộp thư.';
    }catch(error){
      if(!current(token)||token.peer!==peer)return;
      unknown=!error.knownRejected;
      notice=unknown?'Chưa rõ thông điệp đã được gửi hay chưa. Làm mới hộp thư và kiểm tra trước khi gửi lại.':'Chưa gửi được. Nội dung vẫn được giữ; kiểm tra người nhận và quyền ghi rồi thử lại.';
    }finally{if(current(token)){sending=false;paint();if(!unknown)await load();}}
  }
  function open(){
    reset();main.innerHTML='<section id="unit-mailbox" class="unit-mailbox"></section>';host=main.querySelector('#unit-mailbox');
    if(!unit().snapshot().selected){host.innerHTML='<h1>Thông điệp</h1><p>Chọn đơn vị làm việc để mở hộp thư.</p>';return;}
    load();
  }
  function resume(){if(visible()&&unit()?.snapshot().mode==='units'&&state.user)open();}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();else resume();});
  window.addEventListener('message',e=>{
    if(e.source!==parent||e.origin!==location.origin||e.data?.type!=='bdsg-os-visibility')return;
    // Chờ các listener của khung OS cập nhật BDSGAppVisible trong cùng sự kiện.
    if(e.data.visible===false)reset();else setTimeout(resume,0);
  });
  window.addEventListener('pagehide',reset);
  window.BDSGMail=Object.freeze({open,reset,poll(){if(host?.isConnected&&!unknown)load();},leave(){if(location.hash!=='#agents')reset();}});
})();
