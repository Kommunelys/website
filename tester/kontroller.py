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


def _kildetekst(sak: dict) -> str:
    kilde = ""
    f = sak.get("saksframlegg") or {}
    for kandidat in [f.get("dokument_id")] + [s["behandling_id"] for s in sak["saksgang"]]:
        p = TEKST / f"{kandidat}.txt"
        if p.exists():
            kilde += p.read_text(encoding="utf-8")
    return kilde


def _folkevalgte() -> set[str]:
    """Navn i vervlistene. Folkevalgte kan omtales i sin rolle (regel 6)."""
    return {v["navn"] for sti in (ROT / "data" / "verv").glob("*.json")
            for v in json.loads(sti.read_text(encoding="utf-8"))}


def _navn_i_tittel(tittel: str, folkevalgte: set[str] = frozenset()) -> list[str]:
    """Personnavn i en sakstittel: «… - Kari Nordmann og Ola Hansen».

    Grovt: et ledd etter en bindestrek som bare består av ord med stor
    forbokstav (og «og»). Stedsnavn kan slippe gjennom; det er bedre å holde
    tilbake ett sammendrag for mye enn å publisere et navn. Folkevalgte
    unntas.
    """
    navn = []
    for ledd in re.split(r"\s[-–]\s", tittel)[1:]:
        ord_ = ledd.replace(",", " ").split()
        if not 2 <= len(ord_) <= 12 or not all(o[0].isupper() or o == "og" for o in ord_):
            continue
        del_ = []
        for o in ord_ + ["og"]:
            if o == "og":
                if len(del_) >= 2 and " ".join(del_) not in folkevalgte:
                    navn.append(" ".join(del_))
                del_ = []
            else:
                del_.append(o)
    return navn


def sammendrag_avvik(sak: dict, a: dict, folkevalgte: set[str] = frozenset()) -> list[str]:
    """Hvorfor et sammendrag ikke kan publiseres. Tom liste betyr at det kan.

    Tall i sammendraget må finnes i kildeteksten, og navn på privatpersoner
    fra sakstittelen skal ikke være med (CLAUDE.md regel 6). Brukes av
    bygget, som holder tilbake sammendrag med avvik, på samme måte som
    voteringer.
    """
    if a.get("usikker"):
        return ["modellen er usikker"]
    if not a.get("kilder"):
        return ["mangler kildelenke"]  # regel 5
    tekst = " ".join(str(a.get(k, "")) for k in
                     ("tittel_klarsprak", "sammendrag", "betydning", "uenighet"))
    ut = []
    kilde = _kildetekst(sak)
    if kilde:
        uten_mellomrom = re.sub(r"[\s ]", "", kilde)
        for tall in set(re.findall(r"\b\d[\d\s .,]{2,}\b", tekst)):
            rent = re.sub(r"[\s ]", "", tall).rstrip(".,")
            if rent not in uten_mellomrom:
                ut.append(f"tallet {tall.strip()!r} finnes ikke i kilden")
    for n in _navn_i_tittel(sak["tittel"], folkevalgte):
        etternavn = n.split()[-1]
        if n in tekst or re.search(rf"\b{re.escape(etternavn)}\b", tekst):
            ut.append(f"navnet {n!r} fra tittelen står i teksten")
    return ut


def analyser_viser_til_kilden(saker: list[dict]) -> list[str]:
    """Sammendrag med avvik. Stopper ikke publiseringen; bygget holder dem tilbake."""
    etter_sak = {s["sak_id"]: s for s in saker}
    folkevalgte = _folkevalgte()
    ut = []
    for sti in ANALYSE.glob("*.json"):
        a = _les(sti)
        sak = etter_sak.get(a.get("sak_id"))
        if sak and not a.get("usikker"):
            ut += [f"sak {a['sak_id']}: {g}" for g in sammendrag_avvik(sak, a, folkevalgte)]
    return ut


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
    ):
        feil += kontroll(saker)
    # Et sammendrag med avvik holdes tilbake av bygget, ikke hele publiseringen.
    holdt = analyser_viser_til_kilden(saker)
    if holdt:
        print(f"{len(holdt)} sammendrag holdes tilbake:")
        for h in holdt[:20]:
            print(f"  - {h}")
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
