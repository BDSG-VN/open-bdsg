// Chạy mã giao diện thật trong DOM tối thiểu để giữ từ khóa qua lần tải bất đồng bộ.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
async function main() {
  let finish;
  const input = { value: "" },
    grid = { innerHTML: "" };
  const context = {
    window: {},
    location: { hash: "#modules" },
    state: { user: null, products: [] },
    main: { innerHTML: "", querySelector: () => ({ insertAdjacentHTML() {} }) },
    document: { addEventListener() {} },
    setInterval() {},
    $: (selector) =>
      selector === "#bdsg-module-search"
        ? input
        : selector === "#bdsg-module-grid"
          ? grid
          : null,
    esc: (value) => String(value ?? ""),
    icon: () => "",
    clean: (value) => String(value).toLowerCase(),
    api: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "cong-viec.js"), "utf8"),
    context,
  );
  const loading = context.window.BDSGTasks.modules();
  input.value = "crm";
  finish({
    modules: [
      {
        id: "crm",
        name: "BDSG CRM",
        group: "Vận hành",
        purpose: "Khách hàng",
        url: "https://crm.bdsg.vn/",
      },
      {
        id: "erp",
        name: "BDSG ERP",
        group: "Vận hành",
        purpose: "Nguồn lực",
        url: "https://bdsgerp.bdsg.vn/",
      },
    ],
  });
  await loading;
  assert.ok(grid.innerHTML.includes("BDSG CRM"));
  assert.ok(
    !grid.innerHTML.includes("BDSG ERP"),
    "Từ khóa CRM phải được giữ sau khi danh mục tải xong",
  );
  console.log("PASS: module search survives asynchronous catalogue loading");
}
main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
