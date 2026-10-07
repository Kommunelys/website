"""Dekningen: hvor mye av protokollene regelsettet faktisk leser (ADR-021).

En kommune som skriver protokollene annerledes enn mønstrene venter, gir ikke
feil, bare tomt: voteringene mangler uten at noe sier fra. Dekningen fanger det.

Saksprotokollene som er lest (tolk.bygg_voteringer), sorteres i tre:

- med votering: minst én votering eller ett enstemmig vedtak er funnet
- uten votering: teksten nevner ikke at noen stemte, som «Tas til orientering»
- mistenkt: teksten nevner at noen stemte eller noe ble vedtatt
  (VOTERINGSORD i profilen), men ingen votering er funnet

Dekningen for voteringer er andelen med votering av dem som har eller burde
hatt en. For oppmøtet er den andelen møteprotokoller der oppmøtelisten er lest.
Med nivået «voteringer» eller «oppmote» på i kommuner/<slug>.json må dekningen
være minst GRENSE, ellers stopper tester.kontroller publiseringen av kommunen.

    python -m tolk.dekning 2026
"""

from __future__ import annotations

import datetime as dt
import json
import sys

from lager import oppmote as lager_oppmote
from lager import tekst as lager_tekst
from lager import voteringer as lager_voteringer

from .profil import profil

# Steinkjer 2026: 98 % for voteringene (241 av 245) og 100 % for oppmøtet.
GRENSE = 0.95


def kjor(aar: int) -> dict:
    voteringer = lager_voteringer.les(aar, [])
    oppmote = lager_oppmote.les(aar, [])
    ord_ = profil().voteringsord

    uten = [b for b in voteringer if not b["voteringer"]]
    lager_tekst.forhandslast([("behandling", b["behandling_id"]) for b in uten])
    mistenkte = [b["behandling_id"] for b in uten
                 if ord_.search(lager_tekst.les("behandling", b["behandling_id"]) or "")]
    med = len(voteringer) - len(uten)
    lest = sum(1 for m in oppmote if m["oppmote"])
    return {
        "saksprotokoller": len(voteringer),
        "med_votering": med,
        "uten_votering": len(uten) - len(mistenkte),
        "mistenkt": len(mistenkte),
        "voteringer": round(med / (med + len(mistenkte)), 4) if med + len(mistenkte) else None,
        "moteprotokoller": len(oppmote),
        "oppmote_lest": lest,
        "oppmote": round(lest / len(oppmote), 4) if oppmote else None,
        "mistenkte": mistenkte,
    }


def samlet(aar: int) -> dict:
    """Dekningen for alle årene til og med `aar`, slått sammen.

    Tidlig på året er det få protokoller, og én mistenkt kan gi lav andel.
    Kontrollen og nettstedet bruker derfor alle årene samlet (ADR-022).
    """
    from lager import kommune  # noqa: PLC0415

    deler = [kjor(a) for a in kommune.aarene(aar)]
    tall = {k: sum(d[k] for d in deler) for k in
            ("saksprotokoller", "med_votering", "uten_votering", "mistenkt", "moteprotokoller", "oppmote_lest")}
    med, mistenkt = tall["med_votering"], tall["mistenkt"]
    return tall | {
        "voteringer": round(med / (med + mistenkt), 4) if med + mistenkt else None,
        "oppmote": round(tall["oppmote_lest"] / tall["moteprotokoller"], 4) if tall["moteprotokoller"] else None,
        "mistenkte": [i for d in deler for i in d["mistenkte"]],
    }


def under_grensen(dekning: dict, nivaa: dict) -> list[str]:
    """Det som er slått på i nivåene, men har for lav dekning."""
    feil = []
    for del_, navn in (("voteringer", "voteringene"), ("oppmote", "oppmøtet")):
        andel = dekning[del_]
        if nivaa.get(del_, True) and andel is not None and andel < GRENSE:
            feil.append(f"dekningen for {navn} er {andel:.0%}, under grensen på {GRENSE:.0%}; "
                        f"rett profilen eller slå av «{del_}» i nivåene")
    return feil


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    print(json.dumps(kjor(aar), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
