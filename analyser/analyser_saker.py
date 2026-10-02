"""Lager sammendrag og tagger med Claude. SKJELETT — ikke kjørt ennå.

ADR-002: stemmegivning tolkes ikke her. Det gjøres i tolk/.
ADR-006: analysen føres på det minste dokumentet som inneholder svaret.
         Møteinnkallingen sendes aldri inn.

Kjører én gang per sak, ikke per kjøring. Resultatet lagres med modellversjon
og en sjekksum av kildeteksten, og en sak sendes bare inn på nytt når kilden
eller instruksjonen faktisk har endret seg.

    python -m analyser.analyser_saker
    python -m analyser.analyser_saker --tort-lop   # vis hva som ville blitt gjort
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
SAKER = ROT / "data" / "saker"
TEKST = ROT / "data" / "tekst"
ANALYSE = ROT / "data" / "analyse"

MODELL = "claude-sonnet-4-5"
# Endres denne, må alt analyseres på nytt. Derfor inngår den i sjekksummen.
INSTRUKSJON_VERSJON = 1

# Faste tagger. Lar man modellen finne på egne, blir filtrene ubrukelige
# etter et halvt år.
TAGGER = [
    "Økonomi", "Plan og areal", "Landbruk", "Skole og barnehage",
    "Helse og omsorg", "Vei og trafikk", "Kultur og idrett", "Næring",
    "Klima og miljø", "Eierskap og selskaper", "Folkevalgte", "Klager",
    "Regionalt samarbeid", "Høring", "Organisasjon",
]

INSTRUKSJON = f"""Du oppsummerer en kommunal sak for innbyggere i Steinkjer.

Regler:
- Bruk bare innhold som står i dokumentene under. Fyll aldri ut fra generell
  kunnskap.
- Ikke vurder om vedtaket er godt eller dårlig.
- Navngitte politikere omtales bare med det de har gjort i møtet: fremmet
  forslag, stemt, stilt spørsmål.
- Navn på privatpersoner skal ikke med, selv om de står i sakstittelen.
- Er grunnlaget for tynt til et dekkende sammendrag, sett "usikker": true og
  la "sammendrag" stå tom.
- Skriv klarspråk, norsk bokmål. Korte setninger.

Tagger må velges fra denne listen, to til tre stykker:
{", ".join(TAGGER)}

Svar med JSON som følger dette skjemaet, og ingenting annet:
{{
  "tittel_klarsprak": "spørsmålet saken svarer på, én linje",
  "sammendrag": "3-5 linjer om hva saken gjelder og hva som ble bestemt",
  "betydning": "én setning om hva dette betyr for en innbygger",
  "tagger": ["...", "..."],
  "utfall": "vedtatt | falt | utsatt | ikke behandlet",
  "uenighet": "én setning om hva uenigheten gjaldt, eller tom streng",
  "usikker": false
}}"""


def sjekksum(*deler: str) -> str:
    h = hashlib.sha256()
    h.update(f"{MODELL}|{INSTRUKSJON_VERSJON}".encode())
    for d in deler:
        h.update((d or "").encode())
    return h.hexdigest()[:16]


def _les_tekst(dokument_id: int | None) -> str:
    """Tekst trukket ut av et dokument. Tom streng hvis vi ikke har den."""
    if not dokument_id:
        return ""
    sti = TEKST / f"{dokument_id}.txt"
    return sti.read_text(encoding="utf-8") if sti.exists() else ""


def kildetekst(sak: dict) -> str:
    """Setter sammen det modellen skal lese.

    ADR-006: saksframlegget for den enkelte saken, ikke møteinnkallingen.
    Lange dokumenter kuttes; innholdet ligger først og i vedtaksdelen.
    """
    deler = [f"SAKSTITTEL: {sak['tittel']}"]

    gang = " -> ".join(
        f"{s['utvalg']} {s['dato'][:10]} ({s['saksnr']})" for s in sak["saksgang"]
    )
    deler.append(f"SAKSGANG: {gang}")

    framlegg = _les_tekst((sak.get("saksframlegg") or {}).get("dokument_id"))
    if framlegg:
        deler.append("SAKSFRAMLEGG:\n" + framlegg[:20000])

    for steg in sak["saksgang"]:
        if steg["protokoll_publisert"] and not steg["protokoll_skjermet"]:
            vedtak = _les_tekst(steg["behandling_id"])
            if vedtak:
                deler.append(
                    f"VEDTAK I {steg['utvalg']} {steg['dato'][:10]}:\n"
                    + vedtak[:8000]
                )

    if sak.get("vedlegg"):
        titler = ", ".join(v["tittel"] or "uten tittel" for v in sak["vedlegg"])
        deler.append(f"VEDLEGG (ikke lest): {titler}")

    return "\n\n".join(deler)


def analyser(klient, sak: dict) -> dict:
    """Ett kall mot modellen. Krever anthropic-pakken."""
    svar = klient.messages.create(
        model=MODELL,
        max_tokens=1500,
        system=INSTRUKSJON,
        messages=[{"role": "user", "content": kildetekst(sak)}],
    )
    tekst = svar.content[0].text.strip()
    if tekst.startswith("```"):
        tekst = tekst.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(tekst)


def gyldig(a: dict) -> bool:
    """Kontroller skjemaet før noe lagres."""
    if not isinstance(a, dict):
        return False
    for felt in ("tittel_klarsprak", "sammendrag", "tagger", "utfall", "usikker"):
        if felt not in a:
            return False
    if not isinstance(a["tagger"], list) or not a["tagger"]:
        return False
    if any(t not in TAGGER for t in a["tagger"]):
        return False
    return True


def kjor(aar: int, tort_lop: bool = False) -> None:
    saker = json.loads((SAKER / f"{aar}.json").read_text(encoding="utf-8"))
    ANALYSE.mkdir(parents=True, exist_ok=True)

    klient = None
    if not tort_lop:
        try:
            import anthropic  # noqa: PLC0415
        except ImportError:
            raise SystemExit("mangler pakken 'anthropic'. pip install -r krav.txt")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("mangler ANTHROPIC_API_KEY")
        klient = anthropic.Anthropic()

    nye = uendret = hoppet = 0
    for sak in saker:
        if sak["formalia"] or sak["sakstype"] != "PS" or sak["skjermet_tittel"]:
            hoppet += 1
            continue

        kilde = kildetekst(sak)
        sum_ = sjekksum(kilde)
        sti = ANALYSE / f"{sak['sak_id']}.json"

        if sti.exists():
            gammel = json.loads(sti.read_text(encoding="utf-8"))
            if gammel.get("sjekksum") == sum_:
                uendret += 1
                continue

        nye += 1
        if tort_lop:
            print(f"ville analysert {sak['sak_id']}: {sak['tittel'][:70]}")
            continue

        resultat = analyser(klient, sak)
        if not gyldig(resultat):
            print(f"  ugyldig svar for {sak['sak_id']}, hoppet over")
            continue

        resultat.update({
            "sak_id": sak["sak_id"],
            "sjekksum": sum_,
            "modell": MODELL,
            "instruksjon_versjon": INSTRUKSJON_VERSJON,
        })
        sti.write_text(
            json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    print(f"nye/endrede: {nye}, uendret: {uendret}, utenfor scope: {hoppet}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    import datetime as dt  # noqa: PLC0415
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar, tort_lop="--tort-lop" in sys.argv)


if __name__ == "__main__":
    main()
