---
name: ny-kommune
description: Sjekkliste for å legge inn en ny kommune i Kommunelys, fra å finne kilden i innsynsportalen til publisering. Bruk når prosjekteier vil legge inn, onboarde eller ta med en ny kommune, prøve en kommune, eller spør hva som skal til for å få en kommune på nettstedet.
---

# Ny kommune i Kommunelys

Les først `CLAUDE.md` (avsnittet «Flere kommuner»), ADR-021 og ADR-022 i
`docs/04-beslutninger.md`. Alt under bygger på dem.

## Grunnreglene gjelder like mye for en ny kommune

- **Lav takt:** ett kall i sekundet, samlet for verten. Hent aldri for en ny
  kommune mens Oppdater kjører; de deler `prod01.elementscloud.no`.
- **Ingen språkmodell på stemmetall.** Kontrollen av stemmetall er lik for
  alle kommuner.
- **Skjermet informasjon** lastes aldri ned.
- **Ingen PDF-er i git.**
- **Kildelenke** på alle sammendrag.
- **Ingen navn på privatpersoner** i tekst vi skriver.
- **Ikke gjett adresser.** Tenant, database og partilenker åpnes og sjekkes.
- **Avklaring med kommunen:** nye kommuner trenger ingen egen avklaring
  (prosjekteier, 7.10.2026).

## Stoppunkter: spør prosjekteier før du går videre

Merket **STOPP** under. Vis da hva du har funnet, med tall, og vent på svar.

---

## 1. Finn kommunen og kilden

1. Skaff navn, kommunenummer (fire sifre) og slug, for eksempel `snasa` (bare
   `a–z0–9-`).
2. **Finn innsynsportalen.** Bruker kommunen Elements, er adressen
   `https://prod01.elementscloud.no/publikum/<tenant>/…`.
   - `tenant` står i adressen.
   - `database` (en GUID) står i adressene til dokumentene.
3. **Bekreft kilden med ett kall:**
   ```bash
   curl -s -H "tenant: <tenant>" -H "Accept: application/json" \
     "https://prod01.elementscloud.no/publikum/api/PredefinedQuery/DmbMeetings?year=<år>" | head -c 300
   ```
   - JSON med `MO_ID` og `MO_START` betyr riktig.
   - HTML betyr feil adresse (fallgruven «Feil API-adresse gir 200»).
4. Bruker kommunen ikke Elements, trengs en ny kildeadapter. Det er et eget
   prosjekt. **STOPP.**
5. **Velg `fra_aar`**, det første året som hentes. Som regel inneværende år.
   - Hvert år koster rundt 25–40 minutter ved første henting (dokumentene,
     rundt 2 sekunder per dokument).
   - AI-analysen av et år koster rundt 10 dollar.
6. **Kartet** på forsiden har bare Trøndelag (`kommuner/kart/trondelag.json`,
   38 kommuner). Ligger kommunen utenfor, må `bygg.lag_kart` utvides. **STOPP**
   hvis det gjelder.

## 2. Lag `kommuner/<slug>.json`

Kopier `kommuner/steinkjer.json`, og bytt ut:

- **Grunnfeltene:** `slug`, `navn`, `kommunenr`, `fra_aar`.
- **`kilde`:** `basis`, `tenant`, `database`. Må bli lik `kilde_konfig` i databasen.
- **`tolk`:** start med bare `merknad` og `partinavn`; resten fylles i trinn 4.
- **`nivaa`:** `{"voteringer": false, "oppmote": false}` til dekningen er målt.
- **Visningen:** `utvalg_kort`, `utvalg_liste`, `rekkefolge`, `rad`,
  `foretak`, `hovedutvalg` og `organer`. Kodene står i møtelisten (`UT_NAVN`
  og `DMB.ShortCode`). Oppgavene til utvalgene skal stemme med kommunens egne
  sider; skriv `kontrollert_for_hand` med dato.

Lag også `kommuner/<slug>/partisider.json` og `kommuner/<slug>/tillatte-navn.json`.
- Partisidene åpnes og sjekkes én for én, med samme format som
  `data/partisider.json`.
