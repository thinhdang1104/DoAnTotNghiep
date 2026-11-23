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

Hệ thống tự động hóa quy trình kiểm soát phương tiện ra/vào bãi giữ xe trường học bằng **2 luồng Camera AI hoạt động song song hoặc độc lập**, kết hợp nhận diện biển số xe máy Việt Nam (**YOLOv8**) và xác thực sinh trắc học khuôn mặt người gửi (**FaceNet 512-D**). Hệ thống tự động đối chiếu biển số và khuôn mặt khi xe lấy ra khỏi bãi, cảnh báo tức thì trên thanh Top-up nếu phát hiện lệch khuôn mặt, hỗ trợ tra cứu đối chiếu sự cố mất xe (`Check-in · Check-out · Người lấy xe`), xuất báo cáo PDF chuẩn A4 và thống kê doanh thu tự động theo mức giá cố định (`2.000 VNĐ / lượt`).

### Tính năng nổi bật
- **Giám sát 2 Camera AI thời gian thực (`Cam 1` & `Cam 2` chéo luồng đối xứng)**:
  - **Chọn đúng thiết bị theo tên**: Bấm **"Tìm camera"** để trình duyệt liệt kê tên thiết bị thực tế (`MediaDeviceInfo.label` từ Webcam laptop, USB Camera, DroidCam...) vào dropdown **Thiết bị camera** của từng ô `Cam 1` và `Cam 2`, mở chính xác bằng `deviceId: { exact }`, khóa trùng thiết bị giữa 2 ô và hỗ trợ bật/tắt độc lập từng camera.
  - **Hiển thị & Tốc độ xử lý AI**: Luồng `<video>` xem trước hiển thị trực tiếp từ thiết bị trên trình duyệt kèm lớp phủ `<canvas>` vẽ Bounding Box; vòng gửi khung hình JPEG (`640px`) lên Backend AI xử lý được điều tiết định kỳ mỗi `140 ms` (tối đa $\approx 7.1$ lượt suy luận/giây, tự động bỏ qua nhịp nếu yêu cầu trước chưa hoàn tất để không gây nghẽn mạng).
- **Nhận diện Biển số xe Việt Nam 2 giai đoạn (YOLOv8)**:
  - Model 1 (`weights/plate_best.pt`): Phát hiện vùng biển số xe máy trong khung hình.
  - Model 2 (`weights/chars_best.pt`): Phân đoạn và đọc 31 lớp ký tự OCR (`0-9`, `A-Z`), gom dòng thông minh cho biển số xe máy 2 dòng và 1 dòng, hậu xử lý chuẩn định dạng Việt Nam (VD: `59V1-79379`, `30T4-1975`).
- **Xác thực Khuôn mặt Sinh trắc học (FaceNet 512-D)**:
  - Sử dụng **MTCNN** phát hiện khuôn mặt và **InceptionResnetV1 (`vggface2`)** trích xuất vector đặc trưng `512` chiều chuẩn hóa L2, kết hợp đo độ sắc nét Laplacian trên vùng lõi khuôn mặt (`inner 70%`, ngưỡng sàn `15.0`, ngưỡng chuẩn `22.0`).
  - Tự động tính độ tương đồng **Cosine Similarity** giữa khuôn mặt lúc gửi xe và lúc lấy xe (ngưỡng an toàn $\ge 0.65$). Nếu thấp hơn ngưỡng, hệ thống tự động kích hoạt **Cảnh báo lệch khuôn mặt** ngay tại ô Top-up trên thanh tiêu đề để bảo vệ chọn **Cho phép ra** hoặc **Từ chối**.
