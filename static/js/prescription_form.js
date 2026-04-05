const medicineList = document.getElementById("medicine-list");
const addMedicineButton = document.querySelector("[data-add-medicine]");
const diagnosisInput = document.getElementById("diagnosis-input");
const adviceInput = document.getElementById("advice-input");
const templatePicker = document.getElementById("template-picker");
const repeatLastButton = document.getElementById("repeat-last-btn");
const prescriptionShell = document.getElementById("prescription-form-shell");
const templateCatalog = prescriptionShell?.dataset.templates ? JSON.parse(prescriptionShell.dataset.templates) : [];
const lastPrescription = prescriptionShell?.dataset.lastPrescription
    ? JSON.parse(prescriptionShell.dataset.lastPrescription)
    : { diagnosis: "", medicines: [], advice: "" };

function buildMedicineRow() {
    const row = document.createElement("div");
    row.className = "medicine-row";
    row.innerHTML = `
        <input name="medicine_name" class="form-control medicine-name-input" list="medicine-options" placeholder="Medicine name" required>
        <input name="medicine_dosage" class="form-control" placeholder="Dosage">
        <input name="medicine_frequency" class="form-control" placeholder="Frequency">
        <button type="button" class="btn btn-outline-danger" data-remove-medicine>Remove</button>
    `;
    return row;
}

function populateMedicines(medicines) {
    if (!medicineList) {
        return;
    }
    medicineList.innerHTML = "";
    const entries = Array.isArray(medicines) && medicines.length > 0 ? medicines : [{ name: "", dosage: "", frequency: "" }];
    entries.forEach((medicine) => {
        const row = buildMedicineRow();
        const inputs = row.querySelectorAll("input");
        if (inputs[0] instanceof HTMLInputElement) {
            inputs[0].value = medicine.name || "";
        }
        if (inputs[1] instanceof HTMLInputElement) {
            inputs[1].value = medicine.dosage || "";
        }
        if (inputs[2] instanceof HTMLInputElement) {
            inputs[2].value = medicine.frequency || "";
        }
        medicineList.appendChild(row);
    });
}

function applyPrescriptionPayload(payload) {
    if (diagnosisInput instanceof HTMLInputElement) {
        diagnosisInput.value = payload.diagnosis || "";
    }
    if (adviceInput instanceof HTMLTextAreaElement) {
        adviceInput.value = payload.advice || "";
    }
    populateMedicines(payload.medicines || []);
}

if (medicineList) {
    medicineList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        if (!target.matches("[data-remove-medicine]")) {
            return;
        }
        const rows = medicineList.querySelectorAll(".medicine-row");
        if (rows.length === 1) {
            const nameInput = rows[0].querySelector('input[name="medicine_name"]');
            if (nameInput instanceof HTMLInputElement) {
                nameInput.value = "";
                nameInput.focus();
            }
            rows[0].querySelectorAll("input").forEach((input) => {
                if (input instanceof HTMLInputElement && input.name !== "medicine_name") {
                    input.value = "";
                }
            });
            return;
        }
        target.closest(".medicine-row")?.remove();
    });
}

if (addMedicineButton && medicineList) {
    addMedicineButton.addEventListener("click", () => {
        const row = buildMedicineRow();
        medicineList.appendChild(row);
        const nameInput = row.querySelector('input[name="medicine_name"]');
        if (nameInput instanceof HTMLInputElement) {
            nameInput.focus();
        }
    });
}

if (templatePicker) {
    templatePicker.addEventListener("change", () => {
        const selected = templateCatalog.find((template) => template.key === templatePicker.value);
        if (!selected) {
            return;
        }
        applyPrescriptionPayload(selected);
    });
}

if (repeatLastButton) {
    repeatLastButton.addEventListener("click", () => {
        applyPrescriptionPayload(lastPrescription);
    });
}
