# CLAUDE.md

Kontekst for Claude Code i dette repoet. Les denne først.

## Hva dette er

En uoffisiell, offentlig nettside som gjør politiske saker i Steinkjer kommune
forståelige for innbyggere. Data hentes fra kommunens innsynsportal, tolkes med
en språkmodell, og publiseres på nytt automatisk.

Prosjektet er **ikke** laget av eller for Steinkjer kommune. Det må være
utvetydig uoffisielt i all presentasjon.

## Status akkurat nå

| Del | Status |
|---|---|
| API-et til portalen | Kartlagt og dokumentert, se `docs/02-api.md` |
| Innhenting av møter og saker | Virker, kjørt mot hele 2026 |
| Tolkning av protokoll til stemmer | Virker, 42 av 42 voteringer riktig i testmøtet |
| Saksgang på tvers av utvalg | Virker |
| Nedlasting av dokumenter | URL-ene testet og 2026-samlingen målt. Verktøy valgt i ADR-013. Tekst ikke lagret ennå |
| AI-analyse | Ikke bygget. Skjelett i `analyser/` |
| Nettsted | Prototype finnes, se `docs/05-plan.md`. Ikke portet hit |
| GitHub Actions | Skrevet, ikke kjørt. Tidsplanen er slått av til ADR-007 er avklart |

## Grunnregler du ikke skal bryte

1. **Lav takt mot portalen.** Maks ett kall i sekundet, én tråd. Portalens
   `robots.txt` ber automatiske verktøy holde seg unna; dette er ikke avklart
   med kommunen ennå. Se `docs/04-beslutninger.md`, ADR-007.
2. **Stemmetall tolkes aldri av en språkmodell.** Det gjøres med
   mønstergjenkjenning i `tolk/`, og antall navn kontrolleres alltid mot
   oppgitt stemmetall. Avvik skal stoppe raden, ikke rundes av.
3. **Skjermet informasjon lastes aldri ned og sendes aldri til en modell.**
   Portalen merker dette med `ProtocolRestricted`, `IsRestricted` og
   `AccessCodeId`. Respekter feltene i hvert ledd.
4. **Ingen PDF-er i git.** Bare uttrukket tekst. Originalen lenkes til i
   portalen.
5. **Hvert sammendrag skal ha lenke til kilden.** Uten kildelenke publiseres
   det ikke.
6. **Navn på privatpersoner vises ikke**, selv når de står i en offentlig
   sakstittel. Folkevalgte omtales bare i sin rolle.

## Mappene

```
hent/      innhenting fra portalen (JSON og dokumenter)
tolk/      protokoll til voteringer, og saksgang på tvers av utvalg
analyser/  kall mot Claude med caching på sjekksum
bygg/      statisk nettsted
data/raa/      rå API-svar, urørt. Slettes aldri
data/moter/    normaliserte møter
data/saker/    normaliserte saker med saksgang
data/tekst/    tekst trukket ut av PDF
data/analyse/  sammendrag og tagger fra modellen
docs/      arkitektur, API, datamodell, beslutninger, plan
tester/    kontroller som må passere før publisering
```

## Kommandoer

```bash
python -m hent.hent_moter 2026          # møter, saker, saksgang
python -m hent.hent_dokumenter 2026     # PDF/Word -> data/tekst/ (rundt 25 min)
python -m hent.hent_dokumenter 2026 --mal  # bare måling -> data/maling-<år>.json
python -m tolk.bygg_saker               # saksgang og status -> data/saker/
python -m tolk.tolk_protokoll <fil.txt> # voteringer fra én protokolltekst
python -m tolk.saksframlegg <fil.txt>   # avsnittene i ett saksframlegg
python -m tester.kontroller             # alle kontroller
```

## Fallgruver vi allerede har gått i

- **En sak er ikke en behandling.** Samme sak får nytt saksnummer i hvert
  utvalg. `AdditionalDmbHandlings` binder dem sammen. Kjeden bygges med
  disjunkte mengder i `tolk/bygg_saker.py`.
- **Møteinnkallingen er alle saksframleggene limt sammen.** Den for
  kommunestyret 16.09.2026 er over 350 sider. Den skal aldri sendes til
  analyse. Bruk saksframlegget for den enkelte saken.
- **Tomme felter betyr skjermet.** `Title` kan være `null`. Kode som antar
  streng vil krasje; det skjedde i første versjon av innhentingen.
- **`pdftotext -layout` er nødvendig, ikke valgfritt.** Oppmøtelisten i
  protokollen er kolonnebasert. Uten `-layout` mister du koblingen mellom
  navn, funksjon og «varamedlem for».
- **`pdftotext` må være poppler, ikke xpdf.** Den som følger med Git for
  Windows er xpdf: den skriver Latin-1, så æøå blir ødelagt, og den mangler
  `pdfinfo`. `hent.hent_dokumenter` stopper hvis den finner xpdf (ADR-013).
- **Ikke alle vedtak er PDF.** Noen møter har saksprotokollene bare i Word,
  blant annet HPNM og KTU 09.06.2026. De har voteringene og må tas med.
- **Hoveddokumentet er ikke alltid et saksframlegg.** I referatsaker er det
  ofte et brev eller en protokoll fra andre. Bare dokumenter som starter med
  «SAKSFRAMLEGG», deles ved overskriftene (`tolk/saksframlegg.py`).
- **Navnevarianter.** Samme person skrives ulikt i samme dokument, for
  eksempel «Tor André Eide» og «Tor Andre Eide». Normaliseres i
  `tolk/navn.py`.
- **GitHub Actions utløser ikke seg selv.** En commit med standardtokenet
  starter ikke andre arbeidsflyter. Derfor én arbeidsflyt med tre jobber.

## Språk

Kode, variabelnavn og kommentarer på norsk der det gjelder domenet
(sak, møte, utvalg, behandling, votering). Teknisk kode kan være engelsk.
All tekst mot brukeren er på norsk bokmål, i klarspråk.
