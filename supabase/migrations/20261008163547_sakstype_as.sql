-- Sakstypen «AS»: Arbeidsmiljøutvalget i Levanger har sin egen saksserie
-- (AS 2/2026). Den behandles som de andre sakene som ikke er PS: vises, men
-- telles ikke som politiske og analyseres ikke.

alter table kjerne.sak drop constraint sak_sakstype_check;
alter table kjerne.sak add constraint sak_sakstype_check
  check (sakstype in ('PS', 'RS', 'OS', 'FO', 'AS'));
