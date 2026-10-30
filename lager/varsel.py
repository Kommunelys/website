"""Følg saken (ADR-027): det som er publisert i sakene, følgingene og køen.

Bare i databasen. Med KOMMUNELYS_LAGER=json lagres ingenting, og det finnes
ingen følginger, så bygget mot filene virker som før.
"""

from __future__ import annotations

from . import fra_databasen, kjoring_id, pg, pg_skriv


def lagre_tilstander(tilstander: dict[int, dict]) -> None:
    """Fra bygget, for kommunen det bygger: {sak_id: tilstand}."""
    if fra_databasen():
        pg_skriv.i_transaksjon(lambda c, k: pg_skriv.sak_tilstander(c, k, tilstander))


def folgere() -> list[dict]:
    return pg.folger_til_varsel() if fra_databasen() else []


def lagre_ko(ko: list[dict], tilstander: dict[int, dict], tall: dict) -> None:
    """Køen, den nye tilstanden på følgingene og tallene for kjøringen, i én
    transaksjon: et varsel legges i køen nøyaktig én gang."""
    if not fra_databasen():
        return
    from . import db  # noqa: PLC0415

    with db.transaksjon(kjoring_id()) as c:
        pg_skriv.legg_i_ko(c, ko)
        pg_skriv.folger_tilstand(c, tilstander)
        pg_skriv.kjoring_tall(c, None, kjoring_id(), "varsel", tall)


def lagre_tall(tall: dict) -> None:
    """Tallene fra sendingen, i samme del av kjøringen."""
    if not fra_databasen():
        return
    from . import db  # noqa: PLC0415

    with db.transaksjon(kjoring_id()) as c:
        pg_skriv.kjoring_tall(c, None, kjoring_id(), "varsel", tall)


def tall() -> dict | None:
    """Telleren på driftssiden, eller None uten database."""
    return pg.varsel_tall() if fra_databasen() else None
