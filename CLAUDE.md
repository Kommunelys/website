# CLAUDE.md

Kontekst for Claude Code i dette repoet. Les denne først.

## Hva dette er

**Kommunelys**: en uoffisiell, offentlig nettside som gjør politiske saker i
kommunen forståelige for innbyggere. Data hentes fra kommunens innsynsportal,
tolkes med en språkmodell, og publiseres på nytt automatisk. Dekker i dag
Steinkjer kommune; navnet og malen er laget for flere (ADR-016).

Prosjektet er **ikke** laget av eller for Steinkjer kommune eller noen annen
kommune. Det må være utvetydig uoffisielt i all presentasjon.

## Status akkurat nå

| Del | Status |
|---|---|
| API-et til portalen | Kartlagt og dokumentert, se `docs/02-api.md` |
| Innhenting av møter og saker | Virker, kjørt mot hele 2026 |
| Tolkning av protokoll til stemmer | Virker. 42 av 42 i testmøtet, og alle 442 voteringer med navneliste i 2026 består tellekontrollen |
| Oppmøte | Virker. Lest fra alle 67 møteprotokoller i 2026; stemmene i 6 møter avviker fra oppmøtelisten og er flagget |
| Utvalg og verv | Virker. Medlemslistene hentes versjonert; vervene har observerte, ikke vedtatte, datoer |
| Saksgang på tvers av utvalg | Virker |
| Nedlasting av dokumenter | Virker. Tekst fra 724 av 726 saksframlegg og vedtak for 2026 er lagret (ADR-013) |
| AI-analyse | Kjører i arbeidsflyten (`claude-opus-5`, instruksjon v3). Sammendrag vises med kildelenke; de som ikke består kontrollen, holdes tilbake |
| Nettsted | Kommunelys. Bygges fra data, `kommuner/` og `bygg/mal/`, publisert på https://kommunelys.no/ med Steinkjer under `/steinkjer/` (GitHub Pages med eget domene og HTTPS; den gamle adressen på github.io sendes videre). 216 av 221 sammendrag vises. Profil for hver folkevalgt, bare fra egne data. Om-siden (`/om/`) er felles for alle kommunene, med metode, KI-bruk og en dekningstabell regnet ut ved hvert bygg; kommunen har fanen «Hvem bestemmer» for utvalg og saksgang |
| GitHub Actions | Virker. Kjører på tidsplan hver hverdag kl. 05:17 UTC, og kan startes for hånd |
| Drift og besøk | `/drift/` viser besøk (GoatCounter), status, AI-kostnad i kroner og en tabell over kjøringene (ADR-017). Bygges ved hver kjøring av Oppdater. Lenkes ikke fra nettstedet |

## Grunnregler du ikke skal bryte

1. **Lav takt mot portalen.** Maks ett kall i sekundet, én tråd. Portalens
   `robots.txt` ber automatiske verktøy holde seg unna; dette er ikke avklart
   med kommunen ennå. Se `docs/04-beslutninger.md`, ADR-007.
2. **Stemmetall tolkes aldri av en språkmodell.** Det gjøres med
   mønstergjenkjenning i `tolk/`, og antall navn kontrolleres alltid mot
   oppgitt stemmetall. Avvik skal stoppe raden, ikke rundes av. Om en
   votering med avvik likevel skal publiseres, kan vurderes av en modell,
   men vurderingen endrer aldri navn eller tall, og den merkes med
   `vurdert_av` (`data/vurderinger.json`, ADR-015).
3. **Skjermet informasjon lastes aldri ned og sendes aldri til en modell.**
   Portalen merker dette med `ProtocolRestricted`, `IsRestricted` og
   `AccessCodeId`. Respekter feltene i hvert ledd.
4. **Ingen PDF-er i git.** Bare uttrukket tekst. Originalen lenkes til i
   portalen.
5. **Hvert sammendrag skal ha lenke til kilden.** Uten kildelenke publiseres
   det ikke.
6. **Tekst tjenesten skriver selv, har ikke navn på privatpersoner.** Det
   gjelder sammendrag, merknader og forklaringer. Folkevalgte omtales bare i
   sin rolle. Sakstitler og forslagstekster fra protokollene vises uendret,
   også når de inneholder navn; de er offentlige dokumenter (prosjekteier,
   2.10.2026).

## Mappene

