# Beslutningslogg

Hver beslutning med begrunnelse og konsekvens. Nyeste nederst. En beslutning
endres ikke; den erstattes av en ny som sier at den forrige er avløst.

Status: **Besluttet**, **Foreløpig** (gjelder til noe annet er bestemt),
**Åpen** (må avklares).

---

## ADR-001 — Hente data fra portalens JSON-API, ikke skrape HTML

**Besluttet.**

Nettsiden er en React-app som henter alt fra et åpent JSON-API uten innlogging.
API-et er udokumentert, men stabilt i form og langt enklere å lese enn generert
HTML.

**Konsekvens:** Ingen HTML-parsing. Til gjengjeld kan API-et endres uten varsel,
så hvert svar valideres mot et forventet skjema, og rå svar lagres urørt slik at
en endret tolkning kan kjøres om igjen på historikken.

---

## ADR-002 — Stemmegivning tolkes med kode, ikke med språkmodell

**Besluttet.**

Protokollteksten følger et fast mønster: hvem som fremmet forslaget, hvem som
stemte for, hvem som stemte mot, og resultatet. Mønstergjenkjenning gir samme
svar hver gang, og antall navn kan kontrolleres mot det oppgitte stemmetallet.

Testet på kommunestyremøtet 16.09.2026: 42 av 42 voteringer riktig, alle
navnelister stemte med oppgitt tall.

**Konsekvens:** Et stemmetall som varierer mellom kjøringer er ubrukelig, og her
finnes en fasit i teksten. Språkmodellen brukes bare der det ikke finnes noen
fasit, altså til sammendrag og tagger.

---

## ADR-003 — En sak settes sammen på tvers av utvalg

**Besluttet.**

Portalen behandler hver behandling som en egen enhet med eget saksnummer. Samme
sak kan ha fem saksnumre. `AdditionalDmbHandlings` oppgir koblingene.

Kjeden bygges med disjunkte mengder: hver behandling starter som sin egen
gruppe, og hver kobling slår to grupper sammen.

**Konsekvens:** Én linje per sak i grensesnittet, uavhengig av hvor mange
utvalg den har vært innom. Koblinger som peker til fjoråret lagres som kjente,
men uhentede noder.

---

## ADR-004 — JSON i git, ikke en databasefil

**Besluttet.** Erstatter en tidligere antagelse om SQLite.

En SQLite-fil er binær og endres ved hver kjøring. Den ville vokst
git-historikken og skjult nettopp de endringene som er poenget å kunne se.

**Konsekvens:** Data ligger som JSON under `data/`. Hver endring i en sak er
synlig som en diff. Trengs SQL senere, bygges en database fra JSON ved behov.
Datamengden, rundt 600 saker i året, gjør dette uproblematisk.

---

## ADR-005 — PDF-er lagres ikke

**Besluttet.**

Rundt 1 600 dokumenter i året, nesten alle PDF. Git håndterer binærfiler dårlig,
og det er ingen grunn til å hoste kopier av dokumenter kommunen allerede
publiserer.

**Konsekvens:** Teksten trekkes ut én gang og lagres under `data/tekst/`.
Originalen lenkes til i portalen. Dette fjerner samtidig spørsmålet om
videreformidling av kommunens dokumenter. Må et dokument tolkes på nytt med et
bedre verktøy, lastes det ned igjen.

---

## ADR-006 — Analyser alltid det minste dokumentet som inneholder svaret

**Besluttet.**

Dokumentsamlingen overlapper med seg selv. Møteinnkallingen er alle
saksframleggene limt sammen; den for kommunestyret 16.09.2026 er over 350 sider.
Møteprotokollen er alle saksprotokollene samlet.

