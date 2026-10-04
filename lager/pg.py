"""Lesing fra databasen, i samme form som filene i data/ har.

Brukes når KOMMUNELYS_LAGER=pg. Hver funksjon her svarer til en `les`-
funksjon i lager/, og skal gi nøyaktig det samme tilbake, også rekkefølgen
på nøklene: den havner i nettstedets data.js. lager.paritet kontrollerer det.

Fase 2: bare lesing. Skriving går fortsatt til filene, og
forrige telling, måling og kjøreloggen leses fortsatt derfra.
"""

from __future__ import annotations

import datetime as dt
import os

_tilkobling = None
_tekster: dict[tuple[str, int], str] | None = None


def _c():
    global _tilkobling
    if _tilkobling is None:
        import psycopg  # noqa: PLC0415

        from . import db  # noqa: PLC0415

        _tilkobling = psycopg.connect(db.url(), connect_timeout=15, autocommit=True)
    return _tilkobling


def _rader(sql: str, *args) -> list[tuple]:
    return _c().execute(sql, args).fetchall()


def kommune_id() -> int:
    slug = os.environ.get("KOMMUNELYS_KOMMUNE", "steinkjer")
    rad = _rader("select kommune_id from kjerne.kommune where slug = %s", slug)
    if not rad:
        raise SystemExit(f"fant ikke kommunen {slug} i databasen")
    return rad[0][0]


def _sortert(d: dict) -> dict:
    """Filene skrives med sort_keys, så nøklene kommer sortert."""
    return dict(sorted(d.items()))


def _dato(verdi) -> str | None:
    return verdi.isoformat() if verdi is not None else None


def _tidspunkt(verdi: dt.datetime | None) -> str:
    """Som i filene: «2026-01-08T14:30», eller tom streng når den er ukjent."""
    return verdi.strftime("%Y-%m-%dT%H:%M") if verdi else ""


def _mangler(hva: str, standard: tuple):
    if standard:
        return standard[0]
    raise FileNotFoundError(f"databasen har ingen {hva}")


# Rådata --------------------------------------------------------------------

def moteliste(aar: int):
    rad = _rader("select innhold from kjerne.raa_svar where kommune_id = %s and kilde = 'moteliste' "
                 "and nokkel = %s order by hentet desc, id desc limit 1", kommune_id(), str(aar))
    return rad[0][0] if rad else None


def moter_raa(aar: int):
    liste = moteliste(aar)
    if liste is None:
        return None
    ider = [str(m["MO_ID"]) for m in liste]
    return [r[0] for r in _rader(
        "select distinct on (nokkel collate \"C\") innhold from kjerne.raa_svar "
        "where kommune_id = %s and kilde = 'mote' and nokkel = any(%s) "
        "order by nokkel collate \"C\", hentet desc, id desc", kommune_id(), ider)]


def medlemslister():
    return [r[0] for r in _rader(
        "select distinct on (nokkel collate \"C\") innhold from kjerne.raa_svar "
        "where kommune_id = %s and kilde = 'medlemsliste' "
        "order by nokkel collate \"C\", hentet desc, id desc", kommune_id())]


# Saker og møter ---------------------------------------------------------------

