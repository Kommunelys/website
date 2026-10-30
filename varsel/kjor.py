"""Varsel etter bygget: legger endringene i køen og ber om utsending (ADR-027).

Kjøres i Oppdater etter at nettstedet er publisert, så lenkene i e-posten
peker til sider som finnes:

    python -m varsel.kjor              # legger i køen
    VARSEL_SEND=1 python -m varsel.kjor  # og ber edge-funksjonen varsel sende

For hver følging sammenlignes saken med tilstanden ved forrige varsel. Saken
finnes gjennom behandlingen, siden ID-en til saken kan endre seg. En følging
uten tilstand (saken var ikke bygget da den ble fulgt) får tilstanden nå,
uten varsel.

E-postadressene er aldri her: edge-funksjonen slår dem opp og sender via
Resend, med grensene i portal.varsel_til_sending. Tallene lagres i
drift.kjoring_tall under «varsel», for alle kommunene samlet.
"""

from __future__ import annotations

import json
import os
import urllib.request

from bygg.bygg_nettsted import NETTSTED, SUPABASE_URL
from lager import i_dag
from lager import varsel as lager_varsel

from .endringer import endringer

# Kommuner der noen kan følge saker (ADR-024: begrenset krever en rolle, og
# edge-funksjonen sjekker den før sending).
APNE = ("publisert", "begrenset")


def ko(folgere: list[dict], dag: str) -> tuple[list[dict], dict[int, dict]]:
    """Radene til køen, og den nye tilstanden per følging."""
    rader, nye = [], {}
    for f in folgere:
        if f["status"] not in APNE or f["sak_id"] is None or f["naa"] is None:
            continue
        if f["tilstand"] != f["naa"]:
            nye[f["id"]] = f["naa"]
        hendelser = endringer(f["tilstand"], f["naa"], dag)
        if hendelser:
            rader.append({
                "folger_id": f["id"], "user_id": f["user_id"], "kommune_id": f["kommune_id"],
                "sak_id": f["sak_id"], "tittel": f["naa"].get("tittel") or f["tittel"],
                "url": f"{NETTSTED}/{f['kommune']}/#sak/{f['sak_id']}", "hendelser": hendelser,
            })
    return rader, nye


def send() -> dict:
    """Ber edge-funksjonen sende køen. Svaret er tallene fra sendingen."""
    forespørsel = urllib.request.Request(
        f"{SUPABASE_URL}/functions/v1/varsel", method="POST",
        data=json.dumps({"handling": "send"}).encode(),
        headers={"content-type": "application/json", "x-varsel-nokkel": os.environ["VARSEL_NOKKEL"]})
    with urllib.request.urlopen(forespørsel, timeout=600) as svar:
        return json.loads(svar.read())


def main() -> None:
    folgere = lager_varsel.folgere()
    rader, nye = ko(folgere, i_dag())
    print(f"{len(folgere)} følginger, {len(rader)} saker med endringer lagt i køen, "
          f"{len(nye)} tilstander oppdatert")
    tall = {"ny_i_ko": len(rader)}
    lager_varsel.lagre_ko(rader, nye, tall)
    if os.environ.get("VARSEL_SEND") == "1":
        svar = send()
        print(f"sendt {svar.get('sendt', 0)} e-poster, {svar.get('feil', 0)} feil")
        tall = {k: svar.get(k, 0) for k in ("sendt", "mottakere", "feil")}
    else:
        print("VARSEL_SEND er ikke 1: ingenting sendes")
        tall = {}
    # E-postene som venter etter sendingen, til neste dag eller til utsendingen er slått på.
    tall["venter"] = (lager_varsel.tall() or {}).get("venter_brukere", 0)
    lager_varsel.lagre_tall(tall)


if __name__ == "__main__":
    main()
