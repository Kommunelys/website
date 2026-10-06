/* Kontomenyen øverst på sidene (ADR-020). Innloggingen skjer i portalen.

   Uten skript står «Logg inn» og «Ny bruker» som vanlige lenker. Med skript
   tar lenkene deg tilbake til siden du var på. Har du brukt dem i denne
   nettleseren, spørres portalen gjennom en skjult ramme om du er logget inn,
   og menyen viser kontoen din. Svaret går bare mellom portalen og denne
   siden i nettleseren din: ingen informasjonskapsler, og e-postadressen
   sendes ikke til nettstedet. */
(function () {
  var boks = document.querySelector('.konto');
  if (!boks) return;
  var portal = boks.getAttribute('data-portal');
  var FLAGG = 'kommunelys-konto';

  function husk(ja) {
    try { if (ja) localStorage.setItem(FLAGG, '1'); else localStorage.removeItem(FLAGG); } catch (e) {}
  }
  // Adressen settes når lenken brukes, så fanen (#saker) kommer med.
  function tilbake(a, sti) {
    a.addEventListener('click', function () {
      husk(true);
      a.href = portal + sti + '?tilbake=' + encodeURIComponent(location.href);
    });
  }
  boks.querySelectorAll('a[data-sti]').forEach(function (a) { tilbake(a, a.getAttribute('data-sti')); });

  var flagg = null;
  try { flagg = localStorage.getItem(FLAGG); } catch (e) {}
  if (!flagg) return;

  var ramme = document.createElement('iframe');
  ramme.src = portal + '/konto-status.html';
  ramme.title = 'Innlogging';
  ramme.hidden = true;
  ramme.tabIndex = -1;
  ramme.setAttribute('aria-hidden', 'true');
  window.addEventListener('message', function (m) {
    if (m.origin !== portal || !m.data || m.data.kommunelys !== 'konto') return;
    ramme.remove();
    if (m.data.epost) vis(m.data); else husk(false);
  });
  document.body.appendChild(ramme);

  function vis(k) {
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
  }
})();
