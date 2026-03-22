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

// Recording variables
let isRecording = false;
let recordStartTime = 0;
let currentRecordPath = [];
let activeKey = null;
let currentX = 0;
let currentY = 0;
const BASE_SPEED = 0.1; // 100px per 1000ms at 1.0x speed

const KNOWN_NPCS = ["pete", "peggy", "bert", "betty", "guria", "raven", "tinker", "corale", "old salty", "stella", "finn", "eldric", "reginald", "gambit", "victoria", "grimbly", "blacksmith", "tywin", "grimlock", "pharaoh", "hank"];

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

    console.log(`🚀 [COORD]: X: ${Math.round(currentX)} | Y: ${Math.round(currentY)} | Dir: ${direction.toUpperCase()}`);
    
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
    // 🛡️ SENSOR GRACE PERIOD: Thử lại 10 lần (~2 giây) nếu mất kết nối tạm thời
    let data = null;
    for (let i = 0; i < 10; i++) {
        data = getGameData();
        if (data && data.player) break;
        await sleep(200);
    }

    const rawName = targetNPC || document.getElementById('npc-select').value || "";
    const npcName = rawName.toLowerCase().trim();
    
    const custom = memory.npcs[npcName];
    const isValidCustom = custom && custom.x !== undefined && custom.y !== undefined;
    const liveNPC = findNPCInState(npcName);
    const target = liveNPC || (isValidCustom ? custom : null) || npcData;

    if (!target || target.x === undefined || target.y === undefined) {
        console.error(`❌ [LỖI]: Không tìm thấy tọa độ hợp lệ cho ${npcName}.`, target);
        // Cú chót: Tìm lại trong Master Data toàn cục
        for (const isl in MASTER_NPC_DATA) {
            if (MASTER_NPC_DATA[isl][npcName]) {
                const fallback = MASTER_NPC_DATA[isl][npcName];
                console.log(`📡 [TỌA ĐỘ]: Đã tìm thấy ${npcName.toUpperCase()} trong Master Data: (${Math.round(fallback.x)}, ${Math.round(fallback.y)})`);
                await moveTowardsTarget(fallback.x, fallback.y);
                return true;
            }
        }
        return false;
    }

    // IN TỌA ĐỘ ĐỂ USER CHECK
    console.log(`📡 [TỌA ĐỘ BETA]: Mục tiêu ${npcName.toUpperCase()} tại (${Math.round(target.x)}, ${Math.round(target.y)})`);

    // A. CHẾ ĐỘ ENGINE LINK (BỎ QUA RESET TƯỜNG)
    if (data && data.player) {
        console.log(`🚀 [DIRECT LINK]: Đang di chuyển tới ${npcName.toUpperCase()}...`);
        await moveTowardsTarget(target.x, target.y);
        console.log("🎯 [HỆ THỐNG]: Đã tới đích bằng Engine GPS!");
        return true;
    }

    // B. CHẾ ĐỘ FALLBACK (Chỉ dùng khi mất kết nối thật sự > 2 giây)
    console.warn("⚠️ [HỆ THỐNG]: Mất kết nối Engine. Bot đang TẠM DỪNG để chờ đồng bộ lại thay vì lùi về...");
    // Thay vì gọi resetToCorner(), chúng ta trả về false để loop chính quay lại bước WAIT_SYNC
    return false;
}

