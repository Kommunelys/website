"""Hva tjenesten har gjort: kjøringene i GitHub Actions og endringene i dataene.

Tre kilder, slått sammen per kjøring:

- GitHub Actions-API-et: når kjøringene gikk, hvem som startet dem, og
  resultatet for hver jobb. Repoet er offentlig, så API-et kan leses uten
  nøkkel (60 kall i timen). I Actions brukes GITHUB_TOKEN.
- Endringsloggen i databasen: nye møter, saker, voteringer, dokumenter og
  sammendrag per kjøring (lager.pg.endringer).
- Kjøreloggen (drift.logg): kall mot portalen og hvordan AI-analysen gikk.

Alt her er tall og offentlige sakstitler. Ingen tekst skrevet av en modell.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from drift.logg import les as les_logg
from lager import fra_databasen

ROT = Path(__file__).resolve().parent.parent
REPO = "Kommunelys/website"
ARBEIDSFLYT = "oppdater.yml"


# ---------- GitHub Actions ----------

def _api(sti: str):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{sti}",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "kommunelys-drift"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _tid(s: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def kjoringer(antall: int = 30, med_jobber: int = 15) -> list[dict] | None:
    """De siste kjøringene av arbeidsflyten, nyeste først.

    None betyr at API-et ikke svarte; siden sier da det i stedet for å late
    som det ikke har vært kjøringer.
    """
    try:
        # Bare main: en push til en annen gren med en ugyldig arbeidsflytfil gir
        # en «kjøring» som feiler på null sekunder, uten at noe er kjørt.
        svar = _api(f"actions/workflows/{ARBEIDSFLYT}/runs?branch=main&per_page={antall}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"advarsel: fikk ikke hentet kjøringene fra GitHub ({e})")
        return None
    ut = []
    for i, r in enumerate(svar.get("workflow_runs", [])):
        k = {
            "id": str(r["id"]),
            "nr": r.get("run_number"),
            "start": _tid(r.get("run_started_at") or r.get("created_at")),
            "slutt": _tid(r.get("updated_at")),
            "status": r.get("status"),          # completed, in_progress, queued
            "resultat": r.get("conclusion"),    # success, failure, cancelled, …
            "utlost": r.get("event"),           # workflow_dispatch, schedule
            "av": (r.get("triggering_actor") or r.get("actor") or {}).get("login"),
            "url": r.get("html_url"),
            "jobber": None,
        }
        # Jobbene koster ett kall per kjøring; de eldste klarer seg uten.
        if i < med_jobber:
            try:
                jobber = _api(f"actions/runs/{r['id']}/jobs")["jobs"]
                k["jobber"] = [{"navn": j["name"], "resultat": j.get("conclusion"),
                                "status": j.get("status")} for j in jobber]
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
                pass
        ut.append(k)
    return ut


def endringer(dager: int = 45, maks: int = 60) -> list[dict]:
    """Hva kjøringene de siste dagene endret, fra endringsloggen i databasen."""
    if not fra_databasen():
        return []
    from lager import pg  # noqa: PLC0415

    return pg.endringer(dager, maks)


# ---------- Samlet ----------

def tidslinje(kj: list[dict] | None, endr: list[dict]) -> list[dict]:
    """Én post per kjøring, med endringene og loggtallene som hører til.

    Endringer fra en kjøring som ikke er blant de hentede (eldre, eller kjørt
    lokalt), blir egne poster.
    """
    logg = les_logg()
    ider = {k["id"] for k in kj or []}
    poster = [{**k, "endringer": [e for e in endr if e["kjoring"] == k["id"]],
               "logg": logg.get(k["id"], {})} for k in kj or []]
    for e in endr:
        if e["kjoring"] not in ider:
            poster.append({"id": None, "start": e["tid"], "slutt": e["tid"],
                           "status": "completed", "resultat": None, "endringer": [e],
                           "logg": {}, "jobber": None})
    poster.sort(key=lambda p: p["start"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                reverse=True)
    return poster


def sum_endringer(endringer_: list[dict]) -> dict:
    tot: dict = {"nye_saker": [], "tokens_per_modell": {}}
    for e in endringer_:
        for k, v in e.items():
            if k == "nye_saker":
                tot["nye_saker"] += v
            elif k == "tokens_per_modell":
                for modell, (inn, ut) in v.items():
                    m = tot["tokens_per_modell"].setdefault(modell, [0, 0])
                    m[0] += inn
                    m[1] += ut
            elif isinstance(v, int):
                tot[k] = tot.get(k, 0) + v
    return tot


def tidsplan_er_pa() -> bool:
    """Om tidsplanen i arbeidsflyten er slått på (ikke kommentert ut)."""
    yml = (ROT / ".github" / "workflows" / ARBEIDSFLYT).read_text("utf-8")
    return any(l.strip() == "schedule:" for l in yml.splitlines())
