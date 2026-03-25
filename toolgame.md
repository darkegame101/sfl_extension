# SFL Auto-Deliver — Quy trình Vận hành Toàn bộ

Tài liệu này mô tả theo thứ tự từng bước bot chạy trong game, công nghệ sử dụng, lý do chọn, và cách tránh bị game phát hiện.

---

## Tổng quan Kiến trúc

Bot hoạt động qua 2 file chạy ở 2 "thế giới" riêng biệt:

| File | Thế giới | Mô tả |
|--|--|--|
| `content.js` | **Isolated World** (Chrome Extension) | Điều phối tổng thể: scan đơn, điều hướng nhân vật, hậu kiểm UI |
| `bridge.js` | **Main World** (cùng ngữ cảnh với game) | Móc vào engine: XState, Phaser, React Fiber |

---

## Giai đoạn 1 — Khởi động Bridge (document_start)

**File:** `bridge.js`  
**Thời điểm:** Ngay khi trang web bắt đầu tải (trước cả React)

### Bước 1.1 — Chiếm quyền `addEventListener`
```javascript
EventTarget.prototype.addEventListener = function(type, listener, options) { ... }
```
- **Công nghệ:** Monkey-patch prototype của DOM
- **Mục đích:** Ăn cắp và lưu lại toàn bộ listener `keydown`, `pointerdown`, `pointerup` của Phaser và React ngay từ lúc chúng đăng ký
- **Tại sao không bị phát hiện:** Việc override prototype xảy ra ở `document_start` — **trước khi game load**. Game không thể phân biệt listener gốc hay listener bị thay thế

### Bước 1.2 — Scan liên tục (setInterval 500ms)
- Gọi `findEntitiesInFiber()` mỗi 500ms
- Quét toàn bộ cây React Fiber để tìm:
  - Vị trí nhân vật (từ `mmoService → players → sessionId`)
  - Phaser Game Instance (từ `stateNode.game`)
  - XState `gameMachine` (từ `obj.state.context.state.delivery`)
- Kết quả ghi vào `document.body.dataset.*` để `content.js` đọc được qua DOM

---

## Giai đoạn 2 — Quét Đơn Hàng (SCAN)

**File:** `content.js`  
**Hàm:** `scanDeliveries()`

### Bước 2.1 — Mở Codex
- Tìm icon giao hàng (img width ≈ 31.5px, left 50–150px)
- Dùng `simulateFullClick()` → gửi `mousedown + mouseup + click` đầy đủ
- **Tại sao không bị phát hiện:** Không dùng `.click()` đơn lẻ mà gửi chuỗi 3 event giống người thật

### Bước 2.2 — Phát hiện Tim Đỏ (đơn có thể giao)
- Quét các `div.grid > div` tìm `img.absolute.top-0.5.right-0.5.w-3` (icon tim)
- Click vào đơn, đợi 1500ms cho chi tiết tải
- Đọc tên NPC từ HTML (`img src` hoặc text trong panel chi tiết)
- Đóng Codex, set `targetNPC` và `currentTask = "TRAVEL"`

---

## Giai đoạn 3 — Di chuyển đến NPC (TRAVEL → MOVE)

**File:** `content.js`  
**Hàm:** `executePathToNPC()` → `navigateViaGraph()` → `graphBFS()`

### Bước 3.1 — Xác định tọa độ NPC
- Ưu tiên lấy từ `MASTER_NPC_DATA[island][npcName]` (tọa độ cứng)
- **Tại sao dùng tọa độ cứng:** NPC không di chuyển, vị trí cố định 100%

### Bước 3.2 — Điều hướng qua Đồ thị (Node Graph)
- **Công nghệ:** Đồ thị liên thông (Graph) + BFS (Breadth-First Search)
- **Cơ chế:**
  1. Snap vị trí hiện tại đến Node gần nhất trong hệ thống
  2. Tìm đường ngắn nhất qua các Node trung gian để đến vùng chứa NPC
  3. Di chuyển giữa các Node theo quy tắc **Trục tọa độ (Axis-aligned)**: Đi ngang (X) trước, sau đó mới đi dọc (Y) -> **Tuyệt đối không đi chéo**.
- **Tại sao:** Tránh các vật cản lớn mà A* thông thường khó xử lý, đồng thời mô phỏng cách người chơi thường nhấn phím (từng phím một thay vì nhấn tổ hợp).

### Bước 3.3 — Fallback A* (nếu graph lỗi)
- Nếu không có đồ thị cho map đó, bot sẽ quay lại dùng `moveTowardsTarget()` với thuật toán A* cơ bản
- Quét ma trận va chạm từ Phaser scene (`SFL_GRID_REQUEST`)
- Tìm đường lưới 32px để tránh vật cản nhỏ

