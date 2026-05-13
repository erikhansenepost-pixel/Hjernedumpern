# Bidrag

Takk for at du vurderer å bidra. Dette er et lite prosjekt — så prosessen
er enkel.

## Issues

Åpne et issue hvis du:
- Har funnet en feil
- Vil foreslå en endring
- Lurer på om noe burde fungere annerledes

## Pull requests

1. Fork repoet og lag en branch med beskrivende navn (`fix/icloud-deadlock`,
   `feature/ollama-backend`, osv.)
2. Hold endringer fokuserte — én logisk endring per PR
3. Beskriv hvorfor og hvordan i PR-meldingen, ikke bare hva
4. Test lokalt: kjør `pipeline.py --no-analyse` på en test-fil og verifiser
   at output ser fornuftig ut
5. Hold koden i samme stil som resten (norsk i dokumentasjon, engelsk er OK
   i variabelnavn der det føles naturlig)

## Områder hvor bidrag er spesielt velkomne

- Alternative analyse-backends (Ollama, OpenAI, lokale modeller)
- iOS-app-prototype
- Forbedret feilhåndtering for iCloud-edge-cases
- Tester (det finnes ingen i dag — alt utvikles mot ekte audio)

## Stil

- Python: 3.11+, type-hints der det hjelper, ingen unødvendige abstraksjoner
- Bash: `set -euo pipefail`, quote variabler
- Norsk i bruker-vendt tekst (logger, CLI-output, README)
- Engelsk er OK i kode-kommentarer hvis det er kortere/klarere

## Lisens på bidrag

Ved å åpne en PR aksepterer du at bidraget ditt utgis under [MIT](LICENSE).
