// cards.js – Gruppen- und Test-Karten rendern
import { state, navigate } from "./state.js";
import { starIconHtml, bindStarHandlers } from "./favoriten.js";

const GROUP_ICONS = {
  Blutbild: "🩸", Differentialblutbild: "🔬", Entzündung: "🔥",
  Leber: "🫁", Niere: "💧", Elektrolyte: "⚡", Stoffwechsel: "🧬",
  Lipide: "🫀", Pankreas: "🟡", Gerinnung: "🩹", Harnanalyse: "🧪",
  Schilddrüse: "🦋", "Tumor-Marker": "🎯", Autoimmun: "🛡️",
  Hormone: "💉", Körperdaten: "📏", Sonstige: "📋",
};

const GROUP_COLORS = {
  Blutbild: "#ef4444", Differentialblutbild: "#f97316", Entzündung: "#f59e0b",
  Leber: "#84cc16", Niere: "#06b6d4", Elektrolyte: "#8b5cf6", Stoffwechsel: "#ec4899",
  Lipide: "#f43f5e", Pankreas: "#eab308", Gerinnung: "#14b8a6", Harnanalyse: "#6366f1",
  Schilddrüse: "#0ea5e9", "Tumor-Marker": "#a855f7", Autoimmun: "#10b981",
  Hormone: "#d946ef", Körperdaten: "#64748b", Sonstige: "#78716c",
};

const STATUS_CONFIG = {
  gut: { label: "Alles OK", color: "var(--green)", bg: "rgba(16,185,129,.12)" },
  ok: { label: "Weitgehend OK", color: "var(--teal)", bg: "rgba(20,184,166,.12)" },
  "auffällig": { label: "Auffällig", color: "var(--orange)", bg: "rgba(245,158,11,.12)" },
  kritisch: { label: "Kritisch", color: "var(--red)", bg: "rgba(239,68,68,.12)" },
};

