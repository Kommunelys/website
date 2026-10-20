"""Henter opptakene av kommunestyret og kobler dem til møtene og sakene (ADR-026).

For hvert opptak i kommunens arkiv som hører til et møte vi har:
1. bokmerkene, med start og varighet i opptaket, koblet til behandlingen med
   samme saksnummer i møtet. Det gir lenkene fra møtet og saken til opptaket,
   også når opptaket ikke er tekstet;
2. tekstingen, hvis opptaket er tekstet. Den hentes én gang. Opptak uten
   teksting sjekkes på nytt ved neste kjøring (ett kall).

Videoen lastes ikke ned. Opptakene kan bli slettet hos kommunen (arkivet går
tilbake til september 2025). Et opptak som er borte fra arkivet, får
«fjernet», og lenken vises ikke lenger; tekstingen vi har lagret, står.

    python -m hent.hent_opptak 2026
    python -m hent.hent_opptak 2026 --opptak 188     # bare dette opptaket
"""

from __future__ import annotations

import sys

import lager
from lager import kommune
from lager import opptak as lager_opptak
from lager import saker as lager_saker
from tolk.profil import profil

from . import kommunetv


def _moter_og_steg(aar: int) -> tuple[dict[str, list[dict]], dict[int, dict[str, dict]]]:
    """Møtene i kommunestyret per dato, og behandlingene per møte og saksnummer."""
    ks = profil().kommunestyre_kode
    moter: dict[str, list[dict]] = {}
    for m in kommune.alle_aar(lager_saker.les_moter, aar):
        if m["utvalg"] == ks:
            moter.setdefault(m["dato"][:10], []).append(m)
    steg: dict[int, dict[str, dict]] = {}
    for s in kommune.alle_aar(lager_saker.les, aar):
        for st in s["saksgang"]:
            steg.setdefault(st["mote_id"], {})[st["saksnr"]] = {
                "behandling_id": st["behandling_id"], "sak_id": s["sak_id"]}
    return moter, steg


def koble(d: dict, mote: dict, steg: dict[str, dict]) -> dict:
    """Opptaket med bokmerkene koblet til behandlingene i møtet."""
    aar = int(mote["dato"][:4])
    deler = []
    for del_ in kommunetv.deler(d):
        nr = kommunetv.saksnr(del_["nummer"], aar)
        treff = steg.get(nr) if nr else None
        deler.append({**del_, "saksnr": nr,
                      "behandling_id": treff and treff["behandling_id"],
                      "sak_id": treff and treff["sak_id"]})
    playlist = (d.get("playlist") or [{}])[0]
    return {
        "opptak_id": d["stream"]["id"],
        "mote_id": mote["mote_id"],
        "url": kommunetv.lenke(d["stream"]["id"]),
        "varighet_s": playlist.get("duration"),
        "teksting": False,
        "deler": deler,
        "fjernet": None,
    }


def kjor(aar: int, bare: list[int] | None = None) -> list[dict]:
    o = kommunetv.oppsett()
    if not o:
        print(f"{kommune.slug()} har ikke «opptak» i kommuner/{kommune.slug()}.json, hopper over")
        return []

    moter, steg = _moter_og_steg(aar)
    aarene = {str(a) for a in kommune.aarene(aar)}
    lagret = {x["opptak_id"]: x for x in lager_opptak.alle()}
    arkiv = [a for a in kommunetv.arkiv() if a.get("categoryId") == o["kategori"]]
    i_arkivet = {a["id"] for a in arkiv}
    if bare:
        arkiv = [a for a in arkiv if a["id"] in bare]

    nye = []
    for a in sorted(arkiv, key=lambda x: x["date"]):
        d = kommunetv.opptak(a["id"])
        dato = kommunetv.lokal_dato(d)
        if dato[:4] not in aarene:
            continue
        kandidater = moter.get(dato, [])
        if len(kandidater) != 1:
            print(f"  opptak {a['id']} {dato}: {len(kandidater)} møter i kommunestyret den dagen, hoppet over")
            continue
        mote = kandidater[0]
        k = koble(d, mote, steg.get(mote["mote_id"], {}))

        # Tekstingen hentes én gang. Uten teksting sjekkes det på nytt hver gang.
        linjer = biter = None
        if k["opptak_id"] in lagret and lager_opptak.teksting(k["opptak_id"]):
            k["teksting"] = True
        elif (strom := kommunetv.strom(d)) and (tekst := kommunetv.teksting(strom)):
            linjer, biter = tekst
            k["teksting"] = True
        # Opptaket først: tekstingen og rådataene peker til det.
        lager_opptak.lagre([k])
        if linjer:
            lager_opptak.lagre_teksting(k["opptak_id"], linjer)
        lager_opptak.lagre_raa(k["opptak_id"], d, biter)

        koblet = sum(1 for x in k["deler"] if x["behandling_id"])
        med_nr = sum(1 for x in k["deler"] if x["saksnr"])
        print(f"  opptak {k['opptak_id']} {dato} -> møte {mote['mote_id']}: "
              f"{koblet} av {med_nr} saker koblet, {'med' if k['teksting'] else 'uten'} teksting"
              + (", teksting hentet nå" if biter else ""))
        nye.append(k)

    # Opptak som er borte fra kommunens arkiv, får «fjernet»; lenken vises ikke.
    if not bare:
        fjernet = [{**x, "fjernet": lager.i_dag()} for x in lagret.values()
                   if x["opptak_id"] not in i_arkivet and not x.get("fjernet")]
        for x in fjernet:
            print(f"  opptak {x['opptak_id']} er borte fra arkivet, merkes som fjernet")
        if fjernet:
            lager_opptak.lagre(fjernet)
    print(f"{len(nye)} opptak, {sum(x['teksting'] for x in nye)} med teksting")
    return nye


def main() -> None:
    argv = kommune.fra_argv(sys.argv[1:])
    bare = None
    if "--opptak" in argv:
        i = argv.index("--opptak")
        bare = [int(x) for x in argv[i + 1].split(",")]
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        raise SystemExit("bruk: python -m hent.hent_opptak <år> [--opptak ID,...]")
    kjor(int(argv[0]), bare)


if __name__ == "__main__":
    main()
