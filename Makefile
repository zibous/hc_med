# Variablen

PROJECT_NAME = $(notdir $(CURDIR))
FORGEJO_IP   = 10.1.1.119
FORGEJO_PORT = 3143
FORGEJO_USER = peter
FORGEJO_URL  = http://$(FORGEJO_IP):$(FORGEJO_PORT)/$(FORGEJO_USER)/$(PROJECT_NAME).git

SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help dev up down build rebuild logs ps restart labor labor-import labor-csv labor-query labor-stats labor-pathologisch labor-trend labor-reset

DB_FILE   = data/user/$(or $(USER),peter)/labor.db
CSV_FILE  = data/user/$(or $(USER),peter)/laborwerte_gesamt.csv
SCRIPT    = scripts/import_befunde/main.py
SCRIPT_DIR = scripts/import_befunde

# ---------------------------------------------------------
# Docker
# ---------------------------------------------------------

APP_PORT = 5065
HOST_PORT = 8065

dev: ## Startet direkt mit uvicorn (ohne Docker)
	@echo "🚀 Starte Dev-Server: http://10.1.1.119:$(APP_PORT)/"
	python3 -m uvicorn app.main:app --host 0.0.0.0 --port $(APP_PORT) --reload

dev-bg: ## Startet im Hintergrund (ohne Docker)
	@echo "🚀 Starte im Hintergrund: http://10.1.1.119:$(APP_PORT)/"
	nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port $(APP_PORT) > logs/uvicorn.log 2>&1 &
	@echo "PID: $$(lsof -ti:$(APP_PORT))"

dev-stop: ## Hintergrund-Server stoppen
	@PID=$$(lsof -ti:$(APP_PORT)); \
	if [ -n "$$PID" ]; then kill $$PID && echo "✓ Gestoppt (PID $$PID)"; \
	else echo "Kein Prozess auf Port $(APP_PORT)"; fi

up: ## Container starten
	docker compose up -d

down: ## Container stoppen
	docker compose down

build: ## Container neu bauen und starten
	docker compose up -d --build

rebuild: ## Container komplett neu bauen (no cache)
	docker compose down
	docker compose build --no-cache
	docker compose up -d

logs: ## Container-Logs anzeigen
	docker compose logs -f

ps: ## Laufende Container
	docker compose ps

restart: ## Container neustarten
	docker compose restart

# ---------------------------------------------------------
# Laborwerte
# ---------------------------------------------------------

labor: ## Laborwerte extrahieren → SQLite + CSV (PARAM: USER=peter)
	@echo "🔬 Extrahiere Laborwerte für User: $(or $(USER),peter)..."
	@python3 $(SCRIPT) $(or $(USER),peter)

#  make labor-test USER=peter
labor-test: ## Laborwerte extrahieren im Test-Modus (PARAM: USER=peter)
	@echo "🧪 Test-Import für User: $(or $(USER),peter)..."
	@python3 $(SCRIPT) $(or $(USER),peter) --test

labor-import: labor ## Alias für labor (Reimport aller Befunde)

labor-csv: ## Nur CSV anzeigen (erste 30 Zeilen)
	@head -30 $(CSV_FILE) | column -t -s';'

labor-stats: ## Datenbank-Statistiken anzeigen
	@echo "📊 Laborwerte-Statistik:"
	@sqlite3 $(DB_FILE) "\
		SELECT '  Patienten: ' || COUNT(*) FROM patienten; \
		SELECT '  Befunde:   ' || COUNT(*) FROM befunde; \
		SELECT '  Messwerte: ' || COUNT(*) FROM laborwerte; \
		SELECT '  Zeitraum:  ' || MIN(datum) || ' bis ' || MAX(datum) FROM laborwerte;"
	@echo ""
	@echo "  Gruppen:"
	@sqlite3 $(DB_FILE) "SELECT '    ' || gruppe || ': ' || COUNT(*) FROM laborwerte GROUP BY gruppe ORDER BY gruppe;"

labor-aktuell: ## Aktuelle Werte (letzte Messung pro Test)
	@sqlite3 -header -column $(DB_FILE) "SELECT * FROM v_aktuell;"

labor-pathologisch: ## Pathologische Werte anzeigen
	@sqlite3 -header -column $(DB_FILE) "SELECT * FROM v_pathologisch;"

