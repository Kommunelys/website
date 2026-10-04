"""Rå svar fra portalen: møtelisten, hvert møte og medlemslistene.

ADR-001: lagres urørt og slettes aldri, slik at tolkningen kan kjøres på nytt.
Unntak: medlemslistene lagres uten kontaktopplysninger (ADR-014).
"""

from __future__ import annotations

from . import _fil

RAA = _fil.DATA / "raa"
MEDLEMMER = RAA / "medlemmer"


def moteliste(aar: int) -> list[dict] | None:
    """Møtelisten slik den var ved forrige henting, eller None."""
    return _fil.les(RAA / str(aar) / "moter.json", None)


def lagre_moteliste(aar: int, liste: list[dict]) -> None:
    _fil.skriv(RAA / str(aar) / "moter.json", liste)


def moter(aar: int) -> list[dict] | None:
    """Alle hentede møter for året, {mote, detaljer, behandlinger}.

    I fast rekkefølge (etter filnavn). None hvis året ikke er hentet.
    """
    mappe = RAA / str(aar) / "moter"
    if not mappe.exists():
        return None
    return [_fil.les(sti) for sti in sorted(mappe.glob("*.json"))]


def lagre_mote(aar: int, mote_id: int, innhold: dict) -> None:
    _fil.skriv(RAA / str(aar) / "moter" / f"{mote_id}.json", innhold)


def lagre_siste_kjoring(aar: int, oppsummering: dict) -> None:
    _fil.skriv(RAA / str(aar) / "siste-kjoring.json", oppsummering)


def medlemslister() -> list[dict]:
    """Alle lagrede versjoner av medlemslistene, eldste først."""
    return [_fil.les(sti) for sti in sorted(MEDLEMMER.glob("*.json"))]


def lagre_medlemsliste(dato: str, innhold: dict) -> None:
    _fil.skriv(MEDLEMMER / f"{dato}.json", innhold)
