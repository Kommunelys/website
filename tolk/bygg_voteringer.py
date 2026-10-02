"""Tolker voteringene i saksprotokollene og skriver data/voteringer/<år>.json.

ADR-002: mønstergjenkjenning, aldri språkmodell. Hver votering har feltet
`tall_stemmer`. Er det usant, stemmer ikke antall navn med oppgitt stemmetall,
og raden skal ikke publiseres før et menneske har sett på den.

Leser data/saker/<år>.json og data/tekst/<behandlings-ID>.txt, som skrives av
`hent.hent_dokumenter`.

    python -m tolk.bygg_voteringer 2026
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from .tolk_protokoll import les_vedtak

ROT = Path(__file__).resolve().parent.parent
SAKER = ROT / "data" / "saker"
TEKST = ROT / "data" / "tekst"
UT = ROT / "data" / "voteringer"


def _skriv(sti: Path, data) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def kjor(aar: int) -> dict:
    saker = json.loads((SAKER / f"{aar}.json").read_text(encoding="utf-8"))

    ut = []
    for sak in saker:
        for steg in sak["saksgang"]:
            sti = TEKST / f"{steg['behandling_id']}.txt"
            # url_vedtak er None når vedtaket er skjermet eller upublisert.
            if not steg["url_vedtak"] or not sti.exists():
                continue
            voteringer = les_vedtak(sti.read_text(encoding="utf-8"), steg["saksnr"])
            for nr, v in enumerate(voteringer, 1):
                v["nr"] = nr
            ut.append({
                "behandling_id": steg["behandling_id"],
                "sak_id": sak["sak_id"],
                "saksnr": steg["saksnr"],
                "utvalg": steg["utvalg"],
                "dato": steg["dato"],
                "voteringer": voteringer,
            })

    ut.sort(key=lambda b: (b["dato"], b["behandling_id"]))
    _skriv(UT / f"{aar}.json", ut)

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
