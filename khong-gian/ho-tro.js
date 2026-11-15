"use strict";
(() => {
  let revision = 0, pending = false, exchanges = [];
  const choices = [
    ["tu-van", "Tư vấn nền tảng", "Tôi cần tìm nền tảng CRM"],
    ["tai-khoan", "Hỗ trợ tài khoản", "Hướng dẫn mở tài khoản BDSG"],
    ["mua-hang", "Hỗ trợ mua hàng", "Tôi muốn mua hàng trên BDSG Shop"],
  ];
  const current = () => location.hash === "#support";
  function messages() {
    const log = $("#customer-log");
    if (!log) return;
    log.innerHTML = exchanges.map(({question, answer}) => `<article class="support-exchange"><p class="support-question"><strong>Bạn</strong><span>${esc(question)}</span></p><div class="support-answer"><h2>${esc(choices.find(c => c[0] === answer.agent)?.[1] || "Hướng dẫn BDSG")}</h2><p>${esc(answer.message)}</p><ol>${answer.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol><h3>Nền tảng để tiếp tục</h3><ul class="support-platforms">${answer.platforms.map(p => `<li><div><strong>${esc(p.name)}</strong><p>${esc(p.purpose)}</p></div><a class="button small" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Mở nền tảng ${icon("external")}</a></li>`).join("")}</ul></div></article>`).join("");
  }
  function open() {
    revision++; pending = false; exchanges = [];
    main.innerHTML = `<section class="bdsg-work-page support-page"><div class="bdsg-work-page-heading"><div><h1>Hỗ trợ để bạn đi tiếp.</h1><p>Tìm nền tảng, chuẩn bị tài khoản và các bước mua hàng trong hệ sinh thái BDSG.</p></div></div><div class="support-layout"><section class="support-conversation" aria-label="Trao đổi với trợ lý"><p class="support-mode">Hướng dẫn theo danh mục · Chưa dùng mô hình AI</p><div id="customer-log" role="log" aria-live="polite" aria-relevant="additions"></div><form id="customer-support-form"><label>Trợ lý<select id="customer-agent" name="agent">${choices.map(c => `<option value="${c[0]}">${c[1]}</option>`).join("")}</select></label><label>Nền tảng<select id="customer-platform" name="platform_id"><option value="">Gợi ý theo nhu cầu</option>${state.products.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select></label><label class="support-prompt">Bạn cần hỗ trợ gì?<textarea id="customer-message" name="message" rows="3" required maxlength="1000" placeholder="Ví dụ: Tôi muốn mở tài khoản CRM cho doanh nghiệp"></textarea></label><div class="support-send"><p>Không nhập mật khẩu, mã OTP hoặc thông tin thanh toán.</p><button class="button primary" type="submit">Nhận hướng dẫn ${icon("arrow")}</button></div><p id="customer-error" role="alert"></p></form><div class="support-examples" aria-label="Gợi ý bắt đầu">${choices.map(c => `<button class="button small" type="button" data-support-example="${c[0]}">${c[1]}</button>`).join("")}</div></section><aside class="support-boundary"><h2>Bạn giữ quyền quyết định.</h2><p>Trợ lý hiện hướng dẫn các bước và mở đúng website gốc. Chưa tạo tài khoản, đặt hàng hoặc thanh toán thay bạn.</p><h3>Tiếp tục tại nền tảng</h3><p>Giá, tồn kho và trạng thái tài khoản cần kiểm tra trực tiếp. Tự nhập thông tin đăng nhập ở website bạn đã chọn.</p><h3>Riêng tư trong cuộc trò chuyện</h3><p>Câu hỏi không được lưu vào lịch sử máy chủ hoặc gửi cho AI. Nội dung trên màn hình được xóa khi mở lại trang hỗ trợ.</p></aside></div></section>`;
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
      main.innerHTML = `<section class="bdsg-work-page support-settings"><div class="bdsg-work-page-heading"><div><h1>Kết nối ChatGPT.</h1><p>Quản lý điều kiện đăng nhập và dùng hạn mức gói trong BDSG.</p></div></div><section class="panel"><h2>Đang chờ OpenAI cấp quyền</h2><p>${result.registration_submitted ? "Hồ sơ đăng ký đã được gửi. OpenAI đã xác nhận nhận thông tin; chưa có Client ID hoặc quyền sử dụng gói cho website." : "Website cần đăng ký và được OpenAI chấp thuận trước khi bật kết nối."}</p><button class="button primary" disabled aria-describedby="chatgpt-pending">Đăng nhập bằng ChatGPT</button><p id="chatgpt-pending">Nút sẽ được triển khai luồng đăng nhập khi BDSG được cấp quyền và cấu hình hợp lệ. Phiên ChatGPT đang mở trên máy không tự trở thành kết nối của website.</p><ol><li>Gửi hồ sơ BDSG và mục đích sử dụng.</li><li>Nhận quyền đối tác, Client ID và phạm vi được phép.</li><li>Cấu hình đăng nhập, kiểm thử thu hồi quyền và hạn mức trước khi bật.</li></ol><div class="support-links"><a class="button" href="${esc(result.registration_url)}" target="_blank" rel="noopener noreferrer">Trang đăng ký OpenAI ${icon("external")}</a><a class="text-link" href="${esc(result.documentation_url)}" target="_blank" rel="noopener noreferrer">Tài liệu Sign in with ChatGPT ${icon("external")}</a></div></section><section class="support-boundary"><h2>Hạn mức gói và khách hàng</h2><p>Đăng nhập có thể cho phép dùng hạn mức ChatGPT theo quyền OpenAI cấp. Kết nối vẫn gọi dịch vụ mô hình của OpenAI; đây không phải cách chạy mô hình ngay trên máy chủ BDSG.</p><p>Chưa dùng tài khoản hay tín dụng của chủ quản để phục vụ khách ẩn danh. Không lấy cookie hoặc mã đăng nhập từ trình duyệt. Việc được đăng nhập không đồng nghĩa được phép tạo tài khoản hoặc mua hàng.</p><a class="button" href="#support">Xem ba trợ lý khách hàng ${icon("arrow")}</a></section></section>`;
    } catch (error) {
      if (ticket === revision && location.hash === "#settings") main.innerHTML = `<section class="bdsg-work-page"><h1>Chưa tải được kết nối</h1><p role="alert">${esc(error.message)}</p><button class="button" data-chatgpt-retry>Thử lại</button></section>`;
    }
  }
  document.addEventListener("click", event => {
    const example = event.target.closest("[data-support-example]");
    if (example && current() && !pending) {
      const choice = choices.find(c => c[0] === example.dataset.supportExample);
      $("#customer-agent").value = choice[0];
      $("#customer-message").value = choice[2];
      $("#customer-message").focus();
    }
    if (event.target.closest("[data-chatgpt-login]")) auth(settings);
    if (event.target.closest("[data-chatgpt-retry]")) settings();
  });
  document.addEventListener("submit", async event => {
    if (event.target.id !== "customer-support-form") return;
    event.preventDefault();
    if (pending || !current()) return;
    const form = event.target, ticket = revision;
    const data = Object.fromEntries(new FormData(form));
    data.message = data.message.trim();
    if (!data.message) { $("#customer-error").textContent = "Nhập nhu cầu cần hỗ trợ."; return; }
    pending = true;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true; button.textContent = "Đang chuẩn bị hướng dẫn…";
    $("#customer-error").textContent = "";
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(),15000);
    try {
      const answer = await api("/api/customer-support", {method:"POST", body:JSON.stringify(data), signal:controller.signal});
      if (ticket !== revision || !current()) return;
      exchanges.push({question:data.message, answer});
      exchanges = exchanges.slice(-5); messages();
      $("#customer-message").value = "";
    } catch (error) {
      if (ticket === revision && current()) $("#customer-error").textContent = error.name === "AbortError" ? "Chờ phản hồi quá lâu. Câu hỏi vẫn còn để bạn thử lại." : error.message;
    } finally {
      clearTimeout(timeout);
      if (ticket === revision && current()) { pending = false; button.disabled = false; button.textContent = "Nhận hướng dẫn"; $("#customer-message").focus(); }
    }
  });
  window.BDSGSupport = {open, settings, reset() {revision++; pending = false; exchanges = [];}};
})();
