-- Prosjektadmin har siste ord over sammendragene (prosjekteier, 19.10.2026, ADR-025).
--
-- 1. Prosjektadmin kan publisere et sammendrag uansett hva kontrollen fant,
--    også et navn fra sakstittelen. Kontrollen tar feil der også: «Levanger
--    Fotballklubb» ble lest som et personnavn. Vurderingen merkes overstyrt.
--    Vurderere har reglene fra ADR-023.
-- 2. Prosjektadmin kan redigere teksten i sammendraget: tittel i klarspråk,
--    sammendraget, betydningen, uenigheten og temaene. Den redigerte teksten
--    vises i stedet for modellens, merket «redigert av Kommunelys» på
--    nettstedet, uten ny kontroll: prosjektadmin har lest den. Analysen
--    selv endres aldri.
--
-- En redigering gjelder saken, også når saken senere får en ny analyse. Da
-- står teksten til prosjektadmin har sett på den nye analysen (portal.sammendrag,
-- status «ny_analyse») og redigert på nytt eller tatt KI-teksten tilbake
-- (en rad med aktiv = false).

-- 1. Publisere uansett grunn ---------------------------------------------------------

alter table kjerne.sammendrag_vurdering add column overstyrt boolean not null default false;

create or replace function kjerne.sammendrag_vurdering_sjekk() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  select k.grunner into new.grunner
  from kjerne.analyse_kontroll k
  where k.kommune_id = new.kommune_id and k.analyse_id = new.analyse_id
  order by k.kontrollert desc limit 1;
  new.grunner := coalesce(new.grunner, '{}');
  -- Settes alltid her, aldri av den som vurderer.
  new.overstyrt := new.avgjorelse = 'publiser' and not kjerne.kan_overstyres(new.grunner);
  if new.overstyrt and not tilgang.er_prosjektadmin() then
    raise exception 'Sammendraget kan ikke publiseres: grunnene kan bare overstyres av prosjektadmin'
      using errcode = 'check_violation';
  end if;
  return new;
end $$;

-- Viewet fikk kolonnen da det ble laget (select *), men må lages på nytt for å vise den.
create or replace view kjerne.sammendrag_vurdering_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, analyse_id) *
  from kjerne.sammendrag_vurdering
  order by kommune_id, analyse_id, registrert desc, id desc;

create or replace view portal.sammendrag_vurdering with (security_invoker = on) as
  select id, kommune_id, analyse_id, avgjorelse, grunner, merknad, begrunnelse, vurdert_av,
         registrert, registrert_av, overstyrt
  from kjerne.sammendrag_vurdering
  where kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);

-- 2. Redigere teksten ------------------------------------------------------------------

-- Bare innsetting; den nyeste raden for saken gjelder. analyse_id er analysen
-- teksten bygger på; kildene og modellen hentes derfra (regel 5). aktiv =
-- false tar KI-teksten tilbake. registrert_av har ingen fremmednøkkel, som i
-- sammendrag_vurdering, så en konto kan slettes.
create table kjerne.sammendrag_redigering (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  analyse_id bigint not null,
  aktiv boolean not null default true,
  tittel_klarsprak text check (char_length(tittel_klarsprak) <= 200),
  sammendrag text check (char_length(sammendrag) <= 3000),
  betydning text check (char_length(betydning) <= 1000),
  uenighet text check (char_length(uenighet) <= 1000),
  tagger text[],
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  registrert timestamptz not null default now(),
  registrert_av uuid,
  check (not aktiv or (btrim(tittel_klarsprak) <> '' and btrim(sammendrag) <> ''
                       and cardinality(tagger) between 1 and 3)),
  foreign key (kommune_id, analyse_id) references kjerne.analyse (kommune_id, id) deferrable
);

create index sammendrag_redigering_analyse on kjerne.sammendrag_redigering (kommune_id, analyse_id);

create trigger forby_endring before update or delete on kjerne.sammendrag_redigering
  for each row execute function kjerne.forby_endring();
create trigger sjekk_tagger before insert on kjerne.sammendrag_redigering
  for each row execute function kjerne.sjekk_tagger();
create trigger logg_endring after insert or update or delete on kjerne.sammendrag_redigering
  for each row execute function drift.logg_endring('kommune_id', 'id');

-- Den gjeldende redigeringen per sak, også den som tar KI-teksten tilbake.
-- Saken hentes fra analysen, så den følger med når saken får ny ID.
create view kjerne.sammendrag_redigering_gjeldende with (security_invoker = on) as
  select distinct on (r.kommune_id, a.sak_id) a.sak_id, r.*
  from kjerne.sammendrag_redigering r
  join kjerne.analyse a on a.kommune_id = r.kommune_id and a.id = r.analyse_id
  order by r.kommune_id, a.sak_id, r.registrert desc, r.id desc;

