(function () {
    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("[data-export-url]").forEach((button) => {
            button.addEventListener("click", () => {
                const url = button.getAttribute("data-export-url");
                if (url) window.location.href = url;
            });
        });
    });
}());
