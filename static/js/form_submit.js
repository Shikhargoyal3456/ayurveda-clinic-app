document.querySelectorAll("form[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const submitButton = form.querySelector('button[type="submit"], button:not([type]), input[type="submit"]');
        if (!(submitButton instanceof HTMLButtonElement || submitButton instanceof HTMLInputElement)) {
            return;
        }
        const loadingText = submitButton.getAttribute("data-loading-text");
        submitButton.disabled = true;
        if (loadingText && submitButton instanceof HTMLButtonElement) {
            submitButton.dataset.originalText = submitButton.innerHTML;
            submitButton.innerHTML = loadingText;
        }
        if (loadingText && submitButton instanceof HTMLInputElement) {
            submitButton.dataset.originalText = submitButton.value;
            submitButton.value = loadingText;
        }

        window.setTimeout(() => {
            if (!submitButton.disabled) {
                return;
            }
            submitButton.disabled = false;
            if (submitButton instanceof HTMLButtonElement && submitButton.dataset.originalText) {
                submitButton.innerHTML = submitButton.dataset.originalText;
            }
            if (submitButton instanceof HTMLInputElement && submitButton.dataset.originalText) {
                submitButton.value = submitButton.dataset.originalText;
            }
        }, 8000);
    });
});

document.querySelectorAll("form[data-confirm-submit]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (form.dataset.confirmAccepted === "true") {
            delete form.dataset.confirmAccepted;
            return;
        }
        const message = form.getAttribute("data-confirm-submit") || "Are you sure?";
        event.preventDefault();
        const submitter = event.submitter || form.querySelector('button[type="submit"], button:not([type]), input[type="submit"]');
        if (submitter instanceof HTMLElement) {
            submitter.setAttribute("data-confirm", "");
            submitter.setAttribute("data-confirm-title", form.getAttribute("data-confirm-title") || "Confirm action");
            submitter.setAttribute("data-confirm-message", message);
            submitter.setAttribute("data-confirm-form", form.id || "");
            submitter.setAttribute("data-confirm-label", form.getAttribute("data-confirm-label") || "Continue");
            submitter.setAttribute("data-confirm-type", form.getAttribute("data-confirm-type") || "warning");
            submitter.click();
        }
    });
});