```
hent/      innhenting fra portalen (JSON og dokumenter)
tolk/      protokoll til voteringer, og saksgang på tvers av utvalg
analyser/  kall mot Claude med caching på sjekksum
bygg/      statisk nettsted; malen (HTML, CSS, JS, skrift, merke) i bygg/mal/
drift/     kjøreloggen, historikken fra git og Actions, og kostnadsanslaget til /drift/
lager/     all lesing og skriving av data/; resten av koden bruker bare denne
kommuner/  det som er særegent for hver kommune i visningen: navn, utvalg, organer
kommuner/kart/  forenklede kommunegrenser til kartet på forsiden (bygg.lag_kart)
data/raa/      rå API-svar, urørt. Slettes aldri. Unntak: medlemslistene
               lagres uten kontaktopplysninger (raa/medlemmer/)
data/moter/    normaliserte møter
data/saker/    normaliserte saker med saksgang
data/tekst/    tekst trukket ut av PDF og Word (møteprotokoller i tekst/moter/)
data/voteringer/  voteringer og stemmer fra saksprotokollene
data/oppmote/  oppmøte fra møteprotokollene, med avvik mot stemmene
data/utvalg/   utvalg og partier
data/verv/     verv per person og utvalg
data/avvik/    avvik som må vurderes før voteringene publiseres
data/vurderinger.json  avgjørelsene for avvikene, med begrunnelse og hvem som vurderte (ADR-015)
data/analyse/  sammendrag og tagger fra modellen
data/tillatte-navn.json  navn fra sakstitler som er vurdert og kan stå i et sammendrag
data/partisider.json  lenker til partienes egne sider, kontrollert for hånd
data/drift/kjoringer.json  tall fra hver kjøring: kall mot portalen, AI-analysen
docs/      arkitektur, API, datamodell, beslutninger, plan
tester/    kontroller som må passere før publisering
```

## Kommandoer

```bash
python -m hent.hent_moter 2026          # møter, saker, saksgang
python -m hent.hent_medlemmer 2026      # dagens medlemslister -> data/raa/medlemmer/
python -m hent.hent_dokumenter 2026     # PDF/Word -> data/tekst/ (rundt 25 min)
python -m hent.hent_dokumenter 2026 --mal  # bare måling -> data/maling-<år>.json
python -m tolk.bygg_saker               # saksgang og status -> data/saker/
python -m tolk.bygg_voteringer 2026     # voteringer fra vedtakene -> data/voteringer/
python -m tolk.bygg_oppmote 2026        # oppmøte og avvik mot stemmene -> data/oppmote/
python -m tolk.bygg_verv 2026           # utvalg, partier og verv -> data/utvalg/, data/verv/
python -m tolk.bygg_avvik 2026          # avvik som venter på vurdering -> data/avvik/
python -m tolk.tolk_protokoll <fil.txt> # voteringer fra én møteprotokoll
python -m tolk.saksframlegg <fil.txt>   # avsnittene i ett saksframlegg
python -m tester.kontroller             # alle kontroller
KOMMUNELYS_I_DAG=2026-10-04 python -m tolk.bygg_saker 2026  # tolk og bygg som om det var en annen dag
python -m bygg.bygg_nettsted 2026       # nettsted/ fra data og bygg/mal/
python -m bygg.lag_kart                 # kommunegrensene i Trøndelag -> kommuner/kart/ (sjelden)
python -m http.server 8765 --directory nettsted  # se nettstedet lokalt; kommunen under /steinkjer/
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
- **En votering har flere former enn «for» og «mot».** Ved alternativ
  votering står «For forslag 1 stemte 4: …» for hvert forslag. Enstemmige
  vedtak har ingen navneliste. «Ikke til stede (1): …» står inne i
  navnelisten, og noen ganger avgjøres det «med ordførers dobbeltstemme».
  En votering uten stemmetall har ingen fasit og skal stoppes, ikke
  registreres som 0 mot 0 (`tolk/tolk_protokoll.py`).
- **Feil API-adresse gir 200, ikke 404.** Portalen svarer med appens forside
  som HTML. Et svar som ikke er JSON, betyr feil adresse. Adressene i
  `docs/02-api.md` merket «Fra koden» er ikke testet, og to av dem var feil.
- **Medlemslisten har mobilnummer, e-post og kjønn.** Det lagres ikke
  (`hent/hent_medlemmer.py`).
- **Hoveddokumentet er ikke alltid et saksframlegg.** I referatsaker er det
  ofte et brev eller en protokoll fra andre. Bare dokumenter som starter med
  «SAKSFRAMLEGG», deles ved overskriftene (`tolk/saksframlegg.py`).
- **Navnevarianter.** Samme person skrives ulikt i samme dokument, for
  eksempel «Tor André Eide» og «Tor Andre Eide». Oppmøtelisten bruker ofte
  fullt navn der navnelistene i voteringene ikke gjør det, for eksempel
  «Enok Askil Moe» og «Enok Moe». Normaliseres i `tolk/navn.py`.
- **Oppmøtelisten og stemmene stemmer ikke alltid overens.** I 6 møter i
  2026 stemmer noen som ikke står på oppmøtelisten, eller det er flere
  stemmer enn frammøtte. Det står slik i protokollene. `tolk.bygg_oppmote`
  flagger dem; slike voteringer publiseres ikke før det finnes en vurdering
  i `data/vurderinger.json`. Sjekk bevisene med kode før du vurderer: hvem
  som står på listen uten å stemme, partiet deres, og vedtak om permisjon og
  fritak i sakene. Se `docs/03-datamodell.md`.
- **Dagens medlemsliste beskriver ikke plassene tidligere i året.** Permisjon,
  fritak og partibytte gjør at stemmer per parti ikke kan kontrolleres mot
  dagens antall plasser. SP har for eksempel én stemme mer enn dagens faste
  plasser i alle kommunestyremøtene i 2026.
- **GitHub Actions utløser ikke seg selv.** En commit med standardtokenet
  starter ikke andre arbeidsflyter. Derfor én arbeidsflyt med tre jobber.
- **Tall og datoer skrives på mange måter.** «kr. 550.000», «550 000» og
  «4100,-» er vanlige tall; «17.mars», «17 mars» og «17.03.2026» er samme
  dato. pdftotext klistrer sammen tabellceller («30000 304 980») og mister
  tankestreken i årsintervaller («20302040»). Første versjon av kontrollen
  holdt tilbake 53 av 221 sammendrag, nesten alle riktige. Endrer du
  kontrollen, så plant feil i ekte sammendrag og se at de fortsatt fanges.
- **Samme person kan ha to person-ID-er.** Monika Luktvasslimo i HPNM har en
  annen ID enn i de andre utvalgene. Profilene samles på normalisert navn.
- **Malen er felles for alle kommunene.** Et kommunenavn i `bygg/mal/` ville
  stått på de andre kommunenes sider også. Det hører hjemme i
  `kommuner/<kommune>.json` og leses fra `S.kommune`. `tester.kontroller`
  stopper hvis malen nevner en kommune.
- **Lys blå er pynt, ikke tekst.** `#60A5FA` har 2,4:1 mot papirhvit. Lenker,
  fokus og status bruker `--lenke` (ADR-016).
