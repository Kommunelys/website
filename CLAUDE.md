# CLAUDE.md

Kontekst for Claude Code i dette repoet. Les denne først.

## Hva dette er

**Kommunelys**: en uoffisiell, offentlig nettside som gjør politiske saker i
kommunen forståelige for innbyggere. Data hentes fra kommunens innsynsportal,
tolkes med en språkmodell, og publiseres på nytt automatisk. Steinkjer er
publisert, og Levanger har begrenset innsyn; navnet og malen er laget for
flere (ADR-016).

Prosjektet er **ikke** laget av eller for Steinkjer kommune eller noen annen
kommune. Det må være utvetydig uoffisielt i all presentasjon.

## Reglene

Seks regler, vedtatt av prosjekteier 31.10.2026. De går foran alt annet i
repoet. ADR-ene i `docs/04-beslutninger.md` er historikken bak, og «Teknisk
erfaring» lenger ned sier hvordan ting gjøres, ikke hva som er lov.

1. **Dokumentene er fasit.** Alt vi viser kan spores til kommunens dokumenter,
   med lenke. Stemmetall leses med kode og kontrolleres, aldri av KI. Vi
   venter ikke på svar fra kommunen.
2. **Vi skriver ikke navn.** Tekst Kommunelys skriver selv, har ingen navn på
   privatpersoner. Folkevalgte omtales i rollen sin, debatten med partiene.
   Sakstitler og forslag fra dokumentene vises uendret. Unntak: prosjekteier
   med navn og bilde på Om-siden.
3. **KI-tekst er merket og kan holdes tilbake.** Det som ikke består
   kontrollen, vises ikke før det er vurdert. Prosjekteier har siste ord og kan
   redigere.
4. **Vi er en høflig gjest hos kommunen.** Innsyn er en rett, så vi ber ikke om
   lov. Men prosjekteier sender kommunen en e-post når vi begynner å hente fra
   den, og igjen når den blir åpen for alle. Vi henter i lav takt, laster
   aldri ned skjermet innhold, lagrer ikke PDF eller video, og siden er
   tydelig uoffisiell.
5. **Innbyggerne først.** Alt offentlig innhold er gratis og åpent uten konto,
   uten informasjonskapsler og uten profilering. Betalte funksjoner kommer i
   tillegg, aldri i stedet.
6. **Ingenting ut uten ja, og bare det som virker, vises.** Prosjekteier
   godkjenner før noe publiseres. En funksjon er ikke synlig før den virker.
   Koden holdes lett og enkel.

Slik holdes reglene i koden:

- **Stemmetall (1):** mønstergjenkjenning i `tolk/`, og antall navn
  kontrolleres alltid mot oppgitt stemmetall. Et avvik stopper raden. En
  vurdering kan slippe voteringen gjennom, men endrer aldri navn eller tall,
  og merkes med `vurdert_av` (ADR-015, ADR-020).
- **Kildelenke (1):** et sammendrag eller en debatt uten kildelenke
  publiseres ikke.
- **Navn (2):** gjelder sammendrag, debatt, merknader og forklaringer.
  Bunnteksten sier «Kommunelys er en uoffisiell tjeneste, laget av en
  innbygger for innbyggerne», uten navn (`UOFFISIELL`).
- **Lav takt (4):** maks ett kall i sekundet, én tråd, samlet for verten:
  kommunene hentes etter tur, aldri samtidig (`kjor/alle.py`). Portalens
  `robots.txt` ber automatiske verktøy holde seg unna (ADR-007).
- **Skjermet (4):** portalen merker det med `ProtocolRestricted`,
  `IsRestricted` og `AccessCodeId`. Det lastes aldri ned og sendes aldri til
  en modell. Respekter feltene i hvert ledd.
- **PDF og video (4):** bare uttrukket tekst lagres. Originalen og opptaket
  lenkes til hos kommunen.

## Status akkurat nå

