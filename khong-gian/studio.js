"use strict";
(() => {
  let tab = "documents",
    projects = [],
    tasks = [],
    activeProject = "",
    browserState = null,
    busy = false,
    revision = 0;
  const tabs = {
    documents: "Tài liệu",
    actions: "Chờ phê duyệt",
    schedules: "Lịch công việc",
    team: "Cộng tác",
    runtime: "Xử lý dữ liệu",
    browser: "Trình duyệt",
    usage: "Mức sử dụng",
  };
  const error = (e) => toast(e.message || "Chưa hoàn tất thao tác");
  const projectOptions = () =>
    projects
      .filter((p) => !p.archived)
      .map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`)
      .join("");
  const taskOptions = (predicate) =>
    tasks
      .filter((t) => t.owner === state.user?.id && predicate(t))
      .map((t) => `<option value="${esc(t.id)}">${esc(t.title)}</option>`)
      .join("");
  const blank = (text) =>
    `<section class="studio-empty">${icon("briefcase")}<p>${esc(text)}</p></section>`;
  const stamp = (n) => (n ? date(n) : "Chưa chạy");
  function actionCard(a) {
    const target = a.payload.browser_target;
    const pending = a.status === "awaiting";
    const live = pending && a.expires * 1000 > Date.now();
    return `<article class="studio-card"><div class="studio-section-heading"><h3>${target ? "Thao tác trình duyệt" : esc(a.payload.tool)}</h3><span class="mini-tag">${esc(a.status)}</span></div><p>Người giao: ${esc(a.owner)} · Hết hạn ${esc(stamp(a.expires))}</p>${target ? `<p><strong>${esc(target.label || target.tag)}</strong> · ${esc(a.payload.arguments.action)}</p><p>Trang: ${esc(target.url)}<br>Đích biểu mẫu: ${esc(target.form_action || target.href || "Trang hiện tại")}</p>` : ""}<pre>${esc(JSON.stringify(a.payload.arguments, null, 2))}</pre><code>${esc(a.digest)}</code>${a.status === "unknown" ? '<p class="form-error">Chưa rõ tác động bên ngoài. Cần đối chiếu nền tảng trước khi đề xuất lại.</p>' : ""}${target && live ? `<button class="button" data-studio-preview="${esc(a.id)}">Xem màn hình trước khi duyệt</button><div data-studio-preview-result="${esc(a.id)}" aria-live="polite"></div>` : ""}${pending && state.user.role === "quan-tri" ? `<div class="studio-actions">${live ? `<button class="button primary" data-studio-approve="${esc(a.id)}" data-digest="${esc(a.digest)}">Duyệt và thực hiện</button>` : ""}<button class="button" data-studio-reject="${esc(a.id)}" data-digest="${esc(a.digest)}">Từ chối</button></div>` : ""}</article>`;
  }
  async function open() {
    const token = ++revision;
    main.innerHTML = `<section class="bdsg-work-page studio-page"><div class="bdsg-work-page-heading"><div><h1>Xưởng công việc Thanh Hoá.</h1><p>Tài liệu, công cụ và những quyết định cần bạn ở cùng một nơi.</p></div><a class="button primary" href="#work">${icon("plus")}Giao việc mới</a></div>${
      state.user
        ? `<nav class="studio-tabs" aria-label="Công cụ làm việc">${Object.entries(
            tabs,
          )
            .map(
              ([key, name]) =>
                `<button data-studio-tab="${key}" aria-pressed="${key === tab}">${esc(name)}</button>`,
            )
            .join("")}</nav><div id="studio-content">Đang mở công cụ…</div>`
        : blank("Đăng nhập để mở tài liệu và công cụ riêng.") +
          '<button class="button primary" data-studio-login>Đăng nhập không gian</button>'
    }</section>`;
    if (!state.user) return;
    try {
      const [p, t] = await Promise.all([
        tool("du_an.danh_sach"),
        tool("cong_viec.danh_sach"),
      ]);
      if (token !== revision || location.hash !== "#studio") return;
      projects = p.projects || [];
      tasks = t.tasks || [];
      if (!projects.some((p) => p.id === activeProject && !p.archived))
        activeProject = projects.find((p) => !p.archived)?.id || "";
      await draw();
    } catch (e) {
      if (token === revision) $("#studio-content").textContent = e.message;
    }
  }
  async function draw() {
    const target = $("#studio-content");
    if (!target) return;
    target.innerHTML = "Đang mở công cụ…";
    const selected = tab,
      token = revision;
    try {
      let markup = "",
        summaryForUsage = null;
      if (tab === "documents") {
        const docs = activeProject
          ? (await tool("tai_lieu.danh_sach", { project_id: activeProject }))
              .documents
          : [];
        markup = `<div class="studio-section-heading"><h2>Tài liệu của dự án</h2><p>Tệp tối đa 1 MiB. Mỗi lần tải tạo một phiên bản riêng; tải xuống cần quyền dự án.</p></div>${projects.some((p) => !p.archived) ? `<label>Dự án<select id="studio-project">${projectOptions()}</select></label><form id="studio-upload" class="studio-inline"><label>Chọn tài liệu<input name="file" type="file" accept=".txt,.md,.csv,.pdf" required></label><button class="button primary" type="submit">Tải vào dự án</button></form><p class="studio-note">TXT, Markdown, CSV cần UTF-8. PDF cần có văn bản, không mã hóa, tối đa 50 trang; chưa hỗ trợ ảnh quét. Văn bản trích xuất có giới hạn và được ghi rõ khi rút gọn.</p><div class="studio-list">${docs.map((d) => `<article class="studio-row"><span>${icon("briefcase")}</span><div><strong>${esc(d.name)}</strong><small>Phiên bản ${d.version} · ${d.size} byte · ${esc(stamp(d.created))}${d.truncated ? " · Văn bản rút gọn" : ""}</small><code>${esc(d.sha256)}</code></div><a class="button small" href="/api/document?id=${encodeURIComponent(d.id)}">Tải xuống</a></article>`).join("") || blank("Chưa có tài liệu. Tải một tệp để bắt đầu.")}</div>` : blank("Tạo hoặc khôi phục một dự án để tải tài liệu.") + `<a href="#projects" class="button">Mở dự án</a>`}`;
      } else if (tab === "actions") {
        const rows = (await tool("hanh_dong.danh_sach")).actions || [];
        markup = `<div class="studio-section-heading"><h2>Quyết định nằm ở bạn.</h2><p>Đề xuất chưa làm thay đổi nghiệp vụ. Kiểm đúng nơi nhận và nội dung trước khi duyệt. Mỗi đề xuất có hiệu lực 15 phút.</p></div><form id="studio-propose" class="studio-form"><h3>Chuẩn bị hành động</h3><label>Công việc<select name="task_id" required>${taskOptions(() => true)}</select></label><label>Loại hành động<select name="tool"><option value="kinh_doanh.tao_yeu_cau">Ghi nhận yêu cầu kinh doanh</option><option value="kinh_doanh.doi_chang">Đổi chặng yêu cầu</option><option value="ket_noi.ghi">Công cụ ghi MCP đã được cấp</option></select></label><label>Nội dung JSON cần xem trước<textarea name="arguments" rows="5" required placeholder='{"title":"Yêu cầu thử","sector":"cong-nghe","description":"Mô tả nhu cầu cụ thể"}'></textarea></label><button class="button" type="submit">Lưu dự thảo để duyệt</button></form><div class="studio-list">${rows.map(actionCard).join("") || blank("Không có hành động chờ duyệt.")}</div>`;
      } else if (tab === "schedules") {
        const rows = (await tool("lich.danh_sach")).schedules || [];
        markup = `<div class="studio-section-heading"><h2>Công việc có nhịp riêng.</h2><p>Lịch chỉ tổng hợp danh mục và ngữ cảnh dự án; không tự ghi nghiệp vụ, chạy mã hoặc đọc MCP bên ngoài. Khi có AI, mỗi lượt có thể phát sinh phí API.</p></div><form id="studio-schedule" class="studio-form"><label>Tên lịch<input name="name" required minlength="3" maxlength="100"></label><label>Mục tiêu<textarea name="prompt" required minlength="10" maxlength="4000" rows="3"></textarea></label><label>Dự án<select name="project_id"><option value="">Công việc độc lập</option>${projectOptions()}</select></label><label>Chu kỳ (phút)<input name="minutes" type="number" min="15" max="10080" value="1440" required></label><p class="studio-note">Lượt đầu sau một chu kỳ; bỏ qua lượt bị lỡ, không chạy bù hàng loạt. Thời điểm hiển thị theo giờ Việt Nam.</p><button class="button primary" type="submit">Tạo và bật lịch</button></form><div class="studio-list">${rows.map((s) => `<article class="studio-row"><div><strong>${esc(s.name)}</strong><small>${s.enabled ? "Đang bật" : "Đã tạm dừng"} · Chu kỳ ${s.interval / 60} phút · Lượt kế ${esc(stamp(s.next_run))}</small><small>Lần gần nhất: ${esc(s.last_status)} ${s.last_task ? `· <a href="#task/${encodeURIComponent(s.last_task)}">Mở công việc</a>` : ""}</small></div><button class="button" data-studio-schedule-toggle="${esc(s.id)}" data-enabled="${!s.enabled}">${s.enabled ? "Tạm dừng" : "Bật lại"}</button></article>`).join("") || blank("Bạn chưa đặt lịch công việc.")}</div>`;
      } else if (tab === "team") {
        const agents = (await tool("agent.danh_sach")).agents || [];
        markup = `<div class="studio-section-heading"><h2>Phối hợp với đúng quyền.</h2><p>Chia sẻ chỉ dẫn và tài liệu dự án. Công việc riêng của từng người vẫn giữ quyền riêng; thu hồi dự án chặn lần truy cập mới nhưng không xóa bản ngữ cảnh đã được giao trước đó.</p></div><form id="studio-share" class="studio-form"><label>Dự án<select name="id" required>${projectOptions()}</select></label><label>Thành viên<select name="identity" required>${agents
          .filter((a) => a.role === "operator" && a.active)
          .map(
            (a) =>
              `<option value="${esc(a.id)}">${esc(a.name || a.id)}</option>`,
          )
          .join(
            "",
          )}</select></label><label>Quyền<select name="role"><option value="viewer">Đọc dự án/tài liệu</option><option value="editor">Đọc và chỉnh sửa dự án</option><option value="revoke">Thu hồi quyền dự án</option></select></label><button class="button" type="submit">Cập nhật thành viên</button></form>${state.user.role === "quan-tri" ? `<form id="studio-user" class="studio-form"><h3>Tạo tài khoản nhân viên</h3><label>Mã đăng nhập<input name="id" required pattern="[a-z][a-z0-9_-]{2,63}" autocomplete="off"></label><label>Tên hiển thị<input name="name" required maxlength="100"></label><label>Mật khẩu do chủ quản đặt<input name="password" type="password" minlength="16" maxlength="256" required autocomplete="new-password"></label><button class="button primary" type="submit">Tạo người dùng vận hành</button></form><div class="studio-list">${agents.map((a) => `<article class="studio-row"><div><strong>${esc(a.name || a.id)}</strong><small>${esc(a.id)} · ${esc(a.role)} · ${a.active ? "Hoạt động" : "Đã thu hồi"}</small></div>${a.active ? `<button class="button" data-studio-revoke="${esc(a.id)}">Thu hồi đăng nhập</button>` : ""}</article>`).join("")}</div>` : ""}`;
        if (state.user.role === "quan-tri")
          markup += `<form id="studio-delegate" class="studio-form"><h3>Giao một phần việc cho agent</h3><label>Công việc cha<select name="task_id" required>${taskOptions((t) => t.allow_delegation)}</select></label><label>Agent nhận<select name="recipient" required>${agents
            .filter((a) => a.role === "operator" && a.active)
            .map(
              (a) =>
                `<option value="${esc(a.id)}">${esc(a.name || a.id)}</option>`,
            )
            .join(
              "",
            )}</select></label><label>Mục tiêu phần việc<textarea name="prompt" required minlength="10" maxlength="4000" rows="3"></textarea></label><p class="studio-note">Tối đa ba tác vụ con. Agent cần được chia sẻ dự án/tài liệu trước khi nhận việc; không tự được cấp quyền đọc MCP hoặc điều phối tiếp.</p><button class="button primary">Giao phần việc</button></form>`;
      } else if (tab === "runtime") {
        markup = `<div class="studio-section-heading"><h2>Từ dữ liệu đến tệp kết quả.</h2><p>Chọn công việc đã cấp quyền Python. Chạy tối đa 15 giây trong vùng riêng, không mạng và không quyền vào dữ liệu máy chủ. Tệp văn bản tạo ra được lưu vào kết quả công việc.</p></div><form id="studio-python" class="studio-form"><label>Công việc<select name="task_id" required>${taskOptions((t) => t.allow_python)}</select></label><label>Mã Python<textarea name="code" spellcheck="false" rows="8" required maxlength="16000" placeholder="print(1 + 2)"></textarea></label><p class="studio-note">Tài liệu đã chọn trong tác vụ có tên input-1.txt, input-2.txt… Tên tệp mặc định: ket-qua.csv, ket-qua.txt, ket-qua.md. Tối đa 8 tệp UTF-8 khi khai rõ tên đầu ra; xem và tải ở trang công việc.</p><button class="button primary" type="submit">Chạy trong vùng riêng</button></form><pre id="studio-python-result" aria-live="polite"></pre>`;
      } else if (tab === "browser") {
        browserState = null;
        markup = `<div class="studio-section-heading"><h2>Cùng agent nhìn vào công việc.</h2><p>Chọn công việc đã cấp tên miền trình duyệt. Agent đọc, mở liên kết và chuẩn bị thao tác chờ duyệt trong phạm vi được giao; bạn tiếp quản khi cần đăng nhập. Phiên tự đóng sau 15 phút.</p></div><form id="studio-browser-open" class="studio-inline"><label>Công việc<select name="task_id" required>${taskOptions((t) => t.browser_hosts?.length)}</select></label><label>Địa chỉ được cấp<input type="url" name="url" required placeholder="https://…"></label><button class="button primary">Mở trình duyệt</button></form><div id="studio-browser-view"></div>`;
      } else {
        const summary = await tool("van_hanh.tong_quan");
        summaryForUsage = summary;
        const rows = summary.tasks;
        markup = `<div class="studio-section-heading"><h2>Thấy rõ cách công việc được thực hiện.</h2><p>Mô hình: ${esc(summary.model.model || "Chưa cấu hình API")} · Tối đa 8 lượt/một lần chạy, hạn 180 giây giữa các bước. Chưa quy đổi tiền; số token thiếu được ghi rõ.</p></div><div class="studio-list">${rows.map((t) => `<article class="studio-row"><div><a href="#task/${encodeURIComponent(t.id)}"><strong>${esc(t.title)}</strong></a><small>${esc(t.status)} · ${esc(stamp(t.updated))}</small><small>${t.usage ? `${t.usage.requests} lượt API · vào ${t.usage.input_tokens} / ra ${t.usage.output_tokens} token${t.usage.complete ? "" : " · Số liệu chưa đầy đủ"}` : "Chưa có số liệu API"}</small></div></article>`).join("") || blank("Chưa có công việc để tổng hợp.")}</div>`;
      }
      if (token !== revision || tab !== selected || location.hash !== "#studio")
        return;
      target.innerHTML = markup;
      if (tab === "usage") {
        const summary = summaryForUsage;
        if (token !== revision || tab !== "usage" || !$("#studio-content"))
          return;
        target.insertAdjacentHTML(
          "afterbegin",
          `<section class="studio-card"><h3>Kết quả kinh doanh trong phạm vi của bạn</h3><p>${summary.business.request_count} yêu cầu · Tư vấn ${summary.business.stages["tu-van"]} · Triển khai ${summary.business.stages["trien-khai"]} · Vận hành ${summary.business.stages["van-hanh"]} · Kinh doanh ${summary.business.stages["kinh-doanh"]}</p><p>${summary.reserved_api_calls_today} lượt API đã giữ trong ngày (giờ Việt Nam). Hạn 100 lượt/danh tính, 200 lượt/toàn hệ thống và ngân sách đầu ra 65.536 token/danh tính/ngày (giữ trước 4096 token/request); tính cả lần gọi lỗi để giữ hạn mức thận trọng. Chưa có số liệu doanh thu.</p></section>`,
        );
      }
      if ($("#studio-project")) $("#studio-project").value = activeProject;
    } catch (e) {
      if (token === revision && $("#studio-content"))
        target.textContent = e.message;
    }
  }
  async function browserCommand(args) {
    const token = revision;
    const task_id = args.task_id || browserState?.task_id;
    const value = await tool("trinh_duyet.tiep_quan", {
      ...args,
      task_id,
      image: true,
    });
    if (token !== revision || !state.user || !$("#studio-browser-view")) return;
    if (value.closed) {
      browserState = null;
      $("#studio-browser-view").textContent = "Phiên đã đóng.";
      return;
    }
    browserState = { ...value, task_id };
    $("#studio-browser-view").innerHTML =
      `<section class="studio-card"><h3>${esc(value.title)}</h3><p>${esc(value.url)} · Còn ${value.expires_in} giây</p><div class="studio-actions"><button class="button" data-studio-browser="observe">Cập nhật màn hình</button><button class="button" data-studio-browser="close">Đóng và xóa phiên</button></div>${value.screenshot ? `<img class="studio-browser-image" alt="Màn hình trình duyệt công việc" src="data:image/jpeg;base64,${value.screenshot}">` : ""}<details><summary>Nội dung trang</summary><pre>${esc(value.text)}</pre></details><form id="studio-browser-control" class="studio-form"><h3>Bạn đang tiếp quản</h3><label>Thành phần<select name="node">${value.nodes.map((n) => `<option value="${n.id}">${n.id}: ${esc(n.tag)} ${esc(n.type)} — ${esc(n.label || n.href || "Không nhãn")}</option>`).join("")}</select></label><label>Thao tác<select name="action"><option value="click">Bấm thành phần</option><option value="fill">Nhập văn bản/mật khẩu</option><option value="select">Chọn giá trị</option><option value="key">Nhấn Enter/Tab/Escape</option></select></label><label>Nội dung nhập (không lưu lại trong giao diện)<input name="text" type="password" autocomplete="off" maxlength="4000"></label><p class="studio-note">Thao tác này tác động trực tiếp lên trang đang mở. Kiểm màn hình và đích nhận trước khi bấm gửi, mua, xóa hoặc cấp quyền.</p><button class="button primary" type="submit" value="manual">Thực hiện thao tác đã chọn</button><button class="button" type="submit" value="propose">Lưu đề xuất để chủ quản duyệt</button><p class="studio-note">Đề xuất lưu nội dung đã nhập trong sổ hành động. Chỉ dùng dữ liệu nghiệp vụ thông thường; mật khẩu, mã xác minh và thanh toán cần tự tiếp quản, không đưa vào đề xuất.</p></form></section>`;
  }
  document.addEventListener("click", async (e) => {
    if (e.target.closest("[data-studio-login]")) return auth(open);
    const nav = e.target.closest("[data-studio-tab]");
    if (nav) {
      tab = nav.dataset.studioTab;
      return open();
    }
    if (busy) return;
    const approve = e.target.closest(
      "[data-studio-approve],[data-studio-reject]",
    );
    const toggle = e.target.closest("[data-studio-schedule-toggle]");
    const revoke = e.target.closest("[data-studio-revoke]");
    const browser = e.target.closest("[data-studio-browser]");
    const preview = e.target.closest("[data-studio-preview]");
    if (!approve && !toggle && !revoke && !browser && !preview) return;
    if (
      approve?.dataset.studioApprove &&
      !confirm("Duyệt và thực hiện đúng nội dung đang hiển thị?")
    )
      return;
    if (
      revoke &&
      !confirm("Thu hồi mọi phiên đăng nhập và token của tài khoản này?")
    )
      return;
    busy = true;
    try {
      if (preview) {
        const token = revision;
        const id = preview.dataset.studioPreview;
        const result = await tool("hanh_dong.xem_trinh_duyet", { id });
        if (token !== revision || !state.user || tab !== "actions") return;
        const view = document.querySelector(`[data-studio-preview-result="${id}"]`);
        if (!view) return;
        view.innerHTML = `<p>${result.matches ? "Biểu mẫu còn khớp với đề xuất. Hệ thống kiểm lại khi duyệt." : "Biểu mẫu đã thay đổi. Hãy từ chối và tạo đề xuất mới."}</p>${result.screenshot ? `<img class="studio-browser-image" alt="Màn hình hiện tại của đề xuất" src="data:image/jpeg;base64,${esc(result.screenshot)}">` : ""}`;
        const approveButton = view.closest("article").querySelector("[data-studio-approve]");
        if (approveButton) approveButton.disabled = !result.matches;
        return;
      }
      if (approve)
        await tool("hanh_dong.duyet", {
          id: approve.dataset.studioApprove || approve.dataset.studioReject,
          digest: approve.dataset.digest,
          approve: !!approve.dataset.studioApprove,
        });
      if (toggle)
        await tool("lich.bat_tat", {
          id: toggle.dataset.studioScheduleToggle,
          enabled: toggle.dataset.enabled === "true",
        });
      if (revoke)
        await tool("nguoi_dung.thu_hoi", { id: revoke.dataset.studioRevoke });
      if (browser)
        await browserCommand({ action: browser.dataset.studioBrowser });
      else await open();
    } catch (err) {
      error(err);
    } finally {
      busy = false;
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.id === "studio-project") {
      revision++;
      activeProject = e.target.value;
      draw();
    }
  });
  document.addEventListener("submit", async (e) => {
    const id = e.target.id;
    if (!id.startsWith("studio-")) return;
    e.preventDefault();
    if (busy) return;
    const form = e.target,
      uploadProject = activeProject,
      values = Object.fromEntries(new FormData(form)),
      button = form.querySelector("button[type=submit],button:not([type])");
    busy = true;
    if (button) button.disabled = true;
    try {
      if (id === "studio-upload") {
        const file = values.file;
        if (!file?.size || file.size > 1048576)
          throw new Error("Tệp phải từ 1 byte đến 1 MiB");
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = "";
        for (let i = 0; i < bytes.length; i += 8192)
          binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        const response = await api("/api/upload", {
          method: "POST",
          body: JSON.stringify({
            project_id: uploadProject,
            name: file.name,
            content_base64: btoa(binary),
          }),
        });
        if (!response.ok)
          throw new Error(response.ly_do || "Chưa tải được tài liệu");
      } else if (id === "studio-propose")
        await tool("hanh_dong.de_xuat", {
          ...values,
          arguments: JSON.parse(values.arguments),
        });
      else if (id === "studio-schedule")
        await tool("lich.tao", {
          name: values.name,
          interval_seconds: Number(values.minutes) * 60,
          task: { prompt: values.prompt, project_id: values.project_id },
        });
      else if (id === "studio-share") await tool("cong_tac.chia_se", values);
      else if (id === "studio-delegate")
        await tool("phoi_hop.giao_viec", values);
      else if (id === "studio-user") {
        await tool("nguoi_dung.tao", values);
        form.reset();
      } else if (id === "studio-python") {
        $("#studio-python-result").textContent = JSON.stringify(
          await tool("runtime.python", values),
          null,
          2,
        );
        return;
      } else if (id === "studio-browser-open") {
        await browserCommand({ ...values, action: "open" });
        return;
      } else if (id === "studio-browser-control") {
        const args = {
          ...values,
          node: Number(values.node),
          nonce: browserState.nonce,
        };
        form.reset();
        if (e.submitter?.value === "propose") {
          await tool("hanh_dong.de_xuat", {
            task_id: browserState.task_id,
            tool: "trinh_duyet.hanh_dong",
            arguments: { ...args, task_id: browserState.task_id },
          });
          toast("Đã lưu đề xuất. Mở Chờ phê duyệt để kiểm tra và duyệt.");
          return;
        }
        await browserCommand(args);
        return;
      } else return;
      toast("Đã cập nhật công việc.");
      await open();
    } catch (err) {
      error(err);
    } finally {
      busy = false;
      if (button) button.disabled = false;
    }
  });
  window.BDSGStudio = {
    open,
    reset() {
      revision++;
      projects = [];
      tasks = [];
      browserState = null;
      activeProject = "";
    },
  };
})();
