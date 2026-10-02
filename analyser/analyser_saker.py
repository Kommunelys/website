"""Lager sammendrag og tagger med Claude. Fase 2: ikke slått på i arbeidsflyten ennå.

ADR-002: stemmetall tolkes ikke her. Modellen får resultatet av hver votering
fra data/voteringer/, tolket med kode, og hvilke partier som sto på hver side,
men ikke stemmetall eller navn. Den skal heller ikke skrive dem; nettstedet
viser stemmene fra protokollen. Voteringer som er holdt tilbake (ADR-015),
sendes ikke inn.
ADR-006: analysen føres på det minste dokumentet som inneholder svaret.
         Møteinnkallingen sendes aldri inn.
ADR-013: saksframlegget sendes delt ved de faste overskriftene, uten avkorting.

Kjører én gang per sak, ikke per kjøring. Resultatet lagres med modell,
instruksjonsversjon og en sjekksum av grunnlaget, og en sak sendes bare inn på
nytt når grunnlaget eller instruksjonen faktisk har endret seg. Høyst
MAKS_PER_KJORING saker sendes inn per kjøring, så en ny instruksjonsversjon
eller en feil i sjekksummen ikke kan sende hele året på én gang.

    python -m analyser.analyser_saker 2026 --tort-lop    # vis hva som ville blitt sendt
    python -m analyser.analyser_saker 2026 --maks 10     # høyst 10 saker
    python -m analyser.analyser_saker 2026 --vis 8356    # skriv ut grunnlaget for én sak
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from tolk.bygg_avvik import holdt_tilbake
from tolk.saksframlegg import del_opp

ROT = Path(__file__).resolve().parent.parent
SAKER = ROT / "data" / "saker"
TEKST = ROT / "data" / "tekst"
VOTERINGER = ROT / "data" / "voteringer"
ANALYSE = ROT / "data" / "analyse"

MODELL = "claude-opus-5"
INNSATS = "high"
MAKS_TOKENS = 16000
MAKS_PER_KJORING = 25
# Endres instruksjonen eller skjemaet, må alt analyseres på nytt. Derfor inngår
# versjonen i sjekksummen.
INSTRUKSJON_VERSJON = 2

# Faste tagger. Lar man modellen finne på egne, blir filtrene ubrukelige
# etter et halvt år.
TAGGER = [
    "Økonomi", "Plan og areal", "Landbruk", "Skole og barnehage",
    "Helse og omsorg", "Vei og trafikk", "Kultur og idrett", "Næring",
    "Klima og miljø", "Eierskap og selskaper", "Folkevalgte", "Klager",
    "Regionalt samarbeid", "Høring", "Organisasjon",
]
UTFALL = ["vedtatt", "falt", "utsatt", "ikke avgjort ennå"]

SKJEMA = {
    "type": "object",
    "properties": {
        "tittel_klarsprak": {"type": "string"},
        "sammendrag": {"type": "string"},
        "betydning": {"type": "string"},
        "tagger": {"type": "array", "items": {"type": "string", "enum": TAGGER}},
        "utfall": {"type": "string", "enum": UTFALL},
        "uenighet": {"type": "string"},
        "usikker": {"type": "boolean"},
    },
    "required": ["tittel_klarsprak", "sammendrag", "betydning", "tagger",
                 "utfall", "uenighet", "usikker"],
    "additionalProperties": False,
}

INSTRUKSJON = """Du forklarer en politisk sak i Steinkjer kommune for innbyggere uten forkunnskaper. Grunnlaget er dokumentene fra kommunens innsynsportal i meldingen: saksframlegget, vedtakene og voteringene.

- Bruk bare det som står i dokumentene. Fyll aldri ut med generell kunnskap.
- Ikke vurder om forslaget eller vedtaket er godt eller dårlig.
- Skriv ikke navn på privatpersoner, selv om de står i dokumentene. Folkevalgte omtales bare i sin rolle, med det de gjorde i saken.
- Skriv ikke stemmetall eller hvem som stemte hva. Nettstedet viser stemmene fra protokollen ved siden av teksten. I «uenighet» beskriver du hva uenigheten gjaldt og hvilke partier som sto på hver side, slik det går fram av voteringene.
- Er saken ikke avgjort ennå, beskriv hva som skal avgjøres og hva kommunedirektøren foreslår.
- Er grunnlaget for tynt til en dekkende forklaring, sett «usikker» til true og la «sammendrag» stå tomt.
- Skriv klarspråk på norsk bokmål, med korte setninger.

