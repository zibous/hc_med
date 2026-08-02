// chart.js – Trend-Chart mit Chart.js
let chartInstance = null;

export function renderChart(data) {
  const card = document.getElementById("chartCard");
  const canvas = document.getElementById("mainChart");

  if (!data || !data.werte || data.werte.length === 0) {
    card.style.display = "none";
    return;
  }
  card.style.display = "block";

  const ctx = canvas.getContext("2d");
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  // Daten aufbereiten
  const labels = data.werte.map(w => w.datum);
  const values = data.werte.map(w => {
    // Wert bereinigen: "<0.5" -> 0.5, "12,3" -> 12.3
    let raw = String(w.wert_norm || w.wert || "").replace(",", ".");
    raw = raw.replace(/^[<>]\s*/, "");
    const v = parseFloat(raw);
    return isNaN(v) ? null : v;
  });
  const flags = data.werte.map(w => w.flag);

  // Norm-Bereich parsen
  let normMin = null, normMax = null;
  if (data.normbereich) {
    const norm = data.normbereich.trim();
    // Format: "4.00-11.00" oder "4.00 - 11.00"
    const range = norm.match(/^([\d.]+)\s*-\s*([\d.]+)$/);
    if (range) { normMin = parseFloat(range[1]); normMax = parseFloat(range[2]); }
    // Format: "< 0.50" oder "<-200" (bedeutet "< 200")
    const lt = norm.match(/^[<]\s*-?\s*([\d.]+)$/);
    if (lt) { normMin = 0; normMax = parseFloat(lt[1]); }
    // Format: "> 90" oder ">-90"
    const gt = norm.match(/^[>]\s*-?\s*([\d.]+)$/);
    if (gt) { normMin = parseFloat(gt[1]); normMax = null; }
    // Format: "-50" (bedeutet "< 50", obere Grenze)
    const dashMax = norm.match(/^-\s*([\d.]+)$/);
    if (dashMax && !range) { normMin = 0; normMax = parseFloat(dashMax[1]); }
  }

  // Punkt-Farben basierend auf Flag
  const pointColors = flags.map(f => {
    if (f === "H") return isDark ? "#f87171" : "#dc2626";
    if (f === "L") return isDark ? "#60a5fa" : "#2563eb";
    return isDark ? "#34d399" : "#059669";
  });

  // Datasets
  const datasets = [{
    label: data.test,
    data: values,
    borderColor: isDark ? "rgba(52,211,153,1)" : "rgba(5,150,105,1)",
    backgroundColor: isDark ? "rgba(52,211,153,0.1)" : "rgba(5,150,105,0.08)",
    fill: true,
    tension: 0.25,
    pointBackgroundColor: pointColors,
    pointRadius: values.length > 50 ? 0 : values.length > 20 ? 2 : 4,
    pointHoverRadius: values.length > 50 ? 3 : 5,
    borderWidth: values.length > 50 ? 1.2 : 1.8,
  }];

  // Norm-Band als Annotation-Datasets
  if (normMin !== null) {
    datasets.push({
      label: "Norm unten",
      data: Array(values.length).fill(normMin),
      borderColor: isDark ? "rgba(251,146,60,0.6)" : "rgba(234,88,12,0.5)",
      borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0, fill: false,
    });
  }
  if (normMax !== null) {
    datasets.push({
      label: "Norm oben",
      data: Array(values.length).fill(normMax),
      borderColor: isDark ? "rgba(251,146,60,0.6)" : "rgba(234,88,12,0.5)",
      borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0,
      fill: normMin !== null ? "-1" : false,
      backgroundColor: isDark ? "rgba(251,146,60,0.06)" : "rgba(234,88,12,0.05)",
    });
  }

  // Ereignis-Marker (Krankenhausaufenthalte) – dünner horizontaler Streifen am unteren Rand
  const minVal = values.filter(v => v !== null).reduce((a, b) => Math.min(a, b), 0);
  const maxVal = values.filter(v => v !== null).reduce((a, b) => Math.max(a, b), 0);
  const markerY = minVal * 0.95; // knapp unter dem Minimum, aber nicht negativ

  if (data.ereignisse && data.ereignisse.length > 0) {
    data.ereignisse.forEach(e => {
      const markerData = labels.map(l => (l >= e.von && l <= e.bis) ? markerY : null);
      datasets.push({
        label: "🏥 " + e.label,
        data: markerData,
        type: "line",
        borderColor: e.farbe || "#ef4444",
        borderWidth: 4,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0,
        spanGaps: false,
        order: 0,
      });
    });
  }

  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: `${data.test} (${data.einheit || ""})`,
          color: isDark ? "#f1f5f9" : "#1e293b",
          font: { size: 16, weight: "600" },
          align: "start",
        },
        tooltip: {
          enabled: true,
          backgroundColor: isDark ? "rgba(15,23,42,.95)" : "rgba(255,255,255,.95)",
          titleColor: isDark ? "#fff" : "#1e293b",
          bodyColor: isDark ? "#e2e8f0" : "#475569",
          borderColor: isDark ? "rgba(255,255,255,.1)" : "rgba(0,0,0,.08)",
          borderWidth: 1,
          filter: function(tooltipItem) {
            return !tooltipItem.dataset?.label?.startsWith("Norm");
          },
          callbacks: {
            label: function(tooltipItem) {
              const lbl = tooltipItem.dataset?.label || "";
              if (lbl.startsWith("🏥")) return "  " + lbl;
              return `  ${data.test}: ${tooltipItem.parsed.y} ${data.einheit || ""}`;
            }
          }
        },
      },
      scales: {
        x: {
          ticks: { color: isDark ? "#94a3b8" : "#64748b", maxTicksLimit: 8, font: { size: 11 } },
          grid: { display: false },
        },
        y: {
          ticks: { color: isDark ? "#94a3b8" : "#64748b", font: { size: 11 } },
          grid: { color: isDark ? "rgba(255,255,255,.04)" : "rgba(0,0,0,.04)" },
        },
      },
    },
  });

  // Statistik-Box unter dem Chart rendern
  renderChartStats(card, values, data);
}

