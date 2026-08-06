// favoriten.js – Favoriten-Verwaltung (Stern-Toggle + Favoriten-Karte)
import { navigate } from "./state.js";
import { renderNormBar } from "./norm-bar.js";

// Cache der Favoriten-Liste (Testnamen)
let favoritenCache = null;

/**
 * Lädt die Favoriten-Liste vom Server (nur Testnamen).
 */
export async function loadFavoritenListe() {
  try {
    const res = await fetch("api/favoriten/liste");
    const data = await res.json();
    favoritenCache = data.favoriten || [];
  } catch {
    favoritenCache = [];
  }
  return favoritenCache;
}

/**
 * Prüft ob ein Test ein Favorit ist.
 */
export function isFavorit(test) {
  return (favoritenCache || []).includes(test);
}

/**
 * Toggle: Favorit hinzufügen oder entfernen.
 */
export async function toggleFavorit(test) {
  const isFav = isFavorit(test);
  const method = isFav ? "DELETE" : "POST";
  try {
    const res = await fetch(`api/favoriten/${encodeURIComponent(test)}`, { method });
    const data = await res.json();
    favoritenCache = data.favoriten || [];
  } catch {
    // Fallback: lokaler Toggle
    if (isFav) {
      favoritenCache = favoritenCache.filter(f => f !== test);
    } else {
      favoritenCache = [...(favoritenCache || []), test];
    }
  }
  return favoritenCache;
}

/**
 * Erzeugt den SVG-Stern-Button als HTML-String.
 */
export function starIconHtml(test) {
  const active = isFavorit(test);
  return `<button class="fav-star ${active ? "active" : ""}" data-test="${test}" title="${active ? "Favorit entfernen" : "Als Favorit merken"}" aria-label="Favorit">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="${active ? "var(--orange)" : "none"}" stroke="${active ? "var(--orange)" : "var(--text-muted)"}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  </button>`;
}

/**
 * Registriert Click-Handler für alle Stern-Buttons im Container.
 */
export function bindStarHandlers(container) {
  container.querySelectorAll(".fav-star").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation(); // Kein Drilldown beim Star-Klick
      const test = btn.dataset.test;
      await toggleFavorit(test);
      // Stern-Darstellung aktualisieren
      const active = isFavorit(test);
      btn.classList.toggle("active", active);
      btn.title = active ? "Favorit entfernen" : "Als Favorit merken";
      const svg = btn.querySelector("svg");
      const poly = svg.querySelector("polygon");
      poly.setAttribute("fill", active ? "var(--orange)" : "none");
      poly.setAttribute("stroke", active ? "var(--orange)" : "var(--text-muted)");
      // Favoriten-Karte auf Overview aktualisieren (falls sichtbar)
      updateFavoritenKarte();
    });
  });
}

/**
 * Rendert die Favoriten-Karte auf der Startseite.
 */
export async function renderFavoritenKarte() {
  // Bestehende Karte entfernen
  const existing = document.getElementById("favoriten-karte");
  if (existing) existing.remove();

  try {
    const res = await fetch("api/favoriten");
    if (!res.ok) return;
    const data = await res.json();
    const favs = data.favoriten || [];

    if (favs.length === 0) return;

    const kpisEl = document.getElementById("kpis");
    if (!kpisEl) return;

    const karte = document.createElement("div");
    karte.id = "favoriten-karte";
    karte.className = "favoriten-karte";

    const items = favs.map(f => {
      const flagClass = f.flag === "H" ? "high" : f.flag === "L" ? "low" : "";
      const flagIcon = f.flag === "H" ? " ↑" : f.flag === "L" ? " ↓" : "";
      return `<div class="fav-item ${flagClass}" data-test="${f.test}" data-gruppe="">
        <span class="fav-test">${f.test}</span>
        <span class="fav-wert ${flagClass}">${f.wert}${flagIcon}</span>
        <span class="fav-einheit">${f.einheit}</span>
      </div>`;
    }).join("");

    karte.innerHTML = `
      <div class="fav-karte-header">
        <span class="fav-karte-title">⭐ Favoriten</span>
        <span class="fav-karte-count">${favs.length} Tests · Klick für Details →</span>
      </div>
      <div class="fav-items">${items}</div>
    `;

    // Nach den KPIs einfügen
    kpisEl.insertAdjacentElement("afterend", karte);

    // Klick auf die ganze Karte → Favoriten-Listen-View
    karte.style.cursor = "pointer";
    karte.addEventListener("click", () => {
      navigate("favoriten", {});
    });
  } catch (err) {
    console.error("Favoriten-Karte Fehler:", err);
  }
}

/**
 * Aktualisiert die Favoriten-Karte (nach Toggle).
 */
async function updateFavoritenKarte() {
  await renderFavoritenKarte();
}

/**
 * Rendert die Favoriten-Detailansicht als Tabelle (wie Auffällige Tests).
 */
