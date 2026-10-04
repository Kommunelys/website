"""Tekst trukket ut av dokumentene. Skrives av hent.hent_dokumenter.

Tre ID-rom, som ikke må blandes:

- `dokument`: saksframlegg og vedlegg, etter dokument-ID
- `behandling`: saksprotokollen (vedtaket), etter behandlings-ID
- `mote`: møteprotokollen, etter møte-ID

I data/tekst/ deler de to første samme mappe; det er grunnen til at ID-rommet
alltid oppgis.

CLAUDE.md regel 3: skjermet tekst lagres aldri. Det kontrolleres før
`lagre` kalles, og igjen i tester.kontroller.
"""

from __future__ import annotations

from pathlib import Path

from . import _fil

TEKST = _fil.DATA / "tekst"
ID_ROM = ("dokument", "behandling", "mote")


def _sti(id_rom: str, ident: int) -> Path:
    if id_rom not in ID_ROM:
        raise ValueError(f"ukjent ID-rom {id_rom!r}")
    if id_rom == "mote":
        return TEKST / "moter" / f"{ident}.txt"
    return TEKST / f"{ident}.txt"


def har(id_rom: str, ident: int) -> bool:
    return _sti(id_rom, ident).exists()


def les(id_rom: str, ident: int | None) -> str | None:
    """Teksten, eller None hvis vi ikke har den."""
    if not ident:
        return None
    sti = _sti(id_rom, ident)
    return sti.read_text(encoding="utf-8") if sti.exists() else None


def lagre(id_rom: str, ident: int, tekst: str) -> None:
    sti = _sti(id_rom, ident)
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(tekst, encoding="utf-8")