| Del | Status |
|---|---|
| API-et til portalen | Kartlagt og dokumentert, se `docs/02-api.md` |
| Innhenting og dokumenter | Virker. Møter, saker, saksgang på tvers av utvalg, og tekst fra PDF og Word (ADR-013) |
| Stemmer og oppmøte | Virker. Tellekontrollen stopper avvik; avvik mot oppmøtelisten flagges og vurderes. Fasit per kommune i `tester/fasit/` |
| Utvalg og verv | Virker. Medlemslistene hentes versjonert; vervene har observerte, ikke vedtatte, datoer |
| AI-analyse | Kjører i arbeidsflyten (`claude-opus-5`, instruksjon v3). Sammendrag som ikke består kontrollen, holdes tilbake |
| Nettsted | Publisert på https://kommunelys.no/, med hver kommune under `/<slug>/`. Alle år fra `fra_aar`; en sak er én tråd på tvers av år (ADR-022). Saken står i sentrum (`#sak/<id>`, og `#sak/<id>/mote/<id>` når man blar i ett møte), med møtet (`#mote/<id>`), profilene, «Hvem bestemmer» og en felles Om-side (`/om/`). Detaljene står i `docs/01-arkitektur.md` |
| Opptak av kommunestyret | Virker for Steinkjer (ADR-026). Opptakene kobles til møtet og sakene; debatten oppsummeres fra tekstingen med partiene, uten navn og stemmetall |
| GitHub Actions | Virker. Kjører på tidsplan hver hverdag kl. 05:17 UTC, og kan startes for hånd |
| Drift og besøk | Driftssiden (besøk fra GoatCounter, status, AI-kostnad, kjøringene) vises i portalen for prosjektadmin, ikke på nettstedet (ADR-017, ADR-020) |
| Portal | I drift på https://portal.kommunelys.no/ (ADR-020). Se «Portalen» under |
| Flere kommuner | I bruk (ADR-021). Steinkjer er publisert. Levanger har begrenset innsyn (ADR-024): innholdet bare for innloggede med en rolle for kommunen |
| Følg saken | Bygget (ADR-027), ikke i drift. E-post sendes først når variabelen `VARSEL_SEND` er 1. Driftssiden teller e-postene mot grensen i Resend (100 i døgnet, varslene stopper på 70) |
| Database (Supabase) | Kilden siden 6.10.2026 (ADR-019). `data/` i git står som ved byttet. Sikkerhetskopi hver natt (privat repo) |

## Mappene

```
hent/      innhenting fra portalen (JSON og dokumenter), og opptakene fra kommunetv (hent/kommunetv.py)
tolk/      protokoll til voteringer, og saksgang på tvers av utvalg
tolk/profiler/  regelsettene: standarden for Elements og kommunenes egne (tolk/profil.py)
kjor/      alle kommunene etter tur: hent, analyser og bygg (kjor/alle.py)
varsel/    «Følg saken»: det som er publisert i sakene, hva som er nytt, og køen (ADR-027)
analyser/  kall mot Claude med caching på sjekksum
bygg/      statisk nettsted; malen (HTML, CSS, JS, skrift, merke) i bygg/mal/
drift/     kjøreloggen, historikken fra databasen og Actions, og kostnadsanslaget til driftssiden
lager/     all lesing og skriving av data/; resten av koden bruker bare denne
kommuner/  det som er særegent for hver kommune: kilden, regelsettet (tolk),
           nivåene (nivaa) og visningen (navn, utvalg, organer)
kommuner/<slug>/  partisider og tillatte navn for andre kommuner enn Steinkjer
kommuner/kart/  forenklede kommunegrenser til kartet på forsiden (bygg.lag_kart),
               og kandidatene med samme innsynsportal (kandidater.json, grå på kartet)
data/          dataene slik de var ved byttet til databasen 6.10.2026 (ADR-019);
               oppdateres ikke lenger, bortsett fra de to filene for hånd
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
data/vurderinger.json  vurderingene av avvikene slik de var 6.10.2026; nå i databasen (ADR-020)
data/analyse/  sammendrag og tagger fra modellen
data/tillatte-navn.json  navn fra sakstitler som er vurdert og kan stå i et sammendrag
data/partisider.json  lenker til partienes egne sider, kontrollert for hånd
data/drift/kjoringer.json  tall fra hver kjøring: kall mot portalen, AI-analysen
docs/      arkitektur, API, datamodell, beslutninger, plan
tester/    kontroller som må passere før publisering
tester/fasit/  dokumenter kontrollert for hånd, per kommune, med forventet resultat
supabase/  databaseskjemaet (migreringer og tester); databasen er kilden
```

## Kommandoer

Alle kommandoene leser og skriver databasen (`KOMMUNELYS_DB_URL` eller
`~/.kommunelys.env`). `KOMMUNELYS_LAGER=json` bruker filene i `data/` i stedet.

