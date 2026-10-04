# Datamodell

Tabellene under er den logiske modellen. I praksis er hver av dem en JSON-fil
eller en mappe med én fil per enhet under `data/`.

## Oversikt

| Tabell | Innhold | Nøkkel |
|---|---|---|
| `mote` | Møte med dato, sted, utvalg og møtedokumenter | Møte-ID fra portalen |
| `behandling` | Én behandling av en sak i ett møte | Behandlings-ID fra portalen |
| `sak` | Den sammensatte saken på tvers av utvalg | Laveste behandlings-ID i kjeden |
| `dokument` | Saksframlegg og vedlegg, med URL og sjekksum | Dokument-ID fra portalen |
| `votering` | Én votering fra en protokoll | Løpenummer i behandlingen |
| `stemme` | Én representants stemme i én votering | Votering og representant |
| `utvalg` | Kommunestyret, formannskapet, hovedutvalgene og rådene | Utvalgs-ID fra portalen |
| `representant` | Navn, parti og kjente navnevarianter | Egen ID |
| `verv` | Hvem som sitter i hvilket utvalg, med rolle og periode | Representant, utvalg, fra-dato |
| `oppmote` | Hvem som faktisk møtte, og hvem en vara møtte for | Møte og representant |
| `parti` | Partikode, fullt navn og farge | Partikode |
| `analyse` | Sammendrag, tagger og utfall fra modellen | Sak og modellversjon |

## Sak er ikke det samme som behandling

Dette er den vanskeligste delen av modellen. Portalen behandler hver behandling
som en egen enhet med eget saksnummer. Samme sak kan ha fem saksnumre.

```
Sak: "Organisering av renovasjonstjenesten i Steinkjer kommune"
  behandling 8414   HPNM   PS 47/2026    13.10.2026
  behandling 8415   FS     PS 108/2026   15.10.2026
```

`AdditionalDmbHandlings` på hver behandling oppgir koblingene. Kjeden bygges med
disjunkte mengder: hver behandling starter som sin egen gruppe, og hver kobling
slår to grupper sammen. Resultatet er én gruppe per sak, uavhengig av hvilken
vei koblingene peker.

To ting må håndteres:

- Koblinger kan peke til behandlinger i fjoråret, som ikke er hentet. De lagres
  som kjente, men uhentede noder. For 2026 gjelder dette 7 behandlinger.
- En sak kan være behandlet, utsatt og tatt opp igjen, så kjeden sorteres på
  møtedato, ikke på ID.

## Status på en sak

Status er utledet, ikke hentet. Reglene står i `tolk/bygg_saker.py`:

| Status | Betingelse |
|---|---|
| Til kommunestyret | Neste steg i kjeden er et kommunestyremøte som ikke er holdt |
| Til behandling | Det finnes et møte i kjeden som ikke er holdt |
| Vedtatt i kommunestyret | Siste holdte steg er kommunestyret, og protokollen er publisert |
| Behandlet | Siste holdte steg har publisert protokoll |
| Unntatt offentlighet | Siste holdte steg har skjermet protokoll |
| Protokoll ikke publisert | Møtet ble holdt for over 30 dager siden, og protokollen er ikke publisert |
| Venter på protokoll | Møtet er holdt de siste 30 dagene, og protokollen er ikke publisert |

Grensen på 30 dager står i `VENTEGRENSE_DAGER`. I noen utvalg legges protokollen
aldri ut i portalen: Galleri Widegren har 0 av 23 behandlinger i 2026, og
arbeidsutvalget i Innherred regionråd 3 av 22. Uten grensen sto slike saker som
«venter» i månedsvis.

Fordeling for 2026 per 3.10.2026, politiske saker uten formaliteter: 121
behandlet, 49 vedtatt i kommunestyret, 42 protokoll ikke publisert, 32 til
behandling, 14 venter på protokoll, 8 unntatt offentlighet. Tallene kommer fra
`python -m tolk.bygg_saker 2026`.

## Voteringer

`votering` og `stemme` ligger samlet i `data/voteringer/<år>.json`, én post
per behandling med vedtak. Hver votering har en navneliste per standpunkt, og
partiet til hvert navn. Tolkes av `python -m tolk.bygg_voteringer` fra
saksprotokollene i `data/tekst/`.

| Form | Slik står den i protokollen | Antall i 2026 |
|---|---|---|
| For og mot | «For forslaget stemte 29: … Imot forslaget stemte 10: …» | 381 |
| Alternativ votering | «For forslag 1 stemte 4: … For forslag 2 stemte 3: …» | 61 |
| Enstemmig | «Forslag til vedtak enstemmig vedtatt.» Ingen navneliste | 45 |

