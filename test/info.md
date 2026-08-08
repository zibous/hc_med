labor_extractor/
│
├── pyproject.toml             # Konfiguration für Tools (Ruff/Pytest)
│
└── src/
    └── extractor/
        ├── __init__.py
        ├── main.py            # Orchestrierung (Einstiegspunkt)
        ├── config.py          # Globale Pfade oder Mapping-Tabellen
        │
        ├── core/              # Normalisierung & Logik
        │   ├── __init__.py
        │   ├── normalization.py # normalize_test_name, normalize_unit_and_value
        │   └── utils.py       # calculate_age_at_date
        │
        └── parsers/           # Die eigentlichen Dateiparser
            ├── __init__.py
            ├── base.py        # Gemeinsame Logik / Interface
            ├── detector.py    # detect_format
            ├── freetext.py    # parse_freetext_file
            ├── table.py       # parse_table_format, parse_pivot_format
            ├── csv_tab.py     # parse_csv_format, parse_tab_format, parse_simple_csv
            ├── kuerzel.py     # parse_kuerzel_space_format
            └── pdf.py         # parse_pdf_text_format
