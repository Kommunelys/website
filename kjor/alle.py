"""Henter, analyserer og bygger alle kommunene, én om gangen (ADR-021).

Kommunene kjøres etter tur, aldri samtidig, så takten mot portalen gjelder
samlet for verten (ADR-007). Hvert trinn er en egen prosess med
KOMMUNELYS_KOMMUNE satt, så ingenting som er husket fra én kommune, brukes for
en annen. Feiler en kommune, fortsetter kjøringen med neste. Det som feilet,
står i sammendraget for kjøringen i Actions. Feilet noe i hentingen, gjør siste
jobb kjøringen rød etter at de andre kommunene er publisert; feilet noe i
analysen, blir analysejobben rød.

    python -m kjor.alle hent [år] [--alt]
    python -m kjor.alle analyser [år] [--maks 25] [--minutter 150]
    python -m kjor.alle bygg [år] [--hopp-over slug,slug]

Kommunene er de med status «intern», «begrenset» eller «publisert» i kjerne.kommune
(lager.kommune.aktive). Året er i år når det ikke er oppgitt. Hver kommune
hentes og tolkes for alle årene fra «fra_aar» i kommuner/<slug>.json, fordi en
sak kan gå over flere år (ADR-022). Et eldre år koster ett kall mot portalen
(møtelisten) pluss det som er endret.

bygg: kontrollerer og bygger hver kommune. En publisert kommune som stopper i
kontrollene, beholder versjonen som er publisert nå (hentet fra nettstedet).
En intern kommune legges i nettsted-intern/, ikke i nettsted/. En kommune med
begrenset innsyn får siden og status.json i nettsted/, men dataene lagres i
databasen og hentes med innloggingen (bygg.skjerm, ADR-024). Til slutt
bygges det felles. Mangler en publisert kommune helt, stopper bygget, så
nettstedet aldri publiseres uten den.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from analyser.claude import STOPP
from hent.portal import AVVIST
from lager import kommune as lager_kommune

ROT = Path(__file__).resolve().parent.parent
UT = ROT / "nettsted"
INTERN = ROT / "nettsted-intern"
# Saker med debatt som analyseres per kommune og kjøring (analyser.analyser_debatt).
MAKS_DEBATT = 15
# Det som feilet uten å stoppe de andre kommunene, én linje per feil (_meld).
FEIL: list[str] = []


def _kode(slug: str, *kommando: str) -> int:
    """Ett trinn for én kommune, som egen prosess. Gir utgangskoden."""
    print(f"\n== {slug}: {' '.join(kommando)}", flush=True)
    return subprocess.run([sys.executable, "-m", *kommando], cwd=ROT,
                          env=os.environ | {"KOMMUNELYS_KOMMUNE": slug}).returncode


def _kjor(slug: str, *kommando: str) -> bool:
    """Som _kode, men sant når det gikk bra."""
    return _kode(slug, *kommando) == 0


def _hent(slug: str, *kommando: str) -> bool:
    """Som _kjor, men det som feilet, står i FEIL. Avviser innsynsportalen oss,
    sier det det (hent.portal.Avvist)."""
    kode = _kode(slug, *kommando)
    if kode == AVVIST:
        FEIL.append(f"{slug}: innsynsportalen avviser oss, og vi kan være blokkert (eller adressen "
                    "er feil; svaret står i loggen). Kommunen beholder forrige versjon på nettstedet, "
                    "og neste kjøring prøver igjen.")
    elif kode:
        FEIL.append(f"{slug}: {' '.join(kommando)} feilet. Kommunen beholder forrige versjon på nettstedet.")
    return kode == 0


def _analyse(slug: str, *kommando: str) -> bool:
    """Som _kjor, men avviser Claude nøkkelen eller kontoen, stopper analysen
    for alle kommunene, og jobben blir rød (analyser.claude.Stopp)."""
    kode = _kode(slug, *kommando)
    if kode == STOPP:
        FEIL.append("stopper: Claude avviser nøkkelen, eller kontoen er tom for kreditt. "
                    "Ingen saker eller debatter blir analysert før det er rettet.")
        raise SystemExit(1)
    return kode == 0


def _aar(args: list[str]) -> int:
    return int(args[0]) if args else dt.date.today().year


def hent(aar: int, alt: bool) -> dict[str, bool]:
    utfall = {}
    for slug, _ in lager_kommune.aktive():
        aarene = [str(a) for a in lager_kommune.aarene(aar, slug)]
        ok = True
        for a in aarene:
            ok = ok and _hent(slug, "hent.hent_moter", a, *(["--alt"] if alt else []))
        ok = ok and _hent(slug, "hent.hent_medlemmer", str(aar))
        # Sakene bygges én gang, for alle årene: en sak kan gå over flere år.
        ok = ok and _hent(slug, "tolk.bygg_saker", str(aar))
        for a in aarene:
            ok = ok and _hent(slug, "hent.hent_dokumenter", a) and _hent(slug, "tolk.bygg_voteringer", a)
        # Oppmøtet og avvikene kontrollerer stemmene fra alle årene til og med året.
        for a in aarene:
            for trinn in ("tolk.bygg_oppmote", "tolk.bygg_verv", "tolk.bygg_avvik"):
                ok = ok and _hent(slug, trinn, a)
        # Opptakene av møtene (ADR-026), når kommunen har dem. En annen vert enn
        # portalen. Feiler det, beholder kommunen lenkene fra forrige kjøring.
        if ok and lager_kommune.oppsett(slug).get("opptak") and not _kjor(slug, "hent.hent_opptak", str(aar)):
            FEIL.append(f"{slug}: opptakene ble ikke hentet; lenkene er som ved forrige kjøring")
        utfall[slug] = ok
    return utfall


def analyser(aar: int, maks: int, minutter: float) -> dict[str, bool]:
    """Deler antallet saker og tiden likt; det en kommune ikke bruker, går videre.

    Analysen går gjennom alle årene til og med `aar` med én kvote per kommune.
    """
    kommuner = lager_kommune.aktive()
    slutt = time.monotonic() + minutter * 60
    utfall = {}
    for i, (slug, _) in enumerate(kommuner):
        igjen = len(kommuner) - i
        min_her = max(1.0, (slutt - time.monotonic()) / 60 / igjen)
        utfall[slug] = _analyse(slug, "analyser.analyser_saker", str(aar),
                                "--maks", str(math.ceil(maks / len(kommuner))), "--minutter", f"{min_her:.0f}")
        if not utfall[slug]:
            FEIL.append(f"{slug}: AI-analysen av sakene feilet")
        # Debatten fra opptakene (ADR-026). Sakene går først; debatten får
        # sin egen kvote og stopper ikke kommunen om den feiler. En debatt som
        # holdes tilbake av kontrollen, er ikke en feil.
        if lager_kommune.oppsett(slug).get("opptak") and not _analyse(
                slug, "analyser.analyser_debatt", str(aar), "--maks", str(MAKS_DEBATT)):
            FEIL.append(f"{slug}: debatten ble ikke analysert")
    return utfall


def _forrige(slug: str) -> bool:
    """Den publiserte versjonen av kommunen, fra nettstedet, til nettsted/<slug>/."""
    from bygg.bygg_nettsted import BASE, NETTSTED  # noqa: PLC0415

    rot = f"{NETTSTED}{BASE}{slug}/"
    ut = UT / slug
    shutil.rmtree(ut, ignore_errors=True)
    try:
        status = json.loads(urllib.request.urlopen(rot + "status.json", timeout=60).read())
        for f in status["filer"]:
            (ut / f).parent.mkdir(parents=True, exist_ok=True)
            (ut / f).write_bytes(urllib.request.urlopen(rot + f, timeout=60).read())
    except Exception as e:  # noqa: BLE001
        print(f"fikk ikke hentet den publiserte versjonen av {slug}: {e}")
        shutil.rmtree(ut, ignore_errors=True)
        return False
    return True


def bygg(aar: int, hopp_over: set[str]) -> int:
    """hopp_over: kommuner der innhentingen feilet. De beholder forrige versjon."""
    shutil.rmtree(INTERN, ignore_errors=True)
    utfall: dict[str, str] = {}
    mangler = []
    aktive = lager_kommune.aktive()
    for slug, status in aktive:
        begrenset = ["--begrenset"] if status == "begrenset" else []
        ok = (slug not in hopp_over
              and all(_kjor(slug, "tester.kontroller", str(a)) for a in lager_kommune.aarene(aar, slug))
              and _kjor(slug, "bygg.bygg_nettsted", str(aar), "--uten-felles", *begrenset))
        if begrenset and ok:
            # Dataene til databasen, ikke til nettstedet (ADR-024). Siden og
            # status.json publiseres som for de andre. Feiler det, beholdes
            # forrige versjon, både her og i databasen.
            ok = _kjor(slug, "bygg.skjerm")
        if ok and status != "intern":
            # Det som er publisert i sakene, til «Følg saken» (ADR-027). Bare
            # når kommunen faktisk publiseres, så varselet aldri går foran
            # nettstedet. Feiler det, varsles det neste gang.
            _kjor(slug, "varsel.tilstand")
        if status == "intern":
            if ok:
                INTERN.mkdir(exist_ok=True)
                shutil.move(UT / slug, INTERN / slug)
            utfall[slug] = "intern" if ok else "intern, feilet"
        elif ok:
            utfall[slug] = "ny, begrenset innsyn" if begrenset else "ny"
        elif _forrige(slug):
            utfall[slug] = "forrige versjon"
        else:
            mangler.append(slug)
    if mangler:
        print(f"\nstopper: {', '.join(mangler)} kunne verken bygges eller hentes fra nettstedet; publiserer ikke")
        return 1
    # En kommune som er publisert eller tatt ut, skal ikke ha data liggende i
    # databasen for begrenset innsyn.
    _kjor(lager_kommune.STANDARD, "bygg.skjerm", "--rydd",
          ",".join(s for s, st in aktive if st == "begrenset"))
    fil = ROT / "utfall.json"
    fil.write_text(json.dumps(utfall, ensure_ascii=False), encoding="utf-8")
    if not _kjor(lager_kommune.STANDARD, "bygg.bygg_nettsted", "--felles", "--utfall", str(fil)):
        return 1
    print("\n" + "\n".join(f"{s}: {u}" for s, u in utfall.items()))
    return 0


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("hent", "analyser", "bygg"):
        print(__doc__)
        raise SystemExit(2)
    hva, rest = argv[0], argv[1:]
    verdier = {n: rest[rest.index(n) + 1] for n in ("--maks", "--minutter", "--hopp-over") if n in rest}
    aar = _aar([a for a in rest if not a.startswith("--") and a not in verdier.values()])
    if hva == "bygg":
        raise SystemExit(bygg(aar, {s for s in verdier.get("--hopp-over", "").split(",") if s}))
    try:
        if hva == "hent":
            utfall = hent(aar, "--alt" in rest)
        else:
            utfall = analyser(aar, int(verdier.get("--maks", 25)), float(verdier.get("--minutter", 150)))
    finally:
        _meld("Hent og tolk" if hva == "hent" else "AI-analyse")
    print("\n" + "\n".join(f"{s}: {'ok' if ok else 'feilet'}" for s, ok in utfall.items()))
    if hva == "analyser":
        # Rød jobb, men bygget venter ikke på at analysen gikk bra (oppdater.yml).
        raise SystemExit(1 if FEIL else 0)
    # Til bygget: kommunene som feilet, beholder forrige versjon. Til siste jobb:
    # det som feilet, så kjøringen blir rød etter publiseringen.
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"feilet={','.join(s for s, ok in utfall.items() if not ok)}\n"
                    f"feil={' | '.join(FEIL)}\n")
    # Jobben feiler bare når ingen kommune gikk bra; de andre publiseres som vanlig.
    raise SystemExit(0 if any(utfall.values()) else 1)


def _meld(tittel: str) -> None:
    """Det som feilet, i loggen og i sammendraget for kjøringen i Actions."""
    if not FEIL:
        return
    print(f"\n{tittel}, dette feilet:\n" + "\n".join(FEIL), flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"### {tittel}: dette feilet\n\n" + "".join(f"- {x}\n" for x in FEIL) + "\n")


if __name__ == "__main__":
    main()