def saker(aar: int, *standard):
    k = kommune_id()
    rader = _rader("select sak_id, tittel, skjermet_tittel, sakstype, formalia, status, til_kommunestyret "
                   "from kjerne.sak where kommune_id = %s and aar = %s order by rekkefolge", k, aar)
    if not rader:
        return _mangler(f"saker for {aar}", standard)

    steg: dict[int, list] = {}
    for (sak_id, bid, dato, hentet, mote_id, publisert, skjermet, saksnr, url_mote, url_vedtak,
         utvalg, utvalg_navn) in _rader(
            "select st.sak_id, st.behandling_id, st.dato, st.hentet, st.mote_id, st.protokoll_publisert, "
            "st.protokoll_skjermet, st.saksnr, st.url_mote, st.url_vedtak, st.utvalg, st.utvalg_navn "
            "from kjerne.saksgang_steg st join kjerne.sak s using (kommune_id, sak_id) "
            "where st.kommune_id = %s and s.aar = %s order by st.sak_id, st.rekkefolge", k, aar):
        steg.setdefault(sak_id, []).append(_sortert({
            "behandling_id": bid, "dato": _tidspunkt(dato), "hentet": hentet, "mote_id": mote_id,
            "protokoll_publisert": publisert, "protokoll_skjermet": skjermet, "saksnr": saksnr,
            "url_mote": url_mote, "url_vedtak": url_vedtak, "utvalg": utvalg, "utvalg_navn": utvalg_navn}))

    framlegg: dict[int, dict] = {}
    vedlegg: dict[int, list] = {}
    for sak_id, slag, portal_id, tittel, fmt, url in _rader(
            "select d.sak_id, d.slag, d.portal_id, d.tittel, d.format, d.url "
            "from kjerne.dokument d join kjerne.sak s using (kommune_id, sak_id) "
            "where d.kommune_id = %s and s.aar = %s and d.slag in ('saksframlegg', 'vedlegg') "
            "order by d.sak_id, d.rekkefolge", k, aar):
        post = {"dokument_id": portal_id, "format": fmt, "tittel": tittel, "url": url}
        if slag == "saksframlegg":
            framlegg[sak_id] = post
        else:
            vedlegg.setdefault(sak_id, []).append(post)

    return [_sortert({
        "sak_id": sak_id, "tittel": tittel, "skjermet_tittel": skjermet, "sakstype": sakstype,
        "formalia": formalia, "status": status, "til_kommunestyret": til_ks,
        "saksgang": steg.get(sak_id, []), "saksframlegg": framlegg.get(sak_id),
        "vedlegg": vedlegg.get(sak_id, [])})
        for sak_id, tittel, skjermet, sakstype, formalia, status, til_ks in rader]


def moter(aar: int, *standard):
    k = kommune_id()
    rader = _rader("select mote_id, dato, slutt, utvalg, utvalg_navn, sted, rom, antall_saker, url "
                   "from kjerne.mote where kommune_id = %s and extract(year from dato) = %s "
                   "order by dato, mote_id::text collate \"C\"", k, aar)
    if not rader:
        return _mangler(f"møter for {aar}", standard)
    dokumenter: dict[int, list] = {}
    for mote_id, slag, tittel, url in _rader(
            "select mote_id, slag, tittel, url from kjerne.dokument where kommune_id = %s "
            "and slag in ('moteinnkalling', 'moteprotokoll') order by mote_id, rekkefolge", k):
        dokumenter.setdefault(mote_id, []).append(
            {"tittel": tittel, "type": "MI" if slag == "moteinnkalling" else "MP", "url": url})
    return [_sortert({
        "mote_id": mote_id, "dato": _tidspunkt(dato), "slutt": slutt, "utvalg": utvalg,
        "utvalg_navn": utvalg_navn, "sted": sted, "rom": rom, "antall_saker": antall,
        "dokumenter": dokumenter.get(mote_id, []), "url": url})
        for mote_id, dato, slutt, utvalg, utvalg_navn, sted, rom, antall, url in rader]


# Voteringer --------------------------------------------------------------------

