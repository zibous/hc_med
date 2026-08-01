// kpis.js – KPI-Kacheln rendern
import { navigate } from "./state.js";

const BEWERTUNG_STYLES = {
  gut: { icon: "✅", color: "var(--green)" },
  ok: { icon: "👍", color: "var(--teal)" },
  "auffällig": { icon: "⚠️", color: "var(--orange)" },
  kritisch: { icon: "🚨", color: "var(--red)" },
};

export function renderKPIs(kpis, gruppen) {
  const el = document.getElementById("kpis");
  if (!kpis) { el.innerHTML = ""; return; }

  // Gruppen-Detail-Ansicht (hat "bewertung" Feld)
  if (kpis.bewertung) {
    const bst = BEWERTUNG_STYLES[kpis.bewertung_status] || BEWERTUNG_STYLES.gut;
    el.innerHTML = `
      <div class="kpi">
        <div class="kpi-label">Im Normbereich</div>
        <div class="kpi-value green">${kpis.ok}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Auffällig</div>
        <div class="kpi-value red">${kpis.auffaellig}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Gesamt</div>
        <div class="kpi-value blue">${kpis.gesamt}</div>
      </div>
      <div class="kpi kpi-wide">
        <div class="kpi-label">Einschätzung</div>
        <div class="kpi-value-text" style="color:${bst.color}">${bst.icon} ${kpis.bewertung}</div>
      </div>
    `;
    return;
  }

  // Übersicht
  const critical = (gruppen || []).filter(g => g.status === "kritisch" || g.status === "auffällig");
  const criticalHtml = critical.length > 0
    ? critical.map(g => `<a class="kpi-link" data-gruppe="${g.name}" style="color:${g.status === 'kritisch' ? 'var(--red)' : 'var(--orange)'}; cursor:pointer;">${g.name}</a>`).join(", ")
    : `<span style="color:var(--green)">Alles im grünen Bereich</span>`;

  el.innerHTML = `
    <div class="kpi">
      <div class="kpi-label">Gesamt-Messungen</div>
      <div class="kpi-value blue">${kpis.messwerte}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Labor-Befunde</div>
      <div class="kpi-value green">${kpis.befunde}</div>
    </div>
    <div class="kpi kpi-clickable" id="kpi-auffaellig" style="cursor:pointer">
      <div class="kpi-label">Auffällige Werte</div>
      <div class="kpi-value red">${kpis.pathologisch}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Zeitraum</div>
      <div class="kpi-value orange">${kpis.zeitraum_von?.slice(0,4)} – ${kpis.zeitraum_bis?.slice(0,4)}</div>
    </div>
    <div class="kpi kpi-wide">
      <div class="kpi-label">Handlungsbedarf</div>
      <div class="kpi-value-text">${criticalHtml}</div>
    </div>
  `;

  // Klick auf Gruppen-Links
  el.querySelectorAll(".kpi-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.stopPropagation();
      navigate("gruppe", { gruppe: link.dataset.gruppe });
    });
  });

  // Klick auf "Auffällige Werte"
  document.getElementById("kpi-auffaellig")?.addEventListener("click", () => {
    navigate("pathologisch", {});
  });
}
