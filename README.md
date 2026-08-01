# hc_med – Laborwerte Dashboard

Langzeit-Verlaufsanalyse von Laborwerten (2013–2026) mit automatischer Extraktion aus verschiedenen Befund-Formaten, SQLite-Datenbank und interaktivem Web-Dashboard.

## Übersicht

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         hc_med – Architektur                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────────────┐   │
│  │  Befund-TXT  │────▶│  Parser      │────▶│  SQLite (labor.db)     │   │
│  │  PDF → Text  │     │  6 Formate   │     │  629+ Messwerte        │   │
│  │  OCR-Scans   │     │  Validierung │     │  Normalisiert          │   │
│  └──────────────┘     └──────────────┘     └───────────┬────────────┘   │
│                                                         │               │
│                                                         ▼               │
│                              ┌───────────────────────────────────┐      │
│                              │  FastAPI Backend (Port 5065)      │      │
│                              │  /api/overview                    │      │
│                              │  /api/gruppe/{name}               │      │
│                              │  /api/trend/{test}                │      │
│                              │  /api/verknuepfung/{name}         │      │
│                              │  /api/pathologisch                │      │
│                              │  /api/kpidata                     │      │
│                              └───────────────┬───────────────────┘      │
│                                              │                          │
│                                              ▼                          │
│                              ┌───────────────────────────────────┐      │
│                              │  Frontend (Chart.js + ES6)        │      │
│                              │  Übersicht → Gruppe → Trend       │      │
│                              │  Verknüpfungen (Multi-Chart)      │      │
│                              │  Auffällige Werte (sortierbar)    │      │
│                              └───────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Datenverarbeitung – Pipeline

```
  data/befunde/*.txt
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  1. FORMAT-ERKENNUNG (detect_format)                  │
│                                                       │
│  "Laborbefund vom..."  ──▶  freetext                  │
│  "Parameter;Einheit;Referenz;18.10.13..."  ──▶ pivot  │
│  "Tag;Test;Norm;..."  ──▶  csv                        │
│  "Test  Norm  Erst-Wert..."  ──▶  table               │
│  Tab + "Kürzel  Bezeichnung"  ──▶  tab                │
│  "Kürzel Bezeichnung" (Spaces)  ──▶  kuerzel_space    │
│  "Analyse  Ergebnis  Einheit"  ──▶  pdf_text          │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  2. PARSING (pro Format ein Parser)                   │
│                                                       │
│  Ergebnis pro Zeile:                                  │
│  { Datum, Test, Wert, Einheit, Normbereich, Flag }    │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  3. NORMALISIERUNG                                    │
│                                                       │
│  ┌─ Testname ─────────────────────────────────────┐   │
│  │  "GOT (ASAT)" / "AST(GOT)" / "ASAT"  →  "GOT"  │   │
│  │  "HB" / "Hämoglobin" / "HGB"  →  "Hämoglobin"  │   │
│  │  Längster Match zuerst (spezifisch vor allg.)  │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  ┌─ Einheiten ────────────────────────────────────┐   │
│  │  g/L_ → g/dL (÷10)  für Hämoglobin             │   │
│  │  L/L  → %    (×100)  für Hämatokrit            │   │
│  │  KU/l → U/L  (×1000) für Cholinesterase        │   │
│  │  G/L  → 10^9/L       für Leukozyten            │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  ┌─ Korrekturen ──────────────────────────────────┐   │
│  │  rel/abs Zuordnung anhand Einheit (% vs G/L)   │   │
│  │  HbA1c >15 → HbA1c (IFCC) mmol/mol             │   │
│  │  Hämoglobin pg → MCH                           │   │
│  │  Nicht-numerische Artefakte ("1)") → filtern   │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  ┌─ Metadaten ────────────────────────────────────┐   │
│  │  Gruppe zuordnen (Blutbild, Niere, Lipide...)  │   │
│  │  Alter zum Messzeitpunkt berechnen             │   │
│  └────────────────────────────────────────────────┘   │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  4. VALIDIERUNG (validate_labor.py)                   │
│                                                       │
│  • Plausibilitäts-Ranges pro Test (min/max)           │
│  • Erkennung nicht-numerischer Werte                  │
│  • Report: ✅ Plausibel / ❌ Außerhalb / ⚠️ Fehler     │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  5. AUSGABE                                           │
│                                                       │
│  ┌─ SQLite DB (data/labor.db) ────────────────────┐   │
│  │  patienten: Stammdaten                         │   │
│  │  befunde: Quelldateien + Import-Metadaten      │   │
│  │  laborwerte: Normalisierte Messwerte           │   │
│  │  Views: v_zeitreihe, v_aktuell, v_pathologisch │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  ┌─ CSV (data/befunde/laborwerte_gesamt.csv) ─────┐   │
│  │  Semikolon-getrennt, für Excel/Numbers         │   │
│  └────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────┘
```

