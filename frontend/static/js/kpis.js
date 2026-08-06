// kpis.js – KPI-Kacheln rendern
import { navigate } from "./state.js";

const BEWERTUNG_STYLES = {
  gut: { icon: "✅", color: "var(--green)" },
  ok: { icon: "👍", color: "var(--teal)" },
  "auffällig": { icon: "⚠️", color: "var(--orange)" },
  kritisch: { icon: "🚨", color: "var(--red)" },
};

export function renderKPIs(kpis, gruppen, vergleich, gefaess) {
  const el = document.getElementById("kpis");
  if (!kpis) { el.innerHTML = ""; return; }

  // Gruppen-Detail-Ansicht (hat "bewertung" Feld)
  if (kpis.bewertung) {
    const bst = BEWERTUNG_STYLES[kpis.bewertung_status] || BEWERTUNG_STYLES.gut;
    const normPct = kpis.gesamt > 0 ? Math.round(kpis.ok / kpis.gesamt * 100) : 100;
    const pathPct = 100 - normPct;

    // Segmented progress bar
    const okSegs = Math.round(normPct / 10);
    const pathSegs = 10 - okSegs;
    let barHtml = "";
    for (let i = 0; i < 10; i++) {
      const filled = i < okSegs;
      barHtml += `<div class="health-seg ${filled ? "ok" : "path"}"></div>`;
    }

    el.innerHTML = `
      <div class="kpi kpi-half health-card">
        <div class="health-card-header">
          <span class="health-card-label">Verteilung</span>
          <span class="health-card-count">${kpis.gesamt} Messungen</span>
        </div>
        <div class="health-bar">${barHtml}</div>
        <div class="health-legend">
          <span class="health-legend-item"><span class="health-dot ok"></span>${kpis.ok} im Norm (${normPct}%)</span>
          <span class="health-legend-item"><span class="health-dot path"></span>${kpis.auffaellig} auffällig (${pathPct}%)</span>
        </div>
      </div>
      <div class="kpi kpi-half health-card">
        <div class="health-card-header">
          <span class="health-card-label">Einschätzung</span>
        </div>
        <div class="health-status" style="color:${bst.color}">
          <span class="health-status-icon">${bst.icon}</span>
          <span class="health-status-label">${kpis.bewertung_status === 'gut' ? 'Sehr gut' : kpis.bewertung_status === 'ok' ? 'Weitgehend OK' : kpis.bewertung_status === 'auffällig' ? 'Beobachten' : 'Handeln'}</span>
        </div>
        <div class="health-sub">${kpis.bewertung}</div>
      </div>
    `;
    return;
  }

  // Übersicht
  const critical = (gruppen || []).filter(g => g.status === "kritisch" || g.status === "auffällig");
  const normPct = kpis.messwerte > 0 ? Math.round((kpis.messwerte - kpis.pathologisch) / kpis.messwerte * 100) : 100;

  const criticalHtml = critical.length > 0
    ? critical.map(g => `<a class="kpi-link" data-gruppe="${g.name}" style="color:${g.status === 'kritisch' ? 'var(--red)' : 'var(--orange)'}; cursor:pointer;">${g.name}</a>`).join(", ")
    : `<span style="color:var(--green)">Keine</span>`;

  // Gesamtbewertung kurz
  let bewertungIcon;
  if (critical.length === 0) { bewertungIcon = "✅"; }
  else if (critical.filter(g => g.status === "kritisch").length > 0) { bewertungIcon = "🚨"; }
  else { bewertungIcon = "⚠️"; }

  el.innerHTML = `
    <div class="kpi">
      <div class="kpi-label">Messungen</div>
      <div class="kpi-value blue">${kpis.messwerte}</div>
      <div class="kpi-sub">${kpis.befunde} Befunde · ${kpis.zeitraum_von?.slice(0,4)}–${kpis.zeitraum_bis?.slice(0,4)}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Im Normbereich</div>
      <div class="kpi-value green">${normPct}%</div>
      <div class="kpi-sub">${bewertungIcon} ${kpis.messwerte - kpis.pathologisch} von ${kpis.messwerte} Werten</div>
    </div>
    <div class="kpi kpi-clickable" id="kpi-auffaellig" style="cursor:pointer">
      <div class="kpi-label">Auffällige Werte</div>
      <div class="kpi-value red">${kpis.pathologisch}</div>
      <div class="kpi-sub">Klick für Details →</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Handlungsbedarf</div>
      <div class="kpi-value-text" style="font-size:1.4rem">${criticalHtml}</div>
      <div class="kpi-sub">${critical.length} von ${(gruppen||[]).length} Gruppen</div>
    </div>
    ${vergleich ? `<div class="kpi kpi-half kpi-clickable" id="kpi-vergleich" style="cursor:pointer">
      <div class="kpi-label">Vergleich zum Vorjahr</div>
      <div class="kpi-value-text">
        ${vergleich.verbessert?.length ? `<span style="color:var(--green)">↑ Verbessert (${vergleich.verbessert.length}): ${vergleich.verbessert.slice(0,4).map(v => v.test).join(', ')}</span>` : ''}
        ${vergleich.verbessert?.length && vergleich.verschlechtert?.length ? ' · ' : ''}
        ${vergleich.verschlechtert?.length ? `<span style="color:var(--red)">↓ Verschlechtert (${vergleich.verschlechtert.length}): ${vergleich.verschlechtert.slice(0,4).map(v => v.test).join(', ')}</span>` : ''}
        ${!vergleich.verbessert?.length && !vergleich.verschlechtert?.length ? '<span style="color:var(--green)">→ Alle Werte stabil</span>' : ''}
      </div>
      <div class="kpi-sub">${vergleich.stabil_count || 0} Tests unverändert · Klick für Mehrjahresvergleich →</div>
    </div>` : ''}
    ${gefaess ? `<div class="kpi kpi-half kpi-clickable" id="kpi-gefaess" style="cursor:pointer; border-left:3px solid ${gefaess.status === 'kritisch' ? 'var(--red)' : gefaess.status === 'auffällig' ? 'var(--orange)' : 'var(--green)'}">
      <div class="kpi-label">🫀 Gefäßgesundheit (Arterien-Risiko)</div>
      <div class="kpi-value-text">
        <span style="color:${gefaess.status === 'kritisch' ? 'var(--red)' : gefaess.status === 'auffällig' ? 'var(--orange)' : 'var(--green)'}">
          Score ${gefaess.score}/${gefaess.max} – ${gefaess.status === 'kritisch' ? 'Erhöhtes Risiko' : gefaess.status === 'auffällig' ? 'Mäßiges Risiko' : 'Geringes Risiko'}
        </span>
        ${gefaess.details.length ? ' · ' + gefaess.details.join(', ') : ''}
      </div>
      <div class="kpi-sub">Klick für Detailanalyse mit Empfehlungen →</div>
    </div>` : ''}
    <div class="kpi kpi-half kpi-clickable" id="kpi-gesamtbericht" style="cursor:pointer; border-left:3px solid var(--accent)">
      <div class="kpi-label">📋 Gesamtbericht</div>
      <div class="kpi-value-text">Alle Befunde auf einer Seite – für den Arzttermin</div>
      <div class="kpi-sub">Klick → druckfertiger Bericht in neuem Tab →</div>
    </div>
    <div class="kpi kpi-half kpi-clickable" id="kpi-alle-tests" style="cursor:pointer; border-left:3px solid var(--teal)">
      <div class="kpi-label">📋 Alle Tests</div>
      <div class="kpi-value-text">Alle Laborwerte in einer sortierbaren Tabelle mit Norm-Balken</div>
      <div class="kpi-sub">Klick → Übersicht aller Werte →</div>
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

  // Klick auf Gefäßgesundheit
  document.getElementById("kpi-gefaess")?.addEventListener("click", () => {
    navigate("verknuepfung", { verknuepfung: "Gefäßgesundheit" });
  });

  // Klick auf Vergleich
  document.getElementById("kpi-vergleich")?.addEventListener("click", () => {
    navigate("vergleich", {});
  });

  // Klick auf Gesamtbericht
  document.getElementById("kpi-gesamtbericht")?.addEventListener("click", () => {
    window.open("api/gesamtbericht", "_blank");
  });

  // Klick auf Alle Tests
  document.getElementById("kpi-alle-tests")?.addEventListener("click", () => {
    navigate("alle-tests", {});
  });
}
