document.addEventListener('DOMContentLoaded', () => {
    // ─── TABS ───────────────────────────────────────────────────
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');
        });
    });

    // ─── BOT TAB ────────────────────────────────────────────────
    const indicator  = document.getElementById('indicator');
    const statusText = document.getElementById('statusText');
    const startStopBtn = document.getElementById('startStopBtn');

    setInterval(() => {
        chrome.storage.local.get(['isRunning'], r => updateUI(r.isRunning || false));
    }, 1000);

    startStopBtn.addEventListener('click', () => {
        chrome.storage.local.get(['isRunning'], r => {
            const running = r.isRunning || false;
            chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
                chrome.tabs.sendMessage(tabs[0].id, { action: running ? 'stop' : 'start' });
            });
        });
    });

    function updateUI(active) {
        if (active) {
            startStopBtn.textContent = '🛑 DỪNG GIAO HÀNG';
            startStopBtn.classList.add('stop');
            indicator.classList.add('active');
            statusText.textContent = 'ĐANG CHẠY...';
        } else {
            startStopBtn.textContent = '🚀 BẮT ĐẦU GIAO HÀNG';
            startStopBtn.classList.remove('stop');
            indicator.classList.remove('active');
            statusText.textContent = 'CHỜ BẮT ĐẦU';
        }
    }

    // ─── NPC SELECTOR TAB ───────────────────────────────────────
    let allNpcList = [];
    let selectedBlockedNpcs = new Set();

    // Default presets
    const PRESET_A = [];
    const PRESET_B = ["bert", "raven", "pete", "tywin", "cornwell", "tinker", "finley", "finn", "pharaoh", "miranda", "jester", "timmy", "old salty", "corale", "victoria", "peggy"];

    // Fetch all_npcs.json
    fetch(chrome.runtime.getURL('all_npcs.json'))
        .then(res => res.json())
        .then(data => {
            allNpcList = data.npcs || [];
            initNpcTab();
        })
        .catch(err => {
            console.warn('Fallback loading all_npcs.json', err);
            allNpcList = PRESET_B.map(id => ({ id, name: id.charAt(0).toUpperCase() + id.slice(1), island: 'all', blocks: PRESET_A.includes(id) ? ['A', 'B'] : ['B'] }));
            initNpcTab();
        });

    function initNpcTab() {
        chrome.storage.local.get(['sfl_selected_blocked_npcs'], result => {
            if (result.sfl_selected_blocked_npcs && Array.isArray(result.sfl_selected_blocked_npcs)) {
                selectedBlockedNpcs = new Set(result.sfl_selected_blocked_npcs.map(n => n.toLowerCase().trim()));
            } else {
                selectedBlockedNpcs = new Set(PRESET_B); // Default to Preset B
            }
            renderNpcList();
        });
    }

    function renderNpcList(filterText = '') {
        const container = document.getElementById('npcContainer');
        if (!container) return;
        container.innerHTML = '';

        const query = filterText.toLowerCase().trim();
        const filtered = allNpcList.filter(npc => npc.name.toLowerCase().includes(query) || npc.id.toLowerCase().includes(query) || (npc.island && npc.island.toLowerCase().includes(query)));

        if (filtered.length === 0) {
            container.innerHTML = '<div style="opacity:0.5;font-size:11px;padding:8px;text-align:center;">Không tìm thấy NPC nào.</div>';
            return;
        }

        filtered.forEach(npc => {
            const isChecked = selectedBlockedNpcs.has(npc.id.toLowerCase());
            const item = document.createElement('div');
            item.className = 'npc-item';

            const blocksBadge = (npc.blocks || []).map(b => `<span class="badge block-${b.toLowerCase()}">${b}</span>`).join(' ');
            const islandBadge = npc.island ? `<span class="badge" style="opacity:0.7">${npc.island}</span>` : '';

            item.innerHTML = `
                <label>
                    <input type="checkbox" value="${npc.id}" ${isChecked ? 'checked' : ''} />
                    <span><b>${npc.name}</b></span>
                </label>
                <div style="display:flex;gap:4px;align-items:center;">
                    ${islandBadge}
                    ${blocksBadge}
                </div>
            `;

            const chk = item.querySelector('input');
            chk.addEventListener('change', (e) => {
                if (e.target.checked) {
                    selectedBlockedNpcs.add(npc.id.toLowerCase());
                } else {
                    selectedBlockedNpcs.delete(npc.id.toLowerCase());
                }
            });

            container.appendChild(item);
        });
    }

    // Search filter listener
    const npcSearch = document.getElementById('npcSearch');
    if (npcSearch) {
        npcSearch.addEventListener('input', (e) => renderNpcList(e.target.value));
    }

    // Preset Buttons
    document.getElementById('presetABtn')?.addEventListener('click', () => {
        selectedBlockedNpcs = new Set(PRESET_A);
        renderNpcList(npcSearch ? npcSearch.value : '');
    });

    document.getElementById('presetBBtn')?.addEventListener('click', () => {
        selectedBlockedNpcs = new Set(PRESET_B);
        renderNpcList(npcSearch ? npcSearch.value : '');
    });

    document.getElementById('selectAllNpcBtn')?.addEventListener('click', () => {
        allNpcList.forEach(n => selectedBlockedNpcs.add(n.id.toLowerCase()));
        renderNpcList(npcSearch ? npcSearch.value : '');
    });

    document.getElementById('clearAllNpcBtn')?.addEventListener('click', () => {
        selectedBlockedNpcs.clear();
        renderNpcList(npcSearch ? npcSearch.value : '');
    });

    // Save Selection
    document.getElementById('saveNpcsBtn')?.addEventListener('click', () => {
        const blockedArr = Array.from(selectedBlockedNpcs);
        chrome.storage.local.set({ sfl_selected_blocked_npcs: blockedArr }, () => {
            const btn = document.getElementById('saveNpcsBtn');
            const originalText = btn.textContent;
            btn.textContent = `✅ Đã lưu (${blockedArr.length} NPC)!`;
            setTimeout(() => { btn.textContent = originalText; }, 1500);

            chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
                if (tabs[0]) chrome.tabs.sendMessage(tabs[0].id, { action: 'reload_blocked_npcs' });
            });
        });
    });

    // ─── NODE EDITOR TAB ────────────────────────────────────────
    const islandSelect = document.getElementById('islandSelect');
    let graphs = {}; // { plaza: { nodes: {id: {x,y}}, edges: [[a,b],...] }, ... }

    // Load graph data từ storage
    chrome.storage.local.get(['sfl_node_graphs'], r => {
        graphs = r.sfl_node_graphs || {};
        renderGraph();
    });

    islandSelect.addEventListener('change', renderGraph);

    function getIsland() { return islandSelect.value; }

    function ensureIsland(island) {
        if (!graphs[island]) graphs[island] = { nodes: {}, edges: [] };
    }

    // ── Render danh sách node và edge ──────────────────────────
    function renderGraph() {
        const island = getIsland();
        const g = graphs[island] || { nodes: {}, edges: [] };

        // Nodes
        const nodeList = document.getElementById('nodeList');
        nodeList.innerHTML = '';
        const nodeIds = Object.keys(g.nodes);
        if (nodeIds.length === 0) {
            nodeList.innerHTML = '<div style="opacity:0.5;font-size:11px">Chưa có node. Thêm node bên trên.</div>';
        }
        nodeIds.forEach(id => {
            const { x, y } = g.nodes[id];
            const el = document.createElement('div');
            el.className = 'node-item';
            el.innerHTML = `<span>📍 <b>${id}</b> (${x}, ${y})</span><button data-id="${id}" title="Xóa">✕</button>`;
            el.querySelector('button').addEventListener('click', () => {
                delete graphs[island].nodes[id];
                // Xóa cả các edge liên quan
                graphs[island].edges = graphs[island].edges.filter(([a, b]) => a !== id && b !== id);
                renderGraph();
            });
            nodeList.appendChild(el);
        });

        // Edges
        const edgeList = document.getElementById('edgeList');
        edgeList.innerHTML = '';
        if (!g.edges || g.edges.length === 0) {
            edgeList.innerHTML = '<div style="opacity:0.5;font-size:11px">Chưa có cạnh nào.</div>';
        }
        (g.edges || []).forEach(([a, b], idx) => {
            const el = document.createElement('div');
            el.className = 'edge-item';
            el.innerHTML = `<span>${a} ↔ ${b}</span><button data-idx="${idx}">✕</button>`;
            el.querySelector('button').addEventListener('click', () => {
                graphs[island].edges.splice(idx, 1);
                renderGraph();
            });
            edgeList.appendChild(el);
        });

        // Sync autocomplete inputs for edges
        syncDatalist(nodeIds);
    }

    function syncDatalist(nodeIds) {
        ['edgeA', 'edgeB', 'nodeName'].forEach(inputId => {
            const input = document.getElementById(inputId);
            const listId = `${inputId}-list`;
            let dl = document.getElementById(listId);
            if (!dl) {
                dl = document.createElement('datalist');
                dl.id = listId;
                input.setAttribute('list', listId);
                document.body.appendChild(dl);
            }
            dl.innerHTML = nodeIds.map(id => `<option value="${id}">`).join('');
        });
    }

    // ── Thêm node ─────────────────────────────────────────────
    document.getElementById('addNodeBtn').addEventListener('click', () => {
        const name = document.getElementById('nodeName').value.trim().toLowerCase();
        const x = parseInt(document.getElementById('nodeX').value);
        const y = parseInt(document.getElementById('nodeY').value);
        if (!name || isNaN(x) || isNaN(y)) return alert('Nhập đầy đủ: Tên, X, Y');
        const island = getIsland();
        ensureIsland(island);
        graphs[island].nodes[name] = { x, y };
        document.getElementById('nodeName').value = '';
        document.getElementById('nodeX').value = '';
        document.getElementById('nodeY').value = '';
        renderGraph();
    });

    // ── Thêm edge ─────────────────────────────────────────────
    document.getElementById('addEdgeBtn').addEventListener('click', () => {
        const a = document.getElementById('edgeA').value.trim().toLowerCase();
        const b = document.getElementById('edgeB').value.trim().toLowerCase();
        if (!a || !b || a === b) return alert('Nhập 2 tên node khác nhau');
        const island = getIsland();
        ensureIsland(island);
        const g = graphs[island];
        // Tránh trùng cạnh
        const exists = g.edges.some(([ea, eb]) => (ea === a && eb === b) || (ea === b && eb === a));
        if (!exists) g.edges.push([a, b]);
        document.getElementById('edgeA').value = '';
        document.getElementById('edgeB').value = '';
        renderGraph();
    });

    // ── Xóa toàn bộ map ───────────────────────────────────────
    document.getElementById('clearIslandBtn').addEventListener('click', () => {
        if (!confirm(`Xóa toàn bộ đồ thị [${getIsland()}]?`)) return;
        graphs[getIsland()] = { nodes: {}, edges: [] };
        renderGraph();
    });

    // ── Lưu vào storage → content.js sẽ đọc ──────────────────
    document.getElementById('saveGraphBtn').addEventListener('click', () => {
        chrome.storage.local.set({ sfl_node_graphs: graphs }, () => {
            const btn = document.getElementById('saveGraphBtn');
            btn.textContent = '✅ Đã lưu!';
            setTimeout(() => { btn.textContent = '💾 Lưu đồ thị'; }, 1500);
            // Thông báo content.js reload graph data
            chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
                if (tabs[0]) chrome.tabs.sendMessage(tabs[0].id, { action: 'reload_graph' });
            });
        });
    });
});
