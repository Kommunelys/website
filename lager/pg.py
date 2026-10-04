"""Lesing fra databasen, i samme form som filene i data/ har.

Brukes når KOMMUNELYS_LAGER=pg. Hver funksjon her svarer til en `les`-
funksjon i lager/, og skal gi nøyaktig det samme tilbake, også rekkefølgen
på nøklene: den havner i nettstedets data.js. lager.paritet kontrollerer det.

Svarene huskes i prosessen: et bygg spør om det samme mange ganger, og
hver spørring går over nett. glem() tømmer minnet etter skriving. Hver
gang gis en kopi, så den som endrer svaret, ikke endrer minnet.

Tekst hentes bare når den trengs. Fingeravtrykket (md5) av all tekst er
lite og hentes samlet; selve teksten hentes per dokument, eller samlet med
forhandslast().
"""

from __future__ import annotations

import copy
import datetime as dt
import functools
import os

_tilkobling = None
_kommune: int | None = None
_minne: dict = {}
_tekster: dict[tuple[str, int], str] = {}
_avtrykk: dict[tuple[str, int], str] | None = None
_MANGLER = object()


def glem() -> None:
    """Tøm det som er husket, for eksempel etter at noe er skrevet."""
    global _avtrykk
    _minne.clear()
    _tekster.clear()
    _avtrykk = None


def _husket(funksjon):
    """Husker svaret per argument. «standard» (som i lager/) brukes når
    databasen ikke har dataene, og er ikke en del av nøkkelen."""
    @functools.wraps(funksjon)
    def ny(*args, standard=()):
        nokkel = (funksjon.__name__, args)
        if nokkel not in _minne:
            try:
                _minne[nokkel] = funksjon(*args)
            except FileNotFoundError:
                _minne[nokkel] = _MANGLER
        verdi = _minne[nokkel]
        if verdi is _MANGLER:
            if standard:
                return standard[0]
            raise FileNotFoundError(f"databasen har ikke {funksjon.__name__}{args}")
        return copy.deepcopy(verdi)

    def med_standard(*args):
        # lager/ kaller f(aar, *standard); skill året fra standardverdien.
        n = funksjon.__code__.co_argcount
        return ny(*args[:n], standard=args[n:])
    return med_standard


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
    global _kommune
    if _kommune is None:
        slug = os.environ.get("KOMMUNELYS_KOMMUNE", "steinkjer")
        rad = _rader("select kommune_id from kjerne.kommune where slug = %s", slug)
        if not rad:
            raise SystemExit(f"fant ikke kommunen {slug} i databasen")
        _kommune = rad[0][0]
    return _kommune


def _sortert(d: dict) -> dict:
    """Filene skrives med sort_keys, så nøklene kommer sortert."""
    return dict(sorted(d.items()))


def _dato(verdi) -> str | None:
    return verdi.isoformat() if verdi is not None else None


def _tidspunkt(verdi: dt.datetime | None) -> str:
    """Som i filene: «2026-01-08T14:30», eller tom streng når den er ukjent."""
    return verdi.strftime("%Y-%m-%dT%H:%M") if verdi else ""


def _mangler(hva: str):
    raise FileNotFoundError(f"databasen har ingen {hva}")


# Rådata --------------------------------------------------------------------

@_husket
def moteliste(aar: int):
    rad = _rader("select innhold from kjerne.raa_svar where kommune_id = %s and kilde = 'moteliste' "
                 "and nokkel = %s order by hentet desc, id desc limit 1", kommune_id(), str(aar))
    return rad[0][0] if rad else None


@_husket
def moter_raa(aar: int):
    liste = moteliste(aar)
    if liste is None:
        return None
    ider = [str(m["MO_ID"]) for m in liste]
    return [r[0] for r in _rader(
        "select distinct on (nokkel collate \"C\") innhold from kjerne.raa_svar "
        "where kommune_id = %s and kilde = 'mote' and nokkel = any(%s) "
        "order by nokkel collate \"C\", hentet desc, id desc", kommune_id(), ider)]


@_husket
def medlemslister():
    return [r[0] for r in _rader(
        "select distinct on (nokkel collate \"C\") innhold from kjerne.raa_svar "
        "where kommune_id = %s and kilde = 'medlemsliste' "
        "order by nokkel collate \"C\", hentet desc, id desc", kommune_id())]


# Saker og møter ---------------------------------------------------------------

@_husket
def saker(aar: int):
    k = kommune_id()
    rader = _rader("select sak_id, tittel, skjermet_tittel, sakstype, formalia, status, til_kommunestyret "
                   "from kjerne.sak where kommune_id = %s and aar = %s order by rekkefolge", k, aar)
    if not rader:
        return _mangler(f"saker for {aar}")

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


