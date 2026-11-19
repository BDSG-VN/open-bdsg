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
  const text=(element,value)=>{if(element.textContent!==value)element.textContent=value;};
  function syncRows(parent,rows,make,update){
    const existing=new Map([...parent.children].map(node=>[node.dataset.rowId,node]));
    let cursor=parent.firstElementChild;
    for(const row of rows){
      const node=existing.get(row.id)||make(row);node.dataset.rowId=row.id;update(node,row);
      if(node!==cursor)parent.insertBefore(node,cursor);
      cursor=node.nextElementSibling;existing.delete(row.id);
    }
    for(const node of existing.values())node.remove();
  }
  function paint(){
    if(!host?.isConnected)return;
    if(!host.childElementCount){
      host.innerHTML=`<header class="unit-mail-heading"><div><h1>Thông điệp</h1><p>Trao đổi riêng với thành viên trong đơn vị đang chọn.</p></div><button class="button secondary" id="unit-mail-refresh">Làm mới hộp thư</button></header>
        <p class="unit-mail-notice" id="unit-mail-notice" role="status" hidden></p>
        <div class="unit-mail-layout"><section class="unit-mail-people" aria-label="Thành viên đơn vị"><h2>Người đối thoại</h2><p id="unit-mail-directory-state" role="status" hidden></p><div id="unit-mail-choices"></div></section>
        <section class="unit-mail-conversation" aria-label="Nội dung trao đổi"><h2 id="unit-mail-person"></h2><p class="unit-mail-notice" id="unit-mail-history-note" hidden>Người này không còn trong danh bạ hoạt động. Bạn chỉ có thể đọc lịch sử.</p>
        <div id="unit-mail-messages" class="unit-mail-messages" role="log" aria-live="polite" aria-relevant="additions text" aria-label="Thông điệp gần đây"><p class="unit-mail-empty" id="unit-mail-empty"></p><div id="unit-mail-rows"></div></div>
        <form id="unit-mail-form"><label for="unit-mail-draft" id="unit-mail-label"></label><textarea id="unit-mail-draft" rows="3" maxlength="4000" required></textarea><div class="unit-mail-send"><p>Chỉ bên gửi và bên nhận đọc được trong đơn vị này.</p><button class="button" type="submit">Gửi thông điệp</button></div></form></section></div>`;
      host.querySelector('#unit-mail-refresh').onclick=()=>load(true);
      host.querySelector('#unit-mail-draft').oninput=e=>drafts.set(peer,e.target.value);
      host.querySelector('#unit-mail-form').onsubmit=send;
    }
    const people=host.querySelector('.unit-mail-people'),log=host.querySelector('#unit-mail-messages');
    const peopleTop=people.scrollTop,logTop=log.scrollTop,atEnd=log.scrollHeight-log.scrollTop-log.clientHeight<60;
    const switched=host.dataset.mailConversation!==peer;
    const target=contacts.find(r=>r.id===peer);
    const rows=status==='ready'&&target?messages.filter(r=>(r.sender===own()&&r.recipient===peer)||(r.sender===peer&&r.recipient===own())):[];
    const feedback=host.querySelector('#unit-mail-notice');text(feedback,notice);feedback.hidden=!notice;
    const directoryState=host.querySelector('#unit-mail-directory-state');
    const directoryText=status==='loading'?'Đang đọc danh bạ và thông điệp…':status==='error'?'Chưa đọc được hộp thư. Hãy làm mới để thử lại.':!contacts.length?'Chưa có người đối thoại trong đơn vị này.':'';
    text(directoryState,directoryText);directoryState.hidden=!directoryText;
    syncRows(host.querySelector('#unit-mail-choices'),contacts,()=>{
      const button=document.createElement('button');button.type='button';button.innerHTML='<strong></strong><small></small>';
      button.onclick=()=>{
        if(sending||unknown){notice='Hãy làm mới và kiểm tra lần gửi vừa rồi trước khi chuyển người đối thoại.';paint();return;}
        peer=button.dataset.mailPeer;notice='';paint();
      };return button;
    },(button,row)=>{
      button.dataset.mailPeer=row.id;button.setAttribute('aria-pressed',String(row.id===peer));
      text(button.querySelector('strong'),row.id===own()?'Ghi chú cho mình':row.name);
      text(button.querySelector('small'),!row.active?'Chỉ xem lịch sử':row.id===own()?'Chỉ mình bạn đọc':'Thành viên đơn vị');
    });
    text(host.querySelector('#unit-mail-person'),target?.id===own()?'Ghi chú cho mình':target?.name||'Chọn người đối thoại');
    host.querySelector('#unit-mail-history-note').hidden=!target||!!target.active;
    const empty=host.querySelector('#unit-mail-empty');empty.hidden=rows.length>0;
    text(empty,status==='ready'&&target?'Chưa có thông điệp. Viết lời nhắn đầu tiên bên dưới.':'Thông điệp sẽ hiện sau khi xác minh hộp thư.');
    syncRows(host.querySelector('#unit-mail-rows'),rows,()=>{
      const article=document.createElement('article');article.className='unit-mail-message';article.innerHTML='<small><span></span> · <time></time></small><p></p>';return article;
    },(article,row)=>{
      article.classList.toggle('unit-mail-mine',row.sender===own());
      text(article.querySelector('span'),row.sender===own()?'Bạn':target.name);
      const time=article.querySelector('time');text(time,when(row.created));time.dateTime=new Date(row.created*1000).toISOString();
      text(article.querySelector('p'),row.body);
    });
    const locked=status!=='ready'||!target?.active||sending||unknown;
    const field=host.querySelector('#unit-mail-draft'),draft=drafts.get(peer)||'';
    if(field.value!==draft)field.value=draft;field.disabled=locked;
    text(host.querySelector('#unit-mail-label'),peer===own()?'Nội dung ghi chú':'Nội dung thông điệp');
    const submit=host.querySelector('#unit-mail-form button');submit.disabled=locked;text(submit,sending?'Đang gửi…':'Gửi thông điệp');
    host.querySelector('#unit-mail-refresh').disabled=reading||sending;
    people.scrollTop=peopleTop;
    log.scrollTop=switched||atEnd?log.scrollHeight:logTop;host.dataset.mailConversation=peer;
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
      messages=inbox.messages;
      const peers=new Map(directory.agents.map(row=>[row.id,{...row,active:row.active===true||row.active===1}]));
      for(const message of messages){
        const other=message.sender===own()?message.recipient:message.sender;
        if(!peers.has(other))peers.set(other,{id:other,name:other,active:false});
      }
      contacts=[...peers.values()];
      if(!contacts.some(r=>r.id===peer)){drafts.clear();peer=contacts.find(r=>r.id!==own())?.id||contacts[0]?.id||'';}
      status='ready';if(manual){unknown=false;notice='Đã đọc hộp thư mới nhất. Kiểm tra nội dung trước khi gửi lại.';}
    }catch(error){
      if(!current(token))return;
      contacts=[];messages=[];status='error';notice='Chưa đọc được hộp thư. Kiểm tra đơn vị và kết nối rồi làm mới.';
    }finally{if(current(token)){reading=false;paint();}}
  }
  async function send(event){
    event.preventDefault();
    if(sending||unknown||status!=='ready'||!contacts.find(row=>row.id===peer)?.active||!visible())return;
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
