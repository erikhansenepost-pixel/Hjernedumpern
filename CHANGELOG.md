# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versjon: [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planlagt

- iOS-app som auto-trigger transkribering uten aktiv Mac-session
- Alternative analyse-backends (lokal Ollama, OpenAI, Google Gemini)
- iOS Shortcut som snarvei
- Push-notification når prosessering er ferdig

## [0.1.0] — 2026-05-13

### Lagt til

- Lokal transkriberings-CLI (`transkribering/`) med MLX-Whisper og
  faster-whisper-fallback. Default-modell: `aalst/nb-whisper-large-mlx`
  (~2 % WER på norsk).
- Pipeline-orkestrator (`voice-pipeline/`) som overvåker iCloud Drive,
  transkriberer nye filer og leverer strukturert markdown.
- Valgfri LLM-analyse via Claude Sonnet — sammendrag, action items,
  hovedtemaer, personer, stemning. Pipelinen kjører fint uten.
- `--no-analyse`-flagg + auto-detect av Claude CLI: pipeline-en faller
  tilbake til ren transkripsjon hvis `claude` mangler.
- macOS launchd-installer som genererer plist fra template og overvåker
  `~/Library/Mobile Documents/com~apple~CloudDocs/Hjernedumpern/Inn/`.
- Miljøvariabel-overstyring av alle paths (`HJERNEDUMPERN_ICLOUD_DIR`,
  `HJERNEDUMPERN_TRANSKRIBERING`, `HJERNEDUMPERN_PYTHON`, m.fl.).
- SQLite-basert state-store for idempotens (samme fil prosesseres ikke
  to ganger).
- iCloud File Provider-aware fil-håndtering (`brctl download` + `cp -X`)
  for å unngå EDEADLK på sync-aktive filer.
