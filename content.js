// Sunflower Land Auto-Deliver Content Script
let isRunning = false;
let isLicensed = false; // BOT LOCKED BY DEFAULT
let licenseKey = "";
let userHWID = "";
let ownerName = "Premium User";
let licenseStatus = "Checking...";

let memory = {
    npcs: {},
    islands: {},
    delivery_queue: [], // Hàng chờ các NPC đã sẵn sàng giao
    speedMultiplier: 1.0
};

// Đồ thị node người dùng tự nhập (load từ chrome.storage.local)
let userNodeGraphs = {};
chrome.storage.local.get(['sfl_node_graphs'], r => {
    userNodeGraphs = r.sfl_node_graphs || {};
    if (Object.keys(userNodeGraphs).length) console.log('✅ [GRAPH]: Đã nạp đồ thị của user từ storage!', Object.keys(userNodeGraphs));
});
// State machine variables
let currentTask = "IDLE"; // SCAN, TRAVEL, RESET, MOVE, DELIVER, RECORD
let targetNPC = null;
let targetIsland = null;
let isAutoEnabled = false;
let lastIsland = null;
let isNewMapMove = false;

// Toggles
const AUTO_DELIVER_ENABLED = true; // Auto-Deliver is officially ON

// Recording variables
let isRecording = false;
let recordStartTime = 0;
let currentRecordPath = [];
let activeKey = null;
let currentX = 0;
let currentY = 0;
const BASE_SPEED = 0.1; // 100px per 1000ms at 1.0x speed

const KNOWN_NPCS = ["pete", "peggy", "bert", "betty", "guria", "raven", "tinker", "corale", "old salty", "stella", "finn", "eldric", "reginald", "gambit", "victoria", "grimbly", "blacksmith", "tywin", "grimlock", "pharaoh", "hank", "jester", "grubnuk", "gordo", "tango", "miranda", "finley", "timmy", "cornwell", "grimtooth"];
// Mô phỏng Click chuột "Thật" (Mousedown + Mouseup + Click) để vượt qua các lớp chặn React/Phaser
async function simulateFullClick(el) {
    if (!el) return;
    try {
        const rect = el.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const events = ['mousedown', 'mouseup', 'click'];
        events.forEach(type => {
            el.dispatchEvent(new MouseEvent(type, {
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: centerX,
                clientY: centerY,
                button: 0
            }));
        });
        return true;
    } catch (e) { return false; }
}

// Phân loại bảng đang mở: Codex (Danh sách) vs NPC Dialog (Nút bấm)
function getOpenPanelInfo() {
    const panels = document.querySelectorAll('div[id^="headlessui-dialog-panel-"], [role="dialog"]');
    for (const p of panels) {
        const isVisible = !!(p.offsetWidth || p.offsetHeight || p.getClientRects().length);
        if (!isVisible) continue;
        const text = p.textContent.toLowerCase();
        if (text.includes("codex") || text.includes("deliveries")) return { type: "CODEX", el: p };
        if (text.includes("deliver") || text.includes("gift") || text.includes("quest")) return { type: "NPC_DIALOG", el: p };
    }
    return null;
}

// Giữ lại hàm cũ để tránh lỗi các nơi khác đang gọi
function isAnyUIPanelOpen() {
    return !!getOpenPanelInfo();
}

// --- [NEW] A* PATHFINDING ENGINE ---
async function findPath(tx, ty) {
    const data = getGameData();
    if (!data || !data.player) return null;
    const { x: curX, y: curY } = data.player;

    const range = 400; // Khoảng cách quét 400px xung quanh
    const step = 32;   // Bước nhảy 32px

    // Gọi Bridge lấy ma trận va chạm
    console.log(`📡 [A-STAR]: Đang xin bản đồ gạch từ Engine...`);
    const gridData = await new Promise(resolve => {
        const npcToExclude = (targetNPC || "").toLowerCase();
        document.dispatchEvent(new CustomEvent('SFL_GRID_REQUEST', { detail: { minX: curX - range, minY: curY - range, maxX: curX + range, maxY: curY + range, excludeNPC: npcToExclude, step } }));
        setTimeout(() => resolve(JSON.parse(document.body.dataset.sflGrid || "null")), 150);
    });

    if (!gridData || !gridData.grid) return null;

    const { grid, minX, minY } = gridData;
    const goalX = Math.floor((tx - minX) / step);
    const goalY = Math.floor((ty - minY) / step);
    const startX = Math.floor((curX - minX) / step);
    const startY = Math.floor((curY - minY) / step);

    // Simple A-Star Implementation
    const openSet = [{ x: startX, y: startY, g: 0, f: 0, path: [] }];
    const closedSet = new Set();

    while (openSet.length > 0) {
        openSet.sort((a, b) => a.f - b.f);
        const current = openSet.shift();
        const key = `${current.x},${current.y}`;
        if (closedSet.has(key)) continue;
        closedSet.add(key);

        if (Math.abs(current.x - goalX) <= 1 && Math.abs(current.y - goalY) <= 1) {
            return current.path.map(p => ({ x: p.x * step + minX, y: p.y * step + minY }));
        }

        const neighbors = [
            { dx: 0, dy: -1 }, { dx: 0, dy: 1 }, { dx: -1, dy: 0 }, { dx: 1, dy: 0 }
        ];

        for (const n of neighbors) {
            const nx = current.x + n.dx;
            const ny = current.y + n.dy;
            if (nx < 0 || ny < 0 || ny >= grid.length || nx >= grid[0].length || grid[ny][nx] === 1) continue;

            const g = current.g + 1;
            const h = Math.abs(nx - goalX) + Math.abs(ny - goalY);
            openSet.push({ x: nx, y: ny, g, f: g + h, path: [...current.path, { x: nx, y: ny }] });
        }
    }
    return null;
}

// Utility to find elements by text (PRO VERSION: Includes buttons and divs)
function findElementByText(selector, text) {
    const elements = document.querySelectorAll(selector);
    const targetText = text.toLowerCase();

    return Array.from(elements).find(el => {
        const content = el.textContent.trim().toLowerCase();
        if (!content.includes(targetText)) return false;

        // LOẠI TRỪ UI: Không lấy các phần tử nằm trong Bảng Codex hoặc Dialog (trừ khi chính nó là mục tiêu)
        const isUI = el.closest('.fixed, [role="dialog"], .bg-brown-600, .bg-blue-600');
        // Nếu chúng ta đang tìm modal "Go Home", hoặc các nút Skip/Xác nhận thì ĐƯỢC PHÉP tìm trong UI
        if (targetText.includes('home') || targetText.includes('go home') || targetText.includes('return') ||
            targetText.includes('skip') || targetText.includes('confirm') || targetText.includes('yes')) {
            return true;
        }

        if (isUI) return false;
        return true;
    });
}

// Utility to sleep
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Load memory from file/local storage
// Tải toàn bộ trạng thái từ Storage (Tăng cường Resilience)
async function loadMemory() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['sfl_memory', 'isRunning', 'currentTask', 'targetNPC', 'targetIsland', 'licenseKey', 'userHWID'], (result) => {
            if (result.sfl_memory) {
                memory = { ...memory, ...result.sfl_memory };
                if (typeof memory.speedMultiplier !== 'number') memory.speedMultiplier = 1.0;
            }
            if (result.isRunning !== undefined) isRunning = result.isRunning;
            if (result.currentTask !== undefined) currentTask = result.currentTask;
            if (result.targetNPC !== undefined) targetNPC = result.targetNPC;
            if (result.targetIsland !== undefined) targetIsland = result.targetIsland;

            // LICENSE PERSISTENCE
            if (result.licenseKey) licenseKey = result.licenseKey;
            if (result.userHWID) userHWID = result.userHWID;

            isAutoEnabled = isRunning; // Đồng bộ biến điều hướng
            resolve();
        });
    });
}

// Lưu toàn bộ trạng thái sống (Persistent State Machine)
function saveMemory() {
    chrome.storage.local.set({
        'sfl_memory': memory,
        'isRunning': isRunning,
        'currentTask': currentTask,
        'targetNPC': targetNPC,
        'targetIsland': targetIsland,
        'licenseKey': licenseKey,
        'userHWID': userHWID
    });
}

// --- HỆ THỐNG BẢO MẬT & BẢN QUYỀN (FIREBASE LICENSE) ---
const FIREBASE_DB_URL = "https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/"; // <--- ĐÃ CẬP NHẬT URL THỰC CỦA BẠN

// 1. Tạo mã định danh máy tính duy nhất (Persistent Fingerprint)
async function getUniqueHWID() {
    if (userHWID) return userHWID;

    // Tạo ID ngẫu nhiên nếu chưa có
    const p = await new Promise(r => chrome.storage.local.get(['userHWID'], r));
    if (p.userHWID) {
        userHWID = p.userHWID;
        return userHWID;
    }

    const fingerprint = [
        navigator.userAgent,
        screen.width,
        screen.height,
        navigator.language,
        Math.random().toString(36).substring(2, 15)
    ].join('|');

    // Hash đơn giản (hoặc dùng Web Crypto API nếu muốn bảo mật cao hơn)
    const encoder = new TextEncoder();
    const data = encoder.encode(fingerprint);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    userHWID = hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 16);

    chrome.storage.local.set({ userHWID });
    return userHWID;
}

// 2. Xác thực License từ xa qua Firebase REST API
async function checkLicenseRemote() {
    const key = licenseKey || "";
    if (!key) return false;

    console.log(`📡 [LICENSE]: Đang xác thực Key [${key}] qua Background...`);
    const hwid = await getUniqueHWID();

    try {
        // Gửi tin nhắn tới Background để check GET
        const response = await new Promise(r => chrome.runtime.sendMessage({ action: "CHECK_LICENSE", key }, r));

        if (!response || !response.success) {
            console.error("❌ License Check Error:", response?.error || "Unknown error");
            return false;
        }

        const data = response.data;
        if (!data) return false;

        // 1. Kiểm tra trạng thái
        if (data.status !== "active") {
            licenseStatus = "INACTIVE";
            return false;
        }

        // 2. Kiểm tra ngày hết hạn
        const exp = new Date(data.expiration);
        if (exp < new Date()) {
            licenseStatus = "EXPIRED";
            return false;
        }

        // 3. HWID Binding
        if (!data.hwid) {
            console.log("⚡ [LICENSE]: Key chưa kích hoạt. Đang gán HWID vào Key...");
            // Gửi lệnh kích hoạt (gán HWID)
            await new Promise(r => chrome.runtime.sendMessage({ action: "ACTIVATE_LICENSE", key, hwid }, r));

            isLicensed = true;
            licenseStatus = "VALID";
            return true;
        } else if (data.hwid !== hwid) {
            // Máy khác đang dùng Key này
            licenseStatus = "MISMATCH";
            console.error("❌ [SECURITY]: Cảnh báo! Key này đã được dùng ở máy khác.");
            return false;
        }

        isLicensed = true;
        ownerName = data.owner || "Premium User";
        licenseStatus = "VALID";
        return true;
    } catch (e) {
        console.error("License Check Error:", e);
        licenseStatus = "SERVER_ERROR";
        return false;
    }
}