## Dashboard – Navigation

```
┌─────────────────────────────────────────────────┐
│  ÜBERSICHT                                      │
│  KPIs: Messwerte | Befunde | Auffällig | Zeitr. │
│  Handlungsbedarf: [Klickbare Gruppen]           │
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │🩸Blutbild│  │🔥Entzünd│  │💧 Niere │  ...     │
│  │ Status  │  │ Status  │  │ Status  │          │
│  │Sparkline│  │Sparkline│  │Sparkline│          │
│  └────┬────┘  └────┬────┘  └────┬────┘          │
└───────┼─────────────┼───────────┼───────────────┘
        │             │           │
        ▼             ▼           ▼
┌─────────────────────────────────────────────────┐
│  GRUPPE (z.B. Niere)                            │
│  Beschreibung + KPIs (OK/Auffällig/Einschätzung)│
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Kreatinin │  │  GFR     │  │Harnstoff │       │
│  │ 1.12     │  │  66      │  │  34      │       │
│  │▶ Trend   │  │▶ Trend   │  │ 4 Werte  │       │
│  └────┬─────┘  └────┬─────┘  └──────────┘       │
└───────┼──────────────┼──────────────────────────┘
        │              │    (< 5 Messungen:
        ▼              ▼     inline-Anzeige)
┌─────────────────────────────────────────────────┐
│  TREND-CHART (z.B. GFR)                         │
│  Beschreibung + Referenzbereich                 │
│  Zusammenhänge: [Nierenfunktion]                │
│                                                 │
│  ┌─────────────────────────────────────┐        │
│  │  Chart (Line + Norm-Band + Marker)  │        │
│  │  ████████████████████████████████   │        │
│  │  ─ ─ ─ Norm oben ─ ─ ─ ─ ─ ─ ─      │        │
│  │  ─ ─ ─ Norm unten ─ ─ ─ ─ ─ ─       │        │
│  │  ▬▬▬ KH-Aufenthalt (rot, unten)     │        │
│  └─────────────────────────────────────┘        │
│  Min | Max | Durchschnitt | Aktuell | Trend     │
└─────────────────────────────────────────────────┘
        │
        ▼ (Klick "Zusammenhänge")
┌─────────────────────────────────────────────────┐
│  MULTI-CHART (z.B. Nierenfunktion)              │
│  GFR + Kreatinin + Harnstoff übereinander       │
│  Gemeinsame Zeitachse, Legende, 2 Y-Achsen      │
└─────────────────────────────────────────────────┘
```

## Projektstruktur