- **Driftssiden henter historikk fra git og GitHub-API-et.** Bygget trenger
  hele historikken (`fetch-depth: 0`) og `actions: read`. Lokalt brukes
  API-et uten nøkkel, med grense på 60 kall i timen. Svarer det ikke, viser
  siden bare endringene i dataene.
- **Om-siden er felles, «Hvem bestemmer» er kommunens.** Tekst om metode,
  kvalitet og personvern står i `bygg/mal/om.html` og gjelder alle kommunene.
  Hver påstand der skal kunne spores til kode, en ADR eller data. Tall i
  dekningstabellen regnes ut i bygget, og det som er kontrollert for hånd,
  står i `kontrollert_for_hand` i `kommuner/<kommune>.json`. Gamle lenker til
  `#om` sendes til `/om/`.
- **404-siden vises på alle adresser som ikke finnes.** Derfor må lenkene i
  `bygg/mal/404.html` være absolutte, med `{{base}}` foran. Roten kommer fra
  `NETTSTED_BASE`, som arbeidsflyten setter fra GitHub Pages (tom med eget
  domene, «/website» før det); lokalt er den «/». Etter bytte av domene må
  nettstedet bygges på nytt, ellers peker 404-siden til den gamle roten. Bygget stopper ved relative lenker.
  Andre feilkoder (500, 503) kan ikke tilpasses på GitHub Pages.
- **Ikke gjett adresser.** inp.no er ikke Industri- og næringspartiet, men en
  side om kredittkort. Lenker til partier og andre ligger i
  `data/partisider.json` og åpnes og sjekkes før de legges inn.

## Språk

Kode, variabelnavn og kommentarer på norsk der det gjelder domenet
(sak, møte, utvalg, behandling, votering). Teknisk kode kan være engelsk.
All tekst mot brukeren er på norsk bokmål, i klarspråk.
