"""Regelsettet for tolkningen av én kommunes dokumenter.

Profilen bygges i tre lag (ADR-021):

1. tolk/profiler/elements.py: standarden for Elements, fra Steinkjers
   dokumenter i 2026.
2. kommuner/<slug>.json under «tolk»: det som er enkelt å skrive som data.
   Et felt erstatter standarden; «<felt>_tillegg» legger til i en liste eller
   en ordbok. Et mønster skrives som tekst og får samme flagg som i standarden.
3. tolk/profiler/<slug>.py (valgfritt): OVERSTYR = {"FELT": verdi} for det som
   ikke kan skrives som data.

Feltene er navnene i elements.py med små bokstaver: votering, enstemmig,
oppmote_start, formalia, kommunestyre_kode, navnevarianter og så videre.

Stemmetallet kontrolleres likt for alle kommuner (ADR-002); det er ikke en
del av profilen.
"""

from __future__ import annotations

import functools
import importlib
import re
from types import MappingProxyType

from tolk.profiler import elements

FELT = [n for n in vars(elements) if n.isupper()]


class Profil:
    """Feltene fra elements.py, med kommunens endringer. Kan ikke endres."""

    def __init__(self, slug: str, verdier: dict):
        self.slug = slug
        self._verdier = verdier

    def __getattr__(self, navn: str):
        try:
            return self._verdier[navn.upper()]
        except KeyError:
            raise AttributeError(navn) from None


def _som(standard, verdi, felt: str):
    """Gjør en verdi fra JSON om til samme slag som standarden."""
    if isinstance(standard, re.Pattern):
        return re.compile(verdi, standard.flags)
    if felt == "OVERSKRIFTER":
        flagg = standard[0][1].flags
        return tuple((n, re.compile(m, flagg)) for n, m in verdi)
    if isinstance(standard, tuple):
        return tuple(verdi)
    return verdi


def _bygg(slug: str, tolk: dict, overstyr: dict) -> Profil:
    verdier = {n: getattr(elements, n) for n in FELT}
    for nokkel, verdi in tolk.items():
        felt = nokkel.upper()
        if felt.endswith("_TILLEGG"):
            felt = felt.removesuffix("_TILLEGG")
            if felt not in verdier:
                raise SystemExit(f"ukjent felt i profilen for {slug}: {nokkel}")
            gammel = verdier[felt]
            verdier[felt] = ({**gammel, **verdi} if isinstance(gammel, dict)
                             else tuple(gammel) + tuple(verdi))
        elif felt in verdier:
            verdier[felt] = _som(verdier[felt], verdi, felt)
        else:
            raise SystemExit(f"ukjent felt i profilen for {slug}: {nokkel}")
    for felt, verdi in overstyr.items():
        if felt not in verdier:
            raise SystemExit(f"ukjent felt i tolk/profiler/{slug}.py: {felt}")
        verdier[felt] = verdi
    # Ordbøkene skal ikke kunne endres av den som bruker profilen.
    verdier = {n: MappingProxyType(dict(v)) if isinstance(v, dict) else v
               for n, v in verdier.items()}
    return Profil(slug, verdier)


@functools.cache
def _profil(slug: str) -> Profil:
    from lager import kommune  # noqa: PLC0415

    tolk = dict(kommune.oppsett(slug).get("tolk") or {})
    tolk.pop("merknad", None)
    navn = f"tolk.profiler.{slug.replace('-', '_')}"
    try:
        overstyr = dict(getattr(importlib.import_module(navn), "OVERSTYR", {}))
    except ModuleNotFoundError as e:
        if e.name != navn:
            raise
        overstyr = {}
    return _bygg(slug, tolk, overstyr)


def profil(slug: str | None = None) -> Profil:
    """Profilen for kommunen (standard: den aktive, lager.kommune.slug())."""
    if slug is None:
        from lager import kommune  # noqa: PLC0415
        slug = kommune.slug()
    return _profil(slug)
