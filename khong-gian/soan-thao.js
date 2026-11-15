"use strict";
(() => {
  const status = document.querySelector("#status"),
    error = document.querySelector("#error");
  const save = document.querySelector("#save"),
    close = document.querySelector("#close");
  const retry = document.querySelector("#retry");
  let editor,
    key,
    changed = false,
    working = false,
    closed = false,
    clientDirty = false,
    closeRequest = null;
  const showError = (message) => {
    error.textContent = message;
    error.hidden = false;
  };
  retry.addEventListener("click", () => {
    if (!changed && !working) location.reload();
  });
  async function call(name, args) {
    const response = await fetch("/api/tools", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(25000),
      body: JSON.stringify({ name: "van_phong." + name, arguments: args }),
    });
    const value = await response.json();
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
    for (let attempt = 0; attempt < 20; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const progress = await call("phien_soan_thao", { key });
      if (progress.save_error || progress.state !== "active")
        throw new Error(
          "Bộ soạn thảo chưa lưu được. Giữ trang này mở và thử lại.",
        );
      if (!progress.pending && progress.last_saved) return;
    }
    throw new Error(
      "Chưa nhận được xác nhận lưu. Giữ tài liệu mở, kiểm tra lại trước khi rời trang.",
    );
  }
  async function perform(final) {
    if (working || !editor || closed) return;
    working = true;
    document.querySelector("main").inert = true;
    status.tabIndex = -1;
    status.focus();
    save.disabled = close.disabled = true;
    error.hidden = true;
    status.textContent = "Đang chờ lưu phiên bản vào kho BDSG…";
    try {
      await store();
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
        editor.destroyEditor();
        editor = null;
        closed = true;
        working = false;
        location.assign("/#office");
        return;
      }
      status.textContent = "Đã lưu phiên bản vào kho BDSG.";
    } catch (failure) {
      showError(failure.message);
      status.textContent = "Chưa xác nhận hoàn tất thao tác.";
    } finally {
      working = false;
      document.querySelector("main").inert = false;
      save.disabled = close.disabled = !editor;
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
      if (matchMedia("(max-width: 750px)").matches)
        throw new Error(
          "Bản Community dùng bộ soạn thảo trên máy tính. Trên điện thoại, mở kho tệp để tải hoặc nhập tài liệu.",
        );
      const id = new URLSearchParams(location.search).get("id");
      if (!/^[a-f0-9]{24}$/.test(id || ""))
        throw new Error("Thiếu tài liệu. Quay về kho tệp và chọn lại.");
      const result = await call("mo_soan_thao", { id });
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
      const readyTimeout = setTimeout(() => {
        showError(
          "Tài liệu mở lâu hơn dự kiến. Kiểm tra kết nối hoặc tải lại trình soạn thảo.",
        );
        retry.hidden = changed || working;
      }, 60000);
      editor = new DocsAPI.DocEditor("editor", {
        ...result.config,
        events: {
          onDocumentReady: () => {
            clearTimeout(readyTimeout);
            retry.hidden = true;
            error.hidden = true;
            status.textContent =
              "Tài liệu đã mở. Dùng Lưu phiên bản để ghi vào kho BDSG.";
            save.disabled = close.disabled = false;
          },
          onDocumentStateChange: (event) => {
            clientDirty = Boolean(event.data);
            if (event.data) {
              changed = true;
              status.textContent =
                "Có thay đổi đang soạn. Chưa lưu phiên bản vào kho BDSG.";
            }
          },
          onRequestClose: () => {
            if (closeRequest) closeRequest();
            else perform(true);
          },
          onError: () => {
            clearTimeout(readyTimeout);
            retry.hidden = changed || working;
            showError(
              "Bộ soạn thảo gặp lỗi. Giữ trang mở và thử lưu lại; không coi tài liệu đã được lưu.",
            );
          },
        },
      });
    } catch (failure) {
      status.textContent = "Chưa mở được tài liệu.";
      showError(failure.message);
      retry.hidden =
        changed || working || matchMedia("(max-width: 750px)").matches;
    }
  }
  open();
})();
