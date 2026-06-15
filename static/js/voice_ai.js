(function () {
    const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition || null;

    function normalizeError(errorCode) {
        switch (errorCode) {
            case "not-allowed":
            case "service-not-allowed":
                return "Microphone access was not allowed.";
            case "audio-capture":
                return "No microphone was detected.";
            case "network":
                return "Voice recognition had a network issue.";
            case "no-speech":
                return "No speech was detected. Please try again.";
            default:
                return "Voice input is not available right now.";
        }
    }

    function captureOnce(options) {
        const config = options || {};
        return new Promise((resolve, reject) => {
            if (!SpeechRecognitionCtor) {
                reject(new Error("Voice input is not supported on this browser."));
                return;
            }

            const recognition = new SpeechRecognitionCtor();
            let transcript = "";
            let settled = false;
            const timeoutMs = Number(config.timeoutMs || 15000);

            recognition.lang = config.language && config.language !== "auto" ? config.language : "en-IN";
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;

            const finish = (handler, value) => {
                if (settled) {
                    return;
                }
                settled = true;
                window.clearTimeout(timeoutId);
                handler(value);
            };

            recognition.onstart = () => {
                if (typeof config.onStateChange === "function") {
                    config.onStateChange("listening");
                }
            };

            recognition.onresult = (event) => {
                let partial = "";
                for (let index = event.resultIndex; index < event.results.length; index += 1) {
                    const result = event.results[index];
                    const text = String(result[0]?.transcript || "").trim();
                    if (!text) {
                        continue;
                    }
                    if (result.isFinal) {
                        transcript = `${transcript} ${text}`.trim();
                    } else {
                        partial = `${partial} ${text}`.trim();
                    }
                }
                if (typeof config.onPartial === "function") {
                    config.onPartial(partial || transcript);
                }
            };

            recognition.onerror = (event) => {
                if (typeof config.onStateChange === "function") {
                    config.onStateChange("error");
                }
                finish(reject, new Error(normalizeError(event.error)));
            };

            recognition.onend = () => {
                if (settled) {
                    return;
                }
                if (transcript) {
                    if (typeof config.onStateChange === "function") {
                        config.onStateChange("processing");
                    }
                    finish(resolve, transcript);
                    return;
                }
                finish(reject, new Error("No speech was detected. Please try again."));
            };

            const timeoutId = window.setTimeout(() => {
                try {
                    recognition.stop();
                } catch (error) {
                    finish(reject, error instanceof Error ? error : new Error("Voice input timed out."));
                }
            }, timeoutMs);

            try {
                recognition.start();
            } catch (error) {
                finish(reject, error instanceof Error ? error : new Error("Voice input could not start."));
            }
        });
    }

    window.KashVoiceAI = {
        isSupported: Boolean(SpeechRecognitionCtor),
        captureOnce,
    };
})();
