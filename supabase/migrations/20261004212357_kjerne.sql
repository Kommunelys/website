-- Domenedataene. Erstatter filene i data/.
--
-- Hver tabell har kommune_id først i primærnøkkelen. Portalens ID-er er bare
-- unike innenfor én kommunes portal. Fremmednøkler mellom tabellene tar med
-- kommune_id, så en rad i én kommune aldri kan peke til en rad i en annen.
--
-- Fremmednøkler mellom avledede data er DEFERRABLE, så en hel kjøring kan
-- skrives i én transaksjon med `set constraints all deferred`.

-- Kommuner ------------------------------------------------------------------

create table kjerne.kommune (
  kommune_id smallint generated always as identity primary key,
  kommunenr char(4) not null unique check (kommunenr ~ '^[0-9]{4}$'),
  slug text not null unique check (slug ~ '^[a-z0-9-]+$'),
  navn text not null check (btrim(navn) <> ''),
  -- Hvilken kildeadapter som henter dataene (hent/kilder/), og oppsettet den
  -- trenger, for Elements: basis, tenant og database.
  kilde_type text not null default 'elements' check (kilde_type in ('elements')),
  kilde_konfig jsonb not null default '{}' check (jsonb_typeof(kilde_konfig) = 'object'),
  -- ADR-007 gjelder hver kommune for seg.
  status text not null default 'kartlegging'
    check (status in ('kartlegging', 'intern', 'publisert')),
  avklart_med_kommunen date
);

comment on table kjerne.kommune is 'Én rad per kommune. Visningsoppsettet ligger i kommuner/<slug>.json.';

-- Rådata (ADR-001) ------------------------------------------------------------

create table kjerne.raa_svar (
  id bigint generated always as identity primary key,
  kommune_id smallint not null references kjerne.kommune,
  kilde text not null check (kilde in ('moteliste', 'mote', 'medlemsliste')),
  -- Året for møtelisten, møte-ID for et møte, datoen for en medlemsliste.
  nokkel text not null check (btrim(nokkel) <> ''),
  hentet timestamptz not null default now(),
  sjekksum text not null,
  innhold jsonb not null,
  kjoring_id text,
  unique (kommune_id, kilde, nokkel, sjekksum)
);

create index raa_svar_siste on kjerne.raa_svar (kommune_id, kilde, nokkel, hentet desc);

comment on table kjerne.raa_svar is
  'Rå svar fra portalen. Bare innsetting: en ny versjon er en ny rad. Slettes aldri.';

-- Utvalg og partier -----------------------------------------------------------

create table kjerne.utvalg (
  kommune_id smallint not null references kjerne.kommune,
  utvalg_id int not null,  -- portalens UT_ID
  kortnavn text not null,
  navn text not null,
  primary key (kommune_id, utvalg_id)
);

create table kjerne.utvalg_aar (
  kommune_id smallint not null,
  aar smallint not null,
  utvalg_id int not null,
  faste_medlemmer smallint not null check (faste_medlemmer >= 0),
  varamedlemmer smallint not null check (varamedlemmer >= 0),
  moter smallint not null check (moter >= 0),
  medlemsliste_hentet date,
  primary key (kommune_id, aar, utvalg_id),
  foreign key (kommune_id, utvalg_id) references kjerne.utvalg deferrable
);

create table kjerne.parti (
  kommune_id smallint not null references kjerne.kommune,
  kode text not null,
  navn text not null,
  -- Lenke til partiets egen side, åpnet og sjekket for hånd (data/partisider.json).
  url text check (url ~ '^https://'),
  url_tekst text,
  url_kontrollert date,
  primary key (kommune_id, kode),
  check ((url is null) = (url_tekst is null))
);

-- Folkevalgte -----------------------------------------------------------------

create table kjerne.person (
  id bigint generated always as identity primary key,
  kommune_id smallint not null references kjerne.kommune,
  navn text not null check (btrim(navn) <> ''),  -- normalisert (tolk/navn.py)
  slug text not null check (slug ~ '^[a-z0-9-]+$'),
  unique (kommune_id, navn),
  unique (kommune_id, slug),
  unique (kommune_id, id)
);

comment on table kjerne.person is
  'Én rad per person per kommune. Navnet er nøkkelen i protokollene; portal-ID-er står i person_portal_id.';

