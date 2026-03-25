// Sunflower Land Auto-Deliver Content Script
let isRunning = false;
let memory = {
    npcs: {}, // Lưu tọa độ tùy chỉnh của người dùng: { "betty": { "path": [...], "island": "plaza" } }
    islands: {},
    ready_deliveries: [],
    speedMultiplier: 1.0
};

// State machine variables
let currentTask = "IDLE"; // SCAN, TRAVEL, RESET, MOVE, DELIVER, RECORD
let targetNPC = null;
let targetIsland = null;
let isAutoEnabled = false;
let stuckCount = 0;
let detourTicks = 0;
let detourDir = '';
let stuckMemory = {}; // { dir: timestamp }

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
        // Nếu chúng ta đang tìm modal "Go Home", thì ĐƯỢC PHÉP tìm trong UI
        if (targetText.includes('home') || targetText.includes('go home') || targetText.includes('return')) {
            return true;
        }

        if (isUI) return false;
        return true;
    });
}

// Utility to sleep
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Load memory from file/local storage
async function loadMemory() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['sfl_memory'], (result) => {
            if (result.sfl_memory) {
                // Hợp nhất với cấu trúc mặc định để không mất thuộc tính mới
                memory = { ...memory, ...result.sfl_memory };
                // Chốt lại giá trị mặc định nếu bị undefined từ storage
                if (typeof memory.speedMultiplier !== 'number') memory.speedMultiplier = 1.0;
            }
            resolve();
        });
    });
}