```bash
python -m hent.hent_moter 2026          # møter, saker, saksgang
python -m hent.hent_medlemmer 2026      # dagens medlemslister -> data/raa/medlemmer/
python -m hent.hent_dokumenter 2026     # PDF/Word -> data/tekst/ (rundt 25 min)
python -m tolk.bygg_saker               # saksgang og status -> data/saker/
python -m tolk.bygg_voteringer 2026     # voteringer fra vedtakene -> data/voteringer/
python -m tolk.bygg_oppmote 2026        # oppmøte og avvik mot stemmene -> data/oppmote/
python -m tolk.bygg_verv 2026           # utvalg, partier og verv -> data/utvalg/, data/verv/
python -m tolk.bygg_avvik 2026          # avvik som venter på vurdering -> data/avvik/
python -m hent.hent_opptak 2026         # opptakene, bokmerkene og tekstingen fra kommunetv (ADR-026)
python -m analyser.analyser_debatt 2026 --tort-lop  # hvilke debatter som ville blitt oppsummert
python -m analyser.analyser_debatt 2026 --vis 8457  # grunnlaget for debatten om én behandling
python -m tolk.tolk_protokoll <fil.txt> # voteringer fra én møteprotokoll
python -m tolk.saksframlegg <fil.txt>   # avsnittene i ett saksframlegg
python -m tester.kontroller             # alle kontroller
python -m tester.fasit                  # fasiten for tolkningen, alle kommunene (uten database)
python -m tolk.dekning 2026             # hvor mye av protokollene regelsettet leser
python -m kjor.alle hent|analyser|bygg 2026  # alle kommunene etter tur, alle år fra fra_aar
KOMMUNELYS_KOMMUNE=steinkjer python -m ...   # én kommune (standard: steinkjer)
python -m bygg.bygg_nettsted 2026 --kommune steinkjer --uten-felles  # bare nettsted/steinkjer/
python -m bygg.bygg_nettsted --felles   # forsiden, /om/, 404 og driftssiden fra nettsted/*/
KOMMUNELYS_I_DAG=2026-10-04 python -m tolk.bygg_saker 2026  # tolk og bygg som om det var en annen dag
python -m bygg.bygg_nettsted 2026       # nettsted/ fra data og bygg/mal/
python -m lager.vurder <avvik> publiser --begrunnelse ... --vurdert-av ...  # vurdering fra en modell
python -m bygg.bygg_nettsted 2026 --drift-fil drift.html  # driftssiden også lokalt
KOMMUNELYS_PORTAL=http://localhost:5173 python -m bygg.bygg_nettsted 2026  # kontomenyen mot portalen lokalt
python -m lager.paritet 2026           # filene i data/ mot databasen (etter en gjenoppretting)
python -m bygg.lag_kart                 # kommunegrensene i Trøndelag -> kommuner/kart/ (sjelden)
python -m varsel.kjor                   # «Følg saken»: endringene i køen; VARSEL_SEND=1 sender (ADR-027)
python -m bygg.bygg_nettsted --bare-drift --utfall utfall.json  # bare driftssiden, etter varslene
node --test supabase/functions/varsel/logikk.test.ts  # e-posten og nøkkelen for «Slutt å følge»
python -m http.server 8765 --directory nettsted  # se nettstedet lokalt; kommunen under /steinkjer/
```

## Flytting til databasen

Dataene er flyttet fra JSON i git til Postgres i Supabase (ADR-019). Planen
ble vedtatt av prosjekteier 4.10.2026, og byttet ble gjort 6.10.2026;
`supabase/README.md` har detaljene.

