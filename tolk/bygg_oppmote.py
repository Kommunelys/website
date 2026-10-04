"""Leser oppmøtelisten i møteprotokollene og skriver data/oppmote/<år>.json.

ADR-008: oppmøtelisten i hver protokoll er en selvstendig, datert kilde. Den
oppgir funksjon, repr. (parti, eller kommune i interkommunale utvalg) og hvem
et varamedlem møtte for.

Stemmene i data/voteringer/ kontrolleres mot oppmøtet. To slags avvik:
- noen stemte uten å stå på oppmøtelisten
- en votering har flere stemmer enn det møtte medlemmer
Avvikene lagres per møte. En votering med avvik skal ikke publiseres før et
menneske har sett på den, på samme måte som `tall_stemmer` (ADR-002).

Leser møtene, teksten i møteprotokollene (skrives av `hent.hent_dokumenter`),
sakene og voteringene.

    python -m tolk.bygg_oppmote 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import sys

from lager import oppmote as lager_oppmote
from lager import saker as lager_saker
from lager import tekst as lager_tekst
from lager import voteringer as lager_voteringer

from .tolk_protokoll import les_oppmoteblokk


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
    moter = lager_saker.les_moter(aar)
    saker = lager_saker.les(aar, [])
    voteringer = lager_voteringer.les(aar, [])

    mote_for = {s["behandling_id"]: s["mote_id"]
                for sak in saker for s in sak["saksgang"]}
    per_mote = collections.defaultdict(list)
    for b in voteringer:
        per_mote[mote_for.get(b["behandling_id"])].append(b)

    ut = []
    for m in moter:
        protokoll = lager_tekst.les("mote", m["mote_id"])
        if protokoll is None:
            continue
        oppmote, ikke_tolket = les_oppmoteblokk(protokoll)
        ut.append({
            "mote_id": m["mote_id"],
            "utvalg": m["utvalg"],
            "dato": m["dato"],
            "oppmote": oppmote,
            "ikke_tolket": ikke_tolket,
            "avvik": _avvik(oppmote, per_mote.get(m["mote_id"], [])),
        })

    ut.sort(key=lambda m: (m["dato"], m["mote_id"]))
    lager_oppmote.lagre(aar, ut)

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
