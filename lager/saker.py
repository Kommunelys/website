"""Saker med saksgang, og møtene. Skrives av tolk.bygg_saker."""

from __future__ import annotations

from . import _fil, fra_databasen, pg

SAKER = _fil.DATA / "saker"
MOTER = _fil.DATA / "moter"


def les(aar: int, *standard):
    """Sakene for året. Med `standard` gis den tilbake hvis de mangler."""
    if fra_databasen():
        return pg.saker(aar, *standard)
    return _fil.les(SAKER / f"{aar}.json", *standard)


def lagre(aar: int, saker: list[dict]) -> None:
    _fil.skriv(SAKER / f"{aar}.json", saker)


def les_moter(aar: int, *standard):
    if fra_databasen():
        return pg.moter(aar, *standard)
    return _fil.les(MOTER / f"{aar}.json", *standard)


def lagre_moter(aar: int, moter: list[dict]) -> None:
    _fil.skriv(MOTER / f"{aar}.json", moter)
