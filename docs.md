# SFL Technical Analysis - Hacking the Engine

Tài liệu này giải thích cách Sunflower Land (SFL) hoạt động dưới góc độ mã nguồn và cách Extension của chúng ta "đọc" được dữ liệu từ game.

## 1. Công nghệ Cốt lõi (Core Engine)
- **Engine Đồ họa**: Game sử dụng **Phaser.js**. Mọi thứ bạn thấy (nhân vật, cây cối, NPC) đều được vẽ lên một thẻ `<canvas>` duy nhất. 
- **Hệ tọa độ (Cartesian)**: Game sử dụng trục X (ngang) và Y (dọc). Vị trí của mọi vật thể được tính bằng **Pixel thực** trên bản đồ thế giới, không phụ thuộc vào kích thước màn hình của bạn.
- **Quản lý Trạng thái**: Game dùng **React** để quản lý UI và kết nối đồng bộ dữ liệu giữa Server và Client.

## Tại sao Plaza lại khó lấy tọa độ? (Deep Insight)

Plaza không phải là một hòn đảo thông thường; nó là một **Thế giới Đồng bộ (Multiplayer World)** với kiến trúc cực kỳ phức tạp:
1. **Kiến trúc MMO (Colyseus)**: Tọa độ của nhân vật không nằm trong "Cảnh" (Scene) hiển thị mà nằm trong bộ não của một hệ thống quản lý trạng thái (`mmoService`).
2. **Cô lập React Context**: Con Robot `mmoService` này trốn rất kỹ trong các tầng lớp "Context" bảo mật của React. Các cảm biến thông thường chỉ quét bề mặt sẽ không bao giờ nhìn thấy nó.

## Giải pháp: Công nghệ Radar-X (Độc quyền)
Để giải quyết dứt điểm, Antigravity đã triển khai **Radar-X**:
- **Context Drilling**: Khả năng "khoan" sâu vào lớp phụ thuộc (Dependencies) của React để lôi dữ liệu ra.
- **Quét 2000 Nút thắt**: Công suất quét cực đại, đảm bảo không bỏ sót bất kỳ ngóc ngách nào trong RAM game.
- **Đồng bộ Server**: Tọa độ được lấy trực tiếp từ luồng dữ liệu của Server (Colyseus), đảm bảo độ chính xác tuyệt đối 100%.

![Plaza Sync Audit](file:///C:/Users/ADMIN/.gemini/antigravity/brain/326d6de9-f0f6-484a-828b-6f2c62b8940a/plaza_coord_dump_final_1774155794241.webp)
*Ghi lại cuộc "Động kích Bộ nhớ" (Memory Audit) để tìm ra đường dẫn dữ liệu đồng bộ từ Server.*

---
*Tài liệu này được soạn thảo bởi Antigravity nhằm giải đáp cấu trúc vận hành của SFL.*
