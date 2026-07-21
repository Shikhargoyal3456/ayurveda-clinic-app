(() => {
    const role = window.localStorage.getItem("kash_role") || "";
    if (window.location.pathname.startsWith("/doctor") && role === "patient") {
        window.location.href = "/patient";
    }
})();
