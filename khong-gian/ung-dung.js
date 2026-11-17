"use strict";
const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const clean = (v) =>
  String(v)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
let saved = [];
try {
  saved = JSON.parse(localStorage.getItem("bdsg-thanhhoa-favorites") || "[]");
  if (!Array.isArray(saved)) saved = [];
} catch (_) {}
const state = {
  products: [],
  user: null,
  requests: [],
  agents: [],
  messages: [],
  events: [],
  connections: [],
  saved,
  view: "overview",
  query: "",
  group: "all",
  sector: null,
  onlySaved: false,
  peer: null,
  checkedAt: null,
  endpoint: location.origin + "/mcp",
};
const sectors = [
  {
    id: "bat-dong-san",
    name: "Bất động sản",
    icon: "home",
    color: "#7b8e57",
    description:
      "Kết nối nhu cầu, nguồn cung và dịch vụ bất động sản tại địa phương.",
  },
  {
    id: "thuong-mai",
    name: "Thương mại & dịch vụ",
    icon: "briefcase",
    color: "#b28b59",
    description:
      "Phát triển kênh bán hàng, dịch vụ, du lịch và mạng lưới đối tác.",
  },
  {
    id: "van-hanh",
    name: "Vận hành doanh nghiệp",
    icon: "route",
    color: "#527e97",
    description: "Từ khách hàng, bán hàng tới nguồn lực và quy trình vận hành.",
  },
  {
    id: "cong-nghe",
    name: "AI & công nghệ",
    icon: "spark",
    color: "#66857c",
    description:
      "Ứng dụng AI, dữ liệu, bản đồ, hạ tầng và không gian số vào kinh doanh.",
  },
  {
    id: "nong-nghiep",
    name: "Nông nghiệp",
    icon: "globe",
    color: "#6c9a6e",
    description: "Tiếp cận nền tảng cho trang trại và hoạt động nông nghiệp.",
  },
  {
    id: "tri-thuc",
    name: "Tri thức & cộng đồng",
    icon: "link",
    color: "#937797",
    description: "Học tập, chia sẻ tri thức và xây dựng cộng đồng kinh doanh.",
  },
];
const stages = [
  ["tu-van", "Tư vấn", "Hiểu đúng nhu cầu"],
  ["trien-khai", "Triển khai", "Đưa giải pháp vào thực tế"],
  ["van-hanh", "Vận hành", "Giữ công việc chạy đều"],
  ["kinh-doanh", "Kinh doanh", "Mở rộng cơ hội tăng trưởng"],
];
const titles = {
  account: "Tài khoản",
  system: "Máy chủ",
  integrations: "Quản lý kết nối",
  support: "Hỗ trợ khách hàng",
  settings: "Cài đặt ChatGPT",
  projects: "Dự án công việc",
  studio: "Xưởng công việc",
  office: "Văn phòng BDSG",
  work: "Giao việc",
  tasks: "Công việc của tôi",
  staff: "Nhân sự Agent",
  "ai-settings": "Trung tâm AI",
  modules: "Mô-đun BDSG",
  overview: "Tổng quan",
  platforms: "Nền tảng BDSG",
  sectors: "Lĩnh vực kinh doanh",
  requests: "Yêu cầu & triển khai",
  agents: "Không gian agent",
  connections: "Kết nối & MCP",
  activity: "Nhật ký hoạt động",
};
const main = $("#main");
let afterLogin = null,
  toastTimer,
  refreshVersion = 0;

