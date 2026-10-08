"""Deler et saksframlegg ved de faste overskriftene i kommunens mal.

ADR-013: malen starter med «SAKSFRAMLEGG» og har overskriftene «… forslag til
vedtak» (eller «innstilling»), «Saksopplysninger» og «Saksvurderinger», hver på
egen linje og i den rekkefølgen. Testet på 14 saksframlegg fra ulike utvalg.
Andre overskrifter leses ikke ut; skrifttypen ga mer støy enn nytte.

Hoveddokumentet i en referatsak er ofte et brev eller en protokoll fra andre,
ikke et saksframlegg. Det deles ikke.

Teksten må være hentet ut med `pdftotext` uten -layout.

    python -m tolk.saksframlegg data/tekst/835161.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

from .profil import profil

# Overskriftene og ordet dokumentet starter med står i kommunens profil, med
# standarden i tolk/profiler/elements.py.


def er_saksframlegg(tekst: str) -> bool:
    """Følger dokumentet kommunens mal? Linjene i «saksframlegg_foran» kan stå
    først, for eksempel «Levanger kommune» over «Saksframlegg»."""
    p = profil()
    linjer = [linje.strip().upper() for linje in tekst.splitlines() if linje.strip()]
    while linjer and linjer[0] in p.saksframlegg_foran:
        linjer.pop(0)
    return bool(linjer) and linjer[0].startswith(p.saksframlegg_start)


def del_opp(tekst: str) -> dict[str, str] | None:
    """Saksframlegg -> {"innledning", "forslag", "saksopplysninger", "saksvurderinger"}.

    Innledningen er alt før første overskrift: saksgang, arkivsaksnummer og
    tittel. Mangler en overskrift, mangler nøkkelen. Gir None for dokumenter
    som ikke følger malen.
    """
    if not er_saksframlegg(tekst):
        return None

    linjer = tekst.splitlines()
    starter: list[tuple[int, str]] = []
    fra = 0
    for nokkel, monster in profil().overskrifter:
        for i in range(fra, len(linjer)):
            if monster.match(linjer[i].strip()):
                starter.append((i, nokkel))
                fra = i + 1
                break

    forste = starter[0][0] if starter else len(linjer)
    deler = {"innledning": "\n".join(linjer[:forste]).strip()}
    for n, (i, nokkel) in enumerate(starter):
        slutt = starter[n + 1][0] if n + 1 < len(starter) else len(linjer)
        deler[nokkel] = "\n".join(linjer[i + 1:slutt]).strip()
    return deler


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    deler = del_opp(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if deler is None:
        print("ikke et saksframlegg etter malen")
        return
    for nokkel, tekst in deler.items():
        print(f"{nokkel:17} {len(tekst):7} tegn")


if __name__ == "__main__":
    main()
