

```text
hc_med/
├── data/
│   ├── labor.db                    ← SQLite-Datenbank
│   └── befunde/
│       └── laborwerte_gesamt.csv   ← CSV-Export (weiterhin)
└── scripts/
    ├── extract_labvalues.py        ← Hauptskript (parst + schreibt DB + CSV)
    └── labor_db.py                 ← DB-Modul (Schema, Import, Export, Queries)
```

---

## DB-Schema:

- patienten – Stammdaten (erweiterbar für weitere Personen)
- befunde – Quelldateien mit Labor/Arzt und Importdatum
- laborwerte – Einzelwerte mit allen normalisierten und originalen Daten

### Vordefinierte Views:

- v_zeitreihe – Alle Werte chronologisch pro Test (für Verlaufsdiagramme)
- v_aktuell – Letzter Wert pro Test
- v_pathologisch – Nur auffällige Werte (H/L)

---


### SQL Statements

```sql

sqlite3 data/labor.db "SELECT * FROM v_zeitreihe WHERE test='CRP';"
sqlite3 data/labor.db "SELECT * FROM v_pathologisch WHERE datum > '2024-01-01';"

-- GFR-Trend (Nierenfunktion über die Jahre)
sqlite3 data/labor.db "SELECT datum, alter_jahre, wert, einheit, flag FROM v_zeitreihe WHERE test = 'GFR' ORDER BY datum;"

-- Pathologische Werte der letzten Messung
sqlite3 data/labor.db "SELECT datum, gruppe, test, wert, einheit, normbereich, flag FROM v_pathologisch WHERE datum >= '2025-01-01';"

-- CRP-Verlauf über die Jahre
sqlite3 data/labor.db "SELECT datum, alter_jahre, wert, einheit, normbereich, flag FROM v_zeitreihe WHERE test = 'CRP' ORDER BY datum;"

```

## Import
Wenn du neue Befunde hinzufügst, einfach python scripts/extract_labvalues.py erneut laufen lassen – es reimportiert alles idempotent (bestehende Befunde werden aktualisie


## Verteilung:
Jahr	Messwerte
2013	59
2014	28
2015	20
2017	36
2018	200
2019	104
2024	129
2025	71
Total	647
Auffällig:

- 2016 fehlt komplett – keine Befunde für das Jahr
- 2020–2023 fehlen – da hast du wohl noch keine Daten digitalisiert

Wenn du die Lücken 2020–2023 noch findest und als Textdatei in den befunde/-Ordner legst, werden sie beim nächsten make labor automatisch mit eingelesen.

Das Makefile funktioniert – einfach make labor zum Reimport und make labor-trend TEST=CRP für Trends.