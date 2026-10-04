"""Laster ned saksframlegg, saksprotokoller og møteprotokoller og lagrer teksten.

ADR-005: dokumentene lagres ikke i repoet. Bare teksten (lager.tekst), med
         møteprotokollene etter møte-ID.
ADR-006: møteinnkallingen lastes aldri ned for analyse. Den er alle
         saksframleggene limt sammen, over 350 sider for kommunestyret.
         Møteprotokollen hentes bare for oppmøtelisten (ADR-008).
ADR-013: poppler for PDF. Protokoller tas med `pdftotext -layout`, fordi
         oppmøtelisten er kolonnebasert. Saksframlegg tas uten -layout, slik at
         de faste overskriftene står på egne linjer (tolk/saksframlegg.py).
         Noen møter har protokollene bare i Word; de leses med
         standardbiblioteket. Dokumenter uten tekstlag lagres ikke.

Dette skriptet er også måleverktøyet: `--mal` laster ned og rapporterer
sidetall, tegn per side og andel uten tekstlag, uten å lagre tekst.

    python -m hent.hent_dokumenter 2026 --mal      # mål samlingen først
    python -m hent.hent_dokumenter 2026            # hent og lagre tekst
    python -m hent.hent_dokumenter 2026 --vedlegg  # ta med vedlegg
"""

from __future__ import annotations

import collections
import io
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from lager import konfig
from lager import raa as raadata
from lager import saker as lager_saker
from lager import tekst as lager_tekst
from tolk import saksframlegg

from . import portal

# Under dette mangler dokumentet tekstlag og er trolig skannet. Målt 2.10.2026:
# det skannede dokumentet har 1 tegn per side, de korteste protokollene 82.
MIN_TEGN_PER_SIDE = 20

# Målt 2.10.2026: rundt to sekunder per dokument, pausen medregnet.
SEKUND_PER_DOKUMENT = 2

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def sjekk_poppler() -> None:
    """ADR-013: `pdftotext` fra Git for Windows er xpdf. Den skriver Latin-1 og
    mangler `pdfinfo`, og gir feil tekst uten å si fra."""
    for verktoy in ("pdftotext", "pdfinfo"):
        if not shutil.which(verktoy):
            raise SystemExit(f"fant ikke {verktoy}. Installer poppler (ADR-013).")
    v = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    if "poppler" not in (v.stdout + v.stderr).lower():
        raise SystemExit(f"{shutil.which('pdftotext')} er ikke poppler. "
                         "Legg poppler først i PATH (ADR-013).")


def til_tekst(pdf: Path, behold_kolonner: bool) -> tuple[str, int]:
    """PDF -> (tekst, sidetall). Krever poppler."""
    ut = pdf.with_suffix(".txt")
    flagg = ["-layout"] if behold_kolonner else []
    subprocess.run(["pdftotext", *flagg, "-enc", "UTF-8", str(pdf), str(ut)],
                   check=True)
    tekst = ut.read_text(encoding="utf-8", errors="replace")

    sider = 0
    try:
        info = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, check=True
        ).stdout
        for linje in info.splitlines():
            if linje.startswith("Pages:"):
                sider = int(linje.split()[1])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        pass
    return tekst, sider


def docx_til_tekst(data: bytes) -> str:
    """Word -> tekst, ett avsnitt per linje. Bare standardbiblioteket."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        rot = ET.fromstring(z.read("word/document.xml"))
    avsnitt = []
    for p in rot.iter(f"{W}p"):
        deler = []
        for n in p.iter():
            if n.tag == f"{W}t":
                deler.append(n.text or "")
            elif n.tag == f"{W}tab":
                deler.append("\t")
            elif n.tag in (f"{W}br", f"{W}cr"):
                deler.append("\n")
        avsnitt.append("".join(deler))
    return "\n".join(avsnitt)


def filformat(data: bytes) -> str:
    """Portalen svarer med PDF, og for noen møter med Word (målt 2.10.2026)."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" in z.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            pass
    return "ukjent"