// 3. Giao diện nhập Key khi chưa kích hoạt (Blocking UI)
function renderLicenseModal() {
    if (document.getElementById('sfl-license-modal')) return;

    const modal = document.createElement('div');
    modal.id = "sfl-license-modal";
    modal.style.cssText = `
        position: fixed; inset: 0; background: rgba(0,0,0,0.85);
        display: flex; align-items: center; justify-content: center;
        z-index: 99999; backdrop-filter: blur(10px); color: white;
        font-family: system-ui, -apple-system, sans-serif;
    `;

    let msg = "Vui lòng nhập License Key để sử dụng Bot";
    if (licenseStatus === "MISMATCH") msg = "❌ Key này đã được dùng trên máy khác!";
    if (licenseStatus === "EXPIRED") msg = "❌ Key của bạn đã hết hạn!";
    if (licenseStatus === "INACTIVE") msg = "❌ Key này hiện đang bị khóa!";
    if (licenseStatus === "NOT_FOUND") msg = "❌ Không tìm thấy Key này trên hệ thống!";

    modal.innerHTML = `
        <div style="background: #1a1a1a; padding: 40px; border-radius: 20px; border: 1px solid #FFD700; width: 350px; text-align: center; box-shadow: 0 0 50px rgba(255,215,0,0.1);">
            <div style="font-size: 24px; font-weight: 800; color: #FFD700; margin-bottom: 10px;">PREMIUM ACCESS</div>
            <div style="font-size: 12px; color: #888; margin-bottom: 25px;">${msg}</div>
            
            <input type="text" id="license_input" placeholder="G0LD-XXXX-YYYY-ZZZZ" style="width: 100%; padding: 15px; background: #000; border: 1px solid #333; border-radius: 8px; color: #2ed573; text-align: center; font-family: monospace; font-size: 14px; margin-bottom: 20px;">
            <button id="activate_btn" style="width: 100%; padding: 15px; background: linear-gradient(to right, #FFD700, #DAA520); border: none; border-radius: 8px; color: #000; font-weight: 800; cursor: pointer; transition: 0.2s;">KÍCH HOẠT NGAY</button>
            <div style="margin-top: 20px; font-size: 10px; color: #555;">ID Máy: ${userHWID}</div>
        </div>
    `;

    document.body.appendChild(modal);

    document.getElementById('activate_btn').onclick = async () => {
        const key = document.getElementById('license_input').value.trim();
        if (key.length < 5) return;

        document.getElementById('activate_btn').innerText = "ĐANG KIỂM TRA...";
        licenseKey = key;
        const valid = await checkLicenseRemote();

        if (valid) {
            saveMemory();
            window.location.reload(); // Tải lại để khởi động bot
        } else {
            alert("Lỗi: " + licenseStatus);
            document.getElementById('activate_btn').innerText = "KÍCH HOẠT NGAY";
        }
    };
}
function getNPCData(name) {
    if (!name) return null;
    name = name.toLowerCase().trim();

    // 1. Kiểm tra trực tiếp trong Bộ nhớ Tạm (User Record)
    if (memory.npcs[name]) return { island: memory.npcs[name].island || "plaza", ...memory.npcs[name] };

    // 2. Duyệt qua MASTER_NPC_DATA với cơ chế Fuzzy Match (Thông minh hơn)
    for (const island in MASTER_NPC_DATA) {
        for (const npcKey in MASTER_NPC_DATA[island]) {
            // Nếu khớp chính xác HOẶC tên chứa Key HOẶC Key chứa tên (ví dụ: pete vs pumpkin' pete)
            if (npcKey === name || name.includes(npcKey) || npcKey.includes(name)) {
                return { island, ...MASTER_NPC_DATA[island][npcKey] };
            }
        }
    }
    return null;
}

// Tính toán tổng độ dài đường đi qua các node trong một graph
function calculateGraphPathLength(graph, pathIds, startPos, targetPos) {
    if (!pathIds || pathIds.length === 0) {
        // Fallback sang Euclidean nếu không tìm thấy đường trong graph
        const dx = startPos.x - targetPos.x;
        const dy = startPos.y - targetPos.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    let totalLength = 0;
    const startNode = graph.nodes[pathIds[0]];
    const endNode = graph.nodes[pathIds[pathIds.length - 1]];

    // 1. Khoảng cách Segments: Bắt đầu -> Node đầu
    totalLength += Math.sqrt(Math.pow(startPos.x - startNode.x, 2) + Math.pow(startPos.y - startNode.y, 2));

    // 2. Độ dài các cạnh trong Path
    for (let i = 0; i < pathIds.length - 1; i++) {
        const n1 = graph.nodes[pathIds[i]];
        const n2 = graph.nodes[pathIds[i + 1]];
        totalLength += Math.sqrt(Math.pow(n1.x - n2.x, 2) + Math.pow(n1.y - n2.y, 2));
    }

    // 3. Khoảng cách Segments: Node cuối -> Đích thật
    totalLength += Math.sqrt(Math.pow(endNode.x - targetPos.x, 2) + Math.pow(endNode.y - targetPos.y, 2));

    return totalLength;
}

// Tính toán chi phí di chuyển (càng thấp càng gần) - VERSION 2: NODE-AWARE
function calculateTravelCost(currentIsland, currentPos, targetData) {
    if (!targetData) return 999999;

    let cost = 0;
    // Hình phạt thay đổi đảo (Rất lớn vì phải qua Plaza và load map)
    if (currentIsland !== targetData.island) {
        cost += 10000;
        // Nếu phải qua Plaza trung chuyển (Beach <-> Kingdom)
        if ((currentIsland === 'beach' && targetData.island === 'kingdom') ||
            (currentIsland === 'kingdom' && targetData.island === 'beach')) {
            cost += 5000;
        }

        // Với khác đảo, chúng ta chỉ dùng Euclidean làm ước lượng thô cho quãng đường sau khi chuyển map
        const dx = currentPos.x - targetData.x;
        const dy = currentPos.y - targetData.y;
        cost += Math.sqrt(dx * dx + dy * dy);
    } else {
        // CÙNG ĐẢO: Sử dụng Đồ thị Node để tính quãng đường thật
        const graph = (userNodeGraphs[currentIsland] && Object.keys(userNodeGraphs[currentIsland].nodes || {}).length > 0)
            ? userNodeGraphs[currentIsland]
            : window.SFL_ISLAND_GRAPHS[currentIsland];

        if (graph && graph.nodes && graph.edges) {
            const startNodeId = findNearestNode(graph, currentPos.x, currentPos.y);
            const endNodeId = findNearestNode(graph, targetData.x, targetData.y);
            const path = graphBFS(graph, startNodeId, endNodeId);
            cost = calculateGraphPathLength(graph, path, currentPos, targetData);
        } else {
            // Fallback nếu không có graph
            const dx = currentPos.x - targetData.x;
            const dy = currentPos.y - targetData.y;
            cost = Math.sqrt(dx * dx + dy * dy);
        }
    }

    return cost;
}

function sortDeliveryQueue() {
    if (!memory.delivery_queue || memory.delivery_queue.length <= 1) return;

    const currentIsland = getCurrentIsland();
    const gameData = getGameData();
    const currentPos = (gameData && gameData.player) ? gameData.player : { x: 0, y: 0 };

    console.log("📐 [ROUTING]: Đang tối ưu hóa lộ trình giao hàng (Nearest Neighbor)...");

    memory.delivery_queue.sort((a, b) => {
        const dataA = getNPCData(a);
        const dataB = getNPCData(b);
        const costA = calculateTravelCost(currentIsland, currentPos, dataA);
        const costB = calculateTravelCost(currentIsland, currentPos, dataB);
        return costA - costB;
    });

    console.log("📋 [QUEUE-SORTED]:", memory.delivery_queue.join(" -> "));
}

// Log analytics for later export
async function logAnalytics(data) {
    chrome.storage.local.get(['sfl_analytics'], (result) => {
        let logs = result.sfl_analytics || [];
        logs.push({ timestamp: new Date().toISOString(), ...data });
        if (logs.length > 100) logs.shift(); // Keep last 100 events
        chrome.storage.local.set({ 'sfl_analytics': logs });
    });
}

// Emulate Arrow keys for movement (Keyboard Engine 3.0 - Single Direction)
async function moveCharacter(direction, duration = 500) {
    const adjustedDuration = duration * (memory.speedMultiplier || 1.0);
    const keysMap = { 'up': 'ArrowUp', 'down': 'ArrowDown', 'left': 'ArrowLeft', 'right': 'ArrowRight' };
    const key = keysMap[direction] || direction;
    const keyCodes = { 'ArrowUp': 38, 'ArrowDown': 40, 'ArrowLeft': 37, 'ArrowRight': 39 };
    const keyCode = keyCodes[key];

    // Cập nhật tọa độ nội bộ
    const distance = duration * BASE_SPEED * (memory.speedMultiplier || 1.0);
    if (direction === 'up') currentY -= distance;
    if (direction === 'down') currentY += distance;
    if (direction === 'left') currentX -= distance;
    if (direction === 'right') currentX += distance;

    document.body.focus();
    const targets = [window, document, ...Array.from(document.querySelectorAll('canvas'))];

    const interval = setInterval(() => {
        const params = { key, code: key, keyCode, which: keyCode, bubbles: true, cancelable: true, repeat: true, view: window };
        targets.forEach(t => t.dispatchEvent(new KeyboardEvent('keydown', params)));
    }, 25);

    await sleep(adjustedDuration);

    clearInterval(interval);
    const upParams = { key, code: key, keyCode, which: keyCode, bubbles: true, cancelable: true, view: window };
    targets.forEach(t => t.dispatchEvent(new KeyboardEvent('keyup', upParams)));
    activeKey = null;

    await sleep(50);
}

// Dừng tuyệt đối tất cả các phím di chuyển (Phòng trường hợp bị kẹt phím)
function forceStopAllKeys() {
    const keys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'e', 'E'];
    const targets = [window, document, ...Array.from(document.querySelectorAll('canvas'))];
    keys.forEach(k => {
        const upParams = { key: k, code: k, bubbles: true, cancelable: true, view: window };
        targets.forEach(t => t.dispatchEvent(new KeyboardEvent('keyup', upParams)));
    });
    activeKey = null;
    console.log("🛑 [HỆ THỐNG]: Đã giải phóng toàn bộ phím điều khiển.");
}

