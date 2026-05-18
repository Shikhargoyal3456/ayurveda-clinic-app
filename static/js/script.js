async function fetchWithTimeout(url, options = {}, timeoutMs = 25000) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

    try {
        return await fetch(url, { ...options, signal: controller.signal });
    } finally {
        window.clearTimeout(timeoutId);
    }
}

window.__kashScriptInitialized = window.__kashScriptInitialized || false;

function getMockNotifications() {
    return {
        notifications: [
            {
                id: 1,
                message: "Your order #AYU123 has been delivered",
                unread: true,
                link: "/orders/tracking/123",
                icon: "📦",
                timestamp: "5 min ago"
            },
            {
                id: 2,
                message: "Prescription refill reminder: Paracetamol",
                unread: true,
                link: "/prescription/refill",
                icon: "💊",
                timestamp: "2 hours ago"
            }
        ]
    };
}

async function fetchNotifications() {
    try {
        const response = await fetch("/api/v1/notifications");
        if (!response.ok) {
            throw new Error("Notifications endpoint unavailable");
        }
        return await response.json();
    } catch (error) {
        return getMockNotifications();
    }
}

window.fetchNotifications = fetchNotifications;

async function analyzeSymptoms() {
    const result = document.getElementById("result");
    const form = document.getElementById("ai-analyzer-form");
    const symptoms = document.getElementById("symptoms").value.trim();
    const mode = document.getElementById("aiModeInput")?.value || "samhita";
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const analyzeButton = document.getElementById("analyze-button");
    const loadingIndicator = document.getElementById("analysis-loading");

    if (!symptoms) {
        result.textContent = "Enter symptoms before running the analyzer.";
        return;
    }

    result.textContent = "Analyzing symptoms against the indexed samhita knowledge...";
    if (loadingIndicator) {
        loadingIndicator.classList.remove("d-none");
    }
    if (analyzeButton instanceof HTMLButtonElement) {
        analyzeButton.disabled = true;
        analyzeButton.dataset.originalText = analyzeButton.textContent || "Analyze with AI";
        analyzeButton.textContent = analyzeButton.dataset.loadingText || "Analyzing...";
    }

    try {
        const response = await fetchWithTimeout(form.action, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRF-Token": csrfToken
            },
            body: JSON.stringify({ symptoms, mode })
        }, 30000);
        const data = await response.json();
        if (!response.ok) {
            result.textContent = data.detail || "Unable to analyze symptoms.";
            return;
        }
        renderAiResult(data);
    } catch (error) {
        console.error(error);
        result.textContent = "Error connecting to the AI service.";
    } finally {
        if (loadingIndicator) {
            loadingIndicator.classList.add("d-none");
        }
        if (analyzeButton instanceof HTMLButtonElement) {
            analyzeButton.disabled = false;
            analyzeButton.textContent = analyzeButton.dataset.originalText || "Analyze with AI";
        }
    }
}

function renderAiResult(data) {
    const result = document.getElementById("result");
    if (!result) {
        return;
    }

    result.innerHTML = "";

    const answerCard = document.createElement("div");
    answerCard.className = "result-block";

    const answerLabel = document.createElement("h3");
    answerLabel.className = "result-title";
    const currentMode = String(data.mode || "samhita").replace(/_/g, " ");
    answerLabel.textContent = `AI Clinical Draft (${currentMode})`;

    const answerText = document.createElement("pre");
    answerText.textContent = data.answer || "No answer returned.";

    answerCard.append(answerLabel, answerText);
    result.appendChild(answerCard);

    if (data.sources && data.sources.length) {
        const sourceCard = document.createElement("div");
        sourceCard.className = "result-block";

        const sourceLabel = document.createElement("h3");
        sourceLabel.className = "result-title";
        sourceLabel.textContent = "Source References";

        const sourceList = document.createElement("ul");
        sourceList.className = "result-list";
        data.sources.forEach((source) => {
            const item = document.createElement("li");
            item.textContent = source;
            sourceList.appendChild(item);
        });

        sourceCard.append(sourceLabel, sourceList);
        result.appendChild(sourceCard);
    }

    if (data.context_passages && data.context_passages.length) {
        const contextCard = document.createElement("div");
        contextCard.className = "result-block";

        const contextLabel = document.createElement("h3");
        contextLabel.className = "result-title";
        contextLabel.textContent = "Retrieved Chunks";

        const contextList = document.createElement("ul");
        contextList.className = "result-list";
        data.context_passages.forEach((passage) => {
            const item = document.createElement("li");
            item.textContent = `${passage.source_file} (${passage.chunk_id}, score ${passage.score})`;
            contextList.appendChild(item);
        });

        contextCard.append(contextLabel, contextList);
        result.appendChild(contextCard);
    }
}

