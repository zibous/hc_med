// main.js – Einstiegspunkt Labor Dashboard
import { state, navigate } from "./state.js";
import { renderKPIs } from "./kpis.js";
import { renderCards } from "./cards.js";
import { renderChart, renderMultiChart, renderRadarChart } from "./trend-chart.js";
import { renderBreadcrumb } from "./breadcrumb.js";
import { loadFavoritenListe, renderFavoritenKarte, starIconHtml, bindStarHandlers, renderFavoritenDetail } from "./favoriten.js";
import { renderVergleich } from "./vergleich.js";

function cleanupRadar() {
  const r1 = document.getElementById("radarEmpfehlungRow");
  if (r1) r1.remove();
  const r2 = document.getElementById("radarCard");
  if (r2) r2.remove();
}

function renderRadarWithEmpfehlung(data) {
  // Bestehenden Container entfernen
  cleanupRadar();

  // Prüfen ob Radar sinnvoll ist (nur für Gefäßgesundheit)
  const hasEnoughTests = data.gefaess_score && data.tests && Object.keys(data.tests).length >= 3;

  const container = document.createElement("div");
  container.id = "radarEmpfehlungRow";
  container.className = "radar-empfehlung-row";

  // Radar-Seite nur wenn genug Tests
  if (hasEnoughTests) {
    const radarCol = document.createElement("div");
    radarCol.className = "radar-col";
    radarCol.id = "radarCol";
    radarCol.innerHTML = `<canvas id="radarCanvas"></canvas>`;
    container.appendChild(radarCol);
  }

  // Empfehlung-Seite
  if (data.empfehlung) {
    const empCol = document.createElement("div");
    empCol.className = "empfehlung-col";

    // Gefäß-Score Bar (Apple Health Style)
    let scoreHtml = "";
    if (data.gefaess_score) {
      const gs = data.gefaess_score;
      const segments = [];
      for (let i = 0; i < gs.max; i++) {
        const filled = i < gs.score;
        segments.push(`<div class="score-seg ${filled ? "filled" : "empty"}"></div>`);
      }
      const statusLabel = gs.score >= 5 ? "Erhöhtes Risiko" : gs.score >= 3 ? "Mäßiges Risiko" : "Geringes Risiko";
      const statusColor = gs.score >= 5 ? "var(--red)" : gs.score >= 3 ? "var(--orange)" : "var(--green)";

      const faktorenHtml = gs.faktoren.map(f => {
        const dots = [];
        for (let i = 0; i < f.max; i++) {
          dots.push(`<span class="score-dot ${i < f.punkte ? "active" : ""}"></span>`);
        }
        return `<div class="score-faktor ${f.aktiv ? "aktiv" : ""}">
          <span class="score-faktor-name">${f.name}</span>
          <span class="score-faktor-wert">${f.wert}</span>
          <span class="score-faktor-dots">${dots.join("")}</span>
        </div>`;
      }).join("");

      scoreHtml = `<div class="gefaess-score-card">
        <div class="score-header">
          <span class="score-label">Gefäßrisiko</span>
          <span class="score-value" style="color:${statusColor}">${gs.score}/${gs.max}</span>
        </div>
        <div class="score-bar">${segments.join("")}</div>
        <div class="score-status" style="color:${statusColor}">${statusLabel}</div>
        <div class="score-faktoren">${faktorenHtml}</div>
      </div>`;
    }

    const items = data.empfehlung.split(" · ").map(e => `<li>${e}</li>`).join("");
    empCol.innerHTML = `${scoreHtml}<div class="empfehlung-box"><strong>💡 Empfehlung:</strong><ol class="empfehlung-liste">${items}</ol></div>`;
    container.appendChild(empCol);
  }

  // Nur einfügen wenn es Inhalt gibt
  if (container.children.length === 0) return;

  // Nach dem Chart-Card einfügen
  const chartCard = document.getElementById("chartCard");
  chartCard.parentNode.insertBefore(container, chartCard.nextSibling);

  // Radar rendern (nur wenn Canvas vorhanden)
  if (hasEnoughTests) {
    renderRadarChart(data);
    // Wenn Radar-Canvas leer geblieben ist (Chart.js hat keine Instanz drauf), entfernen
    const radarCol = document.getElementById("radarCol");
    if (radarCol) {
      const canvas = radarCol.querySelector("canvas");
      // Chart.js setzt width/height auf dem Canvas wenn es zeichnet
      if (canvas && canvas.width === 0) {
        radarCol.remove();
      }
    }
  }
}

