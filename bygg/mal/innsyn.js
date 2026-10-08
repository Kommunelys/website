/* Begrenset innsyn (ADR-024). Brukes i stedet for data/data.js på sidene til
   en kommune med begrenset innsyn.

   Dataene ligger ikke på nettstedet, men i databasen, og hentes med
   innloggingen fra portalen. Portalen sender en kortvarig tilgangsnøkkel
   tilbake via /konto/, som lagrer den i nettleseren (localStorage). Databasen
   (RLS) avgjør om kontoen har en rolle for kommunen. Har den det, lastes
   app.js som for de andre kommunene. Ellers forklarer siden hvorfor
   innholdet ikke vises, og hvordan man logger inn. */
(function () {
  var s = document.currentScript, d = s.dataset;
  var NOKKEL = 'kommunelys-innsyn', FORSOK = 'kommunelys-innsyn-forsok';
  var navn = d.navn, portal = d.portal;

  function les(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  var inn = les(NOKKEL);
  var konto = les('kommunelys-konto');
  var innlogget = konto && konto.epost && Date.now() - konto.tid < 30 * 24 * 3600 * 1000;

  // Via portalen: logger inn om nødvendig, og sender en ny nøkkel tilbake hit.
  function viaPortalen(sti) { return portal + sti + '?tilbake=' + encodeURIComponent(location.href); }

  // Var brukeren logget inn, men nøkkelen er gått ut, hentes en ny uten å
  // spørre. Bare én gang hvert andre minutt, så det aldri går i ring.
  function fornyEllers(vis) {
    var sist = 0;
    try { sist = +sessionStorage.getItem(FORSOK) || 0; } catch (e) {}
    if (innlogget && Date.now() - sist > 120000) {
      try { sessionStorage.setItem(FORSOK, String(Date.now())); } catch (e) {}
      location.replace(viaPortalen('/login'));
    } else vis();
  }

  function el(tag, tekst, attr) {
    var e = document.createElement(tag);
    if (tekst) e.textContent = tekst;
    for (var k in attr || {}) e.setAttribute(k, attr[k]);
    return e;
  }
  function knapp(tekst, href, hoved) { return el('a', tekst, { href: href, class: 'knapp' + (hoved ? ' hoved' : '') }); }
  function epost() { return el('a', d.epost, { href: 'mailto:' + d.epost }); }

  function vis(tittel, avsnitt, knapper) {
    var b = document.getElementById('innsyn');
    b.textContent = '';
    b.append(el('h1', tittel));
    avsnitt.forEach(function (a) {
      var p = el('p');
      p.append.apply(p, a);
      b.append(p);
    });
    var k = el('div', '', { class: 'knapper' });
    k.append.apply(k, knapper);
    b.append(k);
    b.hidden = false;
    document.body.classList.add('laast');
  }

  var andre = knapp('Se de andre kommunene', '../');

  // Teksten er prosjekteiers (8.10.2026).
  var TITTEL = 'Denne kommunen har begrenset innsyn';
  var BEGRENSET = 'Tilgang til denne kommunen er begrenset til inviterte brukere foreløpig.';
  function spor() { return ['Mener du at du bør ha tilgang? Skriv til ', epost()]; }

  function utenInnlogging() {
    vis(TITTEL, [[BEGRENSET], spor()],
      [knapp('Logg inn', viaPortalen('/login'), true), andre]);
  }

  function utenTilgang() {
    vis(TITTEL, [[(innlogget ? 'Du er logget inn som ' + konto.epost + '. ' : '') + BEGRENSET], spor()], [andre]);
  }

  function ikkeKlar() {
    vis('Sidene for ' + navn + ' er ikke klare ennå', [
      ['Dataene for ' + navn + ' er ikke bygget ennå. Prøv igjen senere.']
    ], [andre]);
  }

  function feil() {
    document.getElementById('lastefeil').hidden = false;
  }

  // Én fil fra databasen, eller null om den ikke finnes. Brukes også av app.js
  // (hentDetaljer), som legger ?v= på adressen; den trengs ikke her.
  function hent(fil) {
    var q = '?kommune=' + encodeURIComponent(d.kommune) + '&fil=' + encodeURIComponent(fil.split('?')[0]);
    return fetch(d.api + '/rest/v1/rpc/nettsted_fil' + q, {
      headers: { apikey: d.nokkel, Authorization: 'Bearer ' + inn.nokkel, 'Accept-Profile': 'portal' },
      cache: 'no-cache'
    }).then(function (r) {
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    }).then(function (t) { return t == null ? null : JSON.parse(t); });
  }

  // Nøkkelen må gjelde minst ett minutt til.
  if (!inn || !inn.nokkel || !(inn.utloper * 1000 > Date.now() + 60000)) {
    fornyEllers(utenInnlogging);
    return;
  }

  hent('data.json').then(function (data) {
    if (!data) return ikkeKlar();
    window.S = data.S;
    window.VOT = data.VOT;
    window.HENT_FIL = hent;
    var app = el('script', '', { src: d.app });
    app.onload = function () { if (!window.KL_KLAR) feil(); };
    app.onerror = feil;
    document.body.append(app);
  }).catch(function (e) {
    if (e.status === 401) {
      // Nøkkelen godtas ikke lenger, for eksempel etter utlogging et annet sted.
      try { localStorage.removeItem(NOKKEL); } catch (x) {}
      fornyEllers(utenInnlogging);
    } else if (e.status === 403) utenTilgang();
    else feil();
  });
})();
