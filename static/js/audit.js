(function () {
    document.addEventListener("DOMContentLoaded", () => {
        const root = document.querySelector("[data-audit-root]");
        const tbody = root?.querySelector("[data-audit-list]");
        if (!root || !tbody) return;
        fetch("/admin/audit/api", { credentials: "same-origin" })
            .then((response) => response.json())
            .then((payload) => {
                if (!payload.success || !Array.isArray(payload.logs)) return;
                tbody.innerHTML = payload.logs.map((log) => `
                    <tr>
                        <td>${log.created_at || "—"}</td>
                        <td>${log.action || "—"}</td>
                        <td>${log.resource || "—"}</td>
                        <td>${log.user_id || "—"}</td>
                        <td><pre style="white-space:pre-wrap;margin:0;">${JSON.stringify(log.details || {}, null, 2)}</pre></td>
                    </tr>
                `).join("");
            })
            .catch(() => {
                tbody.innerHTML = '<tr><td colspan="5" class="muted">Unable to load audit logs.</td></tr>';
            });
    });
}());
