"use strict";
(() => {
  let revision = 0;
  const known = value => value !== null && value !== undefined && Number.isFinite(value);
  const number = value => known(value) ? value.toLocaleString("vi-VN", {maximumFractionDigits:1}) : "Chưa đo được";
  const bytes = value => known(value) ? number(value / 1024 ** 3) + " GiB" : "Chưa đo được";
  const seconds = value => known(value) ? number(value / 3600) + " giờ" : "Chưa đo được";
  const row = (label, value) => `<div class="node-row"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
  const group = (title, rows, note = "") => `<section class="node-group"><h2>${esc(title)}</h2><dl>${rows}</dl>${note ? `<p class="node-note">${esc(note)}</p>` : ""}</section>`;
  function render(report) {
    const {node:n, operations:o, recovery:r} = report;
    const observed = new Date(n.observed_at);
    const at = Number.isFinite(observed.getTime()) ? observed.toLocaleString("vi-VN") : "Chưa xác định";
    const status = n.status === "ok" ? "Đã nhận số liệu" : "Một số số liệu chưa đo được";
    main.innerHTML = `<div class="node-page"><header class="node-heading"><div><h1>Máy chủ ${esc(n.node.id)}</h1><p>Quan sát lúc ${esc(at)} · ${esc(status)}</p></div><button class="button" id="node-refresh" type="button">Làm mới số liệu</button></header>
      <p class="node-status" role="status">${o.status === "ready" ? "Cổng ứng dụng sẵn sàng." : "Cổng ứng dụng cần kiểm tra."} ${n.alerts.length ? "Có cảnh báo tài nguyên cần xử lý." : "Chưa ghi nhận cảnh báo tài nguyên ở lần đo này."}</p>
      ${group("Hệ thống", row("Hệ điều hành", n.host.os || "Chưa đo được") + row("Nhân hệ điều hành", n.host.kernel || "Chưa đo được") + row("Kiến trúc", n.host.architecture || "Chưa đo được") + row("Ảo hóa quan sát", n.host.virtualization.provider || "Chưa xác định") + row("Thời gian máy chạy", seconds(n.host.uptime_seconds)) + row("Bản phát hành ứng dụng", o.release === "unknown" ? "Chưa khai báo" : o.release), "Thông số của môi trường đang chạy; chưa xác thực phần cứng vật lý phía dưới.")}
      ${group("Bộ xử lý và bộ nhớ", row("CPU", n.cpu.model || "Chưa đo được") + row("CPU logic", number(n.cpu.logical_count)) + row("Tải trung bình 1 / 5 / 15 phút", [n.cpu.load_average.one,n.cpu.load_average.five,n.cpu.load_average.fifteen].map(number).join(" / ")) + row("Bộ nhớ tổng", bytes(n.memory.total_bytes)) + row("Bộ nhớ khả dụng", bytes(n.memory.available_bytes)) + row("Bộ nhớ đã dùng", known(n.memory.used_percent) ? number(n.memory.used_percent) + "%" : "Chưa đo được"), "Tải trung bình là số công việc chờ hoặc chạy, không phải phần trăm sử dụng CPU.")}
      ${group("Dung lượng dữ liệu", row("Tổng dung lượng", bytes(n.storage.total_bytes)) + row("Đã dùng", bytes(n.storage.used_bytes)) + row("Còn trống", bytes(n.storage.free_bytes)) + row("Tỷ lệ đã dùng", known(n.storage.used_percent) ? number(n.storage.used_percent) + "%" : "Chưa đo được"), "Đo hệ thống tệp chứa dữ liệu ứng dụng; dung lượng có thể dùng chung với hệ điều hành.")}
      ${group("Sao lưu và phục hồi", row("Diễn tập phục hồi", r.status === "ok" ? "Kiểm dữ liệu đạt" : r.status === "failed" ? "Kiểm dữ liệu thất bại" : "Chưa có kết quả còn hiệu lực") + row("Toàn vẹn dữ liệu", r.integrity === "ok" ? "Đạt" : "Chưa xác nhận") + row("Thời gian phục hồi dữ liệu", known(r.restore_duration_seconds) ? number(r.restore_duration_seconds) + " giây" : "Chưa đo được") + row("Tuổi bản sao hiện tại", seconds(r.backup_age_seconds)) + row("Tự động sao lưu ngoài máy", r.offsite?.configured ? "Đã cấu hình" : "Chưa cấu hình"), "Phục hồi dữ liệu chưa chứng minh khôi phục toàn dịch vụ. Tuổi bản sao hiện tại chưa phải cam kết RPO.")}
      <p class="node-note">Ngưỡng cảnh báo: bộ nhớ hoặc ổ đĩa dùng từ 90%; ổ đĩa còn dưới 1 GiB. Trang chỉ đọc số liệu, không thay cấu hình máy chủ.</p></div>`;
    document.querySelector("#node-refresh").onclick = open;
  }
  async function open() {
    const version = ++revision, identity = state.user?.id;
    if (state.user?.role !== "quan-tri") {
      main.innerHTML = '<section class="node-page"><h1>Máy chủ</h1><p>Chỉ chủ quản được xem số liệu máy chủ. Hãy đăng nhập bằng tài khoản có quyền quản trị.</p></section>';
      return;
    }
    main.innerHTML = '<section class="node-page" aria-busy="true"><h1>Máy chủ</h1><p role="status">Đang đọc số liệu máy chủ…</p></section>';
    try {
      const report = await api("/api/node");
      if (version !== revision || identity !== state.user?.id || state.view !== "system") return;
      render(report);
    } catch (_) {
      if (version !== revision || identity !== state.user?.id || state.view !== "system") return;
      main.innerHTML = '<section class="node-page"><h1>Chưa đọc được số liệu</h1><p role="alert">Kiểm tra kết nối và quyền tài khoản rồi thử lại.</p><button class="button" id="node-retry">Thử lại</button></section>';
      document.querySelector("#node-retry").onclick = open;
    }
  }
  window.BDSGNode = {open, reset() {revision++;}, leave() {revision++;}};
})();
