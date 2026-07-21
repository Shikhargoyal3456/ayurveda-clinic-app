(() => {
  const toastRootId = "toast-container";

  function ensureToastRoot() {
    let root = document.getElementById(toastRootId);
    if (!root) {
      root = document.createElement("div");
      root.id = toastRootId;
      document.body.appendChild(root);
    }
    return root;
  }

  function showToast(message, kind = "error") {
    const root = ensureToastRoot();
    const toast = document.createElement("div");
    toast.className = `toast toast--${kind}`;
    toast.innerHTML = `<span>${String(message || "Something went wrong.")}</span><button class="toast__close" type="button" aria-label="Dismiss">&times;</button>`;
    toast.querySelector("button")?.addEventListener("click", () => toast.remove());
    root.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("toast--visible"));
    setTimeout(() => {
      toast.classList.remove("toast--visible");
      setTimeout(() => toast.remove(), 200);
    }, 4000);
  }

  async function safeFetch(input, init = {}) {
    try {
      const response = await fetch(input, {
        credentials: init.credentials || "same-origin",
        ...init,
      });
      if (!response.ok) {
        let message = "Request failed.";
        try {
          const payload = await response.clone().json();
          message = payload.error || payload.detail || message;
        } catch (_) {
          try {
            message = (await response.text()) || message;
          } catch (_) {
            /* ignore */
          }
        }
        throw new Error(message);
      }
      return response;
    } catch (error) {
      showToast(error?.message || "Network error. Please try again.", "error");
      throw error;
    }
  }

  window.KashUI = window.KashUI || {};
  window.KashUI.showToast = showToast;
  window.KashUI.safeFetch = safeFetch;

  window.addEventListener("error", (event) => {
    const message = event?.error?.message || "Something went wrong.";
    showToast(message, "error");
  });

  window.addEventListener("unhandledrejection", (event) => {
    const message = event?.reason?.message || "Something went wrong.";
    showToast(message, "error");
  });
})();
