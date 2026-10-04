-- Kodeverk og den første kommunen.

-- Taggene i analyser/analyser_saker.TAGGER. Endres lista der, må den endres
-- her også, i en ny migrering.
insert into kjerne.tagg (tagg) values
  ('Økonomi'), ('Plan og areal'), ('Landbruk'), ('Skole og barnehage'),
  ('Helse og omsorg'), ('Vei og trafikk'), ('Kultur og idrett'), ('Næring'),
  ('Klima og miljø'), ('Eierskap og selskaper'), ('Folkevalgte'), ('Klager'),
  ('Regionalt samarbeid'), ('Høring'), ('Organisasjon');

-- Steinkjer, med portaloppsettet fra hent/portal.py. Publisert, men ennå
-- ikke avklart med kommunen (ADR-007).
insert into kjerne.kommune (kommunenr, slug, navn, kilde_type, kilde_konfig, status)
values ('5006', 'steinkjer', 'Steinkjer', 'elements',
        '{"basis": "https://prod01.elementscloud.no/publikum/",
          "tenant": "840029212_PROD-840029212",
          "database": "b069d4f5-192a-4fee-be37-dc006441e271"}',
        'publisert');
