document.getElementById('articleSearchBtn')?.addEventListener('click', async function () {
    const query = document.getElementById('articleSearchInput')?.value || '';
    const response = await fetch(`/api/articles/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    window.showToast?.(`${(data.articles || []).length} articles found.`, 'info');
});
