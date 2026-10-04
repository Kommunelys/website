"""Utvalg, partier og verv. Skrives av tolk.bygg_verv."""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

VERV = _fil.DATA / "verv"
UTVALG = _fil.DATA / "utvalg"


def les(aar: int, *standard):
    if fra_databasen():
        return pg.verv(aar, *standard)
    return _fil.les(VERV / f"{aar}.json", *standard)


def alle_aar() -> list[dict]:
    """Vervene for alle år, eldste år først."""
    if fra_databasen():
        return pg.verv_alle_aar()
    return [v for sti in sorted(VERV.glob("*.json")) for v in _fil.les(sti)]


def lagre(aar: int, verv: list[dict]) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(
            lambda c, k: pg_skriv.verv(c, k, aar, pg_skriv.Personer(c, k), verv))
    _fil.skriv(VERV / f"{aar}.json", verv)


def les_utvalg(aar: int, *standard):
    if fra_databasen():
        return pg.utvalg(aar, *standard)
    return _fil.les(UTVALG / f"{aar}.json", *standard)


def lagre_utvalg(aar: int, utvalg: dict) -> None:
    if fra_databasen():
        from . import konfig  # noqa: PLC0415

        partisider = konfig.partisider()
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.utvalg(c, k, aar, utvalg, partisider))
    _fil.skriv(UTVALG / f"{aar}.json", utvalg)
