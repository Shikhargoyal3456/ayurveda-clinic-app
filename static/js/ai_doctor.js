(function () {
    const config = window.AI_DOCTOR_CONFIG || {};
    const state = {
        listening: false,
        recognition: null,
        messages: [],
    };

    function escapeHtml(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function ensureElements() {
        const container = document.querySelector(".ai-doctor-container") || document.body;
        let chatMessages = document.getElementById("chatMessages");
        let chatInput = document.getElementById("chatInput");
        let sendButton = document.getElementById("sendButton");
        let voiceButton = document.getElementById("voiceButton");
        let quickActions = document.getElementById("quickActions");

        if (!chatMessages) {
            chatMessages = document.createElement("div");
            chatMessages.id = "chatMessages";
            chatMessages.className = "chat-window";
            container.appendChild(chatMessages);
        }
        if (!chatInput) {
            chatInput = document.createElement("textarea");
            chatInput.id = "chatInput";
            chatInput.rows = 2;
            chatInput.placeholder = "Type your message or speak in Hindi...";
            chatInput.className = "form-control";
            container.appendChild(chatInput);
        }
        if (!sendButton) {
            sendButton = document.createElement("button");
            sendButton.id = "sendButton";
            sendButton.type = "button";
            sendButton.className = "doctor-cta doctor-cta--primary";
            sendButton.textContent = "Send";
            container.appendChild(sendButton);
        }
        if (!voiceButton) {
            voiceButton = document.createElement("button");
            voiceButton.id = "voiceButton";
            voiceButton.type = "button";
            voiceButton.className = "doctor-cta doctor-cta--secondary";
            voiceButton.textContent = "🎙 Voice";
            container.appendChild(voiceButton);
        }
        if (!quickActions) {
            quickActions = document.createElement("div");
            quickActions.id = "quickActions";
            quickActions.className = "quick-actions";
            quickActions.innerHTML = `
                <button type="button" class="doctor-cta doctor-cta--secondary quick-action-btn" data-action="summary">Summary</button>
                <button type="button" class="doctor-cta doctor-cta--secondary quick-action-btn" data-action="prescribe">Prescribe</button>
                <button type="button" class="doctor-cta doctor-cta--secondary quick-action-btn" data-action="follow-up">Follow-up</button>
            `;
            container.appendChild(quickActions);
        }

        return { chatMessages, chatInput, sendButton, voiceButton, quickActions };
    }

    function appendMessage(role, text, extraClass = "") {
        const { chatMessages } = ensureElements();
        const message = document.createElement("div");
        message.className = `message ${role}${extraClass ? ` ${extraClass}` : ""}`;
        const icon = role === "user" ? "👤" : "🩺";
        message.innerHTML = `
            <div class="message-content">
                <span class="message-icon">${icon}</span>
                <span class="message-text">${escapeHtml(text)}</span>
            </div>
        `;
        chatMessages.appendChild(message);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function setQuickActions(actions) {
        const { quickActions } = ensureElements();
        if (!quickActions || !actions) return;
        quickActions.innerHTML = `
            <button type="button" class="doctor-cta doctor-cta--secondary quick-action-btn" data-action="summary">${escapeHtml(actions.summary || "Summary")}</button>
            <button type="button" class="doctor-cta doctor-cta--secondary quick-action-btn" data-action="prescribe">${escapeHtml(actions.prescription || "Prescribe")}</button>
            <button type="button" class="doctor-cta doctor-cta--secondary quick-action-btn" data-action="follow-up">${escapeHtml(actions.follow_up || "Follow-up")}</button>
        `;
    }

    function mockAssistantResponse(message) {
        const normalized = message.toLowerCase();
        if (normalized.includes("fever") || normalized.includes("bukhar") || normalized.includes("ज्वर")) {
            return {
                response: "आपके लक्षणों से शरीर में गर्मी या सूजन का संकेत मिल सकता है. आराम करें, पर्याप्त तरल लें, और तेज बुखार हो तो डॉक्टर से मिलें.",
                actions: {
                    summary: "बुखार/गर्मी जैसे लक्षण. तरल, आराम, और निगरानी रखें.",
                    prescription: "गिलोय, गुनगुना पानी, और हल्का भोजन पर विचार करें.",
                    follow_up: "24-48 घंटे में या लक्षण बढ़ने पर फॉलो-अप करें.",
                },
            };
        }
        if (normalized.includes("acidity") || normalized.includes("gas") || normalized.includes("stomach") || normalized.includes("पेट")) {
            return {
                response: "यह पाचन अग्नि से जुड़ी समस्या हो सकती है. देर रात भोजन से बचें, हल्का आहार लें, और दिनचर्या नियमित रखें.",
                actions: {
                    summary: "पाचन असंतुलन की संभावना. भारी भोजन कम करें.",
                    prescription: "त्रिफला रात में, गुनगुना पानी, और तला हुआ भोजन कम करें.",
                    follow_up: "7 दिन में पुनः समीक्षा करें.",
                },
            };
        }
        return {
            response: "मैं आपकी बात समझ रहा हूं. आयुर्वेदिक दृष्टि से हम लक्षणों, दिनचर्या, और आहार के आधार पर आगे बढ़ सकते हैं.",
            actions: {
                summary: "संक्षिप्त आयुर्वेदिक समीक्षा तैयार करें.",
                prescription: "लक्षणों के अनुसार हल्का, पचने योग्य आहार सुझाएं.",
                follow_up: "एक सप्ताह के भीतर फॉलो-अप रखें.",
            },
        };
    }

    async function sendMessage(forcedMessage = "") {
        const { chatInput, sendButton } = ensureElements();
        const message = String(forcedMessage || chatInput?.value || "").trim();
        if (!message) return null;
        if (sendButton) sendButton.disabled = true;

        appendMessage("user", message);
        const typingNode = document.createElement("div");
        typingNode.className = "message ai typing";
        typingNode.innerHTML = "<em>Typing...</em>";
        ensureElements().chatMessages.appendChild(typingNode);
        ensureElements().chatMessages.scrollTop = ensureElements().chatMessages.scrollHeight;
        if (chatInput) chatInput.value = "";

        try {
            const response = await fetch("/api/ai-chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
            });
            const payload = await response.json().catch(() => ({}));
            typingNode?.remove();
            if (!response.ok) {
                const fallback = mockAssistantResponse(message);
                appendMessage("ai", payload.detail || payload.error || fallback.response, "action");
                setQuickActions(fallback.actions);
                state.messages.push({ role: "user", text: message }, { role: "ai", text: fallback.response });
                window.KashUI?.showToast?.(payload.detail || "AI assistant unavailable. Showing a fallback response.", "warning");
                return fallback;
            }
            const modelInfo = payload.model ? ` (${payload.model})` : "";
            appendMessage("ai", `${payload.response || "मैं आपकी मदद कर रहा हूं."}${modelInfo}`, "action");
            setQuickActions(payload.actions || {});
            state.messages.push({ role: "user", text: message }, { role: "ai", text: payload.response || "" });
            return payload;
        } catch (error) {
            typingNode?.remove();
            const fallback = mockAssistantResponse(message);
            appendMessage("ai", fallback.response, "action");
            setQuickActions(fallback.actions);
            window.KashUI?.showToast?.("Could not reach the AI assistant. You can retry the message.", "error");
            return fallback;
        } finally {
            if (sendButton) sendButton.disabled = false;
        }
    }

    function handleActions(action) {
        const prompts = {
            summary: "Please provide a concise Ayurvedic summary.",
            prescribe: "Suggest a gentle Ayurvedic prescription.",
            "follow-up": "Tell me the follow-up timeline.",
        };
        return sendMessage(prompts[action] || action);
    }

    function initVoiceInput() {
        const { voiceButton } = ensureElements();
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition || !voiceButton) {
            if (voiceButton) voiceButton.disabled = true;
            return;
        }

        voiceButton.addEventListener("click", () => {
            if (!state.recognition) {
                state.recognition = new SpeechRecognition();
                state.recognition.lang = "hi-IN";
                state.recognition.continuous = false;
                state.recognition.interimResults = false;
                state.recognition.onresult = (event) => {
                    const transcript = event.results?.[0]?.[0]?.transcript || "";
                    const input = document.getElementById("chatInput");
                    if (input) input.value = transcript;
                    void sendMessage(transcript);
                };
                state.recognition.onerror = (event) => {
                    state.listening = false;
                    voiceButton.textContent = "🎙 Voice";
                    voiceButton.disabled = false;
                    const reason = event?.error === "not-allowed"
                        ? "Microphone permission is blocked. Please allow mic access in the browser, or type your message."
                        : "Voice input could not start. Please type your message or try again.";
                    appendMessage("ai", reason, "action");
                    window.KashUI?.showToast?.(reason, "warning");
                };
                state.recognition.onend = () => {
                    state.listening = false;
                    voiceButton.textContent = "🎙 Voice";
                    voiceButton.disabled = false;
                };
            }
            if (!state.listening) {
                state.listening = true;
                voiceButton.textContent = "Listening...";
                try {
                    state.recognition.start();
                } catch (_error) {
                    state.listening = false;
                    voiceButton.textContent = "🎙 Voice";
                    appendMessage("ai", "Voice input is already starting. Please wait a moment or type your message.", "action");
                }
            } else {
                state.listening = false;
                state.recognition.stop();
            }
        });
    }

    function bindEvents() {
        const { chatInput, sendButton, quickActions } = ensureElements();
        sendButton?.addEventListener("click", () => void sendMessage());
        chatInput?.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage();
            }
        });
        quickActions?.addEventListener("click", (event) => {
            const target = event.target instanceof HTMLElement ? event.target.closest("[data-action]") : null;
            if (!target) return;
            void handleActions(target.getAttribute("data-action") || "");
        });
        if (!document.getElementById("chatMessages")?.children.length) {
            appendMessage("ai", "नमस्ते. मैं आपकी Ayurvedic AI assistant हूं. अपनी समस्या बताइए.");
        }
    }

    window.sendMessage = sendMessage;
    window.handleActions = handleActions;
    window.escapeHtml = escapeHtml;

    document.addEventListener("DOMContentLoaded", () => {
        ensureElements();
        bindEvents();
        initVoiceInput();
        console.log("AI Doctor chat initialized");
    });
})();
