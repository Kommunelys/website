# supabase/

Databaseskjemaet for Kommunelys (Postgres i Supabase). Første steg i flyttingen
fra JSON i git til en database. Nettstedet bruker den ikke ennå: produksjon
leser og skriver fortsatt `data/`.

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

Ingenting ligger i `public`, og ingen av skjemaene er eksponert gjennom Supabase-API-et.

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
