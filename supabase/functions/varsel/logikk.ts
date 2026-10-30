// Det i varsel-funksjonen som kan prøves uten Supabase og Resend (ADR-027):
// nøkkelen for «Slutt å følge», og e-posten med hodene. Ingen import utenom
// malen, så testene kjører med `node --test` (logikk.test.ts).

import { epostHtml, epostTekst, type SakIEpost } from "./mal.ts";

export const PORTAL = "https://portal.kommunelys.no";
export const AVSENDER = "Kommunelys <post@kommunelys.no>";

// En rad fra køen (portal.varsel_til_sending).
export type Rad = {
  id: number;
  folger_id: number;
  sak_id: number;
  tittel: string;
  url: string;
  hendelser: string[];
};

// Nøkkelen i lenken for «Slutt å følge»: HMAC-SHA256 av brukeren og
// følgingen (eller «alle»), med en hemmelighet som bare finnes i funksjonen.
// Lenken virker uten innlogging, men bare for den som fikk e-posten.
export async function signer(hemmelighet: string, bruker: string, folger: number | null): Promise<string> {
  const nokkel = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(hemmelighet), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", nokkel, new TextEncoder().encode(`folg:${bruker}:${folger ?? "alle"}`));
  return btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "").slice(0, 32);
}

export async function gyldig(hemmelighet: string, bruker: string, folger: number | null, n: string): Promise<boolean> {
  const riktig = await signer(hemmelighet, bruker, folger);
  // Lik tid uansett hvor tidlig de skiller seg.
  if (typeof n !== "string" || n.length !== riktig.length) return false;
  let ulik = 0;
  for (let i = 0; i < riktig.length; i++) ulik |= riktig.charCodeAt(i) ^ n.charCodeAt(i);
  return ulik === 0;
}

// Samme sak kan ha flere rader i køen, når e-posten har ventet en dag.
export function perSak(rader: Rad[]): Rad[] {
  const saker = new Map<number, Rad>();
  for (const r of rader) {
    const s = saker.get(r.folger_id);
    if (!s) saker.set(r.folger_id, { ...r, hendelser: [...r.hendelser] });
    else {
      for (const h of r.hendelser) if (!s.hendelser.includes(h)) s.hendelser.push(h);
      // Tittelen og lenken fra den nyeste raden.
      s.tittel = r.tittel;
      s.url = r.url;
    }
  }
  return [...saker.values()];
}

export type Epost = {
  from: string;
  to: string[];
  subject: string;
  html: string;
  text: string;
  headers: Record<string, string>;
};

// E-posten til én bruker. Lenkene i teksten går til vårt eget domene;
// List-Unsubscribe går til funksjonen, fordi GitHub Pages ikke tar imot POST.
export async function lagEpost(
  hemmelighet: string, funksjonUrl: string, bruker: string, epost: string, rader: Rad[],
): Promise<Epost> {
  const saker: SakIEpost[] = [];
  for (const r of perSak(rader)) {
    const n = await signer(hemmelighet, bruker, r.folger_id);
    saker.push({
      tittel: r.tittel,
      url: r.url,
      hendelser: r.hendelser,
      slutt: `${PORTAL}/slutt-a-folge?${new URLSearchParams({ b: bruker, f: String(r.folger_id), n })}`,
    });
  }
  const alleN = await signer(hemmelighet, bruker, null);
  const alle = `${PORTAL}/slutt-a-folge?${new URLSearchParams({ b: bruker, n: alleN })}`;
  const ettKlikk = `${funksjonUrl}?${new URLSearchParams({ handling: "slutt", b: bruker, n: alleN })}`;
  return {
    from: AVSENDER,
    to: [epost],
    subject: saker.length === 1 ? `Nytt i saken du følger: ${saker[0].tittel}` : "Nytt i sakene du følger",
    html: epostHtml(saker, alle, `${PORTAL}/min-konto`),
    text: epostTekst(saker, alle, `${PORTAL}/min-konto`),
    headers: {
      "List-Unsubscribe": `<${ettKlikk}>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
  };
}
