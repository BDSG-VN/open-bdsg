"use strict";
(() => {
  const project = new URLSearchParams(location.search).get("project");
  const pick = document.querySelector("#pick"),
    status = document.querySelector("#status"),
    error = document.querySelector("#error");
  let loaded, picker, pendingSettings;
  const imports = new Map();
  const guard = window.BDSGSessionGuard.create({ onInvalidate(message) {
    try { picker?.setVisible(false); picker?.dispose?.(); } catch (_) {}
    picker = null;
    if (pendingSettings) pendingSettings.access_token = "";
    pendingSettings = null;
    document.querySelectorAll(".picker-dialog, .picker-dialog-bg").forEach(node => node.remove());
    imports.clear();
    document.querySelector("#selection").replaceChildren();
    pick.disabled = true;
    status.textContent = "Phiên chọn tệp đã dừng.";
    error.textContent = message; error.hidden = false;
  } });
  pick.disabled = true;
  guard.ready.then(() => { pick.disabled = false; }).catch(failure => {
    error.textContent = failure.message; error.hidden = false;
  });
  async function request(path, body) {
    const response = await guard.fetch(path, {
      method: "POST",
      credentials: "same-origin",
      signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const value = await response.json();
    guard.assertActive();
    if (response.status === 409 && path === "/api/google/picker")
      throw new Error(
        "Kết nối Google chưa sẵn sàng. Trở về kho tệp, mở Kết nối Google Drive để kiểm tra thiết lập và cấp quyền.",
      );
    if (response.status === 401)
      throw new Error(
        "Phiên BDSG đã hết hạn. Trở về kho tệp và đăng nhập lại.",
      );
    if (!response.ok || value.ok === false)
      throw new Error(
        "Không hoàn tất yêu cầu. Kiểm tra kết nối Google, quyền dự án và giới hạn tệp 8 MiB.",
      );
    return value;
  }
  async function selected(data) {
    if (!guard.active) return;
    if (data.action === google.picker.Action.CANCEL) {
      pick.disabled = false;
      return;
    }
    if (data.action !== google.picker.Action.PICKED) return;
    const file = data.docs?.[0];
    if (!file?.id) {
      pick.disabled = false;
      return;
    }
    status.textContent = "Đang nhập bản sao và quét virus…";
    try {
      if (!imports.has(file.id)) imports.set(file.id, crypto.randomUUID());
      await request("/api/tools", {
        name: "van_phong.google_nhap",
        arguments: {
          project_id: project,
          drive_id: file.id,
          request_key: imports.get(file.id),
        },
      });
      imports.delete(file.id);
      status.textContent =
        "Đã nhập bản sao vào dự án BDSG. Tệp Google gốc vẫn được giữ.";
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    } finally {
      pick.disabled = !guard.active;
    }
  }
  async function load() {
    if (!loaded)
      loaded = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://apis.google.com/js/api.js";
        script.onload = () =>
          gapi.load("picker", {
            callback: resolve,
            onerror: () => reject(new Error("Không tải được Google Picker.")),
          });
        script.onerror = () =>
          reject(new Error("Không tải được Google Picker."));
        document.head.append(script);
      });
    return loaded;
  }
  pick.addEventListener("click", async () => {
    if (!guard.active) return;
    pick.disabled = true;
    error.hidden = true;
    let settings;
    try {
      if (!project)
        throw new Error("Thiếu dự án. Quay về kho tệp và chọn lại.");
      await guard.check();
      settings = await request("/api/google/picker", {});
      pendingSettings = settings;
      await load();
      guard.assertActive();
      picker = new google.picker.PickerBuilder()
        .addView(new google.picker.DocsView(google.picker.ViewId.DOCS))
        .setOAuthToken(settings.access_token)
        .setDeveloperKey(settings.api_key)
        .setAppId(settings.app_id)
        .setOrigin(location.origin)
        .setLocale("vi")
        .setCallback(selected)
        .build();
      picker.setVisible(true);
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
      pick.disabled = !guard.active;
    } finally {
      if (settings) settings.access_token = "";
      pendingSettings = null;
    }
  });
})();
