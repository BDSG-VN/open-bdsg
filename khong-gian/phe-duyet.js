"use strict";
(() => {
  let version = 0, operation = 0, busy = false;
  let tasks = [], modules = [], actions = [], selectedTask = "", selectedPlatform = "";
  const unitMode = () => window.BDSGUnit?.snapshot().mode === "units";
  const current = () => unitMode() && location.hash === "#studio" && !!state.user;
  const capture = () => window.BDSGUnit.capture();
  const live = (token) => current() && window.BDSGUnit.current(token);
  const admin = () => window.BDSGUnit.canAdmin();
  const labels = { awaiting: "Chờ duyệt", executing: "Đang thực hiện", completed: "Đã hoàn thành",
    rejected: "Đã từ chối", expired: "Hết hạn", cancelled: "Đã hủy", unknown: "Cần đối soát",
    "reconciled-applied": "Đã đối soát: đã thực hiện", "reconciled-not-applied": "Đã đối soát: chưa thực hiện" };
  const platformName = (id) => modules.find(item => item.id === id)?.name || id;
  function feedback(message) {
    const target = document.querySelector("#unit-action-feedback");
    if (target) target.textContent = message;
  }
  function availableTasks() {
    return tasks.filter(task => task.owner === state.user.id && ["completed", "running"].includes(task.status));
  }
  function availableModules() {
    const task = tasks.find(item => item.id === selectedTask);
    return modules.filter(item => task?.module_ids.includes(item.id) && item.mcp?.proposal_tools?.length);
  }
  function choices() {
    const available = availableModules();
    if (!available.some(item => item.id === selectedPlatform)) selectedPlatform = available[0]?.id || "";
    const platform = document.querySelector("#unit-action-platform");
    const toolSelect = document.querySelector("#unit-action-tool");
    if (!platform || !toolSelect) return;
    platform.innerHTML = available.map(item => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join("");
    platform.value = selectedPlatform;
    toolSelect.innerHTML = (available.find(item => item.id === selectedPlatform)?.mcp.proposal_tools || [])
      .map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
    document.querySelector("#unit-action-create [type=submit]").disabled = !toolSelect.options.length || busy;
    document.querySelector("#unit-action-tools-note").textContent = available.length
      ? "Chỉ hiển thị công cụ ghi đã được xác minh của mô-đun trong tác vụ này."
      : "Tác vụ này chưa có công cụ ghi được cấp. Chọn tác vụ khác hoặc nhờ quản trị cấu hình Kết nối.";
  }
  function proposalForm() {
    const available = availableTasks();
    if (!available.some(item => item.id === selectedTask)) selectedTask = available[0]?.id || "";
    if (!available.length) return `<section class="studio-empty"><p>Chưa có tác vụ của bạn để lập đề xuất. Giao việc với mô-đun cần dùng trước.</p><a class="button" href="#work">Mở giao việc</a></section>`;
    return `<form id="unit-action-create" class="studio-form"><h2>Lập đề xuất ghi</h2>
      <p>Lưu dự thảo chưa chạy công cụ. Nội dung sẽ được chia sẻ với quản trị doanh nghiệp có quyền dự án để duyệt.</p>
      <fieldset><label>Tác vụ<select id="unit-action-task" name="task_id" required>${available.map(item => `<option value="${esc(item.id)}" ${item.id === selectedTask ? "selected" : ""}>${esc(item.title)}</option>`).join("")}</select></label>
      <label>Nền tảng<select id="unit-action-platform" name="platform_id" required></select></label>
      <label>Công cụ ghi<select id="unit-action-tool" name="tool" required></select></label>
      <p id="unit-action-tools-note" class="studio-note"></p>
      <label>Tham số nghiệp vụ (JSON)<textarea name="arguments" rows="6" required maxlength="14000" spellcheck="false" placeholder='{"record_id":"..."}'>{}</textarea></label>
      <p class="studio-note">Không nhập mật khẩu, khóa API hoặc mã xác minh. Mỗi đề xuất giữ nguyên nội dung và có hiệu lực 15 phút.</p>
      <button class="button primary" type="submit">Lưu đề xuất để duyệt</button></fieldset></form>`;
  }
  function actionCard(action) {
    const payload = action.payload, call = payload.arguments;
    const awaiting = action.status === "awaiting", unexpired = action.expires * 1000 > Date.now();
    const status = awaiting && !unexpired ? "Hết hạn" : labels[action.status] || "Cần kiểm tra trạng thái";
    const reconciliation = action.result?.reconciliation;
    return `<article class="studio-card unit-action-card" data-unit-action="${esc(action.id)}">
      <div class="unit-action-heading"><h3>${esc(platformName(call.platform_id))}</h3><span class="mini-tag">${esc(status)}</span></div>
      <p><strong>Công cụ:</strong> <code>${esc(call.tool)}</code></p>
      <p>Người đề xuất: ${esc(action.owner)} · Lượt ${esc(payload.run)} · Hạn ${esc(date(action.expires))}</p>
      <h4>Nội dung được đề xuất</h4><pre>${esc(JSON.stringify(call.arguments, null, 2))}</pre>
      <details><summary>Mã xác nhận nội dung</summary><code class="unit-action-digest">${esc(action.digest)}</code></details>
      ${action.status === "unknown" ? `<p class="unit-action-warning">Chưa rõ yêu cầu đã tác động hay chưa. Công cụ này bị chặn gửi tiếp trong doanh nghiệp cho đến khi quản trị đối soát nền tảng gốc.</p>` : ""}
      ${action.status === "executing" ? `<p role="status">Đang thực hiện. Cập nhật danh sách để xem kết quả; không gửi lại.</p>` : ""}
      ${awaiting && admin() ? `<div class="studio-actions">${unexpired ? `<button type="button" class="button primary" data-unit-approve="${esc(action.id)}">Duyệt và thực hiện</button>` : ""}<button type="button" class="button" data-unit-reject="${esc(action.id)}">Từ chối đề xuất</button></div>` : ""}
      ${awaiting && !admin() ? `<p class="studio-note">Quản trị doanh nghiệp có quyền dự án cần kiểm tra và duyệt nội dung này.</p>` : ""}
      ${action.status === "unknown" && admin() ? `<form class="unit-action-reconcile" data-unit-reconcile="${esc(action.id)}"><fieldset><legend>Đối soát trên nền tảng gốc</legend>
        <p>Hệ thống chưa tự xác minh kết quả. Bạn cần kiểm tra nền tảng gốc trước khi xác nhận.</p>
        <label>Kết quả đã kiểm tra<select name="outcome" required><option value="">Chọn kết quả đối soát</option><option value="applied">Đã thực hiện trên nền tảng gốc</option><option value="not-applied">Chưa thực hiện trên nền tảng gốc</option></select></label>
        <label>Ghi chú đối soát<textarea name="note" required minlength="10" maxlength="1000" rows="3"></textarea></label>
        <label class="unit-action-confirm"><input type="checkbox" name="confirmed" required><span>Tôi đã đối soát nội dung này trên nền tảng gốc. Xác nhận chỉ ghi kết quả, không tự gửi lại công cụ.</span></label>
        <button class="button" type="submit">Xác nhận kết quả đối soát</button></fieldset></form>` : ""}
      ${reconciliation ? `<p><strong>Ghi chú đối soát:</strong> ${esc(reconciliation.note)}</p><p class="studio-note">Xác nhận do ${esc(reconciliation.by)} nhập; chưa phải kết quả tự kiểm của hệ thống.</p>` : ""}
      ${action.status === "completed" ? `<details><summary>Kết quả công cụ</summary><pre>${esc(JSON.stringify(action.result, null, 2))}</pre></details>` : ""}
    </article>`;
  }
  function draw() {
    if (!current()) return;
    main.innerHTML = `<section class="bdsg-work-page studio-page studio-unit"><div class="bdsg-work-page-heading"><div><h1>Phê duyệt công việc.</h1><p>Đề xuất và quyền duyệt thuộc doanh nghiệp đang chọn. Mở website không tự cấp quyền ghi dữ liệu.</p></div><button class="button" type="button" data-unit-actions-refresh>Cập nhật danh sách</button></div>
      <p class="studio-note">${admin() ? "Bạn là quản trị doanh nghiệp. Chỉ các đề xuất trong phạm vi dự án được cấp mới hiện ở đây." : "Bạn là thành viên doanh nghiệp. Bạn có thể lập đề xuất cho tác vụ của mình; quản trị có quyền dự án duyệt riêng."}</p>
      <p id="unit-action-feedback" role="status" aria-live="polite"></p>${proposalForm()}
      <section aria-labelledby="unit-action-list-title"><h2 id="unit-action-list-title">Đề xuất trong phạm vi của bạn</h2>
      <div class="studio-list">${actions.map(actionCard).join("") || `<div class="studio-empty"><p>Chưa có đề xuất trong phạm vi quyền của bạn.</p></div>`}</div></section></section>`;
    choices();
  }
  async function open() {
    if (!current()) return;
    const ticket = ++version, token = capture();
    main.innerHTML = `<section class="bdsg-work-page studio-page studio-unit"><h1>Phê duyệt công việc.</h1><p role="status">Đang tải tác vụ, công cụ và đề xuất của doanh nghiệp…</p></section>`;
    try {
      const [taskList, moduleList, actionList] = await Promise.all([
        tool("cong_viec.danh_sach"), tool("mo_dun.danh_sach"), tool("hanh_dong.danh_sach")]);
      if (ticket !== version || !live(token)) return;
      tasks = taskList.tasks || []; modules = moduleList.modules || []; actions = actionList.actions || [];
      draw();
    } catch (_) {
      if (ticket !== version || !live(token)) return;
      main.innerHTML = `<section class="bdsg-work-page studio-page studio-unit"><h1>Chưa tải được đề xuất.</h1><p role="alert">Kiểm tra kết nối và quyền doanh nghiệp rồi tải lại. Không có yêu cầu ghi nào được gửi từ thao tác tải danh sách.</p><button class="button primary" type="button" data-unit-actions-refresh>Thử tải lại</button></section>`;
    }
  }
  async function mutate(name, arguments_, success) {
    if (busy || !current()) return;
    busy = true;
    const ticket = ++operation, token = capture();
    document.querySelectorAll(".studio-unit fieldset,.studio-unit button").forEach(element => { element.disabled = true; });
    feedback("Đang xử lý yêu cầu…");
    try {
      await tool(name, arguments_);
      if (ticket !== operation || !live(token)) return;
      await open();
      if (ticket === operation && live(token)) feedback(success);
    } catch (_) {
      if (ticket !== operation || !live(token)) return;
      await open();
      if (ticket === operation && live(token)) feedback("Chưa nhận được xác nhận. Kiểm tra trạng thái trong danh sách trước khi thao tác tiếp; hệ thống không tự gửi lại yêu cầu ghi.");
    } finally {
      if (ticket === operation && live(token)) {
        busy = false;
        document.querySelectorAll(".studio-unit fieldset,.studio-unit button").forEach(element => { element.disabled = false; });
        choices();
      }
    }
  }
  document.addEventListener("change", event => {
    if (!current() || busy) return;
    if (event.target.id === "unit-action-task") { selectedTask = event.target.value; selectedPlatform = ""; choices(); }
    if (event.target.id === "unit-action-platform") { selectedPlatform = event.target.value; choices(); }
  });
  document.addEventListener("click", event => {
    if (!current() || busy) return;
    if (event.target.closest("[data-unit-actions-refresh]")) return open();
    const button = event.target.closest("[data-unit-approve],[data-unit-reject]");
    if (!button || !admin()) return;
    const id = button.dataset.unitApprove || button.dataset.unitReject;
    const action = actions.find(item => item.id === id);
    if (!action) return;
    const approve = !!button.dataset.unitApprove;
    if (approve && !confirm("Thực hiện đúng nội dung đề xuất đang hiển thị trên nền tảng gốc? Đây là thao tác ghi dữ liệu.")) return;
    mutate("hanh_dong.duyet", { id, digest: action.digest, approve }, approve
      ? "Đã nhận kết quả duyệt. Kiểm tra trạng thái đề xuất bên dưới." : "Đã từ chối đề xuất; không chạy công cụ.");
  });
  document.addEventListener("submit", event => {
    if (!current()) return;
    const form = event.target;
    if (form.id !== "unit-action-create" && !form.dataset.unitReconcile) return;
    event.preventDefault();
    if (busy) return;
    const values = Object.fromEntries(new FormData(form));
    if (form.id === "unit-action-create") {
      let arguments_;
      try { arguments_ = JSON.parse(values.arguments); } catch (_) { feedback("Tham số chưa đúng JSON. Kiểm tra dấu ngoặc và dấu phẩy rồi lưu lại."); return; }
      if (!arguments_ || Array.isArray(arguments_) || typeof arguments_ !== "object") { feedback("Tham số phải là một đối tượng JSON, ví dụ {}."); return; }
      mutate("hanh_dong.de_xuat", { task_id: values.task_id, tool: "ket_noi.ghi",
        arguments: { platform_id: values.platform_id, tool: values.tool, arguments: arguments_ } }, "Đã lưu dự thảo. Chưa thực hiện công cụ ghi.");
    } else if (admin()) {
      const action = actions.find(item => item.id === form.dataset.unitReconcile);
      if (!action || values.confirmed !== "on") return;
      mutate("hanh_dong.doi_soat", { id: action.id, digest: action.digest, outcome: values.outcome, note: values.note },
        "Đã lưu xác nhận đối soát của bạn. Không tự gửi lại công cụ; muốn thực hiện tiếp cần đề xuất và duyệt riêng.");
    }
  });
  function reset() {
    version++; operation++; busy = false;
    tasks = []; modules = []; actions = []; selectedTask = ""; selectedPlatform = "";
  }
  window.addEventListener("hashchange", () => { if (!current()) reset(); });
  window.BDSGUnitActions = Object.freeze({ open, reset });
})();
