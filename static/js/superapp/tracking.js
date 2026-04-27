class OrderTracker {
    constructor(orderId) {
        this.orderId = orderId;
        this.startTracking();
    }

    startTracking() {
        this.updateLocation();
        setInterval(() => this.updateLocation(), 30000);
    }

    async updateLocation() {
        const response = await fetch(`/api/orders/${this.orderId}/location`);
        const data = await response.json();
        const eta = document.getElementById('eta');
        if (eta && data.eta) eta.textContent = data.eta;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const cancelButton = document.getElementById('cancelOrderBtn');
    const rescheduleButton = document.getElementById('rescheduleOrderBtn');
    const orderId = Number(cancelButton?.dataset.orderId || rescheduleButton?.dataset.orderId || 0);
    if (orderId) new OrderTracker(orderId);

    cancelButton?.addEventListener('click', async function () {
        const response = await fetch(`/api/orders/${orderId}/cancel`, { method: 'POST' });
        const data = await response.json();
        window.showToast?.(data.success ? 'Order cancelled.' : 'Unable to cancel order.', data.success ? 'success' : 'error');
    });

    rescheduleButton?.addEventListener('click', async function () {
        const newEta = prompt('Enter new delivery ISO datetime', new Date(Date.now() + 3600 * 1000).toISOString());
        if (!newEta) return;
        const response = await fetch(`/api/orders/${orderId}/reschedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estimated_delivery: newEta })
        });
        const data = await response.json();
        window.showToast?.(data.success ? 'Delivery rescheduled.' : 'Unable to reschedule.', data.success ? 'success' : 'error');
    });
});
