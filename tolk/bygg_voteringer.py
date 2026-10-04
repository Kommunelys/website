"""Tolker voteringene i saksprotokollene og skriver data/voteringer/<år>.json.

ADR-002: mønstergjenkjenning, aldri språkmodell. Hver votering har feltet
`tall_stemmer`. Er det usant, stemmer ikke antall navn med oppgitt stemmetall,
og raden skal ikke publiseres før et menneske har sett på den.

Leser sakene og teksten i saksprotokollene, som skrives av
`hent.hent_dokumenter`.

    python -m tolk.bygg_voteringer 2026
"""

from __future__ import annotations

import datetime as dt
import json
import sys

from lager import saker as lager_saker
from lager import tekst as lager_tekst
from lager import voteringer as lager_voteringer

from .tolk_protokoll import les_vedtak, les_vedtakstekst


def kjor(aar: int) -> dict:
    saker = lager_saker.les(aar)

    ut = []
    for sak in saker:
        for steg in sak["saksgang"]:
            # url_vedtak er None når vedtaket er skjermet eller upublisert.
            if not steg["url_vedtak"]:
                continue
            tekst = lager_tekst.les("behandling", steg["behandling_id"])
            if tekst is None:
                continue
            voteringer = les_vedtak(tekst, steg["saksnr"])
            for nr, v in enumerate(voteringer, 1):
                v["nr"] = nr
            ut.append({
                "behandling_id": steg["behandling_id"],
                "sak_id": sak["sak_id"],
                "saksnr": steg["saksnr"],
                "utvalg": steg["utvalg"],
                "dato": steg["dato"],
                "voteringer": voteringer,
                # Det endelige vedtaket, slik protokollen skriver det.
                "vedtak": les_vedtakstekst(tekst),
            })

    ut.sort(key=lambda b: (b["dato"], b["behandling_id"]))
    lager_voteringer.lagre(aar, ut)

    alle = [v for b in ut for v in b["voteringer"]]
    oppsummering = {
        "vedtak_lest": len(ut),
        "vedtak_med_voteringer": sum(1 for b in ut if b["voteringer"]),
        "voteringer": len(alle),
        "med_navneliste": sum(1 for v in alle if not v["enstemmig"]),
        "enstemmige": sum(1 for v in alle if v["enstemmig"]),
        "alternative": sum(1 for v in alle if v["alternativer"]),
        "avgjort_med_dobbeltstemme": sum(1 for v in alle if v["dobbeltstemme"]),
        "tall_stemmer_ikke": [
            f"behandling {b['behandling_id']} votering {v['nr']}"
            for b in ut for v in b["voteringer"] if not v["tall_stemmer"]
        ],
    }
    print(json.dumps(oppsummering, ensure_ascii=False, indent=1))
    return oppsummering


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
