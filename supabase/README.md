# supabase/

Databaseskjemaet for Kommunelys (Postgres i Supabase). Databasen er kilden
siden 6.10.2026 (ADR-019): hele kjeden leser og skriver her, og `data/` i git
står som den var ved byttet. `KOMMUNELYS_LAGER=json` leser og skriver filene
i stedet. To filer vedlikeholdes fortsatt for hånd i git, også da:
`tillatte-navn.json` og `partisider.json`. De gjennomgås i en PR og speiles
inn med `python -m lager.synk --konfig`. Vurderingene av avvik registreres i
databasen, i portalen eller med `python -m lager.vurder` (ADR-020).

| Kommando | Gjør |
|---|---|
| `python -m lager.synk --konfig` | Speiler de to filene som vedlikeholdes for hånd. Kjøres først i hver kjøring |
| `KOMMUNELYS_LAGER=json python -m lager.synk 2026` | Gjør databasen lik `data/` i én transaksjon: bare det som er endret, skrives og logges. Mot en tom database er det en import |
| `python -m lager.paritet 2026` | Leser alt fra filene og fra databasen og sammenligner, tegn for tegn |
| `python -m bygg.bygg_nettsted 2026` | Bygger nettstedet fra databasen |

Tilkoblingen leses fra `KOMMUNELYS_DB_URL` eller `~/.kommunelys.env` (se
`lager/db.py`). Bruk Session pooler-adressen; den direkte er bare IPv6. I
GitHub Actions ligger den som hemmeligheten `KOMMUNELYS_DB_URL`.

| Mappe | Innhold |
|---|---|
| `migrations/` | Skjemaet som SQL, i rekkefølge. Filnavnet er versjonen databasen har registrert |
| `tests/regler.sql` | Prøver å bryte reglene (stemmetall, skjerming, RLS) og ser at de holder |

## Skjemaene

| Skjema | Innhold |
|---|---|
| `kjerne` | Domenedataene: kommuner, rådata, møter, saker, dokumenter, personer, voteringer, stemmer, oppmøte, verv, avvik, vurderinger, analyser |
| `drift` | Kjøringer, bygg og endringsloggen, som erstatter historikken fra git |
| `tilgang` | Hvem som ser hva: prosjektadmin, medlemskap per kommune, abonnement |
| `publisert` | Publiseringsreglene som views: tilbakeholdte voteringer og sammendrag |
| `portal` | Det portalen (portal.kommunelys.no) ser: views med `security_invoker` over de andre, så RLS gjelder (ADR-020) |
| `varsel` | «Følg saken» (ADR-027): hvem som følger hva (`folger`), det som er publisert i sakene (`sak_tilstand`), køen (`utsending`) og e-postene som er sendt (`epost`). Logges ikke i endringsloggen, og slettes med kontoen |

Ingenting ligger i `public`. Bare `portal` er eksponert gjennom Supabase-API-et (Data API, «Exposed schemas»), og bare for innloggede brukere.

Edge-funksjonen `brukeradmin` (`functions/brukeradmin/`) gjør det portalen ikke kan med den publiserbare nøkkelen: liste, invitere, sperre og slette brukere. Bare prosjektadmin kan bruke den. Prosjektadmin gis med SQL, som `postgres`:

```sql
insert into tilgang.prosjektadmin (user_id) select id from auth.users where email = '...';
```

Edge-funksjonen `varsel` (`functions/varsel/`) sender e-post til dem som følger saker (ADR-027), og tar imot «Slutt å følge». Den henter køen med e-postadressene gjennom `portal.varsel_til_sending()`, som bare service-nøkkelen kan kalle, og sender via Resend. Grensene står i databasen (`varsel.grense_dogn`, `varsel.grense_maned`) og på driftssiden (`bygg/drift.py`).

