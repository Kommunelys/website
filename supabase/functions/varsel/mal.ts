// E-posten «Nytt i sakene du følger» (ADR-027). Malen ligger her og ikke i
// supabase/epostmaler/, fordi funksjonen bare får med filene i sin egen mappe.
// Malene der er for e-postene fra innloggingen, som limes inn i Supabase.
//
// Ingen tekst fra sammendraget: tittelen, hva som skjedde, og lenken til
// saken. Bunnteksten er den samme som på nettstedet.

export type SakIEpost = { tittel: string; url: string; hendelser: string[]; slutt: string };

const BUNN = "Kommunelys er en uoffisiell tjeneste, laget av en innbygger for innbyggerne.";

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export function epostHtml(saker: SakIEpost[], alle: string, minKonto: string): string {
  const blokker = saker.map((s) => `
<h3 style="margin:24px 0 6px;font-size:17px"><a href="${esc(s.url)}" style="color:#1F5FAD">${esc(s.tittel)}</a></h3>
<ul style="margin:0 0 8px;padding-left:20px">${s.hendelser.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>
<p style="margin:0;font-size:14px"><a href="${esc(s.url)}" style="color:#1F5FAD">Se saken på kommunelys.no</a> · <a href="${esc(s.slutt)}" style="color:#646B76">Slutt å følge denne saken</a></p>`).join("");
  return `<!doctype html>
<html lang="nb"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:24px 16px;background:#FAF9F6;color:#1F2937;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;font-size:16px;line-height:1.5">
<div style="max-width:560px;margin:0 auto">
<h2 style="margin:0 0 4px;font-size:21px">${saker.length === 1 ? "Nytt i saken du følger" : "Nytt i sakene du følger"}</h2>
<p style="margin:0;color:#646B76;font-size:14px">Dette er nytt siden sist.</p>
${blokker}
<hr style="border:0;border-top:1px solid #E5E7EB;margin:28px 0 14px">
<p style="margin:0 0 8px;color:#646B76;font-size:13px">Du får denne e-posten fordi du følger saker på kommunelys.no. Du ser dem under <a href="${esc(minKonto)}" style="color:#646B76">Min konto</a>, eller du kan <a href="${esc(alle)}" style="color:#646B76">slutte å følge alle sakene</a>. Vi sender høyst én e-post om dagen.</p>
<p style="margin:0;color:#646B76;font-size:13px">${BUNN}</p>
</div></body></html>`;
}

export function epostTekst(saker: SakIEpost[], alle: string, minKonto: string): string {
  const blokker = saker.map((s) =>
    `${s.tittel}\n${s.hendelser.map((h) => `- ${h}`).join("\n")}\nSe saken: ${s.url}\nSlutt å følge denne saken: ${s.slutt}`
  ).join("\n\n");
  return `${saker.length === 1 ? "Nytt i saken du følger" : "Nytt i sakene du følger"}\n\n${blokker}\n\n---\n` +
    `Du får denne e-posten fordi du følger saker på kommunelys.no. Du ser dem under Min konto (${minKonto}), ` +
    `eller du kan slutte å følge alle sakene: ${alle}\nVi sender høyst én e-post om dagen.\n\n${BUNN}\n`;
}