// Execute path to NPC (ULTRA MODE: Direct Link Engine-to-Engine)
async function executePathToNPC(npcData) {
    // 🛡️ SENSOR GRACE PERIOD: Đợi 2 giây nếu mất kết nối
    let data = null;
    for (let i = 0; i < 10; i++) {
        data = getGameData();
        if (data && data.player) break;
        await sleep(200);
    }

    const npcName = (targetNPC || "").toLowerCase().trim();
    if (!npcName) return false;

    // --- CHẾ ĐỘ SET CỨNG (SFL-NAV 2024) ---
    // User muốn dùng tọa độ cố định từ MASTER_NPC_DATA để làm kim chỉ nam tuyệt đối
    const custom = memory.npcs[npcName];
    const master = (MASTER_NPC_DATA[targetIsland] || MASTER_NPC_DATA["plaza"] || {})[npcName];

    // Ưu tiên tọa độ Master (đã được user set cứng) > Bộ nhớ tạm
    const target = master || (custom && custom.x !== undefined ? custom : null);

    if (!target || target.x === undefined) {
        console.error(`❌ [LỖI]: Không tìm thấy tọa độ "cứng" cho ${npcName.toUpperCase()}.`);
        return false;
    }

    console.log(`📡 [PLAZA-NAV]: Đang di chuyển ${npcName.toUpperCase()} -> Tọa độ mục tiêu: (${Math.round(target.x)}, ${Math.round(target.y)})`);

    if (data && data.player) {
        // ƯU TIÊN: Điều hướng qua đồ thị Waypoint Graph
        console.log(`🗺️ [GRAPH-NAV]: Bắt đầu điều hướng qua đồ thị liên thông...`);
        const graphDone = await navigateViaGraph(target.x, target.y);

        if (!graphDone) {
            // FALLBACK: Di chuyển thẳng nếu không có graph
            console.warn(`⚠️ [GRAPH-NAV]: Không dùng được đồ thị. Dùng di chuyển thẳng...`);
            await moveTowardsTarget(target.x, target.y);
        }

        // Xác nhận đã tới đích (bán kính 50px)
        const finalData = getGameData();
        if (finalData && finalData.player) {
            const distX = Math.abs(target.x - finalData.player.x);
            const distY = Math.abs(target.y - finalData.player.y);
            if (distX < 50 && distY < 50) {
                console.log(`🎯 [TỚI ĐÍCH]: Đã chạm vùng tương tác của ${npcName.toUpperCase()}.`);
                return true;
            }
        }
        console.warn(`❌ [LỠ ĐƯỜNG]: Không thể áp sát ${npcName.toUpperCase()}! Bỏ qua tương tác...`);
        return false;
    }

    return false;
}

// Cảm biến di chuyển thông minh (Engine Assisted - Cảm biến Vật cản)
async function moveTowardsTarget(tx, ty) {
    let waypoints = await findPath(tx, ty);
    if (!waypoints) {
        console.warn(`⚠️ [A-STAR]: Không tìm thấy đường đi an toàn. Dùng di chuyển thẳng...`);
        waypoints = [{ x: tx, y: ty }];
    } else {
        console.log(`🗺️ [A-STAR]: Đã vạch ra lộ trình với ${waypoints.length} điểm trung gian.`);
    }

    let waypointIdx = 0;
    let stuckCount = 0;
    let lastX = 0, lastY = 0;
    let maxSteps = 400; // Bảo vệ vòng lặp vô tận (khoảng 40-60 giây)

    while (isRunning && waypointIdx < waypoints.length && maxSteps > 0) {
        maxSteps--;
        const data = getGameData();
        if (!data || !data.player) break;

        const { x: curX, y: curY } = data.player;
        const target = waypoints[waypointIdx];
        const dx = target.x - curX;
        const dy = target.y - curY;

        // Chuyển waypoint khi đã đến gần (20px)
        if (Math.abs(dx) < 20 && Math.abs(dy) < 20) {
            waypointIdx++;
            stuckCount = 0;
            if (waypointIdx >= waypoints.length) break; // Hoàn thành
            continue;
        }

        // KIỂM TRA KẸT
        if (Math.abs(curX - lastX) < 0.2 && Math.abs(curY - lastY) < 0.2) {
            stuckCount++;
        } else {
            stuckCount = 0; // Đã nhúc nhích được
        }
        lastX = curX; lastY = curY;

        // BỊ KẸT: Kích hoạt thuật toán gỡ rối
        if (stuckCount > 8) {
            console.log(`🔄 [STUCK]: Phát hiện vật cản tại (${Math.round(curX)}, ${Math.round(curY)}). Đang lách...`);

            // THUẬT TOÁN LÁCH (ADVANCED JIGGLE): Di chuyển vuông góc với hướng đích
            const moveDir = Math.abs(dx) > Math.abs(dy) ? (dy > 0 ? 'down' : 'up') : (dx > 0 ? 'right' : 'left');
            const sideDirs = (moveDir === 'up' || moveDir === 'down') ? ['left', 'right'] : ['up', 'down'];
            const evasiveDir = sideDirs[stuckCount % 2];

            console.log(`🚦 [LÁCH]: Thử đi hướng [${evasiveDir.toUpperCase()}] để vòng qua vật cản.`);
            await moveCharacter(evasiveDir, 400);

            stuckCount = 0;
            lastX = 0; lastY = 0; // Reset để không bị kẹt ngay lập tức
            continue;
        }

        // TÍNH TOÁN THỜI GIAN NHẤN PHÍM DỰA TRÊN QUÃNG ĐƯỜNG (DYNAMIC DURATION)
        const moveDist = Math.max(Math.abs(dx), Math.abs(dy));
        const dynamicDuration = Math.min(Math.max(moveDist * 4.5, 150), 800); // Tối thiểu 150ms, tối đa 800ms để kịp check vật cản

        console.log(`🏃 [MOVE]: Cách đích ${Math.round(moveDist)}px. Nhấn giữ ${Math.round(dynamicDuration)}ms.`);

        // Di chuyển theo waypoint hiện tại
        if (Math.abs(dx) > Math.abs(dy)) {
            await moveCharacter(dx > 0 ? 'right' : 'left', dynamicDuration);
        } else {
            await moveCharacter(dy > 0 ? 'down' : 'up', dynamicDuration);
        }
        await sleep(5);
    }

    // TRẢ VỀ TÌNH TRẠNG THỰC TẾ: Đã tới nơi (Bán kính 40px) hay chưa?
    const finalData = getGameData();
    if (finalData && finalData.player) {
        const finalDistX = Math.abs(tx - finalData.player.x);
        const finalDistY = Math.abs(ty - finalData.player.y);
        return (finalDistX < 40 && finalDistY < 40);
    }
    return false;
}

// Hàm di chuyển thẳng tuyệt đối (Dùng để đi giữa các node trong Graph)
// - Axis-aligned: X trước, Y sau
// - Dynamic Duration: 800ms (>100px), 70ms (<25px)
// - Node Snapping: Sai số < 14px
// - Evasive Jiggle: Stuck sau 3 hiệp (0.5s), lách vuông góc 150ms
async function moveStraight(tx, ty) {
    let stuckCount = 0;
    let lastX = 0, lastY = 0;
    let maxSteps = 200;

    while (isRunning && maxSteps > 0) {
        maxSteps--;
        const data = getGameData();
        if (!data || !data.player) break;

        const { x: curX, y: curY } = data.player;
        const dx = tx - curX;
        const dy = ty - curY;

        // --- NODE SNAPPING (Sai số < 14px) ---
        if (Math.abs(dx) < 14 && Math.abs(dy) < 14) {
            console.log(`🎯 [SNAP]: Đã neo thành công tại (${Math.round(curX)}, ${Math.round(curY)})`);
            break;
        }

        // --- INSTANT REFLEX (Phát hiện kẹt sau 3 hiệp / ~0.5 giây) ---
        // Tại sao 3 hiệp? Vì mỗi hiệp moveCharacter + sleep mất khoảng 150ms-800ms.
        if (Math.abs(curX - lastX) < 1 && Math.abs(curY - lastY) < 1) {
            stuckCount++;
        } else {
            stuckCount = 0;
        }
        lastX = curX; lastY = curY;

        // --- INSTANT REFLEX (Lách vuông góc 90 độ) ---
        if (stuckCount >= 3) {
            console.warn(`🚧 [STUCK-REFLEX]: Bị chặn! Thực hiện LÁCH VUÔNG GÓC 150ms...`);

            // Xác định trục đang đi để lách theo trục còn lại
            const isMovingX = Math.abs(dx) >= 14;
            const evasiveDir = isMovingX
                ? (stuckCount % 2 === 0 ? 'up' : 'down')
                : (stuckCount % 2 === 0 ? 'left' : 'right');

            console.log(`👟 [JIGGLE]: Nhích sang [${evasiveDir.toUpperCase()}] trong 150ms.`);
            await moveCharacter(evasiveDir, 150);

            stuckCount = 0;
            continue;
        }

        // --- DYNAMIC DURATION & AXIS-ALIGNED (X sau đó mới đến Y) ---
        let moveDir = "";
        let dist = 0;

        if (Math.abs(dx) >= 14) {
            // Ưu tiên trục X
            moveDir = dx > 0 ? 'right' : 'left';
            dist = Math.abs(dx);
        } else if (Math.abs(dy) >= 14) {
            // Sau đó mới đến trục Y
            moveDir = dy > 0 ? 'down' : 'up';
            dist = Math.abs(dy);
        }

        if (moveDir) {
            let duration = 0;
            if (dist > 100) {
                duration = 800; // Chạy nhanh
                console.log(`🏃 [DYNAMIC]: Chạy nhanh (${Math.round(dist)}px) -> 800ms`);
            } else if (dist < 25) {
                duration = 70; // Micro-tuning (Nhích vi mô)
                console.log(`🤏 [MICRO-TUNING]: Nhích nhẹ (${Math.round(dist)}px) -> 70ms`);
            } else {
                // Tuyến tính giữa 25px và 100px (70ms đến 800ms)
                duration = 70 + (dist - 25) * (730 / 75);
            }

            await moveCharacter(moveDir, duration);
        }

        await sleep(50); // Nhịp nghỉ ngắn để engine cập nhật
    }
}

