"use strict";
(() => {
  let rows = [],
    selected = "",
    pending = false,
    epoch = 0;
  const labels = {
    "da-khai-bao": "Đã khai báo",
    "da-xac-minh": "MCP có phản hồi",
    "loi-ket-noi": "Cần kiểm tra kết nối",
    "da-ngat": "Đã ngắt",
  };
  const current = () => location.hash === "#integrations";
  const name = (id) => state.products.find((p) => p.id === id)?.name || id;
  function feedback(message) {
    const element = $("#connector-feedback");
    if (element) element.textContent = message;
  }
  function form() {
    const record = rows.find((r) => r.platform_id === selected);
    return `<section class="panel connector-form"><h2>${record ? "Cập nhật đầu nối" : "Khai báo đầu nối MCP"}</h2><p class="muted">Nhập endpoint và tên công cụ do quản trị nền tảng cung cấp. Chứng thư lưu riêng trên máy chủ; không thể xem lại.</p><form id="connector-form"><label>Nền tảng<select name="platform_id" id="connector-platform" required><option value="">Chọn nền tảng BDSG</option>${state.products.map((p) => `<option value="${esc(p.id)}" ${selected === p.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></label><label>Endpoint MCP<input name="url" type="url" required maxlength="1000" value="${esc(record?.url || "")}" placeholder="https://ten-nen-tang.bdsg.vn/mcp" autocomplete="off"></label><label>Chứng thư Bearer<input name="token" type="password" maxlength="4096" autocomplete="off" placeholder="${record?.has_token ? "Để trống để giữ chứng thư tại cùng endpoint" : "Nhập chứng thư được cấp cho Thanh Hoá"}"></label><label>Công cụ đọc được chủ quản cho phép<textarea name="read_tools" rows="4" placeholder="Mỗi dòng một tên công cụ, có thể để trống để kiểm tra trước">${esc((record?.read_tools || []).join("\n"))}</textarea></label><p class="muted">Lưu không tự gửi yêu cầu. “Kiểm tra MCP” chỉ bắt tay và đọc danh sách công cụ; không chạy nghiệp vụ. Chỉ chủ quản được gọi công cụ đọc đã khai báo.</p><button class="button primary" type="submit" ${pending ? "disabled" : ""}>Lưu cấu hình đầu nối</button></form><p id="connector-feedback" class="connector-feedback" role="status" aria-live="polite"></p></section>`;
  }
  function list() {
    return `<section class="panel connector-list"><h2>Đầu nối đã khai báo</h2>${rows.length ? rows.map((r) => `<article class="connector-row"><div><strong>${esc(name(r.platform_id))}</strong><span class="mini-tag">${esc(labels[r.state] || r.state)}</span></div><code>${esc(r.url)}</code><p>${r.has_token ? "Có chứng thư riêng" : "Không giữ chứng thư hoạt động"} · ${(r.read_tools || []).length} công cụ đọc${r.checked_at ? " · Kiểm tra " + esc(date(r.checked_at)) : ""}</p>${r.discovered_tools?.length ? `<details><summary>Công cụ máy chủ đã trả về${r.tools_complete ? "" : " (danh sách một phần)"}</summary><pre>${esc(r.discovered_tools.join("\n"))}</pre><p>Danh sách trả về không tự cấp quyền. Chỉ thêm công cụ đọc đã được bên quản trị xác nhận.</p></details>` : ""}<div class="connector-actions"><button class="button small" type="button" data-connector-edit="${esc(r.platform_id)}">Cập nhật</button><button class="button small" type="button" data-connector-probe="${esc(r.platform_id)}" ${!r.enabled || pending ? "disabled" : ""}>Kiểm tra MCP</button>${r.enabled ? `<button class="button small" type="button" data-connector-disconnect="${esc(r.platform_id)}" ${pending ? "disabled" : ""}>Ngắt kết nối</button>` : ""}</div></article>`).join("") : '<div class="bdsg-work-empty"><h3>Chưa có đầu nối nghiệp vụ.</h3><p>Website các nền tảng vẫn mở được. Khai báo MCP khi đã có endpoint và chứng thư hợp lệ.</p></div>'}<p class="muted">“MCP có phản hồi” xác nhận initialize và tools/list tại thời điểm kiểm tra; không chứng minh công cụ nghiệp vụ hoặc đồng bộ dữ liệu đã hoạt động.</p></section>`;
  }
  function draw() {
    if (!current()) return;
    main.innerHTML = `<section class="bdsg-work-page"><div class="bdsg-work-page-heading"><div><h1>Đưa nền tảng vào công việc.</h1><p>Khai báo, kiểm tra và quản lý quyền kết nối MCP của từng mô-đun BDSG.</p></div><a class="button" href="#modules">Thư viện mô-đun ${icon("grid")}</a></div>${state.user?.role === "quan-tri" ? `<div class="connector-layout">${form()}${list()}</div>` : `<section class="panel connector-intro"><div class="app-icon">${icon("lock")}</div><h2>Chủ quản quản lý đầu nối.</h2><p>Endpoint, chứng thư và quyền công cụ được cấu hình trong không gian riêng. Danh mục mô-đun vẫn có thể xem công khai.</p><button class="button primary" type="button" data-connector-login>Đăng nhập để quản lý kết nối</button><div class="connector-principles"><span>HTTPS trong miền BDSG</span><span>Chứng thư không hiển thị lại</span><span>Quyền đọc cụ thể theo công cụ</span></div></section>`}</section>`;
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
        `<label>Công cụ ghi được chủ quản cấp rõ<textarea name="write_tools" rows="3" placeholder="Để trống nếu chỉ đọc">${esc((record?.write_tools || []).join("\n"))}</textarea></label><label class="connector-write-consent"><input type="checkbox" name="allow_writes" ${record?.write_tools?.length ? "checked" : ""}>Tôi cấp những công cụ ghi trên. Agent cần tạo dự thảo và được duyệt trước khi thực hiện.</label>`,
      );
  }
  async function open() {
    window.BDSGVietnam?.leave();
    const ticket = ++epoch;
    if (state.user?.role !== "quan-tri") {
      draw();
      return;
    }
    main.innerHTML =
      '<section class="bdsg-work-page"><p>Đang tải cấu hình đầu nối…</p></section>';
    try {
      const result = await tool("cau_hinh.dau_noi");
      if (ticket !== epoch || !current()) return;
      rows = result.connections;
      draw();
    } catch (error) {
      if (ticket === epoch && current())
        main.innerHTML = `<div class="error-state">${esc(error.message)}</div>`;
    }
  }
  async function action(button, toolName, id) {
    if (pending) return;
    pending = true;
    button.disabled = true;
    try {
      const result = await tool(toolName, { platform_id: id });
      await open();
      toast(labels[result.state] || "Đã cập nhật đầu nối");
    } catch (error) {
      toast(error.message);
    } finally {
      pending = false;
      if (current()) draw();
    }
  }
  document.addEventListener("click", async (event) => {
    if (event.target.closest("[data-connector-login]")) {
      auth(() => open());
      return;
    }
    const edit = event.target.closest("[data-connector-edit]");
    if (edit) {
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
    if (event.target.id !== "connector-form") return;
    event.preventDefault();
    if (pending) return;
    const data = Object.fromEntries(new FormData(event.target));
    data.write_tools = (data.write_tools || "")
      .split(/[\n,]/)
      .map((x) => x.trim())
      .filter(Boolean);
    data.allow_writes = data.allow_writes === "on";
    data.read_tools = data.read_tools
      .split(/[\n,]/)
      .map((x) => x.trim())
      .filter(Boolean);
    pending = true;
    const button = event.target.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await tool("cau_hinh.luu_dau_noi", data);
      event.target.elements.token.value = "";
      selected = data.platform_id;
      await open();
      feedback(
        "Đã lưu riêng tư. Chọn Kiểm tra MCP để xác minh khả năng bắt tay.",
      );
    } catch (error) {
      feedback(error.message);
    } finally {
      pending = false;
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
      rows = [];
      selected = "";
    },
  };
})();
