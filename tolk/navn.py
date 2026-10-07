"""Normalisering av representantnavn.

Samme person skrives ulikt i samme dokument. Observert i protokollen fra
16.09.2026: «Tor Andre Eide» og «Tor André Eide», «Line M Nordkvelle» og
«Line Mari Nordkvelle».

Varianter legges inn i kommunens profil, ikke i koden som bruker dem.
"""

from __future__ import annotations

import re

from .profil import profil

# Variantene og partikodene står i kommunens profil (tolk/profil.py):
# partikodene i standarden for Elements, variantene og lokale partier i
# kommuner/<slug>.json under «tolk».

NAVN_MED_PARTI = re.compile(r"^(.+?)\s*\(([A-ZÆØÅ]+)\)$")


def normaliser(navn: str) -> str:
    """Rydd mellomrom og slå sammen kjente varianter."""
    n = re.sub(r"\s+", " ", navn).strip().strip(",.")
    return profil().navnevarianter.get(n, n)


def partikode(parti: str | None) -> str | None:
    """«Senterpartiet» -> «SP». Ukjente navn og koder returneres uendret."""
    if parti is None:
        return None
    p = re.sub(r"\s+", " ", parti).strip()
    return profil().partikoder.get(p, p)


def del_navn_og_parti(tekst: str) -> tuple[str, str] | None:
    """«Gunnar Thorsen (AP)» -> ('Gunnar Thorsen', 'AP').

    Returnerer None hvis strengen ikke har formen navn (PARTI).
    """
    m = NAVN_MED_PARTI.match(re.sub(r"\s+", " ", tekst).strip())
    if not m:
        return None
    return normaliser(m.group(1)), m.group(2)