// Master NPC Data (Pixel Coordinates from Bottom-Right Corner)
// Conversion: 1s walk = 100 points
const MASTER_NPC_DATA = {
    "plaza": {
        "pumpkin' pete": { "x": 389, "y": 425, "island": "plaza" },
        "peggy": { "x": 203, "y": 392, "island": "plaza" },
        "bert": { "x": 776, "y": 122, "island": "plaza" },
        "tywin": { "x": 64, "y": 84, "island": "plaza" },
        "raven": { "x": 281, "y": 83, "island": "plaza" },
        "cornwell": { "x": 497, "y": 126, "island": "plaza" },
        "tinker": { "x": 0, "y": 0, "island": "plaza" },
        "betty": { "x": 529, "y": 122, "island": "plaza" },
        "blacksmith": { "x": 365, "y": 139, "island": "plaza" },
        "grimbly": { "x": 783, "y": 370, "island": "plaza" },
        "timmy": { "x": 627, "y": 122, "island": "plaza" },
        "grimtooth": { "x": 783, "y": 370, "island": "plaza" }
    },
    "beach": {
        "corale": { "x": 244, "y": 711, "island": "beach" },
        "tango": { "x": 475, "y": 423, "island": "beach" },
        "old salty": { "x": 68, "y": 223, "island": "beach" },
        "miranda": { "x": 475, "y": 423, "island": "beach" },
        "pharaoh": { "x": 68, "y": 95, "island": "beach" },
        "finn": { "x": 211, "y": 589, "island": "beach" },
        "finley": { "x": 245, "y": 457, "island": "beach" }
    },
    "kingdom": {
        "gambit": { "x": 250, "y": 150, "island": "kingdom" },
        "jester": { "x": 0, "y": 0, "island": "kingdom" },
        "victoria": { "x": 0, "y": -300, "island": "kingdom" }
    },
    "retreat": {
        "guria": { "x": 409, "y": 246, "island": "retreat" },
        "grubnuk": { "x": 409, "y": 246, "island": "retreat" },
        "gordo": { "x": 552, "y": 260, "island": "retreat" }
    }
};

// Ghi chú: ISLAND_GRAPHS hiện được tải từ file islands_graph_data.js để dễ quản lý tọa độ.


// BFS tìm đường ngắn nhất trên waypoint graph
function graphBFS(graph, startNodeId, endNodeId) {
    if (startNodeId === endNodeId) return [startNodeId];
    const adj = {};
    for (const [a, b] of graph.edges) {
        if (!adj[a]) adj[a] = [];
        if (!adj[b]) adj[b] = [];
        adj[a].push(b);
        adj[b].push(a);
    }
    const queue = [[startNodeId]];
    const visited = new Set([startNodeId]);
    while (queue.length > 0) {
        const path = queue.shift();
        const node = path[path.length - 1];
        for (const neighbor of (adj[node] || [])) {
            if (neighbor === endNodeId) return [...path, neighbor];
            if (!visited.has(neighbor)) {
                visited.add(neighbor);
                queue.push([...path, neighbor]);
            }
        }
    }
    return null; // Không có đường
}

// Tìm node gần nhất với tọa độ (x, y) trong graph
function findNearestNode(graph, x, y) {
    let best = null, bestDist = Infinity;
    for (const [id, node] of Object.entries(graph.nodes)) {
        const d = Math.abs(node.x - x) + Math.abs(node.y - y);
        if (d < bestDist) { bestDist = d; best = id; }
    }
    return best;
}

// Điều hướng nhân vật qua đồ thị đến tọa độ đích
// - Ưu tiên dùng đồ thị user tự nhập (userNodeGraphs)
// - Fallback sang ISLAND_GRAPHS cứng
// - Di chuyển giữa 2 node: đi ngang trước (X), rồi dọc (Y)
async function navigateViaGraph(targetX, targetY) {
    const island = getCurrentIsland() || 'plaza';
    // Ưu tiên user graph, fallback sang hardcoded graph
    const graph = (userNodeGraphs[island] && Object.keys(userNodeGraphs[island].nodes || {}).length > 0)
        ? userNodeGraphs[island]
        : window.SFL_ISLAND_GRAPHS[island];

    if (!graph || !graph.nodes || Object.keys(graph.nodes).length === 0) {
        console.warn(`⚠️ [GRAPH]: Không có đồ thị cho island [${island}]. Dùng di chuyển thẳng.`);
        return false;
    }

    const data = getGameData();
    if (!data || !data.player) return false;

    const { x: curX, y: curY } = data.player;
    let startNode = findNearestNode(graph, curX, curY);

    // Ưu tiên node 'root' nếu ĐÂY LÀ LẦN DI CHUYỂN ĐẦU TIÊN khi vừa đổi map
    if (isNewMapMove && graph.nodes.root) {
        const distRoot = Math.abs(graph.nodes.root.x - curX) + Math.abs(graph.nodes.root.y - curY);
        if (distRoot < 300) { // Tăng nhẹ phạm vi vì vừa vào map player có thể đứng hơi xa root
            console.log("📍 [ENTRY]: Lần đầu vào map. Ưu tiên vào đồ thị qua node [root].");
            startNode = "root";
            isNewMapMove = false; // Đã vào đồ thị thành công, từ sau cứ node gần nhất mà đi
        }
    }

    const endNode = findNearestNode(graph, targetX, targetY);
    console.log(`🗺️ [GRAPH-NAV]: Tìm đường từ node [${startNode}] → [${endNode}] trên map [${island}]`);

    const path = graphBFS(graph, startNode, endNode);
    if (!path || path.length === 0) {
        console.warn(`⚠️ [GRAPH]: Không có đường từ [${startNode}] tới [${endNode}]. Thử di chuyển thẳng.`);
        return false;
    }

    // Thêm điểm đích thật vào cuối path
    const waypoints = path.map(id => graph.nodes[id]);
    const finalTarget = { x: targetX, y: targetY, isTarget: true };
    waypoints.push(finalTarget);

    console.log(`✅ [GRAPH]: Tìm thấy lộ trình ${waypoints.length} điểm:`);
    path.forEach((id, i) => console.log(`   [${i + 1}] Node: ${id} (${graph.nodes[id].x}, ${graph.nodes[id].y})`));
    console.log(`   [${waypoints.length}] ĐÍCH: (${targetX}, ${targetY})`);

    // Di chuyển lần lượt qua từng waypoint
    for (let i = 0; i < waypoints.length; i++) {
        const wp = waypoints[i];
        const nodeName = i < path.length ? `node [${path[i]}]` : "ĐÍCH";

        if (!isRunning) break;

        // Gọi moveStraight một lần duy nhất, hàm này đã tự xử lý (X trước, Y sau) và Dynamic Duration
        await moveStraight(wp.x, wp.y);

        console.log(`📍 [WAYPOINT]: Đã tới ${nodeName} tại (${Math.round(wp.x)}, ${Math.round(wp.y)})`);
    }
    return true;
}

// Hỗ trợ xử lý các bảng xác nhận (Skip Order)
async function handleSkipConfirmation() {
    await sleep(300); // Giảm từ 1000ms -> 300ms
    const confirmVerbs = ['confirm', 'yes', 'ok', 'skip'];
    for (const verb of confirmVerbs) {
        const btn = findElementByText('.material-button, button', verb);
        if (btn) {
            console.log(`✅ [XÁC NHẬN]: Đã thấy nút [${verb}]. Đang click...`);
            await simulateFullClick(btn);
            await sleep(500); // Giảm từ 1500ms -> 500ms
            return true;
        }
    }
    return false;
}

