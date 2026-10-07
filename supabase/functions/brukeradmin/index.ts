// Brukeradministrasjon for portalen (portal.kommunelys.no, ADR-020).
//
// Det portalen ikke kan gjøre med den publiserbare nøkkelen: liste brukere,
// invitere, sperre, sende lenke for nytt passord og slette. Service-nøkkelen
// finnes bare her, i Supabase. Bare prosjektadmin får bruke funksjonen,
// bortsett fra slett_meg, som alle kan bruke på sin egen konto.
//
// Prosjektadmin gis og fjernes fortsatt bare med SQL. Derfor kan ingen
// prosjektadmin sperres eller slettes herfra.

import { createClient, type User } from "npm:@supabase/supabase-js@2";

const URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const PORTAL = "https://portal.kommunelys.no";
// lokal.kommunelys.no peker til 127.0.0.1; hCaptcha virker ikke på localhost.
const TILLATTE_OPPHAV = [PORTAL, "http://localhost:5173", "http://lokal.kommunelys.no:5173"];

// Sperret til langt fram i tid; "none" opphever sperren.
const SPERRET = "876000h";

type Bruker = {
  id: string;
  email: string | undefined;
  opprettet: string;
  sist_innlogget: string | null;
  bekreftet: string | null;
  invitert: string | null;
  sperret_til: string | null;
};

function bruker(u: User): Bruker {
  return {
    id: u.id,
    email: u.email,
    opprettet: u.created_at,
    sist_innlogget: u.last_sign_in_at ?? null,
    bekreftet: u.email_confirmed_at ?? null,
    invitert: u.invited_at ?? null,
    // banned_until finnes på brukeren, men ikke i typen.
    sperret_til: (u as User & { banned_until?: string }).banned_until ?? null,
  };
}

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

Deno.serve(async (req) => {
  const opphav = TILLATTE_OPPHAV.includes(req.headers.get("Origin") ?? "")
    ? req.headers.get("Origin")!
    : PORTAL;
  if (req.method === "OPTIONS") return svar(null, 204, opphav);
  if (req.method !== "POST") return svar({ feil: "Bare POST" }, 405, opphav);

  try {
    const innlogging = req.headers.get("Authorization");
    if (!innlogging) throw new Feil(401, "Ikke innlogget");

    // Brukerens egen innlogging: RLS gjelder.
    const somBruker = createClient(URL, ANON, {
      global: { headers: { Authorization: innlogging } },
      db: { schema: "portal" },
      auth: { persistSession: false },
    });
    const { data: meg, error: megFeil } = await somBruker.auth.getUser();
    if (megFeil || !meg.user) throw new Feil(401, "Ikke innlogget");
    const { data: tilgang, error: tilgangFeil } = await somBruker.rpc("meg");
    if (tilgangFeil) throw new Feil(500, tilgangFeil.message);
    const erProsjektadmin = tilgang?.er_prosjektadmin === true;

    const admin = createClient(URL, SERVICE, { auth: { persistSession: false } }).auth.admin;
    const inn = await req.json().catch(() => ({}));
    const handling: string = inn.handling ?? "";

    if (handling === "slett_meg") {
      if (erProsjektadmin) throw new Feil(400, "Prosjektadmin kan ikke slette seg selv her");
      const { error } = await admin.deleteUser(meg.user.id);
      if (error) throw new Feil(500, error.message);
      return svar({ ok: true }, 200, opphav);
    }

    if (!erProsjektadmin) throw new Feil(403, "Bare for prosjektadmin");

    // Prosjektadminene beskyttes mot sperring og sletting herfra.
    const prosjektadmin = async (id: string) => {
      const { data, error } = await somBruker.from("prosjektadmin").select("user_id").eq("user_id", id);
      if (error) throw new Feil(500, error.message);
      return (data ?? []).length > 0;
    };
    const hent = async (id: string) => {
      const { data, error } = await admin.getUserById(id);
      if (error) throw new Feil(404, error.message);
      return bruker(data.user);
    };

    switch (handling) {
      case "liste": {
        // Få brukere: hent alle, og filtrer, sorter og del opp her.
        const alle: Bruker[] = [];
        for (let side = 1; ; side++) {
          const { data, error } = await admin.listUsers({ page: side, perPage: 1000 });
          if (error) throw new Feil(500, error.message);
          alle.push(...data.users.map(bruker));
          if (data.users.length < 1000) break;
        }
        const sok = String(inn.sok ?? "").toLowerCase();
        const treff = sok ? alle.filter((b) => (b.email ?? "").toLowerCase().includes(sok)) : alle;
        const felt = (inn.sorter ?? "opprettet") as keyof Bruker;
        const retning = inn.retning === "ASC" ? 1 : -1;
        treff.sort((a, b) => String(a[felt] ?? "").localeCompare(String(b[felt] ?? "")) * retning);
        const perSide = Math.min(Number(inn.per_side ?? 25), 1000);
        const fra = (Math.max(Number(inn.side ?? 1), 1) - 1) * perSide;
        return svar({ data: treff.slice(fra, fra + perSide), total: treff.length }, 200, opphav);
      }
      case "hent":
        return svar({ data: await hent(String(inn.id)) }, 200, opphav);
      case "hent_flere": {
        const ider: string[] = Array.isArray(inn.ider) ? inn.ider.map(String) : [];
        const data = await Promise.all(ider.map((id) => hent(id).catch(() => null)));
        return svar({ data: data.filter(Boolean) }, 200, opphav);
      }
      case "inviter": {
        const email = String(inn.email ?? "").trim();
        if (!email.includes("@")) throw new Feil(400, "Ugyldig e-postadresse");
        const { data, error } = await admin.inviteUserByEmail(email, {
          redirectTo: `${opphav}/set-password`,
        });
        if (error) throw new Feil(400, error.message);
        return svar({ data: bruker(data.user) }, 200, opphav);
      }
      case "sperr":
      case "aapne": {
        const id = String(inn.id);
        if (await prosjektadmin(id)) throw new Feil(400, "Prosjektadmin kan ikke sperres her");
        const { data, error } = await admin.updateUserById(id, {
          ban_duration: handling === "sperr" ? SPERRET : "none",
        });
        if (error) throw new Feil(500, error.message);
        return svar({ data: bruker(data.user) }, 200, opphav);
      }
      case "nytt_passord": {
        const b = await hent(String(inn.id));
        if (!b.email) throw new Feil(400, "Brukeren har ingen e-postadresse");
        // Med service-nøkkelen, som slipper captcha. Uten den ville Supabase
        // krevd svar fra en captcha her også.
        const { error } = await createClient(URL, SERVICE, { auth: { persistSession: false } })
          .auth.resetPasswordForEmail(b.email, { redirectTo: `${opphav}/set-password` });
        if (error) throw new Feil(500, error.message);
        return svar({ data: b }, 200, opphav);
      }
      case "slett": {
        const id = String(inn.id);
        if (await prosjektadmin(id)) throw new Feil(400, "Prosjektadmin kan ikke slettes her");
        const b = await hent(id);
        const { error } = await admin.deleteUser(id);
        if (error) throw new Feil(500, error.message);
        return svar({ data: b }, 200, opphav);
      }
      default:
        throw new Feil(400, `Ukjent handling: ${handling}`);
    }
  } catch (e) {
    const status = e instanceof Feil ? e.status : 500;
    return svar({ feil: e instanceof Error ? e.message : String(e) }, status, opphav);
  }
});
