"""Det som er publisert i hver sak, slik varselet sammenligner det (ADR-027).

Bygget (bygg_nettsted.kjor_kommune) lager tilstanden av de samme sakene som
nettstedet viser, før detaljene skilles ut, og skriver den til
varsel-tilstand/<slug>.json. Bare det som er publisert, er med: et sammendrag
eller en debatt som holdes tilbake, finnes ikke i sakene.

kjor.alle lagrer filen i databasen (varsel.sak_tilstand) bare når kommunen
faktisk publiseres, så varselet aldri går foran nettstedet:

    python -m varsel.tilstand            # KOMMUNELYS_KOMMUNE er kommunen
"""

from __future__ import annotations

import json
from pathlib import Path

from lager import kommune as lager_kommune
from lager import varsel as lager_varsel

MAPPE = Path(__file__).resolve().parent.parent / "varsel-tilstand"


def tilstand(c: dict) -> dict:
    """Én sak fra S.cases, med vedtakene (st.vt) og debatten (st.deb) ennå på stegene."""
    return {
        "tittel": c["a"]["tk"] if c.get("a") else c["t"],
        "status": c["status"],
        "steg": [{
            "hid": x["hid"],
            "dato": x["date"],
            "utvalg": x["ut"],
            "kode": x["sc"],
            # Protokollen er publisert, og vedtaket står på saken.
            "protokoll": bool(x["pub"]),
            "vedtak": bool(x["pub"] and x.get("vt")),
        } for x in c["st"]],
        "sammendrag": bool(c.get("a")),
        "debatt": sorted(x["hid"] for x in c["st"] if x.get("deb")),
    }


def skriv(slug: str, cases: list[dict]) -> Path:
    MAPPE.mkdir(exist_ok=True)
    fil = MAPPE / f"{slug}.json"
    fil.write_text(json.dumps({str(c["id"]): tilstand(c) for c in cases}, ensure_ascii=False),
                   encoding="utf-8")
    return fil


def main() -> None:
    slug = lager_kommune.slug()
    fil = MAPPE / f"{slug}.json"
    if not fil.exists():
        raise SystemExit(f"fant ikke {fil}; bygg kommunen først")
    tilstander = {int(k): v for k, v in json.loads(fil.read_text("utf-8")).items()}
    lager_varsel.lagre_tilstander(tilstander)
    print(f"{slug}: tilstanden til {len(tilstander)} saker er lagret for varselet")


if __name__ == "__main__":
    main()
