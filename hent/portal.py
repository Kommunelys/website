"""Klient mot kommunenes innsynsportal (Elements Publikum).

All kontakt med portalen går gjennom denne modulen, slik at takt, header og
feilhåndtering er likt overalt. Se docs/02-api.md for endepunktene.

Adressen, tenant og databasen er kommunens kilde (lager.kommune.kilde), og
hentes første gang de trengs. Kommunene kjøres etter tur, aldri samtidig, så
takten gjelder samlet for verten (ADR-007, ADR-021).
"""

from __future__ import annotations

import atexit
import contextlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# ADR-007: lav takt, én tråd, identifiserbar klient.
PAUSE_SEKUND = 1.0
KONTAKT = "kommunelys (uoffisiell innsynstjeneste; kontakt: post@kommunelys.no)"


@dataclass(frozen=True)
class Kilde:
    """Hvor kommunens innsynsportal ligger i Elements."""
    basis: str
    tenant: str
    database: str


_kilde: Kilde | None = None


def bruk(kilde: Kilde | dict | None) -> None:
    """Sett kilden for denne prosessen. None betyr: les den fra kommunen."""
    global _kilde
    _kilde = Kilde(**kilde) if isinstance(kilde, dict) else kilde


def kilde() -> Kilde:
    if _kilde is None:
        from lager import kommune  # noqa: PLC0415
        bruk(kommune.kilde())
    return _kilde


def _headere() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "tenant": kilde().tenant,
        "User-Agent": KONTAKT,
    }


class PortalFeil(Exception):
    """Portalen svarte ikke slik vi forventer."""


class Avvist(PortalFeil):
    """Portalen avviser oss: 401 eller 403, 429 i alle forsøkene, eller en side
    som ikke er data. Vi kan være blokkert. Hentingen for kommunen stopper med
    en gang, og kjøringen blir rød (kjor.alle)."""

    def __str__(self) -> str:
        return f"innsynsportalen avviser oss: {self.args[0]}."


# Utgangskoden når portalen avviser oss, så kjor.alle kan si det tydelig.
AVVIST = 4


@contextlib.contextmanager
def stopp_ved_avvisning():
    """Rundt main i trinnene som henter fra portalen: Avvist gir AVVIST."""
    try:
        yield
    except Avvist as e:
        print(f"\nstopper: {e}", flush=True)
        raise SystemExit(AVVIST) from e


class Henter:
    """Ett kall i sekundet, én tråd og identifiserbar klient (ADR-007), med nye
    forsøk ved feil og tellingen til kjøreloggen (drift.logg), som viser på
    driftssiden at takten holdes. Felles for innsynsportalen og opptakene
    (hent.kommunetv). `del_` er navnet i kjøreloggen, `feil` unntaket som kastes."""

    def __init__(self, del_: str, feil: type[Exception], avvist: type[Exception] | None = None) -> None:
        self.del_, self.feil, self.avvist = del_, feil, avvist or feil
        self.telling = {"kall": 0, "feil": 0, "byte": 0, "start": None}

    def _logg(self) -> None:
        if not self.telling["kall"]:
            return
        from drift.logg import legg_til  # noqa: PLC0415

        legg_til(self.del_, {
            "kall": self.telling["kall"],
            "feil": self.telling["feil"],
            "megabyte": self.telling["byte"] / 1e6,
            "sekunder": time.monotonic() - self.telling["start"],
        })

    def hent(self, url: str, headere: dict[str, str], les=None, forsok: int = 3):
        """Svaret som JSON, eller gjort om med `les`. Er det ikke JSON når det skal
        være det, prøves det på nytt: en feil adresse kan gi appens forside med 200.

        `avvist` kastes når verten kan ha blokkert oss: 401 eller 403 med en gang,
        og 429 eller svar som ikke er data når også siste forsøk ga det."""
        t, siste = self.telling, None
        if t["start"] is None:
            t["start"] = time.monotonic()
            atexit.register(self._logg)
        for n in range(forsok):
            t["kall"] += 1
            try:
                req = urllib.request.Request(url, headers=headere)
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                t["byte"] += len(data)
                time.sleep(PAUSE_SEKUND)
                return les(data) if les else json.loads(data.decode("utf-8"))
            except urllib.error.HTTPError as e:
                t["feil"] += 1
                # 404 og andre klientfeil blir ikke bedre av nye forsøk. 429 betyr
                # at vi går for fort, og skal vente som andre feil.
                if e.code in (401, 403):
                    time.sleep(PAUSE_SEKUND)
                    raise self.avvist(f"{e.code} {e.reason} på {url}. Vi kan være blokkert") from e
                if 400 <= e.code < 500 and e.code != 429:
                    time.sleep(PAUSE_SEKUND)
                    raise self.feil(f"{e.code} {e.reason}: {url}") from e
                siste = e
                time.sleep(5 * (n + 1))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as e:
                t["feil"] += 1
                siste = e
                time.sleep(5 * (n + 1))
        if isinstance(siste, urllib.error.HTTPError) and siste.code == 429:
            raise self.avvist(f"429 Too Many Requests {forsok} ganger på {url}. Vi kan være blokkert")
        if isinstance(siste, (json.JSONDecodeError, UnicodeDecodeError)):
            raise self.avvist(f"svaret på {url} var ikke data, {forsok} ganger. "
                              "Vi kan være blokkert, eller adressen er feil")
        raise self.feil(f"ga opp etter {forsok} forsøk: {url} ({siste})")