function renderChartStats(container, values, data) {
  const numericVals = values.filter(v => v !== null);
  if (numericVals.length === 0) return;

  const min = Math.min(...numericVals);
  const max = Math.max(...numericVals);
  const avg = numericVals.reduce((a, b) => a + b, 0) / numericVals.length;
  const latest = numericVals[numericVals.length - 1];
  const first = numericVals[0];

  // Trend berechnen: Durchschnitt letzte 12 Monate vs. vorherige 12 Monate
  let trendText, trendColor;
  const trendNow = new Date();
  const trend1yAgo = new Date(trendNow.getFullYear() - 1, trendNow.getMonth(), trendNow.getDate()).toISOString().slice(0,10);
  const trend2yAgo = new Date(trendNow.getFullYear() - 2, trendNow.getMonth(), trendNow.getDate()).toISOString().slice(0,10);

  const recentVals = [], olderVals = [];
  data.werte.forEach((w, i) => {
    if (values[i] === null) return;
    if (w.datum >= trend1yAgo) recentVals.push(values[i]);
    else if (w.datum >= trend2yAgo) olderVals.push(values[i]);
  });

  if (recentVals.length > 0 && olderVals.length > 0) {
    const avgR = recentVals.reduce((a,b) => a+b, 0) / recentVals.length;
    const avgO = olderVals.reduce((a,b) => a+b, 0) / olderVals.length;
    const pct = avgO !== 0 ? ((avgR - avgO) / avgO * 100).toFixed(0) : 0;
    // Nur farbig warnen wenn aktueller Wert auffällig ist (Flag H oder L)
    const lastFlag = data.werte[data.werte.length-1]?.flag;
    const isAuffaellig = lastFlag === "H" || lastFlag === "L";
    if (Math.abs(pct) < 5) { trendText = "→ Stabil"; trendColor = "var(--green)"; }
    else if (pct > 0) { trendText = `↑ +${pct}%`; trendColor = isAuffaellig ? "var(--orange)" : "var(--text-muted)"; }
    else { trendText = `↓ ${pct}%`; trendColor = isAuffaellig ? "var(--accent)" : "var(--text-muted)"; }
  } else {
    // Nicht genug Daten für 12-Monats-Vergleich
    if (numericVals.length < 3) {
      trendText = "— Zu wenig Daten"; trendColor = "var(--text-muted)";
    } else {
      // Fallback: letzte 3 Werte vs. erste 3 Werte
      const lastThree = numericVals.slice(-3).reduce((a,b) => a+b, 0) / 3;
      const firstThree = numericVals.slice(0,3).reduce((a,b) => a+b, 0) / 3;
      const pct = firstThree !== 0 ? ((lastThree - firstThree) / firstThree * 100).toFixed(0) : 0;
      const lastFlag = data.werte[data.werte.length-1]?.flag;
      const isAuffaellig = lastFlag === "H" || lastFlag === "L";
      if (Math.abs(pct) < 10) { trendText = "→ Stabil"; trendColor = "var(--green)"; }
      else if (pct > 0) { trendText = `↑ +${pct}%`; trendColor = isAuffaellig ? "var(--orange)" : "var(--text-muted)"; }
      else { trendText = `↓ ${pct}%`; trendColor = isAuffaellig ? "var(--accent)" : "var(--text-muted)"; }
    }
  }

  // Bestehende Stats entfernen
  const existing = container.querySelector(".chart-stats");
  if (existing) existing.remove();

  const statsEl = document.createElement("div");
  statsEl.className = "chart-stats";
  statsEl.innerHTML = `
    <div class="chart-stat">
      <div class="chart-stat-label">Minimum</div>
      <div class="chart-stat-value">${min.toFixed(1)} ${data.einheit || ""}</div>
    </div>
    <div class="chart-stat">
      <div class="chart-stat-label">Maximum</div>
      <div class="chart-stat-value">${max.toFixed(1)} ${data.einheit || ""}</div>
    </div>
    <div class="chart-stat">
      <div class="chart-stat-label">Durchschnitt</div>
      <div class="chart-stat-value">${avg.toFixed(1)} ${data.einheit || ""}</div>
    </div>
    <div class="chart-stat">
      <div class="chart-stat-label">Aktuell</div>
      <div class="chart-stat-value">${latest.toFixed(1)} ${data.einheit || ""}</div>
    </div>
    <div class="chart-stat">
      <div class="chart-stat-label">Trend (12 Monate)</div>
      <div class="chart-stat-value" style="color:${trendColor}">${trendText}</div>
    </div>
  `;
  container.appendChild(statsEl);
}


