"""Driftssiden: hva tjenesten har gjort, i tabeller og nøkkeltall.

Alt på siden er tall fra drift.historikk og dataene, satt inn i faste
tabeller. Ingenting skrives av en språkmodell (CLAUDE.md, regel 2). Siden
lenkes ikke fra resten av nettstedet og har noindex, men den er offentlig som
alt annet i repoet.

Siden bygges på nytt hver gang Oppdater kjører. Besøkstallene hentes i
nettleseren fra GoatCounter, så de er ferske uansett når siden ble bygget.

Klokkeslett vises i norsk tid. Python på Windows har ikke tidssonedata uten
pakken tzdata, så sommertiden regnes ut her (EU-regelen: siste søndag i mars
til siste søndag i oktober, kl. 01 UTC).
"""

from __future__ import annotations

import datetime as dt
import html
import os

from drift import historikk, kostnad

MANEDER = ("jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des")


# ---------- Formatering ----------

def _siste_sondag(aar: int, maned: int) -> dt.datetime:
    d = dt.datetime(aar, maned + 1, 1, 1, tzinfo=dt.timezone.utc) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def norsk_tid(t: dt.datetime) -> dt.datetime:
    t = t.astimezone(dt.timezone.utc)
    sommer = _siste_sondag(t.year, 3) <= t < _siste_sondag(t.year, 10)
    return (t + dt.timedelta(hours=2 if sommer else 1)).replace(tzinfo=None)


def tidspunkt(t: dt.datetime) -> str:
    """«03.10 22:08»."""
    return f"{norsk_tid(t):%d.%m %H:%M}"


def dato(t: dt.datetime) -> str:
    n = norsk_tid(t)
    return f"{n.day}. {MANEDER[n.month - 1]}"


def tall(n: float, desimaler: int = 0) -> str:
    return f"{n:,.{desimaler}f}".replace(",", " ").replace(".", ",")


def kroner(nok: float) -> str:
    return f"{tall(nok, 1 if nok < 10 else 0)} kr"


def varighet(sek: float) -> str:
    sek = round(sek)
    return f"{sek // 60}:{sek % 60:02d}"


def _e(s) -> str:
    return html.escape(str(s))


# ---------- Utfall ----------

def _jobber(p: dict) -> dict[str, str | None]:
    """Jobbresultat etter rolle, uavhengig av nøyaktig jobbnavn."""
    ut = {}
    for j in p.get("jobber") or []:
        navn = j["navn"].lower()
        rolle = ("proeve" if "prøve" in navn else "hent" if "hent" in navn
                 else "analyse" if "analyse" in navn else "bygg" if "bygg" in navn else navn)
        ut[rolle] = j["resultat"] if j.get("status") == "completed" else "pågår"
    return ut


def utfall(p: dict) -> tuple[str, str]:
    """(merke, merknad). Merknaden er tom når alt gikk som vanlig."""
    if p["id"] is None:
        return "lagret", "Commit uten kjent kjøring (eldre eller lokal)"
    if p["status"] != "completed":
        if p["id"] == os.environ.get("GITHUB_RUN_ID"):
            return "pågår", "Denne kjøringen bygget siden"
        return "pågår", ""
    j = _jobber(p)
    if p["resultat"] == "cancelled":
        return "avbrutt", "Avbrutt"
    if j.get("proeve") not in (None, "skipped"):
        return ("ok" if j["proeve"] == "success" else "feilet"), "Prøveanalyse, ikke lagret"
    if j.get("hent") == "failure":
        return "feilet", "Innhenting feilet, ingenting publisert"
    if j.get("bygg") == "failure":
        return "feilet", "Kontroll eller bygg feilet, ikke publisert"
    if j.get("analyse") == "failure":
        return "delvis", "Analyse feilet, publisert uten nye sammendrag"
    return ("ok", "") if p["resultat"] == "success" else ("feilet", "")


MERKER = {"ok": "OK", "feilet": "Feilet", "delvis": "Delvis", "avbrutt": "Avbrutt",
          "pågår": "Pågår", "lagret": "Commit"}


def _merke(m: str) -> str:
    return f'<span class="drift-merke {m.replace("å", "a")}">{MERKER[m]}</span>'


JOBB = {"success": ("✓", "ok", "Gikk bra"), "failure": ("✗", "feilet", "Feilet"),
        "skipped": ("–", "", "Hoppet over"), "cancelled": ("✗", "delvis", "Avbrutt"),
        "pågår": ("…", "", "Pågår")}


