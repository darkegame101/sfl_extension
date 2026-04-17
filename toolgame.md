# SFL Auto-Deliver — Tài liệu Vận hành Hiện tại
> Cập nhật lần cuối: 2026-04-17  
> Phiên bản: **SFL Custom 2.0 (Trường)**

Tài liệu này mô tả toàn bộ cơ chế bot đang hoạt động: kiến trúc, từng giai đoạn, công nghệ sử dụng, và cách tránh bị phát hiện.

---

## Tổng quan Kiến trúc

Bot hoạt động qua 2 file chạy ở 2 "thế giới" riêng biệt:

| File | Thế giới | Mô tả |
|---|---|---|
| `content.js` | **Isolated World** (Chrome Extension) | Điều phối tổng thể: scan đơn, điều hướng nhân vật, hậu kiểm UI, license |
| `bridge.js` | **Main World** (cùng ngữ cảnh với game) | Móc vào engine: XState, Phaser, React Fiber. Ghi tọa độ ra `document.body.dataset.*` |
| `background.js` | **Service Worker** | Proxy HTTP đến Firebase (tránh CORS) để xác thực license |

---

## ⚙️ Hệ thống Timer — Web Worker Engine (Anti-Throttle)

**Vấn đề:** Chrome throttle `setTimeout`/`setInterval` trên main thread khi tab mất focus → bot dừng.  
**Giải pháp:** Web Worker chạy trên thread riêng, **không bị throttle** dù tab ẩn.

```
[Web Worker] ← không bị throttle dù tab ẩn
  ├─ tick 200ms  → postMessage('loop')      → mainLoop()
  ├─ tick 500ms  → postMessage('watchdog')  → runWatchdog()
  └─ tick 2000ms → postMessage('ui_check')  → kiểm tra UI còn hiển thị không

[Main Thread] nhận message → xử lý callback
```

**Các hàm điều khiển Worker:**
- `startBotWorker()` — tạo Worker, bắt đầu gửi tick
- `stopBotWorker()` — terminate Worker, giải phóng CPU
- `loop()` — alias gọi `startBotWorker()` (giữ tương thích code cũ)

---

## 🛡️ Hệ thống Phát hiện Kẹt — Global Stuck Watchdog v2

**Thuật toán: Rolling Window Buffer** (thay thế phương pháp "distance from last point" cũ)

```
Cứ mỗi 2 giây → chụp 1 snapshot vị trí (x, y)
Buffer giữ 10 điểm gần nhất = cửa sổ 20 giây

Mỗi 500ms → so sánh vị trí hiện tại với điểm CŨ NHẤT trong buffer:
  dist(hiện_tại, cũ_nhất) < 60px?
  → CÓ = kẹt (kể cả nhích lên xuống 30–40px) → RELOAD
  → KHÔNG = đã thoát ra → xóa buffer, bắt đầu lại
```

**Tại sao Rolling Window tốt hơn cách cũ:**
- Cách cũ: reset baseline mỗi khi nhích 25px → bị lừa bởi jiggle up/down
- Cách mới: so với điểm **20 giây trước** → bắt được mọi kiểu dao động

**Điều kiện kích hoạt:** Chỉ khi `currentTask` ∈ {MOVE, TRAVEL, DELIVER, WAIT_SYNC}

**Hành động khi phát hiện kẹt:**
| Task đang chạy | Task được lưu trước reload |
|---|---|
| MOVE | MOVE → tiếp tục đi tới NPC |
| TRAVEL | TRAVEL → thử chuyển map lại |
| DELIVER (kẹt gần NPC) | → đổi thành MOVE → áp sát lại |
| WAIT_SYNC (kẹt chờ map) | → đổi thành TRAVEL → chuyển map lại |

---

## 💾 Hệ thống Resume sau Reload

Bot **tự động tiếp tục nhiệm vụ** sau khi reload trang:

```
saveMemory() lưu vào chrome.storage.local:
  - isRunning, currentTask, targetNPC, targetIsland
  - sfl_memory (delivery_queue, speedMultiplier, ...)
  - licenseKey, userHWID

Khi load lại → loadMemory() → nếu isRunning === true → startBotWorker()
```

**Không bao giờ bị mắc kẹt vô hạn:** Watchdog reload → resume → tiếp tục từ đúng task.

---

## Giai đoạn 1 — Khởi động Bridge (`document_start`)

**File:** `bridge.js` | **Thời điểm:** Trước khi React load

### 1.1 — Monkey-patch `addEventListener`
```javascript
EventTarget.prototype.addEventListener = function(type, listener, options) { ... }
```
- Lưu lại toàn bộ listener `keydown`, `pointerdown`, `pointerup` của Phaser & React
- Xảy ra trước khi game load → game không thể phân biệt

### 1.2 — Scan liên tục (500ms)
- Gọi `findEntitiesInFiber()` → quét cây React Fiber tìm:
  - Vị trí nhân vật: `mmoService → players → sessionId`
  - Phaser Game Instance: `stateNode.game`
  - XState `gameMachine`: `obj.state.context.state.delivery`
