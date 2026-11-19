'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function fixture() {
  let current=true,enabled=true,returned=0;
  const nodes=[],events=new Map();
  const trigger={isConnected:true,focus(){this.focused=true;}};
  function element(tag) {
    const node={tag,contentWindow:{},isConnected:true,handlers:{},setAttribute(){},
      append(child){this.child=child;},addEventListener(type,fn){this.handlers[type]=fn;},
      showModal(){this.open=true;},close(){this.open=false;},remove(){this.isConnected=false;},focus(){}};
    nodes.push(node);return node;
  }
  const win={BDSGUnit:{snapshot:()=>({mode:'units',status:'ready',selected:{id:'a'},capabilities:{office_editor:enabled}}),
    capture:()=>({generation:1}),current:()=>current},
    addEventListener:(name,fn)=>events.set(name,fn)};
  vm.runInNewContext(fs.readFileSync(__dirname+'/mo-soan-thao.js','utf8'),{
    window:win,document:{activeElement:trigger,body:{append(){}},createElement:element}});
  return {api:win.BDSGOfficeLauncher,nodes,events,trigger,disable(){enabled=false;},
    change(){current=false;events.get('bdsg-unit-changed')?.();},onReturn(){returned++;},get returned(){return returned;}};
}
test('mở iframe cùng origin chỉ mang mã tệp, đóng đúng cửa sổ trả về kho tệp',()=>{
  const f=fixture();f.api.open('a'.repeat(24),f.onReturn);
  const frame=f.nodes.find(n=>n.tag==='iframe');
  assert.equal(frame.src,'/soan-thao.html?id='+'a'.repeat(24));
  assert.equal(f.api.active,true);
  assert.equal(f.api.finish({}),false);
  assert.equal(f.returned,0);
  assert.equal(f.api.finish(frame.contentWindow),true);
  assert.equal(f.api.active,false);assert.equal(f.returned,1);assert.equal(f.trigger.focused,true);
});
test('capability đóng, mã tệp sai và mở trùng đều không dựng cửa sổ mới',()=>{
  const f=fixture();f.disable();assert.throws(()=>f.api.open('a'.repeat(24)));
  assert.equal(f.nodes.length,0);
  const g=fixture();assert.throws(()=>g.api.open('https://other.example'));
  g.api.open('a'.repeat(24));assert.throws(()=>g.api.open('b'.repeat(24)));
  assert.equal(g.nodes.filter(n=>n.tag==='iframe').length,1);
});
test('Escape không bỏ tài liệu; đổi đơn vị đóng iframe và bỏ kết quả quay về muộn',()=>{
  const f=fixture();f.api.open('a'.repeat(24),f.onReturn);
  const dialog=f.nodes.find(n=>n.tag==='dialog'),frame=f.nodes.find(n=>n.tag==='iframe');
  let prevented=false;dialog.handlers.cancel({preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(f.api.active,true);
  f.change();assert.equal(f.api.active,false);assert.equal(dialog.isConnected,false);
  assert.equal(f.api.finish(frame.contentWindow),false);assert.equal(f.returned,0);
});