// Cảm biến di chuyển thông minh (Engine Assisted - Cảm biến Vật cản)
async function moveTowardsTarget(tx, ty) {
    let stuckCount = 0;
    let lastX = 0, lastY = 0;
    let fallbackTimer = 0;

    while (isRunning) {
        const data = getGameData();
        if (!data || !data.player) break;

        const { x: curX, y: curY } = data.player;
        const dx = tx - curX;
        const dy = ty - curY;

        // 🎯 ĐÍCH ĐẾN: 10px là vùng an toàn để tương tác
        if (Math.abs(dx) < 10 && Math.abs(dy) < 10) break;

        // 🧠 KIỂM TRA KẸT (STUCK) - Phân tích vật cản (NPC/Vật phẩm)
        if (Math.abs(curX - lastX) < 0.5 && Math.abs(curY - lastY) < 0.5) {
            stuckCount++;
        } else {
            stuckCount = 0;
            fallbackTimer = 0; // Reset timer né vật cản
        }

        lastX = curX; lastY = curY;

        let primaryDir = '';
        let secondaryDir = '';

        // Xác định hướng Ưu tiên (Trục có Delta lớn nhất)
        if (Math.abs(dx) > Math.abs(dy)) {
            primaryDir = dx > 0 ? 'right' : 'left';
            secondaryDir = dy > 0 ? 'down' : 'up';
        } else {
            primaryDir = dy > 0 ? 'down' : 'up';
            secondaryDir = dx > 0 ? 'right' : 'left';
        }

        // 🛡️ CHIẾN THUẬT NÉ VẬT CẢN (NPC/TƯỜNG)
        // Nếu bị kẹt trên trục chính, thử chuyển sang trục phụ 1 lúc để "lách" qua
        if (stuckCount > 3) {
            console.warn(`🧱 [VẬT CẢN]: Đang lách qua NPC/Vật cản bằng hướng ${secondaryDir.toUpperCase()}...`);
            await moveCharacter(secondaryDir, 350); 
            stuckCount = 0; // Reset để thử lại trục chính
            continue;
        }

        await moveCharacter(primaryDir, 150);
        await sleep(20);
    }
}

