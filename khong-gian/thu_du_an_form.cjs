const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

for (const identifier of ['', 'project-existing']) {
  test(`Lưu dự án ${identifier ? 'đã có' : 'mới'} khi input name=id che thuộc tính form.id`, async () => {
    const handlers = {}, writes = [];
    const button = { disabled: false };
    let prevented = false, closed = false;
    const form = {
      // Chromium thực trả INPUT ở form.id với control name=id; id attribute vẫn đúng.
      id: { tagName: 'INPUT', value: identifier },
      getAttribute: name => name === 'id' ? 'project-edit-form' : null,
      querySelector: () => button,
      reset() {},
    };
    const elements = {
      '#project-form-error': { textContent: '' },
      '#project-dialog': { close() { closed = true; } },
    };
    const main = { innerHTML: '' };
    const submitHandlers = [];
    const context = {
      window: {}, main, TextEncoder, location: { hash: '#projects' },
      state: { user: { id: 'actor-test', role: 'operator' } },
      document: { addEventListener: (name, handler) => {
        handlers[name] = handler;
        if (name === 'submit') submitHandlers.push(handler);
      }, querySelector: selector => elements[selector] },
      $: selector => elements[selector], esc: String, icon: () => '', date: () => '', toast() {},
      FormData: class {
        constructor(received) { assert.equal(received, form); }
        *[Symbol.iterator]() { yield* [['id', identifier], ['name', 'Dự án tổng hợp'], ['instructions', ''], ['context', '']]; }
      },
      tool: async (name, args) => {
        if (name === 'du_an.danh_sach') return { projects: [] };
        writes.push({ name, args: JSON.parse(JSON.stringify(args)) });
        return { id: identifier || 'new-project' };
      },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'du-an.js'), 'utf8'), context);
    // Các trình xử lý toàn trang cùng nhận submit của dự án trong workspace.
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'studio.js'), 'utf8'), context);
    for (const handler of submitHandlers)
      await handler({ target: form, preventDefault() { prevented = true; } });
    assert.equal(prevented, true, 'Phải chặn submit mặc định để tên dự án không đi vào URL/tải lại trang');
    assert.deepEqual(writes, [{ name: identifier ? 'du_an.cap_nhat' : 'du_an.tao',
      args: { ...(identifier ? { id: identifier } : {}), name: 'Dự án tổng hợp', instructions: '', context: '' } }]);
    assert.equal(closed, true);
    assert.equal(button.disabled, false);
  });
}
