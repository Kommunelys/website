-- Begrenset innsyn (ADR-024).
--
-- En kommune med status «begrenset» står på forsiden og kartet, men innholdet
-- er bare for innloggede med en rolle for kommunen (leser, vurderer eller
-- admin) og for prosjektadmin. Sidene er de samme som for en publisert
-- kommune; dataene (data.json og detaljer-<år>.json) publiseres ikke på
-- nettstedet, men lagres her og hentes med innloggingen.

-- Status og rolle -----------------------------------------------------------------

alter table kjerne.kommune drop constraint kommune_status_check;
alter table kjerne.kommune add constraint kommune_status_check
  check (status in ('kartlegging', 'intern', 'begrenset', 'publisert'));

alter table tilgang.medlemskap drop constraint medlemskap_rolle_check;
alter table tilgang.medlemskap add constraint medlemskap_rolle_check
  check (rolle in ('admin', 'vurderer', 'leser'));

-- Leser gir innsyn, ikke vurdering. Før var alle rollene vurderer.
create or replace function tilgang.vurderer_kommuner() returns smallint[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(distinct kommune_id), '{}')
  from (
    select m.kommune_id from tilgang.medlemskap m
    where m.user_id = (select auth.uid()) and m.rolle in ('admin', 'vurderer')
    union all
    select k.kommune_id from kjerne.kommune k where tilgang.er_prosjektadmin()
  ) as x
$$;

-- Kommuner brukeren kan se med begrenset innsyn: alle rollene, og prosjektadmin.
create function tilgang.innsyn_kommuner() returns smallint[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(distinct kommune_id), '{}')
  from (
    select m.kommune_id from tilgang.medlemskap m
    where m.user_id = (select auth.uid())
    union all
    select k.kommune_id from kjerne.kommune k where tilgang.er_prosjektadmin()
  ) as x
$$;

revoke all on function tilgang.innsyn_kommuner() from public, anon;
grant execute on function tilgang.innsyn_kommuner() to authenticated;

-- Dataene til nettstedet -----------------------------------------------------------

-- Skrives av bygget (kjor.alle) for kommunene med begrenset innsyn, og byttes
-- ut helt ved hvert bygg. Ingen endringslogg: det er en kopi av det som
-- bygges fra kjerne.
create table drift.nettsted_fil (
  kommune_id smallint not null references kjerne.kommune,
  sti text not null check (sti ~ '^[a-z0-9-]+\.json$'),
  innhold text not null check (length(innhold) > 0),
  bygget timestamptz not null default now(),
  primary key (kommune_id, sti)
);

alter table drift.nettsted_fil enable row level security;
create policy pipeline on drift.nettsted_fil to kommunelys_pipeline using (true) with check (true);
create policy bygg on drift.nettsted_fil to kommunelys_bygg using (true) with check (true);
create policy les_med_innsyn on drift.nettsted_fil for select to authenticated
  using (kommune_id = any ((select tilgang.innsyn_kommuner())::smallint[]));
grant select, insert, update, delete on drift.nettsted_fil to kommunelys_pipeline, kommunelys_bygg;
grant select on drift.nettsted_fil to authenticated;

-- Nettstedet henter én fil med innloggingen: GET /rest/v1/rpc/nettsted_fil
-- med Accept-Profile: portal. Uten rolle for kommunen: 42501, som
-- PostgREST gir som 403. Finnes ikke filen: null.
create function portal.nettsted_fil(kommune text, fil text) returns text
language plpgsql stable security invoker set search_path = '' as $$
declare
  k smallint;
begin
  select kommune_id into k from kjerne.kommune where slug = kommune;
  if k is null or not (k = any (tilgang.innsyn_kommuner())) then
    raise exception 'ingen tilgang til %', kommune using errcode = '42501';
  end if;
  return (select innhold from drift.nettsted_fil where kommune_id = k and sti = fil);
end $$;

revoke all on function portal.nettsted_fil(text, text) from public, anon;
grant execute on function portal.nettsted_fil(text, text) to authenticated;

notify pgrst, 'reload schema';