def _moter_i_raadata(aar: int) -> list[dict]:
    moter = raadata.moter(aar)
    if moter is None:
        raise SystemExit(f"fant ingen møter for {aar}. Kjør hent.hent_moter først.")
    return moter


def _apne_i_raadata(aar: int) -> tuple[set[int], set[int], set[int]]:
    """(åpne dokumenter, åpne vedtak, åpne møtedokumenter), lest rett fra
    rådataene.

    Et flagg som sier skjermet eller upublisert ett sted, vinner over alle
    andre forekomster av samme dokument eller vedtak.
    """
    dok_apne, dok_stengt = set(), set()
    vedtak_apne, vedtak_stengt = set(), set()
    mote_apne, mote_stengt = set(), set()
    for mote in _moter_i_raadata(aar):
        for d in mote["detaljer"].get("MeetingDocuments") or []:
            (mote_stengt if d.get("IsRestricted") else mote_apne).add(d["Id"])

        for b in mote["behandlinger"]:
            for x in [b, *(b.get("AdditionalDmbHandlings") or [])]:
                apent = x.get("ProtocolPublished") and not x.get("ProtocolRestricted")
                (vedtak_apne if apent else vedtak_stengt).add(x["Id"])

            journal = b.get("RegistryEntry") or {}
            for d in journal.get("Documents") or []:
                bes = d.get("DocumentDescription") or {}
                apent = (bes.get("IsPublished") and not bes.get("AccessCodeId")
                         and not journal.get("AccessCodeId"))
                (dok_apne if apent else dok_stengt).add(bes.get("Id"))

    return (dok_apne - dok_stengt, vedtak_apne - vedtak_stengt,
            mote_apne - mote_stengt)


def _oppgaver(aar: int, med_vedlegg: bool) -> list[dict]:
    """Hva som skal hentes. Skjermede dokumenter er allerede filtrert bort
    i tolk/bygg_saker.py, men vi stoler ikke på det alene: hver oppgave
    kontrolleres også mot flaggene i rådataene."""
    saker = lager_saker.les(aar)
    ut: list[dict] = []

    for sak in saker:
        f = sak.get("saksframlegg")
        if f:
            ut.append({"id": f["dokument_id"], "url": f["url"],
                       "slag": "saksframlegg", "kolonner": False})

        for steg in sak["saksgang"]:
            if steg["protokoll_publisert"] and not steg["protokoll_skjermet"]:
                ut.append({"id": steg["behandling_id"],
                           "url": steg["url_vedtak"],
                           "slag": "saksprotokoll", "kolonner": True})

        if med_vedlegg:
            for v in sak.get("vedlegg") or []:
                ut.append({"id": v["dokument_id"], "url": v["url"],
                           "slag": "vedlegg", "kolonner": False})

    # Møteprotokollen, for oppmøtelisten. Aldri møteinnkallingen (ADR-006).
    for mote in _moter_i_raadata(aar):
        mid = mote["mote"]["MO_ID"]
        for d in mote["detaljer"].get("MeetingDocuments") or []:
            if d["DmbDocumentTypeId"] == "MP" and not d.get("IsRestricted"):
                ut.append({"id": d["Id"],
                           "url": portal.url_motedokument(mid, "MP", d["Id"]),
                           "slag": "moteprotokoll", "kolonner": True,
                           "mote_id": mid})

    dok_apne, vedtak_apne, mote_apne = _apne_i_raadata(aar)
    apne_for = {"saksprotokoll": vedtak_apne, "moteprotokoll": mote_apne}
    sett, unike = set(), []
    for o in ut:
        # Vedtak, møtedokumenter og saksdokumenter har hver sine ID-er.
        nokkel = (o["slag"] if o["slag"] in apne_for else "dokument", o["id"])
        if nokkel in sett:
            continue
        sett.add(nokkel)
        apne = apne_for.get(o["slag"], dok_apne)
        if o["id"] not in apne:
            print(f"hopper over {o['slag']} {o['id']}: ikke åpen i rådataene")
            continue
        unike.append(o)
    return unike


