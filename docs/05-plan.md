# Plan

Hver fase er en fungerende tjeneste i seg selv. Det er med vilje: da er det
mulig å stoppe etter fase 1 eller 2 og fortsatt sitte igjen med noe nyttig.

## Fase 1 — datagrunnlaget

Automatisk innhenting, database som JSON, protokolltolkning og et statisk
nettsted. **Ingen AI.**

Sammendrag mangler, men saksgang, status, møter, dokumentlenker og full
stemmegivning er på plass. Det er allerede et stykke foran det portalen gir i
dag, og det er her kvaliteten på datagrunnlaget må sitte før noe bygges oppå.

| Oppgave | Status |
|---|---|
| Kartlegge API-et | Ferdig |
| Hente møter, saker og saksgang for et år | Ferdig, kjørt mot 2026 |
| Bygge saksidentitet på tvers av utvalg | Ferdig |
| Utlede status på en sak | Ferdig |
| Tolke protokoll til voteringer og stemmer | Ferdig. 42 av 42 i testmøtet, 487 voteringer fra saksprotokollene i 2026 |
| Teste dokument-URL-ene | Ferdig, alle tre virker |
| Laste ned og måle hele dokumentsamlingen | Ferdig for saksframlegg og vedtak, se ADR-013 |
| Lagre tekst fra dokumentene | Ferdig for 2026, 724 av 726 |
| Modellere utvalg, verv og oppmøte | Ferdig for 2026. Vervene har observerte datoer, ikke vedtatte |
| Portere nettstedet fra prototype til repo | Ferdig. Bygges fra data, uten sammendrag |
| Sette opp GitHub Actions | Ferdig. Kjøres for hånd; tidsplanen er slått av |

## Fase 2 — AI på toppen

Sammendrag, klarspråkstitler og tagger, med sjekksum-basert caching og de
automatiske kontrollene.

Her flyttes tagging fra ordgjenkjenning til modellen. I en enkel variant basert på ord i tittelen
havner nesten en firedel av de politiske sakene uten tema, og flere får feil
tema fordi tittelen inneholder et ord som ligner.

Dette er fasen som gjør tjenesten forståelig for folk uten forkunnskaper.

| Oppgave | Status |
|---|---|
| Ny modell, feil håndtert per sak, tak per kjøring | Ferdig, testet uten API-kall |
| Strukturert grunnlag: saksframlegg i avsnitt, vedtak og partienes standpunkt, ingen stemmetall | Ferdig |
| Prompt og skjema for sammendrag | Første versjon (instruksjon v2, låst JSON-skjema) |
| Caching på sjekksum av kildetekst og promptversjon | Ferdig |
| Faste tagger, fastsatt én gang | Ferdig, 15 tagger |
| Prøvekjøring på rundt ti saker, lese resultatet | Ferdig. Fem feil funnet og rettet i instruksjon v3 |
| Kontroll av tall og navn i sammendraget | Ferdig. Tall og datoer må finnes i kilden, uansett skrivemåte; navn på privatpersoner fra tittelen holdes ute. 215 av 221 består, de 6 andre er merket usikre av modellen |
| Vise sammendrag på nettstedet med kildelenke | Ferdig |
| Knapp for å melde fra om feil | Ferdig, lenke til et nytt GitHub-issue. Krever GitHub-konto |
| Måle faktisk kostnad per møte | Tokenforbruket lagres per sak og summeres i `nettsted/<kommune>/status.json` |
| Temalisten: mangler tema for frivillighet og sosiale tjenester | Åpent |
| Profil for hver folkevalgt: verv, oppmøte, stemmer og forslag, bare fra egne data | Ferdig, 103 profiler |
| Kommunestyret på forsiden: velg et parti og se representantene, med lenke til partiet | Ferdig |
| Roligere utseende: systemskrift, tekstmeny, linjer i stedet for kort, ingen eksterne skrifter | Ferdig |
| Forsiden rundt tre spørsmål: hva skal skje, hva ble vedtatt, hva venter vi på. Ingen nøkkeltall eller grafer | Ferdig |
| «Venter på protokoll» i måneder: i noen utvalg legges protokollen aldri ut i portalen (Galleri Widegren 0 av 23, arbeidsutvalget i regionrådet 3 av 22). Statusen bør skille dette fra møter som nettopp er holdt | Ferdig. Egen status etter 30 dager, «Protokoll ikke publisert», og «Unntatt offentlighet» for skjermede |
| Driftsside: hva tjenesten har gjort teknisk, i klartekst, og besøk | Ferdig. `/drift/`, med besøk fra GoatCounter (ADR-017) |

