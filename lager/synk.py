"""Speiler data/ inn i databasen (fase 3 i flyttingen til Postgres).

Filene er fortsatt kilden. Denne gjør databasen lik dem for ett år: nye og
endrede rader skrives, rader som er borte, slettes (rådata, analyser og
vurderinger får nye versjoner i stedet). Mot en tom database er det det
samme som en import.

Alt skjer i én transaksjon. Databasen kontrollerer reglene når den
avsluttes (stemmetall, skjerming, kommune på hver rad), så data som bryter
dem, stopper speilingen med en melding om hva som er galt, og ingenting
skrives.

    python -m lager.synk 2026
    python -m lager.synk --konfig    # bare filene som vedlikeholdes for hånd

--konfig speiler vurderingene, de tillatte navnene og partilenkene. De er
filer i git også når resten ligger i databasen, og speiles ved hver kjøring.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from lager import analyse, avvik, db, fra_databasen, konfig, oppmote, pg_skriv, raa, saker, tekst, verv, voteringer
from lager import drift as lager_drift
from tolk.navn import VARIANTER

KOMMUNE = os.environ.get("KOMMUNELYS_KOMMUNE", "steinkjer")


def _kjoring_id() -> tuple[str, str]:
    if os.environ.get("GITHUB_RUN_ID"):
        forsok = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        return f"synk-{os.environ['GITHUB_RUN_ID']}-{forsok}", "actions"
    return f"synk-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}", "lokal"


def _konfig(c, k: int) -> dict:
    return {"nye_vurderinger": pg_skriv.vurderinger(c, k, avvik.vurderinger()),
            "tillatt_navn": pg_skriv.tillatte_navn(c, k, konfig.tillatte_navn()),
            "partilenker": pg_skriv.partilenker(c, k, konfig.partisider())}


def kjor_konfig() -> dict:
    """Bare filene som vedlikeholdes for hånd. Brukes når resten skrives
    direkte til databasen (KOMMUNELYS_LAGER=pg)."""
    return pg_skriv.i_transaksjon(_konfig)


def kjor(aar: int) -> dict:
    if fra_databasen():
        raise SystemExit("speilingen leser fra filene; kjør uten KOMMUNELYS_LAGER=pg")
    kjoring_id, kilde = _kjoring_id()
    moteliste = raa.moteliste(aar) or []
    raa_moter = raa.moter(aar) or []

    with db.transaksjon(kjoring_id) as c:
        rad = c.execute("select kommune_id from kjerne.kommune where slug = %s", (KOMMUNE,)).fetchone()
        if not rad:
            raise SystemExit(f"fant ikke kommunen {KOMMUNE} i databasen")
        k = rad[0]
        c.execute("insert into drift.kjoring (kjoring_id, kilde, git_sha) values (%s, %s, %s)",
                  (kjoring_id, kilde, os.environ.get("GITHUB_SHA")))

        ut: dict = {"kjoring": kjoring_id}
        ut["raa_svar"] = pg_skriv.raa(c, k, aar, moteliste, raa_moter, raa.medlemslister(), kjoring_id)
        personer = pg_skriv.Personer(c, k)
        ut.update(pg_skriv.utvalg(c, k, aar, verv.les_utvalg(aar), konfig.partisider()))
        ut.update(pg_skriv.verv(c, k, aar, personer, verv.les(aar, [])))
        ut["navnevariant"] = pg_skriv.navnevarianter(c, k, personer, VARIANTER)
        ut.update(pg_skriv.moter(c, k, aar, saker.les_moter(aar), raa_moter, moteliste))
        ut.update(pg_skriv.saker(c, k, aar, saker.les(aar)))
        ut["dokument_tekst"] = pg_skriv.tekster(c, k, tekst.les)
        ut.update(pg_skriv.voteringer(c, k, aar, personer, voteringer.les(aar, [])))
        ut.update(pg_skriv.oppmote(c, k, aar, personer, oppmote.les(aar, [])))
        ut.update(pg_skriv.avvik(c, k, aar, avvik.les(aar, [])))
        ut.update(_konfig(c, k))
        ut["forrige_telling"] = pg_skriv.forrige_telling(c, k, konfig.forrige_telling())
        ut["nye_analyser"] = pg_skriv.analyser(c, k, analyse.alle(), kjoring_id)
        ut["kjoringer"] = pg_skriv.kjoringer(c, k, lager_drift.kjoringer())
        ut["personer"] = len(personer.id)

        c.execute("update drift.kjoring set slutt = now() where kjoring_id = %s", (kjoring_id,))
        ut["endringer_i_loggen"] = c.execute(
            "select count(*) from drift.endringslogg where kjoring_id = %s", (kjoring_id,)).fetchone()[0]
    return ut


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--konfig" in sys.argv:
        print(json.dumps(kjor_konfig(), ensure_ascii=False, indent=1, default=str))
        return
    aar = int(args[0]) if args else dt.date.today().year
    print(json.dumps(kjor(aar), ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
