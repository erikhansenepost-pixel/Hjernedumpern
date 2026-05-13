Du skal analysere en transkribert norsk lydopptak og returnere strukturert JSON.

Opptaket er typisk en monolog, samtale eller fri tankerekke. Innholdet kan være digressivt og hoppe mellom temaer — det er OK. Hold tonen nøktern og presis.

Din jobb er å:
1. Lese transkripsjonen
2. Rense opp og destillere til strukturerte felter
3. Returnere KUN gyldig JSON (ingen tekst rundt, ingen markdown)

JSON-schema du må følge eksakt:

```json
{
  "slug": "kort-kebab-case-beskrivelse",
  "sammendrag": "2-4 setninger som oppsummerer hovedinnhold og intensjon",
  "hovedtemaer": ["tema1", "tema2", "tema3"],
  "beslutninger": ["konkret beslutning som ble tatt", "..."],
  "action_items": [
    {"hva": "konkret handling", "eier": "navn eller rolle, ellers 'uavklart'", "når": "i dag|neste uke|Q2|uavklart"}
  ],
  "åpne_spørsmål": ["spørsmål som ble nevnt men ikke besvart", "..."],
  "personer_nevnt": ["navn + kort kontekst", "..."],
  "prosjekter_nevnt": ["prosjektnavn + kort kontekst", "..."],
  "stemning": "ett eller to ord som beskriver tone (reflekterende, frustrert, optimistisk, strategisk, ...)",
  "oppfølging_neste_gang": "én setning om hva som bør tas opp senere"
}
```

Retningslinjer:
- `slug`: 3-6 ord ASCII kebab-case som beskriver KJERNETEMAET (ikke metadata som "voicememo" eller "tale"). Eksempler: `prosjektidé-app-onboarding`, `tilbakemelding-design-revisjon`, `refleksjon-uka-som-gikk`. Bruk æ→ae, ø→o, å→aa. Beskriv innholdet — ikke navnet på opptaket eller stedet det ble tatt opp.
- Hvis et felt er tomt (ingen action items, ingen åpne spørsmål), returner tom liste `[]`
- Ikke finn på ting. Hvis taleren ikke eksplisitt nevnte en eier, skriv "uavklart"
- Personer som nevnes uten kontekst (f.eks. kun fornavn): ta med navnet slik det forekommer
- Vær nøktern — dette er ikke en salgstekst, det er en destillering
- Prosjekter/organisasjoner: bruk slik de blir uttalt
- Beslutninger er det som BLE BESTEMT, ikke det som vurderes

Transkripsjon:
---
{transcript}
---
