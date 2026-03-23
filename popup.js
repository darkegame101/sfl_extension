document.addEventListener('DOMContentLoaded', () => {
    const startStopBtn = document.getElementById('startStopBtn');
    const indicator = document.getElementById('indicator');
    const statusText = document.getElementById('statusText');

    let isRunning = false;

    // Update UI every second based on in-game state
    setInterval(() => {
        chrome.storage.local.get(['isRunning'], (result) => {
            updateUI(result.isRunning || false);
        });
    }, 1000);

    const exportBtn = document.getElementById('exportAnalyticsBtn');
    exportBtn.addEventListener('click', () => {
        chrome.storage.local.get(['sfl_analytics'], (result) => {
            const data = result.sfl_analytics || { message: "No analytics collected yet. Start the bot first." };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sfl_analytics_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        });
    });

    function updateUI(active) {
        if (active) {
            startStopBtn.textContent = '🛑 DỪNG GIAO HÀNG (STOP)';
            startStopBtn.classList.add('stop');
            indicator.classList.add('active');
            statusText.textContent = 'ĐANG CHẠY...';
        } else {
            startStopBtn.textContent = '🚀 BẮT ĐẦU GIAO HÀNG (START)';
            startStopBtn.classList.remove('stop');
            indicator.classList.remove('active');
            statusText.textContent = 'CHỜ BẮT ĐẦU';
        }
    }
});
