"use strict";
(() => {
  let projects = [],
    files = [],
    selected = "",
    trash = false,
    query = "";
  let access = null,
    loading = false,
    busy = false,
    generation = 0;
  let activeFile = null,
    original = "",
    dialogKind = "",
    dirty = false;
  const urls = new Set();
  const current = () => location.hash === "#office" && Boolean(state.user);
  const ticket = () => ({
    generation,
    user: state.user?.id,
    project: selected,
  });
  const valid = (t) =>
    current() &&
    t.generation === generation &&
    t.user === state.user?.id &&
    t.project === selected;
  const write = () => Boolean(access?.permissions?.can_write);
  const bytes = (n) =>
    n < 1024
      ? `${n} B`
      : `${(n / 1024).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} KiB`;
  async function call(name, args = {}) {
    const result = await api("/api/tools", {
      method: "POST",
      body: JSON.stringify({ name: "van_phong." + name, arguments: args }),
    });
    if (!result.ok) {
      const messages = {
        LoiXungDotVanPhong:
          "Tệp đã thay đổi. Đọc lại phiên bản mới trước khi lưu để tránh ghi đè.",
        LoiHanMucVanPhong:
          "Kho dự án đã đạt giới hạn tệp, phiên bản hoặc dung lượng. Liên hệ chủ quản để xử lý.",
        PermissionError:
          "Quyền truy cập đã thay đổi. Mở lại dự án để kiểm tra quyền hiện tại.",
        "xac-thuc":
          "Phiên làm việc hoặc tài khoản không còn hiệu lực. Hãy đăng nhập lại.",
      };
      throw new Error(
        messages[result.loai_loi] ||
          (/hạn mức/.test(result.ly_do || "")
            ? "Bạn đang thao tác quá nhanh. Chờ một phút rồi thử lại; nội dung chưa lưu vẫn được giữ."
            : "Không thể xử lý tệp. Kiểm tra tên, định dạng, dung lượng và quyền dự án rồi thử lại."),
      );
    }
    return result.ket_qua;
  }
  const textFile = (name) => /\.(txt|md|csv)$/i.test(name);
  function encode(raw) {
    let value = "";
    for (const byte of raw) value += String.fromCharCode(byte);
    return btoa(value);
  }
  function decode(value) {
    return Uint8Array.from(atob(value), (c) => c.charCodeAt(0));
  }
  function notice(message, error = false) {
    const target = document.querySelector("#office-notice");
    if (!target || !current()) return;
    target.textContent = message;
    target.setAttribute("role", error ? "alert" : "status");
    target.classList.toggle("form-error", error);
  }
  function heading() {
    return `<div class="office-heading"><div><h1>Văn phòng của dự án</h1><p>Tệp, ghi chú và các phiên bản công việc, trong cùng một không gian.</p></div><a class="button" href="#projects">Quản lý dự án ${icon("arrow")}</a></div>`;
  }
  function draw() {
    if (location.hash !== "#office") return;
    if (!state.user) {
      main.innerHTML = `<section class="office-page">${heading()}<div class="office-empty">${icon("lock")}<h2>Đăng nhập để mở văn phòng</h2><p>Tệp riêng chỉ hiển thị theo quyền dự án của bạn.</p><button class="button primary" type="button" data-office-login>Đăng nhập</button></div></section>`;
      return;
    }
    main.innerHTML = `<section class="office-page">${heading()}
      <div class="office-controls"><label class="office-project-label">Dự án<select id="office-project" ${busy ? "disabled" : ""}><option value="">Chọn dự án…</option>${projects.map((p) => `<option value="${esc(p.id)}" ${p.id === selected ? "selected" : ""}>${esc(p.name)}${p.archived ? " · Đã lưu trữ" : ""}</option>`).join("")}</select></label>
      <div class="office-primary-actions"><button class="button" type="button" data-office-new ${!write() || loading || busy ? "disabled" : ""}>${icon("plus")}Tạo văn bản</button><label class="button primary office-upload ${!write() || loading || busy ? "disabled" : ""}">Tải tệp lên<input id="office-upload" type="file" accept=".txt,.md,.csv,.pdf,.docx,.xlsx,.pptx" aria-label="Chọn tệp để tải lên" ${!write() || loading || busy ? "disabled" : ""}></label></div></div>
      <div class="office-filter-bar"><div class="office-tabs" role="group" aria-label="Khu vực tệp"><button type="button" data-office-tab="files" aria-pressed="${!trash}" ${busy ? "disabled" : ""}>Tệp của dự án</button><button type="button" data-office-tab="trash" aria-pressed="${trash}" ${busy ? "disabled" : ""}>Thùng rác</button></div><label class="office-search">${icon("search")}<input id="office-search" type="search" placeholder="Tìm tên tệp…" aria-label="Tìm tên tệp" value="${esc(query)}"></label></div>
      <p id="office-notice" class="office-notice" role="status" aria-live="polite"></p>
      <div id="office-files" aria-busy="${loading}"></div>
      <div class="office-footer"><p id="office-usage"></p><p>Tệp tối đa 32 KiB. Word, Excel, PowerPoint và PDF chỉ lưu / tải xuống, chưa có trình soạn thảo hoặc quét virus.</p></div>
      </section>`;
    drawFiles();
  }
  function drawFiles() {
    const target = document.querySelector("#office-files");
    if (!target || !current()) return;
    if (loading)
      target.innerHTML =
        '<div class="office-empty"><p>Đang mở kho tệp…</p></div>';
    else if (!selected)
      target.innerHTML = `<div class="office-empty">${icon("briefcase")}<h2>${projects.length ? "Chọn dự án để bắt đầu" : "Tạo dự án đầu tiên của bạn"}</h2><p>Mỗi dự án có kho tệp riêng và kế thừa quyền cộng tác.</p><a class="button" href="#projects">Mở dự án ${icon("arrow")}</a></div>`;
    else {
      const visible = files.filter((f) => clean(f.name).includes(clean(query)));
      target.innerHTML = visible.length
        ? `<div class="office-table-wrap"><table class="office-table"><caption class="sr-only">${trash ? "Tệp trong thùng rác" : "Tệp của dự án"}</caption><thead><tr><th scope="col">Tên tệp</th><th scope="col">Dung lượng</th><th scope="col">Cập nhật</th><th scope="col"><span class="sr-only">Thao tác</span></th></tr></thead><tbody>${visible.map((f) => `<tr><th scope="row"><button type="button" class="office-file-name" data-office-file="${esc(f.id)}" ${busy ? "disabled" : ""}>${icon("briefcase")}<span><strong>${esc(f.name)}</strong><small>Phiên bản ${f.version}${trash ? " · Trong thùng rác" : ""}</small></span></button></th><td>${bytes(f.size)}</td><td><time>${date(f.updated)}</time></td><td><button class="button" type="button" data-office-file="${esc(f.id)}" ${busy ? "disabled" : ""}>Mở</button></td></tr>`).join("")}</tbody></table></div>`
        : `<div class="office-empty">${icon(query ? "search" : "briefcase")}<h2>${query ? "Không tìm thấy tệp" : trash ? "Thùng rác đang trống" : "Chưa có tệp trong dự án"}</h2><p>${query ? "Thử một tên khác hoặc bỏ bớt từ khóa." : trash ? "Tệp đã bỏ vào đây vẫn giữ lịch sử và có thể khôi phục." : "Tải tệp lên hoặc tạo ghi chú cho công việc của bạn."}</p></div>`;
    }
    const usage = document.querySelector("#office-usage");
    if (usage)
      usage.textContent = access
        ? `${access.usage.files} tệp · ${access.usage.versions} phiên bản · ${bytes(access.usage.bytes)} / 20 MiB, kể cả thùng rác.${access.permissions.archived ? " Dự án đã lưu trữ: chỉ đọc." : write() ? " Bạn có quyền chỉnh sửa." : " Bạn có quyền chỉ đọc."}`
        : "";
  }
  function closeDialog(force = false) {
    const dialog = document.querySelector("#office-dialog");
    if (!dialog?.open) return true;
    if (
      !force &&
      (busy || (dirty && !window.confirm("Bỏ những thay đổi chưa lưu?")))
    )
      return false;
    dialog.close();
    dialog.remove();
    activeFile = null;
    original = "";
    dirty = false;
    dialogKind = "";
    return true;
  }
  function reset() {
    generation++;
    closeDialog(true);
    projects = [];
    files = [];
    selected = "";
    access = null;
    loading = false;
    busy = false;
    query = "";
    trash = false;
    for (const url of urls) URL.revokeObjectURL(url);
    urls.clear();
  }
  function leave(hash) {
    if (hash !== "#office") {
      if (
        dirty &&
        state.user &&
        !window.confirm("Rời văn phòng và bỏ thay đổi chưa lưu?")
      ) {
        location.replace("#office");
        return false;
      }
      generation++;
      closeDialog(true);
      files = [];
      access = null;
      loading = false;
      busy = false;
    }
  }
  async function load() {
    const t = ticket();
    loading = true;
    access = null;
    files = [];
    draw();
    if (!selected) {
      loading = false;
      draw();
      return;
    }
    try {
      const [status, listing] = await Promise.all([
        call("trang_thai", { project_id: selected }),
        call("danh_sach", { project_id: selected, trashed: trash }),
      ]);
      if (!valid(t)) return;
      access = status;
      files = listing.files;
      loading = false;
      draw();
    } catch (error) {
      if (!valid(t)) return;
      loading = false;
      draw();
      notice(error.message + " Hãy thử tải lại.", true);
    }
  }
  async function open() {
    if (location.hash !== "#office") return;
    if (dirty && state.user) return;
    closeDialog(true);
    generation++;
    busy = false;
    if (!state.user) {
      draw();
      return;
    }
    const t = ticket();
    loading = true;
    draw();
    try {
      const result = await tool("du_an.danh_sach");
      if (!valid(t)) return;
      projects = result.projects;
      if (!projects.some((p) => p.id === selected))
        selected =
          projects.find((p) => !p.archived)?.id || projects[0]?.id || "";
      await load();
    } catch (error) {
      if (!valid(t)) return;
      loading = false;
      draw();
      notice(error.message, true);
    }
  }
  function dialog(title, body, kind) {
    if (!closeDialog()) return null;
    const element = document.createElement("dialog");
    element.id = "office-dialog";
    element.className = "office-dialog";
    element.setAttribute("aria-labelledby", "office-dialog-title");
    element.innerHTML = `<header><h2 id="office-dialog-title">${esc(title)}</h2><button class="icon-button" type="button" data-office-close aria-label="Đóng cửa sổ">${icon("close")}</button></header>${body}<p id="office-dialog-error" class="form-error" role="alert"></p>`;
    document.body.append(element);
    dialogKind = kind;
    element.addEventListener("cancel", (e) => {
      e.preventDefault();
      closeDialog();
    });
    element.addEventListener("input", () => {
      const editor = element.querySelector("#office-content");
      dirty = editor ? editor.value !== original : kind === "create";
      const label = element.querySelector("#office-save-status");
      if (label) label.textContent = dirty ? "Có thay đổi chưa lưu" : "Đã lưu";
    });
    element.showModal();
    return element;
  }
  function createText() {
    if (!write() || busy) return;
    original = "";
    dialog(
      "Tạo văn bản",
      `<form id="office-create"><label>Tên tệp<input name="name" required maxlength="120" value="ghi-chu.txt" autocomplete="off"></label><p class="muted">Văn bản UTF-8, đuôi .txt, .md hoặc .csv. Không phải tài liệu Word hoặc bảng tính có công thức.</p><label>Nội dung<textarea id="office-content" name="content" rows="12" maxlength="32768"></textarea></label><button type="submit" class="button primary">Tạo văn bản</button></form>`,
      "create",
    );
  }
  function showFile(result, history) {
    const file = result.file;
    const editable = write() && !file.trashed && textFile(file.name);
    let text = null;
    if (textFile(file.name)) {
      try {
        text = new TextDecoder("utf-8", { fatal: true }).decode(
          decode(result.content_base64),
        );
        if (text.includes("\0")) text = null;
      } catch (_) {
        text = null;
      }
    }
    const element = dialog(
      file.name,
      `<div class="office-file-meta"><span>Phiên bản ${file.version} · ${bytes(result.size)}</span><span>${file.trashed ? "Trong thùng rác" : "Kho tệp dự án"}</span></div>
      ${text !== null ? `<form id="office-save"><label>Nội dung văn bản<textarea id="office-content" name="content" rows="14" maxlength="32768" ${editable ? "" : "readonly"}></textarea></label><div class="office-editor-bar"><span id="office-save-status" role="status">Đã lưu</span>${editable ? '<button type="submit" class="button primary">Lưu phiên bản mới</button>' : '<span class="muted">Chỉ đọc</span>'}</div></form>` : '<p class="office-binary-note">Tệp này chỉ hỗ trợ lưu và tải xuống. Chưa có trình soạn thảo hoặc kiểm tra virus. Chỉ mở tệp từ nguồn bạn tin cậy.</p>'}
      <div class="office-file-actions"><button type="button" class="button" data-office-download="${file.version}">Tải xuống</button>${write() ? (file.trashed ? '<button type="button" class="button" data-office-action="untrash">Khôi phục tệp</button>' : '<button type="button" class="button" data-office-rename>Đổi tên</button><button type="button" class="button" data-office-action="trash">Chuyển vào thùng rác</button>') : ""}</div>
      <details class="office-history"><summary>Lịch sử phiên bản (${history.versions.length})</summary><ol>${history.versions.map((v) => `<li><div><strong>Phiên bản ${v.version}</strong><small>${date(v.created)} · ${bytes(v.size)}</small></div><div><button type="button" class="button" data-office-download="${v.version}" aria-label="Tải phiên bản ${v.version}">Tải</button>${write() && !file.trashed && v.version !== file.version ? `<button type="button" class="button" data-office-restore-version="${v.version}">Khôi phục</button>` : ""}</div></li>`).join("")}</ol></details>`,
      "file",
    );
    if (!element) return;
    activeFile = file;
    original = text || "";
    if (text !== null) element.querySelector("#office-content").value = text;
    element.querySelector("[data-office-close]").focus();
  }
  async function openFile(id) {
    if (busy || !current()) return;
    const t = ticket();
    busy = true;
    notice("Đang mở tệp…");
    try {
      const [result, history] = await Promise.all([
        call("doc", { id }),
        call("lich_su", { id }),
      ]);
      if (!valid(t)) return;
      busy = false;
      notice("");
      showFile(result, history);
    } catch (error) {
      if (valid(t)) notice(error.message, true);
    } finally {
      if (valid(t)) busy = false;
    }
  }
  async function mutate(action, extras = {}) {
    if (!activeFile || !write() || busy) return;
    const file = activeFile,
      t = ticket();
    busy = true;
    document
      .querySelectorAll("#office-dialog button")
      .forEach((b) => (b.disabled = true));
    try {
      const updated = await call("cap_nhat", {
        id: file.id,
        expected_revision: file.revision,
        action,
        ...extras,
      });
      if (!valid(t)) return;
      busy = false;
      dirty = false;
      closeDialog(true);
      await load();
      if (!valid(t)) return;
      notice(
        action === "save"
          ? "Đã lưu phiên bản mới."
          : action === "trash"
            ? "Đã chuyển tệp vào thùng rác; lịch sử vẫn được giữ."
            : "Đã cập nhật tệp.",
      );
      if (
        action === "save" ||
        action === "rename" ||
        action === "restore-version"
      )
        await openFile(updated.id);
    } catch (error) {
      if (valid(t)) {
        const node = document.querySelector("#office-dialog-error");
        if (node)
          node.textContent =
            error.message +
            " Nội dung chưa lưu vẫn được giữ; hãy sao chép trước khi mở lại tệp.";
      }
    } finally {
      if (valid(t)) {
        busy = false;
        document
          .querySelectorAll("#office-dialog button")
          .forEach((b) => (b.disabled = false));
      }
    }
  }
  async function upload(file, textName = null) {
    if (!write() || busy || !current()) return;
    if (file.size > (access?.limits?.file_bytes || 32768))
      return notice("Tệp vượt 32 KiB. Chọn tệp nhỏ hơn để tải lên.", true);
    const t = ticket();
    busy = true;
    draw();
    notice("Đang tải tệp lên…");
    try {
      const raw = new Uint8Array(await file.arrayBuffer());
      if (!valid(t)) return;
      const result = await call("tao", {
        project_id: selected,
        name: textName || file.name,
        content_base64: encode(raw),
      });
      if (!valid(t)) return;
      busy = false;
      dirty = false;
      closeDialog(true);
      await load();
      if (valid(t)) notice("Đã lưu tệp. Nội dung chưa được quét virus.");
      return result;
    } catch (error) {
      if (valid(t)) {
        notice(error.message, true);
        const target = document.querySelector("#office-dialog-error");
        if (target) target.textContent = error.message;
      }
    } finally {
      if (valid(t)) {
        busy = false;
        drawFiles();
        const input = document.querySelector("#office-upload");
        if (input) input.value = "";
        drawControls();
      }
    }
  }
  function drawControls() {
    document
      .querySelectorAll("[data-office-new],#office-upload")
      .forEach((e) => (e.disabled = !write() || loading || busy));
    const label = document.querySelector(".office-upload");
    label?.classList.toggle("disabled", !write() || loading || busy);
    document
      .querySelectorAll("#office-project,[data-office-tab]")
      .forEach((e) => (e.disabled = busy));
  }
  async function download(version) {
    if (!activeFile || busy) return;
    const file = activeFile,
      t = ticket();
    busy = true;
    try {
      const result = await call("doc", { id: file.id, version });
      if (!valid(t)) return;
      const url = URL.createObjectURL(
        new Blob([decode(result.content_base64)], {
          type: "application/octet-stream",
        }),
      );
      urls.add(url);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => {
        URL.revokeObjectURL(url);
        urls.delete(url);
      }, 1000);
    } catch (error) {
      if (valid(t))
        document.querySelector("#office-dialog-error").textContent =
          error.message;
    } finally {
      if (valid(t)) busy = false;
    }
  }
  document.addEventListener("input", (event) => {
    if (event.target.id === "office-search") {
      query = event.target.value;
      drawFiles();
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target.id === "office-project") {
      selected = event.target.value;
      generation++;
      busy = false;
      query = "";
      closeDialog(true);
      load();
    }
    if (event.target.id === "office-upload" && event.target.files[0])
      upload(event.target.files[0]);
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-office-login]")) return auth(open);
    if (event.target.closest("[data-office-close]")) return closeDialog();
    if (!current()) return;
    if (event.target.closest("[data-office-new]")) return createText();
    const tab = event.target.closest("[data-office-tab]");
    if (tab && !busy) {
      trash = tab.dataset.officeTab === "trash";
      generation++;
      return load();
    }
    const file = event.target.closest("[data-office-file]");
    if (file) return openFile(file.dataset.officeFile);
    const down = event.target.closest("[data-office-download]");
    if (down) return download(Number(down.dataset.officeDownload));
    if (event.target.closest("[data-office-rename]") && activeFile && !busy) {
      if (dirty && !window.confirm("Bỏ thay đổi chưa lưu để đổi tên tệp?"))
        return;
      const name = window.prompt(
        "Đổi tên tệp (giữ nguyên phần mở rộng)",
        activeFile.name,
      );
      if (name !== null && name !== activeFile.name) mutate("rename", { name });
    }
    const action = event.target.closest("[data-office-action]");
    if (
      action &&
      (!dirty || window.confirm("Bỏ thay đổi chưa lưu và tiếp tục?"))
    )
      mutate(action.dataset.officeAction);
    const restore = event.target.closest("[data-office-restore-version]");
    if (
      restore &&
      window.confirm(
        `${dirty ? "Thay đổi chưa lưu sẽ bị bỏ. " : ""}Tạo phiên bản mới từ bản đã chọn? Các phiên bản hiện có vẫn được giữ.`,
      )
    )
      mutate("restore-version", {
        version: Number(restore.dataset.officeRestoreVersion),
      });
  });
  document.addEventListener("submit", (event) => {
    if (!["office-create", "office-save"].includes(event.target.id)) return;
    event.preventDefault();
    if (busy || !current() || !write()) return;
    const data = new FormData(event.target),
      raw = new TextEncoder().encode(data.get("content"));
    if (raw.length > 32768) {
      document.querySelector("#office-dialog-error").textContent =
        "Nội dung UTF-8 vượt 32 KiB; hãy rút gọn trước khi lưu.";
      return;
    }
    if (event.target.id === "office-save")
      return mutate("save", { content_base64: encode(raw) });
    const name = data.get("name").trim();
    if (!textFile(name)) {
      document.querySelector("#office-dialog-error").textContent =
        "Văn bản cần đuôi .txt, .md hoặc .csv.";
      return;
    }
    upload(new Blob([raw]), name);
  });
  window.addEventListener("beforeunload", (event) => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  window.BDSGOffice = { open, reset, leave };
})();
