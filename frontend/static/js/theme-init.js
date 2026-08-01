// theme-init.js – Inline Theme-Logik (läuft vor DOM-ready)
// ========================================================

// 1. THEME-ZUSTAND STEUERN (Läuft sofort inline für flackerfreien Start)
function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);

  // Synchronisation für alle Dashboards im Projekt (health-theme)
  localStorage.setItem('health-theme', theme);

  // Text im Footer aktualisieren, falls er im DOM bereits existiert
  const footerBtn = document.getElementById('themeToggleFooter');
  if (footerBtn) {
    footerBtn.innerHTML = theme === 'dark' ? '☀️ Helles Design' : '🌙 Dunkles Design';
  }

  window.dispatchEvent(new CustomEvent('themeChanged', { detail: theme }));
}

// Theme beim Start sofort setzen (Prüft 'theme', 'health-theme' oder System-Präferenz)
const savedTheme = localStorage.getItem('theme') || localStorage.getItem('health-theme');
const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

if (savedTheme) {
  setTheme(savedTheme);
} else {
  setTheme(systemPrefersDark ? 'dark' : 'light');
}

// 2. EVENT-DELEGATION (Fängt den Klick ab, sobald das Element im Footer existiert)
document.addEventListener('click', function(event) {
  if (event.target && event.target.id === 'themeToggleFooter') {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
  }
});

// 3. TEXT-ABGLEICH NACH LADEN (Stellt den korrekten Text im Footer beim ersten Laden ein)
document.addEventListener('DOMContentLoaded', function() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const footerBtn = document.getElementById('themeToggleFooter');
  if (footerBtn) {
    footerBtn.innerHTML = currentTheme === 'dark' ? '☀️ Helles Design' : '🌙 Dunkles Design';
  }

  // Optional: Aktuelles Jahr im Footer setzen falls benötigt
  const cy = document.getElementById('currentYear');
  if (cy) cy.textContent = new Date().getFullYear();
});
