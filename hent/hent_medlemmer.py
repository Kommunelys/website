"""Henter dagens medlemslister for alle utvalg som har møter i året.

ADR-008: portalen gir bare dagens medlemmer, ikke historikk. Listen hentes ved
hver kjøring og lagres versjonert, slik at historikken bygges opp framover. Det
skrives en ny fil i data/raa/medlemmer/ bare når noe er endret.

Svaret fra portalen har også mobilnummer, e-post og kjønn for hver folkevalgt.
Det lagres ikke: folkevalgte omtales bare i sin rolle (CLAUDE.md regel 6), og
ingen del av tjenesten trenger det. Dette er et bevisst unntak fra at rå svar
lagres urørt (ADR-001); alle felter som tolkes, beholdes.

    python -m hent.hent_medlemmer 2026
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from . import portal

ROT = Path(__file__).resolve().parent.parent
RAA = ROT / "data" / "raa"
MEDLEMMER = RAA / "medlemmer"


def _skriv(sti: Path, data) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


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
    moter = json.loads((RAA / str(aar) / "moter.json").read_text(encoding="utf-8"))
    utvalg = sorted({(m["UT_ID"], m["UT_NAVN"]) for m in moter})
    print(f"Henter medlemslister for {len(utvalg)} utvalg ...")

    lister = {}
    for uid, navn in utvalg:
        medlemmer = [_rydd(m) for m in portal.utvalgsmedlemmer(uid)]
        medlemmer.sort(key=lambda m: (m["funksjon"] or "", m["repr"] or "", m["navn"] or ""))
        lister[str(uid)] = {"navn": navn, "medlemmer": medlemmer}
        print(f"  {navn}: {len(medlemmer)}")

    forrige = sorted(MEDLEMMER.glob("*.json"))
    if forrige:
        siste = json.loads(forrige[-1].read_text(encoding="utf-8"))
        if siste["utvalg"] == lister:
            print(f"Uendret siden {siste['hentet']}.")
            return {"endret": False}

    _skriv(MEDLEMMER / f"{i_dag}.json", {"hentet": i_dag, "utvalg": lister})
    print(f"Ny versjon: data/raa/medlemmer/{i_dag}.json")
    return {"endret": True}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
