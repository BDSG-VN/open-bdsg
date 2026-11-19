// Mô phỏng phần DOM nhận handoff; không gọi Google hoặc bộ soạn thảo thật.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function harness(embedded) {
  const navigations = [], links = [], notices = [];
  const notice = {
    set textContent(value) { notices.push(value); links.length = 0; },
    classList: { toggle() {} }, setAttribute() {},
    append(...items) { links.push(...items.filter(item => typeof item === "object")); },
  };
  const window = { addEventListener() {}, prompt: () => "tai-lieu.docx" };
  window.self = window;
  window.top = embedded ? {} : window;
  let googleURL = "https://accounts.google.com/o/oauth2/v2/auth?state=synthetic";
  const context = {
    window, state: { user: { id: "synthetic-user" } },
    location: { hash: "#office", assign: url => navigations.push(url) },
    document: {
      addEventListener() {},
      querySelector: selector => selector === "#office-notice" ? notice : null,
      createElement: tag => ({ tagName: tag }), createTextNode: text => text,
    },
    URL, AbortController, setTimeout, clearTimeout,
    crypto: { randomUUID: () => "synthetic-operation" },
    api: async route => route === "/api/google/start"
      ? { url: googleURL } : { ok: true, ket_qua: { id: "synthetic-file" } },
  };
  const source = fs.readFileSync(path.join(__dirname, "van-phong.js"), "utf8");
  // Giữ mã luồng thật; thay tải danh sách vì bài này chỉ kiểm chuyển cửa sổ.
  vm.runInNewContext(source.replace("window.BDSGOffice = { open, reset, leave };", `
    selected = "synthetic-project"; access = { permissions: { can_write: true } };
    load = async () => {};
    window.BDSGOffice = { newOffice, googleAction, separateTab };
  `), context);
  return { api: window.BDSGOffice, links, navigations, notices,
    googleURL: value => { googleURL = value; } };
}

async function main() {
  const frame = harness(true);
  await frame.api.newOffice("docx");
  assert.equal(frame.navigations.length, 0);
  assert.equal(frame.links[0].href, "/soan-thao.html?id=synthetic-file");
  assert.equal(frame.links[0].target, "_blank");
  assert.equal(frame.links[0].rel, "noopener noreferrer");
  await frame.api.googleAction("connect");
  assert.match(frame.links[0].href, /^https:\/\/accounts\.google\.com\//);
  assert.equal(frame.links[0].target, "_blank");
  assert.equal(frame.links[0].rel, "noopener noreferrer");
  for (const url of ["https://evil.example/auth", "https://accounts.google.com/other",
    "https://user@accounts.google.com/o/oauth2/v2/auth",
    "https://accounts.google.com/o/oauth2/v2/auth#bad"]) {
    const invalid = harness(true);
    invalid.googleURL(url);
    await invalid.api.googleAction("connect");
    assert.equal(invalid.links.length, 0);
    assert.equal(invalid.navigations.length, 0);
    assert.ok(invalid.notices.some(text => text.includes("Không mở được")));
  }
  const standalone = harness(false);
  await standalone.api.newOffice("docx");
  await standalone.api.googleAction("connect");
  assert.equal(standalone.navigations.length, 2);
  assert.equal(standalone.links.length, 0);
  assert.equal(standalone.navigations[0], "/soan-thao.html?id=synthetic-file");
  console.log("PASS: embedded Office uses explicit isolated tabs; standalone navigation and Google URL checks remain valid");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
