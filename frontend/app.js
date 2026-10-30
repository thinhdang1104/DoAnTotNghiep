(() => {
  // Navigation & Topbar elements
  const navRecognition = document.getElementById("nav-recognition");
  const navManagement = document.getElementById("nav-management");
  const navItems = [navRecognition, navManagement];
  const views = document.querySelectorAll(".screen-view");
  const dbStatusPill = document.getElementById("db-status-pill");
  const navPendingBadge = document.getElementById("nav-pending-badge");

  // Screen 1: Camera & Active Cam Switcher elements
  const cameraAlertBox = document.getElementById("camera-alert-box");
  const btnCam1 = document.getElementById("btn-cam-1");
  const btnCam2 = document.getElementById("btn-cam-2");
  const activeCamRolePill = document.getElementById("active-cam-role-pill");

  const cameraIndexInput = document.getElementById("camera-index-input");
  const btnScanCamera = document.getElementById("btn-scan-camera");
  const btnStartCamera = document.getElementById("btn-start-camera");
  const btnStopCamera = document.getElementById("btn-stop-camera");
  const cameraStreamImg = document.getElementById("camera-stream-img");
  const cameraPlaceholder = document.getElementById("camera-placeholder");
  const voteAmbiguousWarning = document.getElementById("vote-ambiguous-warning");

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

  const liveVotePill = document.getElementById("live-vote-pill");
  const livePlateValue = document.getElementById("live-plate-value");
  const liveFaceValue = document.getElementById("live-face-value");
  const btnJumpLedger = document.getElementById("btn-jump-ledger");
  const recentMiniTbody = document.getElementById("recent-mini-tbody");

  // Screen 2: Management & Ledger elements
  const managementAlertBox = document.getElementById("management-alert-box");
  const statInParking = document.getElementById("stat-in-parking");
  const statTodayRecords = document.getElementById("stat-today-records");
  const statTotalRecords = document.getElementById("stat-total-records");
  const statPendingRecords = document.getElementById("stat-pending-records");

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

  let activeStatusFilter = "all";
  let isCameraStreaming = false;
  let lastRecordsVersion = -1;
  let lastFeedbackText = "";
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

  if (btnJumpLedger) {
    btnJumpLedger.addEventListener("click", () => {
      activateView("view-management");
    });
  }

  if (
    window.location.hash === "#management" ||
    new URLSearchParams(window.location.search).get("view") === "management"
  ) {
    activateView("view-management");
  }

  function updateDatabaseStatusUI(serverOnline, dbReady, pendingCount) {
    if (dbStatusPill) {
      if (!serverOnline) {
        dbStatusPill.className = "pill neg";
        dbStatusPill.textContent = "Mất kết nối máy chủ";
      } else if (dbReady) {
        dbStatusPill.className = "pill pos";
        dbStatusPill.textContent = "MySQL: Đã kết nối";
      } else {
        dbStatusPill.className = "pill warn";
        dbStatusPill.textContent = "MySQL: Lưu tạm";
      }
    }

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

  // ==================== ACTIVE CAM SWITCHER (CAM 1 / CAM 2) ====================
  function updateActiveCamUI(activeCam, latched) {
    const isCam1 = activeCam === 1;
    if (btnCam1) btnCam1.setAttribute("aria-pressed", isCam1 ? "true" : "false");
    if (btnCam2) btnCam2.setAttribute("aria-pressed", !isCam1 ? "true" : "false");

    if (activeCamRolePill) {
      if (latched) {
        activeCamRolePill.className = "pill pos";
        activeCamRolePill.textContent = `Đang ở Cam ${activeCam} · Đón khuôn mặt ${latched.direction === "IN" ? "VÀO" : "RA"}`;
      } else if (isCam1) {
        activeCamRolePill.className = "pill warn";
        activeCamRolePill.textContent = "Cam 1: Soi biển RA / Mặt VÀO";
      } else {
        activeCamRolePill.className = "pill pos";
        activeCamRolePill.textContent = "Cam 2: Soi biển VÀO / Mặt RA";
      }
    }
  }

  async function switchCameraRole(targetCam) {
    try {
      const res = await fetch("/api/camera/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_cam: targetCam }),
      });
      if (res.ok) {
        const data = await res.json();
        updateActiveCamUI(data.active_cam, null);
        await pollCameraStatusOnce();
      }
    } catch {
      // Ignore transient network error
    }
  }

  if (btnCam1) {
    btnCam1.addEventListener("click", () => switchCameraRole(1));
  }
  if (btnCam2) {
    btnCam2.addEventListener("click", () => switchCameraRole(2));
  }

  window.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (e.key === "1") {
      switchCameraRole(1);
    } else if (e.key === "2") {
      switchCameraRole(2);
    }
  });

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

  // ==================== CAMERA CONTROLS ====================
  btnScanCamera.addEventListener("click", async () => {
    btnScanCamera.disabled = true;
    showBanner(cameraAlertBox, "", "Đang dò các cổng camera (0 - 5)...");
    try {
      const res = await fetch("/api/camera/scan", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể dò cổng camera.");
      }
      if (data.cameras && data.cameras.length > 0) {
        const listText = data.cameras.map((c) => `cổng ${c.index}`).join(", ");
        cameraIndexInput.value = data.cameras[0].index;
        showBanner(cameraAlertBox, "success", `Tìm thấy camera tại: ${listText}.`);
      } else {
        showBanner(cameraAlertBox, "error", "Không tìm thấy camera nào từ cổng 0 đến 5.");
      }
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    } finally {
      if (!isCameraStreaming) {
        btnScanCamera.disabled = false;
      }
    }
  });

  btnStartCamera.addEventListener("click", async () => {
    const deviceIndex = parseInt(cameraIndexInput.value || "0", 10);
    btnStartCamera.disabled = true;
    btnScanCamera.disabled = true;
    showBanner(cameraAlertBox, "", `Đang kết nối camera cổng ${deviceIndex}...`);
    try {
      const res = await fetch("/api/camera/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_index: deviceIndex }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể mở camera.");
      }
      showBanner(cameraAlertBox, "", "");
      await pollCameraStatusOnce();
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
      btnStartCamera.disabled = false;
      btnScanCamera.disabled = false;
    }
  });

  btnStopCamera.addEventListener("click", async () => {
    btnStopCamera.disabled = true;
    try {
      await fetch("/api/camera/stop", { method: "POST" });
      await pollCameraStatusOnce();
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    }
  });

  function updateRecentFeed(pendingRecords, confirmedRecords) {
    const combined = [...(pendingRecords || []), ...(confirmedRecords || [])].slice(0, 5);
    if (combined.length === 0) {
      recentMiniTbody.innerHTML = `
        <tr>
          <td colspan="5">Chưa có bản ghi nhận diện.</td>
        </tr>
      `;
      return;
    }

    recentMiniTbody.innerHTML = combined
      .map((row) => {
        const timePart = String(row["Thời gian nhận diện"] || "").split(" ").pop() || "-";
        return `
          <tr>
            <td><span class="plate-cell-main num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderDirectionPill(row["Luồng"])}</td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td>${renderMatchPill(row["Đối chiếu"])}</td>
            <td class="n num">${escapeHtml(timePart)}</td>
          </tr>
        `;
      })
      .join("");
  }

  async function pollCameraStatusOnce() {
    try {
      const res = await fetch("/api/camera/status");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const state = await res.json();

      updateDatabaseStatusUI(true, state.database_ready, state.pending_count);
      updateActiveCamUI(state.active_cam || 2, state.latched);

      if (state.running) {
        if (!isCameraStreaming) {
          isCameraStreaming = true;
          cameraStreamImg.src = `/api/camera/stream?t=${Date.now()}`;
          cameraStreamImg.classList.remove("hidden");
          cameraPlaceholder.classList.add("hidden");
        }
        cameraIndexInput.disabled = true;
        btnScanCamera.disabled = true;
        btnStartCamera.disabled = true;
        btnStopCamera.disabled = false;
      } else {
        if (isCameraStreaming) {
          isCameraStreaming = false;
          cameraStreamImg.removeAttribute("src");
          cameraStreamImg.classList.add("hidden");
          cameraPlaceholder.classList.remove("hidden");
        }
        cameraIndexInput.disabled = false;
        btnScanCamera.disabled = false;
        btnStartCamera.disabled = false;
        btnStopCamera.disabled = true;
      }

      if (state.error) {
        showBanner(cameraAlertBox, "error", state.error);
      } else if (state.gate_feedback && state.gate_feedback.message) {
        if (state.gate_feedback.message !== lastFeedbackText) {
          lastFeedbackText = state.gate_feedback.message;
          showBanner(
            cameraAlertBox,
            state.gate_feedback.type || "success",
            state.gate_feedback.message
          );
        }
      }

      // Two-Phase Latch UI
      if (state.latched) {
        latchStatusBox.classList.remove("hidden");
        const isIn = state.latched.direction === "IN";
        latchDirectionBadge.className = isIn ? "pill pos" : "pill warn";
        latchDirectionBadge.textContent = isIn ? "LƯU HỜ · ĐI VÀO" : "LƯU HỜ · ĐI RA";
        latchPlateText.textContent = state.latched.plate_number;
        latchStepText.textContent = state.latched.sampling_face
          ? `Đang chọn khuôn mặt nét nhất ở Cam ${state.latched.required_face_cam}...`
          : `Đang chờ khuôn mặt chuẩn ở Cam ${state.latched.required_face_cam} (${state.latched.remaining_seconds}s)`;
        livePlateValue.textContent = state.latched.plate_number;
      } else {
        latchStatusBox.classList.add("hidden");
        if (state.current_plates && state.current_plates.length > 0) {
          livePlateValue.textContent = state.current_plates.join(", ");
        } else {
          livePlateValue.textContent = "-";
        }
      }

      // Security Alert UI (Face mismatch on exit)
      if (state.security_alert) {
        securityAlertBox.classList.remove("hidden");
        alertScorePill.textContent = `Độ khớp: ${state.security_alert.match_score_pct}`;
        alertDetailText.textContent =
          `Xe ${state.security_alert.plate_number} (gửi lúc ${state.security_alert.entry_time}) ` +
          `có khuôn mặt người lấy xe LỆCH so với lúc gửi vào (Cosine ${state.security_alert.match_score_pct} < 45%).`;
      } else {
        securityAlertBox.classList.add("hidden");
      }

      if (state.current_faces && state.current_faces.length > 0) {
        const bestConf = Math.round(Math.max(...state.current_faces) * 100);
        liveFaceValue.textContent = `Có (${bestConf}%)`;
      } else {
        liveFaceValue.textContent = "-";
      }

      if (state.vote) {
        const { vote_count, sample_count, vote_share } = state.vote;
        const pct = Math.round(vote_share * 100);
        liveVotePill.textContent = `${vote_count}/${sample_count} mẫu (${pct}%)`;
      } else if (state.latched) {
        liveVotePill.textContent = "Đã chốt biển · Chờ mặt";
      } else {
        liveVotePill.textContent = "0/3 mẫu";
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
      updateDatabaseStatusUI(false, false, 0);
    }
  }

  async function pollLoop() {
    await pollCameraStatusOnce();
    setTimeout(pollLoop, 400);
  }

  // ==================== MANAGEMENT & HISTORY TABLE ====================
  function renderHistoryTable(records, matchedCount, totalRecords) {
    if (ledgerCountText) {
      ledgerCountText.textContent = `${matchedCount} / ${totalRecords} bản ghi`;
    }

    if (!records || records.length === 0) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="8">Không có bản ghi nào khớp điều kiện lọc.</td>
        </tr>
      `;
      return;
    }

    historyTableBody.innerHTML = records
      .map(
        (row) => `
          <tr>
            <td><span class="plate-cell-main num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderDirectionPill(row["Luồng"])}</td>
            <td>${renderParkingStatusPill(row["Trạng thái bãi"])}</td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td>${renderMatchPill(row["Đối chiếu"])}</td>
            <td class="n num">${escapeHtml(row["Đồng thuận biển số"] || "-")}</td>
            <td class="n num">${escapeHtml(row["Thời gian nhận diện"])}</td>
            <td class="n num">#${escapeHtml(row["ID"])}</td>
          </tr>
        `
      )
      .join("");
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

    updateDatabaseStatusUI(true, data.database_ready, pending.length);

    if (statInParking) statInParking.textContent = String(stats.in_parking ?? 0);
    statTodayRecords.textContent = String(stats.today_records ?? 0);
    statTotalRecords.textContent = String(stats.total_records ?? 0);
    statPendingRecords.textContent = String(pending.length);

    if (tabCountAll) tabCountAll.textContent = String(stats.total_records ?? 0);
    if (tabCountParking) tabCountParking.textContent = String(stats.in_parking ?? 0);
    if (tabCountIn) tabCountIn.textContent = String(stats.total_in ?? 0);
    if (tabCountOut) tabCountOut.textContent = String(stats.total_out ?? 0);

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
            <td><span class="plate-cell-main num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderDirectionPill(row["Luồng"])}</td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td class="n num">${escapeHtml(row["Đồng thuận biển số"])}</td>
            <td class="n num">${escapeHtml(row["Thời gian nhận diện"])}</td>
          </tr>
        `
        )
        .join("");
    } else {
      pendingSection.classList.add("hidden");
      pendingTableBody.innerHTML = "";
    }

    const query = (searchPlateInput.value || "").trim();
    if (!query && activeStatusFilter === "all") {
      updateRecentFeed(pending, records);
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
      updateDatabaseStatusUI(false, false, 0);
      showBanner(managementAlertBox, "error", "Không kết nối được tới máy chủ FastAPI.");
    }
  }

  tabLinks.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabLinks.forEach((b) => b.setAttribute("aria-selected", "false"));
      btn.setAttribute("aria-selected", "true");
      activeStatusFilter = btn.getAttribute("data-status-filter") || "all";
      fetchManagementOverview();
    });
  });

  searchPlateInput.addEventListener("input", () => {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
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
