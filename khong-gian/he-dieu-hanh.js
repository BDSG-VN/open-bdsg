"use strict";
(() => {
  let channel = null, invalidating = false, checking = null;
  try { channel = new BroadcastChannel("bdsg-session-v27"); } catch (_) {}
  function invalidateSession() {
    if (invalidating) return;
    invalidating = true;
    clearPrivateState();
    window.BDSGDesktop?.leave();
    const content = document.querySelector("#main");
    if (content) content.textContent = "Phiên tài khoản đã thay đổi. Đang xác minh lại không gian…";
    if (parent !== window) {
      parent.postMessage({type:"bdsg-os-session-changed"}, location.origin);
      return;
    }
    Promise.resolve().then(() => refresh()).catch(() => {
      if (content) content.textContent = "Chưa xác minh được tài khoản. Hãy tải lại trang trước khi tiếp tục.";
    }).finally(() => { invalidating = false; });
  }
  window.BDSGSession = {
    invalidate: invalidateSession,
    announce() {
      const hint = {type:"identity-changed", actorId:state.user?.id || "guest", eventId:String(Date.now()) + Math.random()};
      if (channel) channel.postMessage(hint);
      else { try { localStorage.setItem("bdsg-session-change", JSON.stringify(hint)); } catch (_) {} }
    },
    check() {
      if (checking) return checking;
      const expected = state.user?.id || "guest";
      checking = fetch("/api/me", {credentials:"same-origin", cache:"no-store"}).then(async response => {
        if (!response.ok) return false;
        const result = await response.json();
        if ((result.user?.id || "guest") !== expected) { invalidateSession(); return false; }
        return (state.user?.id || "guest") === expected && !invalidating;
      }).catch(() => false).finally(() => { checking = null; });
      return checking;
    },
  };
  function accountHint(hint) {
    if (hint?.type === "identity-changed" && hint.actorId !== (state.user?.id || "guest")) invalidateSession();
  }
  if (channel) channel.onmessage = event => accountHint(event.data);
  window.addEventListener("storage", event => { if (event.key === "bdsg-session-change") { try { accountHint(JSON.parse(event.newValue)); } catch (_) {} } });
  window.addEventListener("focus", () => { if (typeof state !== "undefined") window.BDSGSession.check(); });
  const appFrame = location.pathname === "/workspace.html";
  if (appFrame) {
    window.BDSGAppVisible = true;
    document.documentElement.classList.add("ios-app-frame");
    document.addEventListener("click", event => {
      const anchor = event.target.closest('a[href^="#"]');
      const route = anchor?.getAttribute("href");
      if (!route || !/^#(?:system|work|office|projects|studio|tasks|staff|modules|integrations|ai-settings|support|overview|agents|requests|activity|settings|platforms|sectors|connections|task\/[a-f0-9]{24}|support\/[a-z0-9_-]{1,80})$/.test(route)) return;
      event.preventDefault();
      parent.postMessage({type:"bdsg-os-launch-route", route}, location.origin);
    });
    window.addEventListener("message", event => {
      if (event.origin !== location.origin || event.source !== parent) return;
      if (event.data?.type === "bdsg-os-visibility") window.BDSGAppVisible = event.data.visible === true;
      if (event.data?.type === "bdsg-os-preferences") {
        document.documentElement.classList.toggle("ios-large-text", event.data.largeText === true);
        document.documentElement.classList.toggle("ios-reduce-motion", event.data.reduceMotion === true);
      }
    });
    window.addEventListener("hashchange", () => parent.postMessage({type:"bdsg-os-route", route:location.hash}, location.origin));
    return;
  }
  window.BDSGReadBroker = window.BDSGOSState.createReadBroker({getIdentity:()=>state.user?.id || "guest", maxConcurrent:2});
  const apps = [
    {id:"system", title:"Máy chủ", route:"#system", icon:"activity", color:"gray", description:"TH01, tài nguyên và phục hồi dữ liệu"},
    {id:"work", title:"Agent BDSG", route:"#work", icon:"spark", color:"blue", description:"Giao mục tiêu, theo dõi kết quả AI"},
    {id:"office", title:"Văn phòng", route:"#office", icon:"briefcase", color:"orange", description:"Tài liệu, bảng tính và trình chiếu"},
    {id:"projects", title:"Dự án", route:"#projects", icon:"home", color:"indigo", description:"Ngữ cảnh và tài liệu công việc"},
    {id:"browser", title:"Trình duyệt", kind:"browser", icon:"globe", color:"cyan", description:"Tìm kiếm BDSG, tab và dấu trang"},
    {id:"studio", title:"Xưởng việc", route:"#studio", icon:"route", color:"purple", description:"Công cụ, lịch và quy trình"},
    {id:"tasks", title:"Công việc", route:"#tasks", icon:"briefcase", color:"green", description:"Lượt chạy và sản phẩm đã tạo"},
    {id:"staff", title:"Đội ngũ Agent", route:"#staff", icon:"grid", color:"teal", description:"Hồ sơ trợ lý và chuyên môn"},
    {id:"modules", title:"Mô-đun BDSG", route:"#modules", icon:"grid", color:"pink", description:"Danh mục công cụ công nghệ"},
    {id:"integrations", title:"Kết nối", route:"#integrations", icon:"link", color:"gray", description:"Ứng dụng Việt Nam và MCP"},
    {id:"ai-settings", title:"Trung tâm AI", route:"#ai-settings", icon:"spark", color:"purple", description:"Mô hình, khóa và ngân sách"},
    {id:"support", title:"Hỗ trợ", route:"#support", icon:"arrow", color:"green", description:"Trợ lý hướng dẫn nền tảng"},
    {id:"overview", title:"Tổng quan", route:"#overview", icon:"activity", color:"blue", description:"Thông tin vận hành không gian"},
    {id:"agents", title:"Thông điệp", route:"#agents", icon:"link", color:"green", description:"Hộp thư theo danh tính"},
    {id:"requests", title:"Kinh doanh", route:"#requests", icon:"home", color:"red", description:"Yêu cầu và chặng triển khai"},
    {id:"activity", title:"Nhật ký", route:"#activity", icon:"activity", color:"gray", description:"Dấu vết thao tác được cấp quyền"},
    {id:"settings", title:"Cài đặt AI", route:"#settings", icon:"grid", color:"gray", description:"Cấu hình và điều kiện kết nối ChatGPT"},
  ].map(app => ({kind:"internal", ...app}));
  function appIdForRoute(hash) {
    if (typeof hash !== "string") return undefined;
    const aliases = {"#platforms":"modules", "#sectors":"overview", "#connections":"integrations"};
    return /^#task\/[a-f0-9]{24}$/.test(hash) ? "tasks" : /^#support\/[a-z0-9_-]{1,80}$/.test(hash) ? "support" : (Object.hasOwn(aliases, hash) ? aliases[hash] : undefined) || apps.find(app => app.route === hash)?.id;
  }
  let manager, identity = null, root, surface = "home", query = "", group = "apps", message = "";
  const frames = new Map();
  let storageKey = "";
  let preferences = {largeText:false, reduceMotion:matchMedia("(prefers-reduced-motion: reduce)").matches};
  try { const saved = JSON.parse(localStorage.getItem("bdsg-os-preferences") || "{}");
    if (typeof saved.largeText === "boolean") preferences.largeText = saved.largeText;
    if (typeof saved.reduceMotion === "boolean") preferences.reduceMotion = saved.reduceMotion;
  } catch (_) {}
  const sessionKey = id => "bdsg-os-v27:" + id;
  function syncIdentity() {
    const next = state.user?.id || "guest";
    if (next === identity) return;
    if (storageKey) { try { sessionStorage.removeItem(storageKey); } catch (_) {} }
    for (const frame of frames.values()) frame.remove();
    frames.clear();
    identity = next; storageKey = sessionKey(next);
    manager = window.BDSGOSState.create({apps, identityId:next, maxSessions:8});
    try { const value = JSON.parse(sessionStorage.getItem(storageKey) || "null"); if (value) manager.restore(value); } catch (_) {}
    surface = "home";
  }
  function persist() {
    try { sessionStorage.setItem(storageKey, JSON.stringify(manager.snapshot())); } catch (_) {}
  }
  function applyPreferences() {
    document.documentElement.classList.toggle("ios-large-text", preferences.largeText);
    document.documentElement.classList.toggle("ios-reduce-motion", preferences.reduceMotion);
    try { localStorage.setItem("bdsg-os-preferences", JSON.stringify(preferences)); } catch (_) {}
    for (const frame of frames.values()) frame.contentWindow?.postMessage({type:"bdsg-os-preferences", ...preferences}, location.origin);
  }
  function ensureRoot() {
    if (root) return;
    root = document.createElement("section"); root.id = "bdsg-os"; root.className = "os-system";
    root.innerHTML = `<header class="os-status"><a class="os-wordmark" href="#desktop" aria-label="Màn hình chính BDSG"><img src="/bdsg-mark.svg" alt="" width="26" height="26"><span>BDSG <strong>Thanh Hoá</strong></span></a><time id="os-clock"></time><div class="os-status-actions"><button type="button" data-os-action="switcher" aria-label="Ứng dụng đang mở">${icon("grid")}<span id="os-session-count">0</span></button><button type="button" data-os-action="preferences" aria-label="Tùy chỉnh giao diện">${icon("activity")}</button><button type="button" data-os-action="account" id="os-account">Tài khoản</button></div></header><div id="os-view"></div><section id="os-stage" class="os-stage" aria-label="Cửa sổ ứng dụng" hidden><div class="os-window-bar"><button type="button" data-os-action="home">${icon("home")}<span>Màn hình chính</span></button><strong id="os-window-title"></strong><div><button type="button" data-os-action="duplicate" aria-label="Mở cửa sổ khác">${icon("plus")}</button><button type="button" data-os-action="minimize" aria-label="Thu nhỏ ứng dụng">${icon("arrow")}</button><button type="button" data-os-action="close" aria-label="Đóng ứng dụng">${icon("close")}</button></div></div><div id="os-frames"></div></section><nav class="os-dock" aria-label="Dock ứng dụng"><button type="button" data-os-action="home" class="os-dock-home" aria-label="Màn hình chính">${icon("home")}</button>${["work","browser","office"].map(id => tile(apps.find(app => app.id === id), true)).join("")}<button type="button" data-os-action="switcher" class="os-dock-home" aria-label="Chuyển ứng dụng">${icon("grid")}</button></nav><p class="os-notice" id="os-notice" role="status" aria-live="polite" hidden></p>`;
    document.body.append(root);
    root.addEventListener("click", handleClick);
    root.addEventListener("submit", event => { if (event.target.id === "os-search-form") event.preventDefault(); });
    root.addEventListener("input", event => {
      if (event.target.id !== "os-search") return;
      query = event.target.value;
      renderResults();
    });
    root.addEventListener("change", event => {
      if (!event.target.matches("[data-os-preference]")) return;
      preferences[event.target.dataset.osPreference] = event.target.checked;
      applyPreferences();
    });
    updateClock(); setInterval(updateClock, 30000);
  }
  function updateClock() {
    const clock = root?.querySelector("#os-clock");
    if (clock) { const now = new Date(); clock.dateTime = now.toISOString(); clock.textContent = now.toLocaleTimeString("vi-VN", {hour:"2-digit",minute:"2-digit"}); }
  }
  function tile(app, dock = false) {
    return `<button class="os-app${dock ? " os-dock-app" : ""}" type="button" data-os-app="${esc(app.id)}" aria-label="Mở ${esc(app.title)}"><span class="os-app-icon os-${app.color || "blue"}">${icon(app.icon || "globe")}</span><span class="os-app-label">${esc(app.title)}</span></button>`;
  }
  function notice(text) {
    message = text;
    const target = root.querySelector("#os-notice"); target.textContent = text; target.hidden = !text;
    if (text) setTimeout(() => { if (message === text) { target.hidden = true; message = ""; } }, 6000);
  }
  function renderHome() {
    const name = state.user?.name?.split(" ").slice(0, 4).join(" ");
    root.querySelector("#os-view").innerHTML = `<main class="os-home"><div class="os-home-heading"><div><p class="os-date">${esc(new Date().toLocaleDateString("vi-VN", {weekday:"long",day:"numeric",month:"long"}))}</p><h1>Thanh Hoá<span>.</span></h1><p>${name ? "Chào " + esc(name) + ". Công việc của bạn ở đây." : "Ứng dụng, Agent và công việc. Cùng một không gian."}</p></div><button type="button" class="os-text-button" data-os-action="switcher">${manager.snapshot().sessions.length} ứng dụng đang mở ${icon("arrow")}</button></div><form id="os-search-form" role="search"><label for="os-search">${icon("search")}<span class="sr-only">Tìm ứng dụng và nền tảng BDSG</span></label><input id="os-search" type="search" value="${esc(query)}" placeholder="Tìm ứng dụng, nền tảng BDSG" autocomplete="off"><kbd>Ctrl K</kbd></form><div class="os-library-tabs" role="group" aria-label="Phạm vi ứng dụng"><button type="button" data-os-group="apps" aria-pressed="${group === "apps"}">Ứng dụng</button><button type="button" data-os-group="platforms" aria-pressed="${group === "platforms"}">Nền tảng BDSG <span>${state.products.length}</span></button></div><div id="os-results"></div><p class="os-home-note">Các ứng dụng nội bộ dùng phiên BDSG của bạn. Nền tảng bên ngoài mở website riêng.</p></main>`;
    renderResults();
  }
  function renderResults() {
    const target = root.querySelector("#os-results"); if (!target) return;
    const term = clean(query.trim());
    if (group === "apps") {
      const shown = apps.filter(app => clean(app.title + " " + app.description).includes(term));
      target.innerHTML = shown.length ? `<div class="os-app-grid" aria-label="Ứng dụng nội bộ">${shown.map(app => tile(app)).join("")}</div>` : '<div class="os-empty"><h2>Chưa thấy ứng dụng phù hợp.</h2><p>Thử tên ngắn hơn hoặc chuyển sang Nền tảng BDSG.</p></div>';
    } else {
      const shown = state.products.filter(app => clean(app.name + " " + app.purpose + " " + app.group).includes(term));
      target.innerHTML = shown.length ? `<div class="os-platform-list">${shown.map(app => `<a href="${esc(safeExternal(app.url) || "#desktop")}" target="_blank" rel="noopener noreferrer"><span class="os-platform-icon">${icon("globe")}</span><span><strong>${esc(app.name)}</strong><small>${esc(app.purpose || app.group || "Nền tảng BDSG")}</small></span><span class="os-external-label">Mở website ${icon("external")}</span></a>`).join("")}</div>` : '<div class="os-empty"><h2>Chưa thấy nền tảng phù hợp.</h2><p>Thử từ khóa khác. Bạn cũng có thể tìm trên web bằng Trình duyệt BDSG.</p></div>';
    }
  }
  function safeExternal(value) { const result = window.BDSGOSState.normalizeAddress(value); return result?.kind === "url" ? result.url : null; }
  function renderSwitcher() {
    const snapshot = manager.snapshot();
    root.querySelector("#os-view").innerHTML = `<main class="os-switcher"><div class="os-section-heading"><div><h1>Ứng dụng đang mở</h1><p>Chuyển cửa sổ để tiếp tục công việc. Biểu mẫu được giữ khi chuyển ứng dụng.</p></div><button type="button" data-os-action="home" class="os-text-button">Xong</button></div>${snapshot.sessions.length ? `<div class="os-session-grid">${snapshot.mru.map(id => snapshot.sessions.find(session => session.id === id)).filter(Boolean).map(session => {
      const app = apps.find(item => item.id === session.appId);
      return `<article class="os-session"><button type="button" class="os-session-open" data-os-session="${esc(session.id)}"><span class="os-app-icon os-${app.color}">${icon(app.icon)}</span><h2>${esc(app.title)}</h2><p>${frames.has(session.id) ? "Cửa sổ còn trong bộ nhớ" : "Mở lại ứng dụng từ đầu"}</p><span>${session.status === "minimized" ? "Đã thu nhỏ" : "Sẵn sàng tiếp tục"} ${icon("arrow")}</span></button><button type="button" class="os-session-close" data-os-close="${esc(session.id)}" aria-label="Đóng ${esc(app.title)}">${icon("close")}</button></article>`;
    }).join("")}</div>` : '<section class="os-empty"><h2>Chưa có ứng dụng đang mở.</h2><p>Chọn một ứng dụng từ màn hình chính để bắt đầu.</p><button type="button" class="os-primary" data-os-action="home">Mở màn hình chính</button></section>'}<p class="os-footnote">Tải lại trang chỉ khôi phục danh sách cửa sổ, không khôi phục biểu mẫu chưa lưu. Đóng cửa sổ không tự hủy tác vụ trên máy chủ.</p></main>`;
  }
  function renderPreferences() {
    root.querySelector("#os-view").innerHTML = `<main class="os-preferences"><div class="os-section-heading"><div><h1>Tùy chỉnh</h1><p>Thiết lập giao diện trên thiết bị này.</p></div><button type="button" class="os-text-button" data-os-action="home">Xong</button></div><section class="os-setting-list"><label><span><strong>Chữ lớn</strong><small>Tăng cỡ chữ của không gian và ứng dụng nội bộ.</small></span><input type="checkbox" role="switch" data-os-preference="largeText" ${preferences.largeText ? "checked" : ""}></label><label><span><strong>Giảm chuyển động</strong><small>Chuyển ứng dụng không dùng hiệu ứng phóng.</small></span><input type="checkbox" role="switch" data-os-preference="reduceMotion" ${preferences.reduceMotion ? "checked" : ""}></label></section><section class="os-setting-list"><div><span><strong>BDSG Thanh Hoá</strong><small>Không gian ứng dụng trên web · phong cách iOS</small></span></div><div><span><strong>Phiên làm việc</strong><small>Tối đa 8 cửa sổ nội bộ. Cùng tài khoản, cùng quyền máy chủ.</small></span></div><div><span><strong>Dữ liệu và quyền</strong><small>Không lưu khóa hoặc nội dung công việc trong danh sách cửa sổ. Tìm web và mở nền tảng ngoài không tạo đăng nhập dùng chung.</small></span></div></section></main>`;
  }
  function frameFor(session) {
    if (frames.has(session.id)) return frames.get(session.id);
    const app = apps.find(item => item.id === session.appId);
    const frame = document.createElement("iframe"); frame.title = app.title; frame.className = "os-app-frame";
    frame.src = app.kind === "browser" ? "/trinh-duyet.html" : "/workspace.html" + app.route;
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads");
    frame.addEventListener("load", () => {
      frame.contentWindow?.postMessage({type:"bdsg-os-preferences", ...preferences}, location.origin);
      frame.contentWindow?.postMessage({type:"bdsg-os-visibility", visible:!frame.hidden && !root.hidden && surface === "app"}, location.origin);
    });
    root.querySelector("#os-frames").append(frame); frames.set(session.id, frame); return frame;
  }
  function draw() {
    if (!root || root.hidden || !manager) return;
    const snapshot = manager.snapshot();
    root.querySelector("#os-session-count").textContent = snapshot.sessions.length;
    root.querySelector("#os-account").textContent = state.user ? "Tài khoản" : "Đăng nhập";
    const active = surface === "app" && snapshot.sessions.find(session => session.id === snapshot.activeSessionId);
    root.querySelector("#os-stage").hidden = !active;
    root.querySelector("#os-view").hidden = !!active;
    root.classList.toggle("os-app-visible", !!active);
    for (const [id, frame] of frames) {
      frame.hidden = id !== active?.id;
      frame.inert = id !== active?.id;
      frame.contentWindow?.postMessage({type:"bdsg-os-visibility", visible:id === active?.id}, location.origin);
    }
    if (active) {
      const frame = frameFor(active); frame.hidden = false; frame.inert = false;
      root.querySelector("#os-window-title").textContent = apps.find(app => app.id === active.appId).title;
    } else if (surface === "switcher") renderSwitcher();
    else if (surface === "preferences") renderPreferences();
    else renderHome();
    persist(); applyPreferences();
  }
  async function openApp(id, newInstance = false) {
    if (!await window.BDSGSession.check() || !manager) { if (root && !root.hidden) notice("Chưa xác minh được phiên. Hãy thử lại sau khi tài khoản tải xong."); return null; }
    const session = manager.open(id, {newInstance});
    if (!session) { notice("Đã mở tối đa 8 cửa sổ. Hãy đóng một cửa sổ trước khi mở thêm."); return; }
    surface = "app"; draw(); return session;
  }
  function closeSession(id) {
    if (frames.has(id) && !confirm("Đóng cửa sổ này? Nội dung biểu mẫu chưa lưu có thể mất. Tác vụ đã gửi vẫn chạy trên máy chủ.")) return;
    manager.close(id); frames.get(id)?.remove(); frames.delete(id);
    if (!manager.snapshot().activeSessionId) surface = "home";
    draw();
  }
  async function handleClick(event) {
    const launch = event.target.closest("[data-os-app]"); if (launch) return openApp(launch.dataset.osApp);
    const selection = event.target.closest("[data-os-session]"); if (selection) { if (!await window.BDSGSession.check() || !manager) return; manager.activate(selection.dataset.osSession); surface = "app"; return draw(); }
    const close = event.target.closest("[data-os-close]"); if (close) return closeSession(close.dataset.osClose);
    const tab = event.target.closest("[data-os-group]"); if (tab) { group = tab.dataset.osGroup; return renderHome(); }
    const action = event.target.closest("[data-os-action]")?.dataset.osAction;
    if (!action) return;
    if (action === "home") surface = "home";
    if (action === "switcher") surface = "switcher";
    if (action === "preferences") surface = "preferences";
    if (action === "account") {
      if (!state.user) return auth(() => { syncIdentity(); draw(); });
      if (confirm("Đăng xuất tài khoản BDSG trên không gian này? Cửa sổ ứng dụng sẽ đóng.")) document.querySelector("#profile").click();
      return;
    }
    const snapshot = manager.snapshot();
    if (action === "close") return closeSession(snapshot.activeSessionId);
    if (action === "minimize") { manager.minimize(snapshot.activeSessionId); surface = "home"; }
    if (action === "duplicate") { const session = snapshot.sessions.find(item => item.id === snapshot.activeSessionId); if (session) return openApp(session.appId, true); }
    draw();
  }
  window.addEventListener("message", event => {
    if (event.origin !== location.origin || ![...frames.values()].some(frame => frame.contentWindow === event.source)) return;
    if (event.data?.type === "bdsg-os-login") auth(() => { syncIdentity(); draw(); });
    if (event.data?.type === "bdsg-os-logout") { document.querySelector("#profile").click(); }
    if (event.data?.type === "bdsg-os-session-changed") invalidateSession();
    if (event.data?.type === "bdsg-os-launch-route") window.BDSGDesktop.openRoute(event.data.route);
    if (event.data?.type === "bdsg-os-route") {
      const route = event.data.route, target = appIdForRoute(route);
      const entry = [...frames].find(([, frame]) => frame.contentWindow === event.source);
      const session = entry && manager?.snapshot().sessions.find(item => item.id === entry[0]);
      if (target && session && target !== session.appId) {
        const original = apps.find(app => app.id === session.appId);
        frames.get(session.id).contentWindow.location.hash = original.route;
        window.BDSGDesktop.openRoute(route);
      }
    }
  });
  document.addEventListener("keydown", event => {
    if (!root || root.hidden) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault(); surface = "home"; draw(); root.querySelector("#os-search")?.focus();
    }
    if (event.key === "Escape" && !document.querySelector("dialog[open]")) { surface = "home"; draw(); }
  });
  window.BDSGDesktop = {
    open() { ensureRoot(); syncIdentity(); root.hidden = false; document.body.classList.add("ios-desktop-active"); draw(); },
    openRoute(hash) {
      const id = appIdForRoute(hash);
      if (!id) return false;
      this.open(); openApp(id).then(session => {
        const frame = session && frames.get(session.id);
        if (frame && hash !== apps.find(app => app.id === id).route) frame.src = "/workspace.html" + hash;
      });
      return true;
    },
    leave() {
      if (root) root.hidden = true;
      for (const frame of frames.values()) frame.contentWindow?.postMessage({type:"bdsg-os-visibility", visible:false}, location.origin);
      document.body.classList.remove("ios-desktop-active");
    },
    reset() {
      if (storageKey) { try { sessionStorage.removeItem(storageKey); } catch (_) {} }
      for (const frame of frames.values()) frame.remove(); frames.clear();
      identity = null; manager = null; surface = "home"; query = "";
    },
  };
})();
