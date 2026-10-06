"""Avvik som må vurderes, og vurderingene av dem (ADR-015).

Avvikene skrives av tolk.bygg_avvik. Vurderingene registreres i portalen eller
med python -m lager.vurder, og ligger i databasen (ADR-020). data/vurderinger.json
står som den var 6.10.2026.
"""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

AVVIK = _fil.DATA / "avvik"
VURDERINGER = _fil.DATA / "vurderinger.json"


def les(aar: int, *standard):
    if fra_databasen():
        return pg.avvik(aar, *standard)
    return _fil.les(AVVIK / f"{aar}.json", *standard)


def lagre(aar: int, avvik: list[dict]) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.avvik(c, k, aar, avvik))
    _fil.skriv(AVVIK / f"{aar}.json", avvik)


def vurderinger() -> list[dict]:
    """Gjeldende vurdering for hvert avvik."""
    if fra_databasen():
        return pg.vurderinger()
    return _fil.les(VURDERINGER, [])
