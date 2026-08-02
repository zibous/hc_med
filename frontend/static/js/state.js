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
  pathPeriod: saved?.pathPeriod || "all",
  pathSortCol: saved?.pathSortCol || "datum",
  pathSortDir: saved?.pathSortDir || -1,
};

export function navigate(view, params = {}) {
  if (view === "trend" && state.view === "pathologisch") {
    state.fromPath = "pathologisch";
  } else if (view !== "trend" && view !== "verknuepfung") {
    state.fromPath = null;
  }
  state.view = view;
  if (view === "verknuepfung") {
    // Gruppe und Test beibehalten für Zurück-Navigation
    state.verknuepfung = params.verknuepfung || null;
  } else {
    state.gruppe = params.gruppe || null;
    state.test = params.test || null;
    state.verknuepfung = params.verknuepfung || null;
  }
  localStorage.setItem("lab_state", JSON.stringify(state));
  loadView();
}
