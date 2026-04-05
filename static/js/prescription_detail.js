const printPrescriptionButton = document.getElementById("print-prescription-btn");

if (printPrescriptionButton) {
    printPrescriptionButton.addEventListener("click", () => {
        window.print();
    });
}