def _jobbcelle(resultat: str | None) -> str:
    if resultat is None:
        return '<td class="drift-jobb"></td>'
    tegn, klasse, tekst = JOBB.get(resultat, ("?", "", resultat))
    return (f'<td class="drift-jobb {klasse}" title="{_e(tekst)}">'
            f'<span aria-hidden="true">{tegn}</span><span class="vh">{_e(tekst)}</span></td>')


# ---------- Bokser ----------

def _kv(rader: list[tuple[str, str]]) -> str:
    return ('<table class="drift-kv"><tbody>'
            + "".join(f'<tr><th scope="row">{_e(k)}</th><td class="num">{v}</td></tr>'
                      for k, v in rader)
            + "</tbody></table>")


def _status(poster: list[dict], na: dt.datetime) -> str:
    kj = [p for p in poster if p["id"] is not None]
    ferdige = [p for p in kj if p["status"] == "completed"]
    uke = [p for p in kj if p["start"] and p["start"] >= na - dt.timedelta(days=7)]
    feilet = sum(1 for p in uke if utfall(p)[0] in ("feilet", "delvis"))
    kall = [(p["logg"].get("portal") or {}) for p in uke]
    n_kall = sum(int(k.get("kall", 0)) for k in kall)
    sek = sum(k.get("sekunder", 0) for k in kall)
    endret = next((c["tid"] for p in poster for c in p["commits"]
                   if c["nye_moter"] or c["nye_saker"] or c["ny_status"] or c["nye_dokumenter"]
                   or c["nye_voteringer"] or c["nye_protokoller"]), None)
    rader = []
    if ferdige:
        p = ferdige[0]
        rader.append(("Siste kjøring", f"{tidspunkt(p['start'])} {_merke(utfall(p)[0])}"))
    rader += [
        ("Tidsplan", "På" if historikk.tidsplan_er_pa() else "Av, kjøres for hånd"),
        ("Kjøringer, 7 dager", f"{len(uke)}" + (f" ({feilet} med feil)" if feilet else "")),
        ("Kall mot portalen, 7 dager",
         (f"{tall(n_kall)} ({tall(sek / n_kall, 1)} s per kall)" if n_kall else "ikke målt ennå")),
        ("Sist nytt fra portalen", tidspunkt(endret) if endret else "–"),
        ("Siden bygget", tidspunkt(na)),
    ]
    return _kv(rader)


def _innhold(status: dict, avvik: dict[str, int], poster: list[dict], na: dt.datetime) -> str:
    def nye(dager: int) -> int:
        fra = na - dt.timedelta(days=dager)
        return sum(1 for p in poster for c in p["commits"] if c["tid"] >= fra
                   for s in c["nye_saker"] if not s.get("formalia"))
    holdt = len(status.get("sammendrag_holdt_tilbake") or [])
    return _kv([
        (f"Saker {status['ar']}", tall(status["saker"])),
        (f"Møter {status['ar']}", tall(status["moter"])),
        ("Nye saker, 7 / 30 dager", f"{nye(7)} / {nye(30)}"),
        ("Sammendrag vist", f"{tall(status['sammendrag_publisert'])} av {tall(status['analyser'])}"
         + (f" ({holdt} holdt tilbake)" if holdt else "")),
        ("Voteringer der stemmene ikke vises", tall(status.get("voteringer_holdt_tilbake", 0))),
        ("Avvik ikke vurdert", tall(avvik.get("ikke_vurdert", 0))),
        *_dekning(status),
    ])


def _prosent(andel: float | None) -> str:
    return "–" if andel is None else f"{tall(andel * 100)} %"


def _dekning(status: dict) -> list[tuple[str, str]]:
    """Hvor mye av protokollene regelsettet leser (tolk/dekning.py)."""
    d = status.get("dekning")
    if not d:
        return []
    mistenkt = d["mistenkt"]
    return [
        ("Voteringer lest", _prosent(d["voteringer"])
         + (f" ({mistenkt} {'protokoll' if mistenkt == 1 else 'protokoller'} uten treff)" if mistenkt else "")),
        ("Oppmøte lest", _prosent(d["oppmote"])),
    ]


