"""Skriving til databasen: gjør tabellene like dataene, med minst mulig endring.

Hver funksjon tar dataene i samme form som filene i data/ har, og gjør
databasen lik dem innenfor et omfang (en kommune og et år): nye rader settes
inn, endrede oppdateres, og rader som ikke lenger finnes, slettes. Uendrede
rader røres ikke, så endringsloggen (drift.endringslogg) bare viser det som
faktisk er endret.

Rådata, analyser og vurderinger slettes aldri; en ny versjon er en ny rad.
Avvik slettes ikke, men settes inaktive.

Unike rekkefølger (sak, saksgang, oppmøte) sjekkes når transaksjonen
avsluttes (DEFERRABLE), så rader kan bytte plass uten mellomsteg.
"""

from __future__ import annotations

import hashlib
import json



def _jsonb(verdi):
    from psycopg.types.json import Jsonb  # noqa: PLC0415

    return Jsonb(verdi)


def _tid(verdi: str | None) -> str | None:
    """«2026-01-08T14:30» eller tom streng -> det Postgres leser, eller None."""
    return verdi.replace("T", " ") if verdi else None


def sjekksum(innhold) -> str:
    kanonisk = json.dumps(innhold, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(kanonisk.encode("utf-8")).hexdigest()


def synk_tabell(c, tabell: str, kolonner: list[str], nokkel: list[str], rader: list[tuple],
                omfang: str | None = None, omfang_args: tuple = (), slett: bool = True) -> dict:
    """Gjør tabellen lik radene innenfor omfanget.

    omfang er et SQL-vilkår på tabellen med aliaset t, for eksempel
    «t.kommune_id = %s and t.aar = %s». Rader utenfor omfanget røres ikke.
    """
    tmp = "synk_" + tabell.split(".")[-1]
    kol = ", ".join(kolonner)
    c.execute(f"create temp table {tmp} as select {kol} from {tabell} limit 0")
    c.cursor().executemany(f"insert into {tmp} ({kol}) values ({', '.join(['%s'] * len(kolonner))})", rader)

    oppdater = [k for k in kolonner if k not in nokkel]
    if oppdater:
        konflikt = (f"do update set {', '.join(f'{k} = excluded.{k}' for k in oppdater)} "
                    f"where ({', '.join(f't.{k}' for k in oppdater)}) is distinct from "
                    f"({', '.join(f'excluded.{k}' for k in oppdater)})")
    else:
        konflikt = "do nothing"
    endret = c.execute(
        f"insert into {tabell} as t ({kol}) select {kol} from {tmp} "
        f"on conflict ({', '.join(nokkel)}) {konflikt}").rowcount

    slettet = 0
    if slett and omfang:
        lik = " and ".join(f"n.{k} = t.{k}" for k in nokkel)
        slettet = c.execute(
            f"delete from {tabell} t where {omfang} and not exists (select 1 from {tmp} n where {lik})",
            omfang_args).rowcount
    c.execute(f"drop table {tmp}")
    return {"satt_inn_eller_endret": endret, "slettet": slettet}


# Rådata -------------------------------------------------------------------------

def raa(c, k: int, aar: int, moteliste: list, moter: list, medlemslister: list, kjoring_id: str) -> int:
    """Nye versjoner av rådata. Det som alt finnes (samme sjekksum), hoppes over."""
    rader = [(k, "moteliste", str(aar), sjekksum(moteliste), _jsonb(moteliste), kjoring_id)] if moteliste else []
    rader += [(k, "mote", str(m["mote"]["MO_ID"]), sjekksum(m), _jsonb(m), kjoring_id) for m in moter]
    rader += [(k, "medlemsliste", l["hentet"], sjekksum(l), _jsonb(l), kjoring_id) for l in medlemslister]
    cur = c.cursor()
    cur.executemany(
        "insert into kjerne.raa_svar (kommune_id, kilde, nokkel, sjekksum, innhold, kjoring_id) "
        "values (%s, %s, %s, %s, %s, %s) on conflict (kommune_id, kilde, nokkel, sjekksum) do nothing", rader)
    return len(rader)


# Personer -------------------------------------------------------------------------

class Personer:
    """Én rad per normalisert navn. Opprettes ved behov; slettes aldri."""

    def __init__(self, c, k: int) -> None:
        self.c, self.k = c, k
        self.id = {n: pid for pid, n in c.execute(
            "select id, navn from kjerne.person where kommune_id = %s", (k,))}

    def sikre(self, navn: set[str]) -> int:
        nye = sorted(n for n in navn if n and n not in self.id)
        if nye:
            from bygg.bygg_nettsted import _slug as profiladresse  # noqa: PLC0415

            self.c.cursor().executemany(
                "insert into kjerne.person (kommune_id, navn, slug) values (%s, %s, %s)",
                [(self.k, n, profiladresse(n)) for n in nye])
            self.id = {n: pid for pid, n in self.c.execute(
                "select id, navn from kjerne.person where kommune_id = %s", (self.k,))}
        return len(nye)

    def __getitem__(self, navn: str) -> int:
        return self.id[navn]


def navnevarianter(c, k: int, personer: Personer, varianter: dict[str, str]) -> dict:
    personer.sikre(set(varianter.values()))
    return synk_tabell(
        c, "kjerne.navnevariant", ["kommune_id", "variant", "person_id", "begrunnelse"],
        ["kommune_id", "variant"],
        [(k, v, personer[n], "Fra tolk/navn.VARIANTER: samme person, skrevet ulikt i protokollene")
         for v, n in sorted(varianter.items())],
        "t.kommune_id = %s", (k,))


# Utvalg, partier og verv -------------------------------------------------------------

def utvalg(c, k: int, aar: int, utv: dict, partisider: dict) -> dict:
    ut = {}
    ut["utvalg"] = synk_tabell(
        c, "kjerne.utvalg", ["kommune_id", "utvalg_id", "kortnavn", "navn"], ["kommune_id", "utvalg_id"],
        [(k, u["utvalg_id"], u["kortnavn"], u["navn"]) for u in utv["utvalg"]], slett=False)
    ut["utvalg_aar"] = synk_tabell(
        c, "kjerne.utvalg_aar",
        ["kommune_id", "aar", "utvalg_id", "faste_medlemmer", "varamedlemmer", "moter", "medlemsliste_hentet"],
        ["kommune_id", "aar", "utvalg_id"],
        [(k, aar, u["utvalg_id"], u["faste_medlemmer"], u["varamedlemmer"], u["moter"],
          utv["medlemsliste_hentet"] or None) for u in utv["utvalg"]],
        "t.kommune_id = %s and t.aar = %s", (k, aar))
    sider = partisider.get("partier", {})
    ut["parti"] = synk_tabell(
        c, "kjerne.parti", ["kommune_id", "kode", "navn", "url", "url_tekst", "url_kontrollert"],
        ["kommune_id", "kode"],
        [(k, kode, navn, (sider.get(kode) or {}).get("url"), (sider.get(kode) or {}).get("tekst"),
          partisider.get("kontrollert") if kode in sider else None)
         for kode, navn in sorted(utv["partier"].items())], slett=False)
    return ut


def verv(c, k: int, aar: int, personer: Personer, vervliste: list) -> dict:
    personer.sikre({v["navn"] for v in vervliste} | {n for v in vervliste for n in v["motte_for"]})
    portal: dict[int, int] = {}
    for v in vervliste:
        if v["person_id"] is not None:
            pid = personer[v["navn"]]
            if portal.setdefault(v["person_id"], pid) != pid:
                raise SystemExit(f"portal-ID {v['person_id']} brukes av to personer")
    ut = {"person_portal_id": synk_tabell(
        c, "kjerne.person_portal_id", ["kommune_id", "portal_person_id", "person_id"],
        ["kommune_id", "portal_person_id"], [(k, p, pid) for p, pid in sorted(portal.items())], slett=False)}
    ut["verv"] = synk_tabell(
        c, "kjerne.verv",
        ["kommune_id", "aar", "utvalg_id", "person_id", "rolle", "repr", "portal_person_id", "i_dagens_liste",
         "i_medlemslister", "forst_motte", "sist_motte", "moter_som", "motte_for"],
        ["kommune_id", "aar", "utvalg_id", "person_id"],
        [(k, aar, v["utvalg_id"], personer[v["navn"]], v["rolle"], v["repr"], v["person_id"],
          v["i_dagens_liste"], v["i_medlemslister"], v["forst_motte"], v["sist_motte"],
          _jsonb(v["moter_som"]), v["motte_for"]) for v in vervliste],
        "t.kommune_id = %s and t.aar = %s", (k, aar))
    return ut


# Møter og saker ------------------------------------------------------------------------

_DOKUMENT = ["kommune_id", "id_rom", "portal_id", "slag", "tittel", "format", "url", "sak_id",
             "behandling_id", "mote_id", "rekkefolge"]


def moter(c, k: int, aar: int, alle_moter: list, raa_moter: list, moteliste: list) -> dict:
    """Møtene for året, med møteinnkalling og møteprotokoll fra rådataene."""
    ut_id = {m["MO_ID"]: m["UT_ID"] for m in moteliste}
    motedok = {m["mote"]["MO_ID"]: [d for d in m["detaljer"].get("MeetingDocuments") or []
                                    if not d.get("IsRestricted")] for m in raa_moter}
    dokrader = []
    for m in alle_moter:
        fra_raa = motedok.get(m["mote_id"], [])
        if [d["DmbDocumentTypeId"] for d in fra_raa] != [d["type"] for d in m["dokumenter"]]:
            raise SystemExit(f"møte {m['mote_id']}: dokumentene stemmer ikke med rådataene")
        for i, (d, r) in enumerate(zip(m["dokumenter"], fra_raa)):
            slag = {"MI": "moteinnkalling", "MP": "moteprotokoll"}[d["type"]]
            dokrader.append((k, "motedokument", r["Id"], slag, d["tittel"], None, d["url"],
                             None, None, m["mote_id"], i))
    # Et nytt utvalg finnes ikke før vervene bygges (utvalg under), men møtet
    # peker til det. Navnene derfra erstatter disse.
    for m in alle_moter:
        c.execute("insert into kjerne.utvalg (kommune_id, utvalg_id, kortnavn, navn) values (%s, %s, %s, %s) "
                  "on conflict do nothing",
                  (k, ut_id[m["mote_id"]], m["utvalg"] or m["utvalg_navn"], m["utvalg_navn"]))
    omfang = "t.kommune_id = %s and extract(year from t.dato) = %s"
    ut = {"mote": synk_tabell(
        c, "kjerne.mote",
        ["kommune_id", "mote_id", "utvalg_id", "utvalg", "utvalg_navn", "dato", "slutt", "sted", "rom",
         "antall_saker", "url"], ["kommune_id", "mote_id"],
        [(k, m["mote_id"], ut_id[m["mote_id"]], m["utvalg"], m["utvalg_navn"], _tid(m["dato"]), m["slutt"],
          m["sted"], m["rom"], m["antall_saker"], m["url"]) for m in alle_moter], omfang, (k, aar))}
    ut["motedokument"] = synk_tabell(
        c, "kjerne.dokument", _DOKUMENT, ["kommune_id", "id_rom", "portal_id"], dokrader,
        "t.kommune_id = %s and t.id_rom = 'motedokument' and t.mote_id in "
        "(select mote_id from kjerne.mote where kommune_id = %s and extract(year from dato) = %s)", (k, k, aar))
    return ut


def saker(c, k: int, aar: int, alle_saker: list) -> dict:
    """Sakene for året, med saksgang og dokumenter.

    En sak får ny ID når et eldre år hentes og kjeden får en lavere
    behandlings-ID. Da flyttes saken (ON UPDATE CASCADE tar med seg steg,
    dokumenter og analyser) i stedet for å slettes og settes inn på nytt.
    """
    ny_sak = {st["behandling_id"]: s["sak_id"] for s in alle_saker for st in s["saksgang"]}
    flyttet = 0
    for gammel, ny in sorted({(gammel, ny_sak[bid]) for bid, gammel in c.execute(
            "select behandling_id, sak_id from kjerne.saksgang_steg where kommune_id = %s "
            "and behandling_id = any(%s)", (k, list(ny_sak))) if ny_sak[bid] != gammel}):
        if not c.execute("select 1 from kjerne.sak where kommune_id = %s and sak_id = %s", (k, ny)).fetchone():
            c.execute("update kjerne.sak set sak_id = %s where kommune_id = %s and sak_id = %s", (ny, k, gammel))
            flyttet += 1

    sakrader, stegrader, dokrader = [], [], []
    for i, s in enumerate(alle_saker):
        sakrader.append((k, s["sak_id"], aar, i, s["tittel"], s["skjermet_tittel"], s["sakstype"],
                         s["formalia"], s["status"], s["til_kommunestyret"]))
        for j, st in enumerate(s["saksgang"]):
            stegrader.append((k, st["behandling_id"], s["sak_id"], j, st["hentet"], st["mote_id"],
                              _tid(st["dato"]), st["utvalg"], st["utvalg_navn"], st["saksnr"],
                              st["protokoll_publisert"], st["protokoll_skjermet"], st["url_mote"], st["url_vedtak"]))
            if st["url_vedtak"]:
                dokrader.append((k, "behandling", st["behandling_id"], "saksprotokoll", None, None,
                                 st["url_vedtak"], s["sak_id"], st["behandling_id"], None, None))
        if s["saksframlegg"]:
            f = s["saksframlegg"]
            dokrader.append((k, "dokument", f["dokument_id"], "saksframlegg", f["tittel"], f["format"],
                             f["url"], s["sak_id"], None, None, 0))
        for j, d in enumerate(s["vedlegg"]):
            dokrader.append((k, "dokument", d["dokument_id"], "vedlegg", d["tittel"], d["format"],
                             d["url"], s["sak_id"], None, None, j))

    arets = "(select sak_id from kjerne.sak where kommune_id = %s and aar = %s)"
    ut = {"flyttet": flyttet}
    ut["sak"] = synk_tabell(
        c, "kjerne.sak",
        ["kommune_id", "sak_id", "aar", "rekkefolge", "tittel", "skjermet_tittel", "sakstype", "formalia",
         "status", "til_kommunestyret"], ["kommune_id", "sak_id"], sakrader,
        "t.kommune_id = %s and t.aar = %s", (k, aar))
    ut["saksgang_steg"] = synk_tabell(
        c, "kjerne.saksgang_steg",
        ["kommune_id", "behandling_id", "sak_id", "rekkefolge", "hentet", "mote_id", "dato", "utvalg",
         "utvalg_navn", "saksnr", "protokoll_publisert", "protokoll_skjermet", "url_mote", "url_vedtak"],
        ["kommune_id", "behandling_id"], stegrader, f"t.kommune_id = %s and t.sak_id in {arets}", (k, k, aar))
    ut["dokument"] = synk_tabell(
        c, "kjerne.dokument", _DOKUMENT, ["kommune_id", "id_rom", "portal_id"], dokrader,
        f"t.kommune_id = %s and t.id_rom in ('dokument', 'behandling') and t.sak_id in {arets}", (k, k, aar))
    return ut


def tekster(c, k: int, les) -> dict:
    """Teksten for hvert dokument som har den. `les(id_rom, ident)` henter den.

    Tekst slettes ikke her. Den forsvinner med dokumentet, for eksempel når
    et vedtak blir skjermet (CLAUDE.md regel 3).
    """
    rader = []
    for did, id_rom, portal_id, slag, mote_id in c.execute(
            "select id, id_rom, portal_id, slag, mote_id from kjerne.dokument where kommune_id = %s "
            "and slag <> 'moteinnkalling'", (k,)).fetchall():
        innhold = les("mote", mote_id) if slag == "moteprotokoll" else les(id_rom, portal_id)
        if innhold:
            rader.append((k, did, innhold))
    return synk_tabell(c, "kjerne.dokument_tekst", ["kommune_id", "dokument_id", "tekst"],
                       ["kommune_id", "dokument_id"], rader, slett=False)


# Voteringer og oppmøte ---------------------------------------------------------------------

def voteringer(c, k: int, aar: int, personer: Personer, poster: list) -> dict:
    navn = set()
    for b in poster:
        for v in b["voteringer"]:
            navn |= set(v["for"]) | set(v["mot"]) | set(v["ikke_til_stede"])
            navn |= {n for a in v["alternativer"] for n in a["navn"]}
    personer.sikre(navn)

    vedtak, vrader, arader, srader = [], [], [], []
    for b in poster:
        bid = b["behandling_id"]
        vedtak.append((k, bid, b.get("vedtak")))
        for v in b["voteringer"]:
            vrader.append((k, bid, v["nr"], v["type"], v["tekst"], v["resultat"], v["resultat_tekst"],
                           v["enstemmig"], v["antall_for"], v["antall_mot"], v["forslagsstiller"], v["parti"],
                           v["dobbeltstemme"], v["tall_stemmer"], "bare_resultat" if v["enstemmig"] else "navneliste"))
            for valg, liste in (("for", v["for"]), ("mot", v["mot"]), ("ikke_til_stede", v["ikke_til_stede"])):
                for i, n in enumerate(liste):
                    srader.append((k, bid, v["nr"], personer[n], valg, None,
                                   v["partier"][n] if valg != "ikke_til_stede" else None, i))
            for i, a in enumerate(v["alternativer"]):
                arader.append((k, bid, v["nr"], a["forslag"], a["antall"], i))
                for j, n in enumerate(a["navn"]):
                    srader.append((k, bid, v["nr"], personer[n], "alternativ", a["forslag"], a["partier"][n], j))

    arets = ("t.kommune_id = %s and t.behandling_id in (select st.behandling_id from kjerne.saksgang_steg st "
             "join kjerne.sak s using (kommune_id, sak_id) where s.kommune_id = %s and s.aar = %s)")
    args = (k, k, aar)
    return {
        "vedtak_tolket": synk_tabell(c, "kjerne.vedtak_tolket", ["kommune_id", "behandling_id", "vedtak"],
                                     ["kommune_id", "behandling_id"], vedtak, arets, args),
        "votering": synk_tabell(
            c, "kjerne.votering",
            ["kommune_id", "behandling_id", "nr", "type", "tekst", "resultat", "resultat_tekst", "enstemmig",
             "antall_for", "antall_mot", "forslagsstiller", "parti", "dobbeltstemme", "tall_stemmer", "detaljniva"],
            ["kommune_id", "behandling_id", "nr"], vrader, arets, args),
        "votering_alternativ": synk_tabell(
            c, "kjerne.votering_alternativ", ["kommune_id", "behandling_id", "nr", "forslag", "antall", "rekkefolge"],
            ["kommune_id", "behandling_id", "nr", "forslag"], arader, arets, args),
        "stemme": synk_tabell(
            c, "kjerne.stemme",
            ["kommune_id", "behandling_id", "nr", "person_id", "valg", "alternativ_forslag", "parti", "rekkefolge"],
            ["kommune_id", "behandling_id", "nr", "person_id"], srader, arets, args),
    }


def oppmote(c, k: int, aar: int, personer: Personer, moter_: list) -> dict:
    personer.sikre({o["navn"] for m in moter_ for o in m["oppmote"]}
                   | {o["vara_for"] for m in moter_ for o in m["oppmote"] if o["vara_for"]})
    omrader, orader, oarader = [], [], []
    for m in moter_:
        omrader.append((k, m["mote_id"], m["ikke_tolket"]))
        for i, o in enumerate(m["oppmote"]):
            orader.append((k, m["mote_id"], personer[o["navn"]], i, o["funksjon"], o["repr"],
                           personer[o["vara_for"]] if o["vara_for"] else None))
        for i, a in enumerate(m["avvik"]):
            oarader.append((k, m["mote_id"], i, a["behandling_id"], a["votering"], a["type"],
                            a.get("navn"), a.get("stemmer"), a.get("frammotte")))
    arets = ("t.kommune_id = %s and t.mote_id in (select mote_id from kjerne.mote "
             "where kommune_id = %s and extract(year from dato) = %s)")
    args = (k, k, aar)
    return {
        "oppmote_mote": synk_tabell(c, "kjerne.oppmote_mote", ["kommune_id", "mote_id", "ikke_tolket"],
                                    ["kommune_id", "mote_id"], omrader, arets, args),
        "oppmote": synk_tabell(
            c, "kjerne.oppmote",
            ["kommune_id", "mote_id", "person_id", "rekkefolge", "funksjon", "repr", "vara_for_person_id"],
            ["kommune_id", "mote_id", "person_id"], orader, arets, args),
        "oppmote_avvik": synk_tabell(
            c, "kjerne.oppmote_avvik",
            ["kommune_id", "mote_id", "rekkefolge", "behandling_id", "votering_nr", "type", "navn", "stemmer",
             "frammotte"], ["kommune_id", "mote_id", "rekkefolge"], oarader, arets, args),
    }


# Avvik, vurderinger og tillatte navn (ADR-015) ------------------------------------------------

def avvik(c, k: int, aar: int, avviksliste: list) -> dict:
    """Avvikene for året. Et avvik som er borte, settes inaktivt, ikke slettet."""
    ut = {"avvik": synk_tabell(
        c, "kjerne.avvik", ["kommune_id", "avvik", "type", "utvalg", "dato", "beskrivelse", "kilde", "aktiv"],
        ["kommune_id", "avvik"],
        [(k, a["avvik"], a["type"], a["utvalg"], a["dato"], a["beskrivelse"], a.get("kilde"), True)
         for a in avviksliste], slett=False)}
    ut["deaktivert"] = c.execute(
        "update kjerne.avvik set aktiv = false where kommune_id = %s and extract(year from dato) = %s "
        "and aktiv and not (avvik = any(%s))", (k, aar, [a["avvik"] for a in avviksliste])).rowcount
    ut["avvik_votering"] = synk_tabell(
        c, "kjerne.avvik_votering", ["kommune_id", "avvik", "behandling_id", "nr", "rekkefolge"],
        ["kommune_id", "avvik", "behandling_id", "nr"],
        [(k, a["avvik"], b, nr, i) for a in avviksliste for i, (b, nr) in enumerate(a["voteringer"])],
        "t.kommune_id = %s and t.avvik in (select avvik from kjerne.avvik where kommune_id = %s "
        "and extract(year from dato) = %s)", (k, k, aar))
    return ut


def vurderinger(c, k: int, vurd: list) -> int:
    """En ny rad når vurderingen av et avvik er en annen enn den som gjelder."""
    gjeldende = {a: (avg, m, b, v, str(d)) for a, avg, m, b, v, d in c.execute(
        "select avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato from kjerne.vurdering_gjeldende "
        "where kommune_id = %s", (k,))}
    nye = [(k, v["avvik"], v["avgjorelse"], v.get("merknad"), v["begrunnelse"], v["vurdert_av"], v["dato"])
           for v in vurd
           if gjeldende.get(v["avvik"]) != (v["avgjorelse"], v.get("merknad"), v["begrunnelse"],
                                           v["vurdert_av"], v["dato"])]
    c.cursor().executemany(
        "insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato) "
        "values (%s, %s, %s, %s, %s, %s, %s)", nye)
    return len(nye)


def partilenker(c, k: int, partisider: dict) -> int:
    """Lenkene til partienes egne sider (data/partisider.json), på partiene som finnes."""
    sider = partisider.get("partier", {})
    kontrollert = partisider.get("kontrollert")
    endret = 0
    for kode, url, tekst in c.execute("select kode, url, url_tekst from kjerne.parti where kommune_id = %s",
                                      (k,)).fetchall():
        ny = sider.get(kode) or {}
        if (url, tekst) != (ny.get("url"), ny.get("tekst")):
            c.execute("update kjerne.parti set url = %s, url_tekst = %s, url_kontrollert = %s "
                      "where kommune_id = %s and kode = %s",
                      (ny.get("url"), ny.get("tekst"), kontrollert if ny else None, k, kode))
            endret += 1
    return endret


def tillatte_navn(c, k: int, tillatte: list) -> dict:
    return synk_tabell(
        c, "kjerne.tillatt_navn", ["kommune_id", "navn", "sak_id", "begrunnelse", "vurdert"],
        ["kommune_id", "navn", "sak_id"],
        [(k, n["navn"], n["sak_id"], n["begrunnelse"], n["vurdert"]) for n in tillatte],
        "t.kommune_id = %s", (k,))


# Analyser ---------------------------------------------------------------------------------

def analyser(c, k: int, analyser_: dict, kjoring_id: str) -> int:
    """En ny versjon når analysen av en sak er en annen enn den som gjelder."""
    gjeldende = {s: (sj, str(d)) for s, sj, d in c.execute(
        "select sak_id, sjekksum, dato from kjerne.analyse_gjeldende where kommune_id = %s", (k,))}
    nye = [a for a in analyser_.values() if gjeldende.get(a["sak_id"]) != (a["sjekksum"], a["dato"])]
    c.cursor().executemany(
        "insert into kjerne.analyse (kommune_id, sak_id, tittel_klarsprak, sammendrag, betydning, tagger, "
        "utfall, uenighet, usikker, sjekksum, modell, innsats, instruksjon_versjon, dato, tokens_inn, "
        "tokens_ut, kilder, opprettet, kjoring_id) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)",
        [(k, a["sak_id"], a["tittel_klarsprak"], a["sammendrag"], a["betydning"], a["tagger"], a["utfall"],
          a["uenighet"], a["usikker"], a["sjekksum"], a["modell"], a["innsats"], a["instruksjon_versjon"],
          a["dato"], (a.get("tokens") or {}).get("inn", 0), (a.get("tokens") or {}).get("ut", 0),
          _jsonb(a["kilder"]), kjoring_id) for a in nye])
    return len(nye)


# Kjøreloggen -------------------------------------------------------------------------------

def kjoringer(c, k: int, logg: dict) -> int:
    # Tallene sendes som tekst: 168.0 og 168 er like for Postgres, men ikke i
    # filen, og numeric beholder skalaen bare når den får teksten.
    c.cursor().executemany(
        "insert into drift.kjoring (kjoring_id, kilde, start) values (%s, %s, %s) "
        "on conflict (kjoring_id) do nothing",
        [(kid, "actions" if kid.isdigit() else "lokal", post.get("start")) for kid, post in logg.items()])
    rader = [(kid, k, del_, nokkel, verdi) for kid, post in logg.items()
             for del_, tall in post.items() if isinstance(tall, dict) for nokkel, verdi in tall.items()]
    c.cursor().executemany(
        "insert into drift.kjoring_tall (kjoring_id, kommune_id, del, nokkel, verdi) values (%s, %s, %s, %s, %s::numeric) "
        "on conflict (kjoring_id, coalesce(kommune_id, 0), del, nokkel) do update set verdi = excluded.verdi "
        "where drift.kjoring_tall.verdi::text is distinct from excluded.verdi::text",
        [(kid, k_, d, n, str(v)) for kid, k_, d, n, v in rader])
    return len(logg)


# Enkeltskriving fra lager/ (KOMMUNELYS_LAGER=pg) --------------------------------------

def i_transaksjon(skriv):
    """Kjører skriv(c, kommune_id) i én transaksjon, og glemmer det som er husket.

    Hver lagre-funksjon i lager/ skriver i sin egen transaksjon, med
    kjøringen satt for endringsloggen. Bryter dataene en regel, skrives
    ingenting.
    """
    from . import db, kjoring_id, pg  # noqa: PLC0415
    from .kommune import slug as kommune_slug  # noqa: PLC0415

    with db.transaksjon(kjoring_id()) as c:
        slug = kommune_slug()
        rad = c.execute("select kommune_id from kjerne.kommune where slug = %s", (slug,)).fetchone()
        if not rad:
            raise SystemExit(f"fant ikke kommunen {slug} i databasen")
        resultat = skriv(c, rad[0])
    pg.glem()
    return resultat


def tekst_en(c, k: int, id_rom: str, ident: int, innhold: str) -> None:
    """Teksten for ett dokument. Dokumentet må finnes (skrives av saker og møter)."""
    if id_rom == "mote":
        rad = c.execute("select id from kjerne.dokument where kommune_id = %s and slag = 'moteprotokoll' "
                        "and mote_id = %s", (k, ident)).fetchone()
    else:
        rad = c.execute("select id from kjerne.dokument where kommune_id = %s and id_rom = %s and portal_id = %s",
                        (k, id_rom, ident)).fetchone()
    if not rad:
        raise SystemExit(f"fant ikke dokumentet {id_rom} {ident}; skriv sakene og møtene først")
    c.execute("insert into kjerne.dokument_tekst (kommune_id, dokument_id, tekst) values (%s, %s, %s) "
              "on conflict (kommune_id, dokument_id) do update set tekst = excluded.tekst, hentet = now() "
              "where kjerne.dokument_tekst.tekst is distinct from excluded.tekst", (k, rad[0], innhold))


def kjoring_tall(c, k: int, kjoring_id: str, del_: str, tall: dict) -> None:
    """Tall for én del av kjøringen (siste-kjoring.json for henting av møter)."""
    c.execute("insert into drift.kjoring (kjoring_id, kilde) values (%s, %s) on conflict do nothing",
              (kjoring_id, "actions" if kjoring_id.isdigit() else "lokal"))
    c.cursor().executemany(
        "insert into drift.kjoring_tall (kjoring_id, kommune_id, del, nokkel, verdi) values (%s, %s, %s, %s, %s::numeric) "
        "on conflict (kjoring_id, coalesce(kommune_id, 0), del, nokkel) do update set verdi = excluded.verdi",
        [(kjoring_id, k, del_, n, str(v)) for n, v in tall.items()
         if isinstance(v, (int, float)) and not isinstance(v, bool)])


def driftsside(c, html: str) -> None:
    """Driftssiden fra bygget. Det som er eldre enn 30 dager, ryddes bort."""
    from . import kjoring_id  # noqa: PLC0415

    c.execute("insert into drift.side (kjoring_id, html) values (%s, %s)", (kjoring_id(), html))
    c.execute("delete from drift.side where bygget < now() - interval '30 days'")


def nettsted_filer(c, k: int, filer: dict[str, str]) -> None:
    """Dataene til nettstedet for en kommune med begrenset innsyn (ADR-024).
    Byttes ut helt, så ingenting fra et tidligere bygg blir liggende."""
    c.execute("delete from drift.nettsted_fil where kommune_id = %s", (k,))
    for sti, innhold in sorted(filer.items()):
        c.execute("insert into drift.nettsted_fil (kommune_id, sti, innhold) values (%s, %s, %s)",
                  (k, sti, innhold))


def nettsted_filer_rydd(c, begrensede: list[str]) -> int:
    """Fjerner dataene for kommuner som ikke lenger har begrenset innsyn."""
    return c.execute(
        "delete from drift.nettsted_fil f using kjerne.kommune k "
        "where k.kommune_id = f.kommune_id and not (k.slug = any(%s))", (begrensede,)).rowcount


def vurdering(c, k: int, v: dict) -> int:
    """Én ny vurdering (lager.vurder). Avviket må finnes."""
    return c.execute(
        "insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato) "
        "values (%s, %s, %s, %s, %s, %s, %s) returning id",
        (k, v["avvik"], v["avgjorelse"], v.get("merknad"), v["begrunnelse"], v["vurdert_av"], v["dato"]),
    ).fetchone()[0]


def forrige_telling(c, k: int, telling: dict[str, int]) -> int:
    """Antall saker per år ved siste kontroll, som et bygg i drift.bygg."""
    siste = {str(a): n for a, n in c.execute(
        "select distinct on (aar) aar, saker from drift.bygg where kommune_id = %s order by aar, bygget desc", (k,))}
    nye = [(k, int(a), n) for a, n in telling.items() if siste.get(a) != n]
    c.cursor().executemany("insert into drift.bygg (kommune_id, aar, saker, status) values (%s, %s, %s, '{}')", nye)
    return len(nye)
