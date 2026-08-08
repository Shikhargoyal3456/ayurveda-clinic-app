(function () {
    function byId(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const node = byId(id);
        if (node) node.textContent = value || "";
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function showToast(message, type) {
        if (window.showToast) {
            window.showToast(message, type || "info");
            return;
        }
        const toast = document.createElement("div");
        toast.className = `samhita-toast samhita-toast--${type || "info"}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        window.setTimeout(() => toast.remove(), 3000);
    }

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || "";
    }

    async function fetchJson(url, options) {
        const requestOptions = { ...(options || {}) };
        const method = (requestOptions.method || "GET").toUpperCase();
        if (method !== "GET") {
            requestOptions.headers = {
                "X-CSRF-Token": csrfToken(),
                ...(requestOptions.headers || {}),
            };
        }
        const response = await fetch(url, { credentials: "same-origin", ...requestOptions });
        const payload = await response.json();
        if (!response.ok || !payload.success) {
            throw new Error(payload.detail || payload.error || "Request failed");
        }
        return payload;
    }

    async function loadFeaturedTerm(term) {
        try {
            const payload = await fetchJson(`/api/ayurveda/terms/search?query=${encodeURIComponent(term)}`);
            if (payload.results?.length) {
                await loadTermDetail(payload.results[0].id);
            }
        } catch (error) {
            console.error("Error loading featured Ayurvedic term:", error);
        }
    }

    async function loadTermDetail(termId) {
        try {
            const payload = await fetchJson(`/api/ayurveda/terms/${termId}`);
            displayTermDetail(payload.term);
            window.currentAyurvedicTerm = payload.term;
            byId("featured-term")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } catch (error) {
            console.error("Error loading Ayurvedic term detail:", error);
            showToast(error.message || "Unable to load term details.", "error");
        }
    }

    function displayTermDetail(term) {
        setText("featured-term-name", term.term);
        setText("featured-term-sanskrit", term.sanskrit_term);
        setText("featured-term-category", term.category);
        setText("featured-term-ipa", term.ipa_pronunciation);
        setText("featured-term-guide", term.pronunciation_guide);
        setText("featured-term-meaning", term.meaning || "Not available.");
        setText("featured-term-clinical", term.clinical_significance || "Not available.");
        setText("featured-term-samhita", term.samhita || "Unknown");
        setText("featured-term-verse", [term.chapter, term.verse_number].filter(Boolean).join(" "));
        setText("featured-term-commentary-name", term.commentary_name || "None");
        setText("featured-term-verse-number", term.verse_number ? `Verse ${term.verse_number}` : "");
        setText("featured-term-sanskrit-verse", term.verse_sanskrit || term.verse_translation || "");
        setText("featured-term-commentary-translation", term.commentary_translation || term.verse_translation || "");
    }

    function toggleSearch() {
        const searchArea = byId("samhita-search-area");
        searchArea?.classList.toggle("hidden");
        if (searchArea && !searchArea.classList.contains("hidden")) {
            byId("term-search-input")?.focus();
        }
    }

    async function searchTerms() {
        const query = byId("term-search-input")?.value.trim() || "";
        const category = byId("category-filter")?.value || "";
        if (!query && !category) return;

        const params = new URLSearchParams();
        if (query) params.set("query", query);
        if (category) params.set("category", category);

        const container = byId("term-results-container");
        if (container) {
            container.innerHTML = '<div class="ayurveda-empty">Searching classical term index...</div>';
        }

        try {
            const payload = await fetchJson(`/api/ayurveda/terms/search?${params.toString()}`);
            if (!container) return;
            if (payload.results?.length) {
                container.innerHTML = payload.results.map((term) => `
                    <button class="ayurveda-result-card" type="button" data-term-id="${term.id}">
                        <span>
                            <strong>${escapeHtml(term.term)}</strong>
                            <small>${escapeHtml(term.sanskrit_term || "")}</small>
                            <em>${escapeHtml(term.meaning || "")}</em>
                        </span>
                        <span>
                            <small>${escapeHtml(term.category || "")}</small>
                            <b>${escapeHtml(term.samhita || "")}</b>
                        </span>
                    </button>
                `).join("");
                container.querySelectorAll("[data-term-id]").forEach((node) => {
                    node.addEventListener("click", () => loadTermDetail(node.getAttribute("data-term-id")));
                });
            } else {
                container.innerHTML = '<div class="ayurveda-empty">No terms found. Try another spelling or category.</div>';
            }
        } catch (error) {
            console.error("Ayurvedic term search error:", error);
            if (container) container.innerHTML = '<div class="ayurveda-empty">Search failed. Please try again.</div>';
        }
    }

    async function pronounceTerm() {
        const termName = byId("featured-term-name")?.textContent.trim();
        if (!termName) return;

        const button = byId("pronounce-btn");
        const originalLabel = button?.innerHTML;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Preparing';
        }

        try {
            await fetchJson("/api/ayurveda/terms/pronounce", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ term: termName }),
            });
            if ("speechSynthesis" in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(termName);
                utterance.lang = "hi-IN";
                utterance.rate = 0.7;
                utterance.pitch = 1;
                window.speechSynthesis.speak(utterance);
                showToast(`Listening to pronunciation of ${termName}.`, "info");
            } else {
                showToast("Speech synthesis is not available in this browser.", "warning");
            }
        } catch (error) {
            console.error("Pronunciation error:", error);
            showToast(error.message || "Failed to prepare pronunciation.", "error");
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = originalLabel || '<i class="fa-solid fa-volume-high"></i> Listen';
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!byId("featured-term")) return;
        byId("toggle-samhita-search")?.addEventListener("click", toggleSearch);
        byId("search-terms-btn")?.addEventListener("click", searchTerms);
        byId("term-search-input")?.addEventListener("keydown", function (event) {
            if (event.key === "Enter") searchTerms();
        });
        byId("category-filter")?.addEventListener("change", searchTerms);
        byId("pronounce-btn")?.addEventListener("click", pronounceTerm);
        loadFeaturedTerm("Vata");
    });
})();
