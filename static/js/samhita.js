(function () {
    function textFrom(id) {
        return (document.getElementById(id)?.innerText || document.getElementById(id)?.value || "").trim();
    }

    function valueFrom(id, fallback = "") {
        return (document.getElementById(id)?.value || fallback).trim();
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function markdownToHtml(text) {
        return escapeHtml(text || "")
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/^[-•*]\s(.*)$/gm, "• $1")
            .replace(/\n/g, "<br>");
    }

    function sectionItems(text, mode) {
        const lines = String(text || "").split("\n");
        const items = [];
        let active = false;
        for (const line of lines) {
            const lower = line.toLowerCase();
            if (lower.includes(mode) || lower.includes(mode === "favor" ? "pathya" : "apathya")) {
                active = true;
                continue;
            }
            if (active && /^[-•*]\s/.test(line.trim())) {
                items.push(line.trim().replace(/^[-•*]\s/, ""));
                continue;
            }
            if (active && line.trim() === "" && items.length) break;
        }
        return items.length ? items : ["No specific recommendations listed."];
    }

    function mealPlan(text) {
        const lines = String(text || "").split("\n");
        const rows = [];
        let active = false;
        for (const line of lines) {
            const lower = line.toLowerCase();
            if (lower.includes("meal plan") || lower.includes("sample meal")) {
                active = true;
                continue;
            }
            if (active && line.trim()) rows.push(line.trim());
            if (active && !line.trim() && rows.length) break;
        }
        return rows.length ? rows.map(escapeHtml).join("<br>") : "Sample meal plan not specified.";
    }

    function showToast(message, type) {
        if (window.showToast) {
            window.showToast(message, type);
            return;
        }
        const toast = document.createElement("div");
        toast.className = `samhita-toast samhita-toast--${type || "info"}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        window.setTimeout(() => toast.remove(), 4000);
    }

    function displayResults(analysis) {
        const diet = analysis.dietary_recommendations || "";
        const targets = {
            "dosha-analysis": markdownToHtml(analysis.dosha_analysis || ""),
            "diet-favor": sectionItems(diet, "favor").map((item) => `• ${escapeHtml(item)}`).join("<br>"),
            "diet-avoid": sectionItems(diet, "avoid").map((item) => `• ${escapeHtml(item)}`).join("<br>"),
            "meal-plan": mealPlan(diet),
            "herbal-formulations": markdownToHtml(analysis.herbal_formulations || ""),
            "lifestyle-regimen": markdownToHtml(analysis.lifestyle_regimen || ""),
            "treatment-recommendations": markdownToHtml(analysis.treatment_recommendations || ""),
            "classical-reference": markdownToHtml(analysis.classical_reference || ""),
        };
        Object.entries(targets).forEach(([id, html]) => {
            const node = document.getElementById(id);
            if (node) node.innerHTML = html || "No details returned.";
        });
    }

    async function performSamhitaAnalysis() {
        const transcript = textFrom("transcriptDisplay").replace("Waiting to start...", "").trim();
        const symptoms = valueFrom("symptoms", transcript) || transcript;
        if (!symptoms) {
            showToast("Please record or enter symptoms first.", "warning");
            return;
        }

        const analyzeBtn = document.getElementById("analyze-samhita-btn");
        const loadingDiv = document.getElementById("samhita-loading");
        const resultsDiv = document.getElementById("samhita-results");
        const originalLabel = analyzeBtn?.innerHTML;

        if (analyzeBtn) {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
        }
        loadingDiv?.classList.remove("hidden");
        resultsDiv?.classList.add("hidden");

        try {
            const response = await fetch("/api/samhita/analyze", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || "",
                },
                body: JSON.stringify({
                    patient_id: valueFrom("patient-id") || null,
                    consultation_id: valueFrom("consultation-id") || null,
                    symptoms,
                    age: valueFrom("patientAge") || valueFrom("patient-age") || null,
                    gender: valueFrom("patientGender") || valueFrom("patient-gender") || "",
                    prakriti: valueFrom("patient-prakriti", "Unknown"),
                    agni: valueFrom("patient-agni", "Unknown"),
                    history: valueFrom("patient-history", "None"),
                }),
            });
            const payload = await response.json();
            if (!response.ok || !payload.success) {
                throw new Error(payload.detail || payload.error || "Analysis failed");
            }
            displayResults(payload.analysis || {});
            resultsDiv?.classList.remove("hidden");
            showToast("Samhita analysis complete.", "success");
        } catch (error) {
            console.error("Samhita analysis error:", error);
            showToast(error.message || "Failed to analyze. Please try again.", "error");
        } finally {
            if (analyzeBtn) {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = originalLabel || '<i class="fas fa-sparkles"></i> Analyze with Samhita';
            }
            loadingDiv?.classList.add("hidden");
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("analyze-samhita-btn")?.addEventListener("click", performSamhitaAnalysis);
    });
})();
