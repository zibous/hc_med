// state.js – Navigation State
import { loadView } from "./main.js";

// State aus localStorage wiederherstellen
const saved = JSON.parse(localStorage.getItem("lab_state") || "null");

export const state = {
  view: saved?.view || "overview",
  gruppe: saved?.gruppe || null,
  test: saved?.test || null,
  fromPath: saved?.fromPath || null,
  verknuepfung: saved?.verknuepfung || null,
  pathPeriod: saved?.pathPeriod || "2",
  pathSortCol: saved?.pathSortCol || "datum",
  pathSortDir: saved?.pathSortDir || -1,
};

export function navigate(view, params = {}) {
  if (view === "trend" && state.view === "pathologisch") {
    state.fromPath = "pathologisch";
  } else if (view === "trend" && state.view === "vergleich") {
    state.fromPath = "vergleich";
  } else if (view === "trend" && state.view === "favoriten") {
    state.fromPath = "favoriten";
  } else if (view !== "trend" && view !== "verknuepfung") {
    state.fromPath = null;
  }
  state.view = view;
  if (view === "verknuepfung") {
    state.verknuepfung = params.verknuepfung || null;
  } else {
    state.gruppe = params.gruppe || null;
    state.test = params.test || null;
    state.verknuepfung = params.verknuepfung || null;
  }
  localStorage.setItem("lab_state", JSON.stringify(state));
  // Browser-History aktualisieren (ermöglicht Zurück-Button)
  const histState = { view: state.view, gruppe: state.gruppe, test: state.test, verknuepfung: state.verknuepfung, fromPath: state.fromPath };
  history.pushState(histState, "", `#${view}${state.test ? '/' + state.test : state.gruppe ? '/' + state.gruppe : ''}`);
  loadView();
}

// Browser Zurück-Button abfangen
window.addEventListener("popstate", (e) => {
  if (e.state) {
    state.view = e.state.view || "overview";
    state.gruppe = e.state.gruppe || null;
    state.test = e.state.test || null;
    state.verknuepfung = e.state.verknuepfung || null;
    state.fromPath = e.state.fromPath || null;
  } else {
    state.view = "overview";
    state.gruppe = null;
    state.test = null;
    state.verknuepfung = null;
    state.fromPath = null;
  }
  localStorage.setItem("lab_state", JSON.stringify(state));
  loadView();
});
