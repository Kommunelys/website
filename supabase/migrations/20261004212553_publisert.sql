-- Publiseringsreglene, i SQL.
--
-- I dag ligger reglene i Python (tolk/bygg_avvik.holdt_tilbake og
-- bygg/bygg_nettsted._sammendrag). Her står de én gang, så bygget og alt som
-- leser dataene senere ser samme filter. Alle views er security_invoker:
-- de kjører med rettighetene og RLS-reglene til den som spør.

-- Én rad per votering: holdes den tilbake, og hvilke merknader har den.
-- Holdes tilbake hvis ett aktivt avvik som berører den, ikke har vurderingen
-- «publiser» (ADR-015). En votering der antall navn ikke stemmer, holdes
-- alltid tilbake til en vurdering sier noe annet.
create view publisert.votering_status with (security_invoker = on) as
select
  v.kommune_id,
  v.behandling_id,
  v.nr,
  coalesce(bool_or(a.avvik is not null and coalesce(g.avgjorelse, 'ikke_vurdert') <> 'publiser'), false)
    or (not v.tall_stemmer and not coalesce(bool_or(g.avgjorelse = 'publiser'), false)) as holdt,
  coalesce(array_agg(a.avvik order by a.dato, a.avvik)
           filter (where a.avvik is not null and coalesce(g.avgjorelse, 'ikke_vurdert') <> 'publiser'),
           '{}') as holdt_av,
  coalesce(array_agg(g.merknad order by a.dato, a.avvik)
           filter (where g.avgjorelse = 'publiser' and nullif(btrim(g.merknad), '') is not null),
           '{}') as merknader
from kjerne.votering v
left join kjerne.avvik_votering av
  on av.kommune_id = v.kommune_id and av.behandling_id = v.behandling_id and av.nr = v.nr
left join kjerne.avvik a
  on a.kommune_id = av.kommune_id and a.avvik = av.avvik and a.aktiv
left join kjerne.vurdering_gjeldende g
  on g.kommune_id = a.kommune_id and g.avvik = a.avvik
group by v.kommune_id, v.behandling_id, v.nr, v.tall_stemmer;

-- Voteringene som kan vises. En votering som holdes tilbake, vises uten
-- tall og navn: det står at den finnes og hva den gjaldt.
create view publisert.votering with (security_invoker = on) as
select
  v.kommune_id, v.behandling_id, v.nr, v.type, v.tekst, v.resultat, v.resultat_tekst,
  v.enstemmig, v.forslagsstiller, v.parti, v.dobbeltstemme, v.detaljniva,
  case when s.holdt then null else v.antall_for end as antall_for,
  case when s.holdt then null else v.antall_mot end as antall_mot,
  case when s.holdt then null else v.antall_ikke_til_stede end as antall_ikke_til_stede,
  s.holdt,
  s.merknader
from kjerne.votering v
join publisert.votering_status s
  on s.kommune_id = v.kommune_id and s.behandling_id = v.behandling_id and s.nr = v.nr;

-- Stemmene, bare for voteringer som ikke holdes tilbake.
create view publisert.stemme with (security_invoker = on) as
select st.kommune_id, st.behandling_id, st.nr, st.person_id, p.navn, st.valg,
       st.alternativ_forslag, st.parti, st.rekkefolge
from kjerne.stemme st
join kjerne.person p on p.kommune_id = st.kommune_id and p.id = st.person_id
join publisert.votering_status s
  on s.kommune_id = st.kommune_id and s.behandling_id = st.behandling_id and s.nr = st.nr
where not s.holdt;

create view publisert.votering_alternativ with (security_invoker = on) as
select va.*
from kjerne.votering_alternativ va
join publisert.votering_status s
  on s.kommune_id = va.kommune_id and s.behandling_id = va.behandling_id and s.nr = va.nr
where not s.holdt;

-- Sammendragene som kan vises: siste analyse av saken, ikke usikker, og
-- bestått ved siste kontroll mot kilden. Er den ikke kontrollert etter at
-- den ble laget, vises den ikke (CLAUDE.md regel 5 og 6).
create view publisert.sammendrag with (security_invoker = on) as
select a.*
from kjerne.analyse_gjeldende a
where not a.usikker
  and jsonb_array_length(a.kilder) >= 1
  and (
    select k.bestatt from kjerne.analyse_kontroll k
    where k.kommune_id = a.kommune_id and k.analyse_id = a.id and k.kontrollert >= a.opprettet
    order by k.kontrollert desc
    limit 1
  );

grant select on all tables in schema publisert to kommunelys_bygg, kommunelys_pipeline;
grant select on kjerne.vurdering_gjeldende, kjerne.analyse_gjeldende
  to kommunelys_bygg, kommunelys_pipeline, authenticated;
grant usage on schema publisert to kommunelys_pipeline, authenticated;
grant select on all tables in schema publisert to authenticated;
