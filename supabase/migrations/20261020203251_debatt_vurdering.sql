-- Vurdering av debatter som holdes tilbake (ADR-026, etter ADR-023 og ADR-025).
--
-- Bygget kontrollerer hvert sammendrag av debatten (analyser_debatt.avvik) og
-- holder det tilbake ved avvik. Resultatet lagres nå i kjerne.debatt_kontroll,
-- og en vurderer kan slippe gjennom en debatt der kontrollen bare ikke fant
-- partiet i tekstingen. Kommunens automatiske teksting skriver ofte navn og
-- partier feil, så kontrollen tar feil der.
--
-- Navn kan aldri overstyres av en vurderer (regel 6), og heller ikke
-- stemmetall eller utfall i teksten (regel 2). Prosjektadmin kan publisere
-- likevel, som for sammendragene (ADR-025); vurderingen merkes overstyrt.
-- En del eller et tidspunkt som ikke finnes i opptaket, eller en debatt uten
-- teksting, kan ingen publisere: lenkene ville pekt feil, og debatten må
-- analyseres på nytt.
--
-- Innholdet endres aldri av en vurdering. Den avgjør om debatten vises, og
-- kan ha en kort, offentlig merknad uten navn og lenker.

-- Grunnene ---------------------------------------------------------------------------

-- Grunnene fra kontrollen som en vurderer kan overstyre: partiet står ikke i
-- tekstingen nær tidspunktet, eller står ikke blant dem som stemte (enstemmige
-- vedtak har ingen navneliste). Samme regel står i
-- analyser.analyser_debatt.kan_overstyres.
create function kjerne.debatt_kan_overstyres(grunner text[]) returns boolean
language sql immutable set search_path = '' as $$
  select cardinality(grunner) > 0
     and not exists (select 1 from unnest(grunner) as g
                     where g !~ '^(partiet \S+ var ikke i møtet|\S+ er verken nevnt eller ropt opp nær \S+ i del \d+)$')
$$;

-- Grunnene ingen kan overstyre. Samme regel står i
-- analyser.analyser_debatt.kan_aldri_publiseres.
create function kjerne.debatt_kan_aldri_publiseres(grunner text[]) returns boolean
language sql immutable set search_path = '' as $$
  select exists (select 1 from unnest(grunner) as g
                 where g ~ '^(del \S+ finnes ikke|tiden \S+ s er utenfor del \S+|tekstingen mangler)$')
$$;

-- Kontrollen --------------------------------------------------------------------------

-- Resultatet av kontrollen av et sammendrag av debatten, som analyse_kontroll.
-- Bygget lagrer en ny rad når grunnene er annerledes enn sist.
create table kjerne.debatt_kontroll (
  kommune_id smallint not null,
  debatt_id bigint not null,
  kontrollert timestamptz not null default now(),
  bestatt boolean not null,
  grunner text[] not null default '{}',
  kjoring_id text,
  primary key (kommune_id, debatt_id, kontrollert),
  foreign key (kommune_id, debatt_id) references kjerne.debatt (kommune_id, id) deferrable,
  check (bestatt = (cardinality(grunner) = 0))
);

create trigger forby_endring before update or delete on kjerne.debatt_kontroll
  for each row execute function kjerne.forby_endring();
create trigger forby_tomming before truncate on kjerne.debatt_kontroll
  for each statement execute function kjerne.forby_endring();

-- Vurderingen -------------------------------------------------------------------------

-- Bare innsetting; den nyeste raden for debatten gjelder. grunner og
-- overstyrt settes av databasen. Bygget viser debatten bare så lenge dagens
-- grunner er blant dem som ble vurdert. En ny analyse av debatten (ny id) må
-- vurderes på nytt.
create table kjerne.debatt_vurdering (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  debatt_id bigint not null,
  avgjorelse text not null check (avgjorelse in ('publiser', 'ikke_publiser')),
  grunner text[] not null default '{}',
  overstyrt boolean not null default false,
  merknad text check (kjerne.merknad_ok(merknad)),
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  vurdert_av text not null check (btrim(vurdert_av) <> ''),
  registrert timestamptz not null default now(),
  registrert_av uuid,
  foreign key (kommune_id, debatt_id) references kjerne.debatt (kommune_id, id) deferrable
);

