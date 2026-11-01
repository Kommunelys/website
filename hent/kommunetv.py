"""Klient mot kommunens opptak av møtene (Aventia Online Video Platform).

Steinkjer sender kommunestyret på steinkjer.kommunetv.no. Plattformen har et
åpent JSON-API, og opptakene går som HLS fra en egen vert. Er opptaket tekstet,
har strømmen et undertekstspor i WebVTT med tidskoder. Det er bare teksten vi
bruker; videoen lastes ikke ned og vises ikke på nettstedet.

Adressen står under «opptak» i kommuner/<slug>.json. Uten feltet har kommunen
ingen opptak. Takten er den samme som mot innsynsportalen: ett kall i sekundet,
én tråd, identifiserbar klient (ADR-007).

    archive/<opptak>?caseId=<bokmerke>   åpner opptaket på starten av en sak
"""

from __future__ import annotations

import datetime as dt
import re
import zoneinfo

from .portal import KONTAKT, Henter

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


class OpptakFeil(Exception):
    """Opptakstjenesten svarte ikke slik vi forventer."""


_henter = Henter("opptak", OpptakFeil)


def _hent(url: str, *, som_json: bool = True):
    """Ett kall, med pause etterpå. 404 betyr at opptaket er borte."""
    return _henter.hent(url, {"User-Agent": KONTAKT}, None if som_json else (lambda d: d.decode("utf-8")))


def oppsett() -> dict | None:
    """«opptak» i kommuner/<slug>.json, eller None om kommunen ikke har opptak."""
    from lager import kommune  # noqa: PLC0415

    return kommune.oppsett().get("opptak")


def _basis() -> str:
    o = oppsett()
    if not o:
        raise OpptakFeil("kommunen har ikke «opptak» i kommuner/<slug>.json")
    return o["basis"].rstrip("/")


def arkiv() -> list[dict]:
    """Alle opptakene i arkivet, med id, dato, tittel og kategori."""
    d = _hent(f"{_basis()}/api/search?noRetry=true&page=1&pageSize=500&type=Archive")
    if not isinstance(d, dict) or not isinstance(d.get("data"), list):
        raise OpptakFeil("arkivet ga ikke en liste")
    if d.get("total", 0) > len(d["data"]):
        raise OpptakFeil(f"arkivet har {d['total']} opptak, men bare {len(d['data'])} kom med")
    return d["data"]


def opptak(opptak_id: int) -> dict:
    """Ett opptak: bokmerkene (sakene) og spillelisten med tidspunktene."""
    d = _hent(f"{_basis()}/api/streams?streamType=1&id={opptak_id}")
    if not isinstance(d, dict) or "stream" not in d or "bookmarks" not in d:
        raise OpptakFeil(f"opptak {opptak_id} mangler felter")
    return d


def lenke(opptak_id: int, bokmerke_id: int | None = None) -> str:
    """Adressen til opptaket, på starten av en sak hvis bokmerket er gitt."""
    url = f"{_basis()}/archive/{opptak_id}"
    return f"{url}?caseId={bokmerke_id}" if bokmerke_id else url


def strom(d: dict) -> str | None:
    """Adressen til HLS-strømmen, uten tidsparametrene."""
    for kamera in d.get("playlist") or []:
        for p in kamera.get("playlist") or []:
            if p.get("file"):
                return p["file"].split("?")[0]
    return None


_TID = re.compile(r"wowzaplaystart=(\d+)&wowzaplayduration=(\d+)")


