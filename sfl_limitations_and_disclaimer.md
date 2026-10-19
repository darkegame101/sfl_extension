# CÁC CÂU HỎI KHÓ, CÂU TRẢ LỜI TRUNG THỰC & TUYÊN BỐ GIỚI HẠN DỰ ÁN
*(SFL Desktop RPA Tool: Limitations, Honest Audit & Formal Disclaimer)*

---

## 1. Tuyên Bố Kết Luận & Định Vị Bản Chất Hệ Thống

> [!IMPORTANT]
> **KẾT LUẬN CHÍNH THỨC VỀ BẢN CHẤT DỰ ÁN:**  
> *"Đây là bộ sinh hành vi ngẫu nhiên để thử nghiệm trên giao diện giả lập. Chúng tôi chưa chứng minh nó đại diện cho người thật, chưa đánh giá độ chính xác phân loại và không tuyên bố vượt qua hệ thống kiểm tra của nền tảng."*

Mã nguồn này được xây dựng như một **bản mẫu nghiên cứu kỹ thuật (Heuristic Simulation Prototype)** ứng dụng các mô hình tâm lý học vận động (HCI) kinh điển vào tự động hóa giao diện desktop. Mọi thông số thời gian, quỹ đạo và xác suất mô phỏng đều dựa trên lý thuyết công bố công khai, không thu thập dữ liệu người dùng thật (Zero Telemetry Boundary) và không cam kết né tránh hoàn toàn các cơ chế giám sát của bên thứ ba.

---

## 2. Các Câu Hỏi Khó & Câu Trả Lời Trung Thực

### Câu hỏi 1: “Cơ sở nào cho thấy hành vi này đại diện cho người dùng thật?”
- **Câu trả lời trung thực:**  
  Hiện các khoảng thời gian, xác suất bỏ sót, danh tính nhân khẩu và persona được thiết lập theo suy nghiệm (heuristic) trong mã; dự án hoàn toàn không có dữ liệu đo đạc thực nghiệm từ người tham gia hay kết quả kiểm định thống kê trên tập mẫu người chơi thực tế. Vì vậy, hệ thống này được định vị chính xác là **prototype mô phỏng theo heuristic**, chưa phải là mô hình hành vi người dùng đã được kiểm chứng khoa học thực nghiệm.