-- Samme person kan ha flere ID-er i portalen (2160 og 2464 i HPNM).
create table kjerne.person_portal_id (
  kommune_id smallint not null,
  portal_person_id int not null,
  person_id bigint not null,
  primary key (kommune_id, portal_person_id),
  foreign key (kommune_id, person_id) references kjerne.person (kommune_id, id) deferrable
);

-- Skrivemåter i protokollene som er samme person (tolk/navn.VARIANTER).
create table kjerne.navnevariant (
  kommune_id smallint not null,
  variant text not null,
  person_id bigint not null,
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  primary key (kommune_id, variant),
  foreign key (kommune_id, person_id) references kjerne.person (kommune_id, id) deferrable
);

-- Møter, saker og saksgang ------------------------------------------------------

create table kjerne.mote (
  kommune_id smallint not null,
  mote_id int not null,
  utvalg_id int not null,
  utvalg text not null,  -- kortnavnet slik møtet oppgir det
  utvalg_navn text not null,
  dato timestamp(0) not null,
  slutt text not null check (slutt ~ '^([0-9]{2}:[0-9]{2})?$'),  -- tom når ukjent
  sted text,
  rom text,
  antall_saker smallint not null check (antall_saker >= 0),
  url text not null,
  primary key (kommune_id, mote_id),
  foreign key (kommune_id, utvalg_id) references kjerne.utvalg deferrable
);

create table kjerne.sak (
  kommune_id smallint not null references kjerne.kommune,
  -- Laveste hentede behandlings-ID i kjeden. Kan endres når et eldre år
  -- hentes; derfor ON UPDATE CASCADE overalt den brukes.
  sak_id int not null,
  aar smallint not null,
  rekkefolge int not null,  -- rekkefølgen i data/saker/<år>.json
  tittel text not null,
  skjermet_tittel boolean not null,
  sakstype text not null check (sakstype in ('PS', 'RS', 'OS', 'FO')),
  formalia boolean not null,
  status text not null check (status in (
    'Til behandling', 'Til kommunestyret', 'Venter på protokoll',
    'Protokoll ikke publisert', 'Behandlet', 'Vedtatt i kommunestyret',
    'Unntatt offentlighet')),
  til_kommunestyret boolean not null,
  primary key (kommune_id, sak_id),
  unique (kommune_id, aar, rekkefolge) deferrable,
  check (not skjermet_tittel or tittel = '(Unntatt offentlighet)')
);

create table kjerne.saksgang_steg (
  kommune_id smallint not null,
  behandling_id int not null,
  sak_id int not null,
  rekkefolge smallint not null,
  -- hentet er usann for behandlinger i år som ikke er hentet. De peker til
  -- møter som ikke finnes i tabellen, så fremmednøkkelen gjelder bare hentede.
  hentet boolean not null,
  mote_id int,
  mote_hentet int generated always as (case when hentet then mote_id end) stored,
  dato timestamp(0),
  utvalg text,
  utvalg_navn text,
  saksnr text not null,
  protokoll_publisert boolean not null,
  protokoll_skjermet boolean not null,
  url_mote text,
  url_vedtak text,
  primary key (kommune_id, behandling_id),
  unique (kommune_id, sak_id, rekkefolge) deferrable,
  foreign key (kommune_id, sak_id) references kjerne.sak on update cascade on delete cascade deferrable,
  foreign key (kommune_id, mote_hentet) references kjerne.mote (kommune_id, mote_id) deferrable,
  check (not hentet or mote_id is not null),
  -- CLAUDE.md regel 3: et skjermet vedtak har ingen lenke.
  check (not protokoll_skjermet or url_vedtak is null)
);

-- Dokumenter og tekst ----------------------------------------------------------

-- Tre ID-rom i portalen, som ikke må blandes (lager/tekst.py):
--   dokument      saksframlegg og vedlegg, etter DocumentDescription.Id
--   behandling    saksprotokollen, etter behandlings-ID
--   motedokument  møteprotokoll og møteinnkalling, etter MeetingDocuments.Id
-- Skjermede dokumenter blir aldri rader her.
create table kjerne.dokument (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  id_rom text not null check (id_rom in ('dokument', 'behandling', 'motedokument')),
  portal_id int not null,
  slag text not null check (slag in (
    'saksframlegg', 'vedlegg', 'saksprotokoll', 'moteprotokoll', 'moteinnkalling')),
  tittel text,
  format text,
  url text not null,
  sak_id int,
  behandling_id int,
  mote_id int,
  rekkefolge smallint,
  unique (kommune_id, id_rom, portal_id),
  unique (kommune_id, id),
  check ((id_rom = 'dokument') = (slag in ('saksframlegg', 'vedlegg'))),
  check ((id_rom = 'behandling') = (slag = 'saksprotokoll')),
  check ((id_rom = 'motedokument') = (slag in ('moteprotokoll', 'moteinnkalling'))),
  check (slag not in ('saksframlegg', 'vedlegg') or sak_id is not null),
  check (slag <> 'saksprotokoll' or behandling_id = portal_id),
  check (slag not in ('moteprotokoll', 'moteinnkalling') or mote_id is not null),
  foreign key (kommune_id, sak_id) references kjerne.sak on update cascade on delete cascade deferrable,
  foreign key (kommune_id, behandling_id) references kjerne.saksgang_steg on delete cascade deferrable,
  foreign key (kommune_id, mote_id) references kjerne.mote on delete cascade deferrable
);

