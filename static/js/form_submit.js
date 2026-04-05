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
    });
});

document.querySelectorAll("form[data-confirm-submit]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        const message = form.getAttribute("data-confirm-submit") || "Are you sure?";
        if (!window.confirm(message)) {
            event.preventDefault();
        }
    });
});
