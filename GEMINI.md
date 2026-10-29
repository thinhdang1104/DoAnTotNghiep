# Ngữ cảnh Dự án: BienSoXe (Đồ án tốt nghiệp)

## Thông tin chung
- **Loại dự án:** Đồ án tốt nghiệp của người dùng.
- **Tên đề tài:** Xây dựng hệ thống quản lý bãi giữ xe cho trường học với AI nhận diện khuôn mặt và biển số xe.

## Định hướng & Kiến trúc hệ thống
- **Mục tiêu cốt lõi:** Quản lý hoạt động gửi/lấy xe tại trường học (sinh viên, giảng viên, khách), kết hợp xác thực kép bằng **AI nhận diện biển số xe** và **AI nhận diện khuôn mặt**.
- **Stack công nghệ hiện tại:**
  - **Nhận diện biển số & ký tự:** YOLOv8 (`ultralytics`), OpenCV (`weights/plate_best.pt`, `weights/chars_best.pt`), chuẩn hóa định dạng biển số Việt Nam và bỏ phiếu đồng thuận trong cửa sổ 3,0 giây.
  - **Nhận diện & đối chiếu khuôn mặt:** FaceNet (`facenet-pytorch`: `MTCNN` + `InceptionResnetV1(pretrained="vggface2")` trong `face_service.py`, trích xuất vector đặc trưng 512 chiều lưu vào cột `face_embedding BLOB` và đối chiếu Cosine Similarity ≥ 45% với lần ghi nhận gần nhất của cùng biển số).
  - **Backend & Giao diện ứng dụng:** FastAPI + Uvicorn (`main.py`) phục vụ giao diện Web tối đồng nhất (`frontend/index.html`, `frontend/styles.css`, `frontend/app.js`) tách biệt thành 2 màn hình: **Camera nhận diện** và **Lịch sử & quản lý**.
  - **Cơ sở dữ liệu:** MySQL (`database.py`, database `bien_so_xe`, bảng `plate_recognition_history`), kèm cơ chế lưu tạm ra `data/pending_records.json` khi mất kết nối MySQL và tự động đồng bộ lại.
  - **Môi trường Python:** `C:\Python314\python.exe`.
