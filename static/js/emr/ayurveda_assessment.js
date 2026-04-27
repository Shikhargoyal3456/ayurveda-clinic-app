const AyurvedaAssessment = {
    prakritiQuestionnaire: Array.from({ length: 54 }, (_, index) => ({
        id: index + 1,
        text: `Assessment prompt ${index + 1}`,
        vata: "Vata",
        pitta: "Pitta",
        kapha: "Kapha",
    })),
    calculatePrakriti(answers) {
        const scores = { vata: 0, pitta: 0, kapha: 0 };
        answers.forEach((answer) => {
            if (scores[answer] !== undefined) scores[answer] += 1;
        });
        const total = Math.max(1, scores.vata + scores.pitta + scores.kapha);
        return {
            vata: Math.round((scores.vata / total) * 100),
            pitta: Math.round((scores.pitta / total) * 100),
            kapha: Math.round((scores.kapha / total) * 100),
        };
    },
    assessSrotas(symptoms) {
        const text = symptoms.join(" ").toLowerCase();
        return {
            annavaha: text.includes("bloating") || text.includes("acid") ? "disturbed" : "clear",
            pranavaha: text.includes("cough") || text.includes("breath") ? "disturbed" : "clear",
            rasavaha: text.includes("fatigue") ? "watch" : "clear",
        };
    },
};

document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector("[data-calculate-prakriti]");
    const result = document.querySelector("[data-prakriti-result]");
    if (!button || !result) return;
    button.addEventListener("click", () => {
        const answers = Array.from(document.querySelectorAll(".questionnaire input[type='radio']:checked")).map((input) => input.value);
        const scores = AyurvedaAssessment.calculatePrakriti(answers);
        result.innerHTML = `
            <div class="dosha-bar vata" style="width:${scores.vata}%">Vata: ${scores.vata}%</div>
            <div class="dosha-bar pitta" style="width:${scores.pitta}%">Pitta: ${scores.pitta}%</div>
            <div class="dosha-bar kapha" style="width:${scores.kapha}%">Kapha: ${scores.kapha}%</div>
        `;
        if (window.showToast) window.showToast("Prakriti score calculated");
    });
});

window.AyurvedaAssessment = AyurvedaAssessment;