- **Cơ chế Chốt 2 Pha đối xứng (Symmetric Two-Phase Latch — `4.0 giây`) & Chỉ báo thành công sau khi MySQL commit**:
  - Bất kỳ camera nào (`Cam 1` hoặc `Cam 2`) đạt đồng thuận biển số trước ($\ge 3$ mẫu, tỷ lệ $\ge 70\%$ trong cửa sổ `3.0 giây`) thì **camera đối diện (`3 - plate_cam`)** bắt buộc xác thực khuôn mặt người lái trong vòng `4.0 giây`.
  - Hệ thống chỉ khóa cooldown và thông báo **VÀO / RA BÃI THÀNH CÔNG** sau khi bản ghi đã được commit thành công vào cơ sở dữ liệu **MySQL**.
- **Quản lý Lịch sử, Xử lý tình huống mất xe & Xuất báo cáo PDF**:
  - **Lịch sử & Quản lý**: Tìm kiếm theo biển số xe, lọc theo 4 trạng thái (*Tất cả / Đang gửi trong bãi / Lượt vào / Lượt ra*), phân trang trực quan và nút **Xuất PDF** báo cáo lịch sử.
  - **Xử lý tình huống mất xe**: Bấm **"Tra cứu mất xe"** (hoặc bấm vào ảnh cắt) trên bất kỳ dòng nào để hệ thống truy vấn trực tiếp MySQL theo `id` và `entry_record_id`, đối chiếu song song 3 khối thông tin: **(1) Check-in lúc gửi xe**, **(2) Check-out lúc lấy xe**, và **(3) Ảnh khuôn mặt Người lấy xe** kèm nút **Xuất PDF biên bản**.
  - **Quản lý Doanh thu**: Tự động tính phí **`2.000 VNĐ / lượt`** ở chiều vào (`IN`), thống kê theo **Hôm nay / Tháng này / Năm nay / Tổng tích lũy**, bảng chi tiết theo **Ngày / Tháng / Năm** kèm nút **Xuất PDF** báo cáo doanh thu.

---

## 2. Bộ dữ liệu, Quy trình Huấn luyện & Đánh giá Mô hình (`weights/*.pt`)

### 2.1. Quy mô Bộ dữ liệu & Phân chia Tập (`train / valid / test`)
Hai bộ dữ liệu huấn luyện theo chuẩn **YOLOv8 Roboflow format** được khai báo cấu hình tại [`datasets/plates/data.yaml`](datasets/plates/data.yaml) và [`datasets/chars/data.yaml`](datasets/chars/data.yaml) (các thư mục ảnh và nhãn `images/`, `labels/` được loại khỏi Git qua [`.gitignore`](.gitignore) để giữ kích thước repo gọn nhẹ):

| Bộ dữ liệu | Cấu hình | Số lớp (`nc`) | Train | Valid | Test | Tổng số ảnh | Kiểm tra rò rỉ dữ liệu (Data Leakage) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Biển số xe máy VN** | [`datasets/plates/data.yaml`](datasets/plates/data.yaml) | `1` (`plate`) | `704` | `200` | `101` | **`1.005` ảnh** | `0` ảnh trùng SHA-256 byte & `0` tên gốc trùng trước hậu tố `.rf.` giữa `train / valid / test` |
| **Ký tự biển số OCR** | [`datasets/chars/data.yaml`](datasets/chars/data.yaml) | `31` (`0-9`, `A-Z`) | `2.675` | `764` | `380` | **`3.819` ảnh** | `0` ảnh trùng SHA-256 byte & `0` tên gốc trùng trước hậu tố `.rf.` giữa `train / valid / test` |

*(Lưu ý: Kiểm tra trùng byte SHA-256 và tiền tố tên file `.rf.` đảm bảo không có file ảnh gốc bị chia trùng vào nhiều tập, nhưng chưa loại trừ hoàn toàn trường hợp hai khung hình gần giống nhau được chụp liên tiếp).*

### 2.2. Lệnh tái lập huấn luyện & Kết quả đánh giá Checkpoint (`weights/*.pt`)
Hai file trọng số trong thư mục [`weights/`](weights/) được huấn luyện từ mô hình gốc `yolov8n.pt` bằng hai script [`training/train_plates.py`](training/train_plates.py) và [`training/train_chars.py`](training/train_chars.py):

