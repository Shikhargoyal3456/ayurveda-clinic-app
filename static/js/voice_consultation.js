class VoiceConsultation {
    constructor() {
        this.recognition = null;
        this.isRecording = false;
        this.transcript = "";
        this.sessionId = null;
        this.extractedData = {
            patient: { name: "", age: "", gender: "", phone: "" },
            symptoms: [],
            diagnosis: "",
            medicines: [],
            follow_up: "",
        };
        this.processingInterval = null;
        this.language = "en-IN";
        this.bindings();
    }

    bindings() {
        this.startButton = document.getElementById("voiceStartBtn");
        this.pauseButton = document.getElementById("voicePauseBtn");
        this.stopButton = document.getElementById("voiceStopBtn");
        this.transcriptNode = document.getElementById("liveTranscript");
        this.extractedNode = document.getElementById("liveExtracted");
        this.indicator = document.getElementById("recordingIndicator");
        this.patientName = document.getElementById("patientName");
        this.patientAge = document.getElementById("patientAge");
        this.patientGender = document.getElementById("patientGender");
        this.patientPhone = document.getElementById("patientPhone");
        this.caseSymptoms = document.getElementById("caseSymptoms");
        this.diagnosisField = document.getElementById("diagnosisField");
        this.medicineList = document.getElementById("medicineList");
        this.followUpField = document.getElementById("followUpField");
        this.transcriptStatus = document.getElementById("transcriptStatus");
        this.transcriptLanguage = document.getElementById("transcriptLanguage");
        this.saveButton = document.getElementById("saveConsultationBtn");
        this.shareButton = document.getElementById("shareConsultationBtn");
        this.resetButton = document.getElementById("resetConsultationBtn");
        this.summaryActionBtn = document.getElementById("summaryActionBtn");
        this.prescriptionActionBtn = document.getElementById("prescriptionActionBtn");
        this.followUpActionBtn = document.getElementById("followUpActionBtn");
        this.summaryActionText = document.getElementById("summaryActionText");
        this.prescriptionActionText = document.getElementById("prescriptionActionText");
        this.followUpActionText = document.getElementById("followUpActionText");
        this.startButton?.addEventListener("click", () => this.startRecording());
        this.pauseButton?.addEventListener("click", () => this.togglePause());
        this.stopButton?.addEventListener("click", () => this.stopRecording());
        this.saveButton?.addEventListener("click", () => this.saveDraft());
        this.shareButton?.addEventListener("click", () => this.shareDraft());
        this.resetButton?.addEventListener("click", () => this.resetDraft());
        this.summaryActionBtn?.addEventListener("click", () => this.applyAction("summary"));
        this.prescriptionActionBtn?.addEventListener("click", () => this.applyAction("prescription"));
        this.followUpActionBtn?.addEventListener("click", () => this.applyAction("follow_up"));
    }

    async startConsultationSession() {
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Starting consultation...";
        const response = await fetch("/api/consultation/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                doctor_id: window.VOICE_CONSULTATION_CONTEXT?.doctorId || 1,
                patient_id: window.VOICE_CONSULTATION_CONTEXT?.patientId || 0,
            }),
        });
        const payload = await response.json();
        this.sessionId = payload.session_id;
    }

    async startRecording() {
        if (this.isRecording) return;
        await this.startConsultationSession();
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            this.transcriptNode.textContent = "Speech recognition is not supported in this browser.";
            return;
        }
        this.recognition = new SpeechRecognition();
        this.recognition.lang = this.language;
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        if (this.transcriptLanguage) this.transcriptLanguage.textContent = this.language;
        this.recognition.onresult = (event) => {
            this.transcript = Array.from(event.results).map((result) => result[0].transcript).join(" ").trim();
            this.transcriptNode.textContent = this.transcript;
            this.autoFillFromTranscript(this.transcript);
            if (this.transcriptStatus) this.transcriptStatus.textContent = event.results[event.results.length - 1].isFinal ? "Processing transcript..." : "Listening...";
            if (event.results[event.results.length - 1].isFinal) {
                void this.processTranscript();
            }
        };
        this.recognition.onend = () => {
            if (this.isRecording) {
                try {
                    this.recognition.start();
                } catch (_error) {}
            }
        };
        this.recognition.start();
        this.isRecording = true;
        if (this.indicator) this.indicator.textContent = "⏺ RECORDING...";
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Listening...";
        this.processingInterval = window.setInterval(() => void this.processTranscript(), 5000);
    }

    togglePause() {
        if (!this.recognition) return;
        if (this.isRecording) {
            this.recognition.stop();
            this.isRecording = false;
            if (this.indicator) this.indicator.textContent = "⏸ PAUSED";
            if (this.transcriptStatus) this.transcriptStatus.textContent = "Paused";
        } else {
            this.recognition.start();
            this.isRecording = true;
            if (this.indicator) this.indicator.textContent = "⏺ RECORDING...";
            if (this.transcriptStatus) this.transcriptStatus.textContent = "Listening...";
        }
    }

    async processTranscript() {
        if (!this.transcript.trim()) return;
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Optimizing draft...";
        const response = await fetch("/api/voice/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transcript: this.transcript }),
        });
        const payload = await response.json();
        if (payload.success === false) return;
        this.extractedData = payload;
        this.autoFillForm(payload);
        this.applyActions(payload);
        if (this.extractedNode) this.extractedNode.textContent = JSON.stringify(payload, null, 2);
        this.scrollTranscriptToBottom();
    }

    autoFillForm(data) {
        const patient = data.patient || {};
        this.patientName && (this.patientName.value = patient.name || "");
        this.patientAge && (this.patientAge.value = patient.age || "");
        this.patientGender && (this.patientGender.value = patient.gender || "");
        this.patientPhone && (this.patientPhone.value = patient.phone || "");
        this.caseSymptoms && (this.caseSymptoms.innerHTML = this.renderChips(data.symptoms || [], "No symptoms captured yet."));
        this.diagnosisField && (this.diagnosisField.value = data.diagnosis || "");
        this.medicineList && (this.medicineList.innerHTML = this.renderChips(data.medicines || [], "No medicines suggested yet."));
        this.followUpField && (this.followUpField.value = data.follow_up || "");
    }

    autoFillFromTranscript(transcript) {
        const text = String(transcript || "").toLowerCase();
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Drafting patient details...";
        const ageMatch = text.match(/(\d{1,3})\s*(?:years?|yrs?)\b/);
        if (ageMatch && this.patientAge && !this.patientAge.value) this.patientAge.value = ageMatch[1];
        if (text.includes(" male")) this.patientGender && (this.patientGender.value = "Male");
        if (text.includes(" female")) this.patientGender && (this.patientGender.value = "Female");
        const nameMatch = text.match(/(?:patient is|name is)\s+([a-zA-Z\s]{2,40})/);
        if (nameMatch && this.patientName && !this.patientName.value) this.patientName.value = nameMatch[1].trim();
        const phoneMatch = text.match(/(?:phone|mobile)[:\s]*([0-9]{10})/);
        if (phoneMatch && this.patientPhone && !this.patientPhone.value) this.patientPhone.value = phoneMatch[1];
    }

    escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    renderChips(items, emptyLabel) {
        if (!items.length) {
            return `<span class="empty-state-inline">${emptyLabel}</span>`;
        }
        return items
            .map((item) => `<span class="chip">${this.escapeHtml(item)}</span>`)
            .join("");
    }

    applyActions(payload) {
        const summary = payload.actions?.summary || payload.summary || payload.diagnosis || "No summary yet.";
        const prescription = payload.actions?.prescription || (payload.medicines || []).join(", ") || "No prescription yet.";
        const followUp = payload.actions?.follow_up || payload.follow_up || "No follow-up yet.";
        if (this.summaryActionText) this.summaryActionText.textContent = summary;
        if (this.prescriptionActionText) this.prescriptionActionText.textContent = prescription;
        if (this.followUpActionText) this.followUpActionText.textContent = followUp;
    }

    async applyAction(actionName) {
        if (!this.transcript.trim()) return;
        if (this.transcriptStatus) this.transcriptStatus.textContent = `Drafting ${actionName}...`;
        const response = await fetch("/api/ai-chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: `${actionName}: ${this.transcript}` }),
        });
        const payload = await response.json();
        const text = payload?.actions?.[actionName] || payload?.response || "No recommendation available.";
        if (actionName === "summary") {
            if (this.summaryActionText) this.summaryActionText.textContent = text;
            this.populateSummaryAction(text);
        }
        if (actionName === "prescription") {
            if (this.prescriptionActionText) this.prescriptionActionText.textContent = text;
            this.populatePrescriptionAction(payload, text);
        }
        if (actionName === "follow_up") {
            if (this.followUpActionText) this.followUpActionText.textContent = text;
            this.populateFollowUpAction(text);
        }
        if (this.transcriptStatus) this.transcriptStatus.textContent = `${actionName} applied`;
    }

    populateSummaryAction(text) {
        this.diagnosisField && (this.diagnosisField.value = text);
        if (this.extractedData) {
            this.extractedData.diagnosis = text;
        }
    }

    populatePrescriptionAction(payload, fallbackText) {
        const medicineText = payload?.actions?.prescription || payload?.prescription || fallbackText;
        const medicines = Array.isArray(payload?.medicines) && payload.medicines.length ? payload.medicines : [medicineText];
        this.medicineList && (this.medicineList.innerHTML = this.renderChips(medicines, "No medicines suggested yet."));
        if (this.extractedData) {
            this.extractedData.medicines = medicines;
        }
    }

    populateFollowUpAction(text) {
        this.followUpField && (this.followUpField.value = text);
        if (this.extractedData) {
            this.extractedData.follow_up = text;
        }
    }

    scrollTranscriptToBottom() {
        if (this.transcriptNode) this.transcriptNode.scrollTop = this.transcriptNode.scrollHeight;
    }

    saveDraft() {
        const draft = {
            transcript: this.transcript,
            extractedData: this.extractedData,
        };
        window.localStorage.setItem("kash_voice_consultation_draft", JSON.stringify(draft));
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Draft saved";
    }

    shareDraft() {
        const text = [
            `Patient: ${this.patientName?.value || ""}`,
            `Age: ${this.patientAge?.value || ""}`,
            `Gender: ${this.patientGender?.value || ""}`,
            `Symptoms: ${(this.extractedData.symptoms || []).join(", ")}`,
            `Diagnosis: ${this.diagnosisField?.value || ""}`,
            `Medicines: ${(this.extractedData.medicines || []).join(", ")}`,
            `Follow-up: ${this.followUpField?.value || ""}`,
        ].join("\n");
        const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(text)}`;
        window.open(whatsappUrl, "_blank", "noopener,noreferrer");
    }

    fillAllFromActionBundle(payload) {
        if (!payload) return;
        if (payload.summary || payload.actions?.summary) this.populateSummaryAction(payload.actions?.summary || payload.summary);
        if (payload.medicines?.length || payload.actions?.prescription) this.populatePrescriptionAction(payload, payload.actions?.prescription || "");
        if (payload.follow_up || payload.actions?.follow_up) this.populateFollowUpAction(payload.actions?.follow_up || payload.follow_up);
    }

    resetDraft() {
        this.transcript = "";
        this.extractedData = {
            patient: { name: "", age: "", gender: "", phone: "" },
            symptoms: [],
            diagnosis: "",
            medicines: [],
            follow_up: "",
        };
        this.transcriptNode && (this.transcriptNode.textContent = "Waiting to start...");
        this.extractedNode && (this.extractedNode.textContent = "{}");
        this.patientName && (this.patientName.value = "");
        this.patientAge && (this.patientAge.value = "");
        this.patientGender && (this.patientGender.value = "");
        this.patientPhone && (this.patientPhone.value = "");
        this.caseSymptoms && (this.caseSymptoms.innerHTML = '<span class="empty-state-inline">No symptoms captured yet.</span>');
        this.diagnosisField && (this.diagnosisField.value = "");
        this.medicineList && (this.medicineList.innerHTML = '<span class="empty-state-inline">No medicines suggested yet.</span>');
        this.followUpField && (this.followUpField.value = "");
        if (this.extractedData) {
            this.extractedData.diagnosis = "";
            this.extractedData.medicines = [];
            this.extractedData.follow_up = "";
        }
        if (this.summaryActionText) this.summaryActionText.textContent = "No summary yet.";
        if (this.prescriptionActionText) this.prescriptionActionText.textContent = "No prescription yet.";
        if (this.followUpActionText) this.followUpActionText.textContent = "No follow-up yet.";
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Idle";
        window.localStorage.removeItem("kash_voice_consultation_draft");
    }

    async stopRecording() {
        if (this.recognition) this.recognition.stop();
        this.isRecording = false;
        if (this.processingInterval) window.clearInterval(this.processingInterval);
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Saving transcript...";
        if (this.sessionId) {
            await fetch("/api/consultation/stop", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: this.sessionId }),
            });
        }
        if (this.indicator) this.indicator.textContent = "⏹ STOPPED";
        if (this.transcriptStatus) this.transcriptStatus.textContent = "Stopped";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.voiceConsultation = new VoiceConsultation();
    const draft = window.localStorage.getItem("kash_voice_consultation_draft");
    if (draft) {
        try {
            const parsed = JSON.parse(draft);
            if (parsed.transcript) {
                window.voiceConsultation.transcript = parsed.transcript;
                window.voiceConsultation.transcriptNode.textContent = parsed.transcript;
            }
            if (parsed.extractedData) {
                window.voiceConsultation.extractedData = parsed.extractedData;
                window.voiceConsultation.autoFillForm(parsed.extractedData);
                window.voiceConsultation.extractedNode.textContent = JSON.stringify(parsed.extractedData, null, 2);
                window.voiceConsultation.fillAllFromActionBundle(parsed.extractedData);
            }
            if (window.voiceConsultation.transcriptStatus) window.voiceConsultation.transcriptStatus.textContent = "Draft restored";
        } catch (_error) {}
    }
});