Feltene:
- tittel_klarsprak: spørsmålet saken svarer på, på én linje
- sammendrag: tre til fem setninger om hva saken gjelder og hva som ble bestemt eller foreslått
- betydning: én setning om hva dette betyr for innbyggerne
- tagger: to eller tre tema fra listen
- utfall: hvordan saken endte i siste møte som er holdt
- uenighet: én setning, eller tom streng hvis vedtakene var enstemmige eller saken ikke er avgjort"""


class Avvist(Exception):
    """Svaret kan ikke brukes: avslag, kuttet svar eller ugyldig JSON."""


def _les(sti: Path, standard):
    return json.loads(sti.read_text(encoding="utf-8")) if sti.exists() else standard


def sjekksum(*deler: str) -> str:
    h = hashlib.sha256()
    h.update(f"{MODELL}|{INNSATS}|{INSTRUKSJON_VERSJON}".encode())
    for d in deler:
        h.update((d or "").encode())
    return h.hexdigest()[:16]


def _tekst(navn: str | int | None) -> str:
    """Tekst trukket ut av et dokument. Tom streng hvis vi ikke har den."""
    if not navn:
        return ""
    sti = TEKST / f"{navn}.txt"
    return sti.read_text(encoding="utf-8") if sti.exists() else ""


def vedtaksdel(protokoll: str) -> str:
    """Selve vedtaket: teksten etter linjen «Vedtak» i saksprotokollen.

    Delen før, «Behandling», har navnelistene; den sendes ikke. Målt
    3.10.2026: 372 av 375 protokoller har én slik linje, de tre andre har
    ikke noe vedtak.
    """
    linjer = protokoll.splitlines()
    treff = [i for i, l in enumerate(linjer) if re.fullmatch(r"\s*Vedtak:?\s*", l)]
    return "\n".join(linjer[treff[-1] + 1:]).strip() if treff else ""


def _sider(v: dict) -> dict[str, list[str]]:
    """Partienes standpunkt i én votering: for, mot eller delt. Uten tall."""
    teller: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for side, navn in (("for", v["for"]), ("mot", v["mot"])):
        for n in navn:
            teller[v["partier"].get(n, "?")][side] += 1
    ut = {"for": [], "mot": [], "delt": []}
    for parti, c in sorted(teller.items()):
        ut["for" if not c["mot"] else "mot" if not c["for"] else "delt"].append(parti)
    return ut


def _votering(v: dict) -> str:
    forslag = re.sub(r"\s+", " ", v["tekst"] or "").strip()
    av = "innstillingen" if v["type"] == "innstilling" else (v["parti"] or v["type"])
    if v["enstemmig"]:
        return f'<votering resultat="enstemmig vedtatt">\n{forslag}\n</votering>'
    linjer = [f"Forslag fremmet av: {av}", f"Forslag: {forslag}"]
    if v["alternativer"]:
        for a in v["alternativer"]:
            partier = sorted({v["partier"].get(n, "?") for n in a["navn"]})
            linjer.append(f"Partier som stemte for forslag {a['forslag']}: {', '.join(partier)}")
    else:
        s = _sider(v)
        linjer += [f"Partier for: {', '.join(s['for']) or 'ingen'}",
                   f"Partier mot: {', '.join(s['mot']) or 'ingen'}"]
        if s["delt"]:
            linjer.append(f"Partier som delte seg: {', '.join(s['delt'])}")
    return f'<votering resultat="{v["resultat_tekst"]}">\n' + "\n".join(linjer) + "\n</votering>"


def kildetekst(sak: dict, voteringer: dict[int, dict],
               stopp: dict[tuple[int, int], list]) -> tuple[str, list[dict]]:
    """Det modellen skal lese, og kildene det bygger på.

    ADR-006: saksframlegget for den enkelte saken, ikke møteinnkallingen.
    """
    i_dag = dt.date.today().isoformat()
    gang = "\n".join(
        f"- {s['utvalg']} {s['dato'][:10]} {s['saksnr']}"
        + (" (kommende møte)" if s["dato"][:10] >= i_dag else "")
        for s in sak["saksgang"])
    deler = [f"<sak>\nTittel: {sak['tittel']}\nStatus: {sak['status']}\nSaksgang:\n{gang}\n</sak>"]
    kilder = []

    f = sak.get("saksframlegg") or {}
    framlegg = _tekst(f.get("dokument_id"))
    if framlegg:
        avsnitt = del_opp(framlegg)
        if avsnitt:
            innhold = "\n".join(f"<{k}>\n{t}\n</{k}>" for k, t in avsnitt.items()
                                if k != "innledning" and t)
        else:
            innhold = framlegg.strip()
        deler.append(f"<saksframlegg>\n{innhold}\n</saksframlegg>")
        kilder.append({"tittel": "Saksframlegg", "url": f["url"]})

    for steg in sak["saksgang"]:
        if not steg["url_vedtak"]:
            continue  # skjermet eller ikke publisert
        vedtak = vedtaksdel(_tekst(steg["behandling_id"]))
        b = voteringer.get(steg["behandling_id"], {"voteringer": []})
        # Voteringer med avvik som ikke er godkjent, holdes utenfor (ADR-015).
        vs = [_votering(v) for v in b["voteringer"]
              if (steg["behandling_id"], v["nr"]) not in stopp]
        if not vedtak and not vs:
            continue
        hode = f'utvalg="{steg["utvalg"]}" dato="{steg["dato"][:10]}" saksnr="{steg["saksnr"]}"'
        deler.append(f"<vedtak {hode}>\n{vedtak}\n</vedtak>" if vedtak else "")
        if vs:
            deler.append(f"<voteringer {hode}>\n" + "\n".join(vs) + "\n</voteringer>")
        kilder.append({"tittel": f"Vedtak i {steg['utvalg']} {steg['dato'][:10]}",
                       "url": steg["url_vedtak"]})

    return "\n\n".join(d for d in deler if d), kilder


def analyser(klient, kilde: str) -> tuple[dict, str]:
    """Ett kall mot modellen. Gir (svaret, modellen som faktisk svarte).

    Svaret er låst til SKJEMA. Avslår modellens sikkerhetsfiltre, kjøres samme
    forespørsel på Anthropics anbefalte reservemodell (fallbacks: "default").
    """
    svar = klient.beta.messages.create(
        model=MODELL,
        max_tokens=MAKS_TOKENS,
        system=INSTRUKSJON,
        messages=[{"role": "user", "content": kilde}],
        output_config={"effort": INNSATS,
                       "format": {"type": "json_schema", "schema": SKJEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if svar.stop_reason == "refusal":
        raise Avvist(f"avslått ({getattr(svar.stop_details, 'category', None)})")
    if svar.stop_reason == "max_tokens":
        raise Avvist("svaret ble kuttet ved max_tokens")
    tekster = [b.text for b in svar.content if b.type == "text"]
    if not tekster:
        raise Avvist(f"ingen tekst i svaret (stop_reason {svar.stop_reason})")
    try:
        return json.loads(tekster[-1]), svar.model
    except json.JSONDecodeError as e:
        raise Avvist(f"ugyldig JSON: {e}") from e


def gyldig(a: dict) -> bool:
    """Kontroller svaret før noe lagres. Skjemaet sikrer formen; dette sikrer innholdet."""
    if not isinstance(a, dict):
        return False
    if not 2 <= len(a.get("tagger") or []) <= 3:
        return False
    if any(t not in TAGGER for t in a["tagger"]) or a.get("utfall") not in UTFALL:
        return False
    if not a.get("usikker") and not (a.get("sammendrag") or "").strip():
        return False
    return bool((a.get("tittel_klarsprak") or "").strip())


def _kandidater(saker: list[dict]) -> list[dict]:
    """Politiske saker med åpen tittel, de nyeste først."""
    ut = [s for s in saker
          if s["sakstype"] == "PS" and not s["formalia"] and not s["skjermet_tittel"]]
    return sorted(ut, key=lambda s: s["saksgang"][-1]["dato"], reverse=True)


def kjor(aar: int, tort_lop: bool = False, maks: int = MAKS_PER_KJORING,
         vis: int | None = None) -> None:
    saker = json.loads((SAKER / f"{aar}.json").read_text(encoding="utf-8"))
    voteringer = {b["behandling_id"]: b for b in _les(VOTERINGER / f"{aar}.json", [])}
    stopp, _ = holdt_tilbake(aar)

    if vis is not None:
        sak = next((s for s in saker if s["sak_id"] == vis
                    or any(st["behandling_id"] == vis for st in s["saksgang"])), None)
        if not sak:
            raise SystemExit(f"fant ingen sak med ID {vis}")
        kilde, kilder = kildetekst(sak, voteringer, stopp)
        print(kilde)
        print(f"\n--- {len(kilde)} tegn. Kilder: {json.dumps(kilder, ensure_ascii=False)}")
        return

    ANALYSE.mkdir(parents=True, exist_ok=True)
    klient = None
    if not tort_lop:
        try:
            import anthropic  # noqa: PLC0415
        except ImportError:
            raise SystemExit("mangler pakken 'anthropic'. pip install -r krav.txt")
        klient = anthropic.Anthropic()

    teller = collections.Counter()
    tegn = 0
    for sak in _kandidater(saker):
        kilde, kilder = kildetekst(sak, voteringer, stopp)
        if not kilder:
            teller["uten grunnlag"] += 1
            continue  # verken saksframlegg eller vedtak å forklare ut fra

        sum_ = sjekksum(kilde)
        sti = ANALYSE / f"{sak['sak_id']}.json"
        if _les(sti, {}).get("sjekksum") == sum_:
            teller["uendret"] += 1
            continue
        if teller["sendt"] >= maks:
            teller["utsatt til neste kjøring"] += 1
            continue
        teller["sendt"] += 1

        if tort_lop:
            tegn += len(kilde)
            print(f"ville analysert {sak['sak_id']} ({len(kilde)} tegn): {sak['tittel'][:70]}")
            continue

        try:
            resultat, modell = analyser(klient, kilde)
        except anthropic.RateLimitError:
            # SDK-en har alt prøvd på nytt. Flere kall nå vil også bli avvist.
            print(f"  {sak['sak_id']}: rate limit, stopper kjøringen")
            teller["feil"] += 1
            break
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise SystemExit(f"API-nøkkelen virker ikke: {e}") from e
        except anthropic.APIStatusError as e:
            print(f"  {sak['sak_id']}: API-feil {e.status_code}, hoppet over")
            teller["feil"] += 1
            continue
        except anthropic.APIConnectionError:
            print(f"  {sak['sak_id']}: nettverksfeil, hoppet over")
            teller["feil"] += 1
            continue
        except Avvist as e:
            print(f"  {sak['sak_id']}: {e}, hoppet over")
            teller["feil"] += 1
            continue

        if not gyldig(resultat):
            print(f"  {sak['sak_id']}: svaret besto ikke kontrollen, hoppet over")
            teller["feil"] += 1
            continue

        resultat.update({
            "sak_id": sak["sak_id"],
            "sjekksum": sum_,
            "modell": modell,
            "innsats": INNSATS,
            "instruksjon_versjon": INSTRUKSJON_VERSJON,
            "dato": dt.date.today().isoformat(),
            # CLAUDE.md regel 5: uten kildelenke publiseres det ikke.
            "kilder": kilder,
        })
        sti.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")

    print(", ".join(f"{k}: {v}" for k, v in teller.items()))
    if tort_lop and teller["sendt"]:
        print(f"grunnlaget er {tegn} tegn til sammen, i snitt {tegn // teller['sendt']} per sak")


def main() -> None:
    argv = sys.argv[1:]
    med_verdi = ("--maks", "--vis")

    def verdi(flagg: str) -> int | None:
        return int(argv[argv.index(flagg) + 1]) if flagg in argv else None

    # Året er det første argumentet som verken er et flagg eller verdien til et.
    aar = next((int(a) for i, a in enumerate(argv)
                if not a.startswith("--") and (i == 0 or argv[i - 1] not in med_verdi)),
               dt.date.today().year)
    maks = verdi("--maks")
    kjor(aar, tort_lop="--tort-lop" in argv,
         maks=MAKS_PER_KJORING if maks is None else maks, vis=verdi("--vis"))


if __name__ == "__main__":
    main()
