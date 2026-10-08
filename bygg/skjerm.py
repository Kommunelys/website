"""Dataene til en kommune med begrenset innsyn, inn i databasen (ADR-024).

bygg.bygg_nettsted --begrenset skriver data.json og detaljer-<år>.json til
nettsted-skjermet/<slug>/ i stedet for til nettstedet. Herfra lagres de i
drift.nettsted_fil, der bare de med en rolle for kommunen kan hente dem
(portal.nettsted_fil). Kjøres av kjor.alle etter bygget.

    python -m bygg.skjerm [--kommune SLUG]        # lagrer kommunens filer
    python -m bygg.skjerm --rydd [SLUG,SLUG]      # fjerner de andre kommunenes
"""

from __future__ import annotations

import sys

from lager import drift as lager_drift
from lager import kommune as lager_kommune

from .bygg_nettsted import SKJERMET


def lagre() -> None:
    slug = lager_kommune.slug()
    mappe = SKJERMET / slug
    filer = {f.name: f.read_text("utf-8") for f in sorted(mappe.glob("*.json"))}
    if "data.json" not in filer:
        raise SystemExit(f"fant ikke {mappe.name}/data.json; bygg kommunen med --begrenset først")
    lager_drift.lagre_skjermet(filer)
    print(f"{slug}: {len(filer)} filer lagret i databasen "
          f"({sum(len(t.encode()) for t in filer.values()) // 1024} KB)")


def main() -> None:
    argv = lager_kommune.fra_argv(sys.argv[1:])
    if "--rydd" in argv:
        rest = argv[argv.index("--rydd") + 1:]
        lager_drift.rydd_skjermet([s for s in (rest[0] if rest else "").split(",") if s])
    else:
        lagre()


if __name__ == "__main__":
    main()
