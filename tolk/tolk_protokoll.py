"""Tolker en møteprotokoll til oppmøte, voteringer og stemmer.

ADR-002: dette gjøres med mønstergjenkjenning, aldri med en språkmodell. Hver
votering kontrolleres ved at antall navn stemmer med oppgitt stemmetall. Avvik
markeres, ikke rundes av.

Teksten må være hentet ut med `pdftotext -layout`. Oppmøtelisten er
kolonnebasert, og uten -layout mister du koblingen mellom navn, funksjon og
«varamedlem for».

    pdftotext -layout protokoll.pdf protokoll.txt
    python -m tolk.tolk_protokoll protokoll.txt
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .navn import del_navn_og_parti, normaliser

# Et vedtak eller forslag, fram til «Dermed ble ... vedtatt».
VOTERING = re.compile(
    r"((?:(?P<stiller>[A-ZÆØÅ][\wÆØÅæøå .\-]+?) \((?P<parti>[^)]+)\) "
    r"fremmet følgende (?P<type>[\w ]*?forslag):?)|Innstilling:)"
    r"(?P<tekst>.*?)"
    r"(?:For forslaget stemte (?P<n_for>\d+): (?P<for>.*?)\.)? ?"
    r"(?:Imot forslaget stemte (?P<n_mot>\d+): (?P<mot>.*?)\.)? ?"
    r"Dermed ble (?P<resultat>[\w ]+?vedtatt)\.",
    re.S,
)

SAK = re.compile(r"(?=(?:PS|RS|OS|FO) \d+/\d+ [^\n]{0,300}? behandling av sak)")

OPPMOTE = re.compile(
    r"^(?P<navn>.+?)\s{2,}(?P<funksjon>Leder|Nestleder|Medlem|Varamedlem)\s*"
    r"(?P<resten>.*?)\s*$",
    re.M,
)

FUNKSJON_PARTI = re.compile(r"^([A-ZÆØÅ]+)\s*(.*)$")


def _navneliste(tekst: str | None) -> list[tuple[str, str]]:
    """«Kari Nordmann (AP), Ola Hansen (SP)» -> [(navn, parti), ...]"""
    ut = []
    for bit in re.findall(r"([^,]+?\([A-ZÆØÅ]+\))", tekst or ""):
        delt = del_navn_og_parti(bit)
        if delt:
            ut.append(delt)
    return ut


def les_oppmote(tekst: str) -> list[dict]:
    """Oppmøtelisten øverst i protokollen.

    Krever -layout: funksjon, parti og «varamedlem for» står i kolonner.
    """
    slutt = tekst.find("Følgende fra administrasjonen")
    hode = tekst[:slutt] if slutt > 0 else tekst[:4000]

    ut = []
    for m in OPPMOTE.finditer(hode):
        navn = normaliser(m.group("navn"))
        if not navn or navn.lower().startswith("navn"):
            continue  # tabelloverskriften
        rest = re.sub(r"\s+", " ", m.group("resten")).strip()
        fp = FUNKSJON_PARTI.match(rest)
        parti = fp.group(1) if fp else None
        vara_for = normaliser(fp.group(2)) if fp and fp.group(2) else None
        ut.append(
            {
                "navn": navn,
                "funksjon": m.group("funksjon"),
                "parti": parti,
                "vara_for": vara_for or None,
            }
        )
    return ut


def les_voteringer(tekst: str) -> list[dict]:
    """Alle voteringer i protokollen, i rekkefølge."""
    # Bindestrek på linjeskift midt i et navn: «Tor-\nAndré» -> «Tor-André».
    flat = re.sub(r"-\n(?=[A-ZÆØÅa-zæøå])", "-", tekst)
    flat = re.sub(r"\s+", " ", flat)

    ut = []
    for del_ in SAK.split(flat):
        m = re.match(r"((?:PS|RS|OS|FO) \d+/\d+)", del_)
        if not m:
            continue
        saksnr = m.group(1)

        for v in VOTERING.finditer(del_):
            g = v.groupdict()
            stemte_for = _navneliste(g["for"])
            stemte_mot = _navneliste(g["mot"])
            n_for = int(g["n_for"] or 0)
            n_mot = int(g["n_mot"] or 0)

            ut.append(
                {
                    "saksnr": saksnr,
                    "forslagsstiller": (
                        normaliser(g["stiller"]) if g["stiller"] else None
                    ),
                    "parti": g["parti"],
                    "type": (g["type"] or "innstilling").strip(),
                    "tekst": re.sub(r"\s+", " ", g["tekst"]).strip(),
                    "antall_for": n_for,
                    "antall_mot": n_mot,
                    "for": [n for n, _ in stemte_for],
                    "mot": [n for n, _ in stemte_mot],
                    "partier": {n: p for n, p in stemte_for + stemte_mot},
                    "resultat": (
                        "falt" if "ikke" in g["resultat"] else "vedtatt"
                    ),
                    # Kontrollen (ADR-002). Er denne usann, skal raden ikke
                    # publiseres uten at et menneske har sett på den.
                    "tall_stemmer": (
                        len(stemte_for) == n_for and len(stemte_mot) == n_mot
                    ),
                }
            )
    return ut


def tolk(tekst: str) -> dict:
    oppmote = les_oppmote(tekst)
    voteringer = les_voteringer(tekst)

    stemte = {n for v in voteringer for n in v["for"] + v["mot"]}
    tilstede = {o["navn"] for o in oppmote}

    return {
        "oppmote": oppmote,
        "voteringer": voteringer,
        "avvik": {
            "voteringer_med_feil_tall": [
                i for i, v in enumerate(voteringer) if not v["tall_stemmer"]
            ],
            # Observert 16.09.2026: Lena Hanem Bartnes (SP). Se docs/03.
            "stemte_uten_a_sta_pa_oppmotelisten": sorted(stemte - tilstede),
        },
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    tekst = Path(sys.argv[1]).read_text(encoding="utf-8")
    r = tolk(tekst)

    print(f"oppmøtte  : {len(r['oppmote'])}")
    print(f"voteringer: {len(r['voteringer'])}")
    feil = r["avvik"]["voteringer_med_feil_tall"]
    print(f"tellefeil : {len(feil)}" + (f" {feil}" if feil else ""))
    ukjente = r["avvik"]["stemte_uten_a_sta_pa_oppmotelisten"]
    if ukjente:
        print(f"stemte uten å stå på oppmøtelisten: {', '.join(ukjente)}")

    try:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    except BrokenPipeError:
        pass  # rørt videre til head eller less


if __name__ == "__main__":
    main()
