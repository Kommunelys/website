-- Portalen på portal.kommunelys.no (ADR-020).
--
-- Skjemaet portal er det eneste som eksponeres i Supabase Data API. Det har
-- bare views med security_invoker og funksjoner uten security definer, så
-- RLS-en på tabellene under gjelder uendret. anon får ingenting.
--
-- Prosjektadmin gis fortsatt bare som postgres (SQL-editoren), aldri herfra.

create schema portal;
revoke all on schema portal from public;
grant usage on schema portal to authenticated;

-- Hvem er jeg: styrer hvilke menyer portalen viser. Tilgangen håndheves av
-- RLS, ikke av dette svaret.
create function portal.meg() returns jsonb
language sql stable set search_path = '' as $$
  select jsonb_build_object(
    'er_prosjektadmin', (select tilgang.er_prosjektadmin()),
    'admin_kommuner', to_jsonb((select tilgang.admin_kommuner())),
    'vurderer_kommuner', to_jsonb((select tilgang.vurderer_kommuner())))
$$;
revoke all on function portal.meg() from public, anon;
grant execute on function portal.meg() to authenticated;

-- Kodeverk ------------------------------------------------------------------------

create view portal.kommune with (security_invoker = on) as
  select kommune_id, slug, navn, status from kjerne.kommune;

create view portal.produkt with (security_invoker = on) as
  select produkt, beskrivelse from tilgang.produkt;

-- Tilgang ---------------------------------------------------------------------------

-- Prosjektadmin ser hvem som er prosjektadmin. Andre ser bare seg selv.
create policy prosjektadmin_leser on tilgang.prosjektadmin for select to authenticated
  using ((select tilgang.er_prosjektadmin()));

create view portal.prosjektadmin with (security_invoker = on) as
  select user_id, lagt_til from tilgang.prosjektadmin;

create view portal.medlemskap with (security_invoker = on) as
  select user_id, kommune_id, rolle, lagt_til from tilgang.medlemskap;

-- Perioden vises som fra og til, som er enklere i et skjema enn tstzrange.
-- Til kan være tom: da gjelder abonnementet til det avsluttes.
create view portal.abonnement with (security_invoker = on) as
  select id, user_id, kommune_id, produkt, lower(gyldig) as fra, upper(gyldig) as til,
         kilde, ekstern_ref
  from tilgang.abonnement;

-- Kjører som brukeren, så RLS på tilgang.abonnement gjelder.
create function portal.skriv_abonnement() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    delete from tilgang.abonnement where id = old.id;
    return old;
  end if;
  new.fra := coalesce(new.fra, now());
  new.kilde := coalesce(new.kilde, 'manuell');
  if tg_op = 'UPDATE' then
    update tilgang.abonnement
       set user_id = new.user_id, kommune_id = new.kommune_id, produkt = new.produkt,
           gyldig = tstzrange(new.fra, new.til), kilde = new.kilde, ekstern_ref = new.ekstern_ref
     where id = old.id;
    new.id := old.id;
  else
    insert into tilgang.abonnement (user_id, kommune_id, produkt, gyldig, kilde, ekstern_ref)
      values (new.user_id, new.kommune_id, new.produkt, tstzrange(new.fra, new.til),
              new.kilde, new.ekstern_ref)
      returning id into new.id;
  end if;
  return new;
end $$;
revoke all on function portal.skriv_abonnement() from public, anon;

create trigger skriv instead of insert or update or delete on portal.abonnement
  for each row execute function portal.skriv_abonnement();

-- Avvik og vurderinger --------------------------------------------------------------

-- Avvikene med gjeldende vurdering og sakene voteringene hører til.
create view portal.avvik with (security_invoker = on) as
  select a.kommune_id, a.avvik, a.type, a.utvalg, a.dato, a.beskrivelse, a.kilde, a.aktiv,
         v.avgjorelse, v.merknad, v.begrunnelse, v.vurdert_av, v.dato as vurdert,
         (select string_agg(distinct s.tittel, ' | ')
            from kjerne.avvik_votering av
            join kjerne.saksgang_steg g using (kommune_id, behandling_id)
            join kjerne.sak s on s.kommune_id = g.kommune_id and s.sak_id = g.sak_id
           where av.kommune_id = a.kommune_id and av.avvik = a.avvik) as saker
  from kjerne.avvik a
  left join kjerne.vurdering_gjeldende v using (kommune_id, avvik);

-- Bare innsetting, som tabellen under. registrert_av settes fra innloggingen;
-- policyen vurderer_skriver krever at den er brukeren selv.
create view portal.vurdering with (security_invoker = on) as
  select id, kommune_id, avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato,
         registrert, registrert_av
  from kjerne.vurdering;
alter view portal.vurdering alter column registrert_av set default auth.uid();
alter view portal.vurdering alter column dato set default current_date;

-- Driftssiden -------------------------------------------------------------------------

-- Driftssiden bygges som før, men lagres her i stedet for å publiseres på
-- nettstedet. Portalen viser den nyeste.
create table drift.side (
  id bigint generated always as identity primary key,
  bygget timestamptz not null default now(),
  kjoring_id text,
  html text not null check (length(html) > 0)
);

alter table drift.side enable row level security;
create policy pipeline on drift.side to kommunelys_pipeline using (true) with check (true);
create policy bygg_leser on drift.side for select to kommunelys_bygg using (true);
create policy bygg_skriver on drift.side for insert to kommunelys_bygg with check (true);
create policy bygg_rydder on drift.side for delete to kommunelys_bygg
  using (bygget < now() - interval '30 days');
create policy les_som_prosjektadmin on drift.side for select to authenticated
  using ((select tilgang.er_prosjektadmin()));
grant select, insert, delete on drift.side to kommunelys_pipeline, kommunelys_bygg;
grant select on drift.side to authenticated;
grant usage on all sequences in schema drift to kommunelys_pipeline, kommunelys_bygg;

create view portal.drift_side with (security_invoker = on) as
  select id, bygget, kjoring_id, html from drift.side order by bygget desc, id desc limit 1;

-- Rettigheter -------------------------------------------------------------------------

grant select on portal.kommune, portal.produkt, portal.prosjektadmin, portal.avvik,
  portal.drift_side to authenticated;
grant select, insert, update, delete on portal.medlemskap, portal.abonnement to authenticated;
grant select, insert on portal.vurdering to authenticated;

notify pgrst, 'reload schema';
