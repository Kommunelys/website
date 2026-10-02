"""Bygger det statiske nettstedet. SKJELETT.

Hele nettstedet bygges på nytt hver gang, ikke stykkevis. Det tar sekunder ved
denne datamålestokken og fjerner en klasse feil der en gammel side blir
liggende igjen med utdatert innhold.

En fungerende prototype ligger i bygg/prototype.html, bygget på data fra 2026
og kommunestyremøtet 16.09. Den har faner for saker, møter og stemmegivning, og
viser hvordan sidene skal se ut. Jobben her er å skille data fra mal og
generere sidene fra data/.

    python -m bygg.bygg_nettsted
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

from tolk.bygg_avvik import holdt_tilbake

ROT = Path(__file__).resolve().parent.parent
UT = ROT / "nettsted"


def kjor(aar: int) -> None:
    saker = json.loads((ROT / "data" / "saker" / f"{aar}.json").read_text("utf-8"))
    moter = json.loads((ROT / "data" / "moter" / f"{aar}.json").read_text("utf-8"))

    analyser = {}
    for sti in (ROT / "data" / "analyse").glob("*.json"):
        a = json.loads(sti.read_text("utf-8"))
        analyser[a["sak_id"]] = a

    UT.mkdir(exist_ok=True)
    (UT / "data").mkdir(exist_ok=True)

    # ADR-002: en votering med avvik som ikke er godkjent av et menneske,
    # publiseres ikke. Det står at den finnes, men ikke hvem som stemte hva.
    sti = ROT / "data" / "voteringer" / f"{aar}.json"
    voteringer = json.loads(sti.read_text("utf-8")) if sti.exists() else []
    stopp, merknader = holdt_tilbake(aar)
    holdt = 0
    for b in voteringer:
        for i, v in enumerate(b["voteringer"]):
            nokkel = (b["behandling_id"], v["nr"])
            if nokkel in stopp:
                b["voteringer"][i] = {"nr": v["nr"], "holdt_tilbake": True}
                holdt += 1
            elif nokkel in merknader:
                v["merknader"] = merknader[nokkel]

    # Data ved siden av sidene, lastet ved behov.
    for navn, innhold in (("saker", saker), ("moter", moter),
                          ("analyser", analyser), ("voteringer", voteringer)):
        (UT / "data" / f"{navn}-{aar}.json").write_text(
            json.dumps(innhold, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")

    # Søkeindeks bygget på forhånd, kjører i nettleseren.
    indeks = [{
        "id": s["sak_id"],
        "t": (analyser.get(s["sak_id"], {}).get("tittel_klarsprak")
              or s["tittel"]),
        "o": s["tittel"],
        "s": s["status"],
        "g": [steg["utvalg"] for steg in s["saksgang"]],
    } for s in saker if not s["formalia"]]
    (UT / "data" / f"indeks-{aar}.json").write_text(
        json.dumps(indeks, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    # TODO: generer index.html og én side per sak fra en mal.
    # Inntil da kopieres prototypen, slik at kjeden henger sammen ende til ende.
    shutil.copy(Path(__file__).parent / "prototype.html", UT / "index.html")

    (UT / "status.json").write_text(json.dumps({
        "bygget": dt.datetime.now().isoformat(timespec="seconds"),
        "ar": aar,
        "saker": len(saker),
        "moter": len(moter),
        "analyser": len(analyser),
        "voteringer_holdt_tilbake": holdt,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"nettsted/ bygget: {len(saker)} saker, {len(moter)} møter, "
          f"{len(analyser)} analyser, {holdt} voteringer holdt tilbake")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kjor(int(args[0]) if args else dt.date.today().year)


if __name__ == "__main__":
    main()
