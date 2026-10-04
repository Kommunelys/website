-- Prøver å bryte reglene i databasen, og ser at de holder.
--
-- Alt skjer i én transaksjon som rulles tilbake: til slutt kastes en feil
-- med resultatet, så ingenting blir liggende igjen. Kjøres som postgres mot
-- en database med migreringene, for eksempel testprosjektet:
--
--   psql "$DB_URL" -f supabase/tests/regler.sql
--
-- Svaret er feilmeldingen «RESULTAT n av m ok», med én linje per test.

create temp table resultat (test text, ok boolean, melding text);

-- Forventer at setningen feiler, også ved de utsatte kontrollene. Setningen
-- rulles alltid tilbake. Resultatet skrives etterpå, som postgres, siden
-- setningen kan bytte rolle.
create function pg_temp.skal_feile(navn text, setning text) returns void
language plpgsql as $$
declare
  melding text;
begin
  begin
    set constraints all deferred;
    execute setning;
    set constraints all immediate;
    raise exception 'KOMMUNELYS_RULL_TILBAKE';
  exception when others then
    if sqlerrm <> 'KOMMUNELYS_RULL_TILBAKE' then
      melding := sqlerrm;
    end if;
  end;
  set constraints all immediate;
  insert into resultat values (navn, melding is not null, coalesce(melding, 'ingen feil'));
end $$;

-- Forventer at setningen går gjennom, også de utsatte kontrollene. Blir
-- stående hvis den virker.
create function pg_temp.skal_virke(navn text, setning text) returns void
language plpgsql as $$
declare
  melding text;
begin
  begin
    set constraints all deferred;
    execute setning;
    set constraints all immediate;
  exception when others then
    melding := sqlerrm;
  end;
  set constraints all immediate;
  insert into resultat values (navn, melding is null, melding);
end $$;

create function pg_temp.skal_vaere(navn text, verdi boolean) returns void
language sql as $$
  insert into resultat values (navn, coalesce(verdi, false), case when verdi then null else 'usant' end)
$$;

do $$
declare
  k smallint := (select kommune_id from kjerne.kommune where slug = 'steinkjer');
  k2 smallint;
  kari bigint;
  ola bigint;
  dok bigint;
  bruker uuid := gen_random_uuid();
  svar boolean;
  svar2 boolean;
  svar3 boolean;
  svar4 boolean;
  svar5 boolean;
  linjer text;
