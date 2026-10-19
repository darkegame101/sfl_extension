/**
 * SFL BOT - BACKGROUND SERVICE WORKER
 * Handles cross-origin requests to Firebase to bypass CORS.
 */

function getUserIP() {
    return fetch("https://api.ipify.org?format=json")
        .then(response => response.json())
        .then(data => data.ip)
        .catch(() => {
            // API dự phòng nếu ipify bị Adblock chặn
            return fetch("https://icanhazip.com")
                .then(res => res.text())
                .then(text => text.trim())
                .catch(() => null);
        });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "CHECK_LICENSE") {
        const { key, farmId } = request;
        const queryUrl = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/license_v2.json?orderBy="$key"&equalTo="${key}"`;
        const patchUrl = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/license_v2/${key}.json`;
        
        let serverTime = Date.now();
        Promise.all([
            fetch(queryUrl, {
                cache: 'no-store',
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            }).then(response => {
                const dateHeader = response.headers.get('date');
                if (dateHeader) {
                    serverTime = new Date(dateHeader).getTime();
                }
                return response.json();
            }),
            getUserIP()
        ])
        .then(([queryData, currentIp]) => {
            const data = queryData ? queryData[key] : null;
            if (data) {
                const patchData = {
                    last_seen: new Date().toISOString()
                };
                
                if (data.active === undefined) {
                    patchData.active = true;
                    data.active = true;
                }
                
                if (currentIp) {
                    patchData.ip = currentIp;
                    data.ip = currentIp;
                }

                if (farmId) {
                    patchData.farm_id = farmId;
                    data.farm_id = farmId;
                }
                
                fetch(patchUrl, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patchData)
                }).catch(() => {});
            }
            sendResponse({ success: true, data, serverTime, currentIp });
        })
        .catch(error => sendResponse({ success: false, error: error.message }));
        
        return true; // Keep channel open for async response
    }

    if (request.action === "ACTIVATE_LICENSE") {
        const { key, hwid } = request;
        const patchUrl = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/license_v2/${key}.json`;
        
        getUserIP()
        .then(currentIp => {
            const updateFields = { 
                hwid,
                last_seen: new Date().toISOString()
            };
            // Bắt buộc gửi IP
            if (currentIp) {
                updateFields.ip = currentIp;
            }
            
            // Cập nhật HWID và IP trên Firebase cùng lúc
            return fetch(patchUrl, {
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
        const queryUrl = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/license_v2.json?orderBy="$key"&equalTo="${key}"`;
        const patchUrl = `https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/license_v2/${key}.json`;
        
        fetch(queryUrl, {
            cache: 'no-store',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        })
        .then(response => response.json())
        .then(queryData => {
            const data = queryData ? queryData[key] : null;
            if (data) {
                if (data.farm_id !== farmId) {
                    console.log(`📡 [BACKGROUND]: Phát hiện Farm ID mới. Cập nhật Farm ID: ${farmId}`);
                    
                    getUserIP().then(currentIp => {
                        const patchData = { farm_id: farmId };
                        if (currentIp) patchData.ip = currentIp;
                        
                        fetch(patchUrl, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(patchData)
                        })
                        .then(() => sendResponse({ success: true }))
                        .catch(err => {
                            console.error("❌ [BACKGROUND]: Lỗi khi cập nhật Farm ID lên Firebase:", err);
                            sendResponse({ success: false, error: err.message });
                        });
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
