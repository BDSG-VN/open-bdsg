"use strict";
(() => {
  const status = document.querySelector("#status"),
    error = document.querySelector("#error");
  const save = document.querySelector("#save"),
    close = document.querySelector("#close");
  const retry = document.querySelector("#retry");
  let editor,
    key,
    requireReceipt = false,
    changed = false,
    working = false,
    closed = false,
    clientDirty = false,
    closeRequest = null;
  const guard = window.BDSGSessionGuard.create({ onInvalidate(message) {
    closed = true; changed = working = clientDirty = false; key = null;
    try { editor?.destroyEditor(); } catch (_) {}
    editor = null;
    document.querySelector("main").replaceChildren();
    save.disabled = close.disabled = true;
    retry.hidden = true;
    status.textContent = "Phiên soạn thảo đã dừng.";
    showError(message);
  } });
  const showError = (message) => {
    error.textContent = message;
    error.hidden = false;
  };
  retry.addEventListener("click", () => {
    if (!changed && !working) location.reload();
  });
  async function call(name, args) {
    const response = await guard.fetch("/api/tools", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(25000),
      body: JSON.stringify({ name: "van_phong." + name, arguments: args }),
    });
    const value = await response.json();
    guard.assertActive();
    if (!response.ok || !value.ok)
      throw new Error(
        "Không hoàn tất thao tác. Kiểm tra quyền, kết nối và dịch vụ soạn thảo rồi thử lại.",
      );
    return value.ket_qua;
  }
  async function store() {
    for (let attempt = 0; clientDirty && attempt < 100; attempt++)
      await new Promise((resolve) => setTimeout(resolve, 100));
    if (clientDirty)
      throw new Error(
        "Thay đổi chưa gửi hết tới bộ soạn thảo. Nhấn Lưu trong thanh công cụ của tài liệu rồi thử lại.",
      );
    const result = await call("luu_soan_thao", { key });
    if (result.state === "khong-co-thay-doi") {
      if (changed)
        throw new Error(
          "Bộ soạn thảo chưa xác nhận bản sửa mới. Giữ trang mở, nhấn Lưu trong tài liệu rồi thử lại.",
        );
      return;
    }
    const requestId = result.request_id;
    if (typeof requestId !== "string" || !requestId.length || requestId.length > 128)
      throw new Error(
        "Chưa nhận được mã lệnh lưu. Giữ tài liệu mở và kiểm tra lại kết nối.",
      );
    for (let attempt = 0; attempt < 20; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const progress = await call("phien_soan_thao",
        requireReceipt ? { key, request_id: requestId } : { key });
      const hasReceipt = Object.prototype.hasOwnProperty.call(progress, "command_state");
      if ((requireReceipt && !hasReceipt) || (hasReceipt && progress.request_id !== requestId))
        throw new Error(
          "Chưa xác nhận được lần lưu này. Giữ tài liệu mở và kiểm tra lại.",
        );
      if (progress.save_error || progress.state !== "active" ||
          (hasReceipt && ["failed", "superseded", "abandoned", "unchanged"].includes(progress.command_state)))
        throw new Error(
          "Bộ soạn thảo chưa lưu được. Giữ trang này mở và thử lại.",
        );
      // Timestamp thuộc cả phiên; ledger phải xác nhận đúng lệnh đang chờ.
      if (hasReceipt ? progress.command_state === "committed" : !progress.pending && progress.last_saved)
        return;
    }
    throw new Error(
      "Chưa nhận được xác nhận lưu. Giữ tài liệu mở, kiểm tra lại trước khi rời trang.",
    );
  }
  async function perform(final) {
    if (working || !editor || closed || !guard.active) return;
    working = true;
    document.querySelector("main").inert = true;
    status.tabIndex = -1;
    status.focus();
    save.disabled = close.disabled = true;
    error.hidden = true;
    status.textContent = "Đang chờ lưu phiên bản vào kho BDSG…";
    try {
      await store();
      guard.assertActive();
      changed = false;
      if (final) {
        document.querySelector("main").inert = false;
        await new Promise((resolve, reject) => {
          const timer = setTimeout(() => {
            closeRequest = null;
            reject(
              new Error(
                "Tài liệu chưa đóng. Hoàn tất hộp thoại trong trình soạn thảo hoặc tiếp tục làm việc.",
              ),
            );
          }, 20000);
          closeRequest = () => {
            clearTimeout(timer);
            closeRequest = null;
            resolve();
          };
          editor.requestClose();
        });
        guard.assertActive();
        editor.destroyEditor();
        editor = null;
        closed = true;
        working = false;
        location.assign("/#office");
        return;
      }
      status.textContent = "Đã lưu phiên bản vào kho BDSG.";
    } catch (failure) {
      if (closed) return;
      showError(failure.message);
      status.textContent = "Chưa xác nhận hoàn tất thao tác.";
    } finally {
      working = false;
      document.querySelector("main").inert = !guard.active;
      save.disabled = close.disabled = !editor || !guard.active;
    }
  }
  save.addEventListener("click", () => perform(false));
  close.addEventListener("click", () => perform(true));
  document.querySelector("#back").addEventListener("click", (event) => {
    if (editor && !closed) {
      event.preventDefault();
      perform(true);
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (changed || working) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  async function open() {
    try {
      await guard.ready;
      if (matchMedia("(max-width: 750px)").matches)
        throw new Error(
          "Bản Community dùng bộ soạn thảo trên máy tính. Trên điện thoại, mở kho tệp để tải hoặc nhập tài liệu.",
        );
      const id = new URLSearchParams(location.search).get("id");
      if (!/^[a-f0-9]{24}$/.test(id || ""))
        throw new Error("Thiếu tài liệu. Quay về kho tệp và chọn lại.");
      const result = await call("mo_soan_thao", { id });
      const protocol = Object.prototype.hasOwnProperty.call(result, "save_protocol")
        ? result.save_protocol : "legacy";
      if (!["legacy", "request-ledger-v1"].includes(protocol))
        throw new Error("Chưa hỗ trợ phiên bản soạn thảo này. Tải lại trang rồi mở lại tài liệu.");
      requireReceipt = protocol === "request-ledger-v1";
      key = result.key;
      if (result.api_url !== "/office-docs/web-apps/apps/api/documents/api.js")
        throw new Error("Nguồn bộ soạn thảo không hợp lệ.");
      const script = document.createElement("script");
      script.src = result.api_url;
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(
          () =>
            reject(
              new Error(
                "Bộ soạn thảo tải quá chậm. Kiểm tra kết nối rồi tải lại.",
              ),
            ),
          30000,
        );
        script.onload = () => {
          clearTimeout(timeout);
          resolve();
        };
        script.onerror = () => {
          clearTimeout(timeout);
          reject(new Error("Không tải được bộ soạn thảo. Thử tải lại trang."));
        };
        document.head.append(script);
      });
      guard.assertActive();
      const readyTimeout = setTimeout(() => {
        if (!guard.active) return;
        showError(
          "Tài liệu mở lâu hơn dự kiến. Kiểm tra kết nối hoặc tải lại trình soạn thảo.",
        );
        retry.hidden = changed || working;
      }, 60000);
      editor = new DocsAPI.DocEditor("editor", {
        ...result.config,
        events: {
          onDocumentReady: () => {
            if (!guard.active) return;
            clearTimeout(readyTimeout);
            retry.hidden = true;
            error.hidden = true;
            status.textContent =
              "Tài liệu đã mở. Dùng Lưu phiên bản để ghi vào kho BDSG.";
            save.disabled = close.disabled = false;
          },
          onDocumentStateChange: (event) => {
            if (!guard.active) return;
            clientDirty = Boolean(event.data);
            if (event.data) {
              changed = true;
              status.textContent =
                "Có thay đổi đang soạn. Chưa lưu phiên bản vào kho BDSG.";
            }
          },
          onRequestClose: () => {
            if (!guard.active) return;
            if (closeRequest) closeRequest();
            else perform(true);
          },
          onError: () => {
            if (!guard.active) return;
            clearTimeout(readyTimeout);
            retry.hidden = changed || working;
            showError(
              "Bộ soạn thảo gặp lỗi. Giữ trang mở và thử lưu lại; không coi tài liệu đã được lưu.",
            );
          },
        },
      });
    } catch (failure) {
      if (closed) return;
      status.textContent = "Chưa mở được tài liệu.";
      showError(failure.message);
      retry.hidden =
        changed || working || matchMedia("(max-width: 750px)").matches;
    }
  }
  open();
})();