def kommuner(rader: list[tuple[dict, dict, str]]) -> str:
    """Én rad per kommune: (oppsett, status.json, utfallet av bygget)."""
    if not rader:
        return '<p class="liten muted">Ingen kommuner ble bygget.</p>'
    av = {True: "med", False: "uten"}
    linjer = []
    for k, s, utfall in rader:
        n = s.get("nivaa") or {}
        d = s.get("dekning") or {}
        linjer.append(
            f'<tr><td>{_e(k["navn"])}</td><td>{_e(utfall)}</td>'
            f'<td>{_e(str(s.get("bygget", "–")).replace("T", " ")[:16])}</td>'
            f'<td>{av[n.get("voteringer", True)]} stemmer, {av[n.get("oppmote", True)]} oppmøte</td>'
            f'<td class="num">{_prosent(d.get("voteringer"))}</td>'
            f'<td class="num">{_prosent(d.get("oppmote"))}</td></tr>')
    return ('<div class="tw"><table class="drift-tabell"><thead><tr><th>Kommune</th><th>Bygget</th>'
            '<th>Data fra</th><th>Nivå</th><th class="num">Voteringer lest</th>'
            f'<th class="num">Oppmøte lest</th></tr></thead><tbody>{"".join(linjer)}</tbody></table></div>')


def _kostnad(analyser: dict, poster: list[dict], na: dt.datetime,
             kurs: tuple[float, str, bool]) -> str:
    nok_per_usd, kursdato, _ = kurs
    ute: dict[str, list[int]] = {}
    for a in analyser.values():
        t = a.get("tokens") or {}
        m = ute.setdefault(a.get("modell") or "ukjent", [0, 0])
        m[0] += t.get("inn", 0)
        m[1] += t.get("ut", 0)
    usd_ute, ukjent = kostnad.dollar(ute)

    def brukt(dager: int) -> float:
        fra = na - dt.timedelta(days=dager)
        tpm = historikk.sum_endringer(
            [c for p in poster for c in p["commits"] if c["tid"] >= fra])["tokens_per_modell"]
        return kostnad.dollar(tpm)[0] * nok_per_usd

    inn = sum(v[0] for v in ute.values())
    ut = sum(v[1] for v in ute.values())
    modeller = ", ".join(
        f"{m} ${kostnad.PRISER[m][0]:g} / ${kostnad.PRISER[m][1]:g}"
        for m in sorted(ute) if m in kostnad.PRISER)
    rader = [
        ("Brukt siste 7 dager", f"≈ {kroner(brukt(7))}"),
        ("Brukt siste 30 dager", f"≈ {kroner(brukt(30))}"),
        ("Snitt per sammendrag",
         f"≈ {kroner(usd_ute * nok_per_usd / len(analyser))}" if analyser else "–"),
        ("Tokens inn / ut", f"{tall(inn / 1e6, 2)} M / {tall(ut / 1e6, 2)} M"),
        ("Kurs USD", f"{tall(nok_per_usd, 2)} kr ({kursdato[8:10]}.{kursdato[5:7]})"),
    ]
    merknad = (f"Listepris per million tokens inn / ut: {_e(modeller)}. "
               "Uten rabatt for caching og uten mva. Kurs fra Norges Bank. "
               "«Brukt» tar med sammendrag som er skrevet på nytt.")
    if ukjent:
        merknad += f" Ukjent pris for {_e(', '.join(ukjent))}, ikke regnet med."
    return (f'<p class="drift-stort">≈ {kroner(usd_ute * nok_per_usd)}</p>'
            f'<p class="liten muted drift-under">for de {tall(len(analyser))} '
            "sammendragene som ligger ute</p>"
            + _kv(rader) + f'<p class="liten muted">{merknad}</p>')


