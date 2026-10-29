(() => {
  // Navigation & Topbar elements
  const navRecognition = document.getElementById("nav-recognition");
  const navManagement = document.getElementById("nav-management");
  const navItems = [navRecognition, navManagement];
  const views = document.querySelectorAll(".screen-view");
  const dbStatusPill = document.getElementById("db-status-pill");
  const navPendingBadge = document.getElementById("nav-pending-badge");

  // Screen 1: Camera elements
  const cameraAlertBox = document.getElementById("camera-alert-box");
  const cameraIndexInput = document.getElementById("camera-index-input");
  const btnScanCamera = document.getElementById("btn-scan-camera");
  const btnStartCamera = document.getElementById("btn-start-camera");
  const btnStopCamera = document.getElementById("btn-stop-camera");
  const cameraStreamImg = document.getElementById("camera-stream-img");
  const cameraPlaceholder = document.getElementById("camera-placeholder");
  const voteAmbiguousWarning = document.getElementById("vote-ambiguous-warning");

  const liveVotePill = document.getElementById("live-vote-pill");
  const livePlateValue = document.getElementById("live-plate-value");
  const liveFaceValue = document.getElementById("live-face-value");
  const btnJumpLedger = document.getElementById("btn-jump-ledger");
  const recentMiniTbody = document.getElementById("recent-mini-tbody");

  // Screen 2: Management & Ledger elements
  const managementAlertBox = document.getElementById("management-alert-box");
  const statTotalRecords = document.getElementById("stat-total-records");
  const statTodayRecords = document.getElementById("stat-today-records");
  const statFaceRate = document.getElementById("stat-face-rate");
  const statPendingRecords = document.getElementById("stat-pending-records");

  const pendingSection = document.getElementById("pending-section");
  const pendingTableBody = document.getElementById("pending-table-body");
  const btnFlushPending = document.getElementById("btn-flush-pending");

  const tabLinks = document.querySelectorAll(".tab-link[data-face-filter]");
  const tabCountAll = document.getElementById("tab-count-all");
  const tabCountFace = document.getElementById("tab-count-face");
  const tabCountNoface = document.getElementById("tab-count-noface");
  const searchPlateInput = document.getElementById("search-plate-input");
  const ledgerCountText = document.getElementById("ledger-count-text");
  const btnRefreshManagement = document.getElementById("btn-refresh-management");
  const historyTableBody = document.getElementById("history-table-body");

  let activeFaceFilter = "all";
  let isCameraStreaming = false;
  let lastRecordsVersion = -1;
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

  function parseConsensusPct(str) {
    const m = String(str || "").match(/\((\d+)%\)/);
    return m ? parseInt(m[1], 10) : 0;
  }

  function parseConsensusRatio(str) {
    const m = String(str || "").match(/^(\d+\/\d+)/);
    return m ? `${m[1]} mẫu` : String(str || "-");
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
    if (str === "Lần đầu" || str === "Chờ lưu") {
      return `<span class="pill warn">${escapeHtml(str)}</span>`;
    }
    return `<span class="pill">${escapeHtml(str)}</span>`;
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
          <td colspan="4">Chưa có bản ghi nhận diện.</td>
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
      }

      if (state.current_plates && state.current_plates.length > 0) {
        livePlateValue.textContent = state.current_plates.join(", ");
      } else {
        livePlateValue.textContent = "-";
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
          <td colspan="7">Không có bản ghi nào khớp điều kiện lọc.</td>
        </tr>
      `;
      return;
    }

    historyTableBody.innerHTML = records
      .map((row) => {
        const consensusRaw = row["Đồng thuận biển số"] || "-";
        const ratioText = parseConsensusRatio(consensusRaw);
        const pctVal = parseConsensusPct(consensusRaw);
        return `
          <tr>
            <td><span class="plate-cell-main num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td>${renderMatchPill(row["Đối chiếu"])}</td>
            <td class="n num">${escapeHtml(ratioText)}</td>
            <td class="n num">${pctVal > 0 ? `${pctVal}%` : "-"}</td>
            <td class="n num">${escapeHtml(row["Thời gian nhận diện"])}</td>
            <td class="n num">#${escapeHtml(row["ID"])}</td>
          </tr>
        `;
      })
      .join("");
  }

  function applyManagementData(data) {
    const records = data.records || [];
    const pending = data.pending_records || [];
    const stats = data.stats || {
      total_records: records.length,
      today_records: 0,
      with_face: 0,
      no_face: 0,
      face_rate: 0,
    };

    updateDatabaseStatusUI(true, data.database_ready, pending.length);

    statTotalRecords.textContent = String(stats.total_records);
    statTodayRecords.textContent = String(stats.today_records);
    statFaceRate.textContent = `${stats.face_rate}%`;
    statPendingRecords.textContent = String(pending.length);

    if (tabCountAll) tabCountAll.textContent = String(stats.total_records);
    if (tabCountFace) tabCountFace.textContent = String(stats.with_face);
    if (tabCountNoface) tabCountNoface.textContent = String(stats.no_face);

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
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td class="n num">${escapeHtml(row["Đồng thuận biển số"])}</td>
            <td class="n num">${escapeHtml(row["Thời gian nhận diện"])}</td>
            <td class="n num">Cổng ${escapeHtml(row["Camera index"])}</td>
          </tr>
        `
        )
        .join("");
    } else {
      pendingSection.classList.add("hidden");
      pendingTableBody.innerHTML = "";
    }

    const query = (searchPlateInput.value || "").trim();
    if (!query && activeFaceFilter === "all") {
      updateRecentFeed(pending, records);
    }

    const matched = typeof data.matched === "number" ? data.matched : records.length;
    renderHistoryTable(records, matched, stats.total_records);
  }

  async function fetchManagementOverview() {
    const query = (searchPlateInput.value || "").trim();
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (activeFaceFilter && activeFaceFilter !== "all") {
      params.set("face", activeFaceFilter);
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
      activeFaceFilter = btn.getAttribute("data-face-filter") || "all";
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
