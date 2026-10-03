"""Driftssiden /drift/: hva tjenesten har gjort, i klartekst.

Teksten settes sammen av faste setninger og tall fra drift.historikk. Den
skrives ikke av en språkmodell, så tallene på siden er de samme som i
dataene (CLAUDE.md, regel 2). Siden lenkes ikke fra resten av nettstedet og
har noindex, men den er offentlig som alt annet i repoet.

Klokkeslett vises i norsk tid. Python på Windows har ikke tidssonedata uten
pakken tzdata, så sommertiden regnes ut her (EU-regelen: siste søndag i mars
til siste søndag i oktober, kl. 01 UTC).
"""

from __future__ import annotations

import datetime as dt
import html
import os

from drift import historikk

UKEDAGER = ("mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag")
MANEDER = ("januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
           "september", "oktober", "november", "desember")


# ---------- Formatering ----------

def _siste_sondag(aar: int, maned: int) -> dt.datetime:
    d = dt.datetime(aar, maned + 1, 1, 1, tzinfo=dt.timezone.utc) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def norsk_tid(t: dt.datetime) -> dt.datetime:
    t = t.astimezone(dt.timezone.utc)
    sommer = _siste_sondag(t.year, 3) <= t < _siste_sondag(t.year, 10)
    return (t + dt.timedelta(hours=2 if sommer else 1)).replace(tzinfo=None)


def tidspunkt(t: dt.datetime, ukedag: bool = True) -> str:
    n = norsk_tid(t)
    dag = f"{UKEDAGER[n.weekday()]} " if ukedag else ""
    return f"{dag}{n.day}. {MANEDER[n.month - 1]} kl. {n:%H.%M}"


def tall(n: float, desimaler: int = 0) -> str:
    s = f"{n:,.{desimaler}f}".replace(",", " ").replace(".", ",")
    return s


def ant(n: int, entall: str, flertall: str) -> str:
    return f"{tall(n)} {entall if n == 1 else flertall}"


def liste(deler: list[str]) -> str:
    if len(deler) <= 1:
        return "".join(deler)
    return ", ".join(deler[:-1]) + " og " + deler[-1]


def varighet(sek: float) -> str:
    if sek < 90:
        return ant(round(sek), "sekund", "sekunder")
    return ant(round(sek / 60), "minutt", "minutter")


def _stor(s: str) -> str:
    return s[:1].upper() + s[1:]


# ---------- Tekst for én kjøring ----------

def _jobber(p: dict) -> dict[str, str | None]:
    """Jobbresultat etter rolle, uavhengig av nøyaktig jobbnavn."""
    ut = {}
    for j in p.get("jobber") or []:
        navn = j["navn"].lower()
        rolle = ("proeve" if "prøve" in navn else "hent" if "hent" in navn
                 else "analyse" if "analyse" in navn else "bygg" if "bygg" in navn else navn)
        ut[rolle] = j["resultat"] if j.get("status") == "completed" else j.get("status")
    return ut


def utfall(p: dict) -> tuple[str, str]:
    """(merke, setning): kort status og hva den betyr."""
    if p["id"] is None:
        return "lagret", ("Endringer lagret uten en kjøring vi kjenner i GitHub Actions: "
                          "en eldre kjøring, eller kjørt lokalt.")
    if p["status"] != "completed":
        if p["id"] == os.environ.get("GITHUB_RUN_ID"):
            return "pågår", "Dette er kjøringen som bygget denne siden."
        return "pågår", "Kjøringen pågikk da siden ble bygget."
    j = _jobber(p)
    if p["resultat"] == "cancelled":
        return "avbrutt", "Kjøringen ble avbrutt."
    if j.get("proeve") not in (None, "skipped"):
        ok = j["proeve"] == "success"
        return ("ok" if ok else "feilet"), (
            "Prøveanalyse av utvalgte saker. Ingenting ble lagret eller publisert"
            + ("." if ok else ", og analysen feilet."))
    if j.get("hent") == "failure":
        return "feilet", "Innhentingen feilet. Ingenting ble oppdatert eller publisert."
    if j.get("bygg") == "failure":
        return "feilet", ("Publiseringen stoppet i kontrollene eller i byggingen. "
                          "Nettstedet er som før.")
    if j.get("analyse") == "failure":
        return "delvis", ("AI-analysen feilet. Nettstedet ble publisert likevel, "
                          "uten nye sammendrag fra denne kjøringen.")
    if p["resultat"] == "success":
        if j:
            return "ok", "Alt gikk som det skulle: data hentet, analysert og publisert."
        return "ok", "Kjøringen gikk bra."
    return "feilet", "Kjøringen feilet."


