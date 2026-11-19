"use strict";
(() => {
  const message = "Danh tính phiên đã thay đổi hoặc hết hạn. Quay về kho tệp và mở lại sau khi đăng nhập.";
  window.BDSGSessionGuard = Object.freeze({
    create({ onInvalidate = () => {} } = {}) {
      let actorId = null, stopped = false, pendingHint = null;
      const controller = new AbortController();
      const failure = () => new Error(message);
      function invalidate() {
        if (stopped) return;
        stopped = true;
        controller.abort();
        onInvalidate(message);
      }
      function assertActive() {
        if (stopped || !actorId) throw failure();
      }
      function hint(value) {
        if (value?.type !== "identity-changed" || typeof value.actorId !== "string") return;
        if (actorId === null) pendingHint = value.actorId;
        else if (value.actorId !== actorId) invalidate();
      }
      let channel;
      try {
        channel = new BroadcastChannel("bdsg-session-v27");
        channel.addEventListener("message", event => hint(event.data));
      } catch (_) {}
      window.addEventListener("storage", event => {
        if (event.key !== "bdsg-session-change") return;
        try { hint(JSON.parse(event.newValue)); } catch (_) {}
      });
      async function readActor() {
        const response = await fetch("/api/me", { credentials: "same-origin", cache: "no-store", signal: controller.signal });
        if (response.status === 401) { invalidate(); throw failure(); }
        if (!response.ok) throw new Error("Chưa kiểm tra được phiên BDSG. Hãy tải lại trang.");
        const value = await response.json();
        return value.authenticated === true && typeof value.user?.id === "string" ? value.user.id : null;
      }
      const ready = (async () => {
        const current = await readActor();
        if (!current || stopped || (pendingHint !== null && pendingHint !== current)) {
          invalidate(); throw failure();
        }
        actorId = current;
      })();
      async function check() {
        await ready;
        assertActive();
        const current = await readActor();
        if (current !== actorId) invalidate();
        assertActive();
      }
      window.addEventListener("focus", () => { check().catch(() => {}); });
      async function guardedFetch(path, options = {}) {
        await ready;
        assertActive();
        const headers = new Headers(options.headers);
        headers.set("X-BDSG-Actor", actorId);
        const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal;
        let response;
        try { response = await fetch(path, { ...options, headers, credentials: "same-origin", signal }); }
        catch (error) { if (stopped) throw failure(); throw error; }
        if (response.status === 401) invalidate();
        if (response.status === 409) {
          try { if ((await response.clone().json()).code === "identity_changed") invalidate(); } catch (_) {}
        }
        assertActive();
        return response;
      }
      return Object.freeze({ ready, fetch: guardedFetch, check, assertActive, get active() { return !stopped && actorId !== null; } });
    },
  });
})();
