"""Sammendrag og tagger fra modellen, én per sak. Skrives av analyser.analyser_saker."""

from __future__ import annotations

from . import _fil, fra_databasen, pg

ANALYSE = _fil.DATA / "analyse"


def les(sak_id: int) -> dict | None:
    if fra_databasen():
        return pg.analyse(sak_id)
    return _fil.les(ANALYSE / f"{sak_id}.json", None)


def alle() -> dict[int, dict]:
    """Alle analysene etter sak-ID, i stigende rekkefølge.

    Rekkefølgen er fast, ikke filsystemets, så bygget blir likt overalt.
    """
    if fra_databasen():
        return pg.analyser()
    analyser = [_fil.les(sti) for sti in ANALYSE.glob("*.json")]
    return {a["sak_id"]: a for a in sorted(analyser, key=lambda a: a["sak_id"])}


def lagre(analyse: dict) -> None:
    _fil.skriv(ANALYSE / f"{analyse['sak_id']}.json", analyse, sorter=False)
