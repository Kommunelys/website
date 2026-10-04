"""Avvik som må vurderes, og vurderingene av dem (ADR-015).

Avvikene skrives av tolk.bygg_avvik. Vurderingene skrives for hånd, eller av
en modell, i data/vurderinger.json.
"""

from __future__ import annotations

from . import _fil

AVVIK = _fil.DATA / "avvik"
VURDERINGER = _fil.DATA / "vurderinger.json"


def lagre(aar: int, avvik: list[dict]) -> None:
    _fil.skriv(AVVIK / f"{aar}.json", avvik)


def vurderinger() -> list[dict]:
    """Alle vurderingene, slik de står i filen."""
    return _fil.les(VURDERINGER, [])
