"use strict";
(() => {
  let revision = 0;
  let members = [];
  const phases = {
    planning: "Đang phân công",
    working: "Đang phối hợp",
    synthesizing: "Đang tổng hợp",
    completed: "Hoàn thành",
    failed: "Cần xử lý lỗi",
    cancelled: "Đã dừng",
    interrupted: "Bị gián đoạn",
    awaiting_model: "Cần cấu hình AI",
    queued: "Chờ thực hiện",
    running: "Đang làm",
    blocked: "Chờ xử lý phần trước",
  };
  const label = (value) => phases[value] || "Chưa xác định";
  const badge = (value) =>
    `<span class="bdsg-team-state" data-state="${esc(value)}">${esc(label(value))}</span>`;

  function trace(task) {
    const team = task.team;
    if (!team || team.run !== task.run) return "";
    const names = new Map(
      (team.agents || []).map((agent) => [agent.skill_id, agent.name]),
    );
    const completed = (team.agents || []).filter(
      (agent) => agent.state === "completed",
    ).length;
    return `<section class="bdsg-team" aria-label="Đội ngũ chuyên môn">
      <div class="bdsg-team-heading"><h2>Đội ngũ chuyên môn</h2>${badge(team.state)}</div>
      <p class="bdsg-team-lead"><strong>Agent tổng</strong> phân công và tổng hợp kết quả${team.agents?.length ? ` · ${completed}/${team.agents.length} phần việc hoàn thành` : ""}.</p>
      ${team.summary ? `<p>${esc(team.summary)}</p>` : ""}
      ${team.state === "awaiting_model" ? '<p>Đội ngũ chưa thực thi. Cấu hình mô hình AI rồi tiếp tục tác vụ.</p><button type="button" class="button" data-bdsg-model-setup>Cấu hình mô hình AI</button>' : ""}
      <ol class="bdsg-team-members">${(team.agents || [])
        .map((agent) => {
          const artifact = (task.artifacts || []).find(
            (file) =>
              file.run === task.run &&
              file.name === `${agent.skill_id}-luot-${task.run}.md`,
          );
          const dependencies = (agent.depends_on || []).map(
            (id) => names.get(id) || id,
          );
          return `<li><div class="bdsg-team-person"><strong>${esc(agent.name)}</strong>${badge(agent.state)}</div>
          <p>${esc(agent.mission)}</p>
          ${dependencies.length ? `<small>Nhận bàn giao: ${esc(dependencies.join(", "))}</small>` : "<small>Có thể làm độc lập</small>"}
          <details data-staff-section="${esc(agent.skill_id)}"><summary>Sản phẩm cần bàn giao</summary><p>${esc(agent.deliverable)}</p><small>Bản kỹ năng: ${esc(String(agent.skill_sha256 || "").slice(0, 12))}</small></details>
          ${artifact ? `<button type="button" class="button" data-staff-result="${esc(artifact.id)}">Xem kết quả</button>` : ""}
          ${agent.started ? `<small>Bắt đầu ${esc(date(agent.started))}${agent.finished ? ` · Kết thúc ${esc(date(agent.finished))}` : ""}</small>` : ""}
        </li>`;
        })
        .join("")}</ol>
      ${team.state === "failed" ? '<p role="status">Một phần việc chưa hoàn tất. Xem nhật ký bên dưới, bổ sung yêu cầu để tạo lượt tiếp tục; kết quả trước vẫn được giữ.</p>' : ""}
      ${(task.team_history || []).length ? `<details class="bdsg-team-history" data-staff-section="history"><summary>Lịch sử đội ngũ</summary>${task.team_history.map((run) => `<p><strong>Lượt ${esc(run.run)}</strong> · ${esc(label(run.state))}<br>${esc((run.agents || []).map((agent) => agent.name + ": " + label(agent.state)).join("; "))}</p>`).join("")}</details>` : ""}
    </section>`;
  }

  function rows(query = "") {
    const matched = members.filter((agent) =>
      clean(agent.name + " " + agent.description).includes(clean(query)),
    );
    const slot = document.querySelector("#bdsg-staff-list");
    if (!slot) return;
    slot.innerHTML = matched.length
      ? matched
          .map(
            (agent) => `<article class="bdsg-staff-row">
      <div><h2>${esc(agent.name)}</h2><p>${esc(agent.description)}</p></div>
      <details><summary>Đầu ra và nguồn kỹ năng</summary><p>${esc(agent.deliverable)}</p><ul>${(agent.sources || []).map((source) => `<li><a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.repository)}</a> · ${esc(source.license)}</li>`).join("")}</ul></details>
    </article>`,
          )
          .join("")
      : '<p class="bdsg-staff-empty" role="status">Không có chuyên môn khớp từ khóa. Thử tên công việc hoặc lĩnh vực khác.</p>';
    const count = document.querySelector("#bdsg-staff-count");
    if (count) count.textContent = `${matched.length} chuyên môn`;
  }

  async function open() {
    const ticket = ++revision;
    const actor = state.user?.id;
    members = [];
    main.innerHTML = `<section class="bdsg-work-page bdsg-staff-page"><div class="bdsg-work-page-heading"><div><h1>Nhân sự Agent</h1><p>Giao mục tiêu cho Agent tổng. Chuyên môn phù hợp được phân công và phối hợp trong từng tác vụ.</p></div><a class="button primary" href="#work">Giao việc mới ${icon("arrow")}</a></div><div id="bdsg-staff-content" role="status">Đang tải danh mục chuyên môn…</div></section>`;
    const slot = document.querySelector("#bdsg-staff-content");
    if (!state.user) {
      slot.innerHTML =
        '<p>Đăng nhập để xem bộ kỹ năng và giao việc trong không gian riêng.</p><button type="button" class="button" data-staff-login>Đăng nhập</button>';
      return;
    }
    try {
      const catalogue = await tool("nhan_su.danh_sach");
      if (
        ticket !== revision ||
        location.hash !== "#staff" ||
        state.user?.id !== actor ||
        !slot.isConnected
      )
        return;
      members = catalogue.agents || [];
      slot.removeAttribute("role");
      slot.innerHTML = `<div class="bdsg-staff-search"><label for="bdsg-staff-query">Tìm chuyên môn</label><input id="bdsg-staff-query" type="search" placeholder="Tên công việc, kỹ năng hoặc lĩnh vực…" autocomplete="off"><span id="bdsg-staff-count" role="status"></span></div><p class="bdsg-staff-note">Kỹ năng hướng dẫn cách làm. Mô hình AI và công cụ vẫn cần được cấu hình, cấp quyền theo tác vụ.</p><div id="bdsg-staff-list"></div>`;
      rows();
      slot
        .querySelector(".bdsg-staff-search")
        .insertAdjacentHTML(
          "afterend",
          '<div class="bdsg-staff-export"><label for="bdsg-staff-format">Dùng kỹ năng ở hệ AI khác</label><select id="bdsg-staff-format"><option value="portable">Gói Agent Plugins</option><option value="codex">Kỹ năng cho Codex</option><option value="claude">Các gói kỹ năng Claude</option></select><button type="button" class="button" data-staff-export>Tải bộ kỹ năng</button><p id="bdsg-staff-export-status" role="status">Gói hướng dẫn có giấy phép; công cụ và tài khoản kết nối được cấu hình riêng.</p></div>',
        );
    } catch (error) {
      if (
        ticket === revision &&
        location.hash === "#staff" &&
        state.user?.id === actor &&
        slot.isConnected
      )
        slot.innerHTML = `<p role="alert">${esc(error.message)}</p><button type="button" class="button" data-staff-retry>Thử tải lại</button>`;
    }
  }

  async function download(button) {
    if (button.disabled || !state.user) return;
    const ticket = revision,
      actor = state.user.id;
    const message = document.querySelector("#bdsg-staff-export-status");
    const format = document.querySelector("#bdsg-staff-format").value;
    button.disabled = true;
    message.textContent = "Đang đóng gói và kiểm tra tệp…";
    const current = () =>
      ticket === revision &&
      state.user?.id === actor &&
      location.hash === "#staff" &&
      button.isConnected;
    try {
      const result = await tool("nhan_su.xuat_bo", { format });
      if (!current()) return;
      if (
        !/^[A-Za-z0-9_.-]+\.zip$/.test(result.filename) ||
        result.bytes > 3 * 1024 * 1024 ||
        result.mime_type !== "application/zip"
      )
        throw new Error("Gói kỹ năng chưa đúng định dạng.");
      const bytes = Uint8Array.from(atob(result.content_base64), (char) =>
        char.charCodeAt(0),
      );
      const checksum = Array.from(
        new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
        (byte) => byte.toString(16).padStart(2, "0"),
      ).join("");
      if (!current()) return;
      if (bytes.length !== result.bytes || checksum !== result.sha256)
        throw new Error("Dấu kiểm gói kỹ năng không khớp. Hãy tải lại.");
      const url = URL.createObjectURL(
        new Blob([bytes], { type: result.mime_type }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      message.textContent = `Đã tạo gói ${result.skill_count} kỹ năng · SHA-256 ${checksum.slice(0, 12)}. Xem HUONG-DAN.md trong gói trước khi nhập.`;
    } catch (error) {
      if (current()) message.textContent = error.message;
    } finally {
      if (current()) button.disabled = false;
    }
  }

  document.addEventListener("input", (event) => {
    if (event.target.id === "bdsg-staff-query") rows(event.target.value);
  });
  document.addEventListener("click", (event) => {
    const exportButton = event.target.closest("[data-staff-export]");
    if (exportButton) download(exportButton);
    if (event.target.closest("[data-staff-login]")) auth(open);
    if (event.target.closest("[data-staff-retry]")) open();
    const target = event.target.closest("[data-staff-result]");
    if (target) {
      const result = document.getElementById(
        "bdsg-result-" + target.dataset.staffResult,
      );
      result?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "start",
      });
      result?.focus({ preventScroll: true });
    }
  });
  window.BDSGStaff = {
    open,
    trace,
    reset() {
      revision++;
      members = [];
    },
  };
})();
