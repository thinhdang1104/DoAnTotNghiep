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

  const cam1VotePill = document.getElementById("cam1-vote-pill");
  const cam2VotePill = document.getElementById("cam2-vote-pill");
  const cam1PlateValue = document.getElementById("cam1-plate-value");
  const cam1FaceValue = document.getElementById("cam1-face-value");
  const cam2PlateValue = document.getElementById("cam2-plate-value");
  const cam2FaceValue = document.getElementById("cam2-face-value");
  const cam1LiveVideo = document.getElementById("cam1-live-video");
  const cam2LiveVideo = document.getElementById("cam2-live-video");
  const cam1OverlayCanvas = document.getElementById("cam1-overlay-canvas");
  const cam2OverlayCanvas = document.getElementById("cam2-overlay-canvas");
  const cam1Placeholder = document.getElementById("cam1-placeholder");
  const cam2Placeholder = document.getElementById("cam2-placeholder");
  const voteAmbiguousWarning = document.getElementById("vote-ambiguous-warning");
  const gateTopupBox = document.getElementById("gate-topup-box");

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

  // Revenue Report elements
  const revenueUnitPill = document.getElementById("revenue-unit-pill");
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
  const revPaginationRangeText = document.getElementById("rev-pagination-range-text");
  const revPageSizeSelect = document.getElementById("rev-page-size-select");
  const revPaginationControls = document.getElementById("rev-pagination-controls");

  const tabLinks = document.querySelectorAll(".tab-link[data-status-filter]");
  const tabCountAll = document.getElementById("tab-count-all");
  const tabCountParking = document.getElementById("tab-count-parking");
  const tabCountIn = document.getElementById("tab-count-in");
  const tabCountOut = document.getElementById("tab-count-out");
  const searchPlateInput = document.getElementById("search-plate-input");
  const ledgerCountText = document.getElementById("ledger-count-text");
  const btnExportHistoryPdf = document.getElementById("btn-export-history-pdf");
  const btnRefreshManagement = document.getElementById("btn-refresh-management");
  const btnExportRevenuePdf = document.getElementById("btn-export-revenue-pdf");
  const thDirectionSort = document.getElementById("th-direction-sort");
  const directionSortIndicator = document.getElementById("direction-sort-indicator");
  const historyTableBody = document.getElementById("history-table-body");
  const paginationRangeText = document.getElementById("pagination-range-text");
  const pageSizeSelect = document.getElementById("page-size-select");
  const paginationControls = document.getElementById("pagination-controls");

  // Snapshot & Lost Vehicle Case (Check-in / Check-out / Người lấy xe) modal elements
  const snapshotModal = document.getElementById("snapshot-modal");
  const snapshotModalCard = document.getElementById("snapshot-modal-card");
  const snapshotModalTitle = document.getElementById("snapshot-modal-title");
  const checkinBadgePill = document.getElementById("checkin-badge-pill");
  const checkinTimeLabel = document.getElementById("checkin-time-label");
  const checkinPlateLabel = document.getElementById("checkin-plate-label");
  const checkinFaceLabel = document.getElementById("checkin-face-label");
  const checkinPlateImgLabel = document.getElementById("checkin-plate-img-label");
  const checkinFaceImgLabel = document.getElementById("checkin-face-img-label");
  const modalPlateImg = document.getElementById("modal-plate-img");
  const modalFaceImg = document.getElementById("modal-face-img");
  const checkinPlateEmpty = document.getElementById("checkin-plate-empty");
  const checkinFaceEmpty = document.getElementById("checkin-face-empty");
  const btnCloseSnapshotModal = document.getElementById("btn-close-snapshot-modal");
  const btnExportLostCasePdf = document.getElementById("btn-export-lost-case-pdf");
  const lostCaseVerdictBanner = document.getElementById("lost-case-verdict-banner");
  const checkinRecordId = document.getElementById("checkin-record-id");
  const checkinTime = document.getElementById("checkin-time");
  const checkinPlate = document.getElementById("checkin-plate");
  const checkinFaceStatus = document.getElementById("checkin-face-status");
  const checkoutBadgePill = document.getElementById("checkout-badge-pill");
  const checkoutRecordId = document.getElementById("checkout-record-id");
  const checkoutTime = document.getElementById("checkout-time");
  const checkoutParkingStatus = document.getElementById("checkout-parking-status");
  const checkoutMatchStatus = document.getElementById("checkout-match-status");
  const modalCheckoutPlateImg = document.getElementById("modal-checkout-plate-img");
  const checkoutPlateEmpty = document.getElementById("checkout-plate-empty");
  const takerMatchPill = document.getElementById("taker-match-pill");
  const modalTakerFaceImg = document.getElementById("modal-taker-face-img");
  const takerFaceEmpty = document.getElementById("taker-face-empty");
  const takerNoteText = document.getElementById("taker-note-text");

  let activeViewId = "view-recognition";
  let activeStatusFilter = "all";
  let activeDirectionSort = "";
  let activeRevenuePeriod = "daily";
  let revCurrentPage = 1;
  let revPageSize = 10;
  let cachedRevenueData = null;
  let cachedHistoryRecords = [];
  let cachedMatchedCount = 0;
  let cachedTotalRecords = 0;
  let activeLostCase = null;
  let isLostModalOpen = false;
  let lostCaseReqSeq = 0;
  let overviewReqSeq = 0;
  let overviewInFlight = false;
  let currentPage = 1;
  let pageSize = 10;
  let isCameraStreaming = false;
  let camStreaming = { 1: false, 2: false };
  let selectedCamDeviceIds = { 1: "", 2: "" };
  let activeCamDeviceIds = { 1: null, 2: null };
  let activeCamDeviceLabels = { 1: null, 2: null };
  let lastDeviceSelectSig = { 1: "", 2: "" };
  let camBusy = { 1: false, 2: false };
  let manualStoppingCam = { 1: false, 2: false };
  let trackEndedHandlers = { 1: null, 2: null };
  let lastCamError = { 1: "", 2: "" };
  let lastBackendError = "";
  let faceMatchThreshold = 0.65;
  let modelsReady = true;
  let hasDiscoveredOnce = false;
  let cameraPermissionGranted = false;
  let deviceChangeBound = false;
  let lastRecordsVersion = -1;
  let lastFeedbackSeq = -1;
  let hasActiveSecurityAlert = false;
  let activeSecurityAlertPlate = "";
  let resolvingAlertInFlight = false;
  let searchDebounceTimer = null;
  const OVERVIEW_CLIENT_CACHE_MAX = 30;
  const overviewPageCache = new Map();
  const overviewPrefetchInFlight = new Set();
  const lostCaseClientCache = new Map();
  let cachedStatsData = null;

  function clearClientManagementCaches() {
    overviewPageCache.clear();
    overviewPrefetchInFlight.clear();
    lostCaseClientCache.clear();
  }

  function makeOverviewCacheKey(ver, query, statusFilter, page, size, sortBy = "") {
    return `${ver}|${String(query || "").trim()}|${statusFilter || "all"}|${sortBy || ""}|${page}|${size}`;
  }

  function setOverviewClientCache(key, payload) {
    if (overviewPageCache.has(key)) {
      overviewPageCache.delete(key);
    } else if (overviewPageCache.size >= OVERVIEW_CLIENT_CACHE_MAX) {
      const oldestKey = overviewPageCache.keys().next().value;
      if (oldestKey !== undefined) overviewPageCache.delete(oldestKey);
    }
    overviewPageCache.set(key, payload);
  }

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
    const baseClass = box === gateTopupBox ? "topup-toast" : "notice-banner";
    if (box._hideTimer) {
      clearTimeout(box._hideTimer);
      box._hideTimer = null;
    }
    if (!message) {
      box.className = `${baseClass} hidden`;
      box.textContent = "";
      return;
    }
    box.className = type ? `${baseClass} notice-${type}` : baseClass;
    box.textContent = message;
    if (durationMs > 0) {
      box._hideTimer = setTimeout(() => {
        box.className = `${baseClass} hidden`;
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

  function renderDirectionPill(row) {
    const str = String((row && typeof row === "object" ? row["Luồng"] : row) || "Vào bãi");
    if (str.includes("Ra")) {
      const matchLabel =
        row && typeof row === "object" ? String(row["Đối chiếu"] || "") : "";
      const isMismatch =
        matchLabel.includes("Lệch") ||
        (row &&
          typeof row === "object" &&
          typeof row.face_match_score === "number" &&
          row.face_match_score < faceMatchThreshold);
      const pillClass = isMismatch ? "pill neg" : "pill warn";
      return `<span class="${pillClass}">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill pos">${escapeHtml(str)}</span>`;
  }

  // ==================== LATCH & ALERT CONTROLS ====================
  if (btnCancelLatch) {
    btnCancelLatch.addEventListener("click", async () => {
      if (latchStatusBox) latchStatusBox.classList.add("hidden");
      try {
        const res = await fetch("/api/camera/cancel-latch", { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          if (data && data.camera_status) {
            await applyCameraStatus(data.camera_status);
            return;
          }
        }
      } catch (_) {}
      await pollCameraStatusOnce();
    });
  }

  async function resolveAlert(action) {
    if (resolvingAlertInFlight) return;
    resolvingAlertInFlight = true;
    btnApproveExit.disabled = true;
    btnRejectExit.disabled = true;

    // Phản hồi giao diện tức thì (0 ms) ngay khi bấm nút; tự khôi phục hộp cảnh báo nếu ghi CSDL lỗi
    const plateText = activeSecurityAlertPlate || "";
    if (securityAlertBox) {
      securityAlertBox.classList.add("hidden");
    }
    const optimisticMsg =
      action === "approve"
        ? plateText
          ? `XE ${plateText} RA BÃI ĐƯỢC DUYỆT`
          : "ĐÃ DUYỆT CHO XE RA BÃI"
        : plateText
        ? `XE ${plateText} RA BÃI BỊ TỪ CHỐI`
        : "ĐÃ TỪ CHỐI CHO XE RA BÃI";
    const optimisticType = action === "approve" ? "warn" : "error";
    showBanner(gateTopupBox || cameraAlertBox, optimisticType, optimisticMsg, 2500);

    try {
      const res = await fetch("/api/camera/resolve-alert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) {
        throw new Error("HTTP " + res.status);
      }
      const data = await res.json();
      resolvingAlertInFlight = false;

      if (data && data.status === "db_error") {
        hasActiveSecurityAlert = true;
        if (gateTopupBox) {
          showBanner(gateTopupBox, "", "");
        }
        if (securityAlertBox) {
          securityAlertBox.classList.remove("hidden");
        }
        if (data.message) {
          showBanner(cameraAlertBox, "error", data.message);
        }
        if (data.camera_status) {
          await applyCameraStatus(data.camera_status);
        }
        return;
      }

      hasActiveSecurityAlert = false;
      activeSecurityAlertPlate = "";
      if (
        data &&
        data.camera_status &&
        data.camera_status.gate_feedback &&
        typeof data.camera_status.gate_feedback.seq === "number"
      ) {
        lastFeedbackSeq = data.camera_status.gate_feedback.seq;
      }
      if (data && data.message) {
        showBanner(
          gateTopupBox || cameraAlertBox,
          data.type || optimisticType,
          data.message,
          2500
        );
      }
      if (data && data.camera_status) {
        await applyCameraStatus(data.camera_status);
      } else {
        pollCameraStatusOnce();
      }
      ensureBrowserFrameLoop();
    } catch (_) {
      resolvingAlertInFlight = false;
      hasActiveSecurityAlert = true;
      if (gateTopupBox) {
        showBanner(gateTopupBox, "", "");
      }
      if (securityAlertBox) {
        securityAlertBox.classList.remove("hidden");
      }
      showBanner(
        cameraAlertBox,
        "error",
        "Không gửi được yêu cầu duyệt cảnh báo, vui lòng thử lại."
      );
    } finally {
      resolvingAlertInFlight = false;
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

  // ==================== DUAL CAMERA CONTROLS (BROWSER WEBRTC) ====================
  let browserWebRTCActive = false;
  let isStartingCamera = false;
  let browserCamDevices = [];
  let browserStreams = [null, null];
  let browserVideos = [null, null];
  let browserCanvas = null;
  let browserFrameTimer = null;
  let browserInFlight = false;
  let commitPollTimer = null;
  let commitPollInFlight = false;

  function stopCommitStatusPoll() {
    if (commitPollTimer) {
      clearInterval(commitPollTimer);
      commitPollTimer = null;
    }
  }

  function ensureCommitStatusPoll() {
    if (commitPollTimer) return;
    commitPollTimer = setInterval(async () => {
      if (commitPollInFlight || isStartingCamera) return;
      commitPollInFlight = true;
      try {
        await pollCameraStatusOnce();
      } finally {
        commitPollInFlight = false;
      }
    }, 180);
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
      const directOrigin =
        (window.location && window.location.origin) ||
        (window.location && window.location.href) ||
        "trang trực tiếp";
      return inIframe
        ? `Trình duyệt chặn quyền Camera trong khung nhúng. Vui lòng cấp quyền Camera trên thanh địa chỉ hoặc mở trực tiếp ${directOrigin}`
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
      const otherReservedId = activeCamDeviceIds[otherId] || "";
      const currentVal = selectedCamDeviceIds[camId] || "";
      const isDisabled = Boolean(
        camStreaming[camId] || camBusy[camId] || browserCamDevices.length === 0
      );
      const devListSig = browserCamDevices
        .map((d) => `${d.deviceId}:${d.label}`)
        .join("|");
      const nextSig = `${isDisabled ? 1 : 0}::${currentVal}::${otherReservedId}::${devListSig}`;

      if (lastDeviceSelectSig[camId] === nextSig) {
        if (selectEl.value !== currentVal) {
          selectEl.value = currentVal;
        }
        if (selectEl.disabled !== isDisabled) {
          selectEl.disabled = isDisabled;
        }
        return;
      }
      lastDeviceSelectSig[camId] = nextSig;

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
      selectEl.disabled = isDisabled;
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
    } catch (_) {}
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
    if (camStreaming[1] && browserVideos[0] && cam1LiveVideo) {
      cam1LiveVideo.classList.remove("hidden");
      if (cam1OverlayCanvas) cam1OverlayCanvas.classList.remove("hidden");
      cam1Placeholder.classList.add("hidden");
    }
    if (camStreaming[2] && browserVideos[1] && cam2LiveVideo) {
      cam2LiveVideo.classList.remove("hidden");
      if (cam2OverlayCanvas) cam2OverlayCanvas.classList.remove("hidden");
      cam2Placeholder.classList.add("hidden");
    }
  }

  async function runBrowserFrameTick() {
    browserFrameTimer = null;
    if (!browserWebRTCActive) return;
    if (hasActiveSecurityAlert || resolvingAlertInFlight) {
      // Tạm ngưng gửi ảnh nặng khi đang hiện hộp Cảnh báo an ninh để thao tác bấm Duyệt / Từ chối phản hồi tức thì
      browserFrameTimer = setTimeout(runBrowserFrameTick, 120);
      return;
    }
    if (browserInFlight) {
      browserFrameTimer = setTimeout(runBrowserFrameTick, 35);
      return;
    }
    const v1 = browserVideos[0];
    const v2 = browserVideos[1];
    if (!v1 && !v2) return;

    const img1 = v1 ? captureVideoToJpegDataUrl(v1) : null;
    const img2 = v2 ? captureVideoToJpegDataUrl(v2) : null;
    if (!img1 && !img2) {
      browserFrameTimer = setTimeout(runBrowserFrameTick, 80);
      return;
    }

    const t0 = performance.now();
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
      if (browserWebRTCActive && !browserFrameTimer) {
        const elapsed = performance.now() - t0;
        const nextDelay = Math.max(25, Math.round(115 - elapsed));
        browserFrameTimer = setTimeout(runBrowserFrameTick, nextDelay);
      }
    }
  }

  function ensureBrowserFrameLoop() {
    if (browserFrameTimer || browserInFlight) return;
    browserFrameTimer = setTimeout(runBrowserFrameTick, 20);
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
      if (!browserWebRTCActive) {
        stopCommitStatusPoll();
        if (browserFrameTimer) {
          clearTimeout(browserFrameTimer);
          browserFrameTimer = null;
        }
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
    const liveVideoEl = camId === 1 ? cam1LiveVideo : cam2LiveVideo;
    const overlayCanvasEl = camId === 1 ? cam1OverlayCanvas : cam2OverlayCanvas;
    const phEl = camId === 1 ? cam1Placeholder : cam2Placeholder;
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

      try {
        openedCamObj = await tryOpenStreamWithVideo({
          video: { deviceId: { exact: selectedId } },
          audio: false,
        });
      } catch (openErr) {
        throw new Error(formatMediaError(openErr, targetDev.label));
      }

      const res = await fetch(`/api/camera/${camId}/start`, {
        method: "POST",
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
      openedCamObj = null;
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
        votePillEl.textContent = modelsReady
          ? `${targetDev.label} · Đang quét`
          : `${targetDev.label} · Đang tải mô hình AI...`;
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
        "Chưa chọn thiết bị";
      if (!running) {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `${devLabel} · Ngắt`;
      } else if (camData && camData.vote) {
        const pct = Math.round(camData.vote.vote_share * 100);
        votePillEl.className = "pill warn mono-num num";
        votePillEl.textContent = `${camData.vote.candidate} (${camData.vote.vote_count}/${camData.vote.sample_count} · ${pct}%)`;
      } else if (!modelsReady) {
        votePillEl.className = "pill warn mono-num num";
        votePillEl.textContent = `${devLabel} · Đang tải mô hình AI...`;
      } else {
        votePillEl.className = "pill mono-num num";
        votePillEl.textContent = `${devLabel} · Đang quét`;
      }
    }
  }

  function syncSingleCamUI(camId, camState) {
    const slot = camId - 1;
    const ownsBrowserStream = Boolean(browserVideos[slot] && browserStreams[slot]);

    if (ownsBrowserStream) {
      if (!camStreaming[camId]) {
        camStreaming[camId] = true;
        revealCamImagesIfReady();
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
    return ownsBrowserStream;
  }

  async function applyCameraStatus(state) {
    if (!state || isStartingCamera) return;

    if (typeof state.face_match_threshold === "number" && state.face_match_threshold > 0) {
      faceMatchThreshold = state.face_match_threshold;
    }
    if (typeof state.models_ready === "boolean") {
      modelsReady = state.models_ready;
    }

    const active1 = syncSingleCamUI(1, state.cam1);
    const active2 = syncSingleCamUI(2, state.cam2);

    renderDeviceSelects();
    refreshCamControlButtons();

    if (state.error) {
      lastBackendError = state.error;
      showBanner(cameraAlertBox, "error", state.error);
    } else if (lastBackendError) {
      if (cameraAlertBox && cameraAlertBox.textContent === lastBackendError) {
        showBanner(cameraAlertBox, "", "");
      }
      lastBackendError = "";
    }

    if (
      state.gate_feedback &&
      state.gate_feedback.message &&
      state.gate_feedback.seq !== lastFeedbackSeq
    ) {
      lastFeedbackSeq = state.gate_feedback.seq;
      showBanner(
        gateTopupBox || cameraAlertBox,
        state.gate_feedback.type || "success",
        state.gate_feedback.message,
        2500
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

    // Two-Phase Latch UI (hiển thị gọn trong header-topup-slot, không làm nhảy khung Camera)
    if (state.latched && !state.security_alert) {
      if (gateTopupBox) {
        showBanner(gateTopupBox, "", "");
      }
      latchStatusBox.classList.remove("hidden");
      const isIn = state.latched.direction === "IN";
      latchDirectionBadge.className = isIn ? "pill pos" : "pill warn";
      latchDirectionBadge.textContent = isIn ? "LƯU HỜ · ĐI VÀO" : "LƯU HỜ · ĐI RA";
      latchPlateText.textContent = state.latched.plate_number;
      latchStepText.textContent = state.latched.sampling_face
        ? `Cam ${state.latched.plate_cam} đã chốt biển — Đang chọn mặt nét nhất ở Cam ${state.latched.required_face_cam}...`
        : `Cam ${state.latched.plate_cam} đã chốt biển — Chờ khuôn mặt ở Cam ${state.latched.required_face_cam} (${state.latched.remaining_seconds}s)`;
    } else {
      latchStatusBox.classList.add("hidden");
    }

    // Security Alert UI (Face mismatch on exit — Top-up in blue box area)
    if (state.security_alert) {
      hasActiveSecurityAlert = true;
      activeSecurityAlertPlate = state.security_alert.plate_number || "";
      if (!resolvingAlertInFlight) {
        if (gateTopupBox) {
          showBanner(gateTopupBox, "", "");
        }
        securityAlertBox.classList.remove("hidden");
        alertScorePill.textContent = `Độ khớp: ${state.security_alert.match_score_pct}`;
        const threshPct = Math.round(faceMatchThreshold * 100);
        alertDetailText.textContent =
          `Xe ${state.security_alert.plate_number} (gửi lúc ${state.security_alert.entry_time}) ` +
          `có khuôn mặt người lấy xe LỆCH so với lúc gửi xe vào bãi (Cosine ${state.security_alert.match_score_pct} < ${threshPct}%).`;
      }
    } else {
      hasActiveSecurityAlert = false;
      activeSecurityAlertPlate = "";
      securityAlertBox.classList.add("hidden");
    }

    voteAmbiguousWarning.classList.toggle("hidden", !state.ambiguous_frame);

    if (state.committing) {
      ensureCommitStatusPoll();
    } else {
      stopCommitStatusPoll();
    }

    if (
      typeof state.records_version === "number" &&
      state.records_version !== lastRecordsVersion
    ) {
      const wasUninitialized = lastRecordsVersion < 0;
      lastRecordsVersion = state.records_version;
      clearClientManagementCaches();
      if (
        (activeViewId === "view-management" || activeViewId === "view-revenue") &&
        !(wasUninitialized && overviewInFlight)
      ) {
        fetchManagementOverview();
      }
    }
  }

  async function pollCameraStatusOnce() {
    if (isStartingCamera) return;
    try {
      const res = await fetch("/api/camera/status");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const state = await res.json();
      await applyCameraStatus(state);
    } catch {
      // Bỏ qua lỗi mạng tạm thời
    }
  }

  // ==================== REVENUE REPORT (NGÀY / THÁNG / NĂM) ====================
  function formatVnd(amount) {
    const val = Math.max(0, Number(amount) || 0);
    return `${val.toLocaleString("de-DE")} đ`;
  }

  function renderRevenuePaginationControls(totalItems, totalPages) {
    if (!revPaginationControls) return;

    if (totalItems === 0) {
      if (revPaginationRangeText) {
        revPaginationRangeText.textContent = "Hiển thị 0–0";
      }
      revPaginationControls.innerHTML = "";
      return;
    }

    const startIdx = (revCurrentPage - 1) * revPageSize + 1;
    const endIdx = Math.min(totalItems, revCurrentPage * revPageSize);
    if (revPaginationRangeText) {
      revPaginationRangeText.textContent = `Hiển thị ${startIdx}–${endIdx}`;
    }

    const pageItems = buildPageNumbers(totalPages, revCurrentPage);
    const buttonsHtml = [];

    buttonsHtml.push(
      `<button type="button" class="page-btn" data-rev-page="${revCurrentPage - 1}" ${
        revCurrentPage <= 1 ? "disabled" : ""
      } title="Trang trước">‹ Trước</button>`
    );

    pageItems.forEach((item) => {
      if (item === "...") {
        buttonsHtml.push(`<span class="page-ellipsis">…</span>`);
      } else {
        const activeClass = item === revCurrentPage ? " active" : "";
        buttonsHtml.push(
          `<button type="button" class="page-btn${activeClass}" data-rev-page="${item}">${item}</button>`
        );
      }
    });

    buttonsHtml.push(
      `<button type="button" class="page-btn" data-rev-page="${revCurrentPage + 1}" ${
        revCurrentPage >= totalPages ? "disabled" : ""
      } title="Trang sau">Sau ›</button>`
    );

    revPaginationControls.innerHTML = buttonsHtml.join("");
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
    if (revenueUnitPill) {
      revenueUnitPill.textContent = `Đơn giá: ${unitFeeText} / lượt gửi`;
    }
    const rows =
      (cachedRevenueData && cachedRevenueData[activeRevenuePeriod]) || [];

    if (!rows || rows.length === 0) {
      revenueTableBody.innerHTML = `
        <tr>
          <td colspan="4">Chưa có dữ liệu doanh thu trong kỳ này.</td>
        </tr>
      `;
      renderRevenuePaginationControls(0, 1);
      return;
    }

    const totalItems = rows.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / revPageSize));
    if (revCurrentPage > totalPages) revCurrentPage = totalPages;
    if (revCurrentPage < 1) revCurrentPage = 1;

    const startOffset = (revCurrentPage - 1) * revPageSize;
    const pageRows = rows.slice(startOffset, startOffset + revPageSize);

    revenueTableBody.innerHTML = pageRows
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

    renderRevenuePaginationControls(totalItems, totalPages);
  }

  if (revPaginationControls) {
    revPaginationControls.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-rev-page]");
      if (!btn || btn.disabled) return;
      const targetPage = parseInt(btn.getAttribute("data-rev-page") || "1", 10);
      if (!Number.isNaN(targetPage) && targetPage !== revCurrentPage) {
        revCurrentPage = targetPage;
        renderRevenueBreakdownTable();
      }
    });
  }

  if (revPageSizeSelect) {
    revPageSizeSelect.addEventListener("change", () => {
      const val = parseInt(revPageSizeSelect.value || "10", 10);
      revPageSize = Number.isNaN(val) || val < 1 ? 10 : val;
      revCurrentPage = 1;
      renderRevenueBreakdownTable();
    });
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
      revPeriodBtns.forEach((b) => {
        b.setAttribute("aria-pressed", "false");
        b.classList.remove("highlight-card");
      });
      btn.setAttribute("aria-pressed", "true");
      btn.classList.add("highlight-card");
      activeRevenuePeriod = btn.getAttribute("data-rev-period") || "daily";
      revCurrentPage = 1;
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
    if (!row) return { plateImg: "", faceImg: "", hasRealPlate: false, hasRealFace: false };
    const hasRealPlate = Boolean(row.plate_image);
    const hasRealFace = Boolean(row.face_image);
    const plateImg = row.plate_image || makeFallbackPlateSvg(row["Biển số"]);
    const faceImg = row.face_image || makeFallbackFaceSvg(row["Biển số"], row["Khuôn mặt"]);
    return {
      plateImg,
      faceImg,
      realPlateImg: row.plate_image || "",
      realFaceImg: row.face_image || "",
      hasRealPlate,
      hasRealFace,
    };
  }

  function computeLostCaseDetails(checkinRow, checkoutRow, fallbackPlate = "-") {
    const plateNumber =
      (checkinRow && checkinRow["Biển số"]) ||
      (checkoutRow && checkoutRow["Biển số"]) ||
      fallbackPlate ||
      "-";

    const checkinSnap = checkinRow
      ? getRowSnapshots(checkinRow)
      : {
          plateImg: "",
          faceImg: "",
          realPlateImg: "",
          realFaceImg: "",
          hasRealPlate: false,
          hasRealFace: false,
        };
    const checkoutSnap = checkoutRow ? getRowSnapshots(checkoutRow) : null;

    const inStatusCode = checkinRow
      ? String(checkinRow.parking_status_code || "").toUpperCase()
      : "";
    const inStatusText = checkinRow
      ? String(checkinRow["Trạng thái bãi"] || "")
      : "";
    const sessionClosedMissingExit = Boolean(
      checkinRow &&
        !checkoutRow &&
        ((inStatusCode && inStatusCode !== "IN_PARKING") ||
          (inStatusText && !inStatusText.includes("Đang gửi")))
    );

    const matchLabel = checkoutRow
      ? String(checkoutRow["Đối chiếu"] || "-")
      : sessionClosedMissingExit
      ? "Phiên đã đóng, thiếu thông tin lượt ra"
      : "Chưa có lượt ra";

    const isMismatch =
      Boolean(checkoutRow) &&
      (matchLabel.includes("Lệch") ||
        (typeof checkoutRow.face_match_score === "number" &&
          checkoutRow.face_match_score < faceMatchThreshold));

    let verdictType = "warn";
    let verdictText = "";
    let takerNote = "";

    if (checkoutRow) {
      if (isMismatch) {
        verdictType = "alert";
        verdictText =
          `CẢNH BÁO NGHI VẤN MẤT XE: Xe ${plateNumber} đã Check-out lúc ${checkoutRow["Thời gian nhận diện"]} ` +
          `với khuôn mặt Người lấy xe LỆCH so với người gửi lúc Check-in (${matchLabel} — Duyệt ngoại lệ).`;
        takerNote =
          "Khuôn mặt Người lấy xe KHÔNG KHỚP với người gửi xe lúc Check-in. Đề nghị trích xuất ảnh này làm bằng chứng xác minh.";
      } else {
        verdictType = "ok";
        verdictText =
          `ĐÃ LẤY XE RA BÃI: Xe ${plateNumber} Check-in lúc ${checkinRow ? checkinRow["Thời gian nhận diện"] : "-"} ` +
          `và đã Check-out lúc ${checkoutRow["Thời gian nhận diện"]} (${matchLabel}).`;
        takerNote =
          "Ảnh khuôn mặt Người lấy xe được camera cổng ra ghi nhận tại thời điểm Check-out.";
      }
    } else if (sessionClosedMissingExit) {
      verdictType = "warn";
      verdictText =
        `Phiên đã đóng, thiếu thông tin lượt ra: Xe ${plateNumber} (Check-in lúc ${checkinRow ? checkinRow["Thời gian nhận diện"] : "-"}) ` +
        `đã được đánh dấu đóng phiên (${checkinRow["Trạng thái bãi"] || inStatusCode}), nhưng không tìm thấy bản ghi lượt ra liên kết.`;
      takerNote = "Phiên đã đóng, thiếu thông tin lượt ra.";
    } else {
      verdictType = "warn";
      verdictText =
        `CHƯA CÓ LƯỢT CHECK-OUT: Xe ${plateNumber} đã Check-in lúc ${checkinRow ? checkinRow["Thời gian nhận diện"] : "-"} ` +
        `và hiện vẫn đang ở trạng thái Đang gửi trong bãi (chưa ghi nhận lượt lấy xe qua cổng).`;
      takerNote =
        "Chưa có ảnh Người lấy xe vì biển số này chưa thực hiện Check-out qua cổng camera.";
    }

    return {
      plateNumber,
      checkinRow,
      checkoutRow,
      checkinSnap,
      checkoutSnap,
      sessionClosedMissingExit,
      matchLabel,
      isMismatch,
      verdictType,
      verdictText,
      takerNote,
    };
  }

  function renderSnapshotCell(row) {
    const { plateImg, faceImg } = getRowSnapshots(row);
    const plate = escapeHtml(row["Biển số"]);
    const recId = escapeHtml(row["ID"]);
    return `
      <div class="snapshot-cell">
        <button type="button" class="snap-thumb-btn" data-record-id="${recId}" title="Bấm để xem ảnh cắt biển số và khuôn mặt của lượt này">
          <img class="snap-plate-img" src="${plateImg}" alt="Biển số ${plate}" loading="lazy" />
          <img class="snap-face-img" src="${faceImg}" alt="Khuôn mặt ${plate}" loading="lazy" />
        </button>
      </div>
    `;
  }

  function applyImageOrEmptyHint(imgEl, emptyEl, srcUrl, emptyText) {
    if (srcUrl) {
      if (imgEl) {
        imgEl.src = srcUrl;
        imgEl.classList.remove("hidden");
      }
      if (emptyEl) {
        emptyEl.classList.add("hidden");
      }
    } else {
      if (imgEl) {
        imgEl.src = "";
        imgEl.classList.add("hidden");
      }
      if (emptyEl) {
        emptyEl.textContent = emptyText;
        emptyEl.classList.remove("hidden");
      }
    }
  }

  function setModalPrimaryLabels(isSingleMode, isOutRow = false, isMismatch = false) {
    if (snapshotModalCard) {
      snapshotModalCard.classList.toggle("single-snapshot-mode", Boolean(isSingleMode));
    }
    if (isSingleMode && isOutRow) {
      if (checkinBadgePill) {
        checkinBadgePill.className = isMismatch ? "pill neg" : "pill warn";
        checkinBadgePill.textContent = "CHECK OUT (LÚC LẤY XE)";
      }
      if (checkinTimeLabel) checkinTimeLabel.textContent = "Thời gian ra:";
      if (checkinPlateLabel) checkinPlateLabel.textContent = "Biển số lúc ra:";
      if (checkinFaceLabel) checkinFaceLabel.textContent = "Đối chiếu FaceNet:";
      if (checkinPlateImgLabel) checkinPlateImgLabel.textContent = "Biển số Check-out";
      if (checkinFaceImgLabel) checkinFaceImgLabel.textContent = "Người lấy xe (Check-out)";
      return;
    }
    if (checkinBadgePill) {
      checkinBadgePill.className = "pill pos";
      checkinBadgePill.textContent = isSingleMode
        ? "CHECK IN (LÚC GỬI XE)"
        : "1. CHECK IN (LÚC GỬI XE)";
    }
    if (checkinTimeLabel) checkinTimeLabel.textContent = "Thời gian vào:";
    if (checkinPlateLabel) checkinPlateLabel.textContent = "Biển số lúc vào:";
    if (checkinFaceLabel) checkinFaceLabel.textContent = "Nhận diện mặt:";
    if (checkinPlateImgLabel) checkinPlateImgLabel.textContent = "Biển số Check-in";
    if (checkinFaceImgLabel) checkinFaceImgLabel.textContent = "Người gửi xe (Check-in)";
  }

  function openSingleSnapshotModalByRow(row) {
    if (!snapshotModal || !row) return;
    lostCaseReqSeq += 1;
    isLostModalOpen = true;
    activeLostCase = null;
    if (btnExportLostCasePdf) {
      btnExportLostCasePdf.disabled = true;
    }

    const plateNumber = row["Biển số"] || "-";
    const isOut =
      String(row.direction_code || "").toUpperCase() === "OUT" ||
      String(row["Luồng"] || "").includes("Ra");
    const matchLabel = String(row["Đối chiếu"] || "-");
    const isMismatch =
      isOut &&
      (matchLabel.includes("Lệch") ||
        (typeof row.face_match_score === "number" &&
          row.face_match_score < faceMatchThreshold));
    const snap = getRowSnapshots(row);

    setModalPrimaryLabels(true, isOut, isMismatch);
    if (snapshotModalTitle) {
      snapshotModalTitle.textContent = `Biển số ${plateNumber}`;
    }
    if (checkinRecordId) checkinRecordId.textContent = `#${row["ID"]}`;
    if (checkinTime) checkinTime.textContent = row["Thời gian nhận diện"] || "-";
    if (checkinPlate) checkinPlate.textContent = plateNumber;
    if (checkinFaceStatus) {
      checkinFaceStatus.textContent = isOut
        ? matchLabel
        : row["Khuôn mặt"] || "Đã lưu mẫu mặt";
    }
    applyImageOrEmptyHint(
      modalPlateImg,
      checkinPlateEmpty,
      snap.realPlateImg,
      "Không có ảnh lưu trữ"
    );
    applyImageOrEmptyHint(
      modalFaceImg,
      checkinFaceEmpty,
      snap.realFaceImg,
      "Không có ảnh lưu trữ"
    );

    snapshotModal.classList.remove("hidden");
  }

  function renderLostVehicleModalCase(caseData) {
    if (!snapshotModal || !caseData) return;
    setModalPrimaryLabels(false, false, false);
    activeLostCase = caseData;
    if (btnExportLostCasePdf) {
      btnExportLostCasePdf.disabled = false;
    }

    if (snapshotModalTitle) {
      snapshotModalTitle.textContent = `Biển số ${caseData.plateNumber}`;
    }
    if (lostCaseVerdictBanner) {
      lostCaseVerdictBanner.className = `lost-case-verdict verdict-${caseData.verdictType}`;
      lostCaseVerdictBanner.textContent = caseData.verdictText;
    }

    // 1. Check-in
    if (checkinRecordId) {
      checkinRecordId.textContent = caseData.checkinRow ? `#${caseData.checkinRow["ID"]}` : "Chưa rõ";
    }
    if (checkinTime) {
      checkinTime.textContent = caseData.checkinRow
        ? caseData.checkinRow["Thời gian nhận diện"]
        : "Không tìm thấy bản ghi vào";
    }
    if (checkinPlate) {
      checkinPlate.textContent = caseData.plateNumber;
    }
    if (checkinFaceStatus) {
      checkinFaceStatus.textContent = caseData.checkinRow
        ? caseData.checkinRow["Khuôn mặt"] || "Đã lưu mẫu mặt"
        : "-";
    }
    applyImageOrEmptyHint(
      modalPlateImg,
      checkinPlateEmpty,
      caseData.checkinSnap.realPlateImg,
      "Không có ảnh lưu trữ"
    );
    applyImageOrEmptyHint(
      modalFaceImg,
      checkinFaceEmpty,
      caseData.checkinSnap.realFaceImg,
      "Không có ảnh lưu trữ"
    );

    // 2. Check-out & 3. Người lấy xe
    if (caseData.checkoutRow && caseData.checkoutSnap) {
      if (checkoutBadgePill) {
        checkoutBadgePill.className = caseData.isMismatch ? "pill neg" : "pill pos";
        checkoutBadgePill.textContent = "2. CHECK OUT (ĐÃ RA BÃI)";
      }
      if (checkoutRecordId) {
        checkoutRecordId.textContent = `#${caseData.checkoutRow["ID"]}`;
      }
      if (checkoutTime) {
        checkoutTime.textContent = caseData.checkoutRow["Thời gian nhận diện"];
      }
      if (checkoutParkingStatus) {
        checkoutParkingStatus.textContent = "Đã lấy xe ra khỏi bãi";
      }
      if (checkoutMatchStatus) {
        checkoutMatchStatus.textContent = caseData.matchLabel;
      }
      applyImageOrEmptyHint(
        modalCheckoutPlateImg,
        checkoutPlateEmpty,
        caseData.checkoutSnap.realPlateImg,
        "Không có ảnh lưu trữ"
      );

      if (takerMatchPill) {
        takerMatchPill.className = caseData.isMismatch
          ? "pill neg mono-num num"
          : "pill pos mono-num num";
        takerMatchPill.textContent = caseData.matchLabel;
      }
      applyImageOrEmptyHint(
        modalTakerFaceImg,
        takerFaceEmpty,
        caseData.checkoutSnap.realFaceImg,
        "Không có ảnh lưu trữ"
      );
    } else if (caseData.sessionClosedMissingExit) {
      if (checkoutBadgePill) {
        checkoutBadgePill.className = "pill warn";
        checkoutBadgePill.textContent = "2. CHECK OUT (THIẾU BẢN GHI RA)";
      }
      if (checkoutRecordId) checkoutRecordId.textContent = "#-";
      if (checkoutTime) {
        checkoutTime.textContent = "Phiên đã đóng, thiếu thông tin lượt ra";
      }
      if (checkoutParkingStatus) {
        checkoutParkingStatus.textContent = "Phiên đã đóng, thiếu thông tin lượt ra";
      }
      if (checkoutMatchStatus) {
        checkoutMatchStatus.textContent = "Không có dữ liệu lượt ra";
      }

      applyImageOrEmptyHint(
        modalCheckoutPlateImg,
        checkoutPlateEmpty,
        "",
        "Phiên đã đóng, thiếu thông tin lượt ra"
      );

      if (takerMatchPill) {
        takerMatchPill.className = "pill warn mono-num num";
        takerMatchPill.textContent = "Thiếu lượt ra";
      }
      applyImageOrEmptyHint(
        modalTakerFaceImg,
        takerFaceEmpty,
        "",
        "Phiên đã đóng, thiếu thông tin lượt ra"
      );
    } else {
      if (checkoutBadgePill) {
        checkoutBadgePill.className = "pill warn";
        checkoutBadgePill.textContent = "2. CHECK OUT (CHƯA RA)";
      }
      if (checkoutRecordId) checkoutRecordId.textContent = "#-";
      if (checkoutTime) checkoutTime.textContent = "Chưa có lượt ra";
      if (checkoutParkingStatus) checkoutParkingStatus.textContent = "Đang gửi trong bãi";
      if (checkoutMatchStatus) checkoutMatchStatus.textContent = "Chưa đối chiếu";

      applyImageOrEmptyHint(
        modalCheckoutPlateImg,
        checkoutPlateEmpty,
        "",
        "Chưa có lượt Check-out qua cổng"
      );

      if (takerMatchPill) {
        takerMatchPill.className = "pill warn mono-num num";
        takerMatchPill.textContent = "Chưa xác định";
      }
      applyImageOrEmptyHint(
        modalTakerFaceImg,
        takerFaceEmpty,
        "",
        "Xe chưa ghi nhận lượt lấy ra qua cổng"
      );
    }

    if (takerNoteText) {
      takerNoteText.textContent = caseData.takerNote;
    }

    snapshotModal.classList.remove("hidden");
  }

  function renderLostModalLoadingState(row) {
    if (!snapshotModal) return;
    setModalPrimaryLabels(false, false, false);
    activeLostCase = null;
    if (btnExportLostCasePdf) {
      btnExportLostCasePdf.disabled = true;
    }

    const plateNumber = (row && row["Biển số"]) || "-";
    const isOut =
      Boolean(row) &&
      (String(row.direction_code || "").toUpperCase() === "OUT" ||
        String(row["Luồng"] || "").includes("Ra"));
    const rowSnap = row ? getRowSnapshots(row) : null;

    if (snapshotModalTitle) {
      snapshotModalTitle.textContent = `Biển số ${plateNumber}`;
    }
    if (lostCaseVerdictBanner) {
      lostCaseVerdictBanner.className = "lost-case-verdict";
      lostCaseVerdictBanner.textContent = isOut
        ? "Đang đối chiếu bản ghi Check-in từ cơ sở dữ liệu..."
        : "Đang đối chiếu bản ghi Check-out từ cơ sở dữ liệu...";
    }

    if (row && !isOut && rowSnap) {
      // Hiển thị ngay toàn bộ thông tin & ảnh Check-in sẵn có của dòng đang chọn
      if (checkinRecordId) checkinRecordId.textContent = `#${row["ID"]}`;
      if (checkinTime) checkinTime.textContent = row["Thời gian nhận diện"] || "-";
      if (checkinPlate) checkinPlate.textContent = plateNumber;
      if (checkinFaceStatus) {
        checkinFaceStatus.textContent = row["Khuôn mặt"] || "Đã lưu mẫu mặt";
      }
      applyImageOrEmptyHint(
        modalPlateImg,
        checkinPlateEmpty,
        rowSnap.realPlateImg,
        "Không có ảnh lưu trữ"
      );
      applyImageOrEmptyHint(
        modalFaceImg,
        checkinFaceEmpty,
        rowSnap.realFaceImg,
        "Không có ảnh lưu trữ"
      );
    } else {
      if (checkinRecordId) checkinRecordId.textContent = "#-";
      if (checkinTime) checkinTime.textContent = "Đang đối chiếu...";
      if (checkinPlate) checkinPlate.textContent = plateNumber;
      if (checkinFaceStatus) checkinFaceStatus.textContent = "-";
      applyImageOrEmptyHint(modalPlateImg, checkinPlateEmpty, "", "Đang đối chiếu...");
      applyImageOrEmptyHint(modalFaceImg, checkinFaceEmpty, "", "Đang đối chiếu...");
    }

    if (row && isOut && rowSnap) {
      // Hiển thị ngay thông tin & ảnh Check-out / Người lấy xe sẵn có của dòng đang chọn
      const matchLabel = String(row["Đối chiếu"] || "-");
      const isMismatch =
        matchLabel.includes("Lệch") ||
        (typeof row.face_match_score === "number" &&
          row.face_match_score < faceMatchThreshold);
      if (checkoutBadgePill) {
        checkoutBadgePill.className = isMismatch ? "pill neg" : "pill pos";
        checkoutBadgePill.textContent = "2. CHECK OUT (ĐÃ RA BÃI)";
      }
      if (checkoutRecordId) checkoutRecordId.textContent = `#${row["ID"]}`;
      if (checkoutTime) checkoutTime.textContent = row["Thời gian nhận diện"] || "-";
      if (checkoutParkingStatus) {
        checkoutParkingStatus.textContent = "Đã lấy xe ra khỏi bãi";
      }
      if (checkoutMatchStatus) checkoutMatchStatus.textContent = matchLabel;
      applyImageOrEmptyHint(
        modalCheckoutPlateImg,
        checkoutPlateEmpty,
        rowSnap.realPlateImg,
        "Không có ảnh lưu trữ"
      );
      if (takerMatchPill) {
        takerMatchPill.className = isMismatch
          ? "pill neg mono-num num"
          : "pill pos mono-num num";
        takerMatchPill.textContent = matchLabel;
      }
      applyImageOrEmptyHint(
        modalTakerFaceImg,
        takerFaceEmpty,
        rowSnap.realFaceImg,
        "Không có ảnh lưu trữ"
      );
      if (takerNoteText) takerNoteText.textContent = "";
    } else {
      if (checkoutBadgePill) {
        checkoutBadgePill.className = "pill warn";
        checkoutBadgePill.textContent = "2. CHECK OUT (ĐANG ĐỐI CHIẾU...)";
      }
      if (checkoutRecordId) checkoutRecordId.textContent = "#-";
      if (checkoutTime) checkoutTime.textContent = "Đang đối chiếu...";
      if (checkoutParkingStatus) checkoutParkingStatus.textContent = "-";
      if (checkoutMatchStatus) checkoutMatchStatus.textContent = "-";
      applyImageOrEmptyHint(
        modalCheckoutPlateImg,
        checkoutPlateEmpty,
        "",
        "Đang đối chiếu..."
      );
      if (takerMatchPill) {
        takerMatchPill.className = "pill mono-num num";
        takerMatchPill.textContent = "-";
      }
      applyImageOrEmptyHint(
        modalTakerFaceImg,
        takerFaceEmpty,
        "",
        "Đang đối chiếu..."
      );
      if (takerNoteText) takerNoteText.textContent = "";
    }

    snapshotModal.classList.remove("hidden");
  }

  async function openLostVehicleModalByRow(row) {
    if (!snapshotModal || !row) return;
    const recId = Number(row["ID"]);
    const reqId = ++lostCaseReqSeq;
    isLostModalOpen = true;
    const verSnapshot = lastRecordsVersion;
    const cacheKey = `${verSnapshot}:${recId}`;

    if (verSnapshot >= 0 && lostCaseClientCache.has(cacheKey)) {
      renderLostVehicleModalCase(lostCaseClientCache.get(cacheKey));
      return;
    }

    const dirCode = String(row.direction_code || "").toUpperCase();
    const statusCode = String(row.parking_status_code || "").toUpperCase();

    // Dòng IN đang gửi trong bãi (IN_PARKING) chắc chắn chưa có lượt OUT -> hiển thị đầy đủ tức thì 0 ms
    if (verSnapshot >= 0 && dirCode === "IN" && statusCode === "IN_PARKING") {
      const instantCase = computeLostCaseDetails(row, null, row["Biển số"]);
      lostCaseClientCache.set(cacheKey, instantCase);
      renderLostVehicleModalCase(instantCase);
      return;
    }

    // Nếu dòng IN đã lấy xe có sẵn dòng OUT liên kết ngay trong trang hiện tại -> ghép cặp tức thì 0 ms
    if (verSnapshot >= 0 && dirCode === "IN" && recId > 0) {
      const linkedCheckout = cachedHistoryRecords.find(
        (r) =>
          String(r.direction_code || "").toUpperCase() === "OUT" &&
          Number(r.entry_record_id) === recId
      );
      if (linkedCheckout) {
        const instantInCase = computeLostCaseDetails(
          row,
          linkedCheckout,
          row["Biển số"]
        );
        lostCaseClientCache.set(cacheKey, instantInCase);
        renderLostVehicleModalCase(instantInCase);
        return;
      }
    }

    // Nếu dòng OUT có sẵn entry_record_id đang nằm ngay trong trang hiện tại -> ghép cặp tức thì 0 ms
    if (verSnapshot >= 0 && dirCode === "OUT" && row.entry_record_id) {
      const linkedCheckin = cachedHistoryRecords.find(
        (r) => Number(r["ID"]) === Number(row.entry_record_id)
      );
      if (linkedCheckin) {
        const instantLinkedCase = computeLostCaseDetails(
          linkedCheckin,
          row,
          row["Biển số"]
        );
        lostCaseClientCache.set(cacheKey, instantLinkedCase);
        renderLostVehicleModalCase(instantLinkedCase);
        return;
      }
    }

    renderLostModalLoadingState(row);

    if (!Number.isNaN(recId) && recId > 0) {
      try {
        const res = await fetch(`/api/management/session-case/${recId}`);
        if (reqId !== lostCaseReqSeq || !isLostModalOpen) return;
        if (res.ok) {
          const payload = await res.json();
          if (reqId !== lostCaseReqSeq || !isLostModalOpen) return;
          if (payload && ("checkin_row" in payload || "checkout_row" in payload)) {
            const authoritativeCase = computeLostCaseDetails(
              payload.checkin_row || null,
              payload.checkout_row || null,
              payload.plate_number || row["Biển số"]
            );
            if (verSnapshot >= 0 && verSnapshot === lastRecordsVersion) {
              lostCaseClientCache.set(cacheKey, authoritativeCase);
            }
            renderLostVehicleModalCase(authoritativeCase);
            return;
          }
        }
      } catch (_) {
        if (reqId !== lostCaseReqSeq || !isLostModalOpen) return;
      }
    }

    if (reqId === lostCaseReqSeq && isLostModalOpen) {
      const isOut =
        dirCode === "OUT" || String(row["Luồng"] || "").includes("Ra");
      const fallbackCase = computeLostCaseDetails(
        isOut ? null : row,
        isOut ? row : null,
        row["Biển số"]
      );
      renderLostVehicleModalCase(fallbackCase);
    }
  }

  function closeSnapshotModal() {
    isLostModalOpen = false;
    lostCaseReqSeq += 1;
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
    const btn = e.target.closest("button[data-record-id]");
    if (!btn) return;
    const recId = Number(btn.getAttribute("data-record-id"));
    const row = cachedHistoryRecords.find((r) => Number(r["ID"]) === recId);
    if (!row) return;
    if (btn.classList.contains("snap-thumb-btn")) {
      openSingleSnapshotModalByRow(row);
    } else {
      openLostVehicleModalByRow(row);
    }
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
        paginationRangeText.textContent = "Hiển thị 0–0";
      }
      paginationControls.innerHTML = "";
      return;
    }

    const startIdx = (currentPage - 1) * pageSize + 1;
    const endIdx = Math.min(totalItems, currentPage * pageSize);
    if (paginationRangeText) {
      paginationRangeText.textContent = `Hiển thị ${startIdx}–${endIdx}`;
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
      ledgerCountText.textContent = `${cachedMatchedCount} / ${cachedTotalRecords}`;
    }

    const totalItems = cachedMatchedCount;
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    if (currentPage > totalPages) {
      currentPage = totalPages;
    }
    if (currentPage < 1) {
      currentPage = 1;
    }

    if (totalItems === 0 || cachedHistoryRecords.length === 0) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="6">Không có bản ghi nào khớp điều kiện lọc.</td>
        </tr>
      `;
      renderPaginationControls(0, 1);
      return;
    }

    // Hỗ trợ cả hai chế độ: server đã cắt đúng trang (<= pageSize) hoặc mảng nhiều trang
    const pageSlice =
      cachedHistoryRecords.length > pageSize
        ? cachedHistoryRecords.slice(
            (currentPage - 1) * pageSize,
            (currentPage - 1) * pageSize + pageSize
          )
        : cachedHistoryRecords;

    historyTableBody.innerHTML = pageSlice
      .map(
        (row) => `
          <tr>
            <td><span class="plate-cell-main mono-num num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderSnapshotCell(row)}</td>
            <td>${renderDirectionPill(row)}</td>
            <td class="n mono-num num">${escapeHtml(row["Thời gian nhận diện"])}</td>
            <td class="n mono-num num">#${escapeHtml(row["ID"])}</td>
            <td class="n">
              <button type="button" class="btn btn-sm btn-lost-case" data-record-id="${escapeHtml(row["ID"])}">
                Tra cứu mất xe
              </button>
            </td>
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
        fetchManagementOverview();
      }
    });
  }

  if (pageSizeSelect) {
    pageSizeSelect.addEventListener("change", () => {
      const val = parseInt(pageSizeSelect.value || "10", 10);
      pageSize = Number.isNaN(val) || val < 1 ? 10 : val;
      currentPage = 1;
      fetchManagementOverview();
    });
  }

  function setHistoryTableLoading(isLoading) {
    if (!historyTableBody) return;
    historyTableBody.classList.toggle("table-loading", Boolean(isLoading));
  }

  function applyManagementData(data, includeRecords = true) {
    const records = data.records || [];
    if (data.stats) {
      cachedStatsData = data.stats;
    }
    const stats = data.stats || cachedStatsData || {
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

    if (data.revenue) {
      renderRevenueSection(data.revenue);
    }

    if (data.database_error) {
      showBanner(managementAlertBox, "error", `Chưa kết nối được MySQL: ${data.database_error}`);
    } else {
      showBanner(managementAlertBox, "", "");
    }

    if (includeRecords) {
      setHistoryTableLoading(false);
      if (typeof data.page === "number" && data.page >= 1) {
        currentPage = data.page;
      }
      const matched = typeof data.matched === "number" ? data.matched : records.length;
      renderHistoryTable(records, matched, stats.total_records ?? 0);
    }
  }

  function prefetchNextOverviewPage(ver, query, statusFilter, page, size, totalItems, sortBy = "") {
    if (typeof ver !== "number" || ver < 0) return;
    const totalPages = Math.max(1, Math.ceil((Number(totalItems) || 0) / size));
    const nextPage = page + 1;
    if (nextPage > totalPages) return;

    const nextKey = makeOverviewCacheKey(ver, query, statusFilter, nextPage, size, sortBy);
    if (overviewPageCache.has(nextKey) || overviewPrefetchInFlight.has(nextKey)) {
      return;
    }

    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (statusFilter && statusFilter !== "all") {
      params.set("status", statusFilter);
    }
    if (sortBy) {
      params.set("sort", sortBy);
    }
    params.set("page", String(nextPage));
    params.set("page_size", String(size));
    params.set("include_revenue", "false");

    overviewPrefetchInFlight.add(nextKey);
    fetch(`/api/management/overview?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data || data.database_error) return;
        const dataVer =
          typeof data.records_version === "number" ? data.records_version : ver;
        if (dataVer === lastRecordsVersion) {
          setOverviewClientCache(nextKey, data);
        }
      })
      .catch(() => {})
      .finally(() => {
        overviewPrefetchInFlight.delete(nextKey);
      });
  }

  function updateDirectionSortHeaderUI() {
    if (!thDirectionSort || !directionSortIndicator) return;
    const isOutTab = activeStatusFilter === "direction_out";
    thDirectionSort.classList.toggle("sortable-th", isOutTab);
    if (!isOutTab) {
      thDirectionSort.removeAttribute("title");
      directionSortIndicator.textContent = "";
      return;
    }
    thDirectionSort.title = "Bấm để sắp xếp Ra bãi lệch mặt / không lệch mặt";
    if (activeDirectionSort === "mismatch_first") {
      directionSortIndicator.textContent = "▾";
    } else if (activeDirectionSort === "matched_first") {
      directionSortIndicator.textContent = "▴";
    } else {
      directionSortIndicator.textContent = "⇅";
    }
  }

  async function fetchManagementOverview(options = {}) {
    const forceNetwork = Boolean(options && options.forceNetwork);
    const reqSeq = ++overviewReqSeq;

    const isRevenueOnly = activeViewId === "view-revenue";
    const query = (searchPlateInput.value || "").trim();
    const statusFilter = activeStatusFilter || "all";
    const sortBy = statusFilter === "direction_out" ? activeDirectionSort : "";
    const requestedPage = currentPage;
    const requestedSize = pageSize;

    // Trả ngay 0 ms từ RAM nếu trang đã có trong cache hoặc vừa được prefetch
    if (!forceNetwork && !isRevenueOnly && lastRecordsVersion >= 0) {
      const hitKey = makeOverviewCacheKey(
        lastRecordsVersion,
        query,
        statusFilter,
        requestedPage,
        requestedSize,
        sortBy
      );
      if (overviewPageCache.has(hitKey)) {
        const cachedPayload = overviewPageCache.get(hitKey);
        applyManagementData(cachedPayload, true);
        prefetchNextOverviewPage(
          lastRecordsVersion,
          query,
          statusFilter,
          currentPage,
          requestedSize,
          cachedPayload.matched,
          sortBy
        );
        return;
      }
    }
    if (!forceNetwork && isRevenueOnly && lastRecordsVersion >= 0 && cachedRevenueData) {
      if (cachedStatsData) {
        applyManagementData(
          { stats: cachedStatsData, revenue: cachedRevenueData, database_error: null },
          false
        );
      } else {
        renderRevenueSection(cachedRevenueData);
      }
      return;
    }

    const params = new URLSearchParams();
    if (isRevenueOnly) {
      params.set("include_records", "false");
      params.set("include_revenue", "true");
    } else {
      if (query) params.set("q", query);
      if (statusFilter && statusFilter !== "all") {
        params.set("status", statusFilter);
      }
      if (sortBy) {
        params.set("sort", sortBy);
      }
      params.set("page", String(requestedPage));
      params.set("page_size", String(requestedSize));
      params.set("include_revenue", "false");
      setHistoryTableLoading(true);
    }
    const qs = params.toString();
    const url = `/api/management/overview?${qs}`;

    overviewInFlight = true;
    try {
      const res = await fetch(url);
      if (reqSeq !== overviewReqSeq) return;
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (reqSeq !== overviewReqSeq) return;
      if (typeof data.records_version === "number") {
        if (data.records_version !== lastRecordsVersion) {
          clearClientManagementCaches();
        }
        lastRecordsVersion = data.records_version;
      }
      applyManagementData(data, !isRevenueOnly);
      if (!isRevenueOnly && !data.database_error && lastRecordsVersion >= 0) {
        const resolvedPage =
          typeof data.page === "number" && data.page >= 1 ? data.page : requestedPage;
        const storeKey = makeOverviewCacheKey(
          lastRecordsVersion,
          query,
          statusFilter,
          resolvedPage,
          requestedSize,
          sortBy
        );
        setOverviewClientCache(storeKey, data);
        prefetchNextOverviewPage(
          lastRecordsVersion,
          query,
          statusFilter,
          resolvedPage,
          requestedSize,
          data.matched,
          sortBy
        );
      }
    } catch (_) {
      if (reqSeq !== overviewReqSeq) return;
      setHistoryTableLoading(false);
      showBanner(managementAlertBox, "error", "Không kết nối được tới máy chủ FastAPI.");
    } finally {
      if (reqSeq === overviewReqSeq) {
        overviewInFlight = false;
      }
    }
  }

  tabLinks.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabLinks.forEach((b) => b.setAttribute("aria-selected", "false"));
      btn.setAttribute("aria-selected", "true");
      activeStatusFilter = btn.getAttribute("data-status-filter") || "all";
      if (activeStatusFilter !== "direction_out") {
        activeDirectionSort = "";
      }
      updateDirectionSortHeaderUI();
      currentPage = 1;
      fetchManagementOverview();
    });
  });

  if (thDirectionSort) {
    thDirectionSort.addEventListener("click", () => {
      if (activeStatusFilter !== "direction_out") return;
      if (activeDirectionSort === "") {
        activeDirectionSort = "mismatch_first";
      } else if (activeDirectionSort === "mismatch_first") {
        activeDirectionSort = "matched_first";
      } else {
        activeDirectionSort = "";
      }
      updateDirectionSortHeaderUI();
      currentPage = 1;
      fetchManagementOverview();
    });
  }

  searchPlateInput.addEventListener("input", () => {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      currentPage = 1;
      fetchManagementOverview();
    }, 200);
  });

  // ==================== XUẤT BÁO CÁO PDF (LỊCH SỬ / DOANH THU / BIÊN BẢN MẤT XE) ====================
  function formatCurrentTimestamp() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  function openPrintablePdfDocument(docTitle, bodyHtml) {
    const fullHtml = `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <title>${escapeHtml(docTitle)}</title>
  <style>
    @page { size: A4; margin: 14mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 0;
      font-family: "IBM Plex Sans", "Segoe UI", Arial, sans-serif;
      color: #0f172a;
      background: #ffffff;
      font-size: 12.5px;
      line-height: 1.45;
    }
    .report-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 2px solid #0f172a;
      padding-bottom: 10px;
      margin-bottom: 14px;
    }
    .report-title {
      margin: 0 0 4px 0;
      font-size: 18px;
      font-weight: 700;
      text-transform: uppercase;
      color: #0f172a;
    }
    .report-subtitle {
      margin: 0;
      font-size: 12px;
      color: #475569;
    }
    .report-meta {
      text-align: right;
      font-size: 11.5px;
      color: #334155;
    }
    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .kpi-box {
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 8px 12px;
      background: #f8fafc;
    }
    .kpi-box-label {
      font-size: 11px;
      color: #64748b;
      display: block;
      margin-bottom: 2px;
    }
    .kpi-box-val {
      font-size: 16px;
      font-weight: 700;
      color: #0f172a;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
    }
    th, td {
      border: 1px solid #cbd5e1;
      padding: 6px 8px;
      text-align: left;
      vertical-align: middle;
      font-size: 12px;
    }
    th {
      background: #f1f5f9;
      font-weight: 700;
      color: #1e293b;
    }
    td.n, th.n {
      text-align: right;
    }
    .thumb-pair {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .thumb-plate {
      width: 58px;
      height: 28px;
      object-fit: cover;
      border: 1px solid #94a3b8;
      border-radius: 3px;
    }
    .thumb-face {
      width: 28px;
      height: 28px;
      object-fit: cover;
      border: 1px solid #94a3b8;
      border-radius: 50%;
    }
    .verdict-box {
      border: 1px solid #94a3b8;
      background: #f8fafc;
      border-radius: 6px;
      padding: 10px 12px;
      font-weight: 600;
      margin-bottom: 14px;
    }
    .case-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
    }
    .case-col {
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 10px;
    }
    .case-col h4 {
      margin: 0 0 8px 0;
      font-size: 13px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 5px;
    }
    .case-img-box {
      margin-top: 8px;
      text-align: center;
    }
    .case-img-box img {
      max-width: 100%;
      height: 110px;
      object-fit: contain;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      background: #0f172a;
    }
  </style>
</head>
<body>
  ${bodyHtml}
</body>
</html>`;

    const printWin =
      typeof window.open === "function"
        ? window.open("", "_blank", "width=980,height=740")
        : null;
    if (printWin && printWin.document) {
      printWin.document.open();
      printWin.document.write(fullHtml);
      printWin.document.close();
      setTimeout(() => {
        try {
          printWin.focus();
          printWin.print();
        } catch (_) {}
      }, 280);
      return { mode: "popup", html: fullHtml };
    }

    // Fallback khi trình duyệt chặn Popup: tạo <iframe> ẩn và gọi contentWindow.print() trên đúng mẫu A4 nền trắng
    if (document && typeof document.createElement === "function" && document.body) {
      const iframe = document.createElement("iframe");
      iframe.style.cssText =
        "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;";
      document.body.appendChild(iframe);
      const idoc =
        iframe.contentDocument ||
        (iframe.contentWindow && iframe.contentWindow.document);
      if (idoc) {
        idoc.open();
        idoc.write(fullHtml);
        idoc.close();
      }
      const cleanupIframe = () => {
        try {
          iframe.remove();
        } catch (_) {}
      };
      if (iframe.contentWindow) {
        iframe.contentWindow.onafterprint = cleanupIframe;
      }
      setTimeout(() => {
        try {
          if (iframe.contentWindow) {
            iframe.contentWindow.focus();
            iframe.contentWindow.print();
          }
        } catch (_) {}
        setTimeout(cleanupIframe, 60000);
      }, 280);
      return { mode: "iframe", html: fullHtml };
    }

    if (typeof window.print === "function") {
      window.print();
    }
    return { mode: "fallback", html: fullHtml };
  }

  async function exportHistoryPdfReport() {
    if (btnExportHistoryPdf && btnExportHistoryPdf.disabled) return null;
    if (btnExportHistoryPdf) btnExportHistoryPdf.disabled = true;

    try {
      const filterNameMap = {
        all: "Tất cả bản ghi",
        in_parking: "Đang gửi trong bãi",
        direction_in: "Lượt vào bãi",
        direction_out: "Lượt ra bãi",
      };
      const filterLabel = filterNameMap[activeStatusFilter] || "Tất cả bản ghi";
      const searchQuery = ((searchPlateInput && searchPlateInput.value) || "").trim();
      const inParkingVal = (statInParking && statInParking.textContent) || "0";
      const todayVal = (statTodayRecords && statTodayRecords.textContent) || "0";
      const totalVal = (statTotalRecords && statTotalRecords.textContent) || "0";

      let recordsForPdf = cachedHistoryRecords;
      let totalMatchedForPdf = cachedMatchedCount || cachedHistoryRecords.length;
      try {
        const params = new URLSearchParams();
        if (searchQuery) params.set("q", searchQuery);
        if (activeStatusFilter && activeStatusFilter !== "all") {
          params.set("status", activeStatusFilter);
        }
        if (activeStatusFilter === "direction_out" && activeDirectionSort) {
          params.set("sort", activeDirectionSort);
        }
        params.set("limit", "200");
        const res = await fetch(`/api/management/overview?${params.toString()}`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.records)) {
            recordsForPdf = data.records;
            totalMatchedForPdf =
              typeof data.matched === "number" ? data.matched : data.records.length;
          }
        }
      } catch (_) {}

      const rowsHtml =
        recordsForPdf.length === 0
          ? `<tr><td colspan="6">Không có bản ghi nào khớp điều kiện lọc.</td></tr>`
          : recordsForPdf
              .map((row) => {
                const snap = getRowSnapshots(row);
                const imgHtml =
                  snap.hasRealPlate || snap.hasRealFace
                    ? `<span class="thumb-pair">
                        ${snap.hasRealPlate ? `<img class="thumb-plate" src="${snap.realPlateImg}" alt="Biển số" />` : `<span>Không có ảnh biển</span>`}
                        ${snap.hasRealFace ? `<img class="thumb-face" src="${snap.realFaceImg}" alt="Khuôn mặt" />` : `<span>Không có ảnh mặt</span>`}
                      </span>`
                    : "Không có ảnh lưu trữ";
                return `
                  <tr>
                    <td><strong>${escapeHtml(row["Biển số"])}</strong></td>
                    <td>${imgHtml}</td>
                    <td>${escapeHtml(row["Luồng"])}</td>
                    <td>${escapeHtml(row["Đối chiếu"] || "-")}</td>
                    <td class="n">${escapeHtml(row["Thời gian nhận diện"])}</td>
                    <td class="n">#${escapeHtml(row["ID"])}</td>
                  </tr>
                `;
              })
              .join("");

      const limitNote =
        totalMatchedForPdf > recordsForPdf.length
          ? ` (hiển thị ${recordsForPdf.length}/${totalMatchedForPdf} bản ghi mới nhất)`
          : "";

      const bodyHtml = `
        <header class="report-header">
          <div>
            <h1 class="report-title">BÁO CÁO LỊCH SỬ &amp; QUẢN LÝ RA VÀO BÃI XE</h1>
            <p class="report-subtitle">Hệ thống Quản lý Bãi giữ xe Trường học AI Nhận diện Biển số &amp; Khuôn mặt</p>
          </div>
          <div class="report-meta">
            <div>Ngày xuất: <strong>${escapeHtml(formatCurrentTimestamp())}</strong></div>
            <div>Bộ lọc: <strong>${escapeHtml(filterLabel)}</strong>${
        searchQuery ? ` · Tìm biển số: <strong>${escapeHtml(searchQuery)}</strong>` : ""
      }</div>
          </div>
        </header>

        <div class="kpi-strip">
          <div class="kpi-box">
            <span class="kpi-box-label">Đang gửi trong bãi</span>
            <strong class="kpi-box-val">${escapeHtml(inParkingVal)}</strong>
          </div>
          <div class="kpi-box">
            <span class="kpi-box-label">Lượt vào / ra hôm nay</span>
            <strong class="kpi-box-val">${escapeHtml(todayVal)}</strong>
          </div>
          <div class="kpi-box">
            <span class="kpi-box-label">Tổng lượt lưu trữ</span>
            <strong class="kpi-box-val">${escapeHtml(totalVal)}</strong>
          </div>
          <div class="kpi-box">
            <span class="kpi-box-label">Số bản ghi trong báo cáo</span>
            <strong class="kpi-box-val">${escapeHtml(recordsForPdf.length)}${escapeHtml(limitNote)}</strong>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>Biển số xe</th>
              <th>Ảnh cắt (Biển &amp; Mặt)</th>
              <th>Luồng</th>
              <th>Đối chiếu FaceNet</th>
              <th class="n">Thời gian</th>
              <th class="n">Mã ghi</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      `;

      return openPrintablePdfDocument("Bao_Cao_Lich_Su_Bai_Xe", bodyHtml);
    } finally {
      if (btnExportHistoryPdf) btnExportHistoryPdf.disabled = false;
    }
  }

  function exportRevenuePdfReport() {
    const periodLabelMap = {
      daily: "Theo ngày (DD/MM/YYYY)",
      monthly: "Theo tháng (MM/YYYY)",
      yearly: "Theo năm (YYYY)",
    };
    const periodTitle = periodLabelMap[activeRevenuePeriod] || "Kỳ thống kê";
    const rev = cachedRevenueData || {};
    const unitFee = rev.unit_price || 2000;
    const unitFeeText = formatVnd(unitFee);
    const today = rev.today || { tickets: 0, revenue: 0 };
    const month = rev.month || { tickets: 0, revenue: 0 };
    const year = rev.year || { tickets: 0, revenue: 0 };
    const total = rev.total || { tickets: 0, revenue: 0 };
    const rows = rev[activeRevenuePeriod] || [];

    const rowsHtml =
      rows.length === 0
        ? `<tr><td colspan="4">Chưa có dữ liệu doanh thu trong kỳ này.</td></tr>`
        : rows
            .map(
              (item) => `
                <tr>
                  <td><strong>${escapeHtml(item.period)}</strong></td>
                  <td class="n">${escapeHtml(item.tickets)} lượt</td>
                  <td class="n">${escapeHtml(unitFeeText)}</td>
                  <td class="n"><strong>${escapeHtml(formatVnd(item.revenue))}</strong></td>
                </tr>
              `
            )
            .join("");

    const bodyHtml = `
      <header class="report-header">
        <div>
          <h1 class="report-title">BÁO CÁO QUẢN LÝ DOANH THU GIỮ XE</h1>
          <p class="report-subtitle">Đơn giá áp dụng: ${escapeHtml(unitFeeText)} / lượt gửi · Chu kỳ bảng: ${escapeHtml(periodTitle)}</p>
        </div>
        <div class="report-meta">
          <div>Ngày xuất: <strong>${escapeHtml(formatCurrentTimestamp())}</strong></div>
        </div>
      </header>

      <div class="kpi-strip">
        <div class="kpi-box">
          <span class="kpi-box-label">Doanh thu hôm nay (${escapeHtml(today.tickets ?? 0)} lượt)</span>
          <strong class="kpi-box-val">${escapeHtml(formatVnd(today.revenue))}</strong>
        </div>
        <div class="kpi-box">
          <span class="kpi-box-label">Doanh thu tháng này (${escapeHtml(month.tickets ?? 0)} lượt)</span>
          <strong class="kpi-box-val">${escapeHtml(formatVnd(month.revenue))}</strong>
        </div>
        <div class="kpi-box">
          <span class="kpi-box-label">Doanh thu năm nay (${escapeHtml(year.tickets ?? 0)} lượt)</span>
          <strong class="kpi-box-val">${escapeHtml(formatVnd(year.revenue))}</strong>
        </div>
        <div class="kpi-box">
          <span class="kpi-box-label">Tổng doanh thu tích lũy (${escapeHtml(total.tickets ?? 0)} lượt)</span>
          <strong class="kpi-box-val">${escapeHtml(formatVnd(total.revenue))}</strong>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>${escapeHtml(periodTitle)}</th>
            <th class="n">Số lượt gửi xe</th>
            <th class="n">Đơn giá / lượt</th>
            <th class="n">Tổng doanh thu</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    `;

    return openPrintablePdfDocument("Bao_Cao_Doanh_Thu_Bai_Xe", bodyHtml);
  }

  function exportLostCasePdfReport() {
    if (!activeLostCase) return null;
    const c = activeLostCase;
    const bodyHtml = `
      <header class="report-header">
        <div>
          <h1 class="report-title">BIÊN BẢN TRA CỨU &amp; XỬ LÝ TÌNH HUỐNG MẤT XE</h1>
          <p class="report-subtitle">Biển số tra cứu: <strong>${escapeHtml(c.plateNumber)}</strong></p>
        </div>
        <div class="report-meta">
          <div>Ngày xuất: <strong>${escapeHtml(formatCurrentTimestamp())}</strong></div>
        </div>
      </header>

      <div class="verdict-box">${escapeHtml(c.verdictText)}</div>

      <div class="case-grid">
        <div class="case-col">
          <h4>1. CHECK IN (LÚC GỬI XE)</h4>
          <div>Mã bản ghi: <strong>${c.checkinRow ? `#${escapeHtml(c.checkinRow["ID"])}` : "-"}</strong></div>
          <div>Thời gian vào: <strong>${escapeHtml(c.checkinRow ? c.checkinRow["Thời gian nhận diện"] : "-")}</strong></div>
          <div>Biển số: <strong>${escapeHtml(c.plateNumber)}</strong></div>
          <div class="case-img-box">
            <div>Ảnh biển số Check-in</div>
            ${c.checkinSnap.realPlateImg ? `<img src="${c.checkinSnap.realPlateImg}" alt="Biển số lúc vào" />` : `<p>Không có ảnh lưu trữ</p>`}
          </div>
          <div class="case-img-box">
            <div>Ảnh khuôn mặt Người gửi xe</div>
            ${c.checkinSnap.realFaceImg ? `<img src="${c.checkinSnap.realFaceImg}" alt="Người gửi xe" />` : `<p>Không có ảnh lưu trữ</p>`}
          </div>
        </div>

        <div class="case-col">
          <h4>2. CHECK OUT (LÚC LẤY XE)</h4>
          <div>Mã bản ghi: <strong>${c.checkoutRow ? `#${escapeHtml(c.checkoutRow["ID"])}` : c.sessionClosedMissingExit ? "Phiên đã đóng, thiếu thông tin lượt ra" : "Chưa có lượt ra"}</strong></div>
          <div>Thời gian ra: <strong>${escapeHtml(c.checkoutRow ? c.checkoutRow["Thời gian nhận diện"] : c.sessionClosedMissingExit ? "Phiên đã đóng, thiếu thông tin lượt ra" : "Chưa có lượt ra")}</strong></div>
          <div>Đối chiếu FaceNet: <strong>${escapeHtml(c.matchLabel)}</strong></div>
          ${
            c.checkoutSnap
              ? `<div class="case-img-box">
                  <div>Ảnh biển số Check-out</div>
                  ${c.checkoutSnap.realPlateImg ? `<img src="${c.checkoutSnap.realPlateImg}" alt="Biển số lúc ra" />` : `<p>Không có ảnh lưu trữ</p>`}
                </div>`
              : `<p>${c.sessionClosedMissingExit ? "Phiên đã đóng, thiếu thông tin lượt ra." : "Chưa ghi nhận lượt Check-out qua cổng."}</p>`
          }
        </div>

        <div class="case-col">
          <h4>3. NGƯỜI LẤY XE</h4>
          <div>Kết quả đối chiếu: <strong>${escapeHtml(c.matchLabel)}</strong></div>
          ${
            c.checkoutSnap
              ? `<div class="case-img-box">
                  <div>Ảnh khuôn mặt Người lấy xe</div>
                  ${c.checkoutSnap.realFaceImg ? `<img src="${c.checkoutSnap.realFaceImg}" alt="Người lấy xe" />` : `<p>Không có ảnh lưu trữ</p>`}
                </div>`
              : `<p>Chưa có ảnh Người lấy xe.</p>`
          }
          <p>${escapeHtml(c.takerNote)}</p>
        </div>
      </div>
    `;
    return openPrintablePdfDocument(`Bien_Ban_Mat_Xe_${c.plateNumber}`, bodyHtml);
  }

  if (btnExportHistoryPdf) {
    btnExportHistoryPdf.addEventListener("click", () => exportHistoryPdfReport());
  }
  if (btnExportRevenuePdf) {
    btnExportRevenuePdf.addEventListener("click", () => exportRevenuePdfReport());
  }
  if (btnExportLostCasePdf) {
    btnExportLostCasePdf.addEventListener("click", () => exportLostCasePdfReport());
  }

  btnRefreshManagement.addEventListener("click", async () => {
    btnRefreshManagement.disabled = true;
    clearClientManagementCaches();
    cachedRevenueData = null;
    try {
      const res = await fetch("/api/management/reconnect", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Chưa kết nối được MySQL.");
      }
      await fetchManagementOverview({ forceNetwork: true });
      showBanner(managementAlertBox, "success", "Đã làm mới dữ liệu từ MySQL.");
    } catch (err) {
      await fetchManagementOverview({ forceNetwork: true });
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
