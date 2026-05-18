const printPrescriptionButton = document.getElementById("print-prescription-btn");

if (printPrescriptionButton) {
    printPrescriptionButton.addEventListener("click", () => {
        window.print();
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function renderList(items) {
    return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderMedicineInfo(card, info) {
    const host = card.querySelector(".medicine-ai-content");
    const loading = card.querySelector(".loading-ai");
    if (loading) {
        loading.remove();
    }
    if (!host) {
        return;
    }
    host.classList.remove("d-none");
    host.innerHTML = `
        <div class="ai-generated-content">
            <p class="mb-3 text-muted"><small>🤖 AI-generated with ${escapeHtml(info.ai_confidence_percent)}% confidence</small></p>

            <section class="mb-3">
                <p class="eyebrow mb-2">Benefits</p>
                <ul class="mb-0">${renderList(info.benefits)}</ul>
            </section>

            <section class="mb-3">
                <p class="eyebrow mb-2">Side Effects</p>
                <div class="mb-2">
                    <strong>Common:</strong>
                    <ul class="mb-0">${renderList(info.side_effects.common)}</ul>
                </div>
                <div class="mb-2">
                    <strong>Serious (rare):</strong>
                    <ul class="mb-0">${renderList(info.side_effects.serious)}</ul>
                </div>
                <p class="mb-0"><strong>What to do:</strong> ${escapeHtml(info.side_effects.management)}</p>
            </section>

            <section class="mb-3">
                <p class="eyebrow mb-2">Alternative Medicines</p>
                <div class="stack-list">
                    ${info.alternatives.map((alt) => `
                        <div class="stack-item">
                            <strong>${escapeHtml(alt.name)}</strong>
                            <p class="mb-1">${escapeHtml(alt.why_recommended)}</p>
                            <span class="text-muted"><small>💰 ${escapeHtml(alt.estimated_savings)}</small></span>
                        </div>
                    `).join("")}
                </div>
            </section>

            <section class="mb-3">
                <p class="eyebrow mb-2">Dosage Information</p>
                <p class="mb-2"><strong>Standard dosage:</strong> ${escapeHtml(info.dosage.standard)}</p>
                <p class="mb-2"><strong>Maximum daily:</strong> ${escapeHtml(info.dosage.max_daily)}</p>
                <p class="mb-2"><strong>When to take:</strong> ${escapeHtml(info.dosage.timing)}</p>
                <p class="mb-0"><strong>With food?</strong> ${escapeHtml(info.dosage.food_instruction)}</p>
            </section>

            <section class="mb-3">
                <p class="eyebrow mb-2">Precautions</p>
                <ul class="mb-0">${renderList(info.precautions)}</ul>
            </section>

            <section class="mb-3">
                <p class="eyebrow mb-2">Drug Interactions</p>
                <ul class="mb-0">${renderList(info.interactions)}</ul>
            </section>

            <section class="mb-3">
                <p class="eyebrow mb-2">Missed a dose?</p>
                <p class="mb-0">${escapeHtml(info.what_to_do_if_missed)}</p>
            </section>

            <section>
                <p class="eyebrow mb-2">When to consult a doctor</p>
                <p class="mb-0">${escapeHtml(info.when_to_consult_doctor)}</p>
            </section>
        </div>
    `;
}

async function loadPureAIMedicineInfo() {
    const cards = document.querySelectorAll(".medicine-detail-card");
    if (cards.length === 0) {
        return;
    }

    const csrfToken = window.prescriptionDetailConfig?.csrfToken || "";

    for (const card of cards) {
        const medicineName = card.dataset.medicineName || "";
        const diagnosis = card.dataset.diagnosis || "";
        const symptoms = card.dataset.symptoms || "";
        const age = card.dataset.age || "";
        const container = card.querySelector(".loading-ai");

        try {
            const response = await fetch("/api/ai/medicine-info/pure", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({
                    medicine_name: medicineName,
                    diagnosis,
                    symptoms,
                    age,
                }),
            });

            if (response.status === 503) {
                if (container) {
                    container.innerHTML = '<p class="mb-0 text-danger">🤖 AI service is currently unavailable. Please retry.</p>';
                }
                continue;
            }

            const result = await response.json();
            if (result.success && result.source === "ai" && result.data) {
                renderMedicineInfo(card, result.data);
            }
        } catch (_error) {
            if (container) {
                container.innerHTML = '<p class="mb-0 text-danger">⚠️ Could not load AI-generated information.</p>';
            }
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadPureAIMedicineInfo();
});
