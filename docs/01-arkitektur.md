# Arkitektur

Løsningen er en lineær kjede som kjører på tidsplan. Hvert steg leverer noe det
neste bruker, og hele kjeden kan kjøres om igjen fra bunnen uten tap av data.

```
  STEG                              RESULTAT
  ┌────────────────────────────┐
  │ Kommunens innsynsportal    │ ─ ─ ▸ møter, saker, vedtak og vedlegg
  │ åpent JSON-API og PDF      │
  └────────────┬───────────────┘
               ▼
  ┌────────────────────────────┐
  │ Innhenting, daglig jobb    │ ─ ─ ▸ kø med nye saker og nye protokoller
  │ henter bare det som er nytt│
  └────────────┬───────────────┘
               ▼
  ┌────────────────────────────┐
  │ Lagring                    │ ─ ─ ▸ én fil per sak, med hele historikken
  │ JSON i git, tekst av PDF   │
  └────────────┬───────────────┘
               ▼ bare nye og endrede saker
  ┌════════════════════════════┐
  ║ AI-analyse                 ║ ─ ─ ▸ sammendrag og tagger, med kildelenke
  ║ Claude leser framlegg+prot ║
  └════════════┬═══════════════┘
               ▼
  ┌────────────────────────────┐
  │ Bygg av nettsted           │ ─ ─ ▸ HTML-sider og en søkeindeks
  │ statiske sider fra data    │
  └────────────┬───────────────┘
               ▼
  ┌────────────────────────────┐
  │ Offentlig nettside         │ ─ ─ ▸ innbyggere, presse og politikere
  │ GitHub Pages, søk i klient │
  └────────────────────────────┘
```

Det avgjørende valget er at AI-steget bare ser nye og endrede saker. Det holder
kostnaden lav, gjør kjøringen rask, og lar et sammendrag stå urørt helt til
kilden faktisk endrer seg.

## Innhenting

Én jobb som kjører på tidsplan, henter JSON fra portalens API og laster ned de
dokumentene den ikke har fra før.

| Valg | Hva som gjelder |
|---|---|
| Frekvens | Én gang i døgnet. Protokoller dukker opp dager etter møtet, så oftere gir ikke ferskere data |
| Takt | Maks ett kall i sekundet, én tråd |
| Identifikasjon | Egen `User-Agent` med navn på tjenesten og kontaktadresse |
| Feilhåndtering | Tre forsøk med økende ventetid, så logges feilen og jobben fortsetter |
| Idempotens | Hele kjøringen kan gjentas uten sideeffekter |

### Slik oppdages endringer

Møtelisten for inneværende og neste år hentes alltid, fordi den er liten.
Deretter sammenlignes den mot forrige kjøring.

1. **Møter:** nye møte-ID-er, eller møter der dato, sted eller dokumentliste er
   endret.
2. **Saker:** sakslisten hentes for møter som er nye eller endret, og for alle
   møter holdt de siste 30 dagene, siden protokollen kommer etterskuddsvis.
3. **Dokumenter:** en PDF lastes ned én gang. Teksten lagres med en sjekksum, og
   dokumentet hoppes over ved neste kjøring.
4. **Kø:** alt som er nytt eller endret legges i en liste over hva AI-steget
   skal se på.

### Robusthet mot at portalen endrer seg

API-et er udokumentert. To tiltak demper risikoen. Hvert svar valideres mot et
forventet skjema, og jobben stopper med en tydelig feil i stedet for å skrive
halve data. Og rå JSON lagres urørt ved siden av de bearbeidede dataene, slik at
en endret tolkning kan kjøres om igjen på historikken uten å hente alt på nytt.

## Forberedelse av dokumenter

PDF-ene gjøres om til tekst før de når en språkmodell, og teksten lagres.

Dokumentene er maskinskapte, ikke skannede. Protokollen fra 16.09.2026 er laget
i Word, har innebygde skrifter og én illustrasjon, som er logoen. Hele
protokollen på 31 sider blir rundt 79 000 tegn, i størrelsesorden 23 000 tokens.
Sendt som PDF kommer hver side i tillegg som et bilde, og kostnaden mangedobles.

| Hensyn | Hvorfor tekst først |
|---|---|
| Stemmeuttrekket | Mønstergjenkjenning krever tegn, ikke en PDF |
| Gjenbruk | Konverteres én gang. Endres instruksjonen senere, er jobben gjort |
| Utsnitt | Bare vedtaksdelen kan sendes inn. En PDF må sendes hel |
| Søk | Nettsidens søkeindeks trenger den samme teksten uansett |

