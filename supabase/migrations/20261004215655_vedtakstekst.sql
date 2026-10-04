-- Det endelige vedtaket slik saksprotokollen skriver det
-- (tolk.tolk_protokoll.les_vedtakstekst). Tom når protokollen ikke har en
-- linje «Vedtak».
alter table kjerne.vedtak_tolket add column vedtak text check (vedtak is null or btrim(vedtak) <> '');