export async function renderFavoritenDetail() {
  const el = document.getElementById("cards");
  el.style.display = "block";

  try {
    const res = await fetch("api/favoriten/detail");
    if (!res.ok) { el.innerHTML = "<p>Fehler beim Laden der Favoriten.</p>"; return; }
    const data = await res.json();
    const favs = data.favoriten || [];

    if (favs.length === 0) {
      el.innerHTML = `<div class="path-list">
        <div class="card-title" style="margin-bottom:1.2rem; font-size:1.8rem;">⭐ Favoriten</div>
        <p style="color:var(--text-muted)">Keine Favoriten gespeichert. Markiere Tests mit dem ⭐ in der Gruppen-Ansicht.</p>
      </div>`;
      return;
    }

    let sortCol = "gruppe";
    let sortDir = 1;

    function renderTable(items, col, dir) {
      const sorted = [...items].sort((a, b) => {
        let va = a[col] || "", vb = b[col] || "";
        if (col === "wert") {
          va = parseFloat(String(va).replace(/[<>,]/g, "").replace(",", ".")) || 0;
          vb = parseFloat(String(vb).replace(/[<>,]/g, "").replace(",", ".")) || 0;
        }
        if (col === "messungen" || col === "pathologisch") {
          va = a[col] || 0; vb = b[col] || 0;
        }
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
      });

      const arrow = (c) => c === col ? `<span class="sort-arrow">${dir === 1 ? '▲' : '▼'}</span>` : '';

      const rows = sorted.map(f => {
        const flagClass = f.flag === "H" ? "high" : f.flag === "L" ? "low" : "";
        const flagIcon = f.flag === "H" ? "↑ hoch" : f.flag === "L" ? "↓ tief" : "✓ OK";
        const flagPill = f.flag
          ? `<span class="flag-pill ${flagClass}">${flagIcon}</span>`
          : `<span class="flag-pill ok">${flagIcon}</span>`;
        const trendColor = f.trend.startsWith("↑") ? "var(--red)" : f.trend.startsWith("↓") ? "var(--green)" : "var(--text-muted)";

        return `<tr class="fav-detail-row" data-test="${f.test}" data-gruppe="${f.gruppe}">
          <td><span style="color:var(--text-muted)">${f.gruppe}</span></td>
          <td><strong>${f.test}</strong>${f.kurzname ? `<br><span class="card-kurzname">${f.kurzname}</span>` : ""}</td>
          <td class="${flagClass}" style="font-size:1.4rem"><strong>${f.wert}</strong> ${f.einheit}</td>
          <td>${renderNormBar(f.wert, f.normbereich, f.flag) || `<span style="color:var(--text-muted)">${f.normbereich || "–"}</span>`}</td>
          <td>${flagPill}</td>
          <td style="color:${trendColor}">${f.trend || "–"}</td>
          <td style="color:var(--text-muted)">${f.vorwert ? f.vorwert + " " + f.einheit : "–"}</td>
          <td style="color:var(--text-muted)">${f.datum}</td>
          <td style="color:var(--text-muted)">${f.messungen}</td>
        </tr>`;
      }).join("");

      el.innerHTML = `<div class="path-list">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem;">
          <div class="card-title" style="font-size:1.8rem;">⭐ Favoriten (${sorted.length} Tests)</div>
          <button class="print-btn" onclick="window.print()">🖨️ Drucken</button>
        </div>
        <table class="path-table">
          <thead><tr>
            <th data-col="gruppe">Gruppe${arrow('gruppe')}</th>
            <th data-col="test">Test${arrow('test')}</th>
            <th data-col="wert">Aktuell${arrow('wert')}</th>
            <th>Norm</th>
            <th data-col="flag">Status${arrow('flag')}</th>
            <th data-col="trend">Trend${arrow('trend')}</th>
            <th>Vorwert</th>
            <th data-col="datum">Datum${arrow('datum')}</th>
            <th data-col="messungen">Messungen${arrow('messungen')}</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;

      // Sort-Handler
      el.querySelectorAll("th[data-col]").forEach(th => {
        th.style.cursor = "pointer";
        th.addEventListener("click", () => {
          const newCol = th.dataset.col;
          if (newCol === sortCol) { sortDir *= -1; } else { sortCol = newCol; sortDir = 1; }
          renderTable(items, sortCol, sortDir);
        });
      });

      // Row-Click → Trend
      el.querySelectorAll(".fav-detail-row").forEach(row => {
        row.style.cursor = "pointer";
        row.addEventListener("click", () => {
          navigate("trend", { test: row.dataset.test, gruppe: row.dataset.gruppe });
        });
      });
    }

    renderTable(favs, sortCol, sortDir);

  } catch (err) {
    console.error("Favoriten-Detail Fehler:", err);
    el.innerHTML = "<p>Fehler beim Laden.</p>";
  }
}