**Protokoller:** ren tekst med bevart kolonneoppsett (`pdftotext -layout`).
Oppmøtelisten er kolonnebasert, og Markdown-konvertering risikerer å ødelegge
nettopp den strukturen.

Noen møter har protokollene bare i Word. De leses med standardbiblioteket.

**Saksframlegg:** ren tekst uten `-layout`. De faste overskriftene i
kommunens mal, «… forslag til vedtak», «Saksopplysninger» og
«Saksvurderinger», står da på egne linjer, og teksten deles ved dem
(`tolk/saksframlegg.py`). Det gir det samme som Markdown var tenkt å gi:
muligheten til å skjære bort det uvesentlige.

Under 20 tegn per side betyr at dokumentet mangler tekstlag og trolig er
skannet. Teksten lagres da ikke, heller enn å gå videre som en tom tekst som ser
gyldig ut. Det brukes ingen tekstgjenkjenning; i 2026 gjaldt det ett dokument.

Se ADR-013 for målingen og verktøyvalget.

## AI-analyse

Kjører én gang per sak, ikke per kjøring. Resultatet lagres med modellversjon og
en sjekksum av kildeteksten.

**To ulike jobber, ikke én:**

| Jobb | Metode | Hvorfor |
|---|---|---|
| Stemmegivning fra protokoll | Mønstergjenkjenning i kode | Fast format, og en fasit å kontrollere mot |
| Sammendrag, tagger, utfall | Språkmodell | Krever forståelse, ikke mønstre |

Inn går sakstittel og saksgang, saksframlegget delt ved de faste overskriftene
(ADR-013) og uten avkorting, selve vedtaket fra hver saksprotokoll, og
resultatet av hver votering med hvilke partier som sto på hver side. Stemmetall
og navnelister sendes ikke inn; dem viser nettstedet fra koden (ADR-002).
Voteringer som er holdt tilbake (ADR-015), sendes ikke inn i det hele tatt.
`python -m analyser.analyser_saker 2026 --vis <sak>` skriver ut grunnlaget for
én sak.

Ut kommer et JSON-objekt som modellen er låst til med strukturert svar:
klarspråkstittel, sammendrag, hva saken betyr for innbyggeren, to til tre tagger
fra en fast liste, utfall, en setning om uenigheten, og om modellen er usikker.
Kildelenkene legges til av koden, ikke av modellen.

Modellen er `claude-opus-5`. Avslår modellens sikkerhetsfiltre en sak, kjøres
den på Anthropics anbefalte reservemodell (`fallbacks: "default"`), og modellen
som faktisk svarte, lagres. En feil i én sak hopper over saken, og høyst 25
saker sendes inn per kjøring.

Før et sammendrag publiseres, kontrollerer bygget at tallene i det finnes i
kildeteksten, og at det ikke står navn på privatpersoner fra sakstittelen
(folkevalgte unntas). Et sammendrag som ikke består, eller der modellen var
usikker, vises ikke, men stopper ikke resten av nettstedet. På nettstedet står
sammendraget med klarspråkstittel, lenker til dokumentene, merknaden «Skrevet
av KI» og en lenke for å melde fra om feil.

Faste tagger er viktig. Lar modellen finne på tagger selv, blir filtrene
ubrukelige etter et halvt år.

**Regler for sammendragene:**

- Bare innhold som står i dokumentene.
- Ingen vurdering av om vedtaket er godt eller dårlig.
- Navngitte politikere omtales bare med det de har gjort i møtet. Navn på
  privatpersoner tas ikke med.
- Ingen stemmetall eller hvem som stemte hva; uenigheten beskrives på
  partinivå.
- Er grunnlaget for tynt, settes `usikker`, og sammendraget utelates.

## Publisering

Statiske filer på GitHub Pages. Innholdet endrer seg én gang i døgnet, alle ser
det samme, og det finnes ingen innlogging.

| Egenskap | Valg |
|---|---|
| Sideoppbygging | Statiske HTML-filer, bygget etter hver innhenting |
| Data i siden | JSON ved siden av sidene, lastet ved behov |
| Søk | Søkeindeks bygget på forhånd, kjører i nettleseren |
| Adresser | Fast URL per sak og per møte |

