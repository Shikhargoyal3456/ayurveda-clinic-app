(function () {
    const config = window.AI_DOCTOR_LIVE_CONFIG || {};
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
        listening: false,
        started: false,
        speaking: false,
        currentInterimTranscript: "",
        canUseSpeechRecognition: "webkitSpeechRecognition" in window || "SpeechRecognition" in window,
    };

    const elements = {
        video: document.getElementById("liveDoctorVideo"),
        cameraLabel: document.getElementById("cameraLabel"),
        connectionLabel: document.getElementById("connectionLabel"),
        cameraPrompt: document.getElementById("cameraPrompt"),
        conversationState: document.getElementById("conversationState"),
        conversationHint: document.getElementById("conversationHint"),
        waveform: document.getElementById("waveform"),
        startButton: document.getElementById("startConsultationButton"),
        endButton: document.getElementById("endConsultationButton"),
        transcriptBox: document.getElementById("transcriptBox"),
        patientLiveTranscript: document.getElementById("patientLiveTranscript"),
        doctorLiveTranscript: document.getElementById("doctorLiveTranscript"),
        emergencyPanel: document.getElementById("emergencyPanel"),
        emergencyMessage: document.getElementById("emergencyMessage"),
        emergencyButton: document.getElementById("emergencyButton"),
    };

    function updateText(target, text) {
        if (target) {
            target.textContent = text;
        }
    }

    function setWaveformActive(active) {
        if (!elements.waveform) {
            return;
        }
        elements.waveform.classList.toggle("is-active", Boolean(active));
    }

    function appendTranscript(role, text) {
        if (!elements.transcriptBox || !text) {
            return;
        }
        const item = document.createElement("article");
        item.className = `live-doctor-line live-doctor-line--${role}`;
        const label = document.createElement("span");
        label.textContent = role === "patient" ? "You" : role === "doctor" ? "Dr. Kash" : "System";
        const body = document.createElement("p");
        body.textContent = text;
        item.append(label, body);
        elements.transcriptBox.appendChild(item);
        elements.transcriptBox.scrollTop = elements.transcriptBox.scrollHeight;
    }

    function sendJson(payload) {
        if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
            return;
        }
        state.socket.send(JSON.stringify(payload));
    }

    function speak(text) {
        if (!("speechSynthesis" in window) || !text) {
            return;
        }
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.98;
        utterance.pitch = 1;
        utterance.lang = "en-US";
        utterance.onstart = function () {
            state.speaking = true;
            updateText(elements.conversationState, "Dr. Kash is speaking");
            updateText(elements.conversationHint, "You can interrupt naturally by speaking again.");
            setWaveformActive(true);
        };
        utterance.onend = function () {
            state.speaking = false;
            updateText(elements.conversationState, state.listening ? "Listening to you" : "Ready when you are");
            updateText(elements.conversationHint, "Keep talking naturally. Dr. Kash will ask the next best question.");
            setWaveformActive(state.listening);
        };
        utterance.onerror = function () {
            state.speaking = false;
            setWaveformActive(state.listening);
        };
        window.speechSynthesis.speak(utterance);
    }

    function showEmergency(message) {
        if (elements.emergencyPanel) {
            elements.emergencyPanel.hidden = false;
        }
        updateText(
            elements.emergencyMessage,
            message || "This sounds concerning. Please seek immediate medical attention."
        );
    }

    function hideEmergency() {
        if (elements.emergencyPanel) {
            elements.emergencyPanel.hidden = true;
        }
    }

    function handleServerEvent(event) {
        switch (event.type) {
            case "session_ready":
                updateText(elements.connectionLabel, "Connected");
                updateText(elements.conversationState, "Listening to you");
                updateText(elements.conversationHint, "Tell Dr. Kash what is happening and show the affected area if useful.");
                break;
            case "status":
                if (event.status === "connected") {
                    updateText(elements.connectionLabel, "Connected");
                }
                if (event.detail) {
                    updateText(elements.cameraPrompt, event.detail);
                }
                break;
            case "transcript":
                appendTranscript("patient", event.text);
                updateText(elements.patientLiveTranscript, event.text);
                break;
            case "ai_message":
                appendTranscript("doctor", event.text);
                updateText(elements.doctorLiveTranscript, event.text);
                speak(event.text);
                break;
            case "vision_update":
                updateText(elements.cameraPrompt, event.text);
                break;
            case "emergency":
                showEmergency(
                    event.text || "This sounds concerning. Please seek immediate medical attention."
                );
                appendTranscript("system", event.text || "Emergency guidance triggered.");
                break;
            case "error":
                appendTranscript("system", event.message || "The consultation connection was interrupted.");
                updateText(elements.connectionLabel, "Connection issue");
                break;
            case "consultation_summary":
                appendTranscript("system", "Consultation ended. Remember, a real doctor should confirm any diagnosis.");
                break;
            default:
                break;
        }
    }

    function bindSocket() {
        if (!websocketUrl) {
            appendTranscript("system", "Live doctor connection is unavailable on this page.");
            return Promise.resolve();
        }
        if (state.socket && (state.socket.readyState === WebSocket.OPEN || state.socket.readyState === WebSocket.CONNECTING)) {
            return Promise.resolve();
        }

        return new Promise(function (resolve, reject) {
            state.socket = new WebSocket(websocketUrl);

            state.socket.addEventListener("open", function () {
                updateText(elements.connectionLabel, "Connecting Dr. Kash");
                resolve();
            });

            state.socket.addEventListener("message", function (message) {
                try {
                    handleServerEvent(JSON.parse(message.data));
                } catch (_error) {
                    appendTranscript("system", "Received an unreadable message from the AI doctor service.");
                }
            });

            state.socket.addEventListener("close", function () {
                updateText(elements.connectionLabel, "Disconnected");
                setWaveformActive(false);
                state.socket = null;
            });

            state.socket.addEventListener("error", function () {
                updateText(elements.connectionLabel, "Connection issue");
                reject(new Error("socket_error"));
            });
        });
    }

    async function startMedia() {
        if (state.mediaStream) {
            return state.mediaStream;
        }
        state.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        if (elements.video) {
            elements.video.srcObject = state.mediaStream;
        }
        updateText(elements.cameraLabel, "Camera live");
        updateText(elements.cameraPrompt, "Show the area clearly. Dr. Kash will review frames during the consultation.");
        return state.mediaStream;
    }

    function startFrameCapture() {
        if (state.frameTimer) {
            window.clearInterval(state.frameTimer);
        }
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        state.frameTimer = window.setInterval(function () {
            if (!state.socket || state.socket.readyState !== WebSocket.OPEN || !elements.video || elements.video.readyState < 2) {
                return;
            }
            canvas.width = elements.video.videoWidth || 640;
            canvas.height = elements.video.videoHeight || 480;
            context.drawImage(elements.video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL("image/jpeg", 0.75);
            sendJson({
                type: "video_frame",
                mime_type: "image/jpeg",
                image: dataUrl.split(",")[1],
            });
        }, 2000);
    }

    function startAudioRecorder() {
        if (!state.mediaStream || typeof MediaRecorder === "undefined" || state.mediaRecorder) {
            return;
        }
        try {
            state.mediaRecorder = new MediaRecorder(state.mediaStream, { mimeType: "audio/webm" });
        } catch (_error) {
            return;
        }
        state.mediaRecorder.addEventListener("dataavailable", function (event) {
            if (!event.data || !event.data.size) {
                return;
            }
            const reader = new FileReader();
            reader.onloadend = function () {
                const result = typeof reader.result === "string" ? reader.result : "";
                const base64 = result.split(",")[1];
                if (base64) {
                    sendJson({
                        type: "audio_chunk",
                        mime_type: event.data.type || "audio/webm",
                        audio: base64,
                    });
                }
            };
            reader.readAsDataURL(event.data);
        });
        state.mediaRecorder.start(1200);
    }

    function startSpeechRecognition() {
        if (!state.canUseSpeechRecognition) {
            appendTranscript("system", "Live browser transcription is not supported here, but camera and audio streaming are active.");
            return;
        }
        const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
        state.recognition = new RecognitionClass();
        state.recognition.lang = "en-US";
        state.recognition.continuous = true;
        state.recognition.interimResults = true;

        state.recognition.onstart = function () {
            state.listening = true;
            updateText(elements.conversationState, "Listening to you");
            updateText(elements.conversationHint, "Speak naturally. Dr. Kash will respond with voice.");
            setWaveformActive(true);
        };

        state.recognition.onresult = function (event) {
            let finalTranscript = "";
            let interimTranscript = "";

            if (state.speaking && "speechSynthesis" in window) {
                window.speechSynthesis.cancel();
            }

            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const transcript = event.results[i][0].transcript.trim();
                if (event.results[i].isFinal) {
                    finalTranscript += `${transcript} `;
                } else {
                    interimTranscript += `${transcript} `;
                }
            }

            const cleanInterim = interimTranscript.trim();
            if (cleanInterim) {
                state.currentInterimTranscript = cleanInterim;
                updateText(elements.patientLiveTranscript, cleanInterim);
                updateText(elements.conversationState, "You are speaking");
                updateText(elements.conversationHint, "Keep going. Dr. Kash is listening in real time.");
            }

            const cleanFinal = finalTranscript.trim();
            if (cleanFinal) {
                state.currentInterimTranscript = "";
                updateText(elements.patientLiveTranscript, cleanFinal);
                sendJson({ type: "user_text", text: cleanFinal });
            }
        };

        state.recognition.onerror = function () {
            updateText(elements.conversationState, "Microphone issue");
            updateText(elements.conversationHint, "Please allow microphone access and try again.");
            setWaveformActive(false);
        };

        state.recognition.onend = function () {
            if (state.started && state.listening) {
                state.recognition.start();
                return;
            }
            state.listening = false;
            updateText(elements.conversationState, "Consultation paused");
            updateText(elements.conversationHint, "Tap Start Consultation to reconnect.");
            setWaveformActive(false);
        };

        state.recognition.start();
    }

    async function startConsultation() {
        if (state.started) {
            return;
        }
        hideEmergency();
        updateText(elements.connectionLabel, "Starting");
        updateText(elements.conversationState, "Preparing live consultation");
        updateText(elements.conversationHint, "Requesting camera and microphone access.");

        try {
            await bindSocket();
            await startMedia();
            startFrameCapture();
            startAudioRecorder();
            startSpeechRecognition();
            state.started = true;
            if (elements.startButton) {
                elements.startButton.hidden = true;
            }
            if (elements.endButton) {
                elements.endButton.hidden = false;
            }
        } catch (_error) {
            updateText(elements.connectionLabel, "Could not start");
            updateText(elements.conversationState, "Start failed");
            updateText(elements.conversationHint, "Please allow camera and microphone access, then try again.");
            appendTranscript("system", "The live AI doctor session could not start. Please refresh and try again.");
        }
    }

    function stopConsultation() {
        state.started = false;
        state.listening = false;
        setWaveformActive(false);
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
        }
        if (state.recognition) {
            state.recognition.stop();
            state.recognition = null;
        }
        if (state.frameTimer) {
            window.clearInterval(state.frameTimer);
            state.frameTimer = null;
        }
        if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
            state.mediaRecorder.stop();
        }
        state.mediaRecorder = null;
        if (state.mediaStream) {
            state.mediaStream.getTracks().forEach(function (track) {
                track.stop();
            });
            state.mediaStream = null;
        }
        if (state.socket && state.socket.readyState === WebSocket.OPEN) {
            sendJson({ type: "end_consultation" });
            state.socket.close();
        }
        state.socket = null;
        updateText(elements.cameraLabel, "Camera off");
        updateText(elements.connectionLabel, "Consultation ended");
        updateText(elements.cameraPrompt, "Tap Start Consultation to begin again.");
        updateText(elements.conversationState, "Consultation ended");
        updateText(elements.conversationHint, "Remember, a real doctor should confirm any diagnosis.");
        if (elements.startButton) {
            elements.startButton.hidden = false;
        }
        if (elements.endButton) {
            elements.endButton.hidden = true;
        }
    }

    function bindEvents() {
        elements.startButton?.addEventListener("click", startConsultation);
        elements.endButton?.addEventListener("click", stopConsultation);
        elements.emergencyButton?.addEventListener("click", function () {
            showEmergency("Stay calm. Help is on the way. If you can, tell someone nearby your location and call 112 now.");
        });
        window.addEventListener("beforeunload", stopConsultation);
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindEvents();
    });
})();
