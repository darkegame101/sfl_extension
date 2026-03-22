# Kế hoạch Tìm kiếm và Xác định NPC (NPC Discovery Plan)

Dựa trên yêu cầu của bạn về một hệ thống "chuẩn và hợp lý nhất", tôi xin trình bày 3 phương pháp chính để nhân vật có thể tìm thấy NPC trên bản đồ:

## Phương pháp 1: Pixel-Grid Vectoring (Đang áp dụng)
Hệ thống này dựa trên trục tọa độ X/Y lấy (0,0) làm gốc (Corner).
- **Cách hoạt động**: Nhân vật tính toán khoảng cách từ A đến B và đi theo đường thẳng duy nhất (Vectơ).
- **Ưu điểm**: Cực kỳ nhanh, không cần nhìn thấy NPC cũng đi được.
- **Nhược điểm**: Có sai số nếu bị kẹt vật cản không mong muốn.

## Phương pháp 2: DOM-Text Scanning (Quét tên NPC)
Tìm kiếm trực tiếp các phần tử trong mã nguồn game có chứa tên NPC (PETE, BETTY...).
- **Cách hoạt động**: Bot quét toàn bộ màn hình để tìm chữ "PETE". Nếu tìm thấy, nó sẽ click vào đó.
- **Ưu điểm**: Độ chính xác 100% nếu NPC nằm trong khung hình.
- **Nhược điểm**: Chỉ hoạt động khi NPC đã hiện trên màn hình. Không dùng để đi xa được.

## Phương pháp 3: Mixed-Hybrid Discovery (Hệ thống Hoàn hảo - Đang hướng tới)
Kết hợp sức mạnh của cả hai loại trên.
- **Quy trình**:
    1. **Giai đoạn 1 (Chạy nhanh)**: Dùng **Pixel-Grid** để chạy tới gần vị trí NPC đã lưu (ví dụ: cách 50px).
    2. **Giai đoạn 2 (Dò tìm)**: Khi đã tới gần, Bot kích hoạt chế độ **Quét tên**. Nó sẽ xoay nhân vật hoặc đi zic-zac nhẹ để "nhìn thấy" NPC.
    3. **Giai đoạn 3 (Khóa mục tiêu)**: Ngay khi bảng tên NPC xuất hiện trong DOM, Bot sẽ bỏ qua tọa độ X/Y và **Click trực tiếp** vào NPC để tương tác.

---

## Phân tích Chuyên sâu: Identity & Memory (Dữ liệu nội bộ Game)

Tôi đã phân tích cấu trúc bộ nhớ của SFL và xác định được cách Game phân biệt các thực thể:

### 1. Nhân vật của bạn (Local Player)
- **Vị trí**: Nằm trong `mmoService` context.
- **Đặc điểm**: Có `username` là `yourbabyboo` và `farmId` duy nhất (ví dụ: `7009667226...`).
- **Tọa độ**: Được lưu trong `playerCoordinates: { x, y }`. Đây là "GPS kim chỉ nam" tuyệt đối cho bot.

### 2. Người chơi khác (Other Players)
- **Vị trí**: Lưu trong danh sách `players[]`.
- **Đặc điểm**: Có thêm trường `playerId` (chuỗi ký tự như `7sp_2lhAG`).
- **Phân biệt**: Bot sẽ **bỏ qua** nhóm này để không bị nhầm lẫn khi đi theo người khác.

### 3. NPC (Pete, Peggy, v.v.)
- **Vị trí**: Thường được lưu dưới dạng `NPCIcon` (biểu tượng tĩnh) hoặc trong `scene.npcs`.
- **Đặc điểm**: Có tọa độ **CỐ ĐỊNH** (không bao giờ thay đổi) và được định danh bằng Label (ví dụ: `"PETE"`).
- **Cách tìm**: Bot sẽ quét Label này trong scene data để lấy tọa độ pixel đích.

### Lời khuyên (Recommendation)
Bạn nên dùng **Phương pháp 3**. Đây là cách mà các Bot chuyên nghiệp thực hiện.
- Tôi đã xây dựng xong Giai đoạn 1 và 2 (Pixel Grid + Manual Set).
- Để hoàn thiện "chuẩn nhất", tôi sẽ tối ưu thêm phần "Lock-on" (Khóa mục tiêu) khi nhân vật đã đứng cạnh NPC.

Bạn thấy kế hoạch này như thế nào?