- Publiseres med `verify_jwt = false`, fordi e-postprogrammene sender «Slutt å følge» (`List-Unsubscribe-Post`) uten innlogging: `supabase functions deploy varsel --no-verify-jwt`. `send` krever hodet `x-varsel-nokkel`, og «slutt» en signert nøkkel.
- Hemmelighetene i funksjonen: `RESEND_API_KEY` (en nøkkel som bare kan sende), `VARSEL_NOKKEL` (den samme som hemmeligheten i Actions) og `VARSEL_HEMMELIGHET` (signerer lenkene; byttes den, slutter de gamle lenkene å virke).
- Oppdater sender bare når variabelen `VARSEL_SEND` er `1` i repoet. Til da legges varslene i køen, og driftssiden viser at de venter.
- Logikken kan prøves uten Supabase: `node --test supabase/functions/varsel/logikk.test.ts`.

## Regler databasen håndhever

- **Stemmetall (CLAUDE.md regel 1):** står `tall_stemmer` sant, må antall navn stemme med tallene, ellers stopper transaksjonen.
- **Skjerming (regel 4):**
  - Et skjermet vedtak kan ikke ha lenke eller tekst.
  - Blir et vedtak skjermet i ettertid, slettes teksten.
  - Teksten i møteinnkallingen lagres aldri (ADR-006).
- **Kildelenke (regel 1):** en analyse uten kilde kan ikke lagres. Et sammendrag vises bare når siste kontroll mot kilden er bestått.
- **Bare innsetting:** rådata, vurderinger, analyser og endringsloggen kan ikke endres eller slettes. En ny versjon er en ny rad.
- **Ingen kontaktopplysninger** i medlemslistene (ADR-014).
- **Kommune:** hver rad hører til én kommune, og fremmednøklene kan ikke peke på tvers.

## Roller

| Rolle | Brukes av | Kan |
|---|---|---|
| `kommunelys_pipeline` | henting, tolkning, analyse | lese og skrive `kjerne` og `drift`, ikke endre rådata |
| `kommunelys_bygg` | bygget av nettstedet | lese, og skrive bygg og analysekontroll |
| `authenticated` | innloggede brukere | lese det RLS slipper gjennom for kommunene de har tilgang til |
| `anon` | – | ingenting |

Rollene logger ikke inn før et passord er satt for hånd i SQL-editoren. Passordet skal aldri ligge i git:

```sql
alter role kommunelys_pipeline with login password '...';
```

## Endre skjemaet

1. Lag en ny fil i `migrations/`. Eldre filer endres aldri, siden de allerede er kjørt.
2. Kjør migreringen mot testprosjektet, og gi filen versjonsnummeret databasen registrerer.
3. Kjør `tests/regler.sql`. Svaret er en feilmelding som begynner med «RESULTAT n av m ok».

En ny tabell trenger RLS og policyer for rollene. Se `20261004212642_tilgang.sql`.

## Sikkerhetskopi

Arbeidsflyten `Sikkerhetskopi` i det private repoet `Kommunelys/sikkerhetskopi`
tar en kopi av skjemaene `kjerne` og `drift` hver natt (`pg_dump`) og lagrer
den som en fil på kjøringen i 30 dager. Brukere og
innlogging (`tilgang`, `auth`) er ikke med, og heller ikke hvem som følger
hvilke saker (`varsel`). Gratisplanen i Supabase har ingen
sikkerhetskopi å stole på, så dette er den eneste kopien utenfor databasen
når dataene ikke lenger ligger i git.

Kopien har data som ikke er åpne, og filene fra kjøringene i et offentlig repo
kan lastes ned av alle med en GitHub-konto. Derfor ligger den ikke her.

Gjenopprette til en tom database:

1. Kjør migreringene i `migrations/` (skjema, roller, regler).
2. Last ned kopien fra kjøringen i `Kommunelys/sikkerhetskopi`, og les den inn som `postgres`:
   `gzip -dc kommunelys-<dato>.sql.gz | psql "<adresse som postgres>"`.
   Kopien lager skjemaene selv; slett `kjerne` og `drift` fra trinn 1 først
   (`drop schema kjerne, drift cascade`), og kjør migreringene etter `drift`
   på nytt for policyer og rettigheter.
3. Sett passordene på rollene på nytt; de er aldri med i en kopi.
4. `python -m lager.paritet <år>` mot en eksport, eller bygg nettstedet med
   `KOMMUNELYS_LAGER=pg` og sammenlign med det publiserte.
