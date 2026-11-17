"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const shell = fs.readFileSync(__dirname + "/he-dieu-hanh.js", "utf8");
const os = require("./he-dieu-hanh-state.js");
const tick = () => new Promise(resolve => setImmediate(resolve));
function harness() {
  const events = new Map(), nodes = new Map(), frames = [], stored = new Map(), created = [];
  let membership = null, revision = 1, before, confirmations = 0;
  const node = () => ({hidden:false, className:"", dataset:{}, classList:{add(){},remove(){},toggle(){}},
    listeners:{},setAttribute(){}, addEventListener(name,fn){this.listeners[name]=fn;}, focus(){this.focused = true;}, remove(){this.removed = true;},
    append(value){if (value.tag === "iframe") frames.push(value);}, querySelectorAll(){return [];},
    querySelector(key){if (!nodes.has(key)) nodes.set(key,node()); return nodes.get(key);},
    contentWindow:{postMessage(){}}});
  const unit = {snapshot:()=>({mode:"units",selected:membership,status:"ready",apps:["account","browser","work","tasks","projects","office","ai-settings","modules","staff"]}),
    contextKey:()=>JSON.stringify(["actor",membership?.id || null,revision]),
    capture(){return this.contextKey();}, current(value){return value === this.contextKey();},
    beforeSwitch(fn){before = fn;}, async boot(){}};
  const window = {BDSGOSState:os,BDSGUnit:unit,addEventListener:(name,fn)=>events.set(name,fn)};
  const document = {body:node(),documentElement:node(),createElement:tag=>{const value={...node(),tag};created.push(value);return value;},addEventListener(){},querySelector:()=>null};
  const store = {getItem:key=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,value),removeItem:key=>stored.delete(key)};
  vm.runInNewContext(shell,{window,parent:window,document,state:{user:{id:"actor",name:"Kiểm thử"},products:[]},
    location:{pathname:"/",origin:"https://example.test"},localStorage:store,sessionStorage:store,
    matchMedia:()=>({matches:false}),setInterval(){},setTimeout(){},
    confirm:()=>{confirmations++;return true;},esc:value=>String(value),icon:()=>"",clean:value=>value,
    api:async()=>({user:{id:"actor"}}),clearPrivateState(){},refresh:async()=>{}});
  window.BDSGSession.check = async()=>true;
  return {window,nodes,frames,stored,events,clickApp(id){return created.find(item=>item.id==='bdsg-os').listeners.click({target:{closest:selector=>selector==='[data-os-app]' ? {dataset:{osApp:id}} : null}});},get confirmations(){return confirmations;},before:()=>before(),
    select(id){membership = id ? {id,role:"member"} : null;revision++;events.get("bdsg-unit-changed")();}};
}
test("Chưa chọn đơn vị chặn deeplink nghiệp vụ, báo cách khắc phục và đưa focus về selector",()=>{
  const h=harness();h.window.BDSGDesktop.open();
  for (const route of ["#work","#tasks","#projects","#office","#ai-settings","#modules","#staff"]) {
    assert.equal(h.window.BDSGDesktop.openRoute(route),false);
  }
  assert.equal(h.nodes.get("#os-notice").textContent,"Chọn đơn vị để làm việc");
  assert.equal(h.nodes.get("#os-unit-select").focused,true);
  assert.equal(h.frames.length,0);
});
test("Tài khoản và trình duyệt vẫn mở được khi chưa chọn đơn vị",async()=>{
  const h=harness();h.window.BDSGDesktop.open();
  assert.equal(h.window.BDSGDesktop.openRoute("#account"),true);await tick();
  assert.equal(h.frames.length,1);
  await h.clickApp("browser");
  assert.equal(h.frames.length,2);
  assert.equal(h.frames[1].src,"/trinh-duyet.html");
});
test("Đổi đơn vị buộc xóa iframe và metadata cũ, xác nhận chỉ nằm trong hook chuyển chủ động",async()=>{
  const h=harness();h.window.BDSGDesktop.open();h.select("dv-a");
  assert.equal(h.window.BDSGDesktop.openRoute("#work"),true);await tick();
  const oldFrame=h.frames[0];assert.ok(oldFrame);
  assert.equal(await h.before(),true);assert.equal(h.confirmations,1);
  h.select("dv-b");
  assert.equal(oldFrame.removed,true);
  assert.equal(h.confirmations,1);
  assert.equal([...h.stored.keys()].some(key=>key.includes("dv-a")),false);
  assert.equal(JSON.parse([...h.stored.values()].find(value=>value.includes('"sessions"'))).sessions.length,0);
});
