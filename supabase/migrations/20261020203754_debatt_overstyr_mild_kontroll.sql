-- Rettelse til 20261020203251_debatt_vurdering.sql (ADR-026).
--
-- Den milde kontrollen (prosjekteier, 20.10.2026) skriver «AP er verken nevnt
-- eller ropt opp i del 1», uten «nær <tid>». Mønsteret godtok bare den gamle
-- teksten, så en vurderer kunne ikke slippe gjennom de nye. Begge godtas.
-- Samme regel står i analyser.analyser_debatt.kan_overstyres.
create or replace function kjerne.debatt_kan_overstyres(grunner text[]) returns boolean
language sql immutable set search_path = '' as $$
  select cardinality(grunner) > 0
     and not exists (select 1 from unnest(grunner) as g
                     where g !~ '^(partiet \S+ var ikke i møtet|\S+ er verken nevnt eller ropt opp( nær \S+)? i del \d+)$')
$$;