- Tillatte navn er en tom liste til et sammendrag trenger det.

## 3. Prøvekjøring mot en kopi, aldri mot databasen

Rådata, analyser og vurderinger kan ikke slettes i databasen. Prøv derfor alltid
i en egen mappe:

```bash
export KOMMUNELYS_LAGER=json KOMMUNELYS_KOMMUNE=<slug> KOMMUNELYS_DATA=$HOME/kommunelys-<slug>
mkdir -p "$KOMMUNELYS_DATA"
A=<fra_aar>
python -m hent.hent_moter $A          # møtene; ett kall i sekundet
python -m hent.hent_medlemmer $A
python -m tolk.bygg_saker $A
python -m hent.hent_dokumenter $A     # 25–40 min for et helt år
python -m tolk.bygg_voteringer $A
python -m tolk.bygg_oppmote $A
python -m tolk.bygg_verv $A
python -m tolk.bygg_avvik $A
python -m tolk.dekning $A
```

`lager/_fil.py` stopper hvis `KOMMUNELYS_DATA` mangler, så Steinkjers `data/`
aldri røres.

## 4. Les resultatet og juster regelsettet

1. **Dekningen** (`tolk.dekning`): andelen saksprotokoller med votering, og
   listen `mistenkte`. Åpne 3–5 av de mistenkte i
   `$KOMMUNELYS_DATA/tekst/<id>.txt` og se hvordan kommunen skriver.
2. **Regelsettet** står i `tolk/profiler/elements.py`. Felt i `tolk` erstatter
   standarden, og `<felt>_tillegg` legger til. Det vanligste å justere:
   - `kommunestyre_kode`: koden for kommunestyret, hvis ikke `KS`.
   - `partikoder_tillegg`: fullt partinavn til kode, for lokale lister. Se
     «X (Partinavn) fremmet følgende forslag».
   - `partinavn`: kodene med navn, til AI-instruksjonen.
   - `navnevarianter`: samme person skrevet ulikt. Finn dem i avvikene
     «stemte_uten_oppmote».
   - `formalia_tillegg`: titler på møteteknikk.
   - `oppmote_start`, `oppmote_slutt`: markørene for oppmøtelisten.
   - `overskrifter`, `saksframlegg_start`: overskriftene i saksframlegget.
   - `votering` og `enstemmig`: mønstrene, skrevet som tekst. Endres de, kan
     det koste andre steder, så kjør fasiten for alle kommunene etterpå.
3. Det som ikke kan skrives som data, går i `tolk/profiler/<slug>.py` med
   `OVERSTYR = {"FELT": verdi}`.
4. Kjør tolkningen og `tolk.dekning` på nytt, til dekningen er over 95 %, eller
   til det er klart at stemmene ikke kan leses sikkert ennå.
5. **Tellekontrollen.** `tolk.bygg_voteringer` skriver `tall_stemmer_ikke`.
   Hver rad der må forklares fra dokumentet, ikke rundes av.

**STOPP:** vis dekningen, de mistenkte, avvikene og endringene i profilen.

## 5. Fasit

1. Velg 3–5 dokumenter fra kommunen som dekker det vanlige og det spesielle:
   - minst én møteprotokoll (`mote-<id>.txt`),
   - to saksprotokoller (`vedtak-<id>.txt`), gjerne med alternativ votering
     eller dobbeltstemme,
   - ett saksframlegg (`saksframlegg-<id>.txt`).
2. Kopier dem til `tester/fasit/<slug>/`.
3. `python -m tester.fasit <slug> --skriv` lager `.json`. **Kontroller hver
   `.json` mot dokumentet for hånd:** antall voteringer, tallene for og mot, og
   navnene. Det er det som gjør det til en fasit.
4. `python -m tester.fasit` skal bestå for alle kommunene.

**STOPP:** vis fasiten (antall voteringer per dokument og stikkprøver).

## 6. Bygg og se nettstedet lokalt

