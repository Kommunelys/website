"""Kallet til Claude, felles for sakene (analyser_saker) og debatten (analyser_debatt).

Modellen og innsatsen inngår i sjekksummene i begge. Endres de, analyseres
alt på nytt.
"""

from __future__ import annotations

import json

MODELL = "claude-opus-5"
INNSATS = "high"
MAKS_TOKENS = 16000


class Avvist(Exception):
    """Svaret kan ikke brukes: avslag, kuttet svar eller ugyldig JSON."""


def kall(klient, instruksjon: str, skjema: dict, tekst: str) -> tuple[dict, str, dict]:
    """Ett kall mot modellen. Gir (svaret, modellen som faktisk svarte, forbruket).

    Svaret er låst til skjemaet. Avslår modellens sikkerhetsfiltre, kjøres samme
    forespørsel på Anthropics anbefalte reservemodell (fallbacks: "default").
    """
    svar = klient.beta.messages.create(
        model=MODELL,
        max_tokens=MAKS_TOKENS,
        system=instruksjon,
        messages=[{"role": "user", "content": tekst}],
        output_config={"effort": INNSATS,
                       "format": {"type": "json_schema", "schema": skjema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if svar.stop_reason == "refusal":
        raise Avvist(f"avslått ({getattr(svar.stop_details, 'category', None)})")
    if svar.stop_reason == "max_tokens":
        raise Avvist("svaret ble kuttet ved max_tokens")
    tekster = [b.text for b in svar.content if b.type == "text"]
    if not tekster:
        raise Avvist(f"ingen tekst i svaret (stop_reason {svar.stop_reason})")
    try:
        resultat = json.loads(tekster[-1])
    except json.JSONDecodeError as e:
        raise Avvist(f"ugyldig JSON: {e}") from e
    return resultat, svar.model, {"inn": svar.usage.input_tokens, "ut": svar.usage.output_tokens}