function initAiAnalyzer() {
    const analyzerForm = document.getElementById("ai-analyzer-form");
    if (analyzerForm) {
        analyzerForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            await analyzeSymptoms();
        });
    }

    const symptomField = document.getElementById("symptoms");
    const demoButtons = document.querySelectorAll("#ai-demo-chips [data-demo-symptoms]");
    demoButtons.forEach((button) => {
        button.addEventListener("click", () => {
            if (symptomField) {
                symptomField.value = button.getAttribute("data-demo-symptoms") || "";
                symptomField.focus();
            }
        });
    });

    const bestDemoButton = document.getElementById("load-demo-copy");
    if (bestDemoButton) {
        bestDemoButton.addEventListener("click", () => {
            if (symptomField) {
                symptomField.value = "Burning sensation after meals, sour belching, irregular appetite, headache, disturbed sleep, stress-related digestive discomfort.";
                symptomField.focus();
            }
        });
    }

    const rebuildButton = document.getElementById("rebuild-knowledge-button");
    if (rebuildButton) {
        rebuildButton.addEventListener("click", rebuildKnowledgeBase);
    }
}

function initScheduleDemoChips() {
    const scheduleDateField = document.getElementById("appointment-date");
    const scheduleTimeField = document.getElementById("appointment-time");
    const scheduleReasonField = document.getElementById("appointment-reason");
    const buttons = document.querySelectorAll("#schedule-demo-chips [data-demo-date-offset]");

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            const offset = Number(button.getAttribute("data-demo-date-offset") || "0");
            const targetDate = new Date();
            targetDate.setDate(targetDate.getDate() + offset);
            const localDate = new Date(targetDate.getTime() - targetDate.getTimezoneOffset() * 60000)
                .toISOString()
                .slice(0, 10);

            if (scheduleDateField) {
                scheduleDateField.value = localDate;
            }
            if (scheduleTimeField) {
                scheduleTimeField.value = button.getAttribute("data-demo-time") || "";
            }
            if (scheduleReasonField) {
                scheduleReasonField.value = button.getAttribute("data-demo-reason") || "";
            }
        });
    });
}

async function rebuildKnowledgeBase() {
    const result = document.getElementById("result");
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    result.textContent = "Rebuilding PDF knowledge index...";

    try {
        const response = await fetchWithTimeout("/api/ai/rebuild-knowledge", {
            method: "POST",
            headers: { "X-CSRF-Token": csrfToken }
        }, 10000);
        const data = await response.json();
        if (!response.ok) {
            result.textContent = data.detail || "Knowledge rebuild failed.";
            return;
        }
        result.textContent = data.message || "Knowledge rebuild started.";
    } catch (error) {
        console.error(error);
        result.textContent = "Could not rebuild the knowledge base.";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (window.__kashScriptInitialized) {
        return;
    }
    window.__kashScriptInitialized = true;
    initAiAnalyzer();
    initScheduleDemoChips();

    if ("IntersectionObserver" in window) {
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("revealed");
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1, rootMargin: "0px 0px -40px 0px" });

        document.querySelectorAll(".reveal-on-scroll").forEach((element) => {
            revealObserver.observe(element);
        });
    } else {
        document.querySelectorAll(".reveal-on-scroll").forEach((element) => {
            element.classList.add("revealed");
        });
    }

    const progress = document.getElementById("page-progress");
    if (progress) {
        document.addEventListener("click", (event) => {
            const link = event.target.closest("a[href]");
            if (!link) return;
            const href = link.getAttribute("href");
            if (!href) return;
            const currentUrl = new URL(window.location.href);
            const isNonNavigationalScheme = /^(#|javascript:|mailto:|tel:)/i.test(href);
            const targetUrl = !isNonNavigationalScheme ? new URL(href, window.location.href) : null;
            const isSamePage = targetUrl && targetUrl.pathname === currentUrl.pathname && targetUrl.search === currentUrl.search;
            const isExternal = targetUrl && targetUrl.origin !== window.location.origin;
            if (
                isNonNavigationalScheme ||
                link.hasAttribute("download") ||
                link.target === "_blank" ||
                isSamePage ||
                isExternal
            ) {
                return;
            }
            progress.style.width = "0%";
            progress.style.opacity = "";
            progress.classList.add("active");
            requestAnimationFrame(() => {
                requestAnimationFrame(() => { progress.style.width = "70%"; });
            });
        });

        window.addEventListener("pageshow", () => {
            progress.style.width = "100%";
            window.setTimeout(() => {
                progress.style.opacity = "0";
                window.setTimeout(() => {
                    progress.style.width = "0%";
                    progress.style.opacity = "";
                }, 300);
            }, 200);
        });
    }

    document.querySelectorAll('a[href^="/"]').forEach((link) => {
        if (link.dataset.transitionBound === "true") return;
        link.dataset.transitionBound = "true";
        if (link.target || link.hasAttribute("download")) return;
        link.addEventListener("click", (event) => {
            const href = link.getAttribute("href");
            if (!href || href === window.location.pathname || href.startsWith("#")) return;
            event.preventDefault();
            document.body.style.transition = "opacity 0.2s ease";
            document.body.style.opacity = "0";
            window.setTimeout(() => {
                window.location.href = href;
            }, 200);
        });
    });

    window.addEventListener("kash:notification", (event) => {
        const bell = document.getElementById("notif-bell");
        if (!bell) return;
        const detail = event.detail || {};
        const notifEvent = new CustomEvent("kash:notification-received", { detail });
        window.dispatchEvent(notifEvent);
    });
});
