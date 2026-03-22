# SFL Auto-Deliver Extension (Version 2.0)

Công cụ tự động thực hiện các nhiệm vụ Delivery nâng cao trong game Sunflower Land.

## Tính năng Mới (V2.0)
- **Tự động Di chuyển**: Tool sử dụng phím mũi tên để di chuyển nhân vật đến gần NPC.
- **Du hành Thế giới**: Tự động mở bản đồ (World Map) và di chuyển giữa các đảo (Plaza, Beach, v.v.).
- **Nhận diện Heart Icon**: Chỉ thực hiện giao hàng khi nhiệm vụ đã đủ vật phẩm (hiện biểu tượng trái tim trong Codex).
- **Bộ nhớ Thông minh**: Lưu trữ vị trí NPC và trạng thái nhiệm vụ vào tệp `memory.json` và bộ nhớ trình duyệt.

## Cách cài đặt
1. Mở trình duyệt Chrome hoặc Edge.
2. Truy cập `chrome://extensions/`.
3. Bật **Developer mode**.
4. Nhấn **Load unpacked** và chọn thư mục `e:\SFL EXTENSION`.

## Cách sử dụng
1. Đăng nhập vào Sunflower Land.
2. Bật Extension và nhấn **Start Delivery Bot**.
3. Bot sẽ tự động:
    - Quét Codex để tìm nhiệm vụ có hình trái tim.
    - Xem NPC của nhiệm vụ đó ở đâu (ví dụ: Guria ở Plaza).
    - Mở Map, chọn đảo tương ứng.
    - Di chuyển nhân vật tới NPC và thực hiện giao hàng.

## Lưu ý quan trọng
- Hệ thống di chuyển sử dụng giả lập phím bấm (Arrow Keys).
- Tệp `memory.json` chứa tọa độ và vị trí NPC, bạn có thể cập nhật tệp này nếu game có thay đổi.
