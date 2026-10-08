"""Setter sammen utvalg, partier og verv for ett år.

ADR-008: uten medlemskap og oppmøte kan ikke stemmetall tolkes. To kilder:

- Medlemslistene i rådataene, som bare viser dagens medlemmer
  (hent.hent_medlemmer). Hver lagrede versjon er en datert observasjon.
- Oppmøtet fra tolk.bygg_oppmote, som viser hvem som møtte i hvilken rolle
  på hvert møte.

Et verv er én person i ett utvalg. Portalen oppgir ikke når et verv begynte
eller sluttet, så vervet får de datoene det faktisk er observert: i hvilke
medlemslister det står, og på hvilke møter personen møtte. Valg, fritak og
permisjon står i sakene, men leses ikke ut her.

Skriver utvalgene med partiene, og vervene (lager.verv).

    python -m tolk.bygg_verv 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import sys

from lager import oppmote as lager_oppmote
from lager import raa as raadata
from lager import verv as lager_verv

from .navn import funksjon, normaliser

FASTE = ("Leder", "Nestleder", "Medlem")


def _utvalg_i_aar(aar: int) -> dict[int, dict]:
    """UT_ID -> navn, kortnavn og møter, fra rådataene for året."""
    ut: dict[int, dict] = {}
    for m in raadata.moter(aar) or []:
        uid = m["mote"]["UT_ID"]
        u = ut.setdefault(uid, {"navn": m["mote"]["UT_NAVN"], "kortnavn": None, "moter": []})
        u["kortnavn"] = u["kortnavn"] or (m["detaljer"].get("DMB") or {}).get("ShortCode")
        u["moter"].append(m["mote"]["MO_ID"])
    return ut


def kjor(aar: int) -> dict:
    utvalg = _utvalg_i_aar(aar)
    mote_utvalg = {mid: uid for uid, u in utvalg.items() for mid in u["moter"]}

    lister = raadata.medlemslister()
    if not lister:
        raise SystemExit("fant ingen medlemslister. Kjør hent.hent_medlemmer først.")
    siste = lister[-1]

    verv: dict[tuple[int, str], dict] = {}

    def _verv(uid: int, navn: str) -> dict:
        return verv.setdefault((uid, navn), {
            "navn": navn,
            "utvalg_id": uid,
            "utvalg": utvalg.get(uid, {}).get("kortnavn"),
            "person_id": None,
            "rolle": None,
            "repr": None,
            "i_dagens_liste": False,
            "i_medlemslister": [],
            "moter_som": {},
            "forst_motte": None,
            "sist_motte": None,
            "motte_for": [],
        })

    # Medlemslistene: hver versjon er en datert observasjon av vervet.
    for liste in lister:
        for uid_s, u in liste["utvalg"].items():
            for m in u["medlemmer"]:
                v = _verv(int(uid_s), normaliser(m["navn"]))
                v["i_medlemslister"].append(liste["hentet"])
                if liste is siste:
                    v.update(person_id=m["person_id"], rolle=funksjon(m["funksjon"]),
                             repr=m["repr"], i_dagens_liste=True)

    # Oppmøtet: hvem som faktisk møtte, i hvilken rolle og når.
    oppmote = lager_oppmote.les(aar)
    for mote in oppmote:
        uid = mote_utvalg.get(mote["mote_id"])
        dato = mote["dato"][:10]
        for o in mote["oppmote"]:
            v = _verv(uid, o["navn"])
            v["moter_som"][o["funksjon"]] = v["moter_som"].get(o["funksjon"], 0) + 1
            v["forst_motte"] = min(filter(None, [v["forst_motte"], dato]))
            v["sist_motte"] = max(filter(None, [v["sist_motte"], dato]))
            v["repr"] = v["repr"] or o["repr"]
            if o["vara_for"] and o["vara_for"] not in v["motte_for"]:
                v["motte_for"].append(o["vara_for"])

    ut_verv = sorted(verv.values(), key=lambda v: (v["utvalg"] or "", v["rolle"] or "~", v["navn"]))
    lager_verv.lagre(aar, ut_verv)

    partier = {m["repr"]: m["repr_navn"]
               for u in siste["utvalg"].values() for m in u["medlemmer"]
               if m["repr"] and m["repr_navn"]}
    ut_utvalg = []
    for uid, u in sorted(utvalg.items()):
        medlemmer = siste["utvalg"].get(str(uid), {}).get("medlemmer", [])
        ut_utvalg.append({
            "utvalg_id": uid,
            "kortnavn": u["kortnavn"],
            "navn": u["navn"],
            "faste_medlemmer": sum(1 for m in medlemmer if funksjon(m["funksjon"]) in FASTE),
            "varamedlemmer": sum(1 for m in medlemmer if funksjon(m["funksjon"]) == "Varamedlem"),
            "moter": len(u["moter"]),
        })
    lager_verv.lagre_utvalg(aar, {
        "medlemsliste_hentet": siste["hentet"],
        "utvalg": ut_utvalg,
        "partier": partier,
    })

    # Kontroller: hvem møtte som fast medlem uten å stå i dagens liste, og
    # hvilke faste medlemmer har ikke møtt i år. En plass tas av et fast
    # medlem eller et varamedlem som møtte for noen. Varamedlemmer uten
    # «varamedlem for» telles for seg: de tar ingen plass i protokollen.
    faste_seter = {u["utvalg_id"]: u["faste_medlemmer"] for u in ut_utvalg}

    def _seter(m: dict) -> int:
        return sum(1 for o in m["oppmote"]
                   if o["funksjon"] in FASTE or o["vara_for"])

    for_mange = [
        f"møte {m['mote_id']}: {_seter(m)} i plasser, {faste_seter[mote_utvalg[m['mote_id']]]} faste plasser"
        for m in oppmote
        if _seter(m) > faste_seter.get(mote_utvalg.get(m["mote_id"]), 10**6)
    ]
    vara_uten_plass = collections.Counter(
        f"{utvalg[mote_utvalg[m['mote_id']]]['kortnavn']}: {o['navn']}"
        for m in oppmote for o in m["oppmote"]
        if o["funksjon"] == "Varamedlem" and not o["vara_for"])
    oppsummering = {
        "medlemsliste_hentet": siste["hentet"],
        "utvalg": len(ut_utvalg),
        "verv": len(ut_verv),
        "verv_i_dagens_liste": sum(v["i_dagens_liste"] for v in ut_verv),
        "motte_uten_a_sta_i_dagens_liste": sorted(
            f"{v['utvalg']}: {v['navn']} ({', '.join(v['moter_som'])})"
            for v in ut_verv if not v["i_dagens_liste"]),
        "faste_medlemmer_som_ikke_har_motte": sum(
            1 for v in ut_verv if v["rolle"] in FASTE and not v["moter_som"]
            and utvalg.get(v["utvalg_id"], {}).get("moter")),
        "flere_i_plasser_enn_faste_plasser": for_mange,
        "varamedlem_uten_motte_for": dict(vara_uten_plass.most_common()),
    }
    print(json.dumps(oppsummering, ensure_ascii=False, indent=1))
    return oppsummering


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
