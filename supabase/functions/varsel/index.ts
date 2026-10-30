// Varsel til dem som følger saker (ADR-027).
//
// send: Oppdater (varsel.kjor) ber om utsending etter at nettstedet er
// publisert. Funksjonen henter køen med e-postadressene fra databasen
// (portal.varsel_til_sending, bare for service-nøkkelen), og sender én e-post
// per bruker via Resend. Grensene står i databasen: høyst én e-post per bruker
// i døgnet, og varslene stopper litt under grensen i Resend-planen. Resten
// venter til neste dag. E-postadressene er aldri i Actions.
//
// slutt: «Slutt å følge» fra e-posten, uten innlogging. Nøkkelen i lenken er
// signert med VARSEL_HEMMELIGHET. Portalen sender den hit (/slutt-a-folge), og
// e-postprogrammene sender List-Unsubscribe-Post (RFC 8058) rett hit.
//
// Funksjonen publiseres med verify_jwt = false: e-postprogrammene har ingen
// innlogging. send er beskyttet av VARSEL_NOKKEL, slutt av signaturen.

import { createClient } from "npm:@supabase/supabase-js@2";
import { gyldig, lagEpost, PORTAL, type Rad } from "./logikk.ts";

const SUPABASE = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const RESEND = Deno.env.get("RESEND_API_KEY") ?? "";
const NOKKEL = Deno.env.get("VARSEL_NOKKEL") ?? "";
const HEMMELIGHET = Deno.env.get("VARSEL_HEMMELIGHET") ?? "";

const FUNKSJON = `${SUPABASE}/functions/v1/varsel`;
const TILLATTE_OPPHAV = [PORTAL, "http://localhost:5173", "http://lokal.kommunelys.no:5173"];
// Resend tillater 10 kall i sekundet for hele kontoen; vi holder oss på 5.
const PAUSE_MS = 200;

// Svaret på forhåndssjekken (OPTIONS, 204) kan ikke ha innhold.
function svar(body: unknown, status: number, opphav: string): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": opphav,
      "Access-Control-Allow-Headers":
        "authorization, content-type, apikey, x-client-info, x-supabase-api-version",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Vary": "Origin",
    },
  });
}

class Feil extends Error {
  constructor(public status: number, melding: string) {
    super(melding);
  }
}

const db = () => createClient(SUPABASE, SERVICE, { db: { schema: "portal" }, auth: { persistSession: false } });

// Lik tid uansett hvor tidlig nøklene skiller seg.
function lik(a: string, b: string): boolean {
  if (!a || a.length !== b.length) return false;
  let ulik = 0;
  for (let i = 0; i < a.length; i++) ulik |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return ulik === 0;
}

async function send(): Promise<{ sendt: number; mottakere: number; feil: number }> {
  if (!RESEND || !HEMMELIGHET) throw new Feil(500, "Mangler RESEND_API_KEY eller VARSEL_HEMMELIGHET");
  const klient = db();
  const { data, error } = await klient.rpc("varsel_til_sending");
  if (error) throw new Feil(500, error.message);
  const til = (data ?? []) as { user_id: string; epost: string; saker: Rad[] }[];
  let sendt = 0, feil = 0;
  for (const m of til) {
    const e = await lagEpost(HEMMELIGHET, FUNKSJON, m.user_id, m.epost, m.saker);
    const ider = m.saker.map((r) => r.id);
    let resendId: string | null = null, melding: string | null = null, brukt: number | null = null, stopp = false;
    try {
      const r = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${RESEND}`,
          "Content-Type": "application/json",
          // Samme rader sendes ikke to ganger, selv om kallet gjentas (24 timer).
          "Idempotency-Key": `varsel-${ider.join("-")}`.slice(0, 256),
        },
        body: JSON.stringify(e),
      });
      // Hvor mange e-poster kontoen har brukt i dag, også fra innloggingen.
      const kvote = Number(r.headers.get("x-resend-daily-quota"));
      brukt = Number.isFinite(kvote) && r.headers.has("x-resend-daily-quota") ? kvote : null;
      const innhold = await r.json().catch(() => ({}));
      if (r.ok) resendId = innhold.id ?? null;
      else {
        melding = `HTTP ${r.status}: ${innhold.message ?? innhold.name ?? "ukjent feil"}`;
        // Grensen hos Resend er nådd: resten venter til neste kjøring.
        stopp = r.status === 429;
      }
    } catch (x) {
      melding = `Resend svarte ikke: ${x instanceof Error ? x.message : String(x)}`;
    }
    const { error: lagreFeil } = await klient.rpc("varsel_sendt", {
      p_ider: ider, p_resend_id: resendId, p_feil: melding, p_brukt: brukt,
    });
    if (lagreFeil) throw new Feil(500, lagreFeil.message);
    if (melding) feil++;
    else sendt++;
    if (stopp) break;
    await new Promise((ok) => setTimeout(ok, PAUSE_MS));
  }
  return { sendt, mottakere: sendt, feil };
}

async function slutt(b: string, f: string | null, n: string): Promise<number> {
  const folger = f ? Number(f) : null;
  if (!HEMMELIGHET || !b || (f && !Number.isInteger(folger)) || !(await gyldig(HEMMELIGHET, b, folger, n))) {
    throw new Feil(403, "Lenken er ikke gyldig");
  }
  const { data, error } = await db().rpc("varsel_slutt", { p_bruker: b, p_folger: folger });
  if (error) throw new Feil(500, error.message);
  return data as number;
}

Deno.serve(async (req) => {
  const opphav = TILLATTE_OPPHAV.includes(req.headers.get("Origin") ?? "")
    ? req.headers.get("Origin")!
    : PORTAL;
  if (req.method === "OPTIONS") return svar(null, 204, opphav);
  const q = new URL(req.url).searchParams;

  // Åpnes lenken i List-Unsubscribe i en nettleser (GET), skjer ingenting her:
  // den sendes til siden i portalen, som spør først. Lenkeskannere åpner lenker.
  if (req.method === "GET" && q.get("handling") === "slutt") {
    const videre = new URLSearchParams({ b: q.get("b") ?? "", n: q.get("n") ?? "" });
    return Response.redirect(`${PORTAL}/slutt-a-folge?${videre}`, 303);
  }
  if (req.method !== "POST") return svar({ feil: "Bare POST" }, 405, opphav);

  try {
    // Ett klikk fra e-postprogrammet (RFC 8058): parameterne står i adressen.
    if (q.get("handling") === "slutt") {
      const antall = await slutt(q.get("b") ?? "", q.get("f"), q.get("n") ?? "");
      return svar({ antall }, 200, opphav);
    }
    const inn = await req.json().catch(() => ({}));
    if (inn.handling === "slutt") {
      const antall = await slutt(String(inn.b ?? ""), inn.f ? String(inn.f) : null, String(inn.n ?? ""));
      return svar({ antall }, 200, opphav);
    }
    if (inn.handling === "send") {
      if (!lik(req.headers.get("x-varsel-nokkel") ?? "", NOKKEL)) throw new Feil(401, "Ikke tillatt");
      return svar(await send(), 200, opphav);
    }
    throw new Feil(400, "Ukjent handling");
  } catch (e) {
    const status = e instanceof Feil ? e.status : 500;
    return svar({ feil: e instanceof Error ? e.message : String(e) }, status, opphav);
  }
});