def voteringer(aar: int, *standard):
    k = kommune_id()
    poster = _rader(
        "select vt.behandling_id, st.dato, st.sak_id, st.saksnr, st.utvalg, vt.vedtak "
        "from kjerne.vedtak_tolket vt "
        "join kjerne.saksgang_steg st using (kommune_id, behandling_id) "
        "join kjerne.sak s on s.kommune_id = st.kommune_id and s.sak_id = st.sak_id "
        "where vt.kommune_id = %s and s.aar = %s order by st.dato, vt.behandling_id", k, aar)
    if not poster:
        return _mangler(f"voteringer for {aar}", standard)

    stemmer: dict[tuple, dict] = {}
    for bid, nr, valg, forslag, parti, navn in _rader(
            "select st.behandling_id, st.nr, st.valg, st.alternativ_forslag, st.parti, p.navn "
            "from kjerne.stemme st join kjerne.person p on p.kommune_id = st.kommune_id and p.id = st.person_id "
            "where st.kommune_id = %s order by st.behandling_id, st.nr, st.valg, st.rekkefolge", k):
        s = stemmer.setdefault((bid, nr), {"for": [], "mot": [], "ikke_til_stede": [], "alt": {}, "partier": {}})
        if valg == "alternativ":
            s["alt"].setdefault(forslag, []).append((navn, parti))
        else:
            s[valg].append(navn)
        if valg != "ikke_til_stede":
            s["partier"][navn] = parti

    alternativer: dict[tuple, list] = {}
    for bid, nr, forslag, antall in _rader(
            "select behandling_id, nr, forslag, antall from kjerne.votering_alternativ "
            "where kommune_id = %s order by behandling_id, nr, rekkefolge", k):
        navn = stemmer.get((bid, nr), {}).get("alt", {}).get(forslag, [])
        alternativer.setdefault((bid, nr), []).append({
            "antall": antall, "forslag": forslag, "navn": [n for n, _ in navn],
            "partier": _sortert({n: p for n, p in navn})})

    per_post: dict[int, list] = {}
    for (bid, nr, type_, tekst, resultat, resultat_tekst, enstemmig, antall_for, antall_mot,
         forslagsstiller, parti, dobbeltstemme, tall_stemmer) in _rader(
            "select behandling_id, nr, type, tekst, resultat, resultat_tekst, enstemmig, antall_for, "
            "antall_mot, forslagsstiller, parti, dobbeltstemme, tall_stemmer from kjerne.votering "
            "where kommune_id = %s order by behandling_id, nr", k):
        s = stemmer.get((bid, nr), {"for": [], "mot": [], "ikke_til_stede": [], "partier": {}})
        per_post.setdefault(bid, []).append({
            "alternativer": alternativer.get((bid, nr), []), "antall_for": antall_for, "antall_mot": antall_mot,
            "dobbeltstemme": dobbeltstemme, "enstemmig": enstemmig, "for": s["for"],
            "forslagsstiller": forslagsstiller, "ikke_til_stede": s["ikke_til_stede"], "mot": s["mot"],
            "nr": nr, "parti": parti, "partier": _sortert(s["partier"]), "resultat": resultat,
            "resultat_tekst": resultat_tekst, "saksnr": None, "tall_stemmer": tall_stemmer,
            "tekst": tekst, "type": type_})

    ut = []
    for bid, dato, sak_id, saksnr, utvalg, vedtak in poster:
        liste = per_post.get(bid, [])
        for v in liste:
            v["saksnr"] = saksnr
        ut.append({"behandling_id": bid, "dato": _tidspunkt(dato), "sak_id": sak_id, "saksnr": saksnr,
                   "utvalg": utvalg, "vedtak": vedtak, "voteringer": liste})
    return ut


# Oppmøte, utvalg og verv -----------------------------------------------------------

def oppmote(aar: int, *standard):
    k = kommune_id()
    moter_ = _rader(
        "select om.mote_id, m.dato, m.utvalg, om.ikke_tolket from kjerne.oppmote_mote om "
        "join kjerne.mote m using (kommune_id, mote_id) "
        "where om.kommune_id = %s and extract(year from m.dato) = %s order by m.dato, om.mote_id", k, aar)
    if not moter_:
        return _mangler(f"oppmøte for {aar}", standard)
    rader: dict[int, list] = {}
    for mote_id, navn, funksjon, repr_, vara in _rader(
            "select o.mote_id, p.navn, o.funksjon, o.repr, v.navn from kjerne.oppmote o "
            "join kjerne.person p on p.kommune_id = o.kommune_id and p.id = o.person_id "
            "left join kjerne.person v on v.kommune_id = o.kommune_id and v.id = o.vara_for_person_id "
            "where o.kommune_id = %s order by o.mote_id, o.rekkefolge", k):
        rader.setdefault(mote_id, []).append(
            {"funksjon": funksjon, "navn": navn, "repr": repr_, "vara_for": vara})
    avvik: dict[int, list] = {}
    for mote_id, bid, nr, type_, navn, stemmer_, frammotte in _rader(
            "select mote_id, behandling_id, votering_nr, type, navn, stemmer, frammotte "
            "from kjerne.oppmote_avvik where kommune_id = %s order by mote_id, rekkefolge", k):
        post = {"behandling_id": bid, "type": type_, "votering": nr}
        if navn is not None:
            post["navn"] = navn
        if stemmer_ is not None:
            post.update(stemmer=stemmer_, frammotte=frammotte)
        avvik.setdefault(mote_id, []).append(_sortert(post))
    return [{"avvik": avvik.get(mote_id, []), "dato": _tidspunkt(dato), "ikke_tolket": ikke_tolket,
             "mote_id": mote_id, "oppmote": rader.get(mote_id, []), "utvalg": utvalg}
            for mote_id, dato, utvalg, ikke_tolket in moter_]


