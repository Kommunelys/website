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

from . import _fil, fra_databasen, pg, pg_skriv

TEKST = _fil.DATA / "tekst"
ID_ROM = ("dokument", "behandling", "mote")


def _sti(id_rom: str, ident: int) -> Path:
    if id_rom not in ID_ROM:
        raise ValueError(f"ukjent ID-rom {id_rom!r}")
    if id_rom == "mote":
        return TEKST / "moter" / f"{ident}.txt"
    return TEKST / f"{ident}.txt"


def har(id_rom: str, ident: int) -> bool:
    if fra_databasen():
        return (id_rom, ident) in pg.tekst_avtrykk()
    return _sti(id_rom, ident).exists()


def les(id_rom: str, ident: int | None) -> str | None:
    """Teksten, eller None hvis vi ikke har den."""
    if fra_databasen():
        return pg.tekst(id_rom, ident)
    if not ident:
        return None
    sti = _sti(id_rom, ident)
    return sti.read_text(encoding="utf-8") if sti.exists() else None


def lagre(id_rom: str, ident: int, tekst: str) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.tekst_en(c, k, id_rom, ident, tekst))
    sti = _sti(id_rom, ident)
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(tekst, encoding="utf-8")


def avtrykk() -> dict[tuple[str, int], str] | None:
    """md5 av hver tekst i databasen, uten å hente teksten. None for filene,
    der det er like raskt å lese teksten."""
    return pg.tekst_avtrykk() if fra_databasen() else None


def forhandslast(nokler) -> None:
    """Henter mange tekster i ett kall fra databasen. Ingenting å gjøre for filene."""
    if fra_databasen():
        pg.forhandslast(nokler)