create index debatt_vurdering_debatt on kjerne.debatt_vurdering (kommune_id, debatt_id);

create trigger forby_endring before update or delete on kjerne.debatt_vurdering
  for each row execute function kjerne.forby_endring();
create trigger forby_tomming before truncate on kjerne.debatt_vurdering
  for each statement execute function kjerne.forby_endring();

create function kjerne.debatt_vurdering_sjekk() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  select k.grunner into new.grunner
  from kjerne.debatt_kontroll k
  where k.kommune_id = new.kommune_id and k.debatt_id = new.debatt_id
  order by k.kontrollert desc limit 1;
  new.grunner := coalesce(new.grunner, '{}');
  if new.avgjorelse = 'publiser' and kjerne.debatt_kan_aldri_publiseres(new.grunner) then
    raise exception 'Debatten kan ikke publiseres: delen eller tiden i opptaket er feil, eller tekstingen mangler'
      using errcode = 'check_violation';
  end if;
  -- Settes alltid her, aldri av den som vurderer.
  new.overstyrt := new.avgjorelse = 'publiser' and not kjerne.debatt_kan_overstyres(new.grunner);
  if new.overstyrt and not tilgang.er_prosjektadmin() then
    raise exception 'Debatten kan ikke publiseres: grunnene kan bare overstyres av prosjektadmin'
      using errcode = 'check_violation';
  end if;
  return new;
end $$;
revoke all on function kjerne.debatt_vurdering_sjekk() from public;

create trigger sjekk before insert on kjerne.debatt_vurdering
  for each row execute function kjerne.debatt_vurdering_sjekk();

create view kjerne.debatt_vurdering_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, debatt_id) *
  from kjerne.debatt_vurdering
  order by kommune_id, debatt_id, registrert desc, id desc;

-- Endringsloggen: vurderingene logges som de av sammendragene. Kontrollen
-- logges ikke, som analyse_kontroll.
create trigger logg_endring after insert or update or delete on kjerne.debatt_vurdering
  for each row execute function drift.logg_endring('kommune_id', 'id');

-- RLS -------------------------------------------------------------------------------

alter table kjerne.debatt_kontroll enable row level security;
alter table kjerne.debatt_vurdering enable row level security;

-- Kjeden og bygget skriver kontrollen, som analyse_kontroll.
create policy pipeline on kjerne.debatt_kontroll to kommunelys_pipeline using (true) with check (true);
create policy bygg_leser on kjerne.debatt_kontroll for select to kommunelys_bygg using (true);
create policy bygg_skriver on kjerne.debatt_kontroll for insert to kommunelys_bygg with check (true);
grant select, insert on kjerne.debatt_kontroll to kommunelys_pipeline, kommunelys_bygg;

-- Vurderingene kommer fra portalen; kjeden og bygget leser.
create policy pipeline_leser on kjerne.debatt_vurdering for select to kommunelys_pipeline using (true);
create policy bygg_leser on kjerne.debatt_vurdering for select to kommunelys_bygg using (true);
grant select on kjerne.debatt_vurdering, kjerne.debatt_vurdering_gjeldende
  to kommunelys_pipeline, kommunelys_bygg;

-- Den som vurderer i kommunen, ser kontrollen og vurderingene og skriver nye.
create policy les_som_vurderer on kjerne.debatt_kontroll for select to authenticated
  using (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]));
create policy les_som_vurderer on kjerne.debatt_vurdering for select to authenticated
  using (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]));
