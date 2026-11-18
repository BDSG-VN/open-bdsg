// Gọi nút Lưu và giao thức HTTP của controller thật; không mở store nội bộ.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const request = 'c'.repeat(32);
async function harness(progresses, saved = {state:'dang-luu',request_id:request}, protocol = 'request-ledger-v1', expectReady = true) {
  const calls = [], elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      disabled: selector === '#save', hidden: true, textContent:'', handlers:{},
      focus() {}, replaceChildren() {},
      addEventListener(name, handler) { this.handlers[name] = handler; },
    });
    return elements.get(selector);
  }
  let index = 0;
  const guard = {
    ready:Promise.resolve(),active:true,assertActive() {},
    async fetch(route, options) {
      assert.equal(route,'/api/tools');
      const body = JSON.parse(options.body); calls.push(body);
      let result;
      if (body.name === 'van_phong.mo_soan_thao') result = {
        key:'bdsg-'+'a'.repeat(32),config:{},api_url:'/office-docs/web-apps/apps/api/documents/api.js',save_protocol:protocol,
      };
      else if (body.name === 'van_phong.luu_soan_thao') result = saved;
      else {
        assert.equal(body.name,'van_phong.phien_soan_thao');
        result = progresses[Math.min(index++,progresses.length-1)];
      }
      if (body.name === 'van_phong.mo_soan_thao' && protocol === 'absent') delete result.save_protocol;
      return {ok:true,json:async()=>({ok:true,ket_qua:result})};
    },
  };
  const context = {
    window:{BDSGSessionGuard:{create:()=>guard},addEventListener() {}},
    document:{querySelector:element,createElement:()=>({}),
      head:{append:script=>queueMicrotask(()=>script.onload())}},
    location:{search:'?id='+'a'.repeat(24),assign() {},reload() {}},
    matchMedia:()=>({matches:false}),URLSearchParams,AbortSignal,
    setTimeout:(fn,delay)=>{if(delay<5000)queueMicrotask(fn);return 1;},clearTimeout() {},
    DocsAPI:{DocEditor:class {
      constructor(_id, config) {queueMicrotask(()=>config.events.onDocumentReady());}
      destroyEditor() {} requestClose() {}
    }},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'soan-thao.js'),'utf8'),context);
  for (let i=0;i<30 && element('#save').disabled;i++) await Promise.resolve();
  if (!expectReady) return {calls,opened:!element('#save').disabled,error:element('#error')};
  assert.equal(element('#save').disabled,false,'Editor phải sẵn sàng trước thao tác');
  await element('#save').handlers.click();
  return {calls,status:element('#status').textContent,error:element('#error'),polls:index};
}
const progress = overrides => ({state:'active',pending:false,last_saved:123,
  request_id:request,command_state:'committed',...overrides});
const success = result => result.status === 'Đã lưu phiên bản vào kho BDSG.';

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
