"""Standardprofilen for kommuner i Elements: mønstrene tolkningen bruker.

Alt her er funnet i Steinkjers dokumenter fra 2026, og flyttet uendret fra
tolk/tolk_protokoll.py, tolk/saksframlegg.py, tolk/bygg_saker.py og
tolk/navn.py. En kommune som skriver protokollene annerledes, overstyrer
feltene i kommuner/<slug>.json under «tolk», eller i tolk/profiler/<slug>.py.
Se tolk/profil.py.

Endres noe her, gjelder det alle kommunene. Fasiten for hver kommune
(tester/fasit/) skal da fortsatt bestå.
"""

from __future__ import annotations

import re

# Protokollene (tolk/tolk_protokoll.py) ------------------------------------------

# Et vedtak eller forslag, fram til «Dermed ble ... vedtatt».
# Observert i 2026: «Ikke til stede (1): navn.» etter navnelistene, noen ganger
# uten kolon og navn, og «vedtatt, med ordførers dobbeltstemme» (eller leders).
# Ved alternativ votering står «For forslag 1 stemte 4: …» for hvert forslag.
# Én gang står det bare «Dermed vedtatt», uten «ble» og uten punktum.
VOTERING = re.compile(
    r"((?:(?P<stiller>[A-ZÆØÅ][\wÆØÅæøå .\-]+?) \((?P<parti>[^)]+)\) "
    r"fremmet følgende (?P<type>[\w ]*?forslag):?)|Innstilling:|(?P<forslag>Forslag):)"
    r"(?P<tekst>.*?)"
    r"(?:For forslaget stemte (?P<n_for>\d+): (?P<for>.*?)\.)? ?"
    r"(?:Imot forslaget stemte (?P<n_mot>\d+): (?P<mot>.*?)\.)? ?"
    r"(?P<alternativer>(?:For forslag \S+ stemte \d+: .*?\. ?)+)?"
    r"(?:Ikke til stede \((?P<n_borte>\d+)\):? ?(?P<borte>[^.]*?)\.? ?)?"
    r"Dermed (?:ble )?(?P<resultat>[\w ]*?vedtatt)"
    r"(?:,? med (?P<dobbelt>ordførers|leders) dobbeltstemme)?\.?",
    re.S,
)

ALTERNATIV = re.compile(r"For forslag (?P<forslag>\S+) stemte (?P<n>\d+): (?P<navn>.*?)\.(?= For forslag |\s*$)")

# Uten navneliste: «Forslag til vedtak enstemmig vedtatt.», «Innstillingen ble
# enstemmig vedtatt.», «Forslaget fra X (R) ble enstemmig vedtatt.»
ENSTEMMIG = re.compile(r"(?P<tekst>[^.:]{0,100}?)\s*\b(?:ble )?enstemmig vedtatt\b")

# Hvor hver sak begynner i møteprotokollen, og saksnummeret foran den.
SAK = re.compile(r"(?=(?:PS|RS|OS|FO) \d+/\d+ [^\n]{0,300}? behandling av sak)")
SAKSNR = re.compile(r"((?:PS|RS|OS|FO) \d+/\d+)")

OPPMOTE = re.compile(
    r"^(?P<navn>.+?)\s{2,}(?P<funksjon>Leder|Nestleder|Medlem|Varamedlem)\s*"
    r"(?P<resten>.*?)\s*$",
    re.M,
)

# Kolonnen «Repr.» er partiet, eller kommunen i interkommunale utvalg.
FUNKSJON_PARTI = re.compile(r"^(\S+)\s*(.*)$")

# Oppmøtelisten går fra start til slutt; alle 67 møteprotokoller i 2026 har
# begge. Tabelloverskriften har kolonnene «Navn» og «Funksjon».
OPPMOTE_START = "Følgende medlemmer møtte"
OPPMOTE_SLUTT = "Følgende fra administrasjonen"
OPPMOTE_NAVN = "Navn"
OPPMOTE_FUNKSJON = "Funksjon"

# Saksprotokollen slutter med en linje som bare er dette, og vedtaket under.
VEDTAK_LINJE = "Vedtak"

# Hva som ble enstemmig vedtatt: setningen kuttes ved det første av disse ordene.
SUBJEKT = re.compile(r"\b(?:Forslag\w*|Innstilling\w*|Tilleggsforslag\w*|Dette|Følgende)\b.*$")

# Saksframleggene (tolk/saksframlegg.py) ------------------------------------------

SAKSFRAMLEGG_START = "SAKSFRAMLEGG"

# I malens rekkefølge. Bare første treff etter forrige overskrift teller.
# Variantene er funnet i 2026: «… forslag til vedtak i eldrerådet:»,
# «Saksvurdering» og «Sakvurderinger:». Bare «Vurdering» tas ikke med; det
# brukes også som underoverskrift inne i saksopplysningene.
OVERSKRIFTER = (
    ("forslag", re.compile(
        r"^.{0,40}\bforslag til (?:vedtak|innstilling)(?:\s+.{1,40}:|\s*:?)$", re.I)),
    ("saksopplysninger", re.compile(r"^saksopplysninger\s*:?$", re.I)),
    ("saksvurderinger", re.compile(r"^saks?vurdering(?:er)?\s*:?$", re.I)),
)

# Saksgangen (tolk/bygg_saker.py) ---------------------------------------------------

# Saker som ikke er politikk, men møteteknikk. Holdes utenfor tellingene.
FORMALIA = (
    "godkjenning av innkalling",
    "godkjenning av møteinnkalling",
    "godkjenning av sakliste",
    "godkjenning av saksliste",
    "godkjenning av protokoll",
    "gjennomgang av protokoll",
    "eventuelt",
    "referatsaker",
    "orienteringssaker",
)

# Utvalgskoden for kommunestyret i portalen.
KOMMUNESTYRE_KODE = "KS"

# Navn og partier (tolk/navn.py) -------------------------------------------------

# Navnelistene i protokollene bruker koder, forslagsstilleren står med fullt
# partinavn: «Tor Borgan (Senterpartiet) fremmet følgende forslag». Lokale
# partier legges til i kommunens profil.
PARTIKODER = {
    "Arbeiderpartiet": "AP",
    "Fremskrittspartiet": "FRP",
    "Høyre": "H",
    "Pensjonistpartiet": "PP",
    "Rødt": "R",
    "Senterpartiet": "SP",
    "Sosialistisk Venstreparti": "SV",
    "Uavhengig": "UAVH",
    "Venstre": "V",
}

# Samme person skrevet ulikt: variant -> normalisert form. Bare i kommunens profil.
NAVNEVARIANTER: dict[str, str] = {}

# Partikodene i voteringene med navnene AI-analysen bruker (analyser/). Settes i
# kommunens profil, med partiene som faktisk sitter der.
PARTINAVN: dict[str, str] = {}

# Dekningen (tolk/dekning.py) ------------------------------------------------------

# Ord som betyr at det ble stemt over noe. En saksprotokoll med et av dem, men
# uten en votering mønstrene fant, er mistenkt: der går stemmer tapt i stillhet.
# I Steinkjer 2026 fant den «Forslaget ble vedtatt mot 1 stemme (…)» og
# «7 stemte for … 0 stemte imot», som mønstrene ikke leser.
VOTERINGSORD = re.compile(r"\b(?:vedtatt|stemte|stemme|stemmer|votering|enstemmig|dobbeltstemme)\b", re.I)