def _database(na: dt.datetime) -> str:
    """Boksen om databasen. Før byttet: er filene i git og databasen like?

    Fram til byttet speiles data/ inn i databasen ved hver kjøring, og
    lager.paritet sammenligner alt tegn for tegn. Svarer ikke databasen,
    står det her; resten av siden bygges likevel.
    """
    from lager import fra_databasen  # noqa: PLC0415

    kilde = ("Kilde for nettstedet", "Databasen" if fra_databasen() else "Filene i git (data/)")
    try:
        from lager import pg  # noqa: PLC0415

        o = pg.overgang()
    except (Exception, SystemExit) as e:  # noqa: BLE001 (databasen trengs ikke for bygget)
        print(f"advarsel: fikk ikke lest overgangen fra databasen ({e})")
        return _kv([kilde]) + '<p class="liten muted">Databasen svarte ikke da siden ble bygget.</p>'

    k = o["kontroller"]
    if fra_databasen():
        return _database_etter_byttet(o, k)
    rader = [kilde]
    if k:
        siste = k[0]
        merke = ('<span class="drift-merke ok">Like</span>' if siste["likt"]
                 else '<span class="drift-merke feilet">Ulike</span>')
        rader.append(("Siste kontroll", f"{tidspunkt(siste['tid'])} {merke}"))
        rekke = next((i for i, x in enumerate(k) if not x["likt"]), len(k))
        rader.append(("Like på rad", f"{rekke}" + (f" (siden {dato(k[rekke - 1]['tid'])})" if rekke else "")))
        fjorten = [x for x in k if x["tid"] >= na - dt.timedelta(days=14)]
        rader.append(("Like, 14 dager", f"{sum(x['likt'] for x in fjorten)} av {len(fjorten)}"))
    else:
        rader.append(("Siste kontroll", "ingen ennå"))
    if o["speiling"]:
        _, start, endringer = o["speiling"]
        rader.append(("Siste speiling", f"{tidspunkt(start)}, {tall(endringer)} endringer"))
    rader.append(("Størrelse", _e(o["storrelse"])))

    ulike = ""
    if k and not k[0]["likt"]:
        ulike = ('<p class="liten">Dette skilte ved siste kontroll:</p><ul class="liten">'
                 + "".join(f"<li>{_e(u['navn'])}: {_e(u['hvor'])}</li>" for u in k[0]["ulike"][:10])
                 + "</ul>")
    return (_kv(rader) + ulike
            + '<p class="liten muted">Før byttet speiles dataene inn i databasen ved hver kjøring, '
            "og alt sammenlignes tegn for tegn med filene. Nettstedet bygges fra filene til "
            "databasen har vært lik over tid.</p>")


def _database_etter_byttet(o: dict, k: list[dict]) -> str:
    """Databasen er kilden (ADR-019): siste kjøring, og kontrollene før byttet."""
    rader = [("Kilde for nettstedet", "Databasen")]
    if o["kjoring"]:
        _, start, endringer = o["kjoring"]
        rader.append(("Siste kjøring", f"{tidspunkt(start)}, {tall(endringer)} endringer"))
    if k:
        like = sum(x["likt"] for x in k)
        rader.append(("Kontroller før byttet",
                      f"{like} av {len(k)} like ({dato(k[-1]['tid'])}–{dato(k[0]['tid'])})"))
    rader.append(("Størrelse", _e(o["storrelse"])))
    return (_kv(rader)
            + '<p class="liten muted">Dataene ligger i en database (Postgres i Supabase), og en '
            "kopi tas hver natt. Før byttet 6.10.2026 ble databasen sammenlignet tegn for tegn "
            "med filene i git ved hver kjøring.</p>")


# ---------- Tabeller ----------

def _celle(v, kjent: bool = True) -> str:
    if not kjent:
        return '<td class="num muted">–</td>'
    tekst = tall(v) if isinstance(v, int) else _e(v)
    return f'<td class="num{" muted" if not v else ""}">{tekst}</td>'


