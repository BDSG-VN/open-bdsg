"use strict";
(() => {
  const draft = {
    prompt: "",
    module_ids: [],
    template: "de-xuat-giai-phap",
    project_id: "",
    allow_module_reads: false,
  };
  let projects = [];
  let revision = 0;
  let moduleCache = [];
  let currentTask = null;
  let busy = false;
  let pollBusy = false;
  let latestModel = { configured: false };
  const activeStates = new Set(["queued", "running", "cancelling"]);
  const labels = {
    queued: "Đang chờ",
    running: "Đang thực hiện",
    completed: "Hoàn thành",
    cancelled: "Đã dừng",
    cancelling: "Đang dừng",
    failed: "Cần kiểm tra",
    interrupted: "Bị gián đoạn",
    pending: "Chưa bắt đầu",
    done: "Hoàn tất",
  };
  const templates = [
    {
      id: "de-xuat-giai-phap",
      icon: "briefcase",
      title: "Đề xuất giải pháp",
      text: "Từ một nhu cầu kinh doanh đến bộ nền tảng phù hợp.",
      prompt:
        "Đề xuất các nền tảng BDSG phù hợp để phát triển kinh doanh bất động sản tại Thanh Hoá, kèm thứ tự triển khai và những kết nối cần chuẩn bị.",
    },
    {
      id: "kiem-tra-ket-noi",
      icon: "link",
      title: "Kiểm tra kết nối",
      text: "Xem mô-đun nào đã khai báo công cụ và quyền kết nối.",
      prompt:
        "Kiểm tra tình trạng khai báo kết nối các mô-đun BDSG tại Thanh Hoá; phân biệt liên kết web với đầu nối MCP và chỉ rõ phần còn thiếu.",
    },
    {
      id: "tong-quan",
      icon: "grid",
      title: "Tổng quan hệ sinh thái",
      text: "Lập bản đồ các nền tảng và lĩnh vực có thể ứng dụng.",
      prompt:
        "Tổng hợp các nền tảng BDSG hiện có theo lĩnh vực, mô tả vai trò và đề xuất cách phối hợp chúng trong không gian Thanh Hoá.",
    },
  ];

  function routeIs(name) {
    return (location.hash || "#work") === "#" + name;
  }
  function unwrap(value) {
    if (!value.ok)
      throw new Error(value.ly_do || "Chưa hoàn tất được thao tác.");
    return value.ket_qua;
  }
  function stamp(value) {
    return value ? date(value) : "—";
  }
  function status(value) {
    return `<span class="bdsg-job-status bdsg-job-status-${esc(value)}"><span></span>${esc(labels[value] || value)}</span>`;
  }
  function moduleName(id) {
    return moduleCache.find((m) => m.id === id)?.name || id;
  }
  function errorBox(message) {
    return `<div class="bdsg-work-error" role="alert">${esc(message)}</div>`;
  }
  function empty(title, text) {
    return `<div class="bdsg-work-empty">${icon("route")}<h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
  }
  function providerName(provider) {
    return (
      { openai: "OpenAI", anthropic: "Claude", bdsg: "BDSG" }[provider] ||
      "API mô hình"
    );
  }
  function modeLabel(model) {
    return model?.configured
      ? `${esc(providerName(model.provider))} · ${esc(model.model || "Đã cấu hình")}`
      : "Quy trình có kịch bản · API mô hình chưa cấu hình";
  }
  function taskMode(task) {
    return task.mode === "quy-trinh" ? "Quy trình" : "API mô hình";
  }
  async function getModules() {
    const data = state.user
      ? await tool("mo_dun.danh_sach")
      : await api("/api/modules");
    moduleCache = data.modules || [];
    return moduleCache;
  }
  async function getModel() {
    try {
      latestModel = await api("/api/model");
      return latestModel;
    } catch (_) {
      return { configured: false };
    }
  }
  function setupButton() {
    return `<button type="button" class="bdsg-model-setup" data-bdsg-model-setup>${icon("spark")}Cấu hình mô hình AI</button>`;
  }
  async function openModelSettings() {
    if (state.user?.role !== "quan-tri") {
      toast("Chỉ chủ quản có quyền cấu hình mô hình AI.");
      return;
    }
    if (!$("#bdsg-model-dialog")) {
      const dialog = document.createElement("dialog");
      dialog.id = "bdsg-model-dialog";
      dialog.className = "bdsg-model-dialog";
      dialog.innerHTML = `<form id="bdsg-model-form"><div class="dialog-heading"><span class="eyebrow">CẤU HÌNH RIÊNG TƯ</span><button type="button" class="icon-button" aria-label="Đóng cấu hình mô hình" data-bdsg-model-close>${icon("close")}</button></div><h2>Kết nối mô hình của bạn.</h2><p class="bdsg-model-description">Khóa chỉ được lưu riêng trên máy chủ Thanh Hoá và gửi tới nhà cung cấp bạn chọn. Khóa không xuất hiện trong chat, GitHub hoặc phản hồi cấu hình. Nội dung giao việc, ngữ cảnh và kết quả công cụ có thể được gửi tới nhà cung cấp đã chọn để xử lý. Cấu hình mới áp dụng cho lượt chạy mới.</p><label>Nhà cung cấp<select name="provider" id="bdsg-model-provider"><option value="openai">OpenAI</option><option value="anthropic">Claude</option><option value="bdsg">BDSG</option></select></label><label>Tên mô hình<input name="model" type="text" required maxlength="150" autocomplete="off" placeholder="Tên mô hình được cấp trong tài khoản API"></label><label id="bdsg-model-base-label" hidden>Địa chỉ API BDSG<input name="base_url" type="url" maxlength="500" placeholder="https://llm.bdsg.vn/v1" autocomplete="off"></label><label>Khóa API mới<input name="api_key" type="password" required maxlength="2048" autocomplete="off" spellcheck="false" placeholder="Tự nhập khóa API tại đây"></label><p class="bdsg-model-description">Mỗi lần lưu cần nhập khóa mới hoặc nhập lại khóa hiện tại. Không thể xem lại khóa đã lưu. Việc dùng API có thể phát sinh phí theo tài khoản nhà cung cấp.</p><p id="bdsg-model-error" class="form-error" role="alert"></p><button type="submit" class="button primary full">Lưu cấu hình mô hình ${icon("lock")}</button></form>`;
      document.body.append(dialog);
      dialog.insertAdjacentHTML(
        "beforeend",
        '<button type="button" class="button connector-model-disable" id="model-disable" data-bdsg-model-disable>Tắt AI và xóa khóa đã lưu</button>',
      );
      dialog.addEventListener("close", () => $("#bdsg-model-form").reset());
    }
    await getModel();
    const form = $("#bdsg-model-form");
    form.reset();
    form.elements.provider.value = ["openai", "anthropic", "bdsg"].includes(
      latestModel.provider,
    )
      ? latestModel.provider
      : "openai";
    form.elements.model.value = latestModel.model || "";
    $("#bdsg-model-base-label").hidden =
      form.elements.provider.value !== "bdsg";
    $("#bdsg-model-error").textContent = "";
    $("#model-disable").hidden = !latestModel.configured;
    $("#bdsg-model-dialog").showModal();
  }
  function listMarkup(rows, compact = false) {
    if (!rows.length)
      return empty(
        "Công việc đầu tiên bắt đầu từ một nhu cầu.",
        "Giao một việc cụ thể, chọn mô-đun và theo dõi kết quả tại đây.",
      );
    return `<div class="bdsg-job-list ${compact ? "bdsg-job-list-compact" : ""}">${rows.map((row) => `<a class="bdsg-job-row" href="#task/${encodeURIComponent(row.id)}"><span class="bdsg-job-glyph">${icon("route")}</span><div><strong>${esc(row.title || row.prompt || "Công việc")}</strong><small>${esc(stamp(row.updated || row.created))} · ${taskMode(row)}</small></div>${status(row.status)}${icon("arrow")}</a>`).join("")}</div>`;
  }
  function modulePicker() {
    return `<details class="bdsg-module-picker"><summary>${icon("grid")}<span>Chọn mô-đun${draft.module_ids.length ? ` (${draft.module_ids.length})` : ""}</span><small>Tuỳ chọn</small></summary><div class="bdsg-module-options">${moduleCache.map((m) => `<label><input type="checkbox" name="bdsg-module" value="${esc(m.id)}" ${draft.module_ids.includes(m.id) ? "checked" : ""}><span>${esc(m.name)}</span></label>`).join("")}</div><p>Nếu chưa chọn, quy trình sẽ đối chiếu nhu cầu với danh mục. Chọn mô-đun không tự cấp quyền truy cập dữ liệu.</p></details>`;
  }
  async function getProjects() {
    projects =
      state.user && ["operator", "quan-tri"].includes(state.user.role)
        ? (await tool("du_an.danh_sach")).projects.filter((p) => !p.archived)
        : [];
    draft.project_id = window.BDSGProjects?.getSelected() || "";
    if (!projects.some((p) => p.id === draft.project_id)) {
      draft.project_id = "";
      window.BDSGProjects?.clearSelected();
    }
    draft.allow_module_reads = false;
  }
  function scopePicker() {
    return `<div class="bdsg-project-scope"><label>Dự án công việc<select id="bdsg-task-project"><option value="">Công việc độc lập</option>${projects.map((p) => `<option value="${esc(p.id)}" ${draft.project_id === p.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></label><a href="#projects">Quản lý dự án →</a><label class="bdsg-read-consent"><input type="checkbox" id="bdsg-allow-reads" disabled><span>Cho phép agent đọc MCP từ những mô-đun đã chọn. Nội dung đọc được có thể gửi tới nhà cung cấp AI đã cấu hình.</span></label><small id="bdsg-read-note"></small></div>`;
  }
  function refreshConsent() {
    const box = $("#bdsg-allow-reads"),
      note = $("#bdsg-read-note");
    if (!box) return;
    const granted = moduleCache.some(
      (m) =>
        draft.module_ids.includes(m.id) &&
        m.mcp?.state === "da-xac-minh" &&
        m.mcp?.read_tools?.length,
    );
    box.disabled = !(
      state.user?.role === "quan-tri" &&
      latestModel.configured &&
      granted
    );
    if (box.disabled) draft.allow_module_reads = false;
    box.checked = draft.allow_module_reads;
    note.textContent = box.disabled
      ? "Cần chủ quản, mô hình AI và mô-đun có công cụ đọc MCP đã xác minh. Mặc định không đọc dữ liệu bên ngoài."
      : "Chỉ cấp cho tác vụ này; không cấp công cụ ghi. Quyền được kiểm lại trước mỗi lần gọi.";
  }
  async function home() {
    const ticket = ++revision;
    main.innerHTML = `<section class="bdsg-work-home"><div class="bdsg-work-intro"><span class="bdsg-work-kicker">BDSG THANH HOÁ · KHÔNG GIAN THỰC THI</span><h1>Bạn muốn phát triển điều gì<br>ở <em>Thanh Hoá?</em></h1><p>Giao một mục tiêu. Kết nối đúng mô-đun. Theo dõi công việc đến kết quả.</p></div><div id="bdsg-composer-slot" class="bdsg-composer-loading">Đang mở không gian giao việc…</div></section>`;
    try {
      const [, model] = await Promise.all([
        getModules(),
        getModel(),
        getProjects(),
      ]);
      if (ticket !== revision || !routeIs("work")) return;
      main.innerHTML = `<section class="bdsg-work-home"><div class="bdsg-work-intro"><span class="bdsg-work-kicker">BDSG THANH HOÁ · KHÔNG GIAN THỰC THI</span><h1>Bạn muốn phát triển điều gì<br>ở <em>Thanh Hoá?</em></h1><p>Giao một mục tiêu. Kết nối đúng mô-đun. Theo dõi công việc đến kết quả.</p></div><form id="bdsg-task-create" class="bdsg-task-composer"><label class="sr-only" for="bdsg-task-prompt">Mục tiêu công việc</label><textarea id="bdsg-task-prompt" name="prompt" minlength="10" maxlength="4000" rows="3" required placeholder="Ví dụ: Phối hợp các nền tảng BDSG để phát triển kinh doanh tại Thanh Hoá…">${esc(draft.prompt)}</textarea><div class="bdsg-composer-bottom">${modulePicker()}<button class="bdsg-run-button" type="submit" aria-label="Bắt đầu công việc">${icon("arrow")}<span>Bắt đầu</span></button></div><div class="bdsg-composer-mode">${icon("lock")}<span>${modeLabel(model)}</span><small>Thực thi trong phạm vi quyền được cấp</small></div></form><div class="bdsg-task-templates">${templates.map((t) => `<button type="button" data-bdsg-template="${t.id}" class="bdsg-task-template">${icon(t.icon)}<strong>${t.title}</strong><span>${t.text}</span>${icon("arrow")}</button>`).join("")}</div><div class="bdsg-work-footnote"><span class="bdsg-work-live-dot"></span>${moduleCache.length} mô-đun trong hệ sinh thái<a href="#modules">Khám phá mô-đun ${icon("arrow")}</a></div><section class="bdsg-work-recent"><div class="bdsg-work-section-heading"><h2>Công việc gần đây</h2><a href="#tasks">Xem tất cả ${icon("arrow")}</a></div><div id="bdsg-recent-jobs">${state.user ? "Đang tải công việc…" : `<div class="bdsg-work-login-note">${icon("lock")}<p>Công việc và kết quả của bạn được lưu trong không gian riêng.</p><button type="button" class="button" data-bdsg-login>Đăng nhập để làm việc</button></div>`}</div></section></section>`;
      main
        .querySelector(".bdsg-work-footnote")
        .insertAdjacentHTML("beforeend", setupButton());
      $("#bdsg-task-create").insertAdjacentHTML("beforeend", scopePicker());
      refreshConsent();
      if (state.user) {
        const data = unwrap(await api("/api/tasks"));
        const slot = $("#bdsg-recent-jobs");
        if (ticket === revision && slot)
          slot.innerHTML = listMarkup((data.tasks || []).slice(0, 4), true);
      }
    } catch (e) {
      if (ticket === revision) main.innerHTML += errorBox(e.message);
    }
  }
  async function tasks() {
    const ticket = ++revision;
    main.innerHTML = `<section class="bdsg-work-page"><div class="bdsg-work-page-heading"><div><span class="eyebrow">KHÔNG GIAN CỦA BẠN</span><h1>Công việc & kết quả</h1><p>Tiếp tục những việc đang làm và xem lại các sản phẩm đã tạo.</p></div><a class="button primary" href="#work">${icon("plus")}Giao việc mới</a></div><div id="bdsg-jobs-slot">${state.user ? "Đang tải công việc…" : `<div class="bdsg-work-login-note">${icon("lock")}<p>Đăng nhập để xem công việc trong phạm vi quyền của bạn.</p><button class="button primary" data-bdsg-login>Đăng nhập không gian</button></div>`}</div></section>`;
    if (!state.user) return;
    try {
      const data = unwrap(await api("/api/tasks"));
      if (ticket === revision && routeIs("tasks"))
        $("#bdsg-jobs-slot").innerHTML = listMarkup(data.tasks || []);
    } catch (e) {
      if (ticket === revision)
        $("#bdsg-jobs-slot").innerHTML = errorBox(e.message);
    }
  }
  function inlineMarkdown(text) {
    return esc(text)
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`\n]+)`/g, "<code>$1</code>");
  }
  function markdown(text) {
    const lines = String(text || "").split(/\r?\n/);
    let code = false,
      output = "",
      table = false;
    for (const line of lines) {
      if (line.startsWith("```")) {
        if (table) {
          output += "</tbody></table></div>";
          table = false;
        }
        output += code ? "</code></pre>" : "<pre><code>";
        code = !code;
        continue;
      }
      if (code) {
        output += esc(line) + "\n";
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line)) {
        if (/^\s*\|[\s:|\-]+\|\s*$/.test(line)) continue;
        if (!table) {
          output += '<div class="bdsg-markdown-table"><table><tbody>';
          table = true;
        }
        output +=
          "<tr>" +
          line
            .trim()
            .slice(1, -1)
            .split(/(?<!\\)\|/)
            .map(
              (cell) =>
                `<td>${inlineMarkdown(cell.trim().replace(/\\\|/g, "|"))}</td>`,
            )
            .join("") +
          "</tr>";
        continue;
      }
      if (table) {
        output += "</tbody></table></div>";
        table = false;
      }
      const heading = line.match(/^(#{1,4})\s+(.+)$/);
      if (heading) {
        const level = Math.min(heading[1].length + 1, 5);
        output += `<h${level}>${inlineMarkdown(heading[2])}</h${level}>`;
      } else if (/^\s*[-*]\s+/.test(line))
        output += `<p class="bdsg-markdown-bullet">${inlineMarkdown(line.replace(/^\s*[-*]\s+/, ""))}</p>`;
      else if (line.trim()) output += `<p>${inlineMarkdown(line)}</p>`;
    }
    if (code) output += "</code></pre>";
    if (table) output += "</tbody></table></div>";
    return output;
  }
  function traceMarkup(task) {
    const steps = (task.steps || []).filter(
      (s) => !s.run || s.run === task.run,
    );
    return `<div class="bdsg-trace-heading"><span>${icon("activity")}Tiến trình thực thi</span>${status(task.status)}</div><ol class="bdsg-task-steps">${steps.map((s, i) => `<li class="bdsg-step-${esc(s.status)}"><span class="bdsg-step-number">${["completed", "done"].includes(s.status) ? icon("check") : i + 1}</span><div><strong>${esc(s.name)}</strong><small>${esc(labels[s.status] || s.status)}${s.finished ? " · " + esc(stamp(s.finished)) : ""}</small>${s.summary ? `<p>${esc(s.summary)}</p>` : ""}${s.tool ? `<code>${esc(s.tool)}</code>` : ""}</div></li>`).join("") || '<li class="bdsg-trace-empty">Đang chuẩn bị các bước thực thi.</li>'}</ol><div class="bdsg-task-events">${(
      task.events || []
    )
      .slice(-8)
      .reverse()
      .map(
        (e) =>
          `<div><span></span><p>${esc(e.message)}</p><time>${esc(stamp(e.created))}</time></div>`,
      )
      .join("")}</div>`;
  }
  function artifactMarkup(task) {
    const artifacts = task.artifacts || [];
    if (!artifacts.length)
      return empty(
        activeStates.has(task.status)
          ? "Kết quả sẽ xuất hiện tại đây."
          : "Chưa có sản phẩm đầu ra.",
        "Chỉ hiển thị sản phẩm đã được tác vụ tạo và lưu lại.",
      );
    return artifacts
      .map(
        (a) =>
          `<article class="bdsg-task-artifact"><div class="bdsg-artifact-heading"><div>${icon("briefcase")}<span><strong>${esc(a.title || a.name || "Báo cáo")}</strong><small>${esc(stamp(a.created))}${a.run ? ` · Lượt ${esc(a.run)}` : ""}</small></span></div><button type="button" class="button" data-bdsg-download="${esc(a.id)}">Tải .md ${icon("arrow")}</button></div><div class="bdsg-task-markdown">${markdown(a.content)}</div></article>`,
      )
      .join("");
  }
  function conversationMarkup(task) {
    return (task.messages || [])
      .map(
        (m) =>
          `<article class="bdsg-task-message ${m.role === "user" || m.role === "nguoi" ? "bdsg-task-message-user" : ""}"><div><strong>${m.role === "user" || m.role === "nguoi" ? "Bạn" : "Không gian BDSG"}</strong><time>${esc(stamp(m.created))}</time></div><p>${esc(m.content)}</p></article>`,
      )
      .join("");
  }
  function updateTask(task) {
    currentTask = task;
    const trace = $("#bdsg-task-trace");
    if (!trace) return;
    trace.innerHTML = traceMarkup(task);
    $("#bdsg-task-results").innerHTML = artifactMarkup(task);
    $("#bdsg-task-conversation").innerHTML = conversationMarkup(task);
    $("#bdsg-task-status").innerHTML = status(task.status);
    let scope = $("#bdsg-task-scope");
    if (!scope) {
      $("#bdsg-task-status").parentElement.insertAdjacentHTML(
        "beforeend",
        '<span id="bdsg-task-scope"></span>',
      );
      scope = $("#bdsg-task-scope");
    }
    scope.textContent =
      (task.project ? "Dự án: " + task.project.name + " · " : "") +
      (task.allow_module_reads
        ? "Đã cấp đọc MCP theo phạm vi tác vụ"
        : "Không cấp đọc MCP bên ngoài");
    const stop = $("#bdsg-task-stop");
    if (stop) {
      stop.hidden = !activeStates.has(task.status);
      stop.disabled = task.status === "cancelling";
    }
    const send = $("#bdsg-task-followup button[type=submit]");
    if (send) send.disabled = activeStates.has(task.status) || busy;
    const note = $("#bdsg-task-followup-note");
    if (note)
      note.textContent = activeStates.has(task.status)
        ? "Bạn có thể bổ sung yêu cầu sau khi lượt hiện tại kết thúc."
        : "Bổ sung ngữ cảnh để tiếp tục công việc. Kết quả của các lượt trước được giữ lại.";
  }
  async function renderTask(id) {
    const ticket = ++revision;
    currentTask = null;
    main.innerHTML = `<section class="bdsg-work-page"><a class="bdsg-back-link" href="#tasks">← Công việc</a><div id="bdsg-task-loading">${state.user ? "Đang mở công việc…" : `<div class="bdsg-work-login-note">${icon("lock")}<p>Đăng nhập để mở công việc riêng.</p><button class="button primary" data-bdsg-login>Đăng nhập không gian</button></div>`}</div></section>`;
    if (!state.user) return;
    try {
      const task = unwrap(await api("/api/task?id=" + encodeURIComponent(id)));
      if (
        ticket !== revision ||
        location.hash !== "#task/" + encodeURIComponent(id)
      )
        return;
      if (!moduleCache.length) await getModules();
      if (
        ticket !== revision ||
        location.hash !== "#task/" + encodeURIComponent(id)
      )
        return;
      main.innerHTML = `<section class="bdsg-work-page bdsg-task-detail"><a class="bdsg-back-link" href="#tasks">← Công việc</a><div class="bdsg-work-page-heading"><div><span class="eyebrow">${task.mode === "mo-hinh-bdsg" ? "TÁC VỤ MÔ HÌNH BDSG" : "TÁC VỤ THEO QUY TRÌNH"}</span><h1>${esc(task.title || "Công việc")}</h1><div class="bdsg-task-detail-meta"><span id="bdsg-task-status"></span><span>Tạo ${esc(stamp(task.created))}</span></div></div><button type="button" class="button" id="bdsg-task-stop" data-bdsg-stop>Dừng tác vụ</button></div><div class="bdsg-task-layout"><div class="bdsg-task-content"><section class="bdsg-task-context"><div class="bdsg-context-heading">${icon("briefcase")}Ngữ cảnh công việc</div><div id="bdsg-task-conversation"></div><div class="bdsg-task-module-chips">${(task.module_ids || []).map((mid) => `<span>${icon("grid")}${esc(moduleName(mid))}</span>`).join("") || "<small>Đối chiếu theo danh mục hệ sinh thái</small>"}</div></section><div id="bdsg-task-results"></div><form id="bdsg-task-followup" class="bdsg-task-followup"><label for="bdsg-followup-text">Tiếp tục công việc</label><textarea id="bdsg-followup-text" name="text" rows="2" minlength="10" maxlength="4000" required placeholder="Bổ sung nhu cầu hoặc điều chỉnh phạm vi…"></textarea><div><small id="bdsg-task-followup-note"></small><button type="submit" class="button primary">Tiếp tục ${icon("arrow")}</button></div></form></div><aside class="bdsg-task-trace" id="bdsg-task-trace" aria-label="Tiến trình công việc"></aside></div></section>`;
      main.querySelector(".bdsg-task-detail .eyebrow").textContent =
        task.mode === "quy-trinh"
          ? "TÁC VỤ THEO QUY TRÌNH"
          : "TÁC VỤ API MÔ HÌNH";
      updateTask(task);
    } catch (e) {
      if (ticket === revision)
        $("#bdsg-task-loading").innerHTML = errorBox(e.message);
    }
  }
  function modulesMarkup(query = "") {
    const rows = moduleCache.filter((m) =>
      clean(m.name + " " + m.group + " " + m.purpose).includes(clean(query)),
    );
    return (
      rows
        .map(
          (m) =>
            `<article class="bdsg-module-card"><div class="bdsg-module-card-top"><span>${icon("grid")}</span><small>${esc(m.group || "Nền tảng")}</small></div><h2>${esc(m.name)}</h2><p>${esc(m.purpose || "Mô-đun trong hệ sinh thái BDSG")}</p><div class="bdsg-module-capabilities"><span>${icon("external")}Mở ứng dụng</span><span>${icon("link")}${m.mcp?.state === "can-xac-thuc" ? "Đăng nhập xem MCP" : m.kind === "mcp-declared" ? "MCP đã khai báo" : "MCP chưa khai báo"}</span></div><div class="bdsg-module-card-actions"><a href="${esc(m.url)}" target="_blank" rel="noopener noreferrer">Mở nền tảng ${icon("external")}</a><button class="button small" type="button" data-bdsg-select-module="${esc(m.id)}">Dùng trong việc ${icon("plus")}</button></div>${state.user?.role === "quan-tri" && (m.mcp?.read_tools || []).length ? `<details class="bdsg-module-tools"><summary>Công cụ đọc được cấp quyền (${m.mcp.read_tools.length})</summary><form class="bdsg-module-call" data-bdsg-module-call="${esc(m.id)}"><label>Công cụ<select name="tool">${m.mcp.read_tools.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select></label><label>Tham số JSON<textarea name="arguments" rows="3" spellcheck="false">{}</textarea></label><button type="submit" class="button">Gọi công cụ đọc</button><pre role="status"></pre></form></details>` : ""}</article>`,
        )
        .join("") ||
      empty("Chưa có mô-đun phù hợp.", "Thử tên nền tảng hoặc lĩnh vực khác.")
    );
  }
  async function modules() {
    const ticket = ++revision;
    main.innerHTML = `<section class="bdsg-work-page"><div class="bdsg-work-page-heading"><div><span class="eyebrow">HỆ SINH THÁI DẠNG MÔ-ĐUN</span><h1>Nền tảng riêng. Cùng một không gian.</h1><p>Mở ứng dụng để sử dụng trực tiếp; các công cụ MCP cần cấu hình và quyền riêng.</p></div><a href="#connections" class="button">Kết nối & MCP ${icon("link")}</a></div><div class="bdsg-module-search">${icon("search")}<input type="search" id="bdsg-module-search" placeholder="Tìm mô-đun theo tên hoặc lĩnh vực…" aria-label="Tìm mô-đun"></div><div class="bdsg-module-explainer"><strong>Quyền kết nối được khai báo rõ ràng.</strong><p>Liên kết website, công cụ đọc và công cụ ghi là những khả năng khác nhau. Việc chọn một mô-đun không tự đăng nhập hoặc đồng bộ dữ liệu.</p></div><div class="bdsg-module-grid" id="bdsg-module-grid">Đang tải mô-đun…</div></section>`;
    main
      .querySelector(".bdsg-module-explainer")
      .insertAdjacentHTML("beforeend", setupButton());
    main
      .querySelector(".bdsg-module-explainer")
      .insertAdjacentHTML(
        "beforeend",
        '<a class="text-link connector-module-link" href="#integrations">Quản lý đầu nối MCP →</a>',
      );
    try {
      await getModules();
      if (ticket === revision && routeIs("modules"))
        $("#bdsg-module-grid").innerHTML = modulesMarkup(
          $("#bdsg-module-search")?.value || "",
        );
    } catch (e) {
      if (ticket === revision)
        $("#bdsg-module-grid").innerHTML = errorBox(e.message);
    }
  }
  async function create(args) {
    if (busy) return;
    busy = true;
    const button = $("#bdsg-task-create button[type=submit]");
    if (button) button.disabled = true;
    try {
      const created = await tool("cong_viec.tao", args);
      draft.prompt = "";
      location.hash = "task/" + encodeURIComponent(created.id);
    } catch (e) {
      toast(e.message);
    } finally {
      busy = false;
      if (button?.isConnected) button.disabled = false;
    }
  }
  document.addEventListener("input", (e) => {
    if (e.target.id === "bdsg-task-prompt") draft.prompt = e.target.value;
    if (e.target.id === "bdsg-module-search")
      $("#bdsg-module-grid").innerHTML = modulesMarkup(e.target.value);
  });
  document.addEventListener("change", (e) => {
    if (e.target.id === "bdsg-task-project") {
      draft.project_id = e.target.value;
      window.BDSGProjects?.setSelected(draft.project_id);
      draft.allow_module_reads = false;
      refreshConsent();
    }
    if (e.target.id === "bdsg-allow-reads")
      draft.allow_module_reads = !e.target.disabled && e.target.checked;
    if (e.target.id === "bdsg-model-provider")
      $("#bdsg-model-base-label").hidden = e.target.value !== "bdsg";
    if (e.target.name === "bdsg-module") {
      draft.module_ids = Array.from(
        document.querySelectorAll('[name="bdsg-module"]:checked'),
      ).map((e) => e.value);
      draft.allow_module_reads = false;
      refreshConsent();
      const label = $(".bdsg-module-picker summary span");
      if (label)
        label.textContent =
          "Chọn mô-đun" +
          (draft.module_ids.length ? ` (${draft.module_ids.length})` : "");
    }
  });
  document.addEventListener("click", async (e) => {
    if (e.target.closest("[data-bdsg-model-disable]")) {
      if (
        !confirm(
          "Tắt mô hình AI cho các lượt mới và xóa khóa đang lưu? Lượt đang chạy có thể hoàn tất với cấu hình trước đó.",
        )
      )
        return;
      const button = e.target.closest("button");
      button.disabled = true;
      try {
        latestModel = await tool("cau_hinh.tat_mo_hinh");
        $("#bdsg-model-dialog").close();
        toast("Đã tắt mô hình cho lượt mới và xóa khóa đang lưu.");
        if (routeIs("work")) home();
        else if (routeIs("modules")) modules();
      } catch (error) {
        $("#bdsg-model-error").textContent = error.message;
      } finally {
        button.disabled = false;
      }
      return;
    }
    if (e.target.closest("[data-bdsg-model-setup]")) {
      auth(() => openModelSettings().catch((err) => toast(err.message)));
      return;
    }
    if (e.target.closest("[data-bdsg-model-close]")) {
      $("#bdsg-model-form").reset();
      $("#bdsg-model-dialog").close();
      return;
    }
    const preset = e.target.closest("[data-bdsg-template]");
    if (preset) {
      const t = templates.find((t) => t.id === preset.dataset.bdsgTemplate);
      if (t) {
        draft.prompt = t.prompt;
        draft.template = t.id;
        const input = $("#bdsg-task-prompt");
        if (input) {
          input.value = t.prompt;
          input.focus();
        }
      }
      return;
    }
    if (e.target.closest("[data-bdsg-login]")) {
      auth(() => render());
      return;
    }
    const chosen = e.target.closest("[data-bdsg-select-module]");
    if (chosen) {
      if (!draft.module_ids.includes(chosen.dataset.bdsgSelectModule))
        draft.module_ids.push(chosen.dataset.bdsgSelectModule);
      location.hash = "work";
      return;
    }
    if (e.target.closest("[data-bdsg-stop]") && currentTask) {
      try {
        updateTask(await tool("cong_viec.dung", { id: currentTask.id }));
      } catch (err) {
        toast(err.message);
      }
      return;
    }
    const download = e.target.closest("[data-bdsg-download]");
    if (download && currentTask) {
      const a = currentTask.artifacts?.find(
        (a) => a.id === download.dataset.bdsgDownload,
      );
      if (!a) return;
      const url = URL.createObjectURL(
        new Blob([a.content], { type: "text/markdown;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download =
        "bdsg-thanhhoa-" +
        currentTask.id.replace(/[^a-zA-Z0-9_-]/g, "") +
        "-" +
        a.id.replace(/[^a-zA-Z0-9_-]/g, "") +
        ".md";
      link.click();
      URL.revokeObjectURL(url);
    }
  });
  document.addEventListener("submit", async (e) => {
    if (e.target.id === "bdsg-model-form") {
      e.preventDefault();
      const form = e.target,
        button = form.querySelector("[type=submit]");
      button.disabled = true;
      $("#bdsg-model-error").textContent = "";
      try {
        const payload = Object.fromEntries(new FormData(form));
        if (payload.provider !== "bdsg") delete payload.base_url;
        latestModel = await api("/api/model-config", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        form.reset();
        $("#bdsg-model-dialog").close();
        toast("Đã lưu cấu hình mô hình riêng tư.");
        if (routeIs("work")) home();
        else if (routeIs("modules")) modules();
      } catch (err) {
        $("#bdsg-model-error").textContent = err.message;
      } finally {
        button.disabled = false;
      }
    }
    if (e.target.id === "bdsg-task-create") {
      e.preventDefault();
      const args = {
        prompt: draft.prompt.trim(),
        module_ids: [...draft.module_ids],
        template: draft.template,
        project_id: draft.project_id,
        allow_module_reads: draft.allow_module_reads,
      };
      if (args.prompt.length < 10)
        return toast("Mô tả công việc cần ít nhất 10 ký tự.");
      auth(() => create(args));
    }
    if (e.target.id === "bdsg-task-followup") {
      e.preventDefault();
      if (!currentTask || busy) return;
      const form = e.target,
        text = new FormData(form).get("text");
      busy = true;
      try {
        const task = await tool("cong_viec.tiep_tuc", {
          id: currentTask.id,
          text,
        });
        form.reset();
        updateTask(task);
      } catch (err) {
        toast(err.message);
      } finally {
        busy = false;
        if (currentTask) updateTask(currentTask);
      }
    }
    if (e.target.matches("[data-bdsg-module-call]")) {
      e.preventDefault();
      const form = e.target,
        button = form.querySelector("button"),
        result = form.querySelector("pre"),
        values = new FormData(form);
      button.disabled = true;
      try {
        const args = JSON.parse(values.get("arguments"));
        if (!args || typeof args !== "object" || Array.isArray(args))
          throw new Error("Tham số phải là đối tượng JSON.");
        const data = await tool("ket_noi.doc", {
          platform_id: form.dataset.bdsgModuleCall,
          tool: values.get("tool"),
          arguments: args,
        });
        result.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        result.textContent = err.message;
      } finally {
        button.disabled = false;
      }
    }
  });
  setInterval(async () => {
    if (
      pollBusy ||
      !state.user ||
      !currentTask ||
      !activeStates.has(currentTask.status) ||
      document.visibilityState !== "visible" ||
      location.hash !== "#task/" + encodeURIComponent(currentTask.id)
    )
      return;
    pollBusy = true;
    const id = currentTask.id;
    try {
      const data = unwrap(await api("/api/task?id=" + encodeURIComponent(id)));
      if (
        currentTask?.id === id &&
        location.hash === "#task/" + encodeURIComponent(id)
      )
        updateTask(data);
    } catch (_) {
    } finally {
      pollBusy = false;
    }
  }, 2000);
  window.BDSGTasks = { home, tasks, modules, renderTask };
})();