## Fase 3 — mer enn én kommune

Datamodellen er allerede uavhengig av kommune, siden Elements brukes av mange.

| Oppgave |
|---|
| Flere kommuner i samme løsning |
| Varsling på tema eller geografisk område |
| Debatt fra møteopptak, se under |
| Politisk analyse, se under |
| Eierskap som ikke er én person på fritiden |

## To ideer som er utsatt

**Debatt fra møteopptak.** Protokollen forteller hva som ble vedtatt og hvem som
stemte hva, men ikke hvorfor. Feltet «Behandling» er tomt. En transkripsjon av
møteopptaket ville gitt argumentene.

Steinkjer24 ser ut til å ha sendt kommunestyremøter og lagt dem ut i opptak.
Eierskap til opptakene må avklares. Teknisk: lyd til tekst med en norsk modell,
stemmeskille for å knytte innlegg til person, og kobling mot riktig sak.
Største risiko er at et sitat tillegges feil person, så løsningen bør gjengi med
egne ord og alltid lenke til tidspunktet i opptaket.

**Politisk analyse.** En ukentlig tekst som forklarer hvem som samarbeider, hvor
flertallet ligger og hva som står på spill. Den skal analysere, ikke mene.
Reglene måtte være: bare påstander som kan dokumenteres i protokollene, ingen
gjetting om motiver, ingen vurdering av om et vedtak er godt, og samme mål og
tone for alle partier.

Grunnlaget finnes allerede. Fra møtet 16.09.2026, 33 omstridte voteringer:
Senterpartiet stemte likt med AP i 11 av 12 voteringer i NTE-saken, men med
Høyre-siden i 17 av 25 i skolesaken. Elleve voteringer endte 20–19 eller 19–20.

## Åpne spørsmål før fase 1 er ferdig

- [ ] Avklare med Steinkjer kommune om innhenting er greit, og hvem som er
      kontaktpunkt (ADR-007)
- [x] Teste de tre dokument-URL-ene med ett nedlastingskall hver
- [x] Laste ned hele dokumentsamlingen for 2026 og måle den: sidetall per
      dokumenttype, tegn per side, andel uten tekstlag, andel som ikke er PDF
      (ADR-012, avløst av ADR-013)
- [x] Bekrefte at protokolltolkningen virker på minst tre møter fra ulike
      utvalg, ikke bare kommunestyret. Alle 442 voteringer med navneliste i
      2026, fra 9 utvalg, består tellekontrollen
- [x] Vurdere de 10 avvikene i `data/avvik/2026.json`. 9 publiseres med
      merknad
- [ ] Få svar fra kommunen på hvem som møtte i kommunestyret 16.09.2026:
      Lena Hanem Bartnes (SP) eller Anniken Bjørnes (R). Til da holdes 42
      voteringer tilbake
- [ ] Bestemme hvem som eier tjenesten og står som avsender
- [x] Opprette det offentlige GitHub-repoet og legge inn API-nøkkelen som
      Actions secret
- [x] Velge navn som ikke kan forveksles med kommunens: Kommunelys (ADR-016)
- [x] Velge domene: kommunelys.no
- [ ] Sette opp kommunelys.no: DNS hos registraren og eget domene i
      Pages-innstillingene, med HTTPS
- [ ] Opprette en e-postadresse på kommunelys.no for feil og innspill, og
      sette den i `KONTAKT_EPOST` i `bygg/bygg_nettsted.py`. Til da vises
      bare GitHub på Om-siden

## Kjente mangler i nettstedet

- Sammendrag og tema er maskinskrevet. Seks saker mangler sammendrag fordi
  modellen merket dem som usikre.
- Kommunestyrets sammensetning er dagens, fra medlemslisten. Den viser ikke
  permisjoner og bytter tidligere i året.
- Saker fra 2025 som fortsatte i 2026, er bare delvis med.
- Voteringene fra kommunestyret 16.09.2026 er holdt tilbake til kommunen har
  svart på hvem som møtte.
- Hver votering viser typen (innstilling, forslag, endrings- eller tilleggsforslag),
  hvem som fremmet det, og hele forslagsteksten. Utdraget i listen er starten av
  teksten, ikke et sammendrag.