alter table kjerne.sammendrag_redigering enable row level security;

create policy pipeline_leser on kjerne.sammendrag_redigering for select to kommunelys_pipeline using (true);
create policy bygg_leser on kjerne.sammendrag_redigering for select to kommunelys_bygg using (true);
grant select on kjerne.sammendrag_redigering, kjerne.sammendrag_redigering_gjeldende
  to kommunelys_pipeline, kommunelys_bygg;

-- Vurderere i kommunen ser redigeringene; bare prosjektadmin skriver.
create policy les_som_vurderer on kjerne.sammendrag_redigering for select to authenticated
  using (kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]));
create policy prosjektadmin_skriver on kjerne.sammendrag_redigering for insert to authenticated
  with check ((select tilgang.er_prosjektadmin()) and registrert_av = (select auth.uid()));
grant select, insert on kjerne.sammendrag_redigering to authenticated;
grant select on kjerne.sammendrag_redigering_gjeldende to authenticated;

-- Portalen -------------------------------------------------------------------------------

create view portal.sammendrag_redigering with (security_invoker = on) as
  select id, kommune_id, analyse_id, aktiv, tittel_klarsprak, sammendrag, betydning, uenighet,
         tagger, begrunnelse, registrert, registrert_av
  from kjerne.sammendrag_redigering
  where kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);
alter view portal.sammendrag_redigering alter column registrert_av set default auth.uid();
grant select, insert on portal.sammendrag_redigering to authenticated;

-- Temaene som kan velges når teksten redigeres (kjerne.sjekk_tagger).
create view portal.tagg with (security_invoker = on) as
  select tagg from kjerne.tagg where aktiv;
grant select on portal.tagg to authenticated;

-- Alle sammendrag, ett per sak: den gjeldende analysen, siste kontroll,
-- vurderingen og redigeringen. id er analysens. status er et anslag av det
-- bygget gjør (bygg/bygg_nettsted.py, _sammendrag); meldinger om feil er
-- ikke tatt med.
create view portal.sammendrag with (security_invoker = on) as
  select a.id, a.kommune_id, ko.slug as kommune, a.sak_id, s.tittel as sak_tittel,
         a.tittel_klarsprak, a.sammendrag, a.betydning, a.uenighet, a.tagger,
         a.kilder, a.modell, a.opprettet, a.usikker,
         k.grunner, k.kontrollert,
         v.avgjorelse, v.overstyrt, v.registrert as vurdert,
         r.id as redigering_id, r.analyse_id as redigert_analyse_id,
         r.tittel_klarsprak as r_tittel_klarsprak, r.sammendrag as r_sammendrag,
         r.betydning as r_betydning, r.uenighet as r_uenighet, r.tagger as r_tagger,
         r.begrunnelse as r_begrunnelse, r.registrert as redigert,
         case
           when r.aktiv and r.analyse_id <> a.id then 'ny_analyse'
           when r.aktiv then 'redigert'
           when v.avgjorelse = 'ikke_publiser' then 'ikke_publiser'
           when k.grunner is null then 'ikke_kontrollert'
           when a.usikker then 'holdt'
           when cardinality(k.grunner) = 0 then 'vist'
           when v.avgjorelse = 'publiser' and k.grunner <@ v.grunner
                and (v.overstyrt or kjerne.kan_overstyres(k.grunner)) then 'vist'
           else 'holdt'
         end as status
  from kjerne.analyse_gjeldende a
  join kjerne.kommune ko on ko.kommune_id = a.kommune_id
  join kjerne.sak s on s.kommune_id = a.kommune_id and s.sak_id = a.sak_id
  left join lateral (
    select k.grunner, k.kontrollert from kjerne.analyse_kontroll k
    where k.kommune_id = a.kommune_id and k.analyse_id = a.id and k.kontrollert >= a.opprettet
    order by k.kontrollert desc limit 1) k on true
  left join kjerne.sammendrag_vurdering_gjeldende v
    on v.kommune_id = a.kommune_id and v.analyse_id = a.id
  left join kjerne.sammendrag_redigering_gjeldende r
    on r.kommune_id = a.kommune_id and r.sak_id = a.sak_id and r.aktiv
  where a.kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[]);
grant select on portal.sammendrag to authenticated;

-- Et sammendrag prosjektadmin har redigert, venter ikke på vurdering.
create or replace view portal.sammendrag_holdt with (security_invoker = on) as
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
    and a.kommune_id = any ((select tilgang.vurderer_kommuner())::smallint[])
    and not exists (select 1 from kjerne.sammendrag_redigering_gjeldende r
                    where r.kommune_id = a.kommune_id and r.sak_id = a.sak_id and r.aktiv);

notify pgrst, 'reload schema';
