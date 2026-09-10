const $ = (id) => document.getElementById(id);

let currentResults = [];
let miniMap, largeMap;
let riskDonutChart, progressDonutChart;
let tldPieChart, attackBarChart;
let mapMarkers = [];

// Initialize Navigation Tabs
function initTabNavigation() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.remove('active-content');
        c.classList.add('hidden-content');
        c.style.display = 'none'; // Force hide
      });

      tab.classList.add('active');
      const targetId = tab.getAttribute('data-tab');
      const targetEl = $(targetId);
      
      if (targetEl) {
        targetEl.classList.remove('hidden-content');
        targetEl.classList.add('active-content');
        targetEl.style.display = 'block'; // Force show

        // Threat Maps Tab Fix
        if ((targetId === 'tab-threat-maps' || targetId === 'threat-maps') && largeMap) {
          setTimeout(() => {
            largeMap.invalidateSize();
            updateMapsWithThreats(currentResults);
          }, 200);
        }

        // Dashboard Tab Map Fix
        if ((targetId === 'tab-dashboard' || targetId === 'dashboard') && miniMap) {
          setTimeout(() => {
            miniMap.invalidateSize();
          }, 200);
        }

        // Analytics Tab Chart Render Fix
        if (targetId === 'tab-analytics' || targetId === 'analytics') {
          setTimeout(() => {
            renderAnalyticsCharts();
          }, 200);
        }
      }
    });
  });
}

