-- Reglene i CLAUDE.md, håndhevet av databasen i tillegg til koden.
--
-- Koden avgjør fortsatt alt (tolk/ teller stemmer, hent/ hopper over
-- skjermede dokumenter). Databasen nekter å lagre data som bryter reglene,
-- så en feil i koden stopper kjøringen i stedet for å bli publisert.

-- Bare innsetting ------------------------------------------------------------
-- Rådata, vurderinger og analyser endres og slettes ikke. Argumentene er
-- kolonner som likevel kan endres (sak_id flyttes når en sak får ny ID).

create function kjerne.forby_endring() returns trigger
language plpgsql set search_path = '' as $$
declare
  tillatt text[] := tg_argv;
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

create trigger forby_endring before update or delete on kjerne.raa_svar
  for each row execute function kjerne.forby_endring();
create trigger forby_tomming before truncate on kjerne.raa_svar
  for each statement execute function kjerne.forby_endring();

create trigger forby_endring before update or delete on kjerne.vurdering
  for each row execute function kjerne.forby_endring();

create trigger forby_endring before update or delete on kjerne.analyse
  for each row execute function kjerne.forby_endring('sak_id');

create trigger forby_endring before update or delete on kjerne.analyse_kontroll
  for each row execute function kjerne.forby_endring();

-- ADR-014: ingen kontaktopplysninger i medlemslistene ----------------------------

create function kjerne.sjekk_medlemsliste() returns trigger
language plpgsql set search_path = '' as $$
declare
  ukjent text;
begin
  select k into ukjent
  from jsonb_each(coalesce(new.innhold -> 'utvalg', '{}'::jsonb)) as u(id, utvalg),
       jsonb_array_elements(coalesce(u.utvalg -> 'medlemmer', '[]'::jsonb)) as m(medlem),
       jsonb_object_keys(m.medlem) as k
  where k not in ('person_id', 'navn', 'funksjon', 'repr', 'repr_navn')
  limit 1;
  if ukjent is not null then
    raise exception 'medlemslisten har feltet %; bare rolle og person-ID lagres (ADR-014)', ukjent
      using errcode = 'check_violation';
  end if;
  return new;
end $$;

create trigger sjekk_medlemsliste before insert on kjerne.raa_svar
  for each row when (new.kilde = 'medlemsliste')
  execute function kjerne.sjekk_medlemsliste();

-- Regel 2: antall navn skal stemme med oppgitt stemmetall ---------------------------
-- Tolkningen setter tall_stemmer. Står det sant, må stemme-radene telle opp
-- til tallene. Kjøres når transaksjonen avsluttes, så en votering og
-- stemmene kan skrives i hvilken som helst rekkefølge.

create function kjerne.kontroller_stemmetall() returns trigger
language plpgsql set search_path = '' as $$
declare
  rad record;
  v kjerne.votering;
  n_for int;
  n_mot int;
  n_borte int;
  n_alle int;
  feil_alternativ text;
begin
  if tg_op = 'DELETE' then
    rad := old;
  else
    rad := new;
  end if;
  select * into v from kjerne.votering
  where kommune_id = rad.kommune_id and behandling_id = rad.behandling_id and nr = rad.nr;
  if not found then
    return null;  -- voteringen er slettet i samme transaksjon
  end if;

  select count(*) filter (where valg = 'for'),
         count(*) filter (where valg = 'mot'),
         count(*) filter (where valg = 'ikke_til_stede'),
         count(*)
    into n_for, n_mot, n_borte, n_alle
  from kjerne.stemme
  where kommune_id = v.kommune_id and behandling_id = v.behandling_id and nr = v.nr;

  if n_alle > 0 and (v.enstemmig or v.detaljniva <> 'navneliste') then
    raise exception 'votering % nr %: har navn, men er enstemmig eller uten navneliste',
      v.behandling_id, v.nr using errcode = 'check_violation';
  end if;

  if v.tall_stemmer and not v.enstemmig and v.detaljniva = 'navneliste' then
    if n_for <> v.antall_for or n_mot <> v.antall_mot
       or (v.antall_ikke_til_stede is not null and n_borte <> v.antall_ikke_til_stede) then
      raise exception 'votering % nr %: % for og % mot i navnelisten, men % mot % i stemmetallet',
        v.behandling_id, v.nr, n_for, n_mot, v.antall_for, v.antall_mot
        using errcode = 'check_violation';
    end if;

    select a.forslag into feil_alternativ
    from kjerne.votering_alternativ a
    where a.kommune_id = v.kommune_id and a.behandling_id = v.behandling_id and a.nr = v.nr
      and a.antall <> (select count(*) from kjerne.stemme s
                       where s.kommune_id = a.kommune_id and s.behandling_id = a.behandling_id
                         and s.nr = a.nr and s.alternativ_forslag = a.forslag)
    limit 1;
    if feil_alternativ is not null then
      raise exception 'votering % nr %: antall navn for forslag % stemmer ikke med stemmetallet',
        v.behandling_id, v.nr, feil_alternativ using errcode = 'check_violation';
    end if;
  end if;
  return null;
