(function () {
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
    }

    function setLoading(button, loading, idleText, loadingText) {
        if (!button) {
            return;
        }
        button.disabled = Boolean(loading);
        button.textContent = loading ? loadingText : idleText;
    }

    function renderList(host, items) {
        if (!host) {
            return;
        }
        host.innerHTML = "";
        (Array.isArray(items) ? items : []).forEach((item) => {
            const li = document.createElement("li");
            li.textContent = String(item || "").trim();
            host.appendChild(li);
        });
    }

    function bindSymptomAnalyzer() {
        const form = document.getElementById("symptomAnalyzerForm");
        if (!form) {
            return;
        }

        const input = document.getElementById("symptomInput");
        const resultsPanel = document.getElementById("symptomResultsPanel");
        const emptyState = document.getElementById("symptomResultsEmpty");
        const errorBox = document.getElementById("symptomError");
        const summary = document.getElementById("symptomSummary");
        const urgencyBadge = document.getElementById("symptomUrgencyBadge");
        const conditions = document.getElementById("symptomConditions");
        const actions = document.getElementById("symptomActions");
        const seeDoctor = document.getElementById("symptomSeeDoctor");
        const homeCare = document.getElementById("symptomHomeCare");
        const disclaimer = document.getElementById("symptomDisclaimer");
        const submitButton = document.getElementById("symptomAnalyzeButton");
        const demoButton = document.getElementById("symptomDemoButton");
        const voiceButton = document.getElementById("symptomVoiceButton");
        const voiceStatus = document.getElementById("symptomVoiceStatus");
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;

        if (demoButton && input) {
            demoButton.addEventListener("click", function () {
                input.value = "I have throat pain, mild fever, headache, and tiredness since last night. Swallowing hurts more in the morning.";
                input.focus();
            });
        }

        if (SpeechRecognition && voiceButton && input) {
            const recognition = new SpeechRecognition();
            recognition.lang = "en-IN";
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            recognition.onstart = function () {
                voiceButton.classList.add("is-listening");
                voiceButton.textContent = "Listening...";
                if (voiceStatus) {
                    voiceStatus.textContent = "Listening now. Speak naturally and pause when you finish.";
                }
            };

            recognition.onresult = function (event) {
                const text = event.results?.[0]?.[0]?.transcript || "";
                input.value = String(text).trim();
            };

            recognition.onerror = function () {
                if (voiceStatus) {
                    voiceStatus.textContent = "Voice input was not available just now. You can continue by typing.";
                }
            };

            recognition.onend = function () {
                voiceButton.classList.remove("is-listening");
                voiceButton.textContent = "🎙️ Speak";
            };

            voiceButton.addEventListener("click", function () {
                try {
                    recognition.start();
                } catch (_error) {
                    if (voiceStatus) {
                        voiceStatus.textContent = "Voice input is already running or unavailable. You can type instead.";
                    }
                }
            });
        } else if (voiceButton) {
            voiceButton.disabled = true;
            if (voiceStatus) {
                voiceStatus.textContent = "Voice input is not supported on this device. Text entry still works normally.";
            }
        }

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const symptomText = String(input?.value || "").trim();
            if (!symptomText) {
                window.showToast?.("Please describe your symptoms first.", "warning");
                input?.focus();
                return;
            }

            const formData = new FormData();
            formData.append("symptoms", symptomText);

            setLoading(submitButton, true, "Analyze Symptoms", "Analyzing...");
            if (emptyState) {
                emptyState.hidden = true;
            }
            if (errorBox) {
                errorBox.hidden = true;
                errorBox.textContent = "";
            }
            if (resultsPanel) {
                resultsPanel.hidden = false;
                resultsPanel.style.opacity = "0.6";
            }

            try {
                const response = await fetch("/api/patient/symptom-analyze", {
                    method: "POST",
                    headers: { "X-CSRF-Token": getCsrfToken() },
                    body: formData,
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(payload.detail || payload.error || "Unable to analyze symptoms right now.");
                }

                if (summary) {
                    summary.textContent = payload.summary || "";
                }
                if (urgencyBadge) {
                    urgencyBadge.textContent = payload.urgency || "ROUTINE";
                    urgencyBadge.dataset.urgency = payload.urgency || "ROUTINE";
                }
                if (conditions) {
                    conditions.innerHTML = "";
                    (payload.conditions || []).forEach((item) => {
                        const card = document.createElement("article");
                        card.className = "patient-tool-condition";
                        const meta = document.createElement("div");
                        meta.className = "patient-tool-condition__meta";
                        const title = document.createElement("strong");
                        title.textContent = item.name || "Possible condition";
                        const confidence = document.createElement("span");
                        confidence.textContent = `${item.confidence || 0}% confidence`;
                        meta.append(title, confidence);
                        const reason = document.createElement("p");
                        reason.textContent = item.reason || "";
                        card.append(meta, reason);
                        conditions.appendChild(card);
                    });
                }
                renderList(actions, payload.actions || []);
                renderList(seeDoctor, payload.see_doctor_when || []);
                renderList(homeCare, payload.home_care || []);
                if (disclaimer) {
                    disclaimer.textContent = payload.disclaimer || "";
                }
            } catch (error) {
                if (errorBox) {
                    errorBox.hidden = false;
                    errorBox.textContent = String(error.message || "Unable to analyze symptoms right now.");
                }
                if (resultsPanel) {
                    resultsPanel.hidden = true;
                }
            } finally {
                setLoading(submitButton, false, "Analyze Symptoms", "Analyzing...");
                if (resultsPanel) {
                    resultsPanel.style.opacity = "1";
                }
            }
        });
    }

    function bindDietAnalyzer() {
        const form = document.getElementById("dietAnalyzerForm");
        if (!form) {
            return;
        }

        const description = document.getElementById("mealDescription");
        const imageInput = document.getElementById("foodImage");
        const resultsPanel = document.getElementById("dietResultsPanel");
        const emptyState = document.getElementById("dietResultsEmpty");
        const errorBox = document.getElementById("dietError");
        const summary = document.getElementById("dietSummary");
        const calories = document.getElementById("dietCalories");
        const quality = document.getElementById("dietQuality");
        const impact = document.getElementById("dietImpact");
        const breakdown = document.getElementById("dietBreakdown");
        const concerns = document.getElementById("dietConcerns");
        const recommendations = document.getElementById("dietRecommendations");
        const disclaimer = document.getElementById("dietDisclaimer");
        const submitButton = document.getElementById("dietAnalyzeButton");
        const demoButton = document.getElementById("dietDemoButton");

        if (demoButton && description) {
            demoButton.addEventListener("click", function () {
                description.value = "Breakfast was vegetable poha with peanuts, one cup chai with sugar, and a banana.";
                description.focus();
            });
        }

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const mealText = String(description?.value || "").trim();
            const imageFile = imageInput?.files?.[0];
            if (!mealText && !imageFile) {
                window.showToast?.("Please add a meal description or upload a food image.", "warning");
                description?.focus();
                return;
            }

            const formData = new FormData();
            if (mealText) {
                formData.append("meal_description", mealText);
            }
            if (imageFile) {
                formData.append("food_image", imageFile);
            }

            setLoading(submitButton, true, "Analyze Meal", "Analyzing...");
            if (emptyState) {
                emptyState.hidden = true;
            }
            if (errorBox) {
                errorBox.hidden = true;
                errorBox.textContent = "";
            }
            if (resultsPanel) {
                resultsPanel.hidden = false;
                resultsPanel.style.opacity = "0.6";
            }

            try {
                const response = await fetch("/api/patient/diet-analyze", {
                    method: "POST",
                    headers: { "X-CSRF-Token": getCsrfToken() },
                    body: formData,
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(payload.detail || payload.error || "Unable to analyze that meal right now.");
                }

                if (summary) {
                    summary.textContent = payload.summary || "";
                }
                if (calories) {
                    calories.textContent = payload.calorie_estimate || "";
                }
                if (quality) {
                    quality.textContent = payload.nutritional_quality || "";
                }
                if (impact) {
                    impact.textContent = payload.health_impact || "";
                }
                renderList(breakdown, payload.nutritional_breakdown || []);
                renderList(concerns, payload.concerns || []);
                renderList(recommendations, payload.recommendations || []);
                if (disclaimer) {
                    disclaimer.textContent = payload.disclaimer || "";
                }
            } catch (error) {
                if (errorBox) {
                    errorBox.hidden = false;
                    errorBox.textContent = String(error.message || "Unable to analyze that meal right now.");
                }
                if (resultsPanel) {
                    resultsPanel.hidden = true;
                }
            } finally {
                setLoading(submitButton, false, "Analyze Meal", "Analyzing...");
                if (resultsPanel) {
                    resultsPanel.style.opacity = "1";
                }
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindSymptomAnalyzer();
        bindDietAnalyzer();
    });
})();
