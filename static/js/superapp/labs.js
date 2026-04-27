document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('interpretReportBtn');
    const text = document.getElementById('reportText');
    const host = document.getElementById('reportAnalysis');
    button?.addEventListener('click', async function () {
        const response = await fetch('/api/labs/interpret', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ report_text: text?.value || '' })
        });
        const data = await response.json();
        if (!host) return;
        host.innerHTML = `<div class="stack-item"><strong>${data.summary || 'AI Interpretation'}</strong><p class="mb-0">${(data.flags || []).join(' ')}</p><p class="mb-0 text-muted">${data.recommendation || ''}</p></div>`;
    });
});
