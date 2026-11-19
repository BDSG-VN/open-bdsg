"use strict";
(() => {
  let host, row, creating = false, feedback = "";
  const runtime = () => window.BDSGUnit;
  function mount(target) {
    host = target;
    if (!row) {
      row = document.createElement("section");
      row.className = "os-unit-row";
      row.setAttribute("aria-label", "Đơn vị làm việc");
      row.addEventListener("change", async event => {
        if (event.target.id !== "os-unit-select") return;
        const id = event.target.value;
        if (!id) return;
        try { await runtime().switchTo(id); }
        catch (_) { feedback = "Chưa chuyển được đơn vị. Hãy thử lại."; }
        render();
      });
      row.addEventListener("click", async event => {
        if (!event.target.closest("[data-unit-retry]")) return;
        feedback = "";
        try { await runtime().refresh(); }
        catch (_) { feedback = "Chưa đọc được đơn vị. Kiểm tra kết nối rồi thử lại."; }
        render();
      });
      row.addEventListener("submit", createUnit);
    }
    if (!row.isConnected) host.querySelector(".os-status").after(row);
    render();
  }
  function render() {
    if (!host || !runtime()) return;
    const value = runtime().snapshot();
    row.hidden = value.mode !== "units";
    host.classList.toggle("os-unit-mode", !row.hidden);
    if (row.hidden) return;
    const pending = ["loading", "switching"].includes(value.status);
    const failed = !!value.error;
    const selected = value.selected;
    const units = Array.isArray(value.units) ? value.units : [];
    const active = document.activeElement;
    // Khi sửa biểu mẫu, sự kiện cập nhật danh sách không được xóa nội dung chưa gửi.
    const oldForm = row.querySelector("#os-unit-create");
    const draft = oldForm ? {name:oldForm.elements.name.value, admin:oldForm.elements.admin.value, open:oldForm.closest("details").open} : null;
    row.innerHTML = `<div class="os-unit-current"><label for="os-unit-select">Đơn vị làm việc</label><select id="os-unit-select" ${pending || !units.length ? "disabled" : ""} aria-describedby="os-unit-status${selected ? " os-unit-selected-name" : ""}"><option value="" ${!selected ? "selected" : ""}>${pending ? "Đang đọc đơn vị…" : "Chọn đơn vị"}</option>${units.map(unit => `<option value="${esc(unit.id)}" ${unit.id === selected?.id ? "selected" : ""}>${esc(unit.name)}</option>`).join("")}</select><p id="os-unit-status" role="${failed ? "alert" : "status"}">${esc(feedback || (pending ? "Đang xác minh quyền đơn vị…" : failed ? "Chưa đọc được đơn vị. Hãy thử lại." : selected ? (selected.role === "admin" ? "Quản trị đơn vị" : "Thành viên đơn vị") : value.actorId === "guest" ? "Đăng nhập để chọn đơn vị." : value.systemAdmin ? "Chưa có đơn vị được chọn. Chọn đơn vị hoặc tạo đơn vị mới." : units.length ? "Chọn đơn vị để bắt đầu làm việc." : "Bạn chưa có đơn vị. Hãy nhờ quản trị đơn vị cấp tư cách thành viên."))}</p>${selected ? `<p id="os-unit-selected-name" class="os-unit-name">${esc(selected.name)}</p>` : ""}${failed ? '<button type="button" class="os-unit-retry" data-unit-retry>Thử lại</button>' : ""}</div>${value.systemAdmin ? `<details class="os-unit-admin"><summary>Tạo đơn vị</summary><form id="os-unit-create"><h2>Tạo đơn vị mới</h2><label for="os-unit-name">Tên đơn vị</label><input id="os-unit-name" name="name" required minlength="3" maxlength="100" autocomplete="off"><label for="os-unit-admin-id">Mã danh tính quản trị đơn vị</label><input id="os-unit-admin-id" name="admin" value="${esc(value.actorId || "")}" required autocomplete="off" aria-describedby="os-unit-admin-help"><p id="os-unit-admin-help">Dùng mã danh tính đã tồn tại. Mã của bạn: ${esc(value.actorId || "")}. Người tạo chỉ trở thành thành viên nếu được chọn làm quản trị.</p><button type="submit" class="os-primary" ${creating ? "disabled" : ""}>${creating ? "Đang tạo…" : "Tạo đơn vị"}</button><p role="status" id="os-unit-create-status"></p></form></details>` : ""}`;
    if (draft && row.querySelector("#os-unit-create")) {
      row.querySelector("#os-unit-name").value = draft.name;
      row.querySelector("#os-unit-admin-id").value = draft.admin;
      row.querySelector("details").open = draft.open;
    }
    row.setAttribute("aria-busy", String(pending || creating));
    if (active?.id && row.querySelector("#" + active.id)) row.querySelector("#" + active.id).focus({preventScroll:true});
  }
  async function createUnit(event) {
    if (event.target.id !== "os-unit-create") return;
    event.preventDefault();
    if (creating || !runtime().snapshot().systemAdmin) return;
    const form = event.target;
    const name = form.elements.name.value.trim(), admin = form.elements.admin.value.trim();
    if (!form.reportValidity() || !name || !admin) return;
    const token = runtime().capture();
    creating = true; feedback = "";
    form.querySelector("button").disabled = true;
    form.querySelector("#os-unit-create-status").textContent = "Đang tạo đơn vị…";
    try {
      await api("/api/units", {method:"POST", body:JSON.stringify({name, admin})});
      if (!runtime().current(token)) return;
      form.reset();
      feedback = "Đã tạo đơn vị. Chọn đơn vị nếu bạn có tư cách thành viên.";
      await runtime().refresh();
    } catch (error) {
      if (runtime().current(token)) feedback = error.message || "Chưa tạo được đơn vị. Kiểm tra tên và mã danh tính rồi thử lại.";
    } finally { creating = false; render(); }
  }
  window.BDSGUnitUI = {mount};
  window.addEventListener("bdsg-unit-changed", () => { feedback = ""; render(); });
  window.addEventListener("bdsg-unit-list-changed", render);
})();