| Dokument | Antall i 2026 | Rolle |
|---|---|---|
| Saksframlegg, enkeltvis | 351 | Grunnlag for sammendrag av én sak |
| Saksprotokoll, enkeltvis | 368 | Grunnlag for vedtak og stemmer |
| Møteprotokoll | 67 | Leses for oppmøtelisten |
| Møteinnkalling | 91 | Lenkes til, sendes aldri til analyse |
| Vedlegg | 725 | Hentes ved behov, ikke som rutine |

**Konsekvens:** Innkallingen blir noe leseren kan åpne, ikke noe systemet
betaler for å lese.

---

## ADR-007 — Innhenting må avklares med kommunen

**Åpen.**

Innholdet er offentlige saksdokumenter publisert for innsyn, men portalens
`robots.txt` ber automatiske verktøy holde seg unna. Det er ikke et rettslig
forbud, men et uttrykt ønske.

**Konsekvens inntil avklart:** Innhentingen oppfører seg som en god gjest, med
maks ett kall i sekundet, én tråd, egen `User-Agent` med kontaktadresse, og
umiddelbar stopp hvis kommunen ber om det. Tjenesten settes ikke i offentlig
drift før spørsmålet er stilt.

Tidsplanen ble slått på av prosjekteier 4.10.2026, mens spørsmålet fortsatt er
åpent: én kjøring hver hverdag, med takten over. Ber kommunen om stopp,
kommenteres `schedule` ut i `.github/workflows/oppdater.yml`.

---

## ADR-008 — Datamodellen skal inneholde folkevalgte, verv og oppmøte

**Besluttet.**

Uten medlemskap og oppmøte kan ikke stemmetall tolkes, og politikersider blir
direkte feil. I møtet 16.09.2026 var 7 av de 39 frammøtte varamedlemmer. Uten
modellering framstår de 7 som lite aktive faste medlemmer, og de 7 de møtte for
som representanter som aldri stemmer.

**Konsekvens:** Fire tabeller kommer til: `utvalg`, `verv`, `oppmote`, `parti`.
Verv har fra- og til-dato, fordi permisjon, fritak og suppleringsvalg skjer midt
i perioden. Medlemslisten hentes ved hver kjøring og lagres versjonert, siden
portalens endepunkt trolig bare gir dagens medlemmer. Oppmøtelisten i hver
protokoll leses som selvstendig, datert kilde.

---

## ADR-009 — GitHub som plattform

**Besluttet.**

Ett offentlig repo med kode, data og nettsted. GitHub Actions kjører på
tidsplan, GitHub Pages publiserer. Gratis for offentlig repo.

Avveid mot Azure med Functions, Blob Storage og Static Web Apps, som ville
kostet i størrelsesorden 50 til 150 kroner i måneden og passet bedre dersom en
kommune eller et interkommunalt samarbeid skulle eie løsningen.

**Konsekvens:** Hver endring i datagrunnlaget er synlig som en diff, noe som er
en egenskap og ikke en bivirkning for en tjeneste som skal være etterprøvbar.
Flyttes eierskapet senere, er Azure veien videre.

---

## ADR-010 — Én arbeidsflyt, ikke tre

**Besluttet.**

En commit som GitHub Actions dytter med standardtokenet utløser ikke andre
arbeidsflyter. Kjedes innhenting, analyse og bygging sammen med push-utløsere,
stopper det stille etter første steg.

**Konsekvens:** `.github/workflows/oppdater.yml` har tre jobber som kjører etter
hverandre i samme arbeidsflyt. En `concurrency`-gruppe hindrer overlapp.

---

## ADR-011 — Sammendrag publiseres uten forhåndsgodkjenning

**Foreløpig.**

En løsning som krever menneskelig gjennomgang før hver publisering stopper i
praksis opp etter noen uker.

**Konsekvens:** Innsatsen legges to andre steder. Saker som modellen flagger som
usikre får ingen publisert sammendragstekst, bare tittel og lenke til
dokumentet. Og hver sak har en knapp for å melde fra om feil. Dette revurderes
hvis feilraten viser seg høy i fase 2.

---

