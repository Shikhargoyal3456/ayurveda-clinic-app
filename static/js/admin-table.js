(function () {
    const PAGE_SIZE = 20;

    function debounce(callback, delay) {
        let timeoutId = 0;
        return function (...args) {
            window.clearTimeout(timeoutId);
            timeoutId = window.setTimeout(() => callback.apply(this, args), delay);
        };
    }

    function csvEscape(value) {
        const text = String(value ?? "").replace(/"/g, '""');
        return `"${text}"`;
    }

    function getCellValue(row, index) {
        const cell = row.children[index];
        return cell ? cell.textContent.trim() : "";
    }

    function buildSkeletonRows(columnCount) {
        return Array.from({ length: 3 }, () => `
            <tr class="table-skeleton-row" aria-hidden="true">
                ${Array.from({ length: columnCount }, () => '<td><span class="skeleton-line"></span></td>').join("")}
            </tr>
        `).join("");
    }

    function initTable(table) {
        const tbody = table.tBodies[0];
        if (!tbody) return;

        const headers = Array.from(table.querySelectorAll("thead th"));
        const exportName = table.dataset.exportName || "table-export";
        const enablePagination = table.dataset.pagination !== "false";
        const controls = document.createElement("div");
        controls.className = "table-toolbar";
        controls.innerHTML = `
            <div class="table-toolbar__search">
                <label class="sr-only" for="">Search table</label>
                <input type="search" class="form-control" placeholder="Search this table">
            </div>
            <div class="table-toolbar__filters"></div>
            <button type="button" class="btn btn-outline-dark btn-sm">Export CSV</button>
        `;
        table.parentElement?.insertBefore(controls, table);

        const searchInput = controls.querySelector("input");
        const filterHost = controls.querySelector(".table-toolbar__filters");
        const exportButton = controls.querySelector("button");
        const pagination = document.createElement("div");
        pagination.className = "table-pagination";
        pagination.innerHTML = `
            <span class="table-pagination__label">Showing 0-0 of 0</span>
            <div class="hero-actions">
                <button type="button" class="btn btn-outline-dark btn-sm" data-page="prev">Previous</button>
                <button type="button" class="btn btn-outline-dark btn-sm" data-page="next">Next</button>
            </div>
        `;
        if (enablePagination) {
            table.parentElement?.appendChild(pagination);
        }

        const emptyRow = document.createElement("tr");
        emptyRow.dataset.emptyRow = "true";
        emptyRow.hidden = true;
        emptyRow.innerHTML = `<td colspan="${Math.max(headers.length, 1)}"><div class="empty-state"><div class="empty-state__icon"><i class="fa-regular fa-folder-open"></i></div><h3 class="empty-state__title">No matching rows</h3><p class="empty-state__message">Try changing your search or filters to see more results.</p></div></td>`;
        tbody.appendChild(emptyRow);

        const state = {
            sortIndex: -1,
            sortDir: "asc",
            query: "",
            page: 1,
            filters: {},
        };
        let isRendering = false;

        const filterableIndexes = [];
        headers.forEach((header, index) => {
            if (header.hasAttribute("data-filterable")) {
                filterableIndexes.push(index);
                const select = document.createElement("select");
                select.className = "form-control form-control-sm";
                select.dataset.filterIndex = String(index);
                const values = Array.from(new Set(Array.from(tbody.querySelectorAll("tr")).filter((row) => !row.dataset.emptyRow).map((row) => getCellValue(row, index)).filter(Boolean))).sort();
                select.innerHTML = [`<option value="">All ${header.textContent.trim()}</option>`, ...values.map((value) => `<option value="${value}">${value}</option>`)].join("");
                filterHost.appendChild(select);
                select.addEventListener("change", () => {
                    state.filters[index] = select.value;
                    state.page = 1;
                    render();
                });
            }

            header.tabIndex = 0;
            header.classList.add("is-sortable");
            header.addEventListener("click", () => {
                if (state.sortIndex === index) {
                    state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
                } else {
                    state.sortIndex = index;
                    state.sortDir = "asc";
                }
                render();
            });
            header.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    header.click();
                }
            });
        });

        const getFilteredRows = function () {
            let rows = Array.from(tbody.querySelectorAll("tr")).filter((row) => !row.dataset.emptyRow);
            if (state.query) {
                const query = state.query.toLowerCase();
                rows = rows.filter((row) => row.textContent.toLowerCase().includes(query));
            }
            filterableIndexes.forEach((index) => {
                const value = state.filters[index];
                if (value) {
                    rows = rows.filter((row) => getCellValue(row, index) === value);
                }
            });
            if (state.sortIndex > -1) {
                rows.sort((left, right) => {
                    const leftValue = getCellValue(left, state.sortIndex);
                    const rightValue = getCellValue(right, state.sortIndex);
                    const comparison = leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: "base" });
                    return state.sortDir === "asc" ? comparison : -comparison;
                });
            }
            return rows;
        };

        const updateHeaderState = function () {
            headers.forEach((header, index) => {
                header.dataset.sort = state.sortIndex === index ? state.sortDir : "";
                header.querySelector(".sort-indicator")?.remove();
                const indicator = document.createElement("span");
                indicator.className = "sort-indicator";
                indicator.textContent = state.sortIndex === index ? (state.sortDir === "asc" ? " ↑" : " ↓") : "";
                header.appendChild(indicator);
            });
        };

        const render = function () {
            if (isRendering) return;
            isRendering = true;
            const rows = getFilteredRows();
            const total = rows.length;
            const pageCount = enablePagination ? Math.max(1, Math.ceil(total / PAGE_SIZE)) : 1;
            state.page = Math.min(state.page, pageCount);
            const start = enablePagination ? (state.page - 1) * PAGE_SIZE : 0;
            const end = enablePagination ? start + PAGE_SIZE : rows.length;
            const visibleRows = rows.slice(start, end);

            const allRows = Array.from(tbody.querySelectorAll("tr")).filter((row) => !row.dataset.emptyRow);
            allRows.forEach((row) => row.hidden = true);
            visibleRows.forEach((row) => {
                row.hidden = false;
                tbody.appendChild(row);
            });

            emptyRow.hidden = visibleRows.length > 0;
            tbody.appendChild(emptyRow);

            const label = pagination.querySelector(".table-pagination__label");
            if (label) {
                label.textContent = `Showing ${total ? start + 1 : 0}-${Math.min(end, total)} of ${total}`;
            }
            pagination.querySelector('[data-page="prev"]')?.toggleAttribute("disabled", state.page <= 1);
            pagination.querySelector('[data-page="next"]')?.toggleAttribute("disabled", state.page >= pageCount);
            updateHeaderState();
            isRendering = false;
        };

        searchInput?.addEventListener("input", debounce((event) => {
            state.query = event.target.value.trim();
            state.page = 1;
            render();
        }, 200));

        pagination.addEventListener("click", (event) => {
            const button = event.target.closest("[data-page]");
            if (!button) return;
            if (button.dataset.page === "prev" && state.page > 1) state.page -= 1;
            if (button.dataset.page === "next") state.page += 1;
            render();
        });

        exportButton?.addEventListener("click", () => {
            const rows = getFilteredRows().filter((row) => !row.hidden);
            const csvRows = [
                headers.map((header) => csvEscape(header.textContent.replace(/[↑↓]/g, "").trim())).join(","),
                ...rows.map((row) => Array.from(row.children).map((cell) => csvEscape(cell.textContent.trim())).join(",")),
            ];
            const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `${exportName}.csv`;
            link.click();
            URL.revokeObjectURL(url);
        });

        if (table.dataset.loading === "true") {
            tbody.innerHTML = buildSkeletonRows(headers.length);
            window.setTimeout(() => {
                const allRows = Array.from(tbody.querySelectorAll("tr")).filter((row) => !row.dataset.emptyRow);
                tbody.innerHTML = "";
                allRows.forEach((row) => tbody.appendChild(row));
                tbody.appendChild(emptyRow);
                render();
            }, 300);
        } else {
            render();
        }

        const observer = new MutationObserver(() => {
            if (!isRendering) render();
        });
        observer.observe(tbody, { childList: true });
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("table[data-sortable-table]").forEach(initTable);
    });
}());