- Kết quả ghi vào `document.body.dataset.sflPos`, `sflEntities`, `sflNPCVisuals`

---

## Giai đoạn 2 — Khởi động & Xác thực License

**File:** `content.js` | **Hàm:** `checkLicenseRemote()`

### 2.1 — HWID Fingerprint
- Tạo SHA-256 hash từ `userAgent + screen.width + screen.height + random salt`
- Lưu vào `chrome.storage.local` — persistent qua reload

### 2.2 — Xác thực Firebase (qua background.js)
- `content.js` → `chrome.runtime.sendMessage({action: "CHECK_LICENSE"})` → `background.js`
- `background.js` → `fetch(Firebase REST API)` → trả về data
- Kiểm tra: `status === "active"`, ngày hết hạn, HWID binding

### 2.3 — HWID Binding
- Lần đầu dùng key: ghi HWID vào Firebase (`PATCH`)
- Lần sau: so sánh HWID → nếu khác máy → từ chối (`MISMATCH`)

---

## Giai đoạn 3 — Quét Đơn Hàng (SCAN → IDLE)

**File:** `content.js` | **Hàm:** `scanDeliveries()`

### 3.1 — Mở Codex
- Tìm icon sách (img width ≈ 31.5px, left 50–200px)
- `simulateFullClick()` → gửi `mousedown + mouseup + click` đầy đủ

### 3.2 — Phase 1: Dọn dẹp đơn cũ (Skip)
- Quét `.grid > div` tìm item màu cam `rgb(240,145,0)`
- **CHỈ skip** nếu: không có khóa (`padlock`), không có tim (`heart`), phần thưởng là **coin hoặc flower**, không phải **Floater/Ticket**
- Bảo vệ tuyệt đối mục Floater/Wandering/Special

### 3.3 — Phase 2: Gom đơn có tim (Ready)
- Tìm `img.absolute.top-0.5.right-0.5` (icon tim đỏ)
- Click đơn → đọc tên NPC từ `p.capitalize.text-xs` trong panel chi tiết
- **Lọc qua NPC_WHITELIST:** Chỉ lấy các NPC đã được cấu hình:

```javascript
const NPC_WHITELIST = ["betty", "blacksmith", "tango", "guria",
                       "gambit", "grimbly", "grimtooth", "grubnuk", "gordo"];
```

### 3.4 — Tối ưu hóa Lộ trình (Nearest Neighbor)
- `sortDeliveryQueue()` sắp xếp hàng chờ theo **chi phí di chuyển thật**
- Tính cost dùng **Node Graph BFS** (nếu có đồ thị), fallback sang Euclidean
- NPC cùng đảo ưu tiên trước, NPC khác đảo bị cộng penalty 10000

---

## Giai đoạn 4 — Di chuyển đến NPC (TRAVEL → WAIT_SYNC → MOVE)

**File:** `content.js` | **Hàm:** `executePathToNPC()` → `navigateViaGraph()` → `moveStraight()`

### 4.1 — Chuyển đảo (TRAVEL)
- Đổi `window.location.hash` → `#/world/{island}`
- Transit rule: Beach ↔ Kingdom phải qua Plaza trung gian
- Sau khi đến Plaza (đích cuối): `location.reload()` để đồng bộ state

### 4.2 — Chờ Engine đồng bộ (WAIT_SYNC)
- Đợi `getGameData()` trả về `data.player` hợp lệ
- Timeout → watchdog phát hiện → chuyển sang TRAVEL để thử lại

### 4.3 — Điều hướng qua Node Graph (MOVE)
```
Ưu tiên: User Graph (chrome.storage) > Hardcoded Island Graph
  1. findNearestNode(graph, curX, curY) → startNode
  2. Nếu isNewMapMove → dùng node "root" làm điểm xuất phát
  3. graphBFS(startNode, endNode) → danh sách node
  4. moveStraight(wp.x, wp.y) cho từng node
```

### 4.4 — `moveStraight()` — Di chuyển Axis-Aligned
- **X trước, Y sau** (không đi chéo — giống người thật nhấn phím)
- **Dynamic Duration:** >100px → 800ms, <25px → 70ms, giữa → tuyến tính
- **Node Snapping:** Dừng khi sai số < 14px
- **Evasive Jiggle:** Kẹt sau 3 tick → lách vuông góc 150ms

### 4.5 — Fallback A* (nếu không có graph)
- `findPath(tx, ty)` → gửi `SFL_GRID_REQUEST` → nhận ma trận va chạm từ Phaser
- Tìm đường trên lưới 32px tránh vật cản

### 4.6 — Phát hiện Kẹt cục bộ (trong moveStraight/moveTowardsTarget)
- Nếu không xê dịch > 20px trong **6 giây** → `saveMemory()` → `location.reload()`
- **Phát hiện jiggle cục bộ:** `stuckCount > 3` → lách hướng vuông góc

---