// Save memory
function saveMemory() {
    chrome.storage.local.set({ 'sfl_memory': memory });
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

// Emulate Arrow keys for movement (Keyboard Engine 3.0 - Full SFL Support)
// Emulate Arrow keys for movement with coordinate tracking
async function moveCharacter(direction, duration = 500) {
    const adjustedDuration = duration * (memory.speedMultiplier || 1.0);
    const keys = { 'up': 'ArrowUp', 'down': 'ArrowDown', 'left': 'ArrowLeft', 'right': 'ArrowRight' };
    const key = keys[direction] || direction;
    const keyCodes = { 'ArrowUp': 38, 'ArrowDown': 40, 'ArrowLeft': 37, 'ArrowRight': 39 };
    const keyCode = keyCodes[key];

    // Update Internal Coordinate Grid
    const distance = duration * BASE_SPEED * (memory.speedMultiplier || 1.0);
    if (direction === 'up') currentY -= distance;
    if (direction === 'down') currentY += distance;
    if (direction === 'left') currentX -= distance;
    if (direction === 'right') currentX += distance;

    // console.log(`🚀 [COORD]: X: ${Math.round(currentX)} | Y: ${Math.round(currentY)} | Dir: ${direction.toUpperCase()}`);

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

    await sleep(50);
}

// RESET TO CORNER (Adaptive with Modal Detection)
async function resetToCorner() {
    console.log("📐 [RESET]: Đang di chuyển về góc (Hiệu chuẩn 0-0)...");

    // 1. Move DOWN until boundary modal appears
    for (let i = 0; i < 40; i++) { // Max 40 steps to prevent infinite loops
        const modal = findElementByText('h1, h2, span, p, button, div', 'Go Home') ||
            findElementByText('h1, h2, span, p, button, div', 'Return Home');
        if (modal) {
            console.log("🌊 [HỆ THỐNG]: Đã chạm biên DƯỚI.");
            break;
        }
        await moveCharacter('down', 500);
        if (!isRunning && !isRecording) return;
    }

    // Clear Modal
    let modalBtn = document.querySelector('img[src*="close"]') || findElementByText('button, span', 'Go Home') || findElementByText('button, span', 'Return Home');
    if (modalBtn) { modalBtn.click(); await sleep(1000); }

    // 2. Move RIGHT until boundary modal appears
    for (let i = 0; i < 40; i++) {
        const modal = findElementByText('h1, h2, span, p, button, div', 'Go Home') ||
            findElementByText('h1, h2, span, p, button, div', 'Return Home');
        if (modal) {
            console.log("🌊 [HỆ THỐNG]: Đã chạm biên PHẢI.");
            break;
        }
        await moveCharacter('right', 500);
        if (!isRunning && !isRecording) return;
    }

    // Clear Modal again
    modalBtn = document.querySelector('img[src*="close"]') || findElementByText('button, span', 'Go Home') || findElementByText('button, span', 'Return Home');
    if (modalBtn) modalBtn.click();
    await sleep(500);

    // ZERO THE COORDINATES
    currentX = 0;
    currentY = 0;

    console.log("✅ [RESET]: Đã về góc 0-0. Hệ tọa độ đã được hiệu chuẩn!");
    currentTask = "RECORD";
}

// MOVE TO COORDINATE (Targeted Navigation)
async function moveToCoord(targetX, targetY) {
    const dx = targetX - currentX;
    const dy = targetY - currentY;

    console.log(`🎯 [NAV]: Moving to (${Math.round(targetX)}, ${Math.round(targetY)}) | Delta: [${Math.round(dx)}, ${Math.round(dy)}]`);

    // Move X first
    if (Math.abs(dx) > 1) { // 1px threshold
        const dir = dx > 0 ? 'right' : 'left';
        const duration = Math.abs(dx) / (BASE_SPEED * (memory.speedMultiplier || 1.0));
        await moveCharacter(dir, duration);
    }

    // Move Y second
    if (Math.abs(dy) > 1) {
        const dir = dy > 0 ? 'down' : 'up';
        const duration = Math.abs(dy) / (BASE_SPEED * (memory.speedMultiplier || 1.0));
        await moveCharacter(dir, duration);
    }
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
        const reached = await moveTowardsTarget(target.x, target.y);
        
        if (reached) {
            console.log(`🎯 [TỚI ĐÍCH]: Đã chạm vùng tương tác của ${npcName.toUpperCase()}.`);
            return true;
        } else {
            console.warn(`❌ [LỠ ĐƯỜNG]: Bị kẹt, không thể áp sát ${npcName.toUpperCase()}! Bỏ qua tương tác...`);
            return false;
        }
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
        if (stuckCount > 10) {
            console.log(`🔄 [RE-PATH]: Đang tính toán lại đường đi do kẹt...`);
            waypoints = await findPath(tx, ty);
            waypointIdx = 0;
            stuckCount = 0;
            
            if (!waypoints || waypoints.length === 0) {
                console.log("🚦 [LÁCH QUA]: Đường bị bịt kín! Kích hoạt thuật toán Lách (Random Jiggle)...");
                const randDirs = ['up', 'down', 'left', 'right'];
                const evasiveDir = randDirs[Math.floor(Math.random() * randDirs.length)];
                await moveCharacter(evasiveDir, 400); // Né góc lớn
                waypoints = [{ x: tx, y: ty }]; // Chuyển sang đi thẳng lại
                continue;
            }
            continue;
        }

        // Di chuyển theo waypoint hiện tại
        if (Math.abs(dx) > Math.abs(dy)) {
            await moveCharacter(dx > 0 ? 'right' : 'left', 150);
        } else {
            await moveCharacter(dy > 0 ? 'down' : 'up', 150);
        }
        await sleep(10);
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

// Master NPC Data (Pixel Coordinates from Bottom-Right Corner)
// Conversion: 1s walk = 100 points
const MASTER_NPC_DATA = {
    "plaza": {
        "pete": { "x": 370, "y": 430, "island": "plaza" },
        "peggy": { "x": 211, "y": 401, "island": "plaza" },
        "bert": { "x": -400, "y": -800, "island": "plaza" },
        "tywin": { "x": -150, "y": 100, "island": "plaza" },
        "raven": { "x": 200, "y": -1000, "island": "plaza" },
        "cornwell": { "x": 0, "y": 0, "island": "plaza" },
        "tinker": { "x": 500, "y": -1000, "island": "plaza" },
        "betty": { "x": 534, "y": 98, "island": "plaza" },
        "blacksmith": { "x": 366, "y": 130, "island": "plaza" },
        "grimbly": { "x": 0, "y": -800, "island": "plaza" },
        "timmy": { "x": 0, "y": 0, "island": "plaza" },
        "grimtooth": { "x": 809, "y": 362, "island": "plaza" }
    },
    "beach": {
        "corale": { "x": -350, "y": 120, "island": "beach" },
        "tango": { "x": 488, "y": 411, "island": "beach" },
        "old salty": { "x": -400, "y": 0, "island": "beach" },
        "miranda": { "x": 0, "y": 0, "island": "beach" },
        "pharaoh": { "x": -500, "y": -300, "island": "beach" },
        "finn": { "x": 250, "y": -80, "island": "beach" },
        "finley": { "x": 0, "y": 0, "island": "beach" }
    },
    "kingdom": {
        "gambit": { "x": 250, "y": 150, "island": "kingdom" },
        "jester": { "x": 0, "y": 0, "island": "kingdom" },
        "victoria": { "x": 0, "y": -300, "island": "kingdom" }
    },
    "retreat": {
        "guria": { "x": -500, "y": -500, "island": "retreat" },
        "grubnuk": { "x": 0, "y": 0, "island": "retreat" },
        "gordo": { "x": 0, "y": 0, "island": "retreat" }
    }
};

async function scanDeliveries() {
    console.log("--- 🕵️ QUÁET GIAO HÀNG ---");

    // 1. Phá bỏ các bảng sai trước khi quét
    const wrongModal = findElementByText('h1, h2, span', 'Calendar') ||
        findElementByText('h1, h2, span', 'Events');

    if (wrongModal) {
        console.log("⚠️ Phát hiện bảng SAI (Lịch/Sự kiện). Đang thoát...");
        const closeBtn = document.querySelector('img[src*="close"]') || document.querySelector('button[class*="close"]');
        if (closeBtn) closeBtn.click();
        else window.dispatchEvent(new MouseEvent('mousedown', { clientX: 10, clientY: 10, bubbles: true }));
        await sleep(1500);
        return;
    }

    // 2. Kiểm tra bảng Codex đã mở chưa
    console.log("🔍 [BƯỚC 1/2]: Kiểm tra trạng thái bảng Codex... (Sử dụng CSS Selector d-panel)");
    if (!isAnyUIPanelOpen()) {
        console.log("🎯 [BƯỚC 2/2]: Bảng chưa mở. Bắt đầu tìm ICON Vàng hoặc Heart để 'Gõ Cửa'...");
        const allImages = Array.from(document.querySelectorAll('img'));
        let targetImg = allImages.find(img => {
            const rect = img.getBoundingClientRect();
            // ĐẶC ĐIỂM QUYẾT ĐỊNH: Rộng đúng 31.5px, nằm ở Left > 50px (tránh Lịch)
            const isCorrectSize = Math.abs(rect.width - 31.5) < 2;
            const isSidebarZone = rect.left > 50 && rect.left < 150;

            if (isCorrectSize && isSidebarZone) {
                console.log(`🎯 PHÁT HIỆN: Kích thước ${rect.width.toFixed(2)}px tại Left ${rect.left.toFixed(1)}px`);
                return true;
            }
            return false;
        });

        if (targetImg) {
            console.log("📗 Đã tìm thấy Quyển sách Giao hàng! Đang click...");
            await simulateFullClick(targetImg);
            await sleep(3000);
            return;
        }

        console.warn("❌ KHÔNG tìm thấy icon Giao hàng. Đang chờ...");
        return;
    }

    console.log("✅ Codex đã mở. Đang quét biểu tượng TRÁI TIM (Đơn sẵn sàng)...");
    const readyItems = [];
    const gridItems = document.querySelectorAll('.grid > div');

    for (const item of gridItems) {
        // NHẬN DIỆN TIM ĐỎ: Dùng lại selector gốc đã được verify là chuẩn xác
        const heartIcon = item.querySelector('img.absolute.top-0\\.5.right-0\\.5.w-3') ||
            item.querySelector('img.absolute.top-0\\.5.right-0\\.5.sm\\:w-4');

        if (heartIcon) {
            console.log("❤️ PHÁT HIỆN: Trái tim đỏ Giao hàng!");

            // LẬP TỨC CLICK CHỌN ĐƠN HÀNG (Phục hồi thao tác cũ)
            console.log("👉 Đang click chọn đơn hàng...");
            try {
                heartIcon.parentElement.click();
            } catch (e) {
                simulateFullClick(item);
            }
            await sleep(1500); // Đợi bảng chi tiết bên phải tải dữ liệu

            let npcName = "";
            const itemHTML = item.innerHTML.toLowerCase();
            
            // CÁCH 1: Tìm tên NPC trực tiếp trong Avatar của thẻ (Nhanh & Chính xác nhất)
            // Nhờ đã lọc Ổ khóa (Padlock), thẻ này chắc chắn là thẻ xịn, không sợ parse nhầm thẻ của Bert!
            for (const name of KNOWN_NPCS) {
                if (itemHTML.includes(name) || itemHTML.includes(`${name}.png`)) {
                    npcName = name;
                    break;
                }
            }

            // CÁCH 2: Nếu chưa tìm thấy từ ảnh, quét text trong bảng chi tiết bên phải
            if (!npcName) {
                const detailPanel = document.querySelector('.flex.flex-col.items-center.p-2') ||
                    document.querySelector('.flex-1.flex.flex-col') ||
                    document.querySelector('[role="dialog"]') || document.body;

                const panelText = detailPanel ? detailPanel.textContent.toLowerCase() : "";
                const panelHTML = detailPanel ? detailPanel.innerHTML.toLowerCase() : "";

                console.log("📄 Đang quét tên NPC trong bảng chi tiết...");

                for (const name of KNOWN_NPCS) {
                    if (panelText.includes(name) || panelHTML.includes(name)) {
                        npcName = name;
                        break;
                    }
                }
            }

            if (npcName) {
                readyItems.push(npcName);
                console.log(`✅ Đã nhận diện đúng NPC: ${npcName.toUpperCase()}`);

                // Đóng Codex ngay lập tức để chuẩn bị di chuyển
                const closeBtn = document.querySelector('img[src*="close"]') || document.querySelector('button[class*="close"]');
                if (closeBtn) {
                    await simulateFullClick(closeBtn);
                    await sleep(1000);
                }

                targetNPC = npcName;
                currentTask = "TRAVEL";
                isRunning = true;
                saveMemory();
                
                // BẮT BUỘC DỪNG NGAY SAU KHI TÌM ĐƯỢC ĐƠN ĐẦU TIÊN
                break;
            } else {
                console.error("⚠️ KHÔNG nhận diện được NPC trong bảng này! Sẽ dừng quét để tránh click bừa bãi.");
                // BẮT BUỘC DỪNG ĐỂ KHÔNG QUÉT RỚT SANG CÁC TIM KHÁC! Chỉ xử lý 1 đơn tại 1 thời điểm.
                break;
            }
        }
    }

    if (readyItems.length > 0) {
        targetNPC = readyItems[0].toLowerCase().trim();
        console.log(`🎯 Mục tiêu: ${targetNPC.toUpperCase()}. Đang đóng Codex để đồng bộ...`);

        // 🏁 ĐÓNG CODEX NGAY LẬP TỨC 
        await forceClosePanels();
        await sleep(1000);
        currentTask = "TRAVEL";
    } else {
        console.log("🧊 Không có đơn hàng nào sẵn sàng. ĐANG ĐÓNG Codex để chờ...");
        await forceClosePanels();
        await sleep(1000);
        currentTask = "IDLE";
    }

    memory.ready_deliveries = readyItems;
    saveMemory();
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
    const currentIsland = getCurrentIsland();
    console.log(`--- ✈️ DI CHUYỂN ĐẾN: ${islandName.toUpperCase()} (Hiện tại: ${currentIsland || 'unknown'}) ---`);

    if (currentIsland === islandName.toLowerCase()) {
        console.log(`✅ [TRAVEL]: Đã ở đúng map [${islandName}]. Không cần đổi URL.`);
        currentTask = "MOVE";
        return;
    }

    // Đóng Codex/UI trước khi chuyển map
    const closeBtn = document.querySelector('img[src*="close"], .p-2.cursor-pointer');
    if (closeBtn) closeBtn.click();
    await sleep(300);

    // Chuyển map bằng URL hash (chính xác 100%, không cần click nút)
    const targetUrl = `#/world/${islandName.toLowerCase()}`;
    console.log(`🗺️ [TRAVEL]: Đang chuyển URL -> ${targetUrl}`);
    window.location.hash = `/world/${islandName.toLowerCase()}`;

    // Đợi game load map mới
    console.log(`⏳ [TRAVEL]: Đợi game load map [${islandName}]...`);
    await sleep(3000);

    // Xác nhận đã đến đúng map
    const newIsland = getCurrentIsland();
    if (newIsland === islandName.toLowerCase()) {
        console.log(`✅ [TRAVEL]: Đã đến [${newIsland}] thành công!`);
    } else {
        console.warn(`⚠️ [TRAVEL]: URL chưa khớp (Hiện: ${newIsland}, Mong đợi: ${islandName}). Đang đợi thêm...`);
        await sleep(1500);
    }

    currentTask = "WAIT_SYNC";
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

    // 1. Đảm bảo đóng Codex/UI trước khi tương tác
    await forceClosePanels();
    await sleep(800);

    for (let attempt = 0; attempt < 10; attempt++) {
        if (!isRunning) return;

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
                    console.log(`🎉 [XÁC NHẬN]: Đã click nút CHỐT ĐƠN! Giao hàng thành công!`);
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
    if (!isRunning && !isRecording) return;

    try {
        await loadMemory();

        // Connection Handling
        const retryBtn = findElementByText('.material-button, button', 'Retry');
        if (retryBtn) { retryBtn.click(); await sleep(10000); return; }

        // Master UI Injection
        injectPremiumUI();

        if (isRecording) {
            if (currentTask === "RESET") {
                await resetToCorner();
                currentTask = "RECORD";
            }
            return; // Dừng tại đây khi đang ghi âm
        }

        if (!isAutoEnabled) return; // Dừng Auto nếu nút xanh chưa bật

        switch (currentTask) {
            case "IDLE":
                await scanDeliveries();
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
        await sleep(500);
    }
}

// Auto-start UI
setTimeout(() => {
    console.log("🚀 [SYSTEM]: Initializing Premium UI...");
    injectPremiumUI();
}, 2000);

// --- UPDATED COORDINATE LOGIC ---
// Đã khai báo ở trên đầu file, không khai báo lại để tránh lỗi Lint

// INTERNAL ENGINE SENSOR (React Fiber - RADAR-X)
// INTERNAL ENGINE SENSOR (React Fiber - RADAR-X PRO)
function getGameData() {
    // --- ƯU TIÊN 0: OMNI-ENTITY GPS (BRIDGE) ---
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
    `;
    document.body.appendChild(ui);
    initUIEvents();
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
        // Khởi tạo giao diện theo trạng thái mặc định (DỪNG)
        autoBtn.innerText = isAutoEnabled ? '🛑 DỪNG GIAO HÀNG (STOP)' : '🚀 BẮT ĐẦU GIAO HÀNG (START)';
        autoBtn.style.background = isAutoEnabled ? '#2ed573' : '#333';
        autoBtn.style.color = isAutoEnabled ? '#111' : '#fff';

        autoBtn.onclick = () => {
            isAutoEnabled = !isAutoEnabled;
            isRunning = isAutoEnabled;
            chrome.storage.local.set({ isRunning: isAutoEnabled });

            autoBtn.innerText = isAutoEnabled ? '🛑 DỪNG GIAO HÀNG (STOP)' : '🚀 BẮT ĐẦU GIAO HÀNG (START)';
            autoBtn.style.background = isAutoEnabled ? '#ff4757' : '#333';
            autoBtn.style.color = '#fff';

            if (isRunning) {
                console.log("🚀 [HỆ THỐNG]: Bắt đầu tiến trình Giao hàng Tự động...");
                currentTask = "IDLE";
                loop();
            } else {
                console.log("🛑 [HỆ THỐNG]: Đã dừng tiến trình.");
                currentTask = "IDLE";
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
