# Hệ thống Quản lý Bãi giữ xe Trường học với AI Nhận diện Khuôn mặt & Biển số xe

## Mô tả dự án
Đồ án tốt nghiệp xây dựng hệ thống quản lý bãi giữ xe tại trường học kết hợp xác thực kép từ luồng Camera thời gian thực:
- **Nhận diện biển số & ký tự OCR:** YOLOv8 2 tầng (`weights/plate_best.pt` phát hiện vùng biển số, `weights/chars_best.pt` đọc ký tự), kết hợp chuẩn hóa định dạng biển số Việt Nam và bỏ phiếu đồng thuận trong cửa sổ 3,0 giây (tối thiểu 3 mẫu, đồng thuận ≥ 70%).
- **Phát hiện & đối chiếu khuôn mặt:** `facenet-pytorch` (`MTCNN` phát hiện khuôn mặt + `InceptionResnetV1(pretrained="vggface2")` trích xuất vector đặc trưng 512 chiều chuẩn hóa L2), lưu vào MySQL (`face_embedding BLOB`) và tự động đối chiếu Cosine Similarity (ngưỡng ≥ 45%) với lần ghi nhận gần nhất của cùng biển số xe.

Hệ thống sử dụng **FastAPI Backend + Web Frontend** gồm 2 màn hình:
1. **Camera nhận diện:** Khung hình camera tỷ lệ `4:3` thời gian thực (MJPEG), điều khiển cổng thiết bị, hiển thị biển số & khuôn mặt đang đọc cùng danh sách 5 lượt vừa qua.
2. **Lịch sử & quản lý:** Thống kê tổng lượt lưu trữ, số lượt hôm nay, tỷ lệ có khuôn mặt, đồng bộ hàng đợi bản ghi lưu tạm (`data/pending_records.json`) và tìm kiếm / lọc sổ nhật ký trên MySQL.

---

## Cấu trúc dự án

```text
BienSoXe/
├── main.py                  # FastAPI server, luồng đọc camera (FrameGrabber), AI & hàng đợi ghi DB
├── face_service.py          # Phát hiện khuôn mặt (MTCNN), trích xuất vector 512 chiều & Cosine Similarity
├── database.py              # Kết nối MySQL, tự động tạo/migrate bảng và truy vấn thống kê/lịch sử
├── frontend/
│   ├── index.html           # Giao diện Web (Camera nhận diện & Lịch sử quản lý)
│   ├── styles.css           # Giao diện tối đồng nhất (True Dark / Cinema)
│   └── app.js               # Điều khiển Camera, cập nhật trạng thái và tìm kiếm lịch sử
├── requirements.txt         # Danh sách thư viện Python
├── .env.example             # Mẫu cấu hình kết nối MySQL
├── weights/
│   ├── plate_best.pt        # Trọng số YOLOv8 phát hiện biển số
│   └── chars_best.pt        # Trọng số YOLOv8 nhận diện ký tự
└── training/
    ├── train_plates.py      # Script huấn luyện model phát hiện biển số
    └── train_chars.py       # Script huấn luyện model nhận diện ký tự
```

---

## Hướng dẫn cài đặt & chạy dự án

### Bước 1: Cài đặt thư viện
Do `facenet-pytorch==2.6.0` giới hạn phiên bản `torch<2.3` trong metadata, hãy cài các thư viện chính trước rồi cài `facenet-pytorch` với cờ `--no-deps`:
```powershell
C:\Python314\python.exe -m pip install -r requirements.txt
C:\Python314\python.exe -m pip install --no-deps facenet-pytorch==2.6.0
```

### Bước 2: Cấu hình cơ sở dữ liệu MySQL
1. Tạo database trống tên `bien_so_xe` trong MySQL / XAMPP:
   ```sql
   CREATE DATABASE IF NOT EXISTS bien_so_xe CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Sao chép `.env.example` thành `.env` và điền thông tin kết nối MySQL (nếu dùng XAMPP mặc định không mật khẩu, để `MYSQL_PASSWORD=`):
   ```powershell
   Copy-Item .env.example .env
   ```
   Bảng `plate_recognition_history` và các cột/index sẽ được tạo tự động khi khởi động server.

### Bước 3: Chạy ứng dụng
```powershell
C:\Python314\python.exe main.py
```
Mở trình duyệt tại: **http://127.0.0.1:8000**
