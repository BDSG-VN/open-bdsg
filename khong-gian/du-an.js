"use strict";
(() => {
  let projects = [];
  let selectedProject = "";
  let archivedView = false;
  let revision = 0;
  let pending = false;
  const isCurrent = () => location.hash === "#projects";
  const canManage = () => ["operator", "quan-tri"].includes(state.user?.role);
  const isArchived = (project) => Boolean(project.archived);
  const projectById = (id) => projects.find((project) => project.id === id);

  function setSelected(id) {
    if (
      id !== "" &&
      (typeof id !== "string" || !/^[a-zA-Z0-9_-]{1,80}$/.test(id))
    )
      return false;
    selectedProject = id;
    return true;
  }
  function clearSelected() {
    selectedProject = "";
  }
  function showError(message) {
    const target = $("#project-page-error");
    if (target) target.textContent = message;
    else toast(message);
  }
  function pageHeading() {
    return `<div class="bdsg-work-page-heading"><div><h1>Cùng một mục tiêu.<br>Cùng một không gian dự án.</h1><p>Lưu chỉ dẫn và ngữ cảnh dùng chung, để mỗi công việc bắt đầu từ đúng điều cần biết.</p></div>${canManage() ? `<button class="button primary" type="button" data-project-new>${icon("plus")}Tạo dự án</button>` : ""}</div>`;
  }
  function emptyState() {
    return `<section class="panel project-empty"><div class="project-empty-icon">${icon(archivedView ? "briefcase" : "grid")}</div><h2>${archivedView ? "Chưa có dự án được lưu trữ." : "Tạo một không gian cho công việc dài hạn."}</h2><p>${archivedView ? "Lưu trữ giữ lại ngữ cảnh và công việc; bạn có thể khôi phục khi cần." : "Một dự án có thể dành cho phát triển một lĩnh vực, triển khai một nền tảng hoặc phối hợp nhiều mô-đun tại Thanh Hoá."}</p>${!archivedView && canManage() ? '<button class="button primary" type="button" data-project-new>Tạo dự án đầu tiên</button>' : ""}</section>`;
  }
  function card(project) {
    const count =
      typeof project.task_count === "number"
        ? `<span>${project.task_count} công việc</span>`
        : "";
    return `<article class="panel project-card"><div class="project-card-top"><div class="project-card-icon">${icon("briefcase")}</div><span class="mini-tag">${isArchived(project) ? "Đã lưu trữ" : "Đang hoạt động"}</span></div><h2>${esc(project.name)}</h2><p class="project-card-summary">${esc(project.instructions ? project.instructions.slice(0, 220) : "Chưa có chỉ dẫn chung. Bạn có thể bổ sung trong phần chỉnh sửa dự án.")}</p><div class="project-card-meta">${count}<span>Cập nhật ${esc(date(project.updated || project.created))}</span></div><details class="project-context"><summary>${icon("grid")}Xem ngữ cảnh dự án</summary><div><strong>Chỉ dẫn chung</strong><p>${esc(project.instructions || "Chưa có chỉ dẫn.")}</p><strong>Ngữ cảnh tham khảo</strong><pre>${esc(project.context || "Chưa có ngữ cảnh tham khảo.")}</pre><p class="project-context-note">Ngữ cảnh có thể được đưa vào công việc và gửi tới nhà cung cấp mô hình đã chọn khi bạn chạy AI. Không lưu khóa, mật khẩu hoặc chứng thư tại đây.</p></div></details><div class="project-card-actions">${isArchived(project) ? `<button class="button small" type="button" data-project-restore="${esc(project.id)}" ${pending ? "disabled" : ""}>Khôi phục dự án</button>` : `<button class="button primary small" type="button" data-project-use="${esc(project.id)}">Giao việc trong dự án ${icon("arrow")}</button><button class="button small" type="button" data-project-edit="${esc(project.id)}">Chỉnh sửa</button><button class="text-link project-archive" type="button" data-project-archive="${esc(project.id)}" ${pending ? "disabled" : ""}>Lưu trữ</button>`}</div></article>`;
  }
  function draw() {
    if (!isCurrent()) return;
    if (!state.user) {
      projects = [];
      main.innerHTML = `<section class="bdsg-work-page project-page">${pageHeading()}<section class="panel project-empty"><div class="project-empty-icon">${icon("lock")}</div><h2>Không gian dự án của bạn là riêng tư.</h2><p>Đăng nhập để tạo dự án, lưu chỉ dẫn dùng chung và tiếp tục các công việc có cùng ngữ cảnh.</p><button class="button primary" type="button" data-project-login>Đăng nhập để làm việc</button></section></section>`;
      return;
    }
    const visible = projects.filter(
      (project) => isArchived(project) === archivedView,
    );
    const active = projects.filter((project) => !isArchived(project)).length;
    const archived = projects.length - active;
    main.innerHTML = `<section class="bdsg-work-page project-page">${pageHeading()}<div class="project-view-bar"><div class="project-view-tabs" role="group" aria-label="Trạng thái dự án"><button type="button" data-project-view="active" aria-pressed="${!archivedView}" class="${!archivedView ? "active" : ""}">Đang hoạt động <span>${active}</span></button><button type="button" data-project-view="archived" aria-pressed="${archivedView}" class="${archivedView ? "active" : ""}">Đã lưu trữ <span>${archived}</span></button></div><p>Chỉ dẫn dùng chung · Công việc theo quyền truy cập</p></div><p id="project-page-error" class="form-error project-page-error" role="alert"></p>${visible.length ? `<section class="project-grid">${visible.map(card).join("")}</section>` : emptyState()}</section>`;
  }
  async function open() {
    if (!isCurrent()) return;
    const ticket = ++revision;
    if (!state.user) {
      draw();
      return;
    }
    main.innerHTML =
      '<section class="bdsg-work-page project-page"><p class="muted">Đang mở không gian dự án…</p></section>';
    try {
      const result = await tool("du_an.danh_sach");
      if (ticket !== revision || !isCurrent()) return;
      projects = Array.isArray(result.projects) ? result.projects : [];
      if (
        selectedProject &&
        projects.some(
          (project) => project.id === selectedProject && isArchived(project),
        )
      )
        clearSelected();
      draw();
    } catch (error) {
      if (ticket === revision && isCurrent())
        main.innerHTML = `<section class="bdsg-work-page project-page">${pageHeading()}<div class="error-state" role="alert">${esc(error.message)}</div></section>`;
    }
  }
  function ensureDialog() {
    if ($("#project-dialog")) return;
    const dialog = document.createElement("dialog");
    dialog.id = "project-dialog";
    dialog.className = "project-dialog";
    dialog.innerHTML = `<form id="project-edit-form"><div class="dialog-heading"><button class="icon-button" type="button" aria-label="Đóng dự án" data-project-close>${icon("close")}</button></div><h2 id="project-dialog-title">Tạo dự án của bạn.</h2><p class="project-dialog-description">Giữ mục tiêu và chỉ dẫn chung cho các công việc liên quan. Đây là ngữ cảnh văn bản, không phải kho chứng thư hay tệp đính kèm.</p><input name="id" type="hidden"><label>Tên dự án<input name="name" required minlength="3" maxlength="100" placeholder="Ví dụ: Phát triển hệ sinh thái kinh doanh Thanh Hoá" autocomplete="off"></label><label>Chỉ dẫn chung<textarea name="instructions" rows="4" maxlength="4000" placeholder="Mục tiêu, cách làm việc, tiêu chí hoàn tất và các giới hạn cần giữ…"></textarea></label><label>Ngữ cảnh tham khảo<textarea name="context" rows="6" maxlength="12000" placeholder="Mô tả sản phẩm, quy trình hoặc thông tin nền được phép dùng trong công việc…"></textarea></label><p class="project-dialog-description">Ngữ cảnh dùng trong tác vụ AI có thể được gửi tới nhà cung cấp mô hình đã cấu hình. Không nhập khóa API, mật khẩu hoặc thông tin không được phép chia sẻ.</p><p id="project-form-error" class="form-error" role="alert"></p><button type="submit" class="button primary full">Lưu dự án ${icon("check")}</button></form>`;
    document.body.append(dialog);
    dialog.addEventListener("close", () => $("#project-edit-form").reset());
  }
  function edit(id = "") {
    if (!canManage())
      return toast("Danh tính này chưa có quyền quản lý dự án.");
    ensureDialog();
    const project = id ? projectById(id) : null;
    if (id && !project)
      return toast("Không tìm thấy dự án trong phạm vi của bạn.");
    const form = $("#project-edit-form");
    form.reset();
    form.elements.id.value = project?.id || "";
    form.elements.name.value = project?.name || "";
    form.elements.instructions.value = project?.instructions || "";
    form.elements.context.value = project?.context || "";
    $("#project-dialog-title").textContent = project
      ? "Chỉnh sửa không gian dự án."
      : "Tạo dự án của bạn.";
    $("#project-form-error").textContent = "";
    $("#project-dialog").showModal();
  }
  async function changeArchive(id, archived) {
    if (pending || !canManage()) return;
    const project = projectById(id);
    if (!project) return;
    pending = true;
    draw();
    try {
      await tool(archived ? "du_an.luu_tru" : "du_an.khoi_phuc", { id });
      if (archived && selectedProject === id) clearSelected();
      await open();
      toast(
        archived
          ? "Đã lưu trữ dự án; công việc và ngữ cảnh được giữ lại."
          : "Đã khôi phục dự án.",
      );
    } catch (error) {
      showError(error.message);
    } finally {
      pending = false;
      document
        .querySelectorAll("[data-project-archive],[data-project-restore]")
        .forEach((button) => {
          button.disabled = false;
        });
    }
  }
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-project-login]")) {
      auth(() => open());
      return;
    }
    if (event.target.closest("[data-project-new]")) {
      auth(() => edit());
      return;
    }
    if (event.target.closest("[data-project-close]")) {
      $("#project-dialog").close();
      return;
    }
    const view = event.target.closest("[data-project-view]");
    if (view) {
      archivedView = view.dataset.projectView === "archived";
      draw();
      return;
    }
    const editing = event.target.closest("[data-project-edit]");
    if (editing) {
      edit(editing.dataset.projectEdit);
      return;
    }
    const using = event.target.closest("[data-project-use]");
    if (using) {
      if (setSelected(using.dataset.projectUse)) location.hash = "work";
      return;
    }
    const archiving = event.target.closest("[data-project-archive]");
    if (archiving) {
      changeArchive(archiving.dataset.projectArchive, true);
      return;
    }
    const restoring = event.target.closest("[data-project-restore]");
    if (restoring) changeArchive(restoring.dataset.projectRestore, false);
  });
  document.addEventListener("submit", async (event) => {
    if (event.target.getAttribute("id") !== "project-edit-form") return;
    event.preventDefault();
    const form = event.target,
      button = form.querySelector('[type="submit"]');
    if (button.disabled) return;
    const values = Object.fromEntries(new FormData(form));
    const id = values.id;
    delete values.id;
    const args = id ? { id, ...values } : values;
    if (new TextEncoder().encode(JSON.stringify(args)).byteLength > 60000) {
      $("#project-form-error").textContent =
        "Ngữ cảnh vượt giới hạn gửi. Hãy rút gọn nội dung trước khi lưu.";
      return;
    }
    button.disabled = true;
    $("#project-form-error").textContent = "";
    try {
      await tool(id ? "du_an.cap_nhat" : "du_an.tao", args);
      form.reset();
      $("#project-dialog").close();
      archivedView = false;
      await open();
      toast(id ? "Đã cập nhật ngữ cảnh dự án." : "Đã tạo không gian dự án.");
    } catch (error) {
      $("#project-form-error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  window.BDSGProjects = {
    open,
    getSelected: () => selectedProject,
    setSelected,
    clearSelected,
    reset() {
      revision++;
      projects = [];
      selectedProject = "";
      archivedView = false;
      pending = false;
      document.querySelector("#project-dialog")?.remove();
    },
  };
})();