labor-trend: ## Trend für einen Test anzeigen (PARAM: TEST=CRP USER=peter)
	@if [ -z "$(TEST)" ]; then \
		echo "Nutzung: make labor-trend TEST=CRP"; \
		echo ""; \
		echo "Verfügbare Tests:"; \
		sqlite3 $(DB_FILE) "SELECT DISTINCT test_standard FROM laborwerte ORDER BY test_standard;" | sed 's/^/  /'; \
	else \
		sqlite3 -header -column $(DB_FILE) \
			"SELECT datum, alter_jahre, wert, einheit, normbereich, flag \
			 FROM v_zeitreihe WHERE test='$(TEST)' ORDER BY datum;"; \
	fi

labor-gruppe: ## Alle Werte einer Gruppe anzeigen (PARAM: GRUPPE=Niere)
	@if [ -z "$(GRUPPE)" ]; then \
		echo "Nutzung: make labor-gruppe GRUPPE=Niere"; \
		echo ""; \
		echo "Verfügbare Gruppen:"; \
		sqlite3 $(DB_FILE) "SELECT DISTINCT gruppe FROM laborwerte ORDER BY gruppe;" | sed 's/^/  /'; \
	else \
		sqlite3 -header -column $(DB_FILE) \
			"SELECT datum, test_standard AS test, wert_norm AS wert, einheit_norm AS einheit, normbereich, flag \
			 FROM laborwerte WHERE gruppe='$(GRUPPE)' ORDER BY test_standard, datum;"; \
	fi

labor-query: ## Freie SQL-Abfrage (PARAM: SQL="SELECT ...")
	@if [ -z "$(SQL)" ]; then \
		echo "Nutzung: make labor-query SQL=\"SELECT * FROM laborwerte LIMIT 10\""; \
	else \
		sqlite3 -header -column $(DB_FILE) "$(SQL)"; \
	fi

labor-befunde: ## Alle importierten Befund-Dateien anzeigen
	@sqlite3 -header -column $(DB_FILE) \
		"SELECT b.datum, b.quelldatei, b.labor, b.format, COUNT(l.id) AS werte \
		 FROM befunde b LEFT JOIN laborwerte l ON l.befund_id = b.id \
		 GROUP BY b.id ORDER BY b.datum;"

labor-reset: ## Datenbank löschen und neu aufbauen (PARAM: USER=peter)
	@echo "⚠️  Lösche DB für User: $(or $(USER),peter)..."
	@rm -f data/user/$(or $(USER),peter)/labor.db
	@echo "🔬 Reimport Laborwerte..."
	@python3 $(SCRIPT) $(or $(USER),peter)
	@echo "✅ Fertig!"

labor-validate: ## Laborwerte auf Plausibilität prüfen
	@python3 scripts/validate_labor.py

labor-luecken: ## Fehlende Jahre und Jahre mit wenig Daten anzeigen (PARAM: USER=peter)
	@echo "📊 Datenabdeckung pro Jahr:"
	@echo ""
	@sqlite3 -header -column $(DB_FILE) "\
		SELECT substr(datum,1,4) AS jahr, COUNT(*) AS messwerte, \
		       COUNT(DISTINCT test_standard) AS tests, \
		       COUNT(DISTINCT substr(datum,1,7)) AS monate \
		FROM laborwerte \
		WHERE gruppe != 'Körperdaten' \
		GROUP BY jahr ORDER BY jahr;"
	@echo ""
	@echo "⚠️  Fehlende oder schwache Jahre (< 20 Laborwerte):"
	@python3 -c "\
	import sqlite3; \
	conn = sqlite3.connect('$(DB_FILE)'); \
	rows = dict(conn.execute(\"SELECT substr(datum,1,4), COUNT(*) FROM laborwerte WHERE gruppe != 'Körperdaten' GROUP BY 1\").fetchall()); \
	first = int(min(rows.keys())); last = int(max(rows.keys())); \
	missing = [str(y) for y in range(first, last+1) if str(y) not in rows]; \
	weak = [f'{y} ({rows[str(y)]} Werte)' for y in range(first, last+1) if str(y) in rows and rows[str(y)] < 20]; \
	print(f'  Fehlend: {', '.join(missing) if missing else 'Keine'}'); \
	print(f'  Wenig Daten: {', '.join(weak) if weak else 'Keine'}'); \
	conn.close()"