## ADR-012 — Valg av konverteringsverktøy utsettes

**Åpen.**

Protokoller trenger ren tekst med bevart kolonneoppsett, fordi oppmøtelisten er
kolonnebasert. Saksframlegg tjener på Markdown, fordi faste overskrifter gjør
det mulig å skjære bort det uvesentlige. Men samlingen er ikke målt ennå.

**Konsekvens:** `pdftotext -layout` brukes for protokoller, der det er bevist at
det virker. Valget for saksframlegg og vedlegg tas etter at hele samlingen for
2026 er lastet ned og målt på sidetall, tegn per side, andel uten tekstlag og
andel som ikke er PDF.

---

## ADR-013 — Konverteringsverktøy for saksframlegg og protokoller

**Besluttet.** Avløser ADR-012.

Samlingen for 2026 ble lastet ned og målt 2. oktober 2026 med
`python -m hent.hent_dokumenter 2026 --mal`. Vedlegg er ikke målt (ADR-006).

| | Hoveddokument | Saksprotokoll |
|---|---|---|
| Målt | 350 av 351 (1 ga 404) | 375 |
| Ikke PDF | 0 | 22 Word-filer (DOCX) |
| Sider | 1 268, median 3, maks 24 | 591, median 1, maks 19 |
| Tegn per side, median | 1 440 | 840 |
| Uten tekstlag | 1, skannet | 0 |

Fire funn avgjør valget:

1. **Nesten alt er digitalt.** Alle hoveddokumentene er arkiv-PDF (RA-PDF), og
   bare ett dokument i hele samlingen er skannet.
2. **Noen møter har protokollene bare i Word.** Alle vedtak fra HPNM og KTU
   09.06.2026 er blant de 22. Stikkprøven hadde voteringene på vanlig måte, så
   de kan ikke hoppes over.
3. **De faste overskriftene står på egne linjer i ren tekst.** Testet på 16
   hoveddokumenter fra 15 utvalg. 14 av dem er saksframlegg etter kommunens mal
   og starter med «SAKSFRAMLEGG». Alle 14 har «… forslag til vedtak» (eller
   «innstilling») og «Saksvurderinger», i den rekkefølgen. 13 av 14 har også
   «Saksopplysninger».
4. **Andre overskrifter kan ikke leses sikkert ut av skrifttypen.** Med
   skriftstørrelse og fet skrift (`pdftohtml -xml`) ble også tabellhoder og hele
   avsnitt i fet skrift til overskrifter.

Hoveddokumentet er heller ikke alltid et saksframlegg. 126 av 351 hører til
referatsaker, der hoveddokumentet ofte er et brev eller en protokoll fra andre.
Begge referatsakene i testen var slike.

**Konsekvens:**

| Dokument | Verktøy |
|---|---|
| Saksprotokoll i PDF | `pdftotext -layout` |
| Saksprotokoll i Word | `word/document.xml` leses med `zipfile` og `xml.etree` |
| Saksframlegg etter malen | `pdftotext` uten `-layout`, delt ved de faste overskriftene |
| Annet hoveddokument | `pdftotext` uten `-layout`, ikke delt |
| Uten tekstlag | Ingen OCR. Saken får lenke, ikke sammendrag |

- Markdown droppes. Gevinsten ADR-012 så for seg, å skjære bort det
  uvesentlige, kommer fra de faste overskriftene, og de finnes i ren tekst.
- Poppler er det eneste PDF-verktøyet, og det kommer ingen nye
  Python-avhengigheter. `pymupdf4llm` er AGPL og ville vært en motor nummer to
  for PDF. `docling` er tung og laget for skannede og rotete dokumenter, som vi
  nesten ikke har.
- `pdftotext` fra Git for Windows er xpdf, ikke poppler. Den skriver Latin-1 og
  mangler `pdfinfo`, og skal ikke brukes.
