"""Sammendrag av debatten i kommunestyret, fra kommunens teksting av opptaket.

Protokollen sier hva som ble vedtatt og hvem som stemte hva, men ikke hvorfor.
Debatten står bare i opptaket. Kommunen har automatisk teksting på noen av
opptakene (hent.hent_opptak); bare de brukes.

ADR-002 gjelder også her: stemmetall og utfall kommer fra protokollen, aldri
fra teksten modellen skriver. Modellen får vedtaket og forslagene fra
voteringene, så den vet hva som ble stemt over, men skal ikke gjengi utfallet.

Regel 6: folkevalgte omtales bare i sin rolle. Sammendraget sier hvilket parti
som mente hva, aldri hvem. Tekstingen hører ofte navn feil («Rune Kåran» for
Rune Kvaran), så kontrollen leter etter navn som ligner, ikke bare like navn.

Bokmerkene i opptaket settes for hånd og er unøyaktige: slutten av ett
bokmerke kan handle om en annen sak. Modellen skal se bort fra det.

Kjører én gang per behandling, som analyser_saker: resultatet lagres med en
sjekksum av grunnlaget, og sendes bare inn på nytt når grunnlaget eller
instruksjonen er endret. Kontrollen (avvik) kjøres i bygget, og et sammendrag
som ikke består, vises ikke.

    python -m analyser.analyser_debatt 2026 --tort-lop       # vis hva som ville blitt sendt
    python -m analyser.analyser_debatt 2026 --maks 10        # høyst 10 behandlinger
    python -m analyser.analyser_debatt 2026 --vis 8457       # grunnlaget for én behandling
    python -m analyser.analyser_debatt 2026 --kontroller svar.json  # kontroller svar skrevet utenfor
    python -m analyser.analyser_debatt 2026 --lagre svar.json       # lagre svar skrevet utenfor (prøve)
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

from drift.logg import legg_til
from hent import kommunetv
from lager import kommune
from lager import opptak as lager_opptak
from lager import saker as lager_saker
from lager import voteringer as lager_voteringer
from tolk.profil import profil

MODELL = "claude-opus-5"
INNSATS = "high"
MAKS_TOKENS = 16000
MAKS_PER_KJORING = 15
INSTRUKSJON_VERSJON = 1
# Kortere enn dette er bare opplesning og avstemning; da sendes ingenting inn.
KORT_S = 60
# Hvor langt fra et punkt partiet må være nevnt i tekstingen (sekunder).
VINDU_S = 180

SKJEMA = {
    "type": "object",
    "properties": {
        "ingen_debatt": {"type": "boolean"},
        "oppsummering": {"type": "string"},
        "antall_innlegg": {"type": "integer"},
        "punkter": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tekst": {"type": "string"},
                    "partier": {"type": "array", "items": {"type": "string"}},
                    "del": {"type": "integer"},
                    "tid_s": {"type": "integer"},
                },
                "required": ["tekst", "partier", "del", "tid_s"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ingen_debatt", "oppsummering", "antall_innlegg", "punkter"],
    "additionalProperties": False,
}

_INSTRUKSJON = """Du oppsummerer debatten om én sak i kommunestyret i {kommune} kommune for innbyggere uten forkunnskaper. Grunnlaget er kommunens automatiske teksting av opptaket, delt i deler etter bokmerkene i opptaket. Hver linje har tiden fra starten av delen, «[del N mm:ss]».

- Gjengi argumentene med egne ord. Siter aldri.
- Skriv aldri navn på personer, heller ikke folkevalgte. Skriv partiet («SV mente …») eller rollen («ordføreren», «kommunedirektøren»).
- Partiet til en taler finner du der møtelederen gir ordet («… fra SV, vær så god»), eller i listen over representantene. Tekstingen hører navn feil; et navn som ligner, er samme person. Er du ikke sikker på partiet, la «partier» stå tom og skriv «en representant».
- Skriv aldri stemmetall eller hvordan avstemningen endte. Nettstedet viser det fra protokollen.
- Ikke gjett motiver, og ikke vurder om argumentene er gode.
- Bokmerkene er satt for hånd. Ser du bort fra alt som handler om en annen sak, også voteringer i en annen sak.
- Tekstingen er maskinlaget og har hørefeil. Bruk vedtaket og forslagene i grunnlaget til å forstå hva som ble sagt, men skriv bare det som faktisk ble sagt i debatten.
- Hadde ingen ordet (bare opplesning og avstemning), sett «ingen_debatt» til true og la resten stå tomt.
- Skriv klarspråk på norsk bokmål, med korte setninger.

