# transkribering — lokal norsk transkribering

Minimal lokal CLI som transkriberer lydfiler med **NB-Whisper** (norsk
fine-tunet Whisper fra Nasjonalbiblioteket) via Apple MLX (Metal-akselerert).
Alt kjører lokalt: ingen API-key, ingen kost, ingen cloud-send.

## Default-stack

- **Motor:** MLX (Apple Silicon Metal-akselerert)
- **Modell:** `aalst/nb-whisper-large-mlx`
- **Hastighet:** ~1x realtime på M1, raskere på M-Pro/Max
- **Norsk WER:** ~2 % (mot ~8–10 % for OpenAI Whisper API)
- **Personvern:** Lyd forlater aldri Mac-en

## Engangsoppsett

```bash
brew install ffmpeg
cd transkribering
python3 -m venv .venv
.venv/bin/pip install mlx-whisper faster-whisper
chmod +x transkribér.py
```

Ingen API-key. Ingen `.env`-fil.

## Bruk

```bash
cd transkribering

# Standard — beste kvalitet (anbefalt)
.venv/bin/python transkribér.py ~/Downloads/opptak.m4a

# Lange filer: caffeinate hindrer Mac-sleep underveis
caffeinate -i .venv/bin/python transkribér.py ~/Downloads/intervju-2t.m4a

# Raskere (8x), litt lavere kvalitet — for haster-utkast
.venv/bin/python transkribér.py opptak.m4a --fast

# Auto-deteksjon av språk
.venv/bin/python transkribér.py opptak.m4a --language auto

# Egen output-sti
.venv/bin/python transkribér.py opptak.m4a --output ~/notater/opptak.txt

# CPU fallback (Intel Mac eller MLX-feil)
.venv/bin/python transkribér.py opptak.m4a --engine faster-whisper
```

Output lander som `<input>.txt` ved siden av lydfila med mindre `--output` er satt.

## Arbeidsflyt: send inn → hent senere

For lange opptak:

```bash
# Spill inn på iPhone, AirDrop til Mac → ~/Downloads/

# Start transkribering i bakgrunnen, behold logg:
caffeinate -i .venv/bin/python transkribér.py ~/Downloads/opptak.m4a \
  > ~/Downloads/opptak.log 2>&1 &

# Gå og gjør noe annet. Mac sover ikke. Kom tilbake.

# Hent transkriptet:
open ~/Downloads/opptak.txt
```

For 1 times audio: ~1 time processering med MLX large på M1. Hvis du sjekker
2–3 timer senere er det ferdig.

## Første kjøring

Første gang lastes modellen ned fra HuggingFace til `~/.cache/huggingface/hub/`:

- `aalst/nb-whisper-large-mlx` ≈ 3 GB (5–10 min på rimelig nettlinje)
- `aalst/nb-whisper-large-distil-turbo-beta-mlx` ≈ 1,2 GB (kun ved `--fast`)

Senere kjøringer er instant — modellen lastes fra disk-cache på sekunder.

## Ytelse på din maskin

Sanntidsmålinger fra et 56 min monolog-opptak på M1 8 GB:

| Stack | Speedup | Estimat for 56 min audio | Kvalitet |
|-------|---------|--------------------------|----------|
| **MLX large (default)** | 0,95–1,0x | ~60 min | ✅ ~2 % WER |
| MLX turbo (`--fast`) | 8,1x | ~8 min | ⚠️ ~3–4 % WER, noen hallusinasjoner |
| faster-whisper sekvensiell | 0,5x | ~110 min | ✅ ~2 % WER |
| faster-whisper 2× parallell | 0,07x | ~6 timer | ❌ swap-katastrofe på 8 GB |

På M-Pro/Max eller M3/M4 ville MLX large vært 2–5x raskere.

## Flagg

| Flagg | Default | Beskrivelse |
|-------|---------|-------------|
| `--engine` | `mlx` | `mlx` (Metal) eller `faster-whisper` (CPU) |
| `--fast` | av | Bruk MLX turbo-modell (raskere, lavere kvalitet) |
| `--model` | (auto) | Overstyr HuggingFace modell-navn |
| `--language` | `no` | Språkkode, eller `auto` for deteksjon |
| `--output` | `<input>.txt` | Output-sti |
| `--verbose` | av | MLX progress-logging |
| `--beam-size` | `5` | (faster-whisper) beam search width |
| `--no-vad` | av | (faster-whisper) skru av VAD |

## Lyd fra iPhone

- **AirDrop:** Voice Memos → Del → AirDrop til Mac (lander i `~/Downloads/`)
- **iCloud Voice Memos sync:** Slå på i iPhone-innstillinger; opptak vises i Voice Memos-appen på Mac. Høyreklikk → Vis i Finder.
- **Filer-app:** Lagre fra Voice Memos til iCloud Drive

## Filer

- `transkribér.py` — hovedscript (MLX default, faster-whisper fallback)
- `.gitignore` — ekskluderer venv, output-tekst, transkriberte mediefiler
- `pyproject.toml` — dependencies (kun for dokumentasjon)
