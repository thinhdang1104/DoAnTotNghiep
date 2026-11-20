(() => {
  // Navigation & Topbar elements
  const navRecognition = document.getElementById("nav-recognition");
  const navManagement = document.getElementById("nav-management");
  const navRevenue = document.getElementById("nav-revenue");
  const navItems = [navRecognition, navManagement, navRevenue];
  const views = document.querySelectorAll(".screen-view");
  const streamLiveDot = document.getElementById("stream-live-dot");

  // Screen 1: Full-width Dual Camera (Cam 1 + Cam 2) elements
  const cameraAlertBox = document.getElementById("camera-alert-box");
  const cam1DeviceSelect = document.getElementById("cam1-device-select");
  const cam2DeviceSelect = document.getElementById("cam2-device-select");
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

  // Snapshot modal elements
  const snapshotModal = document.getElementById("snapshot-modal");
  const snapshotModalTitle = document.getElementById("snapshot-modal-title");
  const snapshotModalMeta = document.getElementById("snapshot-modal-meta");
  const modalPlateImg = document.getElementById("modal-plate-img");
  const modalFaceImg = document.getElementById("modal-face-img");
  const btnCloseSnapshotModal = document.getElementById("btn-close-snapshot-modal");

  let activeViewId = "view-recognition";
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
  let selectedCamDeviceIds = { 1: "", 2: "" };
  let activeCamDeviceIds = { 1: null, 2: null };
  let activeCamDeviceLabels = { 1: null, 2: null };
  let camBusy = { 1: false, 2: false };
  let manualStoppingCam = { 1: false, 2: false };
  let trackEndedHandlers = { 1: null, 2: null };
  let lastCamError = { 1: "", 2: "" };
  let hasDiscoveredOnce = false;
  let cameraPermissionGranted = false;
  let deviceChangeBound = false;
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

  function showBanner(box, type, message, durationMs = 0) {
    if (!box) return;
    if (box._hideTimer) {
      clearTimeout(box._hideTimer);
      box._hideTimer = null;
    }
    if (!message) {
      box.className = "notice-banner hidden";
      box.textContent = "";
      return;
    }
    box.className = type ? `notice-banner notice-${type}` : "notice-banner";
    box.textContent = message;
    if (durationMs > 0) {
      box._hideTimer = setTimeout(() => {
        box.className = "notice-banner hidden";
        box.textContent = "";
        box._hideTimer = null;
      }, durationMs);
    }
  }

  function activateView(targetId) {
    activeViewId = targetId;
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

    if (targetId === "view-management" || targetId === "view-revenue") {
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

  function renderDirectionPill(dirText) {
    const str = String(dirText || "Vào bãi");
    if (str.includes("Ra")) {
      return `<span class="pill warn">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill pos">${escapeHtml(str)}</span>`;
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
    // Ẩn ngay hộp cảnh báo (Optimistic UI) để giao diện phản hồi tức thì khi bấm nút
    if (securityAlertBox) {
      securityAlertBox.classList.add("hidden");
    }
    try {
      const res = await fetch("/api/camera/resolve-alert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.message) {
          showBanner(cameraAlertBox, data.type || "warn", data.message, 1000);
        }
      }
      pollCameraStatusOnce();
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
  let browserCamDevices = [];
  let browserStreams = [null, null];
  let browserVideos = [null, null];
  let browserCanvas = null;
  let browserFrameTimer = null;
  let browserInFlight = false;
  let statusPollTimer = null;

  function stopStatusPollLoop() {
    if (statusPollTimer) {
      clearTimeout(statusPollTimer);
      statusPollTimer = null;
    }
  }

  function scheduleLocalStatusPollIfNeeded(active1, active2) {
    stopStatusPollLoop();
    const anyLocalActive =
      (active1 && !browserVideos[0]) || (active2 && !browserVideos[1]);
    if (anyLocalActive) {
      statusPollTimer = setTimeout(async () => {
        statusPollTimer = null;
        await pollCameraStatusOnce();
      }, 320);
    }
  }

  function normalizeVideoInputDevices(rawDevices) {
    const videoInputs = (rawDevices || []).filter(
      (d) => d && d.kind === "videoinput" && String(d.deviceId || "").trim() !== ""
    );
    const baseLabels = videoInputs.map((d, idx) => {
      const cleaned = String(d.label || "").trim();
      return cleaned || `Camera ${idx + 1}`;
    });
    const counts = new Map();
    baseLabels.forEach((lbl) => {
      counts.set(lbl, (counts.get(lbl) || 0) + 1);
    });
    const seen = new Map();
    return videoInputs.map((d, idx) => {
      const base = baseLabels[idx];
      let finalLabel = base;
      if ((counts.get(base) || 0) > 1) {
        const nextIdx = (seen.get(base) || 0) + 1;
        seen.set(base, nextIdx);
        finalLabel = `${base} (${nextIdx})`;
      }
      return {
        deviceId: String(d.deviceId),
        label: finalLabel,
      };
    });
  }

  function formatMediaError(err, deviceLabel = "") {
    if (
      !window.isSecureContext ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== "function" ||
      typeof navigator.mediaDevices.enumerateDevices !== "function"
    ) {
      return "Trình duyệt không hỗ trợ WebRTC Camera hoặc trang không ở ngữ cảnh bảo mật (HTTPS / localhost).";
    }
    const name = (err && err.name) || "";
    if (
      name === "NotAllowedError" ||
      name === "PermissionDeniedError" ||
      name === "SecurityError"
    ) {
      const inIframe = window.self !== window.top;
      return inIframe
        ? "Trình duyệt chặn quyền Camera trong khung nhúng. Vui lòng cấp quyền Camera trên thanh địa chỉ hoặc mở trực tiếp https://minhthinh-doan.hf.space"
        : "Bạn đã từ chối cấp quyền truy cập Camera. Vui lòng cho phép quyền Camera trên thanh địa chỉ trình duyệt rồi thử lại.";
    }
    if (
      name === "NotFoundError" ||
      name === "DevicesNotFoundError" ||
      name === "OverconstrainedError"
    ) {
      return deviceLabel
        ? `Thiết bị "${deviceLabel}" không còn tồn tại hoặc không đáp ứng kết nối. Vui lòng chọn thiết bị khác.`
        : "Không tìm thấy thiết bị Camera nào được kết nối với máy của bạn.";
    }
    if (name === "NotReadableError" || name === "TrackStartError") {
      return deviceLabel
        ? `Thiết bị "${deviceLabel}" đang bận hoặc không mở được (có thể đang được dùng bởi ứng dụng khác).`
        : "Thiết bị Camera đang bận hoặc không mở được.";
    }
    return (err && err.message) || "Không thể truy cập thiết bị Camera.";
  }

  function getSelectedDeviceLabel(camId) {
    if (activeCamDeviceLabels[camId]) {
      return activeCamDeviceLabels[camId];
    }
    const devId = selectedCamDeviceIds[camId];
    if (!devId) return "";
    const found = browserCamDevices.find((d) => d.deviceId === devId);
    return found ? found.label : "";
  }

  function setPlaceholderText(camId, text) {
    const phEl = camId === 1 ? cam1Placeholder : cam2Placeholder;
    if (!phEl) return;
    const span = phEl.querySelector(".standby-text");
    if (span) {
      span.textContent = text;
    }
  }

  function renderDeviceSelects() {
    [1, 2].forEach((camId) => {
      const selectEl = camId === 1 ? cam1DeviceSelect : cam2DeviceSelect;
      if (!selectEl) return;
      const otherId = 3 - camId;
      const otherReservedId = activeCamDeviceIds[otherId];
      const currentVal = selectedCamDeviceIds[camId] || "";

      const optionsHtml = [];
      if (browserCamDevices.length === 0) {
        optionsHtml.push(
          `<option value="">-- Bấm "Tìm camera" --</option>`
        );
      } else {
        optionsHtml.push(
          `<option value="">-- Chọn thiết bị camera --</option>`
        );
        browserCamDevices.forEach((dev) => {
          const usedByOther = Boolean(
            otherReservedId && otherReservedId === dev.deviceId
          );
          const suffix = usedByOther ? ` (Đang dùng ở Cam ${otherId})` : "";
          const selectedAttr = currentVal === dev.deviceId ? " selected" : "";
          const disabledAttr = usedByOther ? " disabled" : "";
          optionsHtml.push(
            `<option value="${escapeHtml(dev.deviceId)}"${selectedAttr}${disabledAttr}>${escapeHtml(dev.label + suffix)}</option>`
          );
        });
      }

      selectEl.innerHTML = optionsHtml.join("");
      selectEl.value = currentVal;
      selectEl.disabled = Boolean(
        camStreaming[camId] || camBusy[camId] || browserCamDevices.length === 0
      );
    });
  }

  function refreshCamControlButtons() {
    const anyBusy = Boolean(camBusy[1] || camBusy[2] || isStartingCamera);
    const active1 = Boolean(camStreaming[1]);
    const active2 = Boolean(camStreaming[2]);
    isCameraStreaming = Boolean(active1 || active2);

    if (streamLiveDot) {
      streamLiveDot.classList.toggle("online", isCameraStreaming);
    }

    [1, 2].forEach((camId) => {
      const startBtn = camId === 1 ? btnCam1Start : btnCam2Start;
      const stopBtn = camId === 1 ? btnCam1Stop : btnCam2Stop;
      const otherId = 3 - camId;
      const selId = selectedCamDeviceIds[camId] || "";
      const isUsedByOther = Boolean(
        selId && activeCamDeviceIds[otherId] && activeCamDeviceIds[otherId] === selId
      );
      const canConnect = Boolean(
        !camStreaming[camId] &&
          !camBusy[camId] &&
          browserCamDevices.length > 0 &&
          selId &&
          !isUsedByOther
      );
      if (startBtn) startBtn.disabled = !canConnect;
      if (stopBtn) stopBtn.disabled = Boolean(!camStreaming[camId] || camBusy[camId]);
    });

    if (btnStartCamera) {
      btnStartCamera.disabled = Boolean(
        anyBusy || (active1 && active2) || browserCamDevices.length === 0
      );
    }
    if (btnStopCamera) {
      btnStopCamera.disabled = Boolean(anyBusy || !isCameraStreaming);
    }

    if (liveFlowPill && (!latchStatusBox || latchStatusBox.classList.contains("hidden"))) {
      if (active1 && active2) {
        liveFlowPill.className = "pill pos";
        liveFlowPill.textContent = "2 Camera đối xứng (Chéo luồng)";
      } else if (active1) {
        liveFlowPill.className = "pill warn";
        liveFlowPill.textContent = `Chế độ 1 Cam dự phòng (Cam 1 · ${activeCamDeviceLabels[1] || "Đang bật"})`;
      } else if (active2) {
        liveFlowPill.className = "pill warn";
        liveFlowPill.textContent = `Chế độ 1 Cam dự phòng (Cam 2 · ${activeCamDeviceLabels[2] || "Đang bật"})`;
      } else {
        liveFlowPill.className = "pill pos";
        liveFlowPill.textContent = "2 Camera độc lập";
      }
    }
  }

  function updateIdleBadgeForCam(camId) {
    if (camStreaming[camId]) return;
    const pillEl = camId === 1 ? cam1VotePill : cam2VotePill;
    if (!pillEl) return;
    const lbl = getSelectedDeviceLabel(camId);
    pillEl.className = "pill mono-num num";
    pillEl.textContent = lbl ? `${lbl} · Ngắt` : "Chưa chọn thiết bị · Ngắt";
  }

  function attachDeviceChangeListenerOnce() {
    if (deviceChangeBound) return;
    if (
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.addEventListener === "function"
    ) {
      deviceChangeBound = true;
      navigator.mediaDevices.addEventListener("devicechange", () => {
        discoverCameraDevices({
          requestPermission: false,
          isInitialAssign: false,
        }).catch(() => {});
      });
    }
  }

  async function discoverCameraDevices({
    requestPermission = false,
    isInitialAssign = false,
  } = {}) {
    if (
      !window.isSecureContext ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== "function" ||
      typeof navigator.mediaDevices.enumerateDevices !== "function"
    ) {
      throw new Error(formatMediaError(null));
    }

    attachDeviceChangeListenerOnce();

    let rawDevices = await navigator.mediaDevices.enumerateDevices();
    const hasLabeledVideo = rawDevices.some(
      (d) =>
        d &&
        d.kind === "videoinput" &&
        String(d.deviceId || "").trim() !== "" &&
        String(d.label || "").trim() !== ""
    );
    const hasActiveStream = Boolean(browserStreams[0] || browserStreams[1]);
    if (hasLabeledVideo || hasActiveStream) {
      cameraPermissionGranted = true;
    }

    if (requestPermission && !cameraPermissionGranted) {
      let tempStream = null;
      try {
        tempStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
        cameraPermissionGranted = true;
      } catch (err) {
        if (
          err &&
          (err.name === "NotAllowedError" ||
            err.name === "PermissionDeniedError" ||
            err.name === "SecurityError")
        ) {
          cameraPermissionGranted = false;
        }
        throw new Error(formatMediaError(err));
      } finally {
        if (tempStream) {
          tempStream.getTracks().forEach((t) => t.stop());
        }
      }
      rawDevices = await navigator.mediaDevices.enumerateDevices();
    }

    browserCamDevices = normalizeVideoInputDevices(rawDevices);

    // Giữ nguyên lựa chọn hiện tại nếu deviceId vẫn còn tồn tại; không tự ý đổi sang thiết bị khác nếu bị rút
    [1, 2].forEach((camId) => {
      if (camStreaming[camId] || camBusy[camId]) {
        if (activeCamDeviceIds[camId]) {
          selectedCamDeviceIds[camId] = activeCamDeviceIds[camId];
        }
        return;
      }
      const prevId = selectedCamDeviceIds[camId];
      if (prevId) {
        const stillExists = browserCamDevices.some((d) => d.deviceId === prevId);
        if (!stillExists) {
          selectedCamDeviceIds[camId] = "";
        }
      }
    });

    if (!hasDiscoveredOnce && isInitialAssign && browserCamDevices.length > 0) {
      hasDiscoveredOnce = true;
      if (!selectedCamDeviceIds[1] && !activeCamDeviceIds[1]) {
        selectedCamDeviceIds[1] = browserCamDevices[0].deviceId;
      }
      if (!selectedCamDeviceIds[2] && !activeCamDeviceIds[2]) {
        const secondDev = browserCamDevices.find(
          (d) => d.deviceId !== selectedCamDeviceIds[1]
        );
        selectedCamDeviceIds[2] = secondDev ? secondDev.deviceId : "";
      }
    }

    renderDeviceSelects();
    updateIdleBadgeForCam(1);
    updateIdleBadgeForCam(2);
    refreshCamControlButtons();
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
      video.srcObject = null;
      video.remove();
      throw new Error("Thiết bị camera không trả về khung hình (videoWidth = 0).");
    }
    return { stream, video };
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
      const img2 = v2 ? captureVideoToJpegDataUrl(v2) : null;
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
          if (out.status) {
            await applyCameraStatus(out.status);
          }
        }
      } catch (_) {
        // Bỏ qua lỗi mạng tạm thời
      } finally {
        browserInFlight = false;
      }
    }, 140);
  }

  function detachTrackEndedHandler(camId, stream) {
    const handler = trackEndedHandlers[camId];
    if (handler && stream) {
      stream.getVideoTracks().forEach((t) => {
        try {
          t.removeEventListener("ended", handler);
        } catch (_) {}
      });
    }
    trackEndedHandlers[camId] = null;
  }

  function attachTrackEndedHandler(camId, stream, deviceLabel) {
    const slot = camId - 1;
    detachTrackEndedHandler(camId, stream);
    const tracks = stream ? stream.getVideoTracks() : [];
    if (!tracks.length) return;

    const handler = () => {
      if (manualStoppingCam[camId]) return;
      if (browserStreams[slot] !== stream) return;
      handleUnexpectedTrackEnded(camId, deviceLabel);
    };
    trackEndedHandlers[camId] = handler;
    tracks.forEach((t) => {
      try {
        t.addEventListener("ended", handler, { once: true });
      } catch (_) {
        t.onended = handler;
      }
    });
  }

  async function handleUnexpectedTrackEnded(camId, lostLabel) {
    const labelText = lostLabel || activeCamDeviceLabels[camId] || `Cam ${camId}`;
    stopBrowserWebRTCForCam(camId);
    hideCamStreamUI(camId);
    setPlaceholderText(
      camId,
      `Thiết bị "${labelText}" đã bị ngắt kết nối. Vui lòng chọn thiết bị và kết nối lại.`
    );
    updateIdleBadgeForCam(camId);
    renderDeviceSelects();
    refreshCamControlButtons();
    showBanner(
      cameraAlertBox,
      "error",
      `Cam ${camId} (${labelText}) đã bị ngắt kết nối thiết bị. Vui lòng kiểm tra lại camera và kết nối lại.`
    );
    try {
      await fetch(`/api/camera/${camId}/stop`, { method: "POST" });
    } catch (_) {}
    try {
      await discoverCameraDevices({
        requestPermission: false,
        isInitialAssign: false,
      });
    } catch (_) {}
  }

  function stopBrowserWebRTCForCam(camId) {
    const slot = camId - 1;
    const otherSlot = 1 - slot;
    const s = browserStreams[slot];
    const v = browserVideos[slot];

    manualStoppingCam[camId] = true;
    try {
      if (s) {
        detachTrackEndedHandler(camId, s);
      }
      browserStreams[slot] = null;
      browserVideos[slot] = null;
      activeCamDeviceIds[camId] = null;
      activeCamDeviceLabels[camId] = null;

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
    } finally {
      manualStoppingCam[camId] = false;
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
      imgEl.src = "";
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

  async function startSingleCamUI(camId, { silentSuccessBanner = false } = {}) {
    if (camBusy[camId] || camStreaming[camId]) {
      return Boolean(camStreaming[camId]);
    }
    const slot = camId - 1;
    const otherId = 3 - camId;
    const selectEl = camId === 1 ? cam1DeviceSelect : cam2DeviceSelect;
    lastCamError[camId] = "";

    let selectedId =
      (selectEl && selectEl.value) || selectedCamDeviceIds[camId] || "";

    if (browserCamDevices.length === 0) {
      try {
        await discoverCameraDevices({
          requestPermission: true,
          isInitialAssign: true,
        });
        selectedId =
          (selectEl && selectEl.value) || selectedCamDeviceIds[camId] || "";
      } catch (err) {
        lastCamError[camId] = err.message;
        setPlaceholderText(camId, err.message);
        showBanner(cameraAlertBox, "error", `Cam ${camId}: ${err.message}`);
        return false;
      }
    }

    if (browserCamDevices.length === 0) {
      const msg = "Không tìm thấy thiết bị Camera nào để kết nối.";
      lastCamError[camId] = msg;
      setPlaceholderText(camId, msg);
      showBanner(cameraAlertBox, "error", `Cam ${camId}: ${msg}`);
      return false;
    }

    if (!selectedId) {
      let msg = `Vui lòng chọn thiết bị camera cho Cam ${camId} trước khi kết nối.`;
      if (
        browserCamDevices.length === 1 &&
        activeCamDeviceIds[otherId] === browserCamDevices[0].deviceId
      ) {
        msg = `Máy chỉ có 1 thiết bị Camera (${browserCamDevices[0].label}) và đang được sử dụng ở Cam ${otherId}. Không thể mở cùng 1 thiết bị cho cả 2 ô.`;
      }
      lastCamError[camId] = msg;
      setPlaceholderText(camId, msg);
      showBanner(cameraAlertBox, "error", msg);
      return false;
    }

    if (
      activeCamDeviceIds[otherId] &&
      activeCamDeviceIds[otherId] === selectedId
    ) {
      const dupDev = browserCamDevices.find((d) => d.deviceId === selectedId);
      const dupName = (dupDev && dupDev.label) || "đã chọn";
      const msg = `Thiết bị "${dupName}" đang được sử dụng ở Cam ${otherId}. Vui lòng chọn thiết bị khác cho Cam ${camId}.`;
      lastCamError[camId] = msg;
      setPlaceholderText(camId, msg);
      showBanner(cameraAlertBox, "error", msg);
      return false;
    }

    // Đặt khóa & giữ chỗ thiết bị ĐỒNG BỘ trước lệnh await đầu tiên để chống race condition khi bấm 2 ô liên tiếp
    camBusy[camId] = true;
    selectedCamDeviceIds[camId] = selectedId;
    activeCamDeviceIds[camId] = selectedId;
    renderDeviceSelects();
    refreshCamControlButtons();

    let openedCamObj = null;
    try {
      // Kiểm tra lại danh sách thiết bị hiện có để chắc chắn deviceId vẫn còn tồn tại
      const latestRaw = await navigator.mediaDevices.enumerateDevices();
      browserCamDevices = normalizeVideoInputDevices(latestRaw);
      const targetDev = browserCamDevices.find((d) => d.deviceId === selectedId);
      if (!targetDev) {
        selectedCamDeviceIds[camId] = "";
        throw new Error(
          `Thiết bị đã chọn cho Cam ${camId} không còn tồn tại. Vui lòng chọn thiết bị khác.`
        );
      }

      activeCamDeviceLabels[camId] = targetDev.label;
      showBanner(
        cameraAlertBox,
        "",
        `Đang kết nối Cam ${camId} (${targetDev.label})...`
      );

      // Mở ĐÚNG thiết bị bằng exact deviceId — tuyệt đối không fallback sang thiết bị khác hay video: true
      try {
        openedCamObj = await tryOpenStreamWithVideo({
          video: { deviceId: { exact: selectedId } },
          audio: false,
        });
      } catch (openErr) {
        throw new Error(formatMediaError(openErr, targetDev.label));
      }

      // Đăng ký phiên browser rõ ràng với backend (prefer_browser: true)
      const res = await fetch(`/api/camera/${camId}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_index: camId - 1,
          prefer_browser: true,
        }),
      });
      let data = {};
      try {
        data = await res.json();
      } catch (_) {}
      if (!res.ok) {
        throw new Error(
          data.detail || `Không thể đăng ký phiên Cam ${camId} trên máy chủ.`
        );
      }

      browserStreams[slot] = openedCamObj.stream;
      browserVideos[slot] = openedCamObj.video;
      openedCamObj = null; // đã bàn giao cho browserStreams[slot]
      browserWebRTCActive = Boolean(browserVideos[0] || browserVideos[1]);
      camStreaming[camId] = true;
      isCameraStreaming = Boolean(camStreaming[1] || camStreaming[2]);

      attachTrackEndedHandler(camId, browserStreams[slot], targetDev.label);

      const liveVideoEl = camId === 1 ? cam1LiveVideo : cam2LiveVideo;
      if (liveVideoEl) {
        liveVideoEl.srcObject = browserStreams[slot];
        try {
          await liveVideoEl.play();
        } catch (_) {}
      }

      revealCamImagesIfReady();
      ensureBrowserFrameLoop();

      const votePillEl = camId === 1 ? cam1VotePill : cam2VotePill;
      if (votePillEl) {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `${targetDev.label} · Đang quét`;
      }

      if (!silentSuccessBanner) {
        showBanner(
          cameraAlertBox,
          "success",
          `Đã kết nối Cam ${camId}: ${targetDev.label}`,
          1000
        );
      }
      return true;
    } catch (err) {
      if (openedCamObj) {
        try {
          openedCamObj.stream.getTracks().forEach((t) => t.stop());
        } catch (_) {}
        try {
          openedCamObj.video.srcObject = null;
          openedCamObj.video.remove();
        } catch (_) {}
        openedCamObj = null;
      }
      stopBrowserWebRTCForCam(camId);
      hideCamStreamUI(camId);
      // Giữ lại lựa chọn trong dropdown (nếu thiết bị vẫn còn trong danh sách) để người dùng sửa hoặc thử lại
      if (
        selectedId &&
        browserCamDevices.some((d) => d.deviceId === selectedId)
      ) {
        selectedCamDeviceIds[camId] = selectedId;
      }
      lastCamError[camId] = err.message;
      setPlaceholderText(camId, `Lỗi kết nối Cam ${camId}: ${err.message}`);
      updateIdleBadgeForCam(camId);
      if (!silentSuccessBanner) {
        showBanner(cameraAlertBox, "error", `Cam ${camId}: ${err.message}`);
      }
      return false;
    } finally {
      camBusy[camId] = false;
      renderDeviceSelects();
      refreshCamControlButtons();
    }
  }

  async function stopSingleCamUI(camId) {
    if (camBusy[camId]) return;
    camBusy[camId] = true;
    renderDeviceSelects();
    refreshCamControlButtons();

    stopBrowserWebRTCForCam(camId);
    hideCamStreamUI(camId);
    setPlaceholderText(camId, `Chưa kết nối Cam ${camId}`);
    updateIdleBadgeForCam(camId);
    if (!camStreaming[1] && !camStreaming[2]) {
      stopStatusPollLoop();
    }
    try {
      await fetch(`/api/camera/${camId}/stop`, { method: "POST" });
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    } finally {
      camBusy[camId] = false;
      renderDeviceSelects();
      refreshCamControlButtons();
    }
    await pollCameraStatusOnce();
  }

  [1, 2].forEach((camId) => {
    const selectEl = camId === 1 ? cam1DeviceSelect : cam2DeviceSelect;
    if (!selectEl) return;
    selectEl.addEventListener("change", () => {
      if (camStreaming[camId] || camBusy[camId]) {
        selectEl.value = activeCamDeviceIds[camId] || selectedCamDeviceIds[camId] || "";
        return;
      }
      selectedCamDeviceIds[camId] = selectEl.value || "";
      updateIdleBadgeForCam(camId);
      refreshCamControlButtons();
    });
  });

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
    showBanner(cameraAlertBox, "", "Đang xin quyền và tìm thiết bị camera...");
    try {
      const devices = await discoverCameraDevices({
        requestPermission: true,
        isInitialAssign: true,
      });
      if (devices.length === 0) {
        setPlaceholderText(1, "Không tìm thấy thiết bị Camera nào.");
        setPlaceholderText(2, "Không tìm thấy thiết bị Camera nào.");
        showBanner(
          cameraAlertBox,
          "error",
          "Không tìm thấy thiết bị Camera nào được kết nối với máy của bạn."
        );
      } else if (devices.length === 1) {
        showBanner(
          cameraAlertBox,
          "warn",
          `Tìm thấy 1 thiết bị: ${devices[0].label}. Vì chỉ có 1 thiết bị nên chỉ có thể bật 1 ô (Chế độ 1 Camera dự phòng), không thể bật đồng thời cả 2 ô.`
        );
      } else {
        const names = devices.map((d) => d.label).join(", ");
        showBanner(
          cameraAlertBox,
          "success",
          `Tìm thấy ${devices.length} thiết bị: ${names}. Hãy chọn thiết bị cho Cam 1 / Cam 2 và bấm "Kết nối" hoặc "Bật cả 2".`
        );
      }
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    } finally {
      btnScanCamera.disabled = false;
      renderDeviceSelects();
      refreshCamControlButtons();
    }
  });

  btnStartCamera.addEventListener("click", async () => {
    if (camBusy[1] || camBusy[2] || isStartingCamera) return;
    btnStartCamera.disabled = true;
    try {
      if (browserCamDevices.length === 0) {
        await discoverCameraDevices({
          requestPermission: true,
          isInitialAssign: true,
        });
      }
      if (browserCamDevices.length < 2) {
        const msg =
          browserCamDevices.length === 1
            ? `Chỉ tìm thấy 1 thiết bị (${browserCamDevices[0].label}). Để dùng "Bật cả 2", máy cần kết nối ít nhất 2 thiết bị camera khác nhau (hoặc bấm "Kết nối" ở 1 ô để dùng chế độ 1 Camera dự phòng).`
            : "Không tìm thấy đủ 2 thiết bị camera để bật đồng thời cả 2 ô.";
        showBanner(cameraAlertBox, "error", msg);
        return;
      }

      const dev1 = camStreaming[1]
        ? activeCamDeviceIds[1]
        : (cam1DeviceSelect && cam1DeviceSelect.value) || selectedCamDeviceIds[1] || "";
      const dev2 = camStreaming[2]
        ? activeCamDeviceIds[2]
        : (cam2DeviceSelect && cam2DeviceSelect.value) || selectedCamDeviceIds[2] || "";

      if (!dev1 || !dev2) {
        showBanner(
          cameraAlertBox,
          "error",
          'Vui lòng chọn đủ 2 thiết bị camera cho Cam 1 và Cam 2 trước khi bấm "Bật cả 2".'
        );
        return;
      }
      if (dev1 === dev2) {
        showBanner(
          cameraAlertBox,
          "error",
          "Cam 1 và Cam 2 không được chọn cùng một thiết bị camera. Vui lòng chọn 2 thiết bị khác nhau."
        );
        return;
      }

      const wasStreaming1 = Boolean(camStreaming[1]);
      const wasStreaming2 = Boolean(camStreaming[2]);
      const ok1 = wasStreaming1
        ? true
        : await startSingleCamUI(1, { silentSuccessBanner: true });
      const ok2 = wasStreaming2
        ? true
        : await startSingleCamUI(2, { silentSuccessBanner: true });

      if (ok1 && ok2) {
        showBanner(
          cameraAlertBox,
          "success",
          `Đã kết nối cả 2 Camera: Cam 1 (${activeCamDeviceLabels[1]}) & Cam 2 (${activeCamDeviceLabels[2]}).`,
          1200
        );
      } else if (ok1 && !ok2) {
        showBanner(
          cameraAlertBox,
          "error",
          `Cam 1 (${activeCamDeviceLabels[1]}) đang hoạt động, nhưng Cam 2 kết nối thất bại: ${lastCamError[2] || "Không mở được thiết bị."}`
        );
      } else if (!ok1 && ok2) {
        showBanner(
          cameraAlertBox,
          "error",
          `Cam 2 (${activeCamDeviceLabels[2]}) đang hoạt động, nhưng Cam 1 kết nối thất bại: ${lastCamError[1] || "Không mở được thiết bị."}`
        );
      } else {
        showBanner(
          cameraAlertBox,
          "error",
          `Không thể kết nối cả 2 Camera. Cam 1: ${lastCamError[1] || "Lỗi"} | Cam 2: ${lastCamError[2] || "Lỗi"}`
        );
      }
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    } finally {
      renderDeviceSelects();
      refreshCamControlButtons();
    }
  });

  btnStopCamera.addEventListener("click", async () => {
    if (camBusy[1] || camBusy[2]) return;
    btnStopCamera.disabled = true;
    isStartingCamera = true;
    stopStatusPollLoop();
    stopBrowserWebRTC();
    hideCamStreamUI(1);
    hideCamStreamUI(2);
    setPlaceholderText(1, "Chưa kết nối Cam 1");
    setPlaceholderText(2, "Chưa kết nối Cam 2");
    updateIdleBadgeForCam(1);
    updateIdleBadgeForCam(2);
    renderDeviceSelects();
    refreshCamControlButtons();
    try {
      await fetch("/api/camera/stop", { method: "POST" });
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    } finally {
      isStartingCamera = false;
      renderDeviceSelects();
      refreshCamControlButtons();
    }
    await pollCameraStatusOnce();
  });

  function updateSingleCamReadout(camId, camData, votePillEl, plateValueEl, faceValueEl, running) {
    const plates = (camData && camData.current_plates) || [];
    const faces = (camData && camData.current_faces) || [];

    if (plateValueEl) {
      if (running && plates.length > 0) {
        plateValueEl.textContent = `Biển: ${plates.join(", ")}`;
        plateValueEl.classList.remove("hidden");
      } else {
        plateValueEl.classList.add("hidden");
      }
    }

    if (faceValueEl) {
      if (running && faces.length > 0) {
        const bestConf = Math.round(Math.max(...faces) * 100);
        faceValueEl.textContent = `Mặt: ${bestConf}%`;
        faceValueEl.classList.remove("hidden");
      } else {
        faceValueEl.classList.add("hidden");
      }
    }

    if (votePillEl) {
      const devLabel =
        activeCamDeviceLabels[camId] ||
        getSelectedDeviceLabel(camId) ||
        (camData && camData.mode === "local"
          ? `Camera nội bộ #${camData.device_index}`
          : "Chưa chọn thiết bị");
      if (!running) {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `${devLabel} · Ngắt`;
      } else if (camData && camData.vote) {
        const pct = Math.round(camData.vote.vote_share * 100);
        votePillEl.className = "pill warn mono-num num";
        votePillEl.textContent = `${camData.vote.candidate} (${camData.vote.vote_count}/${camData.vote.sample_count} · ${pct}%)`;
      } else {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `${devLabel} · Đang quét`;
      }
    }
  }

  function syncSingleCamUI(
    camId,
    camState,
    imgEl,
    phEl
  ) {
    const slot = camId - 1;
    const ownsBrowserStream = Boolean(browserVideos[slot] && browserStreams[slot]);
    const isLocalActive = Boolean(
      camState && camState.active && camState.mode === "local"
    );
    const isActiveHere = Boolean(ownsBrowserStream || isLocalActive);

    if (isActiveHere) {
      if (!camStreaming[camId]) {
        camStreaming[camId] = true;
        if (isLocalActive && !ownsBrowserStream && imgEl && phEl) {
          imgEl.src = `/api/camera/stream/${camId}?t=${Date.now()}`;
          imgEl.classList.remove("hidden");
          phEl.classList.add("hidden");
        } else {
          revealCamImagesIfReady();
        }
      }
    } else {
      if (camStreaming[camId] && !camBusy[camId]) {
        stopBrowserWebRTCForCam(camId);
        hideCamStreamUI(camId);
      }
      if (
        camState &&
        camState.active &&
        camState.mode === "browser" &&
        !ownsBrowserStream &&
        !camBusy[camId]
      ) {
        setPlaceholderText(
          camId,
          `Cam ${camId} đang mở ở phiên/tab khác — Chọn thiết bị và bấm "Kết nối" để phát từ tab này`
        );
      }
    }
    return isActiveHere;
  }

  async function applyCameraStatus(state) {
    if (!state || isStartingCamera) return;

    const active1 = syncSingleCamUI(
      1,
      state.cam1,
      cam1StreamImg,
      cam1Placeholder
    );
    const active2 = syncSingleCamUI(
      2,
      state.cam2,
      cam2StreamImg,
      cam2Placeholder
    );

    renderDeviceSelects();
    refreshCamControlButtons();

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
        state.gate_feedback.message,
        1000
      );
    }

    updateSingleCamReadout(
      1,
      state.cam1,
      cam1VotePill,
      cam1PlateValue,
      cam1FaceValue,
      active1
    );
    updateSingleCamReadout(
      2,
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
        liveFlowPill.textContent =
          state.latched.plate_cam === state.latched.required_face_cam
            ? `Đang đón xe ${isIn ? "VÀO" : "RA"} (1 Cam · Cam ${state.latched.plate_cam})`
            : `Đang đón xe ${isIn ? "VÀO" : "RA"} (Biển Cam ${state.latched.plate_cam} + Mặt Cam ${state.latched.required_face_cam})`;
      }
    } else {
      latchStatusBox.classList.add("hidden");
      if (cam1UnitCard) cam1UnitCard.classList.remove("cam-target-highlight");
      if (cam2UnitCard) cam2UnitCard.classList.remove("cam-target-highlight");
      refreshCamControlButtons();
    }

    // Security Alert UI (Face mismatch on exit)
    if (state.security_alert) {
      securityAlertBox.classList.remove("hidden");
      alertScorePill.textContent = `Độ khớp: ${state.security_alert.match_score_pct}`;
      alertDetailText.textContent =
        `Xe ${state.security_alert.plate_number} (gửi lúc ${state.security_alert.entry_time}) ` +
        `có khuôn mặt người lấy xe LỆCH so với lúc gửi xe vào bãi (Cosine ${state.security_alert.match_score_pct} < 65%).`;
    } else {
      securityAlertBox.classList.add("hidden");
    }

    voteAmbiguousWarning.classList.toggle("hidden", !state.ambiguous_frame);

    if (
      typeof state.records_version === "number" &&
      state.records_version !== lastRecordsVersion
    ) {
      lastRecordsVersion = state.records_version;
      if (activeViewId === "view-management" || activeViewId === "view-revenue") {
        fetchManagementOverview();
      }
    }

    scheduleLocalStatusPollIfNeeded(active1, active2);
  }

  async function pollCameraStatusOnce() {
    if (isStartingCamera) return;
    try {
      const res = await fetch("/api/camera/status");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const state = await res.json();
      await applyCameraStatus(state);
    } catch {
      // Giữ nguyên số lượng bản ghi chờ hiện tại nếu lỗi mạng tạm thời
    }
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
  function makeFallbackPlateSvg(plateText) {
    const raw = String(plateText || "59A1-12345").trim();
    const parts = raw.split("-");
    const topLine = escapeHtml(parts[0] || raw);
    const botLine = escapeHtml(parts[1] || "");
    const svg = botLine
      ? `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="96" viewBox="0 0 200 96">
          <rect x="3" y="3" width="194" height="90" rx="8" fill="#f8fafc" stroke="#1e293b" stroke-width="4"/>
          <rect x="7" y="7" width="186" height="82" rx="5" fill="none" stroke="#0f172a" stroke-width="1.5"/>
          <text x="100" y="42" text-anchor="middle" font-family="JetBrains Mono, monospace" font-weight="800" font-size="28" fill="#0f172a">${topLine}</text>
          <text x="100" y="78" text-anchor="middle" font-family="JetBrains Mono, monospace" font-weight="800" font-size="28" fill="#0f172a">${botLine}</text>
        </svg>`
      : `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="96" viewBox="0 0 200 96">
          <rect x="3" y="3" width="194" height="90" rx="8" fill="#f8fafc" stroke="#1e293b" stroke-width="4"/>
          <text x="100" y="58" text-anchor="middle" font-family="JetBrains Mono, monospace" font-weight="800" font-size="24" fill="#0f172a">${topLine}</text>
        </svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }

  function makeFallbackFaceSvg(plateText, faceLabel) {
    const seed = Array.from(String(plateText || "X")).reduce((s, c) => s + c.charCodeAt(0), 0);
    const hues = [200, 265, 150, 32, 330, 185];
    const hue = hues[seed % hues.length];
    const conf = escapeHtml(String(faceLabel || "").replace(/[^0-9%]/g, "") || "-");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
      <rect width="160" height="160" rx="16" fill="hsl(${hue}, 35%, 16%)"/>
      <circle cx="80" cy="58" r="28" fill="hsl(${hue}, 70%, 65%)"/>
      <path d="M32 138 C32 102, 128 102, 128 138" fill="hsl(${hue}, 70%, 65%)"/>
      <rect x="14" y="14" width="132" height="132" rx="10" fill="none" stroke="#d946ef" stroke-width="3" stroke-dasharray="10 6"/>
      <rect x="86" y="118" width="56" height="24" rx="5" fill="rgba(6,7,9,0.82)"/>
      <text x="114" y="135" text-anchor="middle" font-family="JetBrains Mono, monospace" font-weight="700" font-size="13" fill="#f0abfc">${conf}</text>
    </svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }

  function getRowSnapshots(row) {
    const plateImg = row.plate_image || makeFallbackPlateSvg(row["Biển số"]);
    const faceImg = row.face_image || makeFallbackFaceSvg(row["Biển số"], row["Khuôn mặt"]);
    return { plateImg, faceImg };
  }

  function renderSnapshotCell(row) {
    const { plateImg, faceImg } = getRowSnapshots(row);
    const plate = escapeHtml(row["Biển số"]);
    const direction = escapeHtml(row["Luồng"]);
    const time = escapeHtml(row["Thời gian nhận diện"]);
    const match = escapeHtml(row["Đối chiếu"] || "-");
    return `
      <div class="snapshot-cell">
        <button type="button" class="snap-thumb-btn" data-plate="${plate}" data-dir="${direction}" data-time="${time}" data-match="${match}" title="Bấm để phóng to ảnh cắt Biển số & Khuôn mặt">
          <img class="snap-plate-img" src="${plateImg}" alt="Biển số ${plate}" loading="lazy" />
          <img class="snap-face-img" src="${faceImg}" alt="Khuôn mặt ${plate}" loading="lazy" />
        </button>
      </div>
    `;
  }

  function openSnapshotModal(info) {
    if (!snapshotModal || !info) return;
    if (snapshotModalTitle) {
      snapshotModalTitle.textContent = `Ảnh cắt: ${info.plate} (${info.direction})`;
    }
    if (snapshotModalMeta) {
      snapshotModalMeta.textContent = `Thời gian: ${info.time} · Đối chiếu FaceNet: ${info.match}`;
    }
    if (modalPlateImg) modalPlateImg.src = info.plateImg || "";
    if (modalFaceImg) modalFaceImg.src = info.faceImg || "";
    snapshotModal.classList.remove("hidden");
  }

  function closeSnapshotModal() {
    if (!snapshotModal) return;
    snapshotModal.classList.add("hidden");
  }

  if (btnCloseSnapshotModal) {
    btnCloseSnapshotModal.addEventListener("click", closeSnapshotModal);
  }
  if (snapshotModal) {
    snapshotModal.addEventListener("click", (e) => {
      if (e.target === snapshotModal) closeSnapshotModal();
    });
  }
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button.snap-thumb-btn");
    if (!btn) return;
    const pImg = btn.querySelector(".snap-plate-img");
    const fImg = btn.querySelector(".snap-face-img");
    openSnapshotModal({
      plate: btn.getAttribute("data-plate") || "-",
      direction: btn.getAttribute("data-dir") || "-",
      time: btn.getAttribute("data-time") || "-",
      match: btn.getAttribute("data-match") || "-",
      plateImg: pImg ? pImg.src : "",
      faceImg: fImg ? fImg.src : "",
    });
  });

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
        paginationRangeText.textContent = "Hiển thị 0–0 / 0 bản ghi (tối đa 200 bản ghi mới nhất)";
      }
      paginationControls.innerHTML = "";
      return;
    }

    const startIdx = (currentPage - 1) * pageSize + 1;
    const endIdx = Math.min(totalItems, currentPage * pageSize);
    if (paginationRangeText) {
      paginationRangeText.textContent = `Hiển thị ${startIdx}–${endIdx} / ${totalItems} bản ghi (tối đa 200 bản ghi mới nhất)`;
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
      ledgerCountText.textContent = `${cachedMatchedCount} / ${cachedTotalRecords} bản ghi (tối đa 200 bản ghi mới nhất)`;
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
          <td colspan="5">Không có bản ghi nào khớp điều kiện lọc.</td>
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
            <td>${renderSnapshotCell(row)}</td>
            <td>${renderDirectionPill(row["Luồng"])}</td>
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
    const stats = data.stats || {
      total_records: records.length,
      today_records: 0,
      in_parking: 0,
      total_in: 0,
      total_out: 0,
    };

    if (statInParking) statInParking.textContent = String(stats.in_parking ?? 0);
    statTodayRecords.textContent = String(stats.today_records ?? 0);
    statTotalRecords.textContent = String(stats.total_records ?? 0);

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
    params.set("limit", "200");
    const qs = params.toString();
    const url = `/api/management/overview?${qs}`;

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (typeof data.records_version === "number") {
        lastRecordsVersion = data.records_version;
      }
      applyManagementData(data);
    } catch {
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
      showBanner(managementAlertBox, "success", "Đã làm mới dữ liệu từ MySQL.");
    } catch (err) {
      await fetchManagementOverview();
      showBanner(managementAlertBox, "error", err.message);
    } finally {
      btnRefreshManagement.disabled = false;
    }
  });

  attachDeviceChangeListenerOnce();
  setPlaceholderText(
    1,
    'Bấm "Tìm camera" để cấp quyền và chọn thiết bị cho Cam 1'
  );
  setPlaceholderText(
    2,
    'Bấm "Tìm camera" để cấp quyền và chọn thiết bị cho Cam 2'
  );
  renderDeviceSelects();
  refreshCamControlButtons();
  pollCameraStatusOnce();
})();
