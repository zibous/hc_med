// vergleich.js – Mehrjahresvergleich Pivot-Tabelle
import { navigate } from "./state.js";

const BEWERTUNG_ICONS = {
  verschlechtert: "↓",
  neu_auffällig: "⚠️↓",
  verbessert: "↑",
  normalisiert: "✅↑",
  stabil: "→",
};

const BEWERTUNG_COLORS = {
  verschlechtert: "var(--red)",
  neu_auffällig: "var(--red)",
  verbessert: "var(--green)",
  normalisiert: "var(--green)",
  stabil: "var(--text-muted)",
};

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

  const zeitraeume = data.zeitraeume_label || [];

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
      ${zr.flag ? `<span class="vgl-flag">${zr.flag === "H" ? "↑" : "↓"}</span>` : ""}
      ${pctText ? `<span class="vgl-pct">${pctText}</span>` : ""}
      <span class="vgl-icon">${icon}</span>
    </td>`;
  }

  const rows = data.tests.map(t => {
    const flagClass = t.flag === "H" ? "high" : t.flag === "L" ? "low" : "";
    return `<tr class="vgl-row" data-test="${t.test}" data-gruppe="${t.gruppe}">
      <td class="vgl-gruppe" style="color:var(--text-muted)">${t.gruppe}</td>
      <td class="vgl-test"><strong>${t.test}</strong>${t.kurzname ? `<br><span class="card-kurzname">${t.kurzname}</span>` : ""}</td>
      <td class="vgl-aktuell ${flagClass}"><strong>${t.aktuell}</strong> ${t.einheit}${t.flag ? (t.flag === "H" ? " ↑" : " ↓") : ""}</td>
      ${t.zeitraeume.map(zr => renderZelle(zr)).join("")}
    </tr>`;
  }).join("");

  el.innerHTML = `<div class="path-list">
    <div class="card-title" style="margin-bottom:1.2rem; font-size:1.8rem;">📊 Mehrjahresvergleich (${data.anzahl} Tests mit Veränderung)</div>
    <div class="vgl-legende">
      <span style="color:var(--green)">↑ verbessert</span>
      <span style="color:var(--green)">✅↑ normalisiert</span>
      <span style="color:var(--red)">↓ verschlechtert</span>
      <span style="color:var(--red)">⚠️↓ neu auffällig</span>
      <span style="color:var(--text-muted)">→ stabil</span>
    </div>
    <table class="vgl-table">
      <thead><tr>
        <th>Gruppe</th>
        <th>Test</th>
        <th>Aktuell</th>
        ${zeitraeume.map(z => `<th>${z}</th>`).join("")}
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;

  // Row-Click → Trend
  el.querySelectorAll(".vgl-row").forEach(row => {
    row.style.cursor = "pointer";
    row.addEventListener("click", () => {
      navigate("trend", { test: row.dataset.test, gruppe: row.dataset.gruppe });
    });
  });
}
