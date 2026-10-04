"""Kontroller som må passere før publisering.

Kjøres av GitHub Actions før nettstedet bygges. Feiler én kontroll, stopper
publiseringen heller enn å legge ut noe som kan være galt.

    python -m tester.kontroller
    python -m tester.kontroller 2026
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from lager import analyse as lager_analyse
from lager import konfig
from lager import saker as lager_saker
from lager import tekst as lager_tekst
from lager import verv as lager_verv
from tolk.bygg_avvik import ugyldige_vurderinger

ROT = Path(__file__).resolve().parent.parent
MAL = ROT / "bygg" / "mal"
KOMMUNER = ROT / "kommuner"

# Et fall større enn dette tyder på feil i innhentingen, ikke på virkeligheten.
MAKS_FALL = 0.20


class Feil(Exception):
    pass


def _les(sti: Path, standard=None):
    if sti.exists():
        return json.loads(sti.read_text(encoding="utf-8"))
    return standard


def alle_saker_har_kilde(saker: list[dict]) -> list[str]:
    """Ingen sak publiseres uten lenke til portalen."""
    feil = []
    for s in saker:
        if not any(steg.get("url_mote") for steg in s["saksgang"]):
            feil.append(f"sak {s['sak_id']} mangler lenke til møtet")
    return feil


def ingen_skjermet_tekst(saker: list[dict]) -> list[str]:
    """Skjermede dokumenter skal ikke ha lagret tekst."""
    feil = []
    for s in saker:
        for steg in s["saksgang"]:
            if steg["protokoll_skjermet"]:
                if lager_tekst.har("behandling", steg["behandling_id"]):
                    feil.append(
                        f"behandling {steg['behandling_id']} er skjermet, "
                        "men det finnes lagret tekst"
                    )
                if steg.get("url_vedtak"):
                    feil.append(
                        f"behandling {steg['behandling_id']} er skjermet, "
                        "men har vedtakslenke"
                    )
    return feil


def _kilder(sak: dict) -> list[tuple[str, int]]:
    """Dokumentene sammendraget kontrolleres mot: saksframlegget og vedtakene."""
    f = sak.get("saksframlegg") or {}
    return ([("dokument", f.get("dokument_id"))]
            + [("behandling", s["behandling_id"]) for s in sak["saksgang"]])


def _kildetekst(sak: dict) -> str:
    return "".join(lager_tekst.les(id_rom, ident) or "" for id_rom, ident in _kilder(sak))


def _folkevalgte() -> set[str]:
    """Navn i vervlistene. Folkevalgte kan omtales i sin rolle (regel 6)."""
    return {v["navn"] for v in lager_verv.alle_aar()}


def _tillatte_navn() -> set[str]:
    """Navn som er vurdert og kan stå i et sammendrag, for eksempel en avdød
    dikter en byste skal reises over. Vedlikeholdes i data/tillatte-navn.json
    med begrunnelse for hvert navn."""
    return {n["navn"] for n in konfig.tillatte_navn()}


def unntatte_navn() -> set[str]:
    """Navn fra sakstitler som kan stå i et sammendrag."""
    return _folkevalgte() | _tillatte_navn()


# Ord som viser at et ledd i tittelen er et firma, et sted eller et bygg,
# ikke en person: «SalMar Settefisk AS», «Steinkjer Kulturhus», «Bygg B».
IKKE_PERSON = {
    "as", "asa", "sa", "ba", "kf", "iks", "da", "ans", "stiftelse", "lag", "forening",
    "stadion", "kulturhus", "hus", "bygg", "skole", "barnehage", "kirke", "senter",
    "sentrum", "hall", "park", "veg", "vei", "gate", "plass", "kommune", "fylkeskommune",
    "bru", "havn", "torg", "gård", "camping", "hotell", "museum",
}


def _navn_i_tittel(tittel: str, unntatt: set[str] = frozenset()) -> list[str]:
    """Personnavn i en sakstittel: «… - Kari Nordmann og Ola Hansen».

    Grovt: et ledd etter en bindestrek som bare består av ord med stor
    forbokstav (og «og»), uten ord som viser at det er et firma eller et sted.
    Folkevalgte og navn i data/tillatte-navn.json unntas. Det er bedre å holde
    tilbake ett sammendrag for mye enn å publisere et navn.
    """
    navn = []
    for ledd in re.split(r"\s[-–]\s", tittel)[1:]:
        ord_ = ledd.replace(",", " ").split()
        if not 2 <= len(ord_) <= 12 or not all(o[0].isupper() or o == "og" for o in ord_):
            continue
        if any(o.lower().strip(".") in IKKE_PERSON or len(o) == 1 for o in ord_):
            continue
        del_ = []
        for o in ord_ + ["og"]:
            if o == "og":
                if len(del_) >= 2 and " ".join(del_) not in unntatt:
                    navn.append(" ".join(del_))
                del_ = []
            else:
                del_.append(o)
    return navn


MANEDER = {m: i for i, m in enumerate(
    ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "desember"], 1)}
DATO_TALL = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})(?!\d)")
DATO_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})")
# Saksframleggene skriver «17. mars», «17.mars» og «17 mars».
DATO_ORD = re.compile(
    r"\b(\d{1,2})\.?\s*(" + "|".join(MANEDER) + r")\b(?:\s+(\d{4}))?", re.I)
# Tusenskille kan være mellomrom, hardt mellomrom eller punktum: 1 780 307,
# 1.780 307 og 1.780.307 er samme tall. Linjeskift er ikke tusenskille; i
# tabeller fra pdftotext står hver celle på sin egen linje.
SKILLE = r"(?:[^\S\n]|\.)"
TALL = re.compile(r"\d+(?:" + SKILLE + r"\d{3})*(?:,\d+)?")
# Årsintervall der tankestreken har falt ut i tekstuttrekket: «20302040».
AARSPENN = re.compile(r"(?<!\d)((?:19|20)\d\d)((?:19|20)\d\d|\d\d)(?!\d)")


def _tall_i_kilden(tekst: str) -> set[str]:
    """Tall i kildeteksten, også der tabellceller er klistret sammen.

    pdftotext skriver tabeller som «30000 304 980» og «54 680,2 098 141,74».
    Et tall kan derfor begynne midt i en slik rekke, men bare der det forrige
    leddet ikke kan være starten på samme tall: etter et ledd på fire sifre
    eller mer, eller etter et komma. «1 304 980» gir ikke «304 980».
    """
    tall = set()
    for m in re.finditer(r"(?<!\d)\d", tekst):
        foran = re.search(r"(\d+)" + SKILLE + r"\Z", tekst[max(0, m.start() - 12):m.start()])
        if foran and len(foran.group(1)) <= 3:
            continue
        tall.add(re.sub(r"[\s.]", "", TALL.match(tekst, m.start()).group()))
    for m in AARSPENN.finditer(tekst):
        tall.update(g for g in m.groups() if len(g) == 4)
    return tall


def _datoer_og_tall(tekst: str, kilde: bool = False) -> tuple[set[tuple], set[str]]:
    """Datoer som (dag, måned, år eller None), og tall uten tusenskille.

    Bare tall med minst tre sifre eller desimalkomma telles; små tall som
    «to møter» er ofte talt opp av modellen og ikke skrevet i kilden.
    """
    datoer = set()

    def _aar(a: str | None) -> int | None:
        return None if not a else int(a) + (2000 if len(a) == 2 else 0)

    for m in DATO_TALL.finditer(tekst):
        datoer.add((int(m.group(1)), int(m.group(2)), _aar(m.group(3))))
    for m in DATO_ISO.finditer(tekst):
        datoer.add((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    for m in DATO_ORD.finditer(tekst):
        datoer.add((int(m.group(1)), MANEDER[m.group(2).lower()], _aar(m.group(3))))
    uten_datoer = DATO_ORD.sub(" ", DATO_ISO.sub(" ", DATO_TALL.sub(" ", tekst)))
    if kilde:
        tall = _tall_i_kilden(uten_datoer)
    else:
        tall = {re.sub(r"[\s.]", "", t) for t in TALL.findall(uten_datoer)}
    tall = {t for t in tall if len(t) >= 3 or "," in t}
    tall |= {str(d[2]) for d in datoer if d[2]}
    return datoer, tall


def sammendrag_avvik(sak: dict, a: dict, unntatt: set[str] = frozenset()) -> list[str]:
    """Hvorfor et sammendrag ikke kan publiseres. Tom liste betyr at det kan.

    Tall og datoer i sammendraget må finnes i kilden: dokumentene, tittelen og
    møtedatoene i saksgangen. Navn på privatpersoner fra sakstittelen skal ikke
    være med (CLAUDE.md regel 6). Brukes av bygget, som holder tilbake
    sammendrag med avvik, på samme måte som voteringer.
    """
    if a.get("usikker"):
        return ["modellen er usikker"]
    if not a.get("kilder"):
        return ["mangler kildelenke"]  # regel 5
    tekst = " ".join(str(a.get(k, "")) for k in
                     ("tittel_klarsprak", "sammendrag", "betydning", "uenighet"))
    ut = []
    kilde = _kildetekst(sak)
    if kilde:
        kilde += " " + sak["tittel"] + " " + " ".join(st["dato"] for st in sak["saksgang"])
        k_datoer, k_tall = _datoer_og_tall(kilde, kilde=True)
        k_dag_mnd = {(d, m) for d, m, _ in k_datoer}
        s_datoer, s_tall = _datoer_og_tall(tekst)
        for d, m, aar in sorted(s_datoer, key=str):
            # «17. mars» i kilden og «17. mars 2026» i sammendraget er samme
            # dato hvis året også står i kilden.
            if aar:
                funnet = (d, m, aar) in k_datoer or (
                    (d, m, None) in k_datoer and str(aar) in k_tall)
            else:
                funnet = (d, m) in k_dag_mnd
            if not funnet:
                ut.append(f"datoen {d}.{m}.{aar or ''} finnes ikke i kilden")
        for t in sorted(s_tall - k_tall):
            ut.append(f"tallet {t!r} finnes ikke i kilden")
    for n in _navn_i_tittel(sak["tittel"], unntatt):
        etternavn = n.split()[-1]
        if n in tekst or re.search(rf"\b{re.escape(etternavn)}\b", tekst):
            ut.append(f"navnet {n!r} fra tittelen står i teksten")
    return ut


# Endres koden i denne filen, kan kontrollen svare annerledes, og tidligere
# resultater gjelder ikke lenger.
_KODE = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _grunnlag(sak: dict, a: dict, avtrykk: dict, unntatt: set[str]) -> str:
    """Fingeravtrykk av alt sammendrag_avvik bygger på. Navnelisten tas med
    bare så langt den virker: hvilke navn i tittelen som ikke er unntatt."""
    deler = {
        "kode": _KODE,
        "analyse": {k: a.get(k) for k in
                    ("usikker", "kilder", "tittel_klarsprak", "sammendrag", "betydning", "uenighet")},
        "sak": {"tittel": sak["tittel"], "datoer": [st["dato"] for st in sak["saksgang"]]},
        "kilde": [avtrykk.get(n) for n in _kilder(sak)],
        "navn": _navn_i_tittel(sak["tittel"], unntatt),
    }
    return hashlib.sha256(json.dumps(deler, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def sammendrag_avvik_alle(saker: list[dict], analyser: dict[int, dict],
                          unntatt: set[str]) -> dict[int, list[str]]:
    """sammendrag_avvik for hver analyse som har en sak, per sak-ID.

    Fra databasen huskes svaret med et fingeravtrykk av grunnlaget, og bare
    det som er endret, kontrolleres på nytt. Da slipper bygget å laste ned
    all kildetekst hver gang.
    """
    etter_sak = {s["sak_id"]: s for s in saker}
    par = {sid: (etter_sak[sid], a) for sid, a in analyser.items() if sid in etter_sak}
    avtrykk = lager_tekst.avtrykk()
    if avtrykk is None:
        return {sid: sammendrag_avvik(s, a, unntatt) for sid, (s, a) in par.items()}
    grunnlag = {sid: _grunnlag(s, a, avtrykk, unntatt) for sid, (s, a) in par.items()}
    kjent = lager_analyse.kontroller(grunnlag)
    nye = [sid for sid in par if sid not in kjent]
    lager_tekst.forhandslast(n for sid in nye for n in _kilder(par[sid][0]))
    resultat = {sid: sammendrag_avvik(*par[sid], unntatt) for sid in nye}
    lager_analyse.lagre_kontroller({sid: (grunnlag[sid], g) for sid, g in resultat.items()})
    return {sid: kjent.get(sid, resultat.get(sid)) for sid in par}


def analyser_viser_til_kilden(saker: list[dict]) -> list[str]:
    """Sammendrag med avvik. Stopper ikke publiseringen; bygget holder dem tilbake."""
    analyser = {sid: a for sid, a in lager_analyse.alle().items() if not a.get("usikker")}
    return [f"sak {sid}: {g}"
            for sid, grunner in sammendrag_avvik_alle(saker, analyser, unntatte_navn()).items()
            for g in grunner]


def antall_har_ikke_stupt(saker: list[dict], aar: int) -> list[str]:
    forrige = konfig.forrige_telling()
    n = len(saker)
    gammel = forrige.get(str(aar))
    if gammel and n < gammel * (1 - MAKS_FALL):
        return [f"antall saker falt fra {gammel} til {n}; stopper"]
    forrige[str(aar)] = n
    konfig.lagre_forrige_telling(forrige)
    return []


def malen_nevner_ingen_kommune() -> list[str]:
    """Malen er felles for alle kommunene (ADR-016).

    Et kommunenavn i malen ville stått på de andre kommunenes sider også. Det
    som er særegent for kommunen, hører hjemme i kommuner/<kommune>.json.
    """
    navn = [_les(f)["navn"] for f in sorted(KOMMUNER.glob("*.json"))]
    feil = []
    for fil in sorted(MAL.iterdir()):
        if fil.suffix not in (".html", ".js", ".css"):
            continue
        tekst = fil.read_text(encoding="utf-8")
        feil += [f"bygg/mal/{fil.name} nevner {n}; det hører hjemme i kommuner/"
                 for n in navn if n in tekst]
    return feil


def kjor(aar: int) -> int:
    saker = lager_saker.les(aar, None)
    if saker is None:
        print(f"fant ingen saker for {aar}. Kjør tolk.bygg_saker først.")
        return 1

    moter = lager_saker.les_moter(aar, [])
    feil: list[str] = []
    for kontroll in (
        alle_saker_har_kilde,
        ingen_skjermet_tekst,
    ):
        feil += kontroll(saker)
    # Et sammendrag med avvik holdes tilbake av bygget, ikke hele publiseringen.
    holdt = analyser_viser_til_kilden(saker)
    if holdt:
        print(f"{len(holdt)} sammendrag holdes tilbake:")
        for h in holdt[:20]:
            print(f"  - {h}")
    # En vurdering uten begrunnelse, eller av et avvik som ikke lenger finnes,
    # skal ikke kunne slippe voteringer gjennom (ADR-002).
    feil += ugyldige_vurderinger(aar)
    feil += antall_har_ikke_stupt(saker, aar)
    feil += malen_nevner_ingen_kommune()

    print(f"{len(moter)} møter, {len(saker)} saker, "
          f"{len(lager_analyse.alle())} analyser")

    if feil:
        print(f"\n{len(feil)} feil:")
        for f in feil[:40]:
            print(f"  - {f}")
        return 1

    print("alle kontroller passerte")
    return 0


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    raise SystemExit(kjor(aar))


if __name__ == "__main__":
    main()