Partikodene: {partier}. Bruk kodene i «partier».

Feltene:
- oppsummering: to til tre setninger om hva debatten handlet om og hvor partiene sto
- antall_innlegg: hvor mange innlegg fra talerstolen, uten møtelederens
- punkter: tre til seks hovedargumenter, hvert med partiene som fremmet det, delen og tiden i sekunder fra starten av delen der argumentet kommer"""


def instruksjon() -> str:
    partier = ", ".join(f"{k} = {v}" for k, v in profil().partinavn.items())
    return (_INSTRUKSJON.replace("{kommune}", kommune.oppsett()["navn"])
            .replace("{partier}", partier))


def _klokke(s: float) -> str:
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def deler_for(opptak: dict, behandling_id: int) -> list[dict]:
    """Bokmerkene til en behandling, i rekkefølge, med nummer fra 1."""
    ds = [d for d in opptak["deler"] if d["behandling_id"] == behandling_id]
    return [{**d, "del": i} for i, d in enumerate(sorted(ds, key=lambda d: d["start_ms"]), 1)]


def linjer_i(teksting: dict, del_: dict) -> list[dict]:
    """Tekstlinjene i en del, med tiden fra starten av delen."""
    a, b = del_["start_ms"], del_["start_ms"] + del_["varighet_ms"]
    return [{**l, "rel_s": (l["start_ms"] - a) / 1000}
            for l in teksting["linjer"] if a <= l["start_ms"] < b]


def representanter(behandling: dict) -> dict[str, str]:
    """Navn og parti for alle som stemte i behandlingen (fra voteringene)."""
    ut = {}
    for v in behandling.get("voteringer") or []:
        ut.update(v.get("partier") or {})
    return ut


def grunnlag(sak: dict, behandling: dict, opptak: dict, teksting: dict) -> tuple[str, list[dict]]:
    """Det modellen skal lese, og delene det bygger på."""
    ds = deler_for(opptak, behandling["behandling_id"])
    forslag = []
    for v in behandling.get("voteringer") or []:
        if v["type"] == "innstilling":
            continue
        tekst = re.sub(r"\s+", " ", v.get("tekst") or "").strip()
        forslag.append(f"- {v['type']} fra {v.get('parti') or 'ukjent'}: {tekst}")
    rep = representanter(behandling)
    tekst = [
        f"<sak>\nTittel: {sak['tittel']}\nSaksnummer: {behandling['saksnr']}\n</sak>",
        f"<vedtak>\n{behandling.get('vedtak') or ''}\n</vedtak>",
    ]
    if forslag:
        tekst.append("<forslag>\n" + "\n".join(forslag) + "\n</forslag>")
    tekst.append("<representanter>\n" + "\n".join(
        f"{n} ({p})" for n, p in sorted(rep.items())) + "\n</representanter>")
    for d in ds:
        linjer = linjer_i(teksting, d)
        tekst.append(
            f'<del nr="{d["del"]}" bokmerke="{d["tittel"]}" varighet="{_klokke(d["varighet_ms"] / 1000)}">\n'
            + "\n".join(f"[del {d['del']} {_klokke(l['rel_s'])}] {l['tekst']}" for l in linjer)
            + "\n</del>")
    return "\n\n".join(tekst), ds


# --- Kontrollen -----------------------------------------------------------

# Navn og kortformer partiene omtales med i tekstingen. Tekstingen skriver
# «IMP» for INP.
PARTI_ORD = {
    "AP": ["Arbeiderpartiet", "Ap"],
    "FRP": ["Fremskrittspartiet", "Frp", "FrP"],
    "H": ["Høyre"],
    "INP": ["Industri- og næringspartiet", "INP", "IMP"],
    "KRF": ["Kristelig Folkeparti", "KrF"],
    "PP": ["Pensjonistpartiet"],
    "R": ["Rødt"],
    "SP": ["Senterpartiet", "Sp"],
    "SV": ["SV", "Sosialistisk Venstreparti"],
    "V": ["Venstre"],
    "MDG": ["Miljøpartiet", "MDG"],
}

_STEMMETALL = re.compile(
    r"\b\d+\s*(?:stemmer|stemte|mot\b|for\b)|\b\d+\s*[–-]\s*\d+\b|\benstemmig|\bvedtatt\b|\bfalt\b",
    re.IGNORECASE)


def _ord(t: str) -> list[str]:
    return re.findall(r"[A-ZÆØÅÉ][\wæøåéÆØÅÉ-]+", t)


def _ligner(a: str, b: str) -> bool:
    """Tekstingen hører navn feil: «Kåran» for Kvaran, «Krostad» for Krogstad."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.7