## Giai đoạn 5 — Tương tác NPC (DELIVER)

**File:** `content.js` + `bridge.js` | **Hàm:** `interactWithNPC()`

### 5.1 — Tiền điều kiện
- `forceClosePanels()` đóng mọi Codex/Dialog đang mở
- Đợi 800ms để màn hình ổn định

### 5.2 — Kích hoạt tương tác
- `document.dispatchEvent(new CustomEvent('SFL_TRIGGER_REQUEST', { detail: targetNPC }))` → bridge xử lý
- Song song: bắn `simulateCanvasClick()` vào `burstPoints` của NPC (tọa độ pixel đã lưu)

### 5.3 — Xác nhận thành công
- Bridge ghi `document.body.dataset.sflInteractSuccess = "true"` khi delivery thành công
- `content.js` poll mỗi vòng lặp → nhận tín hiệu → xóa NPC khỏi `delivery_queue`

### 5.4 — Xử lý hội thoại
- Quét nút theo priority: `deliver > complete > trade > claim > sell > next > continue > got it`
- Click nút → nếu là "terminal verb" → đơn hoàn thành → về IDLE

### 5.5 — Jiggle khi không mở được dialog
- Sau mỗi 2 lần thất bại → nhích nhẹ `up → down` 100ms để kích hoạt sensor va chạm
- Tối đa 10 lần thử → nếu vẫn thất bại → `currentTask = "IDLE"` (bỏ qua, lấy đơn tiếp)

---

## Giai đoạn 6 — Về IDLE & Lặp lại

- Xóa NPC đã giao khỏi `delivery_queue`
- `currentTask = "IDLE"` → `sortDeliveryQueue()` → lấy NPC gần nhất tiếp theo
- Nếu queue trống → `scanDeliveries()` để tìm đơn mới
- Nếu không có đơn nào sẵn sàng → `isRunning = false` → dừng để tiết kiệm CPU

---

## Hệ thống Tọa độ

### Nguồn dữ liệu (theo thứ tự ưu tiên)
```
1. document.body.dataset.sflPos        ← Bridge Omni-Pulse (nhanh nhất)
2. window.postMessage (SFL_OMNI_PULSE) ← Bridge fallback
3. React Fiber scan                    ← Dự phòng khi bridge crash
```

### MASTER_NPC_DATA
- Tải từ `npc_locations.json` khi script khởi động (`syncNPCLocations()`)
- Format: `{ plaza: { betty: { x, y }, ... }, beach: { ... } }`

### Node Graph
- **Hardcoded:** `islands_graph_data.js` → `window.SFL_ISLAND_GRAPHS`
- **User custom:** `chrome.storage.local['sfl_node_graphs']`
- User graph ưu tiên hơn hardcoded

---

## Cơ chế Tránh Phát hiện

| Kỹ thuật | Mô tả |
|---|---|
| **Không dùng `.dispatchEvent()` thông thường** | `isTrusted: false` bị Phaser/React reject. Gọi thẳng listener function với POJO |
| **Monkey-patch trước game load** | Override `addEventListener` ở `document_start` — game không thể biết |
| **Event native của game** | `order.delivered` là event game tự định nghĩa → không thể phân biệt |
| **Axis-aligned movement** | Di chuyển từng trục, mô phỏng người thật nhấn phím ArrowKey |
| **Dynamic duration** | Thời gian nhấn phím tính từ khoảng cách thực tế, không cố định |
| **Web Worker Timer** | Bot chạy ổn định dù tab ẩn, không cần tab được focus |
| **Chrome Extension context** | Không có WebDriver fingerprint — môi trường bình thường |

---

## State Machine — Luồng chuyển trạng thái

```
IDLE
 ├─ queue còn đơn → TRAVEL
 └─ queue trống   → scanDeliveries()
                      ├─ có đơn → TRAVEL
                      └─ không có → dừng (isRunning = false)

TRAVEL → (chuyển đảo xong) → WAIT_SYNC
WAIT_SYNC → (Engine sync) → MOVE
MOVE → (tới nơi) → DELIVER
     → (thất bại) → IDLE

DELIVER → (thành công) → IDLE
        → (10 lần thất bại) → IDLE
```

---

## Thông số cấu hình quan trọng

| Hằng số | Giá trị | Ý nghĩa |
|---|---|---|
| `SNAPSHOT_INTERVAL_MS` | 2000ms | Watchdog chụp vị trí mỗi 2s |
| `MAX_SNAPSHOTS` | 10 | Buffer 20 giây lịch sử |
| `ESCAPE_RADIUS` | 60px | Phải thoát xa hơn 60px thì mới không coi là kẹt |
| `NPC_WHITELIST` | 9 NPC | Danh sách NPC được phép giao (cấu hình cứng) |
| `BASE_SPEED` | 0.1 | 100px/1000ms ở speedMultiplier=1.0 |
| Worker loop tick | 200ms | Tần suất gọi mainLoop() |
| Worker watchdog tick | 500ms | Tần suất kiểm tra stuck |
