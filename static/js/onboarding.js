const onboardingSteps = [
    {
        element: ".action-btn:first-child",
        title: "💊 Order Medicines",
        description: "Tap here to search and buy medicines",
        position: "bottom",
    },
    {
        element: ".action-btn:nth-child(2)",
        title: "📄 Upload Prescription",
        description: "Take a photo of your prescription. AI will read it!",
        position: "bottom",
    },
    {
        element: ".action-btn:nth-child(3)",
        title: "📦 Track Order",
        description: "See exactly where your medicine is",
        position: "bottom",
    },
];

let onboardingIndex = 0;
let onboardingOverlay = null;

function buildOnboardingStyles() {
    if (document.getElementById("kashOnboardingStyles")) return;
    const style = document.createElement("style");
    style.id = "kashOnboardingStyles";
    style.textContent = `
        .kash-onboarding-overlay {
            position: fixed;
            inset: 0;
            background: rgba(15, 23, 42, 0.42);
            z-index: 9998;
        }
        .kash-onboarding-card {
            position: fixed;
            max-width: 320px;
            background: white;
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.24);
            z-index: 9999;
        }
        .kash-onboarding-card h3 {
            margin: 0 0 8px;
            font-size: 18px;
            color: #0F4C5C;
        }
        .kash-onboarding-card p {
            margin: 0 0 14px;
            color: #475569;
            line-height: 1.5;
        }
        .kash-onboarding-actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }
        .kash-onboarding-actions button {
            border: none;
            border-radius: 999px;
            padding: 9px 14px;
            font-weight: 700;
            cursor: pointer;
        }
        .kash-onboarding-skip {
            background: #E2E8F0;
            color: #334155;
        }
        .kash-onboarding-next {
            background: #0F4C5C;
            color: white;
        }
        .kash-onboarding-highlight {
            position: relative;
            z-index: 9999;
            box-shadow: 0 0 0 5px rgba(255, 215, 0, 0.55);
            border-radius: 20px;
        }
    `;
    document.head.appendChild(style);
}

function clearOnboarding() {
    document.querySelectorAll(".kash-onboarding-highlight").forEach((node) => {
        node.classList.remove("kash-onboarding-highlight");
    });
    onboardingOverlay?.remove();
    onboardingOverlay = null;
}

function finishOnboarding() {
    localStorage.setItem("kash_onboarding_completed", "true");
    clearOnboarding();
}

function placeCard(card, target, position) {
    if (!target) {
        card.style.top = "24px";
        card.style.left = "50%";
        card.style.transform = "translateX(-50%)";
        return;
    }

    const rect = target.getBoundingClientRect();
    const top = position === "bottom" ? rect.bottom + 16 : Math.max(16, rect.top - 180);
    const left = Math.min(window.innerWidth - 336, Math.max(16, rect.left));
    card.style.top = `${top}px`;
    card.style.left = `${left}px`;
}

function renderOnboardingStep() {
    clearOnboarding();
    const step = onboardingSteps[onboardingIndex];
    if (!step) {
        finishOnboarding();
        return;
    }

    const target = document.querySelector(step.element);
    if (!target) {
        finishOnboarding();
        return;
    }

    buildOnboardingStyles();
    target.classList.add("kash-onboarding-highlight");

    onboardingOverlay = document.createElement("div");
    onboardingOverlay.className = "kash-onboarding-overlay";

    const card = document.createElement("div");
    card.className = "kash-onboarding-card";
    card.innerHTML = `
        <h3>${step.title}</h3>
        <p>${step.description}</p>
        <div class="kash-onboarding-actions">
            <button type="button" class="kash-onboarding-skip">Skip</button>
            <button type="button" class="kash-onboarding-next">${onboardingIndex === onboardingSteps.length - 1 ? "Done" : "Next"}</button>
        </div>
    `;

    onboardingOverlay.appendChild(card);
    document.body.appendChild(onboardingOverlay);
    placeCard(card, target, step.position);

    card.querySelector(".kash-onboarding-skip")?.addEventListener("click", finishOnboarding);
    card.querySelector(".kash-onboarding-next")?.addEventListener("click", () => {
        onboardingIndex += 1;
        renderOnboardingStep();
    });
}

function showOnboarding() {
    onboardingIndex = 0;
    renderOnboardingStep();
}

document.addEventListener("DOMContentLoaded", () => {
    if (!document.querySelector(".action-btn")) return;
    if (!localStorage.getItem("kash_onboarding_completed")) {
        setTimeout(() => {
            showOnboarding();
        }, 1000);
    }
});