// Master NPC Data (Pixel Coordinates from Bottom-Right Corner)
// Conversion: 1s walk = 100 points
const MASTER_NPC_DATA = {
    "plaza": {
        "pete": {"x": -1000, "y": -500, "island": "plaza"},
        "peggy": {"x": -1200, "y": -400, "island": "plaza"},
        "bert": {"x": -400, "y": -800, "island": "plaza"},
        "betty": {"x": -600, "y": -820, "island": "plaza"},
        "hank": {"x": -700, "y": -900, "island": "plaza"},
        "guria": {"x": -1000, "y": -1000, "island": "plaza"},
        "raven": {"x": 200, "y": -1000, "island": "plaza"}
    },
    "beach": {
        "corale": {"x": -350, "y": 120, "island": "beach"},
        "old salty": {"x": -400, "y": 0, "island": "beach"},
        "stella": {"x": 500, "y": 0, "island": "beach"},
        "finn": {"x": 250, "y": -80, "island": "beach"},
        "pharaoh": {"x": -500, "y": -300, "island": "beach"}
    },
    "kingdom": {
        "eldric": {"x": -250, "y": -150, "island": "kingdom"},
        "reginald": {"x": 250, "y": -150, "island": "kingdom"},
        "gambit": {"x": 250, "y": 150, "island": "kingdom"},
        "victoria": {"x": 0, "y": -300, "island": "kingdom"},
        "tywin": {"x": -150, "y": 100, "island": "kingdom"}
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

    // Kiểm tra bảng Codex đã mở chưa (Sử dụng search trực tiếp để vượt qua bộ lọc UI)
    const allHeaders = Array.from(document.querySelectorAll('h1, h2, span, p'));
    const codexTitle = allHeaders.find(el => {
        const text = el.textContent.toLowerCase();
        return text.includes('sunflower land codex') || text.includes('deliveries');
    });
    
    if (!codexTitle) {
        // --- 📊 LOGIC NHẬN DIỆN HÌNH ẢNH "VÀNG" (PLAN D) ---
        console.log("🔍 Đang quét biểu tượng Giao hàng theo Kích thước (31.5px)...");
        
        const allImages = Array.from(document.querySelectorAll('img'));
        let targetImg = allImages.find(img => {
            const rect = img.getBoundingClientRect();
            // ĐẶC ĐIỂM QUYẾT ĐỊNH: Rộng đúng 31.5px, nằm ở Left > 50px (tránh Lịch)
            // Lịch (Calendar) chỉ rộng 26.25px
            const isCorrectWidth = Math.abs(rect.width - 31.5) < 1;
            const isSidebarZone = rect.left > 50 && rect.left < 150;
            
            if (isCorrectWidth && isSidebarZone) {
                console.log(`🎯 PHÁT HIỆN: Kích thước ${rect.width.toFixed(2)}px tại Left ${rect.left.toFixed(1)}px`);
                return true;
            }
            return false;
        });

        if (targetImg) {
            console.log("📗 Đã tìm thấy Quyển sách Giao hàng! Đang click...");
            targetImg.click();
            await sleep(3000);
            return;
        }

        // --- DỰ PHÒNG CUỐI CÙNG --- (Dựa trên thông báo đơn mới)
        const newDeliveryPrompt = findElementByText('span', 'New delivery');
        if (newDeliveryPrompt) {
            console.log("✨ Click thông báo ĐƠN MỚI dự phòng...");
            newDeliveryPrompt.click();
            await sleep(3000);
            return;
        }

        console.warn("❌ KHÔNG tìm thấy icon Giao hàng (31.5px) nào trong vùng Sidebar.");
        return;
    }

    console.log("✅ Codex đã mở. Đang quét biểu tượng TRÁI TIM (Đơn sẵn sàng)...");
    const readyItems = [];
    const gridItems = document.querySelectorAll('.grid > div');
    
    for (const item of gridItems) {
        // NHẬN DIỆN TIM ĐỎ: Theo đúng cấu HTML bạn cung cấp
        // Chỉ những thẻ <img> có đúng bộ class này mới là Trái tim Friendship
        const heartIcon = item.querySelector('img.absolute.top-0\\.5.right-0\\.5.w-3') || 
                          item.querySelector('img.absolute.top-0\\.5.right-0\\.5.sm\\:w-4');
        
        if (heartIcon) {
            console.log("❤️ PHÁT HIỆN: Trái tim đỏ Giao hàng!");
            // Click vào chính thẻ cha chứa trái tim (thường là thẻ div có cursor-pointer)
            heartIcon.parentElement.click();
            
            // Đợi 2s để bảng thông tin bên phải cập nhật hoàn toàn
            await sleep(2000);
            
            // QUÉT TÊN NPC TỪ PHẦN CHI TIẾT CỦA BẢNG (Bên phải)
            const detailPanel = document.querySelector('.flex.flex-col.items-center.p-2') || 
                               document.querySelector('.flex-1.flex.flex-col') ||
                               document.querySelector('[role="dialog"]');
            
            const panelText = detailPanel ? detailPanel.textContent || "" : "";
            
            let npcName = "";
            console.log("📄 Đang quét tên NPC trong bảng chi tiết...");
            for (const name of KNOWN_NPCS) {
                // Kiểm tra chính xác tên (Exact-ish match)
                if (panelText.toLowerCase().includes(name)) {
                    npcName = name;
                    break;
                }
            }

            if (npcName) {
                readyItems.push(npcName);
                console.log(`✅ Đã nhận diện đúng NPC: ${npcName.toUpperCase()}`);
                
                // [NÂNG CẤP]: Cập nhật tọa độ LIVE ngay khi vừa chốt đơn
                const livePos = findNPCInState(npcName);
                if (livePos) {
                    console.log(`📍 [AUTO-CALIB]: Đã cập nhật tọa độ mới cho ${npcName.toUpperCase()}: (${Math.round(livePos.x)}, ${Math.round(livePos.y)})`);
                    memory.npcs[npcName] = { ...livePos, island: targetIsland || "plaza" };
                    saveMemory();
                }
                
                // [NÂNG CẤP]: Chỉ chọn 1 đơn hàng đầu tiên rồi đi làm ngay để đảm bảo ổn định 
                break; 
            } else {
                console.warn("⚠️ KHÔNG nhận diện được NPC trong bảng này. Bỏ qua...");
            }
        }
    }

    if (readyItems.length > 0) {
        targetNPC = readyItems[0].toLowerCase().trim();
        console.log(`🎯 Mục tiêu: ${targetNPC.toUpperCase()}. Đang đóng Codex để đồng bộ...`);
        
        // 🏁 ĐÓNG CODEX NGAY LẬP TỨC ĐỂ HIỆN HUD VÀ ĐỒNG BỘ FIBER
        const closeBtn = document.querySelector('img[src*="close"]') || document.querySelector('button[class*="close"]');
        if (closeBtn) closeBtn.click();
        else window.dispatchEvent(new MouseEvent('mousedown', { clientX: 10, clientY: 10, bubbles: true }));
        
        await sleep(1500); 
        currentTask = "TRAVEL";
    } else {
        console.log("🧊 Không có đơn hàng nào sẵn sàng. ĐANG ĐÓNG Codex để chờ...");
        // Tìm nút X để đóng bảng
        const closeBtn = document.querySelector('img[src*="close"]') || document.querySelector('button[class*="close"]');
        if (closeBtn) closeBtn.click();
        await sleep(1000);
        currentTask = "IDLE";
    }
    
    memory.ready_deliveries = readyItems;
    saveMemory();
}

async function travelToIsland(islandName) {
    console.log(`--- ✈️ DI CHUYỂN ĐẾN: ${islandName.toUpperCase()} ---`);
    // Đảm bảo đóng Codex trước khi đi để không bị vướng mắt nhìn (UI)
    const closeBtn = document.querySelector('img[src*="close"], .p-2.cursor-pointer');
    if (closeBtn) closeBtn.click();
    await sleep(500);

    // 1. Tìm nút "Travel to [Island]" trong bảng Codex đang mở
    const travelBtn = findElementByText('.material-button, button', `Travel to ${islandName}`);
    
    if (travelBtn) {
        console.log(`🚢 ĐANG SỬ DỤNG NÚT DI CHUYỂN TRONG GAME: ${islandName.toUpperCase()}...`);
        travelBtn.click();
        
        // Đợi màn hình loading (Nếu có) hoặc chờ nhân vật dịch chuyển
        await sleep(5000);
        currentTask = "MOVE";
        return;
    }

    console.warn(`❌ Không tìm thấy nút 'Travel to ${islandName}' trong bảng Codex.`);
    // Nếu không thấy nút, có thể do đã ở đúng đảo rồi, kiểm tra text tiêu đề vùng (nếu có)
    currentTask = "MOVE";
}

async function interactWithNPC() {
    console.log(`--- ⌨️ KÍCH HOẠT TƯƠNG TÁC PHÍM (SPACE): ${targetNPC.toUpperCase()} ---`);
    
    // 1. ĐẢM BẢO ĐÓNG CODEX TRƯỚC KHI TƯƠNG TÁC (Tránh nhận nhầm bảng UI)
    const closeBtn = document.querySelector('img[src*="close"], .p-2.cursor-pointer');
    if (closeBtn) {
        console.log("🧹 Đang đóng bảng UI để chuẩn bị gọi NPC...");
        closeBtn.click();
        await sleep(800);
    }

    for (let attempt = 0; attempt < 8; attempt++) {
        if (!isRunning) return;

        // Thử nhấn phím SPACE để mở hội thoại (Lệnh chuẩn SFL)
        console.log(`🌀 Đang gọi NPC (Attempt ${attempt + 1})...`);
        const spaceParams = { key: ' ', code: 'Space', keyCode: 32, which: 32, bubbles: true };
        window.dispatchEvent(new KeyboardEvent('keydown', spaceParams));
        document.dispatchEvent(new KeyboardEvent('keydown', spaceParams));
        await sleep(100);
        window.dispatchEvent(new KeyboardEvent('keyup', spaceParams));
        
        await sleep(1500);

        // KIỂM TRA: Bảng hội thoại của NPC đã mở chưa?
        const deliverBtn = findElementByText('.material-button, button', 'Deliver');
        const dialogOpen = document.querySelectorAll('[role="dialog"]');
        
        // CHỈ CHẤP NHẬN NẾU: Không phải bảng Codex (Loại trừ tiêu đề Codex)
        const isRealNPCConversation = Array.from(dialogOpen).some(d => {
            const text = d.textContent.toLowerCase();
            return !text.includes('codex') && !text.includes('deliveries');
        });

        if (deliverBtn || isRealNPCConversation) {
            console.log("✅ Đã mở hội thoại thật thành công!");
            if (deliverBtn) {
                deliverBtn.click();
                console.log("🎉 XÁC NHẬN GIAO HÀNG!");
                await sleep(3000);
                currentTask = "IDLE";
                return;
            }
            // Nếu hội thoại đã mở nhưng chưa có nút Deliver (chưa xong hội thoại đầu) 
            // thì click bất kỳ để skip text
            const skipBtn = document.querySelector('.mt-1.flex.justify-end button') || document.querySelector('[role="dialog"]');
            if (skipBtn) skipBtn.click();
            await sleep(1000);
            continue;
        }

        // Nếu nhấn Space không ăn, thử di chuyển nhẹ (jiggle) để thay đổi vị trí
        console.log("🚧 Đang nhích nhẹ vị trí để bắt sóng NPC...");
        const jiggleDir = ['up', 'down', 'left', 'right'][attempt % 4];
        await moveCharacter(jiggleDir, 300);
    }

    console.warn("❌ Không thể gọi hội thoại sau nhiều lần thử. Reset.");
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
                const moveData = (MASTER_NPC_DATA[targetIsland] || MASTER_NPC_DATA["plaza"] || {})[targetNPC];
                const success = await executePathToNPC(moveData);
                if (success) currentTask = "DELIVER";
                break;
            case "DELIVER":
                await interactWithNPC();
                break;
        }
    } catch (e) {
        console.error("Main Loop Error:", e);
    }
}

