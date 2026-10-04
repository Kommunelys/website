-- Resultatet av lager.paritet for hver kjøring: om databasen ga det samme som
-- filene i data/, og hva som skilte. Vises på driftssiden fram til databasen
-- blir kilden.
create table drift.paritet (
  id bigint generated always as identity primary key,
  kommune_id smallint not null references kjerne.kommune,
  aar smallint not null,
  kjoring_id text,
  kontrollert timestamptz not null default now(),
  likt boolean not null,
  kontroller smallint not null check (kontroller > 0),
  ulike jsonb not null default '[]' check (jsonb_typeof(ulike) = 'array'),
  check (likt = (jsonb_array_length(ulike) = 0))
);

create index paritet_siste on drift.paritet (kommune_id, kontrollert desc);

alter table drift.paritet enable row level security;
create policy pipeline on drift.paritet to kommunelys_pipeline using (true) with check (true);
create policy bygg_leser on drift.paritet for select to kommunelys_bygg using (true);
create policy les_som_prosjektadmin on drift.paritet for select to authenticated
  using ((select tilgang.er_prosjektadmin()));
grant select, insert on drift.paritet to kommunelys_pipeline;
grant select on drift.paritet to kommunelys_bygg, authenticated;
