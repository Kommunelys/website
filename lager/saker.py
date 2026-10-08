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


def lagre_med_moter(saker: dict[int, list[dict]], moter: dict[int, list[dict]]) -> None:
    """Sakene og møtene for årene, i én transaksjon ({år: [...]}).

    Et steg i saksgangen peker til møtet, og et nytt møte kommer gjerne
    samtidig med sakene som behandles der. Hver for seg stopper den ene på
    at den andre mangler; i én transaksjon kontrolleres det til slutt.
    """
    if fra_databasen():
        raa = {a: (pg.moter_raa(a) or [], pg.moteliste(a) or []) for a in moter}

        def skriv(c, k):
            for a, m in moter.items():
                pg_skriv.moter(c, k, a, m, *raa[a])
            for a, s in saker.items():
                pg_skriv.saker(c, k, a, s)
        return pg_skriv.i_transaksjon(skriv)
    for a, m in moter.items():
        _fil.skriv(MOTER / f"{a}.json", m)
    for a, s in saker.items():
        _fil.skriv(SAKER / f"{a}.json", s)


def les_moter(aar: int, *standard):
    if fra_databasen():
        return pg.moter(aar, *standard)
    return _fil.les(MOTER / f"{aar}.json", *standard)
