"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { createSession, findProducts, safeURL, MAX_TABS } = require("./trinh-duyet.js");

test("Mỗi tab có lịch sử riêng; đổi hướng bỏ nhánh tiến tới", () => {
  const session = createSession();
  const first = session.current().id;
  session.navigate({ kind: "search", query: "khach hang" });
  session.navigate({ kind: "url", url: "https://bdsg.vn/" });
  session.move(-1);
  assert.equal(session.current().history[session.current().index].query, "khach hang");
  session.navigate({ kind: "bookmarks" });
  session.move(1);
  assert.equal(session.current().history.at(-1).kind, "bookmarks");
  assert.equal(session.current().history.length, 3);
  session.add();
  assert.equal(session.current().history.length, 1);
  session.select(first);
  assert.equal(session.current().index, 2);
});

test("Giới hạn tab và đóng tab cuối tạo một tab trống", () => {
  const session = createSession();
  for (let i = 1; i < MAX_TABS; i++) assert.equal(session.add(), true);
  assert.equal(session.add(), false);
  assert.equal(session.tabs.length, MAX_TABS);
  for (const tab of [...session.tabs]) session.close(tab.id);
  assert.equal(session.tabs.length, 1);
  assert.equal(session.current().history[0].kind, "home");
});

test("Tìm kiếm tiếng Việt bỏ dấu, chữ hoa và đối sánh mọi từ", () => {
  const products = [{ name: "BDSG CRM", purpose: "Quản lý khách hàng", group: "Điều phối" }, { name: "HỌC TẬP", purpose: "Đào tạo", group: "Tri thức" }];
  assert.equal(findProducts(products, "KHACH hang")[0].name, "BDSG CRM");
  assert.equal(findProducts(products, "dao tao tri")[0].name, "HỌC TẬP");
  assert.equal(findProducts(products, "khach dao").length, 0);
  assert.equal(findProducts(products, "").length, 2);
});

test("Liên kết kết quả chỉ chấp nhận HTTPS công khai theo chính sách chung", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,test", "file:///test", "https://a:b@example.com", "//example.com", "bad url", "http://bdsg.vn/", "https://localhost/", "https://crm.local/", "https://127.0.0.1/", "https://10.0.0.1/", "https://[::1]/", "https://2130706433/", "https://bdsg.vn:8080/"]) assert.equal(safeURL(url), null, url);
  assert.equal(safeURL("https://bdsg.vn/?q=%3Cscript%3E"), "https://bdsg.vn/?q=%3Cscript%3E");
});
