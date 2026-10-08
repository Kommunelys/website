-- portal.nettsted_fil (ADR-024): parameteren «kommune» var tvetydig mot
-- tabellen kjerne.kommune, så funksjonen feilet for alle. Navnene på
-- parameterne står (de er adressen nettstedet bruker), men kvalifiseres.

create or replace function portal.nettsted_fil(kommune text, fil text) returns text
language plpgsql stable security invoker set search_path = '' as $$
declare
  k smallint;
begin
  select km.kommune_id into k from kjerne.kommune km where km.slug = nettsted_fil.kommune;
  if k is null or not (k = any (tilgang.innsyn_kommuner())) then
    raise exception 'ingen tilgang til %', nettsted_fil.kommune using errcode = '42501';
  end if;
  return (select f.innhold from drift.nettsted_fil f where f.kommune_id = k and f.sti = nettsted_fil.fil);
end $$;

revoke all on function portal.nettsted_fil(text, text) from public, anon;
grant execute on function portal.nettsted_fil(text, text) to authenticated;

notify pgrst, 'reload schema';
