"""Oppmøte per møte, med avvik mot stemmene. Skrives av tolk.bygg_oppmote."""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

OPPMOTE = _fil.DATA / "oppmote"


def les(aar: int, *standard):
    if fra_databasen():
        return pg.oppmote(aar, *standard)
    return _fil.les(OPPMOTE / f"{aar}.json", *standard)


def lagre(aar: int, moter: list[dict]) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(
            lambda c, k: pg_skriv.oppmote(c, k, aar, pg_skriv.Personer(c, k), moter))
    _fil.skriv(OPPMOTE / f"{aar}.json", moter)