I tillegg avgjøres 4 voteringer med ordførers eller leders dobbeltstemme, og
5 har «Ikke til stede» inne i navnelisten.

Feltet `tall_stemmer` er kontrollen fra ADR-002: antall navn stemmer med
oppgitt stemmetall for hvert standpunkt. En votering uten noe stemmetall har
ingen fasit og får også `tall_stemmer: false`. Slike rader publiseres ikke
før et menneske har sett på dem. I 2026 gjelder det ingen.

Hvem som stemte i en enstemmig votering, står ikke i protokollen. Det følger
av oppmøtet, som må hentes fra møteprotokollen (se under).

## Folkevalgte, verv og oppmøte

De fem tabellene om folkevalgte bærer mer enn de ser ut til.

**Et stemmetall uten nevner sier lite.** «29 mot 10» betyr noe annet når
kommunestyret er fulltallig enn når mange er borte.

**Varamedlemmer gjør statistikken feil hvis de ikke modelleres.** I møtet
16.09.2026 var 7 av de 39 frammøtte varamedlemmer:

| Vara | Parti | Møtte for |
|---|---|---|
| Knut Egil Sjøli | AP | May Britt Lagesen |
| Eli Djuvsland Rishaug | AP | Terje Tømmerås |
| Anders Schjefte | AP | Bjørg Helland |
| Eirik Forås | SP | Vegard Forbord |
| Stig Rønning | SP | Sigrun Modell |
| Johan Kristian Daling | SP | Morten Resve |
| Charlotte Guin | SV | Gjertrud Holand |

Uten `verv` og `oppmote` framstår disse 7 som lite aktive faste medlemmer, og de
7 de møtte for som representanter som aldri stemmer. Det er 14 personer feil
framstilt i ett eneste møte.

**Vervene endrer seg midt i perioden.** I 2026-dataene finnes både forlenget
permisjon fra verv, fritak og suppleringsvalg. Et verv må derfor ha fra- og
til-dato.

### Kilder til medlemskap

Portalens endepunkt `api/DmbMembers` gir trolig bare dagens medlemmer, ikke
historikk. Derfor to grep:

1. Medlemslisten hentes ved hver kjøring og lagres versjonert, slik at
   historikken bygges opp framover (`hent.hent_medlemmer`, til
   `data/raa/medlemmer/<dato>.json`, ny fil bare når noe er endret).
   Mobilnummer, e-post og kjønn fra portalen lagres ikke.
2. Oppmøtelisten i hver protokoll leses som selvstendig kilde. Den er datert,
   står i et dokument som ikke endres i ettertid, og oppgir både rolle og hvem
   en vara møtte for.

`python -m tolk.bygg_verv` setter de to sammen til `data/verv/<år>.json`, ett
verv per person og utvalg, og `data/utvalg/<år>.json` med utvalg og partier.
Portalen oppgir ikke når et verv begynte eller sluttet. Vervet får derfor de
datoene det er observert: hvilke medlemslister det står i
(`i_medlemslister`), og første og siste møte personen møtte (`forst_motte`,
`sist_motte`). Valg, fritak og permisjon står i sakene, men er ikke lest ut.

Status 2. oktober 2026: 21 utvalg og 602 verv. 750 av 754 oppmøterader finnes
i dagens medlemsliste for utvalget; de fire som mangler, har trolig gått ut
av utvalget i løpet av året.

**Varamedlemmer uten «varamedlem for».** Noen varamedlemmer står på
oppmøtelisten uten å møte for noen, for eksempel Tor Borgan i 9 møter i
formannskapet. De tar ingen plass i protokollen og telles for seg. Med den
regelen har ingen møter flere i plasser enn utvalget har faste plasser.

Oppmøtet ligger i `data/oppmote/<år>.json`, én post per møte, lest av
`python -m tolk.bygg_oppmote` fra alle 67 møteprotokoller i 2026: 754 rader,
136 av dem varamedlemmer. Kolonnen «Repr.» lagres som `repr`. Den er partiet,
men i interkommunale utvalg er den kommunen, og i rådene ofte «ANDRE».

### Kvalitetskontroll på kjøpet

Når `stemme` kontrolleres mot `oppmote`, fanges avvik automatisk. I 2026
gjelder det 97 voteringer i 6 møter, og alle står slik i protokollene:

| Møte | Avvik |
|---|---|
| FS 29.01 | Tor Borgan stemmer uten å stå på listen. May Britt Lagesen stemmer selv om en vara møtte for henne, og to voteringer får 13 stemmer med 12 frammøtte |
| FS 12.02 | May Britt Lagesen stemmer selv om en vara møtte for henne |
| KS 25.03 | Linn Kristine Sandseter stemmer i 21 voteringer uten å stå på listen |
| KS 20.05 | Gunnar Mikalsen Kvifte stemmer i 23 voteringer uten å stå på listen |
| FSKO 17.06 | Lill Marit Sandseter stemmer uten å stå på listen |
| KS 16.09 | Lena Hanem Bartnes (SP) stemmer i 42 voteringer uten å stå på listen |

