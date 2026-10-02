"""Laster ned dokumenter og lagrer teksten. SKJELETT — URL-ene er ikke testet.

ADR-005: PDF-ene lagres ikke i repoet. Bare teksten, under data/tekst/.
ADR-006: møteinnkallingen lastes aldri ned for analyse. Den er alle
         saksframleggene limt sammen, over 350 sider for kommunestyret.
ADR-012: protokoller tas med `pdftotext -layout`, fordi oppmøtelisten er
         kolonnebasert. Valg for saksframlegg tas etter at samlingen er målt.

Dette skriptet er også måleverktøyet: `--mal` laster ned og rapporterer
sidetall, tegn per side og andel uten tekstlag, uten å lagre tekst.

    python -m hent.hent_dokumenter 2026 --mal      # mål samlingen først
    python -m hent.hent_dokumenter 2026            # hent og lagre tekst
    python -m hent.hent_dokumenter 2026 --vedlegg  # ta med vedlegg
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import portal

ROT = Path(__file__).resolve().parent.parent
SAKER = ROT / "data" / "saker"
TEKST = ROT / "data" / "tekst"

# Under dette er dokumentet trolig skannet og mangler tekstlag.
MIN_TEGN_PER_SIDE = 100


def til_tekst(pdf: Path, behold_kolonner: bool) -> tuple[str, int]:
    """PDF -> (tekst, sidetall). Krever poppler-utils."""
    ut = pdf.with_suffix(".txt")
    flagg = ["-layout"] if behold_kolonner else []
    subprocess.run(["pdftotext", *flagg, str(pdf), str(ut)], check=True)
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


def _oppgaver(aar: int, med_vedlegg: bool) -> list[dict]:
    """Hva som skal hentes. Skjermede dokumenter er allerede filtrert bort
    i tolk/bygg_saker.py, men vi stoler ikke på det alene."""
    saker = json.loads((SAKER / f"{aar}.json").read_text(encoding="utf-8"))
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

    sett, unike = set(), []
    for o in ut:
        if o["id"] not in sett:
            sett.add(o["id"])
            unike.append(o)
    return unike


def kjor(aar: int, mal_bare: bool = False, med_vedlegg: bool = False) -> None:
    TEKST.mkdir(parents=True, exist_ok=True)
    oppgaver = _oppgaver(aar, med_vedlegg)
    print(f"{len(oppgaver)} dokumenter. Omtrent "
          f"{len(oppgaver) * portal.PAUSE_SEKUND / 60:.0f} minutter.")

    maling: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, o in enumerate(oppgaver, 1):
            mal = TEKST / f"{o['id']}.txt"
            if mal.exists() and not mal_bare:
                continue

            try:
                data = portal.hent_fil(o["url"])
            except portal.PortalFeil as e:
                print(f"[{i}] feilet {o['id']}: {e}")
                continue

            pdf = Path(tmp) / f"{o['id']}.pdf"
            pdf.write_bytes(data)

            if not data.startswith(b"%PDF"):
                maling.append({**o, "bytes": len(data), "er_pdf": False})
                print(f"[{i}] {o['id']} er ikke PDF, hoppet over")
                continue

            try:
                tekst, sider = til_tekst(pdf, o["kolonner"])
            except subprocess.CalledProcessError as e:
                print(f"[{i}] klarte ikke lese {o['id']}: {e}")
                continue

            per_side = len(tekst) / sider if sider else 0
            maling.append({**o, "bytes": len(data), "sider": sider,
                           "tegn": len(tekst), "tegn_per_side": round(per_side),
                           "er_pdf": True,
                           "mangler_tekstlag": per_side < MIN_TEGN_PER_SIDE})

            if not mal_bare:
                if per_side < MIN_TEGN_PER_SIDE:
                    print(f"[{i}] {o['id']} mangler tekstlag, ikke lagret")
                    continue
                mal.write_text(tekst, encoding="utf-8")

    if mal_bare:
        sti = ROT / "data" / f"maling-{aar}.json"
        sti.write_text(json.dumps(maling, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        pdf_er = [m for m in maling if m.get("er_pdf")]
        uten = [m for m in pdf_er if m.get("mangler_tekstlag")]
        print(f"\nMålt {len(maling)} dokumenter.")
        print(f"  ikke PDF          : {len(maling) - len(pdf_er)}")
        print(f"  mangler tekstlag  : {len(uten)}")
        if pdf_er:
            sider = sum(m.get('sider') or 0 for m in pdf_er)
            print(f"  sider totalt      : {sider}")
            print(f"  største dokument  : "
                  f"{max(m.get('sider') or 0 for m in pdf_er)} sider")
        print(f"  detaljer i {sti}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    import datetime as dt  # noqa: PLC0415
    aar = int(args[0]) if args else dt.date.today().year
    kjor(aar, mal_bare="--mal" in sys.argv, med_vedlegg="--vedlegg" in sys.argv)


if __name__ == "__main__":
    main()