- **Huấn luyện mô hình phát hiện biển số (`weights/plate_best.pt`)**:
  ```bash
  python training/train_plates.py
  # Tham số khớp checkpoint: model=yolov8n.pt, imgsz=640, epochs=50, batch=16, patience=100, seed=0
  ```
- **Huấn luyện mô hình phân đoạn & đọc ký tự (`weights/chars_best.pt`)**:
  ```bash
  python training/train_chars.py
  # Tham số khớp checkpoint: model=yolov8n.pt, imgsz=640, epochs=80, batch=8, patience=20, seed=0
  ```

| Mô hình | File trọng số | Phạm vi đo lường của Metric | Cấu hình (`train_args`) | Precision (Box) | Recall (Box) | mAP@50 (Box) | mAP@50-95 (Box) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Phát hiện biển số** | [`weights/plate_best.pt`](weights/plate_best.pt) | Phát hiện khung Bounding Box biển số xe (`plate`) trong ảnh toàn cảnh | `imgsz=640`, `epochs=50`, `batch=16`, `patience=100` | `99.94%` | `100.0%` | `99.50%` | `80.49%` |
| **Nhận diện ký tự OCR** | [`weights/chars_best.pt`](weights/chars_best.pt) | Phát hiện & phân loại **từng ký tự đơn lẻ** (`character-level`) trong vùng ảnh cắt biển số | `imgsz=640`, `epochs=80`, `batch=8`, `patience=20` | `96.89%` | `93.95%` | `98.38%` | `74.56%` |

> **Chú thích quan trọng về ý nghĩa Metric khi báo cáo**:
> - Các chỉ số `Precision`, `Recall`, `mAP@50`, `mAP@50-95` ở bảng trên là **chỉ số phát hiện mức Bounding Box của từng mô hình trên tập Validation** (với `chars_best.pt` là độ chính xác phát hiện và phân loại **từng ký tự riêng lẻ**, chưa phải tỷ lệ đọc đúng trọn vẹn cả chuỗi biển số).
> - Ở mức vận hành toàn hệ thống bãi giữ xe (*end-to-end plate recognition*), để một biển số được chốt hợp lệ, toàn bộ các ký tự trên biển phải được đọc đúng, vượt qua bước kiểm tra quy tắc định dạng biển số Việt Nam và đạt đồng thuận đa số (`Majority Voting >= 3 mẫu, >= 70%`) kết hợp xác thực khuôn mặt FaceNet (`Cosine Similarity >= 65%`). Khi đánh giá thực nghiệm ngoài thực tế, cần ghi nhận thêm **tỷ lệ đọc đúng toàn bộ biển số (end-to-end accuracy)**, **thời gian trung bình chốt 1 lượt xe** và **tỷ lệ lượt phải quét lại**.

---

## 3. Kiến trúc thư mục

