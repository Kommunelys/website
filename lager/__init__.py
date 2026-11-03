"""Lagringslaget. All lesing og skriving av dataene går gjennom denne pakken.

Hent-, tolke-, analyse- og byggekoden vet ikke hvor dataene ligger. Hver modul
her svarer for én del av datamodellen og returnerer samme form som filene i
data/ hadde. Kilden er Postgres i Supabase (ADR-019). Med KOMMUNELYS_LAGER=json
leses og skrives filer i en egen mappe (KOMMUNELYS_DATA), for å prøve en ny
kommune uten å røre databasen.

    from lager import saker, tekst
    alle = saker.les(2026)
    protokoll = tekst.les("behandling", 7623)
"""

from __future__ import annotations

import datetime as dt
import os


def fra_databasen() -> bool:
    """Standard er databasen (pg). KOMMUNELYS_LAGER=json leser og skriver
    filene i mappen KOMMUNELYS_DATA. data/ i repoet er tatt ut (ADR-019), så
    json uten en egen mappe stopper i stedet for å lese en tom mappe."""
    verdi = os.environ.get("KOMMUNELYS_LAGER", "pg")
    if verdi not in ("json", "pg"):
        raise SystemExit(f"KOMMUNELYS_LAGER må være json eller pg, ikke {verdi!r}")
    if verdi == "json" and not os.environ.get("KOMMUNELYS_DATA"):
        raise SystemExit("KOMMUNELYS_LAGER=json trenger KOMMUNELYS_DATA, en egen mappe for dataene")
    return verdi == "pg"


def i_dag() -> str:
    """Dagens dato som ISO-streng.

    KOMMUNELYS_I_DAG overstyrer, slik at tolkningen og bygget kan gjentas med
    samme resultat en annen dag (status som «Venter på protokoll» avhenger av
    datoen).
    """
    return os.environ.get("KOMMUNELYS_I_DAG") or dt.date.today().isoformat()


def kjoring_id() -> str:
    """Kjøringen som skriver: GITHUB_RUN_ID i Actions, ellers «lokal-<dato>».
    Samme som i drift.logg, så endringsloggen og kjøreloggen kan kobles."""
    return os.environ.get("GITHUB_RUN_ID") or f"lokal-{dt.date.today().isoformat()}"