### Bước 3.4 — Phát hiện kẹt (Stuck Detection)
- So sánh tọa độ thật (từ `document.body.dataset.sflPos`) mỗi 150ms
- Nếu không nhúc nhích sau 10 tick → thực hiện "Random Jiggle" hoặc reset chu trình di chuyển.

---

## Giai đoạn 4 — Tương tác NPC (DELIVER)

**File:** `content.js` → `bridge.js`  
**Hàm:** `interactWithNPC()` → `window.SFL_TRIGGER_NPC()`

### Bước 4.1 — Kiểm tra tiền điều kiện
- Đảm bảo không có Codex/Dialog đang mở (`forceClosePanels()`)
- Đợi 800ms để màn hình ổn định

### Bước 4.2 — PLAN-D: Giao hàng Native qua XState
**Công nghệ:** XState Interpreter `.send()`  
```javascript
send.call(svc, { type: "order.delivered", id: targetOrder.id });
```
- Scan `state.context.state.delivery.orders` để tìm order theo field `from` khớp tên NPC
- Gửi `order.delivered` với đúng `id` — event này được `gameMachine` chấp nhận 100% khi đang ở state "playing"
- **Tại sao an toàn:** Đây là event native của game, không khác gì click nút "Deliver" thật. Game sẽ tự đặt lịch Autosave sau một khoảng thời gian theo cơ chế thông thường

### Bước 4.3 — PLAN-X: Replay lệnh INTERACT đã nghe lén (fallback)
- Nếu đã từng capture được lệnh INTERACT thật (người dùng click thủ công), ta replay lệnh đó với tên NPC được thay thế
- **Tại sao:** Replay lệnh gốc 100% giống người thật, không thể bị phát hiện

### Bước 4.4 — PLAN-E: Ghost Keyboard Event
- Bắn thẳng phím 'E' vào danh sách listener Phaser đã cướp với POJO `{ isTrusted: true }`
- **Tại sao không bị chặn:** Phaser không kiểm tra `instanceof Event` mà chỉ đọc `.key`, `.keyCode`, và `isTrusted`. POJO đã giả đủ 3 trường này

### Bước 4.5 — PLAN-Y: React Fiber Prop Injection
- Duyệt cây React Fiber từ canvas lên 200 node
- Tìm mọi prop có tên bắt đầu `on` hoặc chứa `interact/speak/dialog`
- Gọi trực tiếp: `props.onInteract(npcName)` và `props.onInteract({ npc: npcName })`
- **Tại sao:** React Fiber sẽ không phân biệt được lời gọi từ bot hay từ click chuột thật, vì ta truy cập chính con trỏ hàm gốc

### Bước 4.6 — PLAN-A: Phaser Engine Direct Emit (nếu Engine đã bắt được)
- Tìm Sprite NPC trong `scene.children.list` theo `texture.key`
- Gọi `npc.emit('pointerdown', ptr)` và `scene.input.emit('gameobjectdown', ptr, npc)`
- **Tại sao:** Đây là đường dẫn chính thức của Phaser input pipeline — hoàn toàn không bị game phân biệt

### Bước 4.7 — PLAN-B: Toán học Blind-Fire (last resort)
- Tính offset pixels từ vị trí nhân vật đến NPC theo zoom factor ~3.0
- Rải 25 điểm click hình 5×5, spacing 30px để bù sai số
- Gửi `dispatchEvent(PointerEvent)` + bắn Ghost Pointer vào listener Phaser
- **Rủi ro cao:** Có thể click nhầm vật thể, chỉ dùng khi mọi plan khác thất bại

---

## Giai đoạn 5 — Sau khi giao hàng (IDLE)

- `currentTask = "IDLE"` → vòng lặp chính chờ 3 giây rồi quay lại SCAN
- Codex được mở lại để tìm đơn tiếp theo

---

## Cơ chế Tránh Phát hiện

| Kỹ thuật | Mô tả |
|--|--|
| **Không dùng `.dispatchEvent()` thông thường** | `isTrusted: false` bị Phaser và React reject. Thay bằng gọi thẳng listener function với POJO |
| **Không tự thêm event listener mới** | Chỉ đọc listener của game bằng cách override `addEventListener` trước khi game load |
| **Chạy ở Main World** | `bridge.js` chạy cùng bối cảnh JS với game → truy cập được tất cả biến toàn cục |
| **Dùng event native** | `order.delivered` là event game tự định nghĩa → không có cách nào phân biệt |
| **Mô phỏng typing speed** | Di chuyển theo duration tính toán từ khoảng cách, không teleport ngay lập tức |
| **Không dùng Selenium/Puppeteer** | Không có WebDriver fingerprint — extension Chrome là môi trường bình thường trên trình duyệt |
