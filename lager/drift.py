"""Kjøreloggen: tall fra hver kjøring (drift.logg)."""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

KJORINGER = _fil.DATA / "drift" / "kjoringer.json"


def kjoringer() -> dict:
    if fra_databasen():
        return pg.kjoringer()
    return _fil.les(KJORINGER, {})


def lagre_side(html: str) -> None:
    """Driftssiden, som portalen viser (ADR-020). Med filene lagres den ikke."""
    if fra_databasen():
        pg_skriv.i_transaksjon(lambda c, k: pg_skriv.driftsside(c, html))


def lagre_kjoringer(logg: dict) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.kjoringer(c, k, logg))
    _fil.skriv(KJORINGER, logg, sorter=False)
