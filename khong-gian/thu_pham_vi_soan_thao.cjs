'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const me = {authenticated:true,user:{id:'actor'},workspace:{mode:'units'}};
function fixture({legacy=false,noParent=false,parentOverride}={}) {
  let generation=1;
  const scope={id:'unit-a',epoch:2,revision:3};
  const calls=[],stops=[],listeners=new Map(),windowEvents=new Map(),ticks=[];
  const parent={closed:false,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener() {}};
  parent.BDSGUnit={capture:()=>({generation}),current:t=>t.generation===generation,
    snapshot:()=>({mode:'units',actorId:'actor',selected:{...scope},status:'ready'}),
    headers:()=>({'X-BDSG-Unit':'unit-a','X-BDSG-Unit-Epoch':'2','X-BDSG-Unit-Revision':'3'})};
  const base={ready:Promise.resolve(),active:true,assertActive(){assert.equal(this.active,true);},async check(){},
    async fetch(path,options={}) {
      calls.push({path,options});
      return {ok:true,status:200,json:async()=>path==='/api/me' ? {...me,workspace:{mode:legacy?'legacy':'units'}} : {units:[{...scope}]}};
    }};
  const win={opener:noParent?null:parentOverride||parent,parent:null,addEventListener:(name,fn)=>windowEvents.set(name,fn),removeEventListener(){},
    BDSGSessionGuard:{create:()=>base}};
  win.parent=win;
  const context={window:win,document:{addEventListener(){},removeEventListener(){},visibilityState:'visible'},
    Headers,AbortController,AbortSignal,setInterval:fn=>{ticks.push(fn);return 1;},clearInterval(){}};
  vm.runInNewContext(fs.readFileSync(__dirname+'/bao-ve-office.js','utf8'),context);
  const guard=win.BDSGOfficeGuard.create({onInvalidate:message=>stops.push(message)});
  return {guard,calls,stops,parent,base,scope,ticks,windowEvents,change(){generation++;listeners.get('bdsg-unit-changed')?.();}};
}

test('Cửa sổ gửi phạm vi đã chụp, không nhận header đơn vị giả từ caller',async()=>{
  const f=fixture();await f.guard.ready;
  await f.guard.fetch('/api/tools',{headers:{'X-BDSG-Unit':'forged'}});
  const headers=new Headers(f.calls.at(-1).options.headers);
  assert.equal(headers.get('X-BDSG-Unit'),'unit-a');
  assert.equal(headers.get('X-BDSG-Unit-Epoch'),'2');
  assert.equal(headers.get('X-BDSG-Unit-Revision'),'3');
  assert.equal(f.guard.active,true);
});

test('Namespace trạng thái lưu ghim actor và đơn vị, hết hiệu lực cùng guard',async()=>{
  const f=fixture();await f.guard.ready;
  assert.deepEqual(JSON.parse(f.guard.contextKey),['actor','unit-a',2,3]);
  f.change();assert.throws(()=>f.guard.contextKey);
});
test('Gỡ cửa sổ ứng dụng cha dừng editor dù token đơn vị chưa đổi',async()=>{
  const f=fixture();f.parent.frameElement={isConnected:true};await f.guard.ready;
  f.parent.frameElement.isConnected=false;
  await assert.rejects(f.guard.fetch('/api/tools'));
  assert.equal(f.guard.active,false);assert.equal(f.stops.length,1);
});

async function realParent() {
  const listeners=new Map();
  let rows=[{id:'unit-a',name:'A',role:'member',epoch:2,revision:3},
    {id:'unit-b',name:'B',role:'member',epoch:1,revision:1}];
  const parent={closed:false,location:{pathname:'/'},sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}},
    addEventListener(name,fn){listeners.set(name,fn);},removeEventListener(){},
    dispatchEvent(event){listeners.get(event.type)?.(event);},CustomEvent:class {constructor(type){this.type=type;}},
    fetch:async()=>({ok:true,json:async()=>({units:rows})})};
  parent.parent=parent;
  vm.runInNewContext(fs.readFileSync(__dirname+'/don-vi.js','utf8'),{window:parent});
  await parent.BDSGUnit.boot(me);await parent.BDSGUnit.switchTo('unit-a');
  return {parent,changeMembership(){rows=rows.map(r=>({...r,epoch:r.epoch+1}));}};
}

test('BDSGUnit thật đổi A→B→A hoặc rejoin không cấp lại cửa sổ đã dừng',async()=>{
  const root=await realParent();const f=fixture({parentOverride:root.parent});await f.guard.ready;
  await root.parent.BDSGUnit.switchTo('unit-b');await root.parent.BDSGUnit.switchTo('unit-a');
  assert.equal(f.guard.active,false);await assert.rejects(f.guard.fetch('/api/tools'));
  const g=fixture({parentOverride:root.parent});await g.guard.ready;
  root.changeMembership();await root.parent.BDSGUnit.refresh();
  assert.equal(g.guard.active,false);
});

