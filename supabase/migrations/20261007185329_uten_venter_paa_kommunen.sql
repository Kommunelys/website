-- Avgjørelsen «venter_paa_kommunen» er fjernet (ADR-015, endret 4.10.2026):
-- tjenesten venter ikke på kommunen, og bygget kjenner bare publiser og
-- ikke_publiser. Vurderinger kan ikke endres eller slettes, så finnes det en
-- rad med verdien, stopper denne migreringen når begrensningen legges til.
alter table kjerne.vurdering
  drop constraint vurdering_avgjorelse_check,
  add constraint vurdering_avgjorelse_check check (avgjorelse in ('publiser', 'ikke_publiser'));
