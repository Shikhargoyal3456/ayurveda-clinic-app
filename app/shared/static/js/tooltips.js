document.addEventListener("DOMContentLoaded", () => {
    const tooltips = {
        "#searchBtn, #searchButton": "Search for medicines by name or brand",
        "#uploadRxBtn": "Take photo of prescription, AI will read it",
        "#addToCart, .add-to-cart-btn": "Add medicine to your cart",
        "#checkoutBtn, #checkoutButton": "Proceed to payment and delivery",
        "#trackOrderBtn": "See live delivery status",
        "#startScribeBtn": "AI will listen and fill EMR automatically",
        "#saveEMRBtn": "Save consultation to patient record",
    };

    Object.entries(tooltips).forEach(([selector, message]) => {
        document.querySelectorAll(selector).forEach((element) => {
            element.setAttribute("title", message);
            element.setAttribute("data-tooltip", message);
        });
    });
});