def utvalg(aar: int, *standard):
    k = kommune_id()
    rader = _rader(
        "select ua.utvalg_id, u.kortnavn, u.navn, ua.faste_medlemmer, ua.varamedlemmer, ua.moter, "
        "ua.medlemsliste_hentet from kjerne.utvalg_aar ua join kjerne.utvalg u using (kommune_id, utvalg_id) "
        "where ua.kommune_id = %s and ua.aar = %s order by ua.utvalg_id", k, aar)
    if not rader:
        return _mangler(f"utvalg for {aar}", standard)
    partier = {kode: navn for kode, navn in _rader(
        "select kode, navn from kjerne.parti where kommune_id = %s", k)}
    return {
        "medlemsliste_hentet": _dato(rader[0][6]) or "",
        "partier": _sortert(partier),
        "utvalg": [{"faste_medlemmer": faste, "kortnavn": kort, "moter": antall, "navn": navn,
                    "utvalg_id": uid, "varamedlemmer": vara}
                   for uid, kort, navn, faste, vara, antall, _ in rader],
    }


def _verv(sql_aar: str, *args) -> list[dict]:
    ut = [_sortert({
        "navn": navn, "utvalg_id": uid, "utvalg": kort, "person_id": portal_id, "rolle": rolle,
        "repr": repr_, "i_dagens_liste": dagens, "i_medlemslister": [_dato(d) for d in lister],
        "moter_som": _sortert(moter_som), "forst_motte": _dato(forst), "sist_motte": _dato(sist),
        "motte_for": list(motte_for)})
        for navn, uid, kort, portal_id, rolle, repr_, dagens, lister, moter_som, forst, sist, motte_for in _rader(
            "select p.navn, v.utvalg_id, u.kortnavn, v.portal_person_id, v.rolle, v.repr, v.i_dagens_liste, "
            "v.i_medlemslister, v.moter_som, v.forst_motte, v.sist_motte, v.motte_for "
            "from kjerne.verv v join kjerne.person p on p.kommune_id = v.kommune_id and p.id = v.person_id "
            "join kjerne.utvalg u on u.kommune_id = v.kommune_id and u.utvalg_id = v.utvalg_id "
            "where v.kommune_id = %s" + sql_aar, kommune_id(), *args)]
    # Samme rekkefølge som tolk.bygg_verv skriver.
    return sorted(ut, key=lambda v: (v["utvalg"] or "", v["rolle"] or "~", v["navn"]))


def verv(aar: int, *standard):
    ut = _verv(" and v.aar = %s", aar)
    return ut if ut else _mangler(f"verv for {aar}", standard)


def verv_alle_aar() -> list[dict]:
    aar = [r[0] for r in _rader("select distinct aar from kjerne.verv where kommune_id = %s order by aar",
                                kommune_id())]
    return [v for a in aar for v in _verv(" and v.aar = %s", a)]


# Avvik og vurderinger -----------------------------------------------------------

def avvik(aar: int, *standard):
    """Avvikene slik tolk.bygg_avvik skrev dem, med gjeldende vurdering."""
    k = kommune_id()
    rader = _rader("select avvik, type, utvalg, dato, beskrivelse, kilde from kjerne.avvik "
                   "where kommune_id = %s and aktiv and extract(year from dato) = %s "
                   "order by dato, avvik collate \"C\"", k, aar)
    if not rader:
        return _mangler(f"avvik for {aar}", standard)
    voteringer_: dict[str, list] = {}
    for nokkel, bid, nr in _rader("select avvik, behandling_id, nr from kjerne.avvik_votering "
                                  "where kommune_id = %s order by avvik, rekkefolge", k):
        voteringer_.setdefault(nokkel, []).append([bid, nr])
    vurdert = {v["avvik"]: v for v in vurderinger()}
    ut = []
    for nokkel, type_, utv, dato, beskrivelse, kilde in rader:
        post = {"avvik": nokkel, "beskrivelse": beskrivelse, "dato": _dato(dato), "type": type_,
                "utvalg": utv, "voteringer": voteringer_.get(nokkel, [])}
        if kilde is not None:
            post["kilde"] = kilde
        v = vurdert.get(nokkel)
        post.update(vurdering=_sortert(v) if v else None, status=v["avgjorelse"] if v else "ikke_vurdert")
        ut.append(_sortert(post))
    return ut


