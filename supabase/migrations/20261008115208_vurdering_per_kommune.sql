-- Vurdering per kommune og meldinger om feil (ADR-023).
--
-- Den som har rollen vurderer (eller admin) for en kommune, vurderer det som
-- venter der: avvik i stemmene (fra før), sammendrag som ikke besto
-- kontrollen, og meldinger om feil fra innloggede brukere. Rollene gis
-- fortsatt bare av prosjektadmin.
--
-- Innholdet endres aldri av en vurdering: ikke sammendraget, ikke navn og
-- tall (CLAUDE.md regel 2, 5 og 6). En vurdering avgjør om noe vises, og kan
-- ha en kort, offentlig merknad uten navn og lenker.
--
-- En melding om feil skjuler ingenting før den er vurdert (prosjekteier,
-- 8.10.2026): én konto skal ikke kunne ta ned en sak alene.

-- Merknader -------------------------------------------------------------------------

-- Merknaden vises på nettstedet uten at noen godkjenner teksten for hånd
-- (prosjekteier, 8.10.2026). Derfor kort og uten lenker. Navn kontrolleres i
-- bygget (tolk/merknad.py), som holder saken tilbake om merknaden ikke består.
create function kjerne.merknad_ok(merknad text) returns boolean
language sql immutable set search_path = '' as $$
  select merknad is null or (char_length(merknad) <= 300 and merknad !~* '(https?://|www\.)')
$$;

-- Gjelder nye vurderinger av avvik. De som finnes, er kortere og uten lenker,
-- men er ikke kontrollert her.
alter table kjerne.vurdering
  add constraint vurdering_merknad_check check (kjerne.merknad_ok(merknad)) not valid;

-- Grunnene fra kontrollen (tester/kontroller.py, sammendrag_avvik) som en
-- vurderer kan overstyre: et tall eller en dato som ikke ble funnet i kilden.
-- Kontrollen tar ofte feil der, fordi pdftotext klistrer sammen tabeller.
-- Navn på privatpersoner (regel 6), manglende kilde (regel 5) og et usikkert
-- svar fra modellen kan aldri overstyres. Samme regel står i
-- tester/kontroller.kan_overstyres.
create function kjerne.kan_overstyres(grunner text[]) returns boolean
language sql immutable set search_path = '' as $$
  select cardinality(grunner) > 0
     and not exists (select 1 from unnest(grunner) as g
                     where g !~ '^(datoen|tallet) .+ finnes ikke i kilden$')
$$;

-- Meldinger om feil -------------------------------------------------------------------

-- Bare innsetting. meldt_av settes til null når kontoen slettes; meldingen
-- blir stående uten kobling til noen. Logges ikke i endringsloggen, som ikke
-- kan slettes: der ville kontoen og teksten blitt stående.
create table kjerne.feilmelding (
  id bigint generated always as identity primary key,
  kommune_id smallint not null references kjerne.kommune,
  sak_id int not null,
  gjelder text not null check (gjelder in ('sammendrag', 'stemmer', 'saksgang', 'annet')),
  beskrivelse text not null check (char_length(btrim(beskrivelse)) between 20 and 2000),
  meldt_av uuid default auth.uid() references auth.users on delete set null,
  meldt timestamptz not null default now(),
  unique (kommune_id, id),
  foreign key (kommune_id, sak_id) references kjerne.sak on update cascade deferrable
);

create index feilmelding_sak on kjerne.feilmelding (kommune_id, sak_id);
create index feilmelding_bruker on kjerne.feilmelding (meldt_av, meldt);

create trigger forby_endring before update or delete on kjerne.feilmelding
  for each row execute function kjerne.forby_endring('sak_id', 'meldt_av');

-- Mot misbruk: høyst ti meldinger per bruker per døgn.
create function kjerne.feilmelding_grense() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.meldt_av is not null and (
      select count(*) from kjerne.feilmelding
      where meldt_av = new.meldt_av and meldt > now() - interval '1 day') >= 10 then
    raise exception 'Du har sendt ti meldinger det siste døgnet. Prøv igjen i morgen.'
      using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function kjerne.feilmelding_grense() from public;

create trigger grense before insert on kjerne.feilmelding
  for each row execute function kjerne.feilmelding_grense();