test('Cha cross-origin hoặc khác danh tính không cấp phạm vi editor',async()=>{
  const foreign={};Object.defineProperty(foreign,'BDSGUnit',{get(){throw new Error('cross-origin');}});
  const a=fixture({parentOverride:foreign});await assert.rejects(a.guard.ready);
  const root=await realParent();
  await root.parent.BDSGUnit.boot({...me,user:{id:'different'}});
  await root.parent.BDSGUnit.switchTo('unit-a');
  const b=fixture({parentOverride:root.parent});await assert.rejects(b.guard.ready);
});

test('Không hạ cửa sổ đã chụp đơn vị xuống legacy khi workspace thay đổi',async()=>{
  const f=fixture({legacy:true});await assert.rejects(f.guard.ready);
  assert.equal(f.guard.active,false);
});

test('Cha tải lại hoặc chuyển trang không giữ scope từ đối tượng cũ',async()=>{
  const f=fixture();await f.guard.ready;
  f.parent.BDSGUnit={...f.parent.BDSGUnit};
  await assert.rejects(f.guard.fetch('/api/tools'));
  assert.equal(f.stops.length,1);
});

test('Cha đổi đơn vị trong lúc mở hoặc đổi A→B→A không hồi sinh cửa sổ',async()=>{
  const opening=fixture();opening.change();
  await assert.rejects(opening.guard.ready);
  assert.equal(opening.guard.active,false);
  const f=fixture();await f.guard.ready;f.change();f.change();
  await assert.rejects(f.guard.fetch('/api/tools'));
  assert.equal(f.stops.length,1);
  assert.equal(f.calls.some(c=>c.path==='/api/tools'),false);
});

test('Editor đơn vị không mở trực tiếp; legacy không tự thêm scope',async()=>{
  const direct=fixture({noParent:true});await assert.rejects(direct.guard.ready);
  const legacy=fixture({noParent:true,legacy:true});await legacy.guard.ready;
  await legacy.guard.fetch('/api/tools',{headers:{'X-BDSG-Unit':'forged','X-BDSG-Unit-Epoch':'99'}});
  assert.equal(new Headers(legacy.calls.at(-1).options.headers).has('X-BDSG-Unit'),false);
  assert.equal(new Headers(legacy.calls.at(-1).options.headers).has('X-BDSG-Unit-Epoch'),false);
});

test('Đổi membership revision hoặc cha đóng dừng trước lời gọi tiếp',async()=>{
  const f=fixture();await f.guard.ready;f.scope.revision++;
  await assert.rejects(f.guard.check());assert.equal(f.guard.active,false);
  const g=fixture();await g.guard.ready;g.parent.closed=true;
  await assert.rejects(g.guard.fetch('/api/tools'));
  assert.equal(g.stops.length,1);
});

test('Phản hồi muộn sau đổi cha bị bỏ dù transport không tuân theo abort',async()=>{
  const f=fixture();await f.guard.ready;
  let finish;
  f.base.fetch=()=>new Promise(resolve=>{finish=resolve;});
  const request=f.guard.fetch('/api/tools');
  await Promise.resolve();f.change();
  finish({ok:true,status:200});await assert.rejects(request);
});

test('409 nghiệp vụ giữ phiên; unit_changed dừng phiên',async()=>{
  const f=fixture();await f.guard.ready;
  f.base.fetch=async()=>({status:409,clone:()=>({json:async()=>({code:'conflict'})})});
  await f.guard.fetch('/api/tools');assert.equal(f.guard.active,true);
  f.base.fetch=async()=>({status:409,clone:()=>({json:async()=>({code:'unit_changed'})})});
  await assert.rejects(f.guard.fetch('/api/tools'));assert.equal(f.guard.active,false);
});

test('Hai cửa sổ không dùng chung controller hủy hoặc trạng thái dừng',async()=>{
  const a=fixture(),b=fixture();await Promise.all([a.guard.ready,b.guard.ready]);
  a.change();await b.guard.fetch('/api/tools');
  assert.equal(a.guard.active,false);assert.equal(b.guard.active,true);
});

// Hủy SDK ngay trong pagehide làm Chromium phát cảnh báo trên frame đã bị tách.
test('Rời trang khóa guard ngay, chỉ dọn editor khi trang được hiện lại',async()=>{
  const f=fixture();await f.guard.ready;
  f.windowEvents.get('pagehide')({persisted:true});
  assert.equal(f.guard.active,false);
  assert.equal(f.stops.length,0);
  await assert.rejects(f.guard.fetch('/api/tools'));
  assert.equal(f.calls.some(c=>c.path==='/api/tools'),false);
  f.windowEvents.get('pageshow')({persisted:true});
  assert.equal(f.stops.length,1);
  assert.equal(f.guard.active,false);
  f.windowEvents.get('pageshow')({persisted:true});
  f.change();
  assert.equal(f.stops.length,1);
});