Avvikene lagres per møte. En votering med avvik publiseres ikke før avviket
er vurdert (se under).

### Vurdering av avvik

Avvikene kan vurderes av et menneske eller en språkmodell. Vurderingen
avgjør bare om voteringen publiseres og med hvilken merknad. Navn og tall
gjengis alltid slik protokollen oppgir dem, og `vurdert_av` sier hvem som
har vurdert. Svaret står ofte ikke i dokumentene. Tjenesten venter ikke på
svar fra kommunen: da publiseres voteringen slik protokollen oppgir den,
med en merknad som sier hva som er usikkert, og protokollen gjelder. Se
ADR-015.

`python -m tolk.bygg_avvik` samler avvikene til `data/avvik/<år>.json`. Ett
avvik er én ting å vurdere og berører ofte mange voteringer, for eksempel
`oppmote:1285:lena-hanem-bartnes`, som gjelder 42 voteringer. I 2026 er det
10 avvik og 97 voteringer.

Vurderingen skrives for hånd i `data/vurderinger.json`:

```json
[{"avvik": "oppmote:1285:lena-hanem-bartnes",
  "avgjorelse": "publiser",
  "merknad": "Vises sammen med voteringen",
  "begrunnelse": "Hvorfor, med kilde",
  "vurdert_av": "Navn", "dato": "2026-10-02"}]
```

| `avgjorelse` | Virkning |
|---|---|
| `publiser` | Voteringene publiseres, med merknaden |
| `ikke_publiser` | Holdes tilbake |

Et avvik uten vurdering holdes tilbake. Nettstedet viser at voteringen
finnes, men ikke hvem som stemte hva, og sier hvorfor øverst på møtet.

Status 2. oktober 2026, vurdert av Claude Opus 5.5 etter beslutning fra
prosjekteier: 9 av 10 avvik publiseres med merknad. I dem er personen på
listen og personen i navnelisten fra samme parti, eller det mangler ett navn
på listen hos en som fast møter og stemmer, eller det er én stemme for mye i
en votering som endte 13–0. Partifordelingen og resultatet er da riktig. Kommunestyret 16.09.2026 venter på
kommunen: Lena Hanem Bartnes (SP) stemmer, og Anniken Bjørnes (R) står på
listen. De er fra ulike partier, og møtet hadde 11 voteringer på 20–19 eller
19–20. De 42 voteringene holdes tilbake. `tester.kontroller` stopper
publiseringen hvis en vurdering mangler begrunnelse, har en ukjent
avgjørelse, eller gjelder et avvik som ikke lenger finnes, for eksempel fordi
kommunen har rettet protokollen.

## Navnevarianter

Samme person skrives ulikt, også i samme dokument. Oppmøtelisten bruker ofte
fullt navn der navnelistene i voteringene ikke gjør det:

| Variant | Normalisert til | Hvor |
|---|---|---|
| Tor Andre Eide | Tor André Eide | Protokollen 16.09.2026 |
| Line M Nordkvelle | Line Mari Nordkvelle | Protokollen 16.09.2026 |
| Monika Luktvasslimo | Monika Skoglund Luktvasslimo | Oppmøtet i HPNM, hele 2026 |
| Enok Moe | Enok Askil Moe | Navnelistene i HOK, hele 2026 |
| Terje Langli | Terje Bjarte Langli | Navnelistene i KS, FSKO og FSB 17.06 |

Normaliseringen ligger i `tolk/navn.py`. Hver representant har en liste over
kjente varianter, slik at nye former kan legges til uten å endre koden.

Portalen kan også ha to person-ID-er for samme person: Monika Luktvasslimo i
HPNM har en annen ID enn Monika Skoglund Luktvasslimo i de andre utvalgene.
Profilene på nettstedet samles derfor på normalisert navn, som stemmene, ikke
på person-ID. Bygget stopper hvis to ulike navn gir samme profiladresse.

## Versjonering

Ingenting overskrives. Når en protokoll publiseres eller en sakstittel endres,
skrives en ny rad med tidsstempel, og den forrige markeres som avløst. Det gir
to ting: en tidslinje som viser når noe faktisk ble kjent, og mulighet til å se
hva nettsiden viste på et gitt tidspunkt.

Siden data ligger som JSON i git, gir historikken det samme på et grovere nivå
gratis.