_henter = Henter("portal", PortalFeil, Avvist)


def _hent(url: str, *, binaer: bool = False):
    return _henter.hent(url, _headere(), (lambda d: d) if binaer else None)


def moter(aar: int) -> list[dict]:
    """Alle møter i alle utvalg for ett år."""
    d = _hent(f"{kilde().basis}api/PredefinedQuery/DmbMeetings?year={aar}")
    if not isinstance(d, list):
        raise PortalFeil("DmbMeetings ga ikke en liste")
    for m in d:
        if "MO_ID" not in m or "MO_START" not in m:
            raise PortalFeil(f"møte mangler felter: {m}")
    return d


def mote(mote_id: int) -> dict:
    """Ett møte med møtedokumenter."""
    return _hent(f"{kilde().basis}api/Meetings/{mote_id}")


def saksliste(mote_id: int) -> list[dict]:
    """Sakslisten for ett møte. RegistryEntry er alltid tom her."""
    d = _hent(f"{kilde().basis}api/DmbHandlings/GetByMeetingId/{mote_id}")
    return d if isinstance(d, list) else []


def behandling(behandling_id: int) -> dict:
    """Én behandling med journalpost, dokumenter og saksgang."""
    return _hent(f"{kilde().basis}api/DmbHandlings/{behandling_id}")


def utvalgsmedlemmer(utvalg_id: int) -> list[dict]:
    """Dagens medlemmer og varamedlemmer i ett utvalg, med funksjon og parti.

    Bekreftet 2.10.2026 fra siden «Kalender og medlemmer» i portalen. Utvalgs-ID
    er `UT_ID` fra møtelisten. Gir bare dagens medlemmer, ikke historikk
    (ADR-008). Svaret har også mobilnummer, e-post og kjønn; se
    hent/hent_medlemmer.py for hva som lagres.
    """
    d = _hent(f"{kilde().basis}api/DmbMembers/GetByDmbBoard/{utvalg_id}")
    return d if isinstance(d, list) else []


def hent_fil(url: str) -> bytes:
    """Last ned ett dokument. Kalleren må ha kontrollert skjermingsflagg."""
    return _hent(url, binaer=True)


# --- adresser til dokumenter (docs/02-api.md) ----------------------------


def url_saksprotokoll(behandling_id: int) -> str:
    return f"{kilde().basis}Documents/ShowDmbHandlingDocument/{kilde().database}/{behandling_id}/Protokoll"


def url_motedokument(mote_id: int, typekode: str, dok_id: int) -> str:
    return f"{kilde().basis}Documents/ShowMeetingDocument/{kilde().database}/{mote_id}/{typekode}/{dok_id}"


def url_dokument(journalpost_id: int, dokument_id: int) -> str:
    return f"{kilde().basis}Documents/ShowDocument/{kilde().database}/{journalpost_id}/{dokument_id}"


def url_mote_i_portalen(mote_id: int) -> str:
    """Adressen et menneske kan åpne."""
    return f"{kilde().basis}{kilde().tenant}/DmbMeeting/{mote_id}"
