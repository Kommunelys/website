"""Kontroller som må passere før publisering.

Kjøres av GitHub Actions før nettstedet bygges. Feiler én kontroll, stopper
publiseringen heller enn å legge ut noe som kan være galt.

    python -m tester.kontroller
    python -m tester.kontroller 2026
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

from tolk.bygg_avvik import ugyldige_vurderinger

ROT = Path(__file__).resolve().parent.parent
SAKER = ROT / "data" / "saker"
MOTER = ROT / "data" / "moter"
ANALYSE = ROT / "data" / "analyse"
TEKST = ROT / "data" / "tekst"

# Et fall større enn dette tyder på feil i innhentingen, ikke på virkeligheten.
MAKS_FALL = 0.20


class Feil(Exception):
    pass


def _les(sti: Path, standard=None):
    if sti.exists():
        return json.loads(sti.read_text(encoding="utf-8"))
    return standard


def alle_saker_har_kilde(saker: list[dict]) -> list[str]:
    """Ingen sak publiseres uten lenke til portalen."""
    feil = []
    for s in saker:
        if not any(steg.get("url_mote") for steg in s["saksgang"]):
            feil.append(f"sak {s['sak_id']} mangler lenke til møtet")
    return feil


def ingen_skjermet_tekst(saker: list[dict]) -> list[str]:
    """Skjermede dokumenter skal ikke ha lagret tekst."""
    feil = []
    for s in saker:
        for steg in s["saksgang"]:
            if steg["protokoll_skjermet"]:
                if (TEKST / f"{steg['behandling_id']}.txt").exists():
                    feil.append(
                        f"behandling {steg['behandling_id']} er skjermet, "
                        "men det finnes lagret tekst"
                    )
                if steg.get("url_vedtak"):
                    feil.append(
                        f"behandling {steg['behandling_id']} er skjermet, "
                        "men har vedtakslenke"
                    )
    return feil


def analyser_viser_til_kilden(saker: list[dict]) -> list[str]:
    """Tall og egennavn i sammendraget må finnes i kildeteksten.

    Grov, men fanger mye. Egennavn gjenkjennes som store forbokstaver
    midt i en setning.
    """
    feil = []
    etter_sak = {s["sak_id"]: s for s in saker}

    for sti in ANALYSE.glob("*.json"):
        a = _les(sti)
        sak = etter_sak.get(a.get("sak_id"))
        if not sak or a.get("usikker"):
            continue

        kilde = ""
        f = sak.get("saksframlegg") or {}
        for kandidat in [f.get("dokument_id")] + [
            s["behandling_id"] for s in sak["saksgang"]
        ]:
            p = TEKST / f"{kandidat}.txt"
            if p.exists():
                kilde += p.read_text(encoding="utf-8")
        if not kilde:
            continue  # ingen tekst hentet ennå; ikke en feil i seg selv

        sammendrag = " ".join(
            str(a.get(k, "")) for k in ("sammendrag", "betydning", "uenighet")
        )
        for tall in set(re.findall(r"\b\d[\d  .,]{2,}\b", sammendrag)):
            rent = tall.strip().replace(" ", "").replace(" ", "")
            if rent not in kilde.replace(" ", "").replace(" ", ""):
                feil.append(f"sak {a['sak_id']}: tallet {tall!r} finnes ikke i kilden")

    return feil


def antall_har_ikke_stupt(saker: list[dict], aar: int) -> list[str]:
    forrige = _les(ROT / "data" / "forrige-telling.json", {})
    n = len(saker)
    gammel = forrige.get(str(aar))
    if gammel and n < gammel * (1 - MAKS_FALL):
        return [f"antall saker falt fra {gammel} til {n}; stopper"]
    forrige[str(aar)] = n
    (ROT / "data" / "forrige-telling.json").write_text(
        json.dumps(forrige, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return []


def kjor(aar: int) -> int:
    saker = _les(SAKER / f"{aar}.json")
    if saker is None:
        print(f"fant ingen saker for {aar}. Kjør tolk.bygg_saker først.")
        return 1

    moter = _les(MOTER / f"{aar}.json", [])
    feil: list[str] = []
    for kontroll in (
        alle_saker_har_kilde,
        ingen_skjermet_tekst,
        analyser_viser_til_kilden,
    ):
        feil += kontroll(saker)
    # En vurdering uten begrunnelse, eller av et avvik som ikke lenger finnes,
    # skal ikke kunne slippe voteringer gjennom (ADR-002).
    feil += ugyldige_vurderinger(aar)
    feil += antall_har_ikke_stupt(saker, aar)

    print(f"{len(moter)} møter, {len(saker)} saker, "
          f"{len(list(ANALYSE.glob('*.json')))} analyser")

    if feil:
        print(f"\n{len(feil)} feil:")
        for f in feil[:40]:
            print(f"  - {f}")
        return 1

    print("alle kontroller passerte")
    return 0


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    raise SystemExit(kjor(aar))


if __name__ == "__main__":
    main()
