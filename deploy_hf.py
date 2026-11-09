"""Đẩy mã nguồn + trọng số mô hình lên Hugging Face Space (Gradio SDK).

Cách dùng:
    set HF_TOKEN=hf_xxx   (hoặc truyền token làm tham số đầu tiên / nhập khi được hỏi)
    python deploy_hf.py
"""

import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

REPO_ID = "MinhThinh/DoAn"
BASE_DIR = Path(__file__).resolve().parent

# Chỉ upload đúng những file Space cần để chạy (whitelist).
ALLOW_PATTERNS = [
    "README.md",
    "app.py",
    "main.py",
    "database.py",
    "face_service.py",
    "requirements.txt",
    "packages.txt",
    "frontend/*",
    "weights/*.pt",
    "data/parking_history.db",
]


def main() -> None:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token and len(sys.argv) > 1:
        token = sys.argv[1].strip()
    if not token:
        token = input("Hugging Face Write Token (hf_...): ").strip()
    if not token.startswith("hf_"):
        sys.exit("[LỖI] Token không hợp lệ (phải bắt đầu bằng 'hf_').")

    api = HfApi(token=token)
    print(f"[SYS] Đang đẩy code + weights lên https://huggingface.co/spaces/{REPO_ID} ...")
    api.upload_folder(
        folder_path=str(BASE_DIR),
        repo_id=REPO_ID,
        repo_type="space",
        allow_patterns=ALLOW_PATTERNS,
        # Xóa các file cũ trên Space không còn nằm trong whitelist (dataset, script tạm, ...)
        delete_patterns=["*"],
        commit_message="Deploy He Thong Quan Ly Bai Giu Xe AI 2 Camera",
    )
    print("[OK] Hoàn tất. Web: https://minhthinh-doan.hf.space")


if __name__ == "__main__":
    main()
