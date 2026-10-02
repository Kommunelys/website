"""Bygger det statiske nettstedet fra data/ og malen i bygg/mal/.

Hele nettstedet bygges på nytt hver gang, ikke stykkevis. Det tar sekunder ved
denne datamålestokken og fjerner en klasse feil der en gammel side blir
liggende igjen med utdatert innhold.

Malen (index.html, stil.css, app.js) er portert fra prototypen i
bygg/prototype.html. Alt som var skrevet for hånd om enkeltsaker og ett møte,
er fjernet; sidene lages bare fra dataene. Dataene skrives til
nettsted/data/data.js som to objekter, S og VOT, som malen leser.

ADR-002 og ADR-015: en votering med avvik som ikke er godkjent, publiseres
ikke. Det står at den finnes og hva den gjaldt, men ikke tall eller navn.

    python -m bygg.bygg_nettsted 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

from tolk.bygg_avvik import finn_avvik, holdt_tilbake

ROT = Path(__file__).resolve().parent.parent
DATA = ROT / "data"
MAL = Path(__file__).resolve().parent / "mal"
UT = ROT / "nettsted"

FASTE = ("Leder", "Nestleder", "Medlem")

GRUNN = {
    "venter_paa_kommunen": "Holdt tilbake: protokollen er selvmotsigende om hvem som møtte. Venter på svar fra kommunen.",
    "ikke_publiser": "Holdt tilbake etter vurdering: protokollen er selvmotsigende.",
    "ikke_vurdert": "Holdt tilbake: protokollen er selvmotsigende, og avviket er ikke vurdert ennå.",
}


def _les(sti: Path, standard):
    return json.loads(sti.read_text("utf-8")) if sti.exists() else standard


def _etikett(v: dict) -> str:
    """Hva voteringen gjaldt: starten av forslagsteksten."""
    tekst = re.sub(r"\s+", " ", v.get("tekst") or "").strip()
    if len(tekst) > 120:
        tekst = tekst[:117].rsplit(" ", 1)[0] + " …"
    return tekst or {"innstilling": "Innstillingen"}.get(v["type"], v["type"].capitalize())


def _alternativ_som_for_og_mot(v: dict) -> tuple[list[str], list[str]]:
    """Alternativ votering vises per forslag. For statistikken telles stemmene
    for forslaget som ble vedtatt, som «for», og resten som «mot»."""
    alt = v["alternativer"]
    m = re.search(r"forslag (\S+) vedtatt", v.get("resultat_tekst") or "")
    vinner = next((a for a in alt if m and a["forslag"] == m.group(1)), None)
    vinner = vinner or max(alt, key=lambda a: a["antall"])
    andre = [n for a in alt if a is not vinner for n in a["navn"]]
    return list(vinner["navn"]), andre


def _s(aar: int, saker: list, moter: list) -> dict:
    """Saker, møter, utvalg og kommunestyret, i formen malen bruker."""
    politiske = collections.Counter(
        st["mote_id"] for s in saker if s["sakstype"] == "PS" and not s["formalia"]
        for st in s["saksgang"])
    cases = [{
        "formal": s["formalia"],
        "t": s["tittel"],
        "typ": s["sakstype"],
        # Fase 1 har ingen tema fra modellen. Høring kan leses sikkert av tittelen.
        "tags": ["Høring"] if re.search(r"\bhøring", s["tittel"], re.I) else [],
        "st": [{
            "hid": st["behandling_id"], "date": st["dato"], "ut": st["utvalg_navn"],
            "sc": st["utvalg"], "nr": st["saksnr"], "pub": st["protokoll_publisert"],
            "restr": st["protokoll_skjermet"], "mid": st["mote_id"],
            "prot": st["url_vedtak"], "murl": st["url_mote"],
        } for st in s["saksgang"]],
        "status": s["status"],
        "doc": (s.get("saksframlegg") or {}).get("url"),
        "att": len(s.get("vedlegg") or []),
        "ks": s["til_kommunestyret"],
    } for s in saker]
    meetings = [{
        "id": m["mote_id"], "date": m["dato"], "end": m["slutt"], "ut": m["utvalg_navn"],
        "sc": m["utvalg"], "sted": m["sted"], "rom": m["rom"], "n": m["antall_saker"],
        "nps": politiske.get(m["mote_id"], 0),
        "docs": [{"t": d["tittel"], "ty": d["type"], "u": d["url"]} for d in m["dokumenter"]],
        "url": m["url"],
    } for m in moter]

    utvalg = _les(DATA / "utvalg" / f"{aar}.json", {"partier": {}, "medlemsliste_hentet": ""})
    verv = _les(DATA / "verv" / f"{aar}.json", [])
    seter = collections.Counter(v["repr"] for v in verv
                                if v["utvalg"] == "KS" and v["rolle"] in FASTE and v["i_dagens_liste"])
    return {
        "aar": aar,
        "today": dt.date.today().isoformat(),
        "cases": cases,
        "meetings": meetings,
        "utvalg": {m["utvalg_navn"]: m["utvalg"] for m in moter},
        "partier": utvalg["partier"],
        "ks": {"seter": dict(seter), "hentet": utvalg["medlemsliste_hentet"]},
    }


def _vot(aar: int, saker: list, moter: list) -> tuple[dict, int]:
    """Voteringene per møte, med avvik som ikke er godkjent, holdt tilbake."""
    voteringer = _les(DATA / "voteringer" / f"{aar}.json", [])
    stopp, merknader = holdt_tilbake(aar)
    status = {a["avvik"]: a["status"] for a in finn_avvik(aar)}
    tittel = {st["behandling_id"]: s["tittel"] for s in saker for st in s["saksgang"]}
    mote_for = {st["behandling_id"]: st["mote_id"] for s in saker for st in s["saksgang"]}
    mote = {m["mote_id"]: m for m in moter}

    per_mote: dict[int, list] = collections.defaultdict(list)
    parti: dict[str, str] = {}
    holdt = 0
    for b in voteringer:
        mid = mote_for.get(b["behandling_id"])
        if mid not in mote or not b["voteringer"]:
            continue
        vs = []
        for v in b["voteringer"]:
            nokkel = (b["behandling_id"], v["nr"])
            ut = {"nr": v["nr"], "type": v["type"], "stiller": v["forslagsstiller"],
                  "parti": v["parti"], "lbl": _etikett(v), "res": v["resultat"],
                  "en": v["enstemmig"], "dob": v["dobbeltstemme"]}
            if nokkel in stopp:
                verst = min((status.get(a, "ikke_vurdert") for a in stopp[nokkel]),
                            key=list(GRUNN).index)
                ut["holdt"] = GRUNN[verst]
                holdt += 1
            elif not v["enstemmig"]:
                f, m = v["for"], v["mot"]
                if v["alternativer"]:
                    f, m = _alternativ_som_for_og_mot(v)
                ut.update(nfor=len(f) if v["alternativer"] else v["antall_for"],
                          nmot=len(m) if v["alternativer"] else v["antall_mot"],
                          f=f, m=m, borte=v["ikke_til_stede"],
                          alt=[{"fs": a["forslag"], "n": a["antall"], "navn": a["navn"]}
                               for a in v["alternativer"]],
                          merk=merknader.get(nokkel, []))
                parti.update(v["partier"])
            else:
                ut["merk"] = merknader.get(nokkel, [])
            vs.append(ut)
        per_mote[mid].append({"hid": b["behandling_id"], "nr": b["saksnr"],
                              "t": tittel.get(b["behandling_id"], ""), "v": vs})

    moter_ut = [{"id": mid, "date": mote[mid]["dato"], "sc": mote[mid]["utvalg"],
                 "ut": mote[mid]["utvalg_navn"],
                 "saker": sorted(s, key=lambda x: _saksnr_sortering(x["nr"]))}
                for mid, s in per_mote.items()]
    moter_ut.sort(key=lambda m: m["date"])
    return {"moter": moter_ut, "parti": parti}, holdt


def _saksnr_sortering(nr: str) -> tuple:
    m = re.match(r"(\w+) (\d+)/(\d+)", nr or "")
    return (m.group(1) != "PS", int(m.group(3)), int(m.group(2))) if m else (True, 0, 0)


def kjor(aar: int) -> None:
    saker = json.loads((DATA / "saker" / f"{aar}.json").read_text("utf-8"))
    moter = json.loads((DATA / "moter" / f"{aar}.json").read_text("utf-8"))

    analyser = {}
    for sti in (DATA / "analyse").glob("*.json"):
        a = json.loads(sti.read_text("utf-8"))
        analyser[a["sak_id"]] = a

    UT.mkdir(exist_ok=True)
    (UT / "data").mkdir(exist_ok=True)

    S = _s(aar, saker, moter)
    VOT, holdt = _vot(aar, saker, moter)
    (UT / "data" / "data.js").write_text(
        "const S=" + json.dumps(S, ensure_ascii=False, separators=(",", ":")) + ";\n"
        "const VOT=" + json.dumps(VOT, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    for navn in ("index.html", "stil.css", "app.js"):
        shutil.copy(MAL / navn, UT / navn)

    # Data ved siden av sidene, for andre som vil bruke dem.
    for navn, innhold in (("saker", saker), ("moter", moter), ("analyser", analyser)):
        (UT / "data" / f"{navn}-{aar}.json").write_text(
            json.dumps(innhold, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
    (UT / "data" / f"voteringer-{aar}.json").write_text(
        json.dumps(VOT, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

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

    (UT / "status.json").write_text(json.dumps({
        "bygget": dt.datetime.now().isoformat(timespec="seconds"),
        "ar": aar,
        "saker": len(saker),
        "moter": len(moter),
        "analyser": len(analyser),
        "voteringer": sum(len(s["v"]) for m in VOT["moter"] for s in m["saker"]),
        "voteringer_holdt_tilbake": holdt,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"nettsted/ bygget: {len(saker)} saker, {len(moter)} møter, "
          f"{len(analyser)} analyser, {holdt} voteringer holdt tilbake")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kjor(int(args[0]) if args else dt.date.today().year)


if __name__ == "__main__":
    main()