def deler(d: dict) -> list[dict]:
    """Bokmerkene med start og varighet i ms fra starten av opptaket.

    Tidspunktene står i spillelisten, ikke i bokmerket. Bokmerkene settes for
    hånd under møtet og er unøyaktige: en sak kan starte før bokmerket, og
    slutten av ett bokmerke kan handle om en annen sak.
    """
    tid = {}
    for kamera in d.get("playlist") or []:
        for p in kamera.get("playlist") or []:
            m = _TID.search(p.get("file") or "")
            if m:
                tid[p["bookmarkId"]] = (int(m[1]), int(m[2]))
    ut = []
    for b in d["bookmarks"]:
        if b["id"] not in tid or b.get("isPause"):
            continue
        start, varighet = tid[b["id"]]
        ut.append({
            "bokmerke_id": b["id"],
            "nummer": (b.get("number") or "").strip(),
            "tittel": b.get("title") or "",
            "start_ms": start,
            "varighet_ms": varighet,
        })
    return sorted(ut, key=lambda x: x["start_ms"])


def har_teksting(master: str) -> str | None:
    """Adressen til tekstsporet i master-spillelisten, relativt til strømmen."""
    m = re.search(r'#EXT-X-MEDIA:TYPE=SUBTITLES[^\n]*URI="([^"]+)"', master)
    return m[1] if m else None


_KLOKKE = re.compile(r"(\d+):(\d\d):(\d\d)\.(\d{3}) --> (\d+):(\d\d):(\d\d)\.(\d{3})")


def _ms(t: tuple[str, ...]) -> int:
    return ((int(t[0]) * 60 + int(t[1])) * 60 + int(t[2])) * 1000 + int(t[3])


def les_vtt(tekst: str) -> list[dict]:
    """Linjene i én WebVTT-bit: start og slutt i ms, og teksten på én linje."""
    ut = []
    for blokk in re.split(r"\r?\n\r?\n+", tekst):
        linjer = blokk.strip().splitlines()
        for i, l in enumerate(linjer):
            m = _KLOKKE.match(l.strip())
            if m:
                t = " ".join(x.strip() for x in linjer[i + 1:] if x.strip())
                if t:
                    ut.append({"start_ms": _ms(m.groups()[:4]), "slutt_ms": _ms(m.groups()[4:]),
                               "tekst": t})
                break
    return ut


def teksting(strom_url: str) -> tuple[list[dict], list[str]] | None:
    """Hele tekstingen for et opptak, eller None om det ikke er tekstet.

    Gir linjene i rekkefølge og de rå WebVTT-bitene (de lagres urørt).
    """
    rot = strom_url.rsplit("/", 1)[0] + "/"
    uri = har_teksting(_hent(strom_url, som_json=False))
    if not uri:
        return None
    liste = _hent(rot + uri, som_json=False)
    biter = [l.strip() for l in liste.splitlines() if l.strip() and not l.startswith("#")]
    raa, linjer = [], []
    for b in biter:
        t = _hent(rot + b, som_json=False)
        raa.append(t)
        linjer += les_vtt(t)
    # Bitene kan overlappe i kantene. Samme linje to ganger tas bare med én gang.
    sett, unike = set(), []
    for l in sorted(linjer, key=lambda x: x["start_ms"]):
        k = (l["start_ms"], l["tekst"])
        if k not in sett:
            sett.add(k)
            unike.append(l)
    return unike, raa


def lokal_dato(d: dict) -> str:
    """Datoen opptaket ble sendt, i norsk tid (publishDate er UTC)."""
    t = dt.datetime.fromisoformat(d["stream"]["publishDate"].replace("Z", "+00:00"))
    return t.astimezone(OSLO).date().isoformat()


def saksnr(nummer: str, aar: int) -> str | None:
    """«PS 47/26» i bokmerket blir «PS 47/2026» som i saksgangen. Andre bokmerker
    (kulturinnslag, opprop, spørsmål til ordføreren) har ikke saksnummer."""
    m = re.fullmatch(r"(PS|RS)\s*(\d+)\s*/\s*(\d{2}|\d{4})", nummer or "")
    if not m:
        return None
    a = int(m[3])
    if a < 100:
        a += aar // 100 * 100
    return f"{m[1]} {int(m[2])}/{a}"
