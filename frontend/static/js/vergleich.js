// vergleich.js – Mehrjahresvergleich Pivot-Tabelle + Diverging-Bar-Chart
import { navigate } from "./state.js";

const BEWERTUNG_ICONS = {
  verschlechtert: "▲",
  neu_auffällig: "⚠️",
  verbessert: "▼",
  normalisiert: "✅",
  stabil: "→",
};

const BEWERTUNG_COLORS = {
  verschlechtert: "var(--red)",
  neu_auffällig: "var(--red)",
  verbessert: "var(--green)",
  normalisiert: "var(--green)",
  stabil: "var(--text-muted)",
};

// Chart.js-Instanz für Cleanup
let _vergleichChart = null;

/**
 * Rendert den Diverging-Bar-Chart (Butterfly) unter der Tabelle.
 */
function _renderDivergingChart(container, data) {
  // Cleanup alter Chart
  if (_vergleichChart) {
    _vergleichChart.destroy();
    _vergleichChart = null;
  }

  // Reihenfolge: gleich wie Tabelle (umgekehrt für Chart da Y-Achse von unten nach oben)
  const items = [];
  for (const t of data.tests) {
    const firstZr = t.zeitraeume?.[0];
    if (firstZr && firstZr.pct !== undefined && firstZr.pct !== 0) {
      items.push({ test: t.test, pct: firstZr.pct, flag: t.flag });
    }
  }

  if (items.length < 2) return;

  // Gleiche Reihenfolge wie Tabelle (Chart.js zeichnet Y-Achse von oben nach unten)
  // Keine Umsortierung nötig

  const labels = items.map(d => d.test);

  // Gedeckelte Werte: abs > 150% wird komprimiert
  const cappedValues = items.map(d => {
    const abs = Math.abs(d.pct);
    if (abs <= 150) return d.pct;
    const compressed = 150 + Math.sqrt(abs - 150) * 8;
    return d.pct > 0 ? compressed : -compressed;
  });

  // Einheitliche Farbe – Chart zeigt nur die Änderung, Bewertung steht in der Tabelle
  const bgColors = items.map(() => "rgba(59, 130, 246, 0.7)");

  // Dynamische Höhe
  const chartHeight = Math.max(160, items.length * 30 + 50);
  container.style.height = chartHeight + "px";

  const canvas = document.createElement("canvas");
  canvas.id = "vergleichDivChart";
  container.appendChild(canvas);

  const originalPcts = items.map(d => d.pct);

  // Farben für Achsen – liest CSS-Variablen
  const cs = getComputedStyle(document.documentElement);
  const labelColor = cs.getPropertyValue("--text").trim() || "#1e293b";
  const axisColor = cs.getPropertyValue("--text-muted").trim() || "#64748b";

  _vergleichChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: cappedValues,
        backgroundColor: bgColors,
        borderColor: "transparent",
        borderWidth: 0,
        borderRadius: 3,
        barThickness: 18,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: { padding: { left: 0, right: 15, top: 0, bottom: 0 } },
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: "Veränderung zur letzten Messung (%)",
          font: { size: 12, weight: "600" },
          color: labelColor,
          padding: { bottom: 8 },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const real = originalPcts[ctx.dataIndex];
              return ` ${real > 0 ? "+" : ""}${real}%`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(128,128,128,.2)" },
          ticks: {
            font: { size: 9 },
            color: axisColor,
            callback: (v) => `${v > 0 ? "+" : ""}${Math.round(v)}%`,
          },
          border: { display: false },
        },
        y: {
          grid: { display: false },
          ticks: {
            font: { size: 10, weight: "600" },
            color: labelColor,
            padding: 4,
          },
        },
      },
    },
  });
}

/**
 * Rendert die Vergleichs-Pivot-Tabelle im #cards Container.
 */
