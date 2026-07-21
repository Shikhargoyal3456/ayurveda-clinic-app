(() => {
  const features = [
    { key: "tongue", name: "Tongue Diagnosis", method: "POST", url: "/api/tongue-analyze", body: () => new FormData(), form: true },
    { key: "chat", name: "AI Doctor Chat", method: "POST", url: "/api/ai-chat", body: () => ({ message: "I have fever and cough" }) },
    { key: "billing", name: "Billing Codes", method: "POST", url: "/api/generate-billing-codes", body: () => ({ prescription_id: 1 }), okStatuses: [200, 404] },
    { key: "recommend", name: "Medicine Recommendations", method: "POST", url: "/api/recommend-medicines", body: () => ({ case_sheet_id: 1 }), okStatuses: [200, 404] },
    { key: "voice", name: "Voice Extraction", method: "POST", url: "/api/voice/extract", body: () => ({ transcript: "Patient is Rajesh Kumar, 45 years old, male. Fever for 3 days and cough." }) },
    { key: "churn", name: "Churn Prediction", method: "GET", url: "/api/predict-churn" },
    { key: "telemedicine", name: "Video Consultation", method: "GET", url: "/telemedicine/start", okStatuses: [200] },
    { key: "device", name: "Device Check", method: "GET", url: "/api/device/check" },
  ];

  function statusClass(status) {
    if (status === "working") return "status-pill status-working";
    if (status === "checking") return "status-pill status-checking";
    if (status === "unknown") return "status-pill status-unknown";
    return "status-pill status-failed";
  }

  function updateSummary() {
    const rows = [...document.querySelectorAll("[data-feature]")];
    const counts = rows.reduce((accumulator, row) => {
      const status = row.querySelector("[data-status]")?.dataset.state || "unknown";
      accumulator[status] = (accumulator[status] || 0) + 1;
      return accumulator;
    }, {});
    document.getElementById("workingCount").textContent = counts.working || 0;
    document.getElementById("checkingCount").textContent = counts.checking || 0;
    document.getElementById("failedCount").textContent = counts.failed || 0;
    document.getElementById("totalCount").textContent = rows.length;
  }

  function setRowState(row, state, label) {
    const status = row.querySelector("[data-status]");
    status.dataset.state = state;
    status.className = statusClass(state);
    status.textContent = label;
  }

  function render() {
    const tbody = document.getElementById("featureStatusBody");
    tbody.innerHTML = features.map((feature) => `
      <tr class="feature-row" data-feature="${feature.key}">
        <td><strong>${feature.name}</strong></td>
        <td><span class="${statusClass("checking")}" data-status>Checking</span></td>
        <td class="muted" data-tested>Not tested yet</td>
        <td><div class="feature-actions"><button class="btn btn-primary btn-sm" data-test>Test</button></div></td>
      </tr>
    `).join("");
    tbody.querySelectorAll("[data-test]").forEach((button, index) => button.addEventListener("click", () => testFeature(features[index])));
    updateSummary();
  }

  async function testFeature(feature) {
    const row = document.querySelector(`[data-feature="${feature.key}"]`);
    const tested = row.querySelector("[data-tested]");
    setRowState(row, "checking", "Checking");
    updateSummary();
    try {
      const requestInit = { method: feature.method };
      if (feature.method === "POST" && feature.form) {
        const formData = new FormData();
        formData.append("description", "white coated tongue with cracks");
        formData.append("patient_id", "1");
        requestInit.body = formData;
      } else if (feature.method === "POST") {
        requestInit.headers = { "Content-Type": "application/json" };
        requestInit.body = feature.body ? JSON.stringify(feature.body()) : undefined;
      }
      const response = await fetch(feature.url, requestInit);
      const payload = await response.json();
      const okStatuses = feature.okStatuses || [200];
      const ok = okStatuses.includes(response.status) || (response.ok && (payload.success !== false) && !payload.error && !payload.detail);
      setRowState(row, ok ? "working" : "failed", ok ? "✅ Working" : "❌ Not Working");
      tested.textContent = ok && payload.model ? `${new Date().toLocaleString()} · ${payload.model}` : new Date().toLocaleString();
    } catch (error) {
      setRowState(row, "failed", "❌ Not Working");
      tested.textContent = new Date().toLocaleString();
    }
    updateSummary();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    render();
    for (const feature of features) {
      // Run in sequence to keep load gentle.
      // eslint-disable-next-line no-await-in-loop
      await testFeature(feature);
    }
  });
})();
