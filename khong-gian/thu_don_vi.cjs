'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function client({storage = new Map(), parent, pathname = '/'} = {}) {
  let memberships = [{id:'a',name:'A',role:'admin',epoch:1,revision:1},{id:'b',name:'B',role:'member',epoch:2,revision:1}];
  const events = [];
  const win = {location:{pathname},dispatchEvent:event=>events.push(event),sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}},fetch:async()=>({ok:true,json:async()=>({units:memberships})})};
  win.window=win; win.parent=parent||win;
  vm.runInNewContext(fs.readFileSync(__dirname+'/don-vi.js','utf8'),win);
  return {unit:win.BDSGUnit,win,events,setUnits:value=>memberships=value,storage};
}
const me = {user:{id:'actor',name:'Actor',role:'nguoi-dung'},workspace:{mode:'units',system_admin:true,apps:['account','projects']}};

test('capability Office chỉ nhận boolean thật, snapshot không sửa được trạng thái gốc',async()=>{
  const {unit}=client();
  await unit.boot({...me,workspace:{...me.workspace,capabilities:{office_editor:true,unknown:true}}});
  assert.equal(unit.snapshot().capabilities.office_editor,true);
  unit.snapshot().capabilities.office_editor=false;
  assert.equal(unit.snapshot().capabilities.office_editor,true);
  await unit.boot({...me,workspace:{...me.workspace,capabilities:{office_editor:'true'}}});
  assert.equal(unit.snapshot().capabilities.office_editor,false);
  await unit.boot(me);
  assert.equal(unit.snapshot().capabilities.office_editor,false);
});

