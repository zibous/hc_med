# hc_med – Laborwerte Dashboard

Langzeit-Verlaufsanalyse von Laborwerten (2013–2026) mit automatischer Extraktion aus verschiedenen Befund-Formaten, SQLite-Datenbank, interaktivem Web-Dashboard und druckbarem Arztbericht.

## Übersicht

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         hc_med – Architektur                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────────────┐   │
│  │  Befund-TXT  │────▶│  Parser      │────▶│  SQLite (labor.db)     │   │
│  │  PDF → Text  │     │  7 Formate   │     │  1300+ Messwerte       │   │
│  │  hc_scale DB │     │  Validierung │     │  Normalisiert          │   │
│  └──────────────┘     └──────────────┘     └───────────┬────────────┘   │
│                                                         │               │
│                                                         ▼               │
│                              ┌───────────────────────────────────┐      │
│                              │  FastAPI Backend (Port 5065)      │      │
│                              │  8 Router-Module (je <150 Zeilen) │      │
│                              │  Bewertung + Empfehlungen (Core)  │      │
│                              └───────────────┬───────────────────┘      │
│                                              │                          │
│                                              ▼                          │
│                              ┌───────────────────────────────────┐      │
│                              │  Frontend (Chart.js + ES6)        │      │
│                              │  Übersicht → Gruppe → Trend       │      │
│                              │  Verknüpfungen · Arztbericht      │      │
│                              └───────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Datenverarbeitung – Pipeline

```
  data/befunde/*.txt + hc_scale DB
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  1. FORMAT-ERKENNUNG (7 Formate automatisch)          │
│  2. PARSING (pro Format ein Parser)                   │
│  3. NORMALISIERUNG (Testnamen, Einheiten, rel/abs)    │
│  4. VALIDIERUNG (Plausibilitäts-Ranges)               │
│  5. AUSGABE → SQLite + CSV                            │
└───────────────────────────────────────────────────────┘
```

## App-Architektur (Clean Architecture)

```
app/
├── main.py                      # FastAPI App, Logging, Lifespan, Router-Registry
├── api/                         # Router (je ein Endpoint-Bereich)
│   ├── overview.py              (84 Z.)  /overview
│   ├── gruppe.py                (66 Z.)  /gruppe/{name}
│   ├── trend.py                 (70 Z.)  /trend/{test}
│   ├── verknuepfung.py          (56 Z.)  /verknuepfungen, /verknuepfung/{name}
│   ├── pathologisch.py          (77 Z.)  /pathologisch
│   ├── bericht.py               (137 Z.) /bericht, /bericht/charts
│   ├── kpidata.py               (52 Z.)  /kpidata (für dbo)
│   └── tests_router.py          (20 Z.)  /tests
├── config/
│   └── settings.py              (18 Z.)  YAML-Config laden
├── core/                        # Business Logic
│   ├── bewertung.py             (75 Z.)  Bewertungslogik (Texte aus YAML)
│   └── empfehlungen.py          (233 Z.) Empfehlungslogik (Verknüpfungen)
└── infrastructure/
    └── database.py              (18 Z.)  SQLite-Zugriff
```

## Projektstruktur (komplett)

```
hc_med/
├── app/                         # Backend (FastAPI)
├── frontend/
│   ├── templates/
│   │   ├── index.html           # Dashboard SPA-Shell
│   │   ├── bericht_charts.html  # Arztbericht mit Charts (Jinja2)
│   │   └── bericht_tabelle.html # Arztbericht Tabellen (Jinja2)
│   └── static/
│       ├── css/
│       │   ├── theme.css        # Shared HomeApps Theme (Dark/Light)
│       │   └── style.css        # App-spezifisch
│       └── js/
│           ├── main.js          # Entry, View-Routing, API-Calls
│           ├── state.js         # Navigation State (localStorage)
│           ├── kpis.js          # KPI-Kacheln
│           ├── cards.js         # Gruppen/Test-Karten + Tabelle
│           ├── trend-chart.js   # Trend + Multi-Chart (Chart.js)
│           ├── breadcrumb.js    # Drill-down Navigation
│           └── theme-init.js    # Dark/Light Toggle
├── scripts/
│   ├── extract_labvalues.py     # Parser (7 Formate + Normalisierung)
│   ├── labor_db.py              # SQLite DB-Modul (Schema, Import)
│   ├── import_scale.py          # Körperdaten aus hc_scale
│   └── validate_labor.py        # Plausibilitätsprüfung
├── data/
│   ├── labor.db                 # SQLite Datenbank (generiert)
│   ├── labor_config.yaml        # Zentrale Config (Gruppen, Tests, Empfehlungen)
│   └── befunde/                 # Quelldateien (*.txt)
├── docs/
│   └── nginx_hc_med.conf        # Nginx Config (Auth + Proxy)
├── Dockerfile                   # python:3.12-slim, Port 5065
├── docker-compose.yml           # Host 8065 → Container 5065
├── Makefile                     # dev, labor-reset, jsbuild...
└── requirements.txt             # fastapi, uvicorn, jinja2, pyyaml
```

