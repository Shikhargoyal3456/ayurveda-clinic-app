(function () {
    const config = window.AI_DOCTOR_CONFIG || {};
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const websocketUrl = config.websocketUrl
        ? `${wsProtocol}//${window.location.host}${config.websocketUrl}`
        : null;

    const state = {
        socket: null,
        mediaStream: null,
        mediaRecorder: null,
        recognition: null,
        frameTimer: null,
        connected: false,
        listening: false,
        sessionId: null,
        canUseSpeechRecognition: "webkitSpeechRecognition" in window || "SpeechRecognition" in window,
    };

    const elements = {
        connectionStatus: document.getElementById("connectionStatus"),
        sessionMessage: document.getElementById("sessionMessage"),
        cameraStatus: document.getElementById("cameraStatus"),
        micStatus: document.getElementById("micStatus"),
        patientVideo: document.getElementById("patientVideo"),
        cameraOverlay: document.getElementById("cameraOverlay"),
        transcriptBox: document.getElementById("transcriptBox"),
        manualMessage: document.getElementById("manualMessage"),
        visionInsights: document.getElementById("visionInsights"),
        medicineInsights: document.getElementById("medicineInsights"),
        safetyInsights: document.getElementById("safetyInsights"),
        consultationSummary: document.getElementById("consultationSummary"),
        consultationSummaryText: document.getElementById("consultationSummaryText"),
        startConsultationButton: document.getElementById("startConsultationButton"),
        micToggleButton: document.getElementById("micToggleButton"),
        sendMessageButton: document.getElementById("sendMessageButton"),
        emergencyButton: document.getElementById("emergencyButton"),
        endConsultationButton: document.getElementById("endConsultationButton"),
    };

    function updateStatus(target, text) {
        if (target) target.textContent = text;
    }

    function appendMessage(role, text) {
        if (!elements.transcriptBox || !text) return;
        const wrapper = document.createElement("div");
        wrapper.className = `doctor-message doctor-message--${role}`;
        const label = document.createElement("strong");
        label.textContent = role === "patient" ? "You" : role === "doctor" ? "Dr. Kash" : "System";
        const body = document.createElement("p");
        body.textContent = text;
        wrapper.append(label, body);
        elements.transcriptBox.appendChild(wrapper);
        elements.transcriptBox.scrollTop = elements.transcriptBox.scrollHeight;
    }

    function speak(text) {
        if (!("speechSynthesis" in window) || !text) return;
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.97;
        utterance.pitch = 1;
        utterance.lang = "en-US";
        window.speechSynthesis.speak(utterance);
    }

    function sendJson(payload) {
        if (!state.socket || state.socket.readyState !== WebSocket.OPEN) return;
        state.socket.send(JSON.stringify(payload));
    }

    function handleServerEvent(event) {
        switch (event.type) {
            case "session_ready":
                state.sessionId = event.session_id;
                break;
            case "status":
                updateStatus(elements.sessionMessage, event.detail || "Connected.");
                break;
            case "transcript":
                appendMessage("patient", event.text);
                break;
            case "ai_message":
                appendMessage("doctor", event.text);
                updateStatus(elements.sessionMessage, "Dr. Kash responded.");
                speak(event.text);
                break;
            case "vision_update":
                if (elements.visionInsights) {
                    elements.visionInsights.textContent = event.text;
                }
                break;
            case "medicine_lookup":
                if (elements.medicineInsights) {
                    const topMatch = event.payload?.top_match;
                    elements.medicineInsights.textContent = topMatch
                        ? `${topMatch.name}: ${topMatch.description || "General medicine context available."}`
                        : `Looked up ${event.payload?.query || "the medicine"}, but no strong external match was found.`;
                }
                break;
            case "emergency":
                if (elements.safetyInsights) {
                    elements.safetyInsights.textContent = event.text;
                }
                appendMessage("system", event.text);
                alert("This sounds urgent. Please call emergency services (911) immediately or go to the nearest hospital.");
                break;
            case "consultation_summary":
                if (elements.consultationSummary && elements.consultationSummaryText) {
                    const lines = [
                        `Patient topics: ${(event.summary?.patient_summary || []).join(" | ") || "No patient messages captured."}`,
                        `Visual note: ${event.summary?.visual_summary || "No camera summary."}`,
                        "Next step: book a real doctor if symptoms continue or worsen."
                    ];
                    elements.consultationSummary.hidden = false;
                    elements.consultationSummaryText.textContent = lines.join(" ");
                }
                break;
            case "error":
                appendMessage("system", event.message || "Something went wrong.");
                break;
            default:
                break;
        }
    }

    async function connectWebSocket() {
        if (state.socket && (state.socket.readyState === WebSocket.OPEN || state.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }
        if (!websocketUrl) return;
        state.socket = new WebSocket(websocketUrl);

        state.socket.addEventListener("open", function () {
            state.connected = true;
            updateStatus(elements.connectionStatus, "Connected");
            updateStatus(elements.sessionMessage, "Private AI consultation room is live. Audio and video are used in real time only.");
        });

        state.socket.addEventListener("message", function (message) {
            try {
                const payload = JSON.parse(message.data);
                handleServerEvent(payload);
            } catch (_error) {
                appendMessage("system", "Received an unreadable server message.");
            }
        });

        state.socket.addEventListener("close", function () {
            state.connected = false;
            state.socket = null;
            updateStatus(elements.connectionStatus, "Disconnected");
            updateStatus(elements.sessionMessage, "Connection closed. Refresh to start again.");
        });

        state.socket.addEventListener("error", function () {
            updateStatus(elements.connectionStatus, "Connection issue");
            appendMessage("system", "Could not connect to the AI doctor right now.");
        });
    }

    async function startMedia() {
        if (state.mediaStream) return state.mediaStream;
        try {
            state.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }
            });
            elements.patientVideo.srcObject = state.mediaStream;
            updateStatus(elements.cameraStatus, "Camera on");
            updateStatus(elements.micStatus, "Mic ready");
            if (elements.cameraOverlay) {
                elements.cameraOverlay.textContent = "Camera is live. Hold the affected area steady for a few seconds.";
            }
            startFrameCapture();
            startAudioRecorder();
            return state.mediaStream;
        } catch (error) {
            appendMessage("system", "Please allow camera and microphone access to use the live AI doctor.");
            updateStatus(elements.cameraStatus, "Permission needed");
            updateStatus(elements.micStatus, "Permission needed");
            throw error;
        }
    }

    function startFrameCapture() {
        if (state.frameTimer) {
            window.clearInterval(state.frameTimer);
        }
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        state.frameTimer = window.setInterval(function () {
            const video = elements.patientVideo;
            if (!video || video.readyState < 2 || !state.connected) return;
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
            const base64 = dataUrl.split(",")[1];
            sendJson({ type: "video_frame", mime_type: "image/jpeg", image: base64 });
        }, 2000);
    }

    function startAudioRecorder() {
        if (!state.mediaStream || typeof MediaRecorder === "undefined") return;
        if (state.mediaRecorder) return;

        try {
            state.mediaRecorder = new MediaRecorder(state.mediaStream, { mimeType: "audio/webm" });
        } catch (_error) {
            return;
        }

        state.mediaRecorder.addEventListener("dataavailable", function (event) {
            if (!event.data || !event.data.size || !state.connected) return;
            const reader = new FileReader();
            reader.onloadend = function () {
                const result = typeof reader.result === "string" ? reader.result : "";
                const base64 = result.split(",")[1];
                if (base64) {
                    sendJson({ type: "audio_chunk", mime_type: event.data.type || "audio/webm", audio: base64 });
                }
            };
            reader.readAsDataURL(event.data);
        });
        state.mediaRecorder.start(1500);
    }

    function startSpeechRecognition() {
        if (!state.canUseSpeechRecognition) {
            appendMessage("system", "Live browser transcription is not supported here. You can still type messages below.");
            return;
        }

        const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
        state.recognition = new RecognitionClass();
        state.recognition.lang = "en-US";
        state.recognition.continuous = true;
        state.recognition.interimResults = true;

        state.recognition.onstart = function () {
            state.listening = true;
            updateStatus(elements.micStatus, "Listening");
            if (elements.micToggleButton) {
                elements.micToggleButton.innerHTML = '<i class="fa-solid fa-microphone-slash" aria-hidden="true"></i> Stop Listening';
            }
        };

        state.recognition.onresult = function (event) {
            let finalTranscript = "";
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const transcript = event.results[i][0].transcript.trim();
                if (event.results[i].isFinal) {
                    finalTranscript += `${transcript} `;
                } else {
                    updateStatus(elements.sessionMessage, `Hearing: ${transcript}`);
                }
            }
            const clean = finalTranscript.trim();
            if (clean) {
                sendJson({ type: "user_text", text: clean });
            }
        };

        state.recognition.onerror = function () {
            updateStatus(elements.micStatus, "Mic issue");
        };

        state.recognition.onend = function () {
            if (state.listening) {
                state.recognition.start();
                return;
            }
            updateStatus(elements.micStatus, "Mic off");
            if (elements.micToggleButton) {
                elements.micToggleButton.innerHTML = '<i class="fa-solid fa-microphone" aria-hidden="true"></i> Start Listening';
            }
        };

        state.recognition.start();
    }

    function stopSpeechRecognition() {
        state.listening = false;
        if (state.recognition) {
            state.recognition.stop();
        }
        updateStatus(elements.micStatus, "Mic off");
    }

    async function startConsultation() {
        await connectWebSocket();
        await startMedia();
        updateStatus(elements.connectionStatus, "Connected");
    }

    function stopConsultation() {
        stopSpeechRecognition();
        if (state.frameTimer) {
            window.clearInterval(state.frameTimer);
            state.frameTimer = null;
        }
        if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
            state.mediaRecorder.stop();
        }
        if (state.mediaStream) {
            state.mediaStream.getTracks().forEach(function (track) { track.stop(); });
            state.mediaStream = null;
        }
        if (state.socket && state.socket.readyState === WebSocket.OPEN) {
            sendJson({ type: "end_consultation" });
        }
        updateStatus(elements.cameraStatus, "Camera off");
        updateStatus(elements.micStatus, "Mic off");
    }

    function bindEvents() {
        elements.startConsultationButton?.addEventListener("click", startConsultation);

        elements.micToggleButton?.addEventListener("click", async function () {
            if (!state.connected || !state.mediaStream) {
                await startConsultation();
            }
            if (state.listening) {
                stopSpeechRecognition();
                return;
            }
            startSpeechRecognition();
        });

        elements.sendMessageButton?.addEventListener("click", function () {
            const text = elements.manualMessage?.value.trim();
            if (!text) return;
            sendJson({ type: "user_text", text: text });
            elements.manualMessage.value = "";
        });

        elements.emergencyButton?.addEventListener("click", function () {
            if (elements.safetyInsights) {
                elements.safetyInsights.textContent = "Emergency support requested. Call 911 immediately if there is chest pain, trouble breathing, severe bleeding, seizure, or suicidal thoughts.";
            }
            alert("If this is an emergency, call 911 immediately or go to the nearest hospital.");
            window.location.href = `tel:${config.emergencyPhone || "911"}`;
        });

        elements.endConsultationButton?.addEventListener("click", stopConsultation);
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindEvents();
        connectWebSocket();
    });

    window.addEventListener("beforeunload", function () {
        stopConsultation();
    });
})();
