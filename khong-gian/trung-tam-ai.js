"use strict";
(() => {
  let epoch = 0,
    configuration = null,
    saving = false;
  const capabilities = {
    general: "Tổng quát",
    reasoning: "Lập luận",
    coding: "Lập trình",
    writing: "Viết nội dung",
    analysis: "Phân tích",
    fast: "Phản hồi nhanh",
  };
  const policies = {
    tasks_per_user: "Tác vụ/người/ngày",
    calls_per_user: "Lượt API/người/ngày",
    calls_global: "Lượt API/toàn hệ thống/ngày",
    input_tokens_per_user: "Token đầu vào giữ trước/người/ngày",
    output_tokens_per_user: "Token đầu ra giữ trước/người/ngày",
    output_tokens_per_project: "Token đầu ra giữ trước/dự án/ngày",
    output_tokens_global: "Token đầu ra giữ trước/toàn hệ thống/ngày",
    usd_per_user: "Trần USD/người/ngày",
    usd_global: "Trần USD/toàn hệ thống/ngày",
  };
  const field = (name, label, value = "", type = "text", extra = "") =>
    `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
  const current = (ticket, actor) =>
    ticket === epoch &&
    state.user?.id === actor &&
    location.hash === "#ai-settings";
  function cleanModel(model) {
    const value = { ...model };
    delete value.has_api_key;
    return value;
  }
  function payload() {
    return {
      enabled: configuration.enabled,
      default_model: configuration.default_model,
      models: configuration.models.map(cleanModel),
      policy: { ...configuration.policy },
    };
  }
  function editor(id) {
    const model = configuration.models.find((row) => row.id === id) || {
      id: "",
      label: "",
      upstream_model: "",
      capabilities: ["general"],
      skills: [],
      prices: { input_per_million: "", output_per_million: "" },
    };
    const exists = Boolean(model.id);
    document.querySelector("#bdsg-ai-editor").innerHTML =
      `<form id="bdsg-ai-model-form" class="bdsg-ai-form" method="post" action="/api/ai-form"><h2>${exists ? "Sửa mô hình" : "Thêm mô hình"}</h2>
      ${field("model_id", "Mã mô hình", model.id, "text", `required maxlength="48" ${exists ? "readonly" : ""}`)}
      ${field("label", "Tên hiển thị", model.label, "text", 'required maxlength="80"')}
      ${field("upstream_model", "Tên mô hình theo LiteLLM", model.upstream_model, "text", 'required maxlength="180" placeholder="nhà_cung_cấp/tên_mô_hình"')}
      <p>Hỗ trợ OpenAI, Anthropic, Gemini, DeepSeek, Mistral, Groq và xAI. Dùng đúng tên mô hình đã được cấp quyền trong tài khoản nhà cung cấp.</p>
      ${field("api_key", exists ? "Khóa API mới (để trống để giữ khóa hiện tại)" : "Khóa API", "", "password", `${exists ? "" : "required"} autocomplete="new-password" maxlength="4096"`)}
      <fieldset><legend>Năng lực phù hợp</legend><div class="bdsg-ai-checks">${Object.entries(
        capabilities,
      )
        .map(
          ([value, label]) =>
            `<label><input type="checkbox" name="capability" value="${value}" ${model.capabilities.includes(value) ? "checked" : ""}>${label}</label>`,
        )
        .join("")}</div></fieldset>
      ${field("skills", "Mã kỹ năng ưu tiên (tùy chọn, cách nhau bằng dấu phẩy)", model.skills.join(", "), "text", 'maxlength="2000"')}
      <div class="bdsg-ai-columns">${field("input_price", "Giá input USD / triệu token", model.prices.input_per_million, "number", 'required min="0" max="1000" step="any"')}${field("output_price", "Giá output USD / triệu token", model.prices.output_per_million, "number", 'required min="0" max="1000" step="any"')}</div>
      <p>Giá do chủ quản đối chiếu biểu phí chính thức. Hệ thống giữ trước ngân sách bảo thủ; số này chưa phải hóa đơn nhà cung cấp.</p>
      <button class="button primary" type="submit">Lưu mô hình</button><button class="button" type="button" data-ai-cancel>Đóng biểu mẫu</button></form>`;
    document
      .querySelector('#bdsg-ai-model-form input[name="model_id"]')
      .focus();
  }
  function renderAdmin() {
    const slot = document.querySelector("#bdsg-ai-content");
    slot.innerHTML = `<div class="bdsg-ai-heading"><h2>Danh mục mô hình</h2><button class="button" type="button" data-ai-add>Thêm mô hình</button></div>
      <p>Mỗi khóa chỉ được dùng trên máy chủ. Lưu cấu hình chưa xác nhận quyền API hay số dư của nhà cung cấp. Đợi tác vụ đang chạy kết thúc trước khi đổi danh mục.</p>
      <div class="bdsg-ai-list">${configuration.models.length ? configuration.models.map((model) => `<div class="bdsg-ai-model"><div><strong>${esc(model.label)}</strong><p>${esc(model.upstream_model)}</p><small>${esc(model.capabilities.map((value) => capabilities[value] || value).join(" · "))}</small></div><div class="bdsg-ai-actions"><button type="button" class="button" data-ai-edit="${esc(model.id)}">Sửa</button><button type="button" class="button" data-ai-remove="${esc(model.id)}">Gỡ khỏi danh mục</button></div></div>`).join("") : "<p>Chưa khai báo mô hình. Thêm mô hình và khóa API để bắt đầu.</p>"}</div>
      <div id="bdsg-ai-editor"></div><form id="bdsg-ai-policy-form" class="bdsg-ai-form"><h2>Quyền sử dụng và tài trợ</h2>
      <label class="bdsg-ai-toggle"><input name="enabled" type="checkbox" ${configuration.enabled ? "checked" : ""}>Bật Trung tâm AI cho người dùng</label>
      <label>Mô hình mặc định<select name="default_model"><option value="">Chưa chọn</option>${configuration.models.map((model) => `<option value="${esc(model.id)}" ${model.id === configuration.default_model ? "selected" : ""}>${esc(model.label)}</option>`).join("")}</select></label>
      <div class="bdsg-ai-columns">${Object.entries(policies)
        .map(([key, label]) =>
          field(
            key,
            label,
            configuration.policy[key],
            "number",
            `required min="${key.startsWith("usd_") ? 0 : 1}" step="${key.startsWith("usd_") ? "any" : 1}"`,
          ),
        )
        .join("")}</div>
      <p>Hạn mức đặt lại lúc 00:00 giờ Việt Nam. Một tác vụ có thể gọi nhiều mô hình; lượt tiếp tục tính là một tác vụ tài trợ mới. Lượt API lỗi vẫn giữ dự phòng vì có thể đã bị tính phí. LiteLLM không cấp tín dụng miễn phí.</p>
      <button class="button primary" type="submit">Lưu cấu hình tài trợ</button></form>`;
  }
  async function save(data) {
    if (saving) return;
    saving = true;
    const ticket = epoch,
      actor = state.user?.id;
    const message = document.querySelector("#bdsg-ai-status");
    message.textContent = "Đang lưu cấu hình riêng trên máy chủ…";
    document
      .querySelectorAll("#bdsg-ai-content button")
      .forEach((button) => (button.disabled = true));
    try {
      const result = await tool("mo_hinh.luu", data);
      if (!current(ticket, actor)) return;
      configuration = result;
      renderAdmin();
      message.textContent =
        "Đã lưu cấu hình. Gateway mô hình cần nạp phiên bản mới trước khi xử lý; chưa nghiệm thu gọi API thật.";
    } catch (error) {
      if (current(ticket, actor)) message.textContent = error.message;
    } finally {
      data.models.forEach((model) => delete model.api_key);
      if (current(ticket, actor)) {
        saving = false;
        document
          .querySelectorAll("#bdsg-ai-content button")
          .forEach((button) => (button.disabled = false));
      }
    }
  }
  async function open() {
    const ticket = ++epoch,
      actor = state.user?.id;
    configuration = null;
    saving = false;
    main.innerHTML = `<section class="bdsg-work-page bdsg-ai-page"><div class="bdsg-work-page-heading"><div><h1>Trung tâm AI</h1><p>Chọn mô hình theo công việc, quản lý API và hạn mức được BDSG tài trợ.</p></div><a class="button" href="#work">Giao việc</a></div><p id="bdsg-ai-status" role="status">Đang tải…</p><div id="bdsg-ai-content"></div></section>`;
    if (!state.user) {
      document.querySelector("#bdsg-ai-status").innerHTML =
        '<button class="button" type="button" data-ai-login>Đăng nhập để xem hạn mức</button>';
      return;
    }
    try {
      const quota = await tool("mo_hinh.han_muc");
      if (!current(ticket, actor)) return;
      document.querySelector("#bdsg-ai-status").textContent =
        `Còn ${quota.tasks_remaining}/${quota.policy.tasks_per_user} tác vụ được tài trợ hôm nay, trong trần token và ngân sách. Đặt lại lúc 00:00 giờ Việt Nam.`;
      if (state.user.role !== "quan-tri") {
        document.querySelector("#bdsg-ai-content").innerHTML =
          "<p>Chủ quản cấu hình mô hình và tài trợ. Chọn Tự động hoặc mô hình cụ thể trong ô giao việc.</p>";
        return;
      }
      const result = await tool("mo_hinh.cau_hinh");
      if (!current(ticket, actor)) return;
      configuration = result;
      renderAdmin();
    } catch (error) {
      if (current(ticket, actor))
        document.querySelector("#bdsg-ai-status").innerHTML =
          `${esc(error.message)} <button class="button" type="button" data-ai-retry>Thử lại</button>`;
    }
  }
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-ai-login]")) auth(open);
    if (event.target.closest("[data-ai-retry]")) open();
    if (!configuration || saving || location.hash !== "#ai-settings") return;
    if (event.target.closest("[data-ai-add]")) editor();
    if (event.target.closest("[data-ai-cancel]"))
      document.querySelector("#bdsg-ai-editor").replaceChildren();
    const edit = event.target.closest("[data-ai-edit]");
    if (edit) editor(edit.dataset.aiEdit);
    const remove = event.target.closest("[data-ai-remove]");
    if (remove) {
      const data = payload();
      data.models = data.models.filter(
        (model) => model.id !== remove.dataset.aiRemove,
      );
      if (!data.models.some((model) => model.id === data.default_model))
        data.default_model = data.models[0]?.id || null;
      if (!data.models.length) data.enabled = false;
      save(data);
    }
  });
  document.addEventListener("submit", (event) => {
    if (
      !["bdsg-ai-model-form", "bdsg-ai-policy-form"].includes(event.target.id)
    )
      return;
    event.preventDefault();
    if (!configuration || saving) return;
    const form = event.target,
      values = new FormData(form),
      data = payload();
    if (form.id === "bdsg-ai-model-form") {
      const item = {
        id: values.get("model_id"),
        label: values.get("label"),
        upstream_model: values.get("upstream_model"),
        api_key: values.get("api_key"),
        capabilities: values.getAll("capability"),
        skills: values
          .get("skills")
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        prices: {
          input_per_million: values.get("input_price"),
          output_per_million: values.get("output_price"),
        },
      };
      form.querySelector('[name="api_key"]').value = "";
      const position = data.models.findIndex((model) => model.id === item.id);
      if (position >= 0) data.models[position] = item;
      else data.models.push(item);
      data.default_model = data.default_model || item.id;
    } else {
      data.enabled = values.has("enabled");
      data.default_model = values.get("default_model") || null;
      for (const key of Object.keys(policies))
        data.policy[key] = key.startsWith("usd_")
          ? values.get(key)
          : Number(values.get(key));
    }
    save(data);
  });
  async function picker(draft) {
    const host = document.querySelector(".bdsg-composer-mode");
    if (!host || !state.user) return;
    const actor = state.user.id,
      ticket = ++epoch;
    const valid = () =>
      ticket === epoch &&
      state.user?.id === actor &&
      host.isConnected &&
      location.hash === "#work";
    try {
      const [catalogue, quota] = await Promise.all([
        tool("mo_hinh.danh_sach"),
        tool("mo_hinh.han_muc"),
      ]);
      if (!valid()) return;
      if (!catalogue.models.some((model) => model.id === draft.model_selection))
        draft.model_selection = "auto";
      host.insertAdjacentHTML(
        "beforebegin",
        `<div class="bdsg-ai-model-choice"><label for="bdsg-model-choice">Mô hình AI</label><select id="bdsg-model-choice"><option value="auto">Tự động theo công việc</option>${catalogue.enabled ? catalogue.models.map((model) => `<option value="${esc(model.id)}" ${model.id === draft.model_selection ? "selected" : ""}>${esc(model.label)}</option>`).join("") : ""}</select><small>${catalogue.enabled ? `Còn ${quota.tasks_remaining}/${quota.policy.tasks_per_user} tác vụ tài trợ hôm nay, trong trần token và ngân sách.` : "Danh mục LiteLLM chưa bật. Chủ quản cần cấu hình mô hình để sử dụng."} <a href="#ai-settings">${state.user.role === "quan-tri" ? "Quản lý mô hình và tài trợ" : "Xem hạn mức"}</a></small></div>`,
      );
      document
        .querySelector("#bdsg-model-choice")
        .addEventListener(
          "change",
          (event) => (draft.model_selection = event.target.value),
        );
    } catch (error) {
      if (valid())
        host.insertAdjacentHTML(
          "beforebegin",
          `<p role="status">Chưa tải được danh mục mô hình: ${esc(error.message)}. <a href="#ai-settings">Mở Trung tâm AI</a></p>`,
        );
    }
  }
  window.BDSGAI = {
    open,
    picker,
    reset() {
      epoch++;
      configuration = null;
      saving = false;
      document
        .querySelector('#bdsg-ai-editor input[type="password"]')
        ?.form.reset();
    },
  };
})();
