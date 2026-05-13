# Hjernedumpern

**Dum ned i mikrofonen — få strukturert tekst tilbake.**

Lokal Mac-pipeline som plukker opp lydopptak fra iCloud Drive, transkriberer
norsk tale med NB-Whisper (~2 % WER), og — hvis du vil — destillerer
innholdet til sammendrag, action items og temaer via Claude Sonnet.

Alt kjører lokalt på din egen Mac. Lyden forlater aldri maskinen etter iCloud import.  
Transkriberingen er gratis - kjører lokalt. LLM-analysen er valgfri og koster bare hvis du
bruker den.

```
iPhone Voice Memos
    ↓ Del → Lagre i Filer → iCloud Drive/Hjernedumpern/Inn/
iCloud sync
    ↓
Mac launchd ser ny fil → pipeline.py
    ↓
NB-Whisper transkripsjon (lokalt, MLX)
    ↓
(valgfritt) Claude Sonnet-analyse
    ↓
.md + .txt (+ .json) til Hjernedumpern/Ut/
```

## Hvorfor

Effektiv fangst av tanker og diktater mens man er ute å går. Spill inn på iPhone, glem det, finn et
strukturert sammendrag i Filer-appen et par minutter senere.

- **Lokal:** Lyd forlater aldri Mac-en etter import. Ingen cloud-STT, ingen kost.
- **Norsk:** NB-Whisper er trent på norsk av Nasjonalbiblioteket (~2 % WER).
- **Idempotent:** Pipelinen kjenner igjen filer du allerede har prosessert.
- **Idem-resilient:** Faller tilbake til ren transkripsjon hvis LLM-analysen
  feiler eller mangler.

## Krav

- **macOS** (Apple Silicon anbefalt — Intel Mac fungerer via CPU-fallback)
- **iCloud Drive aktivert** i Systeminnstillinger
- **Python 3.11+**
- **ffmpeg:** `brew install ffmpeg`
- **Claude CLI (valgfritt)** — kun hvis du vil ha LLM-analyse. Installer
  fra <https://claude.com/code>.

## Installasjon

```bash
# 1. Klon repoet
git clone https://github.com/<din-bruker>/Hjernedumpern.git
cd Hjernedumpern

# 2. Sett opp transkribering-verktøyet (laster NB-Whisper-modellen
#    første gang du kjører — ~3 GB)
brew install ffmpeg
cd transkribering
python3 -m venv .venv
.venv/bin/pip install mlx-whisper faster-whisper
cd ..

# 3. Installer pipeline-servicen
bash voice-pipeline/drift/install.sh
```

`install.sh` oppretter `~/Library/Mobile Documents/com~apple~CloudDocs/Hjernedumpern/{Inn,Ut,Arkiv}/`
og en launchd-service som overvåker `Inn/`.

## Bruk

**Fra iPhone:**
1. Voice Memos → ta opptak → Del
2. Lagre i Filer → iCloud Drive → Hjernedumpern → Inn
3. Vent ~1x audio-lengden (1 time for 1 times opptak på M1)
4. Åpne Filer-appen, gå til `Hjernedumpern/Ut/`, åpne `<navn>.md`

**Fra Mac:**
Kopiér/dra filen til `~/Library/Mobile Documents/com~apple~CloudDocs/Hjernedumpern/Inn/`.

**Manuell kjøring (testing):**
```bash
cd voice-pipeline
../transkribering/.venv/bin/python pipeline.py ~/Downloads/opptak.m4a

# Eller bare transkripsjon, uten LLM-analyse:
../transkribering/.venv/bin/python pipeline.py --no-analyse ~/Downloads/opptak.m4a
```

## Bare transkribering — uten pipeline

`transkribering/` er en frittstående CLI som du kan bruke alene:

```bash
cd transkribering
.venv/bin/python transkribér.py ~/Downloads/opptak.m4a
# → opptak.txt
```

Se [`transkribering/README.md`](transkribering/README.md) for flagg og ytelse.

## Status

| Komponent | Status |
|-----------|--------|
| Transkribering (NB-Whisper / MLX) | Stabil — i daglig bruk |
| Pipeline-orkestrator (launchd) | Stabil — fungerer mens du har en aktiv brukersession på Mac-en |
| Claude-analyse | Valgfri — fungerer hvis `claude` CLI er installert |
| iOS-app (auto-trigger uten session) | Roadmap — ikke implementert |
| Andre LLM-backends (Ollama, OpenAI, ...) | Roadmap — ikke implementert |

## Avhengighets-lisenser

Alle ledd er kompatible med MIT:

| Avhengighet | Lisens | Bruk |
|-------------|--------|------|
| Python stdlib | PSF | Pipeline-orkestrering |
| `mlx-whisper` | MIT | Lokal transkripsjon (Apple Silicon) |
| `faster-whisper` | MIT | CPU-fallback |
| NB-Whisper-modellene (`NbAiLab/*`) | Apache 2.0 | Norsk-finetunede vekter |
| `ffmpeg` (runtime-binær) | LGPL/GPL | Lyd-decoding (subprocess-kalt, ikke embedded) |
| `claude` CLI (valgfri runtime-binær) | Anthropic proprietary | LLM-analyse-kall |

## Bidrag

Issues og pull requests er velkomne. Se [CONTRIBUTING.md](CONTRIBUTING.md).

## Lisens

[MIT](LICENSE) — bruk det som du vil.
