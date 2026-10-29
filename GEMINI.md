# Ngữ cảnh Dự án: BienSoXe (Đồ án tốt nghiệp)

## Thông tin chung
- **Loại dự án:** Đồ án tốt nghiệp của người dùng.
- **Tên đề tài:** Xây dựng hệ thống quản lý bãi giữ xe cho trường học với AI nhận diện khuôn mặt và biển số xe.

## Định hướng & Kiến trúc hệ thống
- **Mục tiêu cốt lõi:** Quản lý hoạt động gửi/lấy xe tại trường học (sinh viên, giảng viên, khách), kết hợp xác thực kép bằng **AI nhận diện biển số xe** và **AI nhận diện khuôn mặt**.
- **Stack công nghệ hiện tại:**
  - **Nhận diện biển số & ký tự:** YOLOv8 (`ultralytics`), OpenCV (`weights/plate_best.pt`, `weights/chars_best.pt`).
  - **Nhận diện & đối chiếu khuôn mặt:** FaceNet (`facenet-pytorch`: `MTCNN` + `InceptionResnetV1(pretrained="vggface2")` trong `face_service.py`, trích xuất vector đặc trưng 512 chiều và đối chiếu Cosine Similarity ≥ 45%).
  - **Backend & Giao diện ứng dụng:** FastAPI + Uvicorn (`main.py`) phục vụ giao diện Web điều khiển chuẩn công nghiệp (`frontend/index.html`, `frontend/styles.css`, `frontend/app.js`) tách biệt thành 2 phân hệ: **01 / Trạm Camera Nhận diện** và **02 / Nhật ký & Quản trị dữ liệu**.
  - **Cơ sở dữ liệu:** MySQL (`database.py`, database `bien_so_xe`, bảng `plate_recognition_history`).
  - **Môi trường Python:** `C:\Python314\python.exe`.
