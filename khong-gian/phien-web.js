"use strict";
(() => {
  let revision = 0, sessions = [], hasMore = false, editing = null, busy = false;
  const when = value => typeof value === "number" && Number.isFinite(value) && value > 0
    ? new Date(value * 1000).toLocaleString("vi-VN") : "Chưa ghi nhận";
  const title = item => item.label || (item.client_hint === "Chưa xác định" ? "Phiên chưa đặt tên" : "Phiên trên " + item.client_hint);
  const currentView = (version, identity) => version === revision && state.user?.id === identity && state.view === "account";
  function clear() { revision++; sessions = []; hasMore = false; editing = null; busy = false; }

  function render(message = "", error = false) {
    main.innerHTML = `<div class="sessions-page"><header class="sessions-heading"><div><h1>Tài khoản</h1><p>${esc(state.user.name || "Tài khoản BDSG")} · ${state.user.role === "quan-tri" ? "Chủ quản" : "Người dùng"}</p></div><button class="button" id="sessions-refresh">Làm mới danh sách</button></header>
      ${message ? `<p class="sessions-message" role="${error ? "alert" : "status"}">${esc(message)}</p>` : ""}
      <section class="sessions-group"><h2>Phiên đăng nhập web</h2><p class="sessions-note">Tên nền tảng chỉ là gợi ý từ trình duyệt, chưa xác minh danh tính thiết bị. Anh có thể đặt tên để dễ nhận biết.</p>
      <ul class="sessions-list">${sessions.map(item => `<li class="sessions-item" data-session="${esc(item.id)}"><div class="sessions-detail"><div class="sessions-title"><h3>${esc(title(item))}</h3>${item.current ? '<span class="sessions-current">Phiên hiện tại</span>' : ""}</div><p>${esc(item.client_hint)} · Bắt đầu: ${esc(when(item.created_at))}</p><p>Ghi nhận gần nhất: ${esc(when(item.last_seen_at))}</p><p>Hết hạn: ${esc(when(item.expires_at))}</p></div>
        ${editing === item.id ? `<form class="sessions-rename" data-rename-form="${esc(item.id)}"><label for="session-label">Tên phiên</label><input id="session-label" name="label" maxlength="80" required value="${esc(item.label)}" placeholder="Ví dụ: MacBook BDSG" autocomplete="off"><div><button class="button" type="submit">Lưu tên</button><button class="button secondary" type="button" data-session-cancel>Hủy</button></div></form>` : `<div class="sessions-actions"><button class="button secondary" data-session-rename="${esc(item.id)}">Đổi tên<span class="visually-hidden"> ${esc(title(item))}</span></button>${!item.current ? `<button class="button sessions-danger" data-session-revoke="${esc(item.id)}">Đăng xuất<span class="visually-hidden"> ${esc(title(item))}</span></button>` : ""}</div>`}</li>`).join("")}</ul>
      ${hasMore ? '<p class="sessions-note">Danh sách hiển thị tối đa 100 phiên. Đăng xuất các phiên khác cũng áp dụng cho những phiên chưa hiển thị.</p>' : ""}
      </section><section class="sessions-group sessions-controls"><h2>Kiểm soát đăng nhập</h2><p>Thu hồi ở đây kết thúc phiên web BDSG. Quyền Office, kết nối Google, SSH và token agent đã cấp riêng cần được quản lý riêng.</p><div><button class="button sessions-danger" id="sessions-revoke-others">Đăng xuất các phiên khác</button><button class="button secondary" id="sessions-logout">Đăng xuất phiên hiện tại</button></div><p class="sessions-note">Phiên hiện tại được giữ khi anh đăng xuất các phiên khác. Ghi nhận gần nhất là lúc không gian web kiểm tra phiên, không phải trạng thái thiết bị đang online.</p></section></div>`;
    if (window.BDSGUnit?.snapshot().mode === 'units') {
      const section = document.createElement('section'); section.id = 'connection-management';
      section.className = 'sessions-group'; main.querySelector('.sessions-page').append(section);
      window.BDSGConnections?.mount(section);
      const jump = document.createElement('button'); jump.type = 'button'; jump.className = 'button secondary';
      jump.textContent = 'Quyền kết nối'; jump.onclick = () => { section.scrollIntoView({block:'start'}); section.tabIndex=-1;section.focus({preventScroll:true}); };
      main.querySelector('.sessions-heading').append(jump);
    }
    main.querySelector("#sessions-refresh").onclick = () => open();
    main.querySelector("#sessions-logout").onclick = () => {
      if (confirm("Đăng xuất phiên web BDSG đang dùng?")) document.querySelector("#profile").click();
    };
    main.querySelector("#sessions-revoke-others").onclick = () => confirmRevoke(null);
    main.querySelectorAll("[data-session-rename]").forEach(button => button.onclick = () => {
      editing = button.dataset.sessionRename; render(); main.querySelector("#session-label").focus();
    });
    main.querySelectorAll("[data-session-revoke]").forEach(button => button.onclick = () => confirmRevoke(button.dataset.sessionRevoke));
    const form = main.querySelector("[data-rename-form]");
    if (form) {
      form.onsubmit = event => {
        event.preventDefault();
        const label = form.elements.label.value.trim();
        if (!label || label.length > 80 || /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/.test(label)) {
          render("Tên phiên cần 1–80 ký tự và không có ký tự điều khiển.", true); return;
        }
        return mutate("rename", {id:editing, label});
      };
      main.querySelector("[data-session-cancel]").onclick = () => {editing = null; render();};
    }
  }

  function confirmRevoke(id) {
    if (busy) return;
    const item = id ? sessions.find(session => session.id === id) : null;
    if (id && (!item || item.current)) return;
    const dialog = document.createElement("dialog");
    dialog.className = "sessions-dialog";
    dialog.setAttribute("aria-labelledby", "sessions-confirm-title");
    dialog.innerHTML = `<h2 id="sessions-confirm-title">${item ? "Đăng xuất phiên này?" : "Đăng xuất các phiên khác?"}</h2><p>${item ? `Phiên “${esc(title(item))}” sẽ cần đăng nhập lại vào web BDSG.` : "Tất cả phiên web khác của tài khoản này sẽ cần đăng nhập lại, kể cả phiên chưa có trong danh sách."}</p><p>Phiên anh đang dùng được giữ lại. Quyền Office và các kết nối cấp riêng vẫn được quản lý riêng.</p><div><button class="button secondary" data-session-keep>Giữ lại</button><button class="button sessions-danger" data-session-confirm>Đăng xuất</button></div>`;
    main.append(dialog);
    dialog.querySelector("[data-session-keep]").onclick = () => {dialog.close(); dialog.remove();};
    dialog.addEventListener("cancel", () => dialog.remove(), {once:true});
    dialog.querySelector("[data-session-confirm]").onclick = () => {
      dialog.close(); dialog.remove(); return mutate(id ? "revoke" : "revoke-others", id ? {id} : {});
    };
    dialog.showModal(); dialog.querySelector("[data-session-keep]").focus();
  }

  async function mutate(action, args) {
    if (busy) return;
    busy = true;
    const version = revision, identity = state.user?.id;
    main.querySelectorAll(".sessions-page button").forEach(button => button.disabled = true);
    try {
      const result = await api("/api/sessions/" + action, {method:"POST", body:JSON.stringify(args)});
      if (!currentView(version, identity)) return;
      editing = null;
      const message = action === "rename" ? "Đã lưu tên phiên." : action === "revoke-others" ? `Đã đăng xuất ${result.revoked_count} phiên khác.` : "Đã đăng xuất phiên được chọn.";
      await open(message);
    } catch (_) {
      if (currentView(version, identity)) render("Chưa thực hiện được. Kiểm tra kết nối hoặc làm mới danh sách rồi thử lại.", true);
    } finally { if (currentView(version, identity)) busy = false; }
  }

  async function open(message = "") {
    window.BDSGConnections?.reset();
    const version = ++revision, identity = state.user?.id;
    sessions = []; hasMore = false; editing = null; busy = false;
    if (!state.user) {
      main.innerHTML = '<section class="sessions-page"><h1>Tài khoản</h1><p>Đăng nhập để xem và quản lý các phiên web của anh.</p><button class="button" id="sessions-login">Đăng nhập</button></section>';
      main.querySelector("#sessions-login").onclick = () => document.querySelector("#profile").click();
      return;
    }
    main.innerHTML = '<section class="sessions-page" aria-busy="true"><h1>Tài khoản</h1><p role="status">Đang đọc các phiên đăng nhập…</p></section>';
    try {
      const result = await api("/api/sessions");
      if (!currentView(version, identity)) return;
      if (!Array.isArray(result.sessions) || !result.sessions.length || !result.sessions.some(item => item.current)) throw Error("Invalid session list");
      sessions = result.sessions; hasMore = result.has_more === true;
      render(message);
    } catch (_) {
      if (!currentView(version, identity)) return;
      main.innerHTML = '<section class="sessions-page"><h1>Chưa đọc được phiên đăng nhập</h1><p role="alert">Kiểm tra kết nối và tài khoản rồi thử lại.</p><button class="button" id="sessions-retry">Thử lại</button></section>';
      main.querySelector("#sessions-retry").onclick = () => open();
    }
  }
  window.BDSGSessions = {open, reset:clear, leave() {revision++; main.querySelector(".sessions-dialog")?.remove();}};
})();