create policy vurderer_skriver on kjerne.debatt_vurdering for insert to authenticated
  with check (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[])
              and registrert_av = (select auth.uid()));
grant select on kjerne.debatt_kontroll to authenticated;
grant select, insert on kjerne.debatt_vurdering to authenticated;
grant select on kjerne.debatt_vurdering_gjeldende to authenticated;
grant execute on function kjerne.debatt_kan_overstyres(text[]),
  kjerne.debatt_kan_aldri_publiseres(text[]) to authenticated, kommunelys_pipeline, kommunelys_bygg;

-- Portalen ------------------------------------------------------------------------------

-- Den gjeldende debatten for hver behandling som ikke besto siste kontroll,
-- med saken, lenkene til opptaket og den gjeldende vurderingen. id er
-- debattens. deler er bokmerkene for behandlingen i opptaket, nummerert som
-- «del» i punktene (analyser_debatt.deler_for). Et opptak kommunen har
-- slettet, vises ikke på nettstedet og venter ikke på vurdering.
create view portal.debatt_holdt with (security_invoker = on) as
  select d.id, d.kommune_id, ko.slug as kommune, st.sak_id, s.tittel as sak_tittel,
         d.behandling_id, st.saksnr, st.utvalg_navn, st.dato,
         d.oppsummering, d.antall_innlegg, d.punkter, d.kilder, d.modell, d.opprettet,
         o.url as opptak_url,
         (select coalesce(jsonb_agg(jsonb_build_object(
                    'del', x.del, 'tittel', x.b ->> 'tittel',
                    'url', o.url || '?caseId=' || (x.b ->> 'bokmerke_id'),
                    'start_s', (x.b ->> 'start_ms')::bigint / 1000,
                    'varighet_s', (x.b ->> 'varighet_ms')::bigint / 1000) order by x.del), '[]')
            from (select b, row_number() over (order by (b ->> 'start_ms')::bigint) as del
                  from jsonb_array_elements(o.deler) as b
                  where (b ->> 'behandling_id')::int = d.behandling_id) x) as deler,
         k.grunner, k.kontrollert,
         kjerne.debatt_kan_overstyres(k.grunner) as kan_godkjennes,
         kjerne.debatt_kan_aldri_publiseres(k.grunner) as kan_aldri_publiseres,
         coalesce(v.avgjorelse, 'ikke_vurdert') as avgjorelse, v.overstyrt, v.merknad,
         v.begrunnelse, v.vurdert_av, v.registrert as vurdert
  from kjerne.debatt_gjeldende d
  join kjerne.kommune ko on ko.kommune_id = d.kommune_id
  join kjerne.saksgang_steg st on st.kommune_id = d.kommune_id and st.behandling_id = d.behandling_id
  join kjerne.sak s on s.kommune_id = st.kommune_id and s.sak_id = st.sak_id
  join kjerne.opptak o on o.kommune_id = d.kommune_id and o.opptak_id = d.opptak_id and o.fjernet is null
  join lateral (
    select k.grunner, k.kontrollert from kjerne.debatt_kontroll k
    where k.kommune_id = d.kommune_id and k.debatt_id = d.id and k.kontrollert >= d.opprettet
    order by k.kontrollert desc limit 1) k on cardinality(k.grunner) > 0
  left join kjerne.debatt_vurdering_gjeldende v
    on v.kommune_id = d.kommune_id and v.debatt_id = d.id
  where not d.ingen_debatt
    and d.kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);

create view portal.debatt_vurdering with (security_invoker = on) as
  select id, kommune_id, debatt_id, avgjorelse, grunner, overstyrt, merknad, begrunnelse,
         vurdert_av, registrert, registrert_av
  from kjerne.debatt_vurdering
  where kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);
alter view portal.debatt_vurdering alter column registrert_av set default auth.uid();

grant select on portal.debatt_holdt to authenticated;
grant select, insert on portal.debatt_vurdering to authenticated;

notify pgrst, 'reload schema';
