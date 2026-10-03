"""Omtrentlig kostnad for AI-analysen, i kroner.

Listepris per million tokens fra Anthropic (dollar), ganget med dagens kurs
fra Norges Bank. Rabatt for caching og batch er ikke regnet med, og heller
ikke mva. Tallene er derfor et anslag, ikke en faktura.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

# Dollar per million tokens (inn, ut). Listepris per 25.9.2026.
PRISER = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-fable-5-1": (10.00, 50.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Brukes hvis Norges Bank ikke svarer. Kursen 2.10.2026.
RESERVEKURS = (9.6494, "2026-10-02")

NORGES_BANK = ("https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP"
               "?lastNObservations=1&format=sdmx-json")


def kurs() -> tuple[float, str, bool]:
    """(NOK per USD, dato, hentet nå). Siste publiserte kurs fra Norges Bank."""
    try:
        req = urllib.request.Request(NORGES_BANK, headers={"User-Agent": "kommunelys-drift"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))["data"]
        serie = next(iter(d["dataSets"][0]["series"].values()))
        verdi = float(next(iter(serie["observations"].values()))[0])
        dato = d["structure"]["dimensions"]["observation"][0]["values"][-1]["id"]
        return verdi, dato, True
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, StopIteration,
            json.JSONDecodeError) as e:
        print(f"advarsel: fikk ikke hentet dollarkursen ({e}), bruker {RESERVEKURS[0]}")
        return RESERVEKURS[0], RESERVEKURS[1], False


def dollar(tokens_per_modell: dict[str, list[int]]) -> tuple[float, list[str]]:
    """(dollar, modeller uten kjent pris)."""
    sum_, ukjent = 0.0, []
    for modell, (inn, ut) in tokens_per_modell.items():
        if modell not in PRISER:
            ukjent.append(modell)
            continue
        p_inn, p_ut = PRISER[modell]
        sum_ += inn / 1e6 * p_inn + ut / 1e6 * p_ut
    return sum_, ukjent
