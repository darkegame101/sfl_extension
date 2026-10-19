# PHÂN TÍCH GIAO DIỆN NÔNG TRẠI (FARM UI) & CÁC HOẠT ĐỘNG CƠ BẢN CỦA NÔNG DÂN

> **Nguồn phân tích:** Ảnh chụp thực tế giao diện Sunflower Land tài khoản người chơi (Cập nhật: 2026-10-14).
> **Mã nguồn gốc:** https://github.com/sunflower-land/sunflower-land

---

## 1. BẢN ĐỒ GIAO DIỆN (UI MAP & HEADS-UP DISPLAY)

```
[Top-Left HUD]                                                    [Top-Right HUD]
Avatar Bumpkin | Clock | Compass | Calendar | Flower Point      Coins: 32639 | Block Bucks: 120 | Flowers: 46.7
                                                                Craft Tool | Backpack | Tool Bar | Seed Counter (283)
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
[VÙNG 1: RỪNG CÂY TRÊN CÙNG]
- 9 Cây lấy gỗ / Cây ăn quả lớn (Có đếm ngược thời gian hồi phục 4h, 9h)
- Vị trí mở rộng đất [Expand] ở bờ biển phía Đông Bắc

[VÙNG 2: RUỘNG ĐẤT TRỒNG TRỌT TRUNG TÂM]
- Nhà chính (Farmhouse) + 3 Thùng ủ phân (Composter)
- 3 Nhà kính / Luống dài (Greenhouse)
- 2 Bù nhìn rơm (Scarecrow) tăng năng suất
- Mạng lưới ~50+ ô đất trồng cây (Plots) với thời gian sinh trưởng (6h, 10h, 4h...)
- Khu vực mỏ đá / sỏi / quặng tròn bên phải

[VÙNG 3: KHU BẾP NẤU & KHÁCH HÀNG NPC TẠI FARM]
- Bếp lửa (Fire Pit) + Quầy bánh (Bakery) + Giếng nước (Water Well)
- Các NPC khách hàng đứng đợi món ăn (Pizza, bánh, đồ ăn) ngay tại sân

[VÙNG 4: NGOẠI VI & CẦU TÀU ĐI DU HÀNH]
- Đảo phụ Goblin (Khu vực Upgrade) bên phải biển
- Cầu tàu gỗ (Docks) ở mép dưới để lên thuyền sang Plaza / Beach / Kingdom
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
[Bottom-Left HUD]                                                 [Bottom-Right HUD]
Chat (50) | P2P Trade | Settings                                  Hourglass (Timer) | Global Settings (Bánh răng)
```

---

## 2. NĂM HOẠT ĐỘNG CƠ BẢN CỦA MỘT NÔNG DÂN (FARMER WORKFLOWS)

### Hoạt động 1: Quản lý Ruộng & Thu hoạch (Crop Management)
1. **Kiểm tra ô đất:**
   - Ô có thời gian về 0 hoặc hiển thị quả/củ chín $\rightarrow$ **Click thu hoạch (Harvest)**.
   - Ô đất trống (màu nâu đất) $\rightarrow$ Mở giỏ hạt (Seed Counter) $\rightarrow$ Chọn hạt $\rightarrow$ **Gieo hạt (Plant)**.
2. **Kích hoạt Bù nhìn & Giếng nước:**
   - Đảm bảo các ô đất nằm trong tầm bảo vệ của Bù nhìn rơm (Scarecrow).
   - Kiểm tra giếng nước (Water Well) để duy trì nguồn nước tưới.

### Hoạt động 2: Ủ phân & Bón đất (Composting)
- Bỏ rác hữu cơ / sâu bọ / nông sản phụ vào 3 **Thùng ủ phân (Composter)** cạnh nhà chính.
- Thu về phân bón (Sprout Mix, Fruitful Blend) để bón lót trước khi gieo các loại cây giá trị cao.

### Hoạt động 3: Nấu ăn & Phục vụ Khách NPC tại Chỗ (Cooking & Serving)
- **Nấu nướng:** Bấm vào Bếp lửa (Fire Pit) hoặc Tiệm bánh (Bakery) để nấu các món ăn (Pizza, Bánh, Nước ép).
- **Phục vụ:** Các NPC xuất hiện xung quanh bàn ăn tại farm (như anh chàng ăn pizza ở ảnh chụp). Click vào NPC $\rightarrow$ Bấm nút trao món ăn để nhận điểm kinh nghiệm (Exp) nâng cấp Bumpkin và nhận Coins.

### Hoạt động 4: Khai thác Rừng & Mỏ đá (Resource Gathering)
- Hàng 9 cây gỗ phía trên sau khi hồi thời gian (hết 4h - 9h): Dùng Rìu (Axe) click chặt gỗ.
- Các mỏ đá / quặng phía dưới ruộng: Dùng Cuốc (Pickaxe) để khai thác đá và khoáng sản.