export function renderVergleich(data) {
  const el = document.getElementById("cards");
  if (!data || !data.tests?.length) {
    el.style.display = "block";
    el.innerHTML = `<div class="path-list">
      <div class="card-title" style="margin-bottom:1.2rem; font-size:1.8rem;">📊 Mehrjahresvergleich</div>
      <p style="color:var(--text-muted)">Keine signifikanten Veränderungen gefunden.</p>
    </div>`;
    return;
  }

  el.style.display = "block";

  const maxCols = data.max_cols || 5;

  // Zelle für einen Zeitraum-Vergleich
  function renderZelle(zr) {
    if (!zr || zr.wert === null || zr.wert === undefined) {
      return `<td class="vgl-cell empty">–</td>`;
    }

    const bewertung = zr.bewertung || "stabil";
    const icon = BEWERTUNG_ICONS[bewertung] || "";
    const color = BEWERTUNG_COLORS[bewertung] || "var(--text-muted)";
    const pctText = zr.pct ? `${zr.pct > 0 ? "+" : ""}${zr.pct}%` : "";

    return `<td class="vgl-cell ${bewertung}" style="color:${color}">
      <span class="vgl-wert">${zr.wert}</span>
      ${pctText ? `<span class="vgl-pct">${pctText}</span>` : ""}
      <span class="vgl-icon">${icon}</span>
      ${zr.label ? `<br><span class="vgl-datum">${zr.label}</span>` : ""}
    </td>`;
  }

  const rows = data.tests.map(t => {
    const flagClass = t.flag === "H" ? "high" : t.flag === "L" ? "low" : "";
    // Zellen auffüllen falls weniger als maxCols vorhanden
    const zellen = [];
    for (let i = 0; i < maxCols; i++) {
      zellen.push(renderZelle(t.zeitraeume[i]));
    }
    return `<tr class="vgl-row" data-test="${t.test}" data-gruppe="${t.gruppe}">
      <td class="vgl-gruppe" style="color:var(--text-muted)">${t.gruppe}</td>
      <td class="vgl-test"><strong>${t.test}</strong>${t.kurzname ? `<br><span class="card-kurzname">${t.kurzname}</span>` : ""}</td>
      <td class="vgl-aktuell ${flagClass}"><strong>${t.aktuell}</strong> ${t.einheit}${t.flag ? (t.flag === "H" ? " ↑" : " ↓") : ""}${t.norm ? `<br><span class="vgl-norm">(${t.norm})</span>` : ""}</td>
      ${zellen.join("")}
    </tr>`;
  }).join("");

  // Header: keine globalen Labels da jeder Test eigene Zeitpunkte hat
  const colHeaders = maxCols > 0 ? `<th colspan="${maxCols}" style="text-align:center; font-weight:400; color:var(--text-muted)">← vorherige Messungen (neueste zuerst)</th>` : "";

  el.innerHTML = `<div class="path-list">
    <div class="card-title" style="margin-bottom:1.2rem; font-size:1.8rem;">📊 Mehrjahresvergleich (${data.anzahl} Tests mit Veränderung)</div>
    <div class="vgl-legende">
      <span style="color:var(--green)">▼ verbessert</span>
      <span style="color:var(--green)">✅ normalisiert</span>
      <span style="color:var(--red)">▲ verschlechtert</span>
      <span style="color:var(--red)">⚠️ neu auffällig</span>
      <span style="color:var(--text-muted)">→ unverändert</span>
    </div>
    <table class="vgl-table">
      <thead><tr>
        <th>Gruppe</th>
        <th>Test</th>
        <th>Aktuell</th>
        ${colHeaders}
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div id="vergleich-chart-container" class="vgl-chart-wrap"></div>
  </div>`;

  // Diverging-Bar-Chart rendern
  const chartContainer = document.getElementById("vergleich-chart-container");
  _renderDivergingChart(chartContainer, data);

  // Beim Drucken Chart mit dunklen Farben neu rendern
  const _printHandler = () => {
    if (_vergleichChart) {
      _vergleichChart.options.plugins.title.color = "#1e293b";
      _vergleichChart.options.scales.x.ticks.color = "#475569";
      _vergleichChart.options.scales.y.ticks.color = "#1e293b";
      _vergleichChart.options.scales.x.grid.color = "rgba(0,0,0,.12)";
      _vergleichChart.update("none");
    }
  };
  const _afterPrintHandler = () => {
    if (_vergleichChart) {
      const cs2 = getComputedStyle(document.documentElement);
      _vergleichChart.options.plugins.title.color = cs2.getPropertyValue("--text").trim();
      _vergleichChart.options.scales.x.ticks.color = cs2.getPropertyValue("--text-muted").trim();
      _vergleichChart.options.scales.y.ticks.color = cs2.getPropertyValue("--text").trim();
      _vergleichChart.options.scales.x.grid.color = "rgba(128,128,128,.2)";
      _vergleichChart.update("none");
    }
  };
  window.removeEventListener("beforeprint", _printHandler);
  window.removeEventListener("afterprint", _afterPrintHandler);
  window.addEventListener("beforeprint", _printHandler);
  window.addEventListener("afterprint", _afterPrintHandler);

  // Row-Click → Trend
  el.querySelectorAll(".vgl-row").forEach(row => {
    row.style.cursor = "pointer";
    row.addEventListener("click", () => {
      navigate("trend", { test: row.dataset.test, gruppe: row.dataset.gruppe });
    });
  });
}
