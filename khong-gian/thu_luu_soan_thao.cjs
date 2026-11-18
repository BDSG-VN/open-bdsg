// Gọi nút Lưu và giao thức HTTP của controller thật; không mở store nội bộ.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const request = 'c'.repeat(32);
async function harness(progresses, saved = {state:'dang-luu',request_id:request}, protocol = 'request-ledger-v1', expectReady = true, options = {}) {
  const calls = [], elements = new Map(), snapshots = [], windowEvents = new Map(), navigations = [];
  let destroyed = 0, closeRequests = 0;
  const storage = options.storage || new Map();
  let engineEvents;
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      disabled: selector === '#save', hidden: true, open:false, checked:false, textContent:'', handlers:{},
      focus() {}, replaceChildren() {}, showModal(){this.open=true;}, close(){this.open=false;},
      addEventListener(name, handler) { this.handlers[name] = handler; },
    });
    return elements.get(selector);
  }
  let index = 0;
  const guard = {
    ready:Promise.resolve(),active:true,contextKey:options.contextKey || 'context-a',assertActive() {},
    async fetch(route, requestOptions) {
      assert.equal(route,'/api/tools');
      const body = JSON.parse(requestOptions.body); calls.push(body);
      let result;
      if (body.name === 'van_phong.mo_soan_thao') result = {
        key:options.key || 'bdsg-'+'a'.repeat(32),config:{},api_url:'/office-docs/web-apps/apps/api/documents/api.js',save_protocol:protocol,
        save_intents:Object.hasOwn(options,'intents') ? options.intents : false,
    abandon_sessions:Object.hasOwn(options,'abandonCapability') ? options.abandonCapability : false,
        pending_save:options.pending || null,
      };
      else if (body.name === 'van_phong.luu_soan_thao') {
        options.onSave?.(engineEvents);
        result = typeof saved === 'function' ? await saved(body.arguments) : saved;
      }
      else if (body.name === 'van_phong.bo_phien_soan_thao') {
        result=options.abandon ? await options.abandon(body.arguments) :
          {state:'da-bo-phien',...body.arguments,revoked_sessions:1};
      }
      else {
        assert.equal(body.name,'van_phong.phien_soan_thao');
        result = typeof progresses === 'function' ? progresses(body.arguments,index++) : progresses[Math.min(index++,progresses.length-1)];
      }
      if (body.name === 'van_phong.mo_soan_thao' && protocol === 'absent') delete result.save_protocol;
      return {ok:true,json:async()=>({ok:true,ket_qua:result})};
    },
  };
  const context = {
    window:{parent:options.parent,BDSGOfficeGuard:{create:()=>guard},addEventListener:(name,fn)=>windowEvents.set(name,fn),
      sessionStorage:{getItem:key=>storage.get(key)||null,setItem(key,value){if(options.storageDenied)throw new Error('quota');storage.set(key,value);},removeItem(key){if(options.removeDenied)throw new Error('Synthetic cleanup failure');storage.delete(key);}}},
    document:{querySelector:element,createElement:()=>({}),
      head:{append:script=>queueMicrotask(()=>script.onload())}},
    location:{search:'?id='+'a'.repeat(24),assign:value=>navigations.push(value),reload() {}},
    matchMedia:()=>({matches:options.mobile || false}),URLSearchParams,AbortSignal,crypto:{randomUUID:()=>options.intent || 'e'.repeat(32)},
    setTimeout:(fn,delay)=>{if(delay<5000)queueMicrotask(fn);return 1;},clearTimeout() {},
    DocsAPI:{DocEditor:class {
      constructor(_id, config) {engineEvents=config.events;queueMicrotask(()=>config.events.onDocumentReady());}
      destroyEditor() {destroyed++;} requestClose() {closeRequests++;options.onClose?.(engineEvents);}
    }},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'soan-thao.js'),'utf8'),context);
  for (let i=0;i<30 && element('#save').disabled;i++) await Promise.resolve();
  if (expectReady) assert.equal(element('#save').disabled,false,'Editor phải sẵn sàng trước thao tác');
  for (let click=0;expectReady && click<(options.clicks ?? 1);click++) {
    await element(options.action === 'close' ? '#close' : '#save').handlers.click();
    snapshots.push({inert:element('main').inert,closeDisabled:element('#close').disabled,
      label:element('#save').textContent,status:element('#status').textContent});
  }
  return {calls,get status(){return element('#status').textContent;},error:element('#error'),polls:index,
    opened:!element('#save').disabled,snapshots,storage,element,engineEvents,windowEvents,navigations,
    get destroyed(){return destroyed;},get closeRequests(){return closeRequests;}};
}
const progress = overrides => ({state:'active',pending:false,last_saved:123,
  request_id:request,command_state:'committed',...overrides});
