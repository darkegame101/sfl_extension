/**
 * SFL BOT - BACKGROUND SERVICE WORKER
 * Handles cross-origin requests to Firebase to bypass CORS.
 */

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "CHECK_LICENSE") {
        const { key } = request;
        const url = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/licenses/${key}.json`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => sendResponse({ success: true, data }))
            .catch(error => sendResponse({ success: false, error: error.message }));
        
        return true; // Keep channel open for async response
    }

    if (request.action === "ACTIVATE_LICENSE") {
        const { key, hwid } = request;
        const url = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/licenses/${key}.json`;
        
        // Cập nhật HWID trên Firebase
        fetch(url, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hwid: hwid })
        })
        .then(response => response.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(error => sendResponse({ success: false, error: error.message }));
        
        return true; 
    }
});