- Grensen for manglende tekstlag senkes fra 100 til 20 tegn per side. Det
  skannede dokumentet har 1 tegn per side, de korteste protokollene 82.
- Vedlegg behandles som «annet hoveddokument» når de trengs, og JPEG hoppes
  over. Valget vurderes på nytt hvis vedleggene viser seg å være annerledes.

---

## ADR-014 — Kontaktopplysninger fra medlemslistene lagres ikke

**Besluttet.** Unntak fra ADR-001.

Medlemslisten fra portalen (`api/DmbMembers/GetByDmbBoard`) har mobilnummer,
e-post og kjønn for hver folkevalgt, i tillegg til navn, parti og funksjon.
ADR-001 sier at rå svar lagres urørt, og repoet er offentlig.

Opplysningene er publisert av kommunen, men tjenesten trenger dem ikke, og
folkevalgte omtales bare i sin rolle (CLAUDE.md regel 6). Et offentlig repo med
alle mobilnumrene samlet og versjonert ville vært en ny og mer søkbar kopi.

**Konsekvens:** `hent.hent_medlemmer` lagrer bare person-ID, navn, funksjon,
parti og partinavn. Alle felter som tolkes, beholdes, så hensikten med
ADR-001, å kunne tolke på nytt, er ivaretatt. Trengs et annet felt senere,
hentes det fra da av; eldre versjoner av listen har det ikke.

---

## ADR-015 — Avvik i voteringer kan vurderes av en språkmodell

**Besluttet.** Supplerer ADR-002.

ADR-002 holder stemmetall unna språkmodellen, fordi protokollen har en fasit
å kontrollere mot. Men noen ganger motsier protokollen seg selv: noen stemmer
uten å stå på oppmøtelisten, eller det er flere stemmer enn frammøtte. Da
finnes det ingen fasit, og voteringen stoppes. I 2026 gjaldt det 97
voteringer, samlet i 10 avvik.

Prosjekteier har bestemt at avvikene kan vurderes av en språkmodell i stedet
for et menneske, siden tjenesten uansett bygges og drives med AI.

**Konsekvens:**

- Vurderingen avgjør bare om voteringen publiseres og med hvilken merknad.
  Navn og tall gjengis alltid slik protokollen oppgir dem. Modellen retter
  aldri en navneliste.
- Bevisene hentes ut med kode før vurderingen: hvem som står på listen uten
  å stemme, partiet deres, vervene og vedtak om permisjon og fritak. Hver
  påstand i en begrunnelse skal kunne etterprøves i dataene.
- Hver vurdering står i `data/vurderinger.json` med begrunnelse og
  `vurdert_av`, med modell og versjon. `tester.kontroller` avviser
  vurderinger uten dem.
- Er det uklart hvem som møtte, og de mulige personene er fra ulike partier,
  er avgjørelsen `venter_paa_kommunen`. Da er partifordelingen usikker, og
  den er det tjenesten skal vise.
- Første vurdering ble gjort 2. oktober 2026 av Claude Opus 5.5: 9 av 10
  avvik publiseres med merknad, og kommunestyret 16.09.2026 venter på
  kommunen. En påstand i første utkast var feil, om en permisjon, og ble
  fanget fordi den ble sjekket mot sakene før vurderingen ble lagret.

---

## ADR-016 — Navn og profil: Kommunelys, ett navn for alle kommunene

**Besluttet.** Prosjekteier, 3.10.2026.

Tjenesten het «Steinkjer i klartekst», og kommunenavnet sto i malen. Samme
teknikk kan brukes for andre kommuner som har samme innsynsportal, så navnet
må tåle å bli flere.

Nettstedet heter **Kommunelys**, med slagordet «Et klarere blikk på
vedtakene». Navnet står alene, ikke som «Kommunelys Steinkjer»: kommunen er
innholdet, ikke merkevaren.

**Konsekvens:**

