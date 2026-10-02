"""Samler avvikene som et menneske må vurdere før en votering publiseres.

ADR-002: en votering der antall navn ikke stemmer med stemmetallet, eller der
stemmene ikke stemmer med oppmøtet, publiseres ikke før et menneske har sett
på den. Vurderingen gjøres av et menneske, ikke av en språkmodell (CLAUDE.md
regel 2). Svaret står ofte ikke i dokumentene; noen ganger vet bare kommunen.

Ett avvik er én ting å vurdere, og berører ofte mange voteringer:

- `oppmote`: én person stemmer i ett møte uten å stå på oppmøtelisten
- `antall`: én votering har flere stemmer enn det møtte medlemmer
- `tall`: én votering der antall navn ikke stemmer med stemmetallet

Vurderingene skrives for hånd i data/vurderinger.json, én per avvik:

    {"avvik": "oppmote:1285:lena-hanem-bartnes",
     "avgjorelse": "publiser",
     "merknad": "Vises sammen med voteringen. Kan stå tom.",
     "begrunnelse": "Hvorfor, med kilde. Påkrevd.",
     "vurdert_av": "Navn", "dato": "2026-10-02"}

`avgjorelse` er `publiser`, `ikke_publiser` eller `venter_paa_kommunen`.
Bare `publiser` slipper voteringene gjennom. Et avvik uten vurdering holdes
tilbake.

Leser data/voteringer/<år>.json, data/oppmote/<år>.json og
data/vurderinger.json. Skriver data/avvik/<år>.json, som viser hvert avvik
med nøkkelen som skal brukes i vurderingen.

    python -m tolk.bygg_avvik 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

from hent import portal

ROT = Path(__file__).resolve().parent.parent
VOTERINGER = ROT / "data" / "voteringer"
OPPMOTE = ROT / "data" / "oppmote"
VURDERINGER = ROT / "data" / "vurderinger.json"
UT = ROT / "data" / "avvik"

AVGJORELSER = ("publiser", "ikke_publiser", "venter_paa_kommunen")


def _skriv(sti: Path, data) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def _les(sti: Path, standard):
    return json.loads(sti.read_text(encoding="utf-8")) if sti.exists() else standard


def _slug(navn: str) -> str:
    n = unicodedata.normalize("NFKD", navn).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def vurderinger() -> dict[str, dict]:
    """Vurderingene fra data/vurderinger.json, etter nøkkel."""
    return {v["avvik"]: v for v in _les(VURDERINGER, [])}


def finn_avvik(aar: int) -> list[dict]:
    """Alle avvik for året, med vurderingen hvis den finnes."""
    voteringer = _les(VOTERINGER / f"{aar}.json", [])
    oppmote = _les(OPPMOTE / f"{aar}.json", [])
    funnet: dict[str, dict] = {}

    def _avvik(nokkel: str, **felt) -> dict:
        return funnet.setdefault(nokkel, {"avvik": nokkel, "voteringer": [], **felt})

    for b in voteringer:
        for v in b["voteringer"]:
            if not v["tall_stemmer"]:
                a = _avvik(f"tall:{b['behandling_id']}:{v['nr']}", type="tall",
                           utvalg=b["utvalg"], dato=b["dato"][:10],
                           beskrivelse=f"{b['saksnr']}: antall navn stemmer ikke med stemmetallet")
                a["voteringer"].append([b["behandling_id"], v["nr"]])

    for m in oppmote:
        kilde = portal.url_mote_i_portalen(m["mote_id"])
        for x in m["avvik"]:
            ref = [x["behandling_id"], x["votering"]]
            if x["type"] == "stemte_uten_oppmote":
                for navn in x["navn"]:
                    a = _avvik(f"oppmote:{m['mote_id']}:{_slug(navn)}", type="oppmote",
                               utvalg=m["utvalg"], dato=m["dato"][:10], kilde=kilde,
                               beskrivelse=f"{navn} stemmer uten å stå på oppmøtelisten")
                    a["voteringer"].append(ref)
            else:
                a = _avvik(f"antall:{x['behandling_id']}:{x['votering']}", type="antall",
                           utvalg=m["utvalg"], dato=m["dato"][:10], kilde=kilde,
                           beskrivelse=f"{x['stemmer']} stemmer, men {x['frammotte']} møtte")
                a["voteringer"].append(ref)

    vurdert = vurderinger()
    ut = sorted(funnet.values(), key=lambda a: (a["dato"], a["avvik"]))
    for a in ut:
        v = vurdert.get(a["avvik"])
        a["vurdering"] = v
        a["status"] = v["avgjorelse"] if v else "ikke_vurdert"
    return ut


def holdt_tilbake(aar: int) -> tuple[dict[tuple[int, int], list[str]], dict[tuple[int, int], list[str]]]:
    """(voteringer som holdes tilbake, merknader til voteringer som publiseres).

    Begge er nøklet på (behandlings-ID, voteringens nr). En votering holdes
    tilbake hvis ett eneste avvik som berører den, ikke er godkjent.
    """
    stopp: dict[tuple[int, int], list[str]] = collections.defaultdict(list)
    merknader: dict[tuple[int, int], list[str]] = collections.defaultdict(list)
    for a in finn_avvik(aar):
        for b, nr in a["voteringer"]:
            if a["status"] == "publiser":
                if a["vurdering"].get("merknad"):
                    merknader[(b, nr)].append(a["vurdering"]["merknad"])
            else:
                stopp[(b, nr)].append(a["avvik"])
    return dict(stopp), dict(merknader)


def ugyldige_vurderinger(aar: int) -> list[str]:
    """Vurderinger som mangler noe, eller som viser til avvik som ikke finnes."""
    kjente = {a["avvik"] for a in finn_avvik(aar)}
    feil = []
    for v in _les(VURDERINGER, []):
        n = v.get("avvik", "?")
        if v.get("avgjorelse") not in AVGJORELSER:
            feil.append(f"vurdering {n}: avgjorelse må være en av {', '.join(AVGJORELSER)}")
        if not (v.get("begrunnelse") or "").strip():
            feil.append(f"vurdering {n}: mangler begrunnelse")
        if n.split(":")[0] in ("oppmote", "antall", "tall") and n not in kjente:
            # Kan skyldes at kommunen har rettet protokollen. Da skal
            # vurderingen fjernes, ikke stå igjen og se gyldig ut.
            feil.append(f"vurdering {n}: avviket finnes ikke lenger")
    return feil


def kjor(aar: int) -> dict:
    avvik = finn_avvik(aar)
    _skriv(UT / f"{aar}.json", avvik)
    stopp, _ = holdt_tilbake(aar)
    oppsummering = {
        "avvik": len(avvik),
        "status": dict(collections.Counter(a["status"] for a in avvik)),
        "voteringer_holdt_tilbake": len(stopp),
        "ugyldige_vurderinger": ugyldige_vurderinger(aar),
        "ikke_vurdert": [f"{a['avvik']}  ({a['utvalg']} {a['dato']}, "
                         f"{len(a['voteringer'])} voteringer): {a['beskrivelse']}"
                         for a in avvik if a["status"] == "ikke_vurdert"],
    }
    print(json.dumps(oppsummering, ensure_ascii=False, indent=1))
    return oppsummering


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar)


if __name__ == "__main__":
    main()