const success = result => result.status === 'Đã lưu phiên bản vào kho BDSG.';
async function confirmAbandon(result) {
  await result.element('#abandon').handlers.click();
  for (const id of ['#abandon-loss','#abandon-shared']) {
    result.element(id).checked=true;result.element(id).handlers.change();
  }
  await result.element('#abandon-confirm').handlers.click();
}
test('Lưu và đóng trong iframe trả về host sau đối soát, không điều hướng iframe sang Home',async()=>{
  let returned=0;
  const parent={BDSGOfficeLauncher:{finish(){returned++;return true;}}};
  const result=await harness(args=>progress({request_key:args.request_key}),undefined,undefined,true,
    {intents:true,parent,action:'close',onClose(events){events.onRequestClose();}});
  assert.equal(returned,1);assert.equal(result.destroyed,1);assert.deepEqual(result.navigations,[]);
});
test('Bỏ phiên trong iframe chỉ trả về host sau biên nhận xác nhận',async()=>{
  let returned=0;
  const parent={BDSGOfficeLauncher:{finish(){returned++;return true;}}};
  const result=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,parent});
  assert.equal(returned,0);await confirmAbandon(result);
  assert.equal(returned,1);assert.deepEqual(result.navigations,[]);
});

test('Xác nhận bỏ phiên giữ mã trước ghi và chỉ rời trang sau đúng biên nhận',async()=>{
  const storage=new Map();
  const result=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,storage,
    abandon(args){
      const stored=[...storage.entries()].find(([key])=>key.startsWith('bdsg-office-abandon:'));
      assert.ok(stored,'Phải giữ mã trước gửi');
      const record=JSON.parse(stored[1]);
      assert.deepEqual(Object.keys(record).sort(),['file_id','key','request_key','version']);
      assert.equal(record.request_key,args.request_key);
      return {state:'da-bo-phien',file_id:args.file_id,key:args.key,request_key:args.request_key,revoked_sessions:1};
    }});
  await confirmAbandon(result);
  const writes=result.calls.filter(c=>c.name==='van_phong.bo_phien_soan_thao');
  assert.equal(writes.length,1);
  assert.equal(writes[0].arguments.acknowledge_unsaved_changes,true);
  assert.equal(writes[0].arguments.acknowledge_shared_session,true);
  assert.deepEqual(result.navigations,['/#office']);assert.equal(result.destroyed,1);
  assert.equal(result.storage.size,0);assert.doesNotMatch(result.status,/Đã lưu/);
});

test('Bỏ phiên cần cả hai xác nhận; hủy hộp thoại không gửi ghi',async()=>{
  const result=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0});
  assert.equal(result.element('#abandon').hidden,false);
  await result.element('#abandon').handlers.click();
  assert.equal(result.element('#abandon-dialog').open,true);
  assert.equal(result.element('#abandon-confirm').disabled,true);
  result.element('#abandon-loss').checked=true;
  result.element('#abandon-loss').handlers.change();
  assert.equal(result.element('#abandon-confirm').disabled,true);
  result.element('#abandon-cancel').handlers.click();
  assert.equal(result.element('#abandon-dialog').open,false);
  assert.equal(result.calls.filter(c=>c.name==='van_phong.bo_phien_soan_thao').length,0);
  assert.equal(result.storage.size,0);
});

test('Bỏ phiên mất phản hồi rồi tải lại ưu tiên mã cũ, không mở engine hoặc ghi lưu',async()=>{
  const storage=new Map();
  const first=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,storage,
    abandon(){throw new TypeError('Failed to fetch');}});
  await confirmAbandon(first);
  const sent=first.calls.find(c=>c.name==='van_phong.bo_phien_soan_thao').arguments;
  assert.equal(first.element('main').inert,true);assert.equal(first.element('#close').disabled,true);
  assert.doesNotMatch(first.error.textContent,/Failed to fetch/);
  storage.set('bdsg-office-save:context-a:'+'a'.repeat(24),'{broken');
  const second=await harness([],undefined,undefined,false,{intents:true,abandonCapability:true,storage,
    key:'bdsg-'+'b'.repeat(32),intent:'f'.repeat(32)});
  assert.equal(second.engineEvents,undefined);
  assert.equal(second.element('#abandon').textContent,'Kiểm tra yêu cầu bỏ phiên');
  assert.equal(second.element('#abandon').disabled,false);
  assert.equal(second.calls.length,1);
  await second.element('#abandon').handlers.click();
  assert.deepEqual(second.calls[1].arguments,sent);
  assert.deepEqual(second.navigations,['/#office']);assert.equal(storage.size,0);
});

