document.querySelectorAll('.redeem-reward').forEach((button) => {
    button.addEventListener('click', async function () {
        const response = await fetch('/api/loyalty/redeem', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reward_id: button.dataset.rewardId })
        });
        const data = await response.json();
        window.showToast?.(data.success ? 'Reward redeemed.' : 'Unable to redeem reward.', data.success ? 'success' : 'error');
    });
});
