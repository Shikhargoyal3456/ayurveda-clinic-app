(function () {
    const fab = document.querySelector(".voice-fab");
    if (!fab) return;

    window.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "v") {
            event.preventDefault();
            window.location.href = fab.getAttribute("href") || "/consultation/voice";
        }
    });
})();