| Fase | Status |
|---|---|
| 0. Lagringslag (`lager/`) | Ferdig (#28). All lesing og skriving går gjennom `lager/` |
| 1. Skjema, regler og RLS (`supabase/migrations/`) | Ferdig (#29). Testene i `supabase/tests/regler.sql` består |
| 2. Import og lesing fra databasen | Ferdig (#30). Nettstedet bygget fra databasen er byte-likt |
| 3. Speiling ved hver kjøring | Ferdig (#31). Speilingen ble tatt bort etter byttet |
| 4. Klargjort for bytte | Ferdig (#32, #33). Lesing, skriving, driftsside og nattlig sikkerhetskopi |
| 4. Selve byttet | Ferdig 6.10.2026. `oppdater.yml` bruker databasen og committer ikke `data/`. 6 av 6 kontroller var like før byttet, og en generalprøve mot portalen ga det samme |
| 5. `data/` ut av git | Senere, når databasen har gått en stund. Til da står `data/` som ved byttet |

- **Kilden nå:** databasen. Nettstedet bygges fra den. `data/` i git viser
  dataene slik de var 6.10.2026 og oppdateres ikke.
- **`KOMMUNELYS_LAGER`** er `pg` som standard. `json` leser og skriver filene
  i `data/`, eller i en kopi med `KOMMUNELYS_DATA`, for å prøve en ny kommune.
- **To filer vedlikeholdes for hånd og blir i git også etter byttet:**
  `tillatte-navn.json` og `partisider.json`. De gjennomgås i PR og leses
  rett fra filen. Vurderingene av avvik registreres i
  databasen, i portalen eller med `lager.vurder` (ADR-020).
- **Tilkoblingen** ligger i `KOMMUNELYS_DB_URL`: hemmeligheten i Actions og
  `~/.kommunelys.env` lokalt. Aldri i repoet.
- **Endringsloggen** (`drift.endringslogg`) viser hva hver kjøring endret i
  databasen, og er det driftssiden teller endringene fra.
- **Sikkerhetskopien** tas hver natt i det private repoet
  `Kommunelys/sikkerhetskopi`, ikke her (ADR-019). Git er ikke lenger
  sikkerhetskopien.

## Portalen

Innlogget del av Kommunelys på https://portal.kommunelys.no/ (ADR-020). Ble
satt i drift 6.10.2026. Nettstedet krever ingen innlogging, bortsett fra
kommunene med begrenset innsyn: der gir en rolle for kommunen (`leser`,
`vurderer` eller `admin`) innsyn (ADR-024). Abonnement brukes ikke ennå.

| Del | Hvor |
|---|---|
| Appen | Repoet `Kommunelys/portal` (lokalt `C:\ClaudeCode\kommunelys-portal`): Vite, React, react-admin og ra-supabase. Publiseres på GitHub Pages ved push til `main` |
| Innlogging | Supabase Auth. E-post fra `post@kommunelys.no` via Resend (SMTP). Malene ligger i `supabase/epostmaler/` og limes inn i Supabase for hånd |
| Data | Skjemaet `portal` (`supabase/migrations/20261006181902_portal.sql`): views med `security_invoker`, så RLS gjelder. Det eneste skjemaet i Data API, og bare for innloggede |
| Brukeradministrasjon | Edge-funksjonen `brukeradmin` (`supabase/functions/`): liste, invitere, sperre, nytt passord, slette. Service-nøkkelen finnes bare der |
| Kontomenyen | `bygg/mal/konto.js` og `bygg/mal/konto.html` (`/konto/`) på nettstedet |
| Driftssiden | Bygget lagrer den i `drift.side`; portalen viser den |

- **Prosjektadmin gis bare med SQL** (som `postgres`, i SQL-editoren), aldri
  fra portalen, og kan ikke sperres eller slettes der. Prosjekteier er
  prosjektadmin.
- **Sidene:** alle har registrering, innlogging, glemt passord, Min konto
  (bytte passord og e-post, slette kontoen, mine meldinger om feil) og
  `/meld`, som «Meld fra om feil» på saken lenker til. Vurderere for en
  kommune har «Til vurdering»: meldinger om feil, sammendrag og debatter holdt
  tilbake og avvik i stemmene (ADR-023, ADR-026). Prosjektadmin har i tillegg Brukere (med «Gi
  rolle» og «Gi abonnement»), Roller, Abonnement og Drift.
- **Vurderinger av avvik** registreres i portalen, eller med
  `python -m lager.vurder` når en modell vurderer. De slår inn ved neste
  kjøring av Oppdater. Det samme gjelder vurderinger av sammendrag og
  meldinger om feil, som bare gjøres i portalen.
- **Kontomenyen** viser «Logg inn» og «Ny bruker», eller kontoen når man er
  logget inn. Portalen sender brukeren tilbake via `/konto/` på nettstedet
  (`bygg/mal/konto.html`), med kontoen etter `#`, og siden lagrer den i
  localStorage. Ingen informasjonskapsler; e-postadressen går ikke til
  nettstedets server. `?tilbake=` sier hvor brukeren skal etterpå. Med
  kontoen følger tilgangsnøkkelen (`nokkel`, `utloper`), som `innsyn.js`
  bruker for kommunene med begrenset innsyn (ADR-024).
- **Utseendet** følger nettstedet: fargene fra `stil.css`, skriften Inter og
  merket (`src/tema.ts` i portalen). Endres fargene i `stil.css`, må temaet
  følge med.
- **Lokalt:** `npm run dev` i portalen gir http://localhost:5173 mot den ekte
  databasen. `KOMMUNELYS_PORTAL=http://localhost:5173 python -m bygg.bygg_nettsted 2026`
  lar kontomenyen på nettstedet bruke den.
- **Det som gjøres for hånd i dashbordene:** hCaptcha (hostnavnene),
  Resend (domenet og nøkkelen),
  Supabase Auth (SMTP, Site URL og Redirect URLs, e-postmalene, minste
  passordlengde 10, captcha), Data API (`portal` eksponert, «Automatically expose new
  tables» av), og GitHub Pages med HTTPS for portalen.
- **E-post (7.10.2026):**
  - Portalen sender fra `Kommunelys <post@kommunelys.no>` via Resend.
    Kontrollene SPF (`rsend.kommunelys.no`), DKIM (`resend._domainkey`) og
    DMARC består alle.
  - DMARC er `p=quarantine`.
  - `post@kommunelys.no` tar imot e-post hos Domeneshop (MX
    `mx.domeneshop.no`, SPF `include:_spf.domeneshop.no`) og videresender til
    prosjekteier. Prosjekteier svarer fra Gmail som post@ via `smtp.resend.com`.
  - `post@kommunelys.no` er kontaktadressen overalt: på Om-siden
    (`KONTAKT_EPOST` i `bygg/bygg_nettsted.py`), der en side ikke finnes
    eller ikke kan vises, og i `User-Agent` mot innsynsportalen
    (`hent/portal.py`). Feil i en sak meldes i portalen («Meld fra om feil»,
    ADR-023). Ingen personlig adresse og ikke noe kontaktskjema.
  - Leveres e-post («250»), men kommer ikke fram, er det filteret hos
    mottakeren: søppelpost eller karantene i Microsoft 365.
- **Captcha (hCaptcha):** Supabase krever den ved registrering, innlogging og
  glemt passord (Authentication › Attack Protection, med hemmeligheten der).
  Portalen viser den med sitekeyen i `src/captcha.tsx`; ra-supabase sine
  skjemaer kan ikke sende den med, så innlogging og glemt passord er egne.
  hCaptcha godtar bare hostnavn som finnes i DNS, og virker ikke på
  localhost: lokalt brukes `http://lokal.kommunelys.no:5173`, en A-post til
  127.0.0.1 hos Domeneshop. `brukeradmin` sender lenke for nytt passord med
  service-nøkkelen, som slipper captcha.
- **Senere:** tofaktor for prosjektadmin, betaling og Pro-plan i Supabase.

## Design

- **Siden slik den er nå er utgangspunktet.** Designet fra saksiden (kort som
  åpnes, fargede overskrifter og myk bevegelse, av ved `prefers-reduced-motion`)
  brukes også på møtet, profilen, sakene og oversikten der det passer.
- **Saken er det alt lenker til.** Lenk til `#sak/<id>` (`sakUrl(hid)` i
  `app.js`) og `#mote/<id>`, ikke til `#saker` med et søk. Fra møtet lenkes
  saken som `#sak/<id>/mote/<id>` (`sakIMote`), så man kan bla til forrige og
  neste sak i det møtet. Stemmer har ikke lenger egen fane; nye visninger av
  stemmer hører hjemme på saken, møtet, profilen eller under Politikere ›
  Partiene.
- **Malen nevner ingen kommune.** Et kommunenavn i `bygg/mal/` ville stått på
  de andre kommunenes sider også. Det hører hjemme i `kommuner/<kommune>.json`
  og leses fra `S.kommune`. `tester.kontroller` stopper hvis malen nevner en
  kommune.
- **Lys blå er pynt, ikke tekst.** `#60A5FA` har 2,4:1 mot papirhvit. Lenker,
  fokus og status bruker `--lenke` (ADR-016).
- **Om-siden er felles, «Hvem bestemmer» er kommunens.** Tekst om metode,
  kvalitet og personvern står i `bygg/mal/om.html` og gjelder alle kommunene.
  Hver påstand der skal kunne spores til kode, en ADR eller data. Siden skal
  være kort: ingen dekningstabell, og «Hvem står bak» endres ikke uten
  godkjenning. Gamle lenker til `#om` sendes til `/om/`.

## Teknisk erfaring

Hvordan ting gjøres, lært av feil vi har gjort. Reglene står øverst.

- **En prøve mot filene kjenner ikke databasens regler.** Levanger gikk
  gjennom med `KOMMUNELYS_LAGER=json`, men stoppet i databasen på sakstypen
  «AS» (Arbeidsmiljøutvalget) og på at sakene ble lagret før møtene. Nye
  verdier i felt med en regel (sakstype, funksjon, status) trenger en
  migrering. Sakene og møtene lagres nå i én transaksjon
  (`lager.saker.lagre_med_moter`).
- **Det som ligger på nettstedet, kan alle lese.** For en kommune med
  begrenset innsyn går dataene til `nettsted-skjermet/` og databasen
  (`drift.nettsted_fil`), aldri til `nettsted/` (ADR-024). En ny fil med data
  per kommune må følge med dit, ikke legges ved siden av sidene.
- **En sak er ikke en behandling.** Samme sak får nytt saksnummer i hvert
  utvalg. `AdditionalDmbHandlings` binder dem sammen. Kjeden bygges med
  disjunkte mengder i `tolk/bygg_saker.py`.
- **En sak er ikke et år.** En sak behandlet i desember og avgjort i februar
  fikk én ID per år da kjedene ble bygget av ett års møter. Kjedene bygges nå
  av alle årene fra `fra_aar`. En sak hører til året den begynte, et møte,
  oppmøtet og et avvik til møtets år. Kode som kobler stemmer og oppmøte, må
  lese alle årene (`lager.kommune.alle_aar`), ikke ett (ADR-022).
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
  «Enok Askil Moe» og «Enok Moe». Normaliseres i `tolk/navn.py`, med
  variantene i kommunens profil (`navnevarianter` i `kommuner/<slug>.json`).
- **Ingen treff er ikke det samme som ingen voteringer.** Skriver en kommune
  protokollene annerledes enn mønstrene venter, blir det ikke feil, bare tomt.
  `tolk/dekning.py` finner protokoller som nevner at noen stemte uten at en
  votering ble funnet. I Steinkjer fant den «Forslaget ble vedtatt mot 1
  stemme (…)» og «7 stemte for … 0 stemte imot» i rådene.
- **Mønstre hører hjemme i profilen.** Et nytt mønster eller en ny kode for et
  utvalg i koden ville gjeldt alle kommunene. Legg det i
  `tolk/profiler/elements.py` (alle) eller i kommunens profil, og kjør
  fasiten for alle kommunene.
- **Oppmøtelisten og stemmene stemmer ikke alltid overens.** I 6 møter i
  2026 stemmer noen som ikke står på oppmøtelisten, eller det er flere
  stemmer enn frammøtte. Det står slik i protokollene. `tolk.bygg_oppmote`
  flagger dem; slike voteringer publiseres ikke før det finnes en vurdering
  i databasen (portalen eller `lager.vurder`). Sjekk bevisene med kode før du vurderer: hvem
  som står på listen uten å stemme, partiet deres, og vedtak om permisjon og
  fritak i sakene. Se `docs/03-datamodell.md`.
- **Et avvik som dokumentene ikke avgjør** (regel 1): voteringen publiseres
  slik protokollen oppgir den, med en tydelig merknad om hva som er usikkert
  og lenke til protokollen. Ikke skriv at vi venter på svar eller har spurt
  kommunen.
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
- **Driftssiden henter historikk fra databasen og GitHub-API-et.** Bygget
  trenger `actions: read`. Lokalt brukes API-et uten nøkkel, med grense på 60
  kall i timen. Svarer det ikke, viser siden bare endringene i dataene.
- **Opptaket ligger hos kommunen, ikke hos oss.** Vi lenker til saken i
  kommunens spiller (`archive/<id>?caseId=<bokmerke>`); den kan ikke åpnes på
  et vilkårlig tidspunkt, så debatten skriver tiden i teksten. Videoen lastes
  aldri ned. Opptakene slettes etter en tid (arkivet går tilbake til
  1.9.2025); `hent.hent_opptak` setter da `fjernet`, og lenken forsvinner.
- **Bokmerkene i opptaket er satt for hånd.** De har saksnummeret («PS 47/26»),
  men grensene er unøyaktige: bokmerket for PS 49 16.09.2026 slutter med en ny
  votering i PS 48. En sak kan ha flere bokmerker (før og etter pausen).
- **Ikke alle opptak er tekstet.** Bare tekstede opptak får debatt; de andre
  får lenkene. Tekstingen hører navn feil («Agnestein» for Agdestein), så
  kontrollen av partiene ser etter etternavn som ligner, ikke bare like
  navn. Tekstingen inneholder navn på privatpersoner og vises aldri.
- **Kontrollen av debatten skal være mild** (prosjekteier, 20.10.2026). Den
  stopper stemmetall, tider utenfor saken og partier som ikke sa noe i
  saken, ikke stedsnavn eller forkortelser. Navn ser den ikke etter
  (prosjekteier, 23.10.2026): de tre navnesjekkene ga bare feilalarmer
  («Modellen», «Nye Veier»), og den første utgaven holdt tilbake 8 av 11
  gode sammendrag fordi fornavn lignet korte ord («To» og «Tor»). At
  sammendraget ikke har navn (regel 2), sikres av instruksjonen til
  modellen. Gjør du kontrollen strengere, så prøv den på de ekte debattene
  i databasen, ikke bare på plantede feil.
- **Sted og rom er fritekst i portalen.** Ved befaringer står ruten i begge
  feltene, og noen ganger tidsplanen i rommet. `stedTekst` i `app.js` viser det
  som er likt, én gang.
- **404-siden vises på alle adresser som ikke finnes.** Derfor må lenkene i
  `bygg/mal/404.html` være absolutte, med `{{base}}` foran. Roten kommer fra
  `NETTSTED_BASE`, som arbeidsflyten setter fra GitHub Pages (tom med eget
  domene, «/website» før det); lokalt er den «/». Etter bytte av domene må
  nettstedet bygges på nytt, ellers peker 404-siden til den gamle roten. Bygget stopper ved relative lenker.
  Andre feilkoder (500, 503) kan ikke tilpasses på GitHub Pages.
- **Ikke gjett adresser.** inp.no er ikke Industri- og næringspartiet, men en
  side om kredittkort. Lenker til partier og andre ligger i
  `data/partisider.json` og åpnes og sjekkes før de legges inn.
- **Endrer du formen på dataene, må databasen følge med.** Et nytt felt eller
  en ny type data (som `vedtak` i voteringene, #27) kjenner ikke databasen, og
  det forsvinner uten feilmelding om ingen tar det med. Ta med i samme PR: en
  ny migrering i `supabase/migrations/`, lesingen i `lager/pg.py` og
  skrivingen i `lager/pg_skriv.py`. Prøv lokalt mot databasen før det slås
  sammen. Nye verdier i de samme feltene, og endringer i utseendet, trenger
  ingenting.
- **Gamle migreringer endres aldri.** De er allerede kjørt. En rettelse er en
  ny fil, og filnavnet er versjonen databasen registrerer. En ny tabell trenger
  RLS og policyer for rollene (se `20261004212642_tilgang.sql`). Kjør
  `supabase/tests/regler.sql` etterpå.
- **Rådata, analyser, vurderinger og endringsloggen kan ikke endres eller
  slettes i databasen.** Det er med vilje. En speiling eller import kan ikke
  angres. Prøv derfor endringer mot en kopi av dataene (`KOMMUNELYS_DATA`) før
  de kjøres mot de ekte. Lokale kjøringer skriver til den samme databasen som
  nettstedet bygges fra; det finnes ingen egen testdatabase.
- **Bruk Session pooler-adressen til Supabase.** Den direkte adressen
  (`db.<prosjekt>.supabase.co`) er bare IPv6 og svarer ikke herfra eller fra
  Actions. Koble aldri til som `postgres` fra koden; eieren går forbi RLS.
- **Portalen ser bare skjemaet `portal`.** En ny tabell eller et nytt felt
  portalen skal vise, trenger et view der (med `security_invoker`), rettigheter
  for `authenticated` og tester i `regler.sql`. Supabase legger ikke noe til av
  seg selv.
- **Svar på forhåndssjekken (OPTIONS) kan ikke ha innhold.** Første utgave av
  `brukeradmin` krasjet på det, og nettleseren meldte bare «Failed to send a
  request to the Edge Function».
- **Portalen bruker vanlige adresser, ikke `#`.** Lenkene i e-postene fra
  Supabase krever det. GitHub Pages har ingen omskriving, så publiseringen
  kopierer `index.html` til `404.html`. Undersider svarer derfor med
  statuskode 404, men viser appen.
- **Nettleseren holder på `stil.css` og skriptene.** De lenkes med
  `?v=<sjekksum>`, ellers ser nye endringer feil ut hos dem som har vært
  innom før. Nye filer i `FELLES` trenger det samme, og det har
  `detaljer-<år>.json` (i `S.detaljer`).
- **Søkemotorer og språkmodeller leser HTML-en, ikke appen.** Det som står
  etter `#`, er ikke egne sider for dem, og de fleste KI-robotene kjører ikke
  skript. Kommunesiden har derfor de siste sakene fra kommunestyret i HTML-en
  (`_viktige`), og alle sidene har kanonisk adresse og Open Graph (`_deling`,
  med `delingsbilde.png` fra `bygg/delingsbilde.html`). Bygget lager
  `robots.txt` og `sitemap.xml`. En kommune med begrenset innsyn får ingen
  saker i HTML-en og står ikke i sitemap.
- **Detaljene er ikke i `data.js`.** Hele sammendraget, vedtakstekstene og
  forslagstekstene hentes når en sak åpnes (`hentDetaljer` i `app.js`). En ny
  visning som trenger dem, må vente på `hentDetaljer`, som sakssiden gjør.
- **Lenkene i e-postene skal gå til vårt eget domene.** En e-post fra
  kommunelys.no med lenke til `…supabase.co` ser ut som svindel for filtrene,
  og Microsoft Safe Links åpner lenkene og bruker opp engangslenken. Malene i
  `supabase/epostmaler/` lenker derfor til `{{ .SiteURL }}/bekreft` med
  `{{ .TokenHash }}`, og portalen bekrefter først når mottakeren trykker på
  knappen. Bruk aldri `{{ .ConfirmationURL }}`.
- **Lenker i Supabase-e-poster går til Site URL** hvis `redirectTo` mangler,
  og den adressen må stå i Redirect URLs. Både `https://portal.kommunelys.no/**`
  og `http://localhost:5173/**` står der.
- **Safari på iPhone lar ikke en ramme fra portalen lese innloggingen**,
  selv om portalen ligger på et underdomene. Den første utgaven av
  kontomenyen spurte portalen på den måten, og viste aldri kontoen på iPhone.
  Kontoen må sendes med når portalen sender brukeren tilbake.
- **Vite kan servere en gammel modul** etter mange endringer mens
  utviklingsserveren går («X is not defined» selv om koden er riktig). Start
  den på nytt.
- **En vurdering endrer aldri innholdet.** Den avgjør om noe vises, og kan ha
  en kort merknad som vises uten godkjenning for hånd. Unntaket er
  prosjektadmin, som kan publisere et sammendrag uansett grunn og redigere
  teksten (`kjerne.sammendrag_redigering`, merket «redigert av Kommunelys»;
  ADR-025). Analysen fra modellen endres aldri. Derfor kontrolleres
  merknaden (`kjerne.merknad_ok`, `tolk/merknad.py`), og en merknad med navn
  holder saken tilbake. En melding om feil skjuler ingenting før den er
  vurdert (ADR-023).
- **En rad som kobles til en konto, må tåle at kontoen slettes.**
  `kjerne.feilmelding.meldt_av` settes til null, og `forby_endring` slipper
  akkurat den endringen gjennom. Uten det stopper «Slett kontoen».
- **`tilgang.innsyn_kommuner()` tar ikke med de publiserte kommunene.** Den
  gir kommunene der brukeren har en rolle (og alle for prosjektadmin). En
  regel for «har innsyn» må også slippe gjennom `status = 'publisert'`, som
  policyen på `varsel.folger` gjør.
- **Tall med `kommune_id` null i `drift.kjoring_tall`** leses med hver kommune
  (`pg.kjoringer`). De skrives ikke tilbake på kommunen: delene står i
  `pg.GLOBALE_DELER` (i dag `varsel`). En ny del for alle kommunene må stå der.
- **Varselet bygger på det som er publisert, ikke på databasen.** Det som er
  holdt tilbake, finnes ikke i tilstanden (`varsel/tilstand.py`), og den
  lagres bare når kommunen publiseres. Endres det som vises på saken, må
  tilstanden og `tester.kontroller` (`varselet_fanger_endringene`) følge med.
- **Hver spørring mot databasen tar rundt 50 ms, og tekst går med 0,6 MB/s.**
  `lager/pg.py` husker derfor svarene i prosessen og henter tekst bare når den
  trengs. Spør ikke i en løkke.

## Flere kommuner (ADR-021)

- **En ny kommune** legges inn med en migrering (`kjerne.kommune` med
  `kilde_konfig` og status), og med `kommuner/<slug>.json` der kilden er lik
  og `fra_aar` er det første året som hentes. Sjekklisten står i skillen
  `.claude/skills/ny-kommune/SKILL.md` (`/ny-kommune`).
  Status `kartlegging` hentes ikke, `intern` hentes og bygges uten å
  publiseres, `begrenset` står på forsiden og kartet bare for kontoer med en
  rolle for kommunen, og innholdet krever rollen (ADR-024), og `publisert` er
  åpen for alle.
- **Regelsettet:** felt i `kommuner/<slug>.json` under `tolk` erstatter
  standarden; `<felt>_tillegg` legger til. Mønstre skrives som tekst. Det som
  ikke kan skrives som data, går i `tolk/profiler/<slug>.py` (`OVERSTYR`).
- **Fasit først:** legg 3–5 dokumenter fra kommunen i `tester/fasit/<slug>/`,
  kjør `python -m tester.fasit <slug> --skriv`, og kontroller hver `.json`
  mot dokumentet for hånd før den committes.
- **Nivåer:** uten `nivaa` er alt med. Sett `"nivaa": {"voteringer": false}`
  til dekningen er over 95 %.
- **Prøv mot en kopi:** `KOMMUNELYS_LAGER=json KOMMUNELYS_DATA=<mappe>`.
  `data/` hører til Steinkjer; `lager/_fil.py` stopper en annen kommune som
  vil lese eller skrive der.

## Språk

Kode, variabelnavn og kommentarer på norsk der det gjelder domenet
(sak, møte, utvalg, behandling, votering). Teknisk kode kan være engelsk.
All tekst mot brukeren er på norsk bokmål, i klarspråk.
