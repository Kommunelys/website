"""Hva som er nytt i en sak siden forrige varsel, i klarspråk (ADR-027).

Disse endringene gir varsel:
- et nytt steg i saksgangen, også når saken går tilbake til et utvalg den
  har vært i («igjen»);
- en ny dato for en behandling som kommer;
- et vedtak, eller en protokoll som blir publisert;
- ny status når saken er avgjort eller skal til kommunestyret;
- et sammendrag eller en debatt som blir publisert.

Status som bare følger av datoen («Venter på protokoll», «Protokoll ikke
publisert», «Til behandling»), gir ikke varsel alene: de kommer av seg selv
når møtet har vært, og sier ikke at noe har skjedd i saken.

Teksten bygger bare på tilstanden (varsel/tilstand.py), altså det som er
publisert. Ingen tekst fra sammendraget, og ingen navn utenom utvalgene.
"""

from __future__ import annotations

MANEDER = ("januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
           "september", "oktober", "november", "desember")

# Status som sier at noe har skjedd i saken.
VARSLES = ("Til kommunestyret", "Behandlet", "Vedtatt i kommunestyret", "Unntatt offentlighet")


def dato(verdi: str) -> str:
    """«2026-12-03T10:00» -> «3. desember 2026», som på nettstedet."""
    return f"{int(verdi[8:10])}. {MANEDER[int(verdi[5:7]) - 1]} {verdi[:4]}"


def _smaa(navn: str) -> str:
    return navn[:1].lower() + navn[1:]


def endringer(for_: dict | None, etter: dict | None, i_dag: str) -> list[str]:
    """Hendelsene fra for_ til etter. Uten for_ (saken er nettopp fulgt) eller
    etter (saken finnes ikke lenger) er det ingen."""
    if not for_ or not etter:
        return []
    ut: list[str] = []
    gamle = {x["hid"]: x for x in for_["steg"]}
    for i, x in enumerate(etter["steg"]):
        hvor = _smaa(x["utvalg"] or x["kode"] or "")
        naar = dato(x["dato"]) if x.get("dato") else ""
        g = gamle.get(x["hid"])
        if g is None:
            igjen = any(y["kode"] == x["kode"] for y in etter["steg"][:i])
            if x.get("dato") and x["dato"][:10] >= i_dag:
                ut.append(f"Saken skal opp i {hvor}{' igjen' if igjen else ''} {naar}".rstrip())
            elif not x["protokoll"]:
                # Med protokollen sier linjen under det samme.
                ut.append(f"Saken ble behandlet i {hvor}{' igjen' if igjen else ''} {naar}".rstrip())
        elif (x.get("dato") or "")[:10] != (g.get("dato") or "")[:10] and x.get("dato") \
                and x["dato"][:10] >= i_dag:
            ut.append(f"Ny dato i {hvor}: {naar}")
        if x["vedtak"] and not (g or {}).get("vedtak"):
            ut.append(f"Vedtaket i {hvor} {naar} er publisert".replace("  ", " "))
        elif x["protokoll"] and not (g or {}).get("protokoll"):
            ut.append(f"Protokollen fra {hvor} {naar} er publisert".replace("  ", " "))
    if etter["status"] != for_["status"] and etter["status"] in VARSLES:
        ut.append(f"Ny status: {etter['status']}")
    if etter["sammendrag"] and not for_["sammendrag"]:
        ut.append("Sammendraget er publisert")
    utvalg = {x["hid"]: _smaa(x["utvalg"] or x["kode"] or "") for x in etter["steg"]}
    for hid in etter["debatt"]:
        if hid not in for_["debatt"]:
            ut.append(f"Debatten i {utvalg.get(hid, 'møtet')} er oppsummert")
    return ut