def _kjoringer(poster: list[dict], nok_per_usd: float) -> str:
    rader = []
    for p in poster[:40]:
        merke, merknad = utfall(p)
        e = historikk.sum_endringer(p["commits"])
        j = _jobber(p)
        hentet = j.get("hent") == "success" or bool(p["commits"])
        pl = p["logg"].get("portal") or {}
        sek = ((p["slutt"] - p["start"]).total_seconds()
               if p["id"] and p["status"] == "completed" and p["start"] and p["slutt"] else None)
        nye_saker = sum(1 for s in e["nye_saker"] if not s.get("formalia"))
        usd = kostnad.dollar(e["tokens_per_modell"])[0]
        utlost = {"workflow_dispatch": "hånd", "schedule": "plan"}.get(p.get("utlost"), "")
        logg = (f'<a href="{_e(p["url"])}" title="Logg i GitHub">#{_e(p.get("nr") or "")}</a>'
                if p.get("url") else "")
        moter = f"{e['moter_sjekket']}/{e['moter_hentet']}" if e.get("moter_sjekket") else ""
        sammendrag = (f"{e.get('nye_sammendrag', 0)}/{e.get('oppdaterte_sammendrag', 0)}"
                      if e.get("nye_sammendrag") or e.get("oppdaterte_sammendrag") else 0)
        rader.append(
            "<tr>"
            f"<td>{_merke(merke)}</td>"
            f'<td class="num">{tidspunkt(p["start"]) if p["start"] else ""}</td>'
            f"<td>{logg}</td>"
            f'<td class="muted">{utlost}</td>'
            f'<td class="num">{varighet(sek) if sek is not None else ""}</td>'
            + _jobbcelle(j.get("hent")) + _jobbcelle(j.get("analyse")) + _jobbcelle(j.get("bygg"))
            + _celle(int(pl.get("kall", 0)), bool(pl))
            + f'<td class="num">{_e(moter)}</td>'
            + _celle(e.get("nye_moter", 0), hentet)
            + _celle(nye_saker, hentet)
            + _celle(e.get("nye_dokumenter", 0), hentet)
            + _celle(e.get("nye_voteringer", 0), hentet)
            + _celle(sammendrag)
            + f'<td class="num">{kroner(usd * nok_per_usd) if usd else ""}</td>'
            + f'<td class="liten">{_e(merknad)}</td>'
            "</tr>")
    hode = ("<tr><th>Status</th><th>Start</th><th>Kjøring</th><th>Utløst</th>"
            '<th class="num">Tid</th><th title="Hent og tolk">Hent</th><th>Analyse</th>'
            '<th title="Bygg og publiser">Bygg</th><th class="num">Kall</th>'
            '<th class="num" title="Møter sjekket / hentet på nytt">Møter s/h</th>'
            '<th class="num">Nye møter</th><th class="num">Nye saker</th>'
            '<th class="num">Nye dok.</th><th class="num">Nye vot.</th>'
            '<th class="num" title="Nye / oppdaterte sammendrag">Sammendrag n/o</th>'
            '<th class="num">Kostnad</th><th>Merknad</th></tr>')
    return (f'<div class="tw"><table class="drift-tabell"><thead>{hode}</thead>'
            f'<tbody>{"".join(rader)}</tbody></table></div>')


def _nye_saker(poster: list[dict], na: dt.datetime) -> str:
    fra = na - dt.timedelta(days=30)
    rader = []
    for p in poster:
        for c in p["commits"]:
            if c["tid"] < fra:
                continue
            for s in c["nye_saker"]:
                if s.get("formalia"):
                    continue
                t = _e(s["tittel"]) if s.get("tittel") else "<i>Tittel skjermet</i>"
                lenke = f'<a href="{_e(s["url"])}">{t}</a>' if s.get("url") else t
                rader.append(f'<tr><td class="num">{dato(c["tid"])}</td>'
                             f'<td class="num">{_e(s["id"])}</td><td>{lenke}</td></tr>')
    if not rader:
        return '<p class="muted">Ingen nye saker de siste 30 dagene.</p>'
    return ('<div class="tw"><table class="drift-tabell"><thead><tr><th>Funnet</th>'
            '<th class="num">Sak-ID</th><th>Tittel (lenke til møtet i portalen)</th></tr></thead>'
            f'<tbody>{"".join(rader)}</tbody></table></div>')


def side(mal: str, fyll, status: dict, kommune: dict, avvik: dict[str, int],
         analyser: dict, merke: str, repo: str, goatcounter: str, nettsted: str,
         alle_kommuner: str = "") -> str:
    na = dt.datetime.now(dt.timezone.utc)
    kj = historikk.kjoringer()
    poster = historikk.tidslinje(kj, historikk.endringer())
    kurs = kostnad.kurs()
    kjoringer = _kjoringer(poster, kurs[0])
    if kj is None:
        kjoringer = ('<p class="liten">Kjøringene kunne ikke hentes fra GitHub da siden ble '
                     "bygget. Tabellen viser bare commits med data.</p>" + kjoringer)
    return fyll(mal, {
        "merke": merke,
        "kommune": _e(kommune["navn"]),
        "bygget": tidspunkt(na),
        "versjon": f"{na:%Y%m%d%H%M}",
        "status": _status(poster, na),
        "innhold": _innhold(status, avvik, poster, na),
        "kostnad": _kostnad(analyser, poster, na, kurs),
        "database": _database(na),
        "kjoringer": kjoringer,
        "nye_saker": _nye_saker(poster, na),
        "kommuner": alle_kommuner,
        "goatcounter": _e(goatcounter),
        "repo": repo,
        "nettsted": nettsted,
    })
