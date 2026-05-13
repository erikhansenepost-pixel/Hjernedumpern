"""Konfigurasjon for Hjernedumpern voice-pipeline.

Alle paths kan overstyres med miljøvariabler. Defaults:
- iCloud-mappe:  ~/Library/Mobile Documents/com~apple~CloudDocs/Hjernedumpern
- Transkribering: ../transkribering relativt til denne fila (sibling-mappe)
- Claude CLI:    `claude` i PATH (valgfritt — analyse hoppes over hvis fraværende)

Miljøvariabler:
  HJERNEDUMPERN_ICLOUD_DIR        Full sti til iCloud-mappa (overskriver default)
  HJERNEDUMPERN_TRANSKRIBERING    Sti til transkribering-mappen
  HJERNEDUMPERN_TRANSKRIBER_PY    Direkte sti til transkribér.py
  HJERNEDUMPERN_PYTHON            Python-interpreter for transkribering (default: detect)
  HJERNEDUMPERN_CLAUDE_BIN        Claude CLI (default: claude)
  HJERNEDUMPERN_CLAUDE_MODEL      Modell-navn (default: claude-sonnet-4-6)
  HJERNEDUMPERN_ANALYSE_DISABLED  Sett til 1 for å hoppe over analyse selv om claude finnes
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HOME = Path.home()
PIPELINE_ROOT = Path(__file__).resolve().parent

# ---- iCloud-mappestruktur (opprettes av install.sh) ----

def _detect_icloud_dir() -> Path:
    env = os.environ.get("HJERNEDUMPERN_ICLOUD_DIR")
    if env:
        return Path(env).expanduser().resolve()
    icloud_root = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    return icloud_root / "Hjernedumpern"


ICLOUD_ROOT = _detect_icloud_dir()
INBOX = ICLOUD_ROOT / "Inn"
OUTBOX = ICLOUD_ROOT / "Ut"
ARCHIVE = ICLOUD_ROOT / "Arkiv"

# ---- Pipeline-intern state (lokalt på disk, ikke i iCloud) ----

STATE_DB = PIPELINE_ROOT / "state.sqlite"
LOGS_DIR = PIPELINE_ROOT / "logs"
PROMPTS_DIR = PIPELINE_ROOT / "prompts"

# ---- Transkribering-verktøyet ----

def _detect_transkribering_dir() -> Path | None:
    env = os.environ.get("HJERNEDUMPERN_TRANSKRIBERING")
    if env:
        return Path(env).expanduser().resolve()
    sibling = PIPELINE_ROOT.parent / "transkribering"
    if (sibling / "transkribér.py").exists():
        return sibling
    return None


def _detect_transkriber_py(transkribering_dir: Path | None) -> Path | None:
    env = os.environ.get("HJERNEDUMPERN_TRANSKRIBER_PY")
    if env:
        return Path(env).expanduser().resolve()
    if transkribering_dir is not None:
        candidate = transkribering_dir / "transkribér.py"
        if candidate.exists():
            return candidate
    return None


def _detect_python(transkribering_dir: Path | None) -> str:
    env = os.environ.get("HJERNEDUMPERN_PYTHON")
    if env:
        return str(Path(env).expanduser())
    if transkribering_dir is not None:
        venv_python = transkribering_dir / ".venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
    return sys.executable


TRANSKRIBERING_DIR = _detect_transkribering_dir()
TRANSKRIBER_PY = _detect_transkriber_py(TRANSKRIBERING_DIR)
VENV_PYTHON = _detect_python(TRANSKRIBERING_DIR)

# ---- Claude CLI (valgfritt) ----

CLAUDE_BIN = os.environ.get("HJERNEDUMPERN_CLAUDE_BIN", "claude")
ANALYSE_MODEL = os.environ.get("HJERNEDUMPERN_CLAUDE_MODEL", "claude-sonnet-4-6")


def _analyse_available() -> bool:
    if os.environ.get("HJERNEDUMPERN_ANALYSE_DISABLED") == "1":
        return False
    return shutil.which(CLAUDE_BIN) is not None


ANALYSE_AVAILABLE = _analyse_available()

# ---- Filtyper som aksepteres i inbox ----

AUDIO_SUFFIXES = {".m4a", ".mp3", ".wav", ".ogg", ".flac", ".webm", ".mp4", ".aac", ".aiff"}

# ---- Retry-policy for Claude-kall ----

ANALYSE_MAX_RETRIES = 3
ANALYSE_RETRY_SLEEP_S = 30

# Filstørrelses-grense for å hoppe over "in progress"-iCloud-filer.
# iCloud Drive skriver en 0-byte placeholder før sync fullfører.
MIN_AUDIO_BYTES = 10_000  # 10 KB — mindre enn dette = sannsynligvis placeholder
