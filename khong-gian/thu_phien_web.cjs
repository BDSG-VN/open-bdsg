"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync(__dirname + "/phien-web.js", "utf8");
function harness(api, user = {id:"fixture",name:"Người dùng thử",role:"operator"}) {
  const controls = {}, window = {}, state = {view:"account",user};
  const main = {innerHTML:"",querySelector:key => key === "[data-rename-form]" || key === ".sessions-dialog" ? null : controls[key] ??= {},querySelectorAll:()=>[]};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  vm.runInNewContext(source, {window,state,main,api,esc,document:{querySelector:()=>({click(){}})}});
  return {app:window.BDSGSessions,state,main,controls};
}
const fixture = () => ({sessions:[{id:"public-id",label:"",client_hint:"Windows",created_at:null,last_seen_at:1794867600,expires_at:1794896400,current:true}],has_more:false});

test("Khách không gọi danh sách phiên riêng", async () => {
  let calls=0;const h=harness(()=>calls++,null);await h.app.open();
  assert.equal(calls,0);assert.match(h.main.innerHTML,/Đăng nhập để xem/);
});
test("Phiên cũ không được suy đoán ngày tạo hoặc trạng thái online", async () => {
  const h=harness(async()=>fixture());await h.app.open();
  assert.match(h.main.innerHTML,/Bắt đầu: Chưa ghi nhận/);
  assert.match(h.main.innerHTML,/Phiên hiện tại/);
  assert.match(h.main.innerHTML,/không phải trạng thái thiết bị đang online/);
  assert.match(h.main.innerHTML,/Quyền Office, kết nối Google, SSH và token agent/);
});
test("Nhãn và tên người dùng được escape", async () => {
  const data=fixture();data.sessions[0].label='<img src=x onerror=alert(1)>';
  const h=harness(async()=>data,{id:"fixture",name:'<svg onload=alert(1)>',role:"operator"});await h.app.open();
  assert.doesNotMatch(h.main.innerHTML,/<img|<svg/);assert.match(h.main.innerHTML,/&lt;img/);assert.match(h.main.innerHTML,/&lt;svg/);
});
test("Lỗi mạng và danh sách thiếu phiên hiện tại đều có thử lại", async () => {
  for(const result of [()=>{throw Error("private-location");},()=>({sessions:[],has_more:false})]) {
    let failed=true;const h=harness(async()=>failed?result():fixture());await h.app.open();
    assert.match(h.main.innerHTML,/Chưa đọc được phiên đăng nhập/);assert.doesNotMatch(h.main.innerHTML,/private-location/);
    failed=false;await h.controls["#sessions-retry"].onclick();assert.match(h.main.innerHTML,/Phiên hiện tại/);
  }
});
test("Danh sách giới hạn giải thích phạm vi thu hồi các phiên khác", async () => {
  const data=fixture();data.has_more=true;const h=harness(async()=>data);await h.app.open();
  assert.match(h.main.innerHTML,/áp dụng cho những phiên chưa hiển thị/);
});
test("Phản hồi cũ sau đổi danh tính bị loại bỏ", async () => {
  let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.app.open();
  h.state.user={id:"other",role:"operator"};h.app.reset();h.main.innerHTML="other-account";
  resolve(fixture());await pending;assert.equal(h.main.innerHTML,"other-account");
});
test("Phản hồi cũ sau rời ứng dụng hoặc mở lại bị loại bỏ", async () => {
  let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.app.open();
  h.app.leave();h.main.innerHTML="other-view";resolve(fixture());await pending;assert.equal(h.main.innerHTML,"other-view");
  const pending2=h.app.open();h.state.view="work";h.main.innerHTML="work";
  resolve(fixture());await pending2;assert.equal(h.main.innerHTML,"work");
});
