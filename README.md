---
title: He Thong Quan Ly Bai Giu Xe AI 2 Camera
emoji: 🛵
colorFrom: yellow
colorTo: gray
sdk: gradio
app_file: app.py
app_port: 7860
pinned: false
---

# Hệ thống Quản lý Bãi giữ xe Trường học với AI Nhận diện Khuôn mặt và Biển số xe

> **Đồ án Tốt nghiệp**: Xây dựng hệ thống quản lý bãi giữ xe cho trường học với AI nhận diện khuôn mặt và biển số xe.
> - **Demo trực tuyến (Hugging Face Spaces)**: [https://minhthinh-doan.hf.space](https://minhthinh-doan.hf.space)

---

## 1. Giới thiệu tổng quan

Hệ thống tự động hóa quy trình kiểm soát phương tiện ra/vào bãi giữ xe trường học bằng **2 luồng Camera AI hoạt động song song hoặc độc lập**, kết hợp nhận diện biển số xe máy Việt Nam (**YOLOv8**) và xác thực sinh trắc học khuôn mặt người gửi (**FaceNet 512-D**). Hệ thống tự động đối chiếu biển số và khuôn mặt khi xe lấy ra khỏi bãi, cảnh báo tức thì nếu phát hiện bất thường và thống kê doanh thu tự động theo mức giá cố định (`2.000 VNĐ / lượt`).

### Tính năng nổi bật
- **Giám sát 2 Camera AI thời gian thực (`Cam 1` Phía trong & `Cam 2` Phía ngoài)**:
  - Hỗ trợ bật/tắt và chọn cổng độc lập cho từng camera (hoặc bật 1 camera, tắt 1 camera).
  - Hiển thị luồng `<video>` trực tiếp 60 FPS kết hợp lớp phủ `<canvas>` vẽ khung Bounding Box thời gian thực không giật lag.
- **Nhận diện Biển số xe Việt Nam 2 giai đoạn (YOLOv8)**:
  - Model 1 (`weights/plate_best.pt`): Phát hiện vùng biển số xe máy trong khung hình.
  - Model 2 (`weights/chars_best.pt`): Phân đoạn và đọc ký tự OCR, hỗ trợ thuật toán gom dòng thông minh cho biển số xe máy 2 dòng và 1 dòng, tự động hậu xử lý định dạng chuẩn Việt Nam (VD: `59A1-12345`, `79N2-59633`).
- **Xác thực Khuôn mặt Sinh trắc học (FaceNet 512-D)**:
  - Sử dụng **MTCNN** phát hiện khuôn mặt lớn nhất trong khung hình và **InceptionResnetV1 (`vggface2`)** trích xuất vector đặc trưng `512` chiều chuẩn hóa L2.
  - Tự động tính độ tương đồng **Cosine Similarity** giữa khuôn mặt lúc gửi xe và lúc lấy xe (ngưỡng an toàn $\ge 0.65$). Nếu thấp hơn ngưỡng, hệ thống tự động kích hoạt **Cảnh báo An ninh** trên giao diện.
- **Cơ chế Chốt 2 Pha (Two-Phase Latch)**:
  - Tự động xác định chiều di chuyển (**Xe VÀO** hoặc **Xe RA**) dựa trên vị trí xuất hiện của khuôn mặt và biển số trên `Cam 1` và `Cam 2`:
    - **Chiều VÀO**: `Cam 1` (Phía trong) chụp Khuôn mặt + `Cam 2` (Phía ngoài) đọc Biển số.
    - **Chiều RA**: `Cam 1` (Phía trong) đọc Biển số + `Cam 2` (Phía ngoài) chụp Khuôn mặt đối chiếu.
  - Bỏ phiếu đa số (*Majority Voting*) trong cửa sổ trượt để chống nhiễu OCR trước khi chốt vào cơ sở dữ liệu.
- **Quản lý Lịch sử & Báo cáo Doanh thu**:
  - Tự động tính phí **`2.000 VNĐ / lượt`** ngay khi xe hoàn tất lượt vào.
  - Tra cứu theo biển số, lọc theo trạng thái (*Trong bãi / Đã trả*), lọc theo khoảng ngày, phân trang trực quan và thống kê doanh thu theo **Hôm nay / Tháng này / Năm nay / Toàn thời gian**.

---

## 2. Kiến trúc thư mục

```text
├── main.py                  # FastAPI Backend, luồng xử lý 2 Camera AI, Two-Phase Latch & REST API
├── face_service.py          # Module AI Khuôn mặt (MTCNN + InceptionResnetV1 512-D & Cosine Similarity)
├── database.py              # Tầng lưu trữ dữ liệu (Hỗ trợ MySQL Local & SQLite Cloud Fallback)
├── app.py                   # Entrypoint tích hợp Gradio + FastAPI cho Hugging Face Spaces (ZeroGPU)
├── training/
│   ├── train_plates.py      # Script huấn luyện mô hình YOLOv8 phát hiện biển số
│   └── train_chars.py       # Script huấn luyện mô hình YOLOv8 phân đoạn & đọc ký tự OCR
├── weights/
│   ├── plate_best.pt        # Trọng số YOLOv8 phát hiện biển số xe
│   └── chars_best.pt        # Trọng số YOLOv8 phân đoạn & nhận diện ký tự OCR
├── frontend/
│   ├── index.html           # Giao diện Web quản trị (Bàn điều khiển 2 Camera & Sổ cái lịch sử)
│   ├── styles.css           # Thiết kế giao diện Dark Mode Industrial
│   └── app.js               # Logic điều khiển Camera độc lập, Canvas Overlay 60 FPS & Quản lý dữ liệu
├── requirements.txt         # Danh sách thư viện Python
└── .env.example             # Mẫu cấu hình biến môi trường kết nối MySQL
```

---

## 3. Hướng dẫn cài đặt và chạy trên máy cục bộ (Local)

### Bước 1: Cài đặt thư viện
Yêu cầu **Python 3.10+**. Mở terminal tại thư mục dự án và chạy:

```bash
pip install -r requirements.txt
```

### Bước 2: Cấu hình Cơ sở dữ liệu (MySQL hoặc SQLite tự động)
1. Sao chép file `.env.example` thành `.env`:
   ```bash
   cp .env.example .env
   ```
2. Cập nhật thông tin kết nối MySQL trong `.env`:
   ```env
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=license_plate_db
   ```
   *(Lưu ý: Hệ thống sẽ tự động tạo bảng `plate_recognition_history` khi khởi động. Nếu chưa bật MySQL, hệ thống có cơ chế lưu tạm thông minh hoặc chuyển sang SQLite dự phòng).*

### Bước 3: Khởi chạy ứng dụng
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
Mở trình duyệt truy cập: **`http://localhost:8000`**

---

## 4. Công nghệ sử dụng

- **Artificial Intelligence / Computer Vision**: Ultralytics YOLOv8, PyTorch, Facenet-PyTorch (MTCNN + InceptionResnetV1), OpenCV.
- **Backend**: Python, FastAPI, Uvicorn, Pydantic.
- **Database**: MySQL (`mysql-connector-python`) & SQLite3 (Cloud Mode).
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (WebRTC `getUserMedia`, HTML5 Canvas Overlay).
- **Cloud Deployment**: Hugging Face Spaces (Gradio ASGI Mount).
