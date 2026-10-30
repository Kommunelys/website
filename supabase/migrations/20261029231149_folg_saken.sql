-- Følg saken: e-post når saken kommer videre (ADR-027).
--
-- En innlogget bruker følger en sak fra nettstedet. Etter bygget sammenligner
-- Oppdater (varsel.kjor) hver fulgt sak med tilstanden ved forrige varsel og
-- legger endringene i køen. Edge-funksjonen varsel sender køen via Resend.
--
-- Vi lagrer behandlingen brukeren så på, ikke ID-en til saken: den er den
-- laveste behandlingen i kjeden og kan endre seg. Saken finnes igjen gjennom
-- kjerne.saksgang_steg.
--
-- Hvilke saker en person følger, kan si noe om hva vedkommende mener. Det
-- logges derfor ikke i endringsloggen, som ikke kan slettes, og alt om
-- brukeren slettes med kontoen. Ingen andre enn brukeren ser det, bortsett
-- fra prosjektadmin direkte i databasen.

create schema varsel;
revoke all on schema varsel from public;
comment on schema varsel is 'Kommunelys: hvem som følger hvilke saker, og køen av e-poster (ADR-027).';

-- Det som er publisert i hver sak --------------------------------------------------

-- Skrives av bygget for hver sak, fra de samme dataene som nettstedet
-- (varsel/tilstand.py). Bare det som er publisert, er med: et sammendrag som
-- holdes tilbake, finnes ikke her. Følger ID-en til saken når den endres.
create table varsel.sak_tilstand (
  kommune_id smallint not null,
  sak_id int not null,
  tilstand jsonb not null,
  primary key (kommune_id, sak_id),
  foreign key (kommune_id, sak_id) references kjerne.sak on update cascade on delete cascade deferrable
);

-- Hvem som følger hva ------------------------------------------------------------

-- tilstand er saken slik den så ut da brukeren sist fikk varsel om den, eller
-- da brukeren begynte å følge den. Ingen fremmednøkkel til saksgang_steg:
-- steg kan forsvinne når kjedene bygges på nytt, og følgingen skal ikke
-- stoppe kjeden.
create table varsel.folger (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  kommune_id smallint not null references kjerne.kommune,
  behandling_id int not null,
  opprettet timestamptz not null default now(),
  tilstand jsonb,
  varslet timestamptz,
  unique (user_id, kommune_id, behandling_id)
);

create index folger_sak on varsel.folger (kommune_id, behandling_id);

-- Saken for en behandling, slik den er nå.
create function varsel.sak_for(p_kommune smallint, p_behandling int) returns int
language sql stable security definer set search_path = '' as $$
  select sak_id from kjerne.saksgang_steg where kommune_id = p_kommune and behandling_id = p_behandling
$$;
revoke all on function varsel.sak_for(smallint, int) from public, anon, authenticated;

-- Ved ny følging: behandlingen må finnes, høyst 200 saker per bruker, og
-- tilstanden er det som var publisert da brukeren trykket. Da sammenlignes
-- neste kjøring med det brukeren så, ikke med det som var nytt over natta.
create function varsel.ny_folger() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  sak int;
begin
  sak := varsel.sak_for(new.kommune_id, new.behandling_id);
  if sak is null then
    raise exception 'Saken finnes ikke' using errcode = 'foreign_key_violation';
  end if;
  if (select count(*) from varsel.folger where user_id = new.user_id) >= 200 then
    raise exception 'Du følger allerede 200 saker. Slutt å følge noen før du følger flere.'
      using errcode = 'check_violation';
  end if;
  new.tilstand := (select t.tilstand from varsel.sak_tilstand t
                   where t.kommune_id = new.kommune_id and t.sak_id = sak);
  return new;
end $$;
revoke all on function varsel.ny_folger() from public;

create trigger ny before insert on varsel.folger
  for each row execute function varsel.ny_folger();

-- Køen og tellingen ----------------------------------------------------------------

