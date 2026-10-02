"""Normalisering av representantnavn.

Samme person skrives ulikt i samme dokument. Observert i protokollen fra
16.09.2026: «Tor Andre Eide» og «Tor André Eide», «Line M Nordkvelle» og
«Line Mari Nordkvelle».

Varianter legges inn her, ikke i koden som bruker dem.
"""

from __future__ import annotations

import re

# variant (slik den står i dokumentet) -> normalisert form
VARIANTER: dict[str, str] = {
    "Tor Andre Eide": "Tor André Eide",
    "Line M Nordkvelle": "Line Mari Nordkvelle",
    # Oppmøtelisten og navnelistene i voteringene skriver navnet ulikt, i de
    # samme møtene gjennom hele 2026.
    "Monika Luktvasslimo": "Monika Skoglund Luktvasslimo",
    "Enok Moe": "Enok Askil Moe",
    "Terje Langli": "Terje Bjarte Langli",
}

# Navnelistene i protokollene bruker koder, forslagsstilleren står med fullt
# partinavn: «Tor Borgan (Senterpartiet) fremmet følgende forslag».
PARTIKODER: dict[str, str] = {
    "Arbeiderpartiet": "AP",
    "Fremskrittspartiet": "FRP",
    "Høyre": "H",
    "Industri- og Næringspartiet": "INP",
    "Pensjonistpartiet": "PP",
    "Rødt": "R",
    "Senterpartiet": "SP",
    "Sosialistisk Venstreparti": "SV",
    "Uavhengig": "UAVH",
    "Venstre": "V",
}

NAVN_MED_PARTI = re.compile(r"^(.+?)\s*\(([A-ZÆØÅ]+)\)$")


def normaliser(navn: str) -> str:
    """Rydd mellomrom og slå sammen kjente varianter."""
    n = re.sub(r"\s+", " ", navn).strip().strip(",.")
    return VARIANTER.get(n, n)


def partikode(parti: str | None) -> str | None:
    """«Senterpartiet» -> «SP». Ukjente navn og koder returneres uendret."""
    if parti is None:
        return None
    p = re.sub(r"\s+", " ", parti).strip()
    return PARTIKODER.get(p, p)


def del_navn_og_parti(tekst: str) -> tuple[str, str] | None:
    """«Gunnar Thorsen (AP)» -> ('Gunnar Thorsen', 'AP').

    Returnerer None hvis strengen ikke har formen navn (PARTI).
    """
    m = NAVN_MED_PARTI.match(re.sub(r"\s+", " ", tekst).strip())
    if not m:
        return None
    return normaliser(m.group(1)), m.group(2)
