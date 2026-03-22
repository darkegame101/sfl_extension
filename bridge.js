// SFL ENGINE BRIDGE (Runs in MAIN World)
(function() {
    console.log("💎 SFL BRIDGE ACTIVE: GIGA-PULSE DISCOVERY (METHOD 2 PRO+)");
    let lastLogTime = 0;
    let failReason = "Đang tìm kiếm Engine...";

    function findSFLInFiber() {
        try {
            // QUÉT TOÀN BỘ DOM (Lấy 200 thẻ đầu tiên để tối ưu hiệu năng)
            const elements = Array.from(document.querySelectorAll('*')).slice(0, 200);
            
            for (const el of elements) {
                const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
                if (!fiberKey) continue;

                let node = el[fiberKey];
                let checkedNodes = 0;
                const stack = [node];

                while (stack.length > 0 && checkedNodes < 1000) {
                    const n = stack.pop();
                    if (!n) continue;
                    checkedNodes++;

                    const p = n.memoizedProps || n.pendingProps;
                    const s = n.memoizedState;
                    const sn = n.stateNode;

                    // --- CHỐT HẠ: Tìm bất kỳ Object nào có 'sessionId' và 'players' ---
                    // Đây là signature đặc trưng của Colyseus (SFL dùng cái này)
                    let mmo = p?.mmoService || sn?.mmoService || s?.mmoService;
                    if (!mmo && p?.value?.mmoService) mmo = p.value.mmoService; // Context value

                    if (mmo?.state?.context?.server?.state?.players) {
                        const ctx = mmo.state.context;
                        const pls = ctx.server.state.players;
                        const sid = ctx.server.sessionId;
                        const me = pls.get ? pls.get(sid) : pls[sid];
                        if (me && typeof me.x === 'number') return { x: me.x, y: me.y };
                    }

                    // Dự phòng cho Phaser Engine ẩn
                    const g = p?.game || sn?.game || window.Phaser?.GAMES?.[0];
                    if (g?.scene?.scenes) {
                        for (const scene of g.scene.scenes) {
                            const pl = scene.player || scene.currentPlayer;
                            if (pl && typeof pl.x === 'number') return { x: pl.x, y: pl.y };
                        }
                    }

                    if (n.child) stack.push(n.child);
                    if (n.sibling) stack.push(n.sibling);
                }
            }
        } catch (e) {
            console.error("Fiber Scan Error:", e);
        }
        return null;
    }

    function scan() {
        try {
            const pos = findSFLInFiber();
            if (pos) {
                // Đẩy tọa độ qua 2 kênh
                document.body.dataset.sflPos = `${Math.round(pos.x)},${Math.round(pos.y)}`;
                window.postMessage({ type: 'SFL_OMNI_PULSE', player: pos }, '*');
                
                if (Date.now() - lastLogTime > 5000) {
                    console.log("📡 [BRIDGE]: ✅ LOCKED-ON! (X: " + Math.round(pos.x) + " | Y: " + Math.round(pos.y) + ")");
                    lastLogTime = Date.now();
                }
                failReason = "OK";
            } else {
                failReason = "Không thấy Engine (Đang quét 200 thẻ DOM). Thử di chuyển xem?";
            }
        } catch (e) {
            failReason = "Lỗi quét: " + e.message;
        }

        if (failReason !== "OK" && Date.now() - lastLogTime > 5000) {
            console.warn("🔍 [BRIDGE]: " + failReason);
            lastLogTime = Date.now();
        }
    }

    setInterval(scan, 100); 
})();
