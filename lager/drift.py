"""Kjøreloggen: tall fra hver kjøring (drift.logg)."""

from __future__ import annotations

from . import _fil

KJORINGER = _fil.DATA / "drift" / "kjoringer.json"


def kjoringer() -> dict:
    return _fil.les(KJORINGER, {})


def lagre_kjoringer(logg: dict) -> None:
    _fil.skriv(KJORINGER, logg, sorter=False)
