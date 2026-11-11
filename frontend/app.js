(() => {
  // Navigation & Topbar elements
  const navRecognition = document.getElementById("nav-recognition");
  const navManagement = document.getElementById("nav-management");
  const navItems = [navRecognition, navManagement];
  const views = document.querySelectorAll(".screen-view");
  const navPendingBadge = document.getElementById("nav-pending-badge");
  const streamLiveDot = document.getElementById("stream-live-dot");

  // Screen 1: Full-width Dual Camera (Cam 1 + Cam 2) elements
  const cameraAlertBox = document.getElementById("camera-alert-box");
  const cam1IndexInput = document.getElementById("cam1-index-input");
  const cam2IndexInput = document.getElementById("cam2-index-input");
  const btnScanCamera = document.getElementById("btn-scan-camera");
  const btnStartCamera = document.getElementById("btn-start-camera");
  const btnStopCamera = document.getElementById("btn-stop-camera");
  const btnCam1Start = document.getElementById("btn-cam1-start");
  const btnCam1Stop = document.getElementById("btn-cam1-stop");
  const btnCam2Start = document.getElementById("btn-cam2-start");
  const btnCam2Stop = document.getElementById("btn-cam2-stop");

  const cam1UnitCard = document.getElementById("cam1-unit-card");
  const cam2UnitCard = document.getElementById("cam2-unit-card");
  const cam1VotePill = document.getElementById("cam1-vote-pill");
  const cam2VotePill = document.getElementById("cam2-vote-pill");
  const cam1PlateValue = document.getElementById("cam1-plate-value");
  const cam1FaceValue = document.getElementById("cam1-face-value");
  const cam2PlateValue = document.getElementById("cam2-plate-value");
  const cam2FaceValue = document.getElementById("cam2-face-value");
  const cam1StreamImg = document.getElementById("cam1-stream-img");
  const cam2StreamImg = document.getElementById("cam2-stream-img");
  const cam1LiveVideo = document.getElementById("cam1-live-video");
  const cam2LiveVideo = document.getElementById("cam2-live-video");
  const cam1OverlayCanvas = document.getElementById("cam1-overlay-canvas");
  const cam2OverlayCanvas = document.getElementById("cam2-overlay-canvas");
  const cam1Placeholder = document.getElementById("cam1-placeholder");
  const cam2Placeholder = document.getElementById("cam2-placeholder");
  const voteAmbiguousWarning = document.getElementById("vote-ambiguous-warning");
  const liveFlowPill = document.getElementById("live-flow-pill");

  // Two-Phase Latch elements
  const latchStatusBox = document.getElementById("latch-status-box");
  const latchDirectionBadge = document.getElementById("latch-direction-badge");
  const latchPlateText = document.getElementById("latch-plate-text");
  const latchStepText = document.getElementById("latch-step-text");
  const btnCancelLatch = document.getElementById("btn-cancel-latch");

  // Security Alert elements
  const securityAlertBox = document.getElementById("security-alert-box");
  const alertScorePill = document.getElementById("alert-score-pill");
  const alertDetailText = document.getElementById("alert-detail-text");
  const btnApproveExit = document.getElementById("btn-approve-exit");
  const btnRejectExit = document.getElementById("btn-reject-exit");

  // Screen 2: Management & Ledger elements
  const managementAlertBox = document.getElementById("management-alert-box");
  const statInParking = document.getElementById("stat-in-parking");
  const statTodayRecords = document.getElementById("stat-today-records");
  const statTotalRecords = document.getElementById("stat-total-records");
  const statPendingRecords = document.getElementById("stat-pending-records");

  // Revenue Report elements (2.000 đ / lượt)
  const revTodayAmount = document.getElementById("rev-today-amount");
  const revTodayTickets = document.getElementById("rev-today-tickets");
  const revMonthAmount = document.getElementById("rev-month-amount");
  const revMonthTickets = document.getElementById("rev-month-tickets");
  const revYearAmount = document.getElementById("rev-year-amount");
  const revYearTickets = document.getElementById("rev-year-tickets");
  const revTotalAmount = document.getElementById("rev-total-amount");
  const revTotalTickets = document.getElementById("rev-total-tickets");
  const revPeriodBtns = document.querySelectorAll(".rev-period-btn[data-rev-period]");
  const revenuePeriodColTitle = document.getElementById("revenue-period-col-title");
  const revenueTableBody = document.getElementById("revenue-table-body");

  const pendingSection = document.getElementById("pending-section");
  const pendingTableBody = document.getElementById("pending-table-body");
  const btnFlushPending = document.getElementById("btn-flush-pending");

  const tabLinks = document.querySelectorAll(".tab-link[data-status-filter]");
  const tabCountAll = document.getElementById("tab-count-all");
  const tabCountParking = document.getElementById("tab-count-parking");
  const tabCountIn = document.getElementById("tab-count-in");
  const tabCountOut = document.getElementById("tab-count-out");
  const searchPlateInput = document.getElementById("search-plate-input");
  const ledgerCountText = document.getElementById("ledger-count-text");
  const btnRefreshManagement = document.getElementById("btn-refresh-management");
  const historyTableBody = document.getElementById("history-table-body");
  const paginationRangeText = document.getElementById("pagination-range-text");
  const pageSizeSelect = document.getElementById("page-size-select");
  const paginationControls = document.getElementById("pagination-controls");

  let activeStatusFilter = "all";
  let activeRevenuePeriod = "daily";
  let cachedRevenueData = null;
  let cachedHistoryRecords = [];
  let cachedMatchedCount = 0;
  let cachedTotalRecords = 0;
  let currentPage = 1;
  let pageSize = 10;
  let isCameraStreaming = false;
  let camStreaming = { 1: false, 2: false };
  let browserCamPorts = { 1: null, 2: null };
  let lastRecordsVersion = -1;
  let lastFeedbackSeq = -1;
  let searchDebounceTimer = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function showBanner(box, type, message) {
    if (!box) return;
    if (!message) {
      box.className = "notice-banner hidden";
      box.textContent = "";
      return;
    }
    box.className = type ? `notice-banner notice-${type}` : "notice-banner";
    box.textContent = message;
  }

  function activateView(targetId) {
    navItems.forEach((btn) => {
      if (!btn) return;
      const isMatch = btn.getAttribute("data-target") === targetId;
      if (isMatch) {
        btn.setAttribute("aria-current", "page");
      } else {
        btn.removeAttribute("aria-current");
      }
    });

    views.forEach((section) => {
      section.classList.toggle("active", section.id === targetId);
    });

    if (targetId === "view-management") {
      fetchManagementOverview();
    }
  }

  navItems.forEach((btn) => {
    if (!btn) return;
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      if (targetId) {
        activateView(targetId);
      }
    });
  });

  if (
    window.location.hash === "#management" ||
    new URLSearchParams(window.location.search).get("view") === "management"
  ) {
    activateView("view-management");
  }

  function updatePendingBadgeUI(pendingCount) {
    if (navPendingBadge) {
      if (pendingCount > 0) {
        navPendingBadge.textContent = String(pendingCount);
        navPendingBadge.classList.remove("hidden");
      } else {
        navPendingBadge.classList.add("hidden");
      }
    }
  }

  function renderDirectionPill(dirText) {
    const str = String(dirText || "Vào bãi");
    if (str.includes("Ra")) {
      return `<span class="pill warn">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill pos">${escapeHtml(str)}</span>`;
  }

  function renderParkingStatusPill(statusText) {
    const str = String(statusText || "-");
    if (str === "Đang gửi") {
      return `<span class="pill warn">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill">${escapeHtml(str)}</span>`;
  }

  function renderFacePill(faceText) {
    const str = String(faceText || "");
    if (str.startsWith("Có")) {
      return `<span class="pill pos">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill">${escapeHtml(str || "Không rõ")}</span>`;
  }

  function renderMatchPill(matchText) {
    const str = String(matchText || "-");
    if (str.startsWith("Khớp")) {
      return `<span class="pill pos">${escapeHtml(str)}</span>`;
    }
    if (str.startsWith("Lệch")) {
      return `<span class="pill neg">${escapeHtml(str)}</span>`;
    }
    if (str === "Đã lưu mẫu mặt" || str === "Chờ lưu") {
      return `<span class="pill warn">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill">${escapeHtml(str)}</span>`;
  }

  // ==================== LATCH & ALERT CONTROLS ====================
  if (btnCancelLatch) {
    btnCancelLatch.addEventListener("click", async () => {
      await fetch("/api/camera/cancel-latch", { method: "POST" });
      await pollCameraStatusOnce();
    });
  }

  async function resolveAlert(action) {
    btnApproveExit.disabled = true;
    btnRejectExit.disabled = true;
    try {
      await fetch("/api/camera/resolve-alert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      await pollCameraStatusOnce();
      await fetchManagementOverview();
    } finally {
      btnApproveExit.disabled = false;
      btnRejectExit.disabled = false;
    }
  }

  if (btnApproveExit) {
    btnApproveExit.addEventListener("click", () => resolveAlert("approve"));
  }
  if (btnRejectExit) {
    btnRejectExit.addEventListener("click", () => resolveAlert("reject"));
  }

  // ==================== DUAL CAMERA CONTROLS (LOCAL USB + CLOUD WEBRTC) ====================
  let browserWebRTCActive = false;
  let isStartingCamera = false;
  let didInitialStaleCheck = false;
  let browserCamDevices = [];
  let browserStreams = [null, null];
  let browserVideos = [null, null];
  let browserCanvas = null;
  let browserFrameTimer = null;
  let browserInFlight = false;

  async function scanBrowserWebcams() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return [];
    }
    try {
      const tempStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      tempStream.getTracks().forEach((t) => t.stop());
      await new Promise((r) => setTimeout(r, 180));
    } catch (_) {
      // Nếu cổng mặc định lỗi, vẫn thử liệt kê danh sách thiết bị
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    browserCamDevices = devices.filter((d) => d.kind === "videoinput");
    return browserCamDevices;
  }

  async function waitVideoReady(video, timeoutMs = 1800) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
        return true;
      }
      await new Promise((r) => setTimeout(r, 60));
    }
    return video.videoWidth > 0 && video.videoHeight > 0;
  }

  async function tryOpenStreamWithVideo(constraints) {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    const video = document.createElement("video");
    video.playsInline = true;
    video.muted = true;
    video.autoplay = true;
    video.style.cssText =
      "position:fixed;left:-9999px;top:-9999px;width:2px;height:2px;opacity:0;pointer-events:none;";
    document.body.appendChild(video);
    video.srcObject = stream;
    try {
      await video.play();
    } catch (_) {
      // Ignore play() promise warning if autoplay already started
    }
    const ready = await waitVideoReady(video, 1800);
    if (!ready) {
      stream.getTracks().forEach((t) => t.stop());
      video.remove();
      throw new Error("Thiết bị camera không trả về khung hình (videoWidth = 0).");
    }
    return { stream, video };
  }

  async function openBrowserWebcamAtIndex(camIdx) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        "Trình duyệt chặn quyền Camera (cần chạy trên localhost hoặc HTTPS, hoặc mở trực tiếp https://minhthinh-doan.hf.space)."
      );
    }
    if (!browserCamDevices.length) {
      await scanBrowserWebcams();
    }

    // Sắp xếp thứ tự ưu tiên thử mở:
    // 1. Đúng cổng camIdx người dùng chọn
    // 2. Các cổng có tên "DroidCam" (nếu cổng camIdx bị hỏng/trống)
    // 3. Các cổng videoinput còn lại
    const candidates = [];
    const seenIds = new Set();
    const pushCandidate = (dev, idx) => {
      if (!dev) return;
      const key = dev.deviceId || `idx-${idx}`;
      if (seenIds.has(key)) return;
      seenIds.add(key);
      candidates.push({ dev, idx });
    };

    if (browserCamDevices[camIdx]) {
      pushCandidate(browserCamDevices[camIdx], camIdx);
    }
    browserCamDevices.forEach((d, idx) => {
      if ((d.label || "").toLowerCase().includes("droidcam")) {
        pushCandidate(d, idx);
      }
    });
    browserCamDevices.forEach((d, idx) => pushCandidate(d, idx));

    let lastErr = null;
    for (const item of candidates) {
      if (item.dev && item.dev.deviceId) {
        try {
          // Không ép độ phân giải 960x540 để tương thích 100% với DroidCam DirectShow (640x480)
          const res = await tryOpenStreamWithVideo({
            video: { deviceId: { exact: item.dev.deviceId } },
            audio: false,
          });
          return { ...res, openedIndex: item.idx, label: item.dev.label || `Cổng ${item.idx}` };
        } catch (err) {
          lastErr = err;
        }
      }
    }

    // Fallback cuối cùng: mở camera mặc định của trình duyệt
    try {
      const res = await tryOpenStreamWithVideo({ video: true, audio: false });
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        browserCamDevices = devices.filter((d) => d.kind === "videoinput");
      } catch (_) {}
      return { ...res, openedIndex: camIdx, label: "Webcam mặc định" };
    } catch (err) {
      const finalErr = lastErr || err;
      if (finalErr && (finalErr.name === "NotAllowedError" || finalErr.name === "SecurityError")) {
        const inIframe = window.self !== window.top;
        throw new Error(
          inIframe
            ? "Trình duyệt chặn quyền Camera trong khung nhúng. Vui lòng cho phép quyền Camera trên thanh địa chỉ hoặc mở trực tiếp tại: https://minhthinh-doan.hf.space"
            : "Bạn chưa cấp quyền sử dụng Camera cho trình duyệt. Hãy bấm biểu tượng ổ khóa trên thanh địa chỉ và chọn 'Cho phép (Allow)' Camera."
        );
      }
      if (finalErr && finalErr.name === "NotFoundError") {
        throw new Error("Không tìm thấy thiết bị Webcam nào được kết nối với máy tính/điện thoại của bạn.");
      }
      if (finalErr && finalErr.name === "NotReadableError") {
        throw new Error("Camera đang bị khóa bởi ứng dụng khác hoặc cổng được chọn không hoạt động. Hãy bấm 'Dò cổng' và thử lại.");
      }
      throw finalErr;
    }
  }

  function captureVideoToJpegDataUrl(video) {
    if (!video || video.readyState < 2 || !video.videoWidth) return null;
    if (!browserCanvas) {
      browserCanvas = document.createElement("canvas");
    }
    const targetW = 640;
    const scale = targetW / video.videoWidth;
    const targetH = Math.max(240, Math.round(video.videoHeight * scale));
    browserCanvas.width = targetW;
    browserCanvas.height = targetH;
    const ctx = browserCanvas.getContext("2d");
    ctx.drawImage(video, 0, 0, targetW, targetH);
    return browserCanvas.toDataURL("image/jpeg", 0.78);
  }

  function clearOverlayCanvas(canvasEl) {
    if (!canvasEl) return;
    const ctx = canvasEl.getContext("2d");
    ctx.clearRect(0, 0, canvasEl.width || 640, canvasEl.height || 480);
  }

  function drawOverlayBoxes(videoEl, canvasEl, boxData) {
    if (!canvasEl) return;
    const rect = canvasEl.getBoundingClientRect();
    const cw = Math.round(rect.width) || 640;
    const ch = Math.round(rect.height) || 480;
    if (canvasEl.width !== cw || canvasEl.height !== ch) {
      canvasEl.width = cw;
      canvasEl.height = ch;
    }
    const ctx = canvasEl.getContext("2d");
    ctx.clearRect(0, 0, cw, ch);
    if (!boxData || !videoEl || !videoEl.videoWidth || !videoEl.videoHeight) return;

    const vw = videoEl.videoWidth;
    const vh = videoEl.videoHeight;
    const scale = Math.min(cw / vw, ch / vh);
    const drawW = vw * scale;
    const drawH = vh * scale;
    const offsetX = (cw - drawW) / 2;
    const offsetY = (ch - drawH) / 2;

    ctx.font = "600 13px 'JetBrains Mono', monospace";
    ctx.lineWidth = 2.5;

    (boxData.plates || []).forEach((b) => {
      const x = offsetX + b.x1 * drawW;
      const y = offsetY + b.y1 * drawH;
      const w = (b.x2 - b.x1) * drawW;
      const h = (b.y2 - b.y1) * drawH;
      const color = b.valid ? "#22c55e" : "#f59e0b";
      ctx.strokeStyle = color;
      ctx.strokeRect(x, y, w, h);
      if (b.label) {
        const tw = ctx.measureText(b.label).width + 12;
        const ly = Math.max(0, y - 24);
        ctx.fillStyle = "rgba(6, 7, 9, 0.85)";
        ctx.fillRect(x, ly, tw, 22);
        ctx.fillStyle = "#fde047";
        ctx.fillText(b.label, x + 6, ly + 15);
      }
    });

    (boxData.faces || []).forEach((f) => {
      const x = offsetX + f.x1 * drawW;
      const y = offsetY + f.y1 * drawH;
      const w = (f.x2 - f.x1) * drawW;
      const h = (f.y2 - f.y1) * drawH;
      ctx.strokeStyle = "#d946ef";
      ctx.strokeRect(x, y, w, h);
      if (f.label) {
        const tw = ctx.measureText(f.label).width + 12;
        const ly = Math.max(0, y - 24);
        ctx.fillStyle = "rgba(6, 7, 9, 0.85)";
        ctx.fillRect(x, ly, tw, 22);
        ctx.fillStyle = "#f0abfc";
        ctx.fillText(f.label, x + 6, ly + 15);
      }
    });
  }

  function revealCamImagesIfReady() {
    if (camStreaming[1]) {
      if (browserVideos[0] && cam1LiveVideo) {
        cam1LiveVideo.classList.remove("hidden");
        if (cam1OverlayCanvas) cam1OverlayCanvas.classList.remove("hidden");
        cam1StreamImg.classList.add("hidden");
        cam1Placeholder.classList.add("hidden");
      } else if (cam1StreamImg.getAttribute("src")) {
        cam1StreamImg.classList.remove("hidden");
        cam1Placeholder.classList.add("hidden");
      }
    }
    if (camStreaming[2]) {
      if (browserVideos[1] && cam2LiveVideo) {
        cam2LiveVideo.classList.remove("hidden");
        if (cam2OverlayCanvas) cam2OverlayCanvas.classList.remove("hidden");
        cam2StreamImg.classList.add("hidden");
        cam2Placeholder.classList.add("hidden");
      } else if (cam2StreamImg.getAttribute("src")) {
        cam2StreamImg.classList.remove("hidden");
        cam2Placeholder.classList.add("hidden");
      }
    }
  }

  function ensureBrowserFrameLoop() {
    if (browserFrameTimer) return;
    browserFrameTimer = setInterval(async () => {
      if (!browserWebRTCActive || browserInFlight) return;
      const v1 = browserVideos[0];
      const v2 = browserVideos[1];
      if (!v1 && !v2) return;

      const img1 = v1 ? captureVideoToJpegDataUrl(v1) : null;
      const img2 = v2 ? (v2 === v1 ? img1 : captureVideoToJpegDataUrl(v2)) : null;
      if (!img1 && !img2) return;

      browserInFlight = true;
      try {
        const res = await fetch("/api/camera/browser-frame", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cam1_image: img1, cam2_image: img2 }),
        });
        if (res.ok) {
          const out = await res.json();
          if (v1 && out.cam1_boxes) {
            drawOverlayBoxes(cam1LiveVideo || v1, cam1OverlayCanvas, out.cam1_boxes);
          }
          if (v2 && out.cam2_boxes) {
            drawOverlayBoxes(cam2LiveVideo || v2, cam2OverlayCanvas, out.cam2_boxes);
          }
        }
      } catch (_) {
        // Bỏ qua lỗi mạng tạm thời
      } finally {
        browserInFlight = false;
      }
    }, 220);
  }

  async function startBrowserWebRTCForCam(camId, portIdx) {
    const slot = camId - 1;
    const otherId = 3 - camId;
    const otherSlot = otherId - 1;

    stopBrowserWebRTCForCam(camId);

    let camObj = null;
    if (
      browserVideos[otherSlot] &&
      browserStreams[otherSlot] &&
      (browserCamPorts[otherId] === portIdx || browserCamDevices.length <= 1)
    ) {
      // Dùng chung luồng webcam trình duyệt nếu 2 cam chọn cùng cổng hoặc máy chỉ có 1 webcam
      camObj = {
        stream: browserStreams[otherSlot],
        video: browserVideos[otherSlot],
        openedIndex: browserCamPorts[otherId] ?? portIdx,
      };
    } else {
      camObj = await openBrowserWebcamAtIndex(portIdx);
    }

    browserStreams[slot] = camObj.stream;
    browserVideos[slot] = camObj.video;
    browserCamPorts[camId] = camObj.openedIndex ?? portIdx;
    browserWebRTCActive = Boolean(browserVideos[0] || browserVideos[1]);
    camStreaming[camId] = true;
    isCameraStreaming = Boolean(camStreaming[1] || camStreaming[2]);

    // Hiển thị trực tiếp thẻ <video> ở tốc độ 60 FPS mượt tuyệt đối (độ trễ 0ms)
    const liveVideoEl = camId === 1 ? cam1LiveVideo : cam2LiveVideo;
    if (liveVideoEl) {
      liveVideoEl.srcObject = camObj.stream;
      try {
        await liveVideoEl.play();
      } catch (_) {}
    }
    revealCamImagesIfReady();
    ensureBrowserFrameLoop();
  }

  function stopBrowserWebRTCForCam(camId) {
    const slot = camId - 1;
    const otherSlot = 1 - slot;
    const s = browserStreams[slot];
    const v = browserVideos[slot];

    browserStreams[slot] = null;
    browserVideos[slot] = null;
    browserCamPorts[camId] = null;

    const liveVideoEl = camId === 1 ? cam1LiveVideo : cam2LiveVideo;
    const overlayCanvasEl = camId === 1 ? cam1OverlayCanvas : cam2OverlayCanvas;
    if (liveVideoEl) {
      liveVideoEl.srcObject = null;
      liveVideoEl.classList.add("hidden");
    }
    if (overlayCanvasEl) {
      clearOverlayCanvas(overlayCanvasEl);
      overlayCanvasEl.classList.add("hidden");
    }

    if (s && browserStreams[otherSlot] !== s) {
      s.getTracks().forEach((t) => t.stop());
    }
    if (v && browserVideos[otherSlot] !== v) {
      v.srcObject = null;
      v.remove();
    }

    browserWebRTCActive = Boolean(browserVideos[0] || browserVideos[1]);
    if (!browserWebRTCActive && browserFrameTimer) {
      clearInterval(browserFrameTimer);
      browserFrameTimer = null;
    }
  }

  function stopBrowserWebRTC() {
    stopBrowserWebRTCForCam(1);
    stopBrowserWebRTCForCam(2);
  }

  function hideCamStreamUI(camId) {
    camStreaming[camId] = false;
    isCameraStreaming = Boolean(camStreaming[1] || camStreaming[2]);
    const imgEl = camId === 1 ? cam1StreamImg : cam2StreamImg;
    const liveVideoEl = camId === 1 ? cam1LiveVideo : cam2LiveVideo;
    const overlayCanvasEl = camId === 1 ? cam1OverlayCanvas : cam2OverlayCanvas;
    const phEl = camId === 1 ? cam1Placeholder : cam2Placeholder;
    if (imgEl) {
      imgEl.removeAttribute("src");
      imgEl.classList.add("hidden");
    }
    if (liveVideoEl) {
      liveVideoEl.srcObject = null;
      liveVideoEl.classList.add("hidden");
    }
    if (overlayCanvasEl) {
      clearOverlayCanvas(overlayCanvasEl);
      overlayCanvasEl.classList.add("hidden");
    }
    if (phEl) {
      phEl.classList.remove("hidden");
    }
  }

  async function startSingleCamUI(camId) {
    const inputEl = camId === 1 ? cam1IndexInput : cam2IndexInput;
    const startBtn = camId === 1 ? btnCam1Start : btnCam2Start;
    const portIdx = parseInt((inputEl && inputEl.value) || "0", 10);

    isStartingCamera = true;
    if (startBtn) startBtn.disabled = true;
    if (inputEl) inputEl.disabled = true;
    showBanner(cameraAlertBox, "", `Đang kết nối Cam ${camId} tại cổng ${portIdx}...`);
    try {
      const res = await fetch(`/api/camera/${camId}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_index: portIdx }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Không thể mở Cam ${camId}.`);
      }
      if (data.mode === "browser") {
        await startBrowserWebRTCForCam(camId, portIdx);
      } else {
        const ts = Date.now();
        const imgEl = camId === 1 ? cam1StreamImg : cam2StreamImg;
        const phEl = camId === 1 ? cam1Placeholder : cam2Placeholder;
        camStreaming[camId] = true;
        isCameraStreaming = true;
        if (imgEl) {
          imgEl.src = `/api/camera/stream/${camId}?t=${ts}`;
          imgEl.classList.remove("hidden");
        }
        if (phEl) phEl.classList.add("hidden");
      }
      showBanner(cameraAlertBox, "", "");
      await pollCameraStatusOnce();
    } catch (err) {
      stopBrowserWebRTCForCam(camId);
      hideCamStreamUI(camId);
      await fetch(`/api/camera/${camId}/stop`, { method: "POST" }).catch(() => {});
      showBanner(cameraAlertBox, "error", err.message);
      if (startBtn) startBtn.disabled = false;
      if (inputEl) inputEl.disabled = false;
    } finally {
      isStartingCamera = false;
    }
  }

  async function stopSingleCamUI(camId) {
    const stopBtn = camId === 1 ? btnCam1Stop : btnCam2Stop;
    if (stopBtn) stopBtn.disabled = true;
    stopBrowserWebRTCForCam(camId);
    hideCamStreamUI(camId);
    try {
      await fetch(`/api/camera/${camId}/stop`, { method: "POST" });
      await pollCameraStatusOnce();
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    }
  }

  if (btnCam1Start) {
    btnCam1Start.addEventListener("click", () => startSingleCamUI(1));
  }
  if (btnCam1Stop) {
    btnCam1Stop.addEventListener("click", () => stopSingleCamUI(1));
  }
  if (btnCam2Start) {
    btnCam2Start.addEventListener("click", () => startSingleCamUI(2));
  }
  if (btnCam2Stop) {
    btnCam2Stop.addEventListener("click", () => stopSingleCamUI(2));
  }

  btnScanCamera.addEventListener("click", async () => {
    btnScanCamera.disabled = true;
    showBanner(cameraAlertBox, "", "Đang dò các cổng camera...");
    try {
      const res = await fetch("/api/camera/scan", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể dò cổng camera.");
      }
      if (data.cameras && data.cameras.length > 0) {
        const listText = data.cameras.map((c) => `cổng ${c.index}`).join(", ");
        if (!camStreaming[1]) cam1IndexInput.value = data.cameras[0].index;
        if (!camStreaming[2]) {
          cam2IndexInput.value =
            data.cameras.length >= 2 ? data.cameras[1].index : data.cameras[0].index;
        }
        showBanner(
          cameraAlertBox,
          "success",
          `Tìm thấy ${data.cameras.length} camera (${listText}). Bạn có thể bấm "Kết nối" ở từng Cam hoặc "Bật cả 2".`
        );
      } else {
        const webcams = await scanBrowserWebcams();
        if (webcams.length > 0) {
          const droidIdx = webcams.findIndex((w) =>
            (w.label || "").toLowerCase().includes("droidcam")
          );
          if (droidIdx >= 0) {
            if (!camStreaming[1]) cam1IndexInput.value = droidIdx;
            if (!camStreaming[2]) cam2IndexInput.value = droidIdx;
          } else {
            if (!camStreaming[1]) cam1IndexInput.value = 0;
            if (!camStreaming[2]) cam2IndexInput.value = webcams.length >= 2 ? 1 : 0;
          }
          const names = webcams.map((w, i) => `cổng ${i} (${w.label || "Webcam"})`).join(", ");
          showBanner(
            cameraAlertBox,
            "success",
            `[WebRTC] Tìm thấy ${webcams.length} camera: ${names}. Bấm "Kết nối" ở Cam 1 hoặc Cam 2 để bắt đầu!`
          );
        } else {
          showBanner(cameraAlertBox, "error", "Không tìm thấy camera nào từ cổng 0 đến 5.");
        }
      }
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    } finally {
      btnScanCamera.disabled = false;
    }
  });

  btnStartCamera.addEventListener("click", async () => {
    btnStartCamera.disabled = true;
    try {
      if (!camStreaming[1]) {
        await startSingleCamUI(1);
      }
      if (!camStreaming[2]) {
        await startSingleCamUI(2);
      }
    } finally {
      await pollCameraStatusOnce();
    }
  });

  btnStopCamera.addEventListener("click", async () => {
    btnStopCamera.disabled = true;
    stopBrowserWebRTC();
    hideCamStreamUI(1);
    hideCamStreamUI(2);
    try {
      await fetch("/api/camera/stop", { method: "POST" });
      await pollCameraStatusOnce();
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    }
  });

  function updateSingleCamReadout(camData, votePillEl, plateValueEl, faceValueEl, running) {
    if (!camData) return;

    const plates = camData.current_plates || [];
    const faces = camData.current_faces || [];

    if (plateValueEl) {
      if (plates.length > 0) {
        plateValueEl.textContent = `Biển: ${plates.join(", ")}`;
        plateValueEl.classList.remove("hidden");
      } else {
        plateValueEl.classList.add("hidden");
      }
    }

    if (faceValueEl) {
      if (faces.length > 0) {
        const bestConf = Math.round(Math.max(...faces) * 100);
        faceValueEl.textContent = `Mặt: ${bestConf}%`;
        faceValueEl.classList.remove("hidden");
      } else {
        faceValueEl.classList.add("hidden");
      }
    }

    if (votePillEl) {
      if (!running) {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `Cổng ${camData.device_index} · Ngắt`;
      } else if (camData.vote) {
        const pct = Math.round(camData.vote.vote_share * 100);
        votePillEl.className = "pill warn mono-num num";
        votePillEl.textContent = `${camData.vote.candidate} (${camData.vote.vote_count}/${camData.vote.sample_count} · ${pct}%)`;
      } else {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `Cổng ${camData.device_index} · Đang quét`;
      }
    }
  }

  function syncSingleCamUI(
    camId,
    camState,
    inputEl,
    startBtn,
    stopBtn,
    imgEl,
    phEl
  ) {
    const slot = camId - 1;
    const isActive = Boolean(
      (camState && camState.active) || browserVideos[slot]
    );
    const mode = (camState && camState.mode) || (browserVideos[slot] ? "browser" : "local");

    if (isActive) {
      if (camState && typeof camState.device_index === "number" && inputEl) {
        inputEl.value = camState.device_index;
      }
      if (!camStreaming[camId]) {
        camStreaming[camId] = true;
        if (mode !== "browser" && imgEl && phEl) {
          imgEl.src = `/api/camera/stream/${camId}?t=${Date.now()}`;
          imgEl.classList.remove("hidden");
          phEl.classList.add("hidden");
        } else {
          revealCamImagesIfReady();
        }
      }
      if (inputEl) inputEl.disabled = true;
      if (startBtn) startBtn.disabled = true;
      if (stopBtn) stopBtn.disabled = false;
    } else {
      if (camStreaming[camId]) {
        stopBrowserWebRTCForCam(camId);
        hideCamStreamUI(camId);
      }
      if (inputEl) inputEl.disabled = false;
      if (startBtn) startBtn.disabled = false;
      if (stopBtn) stopBtn.disabled = true;
    }
    return isActive;
  }

  async function pollCameraStatusOnce() {
    if (isStartingCamera) return;
    try {
      const res = await fetch("/api/camera/status");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const state = await res.json();
      if (isStartingCamera) return;

      updatePendingBadgeUI(state.pending_count);

      if (!didInitialStaleCheck) {
        didInitialStaleCheck = true;
        if (state.running && state.mode === "browser" && !browserWebRTCActive) {
          await fetch("/api/camera/stop", { method: "POST" }).catch(() => {});
          state.running = false;
          if (state.cam1) state.cam1.active = false;
          if (state.cam2) state.cam2.active = false;
        }
      }

      const active1 = syncSingleCamUI(
        1,
        state.cam1,
        cam1IndexInput,
        btnCam1Start,
        btnCam1Stop,
        cam1StreamImg,
        cam1Placeholder
      );
      const active2 = syncSingleCamUI(
        2,
        state.cam2,
        cam2IndexInput,
        btnCam2Start,
        btnCam2Stop,
        cam2StreamImg,
        cam2Placeholder
      );

      isCameraStreaming = Boolean(active1 || active2);
      if (streamLiveDot) {
        streamLiveDot.classList.toggle("online", isCameraStreaming);
      }
      btnStartCamera.disabled = Boolean(active1 && active2);
      btnStopCamera.disabled = !isCameraStreaming;

      if (state.error) {
        showBanner(cameraAlertBox, "error", state.error);
      } else if (
        state.gate_feedback &&
        state.gate_feedback.message &&
        state.gate_feedback.seq !== lastFeedbackSeq
      ) {
        lastFeedbackSeq = state.gate_feedback.seq;
        showBanner(
          cameraAlertBox,
          state.gate_feedback.type || "success",
          state.gate_feedback.message
        );
      }

      updateSingleCamReadout(
        state.cam1,
        cam1VotePill,
        cam1PlateValue,
        cam1FaceValue,
        active1
      );
      updateSingleCamReadout(
        state.cam2,
        cam2VotePill,
        cam2PlateValue,
        cam2FaceValue,
        active2
      );

      // Two-Phase Latch UI
      if (state.latched) {
        latchStatusBox.classList.remove("hidden");
        const isIn = state.latched.direction === "IN";
        latchDirectionBadge.className = isIn ? "pill pos" : "pill warn";
        latchDirectionBadge.textContent = isIn ? "LƯU HỜ · ĐI VÀO" : "LƯU HỜ · ĐI RA";
        latchPlateText.textContent = state.latched.plate_number;
        latchStepText.textContent = state.latched.sampling_face
          ? `Cam ${state.latched.plate_cam} đã chốt biển — Đang chọn mặt nét nhất ở Cam ${state.latched.required_face_cam}...`
          : `Cam ${state.latched.plate_cam} đã chốt biển — Chờ khuôn mặt ở Cam ${state.latched.required_face_cam} (${state.latched.remaining_seconds}s)`;

        if (cam1UnitCard) {
          cam1UnitCard.classList.toggle(
            "cam-target-highlight",
            state.latched.required_face_cam === 1
          );
        }
        if (cam2UnitCard) {
          cam2UnitCard.classList.toggle(
            "cam-target-highlight",
            state.latched.required_face_cam === 2
          );
        }
        if (liveFlowPill) {
          liveFlowPill.className = isIn ? "pill pos" : "pill warn";
          liveFlowPill.textContent = isIn
            ? "Đang đón xe VÀO (Biển Cam 2 + Mặt Cam 1)"
            : "Đang đón xe RA (Biển Cam 1 + Mặt Cam 2)";
        }
      } else {
        latchStatusBox.classList.add("hidden");
        if (cam1UnitCard) cam1UnitCard.classList.remove("cam-target-highlight");
        if (cam2UnitCard) cam2UnitCard.classList.remove("cam-target-highlight");
        if (liveFlowPill) {
          if (active1 && active2) {
            liveFlowPill.className = "pill pos";
            liveFlowPill.textContent = "Đang bật cả 2 Camera";
          } else if (active1) {
            liveFlowPill.className = "pill warn";
            liveFlowPill.textContent = "Đang bật Cam 1 (Cam 2 tắt)";
          } else if (active2) {
            liveFlowPill.className = "pill warn";
            liveFlowPill.textContent = "Đang bật Cam 2 (Cam 1 tắt)";
          } else {
            liveFlowPill.className = "pill pos";
            liveFlowPill.textContent = "2 Camera độc lập";
          }
        }
      }

      // Security Alert UI (Face mismatch on exit)
      if (state.security_alert) {
        securityAlertBox.classList.remove("hidden");
        alertScorePill.textContent = `Độ khớp: ${state.security_alert.match_score_pct}`;
        alertDetailText.textContent =
          `Xe ${state.security_alert.plate_number} (gửi lúc ${state.security_alert.entry_time}) ` +
          `có khuôn mặt người lấy xe tại Cam 2 LỆCH so với lúc gửi vào ở Cam 1 (Cosine ${state.security_alert.match_score_pct} < 65%).`;
      } else {
        securityAlertBox.classList.add("hidden");
      }

      voteAmbiguousWarning.classList.toggle("hidden", !state.ambiguous_frame);

      if (
        typeof state.records_version === "number" &&
        state.records_version !== lastRecordsVersion
      ) {
        lastRecordsVersion = state.records_version;
        fetchManagementOverview();
      }
    } catch {
      updatePendingBadgeUI(0);
    }
  }

  async function pollLoop() {
    await pollCameraStatusOnce();
    setTimeout(pollLoop, 400);
  }

  // ==================== REVENUE REPORT (NGÀY / THÁNG / NĂM) ====================
  function formatVnd(amount) {
    const val = Math.max(0, Number(amount) || 0);
    return `${val.toLocaleString("de-DE")} đ`;
  }

  function renderRevenueBreakdownTable() {
    if (!revenueTableBody) return;

    const titleMap = {
      daily: "Ngày (DD/MM/YYYY)",
      monthly: "Tháng (MM/YYYY)",
      yearly: "Năm (YYYY)",
    };
    if (revenuePeriodColTitle) {
      revenuePeriodColTitle.textContent = titleMap[activeRevenuePeriod] || "Kỳ thống kê";
    }

    const unitFee = (cachedRevenueData && cachedRevenueData.unit_price) || 2000;
    const unitFeeText = formatVnd(unitFee);
    const rows =
      (cachedRevenueData && cachedRevenueData[activeRevenuePeriod]) || [];

    if (!rows || rows.length === 0) {
      revenueTableBody.innerHTML = `
        <tr>
          <td colspan="4">Chưa có dữ liệu doanh thu trong kỳ này.</td>
        </tr>
      `;
      return;
    }

    revenueTableBody.innerHTML = rows
      .map(
        (item) => `
          <tr>
            <td class="mono-num num"><strong>${escapeHtml(item.period)}</strong></td>
            <td class="n mono-num num">${escapeHtml(item.tickets)} lượt</td>
            <td class="n mono-num num">${escapeHtml(unitFeeText)}</td>
            <td class="n mono-num num"><span class="fee-cell-amount">${escapeHtml(formatVnd(item.revenue))}</span></td>
          </tr>
        `
      )
      .join("");
  }

  function renderRevenueSection(revenue) {
    cachedRevenueData = revenue || null;
    const today = (revenue && revenue.today) || { tickets: 0, revenue: 0 };
    const month = (revenue && revenue.month) || { tickets: 0, revenue: 0 };
    const year = (revenue && revenue.year) || { tickets: 0, revenue: 0 };
    const total = (revenue && revenue.total) || { tickets: 0, revenue: 0 };

    if (revTodayAmount) revTodayAmount.textContent = formatVnd(today.revenue);
    if (revTodayTickets) revTodayTickets.textContent = `${today.tickets ?? 0} lượt gửi xe`;

    if (revMonthAmount) revMonthAmount.textContent = formatVnd(month.revenue);
    if (revMonthTickets) revMonthTickets.textContent = `${month.tickets ?? 0} lượt gửi xe`;

    if (revYearAmount) revYearAmount.textContent = formatVnd(year.revenue);
    if (revYearTickets) revYearTickets.textContent = `${year.tickets ?? 0} lượt gửi xe`;

    if (revTotalAmount) revTotalAmount.textContent = formatVnd(total.revenue);
    if (revTotalTickets) revTotalTickets.textContent = `${total.tickets ?? 0} lượt gửi xe`;

    renderRevenueBreakdownTable();
  }

  revPeriodBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      revPeriodBtns.forEach((b) => b.setAttribute("aria-pressed", "false"));
      btn.setAttribute("aria-pressed", "true");
      activeRevenuePeriod = btn.getAttribute("data-rev-period") || "daily";
      renderRevenueBreakdownTable();
    });
  });

  // ==================== MANAGEMENT & HISTORY TABLE (WITH PAGINATION) ====================
  function renderFeeCell(feeText) {
    const str = String(feeText || "-");
    if (str.endsWith("đ")) {
      return `<span class="fee-cell-amount mono-num num">${escapeHtml(str)}</span>`;
    }
    return `<span class="stamp">${escapeHtml(str)}</span>`;
  }

  function buildPageNumbers(totalPages, current) {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const pages = [1];
    const start = Math.max(2, current - 1);
    const end = Math.min(totalPages - 1, current + 1);
    if (start > 2) pages.push("...");
    for (let p = start; p <= end; p += 1) {
      pages.push(p);
    }
    if (end < totalPages - 1) pages.push("...");
    pages.push(totalPages);
    return pages;
  }

  function renderPaginationControls(totalItems, totalPages) {
    if (!paginationControls) return;

    if (totalItems === 0) {
      if (paginationRangeText) {
        paginationRangeText.textContent = "Hiển thị 0–0 / 0 bản ghi";
      }
      paginationControls.innerHTML = "";
      return;
    }

    const startIdx = (currentPage - 1) * pageSize + 1;
    const endIdx = Math.min(totalItems, currentPage * pageSize);
    if (paginationRangeText) {
      paginationRangeText.textContent = `Hiển thị ${startIdx}–${endIdx} / ${totalItems} bản ghi`;
    }

    const pageItems = buildPageNumbers(totalPages, currentPage);
    const buttonsHtml = [];

    buttonsHtml.push(
      `<button type="button" class="page-btn" data-page="${currentPage - 1}" ${
        currentPage <= 1 ? "disabled" : ""
      } title="Trang trước">‹ Trước</button>`
    );

    pageItems.forEach((item) => {
      if (item === "...") {
        buttonsHtml.push(`<span class="page-ellipsis">…</span>`);
      } else {
        const activeClass = item === currentPage ? " active" : "";
        buttonsHtml.push(
          `<button type="button" class="page-btn${activeClass}" data-page="${item}">${item}</button>`
        );
      }
    });

    buttonsHtml.push(
      `<button type="button" class="page-btn" data-page="${currentPage + 1}" ${
        currentPage >= totalPages ? "disabled" : ""
      } title="Trang sau">Sau ›</button>`
    );

    paginationControls.innerHTML = buttonsHtml.join("");
  }

  function renderHistoryTable(records, matchedCount, totalRecords) {
    cachedHistoryRecords = Array.isArray(records) ? records : [];
    cachedMatchedCount = typeof matchedCount === "number" ? matchedCount : cachedHistoryRecords.length;
    cachedTotalRecords = typeof totalRecords === "number" ? totalRecords : cachedHistoryRecords.length;

    if (ledgerCountText) {
      ledgerCountText.textContent = `${cachedMatchedCount} / ${cachedTotalRecords} bản ghi`;
    }

    const totalItems = cachedHistoryRecords.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    if (currentPage > totalPages) {
      currentPage = totalPages;
    }
    if (currentPage < 1) {
      currentPage = 1;
    }

    if (totalItems === 0) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="9">Không có bản ghi nào khớp điều kiện lọc.</td>
        </tr>
      `;
      renderPaginationControls(0, 1);
      return;
    }

    const startOffset = (currentPage - 1) * pageSize;
    const pageSlice = cachedHistoryRecords.slice(startOffset, startOffset + pageSize);

    historyTableBody.innerHTML = pageSlice
      .map(
        (row) => `
          <tr>
            <td><span class="plate-cell-main mono-num num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderDirectionPill(row["Luồng"])}</td>
            <td>${renderParkingStatusPill(row["Trạng thái bãi"])}</td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td>${renderMatchPill(row["Đối chiếu"])}</td>
            <td class="n mono-num num">${renderFeeCell(row["Phí giữ xe"])}</td>
            <td class="n mono-num num">${escapeHtml(row["Đồng thuận biển số"] || "-")}</td>
            <td class="n mono-num num">${escapeHtml(row["Thời gian nhận diện"])}</td>
            <td class="n mono-num num">#${escapeHtml(row["ID"])}</td>
          </tr>
        `
      )
      .join("");

    renderPaginationControls(totalItems, totalPages);
  }

  if (paginationControls) {
    paginationControls.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-page]");
      if (!btn || btn.disabled) return;
      const targetPage = parseInt(btn.getAttribute("data-page") || "1", 10);
      if (!Number.isNaN(targetPage) && targetPage !== currentPage) {
        currentPage = targetPage;
        renderHistoryTable(cachedHistoryRecords, cachedMatchedCount, cachedTotalRecords);
      }
    });
  }

  if (pageSizeSelect) {
    pageSizeSelect.addEventListener("change", () => {
      const val = parseInt(pageSizeSelect.value || "10", 10);
      pageSize = Number.isNaN(val) || val < 1 ? 10 : val;
      currentPage = 1;
      renderHistoryTable(cachedHistoryRecords, cachedMatchedCount, cachedTotalRecords);
    });
  }

  function applyManagementData(data) {
    const records = data.records || [];
    const pending = data.pending_records || [];
    const stats = data.stats || {
      total_records: records.length,
      today_records: 0,
      in_parking: 0,
      total_in: 0,
      total_out: 0,
    };

    updatePendingBadgeUI(pending.length);

    if (statInParking) statInParking.textContent = String(stats.in_parking ?? 0);
    statTodayRecords.textContent = String(stats.today_records ?? 0);
    statTotalRecords.textContent = String(stats.total_records ?? 0);
    statPendingRecords.textContent = String(pending.length);

    if (tabCountAll) tabCountAll.textContent = String(stats.total_records ?? 0);
    if (tabCountParking) tabCountParking.textContent = String(stats.in_parking ?? 0);
    if (tabCountIn) tabCountIn.textContent = String(stats.total_in ?? 0);
    if (tabCountOut) tabCountOut.textContent = String(stats.total_out ?? 0);

    renderRevenueSection(data.revenue);

    if (data.database_error) {
      showBanner(managementAlertBox, "error", `Chưa kết nối được MySQL: ${data.database_error}`);
    } else {
      showBanner(managementAlertBox, "", "");
    }

    if (pending.length > 0) {
      pendingSection.classList.remove("hidden");
      pendingTableBody.innerHTML = pending
        .map(
          (row) => `
          <tr>
            <td><span class="plate-cell-main mono-num num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderDirectionPill(row["Luồng"])}</td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td class="n mono-num num">${escapeHtml(row["Đồng thuận biển số"])}</td>
            <td class="n mono-num num">${escapeHtml(row["Thời gian nhận diện"])}</td>
          </tr>
        `
        )
        .join("");
    } else {
      pendingSection.classList.add("hidden");
      pendingTableBody.innerHTML = "";
    }

    const matched = typeof data.matched === "number" ? data.matched : records.length;
    renderHistoryTable(records, matched, stats.total_records ?? 0);
  }

  async function fetchManagementOverview() {
    const query = (searchPlateInput.value || "").trim();
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (activeStatusFilter && activeStatusFilter !== "all") {
      params.set("status", activeStatusFilter);
    }
    const qs = params.toString();
    const url = qs ? `/api/management/overview?${qs}` : "/api/management/overview";

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (typeof data.records_version === "number") {
        lastRecordsVersion = data.records_version;
      }
      applyManagementData(data);
    } catch {
      updatePendingBadgeUI(0);
      showBanner(managementAlertBox, "error", "Không kết nối được tới máy chủ FastAPI.");
    }
  }

  tabLinks.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabLinks.forEach((b) => b.setAttribute("aria-selected", "false"));
      btn.setAttribute("aria-selected", "true");
      activeStatusFilter = btn.getAttribute("data-status-filter") || "all";
      currentPage = 1;
      fetchManagementOverview();
    });
  });

  searchPlateInput.addEventListener("input", () => {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      currentPage = 1;
      fetchManagementOverview();
    }, 200);
  });

  btnRefreshManagement.addEventListener("click", async () => {
    btnRefreshManagement.disabled = true;
    try {
      const res = await fetch("/api/management/reconnect", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Chưa kết nối được MySQL.");
      }
      await fetchManagementOverview();
      const flushedMsg =
        data.flushed > 0 ? ` và đồng bộ ${data.flushed} bản ghi chờ` : "";
      showBanner(managementAlertBox, "success", `Đã làm mới dữ liệu từ MySQL${flushedMsg}.`);
    } catch (err) {
      await fetchManagementOverview();
      showBanner(managementAlertBox, "error", err.message);
    } finally {
      btnRefreshManagement.disabled = false;
    }
  });

  btnFlushPending.addEventListener("click", async () => {
    btnFlushPending.disabled = true;
    try {
      const res = await fetch("/api/management/flush-pending", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể đồng bộ bản ghi chờ.");
      }
      await fetchManagementOverview();
      showBanner(
        managementAlertBox,
        "success",
        `Đã đồng bộ ${data.flushed || 0} bản ghi chờ vào MySQL.`
      );
    } catch (err) {
      await fetchManagementOverview();
      showBanner(managementAlertBox, "error", err.message);
    } finally {
      btnFlushPending.disabled = false;
    }
  });

  fetchManagementOverview();
  pollLoop();
})();
