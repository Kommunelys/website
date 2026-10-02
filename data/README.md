# data/

| Mappe | Innhold | Skrives av |
|---|---|---|
| `raa/<år>/` | Rå API-svar, urørt. Slettes aldri | `hent.hent_moter` |
| `moter/` | Normaliserte møter | `tolk.bygg_saker` |
| `saker/` | Saker med saksgang og status | `tolk.bygg_saker` |
| `tekst/` | Tekst trukket ut av PDF og Word, én fil per dokument-ID (vedtak: behandlings-ID) | `hent.hent_dokumenter` |
| `voteringer/` | Voteringer og stemmer per behandling, fra saksprotokollene | `tolk.bygg_voteringer` |
| `analyse/` | Sammendrag og tagger fra modellen | `analyser.analyser_saker` |
| `maling-<år>.json` | Størrelse, sidetall og tekstlag per dokument, uten tekst | `hent.hent_dokumenter --mal` |

`raa/2026/` er fra det første fullstendige uttrekket 1. oktober 2026. Det gjør
at hele kjeden kan kjøres og utvikles videre uten å røre portalen (ADR-007).

PDF-er lagres aldri her (ADR-005). Originalene lenkes til i portalen.