```text
├── main.py                  # FastAPI Backend, luồng xử lý 2 Camera AI, Two-Phase Latch & REST API
├── face_service.py          # Module AI Khuôn mặt (MTCNN + InceptionResnetV1 512-D & Cosine Similarity)
├── database.py              # Tầng lưu trữ & truy vấn MySQL (Lịch sử, Đối chiếu phiên mất xe, Doanh thu)
├── app.py                   # Entrypoint tích hợp Gradio + FastAPI cho Hugging Face Spaces (ZeroGPU)
├── deploy_hf.py             # Script đẩy mã nguồn & trọng số lên Hugging Face Space (nhập token ẩn qua getpass)
├── datasets/
│   ├── plates/data.yaml     # Cấu hình tập dữ liệu phát hiện biển số (1 class: plate, 704/200/101 ảnh)
│   └── chars/data.yaml      # Cấu hình tập dữ liệu phân đoạn ký tự OCR (31 classes, 2675/764/380 ảnh)
├── training/
│   ├── train_plates.py      # Script huấn luyện YOLOv8 phát hiện biển số (epochs=50, batch=16, patience=100)
│   └── train_chars.py       # Script huấn luyện YOLOv8 nhận diện ký tự OCR (epochs=80, batch=8, patience=20)
├── weights/
│   ├── plate_best.pt        # Trọng số YOLOv8 phát hiện biển số xe (mAP@50 = 99.50%)
│   └── chars_best.pt        # Trọng số YOLOv8 nhận diện ký tự OCR (mAP@50 = 98.38%)
├── frontend/
│   ├── index.html           # Giao diện Web (2 Camera nhận diện, Lịch sử & Quản lý, Quản lý doanh thu)
│   ├── styles.css           # Thiết kế giao diện Dark Mode
│   └── app.js               # Chọn thiết bị WebRTC theo tên, Top-up thông báo, Tra cứu mất xe & Xuất PDF
├── requirements.txt         # Danh sách thư viện Python kèm dải phiên bản đã kiểm chứng
└── .env.example             # Mẫu cấu hình biến môi trường kết nối MySQL
```

---

## 4. Hướng dẫn cài đặt và chạy trên máy cục bộ (Local)

### Bước 1: Cài đặt thư viện
Yêu cầu **Python 3.10+** và dịch vụ **MySQL** đang hoạt động (Local MySQL hoặc Aiven Cloud MySQL). Mở terminal tại thư mục dự án và chạy:

```bash
pip install -r requirements.txt
pip install --no-deps facenet-pytorch==2.6.0
```
*(Lưu ý: `facenet-pytorch==2.6.0` ghim metadata `torch<2.3` cũ trên PyPI dù tương thích hoàn toàn với PyTorch 2.x mới, nên cần cài với cờ `--no-deps` để giữ nguyên bộ thư viện đã kiểm chứng trong [`requirements.txt`](requirements.txt)).*

### Bước 2: Cấu hình Cơ sở dữ liệu MySQL (Bắt buộc)
1. Sao chép file [`.env.example`](.env.example) thành `.env`:
   ```bash
   cp .env.example .env
   ```
2. Cập nhật thông tin kết nối MySQL thực tế trong `.env`:
   ```env
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=defaultdb
   ```
   *(Hệ thống sử dụng thuần **MySQL** và sẽ tự động khởi tạo bảng `plate_recognition_history` khi kết nối thành công. Nếu MySQL chưa kết nối được, hệ thống sẽ báo lỗi kết nối CSDL và tạm hoãn xác thực xe vào/ra để đảm bảo toàn vẹn dữ liệu).*

### Bước 3: Khởi chạy ứng dụng
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
Mở trình duyệt truy cập: **`http://127.0.0.1:8000`**, bấm **"Tìm camera"**, cấp quyền truy cập camera trên trình duyệt và chọn thiết bị từ dropdown cho **Cam 1** và **Cam 2**.

### Bước 4: Đẩy bản cập nhật lên Hugging Face Space (Tùy chọn)
Khi cần cập nhật mã nguồn và trọng số lên Hugging Face Space (`MinhThinh/DoAn`), cài thêm `huggingface_hub` và chạy [`deploy_hf.py`](deploy_hf.py):
```bash
pip install huggingface_hub
python deploy_hf.py
```

---

## 5. Công nghệ sử dụng

- **Artificial Intelligence / Computer Vision**: Ultralytics YOLOv8, PyTorch, Facenet-PyTorch (MTCNN + InceptionResnetV1 512-D), OpenCV.
- **Backend**: Python, FastAPI, Uvicorn, Pydantic.
- **Database**: MySQL (`mysql-connector-python`, Aiven Cloud MySQL / Local MySQL).
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (WebRTC `enumerateDevices` / `getUserMedia` exact `deviceId`, HTML5 Canvas Overlay, Printable A4 PDF Report).
- **Cloud Deployment**: Hugging Face Spaces (Gradio ASGI Mount).
