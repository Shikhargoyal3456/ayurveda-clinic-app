async function fetchWithTimeout(url, options = {}, timeoutMs = 25000) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

    try {
        return await fetch(url, { ...options, signal: controller.signal });
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function analyzeSymptoms() {
    const result = document.getElementById("result");
    const form = document.getElementById("ai-analyzer-form");
    const symptoms = document.getElementById("symptoms").value.trim();
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

    if (!symptoms) {
        result.textContent = "Enter symptoms before running the analyzer.";
        return;
    }

    result.textContent = "Analyzing symptoms against the indexed samhita knowledge...";

    try {
        const response = await fetchWithTimeout(form.action, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRF-Token": csrfToken
            },
            body: JSON.stringify({ symptoms })
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
    answerLabel.textContent = "AI Clinical Draft";

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
    initAiAnalyzer();
    initScheduleDemoChips();
});