```
hc_med/
├── app/
│   ├── main.py                  # FastAPI App + Logging + Lifespan
│   └── api/
│       └── labor.py             # REST-Endpunkte (Overview, Trend, Verknüpfung...)
├── frontend/
│   ├── templates/
│   │   └── index.html           # SPA-Shell
│   └── static/
│       ├── css/
│       │   ├── theme.css        # Shared HomeApps Theme (Dark/Light)
│       │   └── style.css        # App-spezifisch
│       └── js/
│           ├── main.js          # Entry, View-Routing, API-Calls
│           ├── state.js         # Navigation State (localStorage)
│           ├── kpis.js          # KPI-Kacheln
│           ├── cards.js         # Gruppen/Test-Karten + Pathologisch-Tabelle
│           ├── trend-chart.js   # Trend-Chart + Multi-Chart (Chart.js)
│           ├── breadcrumb.js    # Drill-down Navigation
│           └── theme-init.js    # Dark/Light Toggle
├── scripts/
│   ├── extract_labvalues.py     # Haupt-Parser (6 Formate + Normalisierung)
│   ├── labor_db.py              # SQLite DB-Modul (Schema, Import, Export)
│   └── validate_labor.py        # Plausibilitätsprüfung
├── data/
│   ├── labor.db                 # SQLite Datenbank (generiert)
│   ├── labor_config.yaml        # Gruppen, Tests, Ereignisse, Verknüpfungen
│   └── befunde/                 # Quelldateien (*.txt, *.pdf)
├── docs/
│   └── nginx_hc_med.conf        # Nginx Reverse-Proxy Config
├── Dockerfile                   # python:3.12-slim, Port 5065
├── docker-compose.yml           # Host 8065 → Container 5065
├── Makefile                     # dev, labor-reset, labor-validate, jsbuild...
└── requirements.txt             # fastapi, uvicorn, jinja2, pyyaml
```

## Konfiguration (data/labor_config.yaml)

```yaml
gruppen:
  Niere:
    icon: "💧"
    farbe: "#06b6d4"
    beschreibung: "Die Nieren filtern Abfallstoffe..."

tests:
  GFR: "Glomeruläre Filtrationsrate – zeigt wie gut die Nieren filtern."

ereignisse:
  - von: "2018-01-26"
    bis: "2018-03-01"
    label: "KH Feldkirch"
    typ: "krankenhaus"
    farbe: "#ef4444"

verknuepfungen:
  - name: "Nierenfunktion"
    beschreibung: "GFR wird aus Kreatinin berechnet."
    tests: ["GFR", "Kreatinin", "Harnstoff"]
```

## Befund-Formate (automatisch erkannt)

| Format | Beispiel | Erkennung |
|--------|----------|-----------|
| **freetext** | KH-Befunde 2018, 2024, 2026 | "Laborbefund vom DD.MM.YYYY" |
| **pivot** | laborwerte_2013-2029.txt | "Parameter;Einheit;Referenz;DD.MM.YY;..." |
| **csv** | 2025-01-06 Laborbefund.txt | "Tag;Test;Norm;Erst-Wert;..." |
| **table** | 2024-12-06 | "Test  Norm  Erst-Wert  ...  Einheit" |
| **tab** | Arztpraxis Zünd (2025-07) | Tab + "Kürzel\tBezeichnung\tWert" |
| **kuerzel_space** | OCR-Scans 2019 | "KREA Kreatinin 1.01 mg/dl" |
| **pdf_text** | Aus PDF extrahiert | "Analyse  Ergebnis  Einheit  Referenz" |

## Makefile-Befehle

```bash
make dev              # Server starten (uvicorn, Port 5065)
make labor-reset      # DB löschen + neu importieren + validieren
make labor-validate   # Plausibilitätsprüfung
make labor-trend TEST=CRP  # Trend im Terminal anzeigen
make labor-stats      # Statistik-Übersicht
make up               # Docker Container starten
make restart          # Docker Container neustarten
make jsbuild          # JS/CSS bundeln (esbuild via Docker)
```

## Neue Befunde hinzufügen

1. Textdatei in `data/befunde/` ablegen
2. Format: Eines der 7 erkannten Formate (oder Freitext bereinigen)
3. `make labor-reset` auf dem Server ausführen
4. Dashboard zeigt neue Werte automatisch

## Technologie

- **Backend**: Python 3.12, FastAPI, SQLite, Jinja2
- **Frontend**: Vanilla JS (ES6 Modules), Chart.js, CSS Custom Properties
- **Theme**: HomeApps Unified Theme (Dark/Light, shared mit allen Dashboards)
- **Deploy**: Docker oder direkt uvicorn, Nginx Reverse-Proxy
