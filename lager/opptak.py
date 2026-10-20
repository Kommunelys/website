"""Opptak av møtene, tekstingen av dem og sammendragene av debatten (ADR-026).

Skrives av hent.hent_opptak og analyser.analyser_debatt. Opptaket ligger hos
kommunen; her står lenken, bokmerkene for sakene og tekstingen. Videoen
lagres ikke.

Med KOMMUNELYS_LAGER=json ligger dataene i <data>/opptak/ og <data>/debatt/.
De fantes ikke da data/ ble frosset 6.10.2026, så de brukes bare med en kopi
(KOMMUNELYS_DATA).
"""

from __future__ import annotations

from . import _fil, fra_databasen, kjoring_id, pg, pg_skriv

OPPTAK = _fil.DATA / "opptak"
DEBATT = _fil.DATA / "debatt"


def alle() -> list[dict]:
    """Alle opptakene for kommunen, med bokmerkene, etter opptakets ID."""
    if fra_databasen():
        return pg.opptak()
    return _fil.les(OPPTAK / "opptak.json", [])


def lagre(opptak: list[dict]) -> None:
    """Gjør opptakene like listen. Opptak som ikke står i listen, røres ikke."""
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.opptak(c, k, opptak))
    gamle = {o["opptak_id"]: o for o in alle()}
    gamle.update({o["opptak_id"]: o for o in opptak})
    _fil.skriv(OPPTAK / "opptak.json", [gamle[i] for i in sorted(gamle)])


def lagre_raa(opptak_id: int, svar: dict, biter: list[str] | None) -> None:
    """Svaret fra opptakstjenesten og WebVTT-bitene, urørt. Bare innsetting."""
    if fra_databasen():
        return pg_skriv.i_transaksjon(
            lambda c, k: pg_skriv.raa_opptak(c, k, opptak_id, svar, biter, kjoring_id()))
    sti = OPPTAK / f"raa-{opptak_id}.json"
    # Tekstingen hentes én gang; uten nye biter beholdes de gamle.
    biter = biter or _fil.les(sti, {}).get("biter")
    _fil.skriv(sti, {"svar": svar, "biter": biter}, sorter=False)


def teksting(opptak_id: int) -> dict | None:
    """Tekstingen som gjelder for opptaket: {opptak_id, kilde, linjer}."""
    if fra_databasen():
        return pg.teksting(opptak_id)
    return _fil.les(OPPTAK / f"teksting-{opptak_id}.json", None)


def lagre_teksting(opptak_id: int, linjer: list[dict]) -> None:
    t = {"opptak_id": opptak_id, "kilde": "kommunetv-teksting", "linjer": linjer}
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.teksting(c, k, t, kjoring_id()))
    _fil.skriv(OPPTAK / f"teksting-{opptak_id}.json", t, sorter=False)


def debatt(behandling_id: int) -> dict | None:
    if fra_databasen():
        return pg.debatt(behandling_id)
    return _fil.les(DEBATT / f"{behandling_id}.json", None)


def debatter() -> dict[int, dict]:
    """Alle sammendragene av debatten, etter behandling."""
    if fra_databasen():
        return pg.debatter()
    ds = [_fil.les(sti) for sti in DEBATT.glob("*.json")]
    return {d["behandling_id"]: d for d in sorted(ds, key=lambda d: d["behandling_id"])}


def debatt_kontroller() -> dict[int, list[str]]:
    """Grunnene fra siste lagrede kontroll av hver debatt, per behandling.

    Bare i databasen (debatt_kontroll), som kontrollen av sammendragene.
    """
    return pg.debatt_kontroller() if fra_databasen() else {}


def lagre_debatt_kontroller(resultater: dict[int, list[str]]) -> None:
    if fra_databasen():
        pg.lagre_debatt_kontroller(resultater, kjoring_id())


def debatt_vurderinger() -> dict[int, dict]:
    """Gjeldende vurdering av debatten per behandling (portalen)."""
    return pg.debatt_vurderinger() if fra_databasen() else {}


def lagre_debatt(d: dict) -> None:
    if fra_databasen():
        return pg_skriv.i_transaksjon(lambda c, k: pg_skriv.debatter(c, k, [d], kjoring_id()))
    _fil.skriv(DEBATT / f"{d['behandling_id']}.json", d, sorter=False)
