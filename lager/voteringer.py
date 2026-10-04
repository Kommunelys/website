"""Voteringer og stemmer per behandling. Skrives av tolk.bygg_voteringer."""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

VOTERINGER = _fil.DATA / "voteringer"


def les(aar: int, *standard):
    if fra_databasen():
        return pg.voteringer(aar, *standard)
    return _fil.les(VOTERINGER / f"{aar}.json", *standard)


def lagre(aar: int, poster: list[dict]) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(
            lambda c, k: pg_skriv.voteringer(c, k, aar, pg_skriv.Personer(c, k), poster))
    _fil.skriv(VOTERINGER / f"{aar}.json", poster)