-- Det Oppdater har funnet, som skal sendes. Én rad per sak og kjøring; e-posten
-- samler alle radene til brukeren. Forsvinner når brukeren slutter å følge
-- saken eller sletter kontoen.
create table varsel.utsending (
  id bigint generated always as identity primary key,
  folger_id bigint not null references varsel.folger on delete cascade,
  user_id uuid not null references auth.users on delete cascade,
  kommune_id smallint not null references kjerne.kommune,
  sak_id int not null,
  tittel text not null,
  url text not null check (url ~ '^https://(www\.)?kommunelys\.no/'),
  hendelser jsonb not null check (jsonb_typeof(hendelser) = 'array' and jsonb_array_length(hendelser) > 0),
  opprettet timestamptz not null default now(),
  sendt timestamptz,
  forsok smallint not null default 0,
  feil text
);

create index utsending_venter on varsel.utsending (user_id) where sendt is null;
create index utsending_sendt on varsel.utsending (user_id, sendt);

-- Hver e-post som er sendt eller forsøkt, uten hvem den gikk til. Telleren på
-- driftssiden bygger på denne, så tallene står igjen når kontoer slettes.
-- brukt_hos_resend er hodet x-resend-daily-quota fra svaret: alle e-postene
-- fra kontoen i dag, også fra innloggingen (SMTP).
create table varsel.epost (
  id bigint generated always as identity primary key,
  sendt timestamptz not null default now(),
  saker smallint not null,
  resend_id text,
  feil text,
  brukt_hos_resend int
);

create index epost_sendt on varsel.epost (sendt);

-- Grensene. Resend Free (resend.com/pricing, sjekket 29.10.2026): 100 e-poster
-- i døgnet (nullstilles kl. 00 UTC) og 3 000 i måneden, også e-post fra
-- innloggingen og fra post@ via SMTP. Varslene stopper før, så det blir
-- plass til de andre. Samme tall i bygg/drift.py.
create function varsel.grense_dogn() returns int
language sql immutable set search_path = '' as 'select 70';
create function varsel.grense_maned() returns int
language sql immutable set search_path = '' as 'select 2400';

-- RLS ------------------------------------------------------------------------------

alter table varsel.sak_tilstand enable row level security;
alter table varsel.folger enable row level security;
alter table varsel.utsending enable row level security;
alter table varsel.epost enable row level security;

-- Kjeden: bygget skriver tilstanden, varsel.kjor legger i køen og oppdaterer
-- tilstanden på følgingen. Den ser ikke e-postadressene.
grant usage on schema varsel to kommunelys_pipeline, kommunelys_bygg;
create policy pipeline on varsel.sak_tilstand to kommunelys_pipeline using (true) with check (true);
create policy bygg on varsel.sak_tilstand to kommunelys_bygg using (true) with check (true);
grant select, insert, update, delete on varsel.sak_tilstand to kommunelys_pipeline, kommunelys_bygg;

create policy pipeline_leser on varsel.folger for select to kommunelys_pipeline using (true);
create policy pipeline_varsler on varsel.folger for update to kommunelys_pipeline using (true) with check (true);
create policy bygg_leser on varsel.folger for select to kommunelys_bygg using (true);
grant select on varsel.folger to kommunelys_pipeline, kommunelys_bygg;
grant update (tilstand, varslet) on varsel.folger to kommunelys_pipeline;

create policy pipeline on varsel.utsending for select to kommunelys_pipeline using (true);
create policy pipeline_legger_i_ko on varsel.utsending for insert to kommunelys_pipeline with check (true);
create policy bygg_leser on varsel.utsending for select to kommunelys_bygg using (true);
grant select, insert on varsel.utsending to kommunelys_pipeline;
grant select on varsel.utsending to kommunelys_bygg;

create policy pipeline_leser on varsel.epost for select to kommunelys_pipeline using (true);
create policy bygg_leser on varsel.epost for select to kommunelys_bygg using (true);
grant select on varsel.epost to kommunelys_pipeline, kommunelys_bygg;

