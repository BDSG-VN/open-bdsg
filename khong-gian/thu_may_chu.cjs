"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync(__dirname + "/may-chu.js", "utf8");
function harness(api, user = {id:"fixture",role:"quan-tri"}) {
  const main = {innerHTML:""}, controls = {};
  const window = {}, state = {view:"system",user};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  vm.runInNewContext(source, {window,state,main,api,esc,document:{querySelector:key=>controls[key]??=( {})}});
  return {app:window.BDSGNode,state,main,controls};
}
const fixture = () => ({node:{node:{id:"TH01"},observed_at:"2026-11-17T00:00:00Z",status:"partial",alerts:[],host:{virtualization:{}},cpu:{load_average:{}},memory:{},storage:{}},operations:{status:"ready",release:"unknown"},recovery:{status:"unknown",offsite:{configured:false}}});
test("Khách và operator không gọi số liệu riêng", async () => {
  for (const user of [null,{id:"test",role:"operator"}]) {
    let calls=0; const h=harness(()=>calls++,user); await h.app.open();
    assert.equal(calls,0); assert.match(h.main.innerHTML,/Chỉ chủ quản/);
  }
});
test("Số liệu thiếu hiển thị chưa đo, không giả số 0", async () => {
  const h=harness(async()=>fixture()); await h.app.open();
  assert.match(h.main.innerHTML,/Chưa đo được/); assert.match(h.main.innerHTML,/Chưa khai báo/);
  assert.match(h.main.innerHTML,/Chưa có kết quả còn hiệu lực/); assert.doesNotMatch(h.main.innerHTML,/NaN|undefined/);
});
test("Lỗi có thể thử lại mà không làm lộ ngoại lệ", async () => {
  let failure=true;const h=harness(async()=>{if(failure)throw Error("private-path");return fixture();});
  await h.app.open(); assert.match(h.main.innerHTML,/Chưa đọc được số liệu/); assert.doesNotMatch(h.main.innerHTML,/private-path/);
  failure=false;await h.controls["#node-retry"].onclick(); assert.match(h.main.innerHTML,/Máy chủ TH01/);
});
test("Kết quả đến trễ sau đổi tài khoản không được vẽ", async () => {
  let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.app.open();
  h.state.user={id:"other",role:"operator"};h.app.reset();h.main.innerHTML="new-account";
  resolve(fixture());await pending;assert.equal(h.main.innerHTML,"new-account");
});
test("Kết quả đến trễ sau rời ứng dụng không được vẽ", async () => {
  let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.app.open();
  h.app.leave();h.main.innerHTML="other-app";resolve(fixture());await pending;
  assert.equal(h.main.innerHTML,"other-app");
});
test("Nhãn máy và số liệu được escape trước khi vẽ", async () => {
  const data=fixture();data.node.host.os='<script>alert(1)</script>';
  const h=harness(async()=>data);await h.app.open();
  assert.doesNotMatch(h.main.innerHTML,/<script>/);assert.match(h.main.innerHTML,/&lt;script&gt;/);
});
test("Bản ngoài máy đã kiểm vẫn phân biệt với lịch tự động", async () => {
  const data=fixture();data.offsite={status:"verified",verified_at:1000,backup_age_seconds:3600,decryption_verified:true};
  const h=harness(async()=>data);await h.app.open();
  assert.match(h.main.innerHTML,/Đã có bản được kiểm/);
  assert.match(h.main.innerHTML,/Checksum và giải mã đạt/);
  assert.match(h.main.innerHTML,/Chưa xác minh tự động/);
});
test("Bản ngoài máy quá cũ không được hiển thị như bản còn mới", async () => {
  const data=fixture();data.offsite={status:"stale",verified_at:1000,backup_age_seconds:300000,decryption_verified:false};
  const h=harness(async()=>data);await h.app.open();
  assert.match(h.main.innerHTML,/Bản sao đã cũ/);
  assert.doesNotMatch(h.main.innerHTML,/Đã có bản được kiểm|Checksum và giải mã đạt/);
});
