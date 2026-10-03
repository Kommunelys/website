"""Bygger det statiske nettstedet fra data/, kommuner/ og malen i bygg/mal/.

Hele nettstedet bygges på nytt hver gang, ikke stykkevis. Det tar sekunder ved
denne datamålestokken og fjerner en klasse feil der en gammel side blir
liggende igjen med utdatert innhold.

Malen (index.html, stil.css, app.js) er portert fra prototypen i
bygg/prototype.html. Alt som var skrevet for hånd om enkeltsaker og ett møte,
er fjernet; sidene lages bare fra dataene. Dataene skrives til
nettsted/<kommune>/data/data.js som to objekter, S og VOT, som malen leser.

Nettstedet heter Kommunelys og skal dekke flere kommuner (ADR-016). Roten er
Kommunelys-forsiden med en liste over kommunene; hver kommune har sin egen
mappe. Malen nevner ingen kommune ved navn. Det som er særegent for kommunen,
står i kommuner/<kommune>.json.

ADR-002 og ADR-015: en votering med avvik som ikke er godkjent, publiseres
ikke. Det står at den finnes og hva den gjaldt, men ikke tall eller navn.

    python -m bygg.bygg_nettsted 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

from bygg import drift
from tester.kontroller import sammendrag_avvik, unntatte_navn
from tolk.bygg_avvik import finn_avvik, holdt_tilbake
from tolk.navn import PARTIKODER, normaliser, partikode

ROT = Path(__file__).resolve().parent.parent
DATA = ROT / "data"
MAL = Path(__file__).resolve().parent / "mal"
UT = ROT / "nettsted"
KOMMUNER = ROT / "kommuner"

MERKE = "Kommunelys"
# Lenkene fra før kommunene fikk hver sin mappe (/#saker, /#person/…),
# gjaldt alle denne kommunen. Forsiden sender dem videre dit.
GAMLE_LENKER = "steinkjer"
# Felles for alle kommunene, lagt på roten.
FELLES = ("stil.css", "app.js", "favicon.svg", "apple-touch-icon.png")
# Står på hver kommuneside. Bygget stopper uten (CLAUDE.md: utvetydig uoffisiell).
UOFFISIELL = "Ikke laget av {} kommune"

FASTE = ("Leder", "Nestleder", "Medlem")

# Lenken «Meld fra om feil» under hvert sammendrag (ADR-011).
MELD_FEIL = "https://github.com/Kommunelys/website/issues/new"
REPO = MELD_FEIL.rsplit("/issues", 1)[0]
# E-post for feil og innspill på Om-siden. Tom til adressen på kommunelys.no
# er satt opp (docs/05-plan.md); så lenge den er tom, vises den ikke.
KONTAKT_EPOST = ""

# Besøkstelling (ADR-017). Koden er kontonavnet i GoatCounter:
# https://<kode>.goatcounter.com. Tom streng slår tellingen av.
GOATCOUNTER = "kommunelys"


def _telling() -> str:
    """Skriptet som teller sidevisninger, eller ingenting.

    Kommunesidene viser fanene med #saker, #person/… i adressen. GoatCounter
    teller ikke det som står etter #, så hver visning telles for hånd med
    stien og fanen. Søketeksten står ikke i adressen og telles ikke.
    """
    if not GOATCOUNTER:
        return ""
    return (
        "<script>function telle(){var g=window.goatcounter;"
        "if(g&&g.count)g.count({path:location.pathname+location.hash.split('?')[0]})}"
        "addEventListener('hashchange',telle)</script>\n"
        f'<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" '
        """data-goatcounter-settings='{"no_onload":true}' """
        'async src="https://gc.zgo.at/count.js" onload="telle()"></script>')


def _kildenavn(k: dict) -> str:
    """«Vedtak i FS 2026-09-03» -> «vedtaket i FS 03.09.2026»."""
    m = re.match(r"Vedtak i (\S+) (\d{4})-(\d\d)-(\d\d)", k["tittel"])
    if m:
        return f"vedtaket i {m.group(1)} {m.group(4)}.{m.group(3)}.{m.group(2)}"
    return "saksframlegget" if k["tittel"] == "Saksframlegg" else k["tittel"]


def _sammendrag(saker: list, analyser: dict) -> tuple[dict, list[str]]:
    """Sammendragene som kan publiseres, per sak-ID, og hvorfor resten holdes tilbake.

    Samme prinsipp som for voteringer: et sammendrag med avvik vises ikke,
    men stopper ikke resten av nettstedet.
    """
    unntatt = unntatte_navn()
    ut, holdt = {}, []
    for s in saker:
        a = analyser.get(s["sak_id"])
        if not a:
            continue
        avvik = sammendrag_avvik(s, a, unntatt)
        if avvik:
            holdt.append(f"sak {s['sak_id']}: {'; '.join(avvik)}")
            continue
        ut[s["sak_id"]] = {
            "tk": a["tittel_klarsprak"], "sum": a["sammendrag"], "bet": a["betydning"],
            "uen": a["uenighet"], "tags": a["tagger"], "modell": a["modell"],
            "kilder": [{"tittel": _kildenavn(k), "url": k["url"]} for k in a["kilder"]],
        }
    return ut, holdt

GRUNN = {
    "venter_paa_kommunen": "Holdt tilbake: protokollen er selvmotsigende om hvem som møtte. Venter på svar fra kommunen.",
    "ikke_publiser": "Holdt tilbake etter vurdering: protokollen er selvmotsigende.",
    "ikke_vurdert": "Holdt tilbake: protokollen er selvmotsigende, og avviket er ikke vurdert ennå.",
}


def _les(sti: Path, standard):
    return json.loads(sti.read_text("utf-8")) if sti.exists() else standard


def _kommune() -> dict:
    """Oppsettet for kommunen nettstedet bygges for.

    Til dataene ligger per kommune (fase 3), hører data/ til én kommune, og det
    må være nøyaktig én fil i kommuner/.
    """
    filer = sorted(KOMMUNER.glob("*.json"))
    if len(filer) != 1:
        raise SystemExit(f"fant {len(filer)} kommuner i kommuner/, men data/ har bare én")
    k = json.loads(filer[0].read_text("utf-8"))
    k.pop("merknad", None)
    return k


def _fyll(mal: str, verdier: dict[str, str]) -> str:
    """Bytter ut {{navn}} i malen. Stopper hvis noe står igjen."""
    for navn, verdi in verdier.items():
        mal = mal.replace("{{" + navn + "}}", verdi)
    rest = sorted(set(re.findall(r"\{\{\w+\}\}", mal)))
    if rest:
        raise SystemExit(f"ikke fylt inn i malen: {rest}")
    return mal


# Hvem som står bak et forslag, skrevet først i teksten: «På vegne av H, V,
# INP, PP:», «Fra SV og Rødt:», «Forslag fra Rødt, AP, SV og Frp:», ofte uten
# kolon. Listen består av partier, «uavhengig representant X» eller en
# person med parti («Kjell Haugan Ap»). Det som ikke passer, regnes som
# begynnelsen på selve forslaget.
_PARTI = (r"(?:Ap|AP|Arbeiderpartiet|H|Høyre|Sp|SP|Senterpartiet|SV|Sv|R|Rødt|"
          r"FrP|Frp|FRP|Fremskrittspartiet|INP|Inp|PP|Pp|Pensjonistpartiet|V|Venstre|KrF|Krf|"
          r"Uavh\.?|[Uu]avhengig(?: representant(?: [A-ZÆØÅ][\wæøå-]+)?)?|alle partier)")
_LEDD = rf"(?:(?:[A-ZÆØÅ][\wæøå-]+ ){{1,3}}{_PARTI}|{_PARTI})"
_AVSENDER = re.compile(
    rf"^(?:På vegne av|Fellesforslag fra|Forslag fra|Fra):?\s+"
    rf"(?P<bak>{_LEDD}(?:(?:\s*[,;]+\s*og\s+|\s*[,;]+\s*|\s+og\s+){_LEDD})*)(?![\wæøå])"
    r"[\s.,:]*")


def _avsender_og_tekst(tekst: str) -> tuple[str | None, str]:
    """«På vegne av H, V: 1. Kommunestyret …» -> («H, V», «1. Kommunestyret …»)."""
    tekst = re.sub(r"\s+", " ", tekst or "").strip()
    m = _AVSENDER.match(tekst)
    if not m or not tekst[m.end():]:
        return None, tekst
    bak = re.sub(r"\s*[,;][\s,;]*", ", ", m.group("bak")).strip(" ,")
    return bak, tekst[m.end():]


def _etikett(v: dict, tekst: str) -> str:
    """Hva voteringen gjaldt, kort: starten av forslaget, uten avsenderen."""
    if len(tekst) > 160:
        tekst = tekst[:157].rsplit(" ", 1)[0] + " …"
    return tekst or {"innstilling": "Innstillingen"}.get(v["type"], v["type"].capitalize())


# Ved alternativ votering står forslagene etter hverandre i protokollen:
# «<forslag 1> Dette ble satt opp mot: 2) Navn (Parti) fremmet følgende
# alternative forslag: <forslag 2>». Gjelder alle 61 i 2026.
_SATT_OPP_MOT = "Dette ble satt opp mot:"
_ALT_FORSLAG = re.compile(
    r"^\s*(?P<fs>\d)\)\s*(?P<stiller>[^()]{3,80}?)\s*\((?P<parti>[^)]+)\)\s*"
    r"fremmet følgende (?P<type>[\w ]*?forslag):\s*")


def _alternative_deler(v: dict, tekst: str, bak: str | None) -> list[dict] | None:
    """Forslagene i en alternativ votering, hvert for seg, med hvem som fremmet dem."""
    if not v["alternativer"] or _SATT_OPP_MOT not in tekst:
        return None
    forste, andre = tekst.split(_SATT_OPP_MOT, 1)
    del1 = {"fs": "1", "tekst": forste.strip(), "type": v["type"],
            "stiller": v["forslagsstiller"], "parti": v["parti"], "bak": bak}
    m = _ALT_FORSLAG.match(andre)
    if not m:
        return [del1, {"fs": "2", "tekst": andre.strip()}]
    bak2, rest = _avsender_og_tekst(andre[m.end():])
    return [del1, {"fs": m.group("fs"), "tekst": rest, "type": m.group("type").strip(),
                   "stiller": normaliser(m.group("stiller")),
                   "parti": partikode(m.group("parti")), "bak": bak2}]


def _alternativ_som_for_og_mot(v: dict) -> tuple[list[str], list[str], str]:
    """Alternativ votering vises per forslag. For statistikken telles stemmene
    for forslaget som ble vedtatt, som «for», og resten som «mot». Returnerer
    også nummeret på forslaget som ble vedtatt, slik protokollen oppgir det."""
    alt = v["alternativer"]
    m = re.search(r"forslag (\S+) vedtatt", v.get("resultat_tekst") or "")
    vinner = next((a for a in alt if m and a["forslag"] == m.group(1)), None)
    vinner = vinner or max(alt, key=lambda a: a["antall"])
    andre = [n for a in alt if a is not vinner for n in a["navn"]]
    return list(vinner["navn"]), andre, vinner["forslag"]


def _tema(s: dict, sammendrag: dict) -> list[str]:
    """Tema fra modellen, pluss «Høring», som kan leses sikkert av tittelen."""
    tema = set((sammendrag.get(s["sak_id"]) or {}).get("tags") or [])
    if re.search(r"\bhøring", s["tittel"], re.I):
        tema.add("Høring")
    return sorted(tema)


def _slug(navn: str) -> str:
    """«Tor-André Hopen» -> «tor-andre-hopen». Adressen til en profil."""
    s = navn.lower()
    for a, b in (("æ", "ae"), ("ø", "o"), ("å", "a"), ("é", "e"), ("è", "e"),
                 ("ä", "a"), ("ö", "o"), ("ü", "u")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _folk(verv: list) -> list[dict]:
    """De folkevalgte, med verv og oppmøte, til profilene.

    Bare personer som representerer et parti i minst ett utvalg. Medlemmer av
    råd som ikke er valgt for et parti, for eksempel ungdomsrådet, får ikke
    profil. Alt kommer fra medlemslistene og møteprotokollene; ingenting er
    skrevet av en modell, og ingenting er hentet fra andre kilder.
    """
    partier = set(PARTIKODER.values())
    # Samlet på navn, ikke person-ID: portalen har noen ganger to ID-er for
    # samme person (Monika Luktvasslimo i HPNM). Navnene er normalisert i
    # tolk/navn.py, slik stemmene også er.
    per_person: dict[str, list] = collections.defaultdict(list)
    for v in verv:
        per_person[v["navn"]].append(v)
    ut = []
    for vs in per_person.values():
        if not any(v["repr"] in partier for v in vs):
            continue
        # Partiet i kommunestyret gjelder; ellers det som står i flest verv.
        ks = [v["repr"] for v in vs if v["utvalg"] == "KS" and v["repr"] in partier]
        parti = ks[0] if ks else collections.Counter(
            v["repr"] for v in vs if v["repr"] in partier).most_common(1)[0][0]
        ut.append({
            "id": _slug(vs[0]["navn"]), "n": vs[0]["navn"], "p": parti,
            "verv": [{"u": v["utvalg"], "r": v["rolle"], "p": v["repr"],
                      "i": v["i_dagens_liste"], "m": sum(v["moter_som"].values()),
                      "for": v["motte_for"]} for v in vs],
        })
    ider = collections.Counter(p["id"] for p in ut)
    dobbel = [i for i, n in ider.items() if n > 1]
    if dobbel:
        raise SystemExit(f"to personer får samme profiladresse: {dobbel}")
    return sorted(ut, key=lambda p: p["n"])


def _s(aar: int, saker: list, moter: list, sammendrag: dict, kommune: dict) -> dict:
    """Saker, møter, utvalg og kommunestyret, i formen malen bruker."""
    politiske = collections.Counter(
        st["mote_id"] for s in saker if s["sakstype"] == "PS" and not s["formalia"]
        for st in s["saksgang"])
    cases = [{
        "formal": s["formalia"],
        "t": s["tittel"],
        "typ": s["sakstype"],
        "tags": _tema(s, sammendrag),
        **({"a": sammendrag[s["sak_id"]]} if s["sak_id"] in sammendrag else {}),
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
    # Møter med møteprotokoll per utvalg, som grunnlag for oppmøtet.
    protokoller = collections.Counter(
        o["utvalg"] for o in _les(DATA / "oppmote" / f"{aar}.json", []))
    return {
        "merke": MERKE,
        "kommune": kommune,
        "aar": aar,
        "today": dt.date.today().isoformat(),
        "cases": cases,
        "meetings": meetings,
        "utvalg": {m["utvalg_navn"]: m["utvalg"] for m in moter},
        "utvnavn": {u["kortnavn"]: u["navn"] for u in utvalg.get("utvalg", [])},
        "partier": utvalg["partier"],
        "partisider": _les(DATA / "partisider.json", {}).get("partier", {}),
        "ks": {"seter": dict(seter), "hentet": utvalg["medlemsliste_hentet"]},
        "folk": _folk(verv),
        "mprot": dict(protokoller),
        "meld": MELD_FEIL,
        "repo": REPO,
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
            bak, tekst = _avsender_og_tekst(v.get("tekst"))
            # Hele forslagsteksten følger med; etiketten er bare starten.
            ut = {"nr": v["nr"], "type": v["type"], "stiller": v["forslagsstiller"],
                  "parti": v["parti"], "lbl": _etikett(v, tekst), "tekst": tekst,
                  "bak": bak, "res": v["resultat"],
                  "en": v["enstemmig"], "dob": v["dobbeltstemme"]}
            if nokkel in stopp:
                verst = min((status.get(a, "ikke_vurdert") for a in stopp[nokkel]),
                            key=list(GRUNN).index)
                ut["holdt"] = GRUNN[verst]
                holdt += 1
            elif not v["enstemmig"]:
                f, m = v["for"], v["mot"]
                if v["alternativer"]:
                    f, m, ut["vinner"] = _alternativ_som_for_og_mot(v)
                    ut["deler"] = _alternative_deler(v, tekst, bak)
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


def _merke_ikon() -> str:
    """Merket i SVG, felles for toppen på alle sidene."""
    return (MAL / "merke.svg").read_text("utf-8").strip()


def _dato(d: dt.date) -> str:
    return f"{d.day}.{d.month}.{d.year}"


def _hentet(status: dict) -> dt.date:
    """Dataene hentes og nettstedet bygges i samme kjøring av arbeidsflyten."""
    return dt.datetime.fromisoformat(status["bygget"]).date()


def _kommuneside(kommune: dict, ut: Path) -> None:
    """index.html for én kommune, med navnet fylt inn i malen."""
    navn = html.escape(kommune["navn"])
    side = _fyll((MAL / "index.html").read_text("utf-8"),
                 {"merke": MERKE, "merke_ikon": _merke_ikon(), "kommune": navn,
                  "slug": kommune["slug"], "telling": _telling()})
    if UOFFISIELL.format(navn) not in side:
        raise SystemExit(f"kommunesiden mangler «{UOFFISIELL.format(navn)}»")
    (ut / "index.html").write_text(side, encoding="utf-8")


def _forside(kommuner: list[tuple[dict, dict]]) -> None:
    """Kommunelys-forsiden på roten, med en lenke til hver kommune.

    Listen skrives som HTML her, så siden virker uten skript.
    """
    kort = "\n".join(
        f'<li><a class="kommunekort" href="{k["slug"]}/">'
        f'<b>{html.escape(k["navn"])}</b>'
        f'<span>{st["saker"]} saker og {st["moter"]} møter i {st["ar"]}</span>'
        f'<span class="liten muted">Data hentet {_dato(_hentet(st))}</span>'
        f'</a></li>'
        for k, st in kommuner)
    side = _fyll((MAL / "forside.html").read_text("utf-8"), {
        "merke": MERKE, "merke_ikon": _merke_ikon(), "kommuner": kort,
        "gamle_lenker": GAMLE_LENKER, "repo": REPO, "telling": _telling()})
    (UT / "index.html").write_text(side, encoding="utf-8")


def _dekning(kommuner: list[tuple[dict, dict]]) -> str:
    """Tabellen over dekningen på Om-siden, fra status for hver kommune.

    Ingen tall skrives inn for hånd. Det som er kontrollert for hånd, står i
    kommuner/<kommune>.json, fordi malen ikke kan nevne kommunen.
    """
    rader = "\n".join(
        f'<tr><th scope="row"><a href="../{k["slug"]}/">{html.escape(k["navn"])}</a></th>'
        f'<td class="num">{st["moter"]}</td><td class="num">{st["saker"]}</td>'
        f'<td class="num">{st["voteringer"]} ({st["voteringer_holdt_tilbake"]} holdt tilbake)</td>'
        f'<td class="num">{st["sammendrag_publisert"]} av {st["analyser"]}</td>'
        f'<td>{html.escape(k.get("kontrollert_for_hand") or "Ingenting ennå")}</td>'
        f'<td class="num">{_dato(_hentet(st))}</td></tr>'
        for k, st in kommuner)
    return (
        '<div class="tw"><table class="dekning"><thead><tr><th scope="col">Kommune</th>'
        '<th scope="col" class="num">Møter</th><th scope="col" class="num">Saker</th>'
        '<th scope="col" class="num">Avstemninger</th>'
        '<th scope="col" class="num">Sammendrag publisert</th>'
        '<th scope="col">Kontrollert for hånd</th><th scope="col" class="num">Data hentet</th>'
        f'</tr></thead><tbody>\n{rader}\n</tbody></table></div>')


def _om(kommuner: list[tuple[dict, dict]]) -> None:
    """Om-siden på roten, felles for alle kommunene, med dekningen per kommune."""
    kontakt = (f' Du kan også skrive til <a href="mailto:{KONTAKT_EPOST}">{KONTAKT_EPOST}</a>.'
               if KONTAKT_EPOST else "")
    side = _fyll((MAL / "om.html").read_text("utf-8"), {
        "merke": MERKE, "merke_ikon": _merke_ikon(), "dekning": _dekning(kommuner),
        "repo": REPO, "meld": MELD_FEIL, "kontakt": kontakt, "telling": _telling()})
    (UT / "om").mkdir(exist_ok=True)
    (UT / "om" / "index.html").write_text(side, encoding="utf-8")


def kjor(aar: int) -> None:
    kommune = _kommune()
    saker = json.loads((DATA / "saker" / f"{aar}.json").read_text("utf-8"))
    moter = json.loads((DATA / "moter" / f"{aar}.json").read_text("utf-8"))

    analyser = {}
    for sti in (DATA / "analyse").glob("*.json"):
        a = json.loads(sti.read_text("utf-8"))
        analyser[a["sak_id"]] = a

    # Alt bygges på nytt, så ingenting fra et tidligere bygg blir liggende.
    shutil.rmtree(UT, ignore_errors=True)
    ut = UT / kommune["slug"]
    (ut / "data").mkdir(parents=True, exist_ok=True)

    sammendrag, holdt_sammendrag = _sammendrag(saker, analyser)
    S = _s(aar, saker, moter, sammendrag, kommune)
    VOT, holdt = _vot(aar, saker, moter)
    (ut / "data" / "data.js").write_text(
        "const S=" + json.dumps(S, ensure_ascii=False, separators=(",", ":")) + ";\n"
        "const VOT=" + json.dumps(VOT, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    _kommuneside(kommune, ut)
    for navn in FELLES:
        shutil.copy(MAL / navn, UT / navn)
    shutil.copytree(MAL / "fonter", UT / "fonter")

    # Data ved siden av sidene, for andre som vil bruke dem.
    for navn, innhold in (("saker", saker), ("moter", moter), ("analyser", analyser)):
        (ut / "data" / f"{navn}-{aar}.json").write_text(
            json.dumps(innhold, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
    (ut / "data" / f"voteringer-{aar}.json").write_text(
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
    (ut / "data" / f"indeks-{aar}.json").write_text(
        json.dumps(indeks, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    status = {
        "bygget": dt.datetime.now().isoformat(timespec="seconds"),
        "ar": aar,
        "saker": len(saker),
        "moter": len(moter),
        "analyser": len(analyser),
        "voteringer": sum(len(s["v"]) for m in VOT["moter"] for s in m["saker"]),
        "voteringer_holdt_tilbake": holdt,
        "sammendrag_publisert": len(sammendrag),
        "sammendrag_holdt_tilbake": holdt_sammendrag,
        # Fase 2: faktisk forbruk, for å måle kostnaden.
        "tokens": {k: sum((a.get("tokens") or {}).get(k, 0) for a in analyser.values())
                   for k in ("inn", "ut")},
    }
    (ut / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    _forside([(kommune, status)])
    _om([(kommune, status)])

    # Driftssiden. Lenkes ikke fra resten av nettstedet.
    (UT / "drift").mkdir()
    (UT / "drift" / "index.html").write_text(drift.side(
        (MAL / "drift.html").read_text("utf-8"), _fyll, status, kommune,
        collections.Counter(a["status"] for a in finn_avvik(aar)), analyser,
        MERKE, REPO, GOATCOUNTER), encoding="utf-8")

    print(f"nettsted/{kommune['slug']}/ bygget: {len(saker)} saker, {len(moter)} møter, "
          f"{len(sammendrag)} av {len(analyser)} sammendrag publisert, "
          f"{holdt} voteringer holdt tilbake")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kjor(int(args[0]) if args else dt.date.today().year)


if __name__ == "__main__":
    main()