## Konfiguration (data/labor_config.yaml)

Zentrale Konfig-Datei – alle Texte, Beschreibungen und Empfehlungen:

```yaml
patient:                    # Stammdaten
gruppen:                    # Gruppen-Icons, Farben, Beschreibungen
tests:                      # Test-Beschreibungen (Alter/Geschlecht-Kontext)
ereignisse:                 # KH-Aufenthalte (Marker im Chart)
verknuepfungen:             # Zusammenhänge zwischen Tests
empfehlungen_tests:         # Test-spezifische Empfehlungen
bewertungen:                # Bewertungstexte (Gruppe + Trend)
```

## Dashboard – Navigation

```
ÜBERSICHT (KPIs + Gruppen sortiert nach Status)
    │
    ├── Klick Gruppe ──▶ GRUPPEN-DETAIL (Tests mit Sparklines, Bewertung)
    │       │
    │       └── Klick Test ──▶ TREND-CHART (Norm-Band, Marker, Empfehlung)
    │               │
    │               └── Klick Zusammenhang ──▶ MULTI-CHART (mehrere Tests)
    │
    ├── Klick "Auffällige Werte" ──▶ TABELLE (sortierbar, filterbar)
    │       │
    │       └── Klick Zeile ──▶ TREND-CHART
    │
    └── Klick "Bericht drucken" ──▶ ARZTBERICHT (HTML/PDF mit Charts)
```

## Features

- **7 Befund-Formate** automatisch erkannt und geparst
- **Körperdaten** aus Mi Scale Waage (hc_scale Integration)
- **Normalisierung** (Testnamen, Einheiten, HbA1c NGSP/IFCC)
- **Validierung** mit medizinischen Plausibilitäts-Ranges
- **Bewertung** aktuell (letzte 5 Werte) + historisch
- **Alters-/Geschlechtskontext** in allen Beschreibungen (Mann, 70+)
- **Verknüpfungen** mit Multi-Charts und personalisierten Empfehlungen
- **Krankenhaus-Marker** im Verlaufs-Chart
- **Druckbarer Arztbericht** (PDF via Browser-Druckdialog)
- **KPI-Integration** ins übergeordnete DBO-Dashboard
- **Dark/Light Theme** (shared mit allen HomeApps Dashboards)
- **State-Persistenz** (Refresh behält aktuelle View)
- **Nginx Auth** (extern: Basic Auth, LAN: offen, DBO: offen)

## Makefile-Befehle

```bash
# Server
make dev              # Uvicorn starten (Port 5065, --reload)
make up               # Docker Container starten
make restart          # Docker Container neustarten

# Daten
make labor-reset      # DB löschen + Befunde parsen + Scale-Import + Validierung
make labor-validate   # Nur Plausibilitätsprüfung
make labor-trend TEST=CRP  # Trend im Terminal

# Build
make jsbuild          # JS/CSS bundeln (esbuild via Docker)
make jsclean          # Bundles entfernen

# Git
make git-update       # Commit + Push zu Forgejo
```

## Neue Befunde hinzufügen

1. Textdatei in `data/befunde/` ablegen (Format: `YYYY-MM-DD_laborbefund_quelle.txt`)
2. Auf dem Server: `make labor-reset`
3. Dashboard zeigt neue Werte automatisch

## Nginx (extern + Auth)

```bash
# Passwort-Datei erstellen
printf "%s\n%s\n" \
  "peter:$(openssl passwd -apr1 'passwort1')" \
  "reni:$(openssl passwd -apr1 'passwort2')" \
  | sudo tee nginx/includes/.htpasswd_hcmed

# Config: siehe docs/nginx_hc_med.conf
# LAN (10.1.1.x): kein Login
# Extern: Basic Auth
# /api/kpidata: immer offen (für DBO)
```

## Technologie

- **Backend**: Python 3.12, FastAPI, SQLite, Jinja2, PyYAML
- **Frontend**: Vanilla JS (ES6 Modules), Chart.js, CSS Custom Properties
- **Theme**: HomeApps Unified Theme (Dark/Light)
- **Deploy**: Docker oder direkt Uvicorn, Nginx Reverse-Proxy
- **Daten**: hc_scale (Waage), Laborbefund-Textdateien (7 Formate)