async function scanDeliveries() {
    if (!isRunning) return;
    console.log("⚡ [INSTANT-SCAN]: Đang quét NPC trực tiếp qua ID ảnh trên lưới...");

    // BẢN ĐỒ ID NPC (Trích xuất từ đường dẫn ảnh animated_webp)
    const ID_MAP = {
        "392": "betty",
        "394": "pete",
        "48": "bert",
        "391": "peggy",
        "393": "blacksmith",
        "352": "raven",
        "395": "raven",
        "42": "cornwell",
        "390": "tywin",
        "43": "tinker",
        "44": "grimbly",
        "13": "timmy",
        "56": "grimtooth"
    };

    const panelInfo = getOpenPanelInfo();
    if (!panelInfo) {
        console.log("🔍 [INIT]: Codex chưa mở. Đang tìm biểu tượng Quyển sách...");
        const allImages = Array.from(document.querySelectorAll('img'));
        let targetImg = allImages.find(img => {
            const rect = img.getBoundingClientRect();
            return (Math.abs(rect.width - 31.5) < 5) && (rect.left > 50 && rect.left < 200);
        });

        if (targetImg) {
            console.log("🖱️ [CLICK]: Đã tìm thấy Icon Codex. Đang mở...");
            await simulateFullClick(targetImg);
            await sleep(3000);
        }
        return;
    }

    // Đợi Grids xuất hiện (Tối đa 3 lần thử)
    let grids = [];
    for (let wait = 0; wait < 3; wait++) {
        grids = panelInfo.el.querySelectorAll('.grid');
        if (grids.length > 0) break;
        console.log(`⏳ [WAIT]: Đang đợi lưới đơn hàng hiển thị (Lần ${wait + 1})...`);
        await sleep(1000);
    }

    if (!grids.length) {
        console.warn("⚠️ [ERROR]: Không tìm thấy lưới đơn hàng.");
        return;
    }

    let totalItemsSkipped = 0;
    let totalItemsReady = 0;
    memory.delivery_queue = [];

    console.log("🧹 [PHASE 1]: Dọn dẹp đơn cũ màu Cam (Skip)...");

    for (let gIndex = 0; gIndex < grids.length; gIndex++) {
        let grid = grids[gIndex];
        let items = Array.from(grid.querySelectorAll(':scope > div'));

        for (let i = 0; i < items.length; i++) {
            if (!isRunning) return;
            // Scan lại grids để tránh DOM bị stale sau khi skip
            const currentGrids = document.querySelectorAll('.grid');
            const currentItem = currentGrids[gIndex]?.querySelectorAll(':scope > div')[i];
            if (!currentItem) continue;

            const itemHTML = currentItem.innerHTML;
            const isOrange = itemHTML.includes('rgb(240, 145, 0)') || itemHTML.includes('rgb(240,145,0)');
            const padlockIcon = currentItem.querySelector('img[src*="lock"]') || currentItem.querySelector('img[src*="padlock"]');
            const heartIcon = currentItem.querySelector('img.absolute[class*="top-0.5"][class*="right-0.5"]');

            if (isOrange && !padlockIcon && !heartIcon) {
                try { currentItem.click(); } catch (e) { simulateFullClick(currentItem); }
                await sleep(500);

                const dr = getOpenPanelInfo()?.el;
                if (dr && (dr.textContent.includes("Skip in:") || dr.textContent.includes("24 hours"))) {
                    console.log(`⏳ [SKIP]: Mục ${gIndex + 1} đang chờ. Bỏ qua.`);
                    break;
                }

                const skipBtn = findElementByText('p, span, .material-button, button', 'Skip Order');
                if (skipBtn) {
                    console.log("⏭️ [SKIP]: Đang xóa đơn cũ...");
                    await simulateFullClick(skipBtn);
                    await handleSkipConfirmation();
                    totalItemsSkipped++;
                    await sleep(1000);
                    i--; // Quét lại vị trí này do danh sách bị dồn lên
                }
            }
        }
    }

    console.log("📋 [PHASE 2]: Gom đơn hàng Trái Tim (Click Thẻ Cha -> Đọc Tên)...");

    const scanGrids = document.querySelectorAll('.grid');
    let lastReadNPC = "";

    for (let gIdx = 0; gIdx < scanGrids.length; gIdx++) {
        const items = scanGrids[gIdx].querySelectorAll(':scope > div');
        console.log(`🔎 [SCAN]: Đang kiểm tra Mục ${gIdx + 1}...`);

        for (const item of items) {
            if (!isRunning) return;

            // 1. Tìm Trái Tim để biết đơn đã sẵn sàng
            const heartIcon = item.querySelector('img.absolute[class*="top-0.5"][class*="right-0.5"]');

            if (heartIcon) {
                // 2. Click vào thẻ cha (thẻ div có cursor-pointer) để chắc chắn mở bảng Detail
                const clickTarget = item.querySelector('div.cursor-pointer') || item;
                console.log("🎯 [TARGET]: Thấy Trái Tim. Đang Click để đọc tên NPC...");
                try { clickTarget.click(); } catch (e) { simulateFullClick(clickTarget); }

                let npcNameFound = "";
                // 3. Đợi bảng Detail bên phải cập nhật nội dung
                for (let retry = 0; retry < 6; retry++) {
                    await sleep(400);
                    const panel = getOpenPanelInfo()?.el;
                    if (!panel) continue;

                    // Đọc tên NPC từ thẻ <p class="capitalize text-xs"> trong bảng chi tiết
                    const nameEl = panel.querySelector('p.capitalize.text-xs');
                    if (nameEl && nameEl.textContent.trim().length > 2) {
                        const currentName = nameEl.textContent.toLowerCase().trim();
                        // Chống đọc nhầm tên cũ (đợi bảng cập nhật)
                        if (currentName !== lastReadNPC || retry > 3) {
                            npcNameFound = currentName;
                            lastReadNPC = currentName;
                            break;
                        }
                    }
                }

                if (npcNameFound) {
                    if (!memory.delivery_queue.includes(npcNameFound)) {
                        console.log(`✅ [GOM]: Đã nạp NPC: ${npcNameFound.toUpperCase()} vào hàng chờ.`);
                        memory.delivery_queue.push(npcNameFound);
                    }
                    totalItemsReady++;
                } else {
                    console.warn("⚠️ [WARN]: Click rồi nhưng không đọc được tên NPC!");
                }
            }
        }
    }

    console.log(`📊 [HOÀN TẤT]: Skip: ${totalItemsSkipped} | Gom được: ${memory.delivery_queue.length} | Tổng đơn: ${totalItemsReady}`);

    if (memory.delivery_queue.length > 0) {
        sortDeliveryQueue();
        console.log("📝 [HÀNG CHỜ]: " + memory.delivery_queue.join(" -> ").toUpperCase());
        const nextNPC = memory.delivery_queue[0];
        console.log(`🚀 [GO]: Xuất phát ngay: ${nextNPC.toUpperCase()}!`);
        targetNPC = nextNPC;
        currentTask = "TRAVEL";
        await forceClosePanels();
        saveMemory();
    } else {
        console.log("🏁 [AUTO-STOP]: Hiện tại không có đơn nào sẵn sàng. Dừng hệ thống để tiết kiệm CPU...");

        isRunning = false;
        isAutoEnabled = false;
        currentTask = "IDLE";

        await forceClosePanels();
        updateAutoBtnUI(); // Đồng bộ lại nút bấm thành START
        saveMemory();
    }
}

// --- HÀM ĐÓNG TẤT CẢ UI (NUCLEAR OPTION) ---
async function forceClosePanels() {
    console.log("🧹 [DỌN DẸP]: Đang quét và đóng tất cả bảng điều hướng/UI...");

    for (let i = 0; i < 5; i++) { // Thử 5 lần trong 1.5 giây
        const selectors = [
            'img[src*="close"]',
            '.cursor-pointer img[src*="close"]',
            'button[class*="close"]',
            'img.z-20.ml-3',
            '.p-2.cursor-pointer'
        ];

        selectors.forEach(s => {
            const btns = document.querySelectorAll(s);
            btns.forEach(btn => {
                simulateFullClick(btn);
                closed = true;
            });
        });

        if (closed) {
            await sleep(500);
            if (!isAnyUIPanelOpen()) return; // Thoát sớm nếu đã đóng xong
        }

        // Đã gỡ bỏ phím ESC theo yêu cầu người dùng

        if (closed) {
            console.log(`👋 [Lần ${i + 1}]: Đã phát lệnh đóng UI.`);
            await sleep(300);
        } else {
            // Nếu không thấy nút nào nữa sau lần 1, có thể đã đóng xong
            if (i > 0) break;
            await sleep(200);
        }
    }
}

