-- Tilgang per kommune, med RLS på hver tabell.
--
-- Nettstedet er statisk og bruker ikke dette; det bygges av pipelinen. Dette
-- er for innloggede brukere senere: prosjektadministratorer, de som vurderer
-- avvik for en kommune, og eventuelle betalte tilleggstjenester.
--
-- Prinsipp: tilgang gir funksjoner (for eksempel API eller fulltekst), aldri
-- mer innhold enn det som er publisert. Tilbakeholdte voteringer og
-- sammendrag holdes tilbake fordi de kan være feil, ikke av kommersielle
-- grunner. Skjermet innhold lagres aldri.

-- Tabeller -----------------------------------------------------------------------

create table tilgang.produkt (
  produkt text primary key check (produkt ~ '^[a-z_]+$'),
  beskrivelse text not null
);

insert into tilgang.produkt (produkt, beskrivelse) values
  ('api', 'Lesetilgang til de publiserte dataene for kommunen'),
  ('fulltekst', 'Teksten i offentlige saksdokumenter for kommunen');

create table tilgang.prosjektadmin (
  user_id uuid primary key references auth.users on delete cascade,
  lagt_til timestamptz not null default now()
);

create table tilgang.medlemskap (
  user_id uuid not null references auth.users on delete cascade,
  kommune_id smallint not null references kjerne.kommune,
  rolle text not null check (rolle in ('admin', 'vurderer')),
  lagt_til timestamptz not null default now(),
  primary key (user_id, kommune_id)
);

create table tilgang.abonnement (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users on delete cascade,
  kommune_id smallint not null references kjerne.kommune,
  produkt text not null references tilgang.produkt,
  gyldig tstzrange not null check (not isempty(gyldig) and not lower_inf(gyldig)),
  kilde text not null check (kilde in ('manuell', 'betaling')),
  ekstern_ref text,
  exclude using gist (user_id with =, kommune_id with =, produkt with =, gyldig with &&)
);

create index abonnement_bruker on tilgang.abonnement (user_id);

-- Hjelpefunksjoner ---------------------------------------------------------------
-- security definer: de leser tilgangstabellene, som brukeren selv ikke ser
-- alt av. search_path er tom, så alle navn er fullt kvalifisert.
-- Kalles som (select tilgang.f()) i policyene, så de regnes ut én gang per
-- spørring, ikke per rad.

create function tilgang.er_prosjektadmin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from tilgang.prosjektadmin where user_id = (select auth.uid()))
$$;

-- Kommuner brukeren kan se for et produkt: medlemmer ser sin kommune,
-- abonnenter det de har gyldig abonnement på, prosjektadmin alle.
create function tilgang.kommuner_med(p_produkt text) returns smallint[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(distinct kommune_id), '{}')
  from (
    select m.kommune_id from tilgang.medlemskap m
    where m.user_id = (select auth.uid())
    union all
    select a.kommune_id from tilgang.abonnement a
    where a.user_id = (select auth.uid()) and a.produkt = p_produkt and now() <@ a.gyldig
    union all
    select k.kommune_id from kjerne.kommune k where tilgang.er_prosjektadmin()
  ) as x
$$;

-- Kommuner der brukeren kan vurdere avvik (admin eller vurderer).
create function tilgang.vurderer_kommuner() returns smallint[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(distinct kommune_id), '{}')
  from (
    select m.kommune_id from tilgang.medlemskap m
    where m.user_id = (select auth.uid())
    union all
    select k.kommune_id from kjerne.kommune k where tilgang.er_prosjektadmin()
  ) as x
$$;

-- Kommuner der brukeren er administrator.
create function tilgang.admin_kommuner() returns smallint[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(distinct kommune_id), '{}')
  from (
    select m.kommune_id from tilgang.medlemskap m
    where m.user_id = (select auth.uid()) and m.rolle = 'admin'
    union all
    select k.kommune_id from kjerne.kommune k where tilgang.er_prosjektadmin()
  ) as x
$$;

revoke all on function tilgang.er_prosjektadmin(), tilgang.kommuner_med(text),
  tilgang.vurderer_kommuner(), tilgang.admin_kommuner() from public, anon;
grant usage on schema tilgang to authenticated;
grant execute on function tilgang.er_prosjektadmin(), tilgang.kommuner_med(text),
  tilgang.vurderer_kommuner(), tilgang.admin_kommuner() to authenticated;

-- RLS på alt --------------------------------------------------------------------

do $$
declare
  t record;
begin
  for t in
    select schemaname, tablename from pg_tables
    where schemaname in ('kjerne', 'drift', 'tilgang')
  loop
    execute format('alter table %I.%I enable row level security', t.schemaname, t.tablename);
  end loop;
end $$;

-- Pipelinen: leser og skriver kjerne og drift. Egne policyer i stedet for
-- BYPASSRLS, så det står i databasen hvem som kan skrive hva.
-- Bygget: leser kjerne og drift, skriver bare bygg og analysekontroll.
do $$
declare
  t record;
