-- Det som ikke brukes, ut av databasen (gjennomgangen 31.10 og ryddingen
-- 1.11.2026). Ingenting her leses av koden, portalen eller edge-funksjonene.
-- Det som forsvinner, finnes i sikkerhetskopien tatt rett før migreringen.
--
-- En kopi tatt før denne migreringen har tabellene og kolonnene under, og må
-- leses inn med migreringene slik de var da (fra historikken i git).

-- Rollen for et eget bygg. Bygget kjører som kommunelys_pipeline, og denne
-- rollen kan ikke logge inn. Den eier ingenting; drop owned tar policyene og
-- rettighetene den har fått.
do $$ begin
  if exists (select from pg_class where relowner = 'kommunelys_bygg'::regrole)
     or exists (select from pg_proc where proowner = 'kommunelys_bygg'::regrole) then
    raise exception 'kommunelys_bygg eier noe; se over før rollen fjernes';
  end if;
end $$;
drop owned by kommunelys_bygg;
drop role kommunelys_bygg;

-- Publiseringsreglene som views. Bygget holder tilbake i Python
-- (tolk/bygg_avvik, bygg/bygg_nettsted), og ingen leste disse.
drop view publisert.sammendrag, publisert.votering_alternativ, publisert.stemme,
  publisert.votering, publisert.votering_status;
drop schema publisert;

-- Navnevariantene og de tillatte navnene leses fra kommunens profil og fra
-- kommuner/<slug>/. Paritetskontrollene var for byttet 6.10.2026.
drop table kjerne.tillatt_navn, kjerne.navnevariant, drift.paritet;

-- Lenkene til partiene leses fra kommuner/<slug>/partisider.json.
alter table kjerne.parti drop column url, drop column url_tekst, drop column url_kontrollert;

-- Bygget lagrer bare antall saker per år (forrige telling).
alter table drift.bygg drop column kjoring_id, drop column status;