// Lấy tên map hiện tại từ URL (vd: /world/plaza -> "plaza")
function getCurrentIsland() {
    const hash = window.location.hash || '';
    const match = hash.match(/#\/world\/([^/?]+)/);
    return match ? match[1].toLowerCase() : null;
}

async function travelToIsland(islandName) {
    let currentIsland = getCurrentIsland();
    islandName = islandName.toLowerCase();

    console.log(`--- ✈️ DI CHUYỂN ĐẾN: ${islandName.toUpperCase()} (Hiện tại: ${currentIsland || 'unknown'}) ---`);

    // TRANSIT RULES: Beach <-> Kingdom phải qua Plaza
    if ((currentIsland === "beach" && islandName === "kingdom") ||
        (currentIsland === "kingdom" && islandName === "beach")) {
        console.warn(`🚀 [TRANSIT]: Đang ở ${currentIsland}, cần đến ${islandName}. Yêu cầu trung chuyển qua [PLAZA]!`);
        islandName = "plaza"; // Đích đến trung chuyển
    }

    if (currentIsland === islandName) {
        console.log(`✅ [TRAVEL]: Đã ở đúng map [${islandName}]. Không cần đổi URL.`);
        currentTask = "MOVE"; // Sẵn sàng di chuyển
        return;
    }

    // THỬ TÌM NÚT TRAVEL TRONG CODEX (FALLBACK NẾU HASH KHÔNG HOẠT ĐỘNG HOẶC ĐỂ LOCK UI)
    const islandLabel = islandName.charAt(0).toUpperCase() + islandName.slice(1);
    const travelBtn = findElementByText('.material-button, button', `Travel to ${islandLabel}`) ||
        findElementByText('.material-button, button', `Go to ${islandLabel}`) ||
        findElementByText('span', islandLabel);

    if (travelBtn && isAnyUIPanelOpen()) {
        console.log(`👉 [TRAVEL]: Tìm thấy nút di chuyển đến [${islandLabel}] trong Codex. Đang click...`);
        await simulateFullClick(travelBtn);
        await sleep(1000);
    }

    // Chuyển map bằng URL hash (chính xác 100%, cực nhanh)
    const targetUrl = `#/world/${islandName.toLowerCase()}`;
    if (window.location.hash !== targetUrl) {
        console.log(`🗺️ [TRAVEL]: Đang chuyển URL -> ${targetUrl}`);
        window.location.hash = targetUrl;
    }

    // Đợi game load map mới
    console.log(`⏳ [TRAVEL]: Đợi game load map [${islandName}]...`);
    await sleep(3000);

    // Xác nhận đã đến đúng map
    const newIsland = getCurrentIsland();
    const targetIslandName = islandName.toLowerCase();

    if (newIsland === targetIslandName) {
        console.log(`✅ [TRAVEL]: Đã đến [${newIsland}] thành công!`);

        // RELOAD KHI ĐẾN PLAZA ĐỂ ĐỒNG BỘ STATE (Theo yêu cầu User)
        if (newIsland === "plaza") {
            console.warn("🔄 [RELOAD]: Đã tới Plaza. Thực hiện làm mới trang để đồng bộ dữ liệu...");
            saveMemory();
            location.reload();
            return;
        }
        currentTask = "WAIT_SYNC";
    } else {
        console.warn(`⚠️ [TRAVEL]: URL chưa khớp (Hiện: ${newIsland}, Mong đợi: ${targetIslandName}). Đang đợi thêm...`);
        await sleep(1500);
        currentTask = "TRAVEL"; // Thử lại
    }
}

// Giả lập Click chuột vào tọa độ Screen Pixel trên Canvas
function simulateCanvasClick(x, y) {
    const canvas = document.querySelector('canvas');
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = rect.left + x;
    const clientY = rect.top + y;

    const common = {
        clientX, clientY,
        screenX: x, screenY: y,
        pageX: clientX, pageY: clientY,
        bubbles: true, cancelable: true, view: window
    };

    canvas.dispatchEvent(new MouseEvent('mousedown', common));
    canvas.dispatchEvent(new MouseEvent('mouseup', common));
    canvas.dispatchEvent(new MouseEvent('click', common));
}

async function interactWithNPC() {
    const name = (targetNPC || "").toUpperCase();
    const canvas = document.querySelector('canvas');
    console.log(`--- ⌨️ KÍCH HOẠT TƯƠNG TÁC: ${name} ---`);
    document.body.dataset.sflInteractSuccess = "false"; // Reset tín hiệu thành công

    // 1. Đảm bảo đóng Codex/UI trước khi tương tác
    await forceClosePanels();
    await sleep(800);

    for (let attempt = 0; attempt < 10; attempt++) {
        if (!isRunning) return;

        // KIỂM TRA TÍN HIỆU THÀNH CÔNG TỪ BRIDGE
        if (document.body.dataset.sflInteractSuccess === "true") {
            const method = document.body.dataset.sflInteractMethod || "UNKNOWN";
            console.log(`🎉 [XÁC NHẬN]: Đã nhận tín hiệu Giao hàng thành công cho ${targetNPC.toUpperCase()} bằng [${method}]!`);

            // XÓA NPC KHỎI HÀNG CHỜ
            if (memory.delivery_queue && memory.delivery_queue.length > 0) {
                const finished = memory.delivery_queue.shift();
                console.log(`🗑️ [QUEUE]: Đã giao xong cho [${finished.toUpperCase()}]. Xóa khỏi hàng chờ.`);
            }

            forceStopAllKeys();
            await sleep(1500);
            currentTask = "IDLE"; // Về IDLE để lấy đơn tiếp theo từ queue
            saveMemory();
            return;
        }

        console.log(`🔍 [1/3 - KIỂM TRA UI]: Đang tìm bảng chặn đường...`);
        const panelInfo = getOpenPanelInfo();
        let skipFire = false;

        if (panelInfo) {
            console.log(`👀 UI: ${panelInfo.type} (Text: ${panelInfo.el.textContent.slice(0, 30)}...)`);
            if (panelInfo.type === "NPC_DIALOG") {
                console.log("✅ [SUCCESS]: Bảng NPC đã mở sẵn. Tiến đến bước click Deliver (Bỏ qua Bắn).");
                skipFire = true;
            } else if (panelInfo.type === "CODEX") {
                console.warn("⚠️ [BLOCK]: Bảng Codex đang che Betty. Đang gọi dọn dẹp...");
                await forceClosePanels();
                await sleep(1000);
                continue;
            }
        } else {
            console.log("🆗 [UI]: Màn hình trống, sẵn sàng click NPC.");
        }

        if (!skipFire) {
            console.log(`--- 🎯 [THỬ LẦN ${attempt + 1}: ${name.toUpperCase()}] ---`);
            const safeZones = JSON.parse(document.body.dataset.sflSafeZones || "{}");
            const burstPoints = safeZones[targetNPC.toLowerCase()];

            console.log(`🚀 [ATOMIC-TRIGGER]: Đang bắn tổng lực vào ${targetNPC}...`);

            const canvas = document.querySelector('canvas');
            if (canvas) canvas.focus();

            document.dispatchEvent(new CustomEvent('SFL_TRIGGER_REQUEST', { detail: targetNPC }));

            if (burstPoints && Array.isArray(burstPoints)) {
                for (const pt of burstPoints) {
                    simulateCanvasClick(pt.x, pt.y);
                }
            }

            if (attempt > 1 && attempt % 2 === 0) {
                console.log(`🔄 [JIGGLE]: Nhích nhẹ để kích hoạt lại cảm biến va chạm...`);
                await moveCharacter('up', 100);
                await moveCharacter('down', 100);
            }
        }

        console.log(`🔍 [3/3 - HẬU KIỂM]: Đang tìm các nút chức năng trong bảng...`);

        const dialogOpen = document.querySelectorAll('[role="dialog"], div[id^="headlessui-dialog-panel-"]');
        const isRealNPCConversation = Array.from(dialogOpen).some(d => {
            const text = d.textContent.toLowerCase();
            return !text.includes('codex') && !text.includes('deliveries');
        });

        if (isRealNPCConversation || (panelInfo && panelInfo.type === "NPC_DIALOG")) {
            console.log("🔥 [KẾT QUẢ]: Đã thấy bảng hội thoại NPC hoạt động!");

            // 1. Quét tìm Nút Hành Động (Action Button)
            const terminalVerbs = ['deliver', 'complete', 'trade', 'claim', 'sell', 'buy', 'ok'];
            const transitionVerbs = ['next', 'continue', 'got it', 'skip', 'read'];

            let actionBtn = null;
            let isTerminal = false;

            // Tìm đích danh
            for (const verb of [...terminalVerbs, ...transitionVerbs]) {
                const btn = findElementByText('.material-button, button', verb);
                if (btn) {
                    actionBtn = btn;
                    isTerminal = terminalVerbs.includes(verb.toLowerCase());
                    break;
                }
            }

            // Hoặc lấy bừa nút to nhất ở cuối modal nếu không có tên rõ ràng (Loại bỏ nút X đóng)
            if (!actionBtn) {
                const buttons = document.querySelectorAll('[role="dialog"] button, .material-button');
                const validBtns = Array.from(buttons).filter(b => !b.innerHTML.includes('<svg') && b.textContent.trim().length > 0);
                if (validBtns.length > 0) {
                    actionBtn = validBtns[validBtns.length - 1]; // Nút cuối cùng thường là Action
                }
            }

            // 2. Thực thi Click lên Nút (hoặc click bừa vào thẻ Panel để skip chữ)
            if (actionBtn) {
                const btnText = actionBtn.textContent.trim();

                if (!AUTO_DELIVER_ENABLED) {
                    console.log(`⏸️ [TEST MODE]: Phát hiện Nút Hành động [${btnText}] nhưng AUTO_DELIVER đang TẮT. Đóng băng giao dịch để bạn tự Test!`);
                    currentTask = "IDLE"; // Đưa về chế độ rảnh rỗi
                    return; // Ngừng vòng lặp tương tác
                }

                console.log(`👉 Đang click vào nút: [${btnText}]...`);
                await simulateFullClick(actionBtn);

                if (isTerminal || btnText.toLowerCase().includes('deliver') || btnText.toLowerCase().includes('complete')) {
                    console.log(`🎉 [XÁC NHẬN]: Đã click nút CHỐT ĐƠN [MANUAL-UI-CLICK]! Giao hàng thành công!`);
                    forceStopAllKeys(); // Đảm bảo dừng mọi di chuyển (nếu có)

                    // XÓA NPC KHỎI HÀNG CHỜ (Trường hợp click tay vào nút UI)
                    if (memory.delivery_queue && memory.delivery_queue.length > 0) {
                        const finished = memory.delivery_queue.shift();
                        console.log(`🗑️ [QUEUE]: Đã giao xong cho [${finished.toUpperCase()}]. Xóa khỏi hàng chờ.`);
                    }

                    await sleep(3000);
                    currentTask = "IDLE"; // Chuyển về rảnh rỗi để quét mạng lệnh mới
                    saveMemory();
                    return; // Thoát hẳn
                } else {
                    await sleep(1000);
                    continue; // Qua trang hội thoại tiếp theo
                }
            } else {
                console.log("⏭️ [SKIP]: Không chộp được nút chữ, đành click đại vào Panel nền để lướt chữ...");
                const panel = document.querySelector('[role="dialog"] > div') || document.querySelector('[role="dialog"]');
                if (panel) await simulateFullClick(panel);
                await sleep(1000);
                continue;
            }
        }

        // Nếu bảng CÒN CHƯA MỞ, mà đã thử quá nhiều lần -> Bắt đầu nhích nhẹ sang ngang
        if (attempt > 2 && attempt % 2 !== 0 && !skipFire) {
            console.log("🚧 [JIGGLE]: Đang nhích nhẹ để thay đổi góc nhìn...");
            const jiggleDir = ['up', 'down', 'left', 'right'][attempt % 4];
            await moveCharacter(jiggleDir, 200);
        }
    }

    console.warn("❌ [THẤT BẠI]: Không thể tương tác sau 10 lần thử. Quay lại IDLE.");
    forceStopAllKeys();
    currentTask = "IDLE";
}

// COORDINATE RECORDING LOGIC
function startRecording(npcName) {
    console.log(`🔴 [GHI TỌA ĐỘ]: Đang thiết lập bản đồ cho ${npcName.toUpperCase()}...`);
    targetNPC = npcName;
    isRecording = true;
    currentX = 0; currentY = 0; // Tạm thời nháp, Reset sẽ ghi đè
    currentTask = "RESET"; // Luôn về góc trước
}

// Global Coordinate Tracking
window.addEventListener('keydown', (e) => {
    const dirMap = { 'ArrowUp': 'up', 'ArrowDown': 'down', 'ArrowLeft': 'left', 'ArrowRight': 'right' };
    const dir = dirMap[e.key];
    if (dir) activeKey = dir;
});

window.addEventListener('keyup', (e) => {
    const dirMap = { 'ArrowUp': 'up', 'ArrowDown': 'down', 'ArrowLeft': 'left', 'ArrowRight': 'right' };
    const dir = dirMap[e.key];
    if (dir === activeKey) activeKey = null;
});

async function mainLoop() {
    // Luôn đảm bảo UI bảng điều khiển được hiển thị (24/7)
    injectPremiumUI();

    if (!isRunning && !isRecording) return;

    try {
        await loadMemory();
        // ... (phần còn lại)

        // Kiểm tra chuyển map để ưu tiên node [root]
        const currentIsland = getCurrentIsland();
        if (currentIsland && currentIsland !== lastIsland) {
            console.log(`🌍 [ISLAND]: Phát hiện chuyển sang đảo mới [${currentIsland}]. Bật chế độ ưu tiên [root].`);
            lastIsland = currentIsland;
            isNewMapMove = true;
        }

        // Connection Handling
        const retryBtn = findElementByText('.material-button, button', 'Retry');
        if (retryBtn) { retryBtn.click(); await sleep(10000); return; }

        // Master UI Injection
        injectPremiumUI();

        if (isRecording) return; // Dừng tại đây khi đang ghi âm

        if (!isAutoEnabled) return; // Dừng Auto nếu nút xanh chưa bật

        switch (currentTask) {
            case "IDLE":
                // Kiểm tra hàng chờ trước khi quyết định quét lại
                if (memory.delivery_queue && memory.delivery_queue.length > 0) {
                    sortDeliveryQueue(); // Tái sáp xếp từ vị trí hiện tại sau mỗi lần giao
                    const nextNPC = memory.delivery_queue[0];
                    console.log(`📋 [QUEUE]: Hàng chờ còn ${memory.delivery_queue.length} đơn. Mục tiêu TIẾP THEO GẦN NHẤT: ${nextNPC.toUpperCase()}`);
                    targetNPC = nextNPC;
                    currentTask = "TRAVEL";
                } else {
                    await scanDeliveries();
                }
                break;
            case "TRAVEL":
                let travelData = null;
                let foundIsland = "";
                for (const island in MASTER_NPC_DATA) {
                    if (MASTER_NPC_DATA[island][targetNPC]) {
                        travelData = MASTER_NPC_DATA[island][targetNPC];
                        foundIsland = island;
                        break;
                    }
                }
                if (travelData) {
                    targetIsland = foundIsland;
                    await travelToIsland(targetIsland);
                    currentTask = "WAIT_SYNC"; // Chờ đồng bộ sau khi chuyển đảo
                } else {
                    currentTask = "IDLE";
                }
                break;
            case "WAIT_SYNC":
                const sync = getGameData();
                if (sync && sync.player) {
                    console.log("✅ [HỆ THỐNG]: Đồng bộ Engine thành công. Bắt đầu di chuyển...");
                    isNewMapMove = true; // Bot vừa chuyển map/reload, ưu tiên node 'root' khi di chuyển
                    currentTask = "MOVE";
                } else {
                    console.log("⏳ [ĐỢI]: Đang chờ tín hiệu Engine (Đèn Xanh)...");
                    await sleep(1000);
                }
                break;
            case "MOVE":
                // Luôn cập nhật tọa độ mới nhất qua GPS trước khi đi
                const liveTarget = findNPCInState(targetNPC);
                const masterData = (MASTER_NPC_DATA[targetIsland] || MASTER_NPC_DATA["plaza"] || {})[targetNPC];
                const finalTarget = liveTarget || masterData;

                if (finalTarget) {
                    const success = await executePathToNPC(finalTarget);
                    if (success) {
                        currentTask = "DELIVER";
                    } else {
                        console.error(`❌ [LỖI NẶNG]: Hệ thống Di chuyển ĐẦU HÀNG do kẹt vĩnh viễn không thể tới ${targetNPC.toUpperCase()}. Reset chu trình!`);
                        currentTask = "IDLE";
                    }
                } else {
                    console.warn(`❌ [MOVE]: Không tìm thấy tọa độ cho ${targetNPC}. Quay lại quét đơn...`);
                    currentTask = "IDLE";
                }
                break;
            case "DELIVER":
                await interactWithNPC();
                break;
        }

        // --- PERSISTENCE: Lưu trạng thái sau mỗi bước nhảy của State Machine ---
        saveMemory();

    } catch (e) {
        console.error("Main Loop Error:", e);
    }
}

// Start/Stop listener from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start") {
        const wasRunning = isRunning;
        isRunning = true;
        isAutoEnabled = true;
        console.log("SFL Bot Started via Popup");
        if (!wasRunning) loop();
    } else if (request.action === "stop") {
        isRunning = false;
        isAutoEnabled = false;
        console.log("SFL Bot Stopped via Popup");
    } else if (request.action === "reset") {
        currentTask = "IDLE";
        targetNPC = null;
        console.log("SFL Bot Reset to IDLE");
    } else if (request.action === "reload_graph") {
        chrome.storage.local.get(['sfl_node_graphs'], r => {
            userNodeGraphs = r.sfl_node_graphs || {};
            console.log('🔄 [GRAPH]: Đã reload đồ thị từ storage!', Object.keys(userNodeGraphs));
        });
    }
});

