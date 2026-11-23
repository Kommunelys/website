"""Tolker voteringene i saksprotokollene og lagrer dem (lager.voteringer).

ADR-002: mønstergjenkjenning, aldri språkmodell. Hver votering har feltet
`tall_stemmer`. Er det usant, stemmer ikke antall navn med oppgitt stemmetall,
og raden skal ikke publiseres før et menneske har sett på den.

Står samme navn to ganger i en votering, er kontrollen usann, og navnene i
den voteringen lagres ikke: databasen har én stemme per person og votering.
Stemmetallet lagres slik protokollen oppgir det, og avviket holder voteringen
tilbake til den er vurdert (tolk.bygg_avvik). De andre voteringene går videre.

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

from .tolk_protokoll import dobbelte_navn, les_vedtak, les_vedtakstekst


def _uten_navnelister(v: dict) -> list[str]:
    """Tar bort navnelistene i en votering med samme navn to ganger.

    Returnerer navnene som sto mer enn én gang. Stemmetallet beholdes, og
    `tall_stemmer` er alt usann, så voteringen holdes tilbake som et avvik.
    """
    dobbelt = dobbelte_navn(v)
    if dobbelt:
        assert not v["tall_stemmer"]
        v["for"], v["mot"], v["ikke_til_stede"], v["partier"] = [], [], [], {}
        for a in v["alternativer"]:
            a["navn"], a["partier"] = [], {}
    return dobbelt


def kjor(aar: int) -> dict:
    saker = lager_saker.les(aar)

    ut = []
    dobbelt = []
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
                navn = _uten_navnelister(v)
                if navn:
                    dobbelt.append(f"{steg['saksnr']} ({steg['utvalg']}, behandling "
                                   f"{steg['behandling_id']}) votering {nr}: {', '.join(navn)}")
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
        # Holdes tilbake uten navneliste; se protokollen.
        "samme_navn_to_ganger": dobbelt,
    }
    print(json.dumps(oppsummering, ensure_ascii=False, indent=1))
    return oppsummering


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
