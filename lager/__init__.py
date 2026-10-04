"""Lagringslaget. All lesing og skriving av data/ går gjennom denne pakken.

Hent-, tolke-, analyse- og byggekoden vet ikke hvor dataene ligger. Hver modul
her svarer for én del av datamodellen og returnerer samme form som filene i
data/ har i dag. I dag er backend JSON-filer i git. Planen er å flytte
dataene til Postgres (Supabase) uten å endre koden som bruker dem; se
docs/06-database.md når den finnes.

    from lager import saker, tekst
    alle = saker.les(2026)
    protokoll = tekst.les("behandling", 7623)
"""

from __future__ import annotations

import datetime as dt
import os


def i_dag() -> str:
    """Dagens dato som ISO-streng.

    KOMMUNELYS_I_DAG overstyrer, slik at tolkningen og bygget kan gjentas med
    samme resultat en annen dag (status som «Venter på protokoll» avhenger av
    datoen).
    """
    return os.environ.get("KOMMUNELYS_I_DAG") or dt.date.today().isoformat()
