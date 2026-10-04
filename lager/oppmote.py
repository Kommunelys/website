"""Oppmøte per møte, med avvik mot stemmene. Skrives av tolk.bygg_oppmote."""

from __future__ import annotations

from . import _fil

OPPMOTE = _fil.DATA / "oppmote"


def les(aar: int, *standard):
    return _fil.les(OPPMOTE / f"{aar}.json", *standard)


def lagre(aar: int, moter: list[dict]) -> None:
    _fil.skriv(OPPMOTE / f"{aar}.json", moter)
