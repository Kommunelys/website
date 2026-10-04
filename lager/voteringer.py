"""Voteringer og stemmer per behandling. Skrives av tolk.bygg_voteringer."""

from __future__ import annotations

from . import _fil, fra_databasen, pg

VOTERINGER = _fil.DATA / "voteringer"


def les(aar: int, *standard):
    if fra_databasen():
        return pg.voteringer(aar, *standard)
    return _fil.les(VOTERINGER / f"{aar}.json", *standard)


def lagre(aar: int, poster: list[dict]) -> None:
    _fil.skriv(VOTERINGER / f"{aar}.json", poster)
