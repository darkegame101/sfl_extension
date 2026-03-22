// SFL ENGINE BRIDGE (Runs in MAIN World)
(function () {
    console.log("💎 SFL BRIDGE ACTIVE: OMNI-ENTITY GPS (METHOD 2 PRO+)");
    let lastLogTime = 0;
    let failReason = "Đang tìm kiếm Engine...";

    function findEntitiesInFiber() {
        const result = { me: null, others: {} };
        try {
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
                    const sn = n.stateNode;
                    const s = n.memoizedState;

                    let mmo = p?.mmoService || sn?.mmoService || s?.mmoService;
                    if (!mmo && p?.value?.mmoService) mmo = p.value.mmoService;

                    if (mmo?.state?.context?.server?.state?.players) {
                        const ctx = mmo.state.context;
                        const pls = ctx.server.state.players;
                        const sid = ctx.server.sessionId;

                        // Quét mọi thực thể (Player và NPC)
                        pls.forEach((player, id) => {
                            const name = (player.username || "unknown").toLowerCase();
                            const pos = { x: Math.round(player.x), y: Math.round(player.y) };

                            if (id === sid) {
                                result.me = pos;
                            } else {
                                result.others[name] = pos;
                            }
                        });

                        if (result.me) return result;
                    }

                    if (n.child) stack.push(n.child);
                    if (n.sibling) stack.push(n.sibling);
                }
            }
        } catch (e) {
            console.error("Fiber Scan Error:", e);
        }
        return result.me ? result : null;
    }

    function scan() {
        try {
            const data = findEntitiesInFiber();
            if (data) {
                // Xuất tọa độ của tôi
                document.body.dataset.sflPos = `${data.me.x},${data.me.y}`;
                // Xuất danh sách thực thể (NPC/Players) bí mật
                document.body.dataset.sflEntities = JSON.stringify(data.others);

                window.postMessage({ type: 'SFL_OMNI_PULSE', player: data.me, others: data.others }, '*');

                if (Date.now() - lastLogTime > 5000) {
                    // console.log(`📡 [BRIDGE]: ✅ GPS LOCKED! (NPCs Found: ${Object.keys(data.others).length})`);
                    lastLogTime = Date.now();
                }
                failReason = "OK";
            } else {
                failReason = "Không thấy Engine. Thử di chuyển xem?";
            }
        } catch (e) {
            failReason = "Lỗi quét: " + e.message;
        }

        if (failReason !== "OK" && Date.now() - lastLogTime > 5000) {
            // console.warn("🔍 [BRIDGE]: " + failReason);
            lastLogTime = Date.now();
        }
    }

    setInterval(scan, 100);
})();
