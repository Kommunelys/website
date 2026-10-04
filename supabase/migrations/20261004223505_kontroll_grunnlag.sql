-- Fingeravtrykk av alt kontrollen av et sammendrag bygger på: kildeteksten,
-- saken, navnene som kan stå i et sammendrag, og koden i tester/kontroller.py.
-- Er grunnlaget uendret, gjelder forrige resultat, og bygget slipper å laste
-- ned kildeteksten på nytt.
alter table kjerne.analyse_kontroll add column grunnlag text;
create index analyse_kontroll_grunnlag on kjerne.analyse_kontroll (kommune_id, analyse_id, grunnlag);