def avvik(svar: dict, sak: dict, behandling: dict, opptak: dict, teksting: dict) -> list[str]:
    """Grunner til å holde sammendraget tilbake. Tom liste betyr at det kan vises."""
    ut = []
    if svar.get("ingen_debatt"):
        return ut
    rep = representanter(behandling)
    navnedeler = {d for n in rep for d in re.split(r"[\s-]+", n) if len(d) >= 3}
    tillatt = set(_ord(sak["tittel"])) | set(_ord(behandling.get("vedtak") or ""))
    for v in behandling.get("voteringer") or []:
        tillatt |= set(_ord(v.get("tekst") or ""))
    tillatt |= {o for ord_ in PARTI_ORD.values() for x in ord_ for o in _ord(x)}
    tillatt |= set(profil().partinavn) | set(_ord(" ".join(profil().partinavn.values())))
    tillatt |= {kommune.oppsett()["navn"]}

    tekster = [svar.get("oppsummering") or ""] + [p["tekst"] for p in svar.get("punkter") or []]
    for t in tekster:
        if m := _STEMMETALL.search(t):
            ut.append(f"stemmetall eller utfall i teksten: {m[0]!r}")
        for setning in re.split(r"(?<=[.!?:])\s+", t):
            for o in _ord(setning):
                # «Steinkjers» er Steinkjer i genitiv.
                if o in tillatt or o.removesuffix("s") in tillatt:
                    continue
                treff = next((n for n in navnedeler if _ligner(o, n)), None)
                if treff:
                    ut.append(f"ligner navnet {treff!r}: {o!r}")
                elif not setning.startswith(o):
                    ut.append(f"mulig navn: {o!r}")

    ds = {d["del"]: d for d in deler_for(opptak, behandling["behandling_id"])}
    partier_i_mote = set(rep.values())
    for p in svar.get("punkter") or []:
        d = ds.get(p["del"])
        if not d:
            ut.append(f"del {p['del']} finnes ikke")
            continue
        if not 0 <= p["tid_s"] <= d["varighet_ms"] / 1000:
            ut.append(f"tiden {p['tid_s']} s er utenfor del {p['del']}")
            continue
        vindu = " ".join(l["tekst"] for l in linjer_i(teksting, d)
                         if abs(l["rel_s"] - p["tid_s"]) <= VINDU_S)
        vindu_ord = _ord(vindu)
        for parti in p["partier"]:
            if parti not in partier_i_mote:
                ut.append(f"partiet {parti} var ikke i møtet")
                continue
            nevnt = any(re.search(rf"\b{re.escape(x)}\b", vindu) for x in PARTI_ORD.get(parti, [parti]))
            # «Krogstad-Wiborg» ropes opp som «Krostad Viborg».
            etternavn = {d for n, pa in rep.items() if pa == parti
                         for d in n.split()[-1].split("-") if len(d) >= 4}
            ropt_opp = any(_ligner(o, e) for o in vindu_ord for e in etternavn)
            if not (nevnt or ropt_opp):
                ut.append(f"{parti} er verken nevnt eller ropt opp nær {_klokke(p['tid_s'])} i del {p['del']}")
    return sorted(set(ut))


# --- Kjøring ---------------------------------------------------------------

def sjekksum(grunnlag_: str) -> str:
    h = hashlib.sha256()
    h.update(f"{MODELL}|{INNSATS}|{INSTRUKSJON_VERSJON}|{kommune.slug()}".encode())
    h.update(grunnlag_.encode())
    return h.hexdigest()[:16]


class Avvist(Exception):
    """Svaret kan ikke brukes: avslag, kuttet svar eller ugyldig JSON."""