test('Biên nhận bỏ phiên sai hoặc lỗi dọn bộ nhớ không mở khóa hay rời trang',async()=>{
  for (const mismatch of [{key:'bdsg-'+'f'.repeat(32)},{file_id:'f'.repeat(24)},
      {request_key:'other-operation'},{state:'da-luu'},{revoked_sessions:-1},{revoked_sessions:1.5},{revoked_sessions:true}]) {
    const result=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,
      abandon:args=>({state:'da-bo-phien',...args,revoked_sessions:1,...mismatch})});
    await confirmAbandon(result);
    assert.deepEqual(result.navigations,[]);assert.equal(result.destroyed,0);
    assert.equal(result.element('main').inert,true);assert.equal(result.element('#save').disabled,true);
    assert.equal(result.storage.size,1);
  }
  const cleanup=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,removeDenied:true});
  await confirmAbandon(cleanup);
  assert.equal(cleanup.storage.size,1);assert.equal(cleanup.element('main').inert,true);
  assert.deepEqual(cleanup.navigations,[]);assert.match(cleanup.error.textContent,/chưa dọn/);
});

test('Không giữ được mã bỏ phiên thì không gửi ghi; record bỏ phiên hỏng giữ nguyên',async()=>{
  const denied=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,storageDenied:true});
  await confirmAbandon(denied);
  assert.equal(denied.calls.filter(c=>c.name==='van_phong.bo_phien_soan_thao').length,0);
  assert.equal(denied.element('main').inert,true);
  const namespace='bdsg-office-abandon:context-a:'+'a'.repeat(24);
  const storage=new Map([[namespace,'{broken']]);
  const corrupt=await harness([],undefined,undefined,false,{intents:true,abandonCapability:true,storage});
  assert.equal(corrupt.engineEvents,undefined);assert.equal(corrupt.element('#abandon').disabled,true);
  assert.equal(storage.get(namespace),'{broken');assert.equal(corrupt.calls.length,1);
});

test('Capability bỏ phiên thiếu/sai/hạ cấp không bỏ qua operation còn chờ',async()=>{
  const record=JSON.stringify({version:1,file_id:'a'.repeat(24),key:'bdsg-'+'a'.repeat(32),request_key:'old-abandon'});
  for (const capability of [false,null,1,'true']) {
    const storage=new Map([['bdsg-office-abandon:context-a:'+'a'.repeat(24),record]]);
    const result=await harness([],undefined,undefined,false,{intents:true,abandonCapability:capability,storage});
    assert.equal(result.engineEvents,undefined);assert.equal(result.calls.length,1);assert.equal(storage.size,1);
    assert.equal(result.opened,false);
  }
});

test('Điện thoại phục hồi record lưu hỏng bằng bỏ phiên mà không tải engine',async()=>{
  const storage=new Map([['bdsg-office-save:context-a:'+'a'.repeat(24),'{broken']]);
  const result=await harness([],undefined,undefined,false,{intents:true,abandonCapability:true,storage,mobile:true});
  assert.equal(result.engineEvents,undefined);assert.equal(result.element('#abandon').hidden,false);
  assert.equal(result.element('#abandon').disabled,false);
  await confirmAbandon(result);
  assert.deepEqual(result.navigations,['/#office']);assert.equal(storage.size,0);
});

test('Callback SDK muộn không mở nút tải lại hoặc che hướng dẫn bỏ phiên đang chờ',async()=>{
  const result=await harness([],undefined,undefined,true,{intents:true,abandonCapability:true,clicks:0,
    abandon(){throw new TypeError('lost');}});
  await confirmAbandon(result);
  result.engineEvents.onError();
  assert.equal(result.element('#retry').hidden,true);
  assert.match(result.error.textContent,/Kiểm tra yêu cầu bỏ phiên/);
  result.engineEvents.onDocumentStateChange({data:true});
  assert.match(result.status,/bỏ phiên/);
  let warned=false;result.windowEvents.get('beforeunload')({preventDefault(){warned=true;}});
  assert.equal(warned,true);
  result.element('#back').handlers.click({preventDefault(){}});
  assert.equal(result.calls.filter(c=>c.name==='van_phong.bo_phien_soan_thao').length,1);
});

