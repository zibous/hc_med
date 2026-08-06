// alle-tests.js – Alle Tests als sortierbare Tabelle mit Jahres-Bereich-Filter
import { state, navigate } from "./state.js";
import { renderNormBar } from "./norm-bar.js";

/**
 * Rendert die "Alle Tests"-Ansicht als Tabelle mit Von/Bis-Jahr-Dropdowns.
 */
export async function renderAlleTests() {
  const el = document.getElementById("cards");
  el.style.display = "block";

  const von = state.alleTestsVon || "";
  const bis = state.alleTestsBis || "";

  try {
    let url = "api/alle-tests";
    const params = [];
    if (von) params.push(`von=${von}`);
    if (bis) params.push(`bis=${bis}`);
    if (params.length) url += "?" + params.join("&");

    const res = await fetch(url);
    if (!res.ok) { el.innerHTML = "<p>Fehler beim Laden.</p>"; return; }
    const data = await res.json();
    const tests = data.tests || [];
    const jahre = data.verfuegbare_jahre || [];

    // Jahre für Filter speichern (main.js braucht sie)
    window._alleTestsJahre = jahre;

    if (tests.length === 0) {
      el.innerHTML = `<div class="path-list">
        <div class="card-title" style="margin-bottom:1.2rem; font-size:1.8rem;">📋 Alle Tests</div>
        <p style="color:var(--text-muted)">Keine Daten für diesen Zeitraum.</p>
      </div>`;
      return;
    }

    let sortCol = state.alleTestsSortCol || "gruppe";
    let sortDir = state.alleTestsSortDir || 1;

    function renderTable(items, col, dir) {
      const sorted = [...items].sort((a, b) => {
        let va = a[col] || "", vb = b[col] || "";
        if (col === "wert") {
          va = parseFloat(String(va).replace(/[<>,]/g, "").replace(",", ".")) || 0;
          vb = parseFloat(String(vb).replace(/[<>,]/g, "").replace(",", ".")) || 0;
        }
        if (col === "messungen") {
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

        return `<tr class="path-row" data-test="${f.test}" data-gruppe="${f.gruppe}">
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
          <div class="card-title" style="font-size:1.8rem;">📋 Alle Tests (${sorted.length})</div>
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
          state.alleTestsSortCol = sortCol;
          state.alleTestsSortDir = sortDir;
          localStorage.setItem("lab_state", JSON.stringify(state));
          renderTable(items, sortCol, sortDir);
        });
      });

      // Row-Click → Trend
      el.querySelectorAll(".path-row").forEach(row => {
        row.style.cursor = "pointer";
        row.addEventListener("click", () => {
          navigate("trend", { test: row.dataset.test, gruppe: row.dataset.gruppe });
        });
      });
    }

    renderTable(tests, sortCol, sortDir);

  } catch (err) {
    console.error("Alle-Tests Fehler:", err);
    el.innerHTML = "<p>Fehler beim Laden.</p>";
  }
}
