#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

LABEL="dev.hjernedumpern.daemon"

# Bestem iCloud-mappe (samme logikk som install.sh)
ICLOUD_ROOT_DEFAULT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
if [ -n "${HJERNEDUMPERN_ICLOUD_DIR:-}" ]; then
    ICLOUD_DIR="$HJERNEDUMPERN_ICLOUD_DIR"
else
    ICLOUD_DIR="$ICLOUD_ROOT_DEFAULT/Hjernedumpern"
fi

echo "=== Hjernedumpern — status ==="
echo ""

# Service
if launchctl list | grep -q "$LABEL"; then
    echo "Service:     ✅ lastet ($LABEL)"
else
    echo "Service:     ❌ IKKE lastet. Kjør: bash $SCRIPT_DIR/install.sh"
fi

# iCloud-mapper
for sub in Inn Ut Arkiv; do
    if [ -d "$ICLOUD_DIR/$sub" ]; then
        count=$(ls -1 "$ICLOUD_DIR/$sub" 2>/dev/null | wc -l | tr -d ' ')
        echo "iCloud $sub:   ✅ $count fil(er)"
    else
        echo "iCloud $sub:   ❌ mangler"
    fi
done
echo ""

# Logger
echo "Siste hendelser (launchd stdout):"
if [ -f /tmp/hjernedumpern.log ]; then
    tail -5 /tmp/hjernedumpern.log | sed 's/^/  /'
else
    echo "  (ingen logg enda)"
fi
echo ""

echo "Siste feil (launchd stderr):"
if [ -f /tmp/hjernedumpern.err ] && [ -s /tmp/hjernedumpern.err ]; then
    tail -5 /tmp/hjernedumpern.err | sed 's/^/  /'
else
    echo "  (ingen)"
fi
echo ""

# Siste runs fra state.sqlite
if [ -f "$INSTALL_DIR/state.sqlite" ]; then
    echo "Siste 5 prosesserte filer:"
    sqlite3 -column -header "$INSTALL_DIR/state.sqlite" \
        "SELECT id, status, datetime(created_at) as started, datetime(completed_at) as done, input_path
         FROM runs ORDER BY id DESC LIMIT 5" 2>/dev/null | sed 's/^/  /' || echo "  (kan ikke lese state.sqlite)"
fi
