"use strict";
(() => {
  const message = "Phạm vi hoặc quyền soạn thảo đã thay đổi. Quay về kho tệp và mở lại tài liệu trong đúng đơn vị.";
  window.BDSGOfficeGuard = Object.freeze({
    create({ onInvalidate = () => {} } = {}) {
      let owner, unit, token, initial;
      // Chụp trước IO: cha đổi A→B trong lúc /api/me chờ không được chọn B.
      try {
        owner = window.opener || (window.parent !== window ? window.parent : null);
        unit = owner?.BDSGUnit;
        token = unit?.capture();
        const snapshot = unit?.snapshot();
        if (snapshot) initial = {...snapshot, selected: snapshot.selected ? {...snapshot.selected} : null};
      } catch (_) { owner = unit = null; }
      let stopped = false, booted = false, scoped = false, interval, checking, contextKey;
      const controller = new AbortController();
      const failure = () => new Error(message);
      let pendingInvalidation = null;
      function notifyInvalidation() {
        if (pendingInvalidation === null) return;
        const reason = pendingInvalidation;
        pendingInvalidation = null;
        onInvalidate(reason);
      }
      function invalidate(reason = message, deferNotification = false) {
        if (stopped) return;
        stopped = true;
        controller.abort();
        clearInterval(interval);
        try { owner?.removeEventListener("bdsg-unit-changed", parentChanged); } catch (_) {}
        pendingInvalidation = reason;
        if (!deferNotification) notifyInvalidation();
      }
      const session = window.BDSGSessionGuard.create({onInvalidate: invalidate});
      function parentCurrent() {
        try { return !!owner && !owner.closed && !(owner.frameElement && !owner.frameElement.isConnected) &&
          !!unit && owner.BDSGUnit === unit && unit.current(token); }
        catch (_) { return false; }
      }
      function assertActive() {
        if (scoped && !parentCurrent()) invalidate();
        if (stopped || !booted) throw failure();
        session.assertActive();
      }
      function parentChanged() {
        if (unit && !parentCurrent()) invalidate();
      }
      try { owner?.addEventListener("bdsg-unit-changed", parentChanged); } catch (_) {}
      async function membership() {
        assertActive();
        if (!scoped) return;
        const response = await session.fetch("/api/units", {cache:"no-store", signal:controller.signal});
        const data = await response.json();
        assertActive();
        const expected = initial.selected;
        if (!response.ok || !Array.isArray(data.units) || !data.units.some(row =>
          row.id === expected.id && row.epoch === expected.epoch && row.revision === expected.revision))
          throw failure();
      }
      const ready = (async () => {
        try {
          await session.ready;
          const response = await session.fetch("/api/me", {cache:"no-store", signal:controller.signal});
          const me = await response.json();
          if (!response.ok || !me.authenticated || typeof me.user?.id !== "string") throw failure();
          scoped = me.workspace?.mode === "units";
          if (initial?.mode === "units" && !scoped) throw failure();
          if (scoped && (!parentCurrent() || initial?.mode !== "units" ||
            initial.actorId !== me.user.id || initial.status !== "ready" || !initial.selected)) throw failure();
          booted = true;
          contextKey = JSON.stringify([me.user.id,scoped ? initial.selected.id : null,
            scoped ? initial.selected.epoch : null,scoped ? initial.selected.revision : null]);
          await membership();
          if (scoped) interval = setInterval(() => { check().catch(() => {}); }, 5000);
        } catch (error) { invalidate(); throw error; }
      })();
      async function check() {
        if (checking) return checking;
        checking = (async () => {
          try { await ready; assertActive(); await session.check(); await membership(); assertActive(); }
          catch (error) { invalidate(); throw error; }
        })().finally(() => { checking = null; });
        return checking;
      }
      window.addEventListener("focus", () => { check().catch(() => {}); });
      // Khóa IO ngay; hủy SDK trong pagehide có thể mở dialog trên frame đang bị tách.
      // Trang quay lại từ bfcache phải dọn editor trước khi người dùng tiếp tục.
      window.addEventListener("pagehide", () => invalidate(message, true));
      window.addEventListener("pageshow", notifyInvalidation);
      document.addEventListener("visibilitychange", () => { check().catch(() => {}); });
      async function guardedFetch(path, options = {}) {
        await ready;
        assertActive();
        const headers = new Headers(options.headers);
        for (const name of ["X-BDSG-Unit", "X-BDSG-Unit-Epoch", "X-BDSG-Unit-Revision"]) headers.delete(name);
        if (scoped) {
          headers.set("X-BDSG-Unit", initial.selected.id);
          headers.set("X-BDSG-Unit-Epoch", String(initial.selected.epoch));
          headers.set("X-BDSG-Unit-Revision", String(initial.selected.revision));
        }
        const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal;
        const response = await session.fetch(path, {...options,headers,signal});
        if (response.status === 409) {
          try { if ((await response.clone().json()).code === "unit_changed") invalidate(); } catch (_) {}
        }
        assertActive();
        return response;
      }
      return Object.freeze({ready,fetch:guardedFetch,check,assertActive,
        get contextKey() { assertActive(); return contextKey; },
        get active() { try { assertActive(); return session.active; } catch (_) { return false; } }});
    },
  });
})();
