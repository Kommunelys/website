"""Tilkoblingen til databasen (Postgres i Supabase).

Adressen leses fra miljøvariabelen KOMMUNELYS_DB_URL, eller fra filen
~/.kommunelys.env på egen maskin. Den ligger aldri i repoet: den har
passordet til en databaserolle. Bruk Session pooler-adressen i Supabase
(port 5432); den direkte adressen er bare IPv6.

    KOMMUNELYS_DB_URL=postgresql://kommunelys_pipeline.<prosjekt>:<passord>@<vert>:5432/postgres?sslmode=require
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

ENV_FIL = Path.home() / ".kommunelys.env"


def url() -> str:
    if os.environ.get("KOMMUNELYS_DB_URL"):
        return os.environ["KOMMUNELYS_DB_URL"]
    if ENV_FIL.exists():
        for linje in ENV_FIL.read_text(encoding="utf-8-sig").splitlines():
            navn, _, verdi = linje.partition("=")
            if navn.strip() == "KOMMUNELYS_DB_URL" and verdi.strip():
                return verdi.strip()
    raise SystemExit(f"mangler KOMMUNELYS_DB_URL (miljøvariabel eller {ENV_FIL})")


@contextmanager
def transaksjon(kjoring_id: str):
    """Én transaksjon, med kjøringen satt for endringsloggen.

    Fremmednøkler og stemmetallkontrollen sjekkes når transaksjonen avsluttes,
    så rader kan skrives i den rekkefølgen som passer.
    """
    import psycopg  # noqa: PLC0415  (bare når databasen brukes)

    with psycopg.connect(url(), connect_timeout=15) as tilkobling:
        with tilkobling.transaction():
            tilkobling.execute("set constraints all deferred")
            tilkobling.execute("select set_config('kommunelys.kjoring_id', %s, true)", (kjoring_id,))
            yield tilkobling
