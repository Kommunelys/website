"""Leser oppmøtelisten i møteprotokollene og skriver data/oppmote/<år>.json.

ADR-008: oppmøtelisten i hver protokoll er en selvstendig, datert kilde. Den
oppgir funksjon, repr. (parti, eller kommune i interkommunale utvalg) og hvem
et varamedlem møtte for.

Stemmene i data/voteringer/ kontrolleres mot oppmøtet. To slags avvik:
- noen stemte uten å stå på oppmøtelisten
- en votering har flere stemmer enn det møtte medlemmer
Avvikene lagres per møte. En votering med avvik skal ikke publiseres før et
menneske har sett på den, på samme måte som `tall_stemmer` (ADR-002).

Leser data/moter/<år>.json, data/tekst/moter/<møte-ID>.txt (skrives av
`hent.hent_dokumenter`), data/saker/<år>.json og data/voteringer/<år>.json.

    python -m tolk.bygg_oppmote 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import sys
from pathlib import Path

from .tolk_protokoll import les_oppmoteblokk

ROT = Path(__file__).resolve().parent.parent
MOTER = ROT / "data" / "moter"
SAKER = ROT / "data" / "saker"
VOTERINGER = ROT / "data" / "voteringer"
TEKST = ROT / "data" / "tekst" / "moter"
UT = ROT / "data" / "oppmote"


def _skriv(sti: Path, data) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def _les(sti: Path, standard):
    return json.loads(sti.read_text(encoding="utf-8")) if sti.exists() else standard


def _avvik(oppmote: list[dict], behandlinger: list[dict]) -> list[dict]:
    tilstede = {o["navn"] for o in oppmote}
    ut = []
    for b in behandlinger:
        for v in b["voteringer"]:
            navn = v["for"] + v["mot"] + [n for a in v["alternativer"] for n in a["navn"]]
            ukjente = sorted(set(navn) - tilstede)
            if ukjente:
                ut.append({"behandling_id": b["behandling_id"], "votering": v["nr"],
                           "type": "stemte_uten_oppmote", "navn": ukjente})
            if len(navn) > len(oppmote):
                ut.append({"behandling_id": b["behandling_id"], "votering": v["nr"],
                           "type": "flere_stemmer_enn_frammotte",
                           "stemmer": len(navn), "frammotte": len(oppmote)})
    return ut


def kjor(aar: int) -> dict:
    moter = json.loads((MOTER / f"{aar}.json").read_text(encoding="utf-8"))
    saker = _les(SAKER / f"{aar}.json", [])
    voteringer = _les(VOTERINGER / f"{aar}.json", [])

    mote_for = {s["behandling_id"]: s["mote_id"]
                for sak in saker for s in sak["saksgang"]}
    per_mote = collections.defaultdict(list)
    for b in voteringer:
        per_mote[mote_for.get(b["behandling_id"])].append(b)

    ut = []
    for m in moter:
        sti = TEKST / f"{m['mote_id']}.txt"
        if not sti.exists():
            continue
        oppmote, ikke_tolket = les_oppmoteblokk(sti.read_text(encoding="utf-8"))
        ut.append({
            "mote_id": m["mote_id"],
            "utvalg": m["utvalg"],
            "dato": m["dato"],
            "oppmote": oppmote,
            "ikke_tolket": ikke_tolket,
            "avvik": _avvik(oppmote, per_mote.get(m["mote_id"], [])),
        })

    ut.sort(key=lambda m: (m["dato"], m["mote_id"]))
    _skriv(UT / f"{aar}.json", ut)

    rader = [o for m in ut for o in m["oppmote"]]
    oppsummering = {
        "moter": len(ut),
        "oppmoterader": len(rader),
        "varamedlemmer": sum(1 for o in rader if o["funksjon"] == "Varamedlem"),
        "linjer_ikke_tolket": sum(len(m["ikke_tolket"]) for m in ut),
        "voteringer_kontrollert": sum(
            len(b["voteringer"]) for m in ut for b in per_mote.get(m["mote_id"], [])),
        "avvik": [f"møte {m['mote_id']} behandling {a['behandling_id']} "
                  f"votering {a['votering']}: {a['type']} "
                  f"{a.get('navn') or (a['stemmer'], a['frammotte'])}"
                  for m in ut for a in m["avvik"]],
    }
    print(json.dumps(oppsummering, ensure_ascii=False, indent=1))
    return oppsummering


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
