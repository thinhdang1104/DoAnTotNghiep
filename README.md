# Hệ thống Kiểm soát Bãi giữ xe Trường học (YOLOv8 + FaceNet)

## Mô tả dự án
Đồ án tốt nghiệp xây dựng hệ thống quản lý bãi giữ xe trường học sử dụng AI nhận diện đồng thời **biển số xe** và **khuôn mặt** trực tiếp từ luồng Camera thời gian thực:
- **Mô hình phát hiện biển số & ký tự OCR:** YOLOv8 (`weights/plate_best.pt`, `weights/chars_best.pt`)
- **Mô hình phát hiện & trích xuất đặc trưng khuôn mặt:** FaceNet (`facenet-pytorch`: `MTCNN` + `InceptionResnetV1(pretrained="vggface2")`)

Hệ thống sử dụng kiến trúc **FastAPI Backend + Web Frontend** chia tách rõ ràng thành 2 phân hệ:
1. **01 / TRẠM CAMERA NHẬN DIỆN:** Luồng quang học trực tiếp (MJPEG), điều khiển cổng thiết bị camera, bảng hiển thị biển số vật lý, chỉ số FaceNet và bộ bỏ phiếu đồng thuận 3.0 giây.
2. **02 / NHẬT KÝ & QUẢN TRỊ DỮ LIỆU:** Thống kê tổng quan, quản lý kết nối MySQL, đồng bộ hàng đợi bản ghi lưu tạm và tra cứu/lọc sổ nhật ký nhận diện.

---

## Cấu trúc dự án

```
BienSoXe/
├── main.py                  # FastAPI server + luồng xử lý Camera AI
├── face_service.py          # Module nhận diện & trích xuất vector khuôn mặt (FaceNet)
├── database.py              # Module kết nối và lưu lịch sử MySQL
├── frontend/
│   ├── index.html           # Giao diện Trạm kiểm soát & Quản trị nhật ký
│   ├── styles.css           # Thiết kế Industrial Control Terminal / Swiss Grid
│   └── app.js               # Logic điều khiển Camera, Telemetry và Quản trị
├── requirements.txt         # Thư viện cần cài đặt
├── .env.example             # Mẫu cấu hình kết nối MySQL
├── weights/
│   ├── plate_best.pt        # Model detect biển số
│   └── chars_best.pt        # Model nhận diện ký tự
└── training/
    ├── train_plates.py      # Script train model biển số
    └── train_chars.py       # Script train model ký tự
```

## Hướng dẫn chạy project

**Bước 1:** Cài đặt thư viện
```powershell
C:\Python314\python.exe -m pip install -r requirements.txt
```

**Bước 2:** Chạy ứng dụng Web
```powershell
C:\Python314\python.exe main.py
```

Sau khi khởi chạy, mở trình duyệt tại địa chỉ: **http://127.0.0.1:8000**
