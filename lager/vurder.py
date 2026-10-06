"""Registrerer en vurdering av et avvik i databasen (ADR-015, ADR-020).

Vurderinger gjøres vanligvis i portalen (portal.kommunelys.no). Denne
kommandoen er for vurderinger fra en modell i Claude Code, med vurdert_av
satt til modellen. En vurdering kan ikke endres eller slettes; en ny
vurdering av samme avvik erstatter den forrige, og begge blir stående.

    python -m lager.vurder oppmote:1230:navn-navnesen publiser \\
        --begrunnelse "..." --vurdert-av "Claude Opus 5.5 (claude-opus-5-5)" [--merknad "..."]

Vurderingen slår inn på nettstedet ved neste kjøring.
"""

from __future__ import annotations

import argparse

from . import fra_databasen, i_dag, pg_skriv

AVGJORELSER = ("publiser", "ikke_publiser", "venter_paa_kommunen")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("avvik")
    p.add_argument("avgjorelse", choices=AVGJORELSER)
    p.add_argument("--begrunnelse", required=True)
    p.add_argument("--vurdert-av", required=True)
    p.add_argument("--merknad")
    a = p.parse_args()
    if not fra_databasen():
        raise SystemExit("vurderingene ligger i databasen; kjør uten KOMMUNELYS_LAGER=json")
    v = {"avvik": a.avvik, "avgjorelse": a.avgjorelse, "merknad": a.merknad,
         "begrunnelse": a.begrunnelse, "vurdert_av": a.vurdert_av, "dato": i_dag()}
    ny = pg_skriv.i_transaksjon(lambda c, k: pg_skriv.vurdering(c, k, v))
    print(f"vurdering {ny} registrert for {a.avvik}: {a.avgjorelse}")


if __name__ == "__main__":
    main()
