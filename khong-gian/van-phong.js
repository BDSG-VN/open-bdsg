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
  let transfers = [],
    transfer = null;
  let retryUpload = null;
  const googleExports = new Map();
  const googleImports = new Map();
  const createIntents = new Map();
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
      : n < 1048576
        ? `${(n / 1024).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} KiB`
        : `${(n / 1048576).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} MiB`;
  async function call(name, args = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    let result;
    try {
      result = await api(name === "ghi_phan" ? "/api/upload" : "/api/tools", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify(
          name === "ghi_phan"
            ? { destination: "office-part", ...args }
            : { name: "van_phong." + name, arguments: args },
        ),
      });
    } catch (error) {
      if (error.name === "AbortError" || error instanceof TypeError)
        throw new Error("Kết nối bị gián đoạn hoặc phản hồi quá chậm.");
      throw error;
    } finally {
      clearTimeout(timer);
    }
    if (!result.ok) {
      const messages = {
        LoiChuaQuetVirus:
          "Bộ quét virus chưa sẵn sàng. Tệp chưa được xuất bản; hãy thử lại sau.",
        LoiPhatHienVirus:
          "Tệp bị bộ quét virus từ chối. Hủy phiên tải và kiểm tra máy nguồn.",
        LoiKetNoiGoogle:
          "Google chưa hoàn tất thao tác. Kiểm tra kết nối và quyền cấp cho ứng dụng rồi thử lại.",
        LoiXungDotVanPhong:
          "Tệp đã thay đổi. Đọc lại phiên bản mới trước khi lưu để tránh ghi đè.",
        LoiHanMucVanPhong:
          "Kho dự án đã đạt giới hạn tệp, phiên bản hoặc dung lượng. Liên hệ chủ quản để xử lý.",
        LoiDinhDangVanPhong:
          "Tệp không đạt kiểm tra cấu trúc, có nội dung chủ động hoặc định dạng chưa hỗ trợ. Chọn tệp khác và hủy phiên tải này.",
        PermissionError:
          "Quyền truy cập đã thay đổi. Mở lại dự án để kiểm tra quyền hiện tại.",
        "xac-thuc":
          "Phiên làm việc hoặc tài khoản không còn hiệu lực. Hãy đăng nhập lại.",
      };
      const error = new Error(
        messages[result.loai_loi] ||
          (/hạn mức/.test(result.ly_do || "")
            ? "Bạn đang thao tác quá nhanh. Chờ một phút rồi thử lại; nội dung chưa lưu vẫn được giữ."
            : "Không thể xử lý tệp. Kiểm tra tên, định dạng, dung lượng và quyền dự án rồi thử lại."),
      );
      error.code = result.loai_loi;
      throw error;
    }
    return result.ket_qua;
  }
  const textFile = (name) => /\.(txt|md|csv)$/i.test(name);
  function encode(raw) {
    const parts = [];
    for (let i = 0; i < raw.length; i += 8192)
      parts.push(String.fromCharCode(...raw.subarray(i, i + 8192)));
    return btoa(parts.join(""));
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
  async function newOffice(extension) {
    if (!write() || busy) return;
    const name = window.prompt(
      "Tên tài liệu mới (giữ đuôi ." + extension + ")",
      "tai-lieu." + extension,
    );
    if (!name) return;
    if (!name.toLowerCase().endsWith("." + extension))
      return notice("Giữ đúng phần mở rộng đã chọn.", true);
    const t = ticket();
    busy = true;
    try {
      const intent = t.user + ":" + t.project + ":" + name;
      if (!createIntents.has(intent))
        createIntents.set(intent, crypto.randomUUID());
      const file = await call("tao_office", {
        project_id: selected,
        name,
        request_key: createIntents.get(intent),
      });
      createIntents.delete(intent);
      if (valid(t))
        location.assign("/soan-thao.html?id=" + encodeURIComponent(file.id));
    } catch (error) {
      if (valid(t)) notice(error.message, true);
    } finally {
      if (valid(t)) busy = false;
    }
  }
  async function googlePanel() {
    const t = ticket(),
      panel = document.querySelector("#office-google-body");
    if (!panel) return;
    panel.textContent = "Đang kiểm tra kết nối…";
    try {
      const result = await call("google_trang_thai");
      if (!valid(t) || !panel.isConnected) return;
      if (result.state === "chua-cau-hinh") {
        panel.innerHTML =
          "<p>Kết nối Google đang chờ chủ quản thiết lập. Khi sẵn sàng, mỗi người tự chọn tài khoản và cấp quyền cho các tệp muốn dùng. Không nhập mật khẩu Google tại BDSG.</p>";
      } else if (result.state === "chua-ket-noi") {
        panel.innerHTML =
          '<p>Kết nối tài khoản riêng của bạn. Chỉ các tệp bạn cấp cho ứng dụng mới được liệt kê.</p><button type="button" class="button" data-office-google-connect>Kết nối Google</button>';
      } else {
        const list = await call("google_danh_sach");
        if (!valid(t) || !panel.isConnected) return;
        panel.innerHTML = `<p>Đã kết nối. Nhập tệp tạo bản sao riêng trong dự án, không tự đồng bộ hai chiều.</p><button type="button" class="button" data-office-google-disconnect>Ngắt và thu hồi quyền Google</button><ul>${list.files.map((f) => `<li><span>${esc(f.name)}</span>${write() ? `<button class="button" type="button" data-office-google-import="${esc(f.id)}">Nhập bản sao</button>` : ""}</li>`).join("")}</ul><p>${list.files.length ? "" : "Chưa có tệp nào được cấp cho ứng dụng."}${list.limited ? " Đang hiển thị 50 tệp gần nhất." : ""}</p>`;
        if (write()) {
          const picker = document.createElement("a");
          picker.className = "button";
          picker.href =
            "/google-picker.html?project=" + encodeURIComponent(selected);
          picker.textContent = "Chọn tệp khác trên Google Drive";
          panel.prepend(picker);
        }
      }
    } catch (error) {
      if (valid(t) && panel.isConnected) panel.textContent = error.message;
    }
  }
  async function googleAction(action, id) {
    if (busy) return;
    const t = ticket();
    busy = true;
    try {
      if (action === "connect") {
        const result = await api("/api/google/start", {
          method: "POST",
          body: "{}",
        });
        const url = new URL(result.url);
        if (
          url.origin !== "https://accounts.google.com" ||
          url.pathname !== "/o/oauth2/v2/auth"
        )
          throw new Error("Không mở được trang cấp quyền Google.");
        if (valid(t)) location.assign(url.href);
      } else if (action === "disconnect") {
        if (
          !window.confirm(
            "Thu hồi kết nối Google cho ứng dụng? Tệp trên Google và trong BDSG vẫn được giữ.",
          )
        )
          return;
        await call("google_ngat");
        if (valid(t)) await googlePanel();
      } else if (action === "import") {
        const intent = selected + ":" + id;
        if (!googleImports.has(intent))
          googleImports.set(intent, crypto.randomUUID());
        await call("google_nhap", {
          project_id: selected,
          drive_id: id,
          request_key: googleImports.get(intent),
        });
        googleImports.delete(intent);
        if (valid(t)) {
          busy = false;
          await load();
          notice("Đã nhập bản sao từ Google vào dự án.");
        }
      } else if (action === "export") {
        if (
          !window.confirm(
            "Tạo bản sao phiên bản hiện tại trên Google Drive của bạn?",
          )
        )
          return;
        const intent = activeFile.id + ":" + activeFile.version;
        if (!googleExports.has(intent))
          googleExports.set(intent, crypto.randomUUID());
        await call("google_xuat", {
          id: activeFile.id,
          request_key: googleExports.get(intent),
        });
        googleExports.delete(intent);
        if (valid(t))
          document.querySelector("#office-dialog-error").textContent =
            "Đã xuất bản sao lên Google Drive.";
      }
    } catch (error) {
      if (valid(t)) {
        const element = document.querySelector("#office-dialog-error");
        if (element) element.textContent = error.message;
        else notice(error.message, true);
      }
    } finally {
      if (valid(t)) busy = false;
    }
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
      <div class="office-formats" role="group" aria-label="Tạo tài liệu Office">${[
        ["docx", "Tạo Word"],
        ["xlsx", "Tạo Excel"],
        ["pptx", "Tạo PowerPoint"],
      ]
        .map(
          ([ext, label]) =>
            `<button type="button" class="button" data-office-format="${ext}" ${!write() || busy || loading ? "disabled" : ""}>${label}</button>`,
        )
        .join("")}</div>
      <p id="office-notice" class="office-notice" role="status" aria-live="polite"></p>
      <div id="office-progress" class="office-progress" hidden></div>
      <div id="office-transfers"></div>
      <div id="office-files" aria-busy="${loading}"></div>
      <details class="office-google"><summary>Kết nối Google Drive</summary><div id="office-google-body"><p>Mở để kiểm tra kết nối tài khoản riêng của bạn.</p></div></details>
      <div class="office-footer"><p id="office-usage"></p><p>Tệp tối đa 8 MiB; sửa văn bản tối đa 32 KiB. Word, Excel và PowerPoint soạn trên máy tính bằng ONLYOFFICE. ${access?.scan_state === "san-sang" ? "Bộ quét virus đang sẵn sàng." : "Bộ quét virus chưa sẵn sàng; không coi tệp là đã được quét."}</p></div>
      </section>`;
    drawFiles();
    drawTransfers();
    document
      .querySelector(".office-google")
      ?.addEventListener("toggle", (event) => {
        if (event.target.open) googlePanel();
      });
  }
  function drawTransfers() {
    const target = document.querySelector("#office-transfers");
    if (!target || !current()) return;
    target.innerHTML = transfers.length
      ? `<section class="office-pending"><h2>Tệp đang tải dở</h2><p>Chọn lại cùng tệp để tiếp tục. Phiên hết hạn sau 15 phút không truyền thêm.</p><ul>${transfers.map((u) => `<li><div><strong>${esc(u.name)}</strong><small>${bytes(u.received)} / ${bytes(u.total)} đã nhận</small></div><button class="button" type="button" data-office-cancel="${esc(u.id)}" ${busy ? "disabled" : ""}>Hủy phiên tải</button></li>`).join("")}</ul></section>`
      : "";
  }
  function progress(label, received, total) {
    const target =
      document.querySelector("#office-dialog-progress") ||
      document.querySelector("#office-progress");
    if (!target) return;
    target.hidden = false;
    target.innerHTML = `<div><span>${esc(label)} · ${bytes(received)} / ${bytes(total)}</span><button class="button" type="button" data-office-stop>Hủy</button></div><progress value="${received}" max="${total || 1}" aria-label="${esc(label)}"></progress>`;
  }
  function clearProgress() {
    document
      .querySelectorAll("#office-dialog-progress,#office-progress")
      .forEach((e) => {
        e.hidden = true;
        e.replaceChildren();
      });
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
        ? `${access.usage.files} tệp · ${access.usage.versions} phiên bản · ${bytes(access.usage.bytes)} / 20 MiB, kể cả thùng rác.${access.transfer_usage?.reserved_bytes ? " Đang giữ chỗ " + bytes(access.transfer_usage.reserved_bytes) + " cho tải dở." : ""}${access.permissions.archived ? " Dự án đã lưu trữ: chỉ đọc." : write() ? " Bạn có quyền chỉnh sửa." : " Bạn có quyền chỉ đọc."}`
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
  function lockDialog(value) {
    const element = document.querySelector("#office-dialog");
    if (!element) return;
    element.setAttribute("aria-busy", String(value));
    element
      .querySelectorAll("button,input,textarea")
      .forEach((e) => (e.disabled = value));
  }
  function reset() {
    googleExports.clear();
    googleImports.clear();
    createIntents.clear();
    retryUpload = null;
    generation++;
    closeDialog(true);
    projects = [];
    transfers = [];
    transfer = null;
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
      retryUpload = null;
      closeDialog(true);
      files = [];
      access = null;
      transfers = [];
      transfer = null;
      loading = false;
      busy = false;
    }
  }
  async function load() {
    const t = ticket();
    loading = true;
    access = null;
    files = [];
    transfers = [];
    draw();
    if (!selected) {
      loading = false;
      draw();
      return;
    }
    try {
      const [status, listing, pending] = await Promise.all([
        call("trang_thai", { project_id: selected }),
        call("danh_sach", { project_id: selected, trashed: trash }),
        call("phien_tai", { project_id: selected }),
      ]);
      if (!valid(t)) return;
      access = status;
      files = listing.files;
      transfers = pending.uploads.filter((u) => u.state === "pending");
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
      const returned = new URL(location.href);
      if (current() && returned.searchParams.has("google")) {
        const panel = document.querySelector(".office-google");
        if (panel) panel.open = true;
        notice(
          "Đã trở về từ Google. Kiểm tra trạng thái kết nối bên dưới trước khi dùng tệp.",
        );
        returned.searchParams.delete("google");
        history.replaceState(
          null,
          "",
          returned.pathname + returned.search + returned.hash,
        );
      }
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
    element.innerHTML = `<header><h2 id="office-dialog-title">${esc(title)}</h2><button class="icon-button" type="button" data-office-close aria-label="Đóng cửa sổ">${icon("close")}</button></header>${body}<div id="office-dialog-progress" class="office-progress" hidden></div><p id="office-dialog-error" class="form-error" role="alert"></p>`;
    document.body.append(element);
    dialogKind = kind;
    element.addEventListener("cancel", (e) => {
      e.preventDefault();
      closeDialog();
    });
    element.addEventListener("input", () => {
      const editor = element.querySelector("#office-content");
      const name = element.querySelector('input[name="name"]');
      dirty =
        Boolean(editor && editor.value !== original) ||
        Boolean(kind === "create" && name && name.value !== name.defaultValue);
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
    const editable =
      write() && !file.trashed && textFile(file.name) && result.size <= 32768;
    let text = null;
    if (textFile(file.name) && typeof result.content_base64 === "string") {
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
    const actions = element.querySelector(".office-file-actions");
    if (write() && !file.trashed && /\.(docx|xlsx|pptx)$/i.test(file.name)) {
      const link = document.createElement("a");
      link.className = "button primary";
      link.href = "/soan-thao.html?id=" + encodeURIComponent(file.id);
      link.textContent = "Mở bộ soạn thảo";
      actions.prepend(link);
    }
    if (!file.trashed) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button";
      button.dataset.officeGoogleExport = "";
      button.textContent = "Xuất bản sao lên Google";
      actions.append(button);
    }
    const binary = element.querySelector(".office-binary-note");
    if (binary)
      binary.textContent =
        result.checks?.virus_state === "khong-phat-hien"
          ? "Bộ quét chưa phát hiện mã độc ở phiên bản này. Có thể tải xuống hoặc mở bộ soạn thảo nếu định dạng được hỗ trợ."
          : "Phiên bản này chưa có kết quả quét virus. Bộ soạn thảo sẽ yêu cầu quét thành công trước khi mở.";
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
    lockDialog(true);
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
        lockDialog(false);
      }
    }
  }
  async function upload(file, textName = null) {
    if (!write() || busy || !current()) return;
    if (file.size > (access?.limits?.file_bytes || 8388608))
      return notice("Tệp vượt 8 MiB. Chọn tệp nhỏ hơn để tải lên.", true);
    const t = ticket();
    const operation = { cancel: false, id: null };
    transfer = operation;
    const chunkBytes = access?.limits?.chunk_bytes || 524288;
    busy = true;
    lockDialog(true);
    draw();
    progress("Đang chuẩn bị tệp", 0, file.size);
    try {
      let result,
        createIntent = null;
      if (textName !== null) {
        const raw = new Uint8Array(await file.arrayBuffer());
        if (!valid(t)) return;
        if (operation.cancel) {
          notice("Đã hủy trước khi tạo văn bản.");
          return;
        }
        const digest = [
          ...new Uint8Array(await crypto.subtle.digest("SHA-256", raw)),
        ]
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
        if (!valid(t)) return;
        createIntent = t.user + ":" + t.project + ":" + textName + ":" + digest;
        if (!createIntents.has(createIntent))
          createIntents.set(createIntent, crypto.randomUUID());
        result = await call("tao", {
          project_id: selected,
          name: textName,
          content_base64: encode(raw),
          request_key: createIntents.get(createIntent),
        });
      } else {
        const digest = [
          ...new Uint8Array(
            await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
          ),
        ]
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
        if (!valid(t)) return;
        if (operation.cancel) {
          notice("Đã hủy trước khi tải lên.");
          return;
        }
        const inventory = await call("phien_tai", { project_id: selected });
        if (!valid(t)) return;
        const previous =
          retryUpload &&
          retryUpload.user === t.user &&
          retryUpload.project === t.project &&
          retryUpload.name === file.name &&
          retryUpload.total === file.size &&
          retryUpload.sha256 === digest
            ? retryUpload
            : null;
        let session = inventory.uploads.find(
          (u) =>
            ((previous?.id && u.id === previous.id) || u.state === "pending") &&
            u.name === file.name &&
            u.total === file.size &&
            u.sha256 === digest,
        );
        retryUpload = {
          user: t.user,
          project: t.project,
          name: file.name,
          total: file.size,
          sha256: digest,
          key: previous?.key || crypto.randomUUID(),
          id: session?.id || null,
        };
        if (!session)
          session = await call("bat_dau_tai", {
            project_id: selected,
            name: file.name,
            total: file.size,
            sha256: digest,
            request_key: retryUpload.key,
          });
        if (!valid(t)) return;
        operation.id = session.id;
        retryUpload.id = session.id;
        if (session.state !== "complete") {
          progress("Đang tải lên", session.received, file.size);
          while (session.received < file.size) {
            if (!valid(t)) return;
            if (operation.cancel) break;
            const offset = session.received;
            const part = new Uint8Array(
              await file.slice(offset, offset + chunkBytes).arrayBuffer(),
            );
            if (!valid(t)) return;
            session = await call("ghi_phan", {
              id: session.id,
              offset,
              content_base64: encode(part),
            });
            if (!valid(t)) return;
            if (session.received <= offset || session.received > file.size)
              throw new Error("Tiến trình tải không hợp lệ; hãy mở lại dự án.");
            progress("Đang tải lên", session.received, file.size);
          }
          if (operation.cancel) {
            const cancelled = await call("huy_tai", { id: session.id });
            if (!valid(t)) return;
            retryUpload = null;
            busy = false;
            await load();
            if (valid(t))
              notice(
                cancelled.cancelled
                  ? "Đã hủy và giải phóng chỗ giữ cho tệp."
                  : "Tệp đã hoàn tất trước khi hủy; nội dung vẫn được giữ.",
              );
            return;
          }
          progress("Đang kiểm tra và lưu", file.size, file.size);
          result = await call("ket_thuc_tai", { id: session.id });
        } else result = await call("ket_thuc_tai", { id: session.id });
      }
      if (!valid(t)) return;
      const receipt = await call("doc", {
        id: result.file?.id || result.id,
        version: 1,
      });
      if (!valid(t)) return;
      const scanned =
        receipt.checks?.virus_state === "khong-phat-hien" &&
        receipt.checks.sha256 === receipt.sha256;
      if (createIntent) createIntents.delete(createIntent);
      retryUpload = null;
      busy = false;
      dirty = false;
      closeDialog(true);
      await load();
      if (valid(t))
        notice(
          operation.cancel
            ? "Tệp đã lưu xong trước khi hủy; nội dung vẫn được giữ."
            : scanned
              ? "Đã lưu tệp. Đã quét phiên bản tải lên; chưa phát hiện mã độc."
              : "Đã lưu tệp. Phiên bản này chưa có kết quả quét virus.",
        );
      return result;
    } catch (error) {
      if (valid(t)) {
        if (textName === null) {
          busy = false;
          await load();
        }
        if (!valid(t)) return;
        notice(
          error.message +
            (textName === null && error.code !== "LoiDinhDangVanPhong"
              ? " Chọn lại cùng tệp để tiếp tục, hoặc hủy phiên tải dở."
              : ""),
          true,
        );
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
        lockDialog(false);
        clearProgress();
        if (transfer === operation) transfer = null;
      }
    }
  }
  async function cancelPending(id) {
    if (busy || !current()) return;
    const t = ticket();
    busy = true;
    drawControls();
    try {
      const result = await call("huy_tai", { id });
      if (!valid(t)) return;
      if (retryUpload?.id === id) retryUpload = null;
      busy = false;
      await load();
      if (valid(t))
        notice(
          result.cancelled
            ? "Đã hủy phiên tải dở và giải phóng chỗ giữ."
            : "Tệp đã hoàn tất, không bị xóa.",
        );
    } catch (error) {
      if (valid(t)) notice(error.message, true);
    } finally {
      if (valid(t)) {
        busy = false;
        drawControls();
        drawTransfers();
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
      .querySelectorAll(
        "#office-project,[data-office-tab],[data-office-cancel]",
      )
      .forEach((e) => (e.disabled = busy));
  }
  async function download(version) {
    if (!activeFile || busy) return;
    const file = activeFile,
      t = ticket();
    busy = true;
    const operation = { cancel: false };
    transfer = operation;
    try {
      const result = await call("doc", { id: file.id, version });
      if (!valid(t)) return;
      if (
        !Number.isSafeInteger(result.size) ||
        result.size < 0 ||
        result.size > 8388608
      )
        throw new Error("Dung lượng tệp không hợp lệ.");
      let raw;
      if (typeof result.content_base64 === "string")
        raw = decode(result.content_base64);
      else {
        raw = new Uint8Array(result.size);
        let offset = 0;
        while (offset < result.size) {
          if (!valid(t)) return;
          if (operation.cancel) {
            document.querySelector("#office-dialog-error").textContent =
              "Đã hủy tải xuống.";
            return;
          }
          progress("Đang tải xuống", offset, result.size);
          const part = await call("doc_phan", { id: file.id, version, offset });
          if (!valid(t)) return;
          const content = decode(part.content_base64);
          if (
            part.offset !== offset ||
            part.sha256 !== result.sha256 ||
            part.size !== result.size ||
            part.version !== version ||
            part.next_offset !== offset + content.length ||
            !content.length ||
            part.next_offset > result.size
          )
            throw new Error("Phần tải không khớp; chưa lưu tệp vào máy.");
          raw.set(content, offset);
          offset = part.next_offset;
        }
      }
      const digest = [
        ...new Uint8Array(await crypto.subtle.digest("SHA-256", raw)),
      ]
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
      if (!valid(t)) return;
      if (operation.cancel) {
        document.querySelector("#office-dialog-error").textContent =
          "Đã hủy tải xuống.";
        return;
      }
      if (digest !== result.sha256 || raw.length !== result.size)
        throw new Error("Dấu kiểm không khớp; chưa lưu tệp vào máy.");
      const url = URL.createObjectURL(
        new Blob([raw], {
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
      if (valid(t)) {
        busy = false;
        clearProgress();
        if (transfer === operation) transfer = null;
      }
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
    const officeNew = event.target.closest("[data-office-format]");
    if (officeNew && current())
      return newOffice(officeNew.dataset.officeFormat);
    if (event.target.closest("[data-office-google-connect]") && current())
      return googleAction("connect");
    if (event.target.closest("[data-office-google-disconnect]") && current())
      return googleAction("disconnect");
    const googleImport = event.target.closest("[data-office-google-import]");
    if (googleImport && current())
      return googleAction("import", googleImport.dataset.officeGoogleImport);
    if (event.target.closest("[data-office-google-export]") && current())
      return googleAction("export");
    if (event.target.closest("[data-office-login]")) return auth(open);
    if (event.target.closest("[data-office-close]")) return closeDialog();
    if (!current()) return;
    if (event.target.closest("[data-office-stop]")) {
      if (transfer) {
        transfer.cancel = true;
        const button = event.target.closest("[data-office-stop]");
        button.disabled = true;
        button.textContent = "Đang dừng…";
      }
      return;
    }
    const cancelling = event.target.closest("[data-office-cancel]");
    if (cancelling) return cancelPending(cancelling.dataset.officeCancel);
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
