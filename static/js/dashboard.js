(() => {
  function toast(message, kind = "info") {
    window.KashUI?.showToast?.(message, kind);
  }

  function appendTempRow(tableBody, html) {
    if (!tableBody) return null;
    const row = document.createElement("tr");
    row.dataset.optimistic = "1";
    row.innerHTML = html;
    tableBody.prepend(row);
    return row;
  }

  function handlePatientForm(form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitButton = form.querySelector('[type="submit"]') || form.querySelector("button");
      const tableBody = document.querySelector("table tbody");
      const name = form.querySelector('[name="name"]')?.value?.trim() || "New patient";
      const age = form.querySelector('[name="age"]')?.value?.trim() || "";
      const gender = form.querySelector('[name="gender"]')?.value?.trim() || "";
      const tempRow = appendTempRow(
        tableBody,
        `<td>${name}</td><td>${age}</td><td>${gender}</td><td><span class="badge text-bg-secondary">Saving...</span></td>`
      );
      if (submitButton) submitButton.disabled = true;
      try {
        const response = await fetch(form.action, {
          method: form.method || "POST",
          body: new FormData(form),
          credentials: "same-origin",
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.success === false) {
          throw new Error(payload.detail || payload.error || "Could not add patient.");
        }
        if (tempRow) {
          tempRow.innerHTML = `<td>${payload.patient?.name || name}</td><td>${payload.patient?.age || age}</td><td>${payload.patient?.gender || gender}</td><td><span class="badge text-bg-success">Saved</span></td>`;
        }
        toast("Patient added instantly and saved in the background.", "success");
      } catch (error) {
        tempRow?.remove();
        toast(error.message || "Patient creation failed. Please try again.", "error");
      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  }

  function installGenericOptimism() {
    const patientForm = document.querySelector('form[action="/patients"]');
    if (patientForm) handlePatientForm(patientForm);

    document.addEventListener("submit", (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      const action = String(form.getAttribute("action") || "");
      if (action.includes("/appointments")) {
        toast("Appointment queued optimistically while the server saves it.", "info");
      }
      if (action.includes("/prescriptions")) {
        toast("Prescription preview is ready instantly.", "info");
      }
    }, true);
  }

  document.addEventListener("DOMContentLoaded", installGenericOptimism);
})();
