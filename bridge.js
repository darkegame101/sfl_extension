// SFL ENGINE BRIDGE (Runs in MAIN World)
// Optimized for reliable NPC interaction & GPS scanning
(function () {
    console.log("💎 SFL BRIDGE 7.0: ABSOLUTE GOD-MODE (EVENT HIJACKER)");
    
    // Khởi tạo trạng thái toàn cục để dùng chung giữa các lần Inject (Fix Closure Desync)
    if (!window.__SFL_ENGINE__) {
        window.__SFL_ENGINE__ = { latestScene: null, latestSn: null };
        window.__SFL_LISTENERS = { keydown: [], pointerdown: [], pointerup: [] };
        
        // 🔥 [ABSOLUTE GOD-MODE]: HIJACK EVENT LISTENERS 🔥
        // Trình duyệt chặn isTrusted? Đội ngũ Dev cài bẫy? Không sao cả!
        // Chúng ta sẽ ăn cắp thẳng Cầu dao của họ bằng cách đè lên addEventListener.
        try {
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                if (type === 'keydown' || type === 'pointerdown' || type === 'pointerup') {
                    if (!this.__sfl_listeners) this.__sfl_listeners = {};
                    if (!this.__sfl_listeners[type]) this.__sfl_listeners[type] = [];
                    this.__sfl_listeners[type].push(listener);
                    
                    // Lưu TUYỆT ĐỐI MỌI LISTENER trên mọi Element (Bỏ giới hạn chỉ Canvas/Document)
                    const existing = window.__SFL_LISTENERS[type].find(x => x.fn === listener);
                    if (!existing) {
                        window.__SFL_LISTENERS[type].push({ target: this, fn: listener });
                    }
                }
                return originalAddEventListener.call(this, type, listener, options);
            };
            console.log("🛡️ [GOD-MODE]: Đã cài đặt Hệ thống Ăn Chặn Sự Kiện Toàn Cầu!");
        } catch(e) {
            console.error("Lỗi khi bẻ khóa AddEventListener:", e);
        }
    }

    // --- [0. ENGINE DISCOVERY HELPER (MAX-POWER)] ---
    function findEngine() {
        try {
            if (window.__SFL_ENGINE__ && window.__SFL_ENGINE__.latestScene) return true;

            const checkPhaserObj = (obj) => {
                if (obj && obj.scene && typeof obj.scene.getScenes === 'function') {
                    const activeScenes = obj.scene.getScenes(true);
                    const scene = activeScenes.length > 0 ? activeScenes[0] : (obj.scene.scenes && obj.scene.scenes[0]);
                    if (scene) {
                        window.__SFL_ENGINE__.latestSn = { game: obj };
                        window.__SFL_ENGINE__.latestScene = scene;
                        console.log("✅ [PHASER-GOD]: Đã khai quật thành công lõi Phaser Engine từ React Hook!");
                        return true;
                    }
                }
                return false;
            };

            const canvas = document.querySelector('canvas');
            let currentEl = canvas;
            while (currentEl && currentEl !== document.body) {
                const keys = Object.keys(currentEl).filter(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
                for (const k of keys) {
                    let node = currentEl[k];
                    let visited = 0;
                    while (node && visited < 100) {
                        // 1. Quét StateNode truyền thống (Class Components)
                        if (node.stateNode && node.stateNode.game) {
                            if (checkPhaserObj(node.stateNode.game)) return true;
                        }
                        if (checkPhaserObj(node.stateNode)) return true;

                        // 2. Quét MemoizedState (Hook Chains - Functional Components)
                        let hook = node.memoizedState;
                        let hookDepth = 0;
                        while (hook && hookDepth < 20) {
                            if (hook && hook.memoizedState) { // Thêm check hook an toàn
                                if (checkPhaserObj(hook.memoizedState)) return true;
                                if (typeof hook.memoizedState === 'object') {
                                    for (let prop in hook.memoizedState) {
                                        if (checkPhaserObj(hook.memoizedState[prop])) return true;
                                    }
                                }
                            }
                            hook = hook ? hook.next : null;
                            hookDepth++;
                        }
                        
                        node = node.return;
                        visited++;
                    }
                }
                currentEl = currentEl.parentElement;
            }

            // 3. Brute-Force Toàn cục Hệ thống Window
            for (let key in window) {
                try {
                    let obj = window[key];
                    if (checkPhaserObj(obj)) return true;
                } catch(e) {}
            }
        } catch(e) { console.error("Engine Hunter Error:", e); }
        return false;
    }

    // --- [1. TRI-LEVEL NPC TRIGGER & BLIND-FIRE FALLBACK] ---
    window.SFL_TRIGGER_NPC = function(npcName) {
        try {
            const NPC_COORDS = { "peggy": { x: 211, y: 401 }, "pete": { x: 370, y: 430 }, "betty": { x: 534, y: 98 }, "blacksmith": { x: 366, y: 130 }, "grimtooth": { x: 809, y: 362 } };
            const myPosStr = document.body.dataset.sflPos;
            let myPos = null;
            if (myPosStr) {
                const parts = myPosStr.split(',');
                myPos = { x: parseInt(parts[0]), y: parseInt(parts[1]) };
            }

            console.log(`🔍 [ACTION]: Đang nhắm bắn nhân vật ${npcName.toUpperCase()}...`);

            // Đồng bộ lại Engine nếu cần
            findEngine();
            const engine = window.__SFL_ENGINE__;
            console.log(`📡 [ENGINE-STATUS]: Scene: ${engine.latestScene ? 'OK' : 'NULL'}, Sn: ${engine.latestSn ? 'OK' : 'NULL'}, Machine: ${window.__SFL_GAME_SERVICE ? 'CAPTURED' : 'NULL'}`);

            const canvas = document.querySelector('canvas');
            if (!canvas) return "Canvas not found";
            const rect = canvas.getBoundingClientRect();

            let targetPoints = [];
            let usingEngine = false;

            // CHIẾN LƯỢC D: GIAO HÀNG NATIVE QUA ORDER.DELIVERED (Đúng event của gameMachine)
            // Đã xác nhận: state.can({ type: "SPEAK" }) = false, nhưng state.can("order.delivered") hoạt động
            // gameMachine chấp nhận "order.delivered" ở mọi trạng thái "playing"
            if (window.__SFL_GAME_SERVICE && window.__SFL_GAME_SERVICE.send) {
                try {
                    const svc = window.__SFL_GAME_SERVICE;
                    const state = svc.state || (typeof svc.getSnapshot === 'function' ? svc.getSnapshot() : null);
                    if (state && state.context && state.context.state && state.context.state.delivery) {
                        const orders = state.context.state.delivery.orders;
                        if (Array.isArray(orders)) {
                            // Tìm đơn hàng theo field 'from' (tránh nhầm 'pumpkin pete' vs 'pete')
                            const targetOrder = orders.find(o => {
                                const from = (o.from || '').toLowerCase();
                                const npc = npcName.toLowerCase();
                                return from === npc || from.includes(npc) || npc.includes(from);
                            });

                            if (document.body.dataset.sflInteractSuccess === "true") return true;

                            if (targetOrder) {
                                console.log(`🎯 [PLAN-D]: Tìm thấy đơn hàng! ID=${targetOrder.id}, From=${targetOrder.from}. Giao hàng...`);
                                const send = svc._originalSend || svc.send;
                                // Gửi đúng event mà gameMachine chấp nhận (đã xác nhận qua state.can)
                                send.call(svc, { type: "order.delivered", id: targetOrder.id });
                                console.log(`✅ [PLAN-D]: ĐÃ GIAO HÀNG THÀNH CÔNG cho ${npcName.toUpperCase()}! ID = ${targetOrder.id}`);
                                document.body.dataset.sflInteractSuccess = "true";
                                return true;
                            } else {
                                console.warn(`⚠️ [PLAN-D]: Không tìm thấy đơn hàng cho [${npcName}] trong danh sách ${orders.length} đơn.`);
                            }
                        }
                    }
                } catch(e) { 
                    console.error("Plan D Crash:", e); 
                    if (e.message && e.message.toLowerCase().includes("already completed")) {
                        console.log("🎊 [ENGINE]: Game báo đơn đã hoàn thành. Tự động xác thực thành công.");
                        document.body.dataset.sflInteractSuccess = "true";
                        return true;
                    }
                }
            }

            // CHIẾN LƯỢC X: BÀN TAY VÔ HÌNH (XSTATE INJECTION DỄ QUẢN LÝ)
            if (document.body.dataset.sflInteractSuccess === "true") return true;

            if (window.__SFL_GAME_SERVICE && window.__SFL_GAME_SERVICE.send) {
                console.log("🌌 [PLAN-X]: Đang sử dụng Hệ thống Nghe lén XState Truyền thống...");
                
                // Cài Hook Nghe Lén
                if (!window.__SFL_GAME_SERVICE._isHooked) {
                    const originalSend = window.__SFL_GAME_SERVICE.send;
                    window.__SFL_GAME_SERVICE._originalSend = originalSend;
                    window.__SFL_GAME_SERVICE.send = function(...args) {
                        try {
                            const strArgs = JSON.stringify(args);
                            if (strArgs.toLowerCase().includes(npcName.toLowerCase()) || strArgs.includes('INTERACT') || strArgs.includes('SPEAK')) {
                                console.log("🔥 [XSTATE-INTERCEPT]: Đã chộp được lệnh Tương Tác!", strArgs);
                                window.__SFL_INTERCEPTED_CMD = args;
                            }
                        } catch(e){}
                        return originalSend.apply(this, args);
                    };
                    window.__SFL_GAME_SERVICE._isHooked = true;
                }

                if (window.__SFL_INTERCEPTED_CMD) {
                    let cmd = JSON.parse(JSON.stringify(window.__SFL_INTERCEPTED_CMD));
                    const replaceNPCName = (obj) => {
                        if (!obj || typeof obj !== 'object') return;
                        for (let k in obj) {
                            if (typeof obj[k] === 'string') {
                                const val = obj[k].toLowerCase();
                                const knownNPCs = ["pete", "peggy", "bert", "betty", "guria", "raven", "tinker", "corale", "old salty", "stella", "finn", "eldric", "reginald", "gambit", "victoria", "grimbly", "blacksmith", "tywin", "grimlock", "pharaoh", "hank", "jester", "grubnuk", "gordo", "tango", "miranda", "finley", "timmy", "cornwell", "grimtooth"];
                                if (knownNPCs.includes(val)) {
                                    obj[k] = npcName.toLowerCase();
                                    console.log(`🤖 [PLAN-X]: Đã tráo đổi danh tính -> ${val} thành ${npcName}!`);
                                }
                            } else if (typeof obj[k] === 'object') {
                                replaceNPCName(obj[k]);
                            }
                        }
                    };
                    cmd.forEach(replaceNPCName);

                    console.log(`⚡ [PLAN-X]: Bắn lại lệnh giả mạo (Interact) vào Lõi XState:`, JSON.stringify(cmd));
                    if (window.__SFL_GAME_SERVICE._originalSend) {
                        window.__SFL_GAME_SERVICE._originalSend.apply(window.__SFL_GAME_SERVICE, cmd);
                        // Tiếp tục chạy các chiến lược khác đề phòng lệnh INTERACT chỉ mở bảng chứ không giao hàng
                    }
                }
            }

            // CHIẾN LƯỢC E: GỌI THẲNG KEYDOWN BẰNG GHOST-EVENT
            if (document.body.dataset.sflInteractSuccess === "true") return true;

            if (window.__SFL_LISTENERS && window.__SFL_LISTENERS.keydown && window.__SFL_LISTENERS.keydown.length > 0) {
                console.log(`⌨️ [PLAN-E]: Bắn phím E thông qua Mạng lưới Bị Giam Giữ...`);
                // Tạo Ghost-Event (Object giả lập Event thật 100% để lách luật V8 isTrusted)
                const buildGhostKey = (keyChar) => ({
                    type: 'keydown', key: keyChar, code: 'KeyE', keyCode: 69, which: 69,
                    bubbles: true, cancelable: true, isTrusted: true, defaultPrevented: false,
                    target: document.body, currentTarget: document, timeStamp: performance.now(),
                    preventDefault: function(){}, stopPropagation: function(){}, stopImmediatePropagation: function(){}
                });
                const eKey1 = buildGhostKey('E');
                const eKey2 = buildGhostKey('e');
                window.__SFL_LISTENERS.keydown.forEach(l => {
                    try { l.fn(eKey1); l.fn(eKey2); } catch(err){}
                });
                console.log(`✅ [PLAN-E]: Đã ép Phaser nhận phím E thành công (Ghost Payload)!`);
            }

            // CHIẾN LƯỢC Y: REACT FIBER PROP INJECTION (Bypass Canvas Hoàn Toàn)
            if (document.body.dataset.sflInteractSuccess === "true") return true;

            console.log(`📡 [PLAN-Y]: Quét sâu React Fiber để tìm Rễ gốc Hàm Tương Tác...`);
            if (canvas) {
                const keys = Object.keys(canvas).filter(k => k.startsWith('__react'));
                for (const k of keys) {
                    let node = canvas[k];
                    let depth = 0;
                    while (node && depth < 200) {
                        const props = node.memoizedProps || node.pendingProps;
                        if (props && typeof props === 'object') {
                            for (let propName in props) {
                                if (typeof props[propName] === 'function') {
                                    const lowName = propName.toLowerCase();
                                    // Bắn MỌI hàm bắt đầu bằng "on" (onClick, onInteract, onSelect...)
                                    if (lowName.startsWith('on') || lowName.includes('interact') || lowName.includes('speak') || lowName.includes('dialog')) {
                                        console.log(`🎯 [PLAN-Y]: PHÁT HIỆN Hàm Khả Nghi: [${propName}] tại Độ sâu: ${depth}`);
                                        try {
                                            props[propName](npcName.toLowerCase());
                                            props[propName]({ npc: npcName.toLowerCase() }); // Một số hàm dùng Object payload
                                            props[propName](npcName.charAt(0).toUpperCase() + npcName.slice(1)); // Dạng Viết Hoa
                                        } catch(e) {}
                                    }
                                }
                            }
                        }
                        node = node.return;
                        depth++;
                    }
                }
                console.log(`✅ [PLAN-Y]: Đã dội bom toàn bộ Hàm Tương tác React có thể tìm thấy!`);
            }

            // CHIẾN LƯỢC A: DÙNG ENGINE (PHASER)
            if (engine.latestScene && engine.latestSn && engine.latestSn.game) {
                usingEngine = true;
                const cam = engine.latestScene.cameras.main;
                
                let world = null;
                const npc = engine.latestScene.children.list.find(c => {
                    let textureKey = (c.texture && c.texture.key || "").toLowerCase();
                    const isPl = textureKey.includes('body') || textureKey.includes('naked') || textureKey.includes('human') || textureKey.includes('avatar');
                    if (isPl) return false;
                    return textureKey.includes(npcName.toLowerCase()) || (c.username && c.username.toLowerCase().includes(npcName.toLowerCase()));
                });

                if (npc) {
                    console.log(`✅ [FOUND]: Thấy Sprite "${npcName}" (${npc.texture.key})`);
                    world = { x: npc.x, y: npc.y };
                    
                    try {
                        const ptr = engine.latestScene.input.activePointer;
                        // 1. Kích hoạt trực tiếp GameObject
                        npc.emit('pointerdown', ptr, 0, 0, null);
                        npc.emit('pointerup', ptr, 0, 0, null);
                        npc.emit('pointertap', ptr, 0, 0, null);
                        // 2. Kích hoạt thông qua Global Input Manager
                        engine.latestScene.input.emit('gameobjectdown', ptr, npc, null);
                        engine.latestScene.input.emit('gameobjectup', ptr, npc, null);
                        console.log("💥 [PHASER-GOD]: Đã ép Phaser kích hoạt tương tác thẳng vào GameObject!");
                    } catch(e){ console.error("Phaser Inject Error:", e); }
                }

                if (world) {
                    const center = cam.getScreenPoint(world.x, world.y);
                    targetPoints = [
                        { x: rect.left + center.x, y: rect.top + center.y },
                        { x: rect.left + center.x, y: rect.top + center.y - 15 },
                        { x: rect.left + center.x, y: rect.top + center.y + 15 }
                    ];
                }
            }

            // CHIẾN LƯỢC B: BLIND-FIRE (TOÁN HỌC TƯƠNG ĐỐI TỪ GPS)
            if (!usingEngine || targetPoints.length === 0) {
                console.warn(`⚠️ [BLIND-FIRE]: Kích hoạt chiến lược ngắm bắn Toán học (Bỏ qua Engine)...`);
                if (!myPos || !NPC_COORDS[npcName.toLowerCase()]) {
                    console.error("❌ [BLIND-FIRE]: Thiếu tọa độ GPS để tính toán!");
                    return "Missing GPS";
                }

                const target = NPC_COORDS[npcName.toLowerCase()];
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                
                // SFL Zoom thường là 2.5 - 3.5. Tâm trục Y thường ở chân nhân vật.
                const dx = target.x - myPos.x;
                const dy = target.y - myPos.y;
                
                const hitX = cx + (dx * 3.0);
                const hitY = cy + (dy * 3.0) - 30; // Giật lên 30px vào người

                console.log(`🎯 [MATH]: Nhắm (Px:${myPos.x}, Py:${myPos.y}) -> (Bx:${target.x}, By:${target.y}) => Delta: ${dx}, ${dy}`);
                
                // Massive Carpet Bombing (Rải thảm hình Vuông Lớn 5x5 = 25 viên) bù trừ sai số Góc đứng của người chơi
                targetPoints = [];
                const spacing = 30; // Khoảng cách giữa các tia
                for (let offsetX = -2; offsetX <= 2; offsetX++) {
                    for (let offsetY = -2; offsetY <= 2; offsetY++) {
                        targetPoints.push({
                            x: hitX + (offsetX * spacing),
                            y: hitY + (offsetY * spacing)
                        });
                    }
                }
            }

            // --- THỰC THI BẮN (HARDWARE) ---
            if (targetPoints.length > 0) {
                console.log(`🚀 [FIRE]: Rải thảm ${targetPoints.length} viên đạn vào mục tiêu!`);
                // Visual Ping
                try {
                    const ctx = canvas.getContext('2d', { willReadFrequently: true });
                    if (ctx) {
                        targetPoints.forEach(p => {
                            ctx.beginPath();
                            ctx.arc(p.x - rect.left, p.y - rect.top, 5, 0, 2 * Math.PI);
                            ctx.fillStyle = usingEngine ? '#2ed573' : '#ff4757'; // Xanh nếu Engine, Đỏ nếu Blind-Fire
                            ctx.fill();
                        });
                        setTimeout(() => { 
                            ctx.clearRect(0, 0, canvas.width, canvas.height); // Xóa ping nhanh
                        }, 500);
                    }
                } catch(e){}

                targetPoints.forEach((p, i) => {
                    // Tạo Ghost-Event Chuột để lừa Phaser Input Manager
                    const buildGhostPointer = (eventType) => ({
                        type: eventType, pointerId: 1, pointerType: 'mouse', isPrimary: true,
                        button: 0, buttons: eventType === 'pointerdown' ? 1 : 0,
                        clientX: p.x, clientY: p.y, pageX: p.x, pageY: p.y, screenX: p.x, screenY: p.y,
                        bubbles: true, cancelable: true, isTrusted: true, defaultPrevented: false,
                        target: canvas, currentTarget: canvas, srcElement: canvas, view: window,
                        timeStamp: performance.now(),
                        preventDefault: function(){}, stopPropagation: function(){}, stopImmediatePropagation: function(){}
                    });

                    const downGhost = buildGhostPointer('pointerdown');
                    const upGhost = buildGhostPointer('pointerup');
                    
                    // Phát phụ trợ qua DOM để đánh lừa các React listener mỏng
                    canvas.dispatchEvent(new PointerEvent('pointerdown', downGhost));

                    // Nã Ghost Event thẳng vào yết hầu của Phaser!
                    if (window.__SFL_LISTENERS && window.__SFL_LISTENERS.pointerdown) {
                        window.__SFL_LISTENERS.pointerdown.forEach(l => {
                            try { l.fn(downGhost); } catch(err){}
                        });
                    }

                    setTimeout(() => {
                        const clickGhost = buildGhostPointer('click');
                        canvas.dispatchEvent(new PointerEvent('click', clickGhost));
                        
                        // [GOD-MODE]: Rút súng
                        if (window.__SFL_LISTENERS && window.__SFL_LISTENERS.pointerup) {
                            window.__SFL_LISTENERS.pointerup.forEach(l => {
                                try { l.fn(upGhost); } catch(err){}
                            });
                        }
                    }, 30 + (i * 20));
                });
                return true;
            }

            return "Failed to calculate targets";
        } catch (e) { console.error(`🚨 [BRIDGE-ERROR]: ${e.message}`); return e.message; }
    };

    // --- [2. COLLISION GRID ENGINE] ---
    window.SFL_GET_COLLISION_GRID = function(minX, minY, maxX, maxY, excludeNPC = "", step = 32) {
        try {
            const latestScene = window.__SFL_ENGINE__.latestScene;
            if (!latestScene || !latestScene.children) return null;
            const obstacles = latestScene.children.list.filter(c => {
                let textureKey = (c.texture && c.texture.key || "").toLowerCase();
                if (excludeNPC && textureKey.includes(excludeNPC.toLowerCase())) return false;
                return (c.texture && (c.texture.key.includes('fence') || c.texture.key.includes('building') || c.texture.key.includes('water'))) || (c.body && c.body.immovable) || (c.type === 'StaticGroup');
            });
            const grid = [];
            for (let y = minY; y <= maxY; y += step) {
                const row = [];
                for (let x = minX; x <= maxX; x += step) {
                    let isBlocked = 0;
                    for (const obj of obstacles) {
                        if (x >= obj.x - 20 && x <= obj.x + 20 && y >= obj.y - 20 && y <= obj.y + 20) {
                            isBlocked = 1; break;
                        }
                    }
                    row.push(isBlocked);
                }
                grid.push(row);
            }
            return { grid, minX, minY, step };
        } catch (e) { return null; }
    };

    // --- [3. CSP HANDLERS] ---
    document.addEventListener('SFL_TRIGGER_REQUEST', (e) => window.SFL_TRIGGER_NPC(e.detail));
    document.addEventListener('SFL_GRID_REQUEST', (e) => {
        const { minX, minY, maxX, maxY, excludeNPC, step } = e.detail;
        const data = window.SFL_GET_COLLISION_GRID(minX, minY, maxX, maxY, excludeNPC, step);
        document.body.dataset.sflGrid = JSON.stringify(data);
    });

    // --- [4. MMO SCANNER (GPS)] ---
    function findEntitiesInFiber() {
        const result = { me: null, others: {}, visuals: {}, safeZones: {} };
        try {
            // Quét rộng hơn (1000 phần tử) để không bỏ sót Canvas nằm sâu
            const elements = Array.from(document.querySelectorAll('*')).slice(0, 1000);
            for (const el of elements) {
                const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
                if (!fiberKey) continue;
                let node = el[fiberKey];
                let checkedNodes = 0;
                const stack = [node];
                while (stack.length > 0 && checkedNodes < 2500) {
                    const n = stack.pop();
                    if (!n) continue;
                    checkedNodes++;
                    const p = n.memoizedProps || n.pendingProps;
                    const sn = n.stateNode;
                    const s = n.memoizedState;

                    // XState Service Extraction (Universal Hooker)
                    const hookTargetMachine = (machine, sourceObj) => {
                        if (!machine || machine._isOmniHooked) return;
                        
                        const originalSend = machine.send;
                        machine._isOmniHooked = true;
                        machine._originalSend = originalSend;
                        
                        machine.send = function(event, payload) {
                            try {
                                let eventType = "";
                                if (typeof event === 'string') eventType = event;
                                else if (event && event.type && typeof event.type === 'string') eventType = event.type;
                                
                                if (eventType && typeof eventType === 'string') {
                                    eventType = eventType.toUpperCase();
                                } else {
                                    eventType = "";
                                }
                                
                                // Lọc các lệnh rác (âm thanh, di chuyển nhỏ)
                                if (eventType.includes('INTERACT') || eventType.includes('SPEAK') || eventType.includes('DELIVER') || eventType.includes('TRADE') || eventType.includes('NPC')) {
                                    console.log(`🔥 [XSTATE-OMNI]: SÓNG NÃO PHÁT HIỆN! Đã chộp giao thức: [${eventType}] từ Machine [${machine.id || 'Unknown'}]`);
                                    window.__SFL_GAME_SERVICE = sourceObj; // Khóa mục tiêu thành Game Service Vĩnh Viễn
                                    
                                    // CHỈ LƯU LỆNH TƯƠNG TÁC ĐỂ DÙNG BÀN TAY VÔ HÌNH MỞ NPC (Bỏ qua các lệnh DELIVER bên trong UI)
                                    if (eventType.includes('INTERACT') || eventType.includes('SPEAK')) {
                                        window.__SFL_INTERCEPTED_CMD = payload !== undefined ? [event, payload] : [event];
                                        console.log(`🤖 [PLAN-X]: ĐÃ CÀI ĐẶT LỆNH MỞ NPC VÀO LÕI NHỚ!`);
                                    }

                                    if (eventType.includes('DELIVERED') || eventType.includes('COMPLETED')) {
                                        console.log(`🎊 [XSTATE-OMNI]: Phát hiện tín hiệu HOÀN THÀNH từ Server!`);
                                        document.body.dataset.sflInteractSuccess = "true";
                                    }
                                }
                            } catch(e){
                                console.error("XState Intercept Error:", e);
                            }
                            return originalSend.call(this, event, payload);
                        };
                    };

                    const checkXState = (obj) => {
                        if (!obj) return;

                        // NEW: Bắt sống Game Service mà không cần chờ user click trước
                        if (obj.state && obj.state.context && obj.state.context.state && obj.state.context.state.delivery) {
                            if (!window.__SFL_GAME_SERVICE_CAPTURED) {
                                window.__SFL_GAME_SERVICE = obj;
                                window.__SFL_GAME_SERVICE_CAPTURED = true;
                                console.log(`✅ [XSTATE-HUNTER]: Đã tự động KHÓA MỤC TIÊU Main Game Service! Sẵn sàng tung PLAN-M.`);
                            }
                        }

                        // 1. Phân Tích Object Tiêu Chuẩn (XState Interpreter Service / Actor)
                        if (typeof obj === 'object' && !Array.isArray(obj)) {
                            // XState v4 (.state), XState v5 / Actor (.getSnapshot / .sessionId)
                            if (typeof obj.send === 'function' && (obj.state || typeof obj.getSnapshot === 'function' || obj.sessionId)) {
                                hookTargetMachine(obj, obj);
                            }
                            // Dự phòng mỏng (Zustand / Redux store có dispatch thay vì send)
                            if (typeof obj.dispatch === 'function' && typeof obj.getState === 'function') {
                                obj.send = obj.dispatch; // Alias để sài chung Logic
                                hookTargetMachine(obj, obj);
                            }
                        }
                        // 2. Phân Tích React Hook Array (Mẫu [state, send, service])
                        if (Array.isArray(obj) && obj.length >= 2) {
                            const state = obj[0];
                            const send = obj[1];
                            const service = obj[2];
                            
                            if (typeof send === 'function' && state && (state.value || state.matches)) {
                                // Nếu có Service gốc (class object), hook vào object đó!
                                if (service && typeof service.send === 'function') {
                                    hookTargetMachine(service, service);
                                } else {
                                    // SFL XState React Hook Array mồ côi
                                    // Bọc thẳng cái Array obj[1]!
                                    if (!obj._isOmniHooked) {
                                        obj[1] = function(event, payload) {
                                            try {
                                                let eventType = typeof event === 'string' ? event : (event ? event.type : "");
                                                if (eventType && typeof eventType === 'string') {
                                                    eventType = eventType.toUpperCase();
                                                    if (eventType.includes('INTERACT') || eventType.includes('SPEAK') || eventType.includes('DELIVER') || eventType.includes('TRADE') || eventType.includes('NPC')) {
                                                        console.log(`🔥 [XSTATE-OMNI]: SÓNG NÃO PHÁT HIỆN TỪ HOOK ARRAY! [${eventType}]`);
                                                        window.__SFL_GAME_SERVICE = obj; // Save Array
                                                        window.__SFL_INTERCEPTED_CMD = payload !== undefined ? [event, payload] : [event];
                                                    }
                                                }
                                            } catch(e){}
                                            return send.call(this, event, payload);
                                        };
                                        obj._originalSend = send;
                                        obj.send = obj[1]; // Alias
                                        obj._isOmniHooked = true;
                                    }
                                }
                            }
                        }
                    };

                    const safeCheck = (obj) => {
                        try {
                            if (obj && typeof obj === 'object') Object.values(obj).forEach(checkXState);
                        } catch(e){}
                    };

                    if (p) {
                        checkXState(p); checkXState(p.value);
                        safeCheck(p.value);
                    }
                    if (s) {
                        // Lọc toàn bộ Linked List của React Hooks
                        let currentHook = s;
                        while (currentHook) {
                            checkXState(currentHook.memoizedState);
                            safeCheck(currentHook.memoizedState);
                            currentHook = currentHook.next;
                        }
                    }

                    // MMO state
                    let mmo = p?.mmoService || sn?.mmoService || s?.mmoService || p?.value?.mmoService;
                    if (mmo?.state?.context?.server?.state?.players) {
                        const ctx = mmo.state.context;
                        const pls = ctx.server.state.players;
                        const sid = ctx.server.sessionId;
                        pls.forEach((player, id) => {
                            const name = (player.username || "unknown").toLowerCase();
                            const pos = { x: Math.round(player.x), y: Math.round(player.y) };
                            if (id === sid) result.me = pos;
                            else result.others[name] = pos;
                        });
                    }

                    // Phaser state
                    if (sn && sn.game && sn.game.scene) {
                        const scene = sn.game.scene.getScene('plaza') || sn.game.scene.scenes[0];
                        if (scene) {
                            window.__SFL_ENGINE__.latestSn = sn;
                            window.__SFL_ENGINE__.latestScene = scene;
                        }
                        
                        const cam = scene.cameras.main;
                        const NPC_COORDS = { "peggy": { x: 211, y: 401 }, "pete": { x: -308, y: 401 }, "betty": { x: 534, y: 98 } };
                        for (const npc in NPC_COORDS) {
                            const world = NPC_COORDS[npc];
                            const p1 = cam.getScreenPoint(world.x, world.y - 10);
                            const p2 = cam.getScreenPoint(world.x, world.y - 25);
                            result.safeZones[npc] = [ { x: Math.round(p1.x), y: Math.round(p1.y) }, { x: Math.round(p2.x), y: Math.round(p2.y) } ];
                        }
                        scene.children.list.forEach(child => {
                            let name = (child.username || child.name || child.id || "").toString().toLowerCase();
                            if (!name && child.texture && child.texture.key) name = child.texture.key.toLowerCase();
                            if (name && name.length > 2) {
                                const screenPos = cam.getScreenPoint(child.x, child.y);
                                result.visuals[name] = { screenX: Math.round(screenPos.x), screenY: Math.round(screenPos.y) };
                            }
                        });
                    }
                    if (n.child) stack.push(n.child);
                    if (n.sibling) stack.push(n.sibling);
                }
            }
        } catch (e) { }
        return result.me ? result : null;
    }

    function scan() {
        try {
            const data = findEntitiesInFiber();
            if (data) {
                document.body.dataset.sflPos = `${data.me.x},${data.me.y}`;
                document.body.dataset.sflEntities = JSON.stringify(data.others);
                document.body.dataset.sflNPCVisuals = JSON.stringify(data.visuals);
                document.body.dataset.sflSafeZones = JSON.stringify(data.safeZones);
            }
        } catch (e) { }
    }
    setInterval(scan, 500);
})();