test('Key open sai định dạng không cho tạo record hoặc gửi bỏ phiên',async()=>{
  const result=await harness([],undefined,undefined,false,{intents:true,abandonCapability:true,key:'invalid-key'});
  assert.equal(result.element('#abandon').disabled,true);
  await result.element('#abandon').handlers.click();
  assert.equal(result.element('#abandon-dialog').open,false);
  assert.equal(result.storage.size,0);assert.equal(result.calls.length,1);
});

test('Retry bỏ phiên lỗi storage không khẳng định yêu cầu trước chưa được gửi',async()=>{
  const options={intents:true,abandonCapability:true,clicks:0,abandon(){throw new TypeError('lost');}};
  const result=await harness([],undefined,undefined,true,options);
  await confirmAbandon(result);
  options.storageDenied=true;
  await result.element('#abandon').handlers.click();
  assert.equal(result.calls.filter(c=>c.name==='van_phong.bo_phien_soan_thao').length,1);
  assert.match(result.error.textContent,/Chưa gửi thêm yêu cầu trong lần thử này/);
  assert.equal(result.element('main').inert,true);
});

test('Lưu gửi đúng mã lệnh khi đọc tiến trình và nhận đúng commit',async()=>{
  const result=await harness([progress({})]);
  assert.equal(success(result),true);
  assert.equal(result.calls.find(c=>c.name==='van_phong.phien_soan_thao').arguments.request_id,request);
});
test('Biên nhận của lệnh khác không được báo đã lưu',async()=>{
  const result=await harness([progress({request_id:'d'.repeat(32)})]);
  assert.equal(success(result),false);assert.equal(result.error.hidden,false);
});
test('Đã nhận lệnh chưa là commit dù last_saved cũ còn tồn tại',async()=>{
  const result=await harness([progress({command_state:'accepted'}),progress({})]);
  assert.equal(result.polls,2);assert.equal(success(result),true);
  assert.equal(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,1);
});
test('Kết quả unknown không mượn timestamp cũ hoặc tự gửi lại save',async()=>{
  const result=await harness([progress({command_state:'unknown'})]);
  assert.equal(success(result),false);assert.equal(result.error.hidden,false);
  assert.equal(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,1);
});
test('Trạng thái kết thúc không commit không mượn phiên đã lưu trước',async()=>{
  for (const state of ['failed','superseded','abandoned','unchanged']) {
    const result=await harness([progress({command_state:state})]);
    assert.equal(success(result),false,state);
  }
});
test('Luồng legacy chưa có ledger vẫn đọc được trạng thái hiện hành',async()=>{
  for (const protocol of ['legacy','absent']) {
    const result=await harness([{state:'active',pending:false,last_saved:123}],undefined,protocol);
    assert.equal(success(result),true);
    assert.deepEqual(Object.keys(result.calls.find(c=>c.name==='van_phong.phien_soan_thao').arguments),['key']);
  }
});
test('Giao thức lạ hoặc khai báo null không được hạ xuống legacy',async()=>{
  for (const protocol of ['next-version',null]) {
    const result=await harness([],undefined,protocol,false);
    assert.equal(result.opened,false);assert.equal(result.error.hidden,false);
    assert.equal(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,0);
  }
});
test('Phiên yêu cầu ledger không được hạ xuống timestamp khi DTO thiếu receipt',async()=>{
  const result=await harness([{state:'active',pending:false,last_saved:123}]);
  assert.equal(success(result),false);assert.equal(result.error.hidden,false);
});
test('Thiếu mã lệnh không được bắt đầu poll hoặc báo thành công',async()=>{
  const result=await harness([progress({})],{state:'dang-luu'});
  assert.equal(success(result),false);assert.equal(result.polls,0);
});

