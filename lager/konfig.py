"""Det som vedlikeholdes for hånd eller måles, og ikke hører til én tabell.

Partisidene og de tillatte navnene er filer i git også når resten ligger i
databasen: de endres for hånd og gjennomgås i en PR. lager.synk --konfig
speiler dem inn i databasen. Målingen er et verktøy som kjøres for hånd og
skrives alltid til fil.

- partisider: lenker til partienes egne sider, kontrollert for hånd
- tillatte navn: navn fra sakstitler som er vurdert og kan stå i et sammendrag
- forrige telling: antall saker ved forrige kontroll, for å oppdage fall
- måling: størrelse, sidetall og tekstlag per dokument (hent_dokumenter --mal)
"""

from __future__ import annotations

from . import _fil, fra_databasen, pg, pg_skriv


def partisider() -> dict:
    return _fil.les(_fil.DATA / "partisider.json", {})


def tillatte_navn() -> list[dict]:
    return _fil.les(_fil.DATA / "tillatte-navn.json", [])


def forrige_telling() -> dict[str, int]:
    if fra_databasen():
        return pg.forrige_telling()
    return _fil.les(_fil.DATA / "forrige-telling.json", {})


def lagre_forrige_telling(telling: dict[str, int]) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.forrige_telling(c, k, telling))
    _fil.skriv(_fil.DATA / "forrige-telling.json", telling, sorter=False)


def lagre_maling(aar: int, maling: list[dict]) -> None:
    _fil.skriv(_fil.DATA / f"maling-{aar}.json", maling, sorter=False)
