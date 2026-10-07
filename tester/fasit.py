"""Fasit for tolkningen: dokumenter kontrollert for hånd, med forventet resultat.

Hver kommune har noen dokumenter i tester/fasit/<kommune>/, som tekst
(<slag>-<id>.txt), med resultatet ved siden av (<slag>-<id>.json):

- mote: en møteprotokoll, tolket med tolk_protokoll.tolk
- vedtak: saksprotokollen for én sak, med voteringene og vedtaksteksten
- saksframlegg: avsnittene i ett saksframlegg

Fasiten gjelder regelsettet (tolk/profil.py). Endres standarden for Elements,
skal fasiten for alle kommunene fortsatt bestå (ADR-021). Trenger ikke
databasen eller data/, og kjøres ved hver PR (.github/workflows/tester.yml).

    python -m tester.fasit                      # alle kommunene
    python -m tester.fasit steinkjer
    python -m tester.fasit steinkjer --skriv    # lager .json der den mangler

--skriv overskriver aldri en fasit. Et nytt resultat må kontrolleres for hånd
mot dokumentet før det legges inn: det er det som gjør det til en fasit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAPPE = Path(__file__).resolve().parent / "fasit"


def _tolk(slag: str, tekst: str):
    from tolk.saksframlegg import del_opp  # noqa: PLC0415
    from tolk.tolk_protokoll import les_vedtak, les_vedtakstekst, tolk  # noqa: PLC0415

    if slag == "mote":
        return tolk(tekst)
    if slag == "vedtak":
        return {"voteringer": les_vedtak(tekst, "-"), "vedtak": les_vedtakstekst(tekst)}
    if slag == "saksframlegg":
        return del_opp(tekst)
    raise SystemExit(f"ukjent slag {slag!r}; bruk mote, vedtak eller saksframlegg")


def _forskjell(ventet, fikk, sti: str = "") -> str | None:
    """Første sted der to JSON-verdier er ulike, som en lesbar sti."""
    if type(ventet) is not type(fikk):
        return f"{sti or '/'}: ventet {ventet!r}, fikk {fikk!r}"
    if isinstance(ventet, dict):
        for n in sorted(set(ventet) | set(fikk)):
            if n not in fikk:
                return f"{sti}/{n}: mangler"
            if n not in ventet:
                return f"{sti}/{n}: finnes ikke i fasiten"
            f = _forskjell(ventet[n], fikk[n], f"{sti}/{n}")
            if f:
                return f
        return None
    if isinstance(ventet, list):
        for i, (v, f_) in enumerate(zip(ventet, fikk)):
            f = _forskjell(v, f_, f"{sti}/{i}")
            if f:
                return f
        if len(ventet) != len(fikk):
            return f"{sti or '/'}: ventet {len(ventet)} elementer, fikk {len(fikk)}"
        return None
    return None if ventet == fikk else f"{sti or '/'}: ventet {ventet!r}, fikk {fikk!r}"


def kjor(kommune: str, skriv: bool = False) -> list[str]:
    """Feilene for én kommune. Tom liste betyr at fasiten består."""
    from lager import kommune as lager_kommune  # noqa: PLC0415

    lager_kommune.bruk(kommune)
    feil = []
    filer = sorted((MAPPE / kommune).glob("*.txt"))
    if not filer:
        return [f"{kommune}: ingen dokumenter i tester/fasit/{kommune}/"]
    for txt in filer:
        slag = txt.stem.split("-", 1)[0]
        # Gjennom JSON, så tupler og lister sammenlignes likt.
        fikk = json.loads(json.dumps(_tolk(slag, txt.read_text(encoding="utf-8")), ensure_ascii=False))
        fasit = txt.with_suffix(".json")
        if not fasit.exists():
            if skriv:
                fasit.write_text(json.dumps(fikk, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"skrev {fasit.relative_to(MAPPE.parent.parent)}; kontroller den for hånd")
            else:
                feil.append(f"{kommune}/{txt.name}: mangler fasit (.json)")
            continue
        f = _forskjell(json.loads(fasit.read_text(encoding="utf-8")), fikk)
        if f:
            feil.append(f"{kommune}/{txt.name}: {f}")
    return feil


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skriv = "--skriv" in sys.argv
    kommuner = args or sorted(p.name for p in MAPPE.iterdir() if p.is_dir())
    feil = []
    for k in kommuner:
        f = kjor(k, skriv)
        n = len(list((MAPPE / k).glob("*.txt")))
        print(f"{k}: {n - len({x.split(':')[0] for x in f})} av {n} dokumenter som i fasiten")
        feil += f
    if feil:
        print(f"\n{len(feil)} feil:")
        for f in feil:
            print(f"  - {f}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
