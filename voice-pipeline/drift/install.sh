#!/bin/bash
set -euo pipefail

# Hjernedumpern voice-pipeline — installer
#
# Genererer en launchd-service som overvåker iCloud-mappen Inn/ og kjører
# pipeline.py automatisk når nye lydfiler dukker opp.
#
# Konfigurasjon via miljøvariabler (alle valgfrie):
#   HJERNEDUMPERN_ICLOUD_DIR        Full sti til iCloud-mappa
#                                   (default: ~/.../com~apple~CloudDocs/Hjernedumpern)
#   HJERNEDUMPERN_TRANSKRIBERING    Sti til transkribering/-mappa
#   HJERNEDUMPERN_PYTHON            Python-interpreter for transkribering

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$SCRIPT_DIR/hjernedumpern.plist.template"

LABEL="dev.hjernedumpern.daemon"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"

echo "=== Hjernedumpern — installasjon ==="

# 1. Sjekk at iCloud Drive er aktivert
if [ ! -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs" ]; then
    echo "FEIL: iCloud Drive er ikke aktivert."
    echo "Slå det på i Systeminnstillinger → Apple-ID → iCloud → iCloud Drive."
    exit 1
fi

# 2. Bestem iCloud-mappe
ICLOUD_ROOT_DEFAULT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
if [ -n "${HJERNEDUMPERN_ICLOUD_DIR:-}" ]; then
    ICLOUD_DIR="$HJERNEDUMPERN_ICLOUD_DIR"
else
    ICLOUD_DIR="$ICLOUD_ROOT_DEFAULT/Hjernedumpern"
fi

# 3. Finn transkribering-mappa (env-var → sibling-mappe)
if [ -n "${HJERNEDUMPERN_TRANSKRIBERING:-}" ]; then
    TRANSKRIBERING_DIR="$HJERNEDUMPERN_TRANSKRIBERING"
elif [ -f "$INSTALL_DIR/../transkribering/transkribér.py" ]; then
    TRANSKRIBERING_DIR="$(cd "$INSTALL_DIR/../transkribering" && pwd)"
else
    echo "FEIL: transkribering-mappa ikke funnet."
    echo "Sett HJERNEDUMPERN_TRANSKRIBERING=<sti>, eller plassér transkribering/"
    echo "som søsken-mappe til voice-pipeline/."
    exit 1
fi
echo "transkribering: $TRANSKRIBERING_DIR"

# 4. Finn Python-interpreter (env-var → transkribering/.venv → system python3)
if [ -n "${HJERNEDUMPERN_PYTHON:-}" ]; then
    PYTHON_BIN="$HJERNEDUMPERN_PYTHON"
elif [ -x "$TRANSKRIBERING_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$TRANSKRIBERING_DIR/.venv/bin/python"
else
    if ! command -v python3 >/dev/null 2>&1; then
        echo "FEIL: python3 ikke funnet."
        exit 1
    fi
    PYTHON_BIN="$(command -v python3)"
    echo "ADVARSEL: bruker system-python ($PYTHON_BIN)."
    echo "  Anbefalt: lag en venv i $TRANSKRIBERING_DIR/.venv og installer mlx-whisper der."
fi
echo "Python:         $PYTHON_BIN"

# 5. Sjekk transkribér.py
if [ ! -f "$TRANSKRIBERING_DIR/transkribér.py" ]; then
    echo "FEIL: $TRANSKRIBERING_DIR/transkribér.py finnes ikke."
    exit 1
fi

# 6. Sjekk Claude CLI (valgfri — analyse hoppes over hvis fraværende)
if ! command -v claude >/dev/null 2>&1; then
    echo "MERK: 'claude' CLI ikke funnet i PATH."
    echo "  Pipelinen vil kjøre i transkripsjon-bare-modus (uten LLM-analyse)."
    echo "  Installer Claude Code fra https://claude.com/code for å aktivere analyse."
fi

# 7. Opprett iCloud-mappestruktur
echo ""
echo "[1/4] Oppretter iCloud-mapper..."
mkdir -p "$ICLOUD_DIR/Inn"
mkdir -p "$ICLOUD_DIR/Ut"
mkdir -p "$ICLOUD_DIR/Arkiv"
echo "  $ICLOUD_DIR/"

# 8. Skriv en README i Inn/ så brukeren ser i Files-appen hva mappen er
cat > "$ICLOUD_DIR/Inn/LES-MEG.txt" <<EOF
Hjernedumpern — Inbox

Legg lydfiler her fra iPhone eller Mac, så transkriberer pipelinen dem
automatisk. Resultatet dukker opp i ../Ut/ som <navn>.md innen kort tid
(typisk 1 min per minutt audio på M1 Mac).

Fra iPhone Voice Memos:
  1. Hold inne opptak → Del
  2. Lagre i Filer
  3. Velg iCloud Drive → Hjernedumpern → Inn

Se også README.md i repoet.
EOF

# 9. Generer plist fra template
echo ""
echo "[2/4] Genererer launchd-plist..."
mkdir -p "$HOME/Library/LaunchAgents"
USER_LOCAL_BIN="$HOME/.local/bin"

sed \
    -e "s|__LABEL__|${LABEL}|g" \
    -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
    -e "s|__PYTHON__|${PYTHON_BIN}|g" \
    -e "s|__WATCH_PATH__|${ICLOUD_DIR}/Inn|g" \
    -e "s|__USER_HOME__|${HOME}|g" \
    -e "s|__USER_LOCAL_BIN__|${USER_LOCAL_BIN}|g" \
    -e "s|__ICLOUD_DIR__|${ICLOUD_DIR}|g" \
    "$TEMPLATE" > "$PLIST_DST"

# 10. Last service
echo "[3/4] Laster service..."
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

# 11. Verifiser
echo "[4/4] Verifiserer..."
if launchctl list | grep -q "$LABEL"; then
    echo "  ✅ Service lastet."
else
    echo "  ⚠️  Service lastet, men vises ikke i launchctl list — sjekk /tmp/hjernedumpern.err"
fi

echo ""
echo "=== Ferdig ==="
echo "Legg en lydfil i: $ICLOUD_DIR/Inn/"
echo "Se resultat i:    $ICLOUD_DIR/Ut/"
echo ""
echo "Logger:           /tmp/hjernedumpern.log  (stdout fra launchd)"
echo "                  /tmp/hjernedumpern.err  (stderr fra launchd)"
echo "                  $INSTALL_DIR/logs/      (detaljert Python-logg)"
echo ""
echo "Status:           bash $SCRIPT_DIR/healthcheck.sh"
echo "Avinstaller:      bash $SCRIPT_DIR/uninstall.sh"
