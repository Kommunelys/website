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

  function les(n) { try { return JSON.parse(localStorage.getItem(n) || 'null'); } catch (e) { return null; } }
  var k = les('kommunelys-konto');
  if (!k || !k.epost || !(Date.now() - k.tid < MAKS_ALDER)) return;
  visBegrensede();

  /* Kommunene med begrenset innsyn (ADR-024) er skjult på forsiden og kartet
     (data-begrenset). De vises for prosjektadmin og for kontoer med en rolle
     for kommunen. Rollene hentes med tilgangsnøkkelen og huskes til
     utlogging, så kommunene står der også etter at nøkkelen er gått ut.
     Bare visning: databasen avgjør hvem som får se innholdet. */
  function visBegrensede() {
    var skjult = document.querySelectorAll('[data-begrenset]');
    function vis(liste) {
      var slugs = liste.map(function (x) { return x.slug; });
      skjult.forEach(function (e) { if (k.pa || slugs.indexOf(e.getAttribute('data-begrenset')) >= 0) e.removeAttribute('hidden'); });
    }
    vis(les('kommunelys-begrenset') || []);
    var inn = les('kommunelys-innsyn');
    if (!inn || !inn.nokkel || !(inn.utloper * 1000 > Date.now())) return;
    var h = { apikey: boks.getAttribute('data-nokkel'), Authorization: 'Bearer ' + inn.nokkel, 'Accept-Profile': 'portal' };
    function hent(sti) {
      return fetch(boks.getAttribute('data-api') + '/rest/v1/' + sti, { headers: h })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
    }
    Promise.all([hent('medlemskap?select=kommune_id'), hent('kommune?select=kommune_id,slug,navn&status=eq.begrenset')])
      .then(function (svar) {
        var mine = svar[0].map(function (m) { return m.kommune_id; });
        var liste = svar[1].filter(function (x) { return k.pa || mine.indexOf(x.kommune_id) >= 0; })
          .map(function (x) { return { slug: x.slug, navn: x.navn }; });
        try { localStorage.setItem('kommunelys-begrenset', JSON.stringify(liste)); } catch (e) {}
        vis(liste);
      }).catch(function () {});
  }

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
  // Prosjektadmin ser lenkene til redigering i portalen (.bare-prosjektadmin,
  // ADR-025). Bare visning: portalen og databasen avgjør hvem som får redigere.
  if (k.pa) document.documentElement.classList.add('prosjektadmin');
  lenke('Min konto', '/min-konto');
  if (k.admin) lenke('Portalen', '/');
  tilbake(lenke('Logg ut', '/logg-ut'), '/logg-ut');

  meny.append(knapp, liste);
  boks.append(meny);
  document.addEventListener('click', function (e) { if (!meny.contains(e.target)) meny.open = false; });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') meny.open = false; });
})();
