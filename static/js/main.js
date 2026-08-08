(function () {
    const languageToggle = document.querySelector("[data-language-toggle]");
    if (languageToggle) {
        languageToggle.addEventListener("click", () => {
            const current = languageToggle.dataset.lang || "hi";
            const next = current === "hi" ? "en" : "hi";
            languageToggle.dataset.lang = next;
            languageToggle.querySelector("span").textContent = next === "hi" ? "Hindi" : "English";
        });
    }
})();
