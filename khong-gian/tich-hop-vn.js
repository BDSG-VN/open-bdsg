"use strict";
(() => {
  let providers = [],
    connections = [],
    selected = "",
    epoch = 0,
    pending = false;
  let latest = null,
    latestContext = null,
    active = false,
    readVersion = 0;
  const columnNames = {
    id: "Mã định danh",
    code: "Mã",
    name: "Tên",
    title: "Tiêu đề",
    bin: "BIN ngân hàng",
    shortName: "Tên viết tắt",
    status: "Trạng thái",
    amount: "Số tiền",
    amountPaid: "Đã thanh toán",
    amountRemaining: "Còn lại",
    orderCode: "Mã đơn",
    orderId: "Mã đơn",
    total: "Tổng",
    total_price: "Tổng tiền",
    basePrice: "Giá cơ bản",
    createdAt: "Ngày tạo",
    updated_time: "Cập nhật",
    transferSupported: "Hỗ trợ chuyển khoản",
    lookupSupported: "Hỗ trợ tra cứu",
    resultCode: "Mã kết quả",
    transId: "Mã giao dịch",
    responseTime: "Thời điểm phản hồi",
    display_name: "Tên hiển thị",
    open_id: "Mã người dùng",
    oa_id: "Mã OA",
    description: "Mô tả",
    inventory_item_name: "Tên vật tư",
    inventory_item_code: "Mã vật tư",
  };
  const current = () => location.hash === "#integrations";
  const names = {
    access_token: "Access token đã được nhà cung cấp cấp",
    client_id: "Client ID",
    api_key: "API key",
    checksum_key: "Checksum key",
    access_key: "Access key",
    secret_key: "Secret key",
    page_id: "Mã Facebook Page",
    graph_version: "Phiên bản Graph API đã chốt",
    retailer: "Tên gian hàng KiotViet",
    store: "Tên shop Sapo (phần trước .mysapo.net)",
    app_id: "App ID do MISA cấp",
    partner_code: "Mã đối tác MoMo",
    environment: "Môi trường",
  };
  const states = {
    configured: "Đã lưu, chưa kiểm tra",
    last_read_succeeded: "Lần đọc gần nhất đạt",
    revoked: "Đã ngắt",
    authorization_required: "Cần cấp lại quyền",
    permission_denied: "Thiếu quyền",
    provider_unavailable: "Nhà cung cấp chưa sẵn sàng",
    invalid_response: "Cần đối chiếu phản hồi",
    rate_limited: "Đang giới hạn lượt gọi",
    connection_changed: "Cấu hình đã thay đổi",
  };
  const operationFields = (provider, operation) => {
    if (provider === "payos")
      return [["payment_id", "Mã đơn hoặc mã link thanh toán", "text"]];
    if (provider === "momo")
      return [["order_id", "Mã đơn MoMo của đối tác", "text"]];
    if (provider === "zalo_zbs")
      return [["template_id", "Mã template đã được cấp quyền", "text"]];
    if (provider === "meta_pages" && operation === "conversations")
      return [["limit", "Số hội thoại tối đa", "number", 20]];
    if (provider === "tiktok_display" && operation === "videos")
      return [["limit", "Số video tối đa", "number", 20]];
    if (provider === "kiotviet" || provider === "amis_act")
      return [
        ["limit", "Số bản ghi tối đa", "number", 50],
        ["offset", "Vị trí bắt đầu", "number", 0],
      ];
    if (provider === "sapo_web" || provider === "haravan")
      return [
        ["limit", "Số bản ghi tối đa", "number", 50],
        ["page", "Trang", "number", 1],
      ];
    return [];
  };
  function valid(ticket, identity) {
    return (
      active &&
      current() &&
      ticket === epoch &&
      identity === state.user?.id &&
      state.user?.role === "quan-tri"
    );
  }
  function record() {
    return connections.find((row) => row.id === selected);
  }
  function contract() {
    const id =
      record()?.provider || document.querySelector("#vn-provider")?.value;
    return (
      providers.find((row) => row.id === id) ||
      providers.find((row) => !row.pending)
    );
  }
  function feedback(message) {
    const element = document.querySelector("#vn-feedback");
    if (element) element.textContent = message;
  }
  function configuration(providerId) {
    const row = record();
    const item =
      providers.find((provider) => provider.id === providerId) ||
      providers.find((provider) => !provider.pending);
    if (!item) return "";
    const fields = Object.keys(item.settings)
      .map((key) =>
        key === "environment"
          ? `<label>${esc(names[key])}<select name="setting-${esc(key)}"><option value="sandbox">Thử nghiệm MoMo</option><option value="production" ${row?.settings[key] === "production" ? "selected" : ""}>Vận hành thật MoMo</option></select></label>`
          : `<label>${esc(names[key] || key)}<input name="setting-${esc(key)}" value="${esc(row?.settings[key] || "")}" maxlength="160" required autocomplete="off"></label>`,
      )
      .join("");
    return `<p class="muted">${esc(item.requires)}</p>${fields}
      ${item.secrets.length ? `<fieldset><legend>Chứng thư riêng trên máy chủ</legend><p class="muted">${row?.has_credentials ? "Để trống toàn bộ để giữ khóa ở cùng tài khoản và cấu hình. Điền đủ các trường nếu thay khóa." : "Dùng khóa tích hợp chính thức; không dùng mật khẩu ngân hàng hay mã OTP."}</p>${item.secrets.map((key) => `<label>${esc(names[key] || key)}<input type="password" name="secret-${esc(key)}" maxlength="8192" autocomplete="new-password" ${row ? "" : "required"}></label>`).join("")}</fieldset>` : '<p class="muted">Đầu nối này chỉ đọc danh mục ngân hàng công khai; không cần khóa bên ngoài.</p>'}
      <fieldset><legend>Cho phép các thao tác đọc</legend>${Object.entries(
        item.operations,
      )
        .map(
          ([key, value]) =>
            `<label class="vn-check"><input type="checkbox" name="operation" value="${esc(key)}" ${row?.operations.includes(key) ? "checked" : ""}>${esc(value)}</label>`,
        )
        .join("")}</fieldset>
      <p class="muted"><a href="${esc(item.docs)}" target="_blank" rel="noopener noreferrer">Tài liệu nhà cung cấp</a> · Đối chiếu ${esc(item.checked_docs_date)}</p>`;
  }
  function form() {
    const row = record();
    const item = contract();
    return `<section class="panel connector-form vn-form"><h2>${row ? "Cấu hình kết nối" : "Thêm kết nối Việt Nam"}</h2>
      <form id="vn-config"><label>Nhà cung cấp<select id="vn-provider" name="provider" ${row ? "disabled" : ""}>${providers
        .filter((p) => !p.pending)
        .map(
          (p) =>
            `<option value="${esc(p.id)}" ${p.id === item?.id ? "selected" : ""}>${esc(p.name)}</option>`,
        )
        .join("")}</select></label>
      <label>Tên kết nối<input name="label" value="${esc(row?.label || "")}" maxlength="120" required placeholder="Ví dụ: Gian hàng Thanh Hoá" autocomplete="off"></label>
      <div id="vn-config-fields">${configuration(item?.id)}</div>
      <button class="button primary" type="submit" ${pending ? "disabled" : ""}>Lưu kết nối riêng tư</button>
      ${row ? '<button class="button" type="button" data-vn-new>Thêm kết nối khác</button>' : ""}</form>
      <p id="vn-feedback" role="status" aria-live="polite"></p></section>`;
  }
  function list() {
    return `<section class="panel connector-list" id="vn-connection-list"><h2>Kết nối của chủ quản</h2>${
      connections.length
        ? connections
            .map(
              (row) =>
                `<article class="connector-row"><div><strong>${esc(row.label)}</strong><span class="mini-tag">${esc(states[row.state] || "Cần kiểm tra")}</span></div><p>${esc(providers.find((p) => p.id === row.provider)?.name || row.provider)} · ${row.operations.length} quyền đọc${row.checked_at ? " · " + esc(date(row.checked_at)) : ""}</p><div class="connector-actions"><button class="button small" type="button" data-vn-edit="${esc(row.id)}">Cấu hình</button><button class="button small" type="button" data-vn-history="${esc(row.id)}">Lịch sử</button>${row.enabled ? `<button class="button small" type="button" data-vn-disconnect="${esc(row.id)}" ${pending ? "disabled" : ""}>Ngắt kết nối</button>` : ""}</div></article>`,
            )
            .join("")
        : '<div class="bdsg-work-empty"><h3>Chưa có tài khoản được kết nối.</h3><p>Chọn dịch vụ, lưu chứng thư và chỉ cấp những thao tác cần dùng.</p></div>'
    }<div id="vn-history" aria-live="polite"></div></section>`;
  }
  function readForm() {
    const rows = connections.filter((row) => row.enabled);
    if (!rows.length) return "";
    return `<section class="panel vn-read"><h2>Đọc dữ liệu có kiểm chứng</h2><p class="muted">Mỗi lần bấm chỉ đọc một trang. Chức năng này không gửi tin, tạo thanh toán, chuyển tiền hoặc phát hành hóa đơn.</p><form id="vn-read"><label>Kết nối<select id="vn-read-connection" name="connection">${rows.map((row) => `<option value="${esc(row.id)}">${esc(row.label)}</option>`).join("")}</select></label><label>Thao tác<select name="operation" id="vn-read-operation"></select></label><div id="vn-read-arguments"></div><button class="button primary" type="submit" ${pending ? "disabled" : ""}>Đọc một trang dữ liệu</button></form><div id="vn-result" role="status" aria-live="polite"></div></section>`;
  }
  function refreshReadOperations() {
    const row = connections.find(
      (item) =>
        item.id === document.querySelector("#vn-read-connection")?.value,
    );
    const select = document.querySelector("#vn-read-operation");
    const item = providers.find((provider) => provider.id === row?.provider);
    if (!row || !select || !item) return;
    select.innerHTML = row.operations
      .map(
        (operation) =>
          `<option value="${esc(operation)}">${esc(item.operations[operation])}</option>`,
      )
      .join("");
    refreshReadArguments();
  }
  function refreshReadArguments() {
    readVersion++;
    const row = connections.find(
      (item) =>
        item.id === document.querySelector("#vn-read-connection")?.value,
    );
    const operation = document.querySelector("#vn-read-operation")?.value;
    const target = document.querySelector("#vn-read-arguments");
    if (!row || !target) return;
    target.innerHTML = operationFields(row.provider, operation)
      .map(
        ([key, label, type, value]) =>
          `<label>${esc(label)}<input name="arg-${esc(key)}" type="${type}" value="${esc(value ?? "")}" ${type === "number" ? 'min="0" max="1000000000" step="1"' : 'maxlength="160"'} required></label>`,
      )
      .join("");
    latest = latestContext = null;
    const result = document.querySelector("#vn-result");
    if (result) result.replaceChildren();
  }
  function draw() {
    if (!current()) return;
    main.innerHTML = `<section class="bdsg-work-page"><div class="bdsg-work-page-heading"><div><h1>Kết nối ứng dụng Việt Nam.</h1><p>Mạng xã hội, thương mại, kế toán và trạng thái thanh toán trong cùng không gian.</p></div><button class="button" type="button" data-vn-mcp>Đầu nối BDSG / MCP</button></div><div class="connector-layout">${form()}${list()}</div>${readForm()}<section class="panel vn-pending"><h2>Dịch vụ cần xác nhận hợp đồng</h2><p class="muted">Đã nhận diện nhu cầu; chưa có công cụ nghiệp vụ được bật.</p><dl>${providers
      .filter((item) => item.pending)
      .map(
        (item) =>
          `<div><dt>${esc(item.name)}</dt><dd>${esc(item.requires)}</dd></div>`,
      )
      .join("")}</dl></section></section>`;
    refreshReadOperations();
  }
  async function open() {
    active = true;
    pending = false;
    const ticket = ++epoch,
      identity = state.user?.id;
    if (state.user?.role !== "quan-tri") {
      providers = [];
      connections = [];
      latest = latestContext = null;
      main.innerHTML =
        '<section class="bdsg-work-page"><h1>Tích hợp ứng dụng Việt Nam.</h1><p>Chủ quản đăng nhập để quản lý tài khoản và quyền dữ liệu.</p><button class="button primary" type="button" data-vn-login>Đăng nhập</button></section>';
      return;
    }
    main.innerHTML =
      '<section class="bdsg-work-page"><p role="status">Đang tải danh mục tích hợp…</p></section>';
    try {
      const result = await tool("tich_hop_vn.danh_sach");
      if (!valid(ticket, identity)) return;
      providers = result.providers;
      connections = result.connections;
      draw();
      if (!result.vault_configured) {
        document
          .querySelectorAll(
            "#vn-config input,#vn-config select,#vn-config button",
          )
          .forEach((element) => {
            element.disabled = true;
          });
        feedback(
          "Kho chứng thư đang chờ người vận hành cấu hình. Chưa thể lưu khóa hoặc gọi dịch vụ.",
        );
      }
    } catch (error) {
      if (valid(ticket, identity))
        main.innerHTML = `<section class="bdsg-work-page"><h1>Chưa tải được tích hợp.</h1><p role="alert">${esc(error.message)}</p><button class="button" data-vn-retry>Thử lại</button></section>`;
    }
  }
  function showResult(result) {
    const target = document.querySelector("#vn-result");
    if (!target) return;
    const columns = [
      ...new Set(result.items.flatMap((item) => Object.keys(item))),
    ].slice(0, 8);
    target.innerHTML = `<p>Đã đọc ${result.items.length} bản ghi lúc ${esc(date(result.observed_at))}${result.replayed ? " · Kết quả của yêu cầu trước" : ""}.</p>${result.items.length ? `<div class="vn-table-scroll" tabindex="0" role="region" aria-label="Dữ liệu đọc từ nhà cung cấp"><table><thead><tr>${columns.map((column) => `<th scope="col">${esc(columnNames[column] || column)}</th>`).join("")}</tr></thead><tbody>${result.items.map((item) => `<tr>${columns.map((column) => `<td>${esc(typeof item[column] === "boolean" ? (item[column] ? "Có" : "Không") : String(item[column] ?? ""))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "<p>Trang này chưa có bản ghi.</p>"}${result.next_arguments ? '<button class="button" type="button" data-vn-next>Đọc trang tiếp theo</button>' : ""}<p class="muted">Nguồn: ${esc(providers.find((item) => item.id === result.provider)?.name || result.provider)}. ${result.signature_verified ? "Đã kiểm chữ ký phản hồi. " : ""}Kết quả không tự ghi nhận thanh toán hoặc thay đổi sổ kế toán.</p>`;
  }
  function addScrollHint() {
    const table = document.querySelector("#vn-result .vn-table-scroll");
    if (!table) return;
    const hint = document.createElement("p");
    hint.className = "vn-scroll-hint muted";
    hint.textContent = "Cuộn ngang bảng để xem đầy đủ các cột.";
    table.before(hint);
  }
  async function readPage(context) {
    if (pending) return;
    const ticket = epoch,
      identity = state.user?.id,
      version = readVersion;
    pending = true;
    document
      .querySelectorAll("#vn-read button,[data-vn-next]")
      .forEach((button) => {
        button.disabled = true;
      });
    try {
      const result = await tool("tich_hop_vn.doc", context);
      if (!valid(ticket, identity) || version !== readVersion) return;
      latest = result;
      latestContext = context;
      if (!result.replayed) {
        const row = connections.find((item) => item.id === context.id);
        if (row) {
          row.state = "last_read_succeeded";
          row.checked_at = result.observed_at;
          const summary = document.querySelector("#vn-connection-list");
          if (summary) summary.outerHTML = list();
        }
      }
      showResult(result);
      addScrollHint();
    } catch (error) {
      if (valid(ticket, identity) && version === readVersion) {
        const target = document.querySelector("#vn-result");
        if (target)
          target.textContent =
            error.message +
            " Kiểm tra quyền, mã giao dịch hoặc thử một yêu cầu mới khi dịch vụ sẵn sàng.";
      }
    } finally {
      pending = false;
      if (valid(ticket, identity))
        document
          .querySelectorAll("#vn-read button,[data-vn-next]")
          .forEach((button) => {
            button.disabled = false;
          });
    }
  }
  document.addEventListener("click", async (event) => {
    if (event.target.closest("[data-vn-open],[data-vn-retry]")) return open();
    if (event.target.closest("[data-vn-mcp]")) {
      epoch++;
      return window.BDSGConnectors?.open();
    }
    if (event.target.closest("[data-vn-login]")) return auth(() => open());
    if (event.target.closest("[data-vn-new]")) {
      selected = "";
      return draw();
    }
    const edit = event.target.closest("[data-vn-edit]");
    if (edit) {
      selected = edit.dataset.vnEdit;
      draw();
      document.querySelector("#vn-config input")?.focus();
      return;
    }
    const next = event.target.closest("[data-vn-next]");
    if (next && latest?.next_arguments && latestContext)
      return readPage({
        ...latestContext,
        arguments: latest.next_arguments,
        request_key: crypto.randomUUID(),
      });
    const disconnect = event.target.closest("[data-vn-disconnect]");
    if (disconnect && !pending) {
      const row = connections.find(
        (item) => item.id === disconnect.dataset.vnDisconnect,
      );
      if (
        !row ||
        !confirm(
          `Ngắt kết nối “${row.label}” và bỏ khóa đang lưu? Dữ liệu gốc tại nhà cung cấp vẫn được giữ.`,
        )
      )
        return;
      const ticket = epoch,
        identity = state.user?.id;
      pending = true;
      disconnect.disabled = true;
      try {
        await tool("tich_hop_vn.ngat", {
          id: row.id,
          expected_revision: row.revision,
        });
        if (valid(ticket, identity)) {
          latest = latestContext = null;
          pending = false;
          await open();
        }
      } catch (error) {
        if (valid(ticket, identity)) toast(error.message);
      } finally {
        if (valid(ticket, identity)) {
          pending = false;
          if (disconnect.isConnected) disconnect.disabled = false;
        }
      }
      return;
    }
    const history = event.target.closest("[data-vn-history]");
    if (history) {
      const ticket = epoch,
        identity = state.user?.id;
      try {
        const result = await tool("tich_hop_vn.lich_su", {
          id: history.dataset.vnHistory,
        });
        if (!valid(ticket, identity)) return;
        const target = document.querySelector("#vn-history");
        if (target)
          target.innerHTML = `<h3>Lượt đọc gần nhất</h3>${result.runs.length ? `<ul>${result.runs.map((run) => `<li>${esc(date(run.started))} · ${esc(run.operation)} · ${esc(run.state)} · ${run.records} bản ghi</li>`).join("")}</ul>` : "<p>Chưa có lượt đọc.</p>"}`;
      } catch (error) {
        if (valid(ticket, identity)) toast(error.message);
      }
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target.id === "vn-provider") {
      document.querySelector("#vn-config-fields").innerHTML = configuration(
        event.target.value,
      );
    }
    if (event.target.id === "vn-read-connection") refreshReadOperations();
    if (event.target.id === "vn-read-operation") refreshReadArguments();
  });
  document.addEventListener("submit", async (event) => {
    if (event.target.id === "vn-read") {
      event.preventDefault();
      const form = new FormData(event.target),
        row = connections.find((item) => item.id === form.get("connection"));
      if (!row) return;
      const args = {};
      operationFields(row.provider, form.get("operation")).forEach(
        ([key, , type]) => {
          args[key] =
            type === "number"
              ? Number(form.get("arg-" + key))
              : form.get("arg-" + key);
        },
      );
      return readPage({
        id: row.id,
        operation: form.get("operation"),
        arguments: args,
        request_key: crypto.randomUUID(),
      });
    }
    if (event.target.id !== "vn-config") return;
    event.preventDefault();
    if (pending) return;
    const row = record(),
      item = providers.find(
        (provider) =>
          provider.id ===
          (row?.provider || event.target.elements.provider.value),
      );
    if (!item) return;
    const values = new FormData(event.target),
      settings = {},
      credentials = {};
    Object.keys(item.settings).forEach((key) => {
      settings[key] = values.get("setting-" + key);
    });
    item.secrets.forEach((key) => {
      credentials[key] = values.get("secret-" + key);
    });
    const filled = Object.values(credentials).filter(Boolean).length;
    if (filled && filled !== item.secrets.length)
      return feedback(
        "Điền đủ bộ chứng thư hoặc để trống toàn bộ để giữ bộ cũ.",
      );
    const operations = values.getAll("operation");
    if (!operations.length)
      return feedback("Chọn ít nhất một thao tác đọc được cho phép.");
    const body = {
      provider: item.id,
      label: values.get("label"),
      settings,
      operations,
    };
    if (filled || !item.secrets.length) body.credentials = credentials;
    if (row) {
      body.id = row.id;
      body.expected_revision = row.revision;
    }
    event.target.querySelectorAll('input[type="password"]').forEach((input) => {
      input.value = "";
    });
    const ticket = epoch,
      identity = state.user?.id;
    pending = true;
    feedback("Đang lưu cấu hình…");
    event.target.querySelector('button[type="submit"]').disabled = true;
    try {
      const saved = await tool("tich_hop_vn.luu", body);
      if (!valid(ticket, identity)) return;
      selected = saved.id;
      pending = false;
      await open();
      feedback(
        "Đã lưu riêng tư. Lưu cấu hình chưa gọi mạng; chọn thao tác để kiểm tra bằng một lượt đọc.",
      );
    } catch (error) {
      if (valid(ticket, identity)) feedback(error.message);
    } finally {
      Object.keys(credentials).forEach((key) => {
        credentials[key] = "";
      });
      pending = false;
      if (valid(ticket, identity)) {
        const button = document.querySelector(
          '#vn-config button[type="submit"]',
        );
        if (button) button.disabled = false;
      }
    }
  });
  window.BDSGVietnam = {
    open,
    leave() {
      active = false;
      epoch++;
    },
    reset() {
      active = false;
      epoch++;
      providers = [];
      connections = [];
      selected = "";
      latest = latestContext = null;
      pending = false;
    },
  };
})();
