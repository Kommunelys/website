"""Henter møter, saker og saksgang for ett år.

Skriver rå API-svar til data/raa/<år>/ og rører aldri det som alt ligger der.
Inkrementell: henter bare sakslister for møter som er nye eller endret, og for
møter holdt siste 30 dager, siden protokollen kommer etterskuddsvis.

    python -m hent.hent_moter 2026
    python -m hent.hent_moter 2026 --alt     # tving full henting
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from . import portal

ROT = Path(__file__).resolve().parent.parent
RAA = ROT / "data" / "raa"

# Protokollen publiseres dager etter møtet, så nylige møter sjekkes på nytt.
ETTERSLEP_DAGER = 30


def _les(sti: Path):
    if sti.exists():
        return json.loads(sti.read_text(encoding="utf-8"))
    return None


def _skriv(sti: Path, data) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def _ma_hentes(m: dict, forrige: dict | None, i_dag: str, alt: bool) -> bool:
    if alt or forrige is None:
        return True
    # Endret møtetidspunkt, sted eller rom.
    for felt in ("MO_START", "MO_SLUTT", "MO_STED", "MO_ROM"):
        if m.get(felt) != forrige.get(felt):
            return True
    # Nylig holdt møte: protokollen kan ha kommet.
    dato = m["MO_START"][:10]
    if dato <= i_dag:
        grense = (
            dt.date.fromisoformat(i_dag) - dt.timedelta(days=ETTERSLEP_DAGER)
        ).isoformat()
        if dato >= grense:
            return True
    return False


def kjor(aar: int, alt: bool = False) -> dict:
    i_dag = dt.date.today().isoformat()
    ut = RAA / str(aar)

    print(f"Henter møtelisten for {aar} ...")
    liste = portal.moter(aar)
    liste.sort(key=lambda m: m["MO_START"])
    print(f"  {len(liste)} møter")

    forrige_liste = _les(ut / "moter.json") or []
    forrige = {m["MO_ID"]: m for m in forrige_liste}
    _skriv(ut / "moter.json", liste)

    endret, hoppet = [], 0
    for i, m in enumerate(liste, 1):
        mid = m["MO_ID"]
        if not _ma_hentes(m, forrige.get(mid), i_dag, alt):
            hoppet += 1
            continue

        print(f"[{i}/{len(liste)}] {m['MO_START'][:10]} {m['UT_NAVN']}")
        detaljer = portal.mote(mid)
        saksliste = portal.saksliste(mid)

        behandlinger = []
        for s in saksliste:
            try:
                behandlinger.append(portal.behandling(s["Id"]))
            except portal.PortalFeil as e:
                print(f"   hoppet over behandling {s.get('Id')}: {e}")
                behandlinger.append(s)

        _skriv(
            ut / "moter" / f"{mid}.json",
            {"mote": m, "detaljer": detaljer, "behandlinger": behandlinger},
        )
        endret.append(mid)

    _skriv(
        ut / "siste-kjoring.json",
        {"tidspunkt": dt.datetime.now().isoformat(timespec="seconds"),
         "moter_totalt": len(liste),
         "moter_hentet": len(endret),
         "moter_uendret": hoppet,
         "endrede_moter": endret},
    )
    print(f"\nFerdig. {len(endret)} møter hentet, {hoppet} uendret.")
    return {"hentet": endret, "uendret": hoppet}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar, alt="--alt" in sys.argv)


if __name__ == "__main__":
    main()
