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
                const patchData = {
                    last_seen: new Date().toISOString()
                };
                
                // Nếu key chưa có trường active, tự động khởi tạo với true
                if (data.active === undefined) {
                    console.log(`📡 [BACKGROUND]: Key chưa có trường active. Tự động khởi tạo: active = true`);
                    patchData.active = true;
                    data.active = true;
                }
                
                // Nếu lấy được IP và IP hiện tại khác IP đã lưu (hoặc chưa lưu IP)
                if (currentIp && data.ip !== currentIp) {
                    console.log(`📡 [BACKGROUND]: Phát hiện đổi IP hoặc IP mới. Cập nhật IP: ${currentIp}`);
                    patchData.ip = currentIp;
                    data.ip = currentIp;
                }
                
                fetch(url, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patchData)
                })
                .then(() => console.log(`✅ [BACKGROUND]: Đã cập nhật trạng thái mới (last_seen/ip) lên Firebase.`))
                .catch(err => console.error("❌ [BACKGROUND]: Lỗi khi cập nhật trạng thái lên Firebase:", err));
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
            const updateFields = { 
                hwid,
                last_seen: new Date().toISOString()
            };
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

    if (request.action === "UPDATE_FARM_ID") {
        const { key, farmId } = request;
        const url = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/licenses/${key}.json`;
        
        fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data) {
                if (data.farm_id !== farmId) {
                    console.log(`📡 [BACKGROUND]: Phát hiện Farm ID mới. Cập nhật Farm ID: ${farmId}`);
                    fetch(url, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ farm_id: farmId })
                    })
                    .then(() => sendResponse({ success: true }))
                    .catch(err => {
                        console.error("❌ [BACKGROUND]: Lỗi khi cập nhật Farm ID lên Firebase:", err);
                        sendResponse({ success: false, error: err.message });
                    });
                } else {
                    sendResponse({ success: true });
                }
            } else {
                sendResponse({ success: false, error: "Key not found" });
            }
        })
        .catch(error => sendResponse({ success: false, error: error.message }));
        
        return true; 
    }
});