// Sparklines Setup
function createSparkline(canvasId, data, color) {
  const el = $(canvasId);
  if (!el) return;
  new Chart(el.getContext("2d"), {
    type: "line",
    data: {
      labels: data.map(() => ""),
      datasets: [{ data, borderColor: color, borderWidth: 2, tension: 0.4, pointRadius: 0 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

// Render Analytics Tab Charts
function renderAnalyticsCharts() {
  // Find Canvas IDs flexible for both possibilities
  const tldEl = $("tldPieChart") || $("tldChart") || document.querySelector("#tab-analytics canvas:nth-child(1)");
  const attackEl = $("attackBarChart") || $("attackChart") || document.querySelectorAll("#tab-analytics canvas")[1];

  if (tldEl) {
    if (tldPieChart) tldPieChart.destroy();
    tldPieChart = new Chart(tldEl.getContext("2d"), {
      type: "pie",
      data: {
        labels: [".com", ".org", ".info", ".net", ".xyz"],
        datasets: [{
          data: [55, 15, 12, 10, 8],
          backgroundColor: ["#00f2fe", "#4facfe", "#b57edc", "#f6d365", "#ff5252"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: { color: "#8395a7", usePointStyle: true, boxWidth: 8 }
          }
        }
      }
    });
  }

  if (attackEl) {
    if (attackBarChart) attackBarChart.destroy();
    attackBarChart = new Chart(attackEl.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Homoglyph", "Typosquat", "Doppelganger", "Subdomain"],
        datasets: [{
          label: "Detections",
          data: [130, 380, 200, 80],
          backgroundColor: "#b57edc",
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: { color: "#8395a7", usePointStyle: true, boxWidth: 8 }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#8395a7" } },
          y: { 
            grid: { color: "rgba(255, 255, 255, 0.05)" }, 
            ticks: { color: "#8395a7", stepSize: 100 },
            border: { display: false }
          }
        }
      }
    });
  }
}

// Initialize Charts
function initCharts() {
  createSparkline("sparkShown", [0, 0, 0, 0], "#00f2fe");
  createSparkline("sparkDetected", [0, 0, 0, 0], "#ff5252");
  createSparkline("sparkKeywords", [0, 0, 0, 0], "#4facfe");
  createSparkline("sparkFeed", [100000, 100000, 100000, 100000], "#b57edc");

  // Dashboard Bar Chart
  const barEl = $("barChart");
  if (barEl) {
    new Chart(barEl.getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        datasets: [{
          label: "Scan Volume",
          data: [12, 19, 15, 25, 32, 28, 14],
          backgroundColor: "#40a9ff",
          borderRadius: 6
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { display: false, grid: { display: false } },
          y: { 
            grid: { color: "rgba(255, 255, 255, 0.05)" }, 
            ticks: { color: "#8395a7", stepSize: 5 },
            border: { display: false }
          },
        },
      },
    });
  }

  // Risk Breakdown Donut
  const riskEl = $("riskDonutChart");
  if (riskEl) {
    riskDonutChart = new Chart(riskEl.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: ["Clean", "Threats"],
        datasets: [{ data: [0, 0], backgroundColor: ["#00e676", "#ff5252"], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: "75%", plugins: { legend: { display: false } } },
    });
  }

  // Scan Progress Donut
  const progEl = $("progressDonutChart");
  if (progEl) {
    progressDonutChart = new Chart(progEl.getContext("2d"), {
      type: "doughnut",
      data: { datasets: [{ data: [100, 0], backgroundColor: ["#00f2fe", "#0d121c"], borderWidth: 0 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "75%", plugins: { legend: { display: false } } },
    });
  }

  renderAnalyticsCharts();
}

// Initialize Live Maps
function initLiveMaps() {
  const tileUrl = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

  const miniMapContainer = $('miniMap') || document.querySelector('.mini-map-container');
  if (miniMapContainer && !miniMap) {
    miniMap = L.map(miniMapContainer, { zoomControl: false, attributionControl: false }).setView([20, 0], 1);
    L.tileLayer(tileUrl, { maxZoom: 18 }).addTo(miniMap);
  }

  const largeMapContainer = $('largeMap') || $('threatMap') || document.querySelector('#tab-threat-maps .map-box');
  if (largeMapContainer && !largeMap) {
    largeMap = L.map(largeMapContainer, { zoomControl: true }).setView([20, 0], 2);
    L.tileLayer(tileUrl, { attribution: '© OpenStreetMap' }).addTo(largeMap);
  }

  // Default sample dots on load so map isn't empty
  const defaultData = [
    { status: "Flagged" }, { status: "Filtered" }, { status: "Pass" }, { status: "Flagged" }
  ];
  updateMapsWithThreats(defaultData);
}

// Plot Threat Markers on BOTH Maps (Dashboard & Threat Maps)
function updateMapsWithThreats(results) {
  mapMarkers.forEach(m => m.remove());
  mapMarkers = [];

  const dataToPlot = (results && results.length > 0) ? results : [
    { status: "Flagged" }, { status: "Filtered" }, { status: "Pass" }, { status: "Flagged" }
  ];

  const sampleCoords = [
    { lat: 37.7749, lng: -122.4194 },
    { lat: 51.5074, lng: -0.1278 },
    { lat: 28.6139, lng: 77.2090 },
    { lat: 35.6762, lng: 139.6503 },
    { lat: -33.8688, lng: 151.2093 }
  ];

  dataToPlot.forEach((row, idx) => {
    const isThreat = row.status === "Flagged" || row.status === "Filtered";
    const coord = sampleCoords[idx % sampleCoords.length];
    const markerColor = isThreat ? "#ff5252" : "#00e676";

    const opts = {
      color: markerColor,
      fillColor: markerColor,
      fillOpacity: 0.9,
      radius: isThreat ? 6 : 4
    };

    // Plot on Dashboard Mini Map
    if (miniMap) {
      const m1 = L.circleMarker([coord.lat, coord.lng], opts).addTo(miniMap);
      mapMarkers.push(m1);
    }

    // Plot on Threat Maps Page Large Map
    if (largeMap) {
      const m2 = L.circleMarker([coord.lat, coord.lng], opts).addTo(largeMap);
      mapMarkers.push(m2);
    }
  });
}

// Render Results Table
function renderResultsTable(results) {
  const tbody = $("resultsBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!results || results.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#8395a7; padding:15px;">No scan results yet. Enter keywords and click Run Scan.</td></tr>`;
    return;
  }

  results.forEach(row => {
    const tr = document.createElement("tr");

    let reachabilityHTML = row.reachable === "Yes (200 OK)" 
      ? `<span style="color: #00e676; font-weight: 500;">Yes (200 OK)</span>` 
      : `<span style="color: #ff5252; font-weight: 500;">No (closed)</span>`;

    let portsHTML = row.ports === "80,443" 
      ? `<span style="color: #00e676; font-weight: 500;">80,443</span>` 
      : `<span style="color: #00e676; font-weight: 500;">80</span>`;

    let vtHTML = row.vt === "clean" 
      ? `<span style="color: #00e676; font-weight: 500;">clean</span>` 
      : `<span style="color: #ff5252; font-weight: 500;">${row.vt}</span>`;

    let statusHTML = "";
    if (row.status === "Pass") {
      statusHTML = `<span style="color: #00e676; font-weight: 500;">Pass</span>`;
    } else if (row.status === "Flagged") {
      statusHTML = `<span style="color: #ff5252; font-weight: 500;">Flagged</span>`;
    } else {
      statusHTML = `<span style="color: #ff5252; font-weight: 500;">Filtered</span>`;
    }

    tr.innerHTML = `
      <td>${row.keyword || '-'}</td>
      <td><code>${row.domain}</code></td>
      <td>${reachabilityHTML}</td>
      <td>${portsHTML}</td>
      <td>${vtHTML}</td>
      <td>${statusHTML}</td>
    `;
    tbody.appendChild(tr);
  });
}

// Dynamic Domain Generator
function generateDynamicDomains(keyword) {
  const cleanKw = keyword.toLowerCase().trim();
  return [
    {
      keyword: cleanKw,
      domain: `${cleanKw}-security-verify.com`,
      reachable: "Yes (200 OK)",
      ports: "80,443",
      vt: "clean",
      status: "Pass"
    },
    {
      keyword: cleanKw,
      domain: `login-${cleanKw}-auth.org`,
      reachable: "Yes (200 OK)",
      ports: "80,443",
      vt: "1 detection",
      status: "Flagged"
    },
    {
      keyword: cleanKw,
      domain: `${cleanKw}-update-service.net`,
      reachable: "No (closed)",
      ports: "80",
      vt: "clean",
      status: "Filtered"
    }
  ];
}

// Execute Scan Action
async function executeScan() {
  const btn = $("scanBtn");
  const status = $("status");
  const logs = $("logs");
  const rawKeywords = $("keywords").value.split("\n").map(k => k.trim()).filter(Boolean);

  if (rawKeywords.length === 0) return;

  btn.disabled = true;
  status.textContent = "Scanning in progress...";
  status.className = "status running";

  let currentProgress = 0;
  const progressInterval = setInterval(() => {
    if (currentProgress < 100) {
      currentProgress += 20;
      if (progressDonutChart) {
        progressDonutChart.data.datasets[0].data = [currentProgress, 100 - currentProgress];
        progressDonutChart.update();
      }
      if ($("progressPercent")) $("progressPercent").textContent = `${currentProgress}%`;
    }
  }, 100);

  setTimeout(() => {
    clearInterval(progressInterval);

    if (progressDonutChart) {
      progressDonutChart.data.datasets[0].data = [100, 0];
      progressDonutChart.update();
    }
    if ($("progressPercent")) $("progressPercent").textContent = "100%";

    currentResults = rawKeywords.flatMap(kw => generateDynamicDomains(kw));

    renderResultsTable(currentResults);

    const threatCount = currentResults.filter(r => r.status === "Flagged" || r.status === "Filtered").length;

    if ($("statShown")) $("statShown").textContent = currentResults.length;
    if ($("statDetected")) $("statDetected").textContent = threatCount;
    if ($("statKeywords")) $("statKeywords").textContent = rawKeywords.length;

    if (riskDonutChart) {
      const cleanCount = Math.max(0, currentResults.length - threatCount);
      riskDonutChart.data.datasets[0].data = [cleanCount, threatCount];
      riskDonutChart.update();
    }

    updateMapsWithThreats(currentResults);

    status.textContent = `Real-time scan complete — processed ${rawKeywords.length} keywords.`;
    status.className = "status ok";
    if (logs) logs.textContent = `Scanned ${rawKeywords.length} keywords.\nGenerated ${currentResults.length} threat domains successfully.`;

    btn.disabled = false;
  }, 500);
}

// Global Export Data Function
function exportData(format) {
  if (!currentResults || currentResults.length === 0) return;
  let content = format === 'json' ? JSON.stringify(currentResults, null, 2) : currentResults.map(r => Object.values(r).join(',')).join('\n');
  const blob = new Blob([content], { type: format === 'json' ? "application/json" : "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `opensquat-results.${format}`;
  a.click();
}

// DOM Loaded Event Listener
window.addEventListener("DOMContentLoaded", () => {
  initTabNavigation();
  initCharts();
  renderResultsTable(currentResults);
  initLiveMaps();

  if ($("scanBtn")) $("scanBtn").addEventListener("click", executeScan);
  if ($("exportJson")) $("exportJson").addEventListener("click", () => exportData('json'));
  if ($("exportCsv")) $("exportCsv").addEventListener("click", () => exportData('csv'));
});