// Start/Stop listener from popup (same as before)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start") {
        isRunning = true;
        console.log("SFL Bot Started");
        loop();
    } else if (request.action === "stop") {
        isRunning = false;
        console.log("SFL Bot Stopped");
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
        if (!latestEngineData) console.log("📥 [BOT]: ✅ Nhận tín hiệu Omni-Pulse lần đầu!");
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
    // --- ƯU TIÊN 0: DOM-DATA BYPASS (MAIN WORLD BRIDGE) ---
    // Đây là kênh truyền tin nhanh và ổn định nhất, không bị trình duyệt chặn
    const posStr = document.body.dataset.sflPos;
    if (posStr) {
        const [x, y] = posStr.split(',').map(parseFloat);
        if (!isNaN(x) && !isNaN(y)) return { player: { x, y } };
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
    } catch (e) {}
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
            <div style="display:flex; gap:5px; margin-top:10px;">
                <input type="number" id="manual_x" value="0" style="flex:1; background:transparent; border:1px solid #333; color:#2ed573; font-size:10px; padding:2px;">
                <input type="number" id="manual_y" value="0" style="flex:1; background:transparent; border:1px solid #333; color:#2ed573; font-size:10px; padding:2px;">
            </div>
        </div>
        <button id="auto_btn" style="width:100%; padding:12px; border:none; border-radius:8px; font-weight:800; background:#333; color:white; cursor:pointer; margin-bottom: 12px;">🚀 CHẠY AUTO (GIAO HÀNG)</button>
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
    if (autoBtn) autoBtn.onclick = () => {
        isAutoEnabled = !isAutoEnabled;
        autoBtn.innerText = isAutoEnabled ? '🛑 DỪNG AUTO' : '🚀 CHẠY AUTO';
        autoBtn.style.background = isAutoEnabled ? '#2ed573' : '#333';
        autoBtn.style.color = isAutoEnabled ? '#111' : '#fff';
    };

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
        console.log("⬇️ JSON BỘ NHỚ:", JSON.stringify(memory, null, 2));
        alert("Đã Export vào Console (F12)!");
    };

    const saveBtn = document.getElementById('save_btn');
    if (saveBtn) saveBtn.onclick = () => {
        saveMemory();
        saveBtn.innerText = "✓ OK!";
        setTimeout(() => { saveBtn.innerText = "SAVE ALL"; }, 2000);
    };
}

// Global UI Heartbeat
setInterval(() => {
    const data = getGameData();
    const indicator = document.getElementById('sync-indicator');
    if (indicator) {
        if (data && data.player) {
            indicator.style.background = "#2ed573";
            indicator.style.boxShadow = "0 0 5px #2ed573";
        } else {
            indicator.style.background = "#555";
            indicator.style.boxShadow = "none";
        }
    }
}, 500);
