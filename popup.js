document.addEventListener('DOMContentLoaded', () => {
    const startStopBtn = document.getElementById('startStopBtn');
    const indicator = document.getElementById('indicator');
    const statusText = document.getElementById('statusText');

    let isRunning = false;

    // Load current state
    chrome.storage.local.get(['isRunning'], (result) => {
        isRunning = result.isRunning || false;
        updateUI(isRunning);
    });

    startStopBtn.addEventListener('click', () => {
        isRunning = !isRunning;
        chrome.storage.local.set({ isRunning });
        
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0] && tabs[0].url.includes('sunflower-land.com')) {
                const action = isRunning ? 'start' : 'stop';
                
                // Use a callback to check for errors/missing content script
                chrome.tabs.sendMessage(tabs[0].id, { action }, (response) => {
                    const error = chrome.runtime.lastError;
                    if (error) {
                        console.warn("Message failed:", error.message);
                        statusText.textContent = 'Error: Please Refresh Game Page';
                        statusText.style.color = 'red';
                        // Rollback state if it failed to send
                        isRunning = false;
                        chrome.storage.local.set({ isRunning });
                        updateUI(isRunning);
                    } else {
                        statusText.style.color = '';
                        updateUI(isRunning);
                    }
                });
            } else {
                statusText.textContent = 'Error: Open SFL Game Tab';
                statusText.style.color = 'red';
                isRunning = false;
                chrome.storage.local.set({ isRunning });
                updateUI(isRunning);
            }
        });
    });

    const resetBtn = document.getElementById('resetBtn');
    resetBtn.addEventListener('click', () => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { action: 'reset' });
                statusText.textContent = 'Resetting...';
                setTimeout(() => updateUI(isRunning), 1000);
            }
        });
    });

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
            startStopBtn.textContent = 'Tắt Extension';
            startStopBtn.classList.add('stop');
            indicator.classList.add('active');
            statusText.textContent = 'Hoạt động';
        } else {
            startStopBtn.textContent = 'Bật Extension';
            startStopBtn.classList.remove('stop');
            indicator.classList.remove('active');
            statusText.textContent = 'Chưa bật';
        }
    }
});
