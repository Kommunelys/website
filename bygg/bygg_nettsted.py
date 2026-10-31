"""Bygger det statiske nettstedet fra dataene, kommuner/ og malen i bygg/mal/.

Hele nettstedet bygges på nytt hver gang, ikke stykkevis. Det tar sekunder ved
denne datamålestokken og fjerner en klasse feil der en gammel side blir
liggende igjen med utdatert innhold.

Malen (index.html, stil.css, app.js) er portert fra prototypen i
bygg/prototype.html. Alt som var skrevet for hånd om enkeltsaker og ett møte,
er fjernet; sidene lages bare fra dataene. Dataene skrives til
nettsted/<kommune>/data/data.js som to objekter, S og VOT, som malen leser.

Nettstedet heter Kommunelys og skal dekke flere kommuner (ADR-016). Roten er
Kommunelys-forsiden med en liste over kommunene; hver kommune har sin egen
mappe. Malen nevner ingen kommune ved navn. Det som er særegent for kommunen,
står i kommuner/<kommune>.json.

ADR-002 og ADR-015: en votering med avvik som ikke er godkjent, publiseres
ikke. Det står at den finnes og hva den gjaldt, men ikke tall eller navn.

    python -m bygg.bygg_nettsted 2026
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

import lager
from bygg import drift
from lager import analyse as lager_analyse
from lager import drift as lager_drift
from lager import kommune as lager_kommune
from lager import konfig
from lager import oppmote as lager_oppmote
from lager import opptak as lager_opptak
from lager import saker as lager_saker
from lager import verv as lager_verv
from lager import voteringer as lager_voteringer
from lager import avvik as lager_avvik
from tester.kontroller import kan_overstyres, sammendrag_avvik_alle, unntatte_navn
from tolk import dekning
from tolk.bygg_avvik import AVGJORELSER, alle_avvik, folkevalgte, holdt_tilbake
from tolk.merknad import merknad_avvik
from tolk.navn import normaliser, partikode
from tolk.profil import profil
from varsel import tilstand as varsel_tilstand

ROT = Path(__file__).resolve().parent.parent
MAL = Path(__file__).resolve().parent / "mal"
UT = ROT / "nettsted"
# Dataene til kommunene med begrenset innsyn (ADR-024). Publiseres ikke;
# kjor.alle lagrer dem i databasen (drift.nettsted_fil).
SKJERMET = ROT / "nettsted-skjermet"
KOMMUNER = ROT / "kommuner"

MERKE = "Kommunelys"
# Lenkene fra før kommunene fikk hver sin mappe (/#saker, /#person/…),
# gjaldt alle denne kommunen. Forsiden sender dem videre dit.
GAMLE_LENKER = "steinkjer"
# Felles for alle kommunene, lagt på roten.
FELLES = ("stil.css", "app.js", "konto.js", "innsyn.js", "favicon.svg", "apple-touch-icon.png", "delingsbilde.png")
# Bildet en lenke får når den deles (Open Graph). Felles, uten kommunenavn.
# Lages fra bygg/delingsbilde.html; se kommentaren der.
DELINGSBILDE = "delingsbilde.png"
# Står i bunnteksten på hver side. Bygget stopper uten (CLAUDE.md:
# utvetydig uoffisiell). Ordlyden er prosjekteiers, 7.10.2026.
UOFFISIELL = "er en uoffisiell tjeneste"

FASTE = ("Leder", "Nestleder", "Medlem")

# Lenken «Meld fra om feil» under hvert sammendrag (ADR-011).
MELD_FEIL = "https://github.com/Kommunelys/website/issues/new"
REPO = MELD_FEIL.rsplit("/issues", 1)[0]
# E-post for feil og innspill. Står på Om-siden, og «Meld fra om feil» åpner
# en e-post hit med saken fylt inn.
KONTAKT_EPOST = "post@kommunelys.no"
# Roten til nettstedet på serveren. 404-siden vises på alle adresser som ikke
# finnes, så den trenger absolutte lenker. Arbeidsflyten setter NETTSTED_BASE
# fra GitHub Pages (tom med eget domene, «/website» før det); lokalt er det «/».
BASE = "/" + "".join(d + "/" for d in os.environ.get("NETTSTED_BASE", "").split("/") if d)
# Nettstedet sett utenfra. Driftssiden vises i portalen og henter stilark og
# lenker herfra.
NETTSTED = "https://kommunelys.no"
# Portalen, der man logger inn (ADR-020). KOMMUNELYS_PORTAL overstyrer lokalt,
# for eksempel http://localhost:5173.
PORTAL = os.environ.get("KOMMUNELYS_PORTAL", "https://portal.kommunelys.no")
# Databasen, for kommunene med begrenset innsyn (innsyn.js, ADR-024). Begge er
# offentlige, som i portalen: nøkkelen gir bare det RLS tillater.
SUPABASE_URL = "https://lsxqodiqkjroihzoikje.supabase.co"
SUPABASE_NOKKEL = "sb_publishable_IXC-qhq0BGYyqLjpk68BsQ_dqQxfsr1"

# Besøkstelling (ADR-017). Koden er kontonavnet i GoatCounter:
# https://<kode>.goatcounter.com. Tom streng slår tellingen av.
GOATCOUNTER = "kommunelys"


def _telling() -> str:
    """Skriptet som teller sidevisninger, eller ingenting.

    Kommunesidene viser fanene med #saker, #person/… i adressen. GoatCounter
    teller ikke det som står etter #, så hver visning telles for hånd med
    stien og fanen. Søketeksten står ikke i adressen og telles ikke.
    """
    if not GOATCOUNTER:
        return ""
    return (
        "<script>function telle(){var g=window.goatcounter;"
        "if(g&&g.count)g.count({path:location.pathname+location.hash.split('?')[0]})}"
        "addEventListener('hashchange',telle)</script>\n"
        f'<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" '
        """data-goatcounter-settings='{"no_onload":true}' """
        'async src="https://gc.zgo.at/count.js" onload="telle()"></script>')


def _kildenavn(k: dict) -> str:
    """«Vedtak i FS 2026-09-03» -> «vedtaket i FS 03.09.2026»."""
    m = re.match(r"Vedtak i (\S+) (\d{4})-(\d\d)-(\d\d)", k["tittel"])
    if m:
        return f"vedtaket i {m.group(1)} {m.group(4)}.{m.group(3)}.{m.group(2)}"
    return "saksframlegget" if k["tittel"] == "Saksframlegg" else k["tittel"]


def _meldinger() -> dict:
    """Det vurderingene av meldinger om feil gjør på nettstedet (ADR-023).

    sammendrag og stemmer: sakene der det som ble meldt, holdes tilbake.
    merk: offentlige merknader per sak, med dato. Merknader som ikke består
    kontrollen (tolk/merknad.py), vises ikke.
    """
    navn = folkevalgte()
    ut: dict = {"sammendrag": set(), "stemmer": set(), "merk": collections.defaultdict(list)}
    for v in lager_avvik.feilmelding_vurderinger():
        if v["avgjorelse"] == "holdes_tilbake" and v["gjelder"] in ("sammendrag", "stemmer"):
            # Et sammendrag som er erstattet av en ny analyse, vises igjen.
            if v["gjelder"] == "stemmer" or v["gjelder_naa"]:
                ut[v["gjelder"]].add(v["sak_id"])
        if v["merknad"] and v["gjelder_naa"]:
            feil = merknad_avvik(v["merknad"], navn)
            if feil:
                print(f"ADVARSEL: merknaden til en melding i sak {v['sak_id']} vises ikke: "
                      f"{'; '.join(feil)}", file=sys.stderr)
            else:
                ut["merk"][v["sak_id"]].append({"t": v["merknad"], "d": v["dato"]})
    return ut


def _sammendrag(saker: list, analyser: dict, meldinger: dict,
                redigert: dict) -> tuple[dict, int]:
    """Sammendragene som kan publiseres, per sak-ID, og hvor mange som holdes tilbake.

    Samme prinsipp som for voteringer: et sammendrag med avvik vises ikke,
    men stopper ikke resten av nettstedet. En vurderer kan slippe gjennom et
    sammendrag der kontrollen bare savner tall eller datoer i kilden
    (kan_overstyres), så lenge grunnene er de samme som da det ble vurdert.
    Prosjektadmin kan slippe gjennom alle grunner (overstyrt), og redigere
    teksten (redigert); den redigerte teksten vises uten ny kontroll og merkes
    (ADR-025). Et sammendrag holdes også tilbake når en melding om feil er
    vurdert slik (ADR-023).
    """
    alle_avvik = sammendrag_avvik_alle(saker, analyser, unntatte_navn())
    vurdert = lager_avvik.sammendrag_vurderinger()
    navn = folkevalgte()
    ut, holdt = {}, 0
    for s in saker:
        a = analyser.get(s["sak_id"])
        if not a:
            continue
        if s["sak_id"] in meldinger["sammendrag"]:
            holdt += 1
            continue
        r = redigert.get(s["sak_id"])
        avvik = alle_avvik[s["sak_id"]]
        v = vurdert.get(s["sak_id"])
        merk_feil = merknad_avvik(v["merknad"], navn) if v else []
        if r:
            a = r
        elif v and v["avgjorelse"] == "ikke_publiser":
            holdt += 1
            continue
        elif avvik:
            godkjent = (v and v["avgjorelse"] == "publiser"
                        and (kan_overstyres(avvik) or v["overstyrt"])
                        and set(avvik) <= set(v["grunner"]) and not merk_feil)
            if not godkjent:
                holdt += 1
                continue
        ut[s["sak_id"]] = {
            "tk": a["tittel_klarsprak"], "sum": a["sammendrag"], "bet": a["betydning"],
            "uen": a["uenighet"], "tags": a["tagger"], "modell": a["modell"],
            "kilder": [{"tittel": _kildenavn(k), "url": k["url"]} for k in a["kilder"]],
        }
        if r:
            ut[s["sak_id"]]["red"] = r["dato"]
        if v and v["merknad"] and not merk_feil:
            ut[s["sak_id"]]["merk"] = {"t": v["merknad"], "d": v["dato"]}
    return ut, holdt

def _opptak(aar: int, saker: list, meldinger: dict) -> tuple[dict, dict, dict, int]:
    """Lenkene til opptakene og sammendragene av debatten (ADR-026).

    Gir opptaket per møte, bokmerkene per behandling, debatten som kan vises
    per behandling, og hvor mange debatter som holdes tilbake. Lenkene
    står også når opptaket ikke er tekstet; bare debatten trenger tekstingen.
    Et opptak kommunen har slettet («fjernet»), får ingen lenke.

    Kontrollen lagres når grunnene er endret siden sist, så portalen kan vise
    det som holdes tilbake. Som for sammendragene kan en vurderer slippe
    gjennom en debatt der kontrollen bare ikke fant partiet i tekstingen
    (kan_overstyres), og prosjektadmin alt annet enn feil del eller tid
    (overstyrt), så lenge grunnene er de samme som da den ble vurdert.
    """
    from analyser.analyser_debatt import avvik as debatt_avvik  # noqa: PLC0415
    from analyser.analyser_debatt import deler_for, kan_aldri_publiseres  # noqa: PLC0415
    from analyser.analyser_debatt import kan_overstyres as debatt_kan_overstyres  # noqa: PLC0415

    opptak = [o for o in lager_opptak.alle() if not o.get("fjernet")]
    per_mote, per_steg = {}, {}
    for o in opptak:
        per_mote[o["mote_id"]] = {"u": o["url"], "d": o["varighet_s"], "tx": o["teksting"]}
        for hid in dict.fromkeys(d["behandling_id"] for d in o["deler"] if d["behandling_id"]):
            ds = deler_for(o, hid)
            per_steg[hid] = [{
                "u": f"{o['url']}?caseId={d['bokmerke_id']}",
                "s": d["start_ms"] // 1000, "d": d["varighet_ms"] // 1000,
                # «Før pausen» og «Etter pausen» når saken er delt i opptaket.
                **({"t": d["tittel"].rsplit(" - ", 1)[-1]} if len(ds) > 1 and " - " in d["tittel"] else {}),
            } for d in ds]

    debatter = lager_opptak.debatter()
    sak_for = {st["behandling_id"]: s for s in saker for st in s["saksgang"]}
    voteringer = {b["behandling_id"]: b for b in lager_kommune.alle_aar(lager_voteringer.les, aar)}
    o_id = {o["opptak_id"]: o for o in opptak}
    tekster: dict[int, dict | None] = {}
    lagret, nye = lager_opptak.debatt_kontroller(), {}
    vurdert = lager_opptak.debatt_vurderinger()
    navn = folkevalgte()
    vis, holdt = {}, 0
    for hid, d in debatter.items():
        sak, o, b = sak_for.get(hid), o_id.get(d["opptak_id"]), voteringer.get(hid)
        if not (sak and o and b) or hid not in per_steg:
            continue
        if d["opptak_id"] not in tekster:
            tekster[d["opptak_id"]] = lager_opptak.teksting(d["opptak_id"])
        t = tekster[d["opptak_id"]]
        feil = debatt_avvik(d, sak, b, o, t) if t else ["tekstingen mangler"]
        if lagret.get(hid) != feil:
            nye[hid] = feil
        if sak["sak_id"] in meldinger["sammendrag"]:
            holdt += 1
            continue
        v = vurdert.get(hid)
        merk_feil = merknad_avvik(v["merknad"], navn) if v else []
        if v and v["avgjorelse"] == "ikke_publiser":
            holdt += 1
            continue
        if feil:
            godkjent = (v and v["avgjorelse"] == "publiser" and not kan_aldri_publiseres(feil)
                        and (debatt_kan_overstyres(feil) or v["overstyrt"])
                        and set(feil) <= set(v["grunner"]) and not merk_feil)
            if not godkjent:
                holdt += 1
                continue
        vis[hid] = {"ing": 1} if d["ingen_debatt"] else {
            "o": d["oppsummering"], "n": d["antall_innlegg"],
            "p": [{"t": p["tekst"], "pa": p["partier"], "del": p["del"], "s": p["tid_s"]}
                  for p in d["punkter"]],
        }
        if v and v["merknad"] and not merk_feil and not d["ingen_debatt"]:
            vis[hid]["merk"] = {"t": v["merknad"], "d": v["dato"]}
    lager_opptak.lagre_debatt_kontroller(nye)
    return per_mote, per_steg, vis, holdt


# Hvorfor stemmene i en votering ikke vises. Står på voteringen, med lenke til
# protokollen, som alltid gjelder.
GRUNN = {
    "ikke_publiser": "Stemmene vises ikke: protokollen er selvmotsigende, og det går ikke an å si fra dokumentet hvordan partiene stemte.",
    "ikke_vurdert": "Stemmene vises ikke ennå: protokollen er selvmotsigende, og avviket er ikke gått gjennom.",
}
# Når en melding om feil i stemmene er vurdert slik (ADR-023).
GRUNN_MELDING = "Stemmene vises ikke: det er meldt om en feil i dem, og de holdes tilbake til den er rettet."
# En avgjørelse bygget ikke kjenner, regnes som ingen vurdering: voteringen
# holdes tilbake, og bygget sier fra (tester.kontroller stopper den også).
UKJENT = "ikke_vurdert"


# Det i kommuner/<slug>.json som ikke hører til visningen, og ikke sendes til
# nettleseren: kilden i portalen, opptakstjenesten, regelsettet og nivåene.
IKKE_VISNING = ("kilde", "opptak", "tolk", "nivaa", "fra_aar")


def _kommune(slug: str | None = None) -> dict:
    """Visningsoppsettet for kommunen (standard: den bygget gjelder, KOMMUNELYS_KOMMUNE)."""
    slug = slug or lager_kommune.slug()
    k = lager_kommune.oppsett(slug)
    for nokkel in IKKE_VISNING:
        k.pop(nokkel, None)
    # Malen bruker «KS» når kommunen ikke har en annen kode for kommunestyret.
    if profil(slug).kommunestyre_kode != "KS":
        k["kommunestyre_kode"] = profil(slug).kommunestyre_kode
    return k


def _nivaa() -> dict:
    """Hva kommunen publiseres med (ADR-021). Uten «nivaa» er alt med."""
    return {"voteringer": True, "oppmote": True} | lager_kommune.oppsett().get("nivaa", {})


def _fyll(mal: str, verdier: dict[str, str]) -> str:
    """Bytter ut {{navn}} i malen. Stopper hvis noe står igjen."""
    for navn, verdi in verdier.items():
        mal = mal.replace("{{" + navn + "}}", verdi)
    rest = sorted(set(re.findall(r"\{\{\w+\}\}", mal)))
    if rest:
        raise SystemExit(f"ikke fylt inn i malen: {rest}")
    return mal


# Hvem som står bak et forslag, skrevet først i teksten: «På vegne av H, V,
# INP, PP:», «Fra SV og Rødt:», «Forslag fra Rødt, AP, SV og Frp:», ofte uten
# kolon. Listen består av partier, «uavhengig representant X» eller en
# person med parti («Kjell Haugan Ap»). Det som ikke passer, regnes som
# begynnelsen på selve forslaget.
_PARTI = (r"(?:Ap|AP|Arbeiderpartiet|H|Høyre|Sp|SP|Senterpartiet|SV|Sv|R|Rødt|"
          r"FrP|Frp|FRP|Fremskrittspartiet|INP|Inp|PP|Pp|Pensjonistpartiet|V|Venstre|KrF|Krf|"
          r"Uavh\.?|[Uu]avhengig(?: representant(?: [A-ZÆØÅ][\wæøå-]+)?)?|alle partier)")
_LEDD = rf"(?:(?:[A-ZÆØÅ][\wæøå-]+ ){{1,3}}{_PARTI}|{_PARTI})"
# Foran står ofte hva slags forslag det er: «Alternativt på vegne AP, …»,
# «Alternativt helhetlig forslag fra Rødt, …», «Fellesforslag Rødt og AP».
_SLAG = r"(?:Alternativt|alternativt|Helhetlig|helhetlig|Tilleggsforslag|Forslag|forslag|forlag)"
_AVSENDER = re.compile(
    rf"^(?:(?:{_SLAG}\s+)*(?:[Pp]å vegne(?: av)?|[Ff]ra)|Fellesforslag(?: fra)?):?\s+"
    rf"(?P<bak>{_LEDD}(?:(?:\s*[,;]+\s*og\s+|\s*[,;]+\s*|\s+og\s+){_LEDD})*)(?![\wæøå])"
    r"[\s.,:]*")


def _avsender_og_tekst(tekst: str) -> tuple[str | None, str]:
    """«På vegne av H, V: 1. Kommunestyret …» -> («H, V», «1. Kommunestyret …»)."""
    tekst = re.sub(r"\s+", " ", tekst or "").strip()
    m = _AVSENDER.match(tekst)
    if not m or not tekst[m.end():]:
        return None, tekst
    bak = re.sub(r"\s*[,;][\s,;]*", ", ", m.group("bak")).strip(" ,")
    return bak, tekst[m.end():]


def _etikett(v: dict, tekst: str) -> str:
    """Hva voteringen gjaldt, kort: starten av forslaget, uten avsenderen."""
    if len(tekst) > 160:
        tekst = tekst[:157].rsplit(" ", 1)[0] + " …"
    return tekst or {"innstilling": "Innstillingen"}.get(v["type"], v["type"].capitalize())


# Ved alternativ votering står forslagene etter hverandre i protokollen:
# «<forslag 1> Dette ble satt opp mot: 2) Navn (Parti) fremmet følgende
# alternative forslag: <forslag 2>». Gjelder alle 61 i 2026.
_SATT_OPP_MOT = "Dette ble satt opp mot:"
_ALT_FORSLAG = re.compile(
    r"^\s*(?P<fs>\d)\)\s*(?P<stiller>[^()]{3,80}?)\s*\((?P<parti>[^)]+)\)\s*"
    r"fremmet følgende (?P<type>[\w ]*?forslag):\s*")


def _alternative_deler(v: dict, tekst: str, bak: str | None) -> list[dict] | None:
    """Forslagene i en alternativ votering, hvert for seg, med hvem som fremmet dem."""
    if not v["alternativer"] or _SATT_OPP_MOT not in tekst:
        return None
    forste, andre = tekst.split(_SATT_OPP_MOT, 1)
    del1 = {"fs": "1", "tekst": forste.strip(), "type": v["type"],
            "stiller": v["forslagsstiller"], "parti": v["parti"], "bak": bak}
    m = _ALT_FORSLAG.match(andre)
    if not m:
        return [del1, {"fs": "2", "tekst": andre.strip()}]
    bak2, rest = _avsender_og_tekst(andre[m.end():])
    return [del1, {"fs": m.group("fs"), "tekst": rest, "type": m.group("type").strip(),
                   "stiller": normaliser(m.group("stiller")),
                   "parti": partikode(m.group("parti")), "bak": bak2}]


def _alternativ_som_for_og_mot(v: dict) -> tuple[list[str], list[str], str]:
    """Alternativ votering vises per forslag. For statistikken telles stemmene
    for forslaget som ble vedtatt, som «for», og resten som «mot». Returnerer
    også nummeret på forslaget som ble vedtatt, slik protokollen oppgir det."""
    alt = v["alternativer"]
    m = re.search(r"forslag (\S+) vedtatt", v.get("resultat_tekst") or "")
    vinner = next((a for a in alt if m and a["forslag"] == m.group(1)), None)
    vinner = vinner or max(alt, key=lambda a: a["antall"])
    andre = [n for a in alt if a is not vinner for n in a["navn"]]
    return list(vinner["navn"]), andre, vinner["forslag"]


def _tema(s: dict, sammendrag: dict) -> list[str]:
    """Tema fra modellen, pluss «Høring», som kan leses sikkert av tittelen."""
    tema = set((sammendrag.get(s["sak_id"]) or {}).get("tags") or [])
    if re.search(r"\bhøring", s["tittel"], re.I):
        tema.add("Høring")
    return sorted(tema)


def _slug(navn: str) -> str:
    """«Tor-André Hopen» -> «tor-andre-hopen». Adressen til en profil."""
    s = navn.lower()
    for a, b in (("æ", "ae"), ("ø", "o"), ("å", "a"), ("é", "e"), ("è", "e"),
                 ("ä", "a"), ("ö", "o"), ("ü", "u")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _verv_alle(aarene: list[int]) -> list[dict]:
    """Vervene for alle årene, slått sammen per utvalg og person (ADR-022).

    «Møtt» summeres, «møtt for» slås sammen, og rolle, parti og dagens liste
    tas fra det nyeste året. Kortkoden for utvalget hentes fra alle årene, så
    et utvalg som ikke har møtt ennå i år (januar), ikke mister koden.
    """
    per_aar = [lager_verv.les(a, []) for a in aarene]
    if len(per_aar) == 1:
        return per_aar[0]
    kode = {v["utvalg_id"]: v["utvalg"] for vs in per_aar for v in vs if v["utvalg"]}
    samlet: dict[tuple, dict] = {}
    for vs in per_aar:  # eldste år først; det nyeste overstyrer
        for v in vs:
            n = (v["utvalg_id"], v["navn"])
            if n not in samlet:
                samlet[n] = {**v, "moter_som": dict(v["moter_som"]), "motte_for": list(v["motte_for"])}
                continue
            g = samlet[n]
            for k, x in v["moter_som"].items():
                g["moter_som"][k] = g["moter_som"].get(k, 0) + x
            g["motte_for"] += [x for x in v["motte_for"] if x not in g["motte_for"]]
            for k in ("rolle", "repr", "i_dagens_liste", "person_id"):
                g[k] = v[k]
    for g in samlet.values():
        g["utvalg"] = kode.get(g["utvalg_id"], g["utvalg"])
    return list(samlet.values())


def _utvalg_alle(aarene: list[int]) -> dict:
    """Utvalgene for alle årene. Partiene og medlemslisten fra det nyeste året."""
    tom = {"partier": {}, "medlemsliste_hentet": ""}
    per_aar = [lager_verv.les_utvalg(a, tom) for a in aarene]
    if len(per_aar) == 1:
        return per_aar[0]
    nyeste = next((u for u in reversed(per_aar) if u.get("medlemsliste_hentet")), per_aar[-1])
    return {**nyeste, "utvalg": [x for u in per_aar for x in u.get("utvalg", [])]}


def _folk(verv: list) -> list[dict]:
    """De folkevalgte, med verv og oppmøte, til profilene.

    Bare personer som representerer et parti i minst ett utvalg. Medlemmer av
    råd som ikke er valgt for et parti, for eksempel ungdomsrådet, får ikke
    profil. Alt kommer fra medlemslistene og møteprotokollene; ingenting er
    skrevet av en modell, og ingenting er hentet fra andre kilder.
    """
    partier = set(profil().partikoder.values())
    # Samlet på navn, ikke person-ID: portalen har noen ganger to ID-er for
    # samme person (Monika Luktvasslimo i HPNM). Navnene er normalisert i
    # tolk/navn.py, slik stemmene også er.
    per_person: dict[str, list] = collections.defaultdict(list)
    for v in verv:
        per_person[v["navn"]].append(v)
    ut = []
    for vs in per_person.values():
        if not any(v["repr"] in partier for v in vs):
            continue
        # Partiet i kommunestyret gjelder; ellers det som står i flest verv.
        ks = [v["repr"] for v in vs if v["utvalg"] == profil().kommunestyre_kode and v["repr"] in partier]
        parti = ks[0] if ks else collections.Counter(
            v["repr"] for v in vs if v["repr"] in partier).most_common(1)[0][0]
        ut.append({
            "id": _slug(vs[0]["navn"]), "n": vs[0]["navn"], "p": parti,
            "verv": [{"u": v["utvalg"], "r": v["rolle"], "p": v["repr"],
                      "i": v["i_dagens_liste"], "m": sum(v["moter_som"].values()),
                      "for": v["motte_for"]} for v in vs],
        })
    ider = collections.Counter(p["id"] for p in ut)
    dobbel = [i for i, n in ider.items() if n > 1]
    if dobbel:
        raise SystemExit(f"to personer får samme profiladresse: {dobbel}")
    return sorted(ut, key=lambda p: p["n"])


def _oppmote(o: dict, partier: set) -> dict:
    """Hvem som møtte, fra møteprotokollen. Som på profilene står bare de som er
    valgt for et parti, med navn; de andre telles. «avvik» betyr at stemmene i
    protokollen ikke stemmer med oppmøtelisten (tolk.bygg_oppmote)."""
    med = [p for p in o["oppmote"] if p["repr"] in partier]
    return {"navn": [{"n": p["navn"], "p": p["repr"], "f": p["funksjon"], "vf": p["vara_for"]}
                     for p in med],
            "andre": len(o["oppmote"]) - len(med), "avvik": bool(o["avvik"])}


def _s(aarene: list[int], saker: list, moter: list, sammendrag: dict, kommune: dict,
       vedtak: dict, med_oppmote: bool = True, opptak: tuple = ({}, {}, {})) -> dict:
    """Saker, møter, utvalg og kommunestyret, i formen malen bruker.

    vedtak er vedtaksteksten per behandling, uendret fra protokollen. Den står
    på hvert steg i saksgangen, også der ingen stemte, som uttalelsene fra rådene.
    opptak er lenkene til opptaket per møte og per behandling, og debatten som
    kan vises per behandling (_opptak).
    """
    op_mote, op_steg, debatt = opptak
    politiske = collections.Counter(
        st["mote_id"] for s in saker if s["sakstype"] == "PS" and not s["formalia"]
        for st in s["saksgang"])
    # Uten oppmøte i nivåene vises det ikke, og malen sier hvorfor (S.ikke_oppmote).
    aar = aarene[-1]
    oppmote = lager_kommune.alle_aar(lager_oppmote.les, aar) if med_oppmote else []
    opp_mote = {o["mote_id"]: o for o in oppmote}
    partier = set(profil().partikoder.values())
    cases = [{
        "id": s["sak_id"],
        "formal": s["formalia"],
        "t": s["tittel"],
        "typ": s["sakstype"],
        "tags": _tema(s, sammendrag),
        **({"a": sammendrag[s["sak_id"]]} if s["sak_id"] in sammendrag else {}),
        "st": [{
            "hid": st["behandling_id"], "date": st["dato"], "ut": st["utvalg_navn"],
            "sc": st["utvalg"], "nr": st["saksnr"], "pub": st["protokoll_publisert"],
            "restr": st["protokoll_skjermet"], "mid": st["mote_id"],
            "prot": st["url_vedtak"], "murl": st["url_mote"],
            **({"vt": vedtak[st["behandling_id"]]} if vedtak.get(st["behandling_id"]) else {}),
            **({"op": op_steg[st["behandling_id"]]} if st["behandling_id"] in op_steg else {}),
            **({"deb": debatt[st["behandling_id"]]} if st["behandling_id"] in debatt else {}),
        } for st in s["saksgang"]],
        "status": s["status"],
        "doc": (s.get("saksframlegg") or {}).get("url"),
        "att": len(s.get("vedlegg") or []),
        "ks": s["til_kommunestyret"],
    } for s in saker]
    meetings = [{
        "id": m["mote_id"], "date": m["dato"], "end": m["slutt"], "ut": m["utvalg_navn"],
        "sc": m["utvalg"], "sted": m["sted"], "rom": m["rom"], "n": m["antall_saker"],
        "nps": politiske.get(m["mote_id"], 0),
        "docs": [{"t": d["tittel"], "ty": d["type"], "u": d["url"]} for d in m["dokumenter"]],
        "url": m["url"],
        **({"op": op_mote[m["mote_id"]]} if m["mote_id"] in op_mote else {}),
        **({"opp": _oppmote(opp_mote[m["mote_id"]], partier)} if m["mote_id"] in opp_mote else {}),
    } for m in moter]

    utvalg = _utvalg_alle(aarene)
    verv = _verv_alle(aarene)
    seter = collections.Counter(v["repr"] for v in verv
                                if v["utvalg"] == profil().kommunestyre_kode and v["rolle"] in FASTE and v["i_dagens_liste"])
    # Møter med møteprotokoll per utvalg, som grunnlag for oppmøtet.
    protokoller = collections.Counter(o["utvalg"] for o in oppmote)
    return {
        "merke": MERKE,
        "kommune": kommune,
        "aar": aar,
        # Bare når det er flere år, så nettstedet med ett år er som før.
        **({"aarene": aarene} if len(aarene) > 1 else {}),
        "today": lager.i_dag(),
        "cases": cases,
        "meetings": meetings,
        "utvalg": {m["utvalg_navn"]: m["utvalg"] for m in moter},
        "utvnavn": {u["kortnavn"]: u["navn"] for u in utvalg.get("utvalg", [])},
        "partier": utvalg["partier"],
        "partisider": konfig.partisider().get("partier", {}),
        "ks": {"seter": dict(seter), "hentet": utvalg["medlemsliste_hentet"]},
        # Antall medlemmer per utvalg i dagens medlemsliste. Bare de som er valgt
        # for et parti, har profil og vises med navn; resten telles.
        "medl": {u: {"faste": sum(1 for v in verv if v["utvalg"] == u and v["i_dagens_liste"]
                                  and v["rolle"] in FASTE),
                     "vara": sum(1 for v in verv if v["utvalg"] == u and v["i_dagens_liste"]
                                 and v["rolle"] not in FASTE)}
                 for u in sorted({v["utvalg"] for v in verv})},
        "folk": _folk(verv),
        "mprot": dict(protokoller),
        "meld": MELD_FEIL,
        "repo": REPO,
        "epost": KONTAKT_EPOST,
        # «Meld fra om feil» går til skjemaet i portalen, som krever
        # innlogging (ADR-023).
        "portal": PORTAL,
        **({} if med_oppmote else {"ikke_oppmote": True}),
    }


def _vot(aar: int, saker: list, moter: list, meldinger: dict) -> tuple[dict, int]:
    """Voteringene per møte, med avvik som ikke er godkjent, holdt tilbake.

    Stemmene i en sak holdes også tilbake når en melding om feil i dem er
    vurdert slik (ADR-023).
    """
    voteringer = lager_kommune.alle_aar(lager_voteringer.les, aar)
    stopp, merknader = holdt_tilbake(aar)
    status = {a["avvik"]: a["status"] for a in alle_avvik(aar)}
    tittel = {st["behandling_id"]: s["tittel"] for s in saker for st in s["saksgang"]}
    meldt = {st["behandling_id"] for s in saker for st in s["saksgang"] if s["sak_id"] in meldinger["stemmer"]}
    mote_for = {st["behandling_id"]: st["mote_id"] for s in saker for st in s["saksgang"]}
    mote = {m["mote_id"]: m for m in moter}

    per_mote: dict[int, list] = collections.defaultdict(list)
    parti: dict[str, str] = {}
    holdt = 0
    ukjent: set[tuple[str, str]] = set()
    for b in voteringer:
        mid = mote_for.get(b["behandling_id"])
        if mid not in mote or not b["voteringer"]:
            continue
        vs = []
        for v in b["voteringer"]:
            nokkel = (b["behandling_id"], v["nr"])
            bak, tekst = _avsender_og_tekst(v.get("tekst"))
            # Hele forslagsteksten følger med; etiketten er bare starten.
            ut = {"nr": v["nr"], "type": v["type"], "stiller": v["forslagsstiller"],
                  "parti": v["parti"], "lbl": _etikett(v, tekst), "tekst": tekst,
                  "bak": bak, "res": v["resultat"],
                  "en": v["enstemmig"], "dob": v["dobbeltstemme"]}
            if b["behandling_id"] in meldt:
                ut["holdt"] = GRUNN_MELDING
                holdt += 1
            elif nokkel in stopp:
                grunner = []
                for a in stopp[nokkel]:
                    s = status.get(a, "ikke_vurdert")
                    if s not in GRUNN:
                        ukjent.add((a, s))
                        s = UKJENT
                    grunner.append(s)
                ut["holdt"] = GRUNN[min(grunner, key=list(GRUNN).index)]
                holdt += 1
            elif not v["enstemmig"]:
                f, m = v["for"], v["mot"]
                if v["alternativer"]:
                    f, m, ut["vinner"] = _alternativ_som_for_og_mot(v)
                    ut["deler"] = _alternative_deler(v, tekst, bak)
                ut.update(nfor=len(f) if v["alternativer"] else v["antall_for"],
                          nmot=len(m) if v["alternativer"] else v["antall_mot"],
                          f=f, m=m, borte=v["ikke_til_stede"],
                          alt=[{"fs": a["forslag"], "n": a["antall"], "navn": a["navn"]}
                               for a in v["alternativer"]],
                          merk=merknader.get(nokkel, []))
                parti.update(v["partier"])
            else:
                ut["merk"] = merknader.get(nokkel, [])
            vs.append(ut)
        # Vedtaksteksten står på saksgangen i S (st.vt), ikke her.
        per_mote[mid].append({"hid": b["behandling_id"], "nr": b["saksnr"],
                              "t": tittel.get(b["behandling_id"], ""), "v": vs})

    moter_ut = [{"id": mid, "date": mote[mid]["dato"], "sc": mote[mid]["utvalg"],
                 "ut": mote[mid]["utvalg_navn"],
                 # Møteprotokollen er fasit når protokollen er selvmotsigende.
                 "mp": next((d["url"] for d in mote[mid].get("dokumenter") or []
                             if d.get("type") == "MP"), None),
                 "saker": sorted(s, key=lambda x: _saksnr_sortering(x["nr"]))}
                for mid, s in per_mote.items()]
    moter_ut.sort(key=lambda m: m["date"])
    for a, s in sorted(ukjent):
        print(f"ADVARSEL: avviket {a} har ukjent avgjørelse «{s}»; voteringene holdes tilbake "
              f"som ikke vurdert. Gyldige: {', '.join(AVGJORELSER)}.", file=sys.stderr)
    return {"moter": moter_ut, "parti": parti}, holdt


def _saksnr_sortering(nr: str) -> tuple:
    m = re.match(r"(\w+) (\d+)/(\d+)", nr or "")
    return (m.group(1) != "PS", int(m.group(3)), int(m.group(2))) if m else (True, 0, 0)


# Personikonet for «Logg inn» på smale skjermer.
PERSON = ('<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">'
          '<circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="2"/>'
          '<path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7" fill="none" stroke="currentColor" '
          'stroke-width="2" stroke-linecap="round"/></svg>')


# Hengelåsen for kommunene med begrenset innsyn (ADR-024).
LAAS = ('<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">'
        '<rect x="5" y="11" width="14" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M8 11V7a4 4 0 0 1 8 0v4" fill="none" stroke="currentColor" stroke-width="2"/></svg>')


def _v(navn: str) -> str:
    """Versjonen av en fil i malen, til ?v=: nettleseren henter filen på nytt
    når innholdet endres, og bruker den den har ellers."""
    return hashlib.sha256((MAL / navn).read_bytes()).hexdigest()[:10]


def _konto(rot: str) -> str:
    """Kontomenyen øverst til høyre: lenker til portalen, og kontoen når man
    er logget inn (konto.js). rot er veien til roten av nettstedet."""
    p = html.escape(PORTAL)
    # Med API-et og den offentlige nøkkelen finner konto.js kommunene med
    # begrenset innsyn som kontoen har tilgang til (ADR-024).
    return (f'<div class="konto" data-portal="{p}" data-api="{SUPABASE_URL}" data-nokkel="{SUPABASE_NOKKEL}">'
            f'<a href="{p}/login" data-sti="/login" aria-label="Logg inn">{PERSON}'
            f'<span class="konto-tekst">Logg inn</span></a>'
            f'<a class="konto-ny" href="{p}/registrer" data-sti="/registrer">Ny bruker</a>'
            f'</div><script src="{rot}konto.js?v={_v("konto.js")}" defer></script>')


def _url(sti: str = "") -> str:
    """Den kanoniske adressen til en side, for eksempel «steinkjer/» eller «om/»."""
    return f"{NETTSTED}{BASE}{sti}"


def _deling(sti: str, tittel: str, beskrivelse: str) -> str:
    """Beskrivelsen, den kanoniske adressen og Open Graph i <head>.

    Den kanoniske adressen gjør at søkemotorene ser én side, også når den nås
    som /om/?kommune=…. Open Graph gir tittel, tekst og bilde når lenken deles
    på Facebook, Messenger og lignende.
    """
    a = html.escape
    url = a(_url(sti))
    bilde = a(f"{_url(DELINGSBILDE)}?v={_v(DELINGSBILDE)}")
    return "\n".join([
        f'<meta name="description" content="{a(beskrivelse)}">',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{MERKE}">',
        '<meta property="og:locale" content="nb_NO">',
        f'<meta property="og:title" content="{a(tittel)}">',
        f'<meta property="og:description" content="{a(beskrivelse)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{bilde}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{MERKE}: et klarere blikk på vedtakene">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def _merke_ikon() -> str:
    """Merket i SVG, felles for toppen på alle sidene."""
    return (MAL / "merke.svg").read_text("utf-8").strip()


def _dato(d: dt.date) -> str:
    return f"{d.day}.{d.month}.{d.year}"


def _hentet(status: dict) -> dt.date:
    """Dataene hentes og nettstedet bygges i samme kjøring av arbeidsflyten."""
    return dt.datetime.fromisoformat(status["bygget"]).date()


# Det i sammendraget som bare sakssiden bruker. Tittel, sammendrag (søket) og
# betydning blir i data.js.
DETALJER_A = ("uen", "tags", "modell", "kilder", "red")


def _del_detaljer(S: dict, VOT: dict, sakens_aar: dict[int, int]) -> dict[int, dict]:
    """Tar ut det bare sakssiden bruker, og gir det tilbake per år (ADR-022).

    Hele sammendraget, vedtakstekstene (st.vt), debatten (st.deb) og
    forslagstekstene i voteringene (v.tekst, deler[].tekst) står i data/detaljer-<år>.json og
    hentes når en sak åpnes. Året er året saken begynte. S og VOT endres.
    """
    ut: dict[int, dict] = {a: {"a": {}, "vt": {}, "v": {}, "d": {}} for a in set(sakens_aar.values())}
    sak_for = {}
    for c in S["cases"]:
        d = ut[sakens_aar[c["id"]]]
        if "a" in c:
            d["a"][c["id"]] = {k: c["a"].pop(k) for k in DETALJER_A if k in c["a"]}
        for x in c["st"]:
            sak_for[x["hid"]] = c["id"]
            if "vt" in x:
                d["vt"][x["hid"]] = x.pop("vt")
            # Debatten (ADR-026). Steget beholder et merke, så sidene vet at den finnes:
            # 1 med innlegg, 0 når ingen hadde ordet. Forsiden velger saker etter det.
            if "deb" in x:
                d["d"][x["hid"]] = deb = x.pop("deb")
                x["db"] = 0 if deb.get("ing") else 1
    for m in VOT["moter"]:
        for s in m["saker"]:
            d = ut[sakens_aar[sak_for[s["hid"]]]] if s["hid"] in sak_for else None
            for v in s["v"]:
                tekst = {"tekst": v.pop("tekst", None)}
                if v.get("deler"):
                    tekst["deler"] = [x.pop("tekst", None) for x in v["deler"]]
                if d is not None:
                    d["v"][f"{s['hid']}-{v['nr']}"] = tekst
    return ut


def _skript(kommune: dict, begrenset: bool) -> str:
    """Skriptene som tegner siden. Med begrenset innsyn henter innsyn.js
    dataene fra databasen med innloggingen, og laster app.js etterpå (ADR-024)."""
    app = f"../app.js?v={_v('app.js')}"
    if not begrenset:
        return (f'<script src="data/data.js"></script>\n<script src="{app}"></script>\n'
                "<script>if(!window.KL_KLAR)document.getElementById('lastefeil').hidden=false</script>")
    a = html.escape
    return (f'<script src="../innsyn.js?v={_v("innsyn.js")}" data-kommune="{a(kommune["slug"])}" '
            f'data-navn="{a(kommune["navn"])}" data-app="{a(app)}" data-portal="{a(PORTAL)}" '
            f'data-api="{a(SUPABASE_URL)}" data-nokkel="{a(SUPABASE_NOKKEL)}" '
            f'data-epost="{a(KONTAKT_EPOST)}"></script>')


# Sakene på kommunesiden uten skript: fra så mange av de siste møtene i
# kommunestyret, og høyst så mange.
VIKTIGE_MOTER = 3
VIKTIGE_ANTALL = 6


def _viktige(S: dict) -> str:
    """De siste sakene fra kommunestyret som HTML i #viktig.

    Søkemotorer og språkmodeller som leser siden uten skript, ser da hva siden
    handler om, ikke bare menyen. app.js tegner kortene på nytt (viktigeSaker).
    Bare saker med et publisert sammendrag er med, og ikke saker om
    enkeltpersoners verv (temaet «Folkevalgte»), som i app.js. Teksten er
    merket KI og har lenke til kilden. Må kalles før _del_detaljer, som tar
    ut kildene. Aldri for en kommune med begrenset innsyn: siden er åpen.
    """
    ks = profil().kommunestyre_kode
    moter = sorted((m for m in S["meetings"] if m["sc"] == ks and m["date"][:10] < S["today"]),
                   key=lambda m: m["date"])[-VIKTIGE_MOTER:]
    kort = []
    for m in reversed(moter):
        for c in S["cases"]:
            a = c.get("a")
            if (c["typ"] != "PS" or c["formal"] or not a or not a.get("bet")
                    or "Folkevalgte" in c["tags"] or not any(x["mid"] == m["id"] for x in c["st"])):
                continue
            kilde = (a.get("kilder") or [{"tittel": "saksframlegget", "url": c["doc"]}])[0]
            if kilde["url"]:
                kort.append((m, c, kilde))
    e = html.escape
    return "\n".join(
        '<article class="sakkort vkort">'
        f'<div class="vtopp"><a href="#mote/{m["id"]}">{e(m["ut"])} {_dato(dt.date.fromisoformat(m["date"][:10]))}</a>'
        f'<span class="st {"ok" if c["status"].startswith("Vedtatt") else "bh"}">{e(c["status"])}</span></div>'
        f'<h3><a href="#sak/{c["id"]}">{e(c["a"]["tk"])}</a></h3>'
        f'<p class="bet"><span class="ki" title="Skrevet av KI ut fra saksdokumentene">KI</span> {e(c["a"]["bet"])}</p>'
        f'<a class="kort-lenke" href="{e(kilde["url"])}">Kilde: {e(kilde["tittel"])}</a>'
        '</article>'
        for m, c, kilde in kort[:VIKTIGE_ANTALL])


def _kommuneside(kommune: dict, ut: Path, begrenset: bool = False, viktige: str = "") -> None:
    """index.html for én kommune, med navnet fylt inn i malen."""
    navn = html.escape(kommune["navn"])
    side = _fyll((MAL / "index.html").read_text("utf-8"),
                 {"merke": MERKE, "merke_ikon": _merke_ikon(), "konto": _konto("../"), "v_stil": _v("stil.css"),
                  "kommune": navn, "skript": _skript(kommune, begrenset), "viktige": viktige,
                  "deling": _deling(f'{kommune["slug"]}/', f"Politikken i {kommune['navn']}: saker, vedtak og stemmer",
                                    f"Uoffisiell oversikt over politiske saker, møter og stemmegivning i "
                                    f"{kommune['navn']} kommune, laget av en innbygger for innbyggerne."),
                  # Søkemotorene ser bare innloggingen; den skal ikke vises i søk.
                  "robots": '<meta name="robots" content="noindex">\n' if begrenset else "",
                  "slug": kommune["slug"], "meld": MELD_FEIL, "telling": _telling()})
    if UOFFISIELL not in (MAL / "app.js").read_text("utf-8"):
        raise SystemExit(f"bunnteksten i app.js mangler «{UOFFISIELL}»")
    (ut / "index.html").write_text(side, encoding="utf-8")


def _kart(kommuner: list[dict], begrensede: frozenset[str] = frozenset()) -> str:
    """Kartet over Trøndelag på forsiden, som SVG.

    Kommunene med data er lenker og farget. Kommunene som bruker samme
    innsynsportal (kommuner/kart/kandidater.json) er grå, fordi de kommer snart;
    de andre er lysere. En kommune med begrenset innsyn tegnes som om den ikke
    hadde data, og lenken over den er skjult (data-begrenset). konto.js viser
    den for kontoer med tilgang. Grensene lages av bygg.lag_kart og ligger i
    kommuner/kart/.
    """
    kart = json.loads((KOMMUNER / "kart" / "trondelag.json").read_text("utf-8"))
    kandidater = {k["kommunenr"] for k in json.loads(
        (KOMMUNER / "kart" / "kandidater.json").read_text("utf-8"))["kommuner"]}
    med_data = {k["kommunenr"]: k for k in kommuner}
    uten, senere, farget = [], [], []
    for k in kart["kommuner"]:
        navn = html.escape(k["navn"])
        slug = med_data[k["kommunenr"]]["slug"] if k["kommunenr"] in med_data else None
        if slug in begrensede:
            (senere if k["kommunenr"] in kandidater else uten).append(
                f'<path d="{k["d"]}"><title>{navn}{": kommer snart" if k["kommunenr"] in kandidater else ""}</title></path>')
        if slug:
            # Navnet midt i kommunen: snittet av hjørnene er godt nok her.
            pkt = [tuple(map(float, xy.split(","))) for xy in re.findall(r"[\d.]+,[\d.]+", k["d"])]
            x, y = (sum(v) / len(pkt) for v in zip(*pkt))
            skjult = f' data-begrenset="{slug}" hidden' if slug in begrensede else ""
            tittel = f"{navn}: begrenset innsyn" if slug in begrensede else navn
            farget.append(f'<a href="{slug}/" aria-label="{tittel}"{skjult}><path d="{k["d"]}">'
                          f'<title>{tittel}</title></path>'
                          f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="middle" '
                          f'dominant-baseline="middle">{navn}</text></a>')
        elif k["kommunenr"] in kandidater:
            senere.append(f'<path d="{k["d"]}"><title>{navn}: kommer snart</title></path>')
        else:
            uten.append(f'<path d="{k["d"]}"><title>{navn}</title></path>')
    forklaring = ('<figcaption class="kart-forklaring liten muted">'
                  '<span><i class="kart-merke med"></i>Kan velges</span>'
                  '<span><i class="kart-merke senere"></i>Kommer snart</span>'
                  '</figcaption>') if senere else ""
    return (f'<svg class="kart" viewBox="0 0 {kart["bredde"]} {kart["hoyde"]}" role="group" '
            'aria-label="Kart over kommunene i Trøndelag. Kommunene med data er farget og '
            'kan velges. Kommunene i grått kommer snart.">'
            f'<g class="kart-uten">{"".join(uten)}</g>'
            f'<g class="kart-senere">{"".join(senere)}</g>'
            f'<g class="kart-med">{"".join(farget)}</g></svg>{forklaring}')


def periode(st: dict) -> str:
    """«i 2026» med ett år, «siden 2026» med flere (status.json)."""
    aarene = st.get("aarene") or [st["ar"]]
    return f"siden {aarene[0]}" if len(aarene) > 1 else f"i {st['ar']}"


def _kommunekort(kommuner: list[tuple[dict, dict]], foran: str = "") -> str:
    """Listen over kommunene som HTML, så den virker uten skript. En kommune
    med begrenset innsyn er skjult til konto.js finner at kontoen har tilgang."""
    def linje(st: dict) -> str:
        if st.get("begrenset"):
            return f'<span class="liten laas">{LAAS}Begrenset innsyn</span>'
        return f'<span class="liten muted">Data hentet {_dato(_hentet(st))}</span>'
    def skjult(k: dict, st: dict) -> str:
        return f' data-begrenset="{k["slug"]}" hidden' if st.get("begrenset") else ""
    return "\n".join(
        f'<li{skjult(k, st)}>'
        f'<a class="kommunekort" href="{foran}{k["slug"]}/">'
        f'<b>{html.escape(k["navn"])}</b>'
        f'<span>{st["saker"]} saker og {st["moter"]} møter {periode(st)}</span>'
        f'{linje(st)}'
        f'</a></li>'
        for k, st in kommuner)


def _forside(kommuner: list[tuple[dict, dict]]) -> None:
    """Kommunelys-forsiden på roten, med en lenke til hver kommune."""
    side = _fyll((MAL / "forside.html").read_text("utf-8"), {
        "merke": MERKE, "merke_ikon": _merke_ikon(), "konto": _konto(""), "v_stil": _v("stil.css"), "kommuner": _kommunekort(kommuner),
        "deling": _deling("", f"{MERKE}: et klarere blikk på vedtakene",
                          "Uoffisiell oversikt over politiske saker, møter og stemmegivning i kommunene, "
                          "laget av en innbygger for innbyggerne."),
        "kart": _kart([k for k, _ in kommuner],
                      frozenset(k["slug"] for k, st in kommuner if st.get("begrenset"))),
        "gamle_lenker": GAMLE_LENKER, "repo": REPO, "telling": _telling()})
    (UT / "index.html").write_text(side, encoding="utf-8")


def _om(kommuner: list[tuple[dict, dict]]) -> None:
    """Om-siden på roten, felles for alle kommunene."""
    side = _fyll((MAL / "om.html").read_text("utf-8"), {
        "merke": MERKE, "merke_ikon": _merke_ikon(), "konto": _konto("../"), "v_stil": _v("stil.css"),
        "repo": REPO, "epost": html.escape(KONTAKT_EPOST), "telling": _telling(),
        "deling": _deling("om/", f"Om {MERKE}",
                          f"Hva {MERKE} er, og hvordan det er laget: kilder, hva som gjøres med kode og hva KI "
                          "gjør, kvalitet, personvern og dekning. Uoffisiell og uavhengig."),
        # Navnene til kommunevalget i toppen (?kommune=). Ikke de med begrenset innsyn.
        "kommuner_json": json.dumps({k["slug"]: k["navn"] for k, st in kommuner if not st.get("begrenset")},
                                    ensure_ascii=False).replace("</", "<\\/")})
    (UT / "om").mkdir(exist_ok=True)
    (UT / "om" / "index.html").write_text(side, encoding="utf-8")
    # Bildet under «Hvem står bak» (ADR-018).
    shutil.copy(MAL / "karl-kristian-aurstad.jpg", UT / "om" / "karl-kristian-aurstad.jpg")


def _ikke_funnet(kommuner: list[tuple[dict, dict]]) -> None:
    """404.html på roten. GitHub Pages viser den for alle adresser som ikke finnes.

    Andre feil (500, 503) viser GitHub sine egne sider; de kan ikke byttes ut.
    Siden kan vises på hvilken som helst adresse, så alle lenker må være
    absolutte. Bygget stopper hvis en relativ lenke har sneket seg inn.
    """
    # Kommunene med begrenset innsyn er ikke med i forslagene.
    liste = json.dumps([{"slug": k["slug"], "navn": k["navn"]} for k, st in kommuner if not st.get("begrenset")],
                       ensure_ascii=False).replace("</", "<\\/")
    side = _fyll((MAL / "404.html").read_text("utf-8"), {
        "merke": MERKE, "merke_ikon": _merke_ikon(), "konto": _konto(BASE), "v_stil": _v("stil.css"), "base": BASE,
        "kommuner": _kommunekort(kommuner, BASE), "kommuner_json": liste,
        "gamle_lenker": GAMLE_LENKER, "repo": REPO, "meld": MELD_FEIL,
        "telling": _telling()})
    relative = sorted({a for a in re.findall(r'(?:href|src)="([^"]*)"', side)
                       if not a.startswith(("/", "#", "https://", "http://localhost", "mailto:"))})
    if relative:
        raise SystemExit(f"404.html har relative lenker, som peker feil der siden vises: {relative}")
    (UT / "404.html").write_text(side, encoding="utf-8")


def _robots_og_sitemap(kommuner: list[tuple[dict, dict]]) -> None:
    """robots.txt og sitemap.xml på roten.

    Alle robotene er velkomne, også de som henter sider til språkmodeller:
    målet er at sakene blir funnet. Kartet over sidene har bare det som er
    åpent for alle. Kommunene med begrenset innsyn er ikke med (ADR-024); de
    har noindex, og robotene må kunne lese siden for å se det.
    """
    aapne = [(k, st) for k, st in kommuner if not st.get("begrenset")]
    sist = max(_hentet(st) for _, st in kommuner).isoformat()
    sider = [("", sist), ("om/", sist)] + [(f'{k["slug"]}/', _hentet(st).isoformat()) for k, st in aapne]
    (UT / "robots.txt").write_text(
        f"# {MERKE} er åpent for søkemotorer og språkmodeller.\n"
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {_url('sitemap.xml')}\n", encoding="utf-8")
    (UT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(_url(sti))}</loc><lastmod>{dato}</lastmod></url>\n"
                  for sti, dato in sider)
        + "</urlset>\n", encoding="utf-8")


def kjor_kommune(aar: int, begrenset: bool = False) -> tuple[dict, dict]:
    """nettsted/<slug>/ for kommunen bygget gjelder. Rører ikke de andre kommunene.

    Med begrenset innsyn (ADR-024) får nettsted/<slug>/ bare siden og
    status.json. Dataene (data.json og detaljer-<år>.json) skrives til
    nettsted-skjermet/<slug>/, som kjor.alle lagrer i databasen.
    """
    kommune = _kommune()
    # Alle årene fra kommunens «fra_aar»: en sak kan gå over flere år (ADR-022).
    aarene = lager_kommune.aarene(aar)
    saker = lager_kommune.alle_aar(lager_saker.les, aar)
    # Utvalg som ikke er politiske, for eksempel et testutvalg i portalen
    # («skjul_utvalg» i kommuner/<slug>.json), vises ikke.
    skjul = set(kommune.get("skjul_utvalg", []))
    moter = [m for m in lager_kommune.alle_aar(lager_saker.les_moter, aar) if m["utvalg"] not in skjul]
    analyser = lager_analyse.alle()

    # Kommunen bygges på nytt, så ingenting fra et tidligere bygg blir liggende.
    ut = UT / kommune["slug"]
    shutil.rmtree(ut, ignore_errors=True)
    skjermet = SKJERMET / kommune["slug"]
    shutil.rmtree(skjermet, ignore_errors=True)
    if begrenset:
        ut.mkdir(parents=True, exist_ok=True)
        skjermet.mkdir(parents=True, exist_ok=True)
    else:
        (ut / "data").mkdir(parents=True, exist_ok=True)

    meldinger = _meldinger()
    redigert = lager_avvik.sammendrag_redigeringer()
    sammendrag, holdt_sammendrag = _sammendrag(saker, analyser, meldinger, redigert)
    # Det som publiseres i data/, med teksten prosjektadmin har redigert (ADR-025).
    vist_analyse = {sid: {**a, **redigert[sid], "redigert": redigert[sid]["dato"]}
                    if sid in redigert else a for sid, a in analyser.items()}
    vedtak = {b["behandling_id"]: b.get("vedtak")
              for b in lager_kommune.alle_aar(lager_voteringer.les, aar)}
    nivaa = _nivaa()
    op_mote, op_steg, debatt, holdt_debatt = _opptak(aar, saker, meldinger)
    S = _s(aarene, saker, moter, sammendrag, kommune, vedtak, nivaa["oppmote"], (op_mote, op_steg, debatt))
    for c in S["cases"]:
        if c["id"] in meldinger["merk"]:
            c["merk"] = meldinger["merk"][c["id"]]
    # Det som er publisert i hver sak, til «Følg saken» (ADR-027). Før detaljene
    # skilles ut; kjor.alle lagrer det når kommunen publiseres.
    varsel_tilstand.skriv(kommune["slug"], S["cases"], kommune.get("utvalg_kort"))
    if nivaa["voteringer"]:
        VOT, holdt = _vot(aar, saker, moter, meldinger)
    else:
        # Stemmene kan ikke leses sikkert ennå; malen sier det (VOT.ikke_dekket).
        VOT, holdt = {"moter": [], "parti": {}, "ikke_dekket": True}, 0

    # Data ved siden av sidene, for andre som vil bruke dem, ett sett per år.
    # En sak står i året den begynte; et møte og voteringene i møtets år.
    # Med begrenset innsyn publiseres ingen av dem.
    filer = ["status.json", "index.html"] + ([] if begrenset else ["data/data.js"])
    for a in [] if begrenset else aarene:
        arets = lager_saker.les(a, [])
        arets_id = {s["sak_id"] for s in arets}
        arets_mote_liste = [m for m in lager_saker.les_moter(a, []) if m["utvalg"] not in skjul]
        arets_moter = {m["mote_id"] for m in arets_mote_liste}
        innhold = {
            "saker": arets,
            "moter": arets_mote_liste,
            # Bare sammendragene som vises; de som holdes tilbake, publiseres
            # ikke her heller.
            "analyser": {k: v for k, v in vist_analyse.items() if k in arets_id and k in sammendrag},
            "voteringer": VOT if len(aarene) == 1 else
            {**VOT, "moter": [m for m in VOT["moter"] if m["id"] in arets_moter]},
            # Søkeindeks bygget på forhånd, kjører i nettleseren. Klarspråkstittelen
            # bare fra sammendragene som vises.
            "indeks": [{
                "id": s["sak_id"],
                "t": sammendrag.get(s["sak_id"], {}).get("tk") or s["tittel"],
                "o": s["tittel"],
                "s": s["status"],
                "g": [steg["utvalg"] for steg in s["saksgang"]],
            } for s in arets if not s["formalia"]],
        }
        for navn in ("saker", "moter", "analyser", "voteringer", "indeks"):
            fil = f"data/{navn}-{a}.json"
            (ut / fil).write_text(
                json.dumps(innhold[navn], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            filer.append(fil)

    # Detaljene skilles ut etter at filene over har fått hele teksten.
    sakens_aar = {s["sak_id"]: a for a in aarene for s in lager_saker.les(a, [])}
    if len(aarene) > 1:
        for c in S["cases"]:
            c["y"] = sakens_aar[c["id"]]
    viktige = "" if begrenset else _viktige(S)
    detaljer = _del_detaljer(S, VOT, sakens_aar)
    S["detaljer"] = {}
    for a, d in sorted(detaljer.items()):
        tekst = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        fil = f"detaljer-{a}.json"
        if begrenset:
            (skjermet / fil).write_text(tekst, encoding="utf-8")
        else:
            (ut / "data" / fil).write_text(tekst, encoding="utf-8")
            filer.append(f"data/{fil}")
        # ?v= gjør at nettleseren henter filen på nytt når den er endret.
        S["detaljer"][str(a)] = f"{fil}?v={hashlib.sha256(tekst.encode()).hexdigest()[:10]}"
    if begrenset:
        (skjermet / "data.json").write_text(
            json.dumps({"S": S, "VOT": VOT}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        (ut / "data" / "data.js").write_text(
            "const S=" + json.dumps(S, ensure_ascii=False, separators=(",", ":")) + ";\n"
            "const VOT=" + json.dumps(VOT, ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8")
    _kommuneside(kommune, ut, begrenset, viktige)

    status = {
        "bygget": dt.datetime.now().isoformat(timespec="seconds"),
        "ar": aar,
        "aarene": aarene,
        "saker": len(saker),
        "moter": len(moter),
        "analyser": len(analyser),
        "voteringer": sum(len(s["v"]) for m in VOT["moter"] for s in m["saker"]),
        "voteringer_holdt_tilbake": holdt,
        "sammendrag_publisert": len(sammendrag),
        "sammendrag_holdt_tilbake": holdt_sammendrag,
        # Opptakene og debatten fra dem (ADR-026).
        "opptak": len(op_mote),
        "debatt_publisert": len(debatt),
        "debatt_holdt_tilbake": holdt_debatt,
        "meldinger_apne": lager_avvik.apne_meldinger(),
        # Hvor mye av protokollene regelsettet leser (tolk/dekning.py).
        "dekning": {k: v for k, v in dekning.samlet(aar).items() if k != "mistenkte"},
        # Filene kjor.alle henter når kommunen beholder forrige versjon.
        "filer": filer,
        # Står på forsiden, men innholdet krever innlogging (ADR-024).
        "begrenset": begrenset,
        "nivaa": nivaa,
        # Fase 2: faktisk forbruk, for å måle kostnaden.
        "tokens": {k: sum((a.get("tokens") or {}).get(k, 0) for a in analyser.values())
                   for k in ("inn", "ut")},
    }
    (ut / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"nettsted/{kommune['slug']}/ bygget: {len(saker)} saker, {len(moter)} møter, "
          f"{len(sammendrag)} av {len(analyser)} sammendrag publisert, "
          f"{len(op_mote)} møter med opptak, {len(debatt)} debatter, "
          f"{holdt} voteringer holdt tilbake")
    return kommune, status


def _bygde() -> list[tuple[dict, dict]]:
    """Kommunene som ligger i nettsted/, med status.json, sortert etter navn."""
    ut = []
    for fil in sorted(UT.glob("*/status.json")):
        ut.append((_kommune(fil.parent.name), json.loads(fil.read_text("utf-8"))))
    return sorted(ut, key=lambda ks: ks[0]["navn"])


def kjor_felles(drift_fil: str | None = None, utfall: dict[str, str] | None = None) -> None:
    """Det som er felles for kommunene: forsiden, /om/, /konto/, 404-siden,
    stil, skript og skrift, og driftssiden. Bygges fra kommunene i nettsted/."""
    kommuner = _bygde()
    if not kommuner:
        raise SystemExit("fant ingen kommuner i nettsted/; bygg kommunene først")
    for navn in FELLES:
        shutil.copy(MAL / navn, UT / navn)
    shutil.rmtree(UT / "fonter", ignore_errors=True)
    shutil.copytree(MAL / "fonter", UT / "fonter")
    # Portalen sender hit etter innlogging og utlogging (konto.js).
    (UT / "konto").mkdir(exist_ok=True)
    shutil.copy(MAL / "konto.html", UT / "konto" / "index.html")
    _forside(kommuner)
    _om(kommuner)
    _ikke_funnet(kommuner)
    _robots_og_sitemap(kommuner)

    driftsside(kommuner, drift_fil, utfall)


def driftsside(kommuner: list[tuple[dict, dict]], drift_fil: str | None = None,
               utfall: dict[str, str] | None = None) -> None:
    """Driftssiden publiseres ikke. Den lagres i databasen og vises i portalen
    for prosjektadmin (ADR-020); --drift-fil STI lagrer den også lokalt.
    Detaljene gjelder kommunen prosessen gjelder; tabellen «Kommunene» alle.

    --bare-drift lager bare den, fra kommunene i nettsted/, etter at varslene
    er sendt (ADR-027), så telleren viser denne kjøringen."""
    kommune = _kommune()
    status = next((s for k, s in kommuner if k["slug"] == kommune["slug"]), None)
    if status is None:
        print(f"advarsel: {kommune['slug']} er ikke bygget; driftssiden lages ikke")
        return
    utfall = utfall or {}
    side = drift.side(
        (MAL / "drift.html").read_text("utf-8"), _fyll, status, kommune,
        collections.Counter(a["status"] for a in alle_avvik(status["ar"])), lager_analyse.alle(),
        MERKE, REPO, GOATCOUNTER, f"{NETTSTED}{BASE}",
        drift.kommuner([(k, s, utfall.get(k["slug"], "ny")) for k, s in kommuner]),
        lager_opptak.debatter())
    lager_drift.lagre_side(side)
    if drift_fil:
        Path(drift_fil).write_text(side, encoding="utf-8")


def kjor(aar: int, drift_fil: str | None = None) -> None:
    """Kommunen bygget gjelder, og det felles. Som før kommunene ble flere."""
    kjor_kommune(aar)
    kjor_felles(drift_fil)


def main() -> None:
    """python -m bygg.bygg_nettsted [år] [--kommune SLUG] [--uten-felles [--begrenset] | --felles | --bare-drift]
    [--drift-fil STI] [--utfall STI]

    Uten valg bygges kommunen og det felles. --uten-felles bygger bare
    nettsted/<slug>/; --felles bare det felles, fra kommunene i nettsted/.
    --utfall er en JSON-fil {slug: utfall} fra kjor.alle til driftssiden.
    --begrenset bygger kommunen med begrenset innsyn (ADR-024): dataene til
    nettsted-skjermet/<slug>/, ikke til nettstedet.
    --bare-drift lager bare driftssiden på nytt, etter varslene (ADR-027).
    """
    argv = lager_kommune.fra_argv(sys.argv[1:])
    verdier = {n: argv[argv.index(n) + 1] for n in ("--drift-fil", "--utfall") if n in argv}
    args = [a for a in argv if not a.startswith("--") and a not in verdier.values()]
    aar = int(args[0]) if args else dt.date.today().year
    drift_fil = verdier.get("--drift-fil")
    utfall_fil = Path(verdier["--utfall"]) if "--utfall" in verdier else None
    if "--bare-drift" in argv:
        kommuner = _bygde()
        if not kommuner:
            raise SystemExit("fant ingen kommuner i nettsted/; bygg kommunene først")
        driftsside(kommuner, drift_fil,
                   json.loads(utfall_fil.read_text("utf-8")) if utfall_fil and utfall_fil.exists() else None)
    elif "--felles" in argv:
        utfall = json.loads(Path(verdier["--utfall"]).read_text("utf-8")) if "--utfall" in verdier else None
        kjor_felles(drift_fil, utfall)
    elif "--uten-felles" in argv:
        kjor_kommune(aar, begrenset="--begrenset" in argv)
    else:
        kjor(aar, drift_fil)


if __name__ == "__main__":
    main()