create unique index dokument_ett_saksframlegg on kjerne.dokument (kommune_id, sak_id)
  where slag = 'saksframlegg';
create unique index dokument_en_moteprotokoll on kjerne.dokument (kommune_id, mote_id)
  where slag = 'moteprotokoll';

-- Teksten forsvinner med dokumentet: blir et dokument skjermet i portalen,
-- fjernes raden, og teksten med den (CLAUDE.md regel 3).
create table kjerne.dokument_tekst (
  kommune_id smallint not null,
  dokument_id bigint not null,
  tekst text not null check (length(tekst) > 0),
  hentet timestamptz not null default now(),
  kjoring_id text,
  primary key (kommune_id, dokument_id),
  foreign key (kommune_id, dokument_id) references kjerne.dokument (kommune_id, id)
    on delete cascade deferrable
);

-- Voteringer og stemmer --------------------------------------------------------

-- Ett vedtak som er lest, også når det ikke har voteringer.
create table kjerne.vedtak_tolket (
  kommune_id smallint not null,
  behandling_id int not null,
  primary key (kommune_id, behandling_id),
  foreign key (kommune_id, behandling_id) references kjerne.saksgang_steg on delete cascade deferrable
);

create table kjerne.votering (
  kommune_id smallint not null,
  behandling_id int not null,
  nr smallint not null check (nr >= 1),
  type text not null check (type in (
    'innstilling', 'tilleggsforslag', 'forslag', 'enstemmig',
    'alternative forslag', 'endringsforslag')),
  tekst text,
  resultat text not null check (resultat in ('vedtatt', 'falt')),
  resultat_tekst text,
  enstemmig boolean not null,
  antall_for smallint check (antall_for >= 0),
  antall_mot smallint not null check (antall_mot >= 0),
  -- «Ikke til stede (n)» leses i dag uten å lagres; null til tolkningen gjør det.
  antall_ikke_til_stede smallint check (antall_ikke_til_stede >= 0),
  forslagsstiller text,
  parti text,
  dobbeltstemme text check (dobbeltstemme in ('ordfører', 'leder')),
  -- Satt av tolk/ etter tellekontrollen (CLAUDE.md regel 2). Databasen
  -- kontrollerer det igjen: se kjerne.kontroller_stemmetall.
  tall_stemmer boolean not null,
  -- Hvor mye protokollen oppgir. Kommuner skriver ulikt; bare navneliste
  -- har stemme-rader.
  detaljniva text not null default 'navneliste'
    check (detaljniva in ('navneliste', 'bare_tall', 'bare_resultat')),
  tolket_med text,
  primary key (kommune_id, behandling_id, nr),
  foreign key (kommune_id, behandling_id) references kjerne.vedtak_tolket on delete cascade deferrable,
  check (enstemmig = (type = 'enstemmig')),
  check (not enstemmig or (antall_for is null and antall_mot = 0)),
  check (enstemmig or antall_for is not null)
);

create table kjerne.votering_alternativ (
  kommune_id smallint not null,
  behandling_id int not null,
  nr smallint not null,
  forslag text not null,
  antall smallint not null check (antall >= 0),
  rekkefolge smallint not null,
  primary key (kommune_id, behandling_id, nr, forslag),
  foreign key (kommune_id, behandling_id, nr) references kjerne.votering
    on update cascade on delete cascade deferrable
);

