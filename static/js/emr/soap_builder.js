const SOAPBuilder = {
    templates: {
        hypertension: {
            subjective: "Headache, dizziness, and elevated home BP log.",
            objective: "BP elevated on exam. No acute distress.",
            assessment: "Essential hypertension, uncontrolled.",
            plan: "Optimize antihypertensive therapy, low-salt diet, follow-up in 2 weeks.",
        },
        diabetes: {
            subjective: "Polyuria, fatigue, occasional hyperglycemia readings.",
            objective: "Random glucose elevated. Weight stable.",
            assessment: "Type 2 diabetes mellitus.",
            plan: "Review diet, adjust oral agents, order HbA1c, foot-care counseling.",
        },
        arthritis: {
            subjective: "Morning stiffness and joint pain in both knees.",
            objective: "Mild crepitus and tenderness on movement.",
            assessment: "Osteoarthritis with pain flare.",
            plan: "Analgesia, physiotherapy, weight support, review in 4 weeks.",
        },
    },
    addTemplate(name, data) {
        this.templates[name] = data;
    },
    loadTemplate(name) {
        const template = this.templates[name];
        if (!template) return;
        document.querySelector(".soap-subjective")?.value = template.subjective || "";
        document.querySelector(".soap-objective")?.value = template.objective || "";
        document.querySelector(".soap-assessment")?.value = template.assessment || "";
        document.querySelector(".soap-plan")?.value = template.plan || "";
        if (window.showToast) window.showToast(`${name} template loaded`, "info");
    },
    exportToPDF() {
        window.print();
    },
};

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-load-soap-template]").forEach((button) => {
        button.addEventListener("click", () => SOAPBuilder.loadTemplate(button.dataset.loadSoapTemplate));
    });
});

window.SOAPBuilder = SOAPBuilder;