-- Bare innsetting: en ny vurdering av samme melding er en ny rad, og den
-- nyeste gjelder. holdes_tilbake skjuler sammendraget (det gjeldende da
-- meldingen ble vurdert, analyse_id) eller stemmene i saken.
create table kjerne.feilmelding_vurdering (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  feilmelding_id bigint not null,
  avgjorelse text not null check (avgjorelse in ('ikke_feil', 'rettet', 'holdes_tilbake')),
  analyse_id bigint,
  merknad text check (kjerne.merknad_ok(merknad)),
  svar text check (char_length(svar) <= 2000),
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  vurdert_av text not null check (btrim(vurdert_av) <> ''),
  registrert timestamptz not null default now(),
  registrert_av uuid,
  foreign key (kommune_id, feilmelding_id) references kjerne.feilmelding (kommune_id, id) deferrable,
  foreign key (kommune_id, analyse_id) references kjerne.analyse (kommune_id, id) deferrable
);

create trigger forby_endring before update or delete on kjerne.feilmelding_vurdering
  for each row execute function kjerne.forby_endring();

-- Bare sammendrag og stemmer kan holdes tilbake. For et sammendrag huskes
-- hvilken analyse det gjaldt, så en ny analyse av saken vises igjen.
create function kjerne.feilmelding_vurdering_sjekk() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  gjelder_ text;
  sak int;
begin
  select f.gjelder, f.sak_id into gjelder_, sak
  from kjerne.feilmelding f where f.kommune_id = new.kommune_id and f.id = new.feilmelding_id;
  new.analyse_id := null;
  if new.avgjorelse = 'holdes_tilbake' then
    if gjelder_ not in ('sammendrag', 'stemmer') then
      raise exception 'Bare sammendrag og stemmer kan holdes tilbake'
        using errcode = 'check_violation';
    end if;
    if gjelder_ = 'sammendrag' then
      select a.id into new.analyse_id from kjerne.analyse_gjeldende a
      where a.kommune_id = new.kommune_id and a.sak_id = sak;
      if new.analyse_id is null then
        raise exception 'Saken har ikke noe sammendrag' using errcode = 'check_violation';
      end if;
    end if;
  end if;
  return new;
end $$;
revoke all on function kjerne.feilmelding_vurdering_sjekk() from public;

create trigger sjekk before insert on kjerne.feilmelding_vurdering
  for each row execute function kjerne.feilmelding_vurdering_sjekk();

create view kjerne.feilmelding_vurdering_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, feilmelding_id) *
  from kjerne.feilmelding_vurdering
  order by kommune_id, feilmelding_id, registrert desc, id desc;

-- Sammendrag som ikke besto kontrollen -----------------------------------------------

-- Bare innsetting. grunner er grunnene fra kontrollen da vurderingen ble
-- gjort, satt av databasen. Bygget viser sammendraget bare så lenge dagens
-- grunner er blant dem (bygg/bygg_nettsted.py, _sammendrag).
create table kjerne.sammendrag_vurdering (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  analyse_id bigint not null,
  avgjorelse text not null check (avgjorelse in ('publiser', 'ikke_publiser')),
  grunner text[] not null default '{}',
  merknad text check (kjerne.merknad_ok(merknad)),
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  vurdert_av text not null check (btrim(vurdert_av) <> ''),
  registrert timestamptz not null default now(),
  registrert_av uuid,
  foreign key (kommune_id, analyse_id) references kjerne.analyse (kommune_id, id) deferrable
);

create trigger forby_endring before update or delete on kjerne.sammendrag_vurdering
  for each row execute function kjerne.forby_endring();

create function kjerne.sammendrag_vurdering_sjekk() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  select k.grunner into new.grunner
  from kjerne.analyse_kontroll k
  where k.kommune_id = new.kommune_id and k.analyse_id = new.analyse_id
  order by k.kontrollert desc limit 1;
  new.grunner := coalesce(new.grunner, '{}');
  if new.avgjorelse = 'publiser' and not kjerne.kan_overstyres(new.grunner) then
    raise exception 'Sammendraget kan ikke publiseres: grunnene kan ikke overstyres i portalen'
      using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function kjerne.sammendrag_vurdering_sjekk() from public;

create trigger sjekk before insert on kjerne.sammendrag_vurdering
  for each row execute function kjerne.sammendrag_vurdering_sjekk();

create view kjerne.sammendrag_vurdering_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, analyse_id) *
  from kjerne.sammendrag_vurdering
  order by kommune_id, analyse_id, registrert desc, id desc;

-- Endringsloggen: vurderingene logges som de av avvik. Meldingene logges ikke
-- (se over).
create trigger logg_endring after insert or update or delete on kjerne.feilmelding_vurdering
  for each row execute function drift.logg_endring('kommune_id', 'id');
create trigger logg_endring after insert or update or delete on kjerne.sammendrag_vurdering
  for each row execute function drift.logg_endring('kommune_id', 'id');

