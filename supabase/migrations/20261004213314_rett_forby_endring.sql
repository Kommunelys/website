-- Rettelse: uten argumenter er tg_argv NULL, ikke en tom liste. Da ble
-- sammenligningen NULL, og endringer i rådata, vurderinger og endringsloggen
-- slapp gjennom. Funnet av supabase/tests/regler.sql.
create or replace function kjerne.forby_endring() returns trigger
language plpgsql set search_path = '' as $$
declare
  tillatt text[] := coalesce(tg_argv, '{}');
begin
  if tg_op = 'DELETE' or tg_op = 'TRUNCATE' then
    raise exception '%.% kan ikke slettes', tg_table_schema, tg_table_name
      using errcode = 'insufficient_privilege';
  end if;
  if (to_jsonb(new) - tillatt) is distinct from (to_jsonb(old) - tillatt) then
    raise exception '%.% kan ikke endres; legg inn en ny rad', tg_table_schema, tg_table_name
      using errcode = 'insufficient_privilege';
  end if;
  return new;
end $$;
