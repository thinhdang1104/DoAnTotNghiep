"""Điểm khởi chạy trên Hugging Face Spaces (Gradio SDK + ZeroGPU).

Gradio chỉ đóng vai trò "vỏ" để vượt qua bước kiểm tra của ZeroGPU; toàn bộ giao diện
và API thực sự vẫn là FastAPI trong `main.py`, được gắn trực tiếp vào server của Gradio.
Chạy cục bộ thì dùng `python main.py` như bình thường.
"""

import os
import threading

# Tắt Node SSR proxy của Gradio 6 (proxy này chặn các route FastAPI được gắn thêm).
os.environ["GRADIO_SSR_MODE"] = "false"

import torch

# ZeroGPU cấm khởi tạo CUDA/NVML ở tiến trình chính -> ép chạy CPU.
torch.cuda.is_available = lambda: False
torch.cuda.device_count = lambda: 0

try:
    import spaces
except ImportError:
    spaces = None

import gradio as gr
from main import (
    DatabaseConfigurationError,
    DatabaseOperationError,
    app as fastapi_app,
    state,
)


def _gpu_warmup():
    return "ok"


# ZeroGPU yêu cầu ứng dụng đăng ký ít nhất một hàm @spaces.GPU.
if spaces is not None:
    _gpu_warmup = spaces.GPU(_gpu_warmup)


CUSTOM_CSS = """
html, body, .gradio-container, .main, .wrap, .contain {
    margin: 0 !important;
    padding: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    max-width: 100vw !important;
    overflow: hidden !important;
    background: #060709 !important;
}
footer { display: none !important; }
"""

IFRAME_HTML = """
<iframe
    src="/ui"
    allow="camera; microphone; fullscreen; autoplay"
    style="position:fixed; top:0; left:0; width:100vw; height:100vh; border:none; margin:0; padding:0; z-index:999999; background:#060709;"
></iframe>
"""

with gr.Blocks(title="Hệ thống Quản lý Bãi giữ xe AI (2 Camera)") as demo:
    gr.HTML(IFRAME_HTML)
    warmup_btn = gr.Button("Warmup", visible=False)
    warmup_out = gr.Textbox(visible=False)
    warmup_btn.click(fn=_gpu_warmup, inputs=[], outputs=[warmup_out])


def _init_backend_services() -> None:
    """Tương đương `lifespan` của FastAPI (lifespan không chạy khi route được gắn vào Gradio)."""
    state.load_pending_from_disk()
    try:
        flushed = state.connect_database()
        if flushed:
            print(f"[DB] Đã đồng bộ {flushed} bản ghi chờ từ lần chạy trước.")
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        print(f"[WARN] Chưa kết nối được DB, bản ghi sẽ được lưu tạm: {error}")
    state.start_db_writer()
    threading.Thread(target=state.load_ai_models, daemon=True).start()


def _attach_fastapi_routes(gr_app) -> None:
    """Chèn các route của FastAPI (main.py) lên đầu router của Gradio sau khi launch() hoàn tất."""
    if gr_app is None:
        return
    skip_paths = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
    # Xóa route "/" mặc định của Gradio sau khi startup check đã xong để phục vụ trực tiếp index.html (không qua iframe lồng nhau)
    gr_app.router.routes[:] = [
        r for r in gr_app.router.routes if getattr(r, "path", None) != "/"
    ]
    existing = {getattr(r, "path", None) for r in gr_app.router.routes}
    for route in reversed(fastapi_app.router.routes):
        path = getattr(route, "path", None)
        if path and path not in skip_paths and path not in existing:
            gr_app.router.routes.insert(0, route)


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860")))
    print(f"\n[SYS] Khởi động Hệ thống Quản lý Bãi giữ xe AI (Gradio + ZeroGPU) trên cổng {port}...\n")
    _init_backend_services()
    launched = demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True,
        ssr_mode=False,
        css=CUSTOM_CSS,
    )
    gr_server_app = launched[0] if isinstance(launched, tuple) else getattr(demo, "server_app", None)
    _attach_fastapi_routes(gr_server_app)
    demo.block_thread()