const activeUnitRequests = new Set();
async function api(path, options = {}, brokered = false) {
  const unit = window.BDSGUnit;
  const scopeHeaders = unit?.headers(path) || {};
  const token = unit?.capture();
  const publicRead = ["/api/me", "/api/catalogue", "/api/auth/google", "/api/ready"].includes(path);
  const scoped = !!scopeHeaders["X-BDSG-Unit"] || (!publicRead && !path.startsWith('/api/sessions') && !path.startsWith('/api/units') && !path.startsWith('/api/auth/') && !['/api/login','/api/logout'].includes(path));
  let sharedRead = !options.method && !publicRead;
  if (path === "/api/tools" && options.body) {
    try { sharedRead = ["mo_dun.danh_sach", "du_an.danh_sach"].includes(JSON.parse(options.body).name); } catch (_) {}
  }
  if (!brokered && sharedRead && location.pathname === "/workspace.html" && parent !== window && parent.BDSGReadBroker) {
    return parent.BDSGReadBroker.read(path + "|" + (options.body || ""), unit?.contextKey() || state.user?.id || "guest", () => api(path, options, true));
  }
  const controller = new AbortController();
  if (scoped) activeUnitRequests.add(controller);
  const headers = new Headers(options.headers || {});
  // Người gọi không thể ghi đè phạm vi đã chụp, kể cả bằng tên header khác hoa/thường.
  for (const name of ['X-BDSG-Unit','X-BDSG-Unit-Epoch','X-BDSG-Unit-Revision','X-BDSG-Actor']) headers.delete(name);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type','application/json');
  if (state.user?.id && !["/api/me", "/api/catalogue", "/api/login"].includes(path) && !path.startsWith('/api/auth/')) headers.set('X-BDSG-Actor', token?.actorId || state.user.id);
  for (const [name,value] of Object.entries(scopeHeaders)) headers.set(name,value);
  const stale = () => controller.signal.aborted || (scoped && unit && !unit.current(token));
  const changedError = () => Object.assign(new Error('Phạm vi làm việc đã thay đổi. Hãy mở lại ứng dụng.'),{name:'AbortError'});
  try {
    const r = await fetch(path, {
      credentials: "same-origin", ...options, headers,
      signal: options.signal ? AbortSignal.any([controller.signal,options.signal]) : controller.signal,
    });
    if (stale()) throw changedError();
    let data;
    try { data = await r.json(); } catch (_) {
      if (stale()) throw changedError();
      throw new Error("Dịch vụ chưa sẵn sàng. Vui lòng thử lại.");
    }
    if (stale()) throw changedError();
    if (!r.ok) {
      if (data.code === "identity_changed") window.BDSGSession?.invalidate();
      if ([403,409].includes(r.status) && data.code === 'unit_changed') {
        void unit?.refresh({invalidate:true});
        throw changedError();
      }
      throw new Error(data.error || "Chưa hoàn tất được yêu cầu.");
    }
    return data;
  } finally { activeUnitRequests.delete(controller); }
}
async function tool(name, args = {}) {
  const r = await api("/api/tools", {
    method: "POST",
    body: JSON.stringify({ name, arguments: args }),
  });
  if (!r.ok)
    throw new Error(
      r.ly_do || "Công cụ chưa sẵn sàng trong phạm vi quyền của bạn.",
    );
  return r.ket_qua;
}
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3800);
}
function sectorOf(p) {
  if (p.group === "Bất động sản") return "bat-dong-san";
  if (p.group === "Vận hành") return "van-hanh";
  if (p.group === "Nông nghiệp") return "nong-nghiep";
  if (["Thương mại số", "Dịch vụ chuyên môn"].includes(p.group))
    return "thuong-mai";
  if (["Tri thức", "Cộng đồng"].includes(p.group)) return "tri-thuc";
  return "cong-nghe";
}
function date(value) {
  return value
    ? new Date(typeof value === "number" ? value * 1000 : value).toLocaleString(
        "vi-VN",
        {
          timeZone: "Asia/Ho_Chi_Minh",
          hour: "2-digit",
          minute: "2-digit",
          day: "2-digit",
          month: "2-digit",
        },
      )
    : "Chưa đo";
}
function heading(label, title, description, action = "") {
  return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${action}</div>`;
}
function webState(p) {
  const s = p.web?.state;
  return s === "co-phan-hoi"
    ? ["ok", "Có phản hồi web"]
    : s === "can-dang-nhap"
      ? ["ok", "Cần đăng nhập"]
      : s === "gioi-han-truy-cap"
        ? ["warn", "Giới hạn truy cập"]
        : s === "khong-phan-hoi"
          ? ["warn", "Chưa truy cập được"]
          : ["", "Chưa kiểm tra web"];
}
function card(p) {
  const color = /^#[a-f0-9]{6}$/i.test(p.color) ? p.color : "#136b61";
  const status = webState(p);
  const fav = state.saved.includes(p.id);
  const short =
    p.name
      .replace(/BDSG\s*/i, "")
      .slice(0, 2)
      .toUpperCase() || "B";
  return `<article class="platform-card" style="--color:${color};--tint:${color}0d"><div class="card-top"><div class="app-icon">${esc(short)}</div><button class="favorite ${fav ? "saved" : ""}" data-save="${esc(p.id)}" aria-label="${fav ? "Bỏ lưu" : "Lưu"} ${esc(p.name)}" aria-pressed="${fav}">${icon("heart")}</button></div><h3>${esc(p.name)}</h3><p>${esc(p.purpose)}</p><div class="card-footer"><span class="web-state ${status[0]}" title="Phản hồi trang web không xác nhận đăng nhập hoặc liên thông dữ liệu">${status[1]}</span><a class="open-app" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Mở ${icon("external")}</a></div></article>`;
}
function process() {
  return `<div class="process">${stages.map((s, i) => `<div class="process-step"><span class="step-number">0${i + 1}</span><strong>${s[1]}</strong><small>${s[2]}</small></div>`).join("")}</div>`;
}
function section(title, desc, link, hash) {
  return `<div class="section-heading"><div><h2>${title}</h2>${desc ? `<p>${desc}</p>` : ""}</div>${link ? `<a class="text-link" href="#${hash}">${link} ${icon("arrow")}</a>` : ""}</div>`;
}
function empty(title, description, ico = "grid") {
  return `<div class="empty">${icon(ico)}<strong>${esc(title)}</strong>${esc(description)}</div>`;
}
function overview() {
  const priority = [
    "bdsg_crm",
    "bdsg_land",
    "bdsg_aichat",
    "bdsg_erp",
    "bdsg_shop",
    "bdsg_academy",
    "bdsg_map",
    "bdsg_agent",
  ];
  let selected = state.saved.length
    ? state.products.filter((p) => state.saved.includes(p.id))
    : priority
        .map((id) => state.products.find((p) => p.id === id))
        .filter(Boolean);
  const online = state.products.filter((p) =>
    ["co-phan-hoi", "can-dang-nhap"].includes(p.web?.state),
  ).length;
  main.innerHTML =
    heading(
      "BDSG THANH HOÁ",
      "Kết nối để cùng phát triển.",
      "Một không gian điều phối công nghệ và phát triển kinh doanh tại Thanh Hoá.",
      `<span class="date-label">${esc(new Intl.DateTimeFormat("vi-VN", { dateStyle: "long", timeZone: "Asia/Ho_Chi_Minh" }).format(new Date()))}</span>`,
    ) +
    `<section class="hero"><div class="hero-copy"><h2>Công nghệ kết nối.<br><span>Kinh doanh rộng mở.</span></h2><p>Tiếp cận các nền tảng BDSG, kết nối đúng lĩnh vực và đưa nhu cầu của bạn đi từ ý tưởng đến hoạt động kinh doanh.</p><div class="hero-buttons"><a class="button white" href="#platforms">Khám phá nền tảng ${icon("arrow")}</a><button class="button outline-light" data-new-request>${icon("plus")} Tạo yêu cầu kinh doanh</button></div></div></section>` +
    `<section class="stats" aria-label="Tổng quan không gian"><div class="stat"><div class="stat-top">Nền tảng trong danh mục ${icon("grid")}</div><strong>${state.products.length}</strong><small>Mở từ một không gian duy nhất</small></div><div class="stat"><div class="stat-top">Có phản hồi trang web ${icon("globe")}</div><strong>${state.checkedAt ? online : "—"}</strong><small>${state.checkedAt ? "Kiểm tra " + date(state.checkedAt) : "Chưa có lần đo kết nối"}</small></div><div class="stat"><div class="stat-top">Yêu cầu đang quản lý ${icon("briefcase")}</div><strong>${state.user ? state.requests.length : "—"}</strong><small>${state.user ? "Dữ liệu trong không gian của bạn" : "Đăng nhập để xem công việc"}</small></div><div class="stat"><div class="stat-top">Đầu nối MCP nghiệp vụ ${icon("link")}</div><strong>${state.user ? state.connections.length : "—"}</strong><small>${state.user ? "Số đầu nối đã khai báo" : "Đăng nhập để xem kết nối"}</small></div></section>` +
    section(
      state.saved.length ? "Nền tảng đã lưu" : "Bắt đầu cùng hệ sinh thái",
      "Các nền tảng để bắt đầu công việc của bạn.",
      "Xem tất cả",
      "platforms",
    ) +
    `<section class="platform-grid">${selected.slice(0, 8).map(card).join("")}</section>` +
    `<div class="two-columns"><section class="panel" style="margin-top:25px"><div class="panel-head"><h2>Một hành trình phát triển kinh doanh</h2><a class="text-link" href="#requests">Tạo yêu cầu ${icon("arrow")}</a></div>${process()}</section><section class="panel" style="margin-top:25px"><div class="panel-head"><h2>Kết nối có kiểm soát</h2><span class="mini-tag">MCP</span></div><div class="connect-summary"><div class="app-icon">${icon("link")}</div><div><strong>Nền tảng riêng. Cùng một cách kết nối.</strong><p>Mở nền tảng để sử dụng ngay. Kết nối dữ liệu qua đầu nối được cấp quyền khi có cấu hình.</p><a class="text-link" href="#connections">Khám phá kết nối ${icon("arrow")}</a></div></div></section></div>`;
}
function platforms() {
  let list = state.products.filter(
    (p) =>
      (state.group === "all" || p.group === state.group) &&
      (!state.sector || sectorOf(p) === state.sector) &&
      (!state.onlySaved || state.saved.includes(p.id)) &&
      clean(p.name + " " + p.purpose + " " + p.group).includes(
        clean(state.query),
      ),
  );
  const groupNames = [...new Set(state.products.map((p) => p.group))];
  main.innerHTML =
    heading(
      "HỆ SINH THÁI MỞ",
      "Nền tảng cho mọi bước phát triển.",
      "Khám phá và mở ứng dụng gốc của BDSG. Tài khoản và dữ liệu được quản lý tại từng nền tảng.",
    ) +
    `<div class="toolbar"><div class="search-field">${icon("search")}<input id="catalogue-search" type="search" value="${esc(state.query)}" placeholder="Tìm kiếm nền tảng, nhu cầu, lĩnh vực…" aria-label="Tìm kiếm nền tảng"></div><button class="button ${state.onlySaved ? "primary" : ""}" data-only-saved>${icon("heart")}Đã lưu (${state.saved.length})</button></div><div class="filters"><button class="filter ${state.group === "all" && !state.sector ? "active" : ""}" data-group="all">Tất cả nền tảng</button>${groupNames.map((g) => `<button class="filter ${state.group === g ? "active" : ""}" data-group="${esc(g)}">${esc(g)}</button>`).join("")}</div><div class="catalogue-meta">${list.length} nền tảng${state.sector ? " · " + esc(sectors.find((s) => s.id === state.sector)?.name) : ""} · ${state.checkedAt ? "Kiểm tra web " + date(state.checkedAt) : "Chưa có lần đo web"} · Mở liên kết không đồng nghĩa đã liên thông dữ liệu</div><section class="platform-grid" id="catalogue-grid">${list.length ? list.map(card).join("") : ""}</section>${list.length ? "" : empty("Chưa có kết quả phù hợp", "Thử từ khoá khác hoặc bỏ bộ lọc.", "search")}`;
}
function sectorsPage() {
  main.innerHTML =
    heading(
      "ĐI SÂU VÀO KINH DOANH",
      "Bắt đầu từ lĩnh vực của bạn.",
      "Chọn đúng nhu cầu, tiếp cận đúng nền tảng và xây dựng lộ trình triển khai.",
    ) +
    `<section class="sector-grid">${sectors.map((s) => `<article class="sector-card" style="--color:${s.color};--tint:${s.color}0e"><div class="app-icon">${icon(s.icon)}</div><h2>${s.name}</h2><p>${s.description}</p><span class="sector-count">${state.products.filter((p) => sectorOf(p) === s.id).length} nền tảng trong danh mục</span><div class="hero-buttons"><button class="button small" data-sector="${s.id}">Xem nền tảng ${icon("arrow")}</button><button class="text-link" data-request-sector="${s.id}">Tạo yêu cầu ${icon("plus")}</button></div></article>`).join("")}</section>`;
}
function locked(title, description) {
  main.innerHTML =
    heading("KHÔNG GIAN CỦA BẠN", title, description) +
    `<section class="locked"><div class="lock-icon">${icon("lock")}</div><h2>Công việc riêng cần một danh tính.</h2><p>Đăng nhập để quản lý yêu cầu, trao đổi với các hộp thư agent và theo dõi hoạt động trong phạm vi quyền của bạn.</p><button class="button primary" data-login>Đăng nhập không gian ${icon("arrow")}</button></section>`;
}
function requestsPage() {
  if (!state.user)
    return locked(
      "Từ nhu cầu đến kết quả.",
      "Quản lý yêu cầu qua từng chặng phát triển kinh doanh.",
    );
  main.innerHTML =
    heading(
      "TIẾN TRÌNH KINH DOANH",
      "Từ nhu cầu đến kết quả.",
      "Ghi nhận và quản lý yêu cầu thực tế của bạn.",
      `<button class="button primary" data-new-request>${icon("plus")}Tạo yêu cầu</button>`,
    ) +
    `<div class="request-grid">${stages
      .map(([key, label]) => {
        const items = state.requests.filter((r) => r.stage === key);
        return `<section class="kanban"><div class="kanban-head">${label}<span>${items.length}</span></div>${items.map((r) => `<article class="request-card"><span class="small-label">${esc(sectors.find((s) => s.id === r.sector)?.name || r.sector)}</span><strong>${esc(r.title)}</strong><p>${esc(r.description)}</p><select aria-label="Chặng của ${esc(r.title)}" data-stage="${esc(r.id)}">${stages.map(([id, name]) => `<option value="${id}" ${id === r.stage ? "selected" : ""}>${name}</option>`).join("")}</select></article>`).join("") || '<div class="muted" style="font-size:10px">Chưa có yêu cầu ở chặng này.</div>'}</section>`;
      })
      .join("")}</div>`;
}
function selectedAgent() {
  return (
    state.agents.find((a) => a.id === state.peer) ||
    state.agents.find((a) => a.active)
  );
}
function messageMarkup() {
  const agent = selectedAgent();
  if (!agent)
    return empty(
      "Chưa có agent được đăng ký",
      "Chủ quản đăng ký danh tính MCP trước khi trao đổi.",
      "spark",
    );
  const rows = state.messages.filter(
    (m) => m.sender === agent.id || m.recipient === agent.id,
  );
  return rows.length
    ? rows
        .map(
          (m) =>
            `<article class="message ${m.sender === state.user.id ? "mine" : ""}"><small>${esc(m.sender === state.user.id ? "Bạn" : agent.name)} · ${date(m.created)}</small><p>${esc(m.body)}</p></article>`,
        )
        .join("")
    : empty(
        "Bắt đầu một trao đổi có ngữ cảnh",
        "Thông điệp được giao vào hộp thư MCP. Agent có thể đọc và trả lời bằng danh tính riêng.",
        "spark",
      );
}
function agentsPage() {
  if (!state.user)
    return locked(
      "Cùng agent làm việc có ngữ cảnh.",
      "Kênh trao đổi giữa con người và các danh tính agent qua MCP.",
    );
  const agent = selectedAgent();
  state.peer = agent?.id || null;
  main.innerHTML =
    heading(
      "ĐIỀU PHỐI CÓ DANH TÍNH",
      "Cùng agent làm việc có ngữ cảnh.",
      "Mỗi agent có chứng thư và hộp thư riêng. Nội dung chỉ hiện với bên gửi và bên nhận.",
    ) +
    `<div class="agent-layout"><section class="panel"><div class="panel-head"><h2>Danh tính agent</h2><span class="mini-tag">${state.agents.filter((a) => a.active).length}</span></div><div class="agent-list">${
      state.agents
        .filter((a) => a.active)
        .map(
          (a) =>
            `<button class="agent-choice ${state.peer === a.id ? "selected" : ""}" data-peer="${esc(a.id)}"><div class="app-icon">${icon("spark")}</div><span><strong>${esc(a.name)}</strong><small>Hộp thư MCP sẵn sàng</small></span></button>`,
        )
        .join("") || '<p class="muted">Chưa đăng ký agent.</p>'
    }</div></section><section class="panel chat-panel"><div class="chat-heading"><strong>${esc(agent?.name || "Không gian trao đổi")}</strong><small>Kênh thông điệp MCP · xác thực từng danh tính</small></div><div class="messages" id="messages">${messageMarkup()}</div><form class="chat-form" id="message-form"><textarea name="body" rows="2" maxlength="4000" required placeholder="Gửi ngữ cảnh hoặc yêu cầu tới hộp thư agent…" aria-label="Nội dung thông điệp" ${agent ? "" : "disabled"}></textarea><button class="button primary" type="submit" ${agent ? "" : "disabled"}>${icon("send")}<span>Gửi</span></button></form><div class="chat-note">Kênh trao đổi đã hoạt động. Mô hình hội thoại AI và các agent xử lý tự động chưa được cấu hình.</div></section></div>`;
}
function connectionsPage() {
  main.innerHTML =
    heading(
      "LIÊN THÔNG CÓ KIỂM SOÁT",
      "Kết nối đúng quyền. Dữ liệu đúng nơi.",
      "Phân biệt rõ mở trang web, kết nối MCP và quyền thao tác trên nền tảng.",
    ) +
    `<div class="connection-overview"><section class="panel connection-detail"><div class="app-icon">${icon("link")}</div><h2>Cổng MCP Thanh Hoá</h2><p>Cổng chung để các danh tính được cấp quyền tra cứu danh mục, quản lý yêu cầu và trao đổi thông điệp. Chứng thư agent được chủ quản cấp riêng.</p><div class="endpoint"><code>${esc(state.endpoint)}</code><button class="icon-button" data-copy-endpoint aria-label="Sao chép địa chỉ MCP">${icon("link")}</button></div><div class="filters"><span class="mini-tag">Xác thực Bearer</span><span class="mini-tag">Quyền theo công cụ</span><span class="mini-tag">Nhật ký qua nhân BDSG</span></div><div class="info-box">Mở một nền tảng bằng liên kết web chưa tạo đăng nhập dùng chung hoặc đồng bộ dữ liệu. Mỗi đầu nối nghiệp vụ cần được cấu hình và cấp quyền riêng.</div></section><section class="panel"><div class="panel-head"><h2>Trạng thái kết nối</h2><span class="mini-tag">Thanh Hoá</span></div><div class="connection-list"><div class="connection-row">${icon("grid")}Danh mục nền tảng<span>${state.products.length} mục</span></div><div class="connection-row">${icon("lock")}Cổng MCP<span>Xác thực bắt buộc</span></div><div class="connection-row">${icon("spark")}Kênh thông điệp agent<span>Đã triển khai</span></div><div class="connection-row">${icon("link")}MCP nghiệp vụ bên ngoài<span>${state.user ? state.connections.length + " đã khai báo" : "Cần đăng nhập"}</span></div><div class="connection-row">${icon("globe")}Đăng nhập BDSG tổng<span>Chưa kết nối</span></div></div><div style="padding:0 22px 22px"><p class="muted" style="font-size:10px">Chỉ công cụ nằm trong danh sách cho phép mới được chuyển tới nền tảng đích. Quyền đọc và quyền ghi được khai riêng.</p><a class="text-link" href="https://github.com/BDSG-VN/open-bdsg/pull/1" target="_blank" rel="noopener noreferrer">Xem đóng góp mã nguồn ${icon("external")}</a></div></section></div>`;
}
const eventNames = {
  "dang-nhap": "Đăng nhập không gian",
  "tao-yeu-cau": "Tạo yêu cầu kinh doanh",
  "doi-chang": "Cập nhật chặng triển khai",
  "gui-thong-diep": "Gửi thông điệp agent",
};
function activityPage() {
  if (!state.user)
    return locked(
      "Mỗi hành động đều có dấu vết.",
      "Theo dõi ai đã làm gì trong không gian Thanh Hoá.",
    );
  main.innerHTML =
    heading(
      "MINH BẠCH TRONG VẬN HÀNH",
      "Mỗi hành động đều có dấu vết.",
      "Nhật ký thao tác không hiển thị mật khẩu, chứng thư hoặc nội dung thông điệp.",
    ) +
    `<section class="panel"><div class="panel-head"><h2>Hoạt động gần đây</h2><span class="mini-tag">${state.events.length} bản ghi gần nhất</span></div><div class="activity-list">${state.events.length ? state.events.map((e) => `<div class="event"><span class="event-dot"></span><div><strong>${esc(eventNames[e.action] || e.action)}</strong><small>${esc(e.actor)}${e.target ? " · " + esc(e.target) : ""}</small></div><time>${date(e.created)}</time></div>`).join("") : empty("Chưa có hoạt động", "Các thao tác mới sẽ được ghi nhận tại đây.", "activity")}</div></section>`;
}
function render() {
  window.BDSGConnections?.reset();
  window.BDSGSessions?.leave();
  window.BDSGNode?.leave();
  if (location.pathname !== "/workspace.html" && window.BDSGDesktop) {
    if (!location.hash || location.hash === "#desktop") {
      window.BDSGDesktop.open();
      document.title = "BDSG Thanh Hoá — Màn hình chính";
      return;
    }
    if (window.BDSGDesktop.openRoute(location.hash)) return;
  }
  window.BDSGDesktop?.leave();
  if (window.BDSGOffice?.leave(location.hash) === false) return;
  const taskMatch = /^#task\/([a-f0-9]{24})$/.exec(location.hash);
  const supportMatch = /^#support\/([a-z0-9_-]{1,80})$/.exec(location.hash);
  state.view = Object.hasOwn(titles, location.hash.slice(1))
    ? location.hash.slice(1)
    : supportMatch
      ? "support"
      : taskMatch
      ? "tasks"
      : "work";
  $("#view-title").textContent = titles[state.view];
  document.title = titles[state.view] + " — BDSG Thanh Hoá";
  document.querySelectorAll("nav [data-view]").forEach((a) => {
    const on = a.dataset.view === state.view;
    a.classList.toggle("active", on);
    on
      ? a.setAttribute("aria-current", "page")
      : a.removeAttribute("aria-current");
  });
  if (taskMatch) {
    window.BDSGTasks?.renderTask(taskMatch[1]);
    return;
  }
  if (supportMatch) {
    window.BDSGSupport?.open(supportMatch[1]);
    return;
  }
  ({
    account: () => window.BDSGSessions?.open(),
    system: () => window.BDSGNode?.open(),
    integrations: () => window.BDSGConnectors?.open(),
    support: () => window.BDSGSupport?.open(),
    settings: () => window.BDSGSupport?.settings(),
    projects: () => window.BDSGProjects?.open(),
    studio: () => window.BDSGStudio?.open(),
    office: () => window.BDSGOffice?.open(),
    work: () => window.BDSGTasks?.home(),
    tasks: () => window.BDSGTasks?.tasks(),
    staff: () => window.BDSGStaff?.open(),
    "ai-settings": () => window.BDSGAI?.open(),
    modules: () => window.BDSGTasks?.modules(),
    overview,
    platforms,
    sectors: sectorsPage,
    requests: requestsPage,
    agents: agentsPage,
    connections: connectionsPage,
    activity: activityPage,
  })[state.view]();
}
function auth(callback) {
  if (location.pathname === "/workspace.html" && parent !== window && !state.user) {
    parent.postMessage({type:"bdsg-os-login"}, location.origin);
    return;
  }
  if (state.user) {
    callback?.();
    return;
  }
  afterLogin = callback;
  $("#login-error").textContent = "";
  $("#google-login-error").hidden = true;
  $("#login-dialog").showModal();
  api('/api/auth/google')
    .then(data => {
      $('#google-login-option').hidden = !data.available;
      $('#google-login-note').textContent = data.registration === 'public'
        ? 'Đăng nhập hoặc tạo tài khoản bằng Google. Không yêu cầu quyền Drive.'
        : 'Dùng tài khoản Google đã được mời. Không yêu cầu quyền Drive.';
    })
    .catch(() => { $('#google-login-option').hidden = true; });
}
function newRequest(sector) {
  auth(() => {
    $("#request-sector").innerHTML = sectors
      .map(
        (s) =>
          `<option value="${s.id}" ${s.id === sector ? "selected" : ""}>${s.name}</option>`,
      )
      .join("");
    $("#request-error").textContent = "";
    $("#request-dialog").showModal();
  });
}
async function loadPrivate() {
  if (!state.user || window.BDSGUnit?.snapshot().mode === 'units') return;
  // Các ứng dụng có API riêng không cần tải lại toàn bộ hộp thư/nhật ký khi mở cửa sổ.
  if (!['#overview', '#requests', '#agents', '#activity', '#connections'].includes(location.hash)) return;
  const actor = state.user.id;
  const routes = [
    ["requests", "/api/requests", "requests"],
    ["agents", "/api/agents", "agents"],
    ["messages", "/api/messages", "messages"],
    ["events", "/api/activity", "events"],
    ["connections", "/api/connections", "connections"],
  ];
  await Promise.all(
    routes.map(async ([key, path, field]) => {
      const r = await api(path);
      if (r.ok && state.user?.id === actor) state[key] = r.ket_qua[field];
    }),
  );
}
async function refresh() {
  let version = ++refreshVersion;
  const [catalog, me] = await Promise.all([
    api("/api/catalogue"),
    api("/api/me"),
  ]);
  if (version !== refreshVersion) return;
  if ((state.user?.id || "guest") !== (me.user?.id || "guest")) { clearPrivateState(); version = refreshVersion; }
  state.products = catalog.products;
  state.checkedAt = catalog.checked_at;
  state.endpoint = catalog.mcp_endpoint;
  state.user = me.user;
  await window.BDSGUnit?.boot(me);
  if (version !== refreshVersion) return;
  $("#nav-count").textContent = state.products.length;
  $("#profile-name").textContent = state.user
    ? state.user.name || 'Người dùng BDSG'
    : "Không gian công khai";
  $("#profile-role").textContent = state.user
    ? "Đăng xuất không gian"
    : "Đăng nhập để làm việc";
  await loadPrivate();
  render();
}

document.addEventListener("click", async (e) => {
  const close = e.target.closest("[data-close]");
  if (close) return $("#" + close.dataset.close).close();
  const save = e.target.closest("[data-save]");
  if (save) {
    const id = save.dataset.save;
    state.saved = state.saved.includes(id)
      ? state.saved.filter((s) => s !== id)
      : [...state.saved, id];
    try {
      localStorage.setItem(
        "bdsg-thanhhoa-favorites",
        JSON.stringify(state.saved),
      );
    } catch (_) {}
    render();
    return;
  }
  const group = e.target.closest("[data-group]");
  if (group) {
    state.group = group.dataset.group;
    state.sector = null;
    platforms();
    return;
  }
  if (e.target.closest("[data-only-saved]")) {
    state.onlySaved = !state.onlySaved;
    platforms();
    return;
  }
  const sector = e.target.closest("[data-sector]");
  if (sector) {
    state.sector = sector.dataset.sector;
    state.group = "all";
    state.query = "";
    state.onlySaved = false;
    location.hash = "platforms";
    return;
  }
  if (e.target.closest("[data-new-request]")) return newRequest();
  const sr = e.target.closest("[data-request-sector]");
  if (sr) return newRequest(sr.dataset.requestSector);
  if (e.target.closest("[data-login]")) return auth(() => render());
  const peer = e.target.closest("[data-peer]");
  if (peer) {
    state.peer = peer.dataset.peer;
    agentsPage();
    return;
  }
  if (e.target.closest("[data-copy-endpoint]")) {
    try {
      await navigator.clipboard.writeText(state.endpoint);
      toast("Đã sao chép địa chỉ MCP");
    } catch (_) {
      toast(state.endpoint);
    }
    return;
  }
  const nav = e.target.closest("nav [data-view]");
  if (nav) {
    if (nav.dataset.view === "platforms") {
      state.group = "all";
      state.sector = null;
      state.query = "";
    }
    $("#sidebar").classList.remove("open");
    $("#sidebar-scrim").classList.remove("open");
    if (location.hash === "#" + nav.dataset.view) render();
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "catalogue-search") {
    const pos = e.target.selectionStart;
    state.query = e.target.value;
    platforms();
    const input = $("#catalogue-search");
    input.focus();
    if (input.type !== "search") input.setSelectionRange(pos, pos);
  }
});
document.addEventListener("change", async (e) => {
  if (!e.target.dataset.stage) return;
  try {
    await tool("kinh_doanh.doi_chang", {
      id: e.target.dataset.stage,
      stage: e.target.value,
    });
    await loadPrivate();
    render();
    toast("Đã cập nhật chặng triển khai");
  } catch (err) {
    toast(err.message);
    render();
  }
});
document.addEventListener("submit", async (e) => {
  if (e.target.id !== "message-form") return;
  e.preventDefault();
  const form = e.target,
    button = form.querySelector("button");
  button.disabled = true;
  try {
    const body = new FormData(form).get("body");
    await tool("agent.gui_tin", { recipient: state.peer, body });
    form.reset();
    await loadPrivate();
    agentsPage();
    const messages = $("#messages");
    messages.scrollTop = messages.scrollHeight;
    toast("Đã giao thông điệp vào hộp thư agent");
  } catch (err) {
    toast(err.message);
    button.disabled = false;
  }
});
$('#google-login-button').addEventListener('click', async () => {
  const button = $('#google-login-button');
  const text = button.querySelector('span');
  const error = $('#google-login-error');
  const passwordButton = $('#login-form button[type=submit]');
  button.disabled = true;
  passwordButton.disabled = true;
  button.setAttribute('aria-busy', 'true');
  text.textContent = 'Đang mở Google…';
  error.hidden = true;
  try {
    const data = await api('/api/auth/google/start', {method:'POST', body:'{}'});
    const target = new URL(data.url);
    if (target.origin !== 'https://accounts.google.com' || target.pathname !== '/o/oauth2/v2/auth') {
      throw new Error('Chưa mở được Google. Vui lòng thử lại.');
    }
    location.assign(target.href);
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
    error.focus();
    button.disabled = false;
    passwordButton.disabled = false;
    button.removeAttribute('aria-busy');
    text.textContent = 'Tiếp tục với Google';
  }
});
window.addEventListener('pageshow', () => {
  const button = $('#google-login-button');
  button.disabled = false;
  button.removeAttribute('aria-busy');
  button.querySelector('span').textContent = 'Tiếp tục với Google';
  $('#login-form button[type=submit]').disabled = false;
});
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = e.target.querySelector("[type=submit]");
  button.disabled = true;
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
    });
    e.target.reset();
    e.target.elements.username.value = "chu-quan";
    $("#login-dialog").close();
    await refresh();
    window.BDSGSession?.announce();
    const cb = afterLogin;
    afterLogin = null;
    cb?.();
    toast("Đã đăng nhập không gian");
  } catch (err) {
    $("#login-error").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});
$("#request-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = e.target.querySelector("[type=submit]");
  button.disabled = true;
  try {
    await tool(
      "kinh_doanh.tao_yeu_cau",
      Object.fromEntries(new FormData(e.target)),
    );
    e.target.reset();
    $("#request-dialog").close();
    await loadPrivate();
    location.hash = "requests";
    render();
    toast("Đã ghi nhận yêu cầu kinh doanh");
  } catch (err) {
    $("#request-error").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});
$("#profile").addEventListener("click", async () => {
  if (location.pathname === "/workspace.html" && parent !== window) {
    parent.postMessage({type:state.user ? "bdsg-os-logout" : "bdsg-os-login"}, location.origin);
    return;
  }
  if (!state.user) return auth(() => render());
  try {
    await api("/api/logout", { method: "POST", body: "{}" });
    clearPrivateState();
    window.BDSGSession?.announce();
    await refresh();
    toast("Đã đăng xuất không gian");
  } catch (err) {
    toast(err.message);
  }
});
function clearUnitState() {
  for (const controller of activeUnitRequests) controller.abort();
  activeUnitRequests.clear();
  window.BDSGSessions?.reset();
  window.BDSGConnections?.reset();
  window.BDSGNode?.reset();
  window.BDSGReadBroker?.reset();
  window.BDSGProjects?.reset?.();
  window.BDSGProjects?.clearSelected();
  window.BDSGTasks?.reset(); window.BDSGStaff?.reset(); window.BDSGAI?.reset();
  window.BDSGStudio?.reset(); window.BDSGOffice?.reset(); window.BDSGConnectors?.reset();
  window.BDSGVietnam?.reset(); window.BDSGSupport?.reset();
  state.requests = []; state.agents = []; state.messages = []; state.events = []; state.connections = [];
}
window.addEventListener('bdsg-unit-changed', () => {
  clearUnitState();
  if (state.user && state.user.id === window.BDSGUnit?.snapshot().actorId) render();
});
function clearPrivateState() {
  refreshVersion++;
  state.user = null;
  clearUnitState();
  window.BDSGDesktop?.reset();
  $("#profile-name").textContent = "Không gian công khai";
  $("#profile-role").textContent = "Đăng nhập để làm việc";
}
$("#menu-toggle").addEventListener("click", () => {
  $("#sidebar").classList.add("open");
  $("#sidebar-scrim").classList.add("open");
});
$("#sidebar-scrim").addEventListener("click", () => {
  $("#sidebar").classList.remove("open");
  $("#sidebar-scrim").classList.remove("open");
});
function search() {
  if (state.view !== "platforms") {
    location.hash = "platforms";
    requestAnimationFrame(() => $("#catalogue-search")?.focus());
  } else $("#catalogue-search")?.focus();
}
$("#search-trigger").addEventListener("click", search);
document.addEventListener("keydown", (e) => {
  if (e.defaultPrevented) return;
  if (e.ctrlKey && e.key.toLowerCase() === "k") {
    e.preventDefault();
    search();
  }
});
$("#refresh").addEventListener("click", () =>
  refresh()
    .then(() => toast("Đã tải dữ liệu hiện tại"))
    .catch((e) => toast(e.message)),
);
window.addEventListener("hashchange", render);
setInterval(async () => {
  if (
    state.view !== "agents" ||
    !state.user ||
    window.BDSGAppVisible === false ||
    document.visibilityState !== "visible"
  )
    return;
  try {
    const r = await api("/api/messages");
    if (r.ok) {
      state.messages = r.ket_qua.messages;
      const box = $("#messages");
      if (box) {
        const bottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
        box.innerHTML = messageMarkup();
        if (bottom) box.scrollTop = box.scrollHeight;
      }
    }
  } catch (_) {}
}, 10000);
refresh().then(() => {
  const result = new URLSearchParams(location.search).get('login');
  if (!['google-success', 'google-failed'].includes(result)) return;
  history.replaceState(null, '', location.pathname + location.hash);
  if (result === 'google-success' && state.user) {
    window.BDSGSession?.announce();
    toast('Đã đăng nhập bằng Google');
  } else {
    auth();
    const error = $('#google-login-error');
    error.textContent = 'Chưa đăng nhập được bằng Google. Hãy thử lại; nếu vẫn lỗi, vui lòng liên hệ người quản trị.';
    error.hidden = false;
    error.focus();
  }
}).catch((e) => {
  main.innerHTML = `<section class="error-state"><h1>Chưa mở được không gian</h1><p>${esc(e.message)}</p><button class="button" id="retry">Thử lại</button></section>`;
  $("#retry").onclick = () => location.reload();
});
