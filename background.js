/**
 * SFL BOT - BACKGROUND SERVICE WORKER
 * Handles cross-origin requests to Firebase to bypass CORS.
 */

function getUserIP() {
    return fetch("https://api.ipify.org?format=json")
        .then(response => response.json())
        .then(data => data.ip)
        .catch(error => {
            console.error("❌ [BACKGROUND]: Lỗi khi lấy IP người dùng:", error);
            return null;
        });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "CHECK_LICENSE") {
        const { key } = request;
        const url = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/licenses/${key}.json`;
        
        Promise.all([
            fetch(url).then(response => response.json()),
            getUserIP()
        ])
        .then(([data, currentIp]) => {
            if (data) {
                // Nếu lấy được IP và IP hiện tại khác IP đã lưu (hoặc chưa lưu IP)
                if (currentIp && data.ip !== currentIp) {
                    console.log(`📡 [BACKGROUND]: Phát hiện đổi IP hoặc IP mới. Cập nhật IP: ${currentIp}`);
                    fetch(url, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ip: currentIp })
                    })
                    .then(() => console.log(`✅ [BACKGROUND]: Đã cập nhật IP mới (${currentIp}) lên Firebase.`))
                    .catch(err => console.error("❌ [BACKGROUND]: Lỗi khi cập nhật IP lên Firebase:", err));
                    
                    data.ip = currentIp;
                }
            }
            sendResponse({ success: true, data });
        })
        .catch(error => sendResponse({ success: false, error: error.message }));
        
        return true; // Keep channel open for async response
    }

    if (request.action === "ACTIVATE_LICENSE") {
        const { key, hwid } = request;
        const url = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/licenses/${key}.json`;
        
        getUserIP()
        .then(currentIp => {
            const updateFields = { hwid };
            if (currentIp) {
                updateFields.ip = currentIp;
            }
            
            // Cập nhật HWID và IP trên Firebase cùng lúc
            return fetch(url, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updateFields)
            });
        })
        .then(response => response.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(error => sendResponse({ success: false, error: error.message }));
        
        return true; 
    }
});
