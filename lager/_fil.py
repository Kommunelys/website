"""JSON- og tekstfiler under data/. Bare modulene i lager/ bruker denne."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
# KOMMUNELYS_DATA peker til en annen datamappe, for eksempel en eksport som
# skal sammenlignes med data/.
DATA = Path(os.environ.get("KOMMUNELYS_DATA") or ROT / "data")

_MANGLER = object()


def _vakt(sti: Path) -> None:
    """data/ hører til Steinkjer. En annen kommune med KOMMUNELYS_LAGER=json må
    ha sin egen mappe i KOMMUNELYS_DATA, ellers ville den lest og skrevet over
    Steinkjers filer."""
    slug = os.environ.get("KOMMUNELYS_KOMMUNE") or "steinkjer"
    if slug != "steinkjer" and not os.environ.get("KOMMUNELYS_DATA") and sti.is_relative_to(ROT / "data"):
        raise SystemExit(f"data/ hører til steinkjer; sett KOMMUNELYS_DATA til en egen mappe for {slug}")


def les(sti: Path, standard=_MANGLER):
    """JSON fra fil. Uten `standard` er en manglende fil en feil."""
    _vakt(sti)
    if standard is not _MANGLER and not sti.exists():
        return standard
    return json.loads(sti.read_text(encoding="utf-8"))


def skriv(sti: Path, data, *, sorter: bool = True) -> None:
    """Samme format som før lagringslaget, så en ny kjøring ikke gir diff.

    De fleste filene har sorterte nøkler. Analysene, målingen, kjøreloggen og
    tellingen har det ikke.
    """
    _vakt(sti)
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=sorter),
        encoding="utf-8",
    )
