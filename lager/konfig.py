"""Det som vedlikeholdes for hånd eller måles, og ikke hører til én tabell.

- partisider: lenker til partienes egne sider, kontrollert for hånd
- tillatte navn: navn fra sakstitler som er vurdert og kan stå i et sammendrag
- forrige telling: antall saker ved forrige kontroll, for å oppdage fall
- måling: størrelse, sidetall og tekstlag per dokument (hent_dokumenter --mal)
"""

from __future__ import annotations

from . import _fil


def partisider() -> dict:
    return _fil.les(_fil.DATA / "partisider.json", {})


def tillatte_navn() -> list[dict]:
    return _fil.les(_fil.DATA / "tillatte-navn.json", [])


def forrige_telling() -> dict[str, int]:
    return _fil.les(_fil.DATA / "forrige-telling.json", {})


def lagre_forrige_telling(telling: dict[str, int]) -> None:
    _fil.skriv(_fil.DATA / "forrige-telling.json", telling, sorter=False)


def lagre_maling(aar: int, maling: list[dict]) -> None:
    _fil.skriv(_fil.DATA / f"maling-{aar}.json", maling, sorter=False)
