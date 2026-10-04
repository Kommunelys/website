"""Kjøreloggen: tall fra hver kjøring som ikke kan leses ut av dataene etterpå.

Det som endres i dataene, finnes i git-historikken og regnes ut av
drift.historikk. Her lagres bare det som ellers ville vært borte når jobben er
ferdig: hvor mange kall som gikk til portalen, og hvordan AI-analysen gikk.

Bare tall. Ingen navn, titler eller tekst fra dokumentene.

Loggen (lager.drift) er et objekt med kjørings-ID som nøkkel. I GitHub
Actions er det GITHUB_RUN_ID; lokalt «lokal-<dato>».
"""

from __future__ import annotations

import datetime as dt
import os

from lager import drift as lager_drift

# Loggen vokser med én post per kjøring. Eldre poster ligger i git.
MAKS_POSTER = 200


def kjoring_id() -> str:
    return os.environ.get("GITHUB_RUN_ID") or f"lokal-{dt.date.today().isoformat()}"


def les() -> dict:
    return lager_drift.kjoringer()


def legg_til(del_: str, tall: dict[str, int | float]) -> None:
    """Legger tallene til under del_ i posten for denne kjøringen.

    Flere prosesser i samme kjøring (hent_moter, hent_medlemmer,
    hent_dokumenter) skriver til samme del; tallene summeres.
    """
    logg = les()
    post = logg.setdefault(kjoring_id(), {
        "start": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    gammel = post.setdefault(del_, {})
    for k, v in tall.items():
        gammel[k] = round(gammel.get(k, 0) + v, 1)
    # Nøklene er tall-ID-er i Actions og «lokal-…» lokalt; sorter på start.
    beholdt = sorted(logg.items(), key=lambda kv: kv[1].get("start", ""))[-MAKS_POSTER:]
    lager_drift.lagre_kjoringer(dict(beholdt))
