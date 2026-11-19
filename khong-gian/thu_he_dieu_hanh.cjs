'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { create, normalizeAddress, createReadBroker } = require('./he-dieu-hanh-state.js');

const apps = [
  { id: 'work', title: 'Công việc', kind: 'internal', route: '#work' },
  { id: 'office', title: 'Văn phòng', kind: 'internal', route: '#office' },
  { id: 'browser', title: 'Trình duyệt', kind: 'browser' },
];
function state(options = {}) {
  let id = 0;
  return create({ apps, idFactory: () => `s-${++id}`, ...options });
}

test('Mở lại ứng dụng dùng đúng phiên, phiên độc lập cần yêu cầu rõ', () => {
  const os = state();
  const first = os.open('work');
  os.open('office');
  assert.equal(os.open('work').id, first.id);
  const another = os.open('work', { newInstance: true });
  assert.notEqual(another.id, first.id);
  assert.equal(os.snapshot().sessions.length, 3);
  assert.deepEqual(os.snapshot().mru, [another.id, first.id, 's-2']);
});

test('Giới hạn phiên không đóng mất công việc và vẫn mở lại phiên có sẵn', () => {
  const os = state();
  for (let i = 0; i < 8; i++) assert.ok(os.open('work', { newInstance: true }));
  const before = os.snapshot();
  assert.equal(os.open('office'), null);
  assert.deepEqual(os.snapshot(), before);
  assert.ok(os.open('work'));
  assert.equal(os.snapshot().sessions.length, 8);
});

test('Thu nhỏ, kích hoạt và đóng dùng MRU, không hiện lại phiên đã thu nhỏ', () => {
  const os = state();
  const work = os.open('work');
  const office = os.open('office');
  const browser = os.open('browser');
  os.minimize(office.id);
  assert.equal(os.close(browser.id).activeSessionId, work.id);
  assert.equal(os.minimize(work.id).activeSessionId, null);
  assert.equal(os.snapshot().sessions.filter(item => item.status === 'active').length, 0);
  assert.equal(os.activate(office.id).activeSessionId, office.id);
  os.close(office.id);
  assert.equal(os.snapshot().activeSessionId, null);
});

test('Danh tính đổi xoá toàn bộ phiên, không khôi phục trạng thái người trước', () => {
  const os = state({ identityId: 'a' });
  os.open('work');
  const saved = os.snapshot();
  os.resetIdentity('b');
  assert.equal(os.snapshot().identityId, 'b');
  assert.deepEqual(os.snapshot().sessions, []);
  assert.deepEqual(os.restore(saved).sessions, []);
});

test('Khôi phục chỉ giữ metadata đã biết, sửa phiên trùng và trạng thái active sai', () => {
  const os = state();
  const saved = {
    version: 1, identityId: 'guest', activeSessionId: 'one', token: 'khong-luu',
    sessions: [
      { id: 'one', appId: 'work', status: 'active', url: 'https://example.com', data: 'khong-luu' },
      { id: 'one', appId: 'office', status: 'active' },
      { id: 'two', appId: 'office', status: 'active' },
      { id: 'three', appId: 'unknown', status: 'active' },
      { id: 'four', appId: 'work', status: 'closed' },
    ], mru: ['two', 'two', 'unknown'],
  };
  assert.deepEqual(os.restore(saved), {
    version: 1, identityId: 'guest', activeSessionId: 'one',
    sessions: [{ id: 'one', appId: 'work', status: 'active' }, { id: 'two', appId: 'office', status: 'background' }],
    mru: ['one', 'two'],
  });
  const copy = os.snapshot();
  copy.sessions[0].appId = 'browser';
  copy.mru.length = 0;
  assert.equal(os.snapshot().sessions[0].appId, 'work');
  assert.equal(os.snapshot().mru.length, 2);
});

test('Khôi phục không tự kích hoạt khi không có phiên active hợp lệ và giới hạn dung lượng', () => {
  const os = state({ maxSessions: 2 });
  const sessions = Array.from({ length: 12 }, (_, i) => ({ id: `x-${i}`, appId: 'work', status: 'background' }));
  const restored = os.restore({ version: 1, identityId: 'guest', activeSessionId: 'missing', sessions });
  assert.equal(restored.sessions.length, 2);
  assert.equal(restored.activeSessionId, null);
  for (const malformed of [null, '', [], {}, { version: 1, identityId: 'guest', sessions: {} }]) assert.deepEqual(os.restore(malformed).sessions, []);
});

test('Đầu vào sai không làm thay đổi phiên; ID đã dùng không được tái sử dụng', () => {
  const os = state({ idFactory: () => 'fixed' });
  const opened = os.open('work');
  assert.equal(os.open('office'), null);
  for (const action of ['activate', 'close', 'minimize']) assert.equal(os[action]('missing'), null);
  assert.equal(os.open('unknown'), null);
  assert.equal(os.open('work', null), null);
  os.close(opened.id);
  assert.equal(os.open('work'), null);
  assert.throws(() => state({ maxSessions: 9 }), TypeError);
  assert.throws(() => create({ apps: [{ id: 'bad', kind: 'internal', route: 'https://example.com' }] }), TypeError);
});

test('Trình duyệt nhận HTTPS công khai hoặc từ khoá tìm kiếm', () => {
  assert.deepEqual(normalizeAddress(' example.com/duong-dan?q=abc '), { kind: 'url', url: 'https://example.com/duong-dan?q=abc' });
  assert.deepEqual(normalizeAddress('HTTPS://BDSG.VN/'), { kind: 'url', url: 'https://bdsg.vn/' });
  assert.deepEqual(normalizeAddress('bất động sản Thanh Hoá'), { kind: 'search', query: 'bất động sản Thanh Hoá' });
});

