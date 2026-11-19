"use strict";
(() => {
  let rows = [],
    selected = "",
    pending = false,
    epoch = 0,
    mutation = 0;
  const labels = {
    "da-khai-bao": "Đã khai báo",
    "da-xac-minh": "MCP có phản hồi",
    "loi-ket-noi": "Cần kiểm tra kết nối",
    "da-ngat": "Đã ngắt",
  };
  const current = () => location.hash === "#integrations";
  const unitMode = () => window.BDSGUnit?.snapshot().mode === "units";
  const canManage = () => unitMode() ? window.BDSGUnit.canAdmin() : state.user?.role === "quan-tri";
  const capture = () => window.BDSGUnit?.capture();
  const live = (token) => !token || window.BDSGUnit?.current(token);
  function clearToken() {
    const input = document.querySelector('#connector-form input[name="token"]');
    if (input) input.value = "";
  }
  const name = (id) => state.products.find((p) => p.id === id)?.name || id;
  function feedback(message) {
    const element = $("#connector-feedback");
    if (element) element.textContent = message;
  }
  function form() {
    const record = rows.find((r) => r.platform_id === selected);
    return `<section class="panel connector-form"><h2>${record ? "Cập nhật đầu nối" : "Khai báo đầu nối MCP"}</h2><p class="muted">Nhập endpoint và tên công cụ do quản trị nền tảng cung cấp. Chứng thư lưu riêng trên máy chủ; không thể xem lại.</p><form id="connector-form"><fieldset id="connector-fields" ${pending ? "disabled" : ""}><label>Nền tảng<select name="platform_id" id="connector-platform" required><option value="">Chọn nền tảng BDSG</option>${state.products.map((p) => `<option value="${esc(p.id)}" ${selected === p.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></label><label>Endpoint MCP<input name="url" type="url" required maxlength="1000" value="${esc(record?.url || "")}" placeholder="https://ten-nen-tang.bdsg.vn/mcp" autocomplete="off"></label><label>Chứng thư Bearer<input name="token" type="password" maxlength="4096" autocomplete="off" placeholder="${record?.has_token ? "Để trống để giữ chứng thư tại cùng endpoint" : "Nhập chứng thư được cấp cho Thanh Hoá"}"></label><label>Công cụ đọc được ${unitMode() ? "quản trị đơn vị" : "chủ quản"} cho phép<textarea name="read_tools" rows="4" placeholder="Mỗi dòng một tên công cụ, có thể để trống để kiểm tra trước">${esc((record?.read_tools || []).join("\n"))}</textarea></label>${unitMode() ? `<fieldset class="connector-read-roles"><legend>Ai được dùng công cụ đọc?</legend><label><input type="checkbox" name="read_admin" ${!record || record.read_roles?.includes("admin") ? "checked" : ""}>Quản trị đơn vị</label><label><input type="checkbox" name="read_member" ${record?.read_roles?.includes("member") ? "checked" : ""}>Thành viên đơn vị</label></fieldset><p class="muted">Lưu chỉ áp dụng cho đơn vị đang chọn. Quyền đọc của từng tác vụ cần cấp riêng; mỗi nội dung ghi phải được quản trị có quyền dự án duyệt.</p>` : ""}<p class="muted">Lưu không tự gửi yêu cầu. “Kiểm tra MCP” chỉ bắt tay và đọc danh sách công cụ; không chạy nghiệp vụ.${unitMode() ? "" : " Chỉ chủ quản được gọi công cụ đọc đã khai báo."}</p><button class="button primary" type="submit" ${pending ? "disabled" : ""}>Lưu cấu hình đầu nối</button></fieldset></form><p id="connector-feedback" class="connector-feedback" role="status" aria-live="polite"></p></section>`;
  }
  function memberView() {
    return `<section class="panel connector-intro"><h2>Kết nối của đơn vị</h2><p>Bạn đang là thành viên đơn vị. Chỉ quản trị đơn vị được thay đổi endpoint, chứng thư và quyền công cụ.</p>${rows.length ? rows.map(row => `<article class="connector-row"><div><strong>${esc(name(row.platform_id))}</strong><span class="mini-tag">${esc(labels[row.state] || row.state)}</span></div><p>${row.read_tools?.length ? "Công cụ đọc được cấp: " + esc(row.read_tools.join(", ")) : "Chưa có công cụ đọc được cấp cho vai trò của bạn."}</p></article>`).join("") : '<p>Đơn vị chưa khai báo đầu nối MCP. Hãy nhờ quản trị đơn vị cấu hình khi đã có endpoint và chứng thư.</p>'}<p>Quyền đọc trong từng tác vụ cần được cấp riêng; mở website không tự liên thông dữ liệu.</p><a class="button primary" href="#work">Mở giao việc</a></section>`;
  }
  function list() {
    return `<section class="panel connector-list"><h2>Đầu nối đã khai báo</h2>${rows.length ? rows.map((r) => `<article class="connector-row"><div><strong>${esc(name(r.platform_id))}</strong><span class="mini-tag">${esc(labels[r.state] || r.state)}</span></div><code>${esc(r.url)}</code><p>${r.has_token ? "Có chứng thư riêng" : "Không giữ chứng thư hoạt động"} · ${(r.read_tools || []).length} công cụ đọc${r.checked_at ? " · Kiểm tra " + esc(date(r.checked_at)) : ""}</p>${r.discovered_tools?.length ? `<details><summary>Công cụ máy chủ đã trả về${r.tools_complete ? "" : " (danh sách một phần)"}</summary><pre>${esc(r.discovered_tools.join("\n"))}</pre><p>Danh sách trả về không tự cấp quyền. Chỉ thêm công cụ đọc đã được bên quản trị xác nhận.</p></details>` : ""}<div class="connector-actions"><button class="button small" type="button" data-connector-edit="${esc(r.platform_id)}">Cập nhật</button><button class="button small" type="button" data-connector-probe="${esc(r.platform_id)}" ${!r.enabled || pending ? "disabled" : ""}>Kiểm tra MCP</button>${r.enabled ? `<button class="button small" type="button" data-connector-disconnect="${esc(r.platform_id)}" ${pending ? "disabled" : ""}>Ngắt kết nối</button>` : ""}</div></article>`).join("") : '<div class="bdsg-work-empty"><h3>Chưa có đầu nối nghiệp vụ.</h3><p>Website các nền tảng vẫn mở được. Khai báo MCP khi đã có endpoint và chứng thư hợp lệ.</p></div>'}<p class="muted">“MCP có phản hồi” xác nhận initialize và tools/list tại thời điểm kiểm tra; không chứng minh công cụ nghiệp vụ hoặc đồng bộ dữ liệu đã hoạt động.</p></section>`;
  }
  function draw() {
    if (!current()) return;
    main.innerHTML = `<section class="bdsg-work-page connector-page ${unitMode() ? "connector-unit" : ""}"><div class="bdsg-work-page-heading"><div><h1>Đưa nền tảng vào công việc.</h1><p>${unitMode() ? "Endpoint, chứng thư và quyền công cụ thuộc đơn vị đang chọn." : "Khai báo, kiểm tra và quản lý quyền kết nối MCP của từng mô-đun BDSG."}</p></div><a class="button" href="#modules">Thư viện mô-đun ${icon("grid")}</a></div>${canManage() ? `<div class="connector-layout">${form()}${list()}</div>` : unitMode() && state.user ? memberView() : `<section class="panel connector-intro"><div class="app-icon">${icon("lock")}</div><h2>Chủ quản quản lý đầu nối.</h2><p>Endpoint, chứng thư và quyền công cụ được cấu hình trong không gian riêng. Danh mục mô-đun vẫn có thể xem công khai.</p><button class="button primary" type="button" data-connector-login>Đăng nhập để quản lý kết nối</button><div class="connector-principles"><span>HTTPS trong miền BDSG</span><span>Chứng thư không hiển thị lại</span><span>Quyền đọc cụ thể theo công cụ</span></div></section>`}</section>`;
    if (unitMode()) { writeFields(); return; }
    const vietnam = document.createElement("button");
    vietnam.type = "button";
    vietnam.className = "button";
    vietnam.dataset.vnOpen = "";
    vietnam.textContent = "Ứng dụng Việt Nam";
    main.querySelector(".bdsg-work-page-heading")?.append(vietnam);
    writeFields();
  }
  function writeFields() {
    const target = document.querySelector("#connector-form");
    if (!target || target.elements.write_tools) return;
    const record = rows.find((r) => r.platform_id === selected);
    target
      .querySelector('button[type="submit"]')
      .insertAdjacentHTML(
        "beforebegin",
        `<label>Công cụ ghi được ${unitMode() ? "quản trị doanh nghiệp" : "chủ quản"} cấp rõ<textarea name="write_tools" rows="3" placeholder="Để trống nếu chỉ đọc">${esc((record?.write_tools || []).join("\n"))}</textarea></label><label class="connector-write-consent"><input type="checkbox" name="allow_writes" ${record?.write_tools?.length ? "checked" : ""}><span>Tôi cấp những công cụ ghi trên. Mỗi nội dung ghi cần được duyệt riêng trước khi thực hiện.</span></label>${unitMode() ? '<p class="muted">Không thêm công cụ ghi vào danh sách đọc. Công cụ được máy chủ trả về không tự được cấp quyền.</p>' : ""}`,
      );
  }
  async function open() {
    window.BDSGVietnam?.leave();
    const ticket = ++epoch;
    const token = capture();
    if (!canManage() && !(unitMode() && state.user)) {
      draw();
      return;
    }
    main.innerHTML =
      '<section class="bdsg-work-page"><p role="status">Đang tải cấu hình đầu nối…</p></section>';
    try {
      const result = await tool(canManage() ? "cau_hinh.dau_noi" : "nen_tang.ket_noi");
      if (ticket !== epoch || !current() || !live(token)) return;
      rows = Array.isArray(result.connections) ? result.connections : [];
      draw();
    } catch (error) {
      if (ticket === epoch && current() && live(token))
        main.innerHTML = `<section class="bdsg-work-page connector-page ${unitMode() ? "connector-unit" : ""}"><div class="error-state"><h1>Chưa mở được kết nối</h1><p>${unitMode() ? "Kiểm tra kết nối mạng và quyền trong đơn vị rồi thử lại." : esc(error.message)}</p><button class="button primary" type="button" data-connector-retry>Thử lại</button></div></section>`;
    }
  }
  async function action(button, toolName, id) {
    if (pending || !canManage()) return;
    const operation = ++mutation, token = capture();
    let refreshed = false;
    clearToken();
    pending = true;
    button.disabled = true;
    button.textContent = toolName === "cau_hinh.kiem_tra_dau_noi" ? "Đang kiểm tra MCP…" : "Đang ngắt…";
    document.querySelectorAll(".connector-actions button").forEach(element => { element.disabled = true; });
    const fields = $("#connector-fields");
    if (fields) fields.disabled = true;
    try {
      const result = await tool(toolName, { platform_id: id });
      if (operation !== mutation || !live(token)) return;
      pending = false;
      await open();
      refreshed = true;
      if (operation === mutation && live(token) && current()) toast(labels[result.state] || "Đã cập nhật đầu nối");
    } catch (error) {
      if (operation === mutation && live(token) && current()) toast(unitMode() ? "Chưa hoàn tất thao tác. Kiểm tra cấu hình và quyền của bạn rồi thử lại." : error.message);
    } finally {
      if (operation === mutation && live(token)) {
        pending = false;
        if (current() && !refreshed) draw();
      }
    }
  }
  document.addEventListener("click", async (event) => {
    if (event.target.closest("[data-connector-retry]")) return open();
    if (event.target.closest("[data-connector-login]")) {
      auth(() => open());
      return;
    }
    const edit = event.target.closest("[data-connector-edit]");
    if (edit) {
      if (pending || !canManage()) return;
      selected = edit.dataset.connectorEdit;
      draw();
      $("#connector-platform").focus();
      return;
    }
    const probe = event.target.closest("[data-connector-probe]");
    if (probe)
      return action(
        probe,
        "cau_hinh.kiem_tra_dau_noi",
        probe.dataset.connectorProbe,
      );
    const disconnect = event.target.closest("[data-connector-disconnect]");
    if (disconnect) {
      if (
        confirm(
          "Ngắt đầu nối này và xóa chứng thư đang lưu? Việc này không xóa dữ liệu tại nền tảng gốc.",
        )
      )
        return action(
          disconnect,
          "cau_hinh.ngat_dau_noi",
          disconnect.dataset.connectorDisconnect,
        );
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target.id === "connector-platform") {
      selected = event.target.value;
      draw();
    }
  });
  document.addEventListener("submit", async (event) => {
    if (event.target.getAttribute("id") !== "connector-form") return;
    event.preventDefault();
    if (pending || !canManage()) return;
    const data = Object.fromEntries(new FormData(event.target));
    if (unitMode()) {
      data.read_roles = [data.read_admin === "on" ? "admin" : null, data.read_member === "on" ? "member" : null].filter(Boolean);
      delete data.read_admin; delete data.read_member;
      if (!data.read_roles.length) {
        feedback("Chọn ít nhất một vai trò được dùng công cụ đọc.");
        event.target.elements.read_admin.focus();
        return;
      }
      const record = rows.find(row => row.platform_id === data.platform_id);
      if (!data.token && (!record?.has_token || !record.enabled || record.url !== data.url)) {
        feedback("Cần chứng thư mới khi khai báo, đổi endpoint hoặc kết nối lại.");
        event.target.elements.token.focus();
        return;
      }
    }
    data.write_tools = (data.write_tools || "")
      .split(/[\n,]/)
      .map((x) => x.trim())
      .filter(Boolean);
    data.allow_writes = data.allow_writes === "on";
    data.read_tools = data.read_tools
      .split(/[\n,]/)
      .map((x) => x.trim())
      .filter(Boolean);
    if (unitMode() && ((data.write_tools.length > 0) !== data.allow_writes || data.read_tools.some(name => data.write_tools.includes(name)))) {
      feedback("Cấp quyền ghi cần danh sách công cụ cụ thể và ô đồng ý. Công cụ ghi không được nằm trong danh sách đọc.");
      return;
    }
    pending = true;
    const operation = ++mutation, token = capture();
    clearToken();
    const fields = $("#connector-fields");
    if (fields) fields.disabled = true;
    feedback("Đang lưu cấu hình…");
    document.querySelectorAll(".connector-actions button").forEach(element => { element.disabled = true; });
    const button = event.target.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await tool("cau_hinh.luu_dau_noi", data);
      if (operation !== mutation || !live(token)) return;
      pending = false;
      selected = data.platform_id;
      await open();
      if (operation === mutation && live(token) && current()) feedback(
        "Đã lưu riêng tư. Chọn Kiểm tra MCP để xác minh khả năng bắt tay.",
      );
    } catch (error) {
      if (operation === mutation && live(token) && current()) feedback(unitMode() ? "Chưa lưu được cấu hình. Kiểm tra endpoint, chứng thư và quyền quản trị đơn vị rồi thử lại." : error.message);
    } finally {
      if (operation !== mutation || !live(token)) return;
      pending = false;
      if (fields?.isConnected) fields.disabled = false;
      if (button.isConnected) button.disabled = false;
      document
        .querySelectorAll("[data-connector-probe],[data-connector-disconnect]")
        .forEach((e) => {
          const id = e.dataset.connectorProbe || e.dataset.connectorDisconnect;
          e.disabled = !rows.find((r) => r.platform_id === id)?.enabled;
        });
    }
  });
  window.BDSGConnectors = {
    open,
    reset() {
      epoch++;
      mutation++;
      pending = false;
      clearToken();
      rows = [];
      selected = "";
    },
  };
  window.addEventListener("hashchange", () => { if (!current()) window.BDSGConnectors.reset(); });
})();