# ---------------------------------------------------------
# Build (JS/CSS Bundling)
# ---------------------------------------------------------

jsbuild: ## 🔧 Komprimiert JS und CSS parallel über Docker – maximal optimiert
	@echo "📦 Starte JS & CSS Bundling via Docker & esbuild..."
	@cp ../shared/themes/theme.css frontend/static/css/theme.css
	@docker run --rm -v "$$(pwd)":/app -w /app node:20-alpine sh -c "\
		npx esbuild frontend/static/js/main.js --bundle --minify --sourcemap --target=es2020 --outfile=frontend/static/js/main.bundle.js && \
		npx esbuild frontend/static/css/style.css --bundle --minify --sourcemap --outfile=frontend/static/css/style.bundle.css"
	@echo "✅ Fertig!"

deploy: jsbuild restart ## 🚀 Build + Restart in einem Schritt

jsclean: ## 🔧 Komprimiert JS und CSS entfernen
	@echo "🧼 Bereinige produktive Build-Dateien..."
	@rm -f frontend/static/js/main.bundle.js
	@rm -f frontend/static/js/main.bundle.js.map
	@rm -f frontend/static/css/style.bundle.css
	@rm -f frontend/static/css/style.bundle.css.map
	@echo "✨ Verzeichnis ist wieder sauber."

# ---------------------------------------------------------
# Maintenance
# ---------------------------------------------------------

install: ## Dependencies installieren
	@pip install -r requirements.txt

# ---------------------------------------------------------
# Git (Forgejo)
# ---------------------------------------------------------

git-status: ## Git-Remote-Konfiguration anzeigen
	@echo "🔍 Überprüfe Git-Remote-Konfiguration..."
	@if ! git remote get-url origin >/dev/null 2>&1; then \
		echo "❌ Fehler: 'origin' ist noch nicht eingerichtet!"; \
		echo "👉 Bitte führe aus: make git-setup"; \
		exit 1; \
	fi
	@URL=$$(git remote get-url origin); \
	echo "🍏 Forgejo-Server ist aktiv verbunden!" ; \
	echo "🔗 Aktuelle URL: $$URL"

git-setup: ## Git-Verbindung zum Forgejo-Server einrichten
	@echo "🛠️ Initialisiere Forgejo Server-Verbindung für '$(PROJECT_NAME)'..."
	@if ! git remote get-url origin >/dev/null 2>&1; then \
		git remote add origin $(FORGEJO_URL); \
		echo "🎉 Server-URL erfolgreich neu angelegt!"; \
	else \
		git remote set-url origin $(FORGEJO_URL); \
		echo "🔄 Bestehende Server-URL erfolgreich korrigiert!"; \
	fi
	@echo "🔗 Ziel-Adresse: $(FORGEJO_URL)"

git-update: git-status ## Git Update durchführen
	git add -A
	git commit -m "Update am $$(date +'%Y-%m-%d %H:%M')" || true
	git push -u origin main

git-release: git-status ## Neues Versions-Tag automatisch berechnen, erstellen und zu Forgejo pushen
	git add -A
	git commit -m "Release-Vorbereitung am $$(date +'%Y-%m-%d %H:%M')" || true
	git push origin main
	@LAST_TAG=$$(git describe --tags --abbrev=0 2>/dev/null || echo "v2.1.0"); \
	NEXT_TAG=$$(echo $$LAST_TAG | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	echo "🍏 Letzte Version war: $$LAST_TAG"; \
	echo "⚡ Berechnete neue Version: $$NEXT_TAG"; \
	echo "📦 Erstelle Git-Tag $$NEXT_TAG mit aktuellem Zeitstempel..."; \
	git tag -a $$NEXT_TAG -m "Automatisches Release $$NEXT_TAG am $$(date +'%Y-%m-%d %H:%M') via Makefile"; \
	git push origin $$NEXT_TAG; \
	echo "🎉 Version $$NEXT_TAG erfolgreich an Forgejo übermittelt!"


# ---------------------------------------------------------
# Help
# ---------------------------------------------------------

help: ## Hilfe anzeigen
	@echo "Multi-User: USER=peter (default) | USER=reni | USER=guest"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