Siden bygges i sin helhet hver gang, ikke stykkevis. Det tar sekunder ved denne
datamålestokken og fjerner en klasse feil der en gammel side blir liggende igjen
med utdatert innhold.

Saker som forsvinner fra portalen beholdes med en merknad om at de ikke lenger
ligger i kilden. Å fjerne dem i stillhet ville gjøre tjenesten mindre
etterrettelig enn kilden den bygger på.

## Kvalitetssikring

### Sporbarhet

Hvert sammendrag står sammen med en lenke til dokumentet det bygger på, og hvert
stemmetall med en lenke til protokollen. Sammendraget merkes med at det er
maskinskrevet, med dato og modellnavn.

### Kontroller som stopper en bygging

- Antall navn i en stemmeliste stemmer ikke med oppgitt stemmetall
- En representant stemmer både for og mot i samme votering
- En som stemmer står ikke på oppmøtelisten
- Et sammendrag inneholder tall eller navn som ikke finnes i kildeteksten
- En sak mangler lenke til kilde
- Antall saker faller mer enn 20 prosent fra forrige kjøring

Den fjerde er viktigst og vanskeligst. En enkel variant som fanger mye: trekk ut
alle tall og egennavn fra sammendraget og kontroller at de finnes i kilden.

### Skjermet informasjon

Portalen merker skjermede saker og dokumenter med egne felt. Disse respekteres i
hvert ledd: skjermede dokumenter lastes ikke ned, sendes aldri til en
språkmodell, og vises bare som sakstittel, eller som «unntatt offentlighet» når
tittelen også er skjermet. Reglene ligger som tester, ikke bare som rutine.

## Drift

Ett offentlig GitHub-repo. Actions kjører på tidsplan, Pages publiserer.

| Del | Hvor |
|---|---|
| Kjøring på tidsplan | GitHub Actions med cron |
| Kode | `hent/`, `tolk/`, `analyser/`, `bygg/` |
| Data | `data/` som JSON i repoet |
| Dokumenttekst | `data/tekst/` |
| PDF-er | Lagres ikke |
| Nettsted | GitHub Pages |
| API-nøkkel | Actions secret, `ANTHROPIC_API_KEY` |

**Fire ting før første kjøring.** Den første kjøringen laster ned rundt 1 600
dokumenter og tar nærmere en halvtime; den startes manuelt. En
`concurrency`-gruppe hindrer overlapp. Cron i Actions er ikke punktlig, noe som
ikke betyr noe her. Og GitHub kan slå av planlagte arbeidsflyter i repoer uten
aktivitet, så det bør kontrolleres at jobbens egne commits teller som aktivitet.

### Overvåking

Tre signaler: varsling hvis jobben ikke har kjørt vellykket på to døgn, varsling
hvis en kontroll stopper byggingen, og en statusside som viser når siste kjøring
var og hvor mange saker som ble oppdatert.

### Gjenoppretting

Git-historikken er sikkerhetskopien. Fordi rå API-svar lagres urørt, kan hele
den normaliserte modellen bygges opp igjen uten å hente noe fra portalen. Fordi
AI-resultatene er lagret med sjekksum av kildeteksten, må bare endrede saker
analyseres på nytt.

## Juss og etikk

Dette avgjør om tjenesten kan ligge offentlig, og bør avklares før det bygges
videre. Vurderingene under er utgangspunkt for en samtale med kommunen, ikke en
juridisk konklusjon.

**Tilgang til dataene.** Innholdet er offentlige saksdokumenter, men portalens
`robots.txt` ber automatiske verktøy holde seg unna. Den praktiske veien videre
er å spørre kommunen. Se ADR-007.

**Personopplysninger.** Stemmegivning og forslag fra folkevalgte er publisert av
kommunen som ledd i et offentlig verv, og å gjengi dem ryddig er kjernen i
innsyn. Tre grenser ligger fast:

- I tekst tjenesten skriver selv, omtales bare folkevalgte og ledende ansatte
  ved navn, og bare i sin rolle. Sakstitler og forslagstekster fra
  protokollene vises uendret, også når de inneholder navn på privatpersoner,
  fordi de er offentlige dokumenter (prosjekteier, 2.10.2026).
- Ingen profilering ut over det som følger direkte av protokollene.
- Siden skal kunne rettes, raskt.

**Avsender.** Tjenesten må være utvetydig uoffisiell: eget navn, egen profil,
ingen bruk av kommunevåpen, et domene som ikke ligner kommunens, og en tydelig
setning på hver side om hvem som står bak.