// --- OMNI BRIDGE LISTENER ---
let latestEngineData = null;
window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "SFL_OMNI_PULSE") {
        // if (!latestEngineData) console.log("📥 [BOT]: ✅ Nhận tín hiệu Omni-Pulse lần đầu!");
        latestEngineData = { player: event.data.player };
    }
});

async function loop() {
    while (isRunning) {
        await mainLoop();
        await sleep(200); // Giảm từ 500ms -> 200ms để tăng tốc quét lại
    }
}

// --- INIT & PERSISTENCE RESUME ---
(async () => {
    console.log("📡 [SYSTEM]: Khởi động Engine Persistence & Dashboard...");
    await loadMemory();
    await getUniqueHWID();

    // Hiển thị UI ngay lập tức
    injectPremiumUI();

    // KIỂM TRA BẢN QUYỀN NGAY KHI VÀO (STARTUP CHECK)
    const valid = await checkLicenseRemote();

    if (valid) {
        console.log(`✅ [LICENSE]: Bản quyền hợp lệ (${ownerName}).`);
        if (isRunning) {
            console.log(`🚀 [RESUME]: Tự động khôi phục nhiệm vụ: ${currentTask}`);
            loop();
        }
    } else {
        console.warn("❌ [SECURITY]: Cần kích hoạt bản quyền để sử dụng.");
        renderLicenseModal();
    }
})();

// --- UPDATED COORDINATE LOGIC ---
// Đã khai báo ở trên đầu file, không khai báo lại để tránh lỗi Lint

// INTERNAL ENGINE SENSOR (React Fiber - RADAR-X)
function getCurrentIsland() {
    const hash = window.location.hash;
    if (hash.includes('/plaza')) return 'plaza';
    if (hash.includes('/beach')) return 'beach';
    if (hash.includes('/kingdom')) return 'kingdom';
    if (hash.includes('/retreat')) return 'retreat';
    return null;
}

// INTERNAL ENGINE SENSOR (React Fiber - RADAR-X PRO)
function getGameData() {
    // --- ƯU TIÊN 0: OMNI-ENTITY GPS (BRIDGE) ---
    if (!document.body) return null;
    const posStr = document.body.dataset.sflPos;
    const entStr = document.body.dataset.sflEntities;
    const visStr = document.body.dataset.sflNPCVisuals;
    if (posStr) {
        const [x, y] = posStr.split(',').map(parseFloat);
        let entities = {};
        let visuals = {};
        try { if (entStr) entities = JSON.parse(entStr); } catch (e) { }
        try { if (visStr) visuals = JSON.parse(visStr); } catch (e) { }

        if (!isNaN(x) && !isNaN(y)) {
            return {
                player: { x, y },
                allPlayers: entities,
                visuals: visuals
            };
        }
    }

    // --- ƯU TIÊN 1: POST MESSAGE PULSE ---
    if (latestEngineData) return latestEngineData;

    try {
        // --- STEP 2: FIBER OMNI-SCAN (Phòng trường hợp Bridge bị crash) ---
        // Vẫn giữ Fiber làm dự phòng nếu Phaser bị đóng gói (Bundled)
        const nodes = document.querySelectorAll('*');
        for (let i = 0; i < Math.min(nodes.length, 50); i++) {
            const el = nodes[i];
            const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
            if (!fiberKey) continue;

            const stack = [el[fiberKey]];
            let checked = 0;
            while (stack.length > 0 && checked < 3000) {
                const n = stack.pop();
                if (!n) continue;
                checked++;

                const p = n.memoizedProps || n.pendingProps;
                const s = n.stateNode;

                // --- TRƯỜNG HỢP LOGIC: mmoService ---
                let mmo = p?.mmoService || s?.mmoService;
                if (!mmo && n.dependencies?.firstContext) {
                    let c = n.dependencies.firstContext;
                    while (c) {
                        if (c.memoizedValue?.mmoService) { mmo = c.memoizedValue.mmoService; break; }
                        c = c.next;
                    }
                }

                if (mmo?.state?.context?.server?.state?.players) {
                    const ctx = mmo.state.context;
                    const sid = ctx.server.sessionId;
                    const pls = ctx.server.state.players;
                    const ply = pls.get ? pls.get(sid) : pls[sid];
                    if (ply && typeof ply.x === 'number') return { player: { x: ply.x, y: ply.y }, allPlayers: pls };
                }

                if (n.child) stack.push(n.child);
                if (n.sibling) stack.push(n.sibling);
            }
        }
    } catch (e) { }
    return null;
}

function findNPCInState(npcName) {
    const data = getGameData();
    if (!data || !data.allPlayers) return null;

    const players = Object.values(data.allPlayers);
    const npc = players.find(p => p.username && p.username.toLowerCase().includes(npcName.toLowerCase()) && p.username !== "yourbabyboo");

    if (npc) {
        // Deep Search tọa độ x, y (Phòng trường hợp nằm trong .body hoặc nested)
        let tx = npc.x, ty = npc.y;
        if (tx === undefined && npc.body) { tx = npc.body.x; ty = npc.body.y; }

        // Kiểm tra tính hợp lệ của số
        if (typeof tx === 'number' && typeof ty === 'number' && !isNaN(tx)) {
            return { x: tx, y: ty };
        }
    }
    return null;
}

// Làm sạch bộ nhớ NPC bị hỏng (Sanitization)
function sanitizeNPCObject(obj) {
    if (!obj) return null;
    // Nếu có 'path' mà không có x/y, hoặc tọa độ là NaN -> Xóa bỏ
    if (obj.path && (obj.x === undefined || isNaN(obj.x))) return null;
    if (typeof obj.x !== 'number') return null;
    return obj;
}

// HYBRID NAVIGATION ENGINE
let lastPulseTime = Date.now();
setInterval(() => {
    const data = getGameData();
    const syncIndicator = document.getElementById('sync-indicator');

    if (data && data.player) {
        currentX = data.player.x;
        currentY = data.player.y;

        // Cập nhật tọa độ lên UI Radar
        const radarX = document.getElementById('radar_x');
        const radarY = document.getElementById('radar_y');
        if (radarX) radarX.innerText = Math.round(currentX);
        if (radarY) radarY.innerText = Math.round(currentY);

        if (syncIndicator) {
            syncIndicator.style.background = '#2ed573'; // Xanh
            syncIndicator.style.boxShadow = '0 0 10px #2ed573';
        }
        lastPulseTime = Date.now();
    }
    else if (activeKey) {
        // DEAD RECKONING MODE
        if (syncIndicator) {
            syncIndicator.style.background = '#ff4757'; // Đỏ
            syncIndicator.style.boxShadow = '0 0 10px #ff4757';
        }
        const now = Date.now();
        const duration = now - lastPulseTime;
        const distance = duration * BASE_SPEED * (memory.speedMultiplier || 1.0);
        if (activeKey === 'up') currentY -= distance;
        if (activeKey === 'down') currentY += distance;
        if (activeKey === 'left') currentX -= distance;
        if (activeKey === 'right') currentX += distance;
    } else {
        if (syncIndicator) {
            syncIndicator.style.background = '#555'; // Xám
            syncIndicator.style.boxShadow = 'none';
        }
    }

    const inX = document.getElementById('manual_x');
    const inY = document.getElementById('manual_y');
    if (inX && inY) {
        if (document.activeElement !== inX && document.activeElement !== inY) {
            inX.value = Math.round(currentX);
            inY.value = Math.round(currentY);
        }
    }
    lastPulseTime = Date.now();
}, 500);

function stopRecording() {
    isRecording = false;
    memory.npcs[targetNPC] = {
        x: Math.round(currentX),
        y: Math.round(currentY),
        island: targetIsland || "plaza"
    };
    saveMemory();
    console.log(`✅ [GHI TỌA ĐỘ]: Đã lưu Pixel (${Math.round(currentX)}, ${Math.round(currentY)}) cho ${targetNPC}!`);
}

