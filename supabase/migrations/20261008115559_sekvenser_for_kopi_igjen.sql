-- Sikkerhetskopien (pg_dump som kommunelys_pipeline) har feilet siden
-- 7.10.2026: drift.side_id_seq (portal) og sekvensene til de nye tabellene i
-- vurdering_per_kommune fikk bare USAGE. pg_dump leser verdien i hver sekvens.
-- Standardrettighetene gjør at nye sekvenser i kjerne og drift får det samme.
grant select, usage on all sequences in schema kjerne, drift to kommunelys_pipeline;
alter default privileges in schema kjerne, drift
  grant select, usage on sequences to kommunelys_pipeline;