-- Innloggede følger saker i kommuner de har innsyn i: de som er publisert, og
-- de med begrenset innsyn der de har en rolle (tilgang.innsyn_kommuner tar
-- bare med de siste). De ser og sletter bare sine egne.
grant usage on schema varsel to authenticated;
create policy egne on varsel.folger for select to authenticated
  using (user_id = (select auth.uid()));
create policy folger on varsel.folger for insert to authenticated
  with check (user_id = (select auth.uid())
              and (exists (select 1 from kjerne.kommune k
                           where k.kommune_id = folger.kommune_id and k.status = 'publisert')
                   or kommune_id = any ((select tilgang.innsyn_kommuner())::smallint[])));
create policy slutter on varsel.folger for delete to authenticated
  using (user_id = (select auth.uid()));
grant select (id, user_id, kommune_id, behandling_id, opprettet), insert (kommune_id, behandling_id), delete
  on varsel.folger to authenticated;

-- Saken og tittelen for en behandling brukeren følger. Brukeren ser ikke
-- kjerne.sak uten tilgang (les_med_tilgang); sakstitlene er offentlige på
-- nettstedet, men bare for saker brukeren selv følger.
create function varsel.fulgt_sak(p_kommune smallint, p_behandling int)
returns table (sak_id int, tittel text)
language sql stable security definer set search_path = '' as $$
  select s.sak_id, s.tittel
  from kjerne.saksgang_steg g
  join kjerne.sak s on s.kommune_id = g.kommune_id and s.sak_id = g.sak_id
  where g.kommune_id = p_kommune and g.behandling_id = p_behandling
    and exists (select 1 from varsel.folger f
                where f.user_id = (select auth.uid())
                  and f.kommune_id = p_kommune and f.behandling_id = p_behandling)
$$;
revoke all on function varsel.fulgt_sak(smallint, int) from public, anon;
grant execute on function varsel.fulgt_sak(smallint, int) to authenticated;

-- Portalen og nettstedet -----------------------------------------------------------

-- Sakene brukeren følger. sak_id er dagens; nettstedet bruker den til å vise
-- «Følger» på saken, portalen til lenken under Min konto.
create view portal.folger with (security_invoker = on) as
  select f.id, ko.slug as kommune, f.kommune_id, f.behandling_id, s.sak_id, s.tittel, f.opprettet
  from varsel.folger f
  join kjerne.kommune ko on ko.kommune_id = f.kommune_id
  left join lateral varsel.fulgt_sak(f.kommune_id, f.behandling_id) s on true;

-- Innsetting med kommunen som slug (nettstedet kjenner ikke ID-en), og
-- sletting. Kjører som brukeren, så RLS gjelder. Følger brukeren saken
-- allerede, er det ingen feil.
create function portal.skriv_folger() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    delete from varsel.folger where id = old.id;
    return old;
  end if;
  if new.kommune_id is null then
    select kommune_id into new.kommune_id from kjerne.kommune where slug = new.kommune;
  end if;
  insert into varsel.folger (kommune_id, behandling_id) values (new.kommune_id, new.behandling_id)
    on conflict (user_id, kommune_id, behandling_id) do nothing;
  select f.id, f.opprettet into new.id, new.opprettet from varsel.folger f
  where f.user_id = (select auth.uid()) and f.kommune_id = new.kommune_id
    and f.behandling_id = new.behandling_id;
  select s.sak_id, s.tittel into new.sak_id, new.tittel
  from varsel.fulgt_sak(new.kommune_id, new.behandling_id) s;
  return new;
end $$;
revoke all on function portal.skriv_folger() from public, anon;

create trigger skriv instead of insert or delete on portal.folger
  for each row execute function portal.skriv_folger();

grant select, insert, delete on portal.folger to authenticated;

-- Edge-funksjonen varsel -----------------------------------------------------------

-- Funksjonen når bare skjemaet portal gjennom Data API-et, med service-nøkkelen.
-- Disse tre er bare for den (service_role), ikke for innloggede.

