"""Setter sammen behandlinger til saker, og utleder status.

ADR-003: samme sak får nytt saksnummer i hvert utvalg. `AdditionalDmbHandlings`
oppgir koblingene, og kjeden bygges med disjunkte mengder.

Leser rådataene og skriver møtene og sakene (lager.raa, lager.saker).

    python -m tolk.bygg_saker 2026
    python -m tolk.bygg_saker 2026 --fra-fil gammel_raadata.json
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import sys
from pathlib import Path

import lager
from hent import portal
from lager import raa as raadata
from lager import saker as lager_saker

# Saker som ikke er politikk, men møteteknikk. Holdes utenfor tellingene.
FORMALIA = (
    "godkjenning av innkalling",
    "godkjenning av møteinnkalling",
    "godkjenning av sakliste",
    "godkjenning av saksliste",
    "godkjenning av protokoll",
    "gjennomgang av protokoll",
    "eventuelt",
    "referatsaker",
    "orienteringssaker",
)


def les_raa(aar: int, fra_fil: str | None = None) -> list[dict]:
    """Møter med behandlinger, fra rådataene eller fra en eldre samlefil."""
    if fra_fil:
        gammel = json.loads(Path(fra_fil).read_text(encoding="utf-8"))
        return [
            {"mote": m["mote"], "detaljer": m["detaljer"],
             "behandlinger": m.get("saker") or m.get("behandlinger") or []}
            for m in gammel
        ]

    moter = raadata.moter(aar)
    if moter is None:
        raise SystemExit(f"fant ingen møter for {aar}. Kjør hent.hent_moter først.")
    return moter


class Grupper:
    """Disjunkte mengder: binder behandlinger sammen til én sak."""

    def __init__(self) -> None:
        self._far: dict[int, int] = {}

    def finn(self, x: int) -> int:
        self._far.setdefault(x, x)
        while self._far[x] != x:
            self._far[x] = self._far[self._far[x]]
            x = self._far[x]
        return x

    def slaa_sammen(self, a: int, b: int) -> None:
        ra, rb = self.finn(a), self.finn(b)
        if ra != rb:
            self._far[rb] = ra


def _er_formalia(tittel: str) -> bool:
    t = tittel.lower().strip()
    return any(t.startswith(f) for f in FORMALIA)


def _steg(bid: int, kjent: dict, ukjent: dict) -> dict:
    """Ett ledd i saksgangen: ett utvalg, én dato, ett saksnummer."""
    if bid in kjent:
        mote, b = kjent[bid]
        utvalg = (b.get("Dmb") or {}).get("ShortCode") or mote["UT_NAVN"]
        navn = (b.get("Dmb") or {}).get("Name") or mote["UT_NAVN"]
        dato, mid = mote["MO_START"][:16], mote["MO_ID"]
        publisert = bool(b.get("ProtocolPublished"))
        skjermet = bool(b.get("ProtocolRestricted"))
    else:
        b = ukjent[bid]
        m = b.get("Meeting") or {}
        d = b.get("Dmb") or {}
        utvalg, navn = d.get("ShortCode"), d.get("Name")
        dato, mid = (m.get("StartDate") or "")[:16], m.get("Id")
        publisert = bool(b.get("ProtocolPublished"))
        skjermet = bool(b.get("ProtocolRestricted"))

    steg = {
        "behandling_id": bid,
        "dato": dato,
        "utvalg": utvalg,
        "utvalg_navn": navn,
        "mote_id": mid,
        "saksnr": f"{b['MeetingCaseTypeId']} {b['SequenceNumber']}/{b['Year']}",
        "protokoll_publisert": publisert,
        "protokoll_skjermet": skjermet,
        "hentet": bid in kjent,
    }
    # ADR-005/kvalitet: adressen oppgis bare når vedtaket faktisk er åpent.
    steg["url_vedtak"] = (
        portal.url_saksprotokoll(bid) if publisert and not skjermet else None
    )
    steg["url_mote"] = portal.url_mote_i_portalen(mid) if mid else None
    return steg


# Etter så mange dager uten protokoll er det ikke lenger riktig å si at saken
# venter: i noen utvalg legges protokollen aldri ut i portalen (Galleri
# Widegren 0 av 23 behandlinger i 2026, arbeidsutvalget i regionrådet 3 av 22).
VENTEGRENSE_DAGER = 30


def _status(steg: list[dict], i_dag: str) -> str:
    kommende = [s for s in steg if s["dato"][:10] >= i_dag]
    holdt = [s for s in steg if s["dato"][:10] < i_dag]
    if kommende:
        return ("Til kommunestyret" if kommende[0]["utvalg"] == "KS"
                else "Til behandling")
    if holdt and holdt[-1]["protokoll_publisert"]:
        return ("Vedtatt i kommunestyret" if holdt[-1]["utvalg"] == "KS"
                else "Behandlet")
    if holdt and holdt[-1]["protokoll_skjermet"]:
        return "Unntatt offentlighet"
    if holdt and (dt.date.fromisoformat(i_dag)
                  - dt.date.fromisoformat(holdt[-1]["dato"][:10])).days > VENTEGRENSE_DAGER:
        return "Protokoll ikke publisert"
    return "Venter på protokoll"


def kjor(aar: int, fra_fil: str | None = None) -> dict:
    i_dag = lager.i_dag()
    raa = les_raa(aar, fra_fil)

    kjent: dict[int, tuple[dict, dict]] = {}
    for m in raa:
        for b in m["behandlinger"]:
            kjent[b["Id"]] = (m["mote"], b)

    # Bind behandlinger sammen til saker.
    g = Grupper()
    ukjent: dict[int, dict] = {}
    for bid, (_, b) in kjent.items():
        g.finn(bid)
        for a in b.get("AdditionalDmbHandlings") or []:
            g.slaa_sammen(bid, a["Id"])
            if a["Id"] not in kjent:
                ukjent[a["Id"]] = a

    grupper = collections.defaultdict(list)
    for bid in list(kjent) + list(ukjent):
        grupper[g.finn(bid)].append(bid)

    saker = []
    for ider in grupper.values():
        hentede = [i for i in ider if i in kjent]
        if not hentede:
            continue
        forste = min(hentede, key=lambda i: kjent[i][0]["MO_START"])
        _, b = kjent[forste]

        steg = sorted((_steg(i, kjent, ukjent) for i in ider),
                      key=lambda s: s["dato"])

        journalpost = None
        for i in hentede:
            r = kjent[i][1].get("RegistryEntry")
            if r:
                journalpost = r
                break

        hoved, vedlegg = None, []
        for d in (journalpost or {}).get("Documents") or []:
            bes = d.get("DocumentDescription") or {}
            if not bes.get("IsPublished"):
                continue  # skjermet: hverken lenke eller analyse
            post = {
                "dokument_id": bes["Id"],
                "tittel": bes.get("DocumentTitle"),
                "format": bes.get("FileFormatId"),
                "url": portal.url_dokument(journalpost["Id"], bes["Id"]),
            }
            if d.get("IsMainDocument"):
                hoved = post
            else:
                vedlegg.append(post)

        tittel = b.get("Title")
        saker.append({
            "sak_id": min(hentede),
            "tittel": tittel or "(Unntatt offentlighet)",
            "skjermet_tittel": tittel is None,
            "sakstype": b["MeetingCaseTypeId"],
            "formalia": _er_formalia(tittel or ""),
            "status": _status(steg, i_dag),
            "saksgang": steg,
            "til_kommunestyret": any(s["utvalg"] == "KS" for s in steg),
            "saksframlegg": hoved,
            "vedlegg": vedlegg,
        })

    saker.sort(key=lambda s: s["saksgang"][0]["dato"])
    lager_saker.lagre(aar, saker)

    moter = [{
        "mote_id": m["mote"]["MO_ID"],
        "dato": m["mote"]["MO_START"][:16],
        "slutt": (m["mote"]["MO_SLUTT"] or "")[11:16],
        "utvalg": (m["detaljer"].get("DMB") or {}).get("ShortCode"),
        "utvalg_navn": m["mote"]["UT_NAVN"],
        "sted": m["mote"].get("MO_STED"),
        "rom": m["mote"].get("MO_ROM"),
        "antall_saker": len(m["behandlinger"]),
        "dokumenter": [{
            "tittel": (d.get("Title") or "").strip(),
            "type": d["DmbDocumentTypeId"],
            "url": portal.url_motedokument(
                m["mote"]["MO_ID"], d["DmbDocumentTypeId"], d["Id"]),
        } for d in m["detaljer"].get("MeetingDocuments") or []
            if not d.get("IsRestricted")],
        "url": portal.url_mote_i_portalen(m["mote"]["MO_ID"]),
    } for m in raa]
    moter.sort(key=lambda m: m["dato"])
    lager_saker.lagre_moter(aar, moter)

    politiske = [s for s in saker if s["sakstype"] == "PS" and not s["formalia"]]
    oppsummering = {
        "moter": len(moter),
        "behandlinger": len(kjent),
        "saker": len(saker),
        "politiske_saker": len(politiske),
        "uhentede_koblinger": len(ukjent),
        "status": dict(collections.Counter(s["status"] for s in politiske)),
    }
    print(json.dumps(oppsummering, ensure_ascii=False, indent=1))
    return oppsummering


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    fra_fil = None
    if "--fra-fil" in sys.argv:
        fra_fil = sys.argv[sys.argv.index("--fra-fil") + 1]
    kjor(aar, fra_fil)


if __name__ == "__main__":
    main()
