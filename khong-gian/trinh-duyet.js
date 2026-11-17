"use strict";
(() => {
  const MAX_TABS = 12;
  const fold = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
  const findProducts = (products, query) => {
    const terms = fold(query).trim().split(/\s+/).filter(Boolean);
    return products.filter((product) => terms.every((term) => fold([product.name, product.purpose, product.group].join(" ")).includes(term)));
  };
  const safeURL = (value) => {
    const normalize = typeof module !== "undefined" && module.exports
      ? require("./he-dieu-hanh-state.js").normalizeAddress
      : window.BDSGOSState?.normalizeAddress;
    if (typeof normalize !== "function" || typeof value !== "string" || !/^https:\/\//i.test(value)) return null;
    const entry = normalize(value);
    return entry?.kind === "url" ? entry.url : null;
  };
  function createSession() {
    let nextId = 1;
    const makeTab = () => ({ id: nextId++, history: [{ kind: "home" }], index: 0 });
    const tabs = [makeTab()];
    let selected = tabs[0].id;
    return {
      tabs,
      current: () => tabs.find((tab) => tab.id === selected),
      select(id) { if (tabs.some((tab) => tab.id === id)) selected = id; },
      add() { if (tabs.length >= MAX_TABS) return false; const tab = makeTab(); tabs.push(tab); selected = tab.id; return true; },
      close(id) {
        const index = tabs.findIndex((tab) => tab.id === id);
        if (index < 0) return;
        tabs.splice(index, 1);
        if (!tabs.length) tabs.push(makeTab());
        if (id === selected) selected = tabs[Math.min(index, tabs.length - 1)].id;
      },
      navigate(entry) { const tab = this.current(); tab.history.splice(tab.index + 1); tab.history.push(entry); tab.index = tab.history.length - 1; },
      move(delta) { const tab = this.current(); tab.index = Math.max(0, Math.min(tab.history.length - 1, tab.index + delta)); },
    };
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { fold, findProducts, safeURL, createSession, MAX_TABS };
    return;
  }

  const $ = (selector) => document.querySelector(selector);
  const session = createSession();
  const bookmarks = new Map();
  let products = [], catalogueState = "loading", request = 0, toastTimer;
  const currentEntry = () => { const tab = session.current(); return tab.history[tab.index]; };
  const entryKey = (entry) => entry.kind === "url" ? entry.url : entry.kind === "search" ? `search:${entry.query}` : null;
  const title = (entry) => entry.kind === "url" ? new URL(entry.url).hostname : entry.kind === "search" ? entry.query : entry.kind === "bookmarks" ? "Dấu trang" : "Tab mới";
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function announce(message) {
    clearTimeout(toastTimer);
    $("#notice").textContent = message;
    toastTimer = setTimeout(() => { $("#notice").textContent = ""; }, 4500);
  }
  function button(text, className, action) {
    const node = element("button", className, text);
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  }
  function externalLink(text, url, className) {
    const link = element("a", className, text);
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }
  function navigate(entry) { session.navigate(entry); render(); $("#page").focus({ preventScroll: true }); }
  function submitAddress(value) {
    const normalize = window.BDSGOSState?.normalizeAddress;
    if (typeof normalize !== "function") { announce("Thanh địa chỉ chưa sẵn sàng. Hãy tải lại ứng dụng."); return; }
    const entry = normalize(value);
    if (!entry) { announce("Nhập từ khóa hoặc địa chỉ HTTPS công khai hợp lệ, không kèm tài khoản."); return; }
    if (entry.kind === "url") {
      const url = safeURL(entry.url);
      if (!url) { announce("Địa chỉ website không hợp lệ."); return; }
      navigate({ kind: "url", url });
    } else if (entry.kind === "search" && typeof entry.query === "string" && entry.query.trim()) {
      navigate({ kind: "search", query: entry.query.trim().slice(0, 2048) });
    }
  }
  function renderTabs() {
    const strip = $("#session-tabs");
    strip.replaceChildren();
    session.tabs.forEach((tab) => {
      const selected = session.current().id === tab.id;
      const wrapper = element("div", `session-tab${selected ? " selected" : ""}`);
      const name = title(tab.history[tab.index]);
      const select = button(name, "tab-button", () => { session.select(tab.id); render(); });
      select.id = `session-tab-${tab.id}`;
      select.setAttribute("role", "tab");
      select.setAttribute("aria-selected", String(selected));
      select.setAttribute("aria-controls", "page");
      select.tabIndex = selected ? 0 : -1;
      select.title = name;
      select.addEventListener("keydown", (event) => {
        const index = session.tabs.indexOf(tab);
        let next;
        if (event.key === "ArrowRight") next = session.tabs[(index + 1) % session.tabs.length];
        if (event.key === "ArrowLeft") next = session.tabs[(index - 1 + session.tabs.length) % session.tabs.length];
        if (event.key === "Home") next = session.tabs[0];
        if (event.key === "End") next = session.tabs[session.tabs.length - 1];
        if (next) { event.preventDefault(); session.select(next.id); render(); $(`#session-tab-${next.id}`).focus(); }
      });
      const close = button("", "close-tab", () => { session.close(tab.id); render(); $(`#session-tab-${session.current().id}`).focus(); });
      close.setAttribute("aria-label", `Đóng tab ${name}`);
      // Biểu tượng cố định; tên và kết quả bên ngoài luôn đi qua textContent.
      close.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>';
      wrapper.append(select, close);
      strip.append(wrapper);
    });
    $("#new-tab").disabled = session.tabs.length >= MAX_TABS;
    $("#new-tab").title = session.tabs.length >= MAX_TABS ? "Đã đủ 12 tab trong phiên" : "Tab mới";
  }
  function render() {
    renderTabs();
    const entry = currentEntry(), tab = session.current();
    document.title = `${title(entry)} — Trình duyệt BDSG`;
    $("#address").value = entry.kind === "url" ? entry.url : entry.kind === "search" ? entry.query : "";
    $("#back").disabled = tab.index === 0;
    $("#forward").disabled = tab.index === tab.history.length - 1;
    const key = entryKey(entry), saved = !!key && bookmarks.has(key);
    $("#bookmark").disabled = !key;
    $("#bookmark").setAttribute("aria-pressed", String(saved));
    $("#bookmark").setAttribute("aria-label", saved ? "Bỏ lưu trang" : "Lưu trang");
    $("#show-bookmarks").setAttribute("aria-pressed", String(entry.kind === "bookmarks"));
    $("#page").setAttribute("aria-labelledby", `session-tab-${tab.id}`);
    renderPage();
  }
  function renderCatalogue(container, query) {
    if (catalogueState === "loading") {
      container.append(element("p", "", "Đang tải danh mục BDSG…"), element("div", "loading"));
      container.setAttribute("aria-busy", "true");
      return;
    }
    if (catalogueState === "error") {
      const error = element("section", "empty");
      error.append(element("h2", "", "Chưa tải được danh mục"), element("p", "", "Kiểm tra kết nối rồi thử lại để tìm các nền tảng BDSG."), button("Thử lại", "secondary", loadCatalogue));
      container.append(error);
      return;
    }
    const list = findProducts(products, query);
    container.append(element("p", "quiet", `${list.length} nền tảng trong danh mục công khai`));
    if (!list.length) {
      const empty = element("section", "empty");
      empty.append(element("h2", "", "Chưa có nền tảng phù hợp"), element("p", "", "Thử tên nền tảng hoặc nhu cầu ngắn hơn, như “khách hàng”, “học tập”."));
      container.append(empty);
      return;
    }
    const results = element("div", "list");
    for (const product of list) {
      const row = element("article", "result"), copy = element("div", "result-copy");
      copy.append(externalLink(product.name, product.url, "result-title"), element("p", "", product.purpose), element("p", "host", `${product.group} · ${new URL(product.url).hostname}`));
      const open = externalLink("Mở", product.url, "result-open");
      open.setAttribute("aria-label", `Mở ${product.name} trong tab thiết bị`);
      row.append(copy, open);
      results.append(row);
    }
    container.append(results);
  }
  function renderWebSearch(container, query) {
    const section = element("section", "web-search");
    section.append(element("h2", "", "Tìm trên web"), element("p", "", "Mở công cụ tìm kiếm trong tab thiết bị để xem kết quả web."));
    const actions = element("div", "actions");
    actions.append(externalLink("Tìm với Google", `https://www.google.com/search?q=${encodeURIComponent(query)}`, "secondary"), externalLink("Tìm với Bing", `https://www.bing.com/search?q=${encodeURIComponent(query)}`, "secondary"));
    section.append(actions);
    container.append(section);
  }
  function renderPage() {
    const page = $("#page"), entry = currentEntry();
    page.replaceChildren();
    page.removeAttribute("aria-busy");
    if (entry.kind === "home") {
      const intro = element("div", "intro");
      intro.append(element("h1", "", "Khám phá cùng BDSG"), element("p", "", "Tìm nền tảng cho công việc, hoặc mở một địa chỉ website."));
      const form = element("form", "home-search"), input = element("input");
      input.type = "search"; input.placeholder = "Bạn đang tìm gì?"; input.maxLength = 2048; input.setAttribute("aria-label", "Tìm trong BDSG hoặc nhập địa chỉ");
      const go = element("button", "primary", "Tìm kiếm"); go.type = "submit";
      form.append(input, go); form.addEventListener("submit", (event) => { event.preventDefault(); submitAddress(input.value); });
      const suggestions = element("div", "suggestions");
      for (const label of ["Khách hàng", "Học tập", "Thương mại", "AI"]) suggestions.append(button(label, "", () => submitAddress(label)));
      page.append(intro, form, suggestions, element("h2", "", "Nền tảng BDSG"));
      renderCatalogue(page, "");
    } else if (entry.kind === "search") {
      const heading = element("div", "search-header");
      heading.append(element("h1", "", `Tìm “${entry.query}”`));
      page.append(heading);
      renderCatalogue(page, entry.query);
      renderWebSearch(page, entry.query);
    } else if (entry.kind === "url") {
      page.append(element("h1", "", "Mở website"), element("p", "", "Website mở trong tab thiết bị. Bạn tiếp tục duyệt và đăng nhập trực tiếp tại website đó."));
      const section = element("section", "destination");
      section.append(element("h2", "", new URL(entry.url).hostname), element("p", "url", entry.url));
      const actions = element("div", "actions");
      actions.append(externalLink("Mở website", entry.url, "primary"));
      section.append(actions);
      page.append(section, element("p", "quiet", "Nút quay lại và tiến tới chỉ di chuyển giữa các trang trong ứng dụng này."));
    } else if (entry.kind === "bookmarks") {
      page.append(element("h1", "", "Dấu trang"), element("p", "", "Các địa chỉ và lượt tìm kiếm bạn đã lưu trong phiên này. Tải lại ứng dụng sẽ xóa dấu trang."));
      if (!bookmarks.size) {
        const empty = element("section", "empty");
        empty.append(element("h2", "", "Giữ lại trang đang cần"), element("p", "", "Tìm kiếm hoặc nhập một địa chỉ, rồi chọn nút Lưu trang trên thanh công cụ."));
        page.append(empty);
      } else {
        const list = element("div", "list");
        for (const [key, saved] of bookmarks) {
          const row = element("article", "result"), copy = element("div", "result-copy");
          copy.append(button(title(saved), "secondary", () => navigate({ ...saved })), element("p", "host", saved.kind === "url" ? saved.url : "Tìm trong BDSG"));
          row.append(copy, button("Xóa", "remove", () => { bookmarks.delete(key); render(); announce("Đã xóa dấu trang."); }));
          list.append(row);
        }
        page.append(list);
      }
    }
  }
  async function loadCatalogue() {
    const version = ++request, controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    catalogueState = "loading";
    renderPage();
    try {
      const response = await fetch("/api/catalogue", { credentials: "same-origin", signal: controller.signal });
      if (!response.ok) throw new Error("catalogue");
      const data = await response.json();
      if (!Array.isArray(data.products)) throw new Error("catalogue");
      const cleanProducts = data.products.slice(0, 1000).filter((product) => product && typeof product.name === "string" && safeURL(product.url)).map((product) => ({ name: product.name.slice(0, 200), purpose: String(product.purpose || "").slice(0, 1000), group: String(product.group || "").slice(0, 120), url: safeURL(product.url) }));
      if (version !== request) return;
      products = cleanProducts;
      catalogueState = "ready";
    } catch (_) { if (version === request) catalogueState = "error"; }
    finally { clearTimeout(timer); if (version === request) renderPage(); }
  }
  $("#address-form").addEventListener("submit", (event) => { event.preventDefault(); submitAddress($("#address").value); });
  $("#address").addEventListener("focus", (event) => event.target.select());
  $("#new-tab").addEventListener("click", () => { if (!session.add()) return; render(); $("#address").focus(); });
  $("#back").addEventListener("click", () => { session.move(-1); render(); });
  $("#forward").addEventListener("click", () => { session.move(1); render(); });
  $("#reload").addEventListener("click", () => {
    if (["home", "search"].includes(currentEntry().kind)) loadCatalogue();
    else { render(); announce(currentEntry().kind === "url" ? "Đã làm mới địa chỉ. Chọn Mở website để tải website trong tab thiết bị." : "Đã làm mới danh sách dấu trang."); }
  });
  $("#bookmark").addEventListener("click", () => {
    const entry = currentEntry(), key = entryKey(entry);
    if (!key) return;
    if (bookmarks.has(key)) { bookmarks.delete(key); announce("Đã bỏ lưu trang."); }
    else { bookmarks.set(key, { ...entry }); announce("Đã lưu trang trong phiên này."); }
    render();
  });
  $("#show-bookmarks").addEventListener("click", () => { if (currentEntry().kind !== "bookmarks") navigate({ kind: "bookmarks" }); });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "l") { event.preventDefault(); $("#address").focus(); $("#address").select(); }
    if (event.altKey && ["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); session.move(event.key === "ArrowLeft" ? -1 : 1); render(); }
    if (event.key === "Escape" && document.activeElement === $("#address")) { render(); $("#page").focus(); }
  });
  window.addEventListener("message", (event) => {
    if (event.origin !== location.origin || event.source !== window.parent || event.data?.type !== "bdsg-os-preferences") return;
    document.documentElement.classList.toggle("ios-large-text", event.data.largeText === true);
    document.documentElement.classList.toggle("ios-reduce-motion", event.data.reduceMotion === true);
  });
  render();
  const initialQuery = new URLSearchParams(location.search).get("q");
  if (initialQuery) submitAddress(initialQuery.slice(0, 2048));
  loadCatalogue();
})();
