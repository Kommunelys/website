"""Saker med saksgang, og møtene. Skrives av tolk.bygg_saker."""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

SAKER = _fil.DATA / "saker"
MOTER = _fil.DATA / "moter"


def les(aar: int, *standard):
    """Sakene for året. Med `standard` gis den tilbake hvis de mangler."""
    if fra_databasen():
        return pg.saker(aar, *standard)
    return _fil.les(SAKER / f"{aar}.json", *standard)


def lagre(aar: int, saker: list[dict]) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.saker(c, k, aar, saker))
    _fil.skriv(SAKER / f"{aar}.json", saker)


def les_moter(aar: int, *standard):
    if fra_databasen():
        return pg.moter(aar, *standard)
    return _fil.les(MOTER / f"{aar}.json", *standard)


def lagre_moter(aar: int, moter: list[dict]) -> None:
    if fra_databasen():
        raa_moter, moteliste = pg.moter_raa(aar) or [], pg.moteliste(aar) or []
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.moter(c, k, aar, moter, raa_moter, moteliste))
    _fil.skriv(MOTER / f"{aar}.json", moter)