test('Mất phản hồi save vẫn kiểm đúng intent, không gửi write thứ hai',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key}),
    async()=>{throw new TypeError('Synthetic response lost');},undefined,true,{intents:true,clicks:2});
  assert.equal(success(result),true,JSON.stringify({calls:result.calls,snapshots:result.snapshots,error:result.error.textContent}));
  const writes=result.calls.filter(c=>c.name==='van_phong.luu_soan_thao');
  assert.equal(writes.length,1);assert.equal(writes[0].arguments.request_key,'e'.repeat(32));
  assert.equal(result.snapshots[0].inert,true);assert.equal(result.snapshots[0].closeDisabled,true);
  assert.equal(result.snapshots[0].label,'Kiểm tra lần lưu');
  assert.doesNotMatch(result.snapshots[0].status,/Synthetic|Failed to fetch/);
  assert.equal(result.storage.size,0);
});

test('Unknown giữ khóa sửa/đóng và cảnh báo rời trang dù chưa có dirty',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key,command_state:'unknown'}),undefined,undefined,true,{intents:true});
  assert.equal(result.snapshots[0].inert,true);assert.equal(result.snapshots[0].closeDisabled,true);
  let warned=false;result.windowEvents.get('beforeunload')({preventDefault(){warned=true;}});
  assert.equal(warned,true);assert.equal(result.storage.size,1);
  result.engineEvents.onDocumentReady();result.engineEvents.onError();
  assert.equal(result.element('#close').disabled,true);assert.equal(result.element('#retry').hidden,true);
  const record=JSON.parse([...result.storage.values()][0]);
  assert.deepEqual(Object.keys(record).sort(),['key','request_id','request_key','version']);
});

test('Tải lại cùng phạm vi tiếp tục hỏi intent cũ, không write mới',async()=>{
  const first=await harness([],async()=>{throw new TypeError('lost');},undefined,true,{intents:true});
  const second=await harness(args=>progress({request_key:args.request_key}),undefined,undefined,true,{intents:true,storage:first.storage});
  assert.equal(success(second),true);
  assert.equal(second.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,0);
});

test('Not-started chỉ gửi lại khi người dùng bấm và dùng cùng intent',async()=>{
  let writes=0;
  const result=await harness((args,index)=>progress({request_key:args.request_key,
      ...(index===0?{request_id:null,command_state:'not-started'}:{})}),
    async()=>{if(++writes===1)throw new TypeError('lost before write');return {state:'dang-luu',request_id:request};},
    undefined,true,{intents:true,clicks:3});
  assert.equal(result.snapshots[0].label,'Kiểm tra lần lưu');
  assert.equal(result.snapshots[1].label,'Thử lưu lại');
  assert.equal(writes,2);assert.equal(success(result),true);
  assert.deepEqual(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').map(c=>c.arguments.request_key),['e'.repeat(32),'e'.repeat(32)]);
});

test('Receipt intent khác hoặc mã lệnh đổi không được mở khóa',async()=>{
  for (const overrides of [{request_key:'other-intent'},{request_id:'d'.repeat(32)}]) {
    const result=await harness(args=>progress({request_key:args.request_key,...overrides}),undefined,undefined,true,{intents:true});
    assert.equal(success(result),false);assert.equal(result.element('main').inert,true);
    assert.equal(result.storage.size,1);
  }
});

test('Dirty mới trong lúc chờ không bị receipt cũ xóa',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key}),undefined,undefined,true,
    {intents:true,onSave(events){events.onDocumentStateChange({data:true});events.onDocumentStateChange({data:false});}});
  assert.equal(success(result),false);assert.match(result.status,/thay đổi mới chưa lưu/);
  let warned=false;result.windowEvents.get('beforeunload')({preventDefault(){warned=true;}});assert.equal(warned,true);
  assert.equal(result.element('main').inert,false);
});

test('Không giữ được record thì không gọi write',async()=>{
  const result=await harness([],undefined,undefined,true,{intents:true,storageDenied:true});
  assert.equal(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,0);
  assert.equal(result.element('main').inert,true);
});

test('Record key khác hoặc hỏng không tự bị bỏ khi mở lại',async()=>{
  const first=await harness([],async()=>{throw new TypeError('lost');},undefined,true,{intents:true});
  const wrong=await harness([],undefined,undefined,false,{intents:true,storage:first.storage,key:'bdsg-'+'b'.repeat(32)});
  assert.equal(wrong.opened,false);assert.equal(first.storage.size,1);
  first.storage.set([...first.storage.keys()][0],'{broken');
  const broken=await harness([],undefined,undefined,false,{intents:true,storage:first.storage});
  assert.equal(broken.opened,false);assert.equal(first.storage.size,1);
});

