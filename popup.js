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
