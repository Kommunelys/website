"""JSON- og tekstfiler i mappen KOMMUNELYS_DATA (KOMMUNELYS_LAGER=json), og
filene som vedlikeholdes for hånd i kommuner/<slug>/. Bare modulene i lager/
bruker denne."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
# Mappen for KOMMUNELYS_LAGER=json, for eksempel for å prøve en ny kommune.
# lager.fra_databasen() stopper json uten KOMMUNELYS_DATA, så reserven brukes
# ikke; den finnes bare fordi modulene lager stiene når de importeres.
DATA = Path(os.environ.get("KOMMUNELYS_DATA") or ROT / "data")

_MANGLER = object()


def les(sti: Path, standard=_MANGLER):
    """JSON fra fil. Uten `standard` er en manglende fil en feil."""
    if standard is not _MANGLER and not sti.exists():
        return standard
    return json.loads(sti.read_text(encoding="utf-8"))


def skriv(sti: Path, data, *, sorter: bool = True) -> None:
    """Samme format som før lagringslaget, så en ny kjøring ikke gir diff.

    De fleste filene har sorterte nøkler. Analysene, kjøreloggen og tellingen
    har det ikke.
    """
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=sorter),
        encoding="utf-8",
    )
