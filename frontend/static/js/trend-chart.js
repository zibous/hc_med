// chart.js – Trend-Chart mit Chart.js
let chartInstance = null;

export function renderChart(data) {
  const card = document.getElementById("chartCard");
  const canvas = document.getElementById("mainChart");

  // Bestehende Tabelle entfernen (bevor Chart neu gerendert wird)
  const existingTable = document.querySelector(".chart-table");
  if (existingTable) existingTable.remove();

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

  // Flags basierend auf Referenzbereich neu berechnen (für konsistente Farben)
  const calculatedFlags = values.map((v, i) => {
    if (v === null) return flags[i] || "";
    if (normMax !== null && v > normMax) return "H";
    if (normMin !== null && v < normMin) return "L";
    return "";
  });

  // Punkt-Farben basierend auf berechneten Flags
  const pointColors = calculatedFlags.map((f, i) => {
    if (f === "H") return isDark ? "#f87171" : "#dc2626";
    if (f === "L") return isDark ? "#60a5fa" : "#2563eb";
    return isDark ? "#34d399" : "#059669";
  });

  // Punkt-Rahmen für nicht-nüchtern Werte (orange Umrandung)
  const nichtNuechtern = data.werte.map(w => w.nicht_nuechtern || false);
  const pointBorderColors = nichtNuechtern.map((nn, i) => nn ? "#f59e0b" : pointColors[i]);
  const pointBorderWidths = nichtNuechtern.map(nn => nn ? 2 : 0);
  const pointRadii = values.map((v, i) => {
    const base = values.length > 50 ? 0 : values.length > 20 ? 2 : 4;
    return nichtNuechtern[i] ? base + 1 : base;
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
    pointBorderColor: pointBorderColors,
    pointBorderWidth: pointBorderWidths,
    pointRadius: pointRadii,
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
  
  // Daten-Tabelle als separaten Container nach der chartCard rendern
  renderChartTable(data);
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
    if (Math.abs(pct) < 5) { trendText = "→ Unverändert"; trendColor = "var(--green)"; }
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
      if (Math.abs(pct) < 10) { trendText = "→ Unverändert"; trendColor = "var(--green)"; }
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

function renderChartTable(data) {
  // Bestehende Tabelle entfernen
  const existing = document.querySelector(".chart-table");
  if (existing) existing.remove();

  if (!data.werte || data.werte.length === 0) return;

  // Tabelle als separaten Container nach der chartCard einfügen
  const chartCard = document.getElementById("chartCard");
  if (!chartCard) return;

  const tableEl = document.createElement("div");
  tableEl.className = "chart-table";
  
  // Tabellen-Header
  let tableHtml = `
    <table>
      <thead>
        <tr>
          <th>Datum</th>
          <th>Wert (${data.einheit || ""})</th>
          <th>Hinweis</th>
          <th>Krankenhaus</th>
        </tr>
      </thead>
      <tbody>
  `;

  // Norm-Bereich parsen (für Klassifizierung in Tabelle)
  let normMin = null, normMax = null;
  if (data.normbereich) {
    const norm = data.normbereich.trim();
    const range = norm.match(/^([\d.]+)\s*-\s*([\d.]+)$/);
    if (range) { normMin = parseFloat(range[1]); normMax = parseFloat(range[2]); }
    const lt = norm.match(/^[<]\s*-?\s*([\d.]+)$/);
    if (lt) { normMin = 0; normMax = parseFloat(lt[1]); }
    const gt = norm.match(/^[>]\s*-?\s*([\d.]+)$/);
    if (gt) { normMin = parseFloat(gt[1]); normMax = null; }
    const dashMax = norm.match(/^-\s*([\d.]+)$/);
    if (dashMax && !range) { normMin = 0; normMax = parseFloat(dashMax[1]); }
  }

  // Tabellen-Zeilen (umgekehrte Reihenfolge - neueste zuerst)
  data.werte.slice().reverse().forEach(w => {
    const date = w.datum || "";
    const value = w.wert_norm || w.wert || "";
    const flag = w.flag || "";
    
    // Wert bereinigen für Klassifizierung
    let raw = String(value).replace(",", ".");
    raw = raw.replace(/^[<>]\s*/, "");
    const numValue = parseFloat(raw);
    
    // Flag basierend auf Referenzbereich berechnen (überschreibt gespeichertes Flag)
    let calculatedFlag = flag;
    if (!isNaN(numValue) && (normMin !== null || normMax !== null)) {
      if (normMax !== null && numValue > normMax) {
        calculatedFlag = "H";
      } else if (normMin !== null && numValue < normMin) {
        calculatedFlag = "L";
      } else {
        calculatedFlag = "";
      }
    }
    
    // Flag-Icon und Text-Hinweis
    let hint = "";
    let hintClass = "";
    if (calculatedFlag === "H") {
      hint = "↑ erhöht";
      hintClass = "hint-flag-high";
    } else if (calculatedFlag === "L") {
      hint = "↓ erniedrigt";
      hintClass = "hint-flag-low";
    } else {
      hint = "✓ normal";
      hintClass = "hint-flag-normal";
    }
    
    // Nüchtern-Hinweis
    if (w.nicht_nuechtern) {
      hint += " (nicht nüchtern)";
    }
    
    // Krankenhaus-Marker prüfen
    let hospitalMarker = "";
    if (data.ereignisse && data.ereignisse.length > 0) {
      const matchingEvent = data.ereignisse.find(e => 
        date >= e.von && date <= e.bis
      );
      if (matchingEvent) {
        hospitalMarker = matchingEvent.label || "";
      }
    }
    
    tableHtml += `
      <tr>
        <td>${date}</td>
        <td><span class="value-cell ${hintClass}">${value}</span></td>
        <td class="${hintClass}">${hint}</td>
        <td>${hospitalMarker}</td>
      </tr>
    `;
  });

  tableHtml += `
      </tbody>
    </table>
  `;

  tableEl.innerHTML = tableHtml;
  // Tabelle nach der chartCard einfügen (nicht darin)
  chartCard.parentNode.insertBefore(tableEl, chartCard.nextSibling);
}


// Multi-Chart: Mehrere Tests übereinander mit gleicher Zeitachse
// Kontraststarke Palette für dunklen UND hellen Hintergrund
const MULTI_COLORS = ["#34d399", "#60a5fa", "#fb923c", "#f472b6", "#facc15", "#22d3ee"];

export function renderMultiChart(data) {
  const card = document.getElementById("chartCard");

  if (!data || !data.tests || Object.keys(data.tests).length === 0) {
    card.style.display = "block";
    card.innerHTML = `<canvas id="mainChart"></canvas><p style="color:var(--text-muted);padding:1rem;">Keine Daten für diese Verknüpfung verfügbar.</p>`;
    return;
  }

  card.style.display = "block";
  const existingStats = card.querySelector(".chart-stats");
  if (existingStats) existingStats.remove();

  const canvas = document.getElementById("mainChart");
  const ctx = canvas.getContext("2d");
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  // Alle Datumswerte sammeln (Union aller Tests)
  const allDates = new Set();
  Object.values(data.tests).forEach(t => t.werte.forEach(w => allDates.add(w.datum)));
  const labels = [...allDates].sort();

  // Tests in zwei Gruppen teilen für Dual-Axis
  const testNames = Object.keys(data.tests);
  const groupLeft = []; // große Werte → linke Y-Achse
  const groupRight = []; // kleine Werte → rechte Y-Achse

  // Mediane berechnen
  const medians = {};
  testNames.forEach(name => {
    const t = data.tests[name];
    const vals = t.werte.map(w => parseFloat(String(w.wert).replace(",", ".").replace(/^[<>]/, "")) || 0).filter(v => v > 0);
    vals.sort((a, b) => a - b);
    medians[name] = vals[Math.floor(vals.length / 2)] || 0;
  });

  // Dynamische Aufteilung: wenn Verhältnis max/min Median > 2.5 → Dual-Axis
  const medianValues = Object.values(medians).filter(v => v > 0);
  const maxMedian = Math.max(...medianValues);
  const minMedian = Math.min(...medianValues);
  const ratio = minMedian > 0 ? maxMedian / minMedian : 1;

  if (ratio > 1.8 && testNames.length >= 2) {
    // Schwelle: Mitte zwischen min und max Median
    const threshold = (maxMedian + minMedian) / 2;
    testNames.forEach(name => {
      if (medians[name] >= threshold) {
        groupLeft.push(name);
      } else {
        groupRight.push(name);
      }
    });
  } else {
    // Alle auf eine Achse
    testNames.forEach(name => groupLeft.push(name));
  }

  // Falls alle in einer Gruppe landen, keine zweite Achse
  const useDualAxis = groupLeft.length > 0 && groupRight.length > 0;

  // Datasets pro Test
  const datasets = [];

  testNames.forEach((name, i) => {
    const t = data.tests[name];
    const color = MULTI_COLORS[i % MULTI_COLORS.length];
    const isRight = useDualAxis && groupRight.includes(name);

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
      pointHoverRadius: 5,
      borderWidth: 2.5,
      borderDash: isRight ? [6, 3] : [],
      spanGaps: true,
      yAxisID: isRight ? "y1" : "y",
    });
  });

  if (chartInstance) chartInstance.destroy();

  // Achsen-Config
  const scales = {
    x: {
      ticks: { color: isDark ? "#e2e8f0" : "#64748b", maxTicksLimit: 8, font: { size: 11 } },
      grid: { display: false },
    },
    y: {
      position: "left",
      ticks: { color: isDark ? "#e2e8f0" : "#64748b", font: { size: 11 } },
      grid: { color: isDark ? "rgba(255,255,255,.06)" : "rgba(0,0,0,.06)" },
      title: {
        display: useDualAxis,
        text: groupLeft.join(", "),
        color: isDark ? "#e2e8f0" : "#64748b",
        font: { size: 10 },
      },
    },
  };

  if (useDualAxis) {
    scales.y1 = {
      position: "right",
      ticks: { color: isDark ? "#e2e8f0" : "#64748b", font: { size: 11 } },
      grid: { display: false },
      title: {
        display: true,
        text: groupRight.join(", "),
        color: isDark ? "#e2e8f0" : "#64748b",
        font: { size: 10 },
      },
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
          labels: {
            color: isDark ? "#e2e8f0" : "#1e293b",
            font: { size: 13, weight: "600" },
            usePointStyle: true,
            padding: 16,
          },
        },
        title: {
          display: true,
          text: data.name + (useDualAxis ? "  (gestrichelt = rechte Achse)" : ""),
          color: isDark ? "#e2e8f0" : "#1e293b",
          font: { size: 15, weight: "600" },
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


// Radar-Chart: Aktueller Risiko-Snapshot für Verknüpfungen
let radarInstance = null;

export function renderRadarChart(data) {
  if (!data || !data.tests || Object.keys(data.tests).length < 3) return;

  const canvas = document.getElementById("radarCanvas");
  if (!canvas) return;

  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const testNames = Object.keys(data.tests);

  // Pro Test: letzten Wert als % vom Norm-Maximum berechnen
  const radarData = [];
  const radarLabels = [];

  for (const name of testNames) {
    const t = data.tests[name];
    if (!t.werte || t.werte.length === 0) continue;

    const lastWert = t.werte[t.werte.length - 1];
    const raw = String(lastWert.wert).replace(",", ".").replace(/^[<>]\s*/, "");
    const val = parseFloat(raw);
    if (isNaN(val)) continue;

    // Normbereich parsen
    let normMax = null;
    if (t.normbereich) {
      const norm = t.normbereich.trim();
      const range = norm.match(/^([\d.]+)\s*-\s*([\d.]+)$/);
      if (range) normMax = parseFloat(range[2]);
      const lt = norm.match(/^[<]\s*-?\s*([\d.]+)$/);
      if (lt) normMax = parseFloat(lt[1]);
      const dashMax = norm.match(/^-\s*([\d.]+)$/);
      if (dashMax && !range) normMax = parseFloat(dashMax[1]);
    }

    // Wert als % der oberen Norm (100% = Normgrenze)
    let pct = normMax && normMax > 0 ? (val / normMax) * 100 : 50;
    // HDL ist invers – höher ist besser
    if (name === "HDL" && normMax) {
      pct = Math.min(150, (val / 60) * 100);
    }
    pct = Math.min(200, Math.max(0, pct)); // Clamp 0-200

    radarLabels.push(name);
    radarData.push(Math.round(pct));
  }

  if (radarLabels.length < 3) return;

  const ctx = canvas.getContext("2d");

  if (radarInstance) radarInstance.destroy();

  radarInstance = new Chart(ctx, {
    type: "radar",
    data: {
      labels: radarLabels,
      datasets: [
        {
          label: "Aktuell (% der Norm)",
          data: radarData,
          borderColor: isDark ? "#60a5fa" : "#3b82f6",
          backgroundColor: isDark ? "rgba(96,165,250,.15)" : "rgba(59,130,246,.1)",
          borderWidth: 2,
          pointBackgroundColor: radarData.map(v =>
            v > 120 ? (isDark ? "#f87171" : "#dc2626") :
            v > 100 ? (isDark ? "#fbbf24" : "#d97706") :
            (isDark ? "#34d399" : "#059669")
          ),
          pointRadius: 5,
          pointHoverRadius: 7,
        },
        {
          label: "Normgrenze (100%)",
          data: Array(radarLabels.length).fill(100),
          borderColor: isDark ? "rgba(251,146,60,.5)" : "rgba(234,88,12,.4)",
          backgroundColor: "transparent",
          borderWidth: 1.5,
          borderDash: [5, 3],
          pointRadius: 0,
          pointHoverRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 500 },
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: {
            color: isDark ? "#e2e8f0" : "#1e293b",
            font: { size: 12, weight: "500" },
            usePointStyle: true,
          },
        },
        title: {
          display: true,
          text: "Risiko-Profil (aktueller Stand)",
          color: isDark ? "#e2e8f0" : "#1e293b",
          font: { size: 14, weight: "600" },
        },
        tooltip: {
          backgroundColor: isDark ? "rgba(15,23,42,.95)" : "rgba(255,255,255,.95)",
          titleColor: isDark ? "#fff" : "#1e293b",
          bodyColor: isDark ? "#e2e8f0" : "#475569",
          borderColor: isDark ? "rgba(255,255,255,.1)" : "rgba(0,0,0,.08)",
          borderWidth: 1,
          callbacks: {
            label: function(ctx) {
              if (ctx.datasetIndex === 1) return "  Normgrenze: 100%";
              const v = ctx.parsed.r;
              const status = v > 120 ? "⚠️ deutlich erhöht" : v > 100 ? "⬆ leicht erhöht" : "✓ normal";
              return `  ${ctx.label}: ${v}% ${status}`;
            },
          },
        },
      },
      scales: {
        r: {
          beginAtZero: true,
          max: Math.max(150, ...radarData.map(v => Math.min(v + 20, 200))),
          ticks: {
            color: isDark ? "#94a3b8" : "#64748b",
            backdropColor: "transparent",
            font: { size: 10 },
            stepSize: 50,
          },
          grid: {
            color: isDark ? "rgba(255,255,255,.15)" : "rgba(0,0,0,.1)",
          },
          angleLines: {
            color: isDark ? "rgba(255,255,255,.15)" : "rgba(0,0,0,.1)",
          },
          pointLabels: {
            color: isDark ? "#e2e8f0" : "#1e293b",
            font: { size: 13, weight: "600" },
          },
        },
      },
    },
  });
}