begin
  perform set_config('kommunelys.kjoring_id', 'test', true);

  -- Testdata ----------------------------------------------------------------
  insert into kjerne.utvalg values (k, 100, 'KS', 'Kommunestyret');
  insert into kjerne.mote (kommune_id, mote_id, utvalg_id, utvalg, utvalg_navn, dato, slutt, antall_saker, url)
    values (k, 1000, 100, 'KS', 'Kommunestyret', '2026-01-01 10:00', '', 1, 'https://portal/mote');
  insert into kjerne.sak values (k, 5000, 2026, 1, 'Testsak', false, 'PS', false, 'Behandlet', true);
  insert into kjerne.saksgang_steg (kommune_id, behandling_id, sak_id, rekkefolge, hentet, mote_id, dato,
      utvalg, utvalg_navn, saksnr, protokoll_publisert, protokoll_skjermet, url_mote, url_vedtak)
    values (k, 5000, 5000, 0, true, 1000, '2026-01-01 10:00', 'KS', 'Kommunestyret', 'PS 1/2026',
            true, false, 'https://portal/mote', 'https://portal/vedtak');
  insert into kjerne.vedtak_tolket values (k, 5000);
  insert into kjerne.person (kommune_id, navn, slug) values (k, 'Kari Test', 'kari-test') returning id into kari;
  insert into kjerne.person (kommune_id, navn, slug) values (k, 'Ola Test', 'ola-test') returning id into ola;

  -- Regel 2: stemmetall ----------------------------------------------------
  perform pg_temp.skal_virke('stemmetall: 2 for med 2 navn',
    format($s$
      insert into kjerne.votering (kommune_id, behandling_id, nr, type, resultat, enstemmig, antall_for, antall_mot, tall_stemmer)
        values (%1$s, 5000, 1, 'innstilling', 'vedtatt', false, 2, 0, true);
      insert into kjerne.stemme values (%1$s, 5000, 1, %2$s, 'for', null, 'AP', 1),
                                       (%1$s, 5000, 1, %3$s, 'for', null, 'H', 2);
    $s$, k, kari, ola));
  perform pg_temp.skal_feile('stemmetall: 2 for med 1 navn stoppes',
    format($s$
      insert into kjerne.votering (kommune_id, behandling_id, nr, type, resultat, enstemmig, antall_for, antall_mot, tall_stemmer)
        values (%1$s, 5000, 2, 'forslag', 'falt', false, 2, 0, true);
      insert into kjerne.stemme values (%1$s, 5000, 2, %2$s, 'for', null, 'AP', 1);
    $s$, k, kari));
  perform pg_temp.skal_feile('stemmetall: å fjerne et navn senere stoppes',
    format('delete from kjerne.stemme where kommune_id = %s and behandling_id = 5000 and nr = 1 and person_id = %s', k, ola));
  perform pg_temp.skal_virke('stemmetall: avvik lagres når tall_stemmer er usann',
    format($s$
      insert into kjerne.votering (kommune_id, behandling_id, nr, type, resultat, enstemmig, antall_for, antall_mot, tall_stemmer)
        values (%1$s, 5000, 3, 'forslag', 'falt', false, 5, 0, false);
      insert into kjerne.stemme values (%1$s, 5000, 3, %2$s, 'for', null, 'AP', 1);
    $s$, k, kari));
  perform pg_temp.skal_feile('stemmetall: enstemmig med navn stoppes',
    format($s$
      insert into kjerne.votering (kommune_id, behandling_id, nr, type, resultat, enstemmig, antall_for, antall_mot, tall_stemmer)
        values (%1$s, 5000, 4, 'enstemmig', 'vedtatt', true, null, 0, true);
      insert into kjerne.stemme values (%1$s, 5000, 4, %2$s, 'for', null, 'AP', 1);
    $s$, k, kari));
  perform pg_temp.skal_feile('stemmetall: samme person to ganger stoppes',
    format($s$insert into kjerne.stemme values (%1$s, 5000, 1, %2$s, 'mot', null, 'AP', 3)$s$, k, kari));
  perform pg_temp.skal_virke('stemmetall: alternativ votering med riktig antall',
    format($s$
      insert into kjerne.votering (kommune_id, behandling_id, nr, type, resultat, enstemmig, antall_for, antall_mot, tall_stemmer)
        values (%1$s, 5000, 5, 'alternative forslag', 'vedtatt', false, 0, 0, true);
      insert into kjerne.votering_alternativ values (%1$s, 5000, 5, '1', 1, 1), (%1$s, 5000, 5, '2', 1, 2);
      insert into kjerne.stemme values (%1$s, 5000, 5, %2$s, 'alternativ', '1', 'AP', 1),
                                       (%1$s, 5000, 5, %3$s, 'alternativ', '2', 'H', 2);
    $s$, k, kari, ola));
  perform pg_temp.skal_feile('stemmetall: alternativ votering med feil antall stoppes',
    format($s$update kjerne.votering_alternativ set antall = 2
              where kommune_id = %s and behandling_id = 5000 and nr = 5 and forslag = '1'$s$, k));

  -- Kommunene holdes adskilt ------------------------------------------------
  insert into kjerne.kommune (kommunenr, slug, navn) values ('9999', 'testkommune', 'Testkommune')
    returning kommune_id into k2;
  perform pg_temp.skal_feile('kommune: en rad kan ikke peke til en person i en annen kommune',
    format($s$insert into kjerne.navnevariant values (%s, 'Kari T.', %s, 'test')$s$, k2, kari));

  -- Rådata og ADR-014 -----------------------------------------------------------
  insert into kjerne.raa_svar (kommune_id, kilde, nokkel, sjekksum, innhold)
    values (k, 'mote', '1000', 'abc', '{"mote": {}}');
  perform pg_temp.skal_feile('rådata: kan ikke endres',
    format('update kjerne.raa_svar set innhold = ''{}'' where kommune_id = %s', k));
  perform pg_temp.skal_feile('rådata: kan ikke slettes',
    format('delete from kjerne.raa_svar where kommune_id = %s', k));
  perform pg_temp.skal_feile('rådata: kan ikke tømmes', 'truncate kjerne.raa_svar');
  perform pg_temp.skal_feile('medlemsliste: mobilnummer stoppes (ADR-014)',
    format($s$insert into kjerne.raa_svar (kommune_id, kilde, nokkel, sjekksum, innhold)
      values (%s, 'medlemsliste', '2026-10-04', 'x',
              '{"utvalg": {"100": {"medlemmer": [{"navn": "Kari Test", "mobil": "99999999"}]}}}')$s$, k));
  perform pg_temp.skal_virke('medlemsliste: rolle og person-ID går gjennom',
    format($s$insert into kjerne.raa_svar (kommune_id, kilde, nokkel, sjekksum, innhold)
      values (%s, 'medlemsliste', '2026-10-04', 'y',
              '{"utvalg": {"100": {"medlemmer": [{"navn": "Kari Test", "person_id": 1, "funksjon": "Medlem", "repr": "AP", "repr_navn": "Arbeiderpartiet"}]}}}')$s$, k));

  -- Regel 3 og ADR-006: tekst ----------------------------------------------------
  insert into kjerne.dokument (kommune_id, id_rom, portal_id, slag, url, mote_id)
    values (k, 'motedokument', 77, 'moteinnkalling', 'https://portal/mi', 1000) returning id into dok;
  perform pg_temp.skal_feile('tekst: møteinnkallingen lagres ikke (ADR-006)',
    format($s$insert into kjerne.dokument_tekst (kommune_id, dokument_id, tekst) values (%s, %s, 'alt')$s$, k, dok));
  insert into kjerne.dokument (kommune_id, id_rom, portal_id, slag, url, behandling_id)
    values (k, 'behandling', 5000, 'saksprotokoll', 'https://portal/vedtak', 5000) returning id into dok;
  insert into kjerne.dokument_tekst (kommune_id, dokument_id, tekst) values (k, dok, 'Vedtak: ...');
  perform pg_temp.skal_feile('saksgang: skjermet vedtak med lenke stoppes',
    format('update kjerne.saksgang_steg set protokoll_skjermet = true where kommune_id = %s and behandling_id = 5000', k));
  update kjerne.saksgang_steg set protokoll_skjermet = true, url_vedtak = null
    where kommune_id = k and behandling_id = 5000;
  perform pg_temp.skal_vaere('tekst: forsvinner når vedtaket blir skjermet',
    not exists (select 1 from kjerne.dokument_tekst where kommune_id = k and dokument_id = dok));
  perform pg_temp.skal_feile('tekst: lagres ikke for skjermet vedtak',
    format($s$
      insert into kjerne.dokument (kommune_id, id_rom, portal_id, slag, url, behandling_id)
        values (%1$s, 'behandling', 5000, 'saksprotokoll', 'https://portal/vedtak', 5000);
      insert into kjerne.dokument_tekst (kommune_id, dokument_id, tekst)
        select %1$s, id, 'Vedtak' from kjerne.dokument where kommune_id = %1$s and portal_id = 5000 and id_rom = 'behandling';
    $s$, k));
  update kjerne.saksgang_steg set protokoll_skjermet = false, url_vedtak = 'https://portal/vedtak'
    where kommune_id = k and behandling_id = 5000;

  -- Analyse (regel 5) -------------------------------------------------------------
  perform pg_temp.skal_feile('analyse: uten kildelenke stoppes',
    format($s$insert into kjerne.analyse (kommune_id, sak_id, tittel_klarsprak, sammendrag, betydning, tagger,
      utfall, uenighet, usikker, sjekksum, modell, innsats, instruksjon_versjon, dato, kilder)
      values (%s, 5000, 'T', 'S', 'B', '{Økonomi}', 'vedtatt', '', false, 'x', 'm', 'high', 3, '2026-10-04', '[]')$s$, k));
  perform pg_temp.skal_feile('analyse: ukjent tagg stoppes',
    format($s$insert into kjerne.analyse (kommune_id, sak_id, tittel_klarsprak, sammendrag, betydning, tagger,
      utfall, uenighet, usikker, sjekksum, modell, innsats, instruksjon_versjon, dato, kilder)
      values (%s, 5000, 'T', 'S', 'B', '{Fotball}', 'vedtatt', '', false, 'x', 'm', 'high', 3, '2026-10-04',
              '[{"tittel": "Saksframlegg", "url": "https://portal/doc"}]')$s$, k));
  insert into kjerne.analyse (kommune_id, sak_id, tittel_klarsprak, sammendrag, betydning, tagger,
      utfall, uenighet, usikker, sjekksum, modell, innsats, instruksjon_versjon, dato, kilder)
    values (k, 5000, 'T', 'S', 'B', '{Økonomi}', 'vedtatt', '', false, 'x', 'm', 'high', 3, '2026-10-04',
            '[{"tittel": "Saksframlegg", "url": "https://portal/doc"}]');
  perform pg_temp.skal_feile('analyse: kan ikke endres',
    format('update kjerne.analyse set sammendrag = ''annet'' where kommune_id = %s', k));
  perform pg_temp.skal_vaere('sammendrag: vises ikke før det er kontrollert',
    not exists (select 1 from publisert.sammendrag where kommune_id = k));
  insert into kjerne.analyse_kontroll (kommune_id, analyse_id, bestatt)
    select k, id, true from kjerne.analyse where kommune_id = k;
  perform pg_temp.skal_vaere('sammendrag: vises når kontrollen er bestått',
    exists (select 1 from publisert.sammendrag where kommune_id = k));
  perform pg_temp.skal_virke('sak: ny sak-ID flyttes til analysen',
    format('update kjerne.sak set sak_id = 4999 where kommune_id = %s and sak_id = 5000', k));
  perform pg_temp.skal_vaere('sak: analysen fulgte med',
    exists (select 1 from kjerne.analyse where kommune_id = k and sak_id = 4999));
  update kjerne.sak set sak_id = 5000 where kommune_id = k and sak_id = 4999;

  -- Avvik og publisering (ADR-015) ------------------------------------------------
  insert into kjerne.avvik (kommune_id, avvik, type, utvalg, dato, beskrivelse)
    values (k, 'oppmote:1000:kari-test', 'oppmote', 'KS', '2026-01-01', 'Kari Test stemmer uten å stå på oppmøtelisten');
  insert into kjerne.avvik_votering values (k, 'oppmote:1000:kari-test', 5000, 1, 1);
  perform pg_temp.skal_vaere('publisering: votering med avvik uten vurdering holdes tilbake',
    (select holdt from publisert.votering_status where kommune_id = k and behandling_id = 5000 and nr = 1));
  perform pg_temp.skal_vaere('publisering: navnene vises ikke når voteringen holdes tilbake',
    not exists (select 1 from publisert.stemme where kommune_id = k and behandling_id = 5000 and nr = 1));
  perform pg_temp.skal_vaere('publisering: tallene vises ikke når voteringen holdes tilbake',
    (select antall_for is null from publisert.votering where kommune_id = k and behandling_id = 5000 and nr = 1));
  perform pg_temp.skal_vaere('publisering: votering der tallene ikke stemmer, holdes tilbake',
    (select holdt from publisert.votering_status where kommune_id = k and behandling_id = 5000 and nr = 3));
  perform pg_temp.skal_feile('vurdering: uten begrunnelse stoppes',
    format($s$insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, begrunnelse, vurdert_av, dato)
      values (%s, 'oppmote:1000:kari-test', 'publiser', ' ', 'test', '2026-10-04')$s$, k));
  perform pg_temp.skal_feile('vurdering: av avvik som ikke finnes, stoppes',
    format($s$insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, begrunnelse, vurdert_av, dato)
      values (%s, 'oppmote:1000:ingen', 'publiser', 'b', 'test', '2026-10-04')$s$, k));
  insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato)
    values (k, 'oppmote:1000:kari-test', 'publiser', 'Merknaden', 'Begrunnelse', 'test', '2026-10-04');
  perform pg_temp.skal_vaere('publisering: vises når vurderingen er publiser, med merknad',
    (select not holdt and merknader = array['Merknaden']
     from publisert.votering_status where kommune_id = k and behandling_id = 5000 and nr = 1));
  perform pg_temp.skal_vaere('publisering: navnene vises etter vurderingen',
    (select count(*) = 2 from publisert.stemme where kommune_id = k and behandling_id = 5000 and nr = 1));
  perform pg_temp.skal_feile('vurdering: kan ikke endres',
    format('update kjerne.vurdering set avgjorelse = ''ikke_publiser'' where kommune_id = %s', k));

  -- Endringsloggen ---------------------------------------------------------------
  perform pg_temp.skal_vaere('endringslogg: ny sak logges med kjøringen',
    exists (select 1 from drift.endringslogg
            where tabell = 'sak' and operasjon = 'I' and kjoring_id = 'test' and nokkel ->> 'sak_id' = '5000'));
  perform pg_temp.skal_vaere('endringslogg: endret sak-ID logges som endring',
    exists (select 1 from drift.endringslogg
            where tabell = 'sak' and operasjon = 'U' and 'sak_id' = any (endrede_felt)));
  perform pg_temp.skal_vaere('endringslogg: teksten selv logges ikke',
    not exists (select 1 from drift.endringslogg where tabell = 'dokument_tekst' and ny ? 'tekst'));
  perform pg_temp.skal_feile('endringslogg: kan ikke endres',
    'update drift.endringslogg set tabell = ''x''');

  -- Roller og RLS -----------------------------------------------------------------
  perform pg_temp.skal_feile('anon: ser ingenting',
    'set local role anon; select count(*) from kjerne.sak');
  perform pg_temp.skal_feile('pipeline: kan ikke endre rådata',
    format('set local role kommunelys_pipeline; update kjerne.raa_svar set kjoring_id = ''x'' where kommune_id = %s', k));
  perform pg_temp.skal_feile('pipeline: kan ikke skrive i endringsloggen direkte',
    $s$set local role kommunelys_pipeline;
       insert into drift.endringslogg (tabell, operasjon, nokkel) values ('x', 'I', '{}')$s$);
  perform pg_temp.skal_feile('pipeline: ser ikke tilgangstabellene',
    'set local role kommunelys_pipeline; select count(*) from tilgang.medlemskap');
  perform pg_temp.skal_feile('bygg: kan ikke endre saker',
    format('set local role kommunelys_bygg; update kjerne.sak set tittel = ''x'' where kommune_id = %s', k));

  set local role kommunelys_pipeline;
  svar := (select count(*) = 1 from kjerne.sak where kommune_id = k);
  reset role;
  perform pg_temp.skal_vaere('pipeline: leser kjerne', svar);

  -- En innlogget bruker uten tilgang ser ingenting.
  perform set_config('request.jwt.claims', json_build_object('sub', bruker, 'role', 'authenticated')::text, true);
  set local role authenticated;
  svar := (select count(*) = 0 from kjerne.sak);
  svar2 := (select count(*) = 0 from publisert.stemme);
  reset role;
  perform pg_temp.skal_vaere('innlogget uten tilgang: ser ingen saker', svar);
  perform pg_temp.skal_vaere('innlogget uten tilgang: ser ingen stemmer', svar2);

  -- Med abonnement på Steinkjer: ser Steinkjer, ikke testkommunen.
  begin
    insert into auth.users (id, aud, role, email)
      values (bruker, 'authenticated', 'authenticated', 'test@example.invalid');
    insert into kjerne.sak values (k2, 6000, 2026, 1, 'Annen kommune', false, 'PS', false, 'Behandlet', false);
    insert into tilgang.abonnement (user_id, kommune_id, produkt, gyldig, kilde)
      values (bruker, k, 'api', tstzrange(now() - interval '1 day', now() + interval '30 days'), 'manuell');
    set local role authenticated;
    svar := (select count(*) = 1 from kjerne.sak where kommune_id = k);
    svar2 := (select count(*) = 0 from kjerne.sak where kommune_id = k2);
    svar3 := (select count(*) = 0 from kjerne.avvik);
    svar4 := (select count(*) = 0 from kjerne.dokument_tekst);
    svar5 := (select count(*) = 2 from publisert.stemme where kommune_id = k and behandling_id = 5000 and nr = 1);
    reset role;
    perform pg_temp.skal_vaere('abonnent: ser sakene i sin kommune', svar);
    perform pg_temp.skal_vaere('abonnent: ser ikke saker i en annen kommune', svar2);
    perform pg_temp.skal_vaere('abonnent: ser ikke avvik og vurderinger', svar3);
    perform pg_temp.skal_vaere('abonnent: ser ikke teksten uten fulltekst', svar4);
    perform pg_temp.skal_vaere('abonnent: ser publiserte stemmer', svar5);
    perform pg_temp.skal_feile('abonnent: kan ikke legge inn vurderinger',
      format($s$set local role authenticated;
        insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, begrunnelse, vurdert_av, dato, registrert_av)
        values (%s, 'oppmote:1000:kari-test', 'publiser', 'b', 'meg', '2026-10-04', '%s')$s$, k, bruker));
    update tilgang.abonnement set gyldig = tstzrange(now() - interval '30 days', now() - interval '1 day')
      where user_id = bruker;
    set local role authenticated;
    svar := (select count(*) = 0 from kjerne.sak);
    reset role;
    perform pg_temp.skal_vaere('abonnent: utløpt abonnement gir ingen tilgang', svar);
  exception when others then
    reset role;
    insert into resultat values ('abonnent: kunne ikke kjøres', false, sqlerrm);
  end;

  -- Resultat --------------------------------------------------------------------
  select string_agg(case when ok then 'ok   ' else 'FEIL ' end || test
                    || coalesce('  [' || left(melding, 100) || ']', ''), E'\n' order by ok, test)
    into linjer from resultat;
  raise exception E'RESULTAT % av % ok\n%',
    (select count(*) filter (where ok) from resultat), (select count(*) from resultat), linjer;
end $$;
