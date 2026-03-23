// SFL ENGINE BRIDGE (Runs in MAIN World)
// Optimized for reliable NPC interaction & GPS scanning
(function () {
    console.log("💎 SFL BRIDGE 5.0: GLOBAL-SYNC & STICKY ENGINE");
    
    // Khởi tạo trạng thái toàn cục để dùng chung giữa các lần Inject (Fix Closure Desync)
    if (!window.__SFL_ENGINE__) {
        window.__SFL_ENGINE__ = {
            latestScene: null,
            latestSn: null
        };
    }

    // --- [0. ENGINE DISCOVERY HELPER (MAX-POWER)] ---
    function findEngine() {
        try {
            // 1. Sticky check
            if (window.__SFL_ENGINE__.latestScene) return true;

            // 2. Ưu tiên quét thẳng Canvas (Nơi chắc chắn có Phaser)
            const canvas = document.querySelector('canvas');
            if (canvas) {
                const keys = Object.keys(canvas).filter(k => k.startsWith('__react'));
                for (const k of keys) {
                    let node = canvas[k];
                    while (node) {
                        const sn = node.stateNode;
                        if (sn && sn.game && sn.game.scene) {
                            const scene = sn.game.scene.getScene('plaza') || sn.game.scene.scenes[0];
                            if (scene) {
                                window.__SFL_ENGINE__.latestSn = sn;
                                window.__SFL_ENGINE__.latestScene = scene;
                                console.log("✅ [ENGINE]: Đã tìm thấy máy game bằng cách quét Canvas!");
                                return true;
                            }
                        }
                        node = node.return;
                    }
                }
            }

            // 3. Quét rộng toàn bộ DOM (Không giới hạn 300 phần tử)
            const elements = Array.from(document.querySelectorAll('canvas, div, #root'));
            for (const el of elements) {
                const keys = Object.keys(el).filter(k => k.startsWith('__react'));
                for (const k of keys) {
                    let node = el[k];
                    let visited = 0;
                    while (node && visited < 50) {
                        const sn = node.stateNode;
                        if (sn && sn.game && sn.game.scene) {
                            const scene = sn.game.scene.getScene('plaza') || sn.game.scene.scenes[0];
                            if (scene) {
                                window.__SFL_ENGINE__.latestSn = sn;
                                window.__SFL_ENGINE__.latestScene = scene;
                                console.log(`✅ [ENGINE]: Đồng bộ thành công từ Element: ${el.tagName}#${el.id}`);
                                return true;
                            }
                        }
                        node = node.return;
                        visited++;
                    }
                }
            }
        } catch(e){}
        return false;
    }

    // --- [1. TRI-LEVEL NPC TRIGGER & BLIND-FIRE FALLBACK] ---
    window.SFL_TRIGGER_NPC = function(npcName) {
        try {
            const NPC_COORDS = { "peggy": { x: 211, y: 401 }, "pete": { x: -308, y: 401 }, "betty": { x: 534, y: 98 }, "blacksmith": { x: 137, y: 134 } };
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
            console.log(`📡 [ENGINE-STATUS]: Scene: ${engine.latestScene ? 'OK' : 'NULL'}, Sn: ${engine.latestSn ? 'OK' : 'NULL'}`);

            const canvas = document.querySelector('canvas');
            if (!canvas) return "Canvas not found";
            const rect = canvas.getBoundingClientRect();

            let targetPoints = [];
            let usingEngine = false;

            // CHIẾN LƯỢC X: BÀN TAY VÔ HÌNH (XSTATE INJECTION)
            if (window.__SFL_GAME_SERVICE && window.__SFL_GAME_SERVICE.send) {
                console.log("🌌 [PLAN-X]: Đang sử dụng Bàn Tay Vô Hình để truy cập Nội tại Game...");
                
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
                            } else {
                                console.log("🔍 [XSTATE]: Lệnh được gửi:", strArgs);
                            }
                        } catch(e){}
                        return originalSend.apply(this, args);
                    };
                    window.__SFL_GAME_SERVICE._isHooked = true;
                }

                if (window.__SFL_INTERCEPTED_CMD) {
                    let cmd = window.__SFL_INTERCEPTED_CMD;
                    console.log(`⚡ [PLAN-X]: Bắn lại lệnh vừa copy vào Lõi XState:`, JSON.stringify(cmd));
                    if (window.__SFL_GAME_SERVICE._originalSend) {
                        window.__SFL_GAME_SERVICE._originalSend.apply(window.__SFL_GAME_SERVICE, cmd);
                        return true;
                    }
                } else {
                    console.warn("⏳ [PLAN-X]: Đang chờ nội tại. VUI LÒNG TỰ CLICK VÀO BETTY BẰNG CHUỘT THẬT 1 LẦN để Bot copy mã Lệnh XState!");
                    // Vẫn cho phép nhảy xuống Chiến lược Blind-Fire ở dưới để dự phòng
                }
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
                } else if (NPC_COORDS[npcName.toLowerCase()]) {
                    console.warn(`⚠️ [FALLBACK]: Dùng tọa độ mốc cho ${npcName}`);
                    world = NPC_COORDS[npcName.toLowerCase()];
                }

                if (world) {
                    const center = cam.getScreenPoint(world.x, world.y);
                    targetPoints = [
                        { x: rect.left + center.x, y: rect.top + center.y },
                        { x: rect.left + center.x, y: rect.top + center.y - 15 },
                        { x: rect.left + center.x, y: rect.top + center.y + 15 }
                    ];
                    
                    // Engine Injection (Tri-Level)
                    if (npc) {
                        try {
                            latestScene.events.emit('GAMEOBJECT_POINTER_DOWN', latestScene.input.activePointer, npc);
                            npc.emit('pointerdown'); npc.emit('pointertap');
                        } catch(e){}
                    }
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
                
                // Carpet Bombing (Rải thảm hình chữ thập) bù trừ sai số Zoom
                targetPoints = [
                    { x: hitX, y: hitY },
                    { x: hitX, y: hitY - 25 }, // Lên
                    { x: hitX, y: hitY + 25 }, // Xuống
                    { x: hitX - 25, y: hitY }, // Trái
                    { x: hitX + 25, y: hitY }  // Phải
                ];
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
                    const opts = { bubbles: true, clientX: p.x, clientY: p.y, pointerId: 1, pointerType: 'mouse' };
                    canvas.dispatchEvent(new PointerEvent('pointerdown', opts));
                    setTimeout(() => {
                        canvas.dispatchEvent(new PointerEvent('pointerup', opts));
                        canvas.dispatchEvent(new PointerEvent('click', opts));
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

                    // XState Service Extraction (Brute Force)
                    const checkXState = (obj) => {
                        if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return;
                        if (typeof obj.send === 'function' && obj.state && (obj.id || obj.machine)) {
                            // Ưu tiên chọn XState bự nhất (nhiều state key nhất)
                            const currentBest = window.__SFL_GAME_SERVICE;
                            if (!currentBest || obj.id === 'gameMachine' || obj.id === 'plazaMachine') {
                                window.__SFL_GAME_SERVICE = obj;
                            }
                        }
                    };

                    if (p) {
                        checkXState(p); checkXState(p.value);
                        if (p.value && typeof p.value === 'object') Object.values(p.value).forEach(checkXState);
                    }
                    if (s) {
                        checkXState(s.memoizedState);
                        if (s && typeof s === 'object') Object.values(s).forEach(checkXState);
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
