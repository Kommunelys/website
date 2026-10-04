"""Kontrollerer at databasen gir nøyaktig det samme som filene.

Hver les-funksjon i lager/ kalles to ganger, med KOMMUNELYS_LAGER=json og
=pg, og svarene sammenlignes som JSON, tegn for tegn og i samme rekkefølge.
Rekkefølgen betyr noe: den havner i nettstedets data.js.

Rådataene sammenlignes uten hensyn til rekkefølgen på nøklene (Postgres
lagrer jsonb med egen nøkkelrekkefølge); innholdet må være det samme.

    python -m lager.paritet 2026
    python -m lager.paritet 2026 --lagre   # og lagre resultatet til driftssiden
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from lager import analyse, avvik, konfig, oppmote, pg, raa, saker, tekst, verv, voteringer
from lager import drift as lager_drift


def _med(backend: str, funksjon, *args):
    gammel = os.environ.get("KOMMUNELYS_LAGER")
    os.environ["KOMMUNELYS_LAGER"] = backend
    try:
        return funksjon(*args)
    finally:
        if gammel is None:
            os.environ.pop("KOMMUNELYS_LAGER")
        else:
            os.environ["KOMMUNELYS_LAGER"] = gammel


def _forste_forskjell(a, b, sti: str = "") -> str:
    """Hvor to verdier først skiller seg, for en lesbar melding."""
    if type(a) is not type(b):
        return f"{sti or '/'}: {type(a).__name__} mot {type(b).__name__}"
    if isinstance(a, dict):
        if list(a) != list(b):
            return f"{sti or '/'}: nøkler {list(a)[:8]} mot {list(b)[:8]}"
        for k in a:
            if a[k] != b[k] or json.dumps(a[k], ensure_ascii=False) != json.dumps(b[k], ensure_ascii=False):
                return _forste_forskjell(a[k], b[k], f"{sti}/{k}")
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{sti or '/'}: {len(a)} mot {len(b)} elementer"
        for i, (x, y) in enumerate(zip(a, b)):
            if json.dumps(x, ensure_ascii=False) != json.dumps(y, ensure_ascii=False):
                return _forste_forskjell(x, y, f"{sti}[{i}]")
    return f"{sti or '/'}: {str(a)[:80]!r} mot {str(b)[:80]!r}"


def _lik(fil, db, uten_rekkefolge: bool = False) -> tuple[bool, str]:
    def tekst_(v):
        return json.dumps(v, ensure_ascii=False, sort_keys=uten_rekkefolge)
    if tekst_(fil) == tekst_(db):
        return True, ""
    if uten_rekkefolge:
        fil, db = json.loads(tekst_(fil)), json.loads(tekst_(db))
    return False, _forste_forskjell(fil, db)


def kjor(aar: int, lagre: bool = False) -> int:
    kontroller = [
        ("saker", saker.les, (aar,), False),
        ("møter", saker.les_moter, (aar,), False),
        ("voteringer", voteringer.les, (aar,), False),
        ("oppmøte", oppmote.les, (aar,), False),
        ("verv", verv.les, (aar,), False),
        ("verv, alle år", verv.alle_aar, (), False),
        ("utvalg", verv.les_utvalg, (aar,), False),
        ("avvik", avvik.les, (aar,), False),
        ("analyser", analyse.alle, (), False),
        ("kjøreloggen", lager_drift.kjoringer, (), False),
        ("forrige telling", konfig.forrige_telling, (), False),
        ("rådata: møteliste", raa.moteliste, (aar,), True),
        ("rådata: møter", raa.moter, (aar,), True),
        ("rådata: medlemslister", raa.medlemslister, (), True),
    ]
    resultat: list[tuple[str, bool, str]] = []

    def notert(navn: str, ok: bool, hvor: str) -> None:
        print(f"{'ok  ' if ok else 'ULIK'} {navn}{'' if ok else '  ' + hvor}")
        resultat.append((navn, ok, hvor))

    for navn, funksjon, args, uten_rekkefolge in kontroller:
        fil, db = _med("json", funksjon, *args), _med("pg", funksjon, *args)
        ok, hvor = _lik(fil, db, uten_rekkefolge)
        antall = len(fil) if hasattr(fil, "__len__") else ""
        notert(f"{navn} ({antall})", ok, hvor)

    # Filene som vedlikeholdes for hånd, leses alltid fra filen. Her
    # sammenlignes de med kopien i databasen.
    for navn, fra_fil, fra_db in (("vurderinger", avvik.vurderinger, pg.vurderinger),
                                  ("tillatte navn", konfig.tillatte_navn, pg.tillatte_navn)):
        notert(navn, *_lik(fra_fil(), fra_db()))

    # Partisidene: merknaden i filen er en kommentar og lagres ikke.
    fil = {k: v for k, v in _med("json", konfig.partisider).items() if k != "merknad"}
    notert("partisider", *_lik(fil, pg.partisider()))

    # Teksten: hvert dokument sakene og møtene viser til.
    oppslag = [("mote", m["mote_id"]) for m in saker.les_moter(aar)]
    for s in saker.les(aar):
        if s["saksframlegg"]:
            oppslag.append(("dokument", s["saksframlegg"]["dokument_id"]))
        oppslag += [("dokument", d["dokument_id"]) for d in s["vedlegg"]]
        oppslag += [("behandling", st["behandling_id"]) for st in s["saksgang"]]
    ulike = [o for o in oppslag if _med("json", tekst.les, *o) != _med("pg", tekst.les, *o)]
    funnet = sum(1 for o in oppslag if _med("json", tekst.les, *o) is not None)
    notert(f"tekst ({funnet} av {len(oppslag)} dokumenter har tekst)", not ulike, f"ulike: {ulike[:5]}")

    feil = sum(1 for _, ok, _ in resultat if not ok)
    print()
    print("alt likt" if not feil else f"{feil} ulike")
    if lagre:
        _lagre(aar, resultat)
    return 1 if feil else 0


def _lagre(aar: int, resultat: list[tuple[str, bool, str]]) -> None:
    """Resultatet i drift.paritet, til driftssiden."""
    from psycopg.types.json import Jsonb  # noqa: PLC0415

    from lager import kjoring_id, pg_skriv  # noqa: PLC0415

    ulike = [{"navn": navn, "hvor": hvor} for navn, ok, hvor in resultat if not ok]
    pg_skriv.i_transaksjon(lambda c, k: c.execute(
        "insert into drift.paritet (kommune_id, aar, kjoring_id, likt, kontroller, ulike) "
        "values (%s, %s, %s, %s, %s, %s)", (k, aar, kjoring_id(), not ulike, len(resultat), Jsonb(ulike))))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raise SystemExit(kjor(int(args[0]) if args else dt.date.today().year, lagre="--lagre" in sys.argv))


if __name__ == "__main__":
    main()
