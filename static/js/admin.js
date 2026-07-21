(function () {
    const API_BASE = "/api/backup";

    function formatBytes(bytes) {
        if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
        const units = ["B", "KB", "MB", "GB"];
        let value = bytes;
        let index = 0;
        while (value >= 1024 && index < units.length - 1) {
            value /= 1024;
            index += 1;
        }
        return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
    }

    function setStatus(root, status, message) {
        const statusChip = root.querySelector("[data-backup-status]");
        const messageNode = root.querySelector("[data-backup-message]");
        if (statusChip) statusChip.textContent = status;
        if (messageNode) messageNode.textContent = message;
    }

    function renderRows(root, backups) {
        const tbody = root.querySelector("[data-backup-list]");
        if (!tbody) return;
        if (!backups.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="muted">No backups found.</td></tr>';
            return;
        }
        tbody.innerHTML = backups.map((backup) => `
            <tr>
                <td>${backup.file || backup.path || "backup.enc"}</td>
                <td>${backup.created || "—"}</td>
                <td>${formatBytes(Number(backup.size || 0))}</td>
                <td><button type="button" class="btn btn-secondary pill-btn" data-backup-restore="${backup.path || backup.file}">Restore</button></td>
            </tr>
        `).join("");
    }

    async function loadBackups(root) {
        setStatus(root, "Loading", "Fetching encrypted backups...");
        const response = await fetch(`${API_BASE}/list`, { credentials: "same-origin" });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
            throw new Error(payload.detail || "Unable to load backups");
        }
        renderRows(root, payload.backups || []);
        setStatus(root, "Ready", `Loaded ${payload.backups?.length || 0} backup(s).`);
    }

    async function createBackup(root) {
        setStatus(root, "Working", "Creating encrypted backup...");
        const response = await fetch(`${API_BASE}/create`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: "{}",
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
            throw new Error(payload.detail || payload.error || "Backup failed");
        }
        setStatus(root, "Success", `Backup created: ${payload.backup_file}`);
        await loadBackups(root);
    }

    async function restoreBackup(root, backupFile) {
        const confirmed = window.confirm(`Restore backup "${backupFile}"? This will overwrite the current database.`);
        if (!confirmed) return;
        setStatus(root, "Working", "Restoring backup...");
        const response = await fetch(`${API_BASE}/restore?backup_file=${encodeURIComponent(backupFile)}`, {
            method: "POST",
            credentials: "same-origin",
        });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
            throw new Error(payload.detail || payload.error || "Restore failed");
        }
        setStatus(root, "Success", payload.message || "Backup restored.");
    }

    document.addEventListener("DOMContentLoaded", () => {
        const root = document.querySelector("[data-backup-admin]");
        if (!root) return;
        const createButton = root.querySelector("[data-backup-create]");
        const refreshButton = root.querySelector("[data-backup-refresh]");
        createButton?.addEventListener("click", async () => {
            try {
                await createBackup(root);
            } catch (error) {
                setStatus(root, "Error", error.message || "Backup failed");
            }
        });
        refreshButton?.addEventListener("click", async () => {
            try {
                await loadBackups(root);
            } catch (error) {
                setStatus(root, "Error", error.message || "Unable to refresh backups");
            }
        });
        root.addEventListener("click", async (event) => {
            const button = event.target.closest("[data-backup-restore]");
            if (!button) return;
            try {
                await restoreBackup(root, button.dataset.backupRestore);
            } catch (error) {
                setStatus(root, "Error", error.message || "Restore failed");
            }
        });
        loadBackups(root).catch((error) => setStatus(root, "Error", error.message || "Unable to load backups"));
    });
}());
