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

  // Fallback dataset used only if inspecting static HTML without the server running
  const STATIC_SAMPLE_RECORDS = [
    {
      ID: 108,
      "Biển số": "99E1-22268",
      "Thời gian nhận diện": "2026-10-28 18:11:25",
      "Đồng thuận biển số": "3/3 (100%)",
      "Khuôn mặt": "Không rõ",
      "Camera index": 0,
    },
    {
      ID: 107,
      "Biển số": "79F9-7131",
      "Thời gian nhận diện": "2026-10-28 14:52:19",
      "Đồng thuận biển số": "5/6 (83%)",
      "Khuôn mặt": "Không rõ",
      "Camera index": 0,
    },
    {
      ID: 106,
      "Biển số": "43N2-6176",
      "Thời gian nhận diện": "2026-10-28 14:52:13",
      "Đồng thuận biển số": "6/7 (86%)",
      "Khuôn mặt": "Không rõ",
      "Camera index": 0,
    },
    {
      ID: 105,
      "Biển số": "14AA-99999",
      "Thời gian nhận diện": "2026-10-28 14:23:28",
      "Đồng thuận biển số": "4/5 (80%)",
      "Khuôn mặt": "Không rõ",
      "Camera index": 0,
    },
  ];

  let allHistoryRecords = [];
  let activeFaceFilter = "all";
  let isCameraStreaming = false;
  let lastSeenConfirmedTime = null;

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

  function updateDatabaseStatusUI(dbReady, pendingCount) {
    if (dbStatusPill) {
      if (dbReady) {
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
      await pollCameraStatus();
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
      await pollCameraStatus();
    } catch (err) {
      showBanner(cameraAlertBox, "error", err.message);
    }
  });

  function updateRecentFeed(records) {
    const recentSlice = (records || []).slice(0, 5);
    if (recentSlice.length === 0) {
      recentMiniTbody.innerHTML = `
        <tr>
          <td colspan="4">Chưa có bản ghi nhận diện.</td>
        </tr>
      `;
      return;
    }

    recentMiniTbody.innerHTML = recentSlice
      .map((row) => {
        const timePart = String(row["Thời gian nhận diện"] || "").split(" ").pop() || "-";
        const consensusRaw = row["Đồng thuận biển số"] || "-";
        return `
          <tr>
            <td><span class="plate-cell-main num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
            <td class="n num">${escapeHtml(consensusRaw)}</td>
            <td class="n num">${escapeHtml(timePart)}</td>
          </tr>
        `;
      })
      .join("");
  }

  async function pollCameraStatus() {
    try {
      const res = await fetch("/api/camera/status");
      if (!res.ok) return;
      const state = await res.json();

      updateDatabaseStatusUI(state.database_ready, state.pending_count);

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

      if (state.last_confirmed) {
        if (lastSeenConfirmedTime !== state.last_confirmed.recognized_at) {
          lastSeenConfirmedTime = state.last_confirmed.recognized_at;
          fetchManagementOverview();
        }
      }
    } catch {
      if (allHistoryRecords.length === 0) {
        applyManagementData({
          database_ready: true,
          database_error: null,
          pending_records: [],
          records: STATIC_SAMPLE_RECORDS,
        });
      }
    }
  }

  // ==================== MANAGEMENT & HISTORY TABLE ====================
  function renderHistoryTable() {
    const query = (searchPlateInput.value || "").trim().toUpperCase();

    const withFaceTotal = allHistoryRecords.filter((r) =>
      String(r["Khuôn mặt"] || "").startsWith("Có")
    ).length;
    const noFaceTotal = allHistoryRecords.length - withFaceTotal;

    if (tabCountAll) tabCountAll.textContent = String(allHistoryRecords.length);
    if (tabCountFace) tabCountFace.textContent = String(withFaceTotal);
    if (tabCountNoface) tabCountNoface.textContent = String(noFaceTotal);

    const filtered = allHistoryRecords.filter((row) => {
      const plate = String(row["Biển số"] || "").toUpperCase();
      const face = String(row["Khuôn mặt"] || "");
      if (query && !plate.includes(query)) return false;
      if (activeFaceFilter === "with_face" && !face.startsWith("Có")) return false;
      if (activeFaceFilter === "no_face" && face.startsWith("Có")) return false;
      return true;
    });

    if (ledgerCountText) {
      ledgerCountText.textContent = `${filtered.length} / ${allHistoryRecords.length} bản ghi`;
    }

    if (filtered.length === 0) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="6">Không có bản ghi nào khớp điều kiện lọc.</td>
        </tr>
      `;
      return;
    }

    historyTableBody.innerHTML = filtered
      .map((row) => {
        const consensusRaw = row["Đồng thuận biển số"] || "-";
        const ratioText = parseConsensusRatio(consensusRaw);
        const pctVal = parseConsensusPct(consensusRaw);
        return `
          <tr>
            <td><span class="plate-cell-main num">${escapeHtml(row["Biển số"])}</span></td>
            <td>${renderFacePill(row["Khuôn mặt"])}</td>
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
    allHistoryRecords = records;

    const total = records.length;
    const withFace = records.filter((r) => String(r["Khuôn mặt"] || "").startsWith("Có")).length;
    const faceRate = total > 0 ? Math.round((withFace / total) * 100) : 0;

    const todayPrefix = new Date().toISOString().slice(0, 10);
    const todayRecords =
      data.stats && typeof data.stats.today_records === "number"
        ? data.stats.today_records
        : records.filter((r) => String(r["Thời gian nhận diện"] || "").startsWith(todayPrefix))
            .length;

    updateDatabaseStatusUI(data.database_ready, pending.length);

    statTotalRecords.textContent = String(total);
    statTodayRecords.textContent = String(todayRecords);
    statFaceRate.textContent = `${faceRate}%`;
    statPendingRecords.textContent = String(pending.length);

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

    updateRecentFeed(records);
    renderHistoryTable();
  }

  async function fetchManagementOverview() {
    try {
      const res = await fetch("/api/management/overview");
      if (!res.ok) throw new Error("API status " + res.status);
      const data = await res.json();
      applyManagementData(data);
    } catch {
      if (allHistoryRecords.length === 0) {
        applyManagementData({
          database_ready: true,
          database_error: null,
          pending_records: [],
          records: STATIC_SAMPLE_RECORDS,
        });
      }
    }
  }

  tabLinks.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabLinks.forEach((b) => b.setAttribute("aria-selected", "false"));
      btn.setAttribute("aria-selected", "true");
      activeFaceFilter = btn.getAttribute("data-face-filter") || "all";
      renderHistoryTable();
    });
  });

  searchPlateInput.addEventListener("input", renderHistoryTable);

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

  btnFlushPending.addEventListener("click", async () => {
    btnFlushPending.disabled = true;
    try {
      const res = await fetch("/api/management/flush-pending", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể đồng bộ bản ghi chờ.");
      }
      await fetchManagementOverview();
      showBanner(managementAlertBox, "success", "Đã đồng bộ bản ghi chờ vào MySQL.");
    } catch (err) {
      await fetchManagementOverview();
      showBanner(managementAlertBox, "error", err.message);
    } finally {
      btnFlushPending.disabled = false;
    }
  });

  fetchManagementOverview();
  pollCameraStatus();
  setInterval(pollCameraStatus, 400);
})();
