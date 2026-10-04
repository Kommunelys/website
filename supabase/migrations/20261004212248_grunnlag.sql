-- Grunnlaget: skjemaer og roller.
--
-- kjerne    domenedataene: kommuner, rådata, møter, saker, voteringer, ...
-- drift     kjøringer, bygg og endringsloggen
-- tilgang   hvem som får se hva (medlemskap, abonnement), med hjelpefunksjoner
-- publisert views med publiseringsreglene; det eneste bygget leser
--
-- Ingenting legges i public. Supabase gir anon og authenticated rettigheter
-- der som standard, og PostgREST eksponerer det. Disse skjemaene eksponeres
-- ikke, og ingen får rettigheter uten at en migrering gir dem.

create schema kjerne;
create schema drift;
create schema tilgang;
create schema publisert;

revoke all on schema kjerne, drift, tilgang, publisert from public;

comment on schema kjerne is 'Kommunelys: domenedata. Skrives bare av pipelinen.';
comment on schema drift is 'Kommunelys: kjøringer, bygg og endringslogg.';
comment on schema tilgang is 'Kommunelys: tilgangsstyring per kommune.';
comment on schema publisert is 'Kommunelys: det som kan publiseres, med reglene i SQL.';

-- Rollene logger ikke inn før et passord er satt for hånd (aldri i git):
--   alter role kommunelys_pipeline with login password '...';
-- Pipelinen kobler aldri til som postgres: eieren går forbi RLS.
do $$
begin
  if not exists (select from pg_roles where rolname = 'kommunelys_pipeline') then
    create role kommunelys_pipeline nologin;
  end if;
  if not exists (select from pg_roles where rolname = 'kommunelys_bygg') then
    create role kommunelys_bygg nologin;
  end if;
end $$;

comment on role kommunelys_pipeline is 'Henting, tolkning og analyse. Skriver i kjerne og drift.';
comment on role kommunelys_bygg is 'Bygget av nettstedet. Leser publisert, skriver bygg og analysekontroll.';

grant usage on schema kjerne, drift to kommunelys_pipeline;
grant usage on schema kjerne, drift, publisert to kommunelys_bygg;

-- For exclusion-constraint på abonnementsperioder (tilgang.abonnement).
create extension if not exists btree_gist with schema extensions;
