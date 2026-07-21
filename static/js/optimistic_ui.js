(() => {
  const pendingState = new Map();

  function snapshotText(node) {
    return node ? node.textContent : "";
  }

  function setPending(target, pending, pendingLabel = "Saving...") {
    if (!target) return;
    if (pending) {
      pendingState.set(target, snapshotText(target));
      target.dataset.pending = "1";
      if ("disabled" in target) target.disabled = true;
      if ("textContent" in target) target.textContent = pendingLabel;
    } else {
      const previous = pendingState.get(target);
      if (previous !== undefined && "textContent" in target) target.textContent = previous;
      if ("disabled" in target) target.disabled = false;
      delete target.dataset.pending;
      pendingState.delete(target);
    }
  }

  function installOptimisticForm(form, { onSuccess, onFailure, pendingLabel = "Saving..." } = {}) {
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      setPending(submitter, true, pendingLabel);
      const rollback = () => setPending(submitter, false);
      try {
        const response = await (window.KashUI?.safeFetch ? window.KashUI.safeFetch(form.action, {
          method: form.method || "POST",
          body: new FormData(form),
        }) : fetch(form.action, { method: form.method || "POST", body: new FormData(form) }));
        const data = await response.json().catch(() => ({}));
        if (data?.success === false) throw new Error(data.error || data.detail || "Request failed.");
        if (typeof onSuccess === "function") onSuccess(data, form);
      } catch (error) {
        rollback();
        if (typeof onFailure === "function") onFailure(error, form);
        return;
      }
      rollback();
    });
  }

  function optimisticListAppend(list, item, render, rollbackHint = null) {
    if (!list) return null;
    const node = render(item, { optimistic: true, rollbackHint });
    if (node) list.prepend(node);
    return () => node && node.remove();
  }

  window.KashUI = window.KashUI || {};
  window.KashUI.setPending = setPending;
  window.KashUI.installOptimisticForm = installOptimisticForm;
  window.KashUI.optimisticListAppend = optimisticListAppend;
})();