-- RLS ---------------------------------------------------------------------------------

alter table kjerne.feilmelding enable row level security;
alter table kjerne.feilmelding_vurdering enable row level security;
alter table kjerne.sammendrag_vurdering enable row level security;

-- Kjeden og bygget leser, men skriver ikke: meldinger og vurderinger kommer
-- fra portalen.
do $$
declare
  t text;
begin
  foreach t in array array['feilmelding', 'feilmelding_vurdering', 'sammendrag_vurdering'] loop
    execute format('create policy pipeline_leser on kjerne.%I for select to kommunelys_pipeline using (true)', t);
    execute format('create policy bygg_leser on kjerne.%I for select to kommunelys_bygg using (true)', t);
    execute format('grant select on kjerne.%I to kommunelys_pipeline, kommunelys_bygg', t);
  end loop;
end $$;
grant select on kjerne.feilmelding_vurdering_gjeldende, kjerne.sammendrag_vurdering_gjeldende
  to kommunelys_pipeline, kommunelys_bygg;

-- Innloggede melder om feil i kommuner som er publisert, og ser sine egne
-- meldinger. Den som vurderer i kommunen, og prosjektadmin, ser alle der og
-- hvem som meldte, for å hindre misbruk (prosjekteier, 8.10.2026).
create policy melder on kjerne.feilmelding for insert to authenticated
  with check (meldt_av = (select auth.uid())
              and exists (select 1 from kjerne.kommune k
                          where k.kommune_id = feilmelding.kommune_id and k.status = 'publisert'));
create policy egne_og_vurderer on kjerne.feilmelding for select to authenticated
  using (meldt_av = (select auth.uid())
         or kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]));
grant select, insert on kjerne.feilmelding to authenticated;

-- Den som meldte, ser saken meldingen gjelder, selv uten tilgang til
-- kommunens data ellers. Sakstitlene er offentlige på nettstedet.
create policy meldt_sak on kjerne.sak for select to authenticated
  using (exists (select 1 from kjerne.feilmelding f
                 where f.kommune_id = sak.kommune_id and f.sak_id = sak.sak_id
                   and f.meldt_av = (select auth.uid())));

-- Vurderingene: den som vurderer i kommunen, og aldri sin egen melding. Den
-- som meldte, ser avgjørelsen og svaret (portal.feilmelding), ikke
-- begrunnelsen (portal.feilmelding_vurdering er bare for vurderere).
create policy vurderer_og_melder on kjerne.feilmelding_vurdering for select to authenticated
  using (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[])
         or exists (select 1 from kjerne.feilmelding f
                    where f.kommune_id = feilmelding_vurdering.kommune_id
                      and f.id = feilmelding_vurdering.feilmelding_id
                      and f.meldt_av = (select auth.uid())));
create policy vurderer_skriver on kjerne.feilmelding_vurdering for insert to authenticated
  with check (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[])
              and registrert_av = (select auth.uid())
              and not exists (select 1 from kjerne.feilmelding f
                              where f.kommune_id = feilmelding_vurdering.kommune_id
                                and f.id = feilmelding_vurdering.feilmelding_id
                                and f.meldt_av = (select auth.uid())));
grant select, insert on kjerne.feilmelding_vurdering to authenticated;

create policy les_som_vurderer on kjerne.sammendrag_vurdering for select to authenticated
  using (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]));
create policy vurderer_skriver on kjerne.sammendrag_vurdering for insert to authenticated
  with check (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[])
              and registrert_av = (select auth.uid()));
grant select, insert on kjerne.sammendrag_vurdering to authenticated;

grant select on kjerne.feilmelding_vurdering_gjeldende, kjerne.sammendrag_vurdering_gjeldende
  to authenticated;
grant execute on function kjerne.kan_overstyres(text[]), kjerne.merknad_ok(text) to authenticated;

-- E-postadressen til en som har meldt om feil, for den som vurderer i en
-- kommune der brukeren har meldt, og for prosjektadmin. Ellers null.
-- Adressen hentes fra kontoen og lagres ikke på meldingen, så den forsvinner
-- når kontoen slettes. security definer: auth.users er ikke synlig ellers.
create function tilgang.melder_epost(p_bruker uuid) returns text
language sql stable security definer set search_path = '' as $$
  select u.email::text from auth.users u
  where u.id = p_bruker
    and exists (select 1 from kjerne.feilmelding f
                where f.meldt_av = p_bruker
                  and f.kommune_id = any (tilgang.vurderer_kommuner()))