end $$;

create constraint trigger stemmetall after insert or update on kjerne.votering
  deferrable initially deferred for each row execute function kjerne.kontroller_stemmetall();
create constraint trigger stemmetall after insert or update or delete on kjerne.stemme
  deferrable initially deferred for each row execute function kjerne.kontroller_stemmetall();
create constraint trigger stemmetall after insert or update or delete on kjerne.votering_alternativ
  deferrable initially deferred for each row execute function kjerne.kontroller_stemmetall();

-- Regel 3 og ADR-006: tekst lagres bare fra åpne dokumenter, aldri fra møteinnkallingen

create function kjerne.sjekk_tekst() returns trigger
language plpgsql set search_path = '' as $$
declare
  d kjerne.dokument;
  skjermet boolean;
begin
  select * into d from kjerne.dokument where kommune_id = new.kommune_id and id = new.dokument_id;
  if d.slag = 'moteinnkalling' then
    raise exception 'møteinnkallingen lagres ikke som tekst (ADR-006)' using errcode = 'check_violation';
  end if;
  if d.slag = 'saksprotokoll' then
    select protokoll_skjermet or not protokoll_publisert into skjermet
    from kjerne.saksgang_steg
    where kommune_id = d.kommune_id and behandling_id = d.behandling_id;
    if skjermet then
      raise exception 'vedtaket i behandling % er skjermet eller upublisert; teksten lagres ikke',
        d.behandling_id using errcode = 'check_violation';
    end if;
  end if;
  return new;
end $$;

create trigger sjekk_tekst before insert or update on kjerne.dokument_tekst
  for each row execute function kjerne.sjekk_tekst();

-- Blir et vedtak skjermet i portalen etter at teksten er hentet, fjernes
-- dokumentet og teksten med det.
create function kjerne.fjern_skjermet_vedtak() returns trigger
language plpgsql set search_path = '' as $$
begin
  delete from kjerne.dokument
  where kommune_id = new.kommune_id and id_rom = 'behandling' and portal_id = new.behandling_id;
  return null;
end $$;

create trigger fjern_skjermet_vedtak after update of protokoll_skjermet on kjerne.saksgang_steg
  for each row when (new.protokoll_skjermet and not old.protokoll_skjermet)
  execute function kjerne.fjern_skjermet_vedtak();

-- Taggene må finnes i kjerne.tagg når analysen lagres. En tagg som tas ut
-- av bruk, gjør ikke eldre analyser ugyldige.
create function kjerne.sjekk_tagger() returns trigger
language plpgsql set search_path = '' as $$
declare
  ukjent text;
begin
  select t into ukjent from unnest(new.tagger) as t
  where not exists (select 1 from kjerne.tagg g where g.tagg = t and g.aktiv)
  limit 1;
  if ukjent is not null then
    raise exception 'ukjent tagg %', ukjent using errcode = 'check_violation';
  end if;
  return new;
end $$;

create trigger sjekk_tagger before insert on kjerne.analyse
  for each row execute function kjerne.sjekk_tagger();