-- Brukerne som skal få e-post nå, med adressen og radene fra køen. Høyst én
-- e-post per bruker i døgnet, og ikke flere enn grensene gir plass til i dag
-- og denne måneden. Ikke til sperrede brukere, og ikke for en kommune brukeren
-- har mistet innsynet i: de radene fjernes fra køen.
create function portal.varsel_til_sending() returns table (user_id uuid, epost text, saker jsonb)
language plpgsql security definer set search_path = '' as $$
declare
  i_dag date := (now() at time zone 'utc')::date;
  plass int;
begin
  delete from varsel.utsending u
  where u.sendt is null
    and not exists (select 1 from kjerne.kommune k
                    where k.kommune_id = u.kommune_id and k.status = 'publisert')
    and not exists (select 1 from tilgang.medlemskap m
                    where m.user_id = u.user_id and m.kommune_id = u.kommune_id)
    and not exists (select 1 from tilgang.prosjektadmin p where p.user_id = u.user_id);

  plass := least(
    varsel.grense_dogn() - (select count(*) from varsel.epost e
                            where (e.sendt at time zone 'utc')::date = i_dag),
    varsel.grense_maned() - (select count(*) from varsel.epost e
                             where date_trunc('month', e.sendt at time zone 'utc')
                                 = date_trunc('month', now() at time zone 'utc')));
  if plass <= 0 then
    return;
  end if;

  return query
    select u.user_id, b.email::text,
           jsonb_agg(jsonb_build_object('id', u.id, 'folger_id', u.folger_id, 'sak_id', u.sak_id,
                                        'tittel', u.tittel, 'url', u.url, 'hendelser', u.hendelser)
                     order by u.opprettet, u.id)
    from varsel.utsending u
    join auth.users b on b.id = u.user_id
    where u.sendt is null and u.forsok < 3
      and b.email is not null
      and (b.banned_until is null or b.banned_until < now())
      and not exists (select 1 from varsel.utsending s
                      where s.user_id = u.user_id and (s.sendt at time zone 'utc')::date = i_dag)
    group by u.user_id, b.email
    order by min(u.opprettet)
    limit plass;
end $$;

-- Etter hvert forsøk: radene er sendt, eller forsøket telles. E-posten telles
-- uansett, siden et forsøk også kan gå av grensen hos Resend.
create function portal.varsel_sendt(p_ider bigint[], p_resend_id text, p_feil text, p_brukt int)
returns void
language plpgsql security definer set search_path = '' as $$
begin
  if p_feil is null then
    update varsel.utsending set sendt = now(), feil = null where id = any (p_ider);
    update varsel.folger f set varslet = now()
    where f.id in (select folger_id from varsel.utsending where id = any (p_ider));
  else
    update varsel.utsending set forsok = forsok + 1, feil = left(p_feil, 500) where id = any (p_ider);
  end if;
  insert into varsel.epost (saker, resend_id, feil, brukt_hos_resend)
    values (cardinality(p_ider), p_resend_id, left(p_feil, 500), p_brukt);
end $$;

-- «Slutt å følge» fra e-posten. Nøkkelen er kontrollert i funksjonen før
-- dette kalles. Med p_folger stopper én sak, ellers alle sakene til brukeren.
create function portal.varsel_slutt(p_bruker uuid, p_folger bigint) returns int
language plpgsql security definer set search_path = '' as $$
declare
  antall int;
begin
  delete from varsel.folger
  where user_id = p_bruker and (p_folger is null or id = p_folger);
  get diagnostics antall = row_count;
  return antall;
end $$;

revoke all on function portal.varsel_til_sending(), portal.varsel_sendt(bigint[], text, text, int),
  portal.varsel_slutt(uuid, bigint) from public, anon, authenticated;
grant usage on schema portal to service_role;
grant execute on function portal.varsel_til_sending(), portal.varsel_sendt(bigint[], text, text, int),
  portal.varsel_slutt(uuid, bigint) to service_role;

notify pgrst, 'reload schema';
