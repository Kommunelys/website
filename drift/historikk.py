"""Hva tjenesten har gjort: kjøringene i GitHub Actions og endringene i data/.

Tre kilder, slått sammen per kjøring:

- GitHub Actions-API-et: når kjøringene gikk, hvem som startet dem, og
  resultatet for hver jobb. Repoet er offentlig, så API-et kan leses uten
  nøkkel (60 kall i timen). I Actions brukes GITHUB_TOKEN.
- Git-historikken: hver commit fra oppdater-bot sammenlignes med forelderen.
  Det gir nye møter, saker, voteringer, dokumenter og sammendrag, også for
  kjøringer fra før kjøreloggen fantes.
- Endringsloggen i databasen (KOMMUNELYS_LAGER=pg): det samme per kjøring,
  når dataene skrives dit i stedet for å committes.
- Kjøreloggen (drift.logg): kall mot portalen og hvordan AI-analysen gikk.

Alt her er tall og offentlige sakstitler. Ingen tekst skrevet av en modell.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from drift.logg import les as les_logg
from lager import fra_databasen

ROT = Path(__file__).resolve().parent.parent
REPO = "Kommunelys/website"
ARBEIDSFLYT = "oppdater.yml"
BOT = "oppdater-bot"

# Commits fra arbeidsflyten havner noen sekunder til minutter før kjøringen
# regnes som ferdig. Slingringsmonn i begge ender.
SLINGRING = dt.timedelta(minutes=3)


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


# ---------- Git ----------

def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROT, capture_output=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def _json(rev: str, sti: str):
    tekst = _git("show", f"{rev}:{sti}")
    try:
        return json.loads(tekst) if tekst else None
    except json.JSONDecodeError:
        return None


def _har_protokoll(m: dict) -> bool:
    return any(d.get("type") == "MP" for d in m.get("dokumenter") or [])


def _antall_voteringer(v: list | None) -> int:
    return sum(len(b.get("voteringer") or []) for b in v or [])


def _endringer_i(c: str, p: str) -> dict:
    """Hva commit c endret i data/ sammenlignet med forelderen p."""
    e = {"nye_saker": [], "nye_moter": 0, "nye_protokoller": 0, "ny_status": 0,
         "nye_voteringer": 0, "nye_dokumenter": 0, "nye_sammendrag": 0,
         "oppdaterte_sammendrag": 0, "tokens_inn": 0, "tokens_ut": 0, "nye_avvik": 0,
         "moter_sjekket": 0, "moter_hentet": 0,
         # {modell: [inn, ut]}: prisen avhenger av modellen.
         "tokens_per_modell": {}}
    filer = []
    for linje in _git("diff", "--name-status", "--no-renames", p, c, "--", "data/").splitlines():
        status, _, sti = linje.partition("\t")
        filer.append((status, sti))

    for status, sti in filer:
        if sti.startswith("data/tekst/") and status == "A":
            e["nye_dokumenter"] += 1
        elif sti.startswith("data/analyse/") and status in ("A", "M"):
            e["nye_sammendrag" if status == "A" else "oppdaterte_sammendrag"] += 1
            a = _json(c, sti) or {}
            t = a.get("tokens") or {}
            e["tokens_inn"] += t.get("inn", 0)
            e["tokens_ut"] += t.get("ut", 0)
            m = e["tokens_per_modell"].setdefault(a.get("modell") or "ukjent", [0, 0])
            m[0] += t.get("inn", 0)
            m[1] += t.get("ut", 0)
        elif status != "M" and status != "A":
            continue
        elif sti.endswith("/siste-kjoring.json"):
            # Skrives av hent.hent_moter hver gang: hvor mange møter som ble
            # sjekket mot portalen, og hvor mange som måtte hentes på nytt.
            sk = _json(c, sti) or {}
            e["moter_sjekket"] += sk.get("moter_totalt", 0)
            e["moter_hentet"] += sk.get("moter_hentet", 0)
        elif sti.startswith("data/saker/") and sti.endswith(".json"):
            ny, gml = _json(c, sti) or [], _json(p, sti) or []
            for_ = {s["sak_id"]: s for s in gml}
            for s in ny:
                g = for_.get(s["sak_id"])
                if g is None:
                    e["nye_saker"].append({
                        "id": s["sak_id"], "formalia": s.get("formalia", False),
                        # Skjermede titler vises ikke (CLAUDE.md regel 3).
                        "tittel": None if s.get("skjermet_tittel") else s.get("tittel"),
                        "url": next((st["url_mote"] for st in reversed(s.get("saksgang") or [])
                                     if st.get("url_mote")), None)})
                elif g.get("status") != s.get("status"):
                    e["ny_status"] += 1
        elif sti.startswith("data/moter/") and sti.endswith(".json"):
            ny, gml = _json(c, sti) or [], _json(p, sti) or []
            for_ = {m["mote_id"]: m for m in gml}
            for m in ny:
                g = for_.get(m["mote_id"])
                if g is None:
                    e["nye_moter"] += 1
                if _har_protokoll(m) and not (g and _har_protokoll(g)):
                    e["nye_protokoller"] += 1
        elif sti.startswith("data/voteringer/") and sti.endswith(".json"):
            e["nye_voteringer"] += max(0, _antall_voteringer(_json(c, sti))
                                       - _antall_voteringer(_json(p, sti)))
        elif sti.startswith("data/avvik/") and sti.endswith(".json"):
            gamle = {a["avvik"] for a in _json(p, sti) or []}
            e["nye_avvik"] += sum(1 for a in _json(c, sti) or [] if a["avvik"] not in gamle)
    return e


def endringer(dager: int = 45, maks: int = 60) -> list[dict]:
    """Commits fra arbeidsflyten de siste dagene, med hva de endret.

    Med databasen også kjøringene i endringsloggen. Etter at dataene ikke
    lenger committes, kommer alt nytt derfra; det eldre kommer fra git.
    """
    ut = _endringer_i_git(dager, maks)
    if fra_databasen():
        from lager import pg  # noqa: PLC0415

        ut = sorted(ut + pg.endringer(dager, maks), key=lambda e: e["tid"], reverse=True)[:maks]
    return ut


def _endringer_i_git(dager: int, maks: int) -> list[dict]:
    ut = []
    logg = _git("log", f"--since={dager}.days", f"--max-count={maks}",
                f"--author={BOT}", "--format=%H%x09%P%x09%cI%x09%s", "--", "data/")
    for linje in logg.splitlines():
        h, foreldre, tid, emne = linje.split("\t", 3)
        p = foreldre.split()[0] if foreldre else None
        if not p:
            continue
        ut.append({"commit": h, "tid": _tid(tid), "emne": emne, **_endringer_i(h, p)})
    return ut


# ---------- Samlet ----------

def tidslinje(kj: list[dict] | None, endr: list[dict]) -> list[dict]:
    """Én post per kjøring, med commitene og loggtallene som hører til.

    Commits som ikke passer i noen kjøring (eldre enn de hentede kjøringene,
    eller kjørt lokalt), blir egne poster.
    """
    logg = les_logg()
    poster = []
    brukt = set()
    for k in kj or []:
        start, slutt = k["start"], k["slutt"]
        # Endringer fra databasen har kjøringen på seg; commits kobles på tid.
        commits = [c for c in endr if c["commit"] not in brukt and (
            c.get("kjoring") == k["id"] if c.get("kjoring") else
            start and slutt and start - SLINGRING <= c["tid"] <= slutt + SLINGRING)]
        brukt.update(c["commit"] for c in commits)
        poster.append({**k, "commits": commits, "logg": logg.get(k["id"], {})})
    for c in endr:
        if c["commit"] not in brukt:
            poster.append({"id": None, "start": c["tid"], "slutt": c["tid"],
                           "status": "completed", "resultat": None, "commits": [c],
                           "logg": {}, "jobber": None})
    poster.sort(key=lambda p: p["start"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                reverse=True)
    return poster


def sum_endringer(commits: list[dict]) -> dict:
    tot: dict = {"nye_saker": [], "tokens_per_modell": {}}
    for c in commits:
        for k, v in c.items():
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
