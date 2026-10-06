"""Lagringslaget. All lesing og skriving av dataene går gjennom denne pakken.

Hent-, tolke-, analyse- og byggekoden vet ikke hvor dataene ligger. Hver modul
her svarer for én del av datamodellen og returnerer samme form som filene i
data/ hadde. Kilden er Postgres i Supabase (ADR-019); filene i data/ ble
brukt fram til 6.10.2026 og kan fortsatt leses med KOMMUNELYS_LAGER=json.

    from lager import saker, tekst
    alle = saker.les(2026)
    protokoll = tekst.les("behandling", 7623)
"""

from __future__ import annotations

import datetime as dt
import os


def fra_databasen() -> bool:
    """Standard er databasen (pg). KOMMUNELYS_LAGER=json leser og skriver
    filene i data/, som sto stille fra byttet 6.10.2026 (ADR-019)."""
    verdi = os.environ.get("KOMMUNELYS_LAGER", "pg")
    if verdi not in ("json", "pg"):
        raise SystemExit(f"KOMMUNELYS_LAGER må være json eller pg, ikke {verdi!r}")
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
