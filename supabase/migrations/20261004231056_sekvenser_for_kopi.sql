-- pg_dump leser verdien i hver sekvens (identity-kolonnene). Sikkerhetskopien
-- tas med kommunelys_pipeline, som bare hadde USAGE. Gjelder også drift.paritet,
-- som kom etter forrige tildeling.
grant select, usage on all sequences in schema kjerne, drift to kommunelys_pipeline;