create table kjerne.stemme (
  kommune_id smallint not null,
  behandling_id int not null,
  nr smallint not null,
  person_id bigint not null,
  valg text not null check (valg in ('for', 'mot', 'ikke_til_stede', 'alternativ')),
  alternativ_forslag text,
  parti text,  -- partiet slik protokollen oppgir det i voteringen
  rekkefolge smallint not null,  -- rekkefølgen i navnelisten
  -- Én person stemmer én gang per votering.
  primary key (kommune_id, behandling_id, nr, person_id),
  foreign key (kommune_id, behandling_id, nr) references kjerne.votering
    on update cascade on delete cascade deferrable,
  foreign key (kommune_id, person_id) references kjerne.person (kommune_id, id) deferrable,
  foreign key (kommune_id, behandling_id, nr, alternativ_forslag)
    references kjerne.votering_alternativ on update cascade on delete cascade deferrable,
  check ((valg = 'alternativ') = (alternativ_forslag is not null)),
  check ((valg = 'ikke_til_stede') = (parti is null))
);

create index stemme_person on kjerne.stemme (kommune_id, person_id);

-- Oppmøte og verv ----------------------------------------------------------------

create table kjerne.oppmote_mote (
  kommune_id smallint not null,
  mote_id int not null,
  ikke_tolket text[] not null default '{}',
  tolket_med text,
  primary key (kommune_id, mote_id),
  foreign key (kommune_id, mote_id) references kjerne.mote on delete cascade deferrable
);

create table kjerne.oppmote (
  kommune_id smallint not null,
  mote_id int not null,
  person_id bigint not null,
  rekkefolge smallint not null,
  funksjon text not null check (funksjon in ('Leder', 'Nestleder', 'Medlem', 'Varamedlem')),
  repr text,  -- parti, eller kommunen i interkommunale utvalg
  vara_for_person_id bigint,
  primary key (kommune_id, mote_id, person_id),
  unique (kommune_id, mote_id, rekkefolge) deferrable,
  foreign key (kommune_id, mote_id) references kjerne.oppmote_mote on delete cascade deferrable,
  foreign key (kommune_id, person_id) references kjerne.person (kommune_id, id) deferrable,
  foreign key (kommune_id, vara_for_person_id) references kjerne.person (kommune_id, id) deferrable
);

-- Stemmer som ikke stemmer med oppmøtet (tolk/bygg_oppmote.py).
create table kjerne.oppmote_avvik (
  kommune_id smallint not null,
  mote_id int not null,
  rekkefolge smallint not null,
  behandling_id int not null,
  votering_nr smallint not null,
  type text not null check (type in ('stemte_uten_oppmote', 'flere_stemmer_enn_frammotte')),
  navn text[],
  stemmer smallint,
  frammotte smallint,
  primary key (kommune_id, mote_id, rekkefolge),
  foreign key (kommune_id, mote_id) references kjerne.oppmote_mote on delete cascade deferrable,
  check ((type = 'stemte_uten_oppmote') = (navn is not null)),
  check ((type = 'flere_stemmer_enn_frammotte')
         = (stemmer is not null and frammotte is not null and stemmer > frammotte))
);

create table kjerne.verv (
  kommune_id smallint not null,
  aar smallint not null,
  utvalg_id int not null,
  person_id bigint not null,
  rolle text check (rolle in ('Leder', 'Nestleder', 'Medlem', 'Varamedlem')),
  repr text,
  portal_person_id int,
  i_dagens_liste boolean not null,
  i_medlemslister date[] not null default '{}',
  forst_motte date,
  sist_motte date,
  moter_som jsonb not null default '{}' check (jsonb_typeof(moter_som) = 'object'),
  motte_for text[] not null default '{}',
  primary key (kommune_id, aar, utvalg_id, person_id),
  foreign key (kommune_id, utvalg_id) references kjerne.utvalg deferrable,
  foreign key (kommune_id, person_id) references kjerne.person (kommune_id, id) deferrable,
  check (forst_motte <= sist_motte)
);

-- Avvik og vurderinger (ADR-015) -----------------------------------------------

-- Avvik slettes aldri. Forsvinner det fra protokollen, settes aktiv = false,
-- så en vurdering av det fortsatt peker på noe.
create table kjerne.avvik (
  kommune_id smallint not null references kjerne.kommune,
  avvik text not null,
  type text not null check (type in ('oppmote', 'antall', 'tall')),
  utvalg text,
  dato date not null,
  beskrivelse text not null,
  kilde text,
  aktiv boolean not null default true,
  primary key (kommune_id, avvik),
  check (split_part(avvik, ':', 1) = type),
  check (avvik ~ '^(oppmote:[0-9]+:[a-z0-9-]+|antall:[0-9]+:[0-9]+|tall:[0-9]+:[0-9]+)$')
);

