document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('userMessage');
    const button = document.getElementById('sendSupportMessage');
    const host = document.getElementById('chatMessages');
    async function sendMessage(message) {
        if (!host || !message) return;
        const userNode = document.createElement('div');
        userNode.className = 'stack-item';
        userNode.textContent = message;
        host.appendChild(userNode);
        const response = await fetch('/api/support/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await response.json();
        const botNode = document.createElement('div');
        botNode.className = 'stack-item surface-tint';
        botNode.textContent = data.reply || 'I can help with your healthcare workflow.';
        host.appendChild(botNode);
    }
    button?.addEventListener('click', () => sendMessage(input?.value || ''));
    document.querySelectorAll('.quick-support').forEach((button) => button.addEventListener('click', () => sendMessage(button.dataset.message || 'help')));
});