$$;
revoke all on function tilgang.melder_epost(uuid) from public, anon;
grant execute on function tilgang.melder_epost(uuid) to authenticated;

-- Portalen ------------------------------------------------------------------------------

-- Meldingene med saken og den gjeldende vurderingen. egen sier om
-- innlogget bruker meldte den. Hvem som meldte, og hvor mange meldinger
-- brukeren har sendt i kommunen, ser den som vurderer der (RLS slipper ikke
-- andres meldinger til andre).
create view portal.feilmelding with (security_invoker = on) as
  select f.id, f.kommune_id, k.slug as kommune, f.sak_id, s.tittel as sak_tittel, f.gjelder,
         f.beskrivelse, f.meldt,
         coalesce(f.meldt_av = (select auth.uid()), false) as egen,
         f.meldt_av, tilgang.melder_epost(f.meldt_av) as meldt_av_epost,
         (select count(*) from kjerne.feilmelding f2
           where f2.kommune_id = f.kommune_id and f2.meldt_av = f.meldt_av) as meldinger_fra_bruker,
         coalesce(v.avgjorelse, 'ikke_vurdert') as avgjorelse, v.merknad, v.svar,
         v.registrert as vurdert
  from kjerne.feilmelding f
  join kjerne.kommune k on k.kommune_id = f.kommune_id
  left join kjerne.sak s on s.kommune_id = f.kommune_id and s.sak_id = f.sak_id
  left join kjerne.feilmelding_vurdering_gjeldende v
    on v.kommune_id = f.kommune_id and v.feilmelding_id = f.id;

-- Innsetting gjennom viewet. Kjører som brukeren, så RLS gjelder.
create function portal.skriv_feilmelding() returns trigger
language plpgsql set search_path = '' as $$
begin
  insert into kjerne.feilmelding (kommune_id, sak_id, gjelder, beskrivelse)
    values (new.kommune_id, new.sak_id, new.gjelder, new.beskrivelse)
    returning id, meldt into new.id, new.meldt;
  new.egen := true;
  new.avgjorelse := 'ikke_vurdert';
  return new;
end $$;
revoke all on function portal.skriv_feilmelding() from public, anon;

create trigger skriv instead of insert on portal.feilmelding
  for each row execute function portal.skriv_feilmelding();

create view portal.feilmelding_vurdering with (security_invoker = on) as
  select id, kommune_id, feilmelding_id, avgjorelse, merknad, svar, begrunnelse, vurdert_av,
         registrert, registrert_av
  from kjerne.feilmelding_vurdering
  where kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);
alter view portal.feilmelding_vurdering alter column registrert_av set default auth.uid();

-- Det siste sammendraget for hver sak som ikke besto siste kontroll, med den
-- gjeldende vurderingen. id er analysens.
create view portal.sammendrag_holdt with (security_invoker = on) as
  select a.id, a.kommune_id, ko.slug as kommune, a.sak_id, s.tittel as sak_tittel,
         a.tittel_klarsprak, a.sammendrag,
         a.betydning, a.uenighet, a.kilder, a.modell, a.opprettet,
         k.grunner, k.kontrollert, kjerne.kan_overstyres(k.grunner) as kan_godkjennes,
         coalesce(v.avgjorelse, 'ikke_vurdert') as avgjorelse, v.merknad, v.begrunnelse,
         v.vurdert_av, v.registrert as vurdert
  from kjerne.analyse_gjeldende a
  join kjerne.kommune ko on ko.kommune_id = a.kommune_id
  join kjerne.sak s on s.kommune_id = a.kommune_id and s.sak_id = a.sak_id
  join lateral (
    select k.grunner, k.kontrollert from kjerne.analyse_kontroll k
    where k.kommune_id = a.kommune_id and k.analyse_id = a.id and k.kontrollert >= a.opprettet
    order by k.kontrollert desc limit 1) k on cardinality(k.grunner) > 0
  left join kjerne.sammendrag_vurdering_gjeldende v
    on v.kommune_id = a.kommune_id and v.analyse_id = a.id
  where not a.usikker
    and a.kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);

create view portal.sammendrag_vurdering with (security_invoker = on) as
  select id, kommune_id, analyse_id, avgjorelse, grunner, merknad, begrunnelse, vurdert_av,
         registrert, registrert_av
  from kjerne.sammendrag_vurdering
  where kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);
alter view portal.sammendrag_vurdering alter column registrert_av set default auth.uid();

grant select, insert on portal.feilmelding, portal.feilmelding_vurdering,
  portal.sammendrag_vurdering to authenticated;
grant select on portal.sammendrag_holdt to authenticated;

notify pgrst, 'reload schema';
