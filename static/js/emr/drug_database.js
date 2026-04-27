const DrugDatabase = {
    interactions: {
        Warfarin: ["Ashwagandha", "Guggulu", "Garlic"],
        Metformin: ["Gurmar", "Fenugreek", "Cinnamon"],
        Aspirin: ["Ginger", "Turmeric", "Guggulu"],
        Amlodipine: ["Arjuna", "Punarnava"],
    },
    checkInteraction(drug, herb) {
        return this.interactions[drug]?.includes(herb) || false;
    },
};

window.DrugDatabase = DrugDatabase;
