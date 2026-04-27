class SmartCart {
    constructor() {
        this.items = [];
        this.suggestions = [];
    }

    async addItem(productId, quantity = 1) {
        const response = await fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId, quantity })
        });
        const payload = await response.json();
        this.items = payload.cart?.items || [];
        this.suggestions = payload.cart?.suggestions || [];
        window.showToast?.('Item added to cart', 'success');
        this.updateCartUI();
        return payload;
    }

    async applyBestOffer() {
        const response = await fetch('/api/offers/best');
        const bestOffer = await response.json();
        if (bestOffer && bestOffer.discount) {
            window.showToast?.(`Applied ${bestOffer.discount}% off!`, 'success');
        }
        return bestOffer;
    }

    updateCartUI() {
        const total = this.items.reduce((sum, item) => sum + (Number(item.price || 0) * Number(item.quantity || 1)), 0);
        document.querySelectorAll('[data-cart-count]').forEach((node) => node.textContent = String(this.items.length));
        document.querySelectorAll('[data-cart-total]').forEach((node) => node.textContent = `₹${total.toFixed(0)}`);
    }
}

const superCart = new SmartCart();
document.addEventListener('click', function (event) {
    const button = event.target.closest('.add-superapp-cart');
    if (!button) return;
    superCart.addItem(Number(button.dataset.productId || 0), 1).then(() => superCart.applyBestOffer()).catch(() => {
        window.showToast?.('Unable to add item right now.', 'error');
    });
});

let flashSaleSeconds = 3 * 60 * 60 - 1;
setInterval(() => {
    const target = document.getElementById('flashSaleTimer');
    if (!target) return;
    flashSaleSeconds = Math.max(0, flashSaleSeconds - 1);
    const hrs = String(Math.floor(flashSaleSeconds / 3600)).padStart(2, '0');
    const mins = String(Math.floor((flashSaleSeconds % 3600) / 60)).padStart(2, '0');
    const secs = String(flashSaleSeconds % 60).padStart(2, '0');
    target.textContent = `${hrs}:${mins}:${secs}`;
}, 1000);
