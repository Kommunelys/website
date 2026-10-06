/* Kontomenyen øverst på sidene (ADR-020). Innloggingen skjer i portalen.

   Uten skript står «Logg inn» og «Ny bruker» som vanlige lenker. Med skript
   tar lenkene deg tilbake til siden du var på. Etter innlogging sender
   portalen deg tilbake via /konto/, som lagrer kontoen i nettleseren din
   (localStorage). Da viser menyen kontoen. Ingen informasjonskapsler, og
   e-postadressen sendes ikke til nettstedet. Utlogging går samme vei. */
(function () {
  var boks = document.querySelector('.konto');
  if (!boks) return;
  var portal = boks.getAttribute('data-portal');
  var MAKS_ALDER = 30 * 24 * 3600 * 1000;

  // Adressen settes når lenken brukes, så fanen (#saker) kommer med.
  function tilbake(a, sti) {
    a.addEventListener('click', function () {
      a.href = portal + sti + '?tilbake=' + encodeURIComponent(location.href);
    });
  }
  boks.querySelectorAll('a[data-sti]').forEach(function (a) { tilbake(a, a.getAttribute('data-sti')); });

  var k = null;
  try { k = JSON.parse(localStorage.getItem('kommunelys-konto') || 'null'); } catch (e) {}
  if (!k || !k.epost || !(Date.now() - k.tid < MAKS_ALDER)) return;

  boks.textContent = '';
  var meny = document.createElement('details');
  meny.className = 'konto-meny';
  var knapp = document.createElement('summary');
  knapp.setAttribute('aria-label', 'Kontoen din: ' + k.epost);
  var ikon = document.createElement('span');
  ikon.className = 'konto-ikon';
  ikon.setAttribute('aria-hidden', 'true');
  ikon.textContent = k.epost.charAt(0).toUpperCase();
  var navn = document.createElement('span');
  navn.className = 'konto-navn';
  navn.textContent = k.epost;
  knapp.append(ikon, navn);

  var liste = document.createElement('div');
  liste.className = 'konto-liste';
  var hvem = document.createElement('p');
  var epost = document.createElement('strong');
  epost.textContent = k.epost;
  hvem.append('Logget inn som', document.createElement('br'), epost);
  liste.append(hvem);
  function lenke(tekst, sti) {
    var a = document.createElement('a');
    a.textContent = tekst;
    a.href = portal + sti;
    liste.append(a);
    return a;
  }
  lenke('Min konto', '/min-konto');
  if (k.admin) lenke('Portalen', '/');
  tilbake(lenke('Logg ut', '/logg-ut'), '/logg-ut');

  meny.append(knapp, liste);
  boks.append(meny);
  document.addEventListener('click', function (e) { if (!meny.contains(e.target)) meny.open = false; });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') meny.open = false; });
})();
