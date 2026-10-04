"""Tolker en møteprotokoll til oppmøte, voteringer og stemmer.

ADR-002: dette gjøres med mønstergjenkjenning, aldri med en språkmodell. Hver
votering kontrolleres ved at antall navn stemmer med oppgitt stemmetall. Avvik
markeres, ikke rundes av.

Teksten må være hentet ut med `pdftotext -layout`. Oppmøtelisten er
kolonnebasert, og uten -layout mister du koblingen mellom navn, funksjon og
«varamedlem for».

    pdftotext -layout protokoll.pdf protokoll.txt
    python -m tolk.tolk_protokoll protokoll.txt

Saksprotokollen for én sak, slik `hent.hent_dokumenter` lagrer den, tolkes med
`les_vedtak`. Den har ikke saksnummeret foran hver sak, så saksnummeret oppgis.
Se `tolk/bygg_voteringer.py`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .navn import del_navn_og_parti, normaliser, partikode

# Et vedtak eller forslag, fram til «Dermed ble ... vedtatt».
# Observert i 2026: «Ikke til stede (1): navn.» etter navnelistene, noen ganger
# uten kolon og navn, og «vedtatt, med ordførers dobbeltstemme» (eller leders).
# Ved alternativ votering står «For forslag 1 stemte 4: …» for hvert forslag.
# Én gang står det bare «Dermed vedtatt», uten «ble» og uten punktum.
VOTERING = re.compile(
    r"((?:(?P<stiller>[A-ZÆØÅ][\wÆØÅæøå .\-]+?) \((?P<parti>[^)]+)\) "
    r"fremmet følgende (?P<type>[\w ]*?forslag):?)|Innstilling:|(?P<forslag>Forslag):)"
    r"(?P<tekst>.*?)"
    r"(?:For forslaget stemte (?P<n_for>\d+): (?P<for>.*?)\.)? ?"
    r"(?:Imot forslaget stemte (?P<n_mot>\d+): (?P<mot>.*?)\.)? ?"
    r"(?P<alternativer>(?:For forslag \S+ stemte \d+: .*?\. ?)+)?"
    r"(?:Ikke til stede \((?P<n_borte>\d+)\):? ?(?P<borte>[^.]*?)\.? ?)?"
    r"Dermed (?:ble )?(?P<resultat>[\w ]*?vedtatt)"
    r"(?:,? med (?P<dobbelt>ordførers|leders) dobbeltstemme)?\.?",
    re.S,
)

ALTERNATIV = re.compile(r"For forslag (?P<forslag>\S+) stemte (?P<n>\d+): (?P<navn>.*?)\.(?= For forslag |\s*$)")

# Uten navneliste: «Forslag til vedtak enstemmig vedtatt.», «Innstillingen ble
# enstemmig vedtatt.», «Forslaget fra X (R) ble enstemmig vedtatt.»
ENSTEMMIG = re.compile(r"(?P<tekst>[^.:]{0,100}?)\s*\b(?:ble )?enstemmig vedtatt\b")

SAK = re.compile(r"(?=(?:PS|RS|OS|FO) \d+/\d+ [^\n]{0,300}? behandling av sak)")

OPPMOTE = re.compile(
    r"^(?P<navn>.+?)\s{2,}(?P<funksjon>Leder|Nestleder|Medlem|Varamedlem)\s*"
    r"(?P<resten>.*?)\s*$",
    re.M,
)

# Kolonnen «Repr.» er partiet, eller kommunen i interkommunale utvalg.
FUNKSJON_PARTI = re.compile(r"^(\S+)\s*(.*)$")


def _navneliste(tekst: str | None) -> list[tuple[str, str]]:
    """«Kari Nordmann (AP), Ola Hansen (SP)» -> [(navn, parti), ...]"""
    ut = []
    for bit in re.findall(r"([^,]+?\([A-ZÆØÅ]+\))", tekst or ""):
        delt = del_navn_og_parti(bit)
        if delt:
            ut.append(delt)
    return ut


def les_oppmoteblokk(tekst: str) -> tuple[list[dict], list[str]]:
    """Oppmøtelisten, og linjene i den som ikke kunne tolkes.

    Krever -layout: funksjon, repr. og «varamedlem for» står i kolonner.
    Blokken går fra «Følgende medlemmer møtte» til «Følgende fra
    administrasjonen»; alle 67 møteprotokoller i 2026 har begge.
    """
    start = max(tekst.find("Følgende medlemmer møtte"), 0)
    slutt = tekst.find("Følgende fra administrasjonen", start)
    blokk = tekst[start:slutt] if slutt > 0 else tekst[start:start + 4000]

    ut: list[dict] = []
    ikke_tolket: list[str] = []
    funksjon_kol = None
    for linje in blokk.splitlines():
        if not linje.strip() or linje.startswith("Følgende medlemmer"):
            continue
        if linje.lstrip().startswith("Navn"):
            funksjon_kol = linje.find("Funksjon")
            continue  # tabelloverskriften

        m = OPPMOTE.match(linje)
        if m:
            rest = re.sub(r"\s+", " ", m.group("resten")).strip()
            fp = FUNKSJON_PARTI.match(rest)
            ut.append({
                "navn": normaliser(m.group("navn")),
                "funksjon": m.group("funksjon"),
                "repr": fp.group(1) if fp else None,
                "vara_for": (normaliser(fp.group(2)) if fp and fp.group(2)
                             else None),
            })
        elif ut:
            # Et langt navn brutt over to linjer: «Unn-Elisabeth Tronstad» /
            # «Kristiansen». Står fortsettelsen til høyre for navnekolonnen,
            # hører den til «varamedlem for».
            innrykk = len(linje) - len(linje.lstrip())
            if funksjon_kol is None or innrykk < funksjon_kol:
                ut[-1]["navn"] = normaliser(f"{ut[-1]['navn']} {linje}")
            else:
                ut[-1]["vara_for"] = normaliser(f"{ut[-1]['vara_for'] or ''} {linje}")
        else:
            ikke_tolket.append(linje.strip())
    return ut, ikke_tolket


def les_oppmote(tekst: str) -> list[dict]:
    """Oppmøtelisten øverst i protokollen."""
    return les_oppmoteblokk(tekst)[0]


def _flat(tekst: str) -> str:
    # Bindestrek på linjeskift midt i et navn: «Tor-\nAndré» -> «Tor-André».
    flat = re.sub(r"-\n(?=[A-ZÆØÅa-zæøå])", "-", tekst)
    return re.sub(r"\s+", " ", flat)


def _subjekt(tekst: str) -> str:
    """Hva som ble enstemmig vedtatt: «Forslag til vedtak», «Innstillingen».

    Teksten foran setningen kan være en overskrift eller slutten av et
    forslag, så den kuttes ved det første ordet som innleder setningen.
    """
    t = tekst.strip()
    m = re.search(r"\b(?:Forslag\w*|Innstilling\w*|Tilleggsforslag\w*|Dette|Følgende)\b.*$", t)
    return m.group(0) if m else t


def _voteringer(del_: str, saksnr: str) -> list[dict]:
    """Voteringene i teksten for én sak, i rekkefølge."""
    funnet: list[tuple[int, dict]] = []
    dekket: list[tuple[int, int]] = []

    for v in VOTERING.finditer(del_):
        g = v.groupdict()
        stemte_for = _navneliste(g["for"])
        stemte_mot = _navneliste(g["mot"])
        borte = _navneliste(g["borte"])
        n_for = int(g["n_for"] or 0)
        n_mot = int(g["n_mot"] or 0)
        n_borte = int(g["n_borte"] or 0)
        dekket.append(v.span())

        alternativer = []
        for a in ALTERNATIV.finditer((g["alternativer"] or "").strip()):
            navn = _navneliste(a.group("navn"))
            alternativer.append({
                "forslag": a.group("forslag"),
                "antall": int(a.group("n")),
                "navn": [n for n, _ in navn],
                "partier": {n: p for n, p in navn},
            })
        # Uten noe stemmetall finnes ingen fasit å kontrollere mot. Da skal
        # raden stoppes, ikke gå videre som 0 mot 0.
        har_tall = bool(g["n_for"] or g["n_mot"] or alternativer)

        funnet.append((v.start(), {
            "saksnr": saksnr,
            # «Behandling» er overskriften foran, ikke en del av navnet. Det
            # er også «Det deltok ingen vararepresentant i behandling av
            # saken», som noen ganger står rett foran, med eller uten punktum.
            "forslagsstiller": (
                normaliser(re.sub(r"^(?:Behandling\s+|.*?\bbehandling av saken\.?\s+)",
                                  "", g["stiller"]))
                if g["stiller"] else None
            ),
            "parti": partikode(g["parti"]),
            "type": (g["type"] or ("forslag" if g["forslag"] else "innstilling")).strip(),
            "tekst": re.sub(r"\s+", " ", g["tekst"]).strip(),
            "enstemmig": False,
            "antall_for": n_for,
            "antall_mot": n_mot,
            "for": [n for n, _ in stemte_for],
            "mot": [n for n, _ in stemte_mot],
            "alternativer": alternativer,
            "ikke_til_stede": [n for n, _ in borte],
            "partier": {
                n: p for n, p in stemte_for + stemte_mot
            } | {n: p for a in alternativer for n, p in a["partier"].items()},
            "resultat": (
                "falt" if "ikke" in g["resultat"] else "vedtatt"
            ),
            "resultat_tekst": g["resultat"],
            "dobbeltstemme": (
                {"ordførers": "ordfører", "leders": "leder"}[g["dobbelt"]]
                if g["dobbelt"] else None
            ),
            # Kontrollen (ADR-002). Er denne usann, skal raden ikke
            # publiseres uten at et menneske har sett på den. Navn på de
            # som ikke var til stede, står ikke alltid; da telles de ikke.
            "tall_stemmer": (
                har_tall
                and len(stemte_for) == n_for and len(stemte_mot) == n_mot
                and all(len(a["navn"]) == a["antall"] for a in alternativer)
                and (not borte or len(borte) == n_borte)
            ),
        }))

    for e in ENSTEMMIG.finditer(del_):
        if any(a <= e.start() < b for a, b in dekket):
            continue  # del av en votering med navneliste
        funnet.append((e.start(), {
            "saksnr": saksnr,
            "forslagsstiller": None,
            "parti": None,
            "type": "enstemmig",
            "tekst": _subjekt(e.group("tekst")),
            "enstemmig": True,
            # Hvem som stemte, står ikke. Det følger av oppmøtet (ADR-008).
            "antall_for": None,
            "antall_mot": 0,
            "for": [],
            "mot": [],
            "alternativer": [],
            "ikke_til_stede": [],
            "partier": {},
            "resultat": "vedtatt",
            "resultat_tekst": "enstemmig vedtatt",
            "dobbeltstemme": None,
            "tall_stemmer": True,
        }))

    return [v for _, v in sorted(funnet, key=lambda t: t[0])]


def les_voteringer(tekst: str) -> list[dict]:
    """Alle voteringer i en møteprotokoll, i rekkefølge."""
    ut = []
    for del_ in SAK.split(_flat(tekst)):
        m = re.match(r"((?:PS|RS|OS|FO) \d+/\d+)", del_)
        if m:
            ut += _voteringer(del_, m.group(1))
    return ut


def les_vedtak(tekst: str, saksnr: str) -> list[dict]:
    """Voteringene i saksprotokollen for én sak."""
    return _voteringer(_flat(tekst), saksnr)


def les_vedtakstekst(tekst: str) -> str | None:
    """Det endelige vedtaket i saksprotokollen for én sak, uendret.

    Saksprotokollen slutter med en linje som bare er «Vedtak», og under den
    står vedtaket slik det ble. Gjelder alle 241 saksprotokoller med
    voteringer i 2026. Uten linjen finnes ikke noe vedtak å vise.
    """
    linjer = tekst.splitlines()
    treff = [i for i, l in enumerate(linjer) if l.strip() == "Vedtak"]
    if not treff:
        return None
    vedtak = _flat("\n".join(linjer[treff[-1] + 1:])).strip()
    return vedtak or None


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