test('client OAuth la control plane nhung consent va grant van can don vi',async()=>{
  const {unit}=client();await unit.boot(me);
  assert.deepEqual(Object.keys(unit.headers('/api/oauth/clients')),[]);
  assert.deepEqual(Object.keys(unit.headers('/api/oauth/clients/disable')),[]);
  assert.throws(()=>unit.headers('/api/oauth/bind'),/đơn vị/i);
  assert.throws(()=>unit.headers('/api/oauth/decide'),/đơn vị/i);
  assert.throws(()=>unit.headers('/api/mcp/grants'),/đơn vị/i);
});
test('don vi phai duoc chon tu danh sach thanh vien truoc khi goi API rieng',async()=>{
  const {unit} = client(); await unit.boot(me);
  assert.equal(unit.snapshot().selected,null);
  assert.throws(()=>unit.headers('/api/projects'),/đơn vị/i);
  await unit.switchTo('a');
  assert.equal(unit.headers('/api/projects')['X-BDSG-Unit'],'a');
  assert.equal(unit.canAdmin(),true);
  await assert.rejects(unit.switchTo('other'));
});
test('doi don vi huy token cu, giu tai khoan, khong ghi noi dung vao bo nho',async()=>{
  const {unit,storage,events} = client(); await unit.boot(me); await unit.switchTo('a');
  const token = unit.capture();
  await unit.switchTo('b');
  assert.equal(unit.current(token),false);
  assert.equal(unit.snapshot().actorId,'actor');
  assert.equal(unit.canAdmin(),false);
  assert.equal(storage.size,1); assert.deepEqual([...storage.values()],['b']);
  const count = events.filter(event=>event.type==='bdsg-unit-changed').length;
  await unit.refresh();
  assert.equal(events.filter(event=>event.type==='bdsg-unit-changed').length,count);
  const result = unit.snapshot(); result.selected.id = 'forged'; result.units[0].role='member';
  assert.equal(unit.headers('/api/projects')['X-BDSG-Unit'],'b');
});
test('thu hoi va chu ky vai tro khong khoi phuc token cu du quay lai don vi A',async()=>{
  const {unit,setUnits} = client(); await unit.boot(me); await unit.switchTo('a');
  const first = unit.capture();
  setUnits([{id:'a',name:'A',role:'member',epoch:1,revision:2}]); await unit.refresh();
  assert.equal(unit.canAdmin(),false); assert.equal(unit.current(first),false);
  assert.equal(unit.headers('/api/projects')['X-BDSG-Unit-Revision'],'2');
  const second = unit.capture();
  setUnits([]); await unit.refresh(); assert.equal(unit.snapshot().selected,null);
  assert.throws(()=>unit.headers('/api/projects'));
  setUnits([{id:'a',name:'A',role:'admin',epoch:3,revision:1}]); await unit.refresh();
  assert.equal(unit.snapshot().selected,null);
  await unit.switchTo('a'); assert.equal(unit.current(first),false); assert.equal(unit.current(second),false);
  assert.equal(unit.headers('/api/projects')['X-BDSG-Unit-Epoch'],'3');
});
test('danh sach va phien tai khoan khong nhan header don vi',async()=>{
  const {unit} = client(); await unit.boot(me); await unit.switchTo('a');
  for (const path of ['/api/me','/api/catalogue','/api/units','/api/units/a/members','/api/sessions','/api/sessions/rename','/api/login','/api/logout','/api/auth/google']) {
    assert.equal(Object.keys(unit.headers(path)).length,0,path);
  }
  assert.equal(unit.headers('/api/model')['X-BDSG-Unit'],'a');
  assert.equal(unit.headers('/api/modules')['X-BDSG-Unit'],'a');
});
test('hai tab chon doc lap va tai khoan khac khong ke thua lua chon',async()=>{
  const first = client(), second = client();
  await first.unit.boot(me); await second.unit.boot(me);
  await first.unit.switchTo('a'); await second.unit.switchTo('b');
  assert.equal(first.unit.snapshot().selected.id,'a'); assert.equal(second.unit.snapshot().selected.id,'b');
  const restored = client({storage:first.storage}); await restored.unit.boot(me);
  assert.equal(restored.unit.snapshot().selected.id,'a');
  await restored.unit.boot({...me,user:{...me.user,id:'other'}});
  assert.equal(restored.unit.snapshot().selected,null);
  assert.equal(first.unit.snapshot().selected.id,'a');
});
test('cua so con dong bang pham vi truoc khi cho API me va chan token sau khi cha doi',async()=>{
  const root = client(); await root.unit.boot(me); await root.unit.switchTo('a');
  const pendingChild = client({parent:root.win,pathname:'/workspace.html'});
  const activeChild = client({parent:root.win,pathname:'/workspace.html'});
  await activeChild.unit.boot(me); const token = activeChild.unit.capture();
  await root.unit.switchTo('b');
  await assert.rejects(pendingChild.unit.boot(me));
  assert.equal(activeChild.unit.current(token),false);
  assert.throws(()=>activeChild.unit.headers('/api/projects'));
  await assert.rejects(activeChild.unit.boot(me));
  assert.equal(activeChild.unit.snapshot().selected.id,'a');
});
test('xac nhan chuyen co the huy va doi pham vi trong luc xac nhan khong duoc ghi de',async()=>{
  const {unit} = client(); await unit.boot(me); await unit.switchTo('a');
  const remove = unit.beforeSwitch(async()=>false); await unit.switchTo('b');
  assert.equal(unit.snapshot().selected.id,'a'); remove();
  let resolve; const waiting = new Promise(done=>resolve=done);
  const unhook = unit.beforeSwitch(()=>waiting);
  const changing = unit.switchTo('b');
  await unit.refresh({invalidate:true}); resolve(true);
  await assert.rejects(changing); unhook();
  assert.equal(unit.snapshot().selected,null);
});
test('che do cu giu khoa danh tinh va quyen quan tri cu',async()=>{
  const {unit,storage} = client(); storage.set('bdsg-legacy','unchanged');
  await unit.boot({user:{id:'legacy-actor',role:'quan-tri'}});
  assert.equal(unit.contextKey(),'legacy-actor'); assert.equal(unit.canAdmin(),true);
  assert.equal(Object.keys(unit.headers('/api/tools')).length,0);
  assert.equal(storage.get('bdsg-legacy'),'unchanged');
});
test('cua so con bao unit_changed phai xoa pham vi cha ngay va khong nhan pham vi moi',async()=>{
  const root = client(); await root.unit.boot(me); await root.unit.switchTo('a');
  const child = client({parent:root.win,pathname:'/workspace.html'});
  await child.unit.boot(me); const token = child.unit.capture();
  const invalidating = child.unit.refresh({invalidate:true});
  assert.equal(root.unit.snapshot().selected,null);
  assert.equal(child.unit.current(token),false);
  await invalidating;
  assert.equal(root.unit.snapshot().selected,null);
  assert.equal(child.unit.snapshot().selected.id,'a');
  assert.throws(()=>child.unit.headers('/api/projects'));
});
test('cua so con mo khi cha dang lam moi van dung pham vi da dong bang con hieu luc',async()=>{
  const root = client(); await root.unit.boot(me); await root.unit.switchTo('a');
  let finish;
  root.win.fetch=()=>new Promise(resolve=>finish=resolve);
  const refreshing=root.unit.refresh();
  assert.equal(root.unit.snapshot().status,'loading');
  const child=client({parent:root.win,pathname:'/workspace.html'});
  await child.unit.boot(me);
  assert.equal(child.unit.headers('/api/tasks')['X-BDSG-Unit'],'a');
  const token=child.unit.capture();
  finish({ok:true,json:async()=>({units:[]})}); await refreshing;
  assert.equal(child.unit.current(token),false);
  assert.throws(()=>child.unit.headers('/api/tasks'));
});