test('Trình duyệt chặn tài khoản, giao thức và địa chỉ mạng riêng/ký pháp IP', () => {
  const blocked = [null, {}, '', 'javascript:alert(1)', 'data:text/html,x', 'file:///etc/hosts',
    'http://example.com', 'https://u:p@example.com', 'u@example.com', 'https://localhost', 'localhost',
    'https://router.lan', 'router.internal', 'https://host.home.arpa', 'https://host.test',
    'https://127.0.0.1', 'https://10.1.2.3', 'https://169.254.169.254', 'https://192.168.1.1',
    'https://8.8.8.8', 'https://[::1]', 'https://[fc00::1]', 'https://2130706433', '2130706433',
    'https://0x7f000001', 'https://0177.0.0.1', 'https://%31%32%37.0.0.1',
    'https://example.com:8443', 'https://exa\\mple.com', 'https://example.com\n/path'];
  for (const value of blocked) assert.equal(normalizeAddress(value), null, String(value));
});

function barrier() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
const turn = () => new Promise(resolve => setImmediate(resolve));

test('Hàng đợi đọc chỉ chạy đồng thời theo giới hạn và tiếp tục sau lỗi', async () => {
  const broker = createReadBroker({ getIdentity: () => 'a' });
  const gates = Array.from({ length: 4 }, barrier);
  const started = [];
  let active = 0;
  let peak = 0;
  const results = gates.map((gate, index) => broker.read(`key-${index}`, 'a', async () => {
    started.push(index);
    peak = Math.max(peak, ++active);
    await gate.promise;
    active--;
    if (index === 0) throw new Error('Lỗi đọc mô phỏng');
    return { index };
  }));
  const failed = assert.rejects(results[0], /Lỗi đọc/);
  await turn();
  assert.deepEqual(started, [0, 1]);
  gates[0].resolve();
  await failed;
  await turn();
  assert.deepEqual(started, [0, 1, 2]);
  gates[1].resolve();
  await results[1];
  await turn();
  assert.deepEqual(started, [0, 1, 2, 3]);
  gates[2].resolve();
  gates[3].resolve();
  await Promise.all(results.slice(1));
  assert.equal(peak, 2);
});

test('Các cửa sổ gộp request đang bay, nhận bản JSON riêng và không cache sau hoàn tất', async () => {
  const broker = createReadBroker({ getIdentity: () => 'a' });
  const gate = barrier();
  let calls = 0;
  const load = async () => { calls++; await gate.promise; return { nested: { value: 1 } }; };
  const one = broker.read('projects', 'a', load);
  const two = broker.read('projects', 'a', load);
  await turn();
  assert.equal(calls, 1);
  gate.resolve();
  const [first, second] = await Promise.all([one, two]);
  first.nested.value = 9;
  assert.equal(second.nested.value, 1);
  const third = await broker.read('projects', 'a', load);
  assert.equal(calls, 2);
  assert.deepEqual(third, { nested: { value: 1 } });
});

test('Danh tính sai bị chặn trước loader, kể cả khi danh tính đổi lúc đang đợi', async () => {
  let actor = 'a';
  let calls = 0;
  const broker = createReadBroker({ getIdentity: () => actor, maxConcurrent: 1 });
  await assert.rejects(broker.read('private', 'b', () => { calls++; }), /Phiên tài khoản/);
  const gate = barrier();
  const first = broker.read('first', 'a', () => gate.promise);
  const queued = broker.read('private', 'a', () => { calls++; return {}; });
  const rejected = [first, queued].map(promise => assert.rejects(promise, /Phiên tài khoản/));
  await turn();
  actor = 'b';
  gate.resolve({ secret: 'a-only' });
  await Promise.all(rejected);
  assert.equal(calls, 0);
});

test('Reset huỷ queued và kết quả đang bay, giữ giới hạn cho tới loader cũ kết thúc', async () => {
  const broker = createReadBroker({ getIdentity: () => 'a', maxConcurrent: 1 });
  const gate = barrier();
  let queuedCalls = 0;
  let freshCalls = 0;
  const inflight = broker.read('key', 'a', () => gate.promise);
  const queued = broker.read('queued', 'a', () => { queuedCalls++; return {}; });
  const rejected = [inflight, queued].map(promise => assert.rejects(promise, /Phiên tài khoản/));
  await turn();
  broker.reset();
  await Promise.all(rejected);
  const fresh = broker.read('key', 'a', () => { freshCalls++; return { fresh: true }; });
  await turn();
  assert.equal(freshCalls, 0);
  gate.resolve({ stale: true });
  assert.deepEqual(await fresh, { fresh: true });
  assert.equal(freshCalls, 1);
  assert.equal(queuedCalls, 0);
});

test('Hàng đợi chặn đầu vào sai và vượt quá 64 request chờ', async () => {
  const broker = createReadBroker({ getIdentity: () => 'a', maxConcurrent: 1 });
  const gate = barrier();
  const first = broker.read('first', 'a', () => gate.promise);
  const waiting = Array.from({ length: 64 }, (_, index) => broker.read(`wait-${index}`, 'a', () => ({})));
  await assert.rejects(broker.read('overflow', 'a', () => ({})), /đã đầy/);
  for (const key of ['', ' ', null, {}, 'x'.repeat(257), 'x\n']) await assert.rejects(broker.read(key, 'a', () => ({})), TypeError);
  await assert.rejects(broker.read('key', 'a', null), TypeError);
  const rejected = [first, ...waiting].map(promise => assert.rejects(promise, /Phiên tài khoản/));
  broker.reset();
  gate.resolve({});
  await Promise.all(rejected);
  assert.throws(() => createReadBroker({ getIdentity: () => 'a', maxConcurrent: 0 }), TypeError);
});
