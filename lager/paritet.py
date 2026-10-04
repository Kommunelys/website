"""Kontrollerer at databasen gir nøyaktig det samme som filene.

Hver les-funksjon i lager/ kalles to ganger, med KOMMUNELYS_LAGER=json og
=pg, og svarene sammenlignes som JSON, tegn for tegn og i samme rekkefølge.
Rekkefølgen betyr noe: den havner i nettstedets data.js.

Rådataene sammenlignes uten hensyn til rekkefølgen på nøklene (Postgres
lagrer jsonb med egen nøkkelrekkefølge); innholdet må være det samme.

    python -m lager.paritet 2026
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from lager import analyse, avvik, konfig, oppmote, raa, saker, tekst, verv, voteringer


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


def kjor(aar: int) -> int:
    kontroller = [
        ("saker", saker.les, (aar,), False),
        ("møter", saker.les_moter, (aar,), False),
        ("voteringer", voteringer.les, (aar,), False),
        ("oppmøte", oppmote.les, (aar,), False),
        ("verv", verv.les, (aar,), False),
        ("verv, alle år", verv.alle_aar, (), False),
        ("utvalg", verv.les_utvalg, (aar,), False),
        ("avvik", avvik.les, (aar,), False),
        ("vurderinger", avvik.vurderinger, (), False),
        ("analyser", analyse.alle, (), False),
        ("tillatte navn", konfig.tillatte_navn, (), False),
        ("rådata: møteliste", raa.moteliste, (aar,), True),
        ("rådata: møter", raa.moter, (aar,), True),
        ("rådata: medlemslister", raa.medlemslister, (), True),
    ]
    feil = 0
    for navn, funksjon, args, uten_rekkefolge in kontroller:
        fil, db = _med("json", funksjon, *args), _med("pg", funksjon, *args)
        ok, hvor = _lik(fil, db, uten_rekkefolge)
        antall = len(fil) if hasattr(fil, "__len__") else ""
        print(f"{'ok  ' if ok else 'ULIK'} {navn} ({antall}){'' if ok else '  ' + hvor}")
        feil += not ok

    # Partisidene: merknaden i filen er en kommentar og lagres ikke.
    fil = {k: v for k, v in _med("json", konfig.partisider).items() if k != "merknad"}
    ok, hvor = _lik(fil, _med("pg", konfig.partisider))
    print(f"{'ok  ' if ok else 'ULIK'} partisider{'' if ok else '  ' + hvor}")
    feil += not ok

    # Teksten: hvert dokument sakene og møtene viser til.
    oppslag = [("mote", m["mote_id"]) for m in saker.les_moter(aar)]
    for s in saker.les(aar):
        if s["saksframlegg"]:
            oppslag.append(("dokument", s["saksframlegg"]["dokument_id"]))
        oppslag += [("dokument", d["dokument_id"]) for d in s["vedlegg"]]
        oppslag += [("behandling", st["behandling_id"]) for st in s["saksgang"]]
    ulike = [o for o in oppslag if _med("json", tekst.les, *o) != _med("pg", tekst.les, *o)]
    funnet = sum(1 for o in oppslag if _med("json", tekst.les, *o) is not None)
    print(f"{'ok  ' if not ulike else 'ULIK'} tekst ({funnet} av {len(oppslag)} dokumenter har tekst)"
          + (f"  ulike: {ulike[:5]}" if ulike else ""))
    feil += bool(ulike)

    print(f"\n{'alt likt' if not feil else f'{feil} ulike'}")
    return 1 if feil else 0


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raise SystemExit(kjor(int(args[0]) if args else dt.date.today().year))


if __name__ == "__main__":
    main()
