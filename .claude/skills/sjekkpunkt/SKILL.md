---
name: sjekkpunkt
description: Fast kontroll før en kodesesjon ber prosjekteier om ja til en PR. En blank kontrollør leser bare diffen og reglene i CLAUDE.md og svarer på om endringen er riktig, trygg og slank. Bruk før hver PR i Kommunelys/website, og når prosjekteier eller rådtråden ber om sjekkpunkt.
---

# Sjekkpunkt før PR

Kjøres av sesjonen som har skrevet koden, rett før den ber om ja. Kontrollen
slår aldri sammen, committer eller pusher noe. Prosjekteier er siste port.

## 1. Diffen og tallene

```bash
git fetch -q origin
BASE=$(git merge-base origin/main HEAD)
git diff $BASE --shortstat                  # +linjer/−linjer (med det som ikke er committet)
git diff $BASE --name-status | grep '^A'    # nye filer
git status --short | grep '^??'             # nye filer som ikke er lagt til ennå
git diff $BASE -- krav.txt '*package.json'  # nye avhengigheter
```

Nye skript i `bygg/mal/` og nye pakker i `supabase/functions/` telles også som
avhengigheter. Lagre diffen (med de nye filene) i en fil i scratchpad.

## 2. Den blanke kontrolløren

Start en subagent med Agent-verktøyet (`general-purpose`). Den får bare:
stien til diffen, én setning om hva PR-en skal gjøre, og beskjed om å lese
reglene i `CLAUDE.md`. **Ikke** begrunnelsen, valgene underveis eller
samtalen. Den kan lese resten av repoet. Be den svare på tre ting:

- **Riktig:** Gjør koden det PR-en sier? Finnes det feil? Kjør
  `python -m tester.kontroller` når endringen berører data eller bygget.
- **Trygg:** Brytes noen av reglene i `CLAUDE.md`? Se særlig etter navn på
  privatpersoner, skjermet innhold, kildelenker, informasjonskapsler og
  sporing, hemmeligheter i koden og RLS på nye tabeller.
- **Slank:** Kunne det vært gjort med færre linjer, færre filer eller uten
  den nye avhengigheten? Er noe bygget «for sikkerhets skyld», på forhånd
  eller som en abstraksjon med én bruker? Død kode, eller kode som gjentar
  noe som finnes?

Svaret er en liste med ett funn per linje: `riktig|trygg|slank`, `fil:linje`,
hva som er galt og hva som bør gjøres. Ingen funn gir `ingen funn`. Den
endrer ingen filer.

## 3. Funnene

Sesjonen retter det som er riktig å rette, og skriver én linje om hvorfor
den lar et funn ligge. Rettingen kontrolleres ikke på nytt, med mindre den
er stor.

## 4. Svaret til prosjekteier og rådtråden

```
Sjekkpunkt: godkjent | Sjekkpunkt: N funn, M rettet
+X/−Y linjer, Z nye filer, W nye avhengigheter
```

Under står høyst tre linjer om det som er igjen, ett funn per linje.