export async function loadView() {
  try {
    // Favoriten-Karte entfernen (wird nur in Overview neu gerendert)
    const favKarte = document.getElementById("favoriten-karte");
    if (favKarte) favKarte.remove();

    // Radar/Empfehlung-Row immer bereinigen (wird nur in Verknüpfung neu erstellt)
    cleanupRadar();

    if (state.view === "overview") {
      const res = await fetch("api/overview");
      const data = await res.json();
      renderKPIs(data.kpis, data.gruppen, data.vergleich, data.gefaess);
      renderCards(data.gruppen);
      renderChart(null);
      document.getElementById("view-description").textContent = "";
      // Favoriten-Karte anzeigen
      await renderFavoritenKarte();
      // Untertitel mit aktuellem Zeitraum
      const sub = document.getElementById("subtitle");
      if (sub && data.kpis) {
        sub.textContent = `Verlaufsanalyse · ${data.kpis.zeitraum_von?.slice(0,4)} – ${data.kpis.zeitraum_bis?.slice(0,4)}`;
      }
    } else if (state.view === "pathologisch") {
      const period = state.pathPeriod || "all";
      let url = "api/pathologisch";
      if (period !== "all") url += `?period=${period}`;
      const res = await fetch(url);
      const data = await res.json();
      renderKPIs(null);
      renderCards(data, "pathologisch");
      renderChart(null);
      // Zeitfilter-Buttons
      const periods = [
        { key: "all", label: "Alle" },
        { key: "1y", label: "Letztes Jahr" },
        { key: "6m", label: "6 Monate" },
        { key: "1m", label: "Letzter Monat" },
      ];
      document.getElementById("view-description").innerHTML = `
        <div class="period-filter">
          ${periods.map(p => `<button class="period-btn ${p.key === period ? 'active' : ''}" data-period="${p.key}">${p.label}</button>`).join("")}
        </div>
        <span style="color:var(--text-muted)">Messwerte außerhalb des Normbereichs – klick auf eine Zeile für den Verlauf.</span>
      `;
      document.querySelectorAll(".period-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          state.pathPeriod = btn.dataset.period;
          localStorage.setItem("lab_state", JSON.stringify(state));
          loadView();
        });
      });
      // Bericht-Button
      const reportBtn = document.createElement("a");
      reportBtn.href = `api/bericht/charts?period=${period}&sort=${state.pathSortCol}&dir=${state.pathSortDir}`;
      reportBtn.target = "_blank";
      reportBtn.className = "report-btn";
      reportBtn.textContent = "🖨️ Bericht drucken";
      document.querySelector(".period-filter")?.appendChild(reportBtn);
    } else if (state.view === "vergleich") {
      const res = await fetch("api/vergleich");
      const data = await res.json();
      renderKPIs(null);
      renderChart(null);
      renderVergleich(data);
      document.getElementById("view-description").innerHTML =
        `<div style="display:flex;align-items:center;gap:1rem;">
          <span style="flex:1;color:var(--text-muted)">Zeigt Tests mit signifikanter Veränderung (>5%) gegenüber früheren Werten. Klick auf eine Zeile für den Verlauf.</span>
          <button class="print-btn" onclick="window.print()">🖨️ Drucken</button>
        </div>`;
      // Print-Header befüllen
      const ph = document.querySelector(".print-header");
      if (ph) {
        ph.querySelector("h1").textContent = "Mehrjahresvergleich – Laborwerte";
        const patEl = document.getElementById("patient-name");
        document.getElementById("print-patient").textContent = patEl ? patEl.textContent : "";
        document.getElementById("print-date").textContent = new Date().toLocaleDateString("de-DE");
      }
    } else if (state.view === "favoriten") {
      renderKPIs(null);
      renderChart(null);
      await renderFavoritenDetail();
      document.getElementById("view-description").innerHTML =
        `<span style="color:var(--text-muted)">Deine markierten Laborwerte im Überblick. Klick auf eine Zeile für den Verlauf.</span>`;
      // Print-Header befüllen
      const ph2 = document.querySelector(".print-header");
      if (ph2) {
        ph2.querySelector("h1").textContent = "Favoriten – Laborwerte";
        const patEl2 = document.getElementById("patient-name");
        document.getElementById("print-patient").textContent = patEl2 ? patEl2.textContent : "";
        document.getElementById("print-date").textContent = new Date().toLocaleDateString("de-DE");
      }
    } else if (state.view === "gruppe") {
      const res = await fetch(`api/gruppe/${encodeURIComponent(state.gruppe)}`);
      const data = await res.json();
      renderKPIs(data.kpis, null);
      renderCards(data.tests, "test");
      renderChart(null);
      document.getElementById("view-description").textContent = data.beschreibung || "";
    } else if (state.view === "trend") {
      const res = await fetch(`api/trend/${encodeURIComponent(state.test)}`);
      const data = await res.json();
      renderKPIs(null);
      renderCards(null);
      renderChart(data);
      // Stern-Toggle + Beschreibung + Referenzwerte + Bewertung + Verknüpfungs-Links
      let desc = `<span class="trend-star-row">${starIconHtml(data.test)}</span>`;
      desc += data.beschreibung || "";
      if (data.normbereich) {
        desc += ` Referenzbereich: ${data.normbereich} ${data.einheit || ""}.`;
      }
      // Aktuelle Bewertung basierend auf den letzten Werten
      if (data.bewertung) {
        desc += `<div class="trend-bewertung ${data.bewertung_status}">${data.bewertung}</div>`;
        if (data.bewertung_empfehlung) {
          desc += `<div class="empfehlung-box">💡 ${data.bewertung_empfehlung}</div>`;
        }
      }
      desc += (data.verknuepfungen?.length ? `<br><span class="related-links">Zusammenhänge: ${data.verknuepfungen.map(v => `<a class="related-link" data-vk="${v}">${v}</a>`).join(", ")}</span>` : "");
      document.getElementById("view-description").innerHTML = desc;
      // Stern-Handler für Favoriten-Toggle
      bindStarHandlers(document.getElementById("view-description"));
      // Click-Handler für Verknüpfungs-Links
      document.querySelectorAll(".related-link").forEach(link => {
        link.addEventListener("click", () => navigate("verknuepfung", { verknuepfung: link.dataset.vk }));
      });
    } else if (state.view === "verknuepfung") {
      if (!state.verknuepfung) { navigate("overview"); return; }
      const res = await fetch(`api/verknuepfung/${encodeURIComponent(state.verknuepfung)}`);
      if (!res.ok) { navigate("overview"); return; }
      const data = await res.json();
      renderKPIs(null);
      renderCards(null);
      renderMultiChart(data);
      // Beschreibung oben + Drucken-Button rechts
      let desc = `<div style="display:flex;align-items:center;gap:1rem;">`;
      desc += `<span style="flex:1">${data.beschreibung || ""}</span>`;
      desc += `<button class="print-btn" onclick="window.print()">🖨️ Drucken</button>`;
      desc += `</div>`;
      document.getElementById("view-description").innerHTML = desc;
      // Radar + Empfehlung nebeneinander
      renderRadarWithEmpfehlung(data);
      // Print-Header befüllen
      const ph = document.querySelector(".print-header");
      if (ph) {
        ph.querySelector("h1").textContent = data.name + " – Risikoprofil";
        const patEl = document.getElementById("patient-name");
        document.getElementById("print-patient").textContent = patEl ? patEl.textContent : "";
        document.getElementById("print-date").textContent = new Date().toLocaleDateString("de-DE");
      }
    }
    renderBreadcrumb();
  } catch (err) {
    console.error("Load failed:", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Patient-Name laden
  fetch("api/patient").then(r => r.json()).then(p => {
    const el = document.getElementById("patient-name");
    // if (el && p.vorname) el.textContent = p.vorname + " " + p.nachname;
    el.textContent = "Auswertung"
  }).catch(() => {});
  // Favoriten-Liste vorladen (für Stern-Status in Test-Karten)
  loadFavoritenListe().then(() => loadView());
});
