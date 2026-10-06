# data/

**Står stille fra 6.10.2026.** Dataene ligger nå i en database (Postgres i
Supabase, ADR-019), og arbeidsflyten committer ikke hit lenger. Mappen viser
dataene slik de var ved byttet, og kan leses med `KOMMUNELYS_LAGER=json`.
Unntak: `tillatte-navn.json` og `partisider.json` vedlikeholdes fortsatt her
for hånd og speiles inn i databasen ved hver kjøring. `vurderinger.json` står
stille fra 6.10.2026; vurderingene registreres i databasen (ADR-020).

| Mappe | Innhold | Skrives av |
|---|---|---|
| `raa/<år>/` | Rå API-svar, urørt. Slettes aldri | `hent.hent_moter` |
| `moter/` | Normaliserte møter | `tolk.bygg_saker` |
| `saker/` | Saker med saksgang og status | `tolk.bygg_saker` |
| `tekst/` | Tekst trukket ut av PDF og Word, én fil per dokument-ID (vedtak: behandlings-ID) | `hent.hent_dokumenter` |
| `tekst/moter/` | Tekst fra møteprotokollene, én fil per møte-ID | `hent.hent_dokumenter` |
| `voteringer/` | Voteringer og stemmer per behandling, fra saksprotokollene | `tolk.bygg_voteringer` |
| `oppmote/` | Oppmøte per møte, med avvik mot stemmene | `tolk.bygg_oppmote` |
| `avvik/` | Avvik som må vurderes før voteringene publiseres | `tolk.bygg_avvik` |
| `vurderinger.json` | Avgjørelsene for avvikene fram til 6.10.2026. Nå i databasen (ADR-020) | – |
| `raa/medlemmer/` | Dagens medlemslister, én fil per endring, uten kontaktopplysninger | `hent.hent_medlemmer` |
| `utvalg/` | Utvalg med antall plasser, og partiene | `tolk.bygg_verv` |
| `verv/` | Ett verv per person og utvalg, med observerte datoer | `tolk.bygg_verv` |
| `analyse/` | Sammendrag og tagger fra modellen | `analyser.analyser_saker` |
| `maling-<år>.json` | Størrelse, sidetall og tekstlag per dokument, uten tekst | `hent.hent_dokumenter --mal` |

`raa/2026/` er fra det første fullstendige uttrekket 1. oktober 2026. Det gjør
at hele kjeden kan kjøres og utvikles videre uten å røre portalen (ADR-007).

PDF-er lagres aldri her (ADR-005). Originalene lenkes til i portalen.
