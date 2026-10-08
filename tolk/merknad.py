"""Kontroll av merknadene som vises på nettstedet (ADR-023).

Den som vurderer et avvik, et sammendrag eller en melding om feil, kan skrive
en kort merknad. Den vises ved neste kjøring uten at noen godkjenner teksten
for hånd (prosjekteier, 8.10.2026). Derfor kontrolleres den her: kort, uten
lenker og uten navn på folkevalgte eller privatpersoner (CLAUDE.md regel 6).
En merknad som ikke består, gjør at saken holdes tilbake som om vurderingen
ikke fantes.

Databasen stopper for lange merknader og lenker allerede (kjerne.merknad_ok).
Navnene kan bare kontrolleres her, mot listene kjeden har.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

MAKS = 300
LENKE = re.compile(r"https?://|www\.", re.I)


def merknad_avvik(tekst: str | None, navn: Iterable[str]) -> list[str]:
    """Hvorfor merknaden ikke kan vises. Tom liste betyr at den kan."""
    if not tekst or not tekst.strip():
        return []
    ut = []
    if len(tekst) > MAKS:
        ut.append(f"merknaden er lengre enn {MAKS} tegn")
    if LENKE.search(tekst):
        ut.append("merknaden har en lenke")
    for n in sorted(set(navn)):
        if len(n.split()) >= 2 and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", tekst, re.I):
            ut.append(f"merknaden nevner {n!r}")
    return ut
