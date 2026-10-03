# Kommunelys

*Et klarere blikk på vedtakene.*

En uoffisiell og uavhengig oversikt over politiske saker i kommunen: hva som er
vedtatt, hva som er på vei, og hvordan hver representant stemte. Dekker i dag
Steinkjer kommune.

**Dette er ikke en tjeneste fra Steinkjer kommune eller noen annen kommune.**
Alt innhold kommer fra kommunens offentlige innsynsportal, og hver sak lenker
til originaldokumentet der.

## Hvorfor

Kommunens innsynsportal inneholder alt, men gir lite oversikt. En innbygger som
vil vite hva kommunestyret har bestemt, må lete seg gjennom møtelister, åpne
PDF-er på hundrevis av sider og selv finne ut hvilket utvalg som gjorde hva.

Denne tjenesten henter de samme dataene, setter en sak sammen på tvers av
utvalgene den har vært innom, oppsummerer den i klarspråk, og viser hvordan det
ble stemt.

## Slik virker det

```
Portalen  ->  Innhenting  ->  Lagring  ->  AI-analyse  ->  Bygg  ->  Nettsted
   JSON        ukentlig        JSON        kun nye       statisk     Pages
   og PDF      jobb            i git       saker         HTML
```

Hele kjeden kjøres av én GitHub Actions-arbeidsflyt på tidsplan. Data ligger som
JSON i dette repoet, så enhver endring er synlig som en diff.

## Dokumentasjon

| Dokument | Innhold |
|---|---|
| [docs/01-arkitektur.md](docs/01-arkitektur.md) | Hvordan delene henger sammen |
| [docs/02-api.md](docs/02-api.md) | Portalens API, endepunkter og dokumentadresser |
| [docs/03-datamodell.md](docs/03-datamodell.md) | Tabeller, saksidentitet, folkevalgte |
| [docs/04-beslutninger.md](docs/04-beslutninger.md) | Beslutningslogg med begrunnelser |
| [docs/05-plan.md](docs/05-plan.md) | Faser, åpne spørsmål og neste steg |
| [CLAUDE.md](CLAUDE.md) | Kontekst for Claude Code |

## Kom i gang

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r krav.txt
python -m hent.hent_moter 2026
python -m tolk.bygg_saker
```

Første kjøring henter rundt 120 møter og 600 saker og tar noen minutter.
Dokumentnedlasting er et eget steg og tar vesentlig lengre tid.

## Kildebruk og hensyn

- Maks ett kall i sekundet mot portalen, én tråd.
- Egen `User-Agent` med kontaktadresse.
- Skjermede saker og dokumenter hentes ikke og analyseres ikke.
- PDF-er lagres ikke i dette repoet. Leseren sendes til portalens egen adresse.

Portalens `robots.txt` ber automatiske verktøy holde seg unna. Det er derfor et
åpent punkt å avklare innhentingen med kommunen før tjenesten settes i drift.
Se [docs/04-beslutninger.md](docs/04-beslutninger.md), ADR-007.

## Lisens

Kode: MIT. Innhold hentet fra kommunens portal er kommunens, og gjengis med
lenke til kilden.