- Roten er Kommunelys-forsiden med en liste over kommunene. Hver kommune har
  sin egen mappe, Steinkjer under `/steinkjer/`. Gamle lenker (`/#saker`,
  `/#person/…`) sendes dit.
- Malen i `bygg/mal/` nevner ingen kommune. Det som er særegent for kommunen,
  står i `kommuner/<kommune>.json`. `tester.kontroller` stopper hvis malen
  nevner en kommune, og bygget stopper hvis en kommuneside mangler
  «Ikke laget av <kommune> kommune».
- Merket er et åpent vindu: en blekkramme og en lys blå rute, i SVG. Ingen
  kommunevåpen, skjold eller foto av steder.
- Fargene er blekk og papir med lys blå (`#60A5FA`) som pynt. Lys blå har bare
  2,4:1 mot papirhvit og brukes aldri til tekst eller fokus i lys modus; lenker,
  fokus og status bruker samme blåtone mørkere (`#1F5FAD`, 6:1). Blått ligger
  nær Høyres farge, så det brukes ikke til store flater i dataene.
- Skriften er Inter (OFL), lagt lokalt i `bygg/mal/fonter/`. Det holder
  regelen fra fase 2 om ingen eksterne skrifter eller skript. Unntaket er
  besøkstellingen (ADR-017).
- Til dataene ligger per kommune (fase 3), hører `data/` til Steinkjer, og
  bygget krever nøyaktig én kommune. Instruksjonen til analysen nevner
  fortsatt Steinkjer; den endres når flere kommuner kommer, fordi en endring
  utløser ny analyse av alle sakene.
- Domenet blir `kommunelys.no` (prosjekteier, 3.10.2026). Lenkene på
  nettstedet er relative, så det virker både under `/website/` og på
  roten av domenet. Med publisering fra Actions settes domenet i
  Pages-innstillingene; en `CNAME`-fil i nettstedet brukes ikke. Domenet
  ble tatt i bruk 4.10.2026, med HTTPS for både `kommunelys.no` og
  `www.kommunelys.no`.

---

## ADR-017 — Besøk telles med GoatCounter, og driften vises på /drift/

**Besluttet.** Prosjekteier, 4.10.2026.

Prosjekteier trenger å se hva tjenesten har gjort: kjøringer, nye saker,
innhenting, analyse og besøk. GitHub Pages har ingen besøkslogg, og det finnes
ingen server å logge på. Repoet er offentlig, så en lukket admin-side ville
bare skjult det som allerede kan leses i Actions og git.

**Konsekvens:**

- Sidevisninger telles med GoatCounter (`kommunelys.goatcounter.com`). Det er
  det eneste skriptet som lastes fra et annet domene. GoatCounter bruker ikke
  informasjonskapsler og lagrer ikke IP-adresser, bare sammenlagte tall. Det
  står under «Personvern» på Om-siden.
- Kommunesidene viser fanene etter `#`. Hver visning telles derfor med sti og
  fane (`/steinkjer/#saker`). Søketeksten står ikke i adressen og sendes ikke.
- Kontoen hos GoatCounter opprettes og eies av prosjekteier. Skal tellingen av, settes
  `GOATCOUNTER = ""` i `bygg/bygg_nettsted.py`.
- `/drift/` er offentlig, men lenkes ikke fra resten av nettstedet og har
  `noindex`. Den viser bare tall og offentlige sakstitler. Besøkstallene hentes
  i nettleseren fra GoatCounter, og det krever innstillingen «Allow adding
  visitor counts on your website».
- Kostnaden for AI-analysen vises i kroner: tokens ganget med listeprisen i
  `drift/kostnad.py` og kursen fra Norges Bank. Uten rabatt for caching og
  uten mva, så det er et anslag. Prisene må oppdateres når modellen byttes.
- Innhentingen teller kallene mot portalen og lagrer tallet i
  `data/drift/kjoringer.json`. Da kan vi vise at takten fra ADR-007 holdes.
