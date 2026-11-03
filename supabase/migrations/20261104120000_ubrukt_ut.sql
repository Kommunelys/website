-- Det som ikke brukes, ut av databasen (gjennomgangen 31.10 og ryddingen
-- 1.11.2026). Ingenting her leses av koden, portalen eller edge-funksjonene.
-- Det som forsvinner, finnes i sikkerhetskopien tatt rett før migreringen.
--
-- En kopi tatt før denne migreringen har tabellene og kolonnene under, og må
-- leses inn med migreringene slik de var da (fra historikken i git).

-- Publiseringsreglene som views. Bygget holder tilbake i Python
-- (tolk/bygg_avvik, bygg/bygg_nettsted), og ingen leste disse.
drop view publisert.sammendrag, publisert.votering_alternativ, publisert.stemme,
  publisert.votering, publisert.votering_status;
drop schema publisert;

-- Rollen for et eget bygg. Bygget kjører som kommunelys_pipeline, og denne
-- rollen kan ikke logge inn. Policyene er bare for den, og tas med den.
-- (drop owned by går ikke i Supabase: postgres er ikke superbruker.)
do $$
declare p record;
begin
  for p in select schemaname, tablename, policyname, roles from pg_policies where 'kommunelys_bygg' = any (roles) loop
    if p.roles <> '{kommunelys_bygg}' then
      raise exception 'policyen % på %.% gjelder flere roller', p.policyname, p.schemaname, p.tablename;
    end if;
    execute format('drop policy %I on %I.%I', p.policyname, p.schemaname, p.tablename);
  end loop;
end $$;
revoke all on all tables in schema kjerne, drift, varsel from kommunelys_bygg;
revoke all on all sequences in schema kjerne, drift, varsel from kommunelys_bygg;
revoke all on all functions in schema kjerne, drift, varsel from kommunelys_bygg;
revoke all on schema kjerne, drift, varsel from kommunelys_bygg;
drop role kommunelys_bygg;

-- Navnevariantene og de tillatte navnene leses fra kommunens profil og fra
-- kommuner/<slug>/. Paritetskontrollene var for byttet 6.10.2026.
drop table kjerne.tillatt_navn, kjerne.navnevariant, drift.paritet;

-- Lenkene til partiene leses fra kommuner/<slug>/partisider.json.
alter table kjerne.parti drop column url, drop column url_tekst, drop column url_kontrollert;

-- Bygget lagrer bare antall saker per år (forrige telling).
alter table drift.bygg drop column kjoring_id, drop column status;