// Multi-Chart: Mehrere Tests übereinander mit gleicher Zeitachse
const MULTI_COLORS = ["#34d399", "#60a5fa", "#f97316", "#a78bfa", "#fb7185", "#fbbf24"];

export function renderMultiChart(data) {
  const card = document.getElementById("chartCard");

  if (!data || !data.tests || Object.keys(data.tests).length === 0) {
    card.style.display = "block";
    card.innerHTML = `<canvas id="mainChart"></canvas><p style="color:var(--text-muted);padding:1rem;">Keine Daten für diese Verknüpfung verfügbar.</p>`;
    return;
  }

  card.style.display = "block";
  // Canvas neu erstellen (falls Stats drin waren)
  const existingStats = card.querySelector(".chart-stats");
  if (existingStats) existingStats.remove();

  const canvas = document.getElementById("mainChart");
  const ctx = canvas.getContext("2d");
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  // Alle Datumswerte sammeln (Union aller Tests)
  const allDates = new Set();
  Object.values(data.tests).forEach(t => t.werte.forEach(w => allDates.add(w.datum)));
  const labels = [...allDates].sort();

  // Datasets pro Test
  const datasets = [];
  const testNames = Object.keys(data.tests);

  testNames.forEach((name, i) => {
    const t = data.tests[name];
    const color = MULTI_COLORS[i % MULTI_COLORS.length];

    // Werte auf die gemeinsame Zeitachse mappen
    const valueMap = {};
    t.werte.forEach(w => {
      const raw = String(w.wert).replace(",", ".").replace(/^[<>]/, "");
      valueMap[w.datum] = parseFloat(raw) || null;
    });
    const values = labels.map(d => valueMap[d] ?? null);

    datasets.push({
      label: `${name} (${t.einheit || ""})`,
      data: values,
      borderColor: color,
      backgroundColor: color + "15",
      fill: false,
      tension: 0.25,
      pointRadius: values.filter(v => v !== null).length > 50 ? 0 : 3,
      pointHoverRadius: 4,
      borderWidth: 1.5,
      spanGaps: true,
      yAxisID: testNames.length <= 2 ? (i === 0 ? "y" : "y1") : "y",
    });
  });

  if (chartInstance) chartInstance.destroy();

  // Achsen-Config
  const scales = {
    x: {
      ticks: { color: isDark ? "#94a3b8" : "#64748b", maxTicksLimit: 8, font: { size: 11 } },
      grid: { display: false },
    },
    y: {
      position: "left",
      ticks: { color: MULTI_COLORS[0], font: { size: 11 } },
      grid: { color: isDark ? "rgba(255,255,255,.04)" : "rgba(0,0,0,.04)" },
    },
  };

  // Zweite Y-Achse nur bei 2 Tests (unterschiedliche Einheiten)
  if (testNames.length === 2) {
    scales.y1 = {
      position: "right",
      ticks: { color: MULTI_COLORS[1], font: { size: 11 } },
      grid: { display: false },
    };
  }

  chartInstance = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: { color: isDark ? "#e2e8f0" : "#1e293b", font: { size: 12 }, usePointStyle: true },
        },
        title: {
          display: true,
          text: data.name,
          color: isDark ? "#f1f5f9" : "#1e293b",
          font: { size: 16, weight: "600" },
          align: "start",
        },
        tooltip: {
          enabled: true,
          backgroundColor: isDark ? "rgba(15,23,42,.95)" : "rgba(255,255,255,.95)",
          titleColor: isDark ? "#fff" : "#1e293b",
          bodyColor: isDark ? "#e2e8f0" : "#475569",
          borderColor: isDark ? "rgba(255,255,255,.1)" : "rgba(0,0,0,.08)",
          borderWidth: 1,
        },
      },
      scales,
    },
  });

  // Stats entfernen falls vorhanden
  const existing = card.querySelector(".chart-stats");
  if (existing) existing.remove();
}
