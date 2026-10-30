// node --test supabase/functions/varsel/logikk.test.ts
//
// Nøkkelen for «Slutt å følge», og e-posten: lenkene til vårt eget domene,
// List-Unsubscribe til funksjonen, ingen tekst fra sammendraget.

import assert from "node:assert/strict";
import { test } from "node:test";
import { gyldig, lagEpost, perSak, signer, type Rad } from "./logikk.ts";

const H = "hemmelig";
const B = "11111111-2222-3333-4444-555555555555";
const FUNKSJON = "https://prosjekt.supabase.co/functions/v1/varsel";

const rad = (id: number, folger_id: number, hendelser: string[], tittel = "Ny skole"): Rad => ({
  id, folger_id, sak_id: 100 + folger_id, tittel, url: `https://kommunelys.no/test/#sak/${100 + folger_id}`, hendelser,
});

test("nøkkelen gjelder bare brukeren og følgingen den ble laget for", async () => {
  const n = await signer(H, B, 7);
  assert.equal(n.length, 32);
  assert.ok(await gyldig(H, B, 7, n));
  assert.ok(!(await gyldig(H, B, 8, n)), "en annen sak");
  assert.ok(!(await gyldig(H, B, null, n)), "alle sakene");
  assert.ok(!(await gyldig(H, "99999999-2222-3333-4444-555555555555", 7, n)), "en annen bruker");
  assert.ok(!(await gyldig("annen", B, 7, n)), "en annen hemmelighet");
  assert.ok(!(await gyldig(H, B, 7, n.slice(0, 31))), "kortere");
  assert.ok(await gyldig(H, B, null, await signer(H, B, null)));
});

test("samme sak fra flere dager blir én sak, uten like hendelser to ganger", () => {
  const saker = perSak([rad(1, 7, ["A", "B"]), rad(2, 8, ["C"]), rad(3, 7, ["B", "D"], "Ny skole i sentrum")]);
  assert.equal(saker.length, 2);
  assert.deepEqual(saker[0].hendelser, ["A", "B", "D"]);
  assert.equal(saker[0].tittel, "Ny skole i sentrum");
});

test("e-posten: lenker til vårt eget domene, og ett klikk til funksjonen", async () => {
  const e = await lagEpost(H, FUNKSJON, B, "a@example.invalid",
    [rad(1, 7, ["Ny status: Vedtatt i kommunestyret"]), rad(2, 8, ["Sammendraget er publisert"], "Vei <og> bro")]);
  assert.equal(e.from, "Kommunelys <post@kommunelys.no>");
  assert.deepEqual(e.to, ["a@example.invalid"]);
  assert.equal(e.subject, "Nytt i sakene du følger");
  assert.equal(e.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
  assert.match(e.headers["List-Unsubscribe"], /^<https:\/\/prosjekt\.supabase\.co\/functions\/v1\/varsel\?handling=slutt&b=[^&]+&n=[^&>]+>$/);
  const lenker = [...e.html.matchAll(/href="([^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, "&"));
  assert.ok(lenker.length >= 6);
  for (const l of lenker) assert.match(l, /^https:\/\/(portal\.)?kommunelys\.no\//, l);
  assert.ok(!e.html.includes("supabase"), "bare List-Unsubscribe går til funksjonen");
  assert.ok(e.html.includes("Vei &lt;og&gt; bro"), "tittelen er escapet");
  assert.ok(e.html.includes("uoffisiell tjeneste, laget av en innbygger for innbyggerne"));
  assert.ok(e.text.includes("Slutt å følge denne saken: https://portal.kommunelys.no/slutt-a-folge?"));
  // Hver sak har sin egen lenke, med en nøkkel som bare gjelder den.
  const slutt = lenker.filter((l) => l.includes("&f="));
  assert.equal(slutt.length, 2);
  const u = new URL(slutt[0]);
  assert.ok(await gyldig(H, u.searchParams.get("b")!, Number(u.searchParams.get("f")), u.searchParams.get("n")!));
});

test("én sak: emnet har tittelen", async () => {
  const e = await lagEpost(H, FUNKSJON, B, "a@example.invalid", [rad(1, 7, ["Sammendraget er publisert"])]);
  assert.equal(e.subject, "Nytt i saken du følger: Ny skole");
});