test('Server pending của chính actor khôi phục intent cho cửa sổ mới',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key}),undefined,undefined,true,
    {intents:true,pending:{request_key:'server-intent',request_id:request}});
  assert.equal(success(result),true);assert.equal(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,0);
});

test('Phạm vi khác không đọc record của phiên trước',async()=>{
  const first=await harness([],async()=>{throw new TypeError('lost');},undefined,true,{intents:true});
  const other=await harness(args=>progress({request_key:args.request_key}),undefined,undefined,true,
    {intents:true,contextKey:'context-b',storage:first.storage,intent:'f'.repeat(32)});
  assert.equal(success(other),true);assert.equal(other.storage.size,1);
  assert.equal(other.calls.find(c=>c.name==='van_phong.luu_soan_thao').arguments.request_key,'f'.repeat(32));
});

test('Không hạ capability khi còn record chưa đối soát',async()=>{
  const first=await harness([],async()=>{throw new TypeError('lost');},undefined,true,{intents:true});
  for (const protocol of ['request-ledger-v1','legacy','absent']) {
    const old=await harness([],undefined,protocol,false,{intents:false,storage:first.storage});
    assert.equal(old.opened,false,protocol);assert.equal(first.storage.size,1);
  }
});

test('Lỗi mạng có hướng dẫn tiếng Việt, không lộ thông báo transport',async()=>{
  const result=await harness([],async()=>{throw new TypeError('Failed to fetch');},undefined,true,{intents:true});
  assert.doesNotMatch(result.error.textContent,/Failed to fetch/);
  assert.match(result.error.textContent,/Kiểm tra lần lưu/);
});

test('Capability sai kiểu hoặc true ở legacy không được mở editor',async()=>{
  for (const intents of [null,1,'true']) {
    const result=await harness([],undefined,undefined,false,{intents});assert.equal(result.opened,false);
  }
  const legacy=await harness([],undefined,'legacy',false,{intents:true});assert.equal(legacy.opened,false);
});

test('Dirty đến trong khi requestClose chờ không được hủy hoặc chuyển trang',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key}),undefined,undefined,true,
    {intents:true,action:'close',onClose(events){events.onDocumentStateChange({data:true});events.onDocumentStateChange({data:false});events.onRequestClose();}});
  assert.equal(result.destroyed,0);assert.deepEqual(result.navigations,[]);
  assert.match(result.status,/thay đổi mới chưa lưu/);
  let warned=false;result.windowEvents.get('beforeunload')({preventDefault(){warned=true;}});assert.equal(warned,true);
});

test('Unchanged không báo đã lưu; phiên phục hồi không tự bỏ record',async()=>{
  const unchanged=args=>progress({request_key:args.request_key,command_state:'unchanged'});
  const fresh=await harness(unchanged,undefined,undefined,true,{intents:true});
  assert.equal(success(fresh),false);assert.match(fresh.status,/Không có thay đổi cần lưu/);
  const first=await harness([],async()=>{throw new TypeError('lost');},undefined,true,{intents:true});
  for (const options of [{intents:true,storage:first.storage},
      {intents:true,pending:{request_key:'server-intent',request_id:request}}]) {
    const restored=await harness(unchanged,undefined,undefined,true,options);
    assert.equal(success(restored),false);assert.equal(restored.storage.size,1);
    assert.equal(restored.element('main').inert,true);
  }
});

test('Back và SDK close không gửi lại khi đang đợi explicit retry',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key,request_id:null,command_state:'not-started'}),
    async()=>{throw new TypeError('lost');},undefined,true,{intents:true,clicks:2});
  assert.equal(result.snapshots[1].label,'Thử lưu lại');
  result.element('#back').handlers.click({preventDefault(){}});
  result.engineEvents.onRequestClose();
  for(let i=0;i<20;i++)await Promise.resolve();
  assert.equal(result.calls.filter(c=>c.name==='van_phong.luu_soan_thao').length,1);
  assert.equal(result.element('main').inert,true);
});

test('No-op rồi dirty lúc đóng không được diễn đạt là đã lưu phiên bản',async()=>{
  const result=await harness(args=>progress({request_key:args.request_key,command_state:'unchanged'}),undefined,undefined,true,
    {intents:true,action:'close',onClose(events){events.onDocumentStateChange({data:true});events.onDocumentStateChange({data:false});events.onRequestClose();}});
  assert.equal(result.destroyed,0);assert.match(result.status,/thay đổi mới chưa lưu/);
  assert.doesNotMatch(result.status,/Đã lưu/);
});
