// Kiểm giao diện công khai của Xưởng khi kho dự án chỉ còn các bản lưu trữ.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function render(projects) {
  const content = {innerHTML: ''};
  const context = {
    window: {}, location: {hash: '#studio'}, state: {user: {id:'chu-quan',role:'quan-tri'}},
    main: {innerHTML: ''}, document: {addEventListener() {}},
    $: selector => selector === '#studio-content' ? content : null,
    esc: value => String(value ?? ''), icon: () => '', date: () => '',
    tool: async name => name === 'du_an.danh_sach' ? {projects} : name === 'tai_lieu.danh_sach' ? {documents: []} : {tasks: []},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'studio.js'),'utf8'), context);
  await context.window.BDSGStudio.open();
  return content.innerHTML;
}

(async () => {
  const archived = await render([{id:'old-project',name:'Dự án đã lưu trữ',archived:true}]);
  assert.ok(!archived.includes('id="studio-upload"'),'Chỉ có dự án lưu trữ thì không được hiện biểu mẫu tải vào bộ chọn trống');
  assert.ok(archived.includes('#projects'),'Phải có đường mở dự án để tạo hoặc khôi phục');
  const active = await render([{id:'active-project',name:'Dự án đang hoạt động',archived:false}]);
  assert.ok(active.includes('id="studio-upload"'),'Dự án đang hoạt động vẫn tải tài liệu được');
  console.log('PASS: archived-only projects do not expose an unusable upload form');
})().catch(error => {console.error(error.message);process.exitCode=1;});
