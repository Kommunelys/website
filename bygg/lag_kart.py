"""Lager kartet på forsiden: kommunegrensene i Trøndelag, forenklet.

Grensene er Kartverkets, klippet etter kystlinjen og gjort om til GeoJSON i
robhop/fylker-og-kommuner (CC BY 4.0). Kartverkets eget kommuneinfo-API gir
grensene ut i sjøen, og da forsvinner kysten og fjordene. Grensene forenkles,
projiseres til et lite koordinatsystem og lagres i kommuner/kart/. Bygget
leser bare den lagrede filen, så kartet krever ikke nett ved hvert bygg.
Kjøres på nytt når kommunegrensene endres.

Trøndelag er de gamle fylkene Nord- og Sør-Trøndelag. Kommunenavnene står i
kommuner/kart/, ikke i malen, fordi malen ikke skal nevne noen kommune.

    python -m bygg.lag_kart
"""

from __future__ import annotations

import json
import math
import time
import urllib.request
from pathlib import Path

KILDE = ("https://raw.githubusercontent.com/robhop/fylker-og-kommuner/"
         "main/Kommuner-M.geojson")
FYLKE = "50"  # Trøndelag
UT = Path(__file__).resolve().parent.parent / "kommuner" / "kart" / "trondelag.json"

BREDDE = 600          # bredden på kartet i SVG-enheter
TOLERANSE = 0.6       # forenkling, i SVG-enheter
MIN_AREAL = 0.8       # mindre øyer enn dette (SVG-enheter²) tas ikke med


def _hent() -> dict:
    with urllib.request.urlopen(KILDE, timeout=120) as svar:
        return json.load(svar)


def _forenkle(pkt: list, tol: float) -> list:
    """Douglas–Peucker, uten rekursjon."""
    if len(pkt) < 3:
        return pkt
    behold = [False] * len(pkt)
    behold[0] = behold[-1] = True
    stabel = [(0, len(pkt) - 1)]
    while stabel:
        a, b = stabel.pop()
        (x1, y1), (x2, y2) = pkt[a], pkt[b]
        dx, dy = x2 - x1, y2 - y1
        lengde = math.hypot(dx, dy) or 1e-12
        maks, idx = 0.0, None
        for i in range(a + 1, b):
            x, y = pkt[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / lengde
            if d > maks:
                maks, idx = d, i
        if idx is not None and maks > tol:
            behold[idx] = True
            stabel += [(a, idx), (idx, b)]
    return [p for p, k in zip(pkt, behold) if k]


def _areal(ring: list) -> float:
    return abs(sum(x1 * y2 - x2 * y1
                   for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]))) / 2


def kjor() -> None:
    kommuner = []
    for f in _hent()["features"]:
        k, geo = f["properties"], f["geometry"]
        if not k["kommunenummer"].startswith(FYLKE):
            continue
        flater = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        kommuner.append((k, flater))
    kommuner.sort(key=lambda kf: kf[0]["kommunenummer"])

    # Enkel projeksjon: lengdegrader krympes med cosinus til midtbredden.
    alle = [p for _, fl in kommuner for f in fl for r in f for p in r]
    lon0, lon1 = min(p[0] for p in alle), max(p[0] for p in alle)
    lat0, lat1 = min(p[1] for p in alle), max(p[1] for p in alle)
    kos = math.cos(math.radians((lat0 + lat1) / 2))
    skala = BREDDE / ((lon1 - lon0) * kos)
    hoyde = (lat1 - lat0) * skala

    def proj(p):
        return ((p[0] - lon0) * kos * skala, (lat1 - p[1]) * skala)

    ut = []
    for k, flater in kommuner:
        deler = []
        # Bare ytre ringer; innsjøer og hull er for små til å synes.
        for flate in flater:
            # En lukket ring har samme start og slutt; del den i to halvdeler
            # så forenklingen har en linje å måle avstanden mot.
            pkt = [proj(p) for p in flate[0]]
            m = len(pkt) // 2
            ring = _forenkle(pkt[:m + 1], TOLERANSE)[:-1] + _forenkle(pkt[m:], TOLERANSE)
            if len(ring) >= 4 and _areal(ring) >= MIN_AREAL:
                deler.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in ring[:-1]) + "Z")
        ut.append({"kommunenr": k["kommunenummer"], "navn": k["kommunenavn"],
                   "d": "".join(deler)})

    UT.parent.mkdir(parents=True, exist_ok=True)
    UT.write_text(json.dumps({
        "kilde": "Kartverket (CC BY 4.0), klippet etter kysten i robhop/fylker-og-kommuner",
        "hentet": time.strftime("%Y-%m-%d"),
        "bredde": BREDDE, "hoyde": round(hoyde, 1),
        "kommuner": ut,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{UT.relative_to(UT.parent.parent.parent)}: {len(ut)} kommuner, "
          f"{UT.stat().st_size // 1024} kB")


if __name__ == "__main__":
    kjor()
