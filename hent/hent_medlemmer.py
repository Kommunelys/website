"""Henter dagens medlemslister for alle utvalg som har møter i året.

ADR-008: portalen gir bare dagens medlemmer, ikke historikk. Listen hentes ved
hver kjøring og lagres versjonert, slik at historikken bygges opp framover. Det
lagres en ny versjon (lager.raa) bare når noe er endret.

Svaret fra portalen har også mobilnummer, e-post og kjønn for hver folkevalgt.
Det lagres ikke: folkevalgte omtales bare i sin rolle (CLAUDE.md regel 6), og
ingen del av tjenesten trenger det. Dette er et bevisst unntak fra at rå svar
lagres urørt (ADR-001); alle felter som tolkes, beholdes.

    python -m hent.hent_medlemmer 2026
"""

from __future__ import annotations

import datetime as dt
import sys

from lager import raa as raadata

from . import portal


def _rydd(m: dict) -> dict:
    """Behold rolle og person-ID, ikke kontaktopplysninger."""
    navn = m.get("UserName") or {}
    repr_ = m.get("Represents") or {}
    return {
        "person_id": navn.get("Id"),
        "navn": navn.get("Name"),
        "funksjon": (m.get("Function") or {}).get("Description"),
        "repr": repr_.get("ShortCode"),
        "repr_navn": repr_.get("Name"),
    }


def kjor(aar: int) -> dict:
    i_dag = dt.date.today().isoformat()
    moter = raadata.moteliste(aar)
    if moter is None:
        raise SystemExit(f"fant ingen møteliste for {aar}. Kjør hent.hent_moter først.")
    utvalg = sorted({(m["UT_ID"], m["UT_NAVN"]) for m in moter})
    print(f"Henter medlemslister for {len(utvalg)} utvalg ...")

    lister = {}
    for uid, navn in utvalg:
        medlemmer = [_rydd(m) for m in portal.utvalgsmedlemmer(uid)]
        medlemmer.sort(key=lambda m: (m["funksjon"] or "", m["repr"] or "", m["navn"] or ""))
        lister[str(uid)] = {"navn": navn, "medlemmer": medlemmer}
        print(f"  {navn}: {len(medlemmer)}")

    forrige = raadata.medlemslister()
    if forrige:
        siste = forrige[-1]
        if siste["utvalg"] == lister:
            print(f"Uendret siden {siste['hentet']}.")
            return {"endret": False}

    raadata.lagre_medlemsliste(i_dag, {"hentet": i_dag, "utvalg": lister})
    print(f"Ny versjon av medlemslistene: {i_dag}")
    return {"endret": True}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
