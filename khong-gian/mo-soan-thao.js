"use strict";
(() => {
  let mounted = null;
  function reset() {
    if (!mounted) return;
    const previous = mounted;
    mounted = null;
    previous.dialog.close();
    previous.dialog.remove();
    if (previous.trigger?.isConnected) previous.trigger.focus();
  }
  function open(id, onReturn = () => {}) {
    const unit = window.BDSGUnit;
    const scope = unit?.snapshot();
    if (mounted || !/^[a-f0-9]{24}$/.test(id) || scope?.mode !== "units" ||
        scope.status !== "ready" || !scope.selected || scope.capabilities?.office_editor !== true)
      throw new Error("Chưa mở được bộ soạn thảo. Chọn lại đơn vị và tài liệu có quyền chỉnh sửa.");
    const token = unit.capture();
    const dialog = document.createElement("dialog");
    dialog.className = "office-editor-window";
    dialog.setAttribute("aria-label", "Bộ soạn thảo BDSG Office");
    const frame = document.createElement("iframe");
    frame.title = "Soạn thảo tài liệu trong đơn vị hiện tại";
    // Mã tệp chỉ định tài nguyên; guard con đọc scope từ cha, không lấy quyền từ URL.
    frame.src = "/soan-thao.html?id=" + encodeURIComponent(id);
    dialog.addEventListener("cancel", event => {
      event.preventDefault();
      frame.focus();
    });
    mounted = {dialog,frame,unit,token,onReturn,trigger:document.activeElement};
    dialog.append(frame);
    document.body.append(dialog);
    try { dialog.showModal(); frame.focus(); }
    catch (error) { reset(); throw error; }
  }
  function finish(child) {
    if (!mounted || child !== mounted.frame.contentWindow) return false;
    const previous = mounted;
    const current = previous.unit.current(previous.token);
    reset();
    if (current) previous.onReturn();
    return true;
  }
  window.addEventListener("bdsg-unit-changed", () => {
    if (mounted && !mounted.unit.current(mounted.token)) reset();
  });
  window.BDSGOfficeLauncher = Object.freeze({open,finish,reset,get active(){return !!mounted;}});
})();
