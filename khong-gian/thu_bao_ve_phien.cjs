"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(__dirname + "/bao-ve-phien.js", "utf8");
const actor = id => new Response(JSON.stringify({ authenticated: !!id, user: id ? { id } : null }));
const tick = () => new Promise(resolve => setImmediate(resolve));
function harness(fetch) {
  const events = new Map(), invalidations = [], channels = [];
  const window = { addEventListener(name, handler) { events.set(name, handler); } };
  class Channel {
    constructor() { channels.push(this); }
    addEventListener(_, handler) { this.receive = data => handler({ data }); }
  }
  vm.runInNewContext(source, { window, fetch, Headers, AbortSignal, AbortController, BroadcastChannel: Channel });
  const guard = window.BDSGSessionGuard.create({ onInvalidate: message => invalidations.push(message) });
  return { guard, events, invalidations, channels };
}
test("Ghim danh tính từ /api/me trước khi gọi API; không tin header của bên gọi", async () => {
  let resolveMe;
  const calls = [];
  const { guard } = harness((path, options) => {
    calls.push({ path, options });
    return path === "/api/me" ? new Promise(resolve => { resolveMe = resolve; }) : Promise.resolve(new Response("{}"));
  });
  const pending = guard.fetch("/api/tools", { headers: { "X-BDSG-Actor": "b" }, method: "POST" });
  assert.equal(calls.length, 1);
  resolveMe(actor("a"));
  await pending;
  assert.equal(calls[1].options.headers.get("X-BDSG-Actor"), "a");
  assert.equal(calls[1].options.credentials, "same-origin");
});
test("Không có tài khoản thì dừng trước mọi yêu cầu riêng", async () => {
  let calls = 0;
  const { guard, invalidations } = harness(async () => { calls++; return actor(null); });
  await assert.rejects(guard.ready);
  await assert.rejects(guard.fetch("/api/tools"));
  assert.equal(calls, 1);
  assert.equal(invalidations.length, 1);
});
test("Thông báo cùng danh tính không dừng; khác danh tính chỉ vô hiệu hóa, không đổi tài khoản", async () => {
  const { guard, channels, invalidations } = harness(async () => actor("a"));
  await guard.ready;
  channels[0].receive({ type: "identity-changed", actorId: "a" });
  assert.equal(guard.active, true);
  channels[0].receive({ type: "identity-changed", actorId: "b" });
  assert.equal(guard.active, false);
  assert.equal(invalidations.length, 1);
  await assert.rejects(guard.fetch("/api/tools"));
});
test("Storage dự phòng và kiểm /api/me khi focus đều phát hiện đổi tài khoản", async () => {
  const first = harness(async () => actor("a"));
  await first.guard.ready;
  first.events.get("storage")({ key: "bdsg-session-change", newValue: JSON.stringify({ type: "identity-changed", actorId: "guest" }) });
  assert.equal(first.guard.active, false);
  let id = "a";
  const second = harness(async () => actor(id));
  await second.guard.ready;
  id = "b";
  second.events.get("focus")();
  await tick();
  assert.equal(second.guard.active, false);
});
test("401 và 409 đổi danh tính dừng phiên; 409 cấu hình Google vẫn trả về cho giao diện", async () => {
  for (const [status, code, invalid] of [[401, "expired", true], [409, "identity_changed", true], [409, "google_setup", false]]) {
    const { guard } = harness(async path => path === "/api/me" ? actor("a") : new Response(JSON.stringify({ code }), { status }));
    await guard.ready;
    if (invalid) await assert.rejects(guard.fetch("/api/tools"));
    else assert.equal((await guard.fetch("/api/google/picker")).status, 409);
    assert.equal(guard.active, !invalid);
  }
});
test("Phản hồi cũ không được xuất sau khi phiên đổi, kể cả fetch không tuân theo abort", async () => {
  let finish, signal;
  const { guard, channels } = harness((path, options) => path === "/api/me" ? Promise.resolve(actor("a")) : new Promise(resolve => { finish = resolve; signal = options.signal; }));
  await guard.ready;
  const pending = guard.fetch("/api/tools");
  await tick();
  channels[0].receive({ type: "identity-changed", actorId: "b" });
  assert.equal(signal.aborted, true);
  finish(new Response('{"private":"old"}'));
  await assert.rejects(pending);
});
test("Trình soạn thảo hủy engine, xóa vùng riêng và bỏ qua callback engine sau đổi phiên", async () => {
  const nodes = new Map();
  function node() { return { disabled: true, hidden: true, textContent: "", inert: false, cleared: false,
    listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }, replaceChildren() { this.cleared = true; }, focus() {} }; }
  const document = { querySelector(selector) { if (!nodes.has(selector)) nodes.set(selector, node()); return nodes.get(selector); },
    createElement() { return {}; }, head: { append(script) { queueMicrotask(() => script.onload()); } } };
  let invalidate, destroyed = 0, engineEvents, calls = 0;
  const guard = { active: true, ready: Promise.resolve(), assertActive() { if (!this.active) throw new Error("stale"); },
    async fetch() { calls++; return { ok: true, json: async () => ({ ok: true, ket_qua: { key: "test", api_url: "/office-docs/web-apps/apps/api/documents/api.js", config: {} } }) }; } };
  const window = { BDSGOfficeGuard: { create(options) { invalidate = () => { guard.active = false; options.onInvalidate("Phiên đã đổi"); }; return guard; } }, addEventListener() {} };
  vm.runInNewContext(fs.readFileSync(__dirname + "/soan-thao.js", "utf8"), { window, document,
    location: { search: "?id=" + "a".repeat(24) }, URLSearchParams, matchMedia: () => ({ matches: false }),
    AbortSignal, queueMicrotask, setTimeout: () => 1, clearTimeout() {},
    DocsAPI: { DocEditor: function (_, config) { engineEvents = config.events; this.destroyEditor = () => destroyed++; } } });
  await tick();
  assert.ok(engineEvents);
  engineEvents.onDocumentReady();
  assert.equal(nodes.get("#save").disabled, false);
  invalidate();
  assert.equal(destroyed, 1);
  assert.equal(nodes.get("main").cleared, true);
  engineEvents.onDocumentReady();
  engineEvents.onDocumentStateChange({ data: true });
  nodes.get("#save").listeners.click();
  await tick();
  assert.equal(nodes.get("#save").disabled, true);
  assert.equal(calls, 1);
});
test("Picker đóng hộp chọn và không nhập tệp từ callback cũ sau đổi phiên", async () => {
  const nodes = new Map();
  const document = { querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, { disabled: false, hidden: true, listeners: {},
      addEventListener(name, fn) { this.listeners[name] = fn; }, replaceChildren() { this.cleared = true; } });
    return nodes.get(selector);
  }, querySelectorAll: () => [], createElement: () => ({}), head: { append(script) { queueMicrotask(() => script.onload()); } } };
  let invalidate, selected, calls = 0, disposed = false, visible = false;
  const guard = { active: true, ready: Promise.resolve(), async check() {}, assertActive() { if (!this.active) throw new Error("stale"); },
    async fetch() { calls++; return { ok: true, json: async () => ({ access_token: "test-only", api_key: "test-only", app_id: "test-only" }) }; } };
  const window = { BDSGSessionGuard: { create(options) { invalidate = () => { guard.active = false; options.onInvalidate("Phiên đã đổi"); }; return guard; } } };
  class Builder {
    addView() { return this; } setOAuthToken() { return this; } setDeveloperKey() { return this; }
    setAppId() { return this; } setOrigin() { return this; } setLocale() { return this; }
    setCallback(fn) { selected = fn; return this; }
    build() { return { setVisible(value) { visible = value; }, dispose() { disposed = true; } }; }
  }
  vm.runInNewContext(fs.readFileSync(__dirname + "/google-picker.js", "utf8"), { window, document,
    location: { search: "?project=" + "a".repeat(24), origin: "https://test.invalid" }, URLSearchParams,
    AbortSignal, queueMicrotask, crypto: { randomUUID: () => "test-id" },
    gapi: { load(_, options) { options.callback(); } },
    google: { picker: { PickerBuilder: Builder, DocsView: function () {}, ViewId: { DOCS: "docs" }, Action: { CANCEL: "cancel", PICKED: "picked" } } } });
  await tick();
  await nodes.get("#pick").listeners.click();
  assert.equal(visible, true);
  invalidate();
  assert.equal(disposed, true);
  assert.equal(visible, false);
  assert.equal(nodes.get("#selection").cleared, true);
  await selected({ action: "picked", docs: [{ id: "test-file" }] });
  assert.equal(calls, 1);
  assert.equal(nodes.get("#pick").disabled, true);
});
