-- Levanger kommune, med begrenset innsyn (ADR-021, ADR-024).
--
-- Står på forsiden og kartet; innholdet vises for dem med en rolle for
-- kommunen. Kilden er lik kommuner/levanger.json (tester.kontroller).
-- Dekningen i 2026 ved innleggingen: 98 % av voteringene, 100 % av oppmøtet.

insert into kjerne.kommune (kommunenr, slug, navn, kilde_type, kilde_konfig, status)
values ('5037', 'levanger', 'Levanger', 'elements',
        '{"basis": "https://prod01.elementscloud.no/publikum/", "tenant": "938587051_PROD-938587051", "database": "a9fd78f2-e95a-4e1c-a907-2a79aac185b0"}',
        'begrenset');