def vurderinger() -> list[dict]:
    return [{"avvik": a, "avgjorelse": avg, "merknad": merknad, "begrunnelse": begrunnelse,
             "vurdert_av": vurdert_av, "dato": _dato(dato)}
            for a, avg, merknad, begrunnelse, vurdert_av, dato in _rader(
                "select avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato "
                "from kjerne.vurdering_gjeldende where kommune_id = %s order by id", kommune_id())]


# Analyse --------------------------------------------------------------------------

_ANALYSE = ("select sak_id, tittel_klarsprak, sammendrag, betydning, tagger, utfall, uenighet, usikker, "
            "sjekksum, modell, innsats, instruksjon_versjon, dato, tokens_inn, tokens_ut, kilder "
            "from kjerne.analyse_gjeldende where kommune_id = %s")


def _analyse(rad: tuple) -> dict:
    (sak_id, tittel, sammendrag, betydning, tagger, utfall, uenighet, usikker, sjekksum, modell,
     innsats, versjon, dato, inn, ut, kilder) = rad
    # Samme rekkefølge som analyser_saker skriver: modellens svar først.
    return {"tittel_klarsprak": tittel, "sammendrag": sammendrag, "betydning": betydning,
            "tagger": list(tagger), "utfall": utfall, "uenighet": uenighet, "usikker": usikker,
            "sak_id": sak_id, "sjekksum": sjekksum, "modell": modell, "innsats": innsats,
            "instruksjon_versjon": versjon, "dato": _dato(dato), "tokens": {"inn": inn, "ut": ut},
            "kilder": [{"tittel": k["tittel"], "url": k["url"]} for k in kilder]}


def analyse(sak_id: int) -> dict | None:
    rader = _rader(_ANALYSE + " and sak_id = %s", kommune_id(), sak_id)
    return _analyse(rader[0]) if rader else None


def analyser() -> dict[int, dict]:
    return {r[0]: _analyse(r) for r in _rader(_ANALYSE + " order by sak_id", kommune_id())}


# Det som vedlikeholdes for hånd ----------------------------------------------------

def partisider() -> dict:
    rader = _rader("select kode, url, url_tekst, url_kontrollert from kjerne.parti "
                   "where kommune_id = %s and url is not null order by kode collate \"C\"", kommune_id())
    kontrollert = max((r[3] for r in rader if r[3]), default=None)
    return {"kontrollert": _dato(kontrollert),
            "partier": {kode: {"url": url, "tekst": tekst} for kode, url, tekst, _ in rader}}


def tillatte_navn() -> list[dict]:
    return [{"navn": navn, "sak_id": sak_id, "begrunnelse": begrunnelse, "vurdert": _dato(vurdert)}
            for navn, sak_id, begrunnelse, vurdert in _rader(
                "select navn, sak_id, begrunnelse, vurdert from kjerne.tillatt_navn "
                "where kommune_id = %s order by navn, sak_id", kommune_id())]


# Tekst -------------------------------------------------------------------------------

def _alle_tekster() -> dict[tuple[str, int], str]:
    """All tekst for kommunen, lest én gang (rundt 6 MB per år)."""
    global _tekster
    if _tekster is None:
        _tekster = {}
        for id_rom, portal_id, mote_id, slag, innhold in _rader(
                "select d.id_rom, d.portal_id, d.mote_id, d.slag, t.tekst from kjerne.dokument_tekst t "
                "join kjerne.dokument d on d.kommune_id = t.kommune_id and d.id = t.dokument_id "
                "where t.kommune_id = %s", kommune_id()):
            if slag == "moteprotokoll":
                _tekster[("mote", mote_id)] = innhold
            else:
                _tekster[(id_rom, portal_id)] = innhold
    return _tekster


def tekst(id_rom: str, ident: int) -> str | None:
    return _alle_tekster().get((id_rom, ident))