def _portal(logg: dict, e: dict) -> str | None:
    pl = logg.get("portal")
    deler = []
    if pl and pl.get("kall"):
        s = (f"Innhentingen gjorde {ant(int(pl['kall']), 'kall', 'kall')} mot portalen "
             f"på {varighet(pl.get('sekunder', 0))} ({tall(pl.get('megabyte', 0), 1)} MB)")
        if pl.get("sekunder"):
            s += f", i snitt ett kall hvert {tall(pl['sekunder'] / pl['kall'], 1)} sekund"
        s += "."
        if pl.get("feil"):
            s += f" {ant(int(pl['feil']), 'kall', 'kall')} feilet og ble prøvd på nytt eller hoppet over."
        deler.append(s)
    if e.get("moter_sjekket"):
        deler.append(f"{ant(e['moter_sjekket'], 'møte', 'møter')} ble sjekket mot portalen, "
                     f"og {tall(e['moter_hentet'])} ble hentet på nytt for å se etter endringer.")
    return " ".join(deler) or None


def _data(e: dict) -> str | None:
    saker = [s for s in e.get("nye_saker", []) if not s.get("formalia")]
    deler = [x for x in (
        e.get("nye_moter") and ant(e["nye_moter"], "nytt møte", "nye møter"),
        saker and ant(len(saker), "ny sak", "nye saker"),
        e.get("nye_protokoller") and ant(e["nye_protokoller"], "ny møteprotokoll", "nye møteprotokoller"),
        e.get("nye_voteringer") and ant(e["nye_voteringer"], "ny votering", "nye voteringer"),
        e.get("nye_dokumenter") and f"tekst fra {ant(e['nye_dokumenter'], 'nytt dokument', 'nye dokumenter')}",
    ) if x]
    s = f"Fant {liste(deler)}." if deler else ""
    if e.get("ny_status"):
        s += f" {_stor(ant(e['ny_status'], 'sak', 'saker'))} fikk ny status."
    if e.get("nye_avvik"):
        s += (f" {_stor(ant(e['nye_avvik'], 'nytt avvik', 'nye avvik'))} i voteringene "
              "venter på vurdering.")
    return s.strip() or None


def _analyse(logg: dict, e: dict) -> str | None:
    a = logg.get("analyse") or {}
    deler = []
    nye, oppd = e.get("nye_sammendrag", 0), e.get("oppdaterte_sammendrag", 0)
    if nye or oppd:
        gjort = liste([x for x in (
            nye and f"skrev {ant(nye, 'nytt sammendrag', 'nye sammendrag')}",
            oppd and f"oppdaterte {ant(oppd, 'sammendrag', 'sammendrag')}") if x])
        deler.append(f"Claude {gjort}.")
        if e.get("tokens_inn"):
            deler.append(f"Det gikk med {tall(e['tokens_inn'])} tokens inn og "
                         f"{tall(e['tokens_ut'])} ut.")
    elif a and not a.get("sendt"):
        deler.append("Ingen saker trengte nye sammendrag.")
    if a.get("feil"):
        deler.append(f"{_stor(ant(int(a['feil']), 'svar', 'svar'))} ble forkastet, "
                     "fordi kallet feilet eller svaret ikke besto kontrollen.")
    if a.get("utsatt"):
        deler.append(f"{_stor(ant(int(a['utsatt']), 'sak', 'saker'))} venter til neste kjøring.")
    return " ".join(deler) or None


def _nye_saker(e: dict) -> str:
    saker = [s for s in e.get("nye_saker", []) if not s.get("formalia")]
    if not saker:
        return ""
    li = []
    for s in saker[:30]:
        t = html.escape(s["tittel"]) if s.get("tittel") else "<i>Tittel skjermet</i>"
        li.append(f'<li><a href="{html.escape(s["url"])}">{t}</a></li>' if s.get("url")
                  else f"<li>{t}</li>")
    mer = (f'<li class="muted">… og {len(saker) - 30} til</li>' if len(saker) > 30 else "")
    return (f'<details><summary>{ant(len(saker), "ny sak", "nye saker")}</summary>'
            f'<ul class="drift-saker">{"".join(li)}{mer}</ul></details>')


def _kjoring(p: dict) -> str:
    merke, setning = utfall(p)
    e = historikk.sum_endringer(p["commits"])
    start, slutt = p["start"], p["slutt"]
    om = []
    if p["id"] is not None:
        om.append({"workflow_dispatch": "startet for hånd", "schedule": "planlagt"}
                  .get(p.get("utlost"), p.get("utlost") or ""))
        if p["status"] == "completed" and start and slutt:
            om.append(varighet((slutt - start).total_seconds()))
    avsnitt = [setning] + [x for x in (_portal(p["logg"], e), _data(e), _analyse(p["logg"], e)) if x]
    if (p["id"] is not None and merke in ("ok", "delvis") and not _data(e)
            and _jobber(p).get("hent") == "success"):
        avsnitt.insert(1 + bool(_portal(p["logg"], e)), "Ingen nye møter, saker eller dokumenter.")
    lenke = (f' · <a href="{html.escape(p["url"])}">logg i GitHub</a>' if p.get("url") else "")
    return (f'<article class="drift-kj">'
            f'<h3><span class="drift-merke {merke.replace("å", "a")}">{_stor(merke)}</span> '
            f'{_stor(tidspunkt(start)) if start else "Ukjent tid"}</h3>'
            f'<p class="liten muted">{" · ".join(x for x in om if x)}{lenke}</p>'
            + "".join(f"<p>{html.escape(a)}</p>" for a in avsnitt)
            + _nye_saker(e) + "</article>")


