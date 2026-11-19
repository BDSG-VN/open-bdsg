"use strict";
(() => {
  const status = document.querySelector("#status"),
    error = document.querySelector("#error");
  const save = document.querySelector("#save"),
    close = document.querySelector("#close");
  const retry = document.querySelector("#retry");
  const abandon = document.querySelector("#abandon"),
    abandonDialog = document.querySelector("#abandon-dialog"),
    abandonConfirm = document.querySelector("#abandon-confirm"),
    abandonLoss = document.querySelector("#abandon-loss"),
    abandonShared = document.querySelector("#abandon-shared");
  let editor,
    key,
    fileId,
    abandonMode = false,
    abandonStorageKey,
    pendingAbandon = null,
    abandonCorrupt = false,
    requireReceipt = false,
    intentMode = false,
    intentStorageKey,
    pendingIntent = null,
    recoveryBlocked = false,
    editGeneration = 0,
    editorReady = false,
    changed = false,
    working = false,
    closed = false,
    clientDirty = false,
    closeRequest = null;
  const guard = window.BDSGOfficeGuard.create({ onInvalidate(message) {
    closed = true; changed = working = clientDirty = false; key = null;
    try { editor?.destroyEditor(); } catch (_) {}
    editor = null;
    document.querySelector("main").replaceChildren();
    save.disabled = close.disabled = true;
    retry.hidden = true;
    abandon.disabled = true;
    if (abandonDialog.open) abandonDialog.close();
    status.textContent = "Phiên soạn thảo đã dừng.";
    showError(message);
  } });
  const showError = (message) => {
    error.textContent = message;
    error.hidden = false;
  };
  const validRequest = value => typeof value === "string" && value.length > 0 && value.length <= 128;
  function returnToFiles() {
    try {
      if (window.parent !== window && window.parent?.BDSGOfficeLauncher?.finish(window)) return;
    } catch (_) {}
    location.assign("/#office");
  }
  const validIntent = value => typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value);
  function holdNavigation() {
    if (pendingAbandon) {
      showError("Có yêu cầu bỏ phiên chưa xác nhận. Bấm Kiểm tra yêu cầu bỏ phiên trước khi rời tài liệu.");
      status.textContent = "Tài liệu vẫn khóa để kiểm tra yêu cầu bỏ phiên.";
      return;
    }
    showError(pendingIntent?.canRetry ?
      "Lần lưu chưa có kết quả xác nhận. Chỉ bấm Thử lưu lại khi muốn tiếp tục lưu; tài liệu vẫn mở." :
      "Có lần lưu đang chờ xử lý. Hoàn tất kiểm tra lần lưu trước khi rời tài liệu.");
    status.textContent = "Tài liệu vẫn mở để kiểm tra lần lưu.";
  }
  function keepNewChanges(generation,unchanged) {
    changed = editGeneration !== generation;
    if (changed) status.textContent = unchanged ? "Có thay đổi mới chưa lưu; tài liệu vẫn mở." :
      "Đã lưu phiên bản trước. Có thay đổi mới chưa lưu; tài liệu vẫn mở.";
    return changed;
  }
  function controls() {
    const active = !!editor && guard.active;
    document.querySelector("main").inert = !active || working || !!pendingIntent || recoveryBlocked || !!pendingAbandon || abandonDialog.open;
    save.disabled = !active || working || recoveryBlocked || !!pendingAbandon || abandonDialog.open;
    close.disabled = !active || working || !!pendingIntent || recoveryBlocked || !!pendingAbandon || abandonDialog.open;
    abandon.hidden = !abandonMode;
    abandon.disabled = !abandonMode || !key || working || closed || !guard.active || abandonCorrupt;
    abandon.textContent = pendingAbandon ? "Kiểm tra yêu cầu bỏ phiên" : "Bỏ phiên soạn thảo";
    save.textContent = pendingIntent ? (pendingIntent.canRetry ? "Thử lưu lại" : "Kiểm tra lần lưu") : "Lưu phiên bản";
    if (pendingIntent || recoveryBlocked || pendingAbandon) retry.hidden = true;
  }
  function rememberIntent() {
    const record = JSON.stringify({version:1,key,request_key:pendingIntent.request_key,request_id:pendingIntent.request_id});
    try {
      window.sessionStorage.setItem(intentStorageKey,record);
      if (window.sessionStorage.getItem(intentStorageKey) !== record) throw new Error();
    } catch (_) { throw new Error("Trình duyệt chưa giữ được trạng thái lần lưu. Giữ trang mở và kiểm tra bộ nhớ của trang trước khi thử lại."); }
  }
  function forgetIntent() {
    try {
      window.sessionStorage.removeItem(intentStorageKey);
      if (window.sessionStorage.getItem(intentStorageKey) !== null) throw new Error();
    } catch (_) { throw new Error("Chưa cập nhật được trạng thái lưu trong trình duyệt. Giữ tài liệu mở và kiểm tra lại lần lưu."); }
    pendingIntent = null;
  }
  function rememberAbandon() {
    const record = JSON.stringify(pendingAbandon);
    try {
      window.sessionStorage.setItem(abandonStorageKey, record);
      if (window.sessionStorage.getItem(abandonStorageKey) !== record) throw new Error();
    } catch (_) {
      throw new Error("Chưa giữ được yêu cầu bỏ phiên trong trình duyệt. Chưa gửi thêm yêu cầu trong lần thử này; giữ trang mở và kiểm tra bộ nhớ rồi kiểm lại cùng yêu cầu.");
    }
  }
  function restoreAbandon() {
    if (!abandonStorageKey) return;
    try {
      const raw = window.sessionStorage.getItem(abandonStorageKey);
      if (raw === null) return;
      if (!abandonMode) throw new Error();
      const record = JSON.parse(raw);
      if (!record || Object.keys(record).sort().join(",") !== "file_id,key,request_key,version" ||
          record.version !== 1 || record.file_id !== fileId ||
          typeof record.key !== "string" || !/^bdsg-[a-f0-9]{32}$/.test(record.key) ||
          !validIntent(record.request_key)) throw new Error();
      pendingAbandon = record;
    } catch (_) {
      abandonCorrupt = recoveryBlocked = true;
      throw new Error("Chưa đọc được yêu cầu bỏ phiên trước đó hoặc dịch vụ chưa hỗ trợ. Giữ nguyên trạng thái; chưa thể mở sửa hay tạo yêu cầu bỏ phiên khác.");
    }
  }
  function removeRecord(namespace) {
    window.sessionStorage.removeItem(namespace);
    if (window.sessionStorage.getItem(namespace) !== null) throw new Error();
  }
  async function performAbandon() {
    if (!pendingAbandon || working || closed || !guard.active || abandonCorrupt) return;
    working = true;
    controls();
    status.textContent = "Đang kiểm tra và bỏ phiên soạn thảo…";
    error.hidden = true;
    try {
      rememberAbandon();
      const result = await call("bo_phien_soan_thao", {
        file_id: pendingAbandon.file_id, key: pendingAbandon.key, request_key: pendingAbandon.request_key,
        acknowledge_unsaved_changes: true, acknowledge_shared_session: true,
      });
      if (result.state !== "da-bo-phien" || result.file_id !== pendingAbandon.file_id ||
          result.key !== pendingAbandon.key || result.request_key !== pendingAbandon.request_key ||
          !Number.isSafeInteger(result.revoked_sessions) || result.revoked_sessions < 0)
        throw new Error("Chưa xác nhận được đúng yêu cầu bỏ phiên. Giữ trang mở và bấm Kiểm tra yêu cầu bỏ phiên.");
      guard.assertActive();
      try {
        removeRecord(intentStorageKey);
        removeRecord(abandonStorageKey);
      } catch (_) {
        throw new Error("Đã nhận biên nhận bỏ phiên nhưng chưa dọn được trạng thái trong trình duyệt. Giữ trang mở và bấm Kiểm tra yêu cầu bỏ phiên; không mở sửa tiếp.");
      }
      pendingAbandon = pendingIntent = null;
      changed = recoveryBlocked = false;
      closed = true;
      try { editor?.destroyEditor(); } catch (_) {}
      editor = null;
      status.textContent = "Đã bỏ phiên. Chỉ các phiên bản đã có trong kho BDSG được giữ lại.";
      returnToFiles();
    } catch (failure) {
      if (closed) return;
      showError(failure.message);
      status.textContent = "Chưa hoàn tất bỏ phiên. Bấm Kiểm tra yêu cầu bỏ phiên để tiếp tục cùng yêu cầu.";
    } finally {
      working = false;
      controls();
    }
  }
  function restoreIntent(id,result) {
    if (typeof guard.contextKey !== "string") throw new Error("Chưa xác minh được phạm vi giữ trạng thái lưu.");
    intentStorageKey = "bdsg-office-save:" + encodeURIComponent(guard.contextKey) + ":" + id;
    try {
      const raw = window.sessionStorage.getItem(intentStorageKey);
      if (raw !== null) {
        const record = JSON.parse(raw);
        if (!record || Object.keys(record).sort().join(",") !== "key,request_id,request_key,version" ||
          record.version !== 1 || record.key !== key || !validIntent(record.request_key) ||
          !(record.request_id === null || validRequest(record.request_id))) throw new Error();
        pendingIntent = {...record,generation:editGeneration,canRetry:false,restored:true};
      }
      if (result.pending_save) {
        const record = result.pending_save;
        if (!validIntent(record.request_key) || !validRequest(record.request_id) ||
          (pendingIntent && (pendingIntent.request_key !== record.request_key ||
            (pendingIntent.request_id && pendingIntent.request_id !== record.request_id)))) throw new Error();
        pendingIntent = {...record,generation:editGeneration,canRetry:false,restored:true};
        rememberIntent();
      }
      if (pendingIntent) changed = true;
    } catch (_) {
      recoveryBlocked = true;
      throw new Error("Có trạng thái lưu trước chưa đối soát được với phiên này. Quay về kho tệp để kiểm tra; không tự bỏ lần lưu cũ.");
    }
  }
  retry.addEventListener("click", () => {
    if (!closed && guard.active && !changed && !working && !pendingIntent && !recoveryBlocked && !pendingAbandon && !abandonDialog.open) location.reload();
  });
  async function call(name, args) {
    let response, value;
    try {
      response = await guard.fetch("/api/tools", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(25000),
      body: JSON.stringify({ name: "van_phong." + name, arguments: args }),
      });
      value = await response.json();
    } catch (_) {
      guard.assertActive();
      if (name === "bo_phien_soan_thao") throw new Error("Chưa nhận được phản hồi bỏ phiên. Giữ trang mở và bấm Kiểm tra yêu cầu bỏ phiên; hệ thống sẽ dùng cùng yêu cầu.");
      throw new Error(intentMode ? "Chưa nhận được phản hồi. Giữ trang mở và bấm Kiểm tra lần lưu." :
        "Kết nối chưa xác nhận được thao tác. Giữ tài liệu mở, kiểm tra kết nối rồi thử lại.");
    }
    guard.assertActive();
    if (!response.ok || value?.ok !== true || !value.ket_qua ||
      typeof value.ket_qua !== "object" || Array.isArray(value.ket_qua))
      throw new Error(
        "Không hoàn tất thao tác. Kiểm tra quyền, kết nối và dịch vụ soạn thảo rồi thử lại.",
      );
    return value.ket_qua;
  }
  async function waitForEditor() {
    for (let attempt = 0; clientDirty && attempt < 100; attempt++)
      await new Promise((resolve) => setTimeout(resolve, 100));
    if (clientDirty)
      throw new Error(
        "Thay đổi chưa gửi hết tới bộ soạn thảo. Nhấn Lưu trong thanh công cụ của tài liệu rồi thử lại.",
      );
  }
  async function storeIntent() {
    const sending = !pendingIntent || pendingIntent.canRetry;
    if (!pendingIntent) {
      await waitForEditor();
      pendingIntent = {request_key:crypto.randomUUID(),request_id:null,generation:editGeneration,canRetry:false};
    }
    if (sending) {
      pendingIntent.canRetry = false;
      rememberIntent();
      const result = await call("luu_soan_thao", {key,request_key:pendingIntent.request_key});
      if (!validRequest(result.request_id)) throw new Error("Chưa nhận được mã lệnh lưu. Bấm Kiểm tra lần lưu để xác minh.");
      if (pendingIntent.request_id && pendingIntent.request_id !== result.request_id)
        throw new Error("Kết quả không khớp lần lưu đang chờ. Giữ tài liệu mở và kiểm tra lại.");
      pendingIntent.request_id = result.request_id;
      rememberIntent();
    }
    for (let attempt=0;attempt<20;attempt++) {
      const progress = await call("phien_soan_thao", {key,request_key:pendingIntent.request_key});
      if (progress.request_key !== pendingIntent.request_key || progress.state !== "active")
        throw new Error("Kết quả không khớp phiên lưu đang chờ. Giữ tài liệu mở và kiểm tra lại.");
      if (progress.command_state === "not-started" && progress.request_id === null && !pendingIntent.request_id) {
        pendingIntent.canRetry = true;
        throw new Error("Chưa tìm thấy lệnh của lần lưu này. Bấm Thử lưu lại để gửi cùng lần lưu; hệ thống không tạo lệnh trùng.");
      }
      if (!validRequest(progress.request_id) || (pendingIntent.request_id && progress.request_id !== pendingIntent.request_id))
        throw new Error("Chưa xác nhận được đúng mã lệnh. Giữ tài liệu mở và kiểm tra lại.");
      pendingIntent.request_id = progress.request_id;
      rememberIntent();
      if (progress.command_state === "committed") {
        const generation = pendingIntent.generation;
        forgetIntent();
        return {generation,unchanged:false};
      }
      if (progress.command_state === "unchanged") {
        if (changed || pendingIntent.restored)
          throw new Error("Chưa có phiên bản mới được xác nhận cho lần lưu cũ. Giữ tài liệu mở để kiểm tra, không tự bỏ lần lưu.");
        const generation = pendingIntent.generation;
        forgetIntent();
        return {generation,unchanged:true};
      }
      if (progress.command_state === "failed") {
        changed = true;
        forgetIntent();
        throw new Error("Lần lưu chưa tạo được phiên bản mới. Kiểm tra thay đổi trong tài liệu rồi lưu lại.");
      }
      if (["abandoned","superseded"].includes(progress.command_state))
        throw new Error("Lần lưu đã kết thúc mà chưa có bản lưu xác nhận. Quay về kho tệp để kiểm tra phiên bản.");
      if (attempt<19) await new Promise(resolve=>setTimeout(resolve,2000));
    }
    throw new Error("Chưa nhận được xác nhận lưu. Giữ trang mở và bấm Kiểm tra lần lưu; không gửi thêm lệnh mới.");
  }
  async function store() {
    if (intentMode) return storeIntent();
    await waitForEditor();
    const generation = editGeneration;
    const result = await call("luu_soan_thao", { key });
    if (result.state === "khong-co-thay-doi") {
      if (changed)
        throw new Error(
          "Bộ soạn thảo chưa xác nhận bản sửa mới. Giữ trang mở, nhấn Lưu trong tài liệu rồi thử lại.",
        );
      return {generation,unchanged:true};
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
        return {generation,unchanged:false};
    }
    throw new Error(
      "Chưa nhận được xác nhận lưu. Giữ tài liệu mở, kiểm tra lại trước khi rời trang.",
    );
  }
  async function perform(final) {
    if (working || !editor || closed || !guard.active || pendingAbandon || abandonDialog.open) return;
    if (final && (pendingIntent || recoveryBlocked)) { holdNavigation(); return; }
    working = true;
    document.querySelector("main").inert = true;
    status.tabIndex = -1;
    status.focus();
    save.disabled = close.disabled = true;
    error.hidden = true;
    status.textContent = pendingIntent && !pendingIntent.canRetry ?
      "Đang kiểm tra lần lưu đang chờ…" : "Đang chờ lưu phiên bản vào kho BDSG…";
    try {
      const {generation,unchanged} = await store();
      guard.assertActive();
      if (keepNewChanges(generation,unchanged)) return;
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
        if (keepNewChanges(generation,unchanged)) return;
        editor.destroyEditor();
        editor = null;
        closed = true;
        working = false;
        returnToFiles();
        return;
      }
      status.textContent = unchanged ? "Không có thay đổi cần lưu." : "Đã lưu phiên bản vào kho BDSG.";
    } catch (failure) {
      if (closed) return;
      showError(failure.message);
      status.textContent = "Chưa xác nhận hoàn tất thao tác.";
    } finally {
      working = false;
      controls();
    }
  }
  save.addEventListener("click", () => perform(false));
  abandon.addEventListener("click", () => {
    if (abandon.disabled || working || closed || !guard.active) return;
    if (pendingAbandon) return performAbandon();
    abandonLoss.checked = abandonShared.checked = false;
    abandonConfirm.disabled = true;
    abandonDialog.showModal();
    controls();
  });
  function confirmAbandonControls() {
    abandonConfirm.disabled = !abandonLoss.checked || !abandonShared.checked || working;
  }
  abandonLoss.addEventListener("change", confirmAbandonControls);
  abandonShared.addEventListener("change", confirmAbandonControls);
  document.querySelector("#abandon-cancel").addEventListener("click", () => {
    abandonDialog.close();
    controls();
    abandon.focus();
  });
  abandonDialog.addEventListener("close", controls);
  abandonConfirm.addEventListener("click", () => {
    if (!abandonDialog.open || !abandonLoss.checked || !abandonShared.checked ||
        working || closed || !guard.active || !abandonMode || abandonCorrupt) return;
    pendingAbandon = {version:1,file_id:fileId,key,request_key:crypto.randomUUID()};
    abandonDialog.close();
    return performAbandon();
  });
  close.addEventListener("click", () => perform(true));
  document.querySelector("#back").addEventListener("click", (event) => {
    event.preventDefault();
    // Chưa có editor thì rời iframe không bỏ nội dung đang soạn. Giữ record để đối soát khi mở lại.
    if (!editor && recoveryBlocked && !working) { returnToFiles(); return; }
    if (!closed && (editor || pendingAbandon || recoveryBlocked)) {
      event.preventDefault();
      if (pendingIntent || recoveryBlocked || working || pendingAbandon || abandonDialog.open) { holdNavigation(); return; }
      perform(true);
    } else {
      returnToFiles();
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (!closed && (changed || working || pendingIntent || recoveryBlocked || pendingAbandon)) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  async function open() {
    try {
      await guard.ready;
      const id = new URLSearchParams(location.search).get("id");
      if (!/^[a-f0-9]{24}$/.test(id || ""))
        throw new Error("Thiếu tài liệu. Quay về kho tệp và chọn lại.");
      const result = await call("mo_soan_thao", { id });
      const protocol = Object.prototype.hasOwnProperty.call(result, "save_protocol")
        ? result.save_protocol : "legacy";
      if (!["legacy", "request-ledger-v1"].includes(protocol))
        throw new Error("Chưa hỗ trợ phiên bản soạn thảo này. Tải lại trang rồi mở lại tài liệu.");
      requireReceipt = protocol === "request-ledger-v1";
      if ((Object.hasOwn(result,"save_intents") && typeof result.save_intents !== "boolean") ||
        (result.save_intents === true && !requireReceipt)) throw new Error("Phiên này chưa hỗ trợ đối soát lưu. Tải lại trang rồi mở lại tài liệu.");
      intentMode = result.save_intents === true;
      if ((Object.hasOwn(result,"abandon_sessions") && typeof result.abandon_sessions !== "boolean") ||
          (result.abandon_sessions === true && !intentMode))
        throw new Error("Phiên này chưa hỗ trợ bỏ phiên có đối soát. Giữ trạng thái cũ và mở lại khi dịch vụ sẵn sàng.");
      fileId = id;
      if (intentMode && (typeof result.key !== "string" || !/^bdsg-[a-f0-9]{32}$/.test(result.key)))
        throw new Error("Chưa xác nhận được phiên tài liệu. Quay về kho tệp và mở lại.");
      key = result.key;
      abandonMode = result.abandon_sessions === true;
      if (typeof guard.contextKey === "string") {
        abandonStorageKey = "bdsg-office-abandon:" + encodeURIComponent(guard.contextKey) + ":" + id;
        intentStorageKey = "bdsg-office-save:" + encodeURIComponent(guard.contextKey) + ":" + id;
      }
      if (abandonMode && !abandonStorageKey) throw new Error("Chưa xác minh được phạm vi bỏ phiên.");
      restoreAbandon();
      if (pendingAbandon) {
        status.textContent = "Có yêu cầu bỏ phiên chưa xác nhận. Bấm Kiểm tra yêu cầu bỏ phiên; chưa mở sửa tài liệu.";
        controls();
        return;
      }
      if (intentMode) restoreIntent(id,result);
      else if (typeof guard.contextKey === "string") {
        try {
          const namespace = "bdsg-office-save:" + encodeURIComponent(guard.contextKey) + ":" + id;
          if (window.sessionStorage.getItem(namespace) !== null) throw new Error();
        } catch (_) {
          recoveryBlocked = true;
          throw new Error("Dịch vụ chưa kiểm tra được lần lưu cũ. Quay về kho tệp và mở lại khi dịch vụ sẵn sàng; trạng thái cũ vẫn được giữ.");
        }
      }
      if (result.api_url !== "/office-docs/web-apps/apps/api/documents/api.js")
        throw new Error("Nguồn bộ soạn thảo không hợp lệ.");
      if (matchMedia("(max-width: 750px)").matches)
        throw new Error(
          "Bản Community dùng bộ soạn thảo trên máy tính. Trên điện thoại, mở kho tệp để tải hoặc nhập tài liệu; có thể bỏ phiên đang kẹt sau khi xác nhận.",
        );
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
        retry.hidden = changed || working || !!pendingIntent || recoveryBlocked || !!pendingAbandon;
      }, 60000);
      editor = new DocsAPI.DocEditor("editor", {
        ...result.config,
        events: {
          onDocumentReady: () => {
            if (!guard.active || editorReady) return;
            editorReady = true;
            clearTimeout(readyTimeout);
            retry.hidden = true;
            if (pendingAbandon) { controls(); return; }
            error.hidden = true;
            status.textContent = pendingIntent ? "Có lần lưu đang chờ xác nhận. Bấm Kiểm tra lần lưu trước khi sửa tiếp." :
              "Tài liệu đã mở. Dùng Lưu phiên bản để ghi vào kho BDSG.";
            controls();
          },
          onDocumentStateChange: (event) => {
            if (!guard.active) return;
            clientDirty = Boolean(event.data);
            if (event.data) {
              editGeneration++;
              changed = true;
              if (!pendingIntent && !working && !pendingAbandon) status.textContent =
                "Có thay đổi đang soạn. Chưa lưu phiên bản vào kho BDSG.";
            }
          },
          onRequestClose: () => {
            if (!guard.active) return;
            if (closeRequest) closeRequest();
            else if (pendingIntent || recoveryBlocked || working || pendingAbandon || abandonDialog.open) holdNavigation();
            else perform(true);
          },
          onError: () => {
            if (!guard.active) return;
            clearTimeout(readyTimeout);
            retry.hidden = changed || working || !!pendingIntent || recoveryBlocked || !!pendingAbandon;
            showError(
              pendingAbandon ? "Bộ soạn thảo gặp lỗi. Giữ trang mở và bấm Kiểm tra yêu cầu bỏ phiên; không mở sửa tiếp." :
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
        changed || working || !!pendingIntent || recoveryBlocked || matchMedia("(max-width: 750px)").matches;
      controls();
    }
  }
  open();
})();