### Hoạt động 5: Du hành qua Cầu tàu & Giao đơn Codex (World Travel Deliveries)
- Khi trong rương đã tích đủ nông sản:
  - Bấm vào icon **La bàn (Compass)** ở góc trên bên trái, hoặc đi xuống **Cầu tàu gỗ (Dock)** ở mép dưới.
  - Chọn chuyển map sang **Plaza / Beach / Kingdom**.
  - Đến gặp các NPC lớn (Betty, Blacksmith, Tango, Corale...) giao các đơn hàng lớn để nhận **Tickets, Flowers, Gem**.

---

## 3. BỔ SUNG CHI TIẾT TỪ MÃ NGUỒN SUNFLOWER LAND (GITHUB REPO)

Dựa trên cấu trúc sự kiện XState (`src/features/game/events/`) trong mã nguồn chính thức:

### 1. Cơ chế Nhặt Nấm (`harvestMushroom.ts`):
* **Cách sinh (Spawn logic):** Nấm tự động mọc ngẫu nhiên trên các ô cỏ trống (Wilderness / Grass) sau mỗi 4 – 16 giờ hoặc khi có hiệu ứng thời tiết mưa.
* **Các loại nấm:**
  - *Wild Mushroom (Nấm nâu/đỏ):* Dùng làm nguyên liệu nấu ăn, ủ phân, và nhiệm vụ.
  - *Magic Mushroom (Nấm tím hiếm):* Giá trị cao dùng cho chế tạo đồ ma thuật.
* **Thao tác tool:** Chỉ cần di chuột click thẳng vào icon cây nấm trên cỏ $\rightarrow$ Nhận nông sản vào rương ngay lập tức.

### 2. Ba thùng ủ phân Composter (`compost.ts`):
* 3 chiếc thùng vàng cạnh nhà chính trong ảnh chụp tương ứng với 3 cấp độ:
  - **Basic Composter:** Sản xuất *Sprout Mix* (Ủ từ lúa/nông sản thường).
  - **Advanced Composter:** Sản xuất *Fruitful Blend* (Ủ từ quả và nấm).
  - **Expert Composter:** Sản xuất *Rapid Root* (Tăng 50% tốc độ lớn của cây).
* **Thao tác:** Bấm vào thùng $\rightarrow$ Bấm Start $\rightarrow$ Khi đếm ngược xong bấm thu hoạch phân bón.

### 3. Nhà kính Greenhouse (`plantGreenhouseCrop.ts` & `harvestGreenhouse.ts`):
* 3 luống nhà kính dài hiển thị `1d`, `2d` trong ảnh là cây trồng cao cấp (Olive, Rice, Grape).
* Đòi hỏi nhiên liệu Dầu (Oil) và Nước.

### 4. Bếp nấu & Nâng cấp Bumpkin (`cook.ts` & `feedBumpkin.ts`):
* Nấu ăn tại Bếp lửa (Fire Pit) hoặc Tiệm bánh (Bakery) mất từ vài phút đến vài giờ.
* Nấu xong $\rightarrow$ Cho Bumpkin ăn để tích lũy EXP lên cấp. Cấp càng cao càng mở khóa nhiều ô đất và kỹ năng mới.

### 5. Cơ chế Đồng bộ máy chủ (Syncing & Autosave):
* Sau mỗi chuỗi thao tác, game tự kích hoạt autosave.
* Khi mạng chậm hoặc server lag, màn hình sẽ hiện vòng xoay **"Syncing to blockchain / server..."**. Tool bắt buộc phải nhận diện biểu tượng xoay này để tạm dừng thao tác, chờ game sync xong mới click tiếp.

---

## 4. THỨ TỰ ƯU TIÊN PHÁT TRIỂN TOOL (ĐÃ HOÀN THIỆN)

* **ƯU TIÊN 1 (Cốt lõi hàng ngày): Thu hoạch & Gieo hạt theo luồng an toàn**:
  - Nhận diện các ô ruộng chín $\rightarrow$ Click thu hoạch (có nhịp thở 400-800ms).
  - Ô đất trống $\rightarrow$ Mở giỏ hạt $\rightarrow$ Click gieo hạt.
* **ƯU TIÊN 2: Tự động nhặt Nấm (Wild Mushrooms)**:
  - Quét các cụm cỏ trên đảo chính $\rightarrow$ Click nhặt ngay khi thấy nấm mọc.
* **ƯU TIÊN 3: Nhận diện vòng xoay Syncing & Lá chắn Captcha**:
  - Nếu thấy vòng xoay "Syncing": Tạm dừng chờ đồng bộ.
  - Nếu thấy Modal Captcha / Verify: Đóng băng chuột ngay lập tức và phát cảnh báo.
* **ƯU TIÊN 4: Nấu nướng & Phục vụ NPC tại Farm**:
  - Bấm Bếp lửa / Tiệm bánh nấu ăn và phục vụ khách đứng quanh bàn ăn trên farm.
* **ƯU TIÊN 5: Chặt cây & Đập đá khi hết thời gian hồi phục**:
  - Hàng 9 cây phía trên và các mỏ đá.
* ❌ **Bỏ hoàn toàn việc chuyển đảo giao đơn Codex**: Bạn tự làm thủ công bằng tay.