def _hvor(o: dict) -> tuple[str, int]:
    """Hvor teksten lagres: ID-rommet og nøkkelen (se lager.tekst).

    Møteprotokollen lagres etter møte-ID, ikke dokument-ID, siden det er
    møtet oppmøtelisten hører til.
    """
    if o["slag"] == "moteprotokoll":
        return "mote", o["mote_id"]
    if o["slag"] == "saksprotokoll":
        return "behandling", o["id"]
    return "dokument", o["id"]


def kjor(aar: int, mal_bare: bool = False, med_vedlegg: bool = False) -> None:
    sjekk_poppler()
    oppgaver = _oppgaver(aar, med_vedlegg)
    nye = [o for o in oppgaver if mal_bare or not lager_tekst.har(*_hvor(o))]
    print(f"{len(oppgaver)} dokumenter, {len(nye)} skal lastes ned. Omtrent "
          f"{len(nye) * SEKUND_PER_DOKUMENT / 60:.0f} minutter.")

    maling: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, o in enumerate(oppgaver, 1):
            if lager_tekst.har(*_hvor(o)) and not mal_bare:
                continue

            try:
                data = portal.hent_fil(o["url"])
            except portal.PortalFeil as e:
                maling.append({**o, "feilet": str(e)})
                print(f"[{i}] feilet {o['id']}: {e}")
                continue

            fmt = filformat(data)
            post = {**o, "bytes": len(data), "format": fmt, "er_pdf": fmt == "pdf"}

            if fmt == "pdf":
                pdf = Path(tmp) / f"{o['id']}.pdf"
                pdf.write_bytes(data)
                try:
                    tekst, sider = til_tekst(pdf, o["kolonner"])
                except subprocess.CalledProcessError as e:
                    print(f"[{i}] klarte ikke lese {o['id']}: {e}")
                    continue
                per_side = len(tekst) / sider if sider else 0
                post.update(sider=sider, tegn=len(tekst),
                            tegn_per_side=round(per_side),
                            mangler_tekstlag=per_side < MIN_TEGN_PER_SIDE)
            elif fmt == "docx":
                try:
                    tekst = docx_til_tekst(data)
                except (KeyError, ET.ParseError, zipfile.BadZipFile) as e:
                    print(f"[{i}] klarte ikke lese {o['id']}: {e}")
                    continue
                post.update(tegn=len(tekst), mangler_tekstlag=False)
            else:
                maling.append(post)
                print(f"[{i}] {o['id']} er verken PDF eller Word, hoppet over")
                continue

            if o["slag"] == "saksframlegg":
                deler = saksframlegg.del_opp(tekst)
                post["etter_malen"] = deler is not None
                if deler:
                    post["avsnitt"] = [k for k in deler if k != "innledning"]
            maling.append(post)

            if not mal_bare:
                if post["mangler_tekstlag"]:
                    print(f"[{i}] {o['id']} mangler tekstlag, ikke lagret")
                    continue
                lager_tekst.lagre(*_hvor(o), tekst)

    if mal_bare:
        konfig.lagre_maling(aar, maling)
        formater = collections.Counter(m["format"] for m in maling if "format" in m)
        pdf_er = [m for m in maling if m.get("format") == "pdf"]
        uten = [m for m in maling if m.get("mangler_tekstlag")]
        sf = [m for m in maling if "etter_malen" in m]
        print(f"\nMålt {len(maling)} dokumenter.")
        print(f"  feilet            : {sum(1 for m in maling if 'feilet' in m)}")
        print(f"  format            : {dict(formater)}")
        print(f"  mangler tekstlag  : {len(uten)}")
        if pdf_er:
            sider = sum(m.get('sider') or 0 for m in pdf_er)
            print(f"  sider totalt      : {sider}")
            print(f"  største dokument  : "
                  f"{max(m.get('sider') or 0 for m in pdf_er)} sider")
        if sf:
            print(f"  saksframlegg etter malen: "
                  f"{sum(m['etter_malen'] for m in sf)} av {len(sf)}")
        print(f"  detaljer i data/maling-{aar}.json")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    import datetime as dt  # noqa: PLC0415
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar, mal_bare="--mal" in sys.argv, med_vedlegg="--vedlegg" in sys.argv)


if __name__ == "__main__":
    main()
