(function () {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const waveformBarCount = 25;

    const elements = {
        startScreen: document.getElementById("startScreen"),
        consultationScreen: document.getElementById("consultationScreen"),
        startConsultationButton: document.getElementById("startConsultationButton"),
        sessionStatus: document.getElementById("sessionStatus"),
        activityHint: document.getElementById("activityHint"),
        waveform: document.getElementById("waveform"),
        transcriptText: document.getElementById("transcriptText"),
        diagnosisPanel: document.getElementById("diagnosisPanel"),
        diagnosisList: document.getElementById("diagnosisList"),
        statusBanner: document.getElementById("statusBanner"),
        messageInput: document.getElementById("messageInput"),
        micButton: document.getElementById("micButton"),
        sendButton: document.getElementById("sendButton"),
        restartButton: document.getElementById("restartButton"),
        endSessionButton: document.getElementById("endSessionButton"),
        cameraPreview: document.getElementById("cameraPreview"),
        cameraEmptyState: document.getElementById("cameraEmptyState"),
    };

    const state = {
        recognition: null,
        conversationHistory: [],
        isListening: false,
        isSpeaking: false,
        isSessionActive: false,
        isSupportedRecognition: Boolean(SpeechRecognition),
        isTextOnly: false,
        mediaStream: null,
        hasStartedGreeting: false,
    };

    function createWaveform() {
        if (!elements.waveform) {
            return;
        }
        elements.waveform.innerHTML = "";
        for (let index = 0; index < waveformBarCount; index += 1) {
            const bar = document.createElement("span");
            bar.className = "wave-bar";
            bar.style.setProperty("--delay", `${(index * 0.06).toFixed(2)}s`);
            bar.style.height = `${18 + Math.round(Math.random() * 48)}px`;
            elements.waveform.appendChild(bar);
        }
    }

    function setWaveformMode(mode) {
        if (!elements.waveform) {
            return;
        }
        elements.waveform.classList.remove("listening", "speaking");
        if (mode === "listening") {
            elements.waveform.classList.add("listening");
        }
        if (mode === "speaking") {
            elements.waveform.classList.add("speaking");
        }
    }

    function showBanner(message) {
        if (!elements.statusBanner) {
            return;
        }
        elements.statusBanner.textContent = message;
        elements.statusBanner.classList.add("is-visible");
    }

    function hideBanner() {
        if (!elements.statusBanner) {
            return;
        }
        elements.statusBanner.textContent = "";
        elements.statusBanner.classList.remove("is-visible");
    }

    function setStatus(status, hint) {
        if (elements.sessionStatus) {
            elements.sessionStatus.textContent = status;
        }
        if (elements.activityHint) {
            elements.activityHint.textContent = hint;
        }
    }

    function showConsultationScreen() {
        elements.startScreen?.classList.remove("is-visible");
        elements.consultationScreen?.classList.add("is-visible");
    }

    function showStartScreen() {
        elements.consultationScreen?.classList.remove("is-visible");
        elements.startScreen?.classList.add("is-visible");
    }

    function stopMediaStream() {
        if (!state.mediaStream) {
            return;
        }
        state.mediaStream.getTracks().forEach(function (track) {
            track.stop();
        });
        state.mediaStream = null;
        if (elements.cameraPreview) {
            elements.cameraPreview.srcObject = null;
        }
        if (elements.cameraEmptyState) {
            elements.cameraEmptyState.style.display = "grid";
        }
    }

    async function prepareMedia() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            state.isTextOnly = true;
            showBanner("Camera and microphone preview are not supported here. You can continue with text chat.");
            return;
        }

        try {
            state.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: {
                    facingMode: "user",
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            });
            if (elements.cameraPreview) {
                elements.cameraPreview.srcObject = state.mediaStream;
            }
            if (elements.cameraEmptyState) {
                elements.cameraEmptyState.style.display = "none";
            }
        } catch (_error) {
            state.isTextOnly = true;
            showBanner("Microphone or camera permission was denied. You can still chat with Dr. Kash by typing.");
        }
    }

    function chooseVoice() {
        const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
        return (
            voices.find(function (voice) { return voice.lang === "en-IN"; }) ||
            voices.find(function (voice) { return voice.lang === "en-US"; }) ||
            voices[0] ||
            null
        );
    }

    function stripSafetyArtifacts(text) {
        return String(text || "").replace(/\s+/g, " ").trim();
    }

    function updateDiagnosisPanel(diagnoses) {
        const items = Array.isArray(diagnoses) ? diagnoses : [];
        if (!elements.diagnosisPanel || !elements.diagnosisList) {
            return;
        }

        elements.diagnosisList.innerHTML = "";
        if (!items.length) {
            elements.diagnosisPanel.classList.remove("is-visible");
            return;
        }

        items.forEach(function (item) {
            const safeConfidence = Math.max(0, Math.min(100, Number(item.confidence) || 0));
            const safeColor = item.color || "#3b82f6";

            const wrapper = document.createElement("article");
            wrapper.className = "diagnosis-item";

            const meta = document.createElement("div");
            meta.className = "diagnosis-meta";

            const name = document.createElement("span");
            name.className = "diagnosis-name";
            name.textContent = item.name || "Possible condition";

            const confidence = document.createElement("span");
            confidence.className = "diagnosis-confidence";
            confidence.textContent = `${safeConfidence}%`;

            meta.appendChild(name);
            meta.appendChild(confidence);

            const track = document.createElement("div");
            track.className = "diagnosis-track";

            const fill = document.createElement("div");
            fill.className = "diagnosis-fill";
            fill.style.width = `${safeConfidence}%`;
            fill.style.background = safeColor;

            track.appendChild(fill);
            wrapper.appendChild(meta);
            wrapper.appendChild(track);
            elements.diagnosisList.appendChild(wrapper);
        });

        elements.diagnosisPanel.classList.add("is-visible");
    }

    function speakText(text) {
        const cleanText = stripSafetyArtifacts(text);
        if (!cleanText || !("speechSynthesis" in window)) {
            return;
        }

        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        const voice = chooseVoice();

        utterance.rate = 0.92;
        utterance.pitch = 1.0;
        utterance.lang = voice ? voice.lang : "en-US";
        if (voice) {
            utterance.voice = voice;
        }

        utterance.onstart = function () {
            state.isSpeaking = true;
            setWaveformMode("speaking");
            setStatus("Dr. Kash is speaking.", "Listen in and reply when you’re ready.");
        };

        utterance.onend = function () {
            state.isSpeaking = false;
            setWaveformMode(state.isListening ? "listening" : "idle");
            setStatus("Consultation live.", state.isListening ? "I’m listening for your next message." : "Tap the mic or type your next message.");
        };

        utterance.onerror = function () {
            state.isSpeaking = false;
            setWaveformMode(state.isListening ? "listening" : "idle");
        };

        window.speechSynthesis.speak(utterance);
    }

    function ensureRecognition() {
        if (!state.isSupportedRecognition || state.recognition) {
            return;
        }

        state.recognition = new SpeechRecognition();
        state.recognition.lang = "en-IN";
        state.recognition.interimResults = true;
        state.recognition.continuous = false;

        state.recognition.onstart = function () {
            state.isListening = true;
            elements.micButton?.classList.add("is-recording");
            setWaveformMode("listening");
            setStatus("Listening...", "Speak naturally. I’ll send your message when you finish.");
            hideBanner();
        };

        state.recognition.onresult = function (event) {
            let interimTranscript = "";
            let finalTranscript = "";

            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const transcript = event.results[index][0].transcript.trim();
                if (event.results[index].isFinal) {
                    finalTranscript += `${transcript} `;
                } else {
                    interimTranscript += `${transcript} `;
                }
            }

            const liveText = (finalTranscript || interimTranscript).trim();
            if (elements.messageInput && liveText) {
                elements.messageInput.value = liveText;
            }

            if (finalTranscript.trim()) {
                sendTextMessage(finalTranscript.trim());
            }
        };

        state.recognition.onerror = function (event) {
            state.isListening = false;
            elements.micButton?.classList.remove("is-recording");
            setWaveformMode("idle");

            if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                showBanner("Microphone permission was blocked. You can continue by typing your symptoms.");
                state.isTextOnly = true;
            } else {
                showBanner("Voice input had a problem. Please try again or type your message.");
            }
        };

        state.recognition.onend = function () {
            state.isListening = false;
            elements.micButton?.classList.remove("is-recording");
            setWaveformMode(state.isSpeaking ? "speaking" : "idle");
            if (!state.isSpeaking) {
                setStatus("Consultation live.", "Tap the mic or type your next message.");
            }
        };
    }

    async function sendToAI(message) {
        const trimmedMessage = String(message || "").trim();
        if (!trimmedMessage) {
            return;
        }

        hideBanner();
        setStatus("Dr. Kash is thinking...", "Reviewing what you shared.");

        const outgoingHistory = state.conversationHistory.slice();

        try {
            const response = await fetch("/api/doctor/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    message: trimmedMessage,
                    messages: outgoingHistory,
                }),
            });

            const payload = await response.json().catch(function () {
                return {};
            });

            if (!response.ok) {
                if ((payload.detail || "").includes("GEMINI_API_KEY")) {
                    showBanner("Gemini is not configured yet. Add `GEMINI_API_KEY` to `.env` and restart the server.");
                } else {
                    showBanner(payload.detail || "Network issue talking to Dr. Kash. Please try again.");
                }
                setStatus("Unable to reply right now.", "You can retry your last message.");
                return;
            }

            const reply = stripSafetyArtifacts(payload.reply || "");
            const diagnosis = payload.diagnosis && Array.isArray(payload.diagnosis.items) ? payload.diagnosis.items : [];

            state.conversationHistory.push({ role: "user", content: trimmedMessage });
            state.conversationHistory.push({ role: "assistant", content: reply });

            if (elements.transcriptText) {
                elements.transcriptText.textContent = reply || "Dr. Kash did not return a response.";
            }

            updateDiagnosisPanel(diagnosis);
            speakText(reply);
        } catch (_error) {
            showBanner("Network error while contacting Dr. Kash. Check your connection and try again.");
            setStatus("Connection issue.", "Your session is still open. Retry when ready.");
        }
    }

    function sendTextMessage(forcedMessage) {
        const message = String(
            typeof forcedMessage === "string" ? forcedMessage : elements.messageInput?.value || ""
        ).trim();

        if (!message) {
            return;
        }

        if (elements.messageInput) {
            elements.messageInput.value = "";
        }

        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
        }

        sendToAI(message);
    }

    function toggleMicrophone() {
        ensureRecognition();

        if (!state.isSupportedRecognition || !state.recognition) {
            showBanner("This browser does not support voice recognition here. Please continue with text input.");
            state.isTextOnly = true;
            return;
        }

        if (state.isListening) {
            state.recognition.stop();
            return;
        }

        hideBanner();
        try {
            state.recognition.start();
        } catch (_error) {
            showBanner("Voice input could not start just now. Please try again in a moment.");
        }
    }

    async function startConsultation() {
        showConsultationScreen();
        state.isSessionActive = true;
        state.isTextOnly = false;
        state.hasStartedGreeting = false;
        setStatus("Starting consultation...", "Requesting access to your microphone and camera.");
        hideBanner();

        await prepareMedia();
        ensureRecognition();

        if (!state.isSupportedRecognition) {
            state.isTextOnly = true;
            showBanner("Voice recognition is not supported in this browser. Text chat is ready.");
        }

        setStatus("Consultation live.", "Dr. Kash is joining now.");

        if (!state.hasStartedGreeting) {
            state.hasStartedGreeting = true;
            sendToAI("Hello");
        }
    }

    function restartSession() {
        state.conversationHistory = [];
        state.hasStartedGreeting = false;
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
        }
        if (state.recognition && state.isListening) {
            state.recognition.stop();
        }
        if (elements.messageInput) {
            elements.messageInput.value = "";
        }
        if (elements.transcriptText) {
            elements.transcriptText.textContent = "Starting a fresh consultation...";
        }
        updateDiagnosisPanel([]);
        hideBanner();
        setWaveformMode("idle");
        setStatus("Restarting consultation...", "Dr. Kash will greet you again.");
        sendToAI("Hello");
        state.hasStartedGreeting = true;
    }

    function endSession() {
        state.conversationHistory = [];
        state.isSessionActive = false;
        state.hasStartedGreeting = false;
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
        }
        if (state.recognition) {
            try {
                state.recognition.stop();
            } catch (_error) {
                // no-op
            }
        }
        state.isListening = false;
        state.isSpeaking = false;
        elements.micButton?.classList.remove("is-recording");
        setWaveformMode("idle");
        stopMediaStream();
        updateDiagnosisPanel([]);
        hideBanner();
        if (elements.transcriptText) {
            elements.transcriptText.textContent = "Dr. Kash will greet you as soon as the consultation starts.";
        }
        if (elements.messageInput) {
            elements.messageInput.value = "";
        }
        setStatus("Ready to begin.", "Start a new consultation whenever you’re ready.");
        showStartScreen();
    }

    function bindEvents() {
        elements.startConsultationButton?.addEventListener("click", startConsultation);
        elements.micButton?.addEventListener("click", toggleMicrophone);
        elements.sendButton?.addEventListener("click", function () {
            sendTextMessage();
        });
        elements.restartButton?.addEventListener("click", restartSession);
        elements.endSessionButton?.addEventListener("click", endSession);
        elements.messageInput?.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                sendTextMessage();
            }
        });
        window.addEventListener("beforeunload", function () {
            if ("speechSynthesis" in window) {
                window.speechSynthesis.cancel();
            }
            stopMediaStream();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        createWaveform();
        bindEvents();
        if ("speechSynthesis" in window) {
            window.speechSynthesis.getVoices();
        }
    });

    window.startConsultation = startConsultation;
    window.toggleMicrophone = toggleMicrophone;
    window.sendTextMessage = sendTextMessage;
    window.sendToAI = sendToAI;
    window.updateDiagnosisPanel = updateDiagnosisPanel;
    window.speakText = speakText;
    window.restartSession = restartSession;
    window.endSession = endSession;
})();