create table kjerne.avvik_votering (
  kommune_id smallint not null,
  avvik text not null,
  behandling_id int not null,
  nr smallint not null,
  rekkefolge smallint not null,
  primary key (kommune_id, avvik, behandling_id, nr),
  foreign key (kommune_id, avvik) references kjerne.avvik on delete cascade deferrable,
  foreign key (kommune_id, behandling_id, nr) references kjerne.votering
    on update cascade on delete cascade deferrable
);

-- Bare innsetting: en ny vurdering av samme avvik er en ny rad, og den
-- nyeste gjelder (kjerne.vurdering_gjeldende).
create table kjerne.vurdering (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  avvik text not null,
  avgjorelse text not null check (avgjorelse in ('publiser', 'ikke_publiser', 'venter_paa_kommunen')),
  merknad text,
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  vurdert_av text not null check (btrim(vurdert_av) <> ''),
  dato date not null,
  registrert timestamptz not null default now(),
  registrert_av uuid,
  foreign key (kommune_id, avvik) references kjerne.avvik deferrable
);

create view kjerne.vurdering_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, avvik) *
  from kjerne.vurdering
  order by kommune_id, avvik, dato desc, id desc;

-- Analyse ------------------------------------------------------------------------

-- Taggene modellen kan velge mellom (analyser/analyser_saker.TAGGER). Felles
-- for alle kommunene.
create table kjerne.tagg (
  tagg text primary key,
  aktiv boolean not null default true
);

-- Bare innsetting: en ny analyse av samme sak er en ny rad.
create table kjerne.analyse (
  id bigint generated always as identity primary key,
  kommune_id smallint not null,
  sak_id int not null,
  tittel_klarsprak text not null check (btrim(tittel_klarsprak) <> ''),
  sammendrag text not null,
  betydning text not null,
  tagger text[] not null check (cardinality(tagger) between 1 and 3),
  utfall text not null check (utfall in (
    'vedtatt', 'falt', 'utsatt', 'venter på protokoll', 'ikke avgjort ennå')),
  uenighet text not null,
  usikker boolean not null,
  sjekksum text not null,
  modell text not null,
  innsats text not null,
  instruksjon_versjon smallint not null,
  dato date not null,
  tokens_inn int not null default 0 check (tokens_inn >= 0),
  tokens_ut int not null default 0 check (tokens_ut >= 0),
  -- CLAUDE.md regel 5: uten kildelenke publiseres det ikke.
  kilder jsonb not null check (jsonb_typeof(kilder) = 'array' and jsonb_array_length(kilder) >= 1),
  opprettet timestamptz not null default now(),
  kjoring_id text,
  unique (kommune_id, id),
  foreign key (kommune_id, sak_id) references kjerne.sak on update cascade deferrable,
  check (usikker or btrim(sammendrag) <> '')
);

create index analyse_siste on kjerne.analyse (kommune_id, sak_id, opprettet desc, id desc);

create view kjerne.analyse_gjeldende with (security_invoker = on) as
  select distinct on (kommune_id, sak_id) *
  from kjerne.analyse
  order by kommune_id, sak_id, opprettet desc, id desc;

-- Resultatet av kontrollen av et sammendrag mot kilden (tester/kontroller.py,
-- sammendrag_avvik). Kjøres ved hvert bygg, fordi listen over navn som kan
-- stå i et sammendrag, endres.
create table kjerne.analyse_kontroll (
  kommune_id smallint not null,
  analyse_id bigint not null,
  kontrollert timestamptz not null default now(),
  bestatt boolean not null,
  grunner text[] not null default '{}',
  kjoring_id text,
  primary key (kommune_id, analyse_id, kontrollert),
  foreign key (kommune_id, analyse_id) references kjerne.analyse (kommune_id, id) deferrable,
  check (bestatt = (cardinality(grunner) = 0))
);

-- Navn fra sakstitler som er vurdert og kan stå i et sammendrag.
create table kjerne.tillatt_navn (
  kommune_id smallint not null,
  navn text not null,
  sak_id int not null,
  begrunnelse text not null check (btrim(begrunnelse) <> ''),
  vurdert date not null,
  registrert_av uuid,
  primary key (kommune_id, navn, sak_id),
  foreign key (kommune_id, sak_id) references kjerne.sak on update cascade deferrable
);