function injectPremiumUI() {
    if (document.getElementById('sfl-premium-ui')) return;

    const ui = document.createElement('div');
    ui.id = "sfl-premium-ui";
    ui.style.cssText = `
        position: fixed; bottom: 80px; left: 20px; width: 260px;
        background: rgba(10, 10, 10, 0.95); backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 215, 0, 0.5); border-radius: 16px; 
        padding: 18px; z-index: 10000; color: white; font-family: system-ui;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    `;

    ui.innerHTML = `
        <div style="font-weight: 800; font-size: 14px; margin-bottom: 12px; text-align: center; color: #FFD700; border-bottom: 1px solid rgba(255,215,0,0.2); padding-bottom: 8px;">SFL PRO: ENGINE LINKED</div>
        <div style="background: rgba(0,255,0,0.05); padding: 12px; border-radius: 10px; margin-bottom: 12px; border: 1px dashed #4CAF50;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <div style="display:flex; align-items:center; gap:5px;">
                    <span style="font-size:8px; color:#4CAF50; font-weight:bold;">RADAR</span>
                    <span id="sync-indicator" style="width: 8px; height: 8px; border-radius: 50%; background: #555;"></span>
                </div>
                <button id="deep_scan_btn" style="font-size: 9px; background: rgba(255, 69, 0, 0.2); color: #FF4500; border: 1px solid #FF4500; padding: 2px 8px; border-radius: 4px; cursor: pointer;">DÒ TÌM SÂU</button>
            </div>
            <div style="font-size: 26px; font-weight: 800; font-family: monospace; color: #2ed573; text-align: center; margin: 5px 0;">
                <span id="radar_x">0</span>, <span id="radar_y">0</span>
            </div>
            <div id="target_npc_disp" style="text-align:center; font-size:10px; color:#FFD700; font-weight:bold; margin-bottom:5px;">
                MT: ${targetNPC ? targetNPC.toUpperCase() : "KHÔNG CÓ"}
            </div>
            <div style="display:flex; gap:5px; margin-top:10px;">
                <input type="number" id="manual_x" value="0" style="flex:1; background:transparent; border:1px solid #333; color:#2ed573; font-size:10px; padding:2px;">
                <input type="number" id="manual_y" value="0" style="flex:1; background:transparent; border:1px solid #333; color:#2ed573; font-size:10px; padding:2px;">
            </div>
        </div>
        <button id="auto_btn" style="width:100%; padding:12px; border:none; border-radius:8px; font-weight:800; background:#333; color:white; cursor:pointer; margin-bottom: 12px;">🚀 BẮT ĐẦU GIAO HÀNG (START)</button>
        <div style="margin-bottom: 12px;">
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#888; margin-bottom:4px;"><span>TỐC ĐỘ</span><span id="speed_disp">${memory.speedMultiplier}x</span></div>
            <input type="range" id="speed_slide" min="0.5" max="2" step="0.1" value="${memory.speedMultiplier}" style="width:100%; accent-color:#FFD700;">
        </div>
        <div style="display:flex; gap:8px;">
            <button id="export_btn" style="flex:1; padding:8px; background:#444; color:white; border:none; border-radius:4px; font-size:10px; cursor:pointer;">EXPORT</button>
            <button id="save_btn" style="flex:1; padding:8px; background:linear-gradient(135deg, #FFD700 0%, #B8860B 100%); color:black; border:none; border-radius:4px; font-size:10px; font-weight:bold; cursor:pointer;">SAVE ALL</button>
        </div>
        <div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); font-size: 8px; color: #555; display: flex; flex-direction: column; gap: 4px;">
            <div style="display:flex; justify-content:space-between;">
                <span>OWNER: <span style="color:#FFD700">${ownerName}</span></span>
                <span>KEY: <span style="color:#2ed573">${licenseKey.substring(0, 8)}...</span></span>
            </div>
            <div style="text-align: right; color: #444;">ID: ${userHWID}</div>
        </div>
    `;
    document.body.appendChild(ui);
    initUIEvents();
}

// Đồng bộ hóa Giao diện Nút Bấm Tự động
function updateAutoBtnUI() {
    const autoBtn = document.getElementById('auto_btn');
    if (!autoBtn) return;

    autoBtn.innerText = isAutoEnabled ? '🛑 DỪNG GIAO HÀNG (STOP)' : '🚀 BẮT ĐẦU GIAO HÀNG (START)';

    // Màu sắc theo trạng thái
    if (isAutoEnabled) {
        autoBtn.style.background = '#ff4757'; // Màu Đỏ khi đang chạy (để dừng)
        autoBtn.style.color = '#fff';
    } else {
        autoBtn.style.background = '#333'; // Màu Xám khi đang dừng
        autoBtn.style.color = '#fff';
    }
}

function initUIEvents() {
    const dBtn = document.getElementById('deep_scan_btn');
    if (dBtn) dBtn.onclick = () => {
        console.log("📡 RADAR-X OMNI: Deep Search Triggered...");
        const d = getGameData();
        if (d && d.player) alert(`TÌM THẤY! Tọa độ: X: ${Math.round(d.player.x)}, Y: ${Math.round(d.player.y)}`);
        else alert("LỖI: Không tìm thấy Engine. Bạn hãy di chuyển nhân vật một chút hoặc nhấn F5 rồi thử lại.");
    };

    const autoBtn = document.getElementById('auto_btn');
    if (autoBtn) {
        // Khởi tạo giao diện theo trạng thái mặc định
        updateAutoBtnUI();

        autoBtn.onclick = async () => {
            if (!isAutoEnabled) {
                // ĐANG TẮT -> NHẤN ĐỂ BẬT: Kiểm tra bản quyền TRƯỚC khi chạy
                const valid = await checkLicenseRemote();
                if (!valid) {
                    renderLicenseModal();
                    return;
                }

                isAutoEnabled = true;
                isRunning = true;
                console.log("🚀 [HỆ THỐNG]: Xác thực thành công. Bắt đầu Giao hàng...");

                updateAutoBtnUI();
                chrome.storage.local.set({ isRunning: true });

                memory.delivery_queue = [];
                currentTask = "IDLE";
                saveMemory();
                loop();
            } else {
                // ĐANG BẬT -> NHẤN ĐỂ TẮT: Dừng ngay lập tức (Không cần check license)
                isAutoEnabled = false;
                isRunning = false;
                console.log("🛑 [HỆ THỐNG]: Đã dừng tiến trình.");

                updateAutoBtnUI();
                chrome.storage.local.set({ isRunning: false });
                currentTask = "IDLE";
                saveMemory();
            }
        };
    }

    const speedSlide = document.getElementById('speed_slide');
    if (speedSlide) speedSlide.oninput = () => {
        memory.speedMultiplier = parseFloat(speedSlide.value);
        const disp = document.getElementById('speed_disp');
        if (disp) disp.innerText = speedSlide.value + 'x';
    };

    const inX = document.getElementById('manual_x');
    const inY = document.getElementById('manual_y');
    if (inX) inX.onchange = () => { currentX = parseFloat(inX.value); };
    if (inY) inY.onchange = () => { currentY = parseFloat(inY.value); };

    const exportBtn = document.getElementById('export_btn');
    if (exportBtn) exportBtn.onclick = () => {
        const liveData = getGameData();
        const searchList = ["pete", "peggy", "bert", "tywin", "raven", "cornwell", "tinker", "betty", "blacksmith", "grimbly", "timmy", "grimtooth"];

        const filteredLive = {};
        if (liveData && liveData.allPlayers) {
            Object.keys(liveData.allPlayers).forEach(name => {
                const lowerName = name.toLowerCase();
                if (searchList.some(s => lowerName.includes(s))) {
                    filteredLive[name] = liveData.allPlayers[name];
                }
            });
        }

        const output = {
            timestamp: new Date().toISOString(),
            target_npcs_found: filteredLive,
            full_saved_memory: memory
        };
        console.log("⬇️ [SFL EXPORT]: TRÍCH XUẤT TỌA ĐỘ NPC (FILTERED)");
        console.log(JSON.stringify(output, null, 2));
        alert("Đã Export Tọa độ các NPC chỉ định vào Console (F12)!");
    };

    const saveBtn = document.getElementById('save_btn');
    if (saveBtn) saveBtn.onclick = () => {
        saveMemory();
        saveBtn.innerText = "✓ OK!";
        setTimeout(() => { saveBtn.innerText = "SAVE ALL"; }, 2000);
    };
}

// Global UI Heartbeat (20Hz for Real-time smoothness)
setInterval(() => {
    const data = getGameData();
    const radarX = document.getElementById('radar_x');
    const radarY = document.getElementById('radar_y');
    const targetDisp = document.getElementById('target_npc_disp');
    const indicator = document.getElementById('sync-indicator');

    if (targetDisp) {
        targetDisp.innerText = "MT: " + (targetNPC ? targetNPC.toUpperCase() : "KHÔNG CÓ");
    }

    if (data && data.player) {
        if (radarX && radarY) {
            radarX.innerText = Math.round(data.player.x);
            radarY.innerText = Math.round(data.player.y);
        }
        if (indicator) {
            indicator.style.background = "#2ed573";
            indicator.style.boxShadow = "0 0 5px #2ed573";
        }

        // --- HỆ THỐNG TỰ ĐỘNG HIỆU CHUẨN (AUTO-CALIBRATION) ---
        // Nếu thấy NPC nào đó từ Bridge, tự động cập nhật tọa độ vào bộ nhớ
        if (data.allPlayers) {
            for (const name in data.allPlayers) {
                if (KNOWN_NPCS.includes(name.toLowerCase())) {
                    const pos = data.allPlayers[name];
                    const existing = memory.npcs[name];
                    // Chỉ cập nhật nếu tọa độ khác biệt đáng kể (>5px) để tránh lưu file liên tục
                    if (!existing || Math.abs(existing.x - pos.x) > 5 || Math.abs(existing.y - pos.y) > 5) {
                        memory.npcs[name.toLowerCase()] = { x: pos.x, y: pos.y, island: targetIsland || "plaza" };
                        saveMemory();
                        // Chỉ Log nếu NPC này là mục tiêu hiện tại để tránh loãng Log
                        if (targetNPC && name.toLowerCase() === targetNPC.toLowerCase()) {
                            console.log(`📍 [AUTO-CALIB]: Đã cập nhật tọa độ mới cho ${name.toUpperCase()}!`);
                        }
                    }
                }
            }
        }
    } else {
        if (indicator) {
            indicator.style.background = "#555";
            indicator.style.boxShadow = "none";
        }
    }
}, 50); 