@_husket
def moter(aar: int):
    k = kommune_id()
    rader = _rader("select mote_id, dato, slutt, utvalg, utvalg_navn, sted, rom, antall_saker, url "
                   "from kjerne.mote where kommune_id = %s and extract(year from dato) = %s "
                   "order by dato, mote_id::text collate \"C\"", k, aar)
    if not rader:
        return _mangler(f"møter for {aar}")
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

@_husket
def voteringer(aar: int):
    k = kommune_id()
    poster = _rader(
        "select vt.behandling_id, st.dato, st.sak_id, st.saksnr, st.utvalg, vt.vedtak "
        "from kjerne.vedtak_tolket vt "
        "join kjerne.saksgang_steg st using (kommune_id, behandling_id) "
        "join kjerne.sak s on s.kommune_id = st.kommune_id and s.sak_id = st.sak_id "
        "where vt.kommune_id = %s and s.aar = %s order by st.dato, vt.behandling_id", k, aar)
    if not poster:
        return _mangler(f"voteringer for {aar}")

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

@_husket
def oppmote(aar: int):
    k = kommune_id()
    moter_ = _rader(
        "select om.mote_id, m.dato, m.utvalg, om.ikke_tolket from kjerne.oppmote_mote om "
        "join kjerne.mote m using (kommune_id, mote_id) "
        "where om.kommune_id = %s and extract(year from m.dato) = %s order by m.dato, om.mote_id", k, aar)
    if not moter_:
        return _mangler(f"oppmøte for {aar}")
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


@_husket
def utvalg(aar: int):
    k = kommune_id()
    rader = _rader(
        "select ua.utvalg_id, u.kortnavn, u.navn, ua.faste_medlemmer, ua.varamedlemmer, ua.moter, "
        "ua.medlemsliste_hentet from kjerne.utvalg_aar ua join kjerne.utvalg u using (kommune_id, utvalg_id) "
        "where ua.kommune_id = %s and ua.aar = %s order by ua.utvalg_id", k, aar)
    if not rader:
        return _mangler(f"utvalg for {aar}")
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


@_husket
def verv(aar: int):
    ut = _verv(" and v.aar = %s", aar)
    return ut if ut else _mangler(f"verv for {aar}")


@_husket
def verv_alle_aar() -> list[dict]:
    aar = [r[0] for r in _rader("select distinct aar from kjerne.verv where kommune_id = %s order by aar",
                                kommune_id())]
    return [v for a in aar for v in _verv(" and v.aar = %s", a)]


# Avvik og vurderinger -----------------------------------------------------------

@_husket
def avvik(aar: int):
    """Avvikene slik tolk.bygg_avvik skrev dem, med gjeldende vurdering."""
    k = kommune_id()
    rader = _rader("select avvik, type, utvalg, dato, beskrivelse, kilde from kjerne.avvik "
                   "where kommune_id = %s and aktiv and extract(year from dato) = %s "
                   "order by dato, avvik collate \"C\"", k, aar)
    if not rader:
        return _mangler(f"avvik for {aar}")
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


@_husket
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


@_husket
def analyser() -> dict[int, dict]:
    return {r[0]: _analyse(r) for r in _rader(_ANALYSE + " order by sak_id", kommune_id())}


# Det som vedlikeholdes for hånd ----------------------------------------------------

@_husket
def partisider() -> dict:
    rader = _rader("select kode, url, url_tekst, url_kontrollert from kjerne.parti "
                   "where kommune_id = %s and url is not null order by kode collate \"C\"", kommune_id())
    kontrollert = max((r[3] for r in rader if r[3]), default=None)
    return {"kontrollert": _dato(kontrollert),
            "partier": {kode: {"url": url, "tekst": tekst} for kode, url, tekst, _ in rader}}


@_husket
def tillatte_navn() -> list[dict]:
    return [{"navn": navn, "sak_id": sak_id, "begrunnelse": begrunnelse, "vurdert": _dato(vurdert)}
            for navn, sak_id, begrunnelse, vurdert in _rader(
                "select navn, sak_id, begrunnelse, vurdert from kjerne.tillatt_navn "
                "where kommune_id = %s order by navn, sak_id", kommune_id())]


# Tekst -------------------------------------------------------------------------------

_NOKKEL = ("case when d.slag = 'moteprotokoll' then 'mote' else d.id_rom end, "
           "case when d.slag = 'moteprotokoll' then d.mote_id else d.portal_id end")