function drawMiniSparkline(canvas, values, accentColor) {
  if (!values || values.length < 2) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.offsetWidth, h = canvas.offsetHeight;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);

  const color = accentColor || "#10b981";

  // Gradient
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + "33"); // 20% opacity
  grad.addColorStop(1, "transparent");

  ctx.beginPath();
  values.forEach((v, i) => {
    const x = i * step, y = h - ((v - min) / range) * (h - 4) - 2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  // Line
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = i * step, y = h - ((v - min) / range) * (h - 4) - 2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.8; ctx.lineJoin = "round"; ctx.stroke();
}

export function renderCards(items, mode = "gruppe") {
  const el = document.getElementById("cards");
  if (!items) { el.innerHTML = ""; return; }

  if (mode === "gruppe") {
    el.style.display = ""; // Grid zurücksetzen
    el.style.gridTemplateColumns = ""; // Grid-Spalten zurücksetzen

    // Nach Status sortieren: kritisch → auffällig → ok → gut
    const statusOrder = { "kritisch": 0, "auffällig": 1, "ok": 2, "gut": 3 };
    const sorted = [...items].sort((a, b) => (statusOrder[a.status] ?? 4) - (statusOrder[b.status] ?? 4));

    // Nach Status gruppieren mit Überschriften
    const STATUS_LABELS = {
      kritisch: "🚨 Kritisch – Handlungsbedarf",
      "auffällig": "⚠️ Auffällig – beobachten",
      ok: "👍 Weitgehend OK",
      gut: "✅ Alles im Normbereich",
    };

    let html = "";
    let lastStatus = null;

    sorted.forEach(g => {
      if (g.status !== lastStatus) {
        lastStatus = g.status;
        html += `<div class="cards-section-header">${STATUS_LABELS[g.status] || g.status}</div>`;
      }

      const icon = g.icon || GROUP_ICONS[g.name] || "📋";
      const color = g.farbe || GROUP_COLORS[g.name] || "#64748b";
      const st = STATUS_CONFIG[g.status] || STATUS_CONFIG.gut;
      const auffaellige = (g.letzte_auffaellige || []).map(a =>
        `<span class="flag-item">${a.test_standard}: ${a.wert_norm} ${a.flag === "H" ? "↑" : "↓"}</span>`
      ).join("");

      html += `
        <div class="card" data-gruppe="${g.name}" style="border-top:3px solid ${color}">
          <div class="card-header-row">
            <div class="card-title">${icon} ${g.name}</div>
            <span class="status-pill" style="background:${st.bg};color:${st.color}">${st.label}</span>
          </div>
          <div class="card-desc">${g.beschreibung || ""}</div>
          <div class="card-sparkline-wrap"><canvas class="mini-spark" data-values='${JSON.stringify(g.jahres_trend || [])}' data-color="${color}"></canvas></div>
          <div class="card-stats-row">
            <span class="card-stat">${g.anzahl} Messungen</span>
            <span class="card-stat">${g.pathologisch || 0}× auffällig</span>
            <span class="card-stat">Letzte: ${g.letztes_datum || "–"}</span>
          </div>
          ${auffaellige ? `<div class="card-flags">${auffaellige}</div>` : ""}
        </div>
      `;
    });

    el.innerHTML = html;

    el.querySelectorAll(".card").forEach(card => {
      card.addEventListener("click", () => navigate("gruppe", { gruppe: card.dataset.gruppe }));
    });

    // Sparklines zeichnen
    requestAnimationFrame(() => {
      el.querySelectorAll(".mini-spark").forEach(canvas => {
        const vals = JSON.parse(canvas.dataset.values || "[]");
        const color = canvas.dataset.color || null;
        if (vals.length > 1) drawMiniSparkline(canvas, vals, color);
      });
    });

  } else if (mode === "pathologisch") {
    // Auffällige Werte als kompakte Liste (ein Eintrag pro Test)
    el.style.display = "block";

    let sortCol = state.pathSortCol || "datum";
    let sortDir = state.pathSortDir || -1;

    function renderTable(data, col, dir) {
      const sorted = [...data].sort((a, b) => {
        let va = a[col] || "", vb = b[col] || "";
        if (col === "anzahl") { va = a.anzahl || 0; vb = b.anzahl || 0; }
        if (col === "wert_norm") { va = parseFloat(String(va).replace(/[<>]/g, "")) || 0; vb = parseFloat(String(vb).replace(/[<>]/g, "")) || 0; }
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
      });

      const arrow = (col2) => col2 === col ? `<span class="sort-arrow">${dir === 1 ? '▲' : '▼'}</span>` : '';

      el.innerHTML = `<div class="path-list">
        <div class="card-title" style="margin-bottom:1.2rem; font-size:1.8rem;">⚠️ Auffällige Tests (${sorted.length})</div>
        <table class="path-table">
          <thead><tr>
            <th data-col="datum">Datum${arrow('datum')}</th>
            <th data-col="gruppe">Gruppe${arrow('gruppe')}</th>
            <th data-col="test_standard">Test${arrow('test_standard')}</th>
            <th data-col="wert_norm">Wert${arrow('wert_norm')}</th>
            <th>Norm</th>
            <th data-col="flag">Flag${arrow('flag')}</th>
            <th data-col="anzahl">×${arrow('anzahl')}</th>
          </tr></thead>
          <tbody>
            ${sorted.map(r => `
              <tr class="path-row" data-test="${r.test_standard}" data-gruppe="${r.gruppe}">
                <td>${r.datum}</td>
                <td><span style="color:${GROUP_COLORS[r.gruppe] || '#64748b'}">${r.gruppe}</span></td>
                <td><strong>${r.test_standard}</strong>${r.kurzname ? `<br><span class="card-kurzname">${r.kurzname}</span>` : ''}</td>
                <td>${r.wert_norm} ${r.einheit_norm || ""}</td>
                <td style="color:var(--text-muted)">${r.normbereich || ""}</td>
                <td><span class="flag-pill ${r.flag === 'H' ? 'high' : 'low'}">${r.flag === 'H' ? '↑ hoch' : '↓ tief'}</span></td>
                <td style="font-weight:600;color:var(--text-muted)">${r.anzahl > 1 ? r.anzahl + '×' : '1'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>`;

      // Sort-Handler
      el.querySelectorAll("th[data-col]").forEach(th => {
        th.addEventListener("click", () => {
          const newCol = th.dataset.col;
          if (newCol === sortCol) { sortDir *= -1; } else { sortCol = newCol; sortDir = 1; }
          state.pathSortCol = sortCol;
          state.pathSortDir = sortDir;
          localStorage.setItem("lab_state", JSON.stringify(state));
          renderTable(data, sortCol, sortDir);
          // Bericht-Link aktualisieren
          const btn = document.querySelector(".report-btn");
          if (btn) btn.href = `api/bericht/charts?befunde=${parseInt(sortCol === sortCol ? state.pathPeriod : state.pathPeriod) || 0}&sort=${sortCol}&dir=${sortDir}`;
        });
      });

      // Bericht-Link immer nach renderTable aktualisieren
      const btn = document.querySelector(".report-btn");
      if (btn) btn.href = `api/bericht/charts?befunde=${parseInt(state.pathPeriod) || 0}&sort=${col}&dir=${dir}`;

      // Row-Click
      el.querySelectorAll(".path-row").forEach(row => {
        row.style.cursor = "pointer";
        row.addEventListener("click", () => {
          navigate("trend", { test: row.dataset.test, gruppe: row.dataset.gruppe });
        });
      });
    }

    renderTable(items, sortCol, sortDir);

    el.querySelectorAll(".path-row").forEach(row => {
      row.style.cursor = "pointer";
      row.addEventListener("click", () => {
        navigate("trend", { test: row.dataset.test, gruppe: row.dataset.gruppe });
      });
    });

  } else {
    // Test-Karten innerhalb einer Gruppe
    el.style.display = "";
    el.style.gridTemplateColumns = "";
    const tests = Object.entries(items);

    // Status pro Test berechnen und sortieren
    const testsWithStatus = tests.map(([name, data]) => {
      const highCount = data.werte.filter(w => w.flag === "H").length;
      const lowCount = data.werte.filter(w => w.flag === "L").length;
      const total = data.werte.length;
      const pathRatio = (highCount + lowCount) / total;

      // Aktueller Status: primär am letzten Wert orientiert
      const last = data.werte[data.werte.length - 1];
      const lastFlag = last?.flag || "";
      let status;
      if (!lastFlag) {
        // Letzter Wert OK – letzte 3 prüfen für Stabilität
        const recent3 = data.werte.slice(-3);
        const r3Path = recent3.filter(w => w.flag === "H" || w.flag === "L").length;
        status = r3Path === 0 ? "gut" : "ok";
      } else {
        // Letzter Wert auffällig – letzte 3 prüfen für Schwere
        const recent3 = data.werte.slice(-3);
        const r3Path = recent3.filter(w => w.flag === "H" || w.flag === "L").length;
        status = r3Path >= 3 ? "kritisch" : r3Path >= 2 ? "auffällig" : "auffällig";
      }

      // Historischer Hinweis
      const histHint = (pathRatio > 0.15 && status === "gut") ? "Früher auffällig" : "";

      return { name, data, status, highCount, lowCount, total, histHint };
    });

    const statusOrder = { "kritisch": 0, "auffällig": 1, "ok": 2, "gut": 3 };
    testsWithStatus.sort((a, b) => (statusOrder[a.status] ?? 4) - (statusOrder[b.status] ?? 4));

    const STATUS_LABELS = {
      kritisch: "🚨 Kritisch",
      "auffällig": "⚠️ Auffällig",
      ok: "👍 Weitgehend OK",
      gut: "✅ Im Normbereich",
    };

    let html = "";
    let lastStatus = null;

    testsWithStatus.forEach(({ name, data, status, highCount, lowCount, total, histHint }) => {
      if (status !== lastStatus) {
        lastStatus = status;
        html += `<div class="cards-section-header">${STATUS_LABELS[status] || status}</div>`;
      }

      const last = data.werte[data.werte.length - 1];
      const st = STATUS_CONFIG[status];
      const canDrill = total >= 5;

      const sparkVals = data.werte.map(w => {
        let v = String(w.wert).replace(",", ".").replace(/^[<>]/, "");
        return parseFloat(v) || 0;
      });

      let detailHtml = "";
      if (!canDrill && total > 0) {
        detailHtml = `<div class="card-inline-values">
          ${data.werte.map(w => `
            <span class="inline-val ${w.flag === 'H' ? 'high' : w.flag === 'L' ? 'low' : ''}">
              ${w.datum.slice(0,10)}: <strong>${w.wert}</strong>${w.flag ? (w.flag === 'H' ? ' ↑' : ' ↓') : ''}
            </span>
          `).join("")}
        </div>`;
      }

      html += `
        <div class="card ${canDrill ? '' : 'no-drill'}" data-test="${name}" data-can-drill="${canDrill}">
          <div class="card-header-row">
            <div class="card-title">${starIconHtml(name)} ${name}</div>
            <span class="status-pill" style="background:${st.bg};color:${st.color}">${st.label}</span>
          </div>
          ${data.kurzname ? `<div class="card-kurzname">${data.kurzname}</div>` : ''}
          ${data.beschreibung ? `<div class="card-desc">${data.beschreibung}</div>` : ""}
          <div class="card-value-row">
            <span class="card-count">${last.wert}</span>
            <span class="card-unit">${data.einheit || ""}</span>
          </div>
          ${canDrill ? `<div class="card-sparkline-wrap"><canvas class="mini-spark" data-values='${JSON.stringify(sparkVals)}'></canvas></div>` : detailHtml}
          <div class="card-stats-row">
            <span class="card-stat">${total} Messung${total > 1 ? 'en' : ''}</span>
            <span class="card-stat">Norm: ${data.normbereich || "–"}</span>
            ${canDrill ? '<span class="card-stat card-drill-hint">▶ Trend</span>' : ""}
          </div>
          <div class="card-flags">
            ${highCount ? `<span class="flag-pill high">↑ ${highCount}× hoch</span>` : ""}
            ${lowCount ? `<span class="flag-pill low">↓ ${lowCount}× tief</span>` : ""}
            ${!highCount && !lowCount ? `<span class="flag-pill ok">✓ Alle im Normbereich</span>` : ""}
            ${histHint ? `<span class="flag-pill hist">📋 ${histHint}</span>` : ""}
          </div>
        </div>
      `;
    });

    el.innerHTML = html;

    // Favoriten-Sterne Handler
    bindStarHandlers(el);

    el.querySelectorAll(".card[data-can-drill='true']").forEach(card => {
      card.addEventListener("click", () => navigate("trend", { test: card.dataset.test, gruppe: state.gruppe }));
    });

    requestAnimationFrame(() => {
      el.querySelectorAll(".mini-spark").forEach(canvas => {
        const vals = JSON.parse(canvas.dataset.values || "[]");
        if (vals.length > 1) drawMiniSparkline(canvas, vals);
      });
    });
  }
}
