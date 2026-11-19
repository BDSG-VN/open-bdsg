"use strict";
(() => {
  let revision = 0, pending = false, active = null, directory = [];
  const conversations = new Map();
  const choices = [
    ["tu-van", "Tìm hiểu & triển khai"],
    ["tai-khoan", "Tài khoản & đăng nhập"],
    ["mua-hang", "Mua hàng & dịch vụ"],
  ];
  const current = () => location.hash === "#support" || /^#support\/[a-z0-9_-]{1,80}$/.test(location.hash);
  const selectedRoute = id => "#support/" + encodeURIComponent(id);
  function rows(query = "") {
    const matches = directory.filter(a => clean(a.name + " " + a.description + " " + a.group).includes(clean(query).trim()));
    $("#assistant-count").textContent = `${matches.length} / ${directory.length} trợ lý`;
    $("#assistant-directory").innerHTML = matches.map(a => `<li><div><a class="assistant-name" href="${selectedRoute(a.id)}">${esc(a.name)}</a><p>${esc(a.description)}</p><small>${esc(a.group)} · Hướng dẫn chuyên biệt</small></div><a class="button" href="${selectedRoute(a.id)}">Hỏi trợ lý ${icon("arrow")}</a></li>`).join("") || '<li class="assistant-no-results">Không thấy trợ lý phù hợp. Thử tên nền tảng hoặc lĩnh vực khác.</li>';
  }
  function messages() {
    const log = $("#customer-log");
    if (!log || !active) return;
    const exchanges = conversations.get(active.id) || [];
    log.innerHTML = exchanges.map(({question, answer}) => `<article class="support-exchange"><p class="support-question"><strong>Bạn</strong><span>${esc(question)}</span></p><div class="support-answer"><h2 tabindex="-1">${esc(answer.assistant_name)}</h2><p>${esc(answer.message)}</p><ol>${answer.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol>${answer.intake?.length ? `<details class="assistant-intake"><summary>Thông tin giúp làm rõ nhu cầu</summary><ul>${answer.intake.map(q => `<li>${esc(q)}</li>`).join("")}</ul></details>` : ""}<ul class="support-platforms">${answer.platforms.map(p => `<li><div><strong>${esc(p.name)}</strong><p>${esc(p.purpose)}</p></div><a class="button small" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Mở nền tảng ${icon("external")}</a></li>`).join("")}</ul></div></article>`).join("");
    $("#assistant-clear").disabled = exchanges.length === 0 || pending;
  }
  function drawAssistant(profile) {
    active = profile;
    main.innerHTML = `<section class="bdsg-work-page support-page"><div class="bdsg-work-page-heading"><div><a class="text-link" href="#support">${icon("grid")}Tất cả trợ lý BDSG</a><h1>${esc(profile.name)}</h1><p>${esc(profile.description)}</p></div><button class="button" id="assistant-clear" type="button">Xóa hội thoại này</button></div><div class="support-layout"><section class="support-conversation" aria-label="Hội thoại riêng của trợ lý"><p class="support-mode">Hướng dẫn chuyên biệt · AI chưa cấu hình</p><div id="customer-log" role="log" aria-live="polite" aria-relevant="additions"></div><form id="customer-support-form"><label>Mục đích<select id="customer-agent" name="agent">${choices.map(c => `<option value="${c[0]}">${c[1]}</option>`).join("")}</select></label><label>Nền tảng phụ trách<input value="${esc(profile.platform.name)}" readonly aria-label="Nền tảng phụ trách"></label><label class="support-prompt">Bạn cần trợ lý hỗ trợ gì?<textarea id="customer-message" name="message" rows="3" required maxlength="1000" placeholder="${esc(profile.brain.starter)}"></textarea></label><div class="support-send"><p>Không nhập mật khẩu, mã OTP hoặc thông tin thanh toán.</p><button class="button primary" type="submit">Nhận hướng dẫn ${icon("arrow")}</button></div><p id="customer-error" role="alert"></p></form><div class="support-examples"><button class="button small" type="button" data-assistant-starter>Dùng câu hỏi gợi ý</button></div></section><aside class="support-boundary"><h2>Bộ não chuyên trách</h2><p>${esc(profile.brain.mission)}</p><h3>Kiến thức riêng</h3><ul>${profile.brain.knowledge.facts.map(f => `<li>${esc(f)}</li>`).join("")}</ul><h3>Hội thoại tách biệt</h3><p>Chỉ hiện nội dung trao đổi với trợ lý này. Đổi trợ lý không gửi kèm hội thoại cũ. Nội dung ở bộ nhớ trình duyệt, mất khi tải lại hoặc đăng xuất.</p><h3>Mô hình & công cụ</h3><p>Đã có chỉ dẫn và quy trình riêng. Chưa cấu hình AI và chưa cấp công cụ đọc/ghi dữ liệu nền tảng. Bạn tự xác nhận tài khoản, đơn hàng và thanh toán tại website gốc.</p><details><summary>Nguồn kiến thức & chỉ dẫn</summary><p>Danh mục công khai BDSG và hướng dẫn đã biên soạn, phiên bản ${esc(profile.brain.version)}. Chưa nhập tài liệu nghiệp vụ riêng.</p><p>${esc(profile.brain.system_instructions)}</p></details></aside></div></section>`;
    messages();
  }
  async function open(identifier = "") {
    const ticket = ++revision;
    pending = false; active = null;
    main.innerHTML = '<section class="bdsg-work-page"><p role="status">Đang mở trợ lý BDSG…</p></section>';
    try {
      if (identifier) {
        const profile = await api('/api/customer-agent?id=' + encodeURIComponent(identifier));
        const known = state.products.find(p => p.id === profile.platform_id);
        if (profile.id !== identifier || profile.id !== 'tro-ly-' + profile.platform_id || profile.brain?.id !== identifier || profile.brain?.brain_id !== profile.brain_id || profile.brain?.platform_id !== profile.platform_id || profile.platform?.id !== profile.platform_id || !known || known.url !== profile.platform.url) throw new Error('Hồ sơ trả về không đúng trợ lý đã chọn. Vui lòng thử lại.');
        if (ticket === revision && current()) drawAssistant(profile);
      } else {
        const result = await api('/api/customer-agents');
        if (ticket !== revision || !current()) return;
        directory = result.agents;
        main.innerHTML = `<section class="bdsg-work-page support-directory"><div class="bdsg-work-page-heading"><div><h1>Mỗi nền tảng, một trợ lý.</h1><p>${directory.length} trợ lý chuyên trách với nhiệm vụ, chỉ dẫn và kiến thức hướng dẫn riêng.</p></div></div><p class="support-mode">Đã có hồ sơ bộ não · Đang chạy hướng dẫn, chưa kết nối mô hình AI</p><label class="assistant-search">Tìm trợ lý<input id="assistant-search" type="search" placeholder="Tên nền tảng hoặc lĩnh vực, ví dụ CRM, du lịch, nông nghiệp" autocomplete="off"></label><p id="assistant-count" role="status" aria-live="polite"></p><ul id="assistant-directory" class="assistant-directory"></ul></section>`;
        rows();
      }
    } catch (error) {
      if (ticket === revision && current()) main.innerHTML = `<section class="bdsg-work-page"><h1>Chưa mở được trợ lý</h1><p role="alert">${esc(error.message)}</p><a class="button" href="#support">Về danh sách</a><button class="button" data-assistant-retry>Thử lại</button></section>`;
    }
  }

  async function settings() {
    const ticket = ++revision;
    if (state.user?.role !== "quan-tri") {
      main.innerHTML = `<section class="bdsg-work-page"><h1>Cài đặt ChatGPT</h1><p>Chỉ chủ quản được quản lý kết nối và quyền sử dụng gói.</p>${!state.user ? '<button class="button primary" data-chatgpt-login>Đăng nhập chủ quản</button>' : '<a class="button" href="#support">Mở hỗ trợ khách hàng</a>'}</section>`;
      return;
    }
    main.innerHTML = '<section class="bdsg-work-page"><p role="status">Đang tải trạng thái kết nối ChatGPT…</p></section>';
    try {
      const result = await api("/api/chatgpt-connection");
      if (ticket !== revision || location.hash !== "#settings" || state.user?.role !== "quan-tri") return;
      main.innerHTML = `<section class="bdsg-work-page support-settings"><div class="bdsg-work-page-heading"><div><h1>Kết nối ChatGPT.</h1><p>Quản lý điều kiện đăng nhập và dùng hạn mức gói trong BDSG.</p></div></div><section class="panel"><h2>Đang chờ OpenAI cấp quyền</h2><p>${result.registration_submitted ? "Hồ sơ đăng ký đã được gửi. OpenAI đã xác nhận nhận thông tin; chưa có Client ID hoặc quyền sử dụng gói cho website." : "Website cần đăng ký và được OpenAI chấp thuận trước khi bật kết nối."}</p><button class="button primary" disabled aria-describedby="chatgpt-pending">Đăng nhập bằng ChatGPT</button><p id="chatgpt-pending">Nút sẽ được triển khai luồng đăng nhập khi BDSG được cấp quyền và cấu hình hợp lệ. Phiên ChatGPT đang mở trên máy không tự trở thành kết nối của website.</p><ol><li>Gửi hồ sơ BDSG và mục đích sử dụng.</li><li>Nhận quyền đối tác, Client ID và phạm vi được phép.</li><li>Cấu hình đăng nhập, kiểm thử thu hồi quyền và hạn mức trước khi bật.</li></ol><div class="support-links"><a class="button" href="${esc(result.registration_url)}" target="_blank" rel="noopener noreferrer">Trang đăng ký OpenAI ${icon("external")}</a><a class="text-link" href="${esc(result.documentation_url)}" target="_blank" rel="noopener noreferrer">Tài liệu Sign in with ChatGPT ${icon("external")}</a></div></section><section class="support-boundary"><h2>Hạn mức gói và khách hàng</h2><p>Đăng nhập có thể cho phép dùng hạn mức ChatGPT theo quyền OpenAI cấp. Kết nối vẫn gọi dịch vụ mô hình của OpenAI; đây không phải cách chạy mô hình ngay trên máy chủ BDSG.</p><p>Chưa dùng tài khoản hay tín dụng của chủ quản để phục vụ khách ẩn danh. Không lấy cookie hoặc mã đăng nhập từ trình duyệt. Việc được đăng nhập không đồng nghĩa được phép tạo tài khoản hoặc mua hàng.</p><a class="button" href="#support">Xem trợ lý theo nền tảng ${icon("arrow")}</a></section></section>`;
    } catch (error) {
      if (ticket === revision && location.hash === "#settings") main.innerHTML = `<section class="bdsg-work-page"><h1>Chưa tải được kết nối</h1><p role="alert">${esc(error.message)}</p><button class="button" data-chatgpt-retry>Thử lại</button></section>`;
    }
  }
  document.addEventListener("input", event => {
    if (event.target.id === "assistant-search" && current()) rows(event.target.value);
  });
  document.addEventListener("click", event => {
    if (event.target.closest("[data-assistant-starter]") && active && current() && !pending) {
      $("#customer-message").value = active.brain.starter;
      $("#customer-message").focus();
    }
    if (event.target.closest("#assistant-clear") && active && !pending) {
      conversations.delete(active.id); messages(); $("#customer-message").value = ""; $("#customer-message").focus();
    }
    if (event.target.closest("[data-assistant-retry]")) open(location.hash.split('/')[1] || '');
    if (event.target.closest("[data-chatgpt-login]")) auth(settings);
    if (event.target.closest("[data-chatgpt-retry]")) settings();
  });
  document.addEventListener("submit", async event => {
    if (event.target.id !== "customer-support-form") return;
    event.preventDefault();
    if (pending || !active || !current()) return;
    const form = event.target, ticket = revision, assistant = active;
    const data = Object.fromEntries(new FormData(form));
    data.message = data.message.trim(); data.assistant_id = assistant.id;
    if (!data.message) { $("#customer-error").textContent = "Nhập nhu cầu cần hỗ trợ."; return; }
    pending = true;
    form.querySelectorAll('select,textarea').forEach(field => {field.disabled = true;});
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true; button.textContent = "Đang chuẩn bị hướng dẫn…";
    $("#assistant-clear").disabled = true;
    $("#customer-error").textContent = "";
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(),15000);
    let received = false;
    try {
      const answer = await api("/api/customer-support", {method:"POST", body:JSON.stringify(data), signal:controller.signal});
      if (ticket !== revision || !current() || active?.id !== assistant.id) return;
      if (answer.assistant_id !== assistant.id || answer.brain_id !== assistant.brain_id || answer.agent !== data.agent || !Array.isArray(answer.platforms) || answer.platforms.length !== 1 || answer.platforms[0].id !== assistant.platform_id || answer.platforms[0].url !== assistant.platform.url) throw new Error("Phản hồi không thuộc trợ lý đã chọn. Vui lòng thử lại.");
      const exchanges = conversations.get(assistant.id) || [];
      exchanges.push({question:data.message, answer});
      conversations.set(assistant.id, exchanges.slice(-5)); messages();
      $("#customer-message").value = ""; received = true;
      $("#customer-log .support-exchange:last-child h2").focus();
    } catch (error) {
      if (ticket === revision && current()) $("#customer-error").textContent = error.name === "AbortError" ? "Chờ phản hồi quá lâu. Câu hỏi vẫn còn để bạn thử lại." : error.message;
    } finally {
      clearTimeout(timeout);
      if (ticket === revision && current()) { pending = false; form.querySelectorAll('select,textarea').forEach(field => {field.disabled = false;}); button.disabled = false; button.textContent = "Nhận hướng dẫn"; $("#assistant-clear").disabled = !(conversations.get(assistant.id)?.length); if (!received) $("#customer-message").focus(); }
    }
  });
  window.BDSGSupport = {open, settings, reset() {revision++; pending = false; active = null; directory = []; conversations.clear();}};
})();
