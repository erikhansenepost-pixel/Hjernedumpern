# voice-pipeline — iPhone → transkripsjon → analyse

Lokal Mac-pipeline som plukker opp lydfiler fra iCloud Drive, transkriberer
med NB-Whisper (lokalt, norsk, ~2 % WER), og gjør strukturert LLM-analyse
av innholdet (valgfritt). Alt kjører på din egen Mac — ingen cloud-STT,
ingen kost for transkriberingen.

Dette er kjernen i **Hjernedumpern**. Se rot-README for samlet introduksjon.

## Arbeidsflyt

```
iPhone Voice Memos
    ↓ Del → Lagre i Filer → iCloud Drive/Hjernedumpern/Inn/
iCloud sync (5-30 sek)
    ↓
Mac launchd WatchPaths ser ny fil
    ↓
pipeline.py:
  1. Transkriberer med transkribér.py (MLX, ~1x realtime)
  2. (valgfritt) Analyserer med Claude Sonnet — sammendrag + action items
  3. Skriver strukturert .md + .txt (+ .json hvis analyse)
  4. Flytter lydfila til Arkiv/
iCloud sync
    ↓
iPhone Filer-app viser resultat i Hjernedumpern/Ut/
```

For 1 times opptak: ~1 time prosessering på M1. Du tar opp, sender inn,
gjør noe annet, åpner Filer-appen når du er klar og leser sammendraget.

## Krav

- **macOS** (Apple Silicon anbefalt — Intel Mac fungerer via CPU-fallback)
- **iCloud Drive aktivert** (Systeminnstillinger → Apple-ID → iCloud)
- **Python 3.11+**
- **ffmpeg:** `brew install ffmpeg`
- **NB-Whisper-modell** — lastes automatisk ved første kjøring (~3 GB)
- **Claude CLI (valgfritt):** Installer Claude Code fra <https://claude.com/code>
  hvis du vil ha LLM-analyse. Pipelinen kjører fint uten — den leverer da
  bare ren transkripsjon.

## Installasjon

Forutsetning: `transkribering`-verktøyet må være installert først som
søsken-mappe (se rot-README for full guide).

```bash
cd ../transkribering
python3 -m venv .venv
.venv/bin/pip install mlx-whisper faster-whisper
```

Deretter:

```bash
cd voice-pipeline
bash drift/install.sh
```

`install.sh` oppretter iCloud-mappestrukturen, genererer launchd-servicen
fra template og verifiserer. Første prosessering laster NB-Whisper-modellen
(~3 GB).

## Bruk

**Fra iPhone:**
1. Voice Memos → ta opptak → Del
2. Lagre i Filer → iCloud Drive → Hjernedumpern → Inn
3. Vent ~1x audio-lengden
4. Åpne Filer-appen, gå til Hjernedumpern/Ut/, åpne `<navn>.md`

**Fra Mac (dra filer):**
Bare kopiér/flytt lydfila til `~/Library/Mobile Documents/com~apple~CloudDocs/Hjernedumpern/Inn/`.

**Manuell kjøring (testing):**
```bash
cd voice-pipeline
../transkribering/.venv/bin/python pipeline.py ~/Downloads/opptak.m4a

# Eller uten LLM-analyse:
../transkribering/.venv/bin/python pipeline.py --no-analyse ~/Downloads/opptak.m4a
```

## Output

For hver innkommende `opptak.m4a` får du i `Hjernedumpern/Ut/`:

- **`opptak.md`** — lesbar rapport med sammendrag, action items, personer, stemning, rå transkripsjon
- **`opptak.txt`** — ren transkripsjon (rå NB-Whisper-output)
- **`opptak.json`** — strukturert analyse (kun hvis Claude CLI brukes)

Uten Claude CLI får du fortsatt `.md` + `.txt` — men markdown-en inneholder
kun selve transkripsjonen.

Ved feil: `opptak.error.md` med feilmelding og hvor du finner logger.

Originalen flyttes til `Hjernedumpern/Arkiv/opptak.m4a` når ferdig —
aldri slettet automatisk.

## Struktur

| Fil | Rolle |
|-----|-------|
| `pipeline.py` | Entry-point, orchestrerer hele flyten |
| `analyse.py` | Kaller `claude --print` mot Sonnet med JSON-prompt (valgfri) |
| `render.py` | Slår sammen .txt + .json til lesbar .md |
| `state.py` | SQLite for idempotens + kjøre-historikk |
| `config.py` | Paths og innstillinger (env-var-overstyrbare) |
| `prompts/analyse.md` | Prompt Sonnet får — JSON-schema definert her |
| `drift/` | launchd-template, install/uninstall/healthcheck |

## Miljøvariabler (valgfrie)

| Variabel | Beskrivelse |
|----------|-------------|
| `HJERNEDUMPERN_ICLOUD_DIR` | Full sti til iCloud-mappa (default: `~/.../com~apple~CloudDocs/Hjernedumpern`) |
| `HJERNEDUMPERN_TRANSKRIBERING` | Sti til transkribering-mappa (default: søsken-mappe) |
| `HJERNEDUMPERN_PYTHON` | Python-interpreter for transkribering (default: detect via .venv eller PATH) |
| `HJERNEDUMPERN_CLAUDE_BIN` | Claude CLI (default: `claude`) |
| `HJERNEDUMPERN_CLAUDE_MODEL` | Modell-navn (default: `claude-sonnet-4-6`) |
| `HJERNEDUMPERN_ANALYSE_DISABLED` | Sett til `1` for å tvinge transkripsjon-bare-modus |

## Overvåking

```bash
# Live status
bash drift/healthcheck.sh

# Følg logger
tail -f /tmp/hjernedumpern.log
tail -f /tmp/hjernedumpern.err
tail -f logs/pipeline-$(date +%Y-%m-%d).log

# Se siste 20 prosesseringer
sqlite3 -column -header state.sqlite \
    "SELECT id, status, datetime(completed_at), input_path FROM runs ORDER BY id DESC LIMIT 20"
```

## Avinstallasjon

```bash
bash drift/uninstall.sh
```

Fjerner launchd-servicen. iCloud-filer og `state.sqlite` beholdes.

## Feilsøking

| Symptom | Sjekk |
|---------|-------|
| Fil blir liggende i Inn/ | `bash drift/healthcheck.sh` — er servicen lastet? |
| `.icloud`-filer i stedet for lyd | iCloud har ikke lastet ned fila enda. Trykk på den i Filer-appen på Mac. |
| transkribér.py feiler | Test verktøyet alene: `../transkribering/.venv/bin/python ../transkribering/transkribér.py --help` |
| `claude --print` feiler | `claude --version` — er CLI installert og logget inn? Eller kjør med `--no-analyse`. |
| JSON-parse-feil i analyse | Sjekk `logs/pipeline-*.log` — hva returnerte Claude? |

## Roadmap

- iOS-app som overvåker filopplasting og trigger transkribering uten launchd
- Alternative analyse-backends (lokal Ollama, OpenAI, Google Gemini)
- Automatisk push-notification når ferdig
- iOS Shortcut som snarvei
