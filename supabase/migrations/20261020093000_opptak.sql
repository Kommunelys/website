-- Opptak av møtene, kommunens teksting av dem og sammendrag av debatten
-- (ADR-026).
--
-- Opptaket ligger hos kommunen (Steinkjer: steinkjer.kommunetv.no). Vi lagrer
-- lenken, bokmerkene for sakene med start og varighet, og tekstingen når
-- opptaket er tekstet. Videoen lagres ikke. Opptakene kan bli slettet hos
-- kommunen; da settes «fjernet», og lenken vises ikke lenger.

-- Rådata fra opptakstjenesten ------------------------------------------------
alter table kjerne.raa_svar drop constraint raa_svar_kilde_check;
alter table kjerne.raa_svar add constraint raa_svar_kilde_check
  check (kilde in ('moteliste', 'mote', 'medlemsliste', 'opptak', 'teksting'));

-- Opptaket av et møte ----------------------------------------------------------
create table kjerne.opptak (
  kommune_id smallint not null,
  mote_id int not null,
  opptak_id int not null,  -- ID-en i opptakstjenesten
  url text not null check (url ~ '^https://'),
  varighet_s int check (varighet_s >= 0),
  teksting boolean not null default false,
  -- Bokmerkene: [{bokmerke_id, nummer, saksnr, behandling_id, sak_id, tittel,
  -- start_ms, varighet_ms}]. behandling_id er null for bokmerker uten sak.
  deler jsonb not null check (jsonb_typeof(deler) = 'array'),
  hentet timestamptz not null default now(),
  fjernet date,
  primary key (kommune_id, mote_id),
  unique (kommune_id, opptak_id),
  foreign key (kommune_id, mote_id) references kjerne.mote deferrable
);

comment on table kjerne.opptak is
  'Opptaket av et møte hos kommunen, med bokmerkene for sakene. Videoen lagres ikke.';

-- Tekstingen av et opptak -------------------------------------------------------
-- Bare innsetting: endrer kommunen tekstingen, er det en ny rad.
create table kjerne.teksting (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  opptak_id int not null,
  kilde text not null check (kilde in ('kommunetv-teksting')),
  sjekksum text not null,
  -- [{start_ms, slutt_ms, tekst}], i rekkefølge.
  linjer jsonb not null check (jsonb_typeof(linjer) = 'array' and jsonb_array_length(linjer) > 0),
  hentet timestamptz not null default now(),
  kjoring_id text,
  unique (kommune_id, opptak_id, sjekksum),
  foreign key (kommune_id, opptak_id) references kjerne.opptak (kommune_id, opptak_id) deferrable
);

create index teksting_siste on kjerne.teksting (kommune_id, opptak_id, hentet desc, id desc);

create view kjerne.teksting_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, opptak_id) *
  from kjerne.teksting
  order by kommune_id, opptak_id, hentet desc, id desc;

create trigger forby_endring before update or delete on kjerne.teksting
  for each row execute function kjerne.forby_endring();
create trigger forby_tomming before truncate on kjerne.teksting
  for each statement execute function kjerne.forby_endring();

-- Sammendraget av debatten om en behandling -----------------------------------
-- Bare innsetting, som analysene. Stemmetall og utfall står aldri her; de
-- kommer fra protokollen (ADR-002).
create table kjerne.debatt (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  behandling_id int not null,
  opptak_id int not null,
  ingen_debatt boolean not null,
  oppsummering text not null,
  antall_innlegg smallint not null check (antall_innlegg >= 0),
  -- [{tekst, partier, del, tid_s}]
  punkter jsonb not null check (jsonb_typeof(punkter) = 'array'),
  sjekksum text not null,
  modell text not null,
  innsats text not null,
  instruksjon_versjon smallint not null,
  dato date not null,
  tokens_inn int not null default 0 check (tokens_inn >= 0),
  tokens_ut int not null default 0 check (tokens_ut >= 0),
  -- CLAUDE.md regel 5: uten kildelenke publiseres det ikke.
  kilder jsonb not null check (jsonb_typeof(kilder) = 'array' and jsonb_array_length(kilder) >= 1),
  opprettet timestamptz not null default now(),
  kjoring_id text,
  unique (kommune_id, id),
  foreign key (kommune_id, behandling_id) references kjerne.saksgang_steg deferrable,
  foreign key (kommune_id, opptak_id) references kjerne.opptak (kommune_id, opptak_id) deferrable,
  check (ingen_debatt or btrim(oppsummering) <> '')
);

create index debatt_siste on kjerne.debatt (kommune_id, behandling_id, opprettet desc, id desc);

create view kjerne.debatt_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, behandling_id) *
  from kjerne.debatt
  order by kommune_id, behandling_id, opprettet desc, id desc;

create trigger forby_endring before update or delete on kjerne.debatt
  for each row execute function kjerne.forby_endring();
create trigger forby_tomming before truncate on kjerne.debatt
  for each statement execute function kjerne.forby_endring();

-- Endringsloggen. Tekstingen logges ikke; den er stor og endres aldri.
create trigger logg_endring after insert or update or delete on kjerne.opptak
  for each row execute function drift.logg_endring('kommune_id', 'mote_id');
create trigger logg_endring after insert or update or delete on kjerne.debatt
  for each row execute function drift.logg_endring('kommune_id', 'id');

-- Tilgang, som for de andre tabellene i kjerne (20261004212642_tilgang.sql) ----
alter table kjerne.opptak enable row level security;
alter table kjerne.teksting enable row level security;
alter table kjerne.debatt enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array['opptak', 'teksting', 'debatt'] loop
    execute format('create policy pipeline on kjerne.%I to kommunelys_pipeline using (true) with check (true)', t);
    execute format('create policy bygg_leser on kjerne.%I for select to kommunelys_bygg using (true)', t);
    execute format('grant select, insert, update, delete on kjerne.%I to kommunelys_pipeline', t);
    execute format('grant select on kjerne.%I to kommunelys_bygg', t);
  end loop;
end $$;

grant select on kjerne.teksting_gjeldende, kjerne.debatt_gjeldende to kommunelys_pipeline, kommunelys_bygg;
grant select, usage on all sequences in schema kjerne to kommunelys_pipeline;
grant usage on all sequences in schema kjerne to kommunelys_bygg;

-- Innloggede: opptaket og debatten er publisert som resten; tekstingen er
-- fulltekst, som teksten i dokumentene.
create policy les_med_tilgang on kjerne.opptak for select to authenticated
  using (kommune_id = any ((select tilgang.kommuner_med('api'))::smallint[]));
create policy les_med_tilgang on kjerne.debatt for select to authenticated
  using (kommune_id = any ((select tilgang.kommuner_med('api'))::smallint[]));
create policy les_med_fulltekst on kjerne.teksting for select to authenticated
  using (kommune_id = any ((select tilgang.kommuner_med('fulltekst'))::smallint[]));
grant select on kjerne.opptak, kjerne.debatt, kjerne.teksting,
  kjerne.teksting_gjeldende, kjerne.debatt_gjeldende to authenticated;
