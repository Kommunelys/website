-- Kjøringer, bygg og endringslogg.
--
-- I dag finnes historikken i git: hver kjøring committer data/, og
-- drift/historikk.py leser diffene. Med databasen som kilde tar
-- endringsloggen over: hver innsetting, endring og sletting i kjerne
-- logges med kjøringen som gjorde den. Store felt (tekst, rå innhold) logges
-- ikke; de har sine egne versjoner.

create table drift.kjoring (
  kjoring_id text primary key,  -- GITHUB_RUN_ID, «lokal-<dato>» eller «import-…»
  kilde text not null check (kilde in ('actions', 'lokal', 'import')),
  start timestamptz not null default now(),
  slutt timestamptz,
  git_sha text
);

-- Tall fra kjøringen som ikke kan leses ut av dataene etterpå: kall mot
-- portalen, hvordan analysen gikk (data/drift/kjoringer.json i dag).
create table drift.kjoring_tall (
  kjoring_id text not null references drift.kjoring on update cascade,
  kommune_id smallint references kjerne.kommune,
  del text not null check (del ~ '^[a-z_]+$'),
  nokkel text not null check (nokkel ~ '^[a-z_]+$'),
  verdi numeric not null
);

create unique index kjoring_tall_nokkel
  on drift.kjoring_tall (kjoring_id, coalesce(kommune_id, 0), del, nokkel);

-- Ett bygg av nettstedet for én kommune og ett år. Erstatter
-- data/forrige-telling.json: kontrollen av at antall saker ikke stuper,
-- leser forrige rad.
create table drift.bygg (
  id bigint generated always as identity primary key,
  kommune_id smallint not null references kjerne.kommune,
  aar smallint not null,
  bygget timestamptz not null default now(),
  kjoring_id text,
  saker int not null check (saker >= 0),
  status jsonb not null check (jsonb_typeof(status) = 'object')
);

create index bygg_siste on drift.bygg (kommune_id, aar, bygget desc);

create table drift.endringslogg (
  id bigint generated always as identity primary key,
  tidspunkt timestamptz not null default now(),
  kommune_id smallint,
  kjoring_id text,
  tabell text not null,
  operasjon char(1) not null check (operasjon in ('I', 'U', 'D')),
  nokkel jsonb not null,
  endrede_felt text[],
  gammel jsonb,
  ny jsonb,
  db_rolle text not null default current_user,
  bruker_id uuid default auth.uid()
);

create index endringslogg_kjoring on drift.endringslogg (kjoring_id);
create index endringslogg_kommune on drift.endringslogg (kommune_id, tidspunkt desc);
create index endringslogg_tabell on drift.endringslogg (tabell, operasjon);

create trigger forby_endring before update or delete on drift.endringslogg
  for each row execute function kjerne.forby_endring();
create trigger forby_tomming before truncate on drift.endringslogg
  for each statement execute function kjerne.forby_endring();

-- Argumentene er primærnøkkelen. Kjøringen settes per transaksjon:
--   select set_config('kommunelys.kjoring_id', '<id>', true);
-- Kjører som eieren, så ingen rolle trenger å skrive i loggen selv.
create function drift.logg_endring() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  utelat constant text[] := array['tekst', 'innhold'];
  gammel jsonb;
  ny jsonb;
  felt text[];
  nokkel jsonb;
begin
  if tg_op <> 'INSERT' then
    gammel := to_jsonb(old) - utelat;
  end if;
  if tg_op <> 'DELETE' then
    ny := to_jsonb(new) - utelat;
  end if;

  if tg_op = 'UPDATE' then
    select array_agg(k order by k) into felt
    from jsonb_object_keys(ny) as k
    where ny -> k is distinct from gammel -> k;
    if felt is null then
      return null;  -- ingen endring; uendrede rader logges ikke
    end if;
  end if;

  select jsonb_object_agg(k, coalesce(ny, gammel) -> k) into nokkel
  from unnest(tg_argv) as k;

  insert into drift.endringslogg
    (kommune_id, kjoring_id, tabell, operasjon, nokkel, endrede_felt, gammel, ny)
  values (
    (coalesce(ny, gammel) ->> 'kommune_id')::smallint,
    nullif(current_setting('kommunelys.kjoring_id', true), ''),
    tg_table_name, left(tg_op, 1), nokkel, felt, gammel, ny);
  return null;
end $$;

revoke all on function drift.logg_endring() from public;

do $$
declare
  t record;
begin
  for t in
    select * from (values
      ('kommune', array['kommune_id']),
      ('utvalg', array['kommune_id', 'utvalg_id']),
      ('parti', array['kommune_id', 'kode']),
      ('person', array['kommune_id', 'id']),
      ('person_portal_id', array['kommune_id', 'portal_person_id']),
      ('navnevariant', array['kommune_id', 'variant']),
      ('mote', array['kommune_id', 'mote_id']),
      ('sak', array['kommune_id', 'sak_id']),
      ('saksgang_steg', array['kommune_id', 'behandling_id']),
      ('dokument', array['kommune_id', 'id_rom', 'portal_id']),
      ('dokument_tekst', array['kommune_id', 'dokument_id']),
      ('vedtak_tolket', array['kommune_id', 'behandling_id']),
      ('votering', array['kommune_id', 'behandling_id', 'nr']),
      ('votering_alternativ', array['kommune_id', 'behandling_id', 'nr', 'forslag']),
      ('stemme', array['kommune_id', 'behandling_id', 'nr', 'person_id']),
      ('oppmote', array['kommune_id', 'mote_id', 'person_id']),
      ('verv', array['kommune_id', 'aar', 'utvalg_id', 'person_id']),
      ('avvik', array['kommune_id', 'avvik']),
      ('vurdering', array['kommune_id', 'id']),
      ('analyse', array['kommune_id', 'id']),
      ('tillatt_navn', array['kommune_id', 'navn', 'sak_id'])
    ) as v(tabell, nokkel)
  loop
    execute format(
      'create trigger logg_endring after insert or update or delete on kjerne.%I '
      'for each row execute function drift.logg_endring(%s)',
      t.tabell, (select string_agg(quote_literal(k), ', ') from unnest(t.nokkel) as k));
  end loop;
end $$;