begin
  for t in
    select schemaname, tablename from pg_tables where schemaname in ('kjerne', 'drift')
  loop
    execute format('create policy pipeline on %I.%I to kommunelys_pipeline using (true) with check (true)',
                   t.schemaname, t.tablename);
    execute format('create policy bygg_leser on %I.%I for select to kommunelys_bygg using (true)',
                   t.schemaname, t.tablename);
    execute format('grant select, insert, update, delete on %I.%I to kommunelys_pipeline',
                   t.schemaname, t.tablename);
    execute format('grant select on %I.%I to kommunelys_bygg', t.schemaname, t.tablename);
  end loop;
end $$;

grant usage on all sequences in schema kjerne, drift to kommunelys_pipeline, kommunelys_bygg;

-- Endringsloggen skrives bare av triggeren.
revoke insert, update, delete on drift.endringslogg from kommunelys_pipeline;

create policy bygg_skriver on drift.bygg for insert to kommunelys_bygg with check (true);
create policy bygg_skriver on kjerne.analyse_kontroll for insert to kommunelys_bygg with check (true);
grant insert on drift.bygg, kjerne.analyse_kontroll to kommunelys_bygg;

-- Innloggede brukere: data for kommunene de har tilgang til ----------------------

grant usage on schema kjerne to authenticated;

do $$
declare
  t text;
begin
  -- Det som er offentlig på nettstedet: lesetilgang med produktet «api».
  foreach t in array array[
    'utvalg', 'utvalg_aar', 'parti', 'person', 'mote', 'sak', 'saksgang_steg',
    'dokument', 'vedtak_tolket', 'votering', 'votering_alternativ', 'stemme',
    'oppmote_mote', 'oppmote', 'oppmote_avvik', 'verv', 'analyse', 'analyse_kontroll']
  loop
    execute format(
      'create policy les_med_tilgang on kjerne.%I for select to authenticated '
      'using (kommune_id = any ((select tilgang.kommuner_med(''api''))::smallint[]))', t);
    execute format('grant select on kjerne.%I to authenticated', t);
  end loop;

  -- Arbeidsdata for dem som vurderer avvik i kommunen.
  foreach t in array array[
    'avvik', 'avvik_votering', 'vurdering', 'tillatt_navn', 'navnevariant', 'person_portal_id']
  loop
    execute format(
      'create policy les_som_vurderer on kjerne.%I for select to authenticated '
      'using (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]))', t);
    execute format('grant select on kjerne.%I to authenticated', t);
  end loop;
end $$;

create policy les_med_fulltekst on kjerne.dokument_tekst for select to authenticated
  using (kommune_id = any ((select tilgang.kommuner_med('fulltekst'))::smallint[]));
grant select on kjerne.dokument_tekst to authenticated;

create policy alle_leser on kjerne.kommune for select to authenticated using (true);
create policy alle_leser on kjerne.tagg for select to authenticated using (true);
grant select on kjerne.kommune, kjerne.tagg to authenticated;

-- Rådata: bare prosjektadmin.
create policy les_som_prosjektadmin on kjerne.raa_svar for select to authenticated
  using ((select tilgang.er_prosjektadmin()));
grant select on kjerne.raa_svar to authenticated;

-- Vurderinger og tillatte navn kan legges inn av dem som har rollen.
create policy vurderer_skriver on kjerne.vurdering for insert to authenticated
  with check (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[])
              and registrert_av = (select auth.uid()));
create policy admin_skriver on kjerne.tillatt_navn for insert to authenticated
  with check (kommune_id = any ((select tilgang.admin_kommuner())::smallint[])
              and registrert_av = (select auth.uid()));
grant insert on kjerne.vurdering, kjerne.tillatt_navn to authenticated;

-- Brukeren ser sine egne medlemskap og abonnement. Endringer gjøres av
-- prosjektadmin, eller av betalingsløsningen med service_role.
create policy egne on tilgang.medlemskap for select to authenticated
  using (user_id = (select auth.uid()) or (select tilgang.er_prosjektadmin()));
create policy egne on tilgang.abonnement for select to authenticated
  using (user_id = (select auth.uid()) or (select tilgang.er_prosjektadmin()));
create policy prosjektadmin_skriver on tilgang.medlemskap for all to authenticated
  using ((select tilgang.er_prosjektadmin())) with check ((select tilgang.er_prosjektadmin()));
create policy prosjektadmin_skriver on tilgang.abonnement for all to authenticated
  using ((select tilgang.er_prosjektadmin())) with check ((select tilgang.er_prosjektadmin()));
create policy alle_leser on tilgang.produkt for select to authenticated using (true);
create policy egen on tilgang.prosjektadmin for select to authenticated
  using (user_id = (select auth.uid()));

grant select on tilgang.produkt, tilgang.prosjektadmin to authenticated;
grant select, insert, update, delete on tilgang.medlemskap, tilgang.abonnement to authenticated;

-- Drift: bare prosjektadmin.
grant usage on schema drift to authenticated;
do $$
declare
  t text;
begin
  foreach t in array array['kjoring', 'kjoring_tall', 'bygg', 'endringslogg'] loop
    execute format(
      'create policy les_som_prosjektadmin on drift.%I for select to authenticated '
      'using ((select tilgang.er_prosjektadmin()))', t);
    execute format('grant select on drift.%I to authenticated', t);
  end loop;
end $$;
