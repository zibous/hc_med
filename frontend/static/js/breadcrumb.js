// breadcrumb.js – Navigation Breadcrumb
import { state, navigate } from "./state.js";

export function renderBreadcrumb() {
  const el = document.getElementById("breadcrumb");
  const crumbs = [{ label: "🏠 Übersicht", view: "overview" }];

  if (state.view === "pathologisch") {
    crumbs.push({ label: "⚠️ Auffällige Werte", view: "pathologisch" });
  }
  if (state.view === "vergleich") {
    crumbs.push({ label: "📊 Mehrjahresvergleich", view: "vergleich" });
  }
  if (state.view === "favoriten") {
    crumbs.push({ label: "⭐ Favoriten", view: "favoriten" });
  }
  if (state.view === "trend" && state.fromPath === "pathologisch") {
    crumbs.push({ label: "⚠️ Auffällige Werte", view: "pathologisch" });
  }
  if (state.view === "trend" && state.fromPath === "vergleich") {
    crumbs.push({ label: "📊 Mehrjahresvergleich", view: "vergleich" });
  }
  if (state.view === "trend" && state.fromPath === "favoriten") {
    crumbs.push({ label: "⭐ Favoriten", view: "favoriten" });
  }
  if (state.gruppe && state.view !== "pathologisch") {
    crumbs.push({ label: state.gruppe, view: "gruppe", params: { gruppe: state.gruppe } });
  }
  if (state.test && (state.view === "trend" || state.view === "verknuepfung")) {
    crumbs.push({ label: state.test, view: "trend", params: { test: state.test, gruppe: state.gruppe } });
  }
  if (state.view === "verknuepfung" && state.verknuepfung) {
    crumbs.push({ label: "🔗 " + state.verknuepfung, view: "verknuepfung", params: { verknuepfung: state.verknuepfung } });
  }

  el.innerHTML = crumbs.map((c, i) => {
    const isActive = i === crumbs.length - 1;
    const sep = i < crumbs.length - 1 ? `<span class="crumb-sep">→</span>` : "";
    return `<span class="crumb ${isActive ? "active" : ""}" data-idx="${i}">${c.label}</span>${sep}`;
  }).join("");

  el.querySelectorAll(".crumb").forEach((crumb, i) => {
    crumb.addEventListener("click", () => {
      const target = crumbs[i];
      navigate(target.view, target.params || {});
    });
  });
}
