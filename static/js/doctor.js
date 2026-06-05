(function () {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
    const MAX_HISTORY_MESSAGES = 100;
    const AUTO_SUBMIT_DELAY = 1500;
    const REQUEST_RETRY_LIMIT = 2;
    const DOCTOR_UNAVAILABLE_MESSAGE = "Dr. Kash is temporarily unavailable. Please try again in a moment.";
    const HINDI_VOICE_WARNING = "Hindi voice not available on this device. Text replies will still work normally.";
    const DISCLAIMER_PATTERN = /(?:⚠️\s*)?I am an AI assistant, not a licensed doctor\.[\s\S]*/i;
    const DIAGNOSIS_PATTERN = /\|\|\|DIAGNOSIS\|\|\|(.*?)\|\|\|END\|\|\|/s;
    const PATIENT_CONTEXT_STORAGE_KEY = "doctorPatientContext";

    const UI_TEXT = {
        en: {
            htmlLang: "en",
            micTooltip: "Speak",
            placeholder: "Describe your symptoms here...",
            send: "Send",
            restart: "Restart",
            endSession: "End Session",
            start: "Start Consultation",
            welcome: "Start a bilingual consultation with streaming replies, voice input, and calm spoken guidance from Dr. Kash.",
            support: "Best on Chrome, Edge, and Safari. Text chat still works if voice or camera is unavailable.",
            contextTitle: "Before we start, a few questions for better advice",
            contextHint: "These details help Dr. Kash tailor the guidance to age, allergies, weight, and current medicines.",
            agePlaceholder: "Your age (years)",
            weightPlaceholder: "Weight (kg, optional)",
            allergiesPlaceholder: "Any allergies? (e.g. penicillin, nuts)",
            medicationsPlaceholder: "Current medications?",
            contextStart: "Start Consultation",
            contextSkip: "Skip for now",
            liveReady: "Ready to begin.",
            inputHint: "Type or speak your symptoms. Dr. Kash responds in your selected language.",
            lastReply: "Doctor's latest reply",
            diagnosisTitle: "Preliminary Assessment",
            diagnosisHint: "These possible conditions appear only after enough context is collected.",
            summaryTitle: "Consultation Summary",
            summaryCopy: "Copy Summary",
            summaryShare: "Share on WhatsApp",
            summaryClose: "Close",
            summaryGenerate: "Generate Summary",
            summaryLater: "Later",
            summaryOffer: "Would you like a consultation summary before we close the session?",
            thinking: "Dr. Kash is thinking...",
            typing: "Dr. Kash is typing",
            listening: "Listening...",
            listeningHint: "Speak naturally. I will send your message after a short pause.",
            live: "Consultation live.",
            liveHint: "Tap the mic or type your next message.",
            restartStatus: "Restarting consultation...",
            endedStatus: "Session ended.",
            startGreeting: "Hello doctor, I need help.",
            voiceUnsupported: "Voice recognition is not supported here. Please continue with text.",
            micNoSpeech: "Didn't catch that, please try again",
            voiceNetwork: "Voice not available, please type",
            cameraUnavailable: "Camera preview is unavailable right now. Consultation will continue with text and voice when possible.",
            summaryEmpty: "No consultation summary is available yet.",
            retry: "Retry",
            liveLabel: "LIVE",
            endedLabel: "ENDED",
            insecureMedia: "Microphone and camera need HTTPS or localhost in Chrome. Text chat, summary, and audio playback will still work on this HTTP link.",
            copySuccess: "Summary copied.",
            copyFallback: "Press Ctrl+C to copy the summary.",
            shareBlocked: "WhatsApp popup was blocked. Opening share in this tab.",
        },
        hi: {
            htmlLang: "hi",
            micTooltip: "बोलें",
            placeholder: "अपने लक्षण यहाँ लिखें...",
            send: "भेजें",
            restart: "पुनः आरंभ करें",
            endSession: "सत्र समाप्त करें",
            start: "परामर्श शुरू करें",
            welcome: "स्ट्रीमिंग जवाब, वॉइस इनपुट और Dr. Kash की शांत आवाज़ के साथ द्विभाषी परामर्श शुरू करें।",
            support: "Chrome, Edge और Safari पर सबसे अच्छा अनुभव मिलता है। वॉइस या कैमरा न हो तब भी टेक्स्ट चैट चलेगी।",
            contextTitle: "शुरू करने से पहले बेहतर सलाह के लिए कुछ छोटी जानकारी",
            contextHint: "इन details से Dr. Kash उम्र, allergy, weight और current medicines के हिसाब से जवाब दे पाएंगे।",
            agePlaceholder: "आपकी उम्र (वर्ष)",
            weightPlaceholder: "वज़न (kg, optional)",
            allergiesPlaceholder: "कोई allergy? (जैसे penicillin, nuts)",
            medicationsPlaceholder: "अभी कौन सी medicines ले रहे हैं?",
            contextStart: "परामर्श शुरू करें",
            contextSkip: "अभी छोड़ें",
            liveReady: "शुरू करने के लिए तैयार।",
            inputHint: "अपने लक्षण टाइप करें या बोलें। Dr. Kash चुनी हुई भाषा में जवाब देंगे।",
            lastReply: "डॉक्टर का नया जवाब",
            diagnosisTitle: "प्रारंभिक आकलन",
            diagnosisHint: "पर्याप्त जानकारी मिलने के बाद ही ये संभावित स्थितियां दिखाई जाती हैं।",
            summaryTitle: "परामर्श सारांश",
            summaryCopy: "सारांश कॉपी करें",
            summaryShare: "WhatsApp पर साझा करें",
            summaryClose: "बंद करें",
            summaryGenerate: "सारांश बनाएँ",
            summaryLater: "बाद में",
            summaryOffer: "सत्र समाप्त करने से पहले क्या आप परामर्श सारांश चाहते हैं?",
            thinking: "Dr. Kash सोच रहे हैं...",
            typing: "Dr. Kash जवाब लिख रहे हैं",
            listening: "सुन रहा हूँ...",
            listeningHint: "स्वाभाविक रूप से बोलिए। थोड़े विराम के बाद आपका संदेश भेज दिया जाएगा।",
            live: "परामर्श चालू है।",
            liveHint: "माइक दबाएँ या अपना अगला संदेश टाइप करें।",
            restartStatus: "परामर्श फिर से शुरू हो रहा है...",
            endedStatus: "सत्र समाप्त हो गया।",
            startGreeting: "नमस्ते डॉक्टर, मुझे मदद चाहिए।",
            voiceUnsupported: "इस ब्राउज़र में voice recognition उपलब्ध नहीं है। कृपया टेक्स्ट से जारी रखें।",
            micNoSpeech: "आवाज़ साफ़ नहीं मिली, कृपया फिर से कोशिश करें",
            voiceNetwork: "वॉइस उपलब्ध नहीं है, कृपया टाइप करें",
            cameraUnavailable: "कैमरा preview अभी उपलब्ध नहीं है। परामर्श text और voice के साथ जारी रहेगा।",
            summaryEmpty: "अभी कोई परामर्श सारांश उपलब्ध नहीं है।",
            retry: "फिर से कोशिश करें",
            liveLabel: "LIVE",
            endedLabel: "ENDED",
            insecureMedia: "Chrome में microphone और camera के लिए HTTPS या localhost चाहिए। इस HTTP लिंक पर text chat, summary और audio playback फिर भी काम करेंगे।",
            copySuccess: "सारांश कॉपी हो गया।",
            copyFallback: "सारांश कॉपी करने के लिए Ctrl+C दबाएँ।",
            shareBlocked: "WhatsApp popup block हो गया। इसे इसी tab में खोला जा रहा है।",
        },
    };

    class AIDoctorApp {
        constructor() {
            this.elements = {
                startScreen: document.getElementById("startScreen"),
                consultationScreen: document.getElementById("consultationScreen"),
                startConsultationButton: document.getElementById("startConsultationButton"),
                sessionStatus: document.getElementById("sessionStatus"),
                activityHint: document.getElementById("activityHint"),
                transcriptLabel: document.getElementById("transcriptLabel"),
                transcriptText: document.getElementById("transcriptText"),
                diagnosisPanel: document.getElementById("diagnosisPanel"),
                diagnosisTitle: document.getElementById("diagnosisTitle"),
                diagnosisHint: document.getElementById("diagnosisHint"),
                diagnosisList: document.getElementById("diagnosisList"),
                messageInput: document.getElementById("messageInput"),
                micButton: document.getElementById("micButton"),
                sendButton: document.getElementById("sendButton"),
                restartButton: document.getElementById("restartButton"),
                endSessionButton: document.getElementById("endSessionButton"),
                liveBadge: document.getElementById("liveBadge"),
                liveBadgeText: document.getElementById("liveBadgeText"),
                chatMessages: document.getElementById("chatMessages"),
                chatScroller: document.getElementById("chatScroller"),
                statusBanners: document.getElementById("statusBanners"),
                languageButtons: Array.from(document.querySelectorAll("[data-language]")),
                muteToggle: document.getElementById("muteToggle"),
                cameraWrap: document.getElementById("cameraWrap"),
                cameraPreview: document.getElementById("cameraPreview"),
                cameraPlaceholder: document.getElementById("cameraPlaceholder"),
                cameraMinimize: document.getElementById("cameraMinimize"),
                cameraRestore: document.getElementById("cameraRestore"),
                typingIndicator: document.getElementById("typingIndicator"),
                summaryModal: document.getElementById("summaryModal"),
                summaryContent: document.getElementById("summaryContent"),
                summaryTitle: document.getElementById("summaryTitle"),
                copySummaryButton: document.getElementById("copySummaryButton") || document.getElementById("copySummaryBtn"),
                shareSummaryButton: document.getElementById("shareSummaryButton") || document.getElementById("whatsappShareBtn"),
                closeSummaryButton: document.getElementById("closeSummaryButton") || document.getElementById("closeSummaryBtn"),
                summaryPrompt: document.getElementById("summaryPrompt"),
                summaryPromptText: document.getElementById("summaryPromptText"),
                summaryGenerateButton: document.getElementById("summaryGenerateButton"),
                summaryLaterButton: document.getElementById("summaryLaterButton"),
                startDescription: document.getElementById("startDescription"),
                supportNote: document.getElementById("supportNote"),
                patientContextModal: document.getElementById("patientContextModal"),
                patientAge: document.getElementById("patientAge"),
                patientWeight: document.getElementById("patientWeight"),
                patientAllergies: document.getElementById("patientAllergies"),
                patientMedications: document.getElementById("patientMedications"),
                savePatientContextButton: document.getElementById("savePatientContextButton"),
                skipPatientContextButton: document.getElementById("skipPatientContextButton"),
                patientContextTitle: document.getElementById("patientContextTitle"),
                patientContextHint: document.getElementById("patientContextHint"),
            };

            this.summaryModal = this.elements.summaryModal;
            this.summaryContent = this.elements.summaryContent;
            this.copySummaryBtn = this.elements.copySummaryButton;
            this.whatsappShareBtn = this.elements.shareSummaryButton;
            this.closeSummaryBtn = this.elements.closeSummaryButton;

            this.state = {
                initialized: false,
                language: localStorage.getItem("doctorLanguage") || "en",
                conversationHistory: [],
                recognition: null,
                recognitionStopRequested: false,
                isListening: false,
                isSpeaking: false,
                isSessionActive: false,
                isMuted: localStorage.getItem("doctorMuted") === "true",
                mediaStream: null,
                currentStreamAbort: null,
                autoSubmitTimer: null,
                summaryShown: false,
                summaryOffered: false,
                summaryRequested: false,
                drag: {
                    active: false,
                    offsetX: 0,
                    offsetY: 0,
                },
                patientContext: this.loadPatientContext(),
            };
        }

        t(key) {
            return UI_TEXT[this.state.language][key] || UI_TEXT.en[key] || key;
        }

        init() {
            if (this.state.initialized) {
                return;
            }
            this.state.initialized = true;
            this.renderStaticText();
            this.bindEvents();
            this.ensureRecognition();
            this.updateRecognitionLanguage();
            this.setLastReplyText(" ");
            this.hideSummaryPrompt();
            this.setCameraPreviewVisible(false);
            this.ensureSecureMediaBanner();
            this.checkHindiVoiceAvailability();

            if ("speechSynthesis" in window) {
                window.speechSynthesis.getVoices();
                window.speechSynthesis.onvoiceschanged = () => {
                    this.checkHindiVoiceAvailability();
                };
            }
        }

        escapeHtml(value) {
            return String(value || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        formatMessageText(text) {
            const safe = this.escapeHtml(String(text || "").trim());
            if (!safe) {
                return "";
            }
            return safe
                .replace(/\n/g, "<br>")
                .replace(/(?:⚠️\s*)?I am an AI assistant, not a licensed doctor\.[\s\S]*/i, (match) => `<em>${match}</em>`);
        }

        stripDisclaimerForSpeech(text) {
            return String(text || "").replace(DISCLAIMER_PATTERN, "").replace(/\*/g, "").trim();
        }

        scrollChatToBottom(force) {
            const target = this.elements.chatScroller;
            if (!target) {
                return;
            }
            const applyScroll = () => {
                target.scrollTop = target.scrollHeight;
            };
            if (force) {
                applyScroll();
                return;
            }
            window.requestAnimationFrame(applyScroll);
        }

        currentTimeLabel() {
            return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }

        setStatus(status, hint) {
            if (this.elements.sessionStatus) {
                this.elements.sessionStatus.textContent = status;
            }
            if (this.elements.activityHint) {
                this.elements.activityHint.textContent = hint;
            }
        }

        setLiveBadge(active) {
            if (!this.elements.liveBadge || !this.elements.liveBadgeText) {
                return;
            }
            this.elements.liveBadge.classList.toggle("is-active", Boolean(active));
            this.elements.liveBadge.classList.toggle("is-ended", !active);
            this.elements.liveBadgeText.textContent = active ? this.t("liveLabel") : this.t("endedLabel");
        }

        renderStaticText() {
            document.documentElement.lang = this.t("htmlLang");
            if (this.elements.messageInput) {
                this.elements.messageInput.placeholder = this.t("placeholder");
            }
            if (this.elements.sendButton) {
                this.elements.sendButton.textContent = this.t("send");
            }
            if (this.elements.restartButton) {
                this.elements.restartButton.textContent = this.t("restart");
            }
            if (this.elements.endSessionButton) {
                this.elements.endSessionButton.textContent = this.t("endSession");
            }
            if (this.elements.startConsultationButton) {
                this.elements.startConsultationButton.textContent = this.t("start");
            }
            if (this.elements.startDescription) {
                this.elements.startDescription.textContent = this.t("welcome");
            }
            if (this.elements.supportNote) {
                this.elements.supportNote.textContent = this.t("support");
            }
            if (this.elements.savePatientContextButton) {
                this.elements.savePatientContextButton.textContent = this.t("contextStart");
            }
            if (this.elements.skipPatientContextButton) {
                this.elements.skipPatientContextButton.textContent = this.t("contextSkip");
            }
            if (this.elements.patientContextTitle) {
                this.elements.patientContextTitle.textContent = this.t("contextTitle");
            }
            if (this.elements.patientContextHint) {
                this.elements.patientContextHint.textContent = this.t("contextHint");
            }
            if (this.elements.patientAge) {
                this.elements.patientAge.placeholder = this.t("agePlaceholder");
            }
            if (this.elements.patientWeight) {
                this.elements.patientWeight.placeholder = this.t("weightPlaceholder");
            }
            if (this.elements.patientAllergies) {
                this.elements.patientAllergies.placeholder = this.t("allergiesPlaceholder");
            }
            if (this.elements.patientMedications) {
                this.elements.patientMedications.placeholder = this.t("medicationsPlaceholder");
            }
            if (this.elements.transcriptLabel) {
                this.elements.transcriptLabel.textContent = this.t("lastReply");
            }
            if (this.elements.diagnosisTitle) {
                this.elements.diagnosisTitle.textContent = this.t("diagnosisTitle");
            }
            if (this.elements.diagnosisHint) {
                this.elements.diagnosisHint.textContent = this.t("diagnosisHint");
            }
            if (this.elements.summaryTitle) {
                this.elements.summaryTitle.textContent = this.t("summaryTitle");
            }
            if (this.elements.copySummaryButton) {
                this.elements.copySummaryButton.textContent = this.t("summaryCopy");
            }
            if (this.elements.shareSummaryButton) {
                this.elements.shareSummaryButton.textContent = this.t("summaryShare");
            }
            if (this.elements.closeSummaryButton) {
                this.elements.closeSummaryButton.textContent = this.t("summaryClose");
            }
            if (this.elements.summaryPromptText) {
                this.elements.summaryPromptText.textContent = this.t("summaryOffer");
            }
            if (this.elements.summaryGenerateButton) {
                this.elements.summaryGenerateButton.textContent = this.t("summaryGenerate");
            }
            if (this.elements.summaryLaterButton) {
                this.elements.summaryLaterButton.textContent = this.t("summaryLater");
            }
            if (this.elements.micButton) {
                this.elements.micButton.title = this.t("micTooltip");
                this.elements.micButton.setAttribute("aria-label", this.t("micTooltip"));
            }
            this.renderLanguagePills();
            this.renderMuteToggle();
            this.setLiveBadge(this.state.isSessionActive);
            if (!this.state.isSessionActive) {
                this.setStatus(this.t("liveReady"), this.t("inputHint"));
            }
        }

        renderLanguagePills() {
            this.elements.languageButtons.forEach((button) => {
                const active = button.dataset.language === this.state.language;
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-pressed", active ? "true" : "false");
            });
        }

        renderMuteToggle() {
            if (!this.elements.muteToggle) {
                return;
            }
            this.elements.muteToggle.textContent = this.state.isMuted ? "🔇" : "🔊";
            this.elements.muteToggle.setAttribute("aria-pressed", this.state.isMuted ? "true" : "false");
            localStorage.setItem("doctorMuted", String(this.state.isMuted));
        }

        addBanner(kind, message, id) {
            if (!this.elements.statusBanners || !message) {
                return;
            }
            this.removeBanner(id);
            const banner = document.createElement("div");
            banner.className = `status-banner ${kind || "info"}`;
            banner.dataset.bannerId = id;

            const copy = document.createElement("div");
            copy.className = "status-banner-copy";
            copy.textContent = message;

            const close = document.createElement("button");
            close.type = "button";
            close.className = "status-banner-close";
            close.textContent = "✕";
            close.setAttribute("aria-label", "Dismiss");
            close.addEventListener("click", () => this.removeBanner(id));

            banner.appendChild(copy);
            banner.appendChild(close);
            this.elements.statusBanners.appendChild(banner);
        }

        removeBanner(id) {
            if (!this.elements.statusBanners || !id) {
                return;
            }
            const node = this.elements.statusBanners.querySelector(`[data-banner-id="${id}"]`);
            if (node) {
                node.remove();
            }
        }

        canUseSecureMedia() {
            return Boolean(window.isSecureContext || window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
        }

        ensureSecureMediaBanner() {
            if (this.canUseSecureMedia()) {
                this.removeBanner("secure-context");
                return false;
            }
            this.addBanner("warning", this.t("insecureMedia"), "secure-context");
            return true;
        }

        async queryPermission(name) {
            if (!navigator.permissions || !navigator.permissions.query) {
                return "prompt";
            }
            try {
                const result = await navigator.permissions.query({ name: name });
                return result.state || "prompt";
            } catch (_error) {
                return "prompt";
            }
        }

        async prepareMedia() {
            if (!this.state.isSessionActive) {
                return;
            }
            this.stopMediaStream();
            if (this.ensureSecureMediaBanner()) {
                return;
            }
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.addBanner("info", this.t("cameraUnavailable"), "camera-permission");
                return;
            }

            try {
                const cameraPermission = await this.queryPermission("camera");
                if (cameraPermission === "denied") {
                    this.addBanner("info", this.t("cameraUnavailable"), "camera-permission");
                    return;
                }
                this.state.mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: false,
                    video: {
                        facingMode: "user",
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                    },
                });
                if (this.elements.cameraPreview) {
                    this.elements.cameraPreview.srcObject = this.state.mediaStream;
                }
                this.setCameraPreviewVisible(true);
                this.removeBanner("camera-permission");
            } catch (_error) {
                this.addBanner("info", this.t("cameraUnavailable"), "camera-permission");
                this.setCameraPreviewVisible(false);
            }
        }

        stopMediaStream() {
            if (this.state.mediaStream) {
                this.state.mediaStream.getTracks().forEach((track) => track.stop());
            }
            this.state.mediaStream = null;
            if (this.elements.cameraPreview) {
                this.elements.cameraPreview.srcObject = null;
            }
            this.setCameraPreviewVisible(false);
        }

        setCameraPreviewVisible(visible) {
            if (!this.elements.cameraWrap || !this.elements.cameraPlaceholder) {
                return;
            }
            const show = Boolean(visible && this.state.isSessionActive);
            this.elements.cameraWrap.hidden = !show;
            this.elements.cameraPlaceholder.hidden = show;
            if (!show && this.elements.cameraRestore) {
                this.elements.cameraRestore.hidden = true;
            }
        }

        getHistoryForRequest() {
            return this.state.conversationHistory.slice(-MAX_HISTORY_MESSAGES).map((item) => ({
                role: item.role,
                content: item.content,
            }));
        }

        loadPatientContext() {
            try {
                const raw = window.localStorage.getItem(PATIENT_CONTEXT_STORAGE_KEY);
                const parsed = raw ? JSON.parse(raw) : {};
                return {
                    patient_age: Number(parsed.patient_age) > 0 ? Number(parsed.patient_age) : null,
                    patient_weight: Number(parsed.patient_weight) > 0 ? Number(parsed.patient_weight) : null,
                    allergies: String(parsed.allergies || "").trim(),
                    current_medications: String(parsed.current_medications || "").trim(),
                };
            } catch (_error) {
                return {
                    patient_age: null,
                    patient_weight: null,
                    allergies: "",
                    current_medications: "",
                };
            }
        }

        savePatientContextToStorage() {
            window.localStorage.setItem(PATIENT_CONTEXT_STORAGE_KEY, JSON.stringify(this.state.patientContext));
        }

        fillPatientContextForm() {
            if (this.elements.patientAge) {
                this.elements.patientAge.value = this.state.patientContext.patient_age || "";
            }
            if (this.elements.patientWeight) {
                this.elements.patientWeight.value = this.state.patientContext.patient_weight || "";
            }
            if (this.elements.patientAllergies) {
                this.elements.patientAllergies.value = this.state.patientContext.allergies || "";
            }
            if (this.elements.patientMedications) {
                this.elements.patientMedications.value = this.state.patientContext.current_medications || "";
            }
        }

        openPatientContextModal() {
            if (!this.elements.patientContextModal) {
                this.startConsultation();
                return;
            }
            this.fillPatientContextForm();
            this.elements.patientContextModal.hidden = false;
            this.elements.patientContextModal.style.display = "grid";
        }

        closePatientContextModal() {
            if (!this.elements.patientContextModal) {
                return;
            }
            this.elements.patientContextModal.hidden = true;
            this.elements.patientContextModal.style.display = "none";
        }

        collectPatientContext() {
            const ageValue = this.elements.patientAge ? Number(this.elements.patientAge.value) : 0;
            const weightValue = this.elements.patientWeight ? Number(this.elements.patientWeight.value) : 0;
            this.state.patientContext = {
                patient_age: ageValue > 0 ? ageValue : null,
                patient_weight: weightValue > 0 ? weightValue : null,
                allergies: this.elements.patientAllergies ? String(this.elements.patientAllergies.value || "").trim() : "",
                current_medications: this.elements.patientMedications ? String(this.elements.patientMedications.value || "").trim() : "",
            };
            this.savePatientContextToStorage();
        }

        getPatientContextPayload() {
            return {
                patient_age: this.state.patientContext.patient_age || null,
                patient_weight: this.state.patientContext.patient_weight || null,
                allergies: this.state.patientContext.allergies || null,
                current_medications: this.state.patientContext.current_medications || null,
            };
        }

        pushConversation(role, content) {
            this.state.conversationHistory.push({
                role: role,
                content: String(content || "").trim(),
            });
            if (this.state.conversationHistory.length > MAX_HISTORY_MESSAGES) {
                this.state.conversationHistory = this.state.conversationHistory.slice(-MAX_HISTORY_MESSAGES);
            }
        }

        setLastReplyText(text) {
            if (this.elements.transcriptText) {
                this.elements.transcriptText.textContent = text || "";
            }
        }

        createMessageElement(role, text) {
            if (!this.elements.chatMessages) {
                return null;
            }

            const article = document.createElement("article");
            article.className = `chat-message ${role}`;

            const bubble = document.createElement("div");
            bubble.className = "chat-bubble";

            const body = document.createElement("div");
            body.className = "chat-body";
            body.innerHTML = this.formatMessageText(text);

            const meta = document.createElement("div");
            meta.className = "chat-meta";

            const stamp = document.createElement("span");
            stamp.className = "chat-time";
            stamp.textContent = this.currentTimeLabel();
            meta.appendChild(stamp);

            if (role === "assistant") {
                const replay = document.createElement("button");
                replay.type = "button";
                replay.className = "speaker-button";
                replay.textContent = "🔊";
                replay.addEventListener("click", () => this.speakText(body.textContent || ""));
                meta.appendChild(replay);
            }

            bubble.appendChild(body);
            bubble.appendChild(meta);
            article.appendChild(bubble);
            this.elements.chatMessages.appendChild(article);
            this.scrollChatToBottom();

            return { article: article, body: body, meta: meta };
        }

        updateMessageBody(messageNode, text, keepCursor) {
            if (!messageNode || !messageNode.body) {
                return;
            }
            const cursor = keepCursor ? '<span class="stream-cursor">▌</span>' : "";
            messageNode.body.innerHTML = this.formatMessageText(text) + cursor;
            this.scrollChatToBottom();
        }

        renderTypingIndicator(show) {
            if (!this.elements.typingIndicator) {
                return;
            }
            this.elements.typingIndicator.hidden = !show;
            this.scrollChatToBottom();
        }

        updateDiagnosisPanel(items) {
            if (!this.elements.diagnosisPanel || !this.elements.diagnosisList) {
                return;
            }

            const diagnosisItems = Array.isArray(items) ? items : [];
            this.elements.diagnosisList.innerHTML = "";
            if (!diagnosisItems.length) {
                this.elements.diagnosisPanel.classList.remove("is-visible");
                return;
            }

            diagnosisItems.forEach((item) => {
                const card = document.createElement("article");
                card.className = "diagnosis-item";

                const row = document.createElement("div");
                row.className = "diagnosis-row";

                const title = document.createElement("strong");
                title.textContent = item.name || "Possible condition";

                const seekDoctor = document.createElement("span");
                seekDoctor.textContent = item.seek_doctor ? "See doctor" : "Monitor symptoms";
                seekDoctor.style.color = item.color || "#2d7c68";

                row.appendChild(title);
                row.appendChild(seekDoctor);
                card.appendChild(row);
                card.style.borderLeft = `4px solid ${item.color || "#2d7c68"}`;
                this.elements.diagnosisList.appendChild(card);
            });

            this.elements.diagnosisPanel.classList.add("is-visible");
        }

        extractDiagnosis(text) {
            const match = String(text || "").match(DIAGNOSIS_PATTERN);
            if (!match) {
                return {
                    reply: String(text || "").trim(),
                    diagnosis: { items: [] },
                };
            }
            let diagnosis = { items: [] };
            try {
                const parsed = JSON.parse(match[1].trim());
                if (parsed && Array.isArray(parsed.items)) {
                    diagnosis = parsed;
                }
            } catch (_error) {
                diagnosis = { items: [] };
            }
            return {
                reply: String(text || "").replace(match[0], "").trim(),
                diagnosis: diagnosis,
            };
        }

        cancelSpeech() {
            if ("speechSynthesis" in window) {
                window.speechSynthesis.cancel();
            }
            this.state.isSpeaking = false;
        }

        bestVoice() {
            if (!("speechSynthesis" in window)) {
                return null;
            }
            const voices = window.speechSynthesis.getVoices() || [];
            if (this.state.language === "hi") {
                return (
                    voices.find((voice) => /google/i.test(voice.name) && voice.lang === "hi-IN") ||
                    voices.find((voice) => voice.lang && voice.lang.toLowerCase().startsWith("hi")) ||
                    null
                );
            }
            return (
                voices.find((voice) => /female|samantha|veena|zira/i.test(voice.name) && /en-(IN|US)/i.test(voice.lang)) ||
                voices.find((voice) => voice.lang === "en-IN") ||
                voices.find((voice) => voice.lang === "en-US") ||
                null
            );
        }

        checkHindiVoiceAvailability() {
            if (this.state.language !== "hi" || !("speechSynthesis" in window)) {
                this.removeBanner("hindi-voice-warning");
                return;
            }
            if (!this.bestVoice()) {
                this.addBanner("info", HINDI_VOICE_WARNING, "hindi-voice-warning");
            } else {
                this.removeBanner("hindi-voice-warning");
            }
        }

        speakText(text) {
            const cleanText = this.stripDisclaimerForSpeech(text);
            if (!cleanText || this.state.isMuted || this.state.isListening || !("speechSynthesis" in window)) {
                return;
            }
            this.cancelSpeech();
            const utterance = new SpeechSynthesisUtterance(cleanText);
            const voice = this.bestVoice();
            utterance.rate = 0.92;
            utterance.pitch = 1;
            utterance.lang = voice ? voice.lang : (this.state.language === "hi" ? "hi-IN" : "en-IN");
            if (voice) {
                utterance.voice = voice;
            }
            utterance.onstart = () => {
                this.state.isSpeaking = true;
            };
            utterance.onend = () => {
                this.state.isSpeaking = false;
            };
            utterance.onerror = () => {
                this.state.isSpeaking = false;
            };
            window.speechSynthesis.speak(utterance);
        }

        stopRecognition() {
            if (!this.state.recognition) {
                return;
            }
            this.state.recognitionStopRequested = true;
            try {
                this.state.recognition.stop();
            } catch (_error) {
                // no-op
            }
        }

        clearAutoSubmit() {
            if (this.state.autoSubmitTimer) {
                window.clearTimeout(this.state.autoSubmitTimer);
                this.state.autoSubmitTimer = null;
            }
        }

        scheduleAutoSubmit() {
            this.clearAutoSubmit();
            this.state.autoSubmitTimer = window.setTimeout(() => {
                const value = this.elements.messageInput ? this.elements.messageInput.value.trim() : "";
                if (value) {
                    this.stopRecognition();
                    this.sendMessage(value);
                }
            }, AUTO_SUBMIT_DELAY);
        }

        ensureRecognition() {
            if (!SpeechRecognition || this.state.recognition) {
                return;
            }
            const recognition = new SpeechRecognition();
            recognition.interimResults = true;
            recognition.continuous = true;
            this.state.recognition = recognition;

            recognition.onstart = () => {
                this.state.isListening = true;
                this.state.recognitionStopRequested = false;
                this.cancelSpeech();
                if (this.elements.micButton) {
                    this.elements.micButton.classList.add("is-recording");
                }
                this.setStatus(this.t("listening"), this.t("listeningHint"));
            };

            recognition.onresult = (event) => {
                let transcript = "";
                for (let index = event.resultIndex; index < event.results.length; index += 1) {
                    transcript += event.results[index][0].transcript;
                }
                if (this.elements.messageInput) {
                    this.elements.messageInput.value = transcript.trim();
                }
                this.scheduleAutoSubmit();
            };

            recognition.onerror = (event) => {
                this.state.isListening = false;
                if (this.elements.micButton) {
                    this.elements.micButton.classList.remove("is-recording");
                }
                this.clearAutoSubmit();

                if (event.error === "no-speech") {
                    this.addBanner("warning", this.t("micNoSpeech"), "mic-runtime");
                } else if (event.error === "network") {
                    this.addBanner("warning", this.t("voiceNetwork"), "mic-runtime");
                } else {
                    this.addBanner("warning", this.t("voiceUnsupported"), "mic-runtime");
                }
                this.setStatus(this.t("live"), this.t("liveHint"));
            };

            recognition.onend = () => {
                this.state.isListening = false;
                if (this.elements.micButton) {
                    this.elements.micButton.classList.remove("is-recording");
                }
                this.clearAutoSubmit();
                this.setStatus(this.t("live"), this.t("liveHint"));
            };
        }

        updateRecognitionLanguage() {
            if (this.state.recognition) {
                this.state.recognition.lang = this.state.language === "hi" ? "hi-IN" : "en-IN";
            }
        }

        async toggleMicrophone() {
            this.ensureRecognition();
            this.updateRecognitionLanguage();
            if (!this.state.recognition) {
                this.addBanner("warning", this.t("voiceUnsupported"), "mic-runtime");
                return;
            }
            if (this.ensureSecureMediaBanner()) {
                this.addBanner("warning", this.t("insecureMedia"), "mic-runtime");
                return;
            }
            if (this.state.isListening) {
                this.stopRecognition();
                return;
            }
            const micPermission = await this.queryPermission("microphone");
            if (micPermission === "denied") {
                this.addBanner("warning", this.t("voiceUnsupported"), "mic-runtime");
                return;
            }
            this.removeBanner("mic-runtime");
            try {
                this.state.recognition.start();
            } catch (_error) {
                this.addBanner("warning", this.t("voiceUnsupported"), "mic-runtime");
            }
        }

        closeSummaryModal() {
            if (this.summaryModal) {
                this.summaryModal.hidden = true;
                this.summaryModal.style.display = "none";
            }
        }

        openSummaryModal(text) {
            if (this.summaryContent) {
                this.summaryContent.textContent = String(text || "").trim() || this.t("summaryEmpty");
            }
            if (this.summaryModal) {
                this.summaryModal.hidden = false;
                this.summaryModal.style.display = "grid";
            }
        }

        hideSummaryPrompt() {
            if (this.elements.summaryPrompt) {
                this.elements.summaryPrompt.hidden = true;
            }
        }

        maybeOfferSummary() {
            if (this.state.summaryOffered || this.state.summaryRequested) {
                return;
            }
            const userMessages = this.state.conversationHistory.filter((item) => item.role === "user").length;
            if (userMessages < 10) {
                return;
            }
            this.state.summaryOffered = true;
            if (this.elements.summaryPrompt) {
                this.elements.summaryPrompt.hidden = false;
            }
        }

        async copyText(value) {
            const text = String(value || "").trim();
            if (!text) {
                return false;
            }
            if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            }
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.top = "-9999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            let copied = false;
            try {
                copied = document.execCommand("copy");
            } catch (_error) {
                copied = false;
            }
            document.body.removeChild(textArea);
            return copied;
        }

        async copySummary() {
            const summaryText = this.summaryContent ? (this.summaryContent.innerText || this.summaryContent.textContent || "") : "";
            if (!summaryText.trim()) {
                return;
            }

            const copied = await this.copyText(summaryText);
            if (this.copySummaryBtn) {
                const originalLabel = this.t("summaryCopy");
                this.copySummaryBtn.textContent = copied ? "✓ Copied!" : this.t("copyFallback");
                window.setTimeout(() => {
                    if (this.copySummaryBtn) {
                        this.copySummaryBtn.textContent = originalLabel;
                    }
                }, 2000);
            }

            if (!copied) {
                this.addBanner("info", this.t("copyFallback"), "summary-copy");
            }
        }

        shareOnWhatsApp() {
            const summaryText = this.summaryContent ? (this.summaryContent.innerText || this.summaryContent.textContent || "") : "";
            if (!summaryText.trim()) {
                return;
            }

            const shareUrl = `https://wa.me/?text=${encodeURIComponent(summaryText)}`;
            const popup = window.open(shareUrl, "_blank", "noopener");
            if (!popup) {
                this.addBanner("info", this.t("shareBlocked"), "summary-share");
                window.location.href = shareUrl;
            }
        }

        async fetchJsonWithRetry(url, options) {
            let lastError = null;
            for (let attempt = 0; attempt <= REQUEST_RETRY_LIMIT; attempt += 1) {
                try {
                    const response = await fetch(url, options);
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) {
                        throw new Error(payload.detail || payload.error || DOCTOR_UNAVAILABLE_MESSAGE);
                    }
                    return payload;
                } catch (error) {
                    lastError = error;
                    if (attempt >= REQUEST_RETRY_LIMIT) {
                        break;
                    }
                    await new Promise((resolve) => window.setTimeout(resolve, 350 * (attempt + 1)));
                }
            }
            throw lastError || new Error(DOCTOR_UNAVAILABLE_MESSAGE);
        }

        async generateSummary() {
            if (!this.state.conversationHistory.length) {
                this.openSummaryModal("");
                return;
            }
            this.state.summaryRequested = true;
            this.hideSummaryPrompt();
            this.setStatus(this.t("thinking"), this.t("summaryTitle"));
            try {
                const payload = await this.fetchJsonWithRetry("/api/doctor/summary", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        messages: this.getHistoryForRequest(),
                        language: this.state.language,
                        ...this.getPatientContextPayload(),
                    }),
                });
                this.openSummaryModal(payload.summary || "");
                this.state.summaryShown = true;
                this.setStatus(this.t("live"), this.t("liveHint"));
            } catch (_error) {
                this.addBanner("warning", DOCTOR_UNAVAILABLE_MESSAGE, "summary-error");
                this.setStatus(this.t("live"), this.t("liveHint"));
            }
        }

        parseSseBuffer(buffer, onEvent) {
            let working = buffer;
            let separatorIndex = working.indexOf("\n\n");
            while (separatorIndex !== -1) {
                const rawEvent = working.slice(0, separatorIndex);
                working = working.slice(separatorIndex + 2);
                const dataLines = rawEvent
                    .split("\n")
                    .filter((line) => line.startsWith("data: "))
                    .map((line) => line.slice(6));
                if (dataLines.length) {
                    onEvent(dataLines.join("\n"));
                }
                separatorIndex = working.indexOf("\n\n");
            }
            return working;
        }

        async fallbackChat(message, historyBeforeSend, placeholderNode) {
            const payload = await this.fetchJsonWithRetry("/api/doctor/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: message,
                    messages: historyBeforeSend,
                    language: this.state.language,
                    ...this.getPatientContextPayload(),
                }),
            });
            const reply = String(payload.reply || "").trim();
            this.updateMessageBody(placeholderNode, reply, false);
            this.setLastReplyText(reply);
            this.updateDiagnosisPanel(payload.diagnosis && Array.isArray(payload.diagnosis.items) ? payload.diagnosis.items : []);
            this.pushConversation("user", message);
            this.pushConversation("assistant", reply);
            this.maybeOfferSummary();
            this.speakText(reply);
        }

        appendRetryButton(message, historyBeforeSend, placeholderNode) {
            if (!placeholderNode || !placeholderNode.meta) {
                return;
            }
            const action = document.createElement("button");
            action.type = "button";
            action.className = "retry-button";
            action.textContent = this.t("retry");
            action.addEventListener("click", () => {
                if (placeholderNode.article) {
                    placeholderNode.article.remove();
                }
                this.sendMessage(message, historyBeforeSend);
            });
            placeholderNode.meta.appendChild(action);
        }

        async streamChat(message, historyBeforeSend, placeholderNode) {
            if (!window.ReadableStream) {
                return this.fallbackChat(message, historyBeforeSend, placeholderNode);
            }

            this.state.currentStreamAbort = new AbortController();
            const response = await fetch("/api/doctor/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: message,
                    messages: historyBeforeSend,
                    language: this.state.language,
                    ...this.getPatientContextPayload(),
                }),
                signal: this.state.currentStreamAbort.signal,
            });

            if (!response.ok || !response.body) {
                throw new Error(DOCTOR_UNAVAILABLE_MESSAGE);
            }

            this.renderTypingIndicator(true);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let rawReply = "";
            let streamDone = false;
            let streamError = "";

            while (!streamDone) {
                const result = await reader.read();
                if (result.done) {
                    break;
                }
                buffer += decoder.decode(result.value, { stream: true });
                buffer = this.parseSseBuffer(buffer, (dataLine) => {
                    let payload = {};
                    try {
                        payload = JSON.parse(dataLine);
                    } catch (_error) {
                        payload = {};
                    }

                    if (payload.chunk) {
                        this.renderTypingIndicator(false);
                        rawReply += payload.chunk;
                        const extracted = this.extractDiagnosis(rawReply);
                        this.updateMessageBody(placeholderNode, extracted.reply, true);
                    }
                    if (payload.error) {
                        streamError = payload.error;
                        streamDone = true;
                    }
                    if (payload.done) {
                        streamDone = true;
                    }
                });
            }

            this.renderTypingIndicator(false);
            if (streamError) {
                throw new Error(streamError);
            }

            const extracted = this.extractDiagnosis(rawReply);
            const finalReply = extracted.reply || DOCTOR_UNAVAILABLE_MESSAGE;
            this.updateMessageBody(placeholderNode, finalReply, false);
            this.setLastReplyText(finalReply);
            this.updateDiagnosisPanel(extracted.diagnosis.items || []);
            this.pushConversation("user", message);
            this.pushConversation("assistant", finalReply);
            this.maybeOfferSummary();
            this.speakText(finalReply);
        }

        async sendMessage(forcedMessage, providedHistory) {
            const message = String(forcedMessage || (this.elements.messageInput ? this.elements.messageInput.value : "")).trim();
            if (!message) {
                return;
            }

            const historyBeforeSend = Array.isArray(providedHistory) ? providedHistory : this.getHistoryForRequest();
            this.cancelSpeech();
            this.removeBanner("chat-error");
            this.removeBanner("summary-error");

            if (this.elements.messageInput) {
                this.elements.messageInput.value = "";
            }
            if (this.state.isListening) {
                this.stopRecognition();
            }

            this.createMessageElement("user", message);
            const placeholderNode = this.createMessageElement("assistant", "");
            this.updateMessageBody(placeholderNode, "", true);
            this.setStatus(this.t("thinking"), this.t("typing"));

            try {
                await this.streamChat(message, historyBeforeSend, placeholderNode);
            } catch (_error) {
                try {
                    await this.fallbackChat(message, historyBeforeSend, placeholderNode);
                } catch (_innerError) {
                    this.updateMessageBody(placeholderNode, DOCTOR_UNAVAILABLE_MESSAGE, false);
                    this.appendRetryButton(message, historyBeforeSend, placeholderNode);
                    this.addBanner("warning", DOCTOR_UNAVAILABLE_MESSAGE, "chat-error");
                    this.setLastReplyText(DOCTOR_UNAVAILABLE_MESSAGE);
                }
            } finally {
                this.renderTypingIndicator(false);
                this.state.currentStreamAbort = null;
                this.setStatus(this.t("live"), this.t("liveHint"));
            }
        }

        resetConversationUi(keepSummary) {
            this.state.conversationHistory = [];
            this.state.summaryShown = false;
            this.state.summaryOffered = false;
            this.state.summaryRequested = false;
            if (this.elements.chatMessages) {
                this.elements.chatMessages.innerHTML = "";
            }
            this.updateDiagnosisPanel([]);
            this.setLastReplyText(" ");
            this.hideSummaryPrompt();
            if (!keepSummary) {
                this.closeSummaryModal();
            }
        }

        async startConsultation() {
            if (this.elements.startScreen) {
                this.elements.startScreen.classList.remove("is-visible");
            }
            this.closePatientContextModal();
            if (this.elements.consultationScreen) {
                this.elements.consultationScreen.classList.add("is-visible");
            }
            this.state.isSessionActive = true;
            this.setLiveBadge(true);
            this.resetConversationUi(false);
            this.ensureSecureMediaBanner();
            await this.prepareMedia();
            this.ensureRecognition();
            this.updateRecognitionLanguage();
            if (this.elements.messageInput) {
                this.elements.messageInput.focus();
            }
            this.setStatus(this.t("live"), this.t("liveHint"));
            this.sendMessage(this.t("startGreeting"));
        }

        restartSession() {
            if (this.state.currentStreamAbort) {
                this.state.currentStreamAbort.abort();
                this.state.currentStreamAbort = null;
            }
            this.cancelSpeech();
            this.stopRecognition();
            this.clearAutoSubmit();
            this.resetConversationUi(false);
            this.setStatus(this.t("restartStatus"), this.t("inputHint"));
            window.setTimeout(() => {
                this.setStatus(this.t("live"), this.t("liveHint"));
                this.sendMessage(this.t("startGreeting"));
            }, 150);
        }

        async endSession() {
            if (this.state.conversationHistory.length && !this.state.summaryShown) {
                await this.generateSummary();
            }
            if (this.state.currentStreamAbort) {
                this.state.currentStreamAbort.abort();
                this.state.currentStreamAbort = null;
            }
            this.cancelSpeech();
            this.stopRecognition();
            this.clearAutoSubmit();
            this.stopMediaStream();
            this.state.isSessionActive = false;
            this.setLiveBadge(false);
            this.setStatus(this.t("endedStatus"), this.t("inputHint"));
            if (this.elements.consultationScreen) {
                this.elements.consultationScreen.classList.remove("is-visible");
            }
            if (this.elements.startScreen) {
                this.elements.startScreen.classList.add("is-visible");
            }
            this.resetConversationUi(true);
        }

        handleLanguageChange(language) {
            if (!["en", "hi"].includes(language)) {
                return;
            }
            this.state.language = language;
            localStorage.setItem("doctorLanguage", language);
            this.renderStaticText();
            this.updateRecognitionLanguage();
            this.checkHindiVoiceAvailability();
        }

        toggleMute() {
            this.state.isMuted = !this.state.isMuted;
            if (this.state.isMuted) {
                this.cancelSpeech();
            }
            this.renderMuteToggle();
        }

        bindCameraDrag() {
            if (!this.elements.cameraWrap) {
                return;
            }

            const startDrag = (event) => {
                const target = event.target;
                if (target && target.closest(".camera-action")) {
                    return;
                }
                const point = event.touches ? event.touches[0] : event;
                const rect = this.elements.cameraWrap.getBoundingClientRect();
                this.state.drag.active = true;
                this.state.drag.offsetX = point.clientX - rect.left;
                this.state.drag.offsetY = point.clientY - rect.top;
                this.elements.cameraWrap.classList.add("is-dragging");
            };

            const moveDrag = (event) => {
                if (!this.state.drag.active) {
                    return;
                }
                const point = event.touches ? event.touches[0] : event;
                const nextLeft = point.clientX - this.state.drag.offsetX;
                const nextTop = point.clientY - this.state.drag.offsetY;
                const maxLeft = window.innerWidth - this.elements.cameraWrap.offsetWidth - 12;
                const maxTop = window.innerHeight - this.elements.cameraWrap.offsetHeight - 12;
                this.elements.cameraWrap.style.left = `${Math.max(12, Math.min(maxLeft, nextLeft))}px`;
                this.elements.cameraWrap.style.top = `${Math.max(90, Math.min(maxTop, nextTop))}px`;
                this.elements.cameraWrap.style.right = "auto";
                this.elements.cameraWrap.style.bottom = "auto";
            };

            const endDrag = () => {
                this.state.drag.active = false;
                this.elements.cameraWrap.classList.remove("is-dragging");
            };

            this.elements.cameraWrap.addEventListener("mousedown", startDrag);
            this.elements.cameraWrap.addEventListener("touchstart", startDrag, { passive: true });
            window.addEventListener("mousemove", moveDrag);
            window.addEventListener("touchmove", moveDrag, { passive: true });
            window.addEventListener("mouseup", endDrag);
            window.addEventListener("touchend", endDrag);
        }

        bindEvents() {
            if (this.elements.startConsultationButton) {
                this.elements.startConsultationButton.addEventListener("click", () => this.openPatientContextModal());
            }
            if (this.elements.savePatientContextButton) {
                this.elements.savePatientContextButton.addEventListener("click", () => {
                    this.collectPatientContext();
                    this.startConsultation();
                });
            }
            if (this.elements.skipPatientContextButton) {
                this.elements.skipPatientContextButton.addEventListener("click", () => {
                    this.collectPatientContext();
                    this.startConsultation();
                });
            }
            if (this.elements.micButton) {
                this.elements.micButton.addEventListener("click", () => this.toggleMicrophone());
            }
            if (this.elements.sendButton) {
                this.elements.sendButton.addEventListener("click", () => this.sendMessage());
            }
            if (this.elements.restartButton) {
                this.elements.restartButton.addEventListener("click", () => this.restartSession());
            }
            if (this.elements.endSessionButton) {
                this.elements.endSessionButton.addEventListener("click", () => this.endSession());
            }
            if (this.elements.muteToggle) {
                this.elements.muteToggle.addEventListener("click", () => this.toggleMute());
            }
            this.elements.languageButtons.forEach((button) => {
                button.addEventListener("click", () => this.handleLanguageChange(button.dataset.language));
            });

            if (this.elements.messageInput) {
                this.elements.messageInput.addEventListener("keydown", (event) => {
                    if (event.key === "Enter") {
                        event.preventDefault();
                        this.sendMessage();
                    }
                });
                this.elements.messageInput.addEventListener("input", () => {
                    this.cancelSpeech();
                    if (this.state.isListening) {
                        this.stopRecognition();
                    }
                });
            }

            if (this.copySummaryBtn) {
                this.copySummaryBtn.addEventListener("click", () => this.copySummary());
            }

            if (this.whatsappShareBtn) {
                this.whatsappShareBtn.addEventListener("click", () => this.shareOnWhatsApp());
            }

            if (this.closeSummaryBtn) {
                this.closeSummaryBtn.addEventListener("click", () => this.closeSummaryModal());
            }

            if (this.elements.summaryGenerateButton) {
                this.elements.summaryGenerateButton.addEventListener("click", () => this.generateSummary());
            }

            if (this.elements.summaryLaterButton) {
                this.elements.summaryLaterButton.addEventListener("click", () => this.hideSummaryPrompt());
            }

            if (this.elements.summaryModal) {
                this.elements.summaryModal.addEventListener("click", (event) => {
                    if (event.target === this.elements.summaryModal) {
                        this.closeSummaryModal();
                    }
                });
            }

            if (this.elements.cameraMinimize) {
                this.elements.cameraMinimize.addEventListener("click", () => {
                    if (this.elements.cameraWrap) {
                        this.elements.cameraWrap.classList.add("is-minimized");
                    }
                    if (this.elements.cameraRestore) {
                        this.elements.cameraRestore.hidden = false;
                    }
                });
            }

            if (this.elements.cameraRestore) {
                this.elements.cameraRestore.addEventListener("click", () => {
                    if (this.elements.cameraWrap) {
                        this.elements.cameraWrap.classList.remove("is-minimized");
                    }
                    this.elements.cameraRestore.hidden = true;
                });
            }

            document.addEventListener("visibilitychange", () => {
                if (!document.hidden && this.state.isSessionActive) {
                    this.prepareMedia();
                }
            });

            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape" && this.elements.summaryModal && !this.elements.summaryModal.hidden) {
                    this.closeSummaryModal();
                }
            });

            window.addEventListener("beforeunload", () => {
                if (this.state.currentStreamAbort) {
                    this.state.currentStreamAbort.abort();
                }
                this.cancelSpeech();
                this.stopRecognition();
                this.clearAutoSubmit();
                this.stopMediaStream();
            });

            this.bindCameraDrag();
        }
    }

    function boot() {
        const app = new AIDoctorApp();
        window.DrKashAI = app;
        app.init();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
        boot();
    }
})();
