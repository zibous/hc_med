#!/bin/bash

SAVE=false

for arg in "$@"; do
  case $arg in
    --save) SAVE=true ;;
    --help)
      echo "Usage: ./check.sh [--save]"
      exit 0
      ;;
  esac
done

echo -e "\n🔍 Starte Code-Check (Ruff + Pyright)...\n"

# macOS ._* Dateien vorher loeschen
find . -name "._*" -delete 2>/dev/null

RUFF_CMD="ruff check . --select F --exclude testcases,.venv --output-format concise"

run_checks() {
  echo "===== RUFF ====="
  $RUFF_CMD

  echo ""
  echo "===== PYRIGHT ====="
  pyright . --level error
}

if [ "$SAVE" = true ]; then
  run_checks | tee fehler.txt
else
  run_checks
fi

echo -e "\n🧹 Cleanup..."
find . -type d \( -name "__pycache__" -o -name ".pyrightcache" \) -prune -exec rm -rf {} + 2>/dev/null

echo "✅ Fertig"
