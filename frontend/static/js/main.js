// main.js – Einstiegspunkt Labor Dashboard
import { state, navigate } from "./state.js";
import { renderKPIs } from "./kpis.js";
import { renderCards } from "./cards.js";
import { renderChart, renderMultiChart } from "./trend-chart.js";
import { renderBreadcrumb } from "./breadcrumb.js";

export async function loadView() {
  try {
    if (state.view === "overview") {
      const res = await fetch("api/overview");
      const data = await res.json();
      renderKPIs(data.kpis, data.gruppen);
      renderCards(data.gruppen);
      renderChart(null);
      document.getElementById("view-description").textContent = "";
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
      // Beschreibung + Referenzwerte + Bewertung + Verknüpfungs-Links
      let desc = data.beschreibung || "";
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
      let desc = data.beschreibung || "";
      if (data.empfehlung) {
        desc += `<div class="empfehlung-box">💡 <strong>Empfehlung:</strong> ${data.empfehlung}</div>`;
      }
      document.getElementById("view-description").innerHTML = desc;
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
    if (el && p.vorname) el.textContent = p.vorname + " " + p.nachname;
  }).catch(() => {});
  loadView();
});