# ---------- Sammendrag øverst ----------

def _naa(poster: list[dict], status: dict, kommune: dict, avvik: dict[str, int]) -> str:
    deler = []
    ferdige = [p for p in poster if p["id"] is not None and p["status"] == "completed"]
    if ferdige:
        p = ferdige[0]
        merke, setning = utfall(p)
        deler.append(f"Siste fullførte kjøring var {tidspunkt(p['start'])}. {setning}")
    tidsplan = ("Kjøringene går automatisk etter en tidsplan." if historikk.tidsplan_er_pa()
                else "Tidsplanen er slått av, så kjøringene startes for hånd.")
    deler.append(tidsplan)
    deler.append(
        f"Nettstedet viser {ant(status['saker'], 'sak', 'saker')} og "
        f"{ant(status['moter'], 'møte', 'møter')} i {kommune['navn']} for {status['ar']}. "
        f"{tall(status['sammendrag_publisert'])} av {tall(status['analyser'])} sammendrag vises")
    holdt = len(status.get("sammendrag_holdt_tilbake") or [])
    deler[-1] += (f"; {tall(holdt)} holdes tilbake fordi de ikke besto kontrollen." if holdt else ".")
    if status.get("voteringer_holdt_tilbake"):
        s = (f"{_stor(ant(status['voteringer_holdt_tilbake'], 'votering', 'voteringer'))} "
             "med avvik i protokollen holdes tilbake.")
        if avvik.get("ikke_vurdert"):
            s += f" {_stor(ant(avvik['ikke_vurdert'], 'avvik', 'avvik'))} er ikke vurdert ennå."
        if avvik.get("venter_paa_kommunen"):
            s += (f" {_stor(ant(avvik['venter_paa_kommunen'], 'avvik', 'avvik'))} "
                  "venter på svar fra kommunen.")
        deler.append(s)
    t = status.get("tokens") or {}
    if t.get("inn"):
        deler.append(f"Sammendragene som ligger ute, kostet til sammen {tall(t['inn'])} tokens "
                     f"inn og {tall(t['ut'])} ut.")
    return "".join(f"<p>{html.escape(d)}</p>" for d in deler)


def _uke(poster: list[dict], na: dt.datetime) -> str:
    fra = na - dt.timedelta(days=7)
    uke = [p for p in poster if p["start"] and p["start"] >= fra]
    kj = [p for p in uke if p["id"] is not None]
    if not uke:
        return "<p>Ingen kjøringer de siste sju dagene.</p>"
    feilet = [p for p in kj if utfall(p)[0] in ("feilet", "delvis")]
    e = historikk.sum_endringer([c for p in uke for c in p["commits"]])
    kall = sum(int((p["logg"].get("portal") or {}).get("kall", 0)) for p in uke)
    deler = [f"{_stor(ant(len(kj), 'kjøring', 'kjøringer'))}"
             + (f", og {tall(len(feilet))} av dem feilet helt eller delvis." if feilet
                else ", og ingen feilet.")]
    for x in (_data(e), _analyse({}, e)):
        if x:
            deler.append(x)
    if not _data(e):
        deler.append("Ingen nye møter eller saker.")
    if kall:
        deler.append(f"Til sammen {ant(kall, 'kall', 'kall')} mot portalen.")
    return "".join(f"<p>{html.escape(d)}</p>" for d in deler) + _nye_saker(e)


def side(mal: str, fyll, status: dict, kommune: dict, avvik: dict[str, int],
         merke: str, repo: str, goatcounter: str) -> str:
    na = dt.datetime.now(dt.timezone.utc)
    kj = historikk.kjoringer()
    poster = historikk.tidslinje(kj, historikk.endringer())
    kjoringer = "".join(_kjoring(p) for p in poster[:40])
    if kj is None:
        kjoringer = ("<p>Kjøringene kunne ikke hentes fra GitHub da siden ble bygget. "
                     "Under står bare endringene i dataene.</p>" + kjoringer)
    return fyll(mal, {
        "merke": merke,
        "bygget": tidspunkt(na),
        "naa": _naa(poster, status, kommune, avvik),
        "uke": _uke(poster, na),
        "kjoringer": kjoringer or "<p>Ingen kjøringer funnet.</p>",
        "goatcounter": html.escape(goatcounter),
        "repo": repo,
    })
