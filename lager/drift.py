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


def lagre_skjermet(filer: dict[str, str]) -> None:
    """Dataene til nettstedet for kommunen, når den har begrenset innsyn
    (ADR-024): {sti: innhold}. Med filene lagres de ikke."""
    if fra_databasen():
        pg_skriv.i_transaksjon(lambda c, k: pg_skriv.nettsted_filer(c, k, filer))


def rydd_skjermet(begrensede: list[str]) -> None:
    """Fjerner dataene for kommunene som ikke lenger har begrenset innsyn."""
    if fra_databasen():
        n = pg_skriv.i_transaksjon(lambda c, k: pg_skriv.nettsted_filer_rydd(c, begrensede))
        if n:
            print(f"fjernet {n} filer for kommuner uten begrenset innsyn")


def lagre_kjoringer(logg: dict) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.kjoringer(c, k, logg))
    _fil.skriv(KJORINGER, logg, sorter=False)
