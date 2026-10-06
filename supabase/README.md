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

Ingenting ligger i `public`. Bare `portal` er eksponert gjennom Supabase-API-et (Data API, «Exposed schemas»), og bare for innloggede brukere.

Edge-funksjonen `brukeradmin` (`functions/brukeradmin/`) gjør det portalen ikke kan med den publiserbare nøkkelen: liste, invitere, sperre og slette brukere. Bare prosjektadmin kan bruke den. Prosjektadmin gis med SQL, som `postgres`:

```sql
insert into tilgang.prosjektadmin (user_id) select id from auth.users where email = '...';
```

## Regler databasen håndhever

- **Stemmetall (CLAUDE.md regel 2):** står `tall_stemmer` sant, må antall navn stemme med tallene, ellers stopper transaksjonen.
- **Skjerming (regel 3):**
  - Et skjermet vedtak kan ikke ha lenke eller tekst.
  - Blir et vedtak skjermet i ettertid, slettes teksten.
  - Teksten i møteinnkallingen lagres aldri (ADR-006).
- **Kildelenke (regel 5):** en analyse uten kilde kan ikke lagres. Et sammendrag vises bare når siste kontroll mot kilden er bestått.
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

Arbeidsflyten `Sikkerhetskopi` tar en kopi av skjemaene `kjerne` og `drift` hver
natt (`pg_dump`) og lagrer den som en fil på kjøringen i 90 dager. Brukere og
innlogging (`tilgang`, `auth`) er ikke med. Gratisplanen i Supabase har ingen
sikkerhetskopi å stole på, så dette er den eneste kopien utenfor databasen
når dataene ikke lenger ligger i git.

Gjenopprette til en tom database:

1. Kjør migreringene i `migrations/` (skjema, roller, regler).
2. Last ned kopien fra kjøringen, og les den inn som `postgres`:
   `gzip -dc kommunelys-<dato>.sql.gz | psql "<adresse som postgres>"`.
   Kopien lager skjemaene selv; slett `kjerne` og `drift` fra trinn 1 først
   (`drop schema kjerne, drift cascade`), og kjør migreringene etter `drift`
   på nytt for policyer og rettigheter.
3. Sett passordene på rollene på nytt; de er aldri med i en kopi.
4. `python -m lager.paritet <år>` mot en eksport, eller bygg nettstedet med
   `KOMMUNELYS_LAGER=pg` og sammenlign med det publiserte.
