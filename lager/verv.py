"""Utvalg, partier og verv. Skrives av tolk.bygg_verv."""

from __future__ import annotations

from . import _fil

VERV = _fil.DATA / "verv"
UTVALG = _fil.DATA / "utvalg"


def les(aar: int, *standard):
    return _fil.les(VERV / f"{aar}.json", *standard)


def alle_aar() -> list[dict]:
    """Vervene for alle år, eldste år først."""
    return [v for sti in sorted(VERV.glob("*.json")) for v in _fil.les(sti)]


def lagre(aar: int, verv: list[dict]) -> None:
    _fil.skriv(VERV / f"{aar}.json", verv)


def les_utvalg(aar: int, *standard):
    return _fil.les(UTVALG / f"{aar}.json", *standard)


def lagre_utvalg(aar: int, utvalg: dict) -> None:
    _fil.skriv(UTVALG / f"{aar}.json", utvalg)