```bash
python -m bygg.bygg_nettsted <år> --uten-felles   # nettsted/<slug>/
python -m bygg.bygg_nettsted --felles             # forsiden får kommunen
python -m tester.kontroller <år>
python -m http.server 8765 --directory nettsted
```

Se gjennom:
- forsiden og kartet,
- Saker, en sak, et møte, Hvem bestemmer og en profil,
- merknaden «Stemmene vises ikke …» når voteringene er av.

`python -m analyser.analyser_saker <år> --tort-lop --maks 5` viser grunnlaget
AI-analysen får, uten å sende noe.

**STOPP:** prosjekteier ser på nettstedet lokalt.

## 7. Legg kommunen inn i databasen som intern

1. **Ny migrering** `supabase/migrations/<tidsstempel>_kommune_<slug>.sql`.
   Gamle filer endres aldri.
   ```sql
   insert into kjerne.kommune (kommunenr, slug, navn, kilde_type, kilde_konfig, status)
   values ('<nr>', '<slug>', '<Navn>', 'elements',
           '{"basis": "…", "tenant": "…", "database": "…"}', 'intern');
   ```
   Kjør den slik `supabase/README.md` beskriver, og kjør `supabase/tests/regler.sql`.
2. **PR** med `kommuner/<slug>.json`, `kommuner/<slug>/`, profilen, fasiten og
   migreringen. Arbeidsflyten «Tester» kjører fasiten.
3. **Første henting** av hele året tar 25–40 minutter per år.
   - Jobben «Hent og tolk» i Oppdater har en grense på 60 minutter, sammen
     med de andre kommunene.
   - Har `fra_aar` mer enn ett år, eller er det trangt: hent første gang
     lokalt mot databasen, med `KOMMUNELYS_KOMMUNE=<slug>` og trinnene i
     trinn 3 uten `KOMMUNELYS_LAGER=json`, når Oppdater ikke kjører. Ellers kan
     grensen heves for én kjøring.
4. **AI-analysen** deler `analyse_maks` (25 som standard) mellom kommunene. Et
   helt år for en ny kommune er rundt 200 saker. Start Oppdater for hånd med
   høyere `analyse_maks` noen ganger, så Steinkjer ikke får færre.
5. **Etter kjøringen:** driftssiden (portalen › Drift) viser kommunen i
   tabellen «Kommunene» som «intern», med dekningen. Nettstedet viser den ikke
   ennå (`nettsted-intern/`).

**STOPP:** vis driftssiden og tallene fra kjøringen.

## 8. Begrenset innsyn (valgfritt, før publisering)

Kommunen står på forsiden og kartet, men innholdet vises bare for dem med en
rolle for kommunen (`leser`, `vurderer`, `admin`) og prosjektadmin (ADR-024).

1. Ny migrering som setter `status = 'begrenset'` for kommunen.
2. Etter neste kjøring av Oppdater: driftssiden viser «ny, begrenset innsyn».
   `https://kommunelys.no/<slug>/` ber om innlogging; med rollen vises alt.
3. Gi rollen `leser` i portalen › Brukere › «Gi rolle» til dem som skal se.

**STOPP:** prosjekteier sier ja før migreringen med `begrenset` kjøres.

## 9. Publiser

1. Ny migrering som setter `status = 'publisert'` for kommunen.
2. Slå på `nivaa.voteringer` og `nivaa.oppmote` i `kommuner/<slug>.json` hvis
   dekningen er over 95 %. Ellers står de av, og sidene sier hvorfor.
3. PR, sammenslåing, og en kjøring av Oppdater.
4. **Sjekk etterpå:**
   - forsiden og kartet har kommunen,
   - en sak og et møte vises,
   - driftssiden viser «ny» for begge kommunene,
   - ingen endringer i Steinkjers data (`drift.endringslogg` for kjøringen).

**STOPP:** prosjekteier sier ja før migreringen med `publisert` kjøres.

## 10. Etterpå

- **`CLAUDE.md`:** statusraden «Flere kommuner» (hvilke kommuner, dekning).
- **`docs/05-plan.md`:** fase 3.
- **Skillen:** står noe i denne sjekklisten feil eller mangler, rett den i
  samme PR.