### Câu hỏi 2: “Hệ thống có thực sự thực hiện tác vụ trong game không?”
- **Câu trả lời trung thực & Hiện trạng khắc phục:**  
  - *Thiếu sót ban đầu:* Trong các bản nháp trước, `run.py` chỉ ghi nhận trạng thái gieo trồng vào bộ nhớ JSON (`record_planting`) mà chưa móc nối các lệnh gọi click vật lý `harvest_plots` và `plant_plots` từ [crop_manager.py](file:///f:/sfland%20auto/tasks/crop_manager.py), dẫn đến nguy cơ lệch pha giữa trạng thái nội bộ và giao diện game.
  - *Khắc phục đã thực hiện:* `run.py` hiện đã tích hợp trực tiếp chu trình thu hoạch (`harvest_plots`) và gieo hạt (`plant_plots`) với tọa độ ô đất và giỏ hạt thực tế, đảm bảo mọi ghi nhận trong bộ nhớ chỉ diễn ra đồng thời với chuỗi sự kiện chuột trên màn hình game.

### Câu hỏi 3: “Điều gì xảy ra khi chạy lâu hoặc gặp lỗi?”
- **Câu trả lời trung thực & Hiện trạng khắc phục:**  
  - *Thiếu sót ban đầu:* Các phiên mở trình duyệt không được bọc trong khối `try...finally`, dẫn đến rủi ro rò rỉ profile/tiến trình Chromium nếu có ngoại lệ; danh sách profile chỉ nạp một lần lúc khởi động; trạng thái JSON ghi đè trực tiếp dễ gây file 0-byte nếu mất điện đột ngột.
  - *Khắc phục đã thực hiện:*
    1. **Bọc `try...finally` tuyệt đối:** Mọi phiên đều đảm bảo gọi `gpm.stop_profile(pid)` khi kết thúc hoặc khi gặp lỗi đột ngột.
    2. **Ghi tệp nguyên tử (Atomic Write):** Toàn bộ các mô-đun [farm_memory.py](file:///f:/sfland%20auto/scheduler/farm_memory.py), [persona_manager.py](file:///f:/sfland%20auto/scheduler/persona_manager.py), [scenario_engine.py](file:///f:/sfland%20auto/scheduler/scenario_engine.py) đều ghi ra file tạm `.tmp`, gọi `os.fsync`, sao lưu `.bak` và thực hiện `os.replace` để chống hỏng file.
    3. **Làm mới danh sách Profile động:** Vòng lặp `start_loop` liên tục thăm dò API GPM để nhận diện ngay khi người dùng thêm, xóa hoặc sửa profile.

### Câu hỏi 4: “Phát hiện captcha thì xử lý thế nào?”
- **Câu trả lời trung thực & Bản chất kỹ thuật:**  
  - *Thiếu sót ban đầu:* Cảnh báo phát hiện và chờ nhấn Enter, nhưng sau khi nhấn Enter thì tiếp tục mà không kiểm tra lại xem màn hình còn Captcha hay không.
  - *Làm rõ thuật ngữ:* Khái niệm “Đóng băng chuột” trong hệ thống thực chất là **tạm dừng luồng gửi sự kiện của bot (blocking loop pause)** và phát chuông báo động, chứ **không can thiệp khóa chuột phần cứng ở tầng driver hệ điều hành Windows**, nhằm để người dùng thật có thể tự do dùng chuột giải Captcha.
  - *Khắc phục đã thực hiện:* Sau khi người dùng nhấn Enter xác nhận đã giải xong, hệ thống kích hoạt hàm `recheck_screen_after_solve()` để chụp màn hình và phân tích lại. Nếu Captcha vẫn tồn tại, phiên làm việc sẽ lập tức bị hủy an toàn để bảo vệ tài khoản thay vì cố chấp thao tác.

### Câu hỏi 5: “Kết quả có tái lập được không?”
- **Câu trả lời trung thực & Hiện trạng khắc phục:**  
  - *Thiếu sót ban đầu:* Các lựa chọn ngẫu nhiên không có seed hoặc nhật ký kiểm thử đủ để tái tạo một phiên. Ngoài ra, AI Vision mặc định ở trạng thái tắt (`enabled: false`); một số đường xử lý dùng ảnh toàn màn hình kết hợp tọa độ cửa sổ client nên cần kiểm chứng trên môi trường màn hình cụ thể.
  - *Khắc phục đã thực hiện:* Đã bổ sung cấu hình `reproducibility.seed` trong `config.json` để hỗ trợ thiết lập seed ngẫu nhiên cố định khi chạy thử nghiệm hoặc gỡ lỗi, đồng thời chuẩn hóa hệ quy chiếu tọa độ `WindowHelper.to_screen_coords` từ khung Client Area của cửa sổ game.

---

## 3. Bảng Tổng Hợp Kiểm Định & Phạm Vi Trách Nhiệm

| Tiêu chí | Khẳng định thiết kế | Hiện trạng thực tế | Lưu ý vận hành |
| :--- | :--- | :--- | :--- |
| **Độ giống người** | Phỏng theo định luật Fitts & mô hình Log-Normal | Chỉ là mô phỏng heuristic, chưa có dữ liệu kiểm định trên người thật | Không dùng để tuyên bố "vô hình trước hệ thống phát hiện" |
| **Quyền riêng tư** | Tuyệt đối tuân thủ Zero-Telemetry | Không thu thập dữ liệu gõ phím/chuột của người dùng | Tham số dựa trên tài liệu nghiên cứu HCI công khai |
| **Độ bền khi chạy lâu** | Atomic JSON + Always Stop Profile | Đã bọc `try...finally` và ghi file an toàn nguyên tử | Cần đảm bảo GPM-Login app luôn chạy nền ổn định |
| **Thẩm định Captcha** | Recheck AI Vision sau khi người dùng giải | Yêu cầu người dùng thật can thiệp thủ công | Nếu AI tắt, cần người dùng gõ xác nhận 'y' |
