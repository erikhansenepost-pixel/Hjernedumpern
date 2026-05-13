#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

LABEL="dev.hjernedumpern.daemon"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"

echo "=== Hjernedumpern — avinstallasjon ==="
echo "(iCloud-filer og prosesserte opptak blir IKKE slettet)"
echo ""

if [ -f "$PLIST_DST" ]; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm "$PLIST_DST"
    echo "  ✅ Fjernet launchd-service: $PLIST_DST"
else
    echo "  (service var ikke installert)"
fi

# Bestem iCloud-mappe slik install.sh ville gjort
ICLOUD_ROOT_DEFAULT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
if [ -n "${HJERNEDUMPERN_ICLOUD_DIR:-}" ]; then
    ICLOUD_DIR="$HJERNEDUMPERN_ICLOUD_DIR"
else
    ICLOUD_DIR="$ICLOUD_ROOT_DEFAULT/Hjernedumpern"
fi

echo ""
echo "Filer som IKKE er fjernet (manuell opprydding om du vil):"
echo "  - $ICLOUD_DIR/"
echo "  - $INSTALL_DIR/state.sqlite"
echo "  - $INSTALL_DIR/logs/"
echo "  - /tmp/hjernedumpern.{log,err}"
