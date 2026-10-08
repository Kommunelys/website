"""Hvilken kommune en kjøring gjelder, og oppsettet for den.

Kommunen velges med KOMMUNELYS_KOMMUNE (standard: steinkjer). Hver prosess
gjelder én kommune om gangen; kjor.alle går gjennom dem etter tur, så takten
mot portalen gjelder samlet per vert (ADR-007, ADR-021).

Oppsettet ligger i kommuner/<slug>.json: kilden (adressen, tenant og
databasen i Elements), regelsettet for tolkningen og nivåene for hva som
publiseres. Kilden står også i kjerne.kommune.kilde_konfig, som gjelder når
dataene ligger i databasen; tester.kontroller stopper hvis de er ulike.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path

from . import fra_databasen

ROT = Path(__file__).resolve().parent.parent
KOMMUNER = ROT / "kommuner"
STANDARD = "steinkjer"


def slug() -> str:
    """Kommunen denne prosessen gjelder. Filene i data/ hører til Steinkjer;
    lager/_fil.py stopper en annen kommune som vil lese eller skrive dem."""
    return os.environ.get("KOMMUNELYS_KOMMUNE") or STANDARD


def bruk(ny: str) -> None:
    """Bytt kommune i denne prosessen, og glem det som er husket fra den forrige."""
    from . import pg  # noqa: PLC0415

    os.environ["KOMMUNELYS_KOMMUNE"] = ny
    pg.glem()
    pg._kommune = None
    from hent import portal  # noqa: PLC0415
    portal.bruk(None)


def alle() -> list[str]:
    """Alle kommunene som har en fil i kommuner/."""
    return sorted(f.stem for f in KOMMUNER.glob("*.json"))


@functools.cache
def _les(s: str) -> dict:
    fil = KOMMUNER / f"{s}.json"
    if not fil.exists():
        raise SystemExit(f"fant ikke {fil.relative_to(ROT)}")
    return json.loads(fil.read_text("utf-8"))


def oppsett(s: str | None = None) -> dict:
    """Hele kommuner/<slug>.json, uten merknaden."""
    k = dict(_les(s or slug()))
    k.pop("merknad", None)
    return k


def kilde(s: str | None = None) -> dict:
    """Adressen, tenant og databasen i portalen.

    Fra databasen når dataene ligger der, ellers fra kommuner/<slug>.json.
    """
    s = s or slug()
    if fra_databasen():
        from . import pg  # noqa: PLC0415
        return pg.kilde(s)
    return oppsett(s)["kilde"]


def konfigmappe() -> Path:
    """Mappen med filene som vedlikeholdes for hånd (partisider, tillatte navn).

    Steinkjers ligger i data/ (eller KOMMUNELYS_DATA) som før byttet; de andre
    kommunenes i kommuner/<slug>/.
    """
    from . import _fil  # noqa: PLC0415

    s = slug()
    return _fil.DATA if s == STANDARD else KOMMUNER / s


def fra_argv(argv: list[str]) -> list[str]:
    """Tar «--kommune SLUG» ut av argumentene og setter KOMMUNELYS_KOMMUNE."""
    if "--kommune" not in argv:
        return argv
    i = argv.index("--kommune")
    if i + 1 >= len(argv):
        raise SystemExit("--kommune trenger en kommune, for eksempel --kommune steinkjer")
    os.environ["KOMMUNELYS_KOMMUNE"] = argv[i + 1]
    return argv[:i] + argv[i + 2:]


def aktive() -> list[tuple[str, str]]:
    """Kommunene som hentes og bygges, med status: (slug, «intern», «begrenset» eller «publisert»).

    Status står i kjerne.kommune og endres med en migrering. «intern» bygges og
    kontrolleres, men publiseres ikke; «kartlegging» hentes ikke. «begrenset»
    står på forsiden, men dataene lagres i databasen og vises bare for dem
    med en rolle for kommunen (ADR-024). Uten databasen er det bare Steinkjer,
    publisert.
    """
    if not fra_databasen():
        return [(STANDARD, "publisert")]
    from . import pg  # noqa: PLC0415
    return [(s, st) for s, st in pg._rader(
        "select slug, status from kjerne.kommune where status in ('intern', 'begrenset', 'publisert') order by slug")]


def aarene(til: int, s: str | None = None) -> list[int]:
    """Årene kommunen er hentet for, fra «fra_aar» i kommuner/<slug>.json til og med `til`.

    En sak hører til året den begynte, men kan behandles også senere år
    (ADR-022). Det som kobler saker, voteringer og oppmøte, må derfor lese
    alle årene, ikke bare ett.
    """
    s = s or slug()
    fra = oppsett(s).get("fra_aar")
    if fra is None:
        raise SystemExit(f"kommuner/{s}.json mangler «fra_aar», det første året som hentes")
    return list(range(fra, max(fra, til) + 1))


def alle_aar(les, til: int) -> list:
    """`les(år, [])` for alle årene til og med `til`, slått sammen i rekkefølge."""
    return [x for a in aarene(til) for x in les(a, [])]
