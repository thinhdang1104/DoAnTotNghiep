# Ngữ cảnh Dự án: BienSoXe (Đồ án tốt nghiệp)

## Thông tin chung
- **Loại dự án:** Đồ án tốt nghiệp của người dùng.
- **Tên đề tài:** Xây dựng hệ thống quản lý bãi giữ xe cho trường học với AI nhận diện khuôn mặt và biển số xe.

## Định hướng & Kiến trúc hệ thống hiện tại
- **Mục tiêu cốt lõi:** Quản lý hoạt động gửi/lấy xe tại trường học (sinh viên, giảng viên, khách), kết hợp xác thực kép bằng **AI nhận diện biển số xe** và **AI nhận diện khuôn mặt**.
- **Stack công nghệ hiện tại:**
  - **Nhận diện biển số & ký tự:** YOLOv8 (`ultralytics`), OpenCV (`weights/plate_best.pt`, `weights/chars_best.pt`), chuẩn hóa định dạng biển số Việt Nam và bỏ phiếu đồng thuận trong cửa sổ 3,0 giây.
  - **Nhận diện & đối chiếu khuôn mặt:** FaceNet (`facenet-pytorch`: `MTCNN` + `InceptionResnetV1(pretrained="vggface2")` trong `face_service.py`, trích xuất vector đặc trưng 512 chiều lưu vào cột `face_embedding BLOB` và đối chiếu Cosine Similarity ≥ 45% với lần ghi nhận gần nhất của cùng biển số).
  - **Backend & Giao diện ứng dụng:** FastAPI + Uvicorn (`main.py`) phục vụ giao diện Web tối đồng nhất (`frontend/index.html`, `frontend/styles.css`, `frontend/app.js`) tách biệt thành 2 màn hình: **Camera nhận diện** và **Lịch sử & quản lý**.
  - **Cơ sở dữ liệu:** MySQL (`database.py`, database `bien_so_xe`, bảng `plate_recognition_history`), kèm cơ chế lưu tạm ra `data/pending_records.json` khi mất kết nối MySQL và tự động đồng bộ lại.
  - **Môi trường Python:** `C:\Python314\python.exe`.

## Thiết kế Thuật toán Phân luồng Vào/Ra & Cơ chế "Lưu hờ" (Ý tưởng của Tác giả)
1. **Bố trí 2 Camera đối xứng trên cùng 1 làn cổng (Cam 1 & Cam 2):**
   - Tận dụng đặc thù xe máy tại Việt Nam (biển số gắn ở đuôi xe, khuôn mặt người lái ở phía trước) và **khoảng nghỉ tự nhiên** khi xe dừng tại vạch kiểm soát cổng:
     - **Chiều ĐI VÀO (Check-in):** **Cam 1** (phía trước mặt người lái) thu nhận **Khuôn mặt** + **Cam 2** (phía sau đuôi xe) thu nhận **Biển số xe**.
     - **Chiều ĐI RA (Check-out):** **Cam 2** thu nhận **Khuôn mặt** + **Cam 1** thu nhận **Biển số xe** (ngược lại với chiều đi vào).
   - Hệ thống tự động suy luận luồng **Vào / Ra** dựa trên việc cặp `(Khuôn mặt, Biển số)` xuất hiện ở camera nào.

2. **Cơ chế "Lưu hờ — Đợi đủ cặp chuẩn mới ghi MySQL" (Two-Phase Latch / Staged Commit):**
   - Khi đọc và bỏ phiếu đồng thuận xong **Biển số xe**, hệ thống **chưa ghi ngay vào MySQL** mà đưa vào trạng thái **"Lưu hờ (Pending Pair)"**.
   - Trong khoảng nghỉ khi xe đang dừng tại vạch, hệ thống theo dõi camera đối diện để bắt **Khuôn mặt chuẩn nhất** (độ tin cậy cao, diện tích mặt lớn, lấy khung hình sắc nét nhất trong cửa sổ lấy mẫu ngắn ~0,5 giây).
   - **Chỉ khi đã có đủ cả Biển số hợp lệ VÀ Khuôn mặt chuẩn nhất**, hệ thống mới **đồng thời lưu cả cặp `(Biển số, Vector khuôn mặt 512 chiều, Chiều Vào/Ra, Thời gian)` vào MySQL** (và đối chiếu Cosine với lượt vào nếu là chiều đi ra).
   - Nếu xe rời khỏi vạch dừng quá thời gian chờ (timeout ~3,0 giây sau khi mất biển số) mà vẫn không có khuôn mặt, hệ thống tự động hủy bản lưu hờ để tránh ghép nhầm sang xe tiếp theo.
