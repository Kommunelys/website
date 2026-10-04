"""Sammendrag og tagger fra modellen, én per sak. Skrives av analyser.analyser_saker."""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv

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
    if fra_databasen():
        from . import kjoring_id  # noqa: PLC0415

        return pg_skriv.i_transaksjon(
            lambda c, k: pg_skriv.analyser(c, k, {analyse["sak_id"]: analyse}, kjoring_id()))
    _fil.skriv(ANALYSE / f"{analyse['sak_id']}.json", analyse, sorter=False)


def kontroller(grunnlag: dict[int, str]) -> dict[int, list[str]]:
    """Kontrollresultater som alt finnes for samme grunnlag, per sak.

    Bare i databasen (analyse_kontroll). Filene husker ingenting, så der
    kontrolleres alt hver gang.
    """
    return pg.kontroller(grunnlag) if fra_databasen() else {}


def lagre_kontroller(resultater: dict[int, tuple[str, list[str]]]) -> None:
    if fra_databasen():
        pg.lagre_kontroller(resultater)
