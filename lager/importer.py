"""Kopierer data/ inn i databasen (fase 2 i flyttingen til Postgres).

Alt skjer i én transaksjon: enten kommer alt inn, eller ingenting. Databasen
kontrollerer reglene når transaksjonen avsluttes (stemmetall, skjerming,
kommune på hver rad), så en feil i dataene stopper importen med en melding
om hva som er galt.

Kjøres mot en tom database for kommunen. Rådata kan ikke slettes, så en
import som er gjort, kan ikke gjøres på nytt over seg selv.

    python -m lager.importer 2026
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys

from bygg.bygg_nettsted import _slug as profiladresse
from lager import analyse, avvik, db, fra_databasen, konfig, oppmote, raa, saker, tekst, verv, voteringer
from lager import drift as lager_drift
from tolk.navn import VARIANTER

KOMMUNE = "steinkjer"


def _sjekksum(innhold) -> str:
    kanonisk = json.dumps(innhold, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(kanonisk.encode("utf-8")).hexdigest()


def _tid(verdi: str | None) -> str | None:
    """«2026-01-08T14:30» eller tom streng -> det Postgres leser, eller None."""
    return verdi.replace("T", " ") if verdi else None


class Personer:
    """Én rad per normalisert navn. Navnet er nøkkelen i protokollene."""

    def __init__(self, c, k: int) -> None:
        self.c, self.k, self.id = c, k, {}

    def opprett(self, navn: set[str]) -> None:
        nye = sorted(n for n in navn if n not in self.id)
        self.c.cursor().executemany(
            "insert into kjerne.person (kommune_id, navn, slug) values (%s, %s, %s)",
            [(self.k, n, profiladresse(n)) for n in nye])
        for pid, n in self.c.execute(
                "select id, navn from kjerne.person where kommune_id = %s", (self.k,)):
            self.id[n] = pid

    def __getitem__(self, navn: str) -> int:
        return self.id[navn]


def _alle_navn(vot: list, opp: list, vervliste: list) -> set[str]:
    navn = {v["navn"] for v in vervliste} | {n for v in vervliste for n in v["motte_for"]}
    for b in vot:
        for v in b["voteringer"]:
            navn |= set(v["for"]) | set(v["mot"]) | set(v["ikke_til_stede"])
            navn |= {n for a in v["alternativer"] for n in a["navn"]}
    for m in opp:
        navn |= {o["navn"] for o in m["oppmote"]} | {o["vara_for"] for o in m["oppmote"] if o["vara_for"]}
        navn |= {n for a in m["avvik"] for n in a.get("navn") or []}
    return navn | set(VARIANTER.values())


def kjor(aar: int) -> dict:
    from psycopg.types.json import Jsonb  # noqa: PLC0415

    if fra_databasen():
        raise SystemExit("importen leser fra filene; kjør uten KOMMUNELYS_LAGER=pg")
    kjoring_id = f"import-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    raa_moter = raa.moter(aar) or []
    moteliste = raa.moteliste(aar) or []
    medlemslister = raa.medlemslister()
    alle_saker = saker.les(aar)
    alle_moter = saker.les_moter(aar)
    vot = voteringer.les(aar, [])
    opp = oppmote.les(aar, [])
    vervliste = verv.les(aar, [])
    utv = verv.les_utvalg(aar)
    partisider = konfig.partisider()
    teller: dict[str, int] = {}

    with db.transaksjon(kjoring_id) as c:
        k = c.execute("select kommune_id from kjerne.kommune where slug = %s", (KOMMUNE,)).fetchone()
        if not k:
            raise SystemExit(f"fant ikke kommunen {KOMMUNE} i databasen")
        k = k[0]
        if c.execute("select count(*) from kjerne.sak where kommune_id = %s and aar = %s", (k, aar)).fetchone()[0]:
            raise SystemExit(f"databasen har alt saker for {KOMMUNE} {aar}; importen kjøres bare én gang")
        cur = c.cursor()

        cur.execute("insert into drift.kjoring (kjoring_id, kilde) values (%s, 'import')", (kjoring_id,))

        # Rådata, urørt (ADR-001).
        raarader = [(k, "moteliste", str(aar), _sjekksum(moteliste), Jsonb(moteliste), kjoring_id)]
        raarader += [(k, "mote", str(m["mote"]["MO_ID"]), _sjekksum(m), Jsonb(m), kjoring_id) for m in raa_moter]
        raarader += [(k, "medlemsliste", l["hentet"], _sjekksum(l), Jsonb(l), kjoring_id) for l in medlemslister]
        cur.executemany(
            "insert into kjerne.raa_svar (kommune_id, kilde, nokkel, sjekksum, innhold, kjoring_id) "
            "values (%s, %s, %s, %s, %s, %s)", raarader)
        teller["raa_svar"] = len(raarader)

        # Utvalg og partier.
        cur.executemany("insert into kjerne.utvalg values (%s, %s, %s, %s)",
                        [(k, u["utvalg_id"], u["kortnavn"], u["navn"]) for u in utv["utvalg"]])
        cur.executemany(
            "insert into kjerne.utvalg_aar values (%s, %s, %s, %s, %s, %s, %s)",
            [(k, aar, u["utvalg_id"], u["faste_medlemmer"], u["varamedlemmer"], u["moter"],
              utv["medlemsliste_hentet"] or None) for u in utv["utvalg"]])
        sider = partisider.get("partier", {})
        cur.executemany(
            "insert into kjerne.parti (kommune_id, kode, navn, url, url_tekst, url_kontrollert) "
            "values (%s, %s, %s, %s, %s, %s)",
            [(k, kode, navn, (sider.get(kode) or {}).get("url"), (sider.get(kode) or {}).get("tekst"),
              partisider.get("kontrollert") if kode in sider else None)
             for kode, navn in sorted(utv["partier"].items())])
        teller["utvalg"], teller["parti"] = len(utv["utvalg"]), len(utv["partier"])

        # Personer, med portal-ID-er og navnevarianter.
        personer = Personer(c, k)
        personer.opprett(_alle_navn(vot, opp, vervliste))
        teller["person"] = len(personer.id)
        portal: dict[int, int] = {}
        for v in vervliste:
            if v["person_id"] is not None:
                pid = personer[v["navn"]]
                if portal.setdefault(v["person_id"], pid) != pid:
                    raise SystemExit(f"portal-ID {v['person_id']} brukes av to personer")
        cur.executemany("insert into kjerne.person_portal_id values (%s, %s, %s)",
                        [(k, p, pid) for p, pid in sorted(portal.items())])
        cur.executemany(
            "insert into kjerne.navnevariant values (%s, %s, %s, %s)",
            [(k, variant, personer[kanonisk], "Fra tolk/navn.VARIANTER: samme person, skrevet ulikt i protokollene")
             for variant, kanonisk in sorted(VARIANTER.items())])
        teller["person_portal_id"], teller["navnevariant"] = len(portal), len(VARIANTER)

        # Møter, med møteinnkalling og møteprotokoll.
        ut_id = {m["MO_ID"]: m["UT_ID"] for m in moteliste}
        motedok = {m["mote"]["MO_ID"]: [d for d in m["detaljer"].get("MeetingDocuments") or []
                                        if not d.get("IsRestricted")] for m in raa_moter}
        cur.executemany(
            "insert into kjerne.mote (kommune_id, mote_id, utvalg_id, utvalg, utvalg_navn, dato, slutt, "
            "sted, rom, antall_saker, url) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [(k, m["mote_id"], ut_id[m["mote_id"]], m["utvalg"], m["utvalg_navn"], _tid(m["dato"]),
              m["slutt"], m["sted"], m["rom"], m["antall_saker"], m["url"]) for m in alle_moter])
        dokrader = []
        for m in alle_moter:
            fra_raa = motedok[m["mote_id"]]
            if [d["DmbDocumentTypeId"] for d in fra_raa] != [d["type"] for d in m["dokumenter"]]:
                raise SystemExit(f"møte {m['mote_id']}: dokumentene stemmer ikke med rådataene")
            for i, (d, r) in enumerate(zip(m["dokumenter"], fra_raa)):
                slag = {"MI": "moteinnkalling", "MP": "moteprotokoll"}[d["type"]]
                dokrader.append((k, "motedokument", r["Id"], slag, d["tittel"], None, d["url"],
                                 None, None, m["mote_id"], i))
        teller["mote"] = len(alle_moter)

        # Saker, saksgang, saksframlegg, vedlegg og saksprotokoller.
        sakrader, stegrader = [], []
        for i, s in enumerate(alle_saker):
            sakrader.append((k, s["sak_id"], aar, i, s["tittel"], s["skjermet_tittel"], s["sakstype"],
                             s["formalia"], s["status"], s["til_kommunestyret"]))
            for j, st in enumerate(s["saksgang"]):
                stegrader.append((k, st["behandling_id"], s["sak_id"], j, st["hentet"], st["mote_id"],
                                  _tid(st["dato"]), st["utvalg"], st["utvalg_navn"], st["saksnr"],
                                  st["protokoll_publisert"], st["protokoll_skjermet"], st["url_mote"],
                                  st["url_vedtak"]))
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
        cur.executemany("insert into kjerne.sak values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", sakrader)
        cur.executemany(
            "insert into kjerne.saksgang_steg (kommune_id, behandling_id, sak_id, rekkefolge, hentet, mote_id, "
            "dato, utvalg, utvalg_navn, saksnr, protokoll_publisert, protokoll_skjermet, url_mote, url_vedtak) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", stegrader)
        cur.executemany(
            "insert into kjerne.dokument (kommune_id, id_rom, portal_id, slag, tittel, format, url, sak_id, "
            "behandling_id, mote_id, rekkefolge) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", dokrader)
        teller["sak"], teller["saksgang_steg"], teller["dokument"] = len(sakrader), len(stegrader), len(dokrader)

        # Teksten (regel 3: bare åpne dokumenter har tekst; databasen sjekker igjen).
        dokid = {(rom, pid): did for did, rom, pid in c.execute(
            "select id, id_rom, portal_id from kjerne.dokument where kommune_id = %s", (k,))}
        # Møteprotokollens tekst ligger etter møte-ID (lager.tekst).
        protokoll_for = {portal_id: mote_id for _, _, portal_id, slag, *_, mote_id, _ in dokrader
                         if slag == "moteprotokoll"}
        tekstrader = []
        for (rom, pid), did in dokid.items():
            if rom == "motedokument":
                innhold = tekst.les("mote", protokoll_for.get(pid))
            else:
                innhold = tekst.les(rom, pid)
            if innhold:
                tekstrader.append((k, did, innhold, kjoring_id))
        cur.executemany("insert into kjerne.dokument_tekst (kommune_id, dokument_id, tekst, kjoring_id) "
                        "values (%s, %s, %s, %s)", tekstrader)
        teller["dokument_tekst"] = len(tekstrader)

        # Vedtak, voteringer og stemmer (regel 2: databasen teller igjen).
        vedtak, vrader, arader, srader = [], [], [], []
        for b in vot:
            bid = b["behandling_id"]
            vedtak.append((k, bid, b.get("vedtak")))
            for v in b["voteringer"]:
                vrader.append((k, bid, v["nr"], v["type"], v["tekst"], v["resultat"], v["resultat_tekst"],
                               v["enstemmig"], v["antall_for"], v["antall_mot"], v["forslagsstiller"],
                               v["parti"], v["dobbeltstemme"], v["tall_stemmer"],
                               "bare_resultat" if v["enstemmig"] else "navneliste"))
                for valg, liste in (("for", v["for"]), ("mot", v["mot"]), ("ikke_til_stede", v["ikke_til_stede"])):
                    for i, n in enumerate(liste):
                        parti = v["partier"][n] if valg != "ikke_til_stede" else None
                        srader.append((k, bid, v["nr"], personer[n], valg, None, parti, i))
                for i, a in enumerate(v["alternativer"]):
                    arader.append((k, bid, v["nr"], a["forslag"], a["antall"], i))
                    for j, n in enumerate(a["navn"]):
                        srader.append((k, bid, v["nr"], personer[n], "alternativ", a["forslag"], a["partier"][n], j))
        cur.executemany("insert into kjerne.vedtak_tolket (kommune_id, behandling_id, vedtak) values (%s, %s, %s)",
                        vedtak)
        cur.executemany(
            "insert into kjerne.votering (kommune_id, behandling_id, nr, type, tekst, resultat, resultat_tekst, "
            "enstemmig, antall_for, antall_mot, forslagsstiller, parti, dobbeltstemme, tall_stemmer, detaljniva) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", vrader)
        cur.executemany("insert into kjerne.votering_alternativ values (%s, %s, %s, %s, %s, %s)", arader)
        cur.executemany("insert into kjerne.stemme values (%s, %s, %s, %s, %s, %s, %s, %s)", srader)
        teller.update(vedtak_tolket=len(vedtak), votering=len(vrader), votering_alternativ=len(arader),
                      stemme=len(srader))

        # Oppmøte.
        omrader, orader, oarader = [], [], []
        for m in opp:
            omrader.append((k, m["mote_id"], m["ikke_tolket"]))
            for i, o in enumerate(m["oppmote"]):
                orader.append((k, m["mote_id"], personer[o["navn"]], i, o["funksjon"], o["repr"],
                               personer[o["vara_for"]] if o["vara_for"] else None))
            for i, a in enumerate(m["avvik"]):
                oarader.append((k, m["mote_id"], i, a["behandling_id"], a["votering"], a["type"],
                                a.get("navn"), a.get("stemmer"), a.get("frammotte")))
        cur.executemany("insert into kjerne.oppmote_mote (kommune_id, mote_id, ikke_tolket) values (%s, %s, %s)",
                        omrader)
        cur.executemany("insert into kjerne.oppmote values (%s, %s, %s, %s, %s, %s, %s)", orader)
        cur.executemany("insert into kjerne.oppmote_avvik values (%s, %s, %s, %s, %s, %s, %s, %s, %s)", oarader)
        teller.update(oppmote_mote=len(omrader), oppmote=len(orader), oppmote_avvik=len(oarader))

        # Verv.
        cur.executemany(
            "insert into kjerne.verv values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [(k, aar, v["utvalg_id"], personer[v["navn"]], v["rolle"], v["repr"], v["person_id"],
              v["i_dagens_liste"], v["i_medlemslister"], v["forst_motte"], v["sist_motte"],
              Jsonb(v["moter_som"]), v["motte_for"]) for v in vervliste])
        teller["verv"] = len(vervliste)

        # Avvik og vurderinger (ADR-015).
        avviksliste = avvik.les(aar, [])
        cur.executemany(
            "insert into kjerne.avvik (kommune_id, avvik, type, utvalg, dato, beskrivelse, kilde) "
            "values (%s, %s, %s, %s, %s, %s, %s)",
            [(k, a["avvik"], a["type"], a["utvalg"], a["dato"], a["beskrivelse"], a.get("kilde"))
             for a in avviksliste])
        cur.executemany(
            "insert into kjerne.avvik_votering values (%s, %s, %s, %s, %s)",
            [(k, a["avvik"], b, nr, i) for a in avviksliste for i, (b, nr) in enumerate(a["voteringer"])])
        vurd = avvik.vurderinger()
        cur.executemany(
            "insert into kjerne.vurdering (kommune_id, avvik, avgjorelse, merknad, begrunnelse, vurdert_av, dato) "
            "values (%s, %s, %s, %s, %s, %s, %s)",
            [(k, v["avvik"], v["avgjorelse"], v.get("merknad"), v["begrunnelse"], v["vurdert_av"], v["dato"])
             for v in vurd])
        teller["avvik"], teller["vurdering"] = len(avviksliste), len(vurd)

        # Navn som kan stå i et sammendrag, og analysene.
        tillatte = konfig.tillatte_navn()
        cur.executemany("insert into kjerne.tillatt_navn (kommune_id, navn, sak_id, begrunnelse, vurdert) "
                        "values (%s, %s, %s, %s, %s)",
                        [(k, n["navn"], n["sak_id"], n["begrunnelse"], n["vurdert"]) for n in tillatte])
        analyser = analyse.alle()
        cur.executemany(
            "insert into kjerne.analyse (kommune_id, sak_id, tittel_klarsprak, sammendrag, betydning, tagger, "
            "utfall, uenighet, usikker, sjekksum, modell, innsats, instruksjon_versjon, dato, tokens_inn, "
            "tokens_ut, kilder, opprettet, kjoring_id) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [(k, a["sak_id"], a["tittel_klarsprak"], a["sammendrag"], a["betydning"], a["tagger"], a["utfall"],
              a["uenighet"], a["usikker"], a["sjekksum"], a["modell"], a["innsats"], a["instruksjon_versjon"],
              a["dato"], (a.get("tokens") or {}).get("inn", 0), (a.get("tokens") or {}).get("ut", 0),
              Jsonb(a["kilder"]), a["dato"], kjoring_id) for a in analyser.values()])
        teller["tillatt_navn"], teller["analyse"] = len(tillatte), len(analyser)

        # Kjøreloggen.
        logg = lager_drift.kjoringer()
        cur.executemany(
            "insert into drift.kjoring (kjoring_id, kilde, start) values (%s, %s, %s)",
            [(kid, "actions" if kid.isdigit() else "lokal", post.get("start")) for kid, post in logg.items()])
        cur.executemany(
            "insert into drift.kjoring_tall (kjoring_id, kommune_id, del, nokkel, verdi) values (%s, %s, %s, %s, %s)",
            [(kid, k, del_, nokkel, verdi) for kid, post in logg.items()
             for del_, tall in post.items() if isinstance(tall, dict) for nokkel, verdi in tall.items()])
        teller["kjoringer"] = len(logg)

        c.execute("update drift.kjoring set slutt = now() where kjoring_id = %s", (kjoring_id,))
    return {"kjoring": kjoring_id, **teller}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aar = int(args[0]) if args else dt.date.today().year
    print(json.dumps(kjor(aar), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
