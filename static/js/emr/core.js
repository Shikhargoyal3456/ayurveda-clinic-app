class EMRSystem {
    constructor() {
        this.currentPatient = null;
        this.currentConsultation = null;
    }

    async loadPatient(id) {
        const response = await fetch(`/api/patients/${id}`);
        const payload = await response.json();
        if (payload.success) {
            this.currentPatient = payload.patient;
        }
        return payload;
    }

    async saveConsultation(systemType, data) {
        const response = await fetch(`/api/consultations/${systemType}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        const payload = await response.json();
        if (payload.success) {
            this.currentConsultation = payload.consultation;
            if (window.showToast) window.showToast(`${systemType} consultation saved`);
        }
        return payload;
    }

    async checkInteractions(drugs, herbs) {
        const params = new URLSearchParams();
        drugs.forEach((drug) => params.append("drugs", drug));
        herbs.forEach((herb) => params.append("herbs", herb));
        const response = await fetch(`/api/interactions/check?${params.toString()}`);
        return response.json();
    }

    async generateICD11Code(symptoms) {
        const response = await fetch(`/api/icd11/search?q=${encodeURIComponent(symptoms)}`);
        return response.json();
    }

    calculatePrakriti(answers) {
        const scores = { vata: 0, pitta: 0, kapha: 0 };
        answers.forEach((answer) => {
            if (Object.prototype.hasOwnProperty.call(scores, answer)) {
                scores[answer] += 1;
            }
        });
        const total = Math.max(1, scores.vata + scores.pitta + scores.kapha);
        return {
            vata: Math.round((scores.vata / total) * 100),
            pitta: Math.round((scores.pitta / total) * 100),
            kapha: Math.round((scores.kapha / total) * 100),
        };
    }
}

window.EMR = new EMRSystem();

document.addEventListener("DOMContentLoaded", () => {
    const modernSaveButton = document.querySelector("[data-save-modern-consultation]");
    if (modernSaveButton) {
        modernSaveButton.addEventListener("click", async () => {
            const originalText = modernSaveButton.innerHTML;
            modernSaveButton.disabled = true;
            modernSaveButton.innerHTML = '<span class="fa-solid fa-spinner fa-spin" aria-hidden="true"></span> Processing...';
            const consultationShell = document.querySelector(".consultation-step-shell");
            const patientId = Number(consultationShell?.dataset.patientId || 0);
            if (!patientId) {
                modernSaveButton.disabled = false;
                modernSaveButton.innerHTML = originalText;
                return;
            }
            const payload = {
                patient_id: patientId,
                status: "finalized",
                title: "Modern consultation",
                notes: {
                    subjective: document.querySelector(".soap-subjective")?.value || "",
                    objective: document.querySelector(".soap-objective")?.value || "",
                    assessment: document.querySelector(".soap-assessment")?.value || "",
                    plan: document.querySelector(".soap-plan")?.value || "",
                },
                vitals: {
                    bp_systolic: document.querySelector(".bp-systolic")?.value || "",
                    bp_diastolic: document.querySelector(".bp-diastolic")?.value || "",
                    heart_rate: document.querySelector(".pulse")?.value || "",
                },
                chief_complaint: document.querySelector(".soap-subjective")?.value || "",
                treatment_plan: document.querySelector(".soap-plan")?.value || "",
            };
            try {
                await window.EMR.saveConsultation("modern", payload);
            } finally {
                modernSaveButton.disabled = false;
                modernSaveButton.innerHTML = originalText;
            }
        });
    }

    document.querySelectorAll(".view-patient").forEach((element) => {
        element.addEventListener("click", () => {
            const patientId = Number(element.dataset.patientId || 0);
            if (!patientId) return;
            fetch("/api/audit/log", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "view",
                    record_type: "patient",
                    record_id: patientId,
                    patient_id: patientId,
                }),
            }).catch(() => null);
        });
    });
});
