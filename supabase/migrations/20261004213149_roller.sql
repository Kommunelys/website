-- postgres må kunne bytte til rollene for å teste dem (supabase/tests/) og
-- sette passord. Fra Postgres 16 får den som oppretter en rolle ikke dette
-- automatisk. INHERIT FALSE: postgres får ikke rollenes rettigheter, bare
-- lov til å bytte til dem.
grant kommunelys_pipeline to postgres with inherit false, set true;
grant kommunelys_bygg to postgres with inherit false, set true;
