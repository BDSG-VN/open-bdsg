"use strict";
(() => {
  const stages=[['tu-van','Tư vấn'],['trien-khai','Triển khai'],['van-hanh','Vận hành'],['kinh-doanh','Kinh doanh']];
  let host=null,version=0,rows=[],projects=[],status='idle',reading=false,writing=false,unknown=false,notice='',showForm=false;
  const unit=()=>window.BDSGUnit;
  const visible=()=>location.hash==='#requests'&&window.BDSGAppVisible!==false&&!document.hidden;
  const capture=()=>({version,scope:unit().capture()});
  const current=t=>version===t.version&&unit().current(t.scope)&&visible()&&host?.isConnected;
  const text=(node,value)=>{if(node.textContent!==value)node.textContent=value;};
  function reset(){version++;rows=[];projects=[];status='idle';reading=writing=unknown=showForm=false;notice='';host?.replaceChildren();host=null;}
  function paint(){
    if(!host?.isConnected)return;
    if(!host.childElementCount){
      host.innerHTML=`<header class="unit-biz-heading"><div><h1>Yêu cầu kinh doanh</h1><p id="unit-biz-scope"></p></div><div class="unit-biz-actions"><button class="button secondary" id="unit-biz-refresh">Làm mới</button><button class="button primary" id="unit-biz-new">Tạo yêu cầu</button></div></header>
        <p id="unit-biz-notice" role="status" hidden></p><p id="unit-biz-state" role="status"></p>
        <form id="unit-biz-form" class="unit-biz-form" hidden><h2>Ghi nhận nhu cầu mới</h2>
        <label for="unit-biz-title">Tên yêu cầu</label><input id="unit-biz-title" name="title" required minlength="3" maxlength="160" autocomplete="off">
        <div class="unit-biz-fields"><div><label for="unit-biz-sector">Lĩnh vực</label><select id="unit-biz-sector" name="sector" required></select></div>
        <div><label for="unit-biz-project">Lưu yêu cầu vào</label><select id="unit-biz-project" name="project_id"></select></div></div>
        <p class="unit-biz-help">Yêu cầu cá nhân chỉ bạn đọc được. Yêu cầu trong dự án dùng quyền chia sẻ của dự án. Danh sách có tối đa 100 dự án được phép ghi.</p>
        <label for="unit-biz-description">Nhu cầu và kết quả mong muốn</label><textarea id="unit-biz-description" name="description" rows="4" required minlength="10" maxlength="4000"></textarea>
        <div class="unit-biz-actions"><button class="button primary" type="submit">Lưu yêu cầu</button><button class="button secondary" type="button" id="unit-biz-close">Đóng biểu mẫu</button></div></form>
        <div class="unit-biz-board" aria-label="Yêu cầu theo chặng"></div>`;
      const sector=host.querySelector('#unit-biz-sector');
      for(const row of sectors){const option=document.createElement('option');option.value=row.id;option.textContent=row.name;sector.append(option);}
      host.querySelector('#unit-biz-refresh').onclick=()=>load(true);
      host.querySelector('#unit-biz-new').onclick=()=>{showForm=true;paint();host.querySelector('#unit-biz-title').focus();};
      host.querySelector('#unit-biz-close').onclick=()=>{showForm=false;paint();host.querySelector('#unit-biz-new').focus();};
      host.querySelector('#unit-biz-form').onsubmit=create;
      for(const [id,name] of stages){
        const section=document.createElement('section');section.className='unit-biz-column';section.dataset.bizColumn=id;
        const h=document.createElement('h2');h.textContent=name;section.append(h,document.createElement('div'));
        host.querySelector('.unit-biz-board').append(section);
      }
    }
    text(host.querySelector('#unit-biz-scope'),unit().snapshot().selected?.name||'Đơn vị đang chọn');
    const feedback=host.querySelector('#unit-biz-notice');text(feedback,notice);feedback.hidden=!notice;
    text(host.querySelector('#unit-biz-state'),status==='loading'?'Đang đọc yêu cầu và kiểm tra quyền…':status==='error'?'Chưa đọc được yêu cầu. Hãy kiểm tra đơn vị và làm mới.':status==='ready'?`${rows.length} yêu cầu có quyền truy cập · Tối đa 200 yêu cầu gần nhất`:'');
    const locked=status!=='ready'||writing||unknown;
    host.querySelector('#unit-biz-refresh').disabled=reading||writing;
    host.querySelector('#unit-biz-new').disabled=locked;
    const form=host.querySelector('#unit-biz-form');form.hidden=!showForm;
    for(const field of form.elements)field.disabled=locked;
    text(form.querySelector('[type=submit]'),writing?'Đang lưu…':'Lưu yêu cầu');
    const choice=host.querySelector('#unit-biz-project'),selected=choice.value;
    const choices=[{id:'',name:'Cá nhân — chỉ mình bạn'},...projects];
    if(JSON.stringify([...choice.options].map(o=>[o.value,o.textContent]))!==JSON.stringify(choices.map(p=>[p.id,p.name]))){
      choice.replaceChildren(...choices.map(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=p.name;return o;}));
      if(choices.some(p=>p.id===selected))choice.value=selected;
      else if(selected){showForm=false;form.hidden=true;notice='Quyền dự án đã thay đổi. Kiểm tra nơi lưu trước khi tạo yêu cầu.';text(feedback,notice);feedback.hidden=false;}
    }
    const existing=new Map([...host.querySelectorAll('[data-biz-row]')].map(node=>[node.dataset.bizRow,node]));
    const focused=document.activeElement?.dataset.bizStage;
    for(const [stage,label] of stages){
      const section=host.querySelector(`[data-biz-column="${stage}"]`),parent=section.lastElementChild;
      const items=status==='ready'?rows.filter(r=>r.stage===stage):[];
      text(section.querySelector('h2'),`${label} · ${items.length}`);
      let cursor=parent.firstElementChild;
      for(const row of items){
        let article=existing.get(row.id);
        if(!article){
          article=document.createElement('article');article.className='unit-biz-row';article.dataset.bizRow=row.id;
          article.innerHTML='<small></small><h3></h3><p></p><label></label><select></select>';
          const select=article.querySelector('select');select.dataset.bizStage=row.id;select.id='biz-stage-'+row.id;
          const label=article.querySelector('label');label.htmlFor=select.id;label.textContent='Chặng xử lý';
          for(const [id,name] of stages){const option=document.createElement('option');option.value=id;option.textContent=name;select.append(option);}
          select.onchange=()=>change(row.id,select.value);
        }
        text(article.querySelector('small'),(row.project_name||'Cá nhân')+(row.archived?' · Dự án đã lưu trữ':!row.can_edit?' · Chỉ đọc':''));
        text(article.querySelector('h3'),row.title);text(article.querySelector('p'),row.description);
        const select=article.querySelector('select');select.value=row.stage;select.disabled=locked||!row.can_edit;
        select.setAttribute('aria-label','Chặng của '+row.title);
        if(article!==cursor)parent.insertBefore(article,cursor);cursor=article.nextElementSibling;existing.delete(row.id);
      }
      let empty=parent.querySelector('.unit-biz-empty');
      if(!items.length){if(!empty){empty=document.createElement('p');empty.className='unit-biz-empty';parent.append(empty);}text(empty,'Chưa có yêu cầu ở chặng này.');}
      else empty?.remove();
    }
    for(const node of existing.values())node.remove();
    if(focused){const field=host.querySelector(`[data-biz-stage="${focused}"]`);if(field&&!field.disabled&&document.activeElement!==field)field.focus({preventScroll:true});}
  }
  async function invoke(name,args={}){
    const response=await api('/api/tools',{method:'POST',body:JSON.stringify({name,arguments:args})});
    if(!response.ok)throw Object.assign(new Error(response.ly_do||'Yêu cầu bị từ chối.'),{knownRejected:true});
    return response.ket_qua;
  }
  async function load(manual=false){
    if(reading||writing||!visible())return;
    const token=capture();reading=true;if(status!=='ready')status='loading';paint();
    try{
      const data=await invoke('kinh_doanh.danh_sach');if(!current(token))return;
      rows=data.requests;projects=data.project_options;status='ready';
      if(manual){unknown=false;notice='Đã đọc yêu cầu mới nhất. Kiểm tra kết quả trước khi thao tác lại.';}
    }catch(error){if(!current(token))return;rows=[];projects=[];status='error';notice='Không tải được dữ liệu. Làm mới để kiểm tra lại quyền và kết nối.';}
    finally{if(current(token)){reading=false;paint();}}
  }
  async function write(name,args,onSuccess){
    if(writing||reading||unknown||status!=='ready'||!visible())return;
    const token=capture();let focusId='';writing=true;notice='';paint();
    try{await invoke(name,args);if(!current(token))return;focusId=onSuccess()||'';notice='Đã lưu yêu cầu.';}
    catch(error){if(!current(token))return;unknown=!error.knownRejected;notice=unknown?'Chưa rõ thao tác đã được lưu hay chưa. Làm mới và kiểm tra trước khi thực hiện lại.':'Chưa lưu được. Kiểm tra quyền và cổng ghi; bản nháp vẫn được giữ.';}
    finally{if(current(token)){
      writing=false;paint();if(!unknown)await load();
      if(current(token)&&focusId){
        const target=host.querySelector('#'+focusId);
        (target&&!target.disabled?target:host.querySelector('#unit-biz-refresh')).focus({preventScroll:true});
      }
    }}
  }
  function create(event){
    event.preventDefault();const form=event.currentTarget;if(!form.reportValidity())return;
    const data=Object.fromEntries(new FormData(form));if(!data.project_id)delete data.project_id;
    if(data.project_id&&!projects.some(p=>p.id===data.project_id))return;
    write('kinh_doanh.tao_yeu_cau',data,()=>{form.reset();showForm=false;return 'unit-biz-new';});
  }
  function change(id,stage){
    const row=rows.find(r=>r.id===id);if(reading||writing||unknown||!row?.can_edit){paint();return;}
    write('kinh_doanh.doi_chang',{id,stage},()=>{});
  }
  function open(){
    reset();main.innerHTML='<section id="unit-business" class="unit-business"></section>';host=main.querySelector('#unit-business');
    if(!unit().snapshot().selected){host.innerHTML='<h1>Yêu cầu kinh doanh</h1><p>Chọn đơn vị làm việc để mở yêu cầu.</p>';return;}load();
  }
  function resume(){if(visible()&&unit()?.snapshot().mode==='units'&&state.user)open();}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();else resume();});
  window.addEventListener('message',e=>{if(e.source!==parent||e.origin!==location.origin||e.data?.type!=='bdsg-os-visibility')return;if(e.data.visible===false)reset();else setTimeout(resume,0);});
  window.addEventListener('pagehide',reset);
  setInterval(()=>{if(host?.isConnected&&!unknown)load();},10000);
  window.BDSGRequests=Object.freeze({open,reset,leave(){if(location.hash!=='#requests')reset();}});
})();