def kall(klient, grunnlag_: str) -> tuple[dict, str, dict]:
    """Ett kall mot modellen, låst til SKJEMA, som i analyser_saker."""
    svar = klient.beta.messages.create(
        model=MODELL,
        max_tokens=MAKS_TOKENS,
        system=instruksjon(),
        messages=[{"role": "user", "content": grunnlag_}],
        output_config={"effort": INNSATS, "format": {"type": "json_schema", "schema": SKJEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if svar.stop_reason == "refusal":
        raise Avvist("avslått")
    if svar.stop_reason == "max_tokens":
        raise Avvist("svaret ble kuttet ved max_tokens")
    tekster = [b.text for b in svar.content if b.type == "text"]
    if not tekster:
        raise Avvist(f"ingen tekst i svaret (stop_reason {svar.stop_reason})")
    try:
        resultat = json.loads(tekster[-1])
    except json.JSONDecodeError as e:
        raise Avvist(f"ugyldig JSON: {e}") from e
    return resultat, svar.model, {"inn": svar.usage.input_tokens, "ut": svar.usage.output_tokens}


def gyldig(svar: dict, ds: list[dict]) -> bool:
    """Formen på svaret. Innholdet kontrolleres i bygget (avvik)."""
    if svar.get("ingen_debatt"):
        return True
    punkter = svar.get("punkter") or []
    if not (svar.get("oppsummering") or "").strip() or not 1 <= len(punkter) <= 6:
        return False
    deler = {d["del"] for d in ds}
    return all(p["del"] in deler and p["tid_s"] >= 0 and p["tekst"].strip() for p in punkter)


def kandidater(aar: int) -> list[tuple[dict, dict, dict, dict]]:
    """(sak, behandling, opptak, teksting) for politiske saker i tekstede opptak."""
    saker = {s["sak_id"]: s for s in kommune.alle_aar(lager_saker.les, aar)}
    behandlinger = {b["behandling_id"]: b for b in kommune.alle_aar(lager_voteringer.les, aar)}
    ut = []
    for o in lager_opptak.alle():
        if not o["teksting"] or o.get("fjernet"):
            continue
        t = lager_opptak.teksting(o["opptak_id"])
        if not t:
            continue
        for hid in dict.fromkeys(d["behandling_id"] for d in o["deler"] if d["behandling_id"]):
            b = behandlinger.get(hid)
            sak = b and saker.get(b["sak_id"])
            if sak and sak["sakstype"] == "PS" and not sak["formalia"] and not sak["skjermet_tittel"]:
                ut.append((sak, b, o, t))
    return ut


def _resultat(svar: dict, b: dict, o: dict, ds: list[dict], sum_: str, modell: str,
              forbruk: dict) -> dict:
    ingen = bool(svar["ingen_debatt"])
    return {
        "ingen_debatt": ingen,
        "oppsummering": "" if ingen else svar["oppsummering"].strip(),
        "antall_innlegg": 0 if ingen else int(svar["antall_innlegg"]),
        "punkter": [] if ingen else svar["punkter"],
        "behandling_id": b["behandling_id"],
        "opptak_id": o["opptak_id"],
        "sjekksum": sum_,
        "modell": modell,
        "innsats": INNSATS,
        "instruksjon_versjon": INSTRUKSJON_VERSJON,
        "dato": dt.date.today().isoformat(),
        "tokens": forbruk,
        # Regel 5: lenke til kilden, opptaket på starten av saken.
        "kilder": [{"tittel": "Opptaket av møtet",
                    "url": kommunetv.lenke(o["opptak_id"], ds[0]["bokmerke_id"])}],
    }


def kjor(aar: int, tort_lop: bool = False, maks: int = MAKS_PER_KJORING,
         bare: list[int] | None = None) -> None:
    alle = kandidater(aar)
    if bare:
        alle = [x for x in alle if x[1]["behandling_id"] in bare]
    klient = None
    teller = {"sendt": 0, "uendret": 0, "uten debatt": 0, "feil": 0, "utsatt": 0}
    tokens = {"inn": 0, "ut": 0}
    for sak, b, o, t in alle:
        tekst, ds = grunnlag(sak, b, o, t)
        sum_ = sjekksum(tekst)
        if (lager_opptak.debatt(b["behandling_id"]) or {}).get("sjekksum") == sum_:
            teller["uendret"] += 1
            continue
        # Bare opplesning og avstemning: ingen grunn til å spørre modellen.
        if sum(d["varighet_ms"] for d in ds) < KORT_S * 1000:
            teller["uten debatt"] += 1
            if not tort_lop:
                lager_opptak.lagre_debatt(_resultat(
                    {"ingen_debatt": True}, b, o, ds, sum_, "regel", {"inn": 0, "ut": 0}))
            continue
        if teller["sendt"] >= maks:
            teller["utsatt"] += 1
            continue
        teller["sendt"] += 1
        if tort_lop:
            print(f"ville analysert {b['saksnr']} ({len(tekst)} tegn): {sak['tittel'][:70]}")
            continue
        if klient is None:
            try:
                import anthropic  # noqa: PLC0415
            except ImportError:
                raise SystemExit("mangler pakken 'anthropic'. pip install -r krav.txt")
            klient = anthropic.Anthropic()
        try:
            svar, modell, forbruk = kall(klient, tekst)
        except Avvist as e:
            print(f"  {b['saksnr']}: {e}, hoppet over")
            teller["feil"] += 1
            continue
        except Exception as e:  # noqa: BLE001 - én feil i API-et skal ikke stoppe de andre
            print(f"  {b['saksnr']}: {type(e).__name__}, hoppet over")
            teller["feil"] += 1
            continue
        if not gyldig(svar, ds):
            print(f"  {b['saksnr']}: svaret har feil form, hoppet over")
            teller["feil"] += 1
            continue
        d = _resultat(svar, b, o, ds, sum_, modell, forbruk)
        feil = avvik(d, sak, b, o, t)
        print(f"  {b['saksnr']}: lagret" + (f", men holdes tilbake: {'; '.join(feil)}" if feil else ""))
        lager_opptak.lagre_debatt(d)
        tokens["inn"] += forbruk["inn"]
        tokens["ut"] += forbruk["ut"]
    print(", ".join(f"{k}: {v}" for k, v in teller.items()))
    if not tort_lop and not bare and teller["sendt"]:
        legg_til("debatt", {"sendt": teller["sendt"], "feil": teller["feil"],
                            "tokens_inn": tokens["inn"], "tokens_ut": tokens["ut"]})


def _finn(aar: int, behandling_id: int):
    for x in kandidater(aar):
        if x[1]["behandling_id"] == behandling_id:
            return x
    raise SystemExit(f"behandling {behandling_id} er ikke en politisk sak i et tekstet opptak")


def main() -> None:
    argv = kommune.fra_argv(sys.argv[1:])

    def verdi(flagg: str) -> str | None:
        return argv[argv.index(flagg) + 1] if flagg in argv else None

    aar = int(argv[0])
    if verdi("--vis"):
        tekst, ds = grunnlag(*_finn(aar, int(verdi("--vis"))))
        print(tekst)
        print(f"\n--- {len(tekst)} tegn, {len(ds)} deler, sjekksum {sjekksum(tekst)}")
    elif verdi("--kontroller") or verdi("--lagre"):
        # Svar skrevet utenfor kjøringen, for eksempel i en prøve. Med --lagre
        # lagres de som om modellen hadde svart, med modellen fra filen.
        fil = Path(verdi("--kontroller") or verdi("--lagre"))
        svar = json.loads(fil.read_text("utf-8"))
        for s in svar if isinstance(svar, list) else [svar]:
            sak, b, o, t = _finn(aar, s["behandling_id"])
            tekst, ds = grunnlag(sak, b, o, t)
            feil = avvik(s, sak, b, o, t) if gyldig(s, ds) else ["feil form"]
            print(f"{b['saksnr']}: " + ("består" if not feil else "holdes tilbake"))
            for f in feil:
                print(f"  - {f}")
            if verdi("--lagre") and gyldig(s, ds):
                lager_opptak.lagre_debatt(_resultat(
                    s, b, o, ds, sjekksum(tekst), s.get("modell") or "utenfor", {"inn": 0, "ut": 0}))
    else:
        bare = [int(x) for x in verdi("--saker").split(",")] if verdi("--saker") else None
        kjor(aar, "--tort-lop" in argv, int(verdi("--maks") or MAKS_PER_KJORING), bare)


if __name__ == "__main__":
    main()
