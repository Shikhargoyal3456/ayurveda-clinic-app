(() => {
  const button = document.getElementById("voiceActionBtn");
  const confirmButton = document.getElementById("confirmVoiceActionBtn");
  const recommendButton = document.getElementById("recommendMedicinesBtn");
  if (!button || !confirmButton || !recommendButton) return;

  const patientId = window.kashConsultContext?.patientId || 0;
  const doctorId = window.kashConsultContext?.doctorId || 0;
  const transcript = "Patient reports recurring acidity, fatigue, and tongue coating.";
  let lastPayload = null;

  const setBox = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.innerHTML = value;
  };

  button.addEventListener("click", async () => {
    const response = await fetch("/api/voice-to-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId, doctor_id: doctorId, transcript }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) throw new Error(payload.error || "Voice action failed");
    lastPayload = payload.outputs;
    setBox("voiceCaseSheet", `<strong>Case sheet</strong><p class="mb-0">${lastPayload.case_sheet.symptoms}</p>`);
    setBox("voiceMedicines", `<strong>Medicines</strong><ul>${lastPayload.medicines.map((item) => `<li>${item.name}</li>`).join("")}</ul>`);
    setBox("voicePrescription", `<strong>Prescription</strong><pre class="mb-0">${lastPayload.prescription.text}</pre>`);
    setBox("voiceFollowup", `<strong>Follow-up</strong><p class="mb-0">${lastPayload.followup.date}</p>`);
  });

  confirmButton.addEventListener("click", () => {
    if (!lastPayload) return;
    alert("Draft saved on the server. Review the case sheet and prescription before finalizing.");
  });

  recommendButton.addEventListener("click", async () => {
    const response = await fetch("/api/recommend-medicines", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_sheet_id: 0 }),
    });
    const payload = await response.json();
    const box = document.getElementById("medicineRecommendationBox");
    if (box) {
      box.innerHTML = response.ok && payload.success
        ? `<pre class="mb-0">${JSON.stringify(payload, null, 2)}</pre>`
        : `<div class="alert alert-warning">${payload.error || "No recommendations available."}</div>`;
    }
  });
})();