def tekst_avtrykk() -> dict[tuple[str, int], str]:
    """md5 av hver tekst, etter (ID-rom, ID) som i lager.tekst. Lite: ett kall."""
    global _avtrykk
    if _avtrykk is None:
        _avtrykk = {(rom, ident): md5 for rom, ident, md5 in _rader(
            f"select {_NOKKEL}, md5(t.tekst) from kjerne.dokument_tekst t "
            "join kjerne.dokument d on d.kommune_id = t.kommune_id and d.id = t.dokument_id "
            "where t.kommune_id = %s", kommune_id())}
    return _avtrykk


def forhandslast(nokler) -> None:
    """Henter teksten for mange dokumenter i ett kall."""
    mangler = [n for n in set(nokler) if n in tekst_avtrykk() and n not in _tekster]
    if not mangler:
        return
    for rom, ident, innhold in _rader(
            f"select {_NOKKEL}, t.tekst from kjerne.dokument_tekst t "
            "join kjerne.dokument d on d.kommune_id = t.kommune_id and d.id = t.dokument_id "
            f"where t.kommune_id = %s and ({_NOKKEL}) in (select * from unnest(%s::text[], %s::int[]))",
            kommune_id(), [r for r, _ in mangler], [i for _, i in mangler]):
        _tekster[(rom, ident)] = innhold


def tekst(id_rom: str, ident: int | None) -> str | None:
    if not ident or (id_rom, ident) not in tekst_avtrykk():
        return None
    if (id_rom, ident) not in _tekster:
        forhandslast([(id_rom, ident)])
    return _tekster.get((id_rom, ident))


# Kontrollen av sammendragene ---------------------------------------------------------

def kontroller(grunnlag: dict[int, str]) -> dict[int, list[str]]:
    """Resultatene som alt finnes for gjeldende analyse med samme grunnlag, per sak."""
    ut = {}
    for sak_id, g, grunner in _rader(
            "select a.sak_id, k.grunnlag, k.grunner from kjerne.analyse_gjeldende a "
            "join kjerne.analyse_kontroll k on k.kommune_id = a.kommune_id and k.analyse_id = a.id "
            "where a.kommune_id = %s and k.grunnlag is not null order by k.kontrollert", kommune_id()):
        if grunnlag.get(sak_id) == g:
            ut[sak_id] = list(grunner)
    return ut


def lagre_kontroller(resultater: dict[int, tuple[str, list[str]]]) -> None:
    """Nye kontrollresultater, for gjeldende analyse av hver sak."""
    if not resultater:
        return
    _c().cursor().executemany(
        "insert into kjerne.analyse_kontroll (kommune_id, analyse_id, bestatt, grunner, grunnlag) "
        "select kommune_id, id, %s, %s, %s from kjerne.analyse_gjeldende where kommune_id = %s and sak_id = %s",
        [(not grunner, grunner, g, kommune_id(), sak_id) for sak_id, (g, grunner) in resultater.items()])


# Kjøreloggen og tellingen --------------------------------------------------------------

# Rekkefølgen drift.logg legger tallene inn i.
_KJORING_NOKLER = {"portal": ["kall", "feil", "megabyte", "sekunder"],
                   "analyse": ["sendt", "feil", "utsatt", "tokens_inn", "tokens_ut"]}


def _tall(verdi):
    """numeric -> int eller float, som i filen (round(..., 1) gir 1.7, men 90)."""
    return float(verdi) if verdi.as_tuple().exponent < 0 else int(verdi)


def _orden(navn: str, orden: list[str]) -> tuple:
    return (orden.index(navn) if navn in orden else len(orden), navn)


@_husket
def kjoringer() -> dict:
    """Kjøreloggen slik drift.logg skriver den: bare kjøringer med tall."""
    tall: dict[str, dict] = {}
    for kid, del_, nokkel, verdi in _rader(
            "select kjoring_id, del, nokkel, verdi from drift.kjoring_tall "
            "where kommune_id = %s or kommune_id is null", kommune_id()):
        tall.setdefault(kid, {}).setdefault(del_, {})[nokkel] = _tall(verdi)
    ut = {}
    for kid, start in _rader("select kjoring_id, start from drift.kjoring where kjoring_id = any(%s) "
                             "order by start, kjoring_id", list(tall)):
        post = {"start": start.astimezone(dt.timezone.utc).isoformat(timespec="seconds")}
        for del_ in sorted(tall[kid], key=lambda d: _orden(d, list(_KJORING_NOKLER))):
            orden = _KJORING_NOKLER.get(del_, [])
            post[del_] = {n: tall[kid][del_][n] for n in sorted(tall[kid][del_], key=lambda n: _orden(n, orden))}
        ut[kid] = post
    return ut


@_husket
def forrige_telling() -> dict[str, int]:
    return {str(aar): saker for aar, saker in _rader(
        "select distinct on (aar) aar, saker from drift.bygg where kommune_id = %s "
        "order by aar, bygget desc", kommune_id())}
