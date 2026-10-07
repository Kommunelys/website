/* Kommunelys. Bygges av bygg/bygg_nettsted.py.
   Dataene ligger i data/data.js: S (saker, møter, utvalg, kommunestyret og
   de folkevalgte) og VOT (voteringer per møte). Ingenting her er skrevet for
   hånd om enkeltsaker eller enkeltpersoner, og ingen kommune nevnes ved navn:
   det som er særegent for kommunen, står i S.kommune (kommuner/<kommune>.json). */
const TODAY=S.today, AAR=S.aar, K=S.kommune;
// Utvalgskoden for kommunestyret i portalen. Står bare i S.kommune når den ikke er «KS».
const KSK=K.kommunestyre_kode||'KS';
// Nivåene (ADR-021): en kommune kan publiseres før stemmene eller oppmøtet kan
// leses sikkert fra protokollene. Da sier sidene det, i stedet for å vise tomt.
const IKKE_STEMMER=!!VOT.ikke_dekket, IKKE_OPPMOTE=!!S.ikke_oppmote;
const MANGLER_STEMMER='<p class="merk">Stemmene vises ikke for denne kommunen ennå, fordi vi ikke kan lese dem sikkert fra protokollene. Protokollene ligger i innsynsportalen.</p>';
const MANGLER_OPPMOTE='<p class="merk">Oppmøtet vises ikke for denne kommunen ennå, fordi vi ikke kan lese det sikkert fra møteprotokollene.</p>';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const MON=['jan','feb','mar','apr','mai','jun','jul','aug','sep','okt','nov','des'];
const MONL=['Januar','Februar','Mars','April','Mai','Juni','Juli','August','September','Oktober','November','Desember'];
const dd=d=>`${+d.slice(8,10)}. ${MON[+d.slice(5,7)-1]}`;
const ddl=d=>`${+d.slice(8,10)}. ${MONL[+d.slice(5,7)-1].toLowerCase()}`;
const ddn=d=>d?`${d.slice(8,10)}.${d.slice(5,7)}`:'';
const dato=d=>d?`${d.slice(8,10)}.${d.slice(5,7)}.${d.slice(0,4)}`:'';
const isFut=d=>(d||'').slice(0,10)>=TODAY;
const antall=(n,en,flere)=>`${n} ${n===1?en:flere}`;
const PNAME=S.partier;
const PORDER_ALLE=["AP","SP","H","R","INP","FRP","SV","PP","V","UAVH"];
const SPECTRUM_ALLE=["R","SV","AP","SP","UAVH","INP","PP","V","H","FRP"];
const ordne=(rekke,finnes)=>[...rekke.filter(p=>finnes.includes(p)),...finnes.filter(p=>!rekke.includes(p)).sort()];
const SEATS=S.ks.seter;
const KSN=Object.values(SEATS).reduce((a,b)=>a+b,0);
const PORDER=ordne(PORDER_ALLE,Object.keys(SEATS));
const SPECTRUM=ordne(SPECTRUM_ALLE,Object.keys(SEATS));
const pc=p=>`var(--p-${p},var(--muted))`;
const UTN={...(S.utvnavn||{})};Object.entries(S.utvalg).forEach(([n,c])=>{if(c&&!UTN[c])UTN[c]=n});
const SHORTN=K.utvalg_kort;
const utName=c=>SHORTN[c]||UTN[c]||c;
document.querySelectorAll('.aar').forEach(e=>e.textContent=AAR);

const PS=S.cases.filter(c=>c.typ==='PS'&&!c.formal);
const ALL=S.cases.filter(c=>!c.formal);
ALL.forEach(c=>{c.next=c.st.find(x=>isFut(x.date))||null;c.last=c.st.filter(x=>!isFut(x.date)).pop()||null;c.first=c.st[0]});
const SAK_FOR={},STEG={},SAK_ID={};S.cases.forEach(c=>{SAK_ID[c.id]=c;c.st.forEach(x=>{SAK_FOR[x.hid]=c;STEG[x.hid]=x})});
// Adressen til saksiden for en behandling.
const sakUrl=hid=>SAK_FOR[hid]?`#sak/${SAK_FOR[hid].id}`:'#saker';
const stCls={"Til kommunestyret":"ks","Til behandling":"tb","Vedtatt i kommunestyret":"ok","Behandlet":"bh","Venter på protokoll":"vp","Protokoll ikke publisert":"bh","Unntatt offentlighet":"bh"};
const stPill=s=>`<span class="st ${stCls[s]||'bh'}">${s}</span>`;
/* Sammendrag fra KI (c.a) vises bare når det har bestått kontrollene i bygget. */
const tittel=c=>c.a?c.a.tk:c.t;
const sokTekst=c=>(c.t+' '+(c.a?`${c.a.tk} ${c.a.sum}`:'')).toLowerCase();
// Til kontaktskjemaet på Om-siden når det er satt opp, ellers til GitHub.
const meldUrl=c=>S.skjema?`../om/?sak=${encodeURIComponent(`${(c.first||c.st[0]).nr} ${c.t}`)}&lenke=${encodeURIComponent(location.origin+location.pathname+'#sak/'+c.id)}#kontakt`:`${S.meld}?title=${encodeURIComponent('Feil i sammendraget: '+(c.first||c.st[0]).nr)}&body=${encodeURIComponent(`Sak: ${c.t}\nSaksnummer: ${(c.first||c.st[0]).nr}\n\nHva er feil?\n`)}`;
const ut=(u,t)=>`<a href="${u}" target="_blank" rel="noopener">${t}</a>`;
function oppsummering(c){
  if(!c.a)return c.typ==='PS'&&!c.formal?'<p class="liten muted">Ingen sammendrag ennå. Les dokumentene i lenkene under.</p>':'';
  const a=c.a;
  return `<div class="ai"><span class="ki">KI-sammendrag</span><p>${esc(a.sum)}</p>${a.bet?`<p><b>Hva betyr det?</b> ${esc(a.bet)}</p>`:''}${a.uen?`<p><b>Uenigheten:</b> ${esc(a.uen)}</p>`:''}
   <p class="aikilde">Skrevet av ${esc(a.modell)} ut fra ${a.kilder.map(k=>ut(k.url,esc(k.tittel))).join(', ')}. Dokumentene gjelder. ${ut(meldUrl(c),'Meld fra om feil')}</p></div>`;
}
// Saksgangen på én linje med korte navn: «Helse og omsorg › Formannskapet › Kommunestyret».
const utvKort=sc=>(K.utvalg_liste||{})[sc]||utName(sc);
const stiSteg=c=>{const seen=[];c.st.forEach(x=>{if(!seen.length||seen[seen.length-1].sc!==x.sc)seen.push(x)});return seen};
function pathHtml(c){
  return `<span class="sti">${stiSteg(c).map(x=>x===c.next?`<b title="Neste: ${esc(utName(x.sc))} ${ddn(x.date)}">${esc(utvKort(x.sc))}</b>`:`<span title="${esc(utName(x.sc))} ${ddn(x.date)}">${esc(utvKort(x.sc))}</span>`).join(' › ')}</span>`;
}
/* Utvalget med fullt navn, merket etter nivå: kommunestyret, formannskapet,
   hovedutvalgene, og rådene og resten. Nøytrale farger, ikke fargetoner, så
   de ikke forveksles med partifargene (ADR-016). */
const nivaa=sc=>sc===KSK?'ks':sc==='FS'?'fs':(K.hovedutvalg||[]).includes(sc)?'hu':'andre';
const utvMerke=sc=>`<span class="utv ${nivaa(sc)}">${esc(utName(sc))}</span>`;

/* ---------- FOLKEVALGTE OG STEMMER ---------- */
const FOLK=S.folk||[];const PERS={},PID={};FOLK.forEach(p=>{PERS[p.n]=p;PID[p.id]=p});
const plink=n=>PERS[n]?`<a href="#person/${PERS[n].id}">${esc(n)}</a>`:esc(n);
const RANG=K.rekkefolge;
const rang=u=>{const i=RANG.indexOf(u);return i<0?50:i};
const ROLLE_KS={Leder:'ordfører',Nestleder:'varaordfører',Medlem:'fast medlem',Varamedlem:'varamedlem'};
const ROLLE={Leder:'leder',Nestleder:'nestleder',Medlem:'medlem',Varamedlem:'varamedlem'};
const rolle=(u,r)=>(u===KSK?ROLLE_KS:ROLLE)[r]||(r?String(r).toLowerCase():'rolle ikke oppgitt');
const fast=v=>!!v.r&&v.r!=='Varamedlem';
const rolleRang=r=>({Leder:0,Nestleder:1,Medlem:2}[r]??3);
const partiLenke=p=>S.partisider&&S.partisider[p]?ut(S.partisider[p].url,esc(S.partisider[p].tekst)):'';
const party=n=>VOT.parti[n]||'?';
const ALLEV=[];
VOT.moter.forEach(m=>m.saker.forEach(s=>s.v.forEach(v=>{v.id=`${s.hid}-${v.nr}`;v.sak=s.nr;v.hid=s.hid;v.dato=m.date;v.usc=m.sc;ALLEV.push(v)})));
const voteOf=(v,n)=>v.f&&v.f.includes(n)?'for':v.m&&v.m.includes(n)?'mot':null;
function groupSide(v){const c={};v.f.forEach(n=>{const p=party(n);(c[p]=c[p]||{f:0,m:0}).f++});v.m.forEach(n=>{const p=party(n);(c[p]=c[p]||{f:0,m:0}).m++});const o={};for(const p in c)o[p]=c[p].f>=c[p].m?'for':'mot';return o}
const SIDES=new Map(ALLEV.filter(v=>!v.holdt&&!v.en).map(v=>[v.id,groupSide(v)]));
const omstridt=v=>!v.holdt&&!v.en&&v.nfor>0&&v.nmot>0;
// Saksprotokollen for én behandling. Den gjelder når protokollen er selvmotsigende.
const protFor=hid=>{const c=SAK_FOR[hid],x=c&&c.st.find(x=>x.hid===hid);return x&&x.prot};
// Ved alternativ votering gjelder «vedtatt» ett av forslagene, ikke voteringen som helhet.
const resTxt=v=>v.vinner?`Forslag ${v.vinner} vedtatt`:v.res==='vedtatt'?'Vedtatt':'Falt';
const HOLDT=ALLEV.filter(v=>v.holdt).length;
const MED_STEMMER=new Set(ALLEV.filter(v=>!v.holdt&&!v.en).map(v=>v.hid));
const FORSL={};ALLEV.forEach(v=>{if(!v.holdt&&v.stiller)FORSL[v.stiller]=(FORSL[v.stiller]||0)+1});
FOLK.forEach(p=>{p.m=p.verv.reduce((a,v)=>a+v.m,0);p.f=FORSL[p.n]||0});
function stemmeStat(n){
  const p=party(n);
  const mine=ALLEV.filter(v=>!v.holdt&&!v.en&&voteOf(v,n));
  const omst=mine.filter(omstridt);
  let maj=0;const brk=[];
  omst.forEach(v=>{const s=voteOf(v,n);if(s===(v.res==='vedtatt'?'for':'mot'))maj++;const g=SIDES.get(v.id)[p];if(g&&g!==s)brk.push(v)});
  return {mine,omst,maj,brk,forslag:ALLEV.filter(v=>!v.holdt&&v.stiller===n)};
}

/* ---------- OVERSIKT ---------- */
/* Forsiden svarer på tre spørsmål i hvert sitt kort: hva skal skje, hva ble
   bestemt, og hvordan ble det stemt. Under kortene: kommunestyret. Ingen
   nøkkeltall; de hjelper ikke innbyggeren med å forstå hva kommunen gjør.
   Kortene viser lite og lenker videre til hele listen. */
const meetings=S.meetings;
const upcoming=meetings.filter(m=>isFut(m.date));
const nextM=upcoming[0];
const tilB=PS.filter(c=>c.next);
const RAD=K.rad;
const UKEDAG=['søndag','mandag','tirsdag','onsdag','torsdag','fredag','lørdag'];
const naar=d=>`${UKEDAG[new Date(d.slice(0,10)+'T12:00').getDay()]} ${ddl(d)}`;
const sakLenke=(c,hid)=>`<a class="t" href="${sakUrl(hid)}">${esc(tittel(c))}</a>`;
const smaa=s=>s.charAt(0).toLowerCase()+s.slice(1);
/* Saker gruppert per møte: «Formannskapet onsdag 8. oktober», med de første sakene. */
function moteGrupper(saker,steg,maks,sorter){
  const per=new Map();
  saker.forEach(c=>{const x=steg(c);if(!x)return;if(!per.has(x.mid))per.set(x.mid,{x,saker:[]});per.get(x.mid).saker.push(c)});
  return [...per.values()].sort(sorter).slice(0,maks);
}
function moteHtml(g,vis,ekstra,mer){
  return `<div class="mote-gr"><h3><a href="#mote/${g.x.mid}">${esc(utName(g.x.sc))}</a> <span class="muted">${naar(g.x.date)}</span></h3>
    <ul class="saksliste">${g.saker.slice(0,vis).map(c=>`<li>${sakLenke(c,g.x.hid)}${ekstra?ekstra(c,g):''}</li>`).join('')}</ul>
    ${g.saker.length>vis?`<p class="liten">${mer(g)}</p>`:''}</div>`;
}

/* Hva skal skje: de neste politiske møtene og sakene på sakslisten. Råd som
   bare gir uttalelse, hoppes over; saken vises under neste politiske møte. */
(function(){
  const steg=c=>c.st.find(x=>isFut(x.date)&&!RAD.includes(x.sc));
  const gr=moteGrupper(tilB,steg,2,(a,b)=>a.x.date.localeCompare(b.x.date)||(b.x.sc===KSK)-(a.x.sc===KSK));
  let h=gr.map(g=>moteHtml(g,3,
    (c,g)=>c.ks&&g.x.sc!==KSK?' <span class="liten muted">· skal videre til kommunestyret</span>':'',
    g=>`<a href="#saker/pa-vei" data-go="saker" data-fane="pa-vei" data-ut="${g.x.sc}">${antall(g.saker.length-3,'sak','saker')} til i dette møtet</a>`)).join('');
  const ksM=upcoming.find(m=>m.sc===KSK);
  if(ksM&&!gr.some(g=>g.x.mid===ksM.id))
    h+=`<p class="liten muted">Kommunestyret møtes ${naar(ksM.date)}.${ksM.nps?` ${antall(ksM.nps,'politisk sak','politiske saker')} står på sakslisten.`:' Sakslisten er ikke publisert ennå.'}</p>`;
  $('paavei').innerHTML=h||'<p class="muted">Ingen saker står på sakslisten til et kommende møte.</p>';
})();

/* Hva ble bestemt: de tre siste avgjørelsene med protokoll, høyst to per møte.
   De siste 45 dagene kommer kommunestyret først, så formannskapet, så resten. */
const venter=PS.filter(c=>c.status==='Venter på protokoll'&&c.last&&!RAD.includes(c.last.sc));
(function(){
  const nylig=c=>(Date.parse(TODAY)-Date.parse(c.last.date.slice(0,10)))/864e5<=45;
  const vekt=c=>nylig(c)?({KS:0,FS:1}[c.last.sc]??2):3;
  const avgjort=PS.filter(c=>['Vedtatt i kommunestyret','Behandlet'].includes(c.status)&&c.last&&c.last.pub&&!RAD.includes(c.last.sc))
    .sort((a,b)=>vekt(a)-vekt(b)||b.last.date.localeCompare(a.last.date));
  const perMote={},vis=[];
  for(const c of avgjort){const k=c.last.mid;perMote[k]=(perMote[k]||0)+1;if(perMote[k]<=2)vis.push(c);if(vis.length>=3)break}
  const stemmer=c=>{
    const vs=ALLEV.filter(v=>v.hid===c.last.hid);
    if(!vs.length)return '';
    if(vs.every(v=>v.holdt))return 'stemmene vises ikke';
    if(vs.every(v=>v.en))return 'enstemmig';
    const pub=vs.filter(v=>!v.holdt&&!v.en);
    if(vs.length===1&&!(pub[0].alt&&pub[0].alt.length))return pub[0].nmot?`${pub[0].nfor} mot ${pub[0].nmot} stemmer`:'alle stemte for';
    return antall(vs.length,'avstemning','avstemninger');
  };
  $('nylig').innerHTML=vis.map(c=>{
    const hvor=c.last.sc===KSK?`Vedtatt i kommunestyret ${ddl(c.last.date)}`:`Avgjort i ${smaa(utName(c.last.sc))} ${ddl(c.last.date)}`;
    const st=stemmer(c);
    return `<li>${sakLenke(c,c.last.hid)}${c.a&&c.a.bet?`<p class="bet">${esc(c.a.bet)}</p>`:''}
      <div class="m">${hvor}${st?` · ${st}`:''}${MED_STEMMER.has(c.last.hid)?` · <a href="${sakUrl(c.last.hid)}">hvem stemte hva</a>`:''}</div></li>`}).join('')
    ||'<li class="muted">Ingen avgjørelser med protokoll ennå.</li>';
})();


/* Én setning øverst om hvor ting står akkurat nå. */
$('akkurat').textContent=[
  `Akkurat nå er ${antall(tilB.length,'sak','saker')} på vei til behandling${venter.length?`, og ${venter.length} venter på protokoll`:''}.`,
  nextM?`Neste møte er ${smaa(utName(nextM.sc))} ${naar(nextM.date)}.`:''].filter(Boolean).join(' ');

/* Kommunestyret: halvsirkel og partiliste. Velg et parti for å se hvem som sitter der. */
$('kssub').textContent=`${KSN} representanter ifølge medlemslisten ${dato(S.ks.hentet)}. Velg et parti for å se hvem som sitter der.`;
let ksValgt=null;
(function(){
  const N=KSN,rows=4,R0=60,R1=118,W=260,Hh=130,cx=130,cy=124;
  if(!N)return;
  const radii=[...Array(rows)].map((_,i)=>R0+i*(R1-R0)/(rows-1));
  const tot=radii.reduce((a,b)=>a+b,0);
  const cnt=radii.map(r=>Math.round(N*r/tot));cnt[rows-1]+=N-cnt.reduce((a,b)=>a+b,0);
  const pts=[];radii.forEach((r,i)=>{for(let k=0;k<cnt[i];k++){const a=Math.PI*(1-k/Math.max(cnt[i]-1,1));pts.push({x:cx+r*Math.cos(a),y:cy-r*Math.sin(a),a})}});
  pts.sort((p,q)=>q.a-p.a);
  const cols=[];SPECTRUM.forEach(p=>{for(let i=0;i<SEATS[p];i++)cols.push(p)});
  $('hemi').innerHTML=`<svg viewBox="0 0 ${W} ${Hh+8}" role="img" aria-label="Kommunestyret: ${N} representanter. ${PORDER.map(p=>`${PNAME[p]||p} ${SEATS[p]}`).join(', ')}">${pts.map((p,i)=>`<circle data-p="${cols[i]}" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="7.2" fill="${pc(cols[i])}"><title>${esc(PNAME[cols[i]]||cols[i])}</title></circle>`).join('')}<text x="${cx}" y="${cy-12}" text-anchor="middle" font-weight="750" font-size="28" fill="var(--ink)">${N}</text><text x="${cx}" y="${cy+4}" text-anchor="middle" font-size="11" fill="var(--muted)">representanter</text></svg>`;
  $('seats').innerHTML=PORDER.map(p=>`<tr data-p="${p}" aria-selected="false"><td><button data-p="${p}" aria-controls="ksparti"><span class="dot" style="background:${pc(p)}"></span>${esc(PNAME[p]||p)}</button></td><td class="num">${SEATS[p]}</td></tr>`).join('');
})();
function velgParti(p){
  ksValgt=ksValgt===p?null:p;
  document.querySelectorAll('#hemi circle').forEach(c=>c.classList.toggle('av',!!ksValgt&&c.dataset.p!==ksValgt));
  document.querySelectorAll('#seats tr').forEach(r=>r.setAttribute('aria-selected',String(r.dataset.p===ksValgt)));
  if(!ksValgt){$('ksparti').innerHTML='';return}
  const ks=FOLK.flatMap(x=>x.verv.filter(v=>v.u===KSK&&v.i&&v.p===ksValgt).map(v=>({x,v})));
  const faste=ks.filter(o=>fast(o.v)).sort((a,b)=>rolleRang(a.v.r)-rolleRang(b.v.r)||a.x.n.localeCompare(b.x.n,'nb'));
  const vara=ks.filter(o=>!fast(o.v)).sort((a,b)=>b.v.m-a.v.m||a.x.n.localeCompare(b.x.n,'nb'));
  const li=o=>`<li><a href="#person/${o.x.id}">${esc(o.x.n)}</a>${o.v.r==='Leder'||o.v.r==='Nestleder'?` <small>${rolle(KSK,o.v.r)}</small>`:''}${!fast(o.v)?` <small>${o.v.m?`møtt ${antall(o.v.m,'gang','ganger')}`:'ikke møtt'}</small>`:''}</li>`;
  const lenke=partiLenke(ksValgt);
  $('ksparti').innerHTML=`<div class="partivisning"><div class="hode2"><h3><span class="dot" style="background:${pc(ksValgt)}"></span>${esc(PNAME[ksValgt]||ksValgt)}</h3><span class="liten">${lenke?lenke+' · ':''}<a href="#politikere/${ksValgt}">Alle verv i partiet</a></span></div>
   <div class="kol"><div><h3>Faste representanter (${faste.length})</h3><ul>${faste.map(li).join('')}</ul></div><div><h3>Varamedlemmer (${vara.length})</h3><ul>${vara.map(li).join('')||'<li class="muted">Ingen</li>'}</ul></div></div></div>`;
}
$('ks').addEventListener('click',e=>{const t=e.target.closest('[data-p]');if(t&&(t.tagName==='BUTTON'||t.tagName==='circle'))velgParti(t.dataset.p)});

/* Saksflyt */
(function(){
  const HU=K.hovedutvalg;
  const full=PS.filter(c=>{const s=c.st.map(x=>x.sc);return s.includes(KSK)&&s.includes('FS')&&s.some(x=>HU.includes(x))}).length;
  const fsks=PS.filter(c=>{const s=[...new Set(c.st.map(x=>x.sc))];return s.join()==='FS,KS'}).length;
  const ksAll=PS.filter(c=>c.ks).length;
  // Bare saker som er avgjort; de som fortsatt er til behandling, kan gå videre.
  const avgjort=c=>c.status!=='Til behandling';
  const fsSelv=PS.filter(c=>c.st.some(x=>x.sc==='FS')&&!c.ks&&avgjort(c)).length;
  const huSelv=PS.filter(c=>c.st.some(x=>HU.includes(x.sc))&&!c.st.some(x=>['FS',KSK].includes(x.sc))&&avgjort(c)).length;
  $('flowfact').innerHTML=`I ${AAR} har ${ksAll} saker vært eller skal til kommunestyret. ${fsks} gikk rett fra formannskapet, og ${full} gikk hele veien fra et hovedutvalg via formannskapet. Formannskapet avgjorde ${fsSelv} saker selv, og hovedutvalgene ${huSelv}.`;
})();

$('q0').addEventListener('keydown',e=>{if(e.key==='Enter')go('saker',{q:e.target.value})});

/* ---------- SAKER ---------- */
/* Tre faner etter hvor saken står: avgjort (nyeste først, per måned), på vei
   (per kommende møte) og venter på protokoll (per møte). År og måned gjelder
   datoen saken ble avgjort, eller møtet den skal opp i. Årene er de som finnes
   i dataene, så et nytt år kommer med av seg selv. */
const FANER={avgjort:'Avgjort','pa-vei':'På vei',venter:'Venter på protokoll'};
const FANE_TEKST={avgjort:'nyeste først.','pa-vei':'på sakslisten til kommende møter.',venter:'eldste møte først.'};
let sakFane='avgjort',limit=40,LISTE=[];
const faneFor=c=>c.next?'pa-vei':c.status==='Venter på protokoll'?'venter':'avgjort';
// Møtet som gir saken dato: det neste politiske møtet, ellers det siste.
const sakSteg=c=>c.next?(c.st.find(x=>isFut(x.date)&&!RAD.includes(x.sc))||c.next)
  :([...c.st].reverse().find(x=>!isFut(x.date)&&!RAD.includes(x.sc))||c.last||c.st.at(-1));
const sakDato=c=>(sakSteg(c)||{}).date||'';
const utSet=[...new Set(S.cases.flatMap(c=>c.st.map(x=>x.sc)))].filter(Boolean).sort((a,b)=>utName(a).localeCompare(utName(b),'nb'));
$('fut').innerHTML+=utSet.map(s=>`<option value="${s}">${esc(utName(s))}</option>`).join('');
const TAGS=[...new Set(PS.flatMap(c=>c.tags))].sort((a,b)=>a.localeCompare(b,'nb'));
$('ftema').innerHTML+=TAGS.map(t=>`<option>${esc(t)}</option>`).join('');
const AARENE=[...new Set(ALL.map(c=>sakDato(c).slice(0,4)).filter(Boolean))].sort().reverse();
$('faar').innerHTML+=AARENE.map(a=>`<option>${a}</option>`).join('');
$('fmnd').innerHTML+=MONL.map((m,i)=>`<option value="${String(i+1).padStart(2,'0')}">${m}</option>`).join('');
function filtered(){
  const q=$('q').value.trim().toLowerCase(),u=$('fut').value,tema=$('ftema').value,aar=$('faar').value,mnd=$('fmnd').value;
  return ($('fall').checked?ALL:PS).filter(c=>{const d=sakDato(c);
    return (!q||sokTekst(c).includes(q))&&(!u||c.st.some(x=>x.sc===u))&&(!tema||c.tags.includes(tema))&&(!aar||d.startsWith(aar))&&(!mnd||d.slice(5,7)===mnd)});
}
['q','faar','fmnd','fut','ftema','fall'].forEach(id=>$(id).addEventListener('input',()=>{limit=40;renderList()}));
const sakRad=c=>`<div class="sak"><a href="#sak/${c.id}">
     <span class="t">${esc(tittel(c))}${c.a?`<span class="o">${esc(c.t)}</span>`:''}</span><span class="r">${sakFane==='avgjort'?`<span class="st ${stCls[c.status]||'bh'}">${c.status==='Vedtatt i kommunestyret'?'Vedtatt':c.status}</span>`:''}<span class="mono muted">${ddn(sakDato(c))}</span></span>
     <span class="m">${sakMeta(c)}${c.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</span></a></div>`;
// Under tittelen: utvalget som avgjorde saken, eller møtet den skal opp i,
// med saksnummeret der. Har saken gått gjennom flere utvalg, står veien etter.
function sakMeta(c){
  const x=sakSteg(c)||c.first;
  return `${utvMerke(x.sc)}<span class="mono">${esc(x.nr)}</span>${stiSteg(c).length>1?pathHtml(c):''}`;
}
function renderList(){
  const alle=filtered();
  Object.keys(FANER).forEach(f=>{$('n-'+f).textContent=alle.filter(c=>faneFor(c)===f).length});
  document.querySelectorAll('#saksfaner a').forEach(a=>{if(a.dataset.fane===sakFane)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  const ny=sakFane==='avgjort';
  LISTE=alle.filter(c=>faneFor(c)===sakFane).sort((a,b)=>ny?sakDato(b).localeCompare(sakDato(a)):sakDato(a).localeCompare(sakDato(b)));
  $('count').textContent=`${antall(LISTE.length,'sak','saker')}, ${FANE_TEKST[sakFane]}`;
  $('fanehjelp').innerHTML=sakFane==='venter'?`<div class="grunnlag"><b>Hva betyr «venter på protokoll»?</b> Møtet er holdt, men protokollen er ikke lagt ut i innsynsportalen ennå. Før den kommer, vet vi ikke hva som ble vedtatt eller hvordan det ble stemt. Saken flyttes til Avgjort når protokollen kommer, eller etter 30 dager hvis den ikke kommer.</div>`:'';
  // Avgjorte saker per måned; de andre per møte.
  let h='',gr='';
  LISTE.slice(0,limit).forEach(c=>{const x=sakSteg(c)||{},d=x.date||'';
    const k=ny?d.slice(0,7):`${x.mid}`;
    if(k!==gr){gr=k;h+=ny?`<h2 class="mnd">${d?`${MONL[+d.slice(5,7)-1]} ${d.slice(0,4)}`:'Uten dato'}</h2>`:`<h2 class="mnd"><a href="${moteUrl(x.mid)}">${esc(utName(x.sc))}</a> <span class="muted">${naar(d)} ${d.slice(0,4)}</span></h2>`}
    h+=sakRad(c)});
  $('clist').innerHTML=h||'<p class="muted">Ingen saker passer filtrene.</p>';
  const mb=$('more');mb.hidden=LISTE.length<=limit;mb.textContent=`Vis flere (${LISTE.length-limit} til)`;
}
$('more').addEventListener('click',()=>{limit+=40;renderList()});

/* ---------- MØTER ---------- */
/* Kalender per måned (#moter/2026-10). På brede skjermer et rutenett med én
   kolonne per ukedag, på smale en liste. Hvert møte lenker til møtesiden. */
const MOTE_ID={};meetings.forEach(m=>{MOTE_ID[m.id]=m});
const moteUrl=mid=>MOTE_ID[mid]?`#mote/${mid}`:'';
const mndNaa=TODAY.slice(0,7);
let kalMnd=mndNaa;
const mut=$('mut');
[...new Set(meetings.map(m=>m.sc))].sort((a,b)=>utName(a).localeCompare(utName(b),'nb')).forEach(u=>mut.innerHTML+=`<option value="${u}">${esc(utName(u))}</option>`);
const flyttMnd=(mnd,n)=>{const d=new Date(+mnd.slice(0,4),+mnd.slice(5,7)-1+n,1);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`};
const kl=m=>`kl. ${m.date.slice(11,16)}${m.end?`–${m.end}`:''}`;
function renderMeet(){
  const u=mut.value,ms=meetings.filter(m=>m.date.startsWith(kalMnd)&&(!u||m.sc===u));
  const [aa,mm]=kalMnd.split('-').map(Number);
  $('mtittel').textContent=`${MONL[mm-1]} ${aa}`;
  $('midag').hidden=kalMnd===mndNaa;
  // Rutenettet: uker fra mandag til søndag.
  const forste=(new Date(aa,mm-1,1).getDay()+6)%7,dager=new Date(aa,mm,0).getDate();
  let h='<div class="kal-uke kal-dager">'+['Man','Tir','Ons','Tor','Fre','Lør','Søn'].map(d=>`<span>${d}</span>`).join('')+'</div><div class="kal-uke">';
  for(let i=0;i<forste;i++)h+='<div class="kal-dag tom"></div>';
  for(let d=1;d<=dager;d++){
    const dato=`${kalMnd}-${String(d).padStart(2,'0')}`,dm=ms.filter(m=>m.date.startsWith(dato));
    h+=`<div class="kal-dag${dato===TODAY.slice(0,10)?' idag':''}"><span class="kal-nr">${d}</span>${dm.map(m=>`<a class="kal-m${isFut(m.date)?' fram':''}" href="#mote/${m.id}" title="${esc(utName(m.sc))} ${kl(m)}"><span class="mono">${m.date.slice(11,16)}</span> ${esc(K.utvalg_liste[m.sc]||utName(m.sc))}</a>`).join('')}</div>`;
    if((forste+d)%7===0&&d<dager)h+='</div><div class="kal-uke">';
  }
  for(let i=(forste+dager)%7;i&&i<7;i++)h+='<div class="kal-dag tom"></div>';
  $('kal').innerHTML=h+'</div>';
  // Listen: samme møter, for smale skjermer.
  $('mlist').innerHTML=ms.map(m=>`<a class="mote" href="#mote/${m.id}"><span class="mote-dato"><b>${+m.date.slice(8,10)}.</b> ${UKEDAG[new Date(m.date.slice(0,10)+'T12:00').getDay()].slice(0,3)}</span><span><b>${esc(utName(m.sc))}</b><span class="liten muted">${kl(m)}${m.sted?` · ${esc(renSted(m.sted))}`:''} · ${m.nps?antall(m.nps,'politisk sak','politiske saker'):m.n?antall(m.n,'sak','saker'):'sakslisten er ikke publisert'}</span></span></a>`).join('')
    ||`<p class="muted">Ingen møter i ${MONL[mm-1].toLowerCase()}${u?` i ${esc(smaa(utName(u)))}`:''}.</p>`;
}
const tilMnd=mnd=>{location.hash='#moter/'+mnd};
$('mforr').addEventListener('click',()=>tilMnd(flyttMnd(kalMnd,-1)));
$('mneste').addEventListener('click',()=>tilMnd(flyttMnd(kalMnd,1)));
$('midag').addEventListener('click',()=>tilMnd(mndNaa));
mut.addEventListener('input',renderMeet);

/* ---------- STEMMER ---------- */
/* Hvordan avstemningene vises på saksiden og profilene. Skrevet for folk som
   ikke kjenner møteordningen: «avstemning», ikke «votering», og «forslaget
   saken kom med» foran «innstillingen». */
const pord=ns=>ordne(PORDER_ALLE,[...new Set(ns.map(party))]);
function segBar(v){const seg=ns=>{const c={};ns.forEach(n=>{const p=party(n);c[p]=(c[p]||0)+1});return pord(ns).map(p=>`<span style="flex:${c[p]};background:${pc(p)}" title="${esc(PNAME[p]||p)}: ${c[p]}"></span>`).join('')};
  return `<div class="bar" role="img" aria-label="${v.nfor} stemte for, ${v.nmot} stemte mot">${seg(v.f)}${v.nfor&&v.nmot?'<span class="gap"></span>':''}${v.nmot?`<span style="flex:${v.nmot};display:flex;gap:1px;opacity:.45">${seg(v.m)}</span>`:''}</div>`}
function namesBlock(v){
  const sides=SIDES.get(v.id)||{};
  const grp=(ns,side)=>{const by={};ns.forEach(n=>{(by[party(n)]=by[party(n)]||[]).push(n)});return pord(ns).map(p=>`<div class="pg"><span class="sq" style="background:${pc(p)}"></span><b>${p}</b> ${by[p].map(n=>side&&sides[p]!==side?`<span class="cross" title="Stemte annerledes enn partiet">${plink(n)}</span>`:plink(n)).join(', ')}</div>`).join('')||'<span class="muted">Ingen</span>'};
  const borte=v.borte&&v.borte.length?`<div class="vmeta">Ikke til stede: ${v.borte.map(plink).join(', ')}</div>`:'';
  const brudd=[...v.f.filter(n=>sides[party(n)]&&sides[party(n)]!=='for'),...v.m.filter(n=>sides[party(n)]&&sides[party(n)]!=='mot')].length;
  const merkForklart=brudd?`<div class="vmeta">Uthevet: stemte annerledes enn resten av partiet.</div>`:'';
  if(erAlt(v))return `<div class="names">${v.alt.map(a=>`<div><h4>Stemte for forslag ${esc(a.fs)} (${a.n})</h4>${grp(a.navn,null)}</div>`).join('')}${borte}</div>`;
  // Alle stemte for: navnene står i protokollen, her holder det med tallet.
  if(!v.nmot)return `<div class="names"><p class="liten">Alle ${v.nfor} som stemte, stemte for.</p>${borte}</div>`;
  return `<div class="names"><div><h4 style="color:var(--good)">Stemte for (${v.nfor})</h4>${grp(v.f,'for')}</div><div><h4 style="color:var(--bad)">Stemte mot (${v.nmot})</h4>${grp(v.m,'mot')}</div>${borte}${merkForklart}</div>`}

/* Hva et forslag heter, i vanlige ord. */
const SLAG={forslag:'Forslag','alternative forslag':'Alternativt forslag',tilleggsforslag:'Tilleggsforslag',endringsforslag:'Endringsforslag'};
const erAlt=v=>!!(v.alt&&v.alt.length);
const fra=d=>d.bak?`fra ${d.bak}`:d.parti?`fra ${PNAME[d.parti]||d.parti}`:d.stiller?`fra ${d.stiller}`:'';
const forslagNavn=d=>d.type==='innstilling'?'Forslaget saken kom med':`${SLAG[d.type]||'Forslag'} ${fra(d)}`.trim();
const enNavn=v=>!v.lbl||/innstilling|forslag til vedtak/i.test(v.lbl)?'Forslaget saken kom med':v.lbl;
const typeNavn=v=>v.en?enNavn(v):erAlt(v)?'Valg mellom forslag':forslagNavn(v);
const fremmetAv=d=>d.stiller?`Fremmet av ${plink(d.stiller)}${d.parti?' ('+esc(d.parti)+')':''}.`:'';

/* Ved alternativ votering står forslagene etter hverandre: «… Dette ble satt
   opp mot: 2) Navn (Parti) fremmet følgende alternative forslag: …». De deles
   i hvert sitt avsnitt. */
function formater(t){
  if(!t)return '';
  return t.split(/\s+(?=Dette ble satt opp mot:)|(?<=Dette ble satt opp mot:)\s+|\s+(?=\d\)\s+[A-ZÆØÅ])/).map(formaterDel).join('');
}
/* Nummererte punkter («1.», «2.» i rekkefølge) og kulepunkter («•») blir lister. */
function formaterDel(t){
  t=t.trim();
  if(!t)return '';
  const kule=t.split(/\s*•\s*/);
  if(kule.length>1){const forst=kule.shift();return (forst?`<p>${esc(forst)}</p>`:'')+`<ul>${kule.filter(Boolean).map(d=>`<li>${esc(d)}</li>`).join('')}</ul>`}
  const merker=[];let neste=null;
  for(const m of t.matchAll(/(^|\s)(\d{1,2})\.(?!\d)\s?/g)){
    const n=+m[2];
    if(neste===null||n===neste){merker.push({n,fra:m.index+m[1].length,til:m.index+m[0].length});neste=n+1}
  }
  if(merker.length<2)return `<p>${esc(t)}</p>`;
  const for_=t.slice(0,merker[0].fra).trim();
  const punkter=merker.map((m,i)=>`<li value="${m.n}">${esc(t.slice(m.til,i+1<merker.length?merker[i+1].fra:t.length).trim())}</li>`).join('');
  return (for_?`<p>${esc(for_)}</p>`:'')+`<ol>${punkter}</ol>`;
}

/* «Forslaget saken kom med vant, med 22 mot 16 stemmer.» */
function altVinner(v){
  const d=(v.deler||[]).find(x=>x.fs===v.vinner);
  const vinn=v.alt.find(a=>a.fs===v.vinner),andre=v.alt.filter(a=>a!==vinn);
  const navn=d?forslagNavn(d):`Forslag ${v.vinner}`;
  return `${esc(navn)} vant${vinn&&andre.length?`, med ${vinn.n} mot ${andre.map(a=>a.n).join(' og ')} stemmer`:''}.`;
}
/* Hva saken endte med, regnet ut av avstemningene. Bare fra dataene.
   Forslaget saken kom med (innstillingen) står mot forslagene fremmet i
   møtet: ble innstillingen vedtatt, og ble noe fra møtet vedtatt i tillegg
   eller i stedet? */
const erInnst=v=>v.en?enNavn(v)==='Forslaget saken kom med':v.type==='innstilling';
function utfall(s){
  let iOk=0,iFalt=0,mOk=0,mFalt=0;
  s.v.forEach(v=>{
    if(erAlt(v)&&v.deler){const vinn=v.deler.find(d=>d.fs===v.vinner),har=v.deler.some(d=>d.type==='innstilling');
      if(har){if(vinn&&vinn.type==='innstilling')iOk++;else{iFalt++;mOk++}}else mOk++;return}
    const ok=v.en||v.res==='vedtatt';
    if(erInnst(v))ok?iOk++:iFalt++;else ok?mOk++:mFalt++;
  });
  const n=k=>k===1?'Ett forslag':`${k} forslag`,tall=k=>k===1?'ett':String(k);
  // Forslagene fremmet i møtet, i én setning: hvor mange ble vedtatt, og hvor mange falt.
  const mote=!mOk&&!mFalt?'':!mOk?` ${n(mFalt)} fremmet i møtet falt.`:` ${n(mOk)} fremmet i møtet ble vedtatt${mFalt?`, og ${tall(mFalt)} falt`:''}.`;
  if(!iOk&&!iFalt)return {kort:mOk?'Vedtatt':'Falt',ok:mOk>0,tekst:mote.trim()};
  if(!iFalt&&!mOk)return {kort:mFalt?'Vedtatt uendret':'Vedtatt',ok:true,tekst:`Forslaget saken kom med ble vedtatt${mFalt?' uten endringer':''}.${mote}`};
  if(!iFalt)return {kort:'Vedtatt med endringer',ok:true,tekst:`Forslaget saken kom med ble vedtatt, med endringer.${mote}`};
  return {kort:iOk?'Endret i møtet':mOk?'Et annet forslag vedtatt':'Falt',ok:mOk>0,tekst:`${iOk?'Deler av forslaget saken kom med falt.':'Forslaget saken kom med falt.'}${mote}`};
}
function sakSvar(s){
  const org=utName(s.m.sc),nh=s.v.filter(v=>v.holdt).length;
  const holdtTxt=nh?` Stemmene vises ikke for ${nh===1?'én av avstemningene':`${nh} av avstemningene`}.`:'';
  if(s.v.length===1){
    const v=s.v[0];
    if(v.holdt)return `${org} stemte over saken, men stemmene vises ikke.`;
    if(v.en)return `${org} vedtok saken. Alle stemte for.`;
    if(erAlt(v))return `${org} valgte mellom ${v.deler&&v.deler.length===2?'to':v.deler?v.deler.length:'flere'} forslag. ${altVinner(v)}`;
    const forslaget=v.type==='innstilling'?'forslaget saken kom med':'ett forslag';
    if(!v.nmot)return `${org} stemte over ${forslaget}. Det ble vedtatt. Alle ${v.nfor} stemte for.`;
    return `${org} stemte over ${forslaget}. Det ble ${v.res==='vedtatt'?'vedtatt':'ikke vedtatt'}: ${v.nfor} stemte for og ${v.nmot} mot.`;
  }
  return `${org} stemte ${s.v.length} ganger. ${utfall(s).tekst}${holdtTxt}`;
}
/* Hvilket punkt en avstemning gjelder, bare når protokollen sier det selv:
   «Nytt punkt 4», «Til pkt 3», eller «2.» først i innstillingen. Partienes
   egne nummer («På vegne av H, V: 18.») er ikke punkter i innstillingen og
   brukes ikke. */
function punkt(t,innst){
  t=t||'';
  const kort=t.slice(0,100);
  // «Pkt 5.7» er et underpunkt i et annet dokument, ikke punkt 5.
  const m=kort.match(/\b(nytt|til)?\s*(?:punkt|pkt)\.?\s*(\d{1,2})\b(?![.,]\d)/i);
  if(m)return (m[1]?m[1].toLowerCase()+' ':'')+'punkt '+m[2];
  // «1.» først gjelder bare punkt 1 hvis punkt 2 ikke følger i samme tekst;
  // ellers er det hele innstillingen.
  const n=innst&&kort.match(/^\s*(\d{1,2})\s*\.\s*(?=[A-ZÆØÅ])/);
  if(!n||new RegExp(`(^|\\s)${+n[1]+1}\\.\\s?\\S`).test(t))return '';
  return 'punkt '+n[1];
}
const forst=t=>t.charAt(0).toUpperCase()+t.slice(1);
// Linjen for én avstemning: hva det ble stemt over.
// Har saken bare én avstemning, gjelder den hele innstillingen, selv om teksten starter med «1.».
function votTittel(v,alene){
  if(erAlt(v)&&v.deler){
    const p=v.deler.map(d=>punkt(d.tekst,d.type==='innstilling'&&!alene)).find(Boolean);
    const navn=v.deler.map((d,i)=>{const t=forslagNavn(d);return i?t.charAt(0).toLowerCase()+t.slice(1):t}).join(' mot ');
    return `${p?forst(p.replace(/^(nytt|til) /,''))+': ':''}${esc(navn)}`;
  }
  const p=punkt(v.tekst,v.type==='innstilling'&&!alene);
  return `${esc(typeNavn(v))}${p?`, ${p}`:''}`;
}
/* Partiene: kommunestyret de siste tolv månedene, rullerende.
   Ett møte er for tynt grunnlag, og utvalgene blandes ikke inn, så tallene
   kan sammenlignes. Alle utvalgene står på profilen til hver person. */
const FRA12=(()=>{const d=new Date(TODAY.slice(0,10)+'T12:00');d.setFullYear(d.getFullYear()-1);return d.toISOString().slice(0,10)})();
const KS12=VOT.moter.filter(m=>m.sc===KSK&&m.date.slice(0,10)>FRA12);
const V=KS12.flatMap(m=>m.saker.flatMap(s=>s.v)).filter(v=>!v.holdt&&!v.en);
const contested=V.filter(v=>v.nfor>0&&v.nmot>0);
(function(){
  const alle=KS12.flatMap(m=>m.saker.flatMap(s=>s.v)),nh=alle.filter(v=>v.holdt).length;
  const nm=alle.filter(v=>(v.merk||[]).length&&!v.holdt&&!v.en&&v.nfor>0&&v.nmot>0).length;
  const tekst=KS12.length?`<b>${esc(utName(KSK))}, siste 12 måneder.</b> ${antall(KS12.length,'møte','møter')} fra ${ddl(KS12[0].date)} ${KS12[0].date.slice(0,4)} til ${ddl(KS12.at(-1).date)} ${KS12.at(-1).date.slice(0,4)}, med ${contested.length} avstemninger der noen stemte imot. Enstemmige avstemninger telles ikke${nh?`, og ${nh} der stemmene ikke vises, er ikke med`:''}.${nm?` I ${nm} av dem er protokollen selvmotsigende, oftest om hvem som møtte. De er tatt med slik navnelistene oppgir dem, og er merket på sakene.`:''}`
    :`Ingen avstemninger i ${esc(utName(KSK).toLowerCase())} de siste 12 månedene.`;
  $('partgrunnlag').innerHTML=IKKE_STEMMER?MANGLER_STEMMER:tekst;
})();
function sortPil(tabell,k,d){document.querySelectorAll(`#${tabell} th[data-k]`).forEach(th=>{if(th.dataset.k===k)th.setAttribute('aria-sort',d>0?'ascending':'descending');else th.removeAttribute('aria-sort')})}
const vlinje=(v,vo,ekstra)=>`<div class="vrow"><span class="muted">${ddn(v.dato)} ${esc(v.usc)}</span><span><a href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a><br><span class="liten muted klipp">${esc(typeNavn(v))}: ${esc(v.lbl)}</span>${ekstra||''}</span><span class="v ${vo||''}">${vo==='for'?'For':vo==='mot'?'Mot':''}</span><span class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></div>`;
function renderHeat(){
  const ps=ordne(PORDER_ALLE,[...new Set(contested.flatMap(v=>Object.keys(SIDES.get(v.id))))]);
  const agree=(a,b)=>{let n=0,k=0;contested.forEach(v=>{const s=SIDES.get(v.id);if(s[a]&&s[b]){n++;if(s[a]===s[b])k++}});return n?k/n:null};
  let h=`<tr><th></th>${ps.map(p=>`<th><span class="sq" style="background:${pc(p)}"></span>${p}</th>`).join('')}</tr>`;
  ps.forEach(a=>{h+=`<tr><th class="rh">${esc(PNAME[a]||a)}</th>`+ps.map(b=>{if(a===b)return `<td style="background:var(--soft);color:var(--muted)">–</td>`;const r=agree(a,b);if(r===null)return '<td class="muted">·</td>';const pct=Math.round(r*100);return `<td title="${a} og ${b} stemte likt i ${pct} %" style="background:color-mix(in srgb,var(--ink) ${Math.max(6,pct)}%,var(--bg));color:${pct>55?'var(--bg)':'var(--ink)'}">${pct}</td>`}).join('')+'</tr>'});
  $('heat').innerHTML=contested.length?h:'<tr><td class="muted">Ingen avstemninger der noen stemte imot.</td></tr>';
  $('close').innerHTML=contested.filter(v=>Math.abs(v.nfor-v.nmot)<=3).map(v=>{const s=SIDES.get(v.id);const cross=[...v.f.filter(n=>s[party(n)]!=='for'),...v.m.filter(n=>s[party(n)]!=='mot')];
    return `<div class="jevn"><div><span><a href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a><br><span class="liten muted">${esc(typeNavn(v))}: ${esc(v.lbl)}</span></span><span><b class="num">${v.nfor} for, ${v.nmot} mot</b> <span class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></span></div>${segBar(v)}<div class="liten muted">${cross.length?'Stemte annerledes enn partiet: '+cross.map(n=>`<span class="cross">${plink(n)} (${party(n)})</span>`).join(', '):'Alle stemte som partiet sitt.'}</div>${(v.merk||[]).map(t=>`<div class="merk">Merknad: ${esc(t)}</div>`).join('')}</div>`}).join('')||'<p class="muted">Ingen avstemninger ble avgjort med tre stemmer eller mindre.</p>';
}

/* ---------- POLITIKERE ---------- */
// To faner: politikerne (#politikere) og partiene (#politikere/partiene).
function visPolFane(f){
  ['politikerne','partiene'].forEach(x=>{$('f-'+x).hidden=x!==f});
  document.querySelectorAll('#polfaner a').forEach(a=>{if(a.dataset.fane===f)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
}
const KORT=K.utvalg_liste;
// Kort navn i listen, fullt navn som verktøytips.
const kort=u=>KORT[u]?`<span title="${esc(utName(u))}">${esc(KORT[u])}</span>`:esc(utName(u));
// Foretaksmøtene har nesten samme medlemmer som kommunestyret; de står på profilene, ikke i listen.
const FORETAK=K.foretak;
const PARTI_I_FOLK=ordne(PORDER_ALLE,[...new Set(FOLK.map(p=>p.p))]);
let fparti=null,fsk='n',fsd=1;
const futv=$('futv');
futv.innerHTML+=[...new Set(FOLK.flatMap(p=>p.verv.filter(v=>v.i).map(v=>v.u)))].filter(u=>!FORETAK.includes(u)).sort((a,b)=>rang(a)-rang(b)||utName(a).localeCompare(utName(b),'nb')).map(u=>`<option value="${u}">${esc(utName(u))}</option>`).join('');
function renderFChips(){$('fchips').innerHTML=['Alle',...PARTI_I_FOLK].map(p=>`<button aria-pressed="${(p==='Alle'&&!fparti)||p===fparti}" data-p="${p}">${p==='Alle'?'Alle partier':`<span class="sq" style="background:${pc(p)}"></span>${esc(PNAME[p]||p)}`}</button>`).join('')}
$('fchips').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;fparti=b.dataset.p==='Alle'?null:b.dataset.p;history.replaceState(null,'','#politikere'+(fparti?'/'+fparti:''));renderFChips();renderFolk()});
['fq','futv'].forEach(id=>$(id).addEventListener('input',renderFolk));
document.querySelector('#ftab thead').addEventListener('click',e=>{const th=e.target.closest('th[data-k]');if(!th)return;const k=th.dataset.k;if(fsk===k)fsd*=-1;else{fsk=k;fsd=(k==='n'||k==='p')?1:-1}renderFolk()});
const vervListe=(p,f)=>p.verv.filter(v=>v.i&&fast(v)===f&&!FORETAK.includes(v.u)).sort((a,b)=>rang(a.u)-rang(b.u)||rolleRang(a.r)-rolleRang(b.r)).map(v=>`${kort(v.u)}${v.r==='Leder'||v.r==='Nestleder'?` <span class="muted">(${rolle(v.u,v.r)})</span>`:''}`).join(', ')||'<span class="muted">–</span>';
function renderFolk(){
  const q=$('fq').value.trim().toLowerCase(),u=futv.value;
  const L=FOLK.filter(p=>(!fparti||p.p===fparti)&&(!q||p.n.toLowerCase().includes(q))&&(!u||p.verv.some(v=>v.i&&v.u===u)))
    .sort((a,b)=>{const A=a[fsk],B=b[fsk];return (typeof A==='string'?A.localeCompare(B,'nb'):A-B)*fsd||a.n.localeCompare(b.n,'nb')});
  sortPil('ftab',fsk,fsd);
  const lenke=fparti&&partiLenke(fparti);
  $('partiboks').innerHTML=fparti?`<div class="partilinje"><b><span class="dot" style="background:${pc(fparti)}"></span>${esc(PNAME[fparti]||fparti)}</b><span>${antall(SEATS[fparti]||0,'plass','plasser')} i kommunestyret</span>${lenke?`<span>${lenke}</span>`:''}</div>`:'';
  $('fcount').textContent=`${antall(L.length,'person','personer')}. Foretaksmøtene er utelatt i listen; de har nesten samme medlemmer som kommunestyret.`;
  document.querySelector('#ftab tbody').innerHTML=L.map(p=>`<tr><td><a href="#person/${p.id}">${esc(p.n)}</a></td><td><span class="dot" style="background:${pc(p.p)}"></span>${esc(p.p)}</td><td>${vervListe(p,true)}</td><td>${vervListe(p,false)}</td><td class="num">${p.m||'–'}</td><td class="num">${p.f||'–'}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">Ingen passer søket.</td></tr>';
}

/* ---------- PROFIL ---------- */
function renderPerson(id){
  const p=PID[id],el=$('person');
  if(!p){el.innerHTML='<div class="ingress"><h1>Fant ikke profilen</h1><p>Navnet står ikke i medlemslistene. Det kan ha blitt endret.</p></div>';return}
  document.title=`${p.n} – ${K.navn} | ${S.merke}`;
  const vv=p.verv.filter(v=>v.i).sort((a,b)=>rang(a.u)-rang(b.u)||fast(b)-fast(a)||utName(a.u).localeCompare(utName(b.u),'nb'));
  const tidl=p.verv.filter(v=>!v.i);
  const ks=vv.find(v=>v.u===KSK);
  const hoved=ks?(fast(ks)?`${rolle(KSK,ks.r)[0].toUpperCase()+rolle(KSK,ks.r).slice(1)} i kommunestyret`:'Varamedlem i kommunestyret'):'Verv i kommunens utvalg';
  const st=stemmeStat(p.n);
  const varaFor=[...new Set(p.verv.flatMap(v=>v.for))].sort((a,b)=>a.localeCompare(b,'nb'));
  const lenke=partiLenke(p.p);
  const rad=v=>`<tr><td>${esc(utName(v.u))}${v.p&&v.p!==p.p?` <span class="liten muted">(for ${esc(PNAME[v.p]||v.p)})</span>`:''}</td><td>${rolle(v.u,v.r)}</td><td class="num">${v.m||'–'}</td><td class="num">${S.mprot[v.u]||'–'}</td></tr>`;
  const pct=st.omst.length?Math.round(st.maj/st.omst.length*100):0;
  const sakLenke=v=>`<a href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a>`;
  el.innerHTML=`<div class="profil"><div class="ingress">
    <p class="parti"><span class="dot" style="background:${pc(p.p)}"></span>${esc(PNAME[p.p]||p.p)}</p>
    <h1>${esc(p.n)}</h1>
    <p class="fakta">${hoved}. ${antall(vv.length,'verv','verv')} ifølge medlemslisten ${dato(S.ks.hentet)}.${lenke?` Partiet: ${lenke}.`:''}</p></div>
    <section><h2>Verv</h2>
      <div class="tw"><table><thead><tr><th>Utvalg</th><th>Rolle</th><th class="num">Møtt</th><th class="num">Møter</th></tr></thead><tbody>${vv.map(rad).join('')}</tbody></table></div>
      ${tidl.length?`<p class="liten muted">Sett i protokollene, men ikke i dagens medlemsliste: ${tidl.map(v=>esc(utName(v.u))).join(', ')}.</p>`:''}
      ${varaFor.length?`<p class="liten">Har møtt som varamedlem for ${varaFor.map(plink).join(', ')}.</p>`:''}
      <p class="liten muted">«Møtt» er antall møter i ${AAR} der navnet står på oppmøtelisten i protokollen. «Møter» er antall møter utvalget har hatt med møteprotokoll. Permisjoner og bytter tidligere i året vises ikke.</p>
    </section>
    <section><h2>Stemmer</h2>
      ${IKKE_STEMMER?MANGLER_STEMMER:st.mine.length?`<p class="oppsum">Har vært med på ${antall(st.mine.length,'avstemning','avstemninger')} med navneliste i ${AAR}.${st.omst.length?` I de ${st.omst.length} der noen stemte imot, var stemmen den samme som flertallets i ${pct} % av tilfellene, og annerledes enn resten av partiet ${antall(st.brk.length,'gang','ganger')}.`:''}</p>`
        :`<p class="oppsum muted">Ingen avstemninger med navneliste i ${AAR}. Når alle stemmer likt, har protokollen ingen navneliste.</p>`}
      ${st.brk.length?`<details${st.brk.length<=8?' open':''}><summary>Stemte annerledes enn partiet (${st.brk.length})</summary><div>${st.brk.map(v=>vlinje(v,voteOf(v,p.n))).join('')}</div></details>`:''}
      ${st.omst.length?`<details><summary>Alle avstemninger der noen stemte imot (${st.omst.length})</summary><div>${st.omst.map(v=>vlinje(v,voteOf(v,p.n))).join('')}</div></details>`:''}
    </section>
    <section><h2>Forslag</h2>
      ${IKKE_STEMMER?MANGLER_STEMMER:st.forslag.length?st.forslag.map(v=>vlinje(v,null)).join(''):`<p class="muted">Ingen forslag med navn i protokollene i ${AAR}.</p>`}
    </section>
    <p class="liten muted mt">Kilder: medlemslisten i innsynsportalen (${dato(S.ks.hentet)}), møteprotokollene og saksprotokollene for ${AAR}.${HOLDT?` ${antall(HOLDT,'avstemning','avstemninger')} der stemmene ikke vises, er ikke med.`:''} Ingen tekst her er skrevet av KI.</p>
  </div>`;
}

/* ---------- SAKEN ---------- */
/* Én side per sak (#sak/<id>): tittel, sammendrag, vedtaket, og saksgangen
   som en tråd fra utvalg til utvalg. I hvert møte står forslagene som en boks
   hver, med utfallet og stemmene per parti. Forslaget som vant, har grønn
   ramme. Navnene og forslagsteksten kan foldes ut. */
const VOT_HID={};VOT.moter.forEach(m=>m.saker.forEach(s=>{VOT_HID[s.hid]={...s,m}}));
const erRad=sc=>RAD.includes(sc);
const datoAar=d=>`${ddl(d)} ${d.slice(0,4)}`;
const perParti=ns=>{const c={};ns.forEach(n=>{const p=party(n);c[p]=(c[p]||0)+1});return pord(ns).map(p=>({p,n:c[p]}))};
const partiTekst=ns=>perParti(ns).map(({p,n})=>`<span><span class="sq" style="background:${pc(p)}"></span>${esc(p)} ${n}</span>`).join('');
const partiStolpe=(ns,maks)=>`<div class="bar" style="max-width:${Math.max(8,Math.round(100*ns.length/maks))}%">${perParti(ns).map(({p,n})=>`<span style="flex:${n};background:${pc(p)}" title="${esc(PNAME[p]||p)}: ${n}"></span>`).join('')}</div>`;
const navnPerParti=ns=>perParti(ns).map(({p})=>`<div class="pg"><span class="sq" style="background:${pc(p)}"></span><b>${esc(p)}</b> ${ns.filter(n=>party(n)===p).map(plink).join(', ')}</div>`).join('');
// Hvor saken står, i én linje øverst.
function fase(c){
  if(c.status==='Unntatt offentlighet')return {cls:'bh',t:c.status};
  const neste=c.st.find(x=>isFut(x.date)&&!erRad(x.sc))||c.next;
  if(neste)return {cls:'tb',t:`Skal opp i ${smaa(utName(neste.sc))} ${datoAar(neste.date)}`};
  const sist=[...c.st].reverse().find(x=>!erRad(x.sc))||c.last;
  if(!sist)return {cls:'bh',t:c.status};
  const hvor=`${smaa(utName(sist.sc))} ${datoAar(sist.date)}`;
  if(c.status==='Vedtatt i kommunestyret')return {cls:'ok',t:`Vedtatt i kommunestyret ${datoAar(sist.date)}`};
  if(c.status==='Venter på protokoll')return {cls:'vp',t:`Behandlet i ${hvor}. Venter på protokoll`};
  if(c.status==='Protokoll ikke publisert')return {cls:'bh',t:`Behandlet i ${hvor}. Protokollen er ikke publisert`};
  return {cls:'ok',t:`Behandlet i ${hvor}`};
}
// Én boks per forslag i en alternativ votering, vinneren først.
function altBokser(v){
  const tot=v.alt.reduce((n,a)=>n+a.n,0);
  return [...v.alt].sort((a,b)=>(b.fs===v.vinner)-(a.fs===v.vinner)).map(a=>{
    const d=(v.deler||[]).find(x=>x.fs===a.fs),vant=a.fs===v.vinner;
    const tekst=d&&d.tekst?`<div class="forslag">${formater(d.tekst)}</div>`:'';
    return `<div class="fboks${vant?' vant':''}"><div class="fboks-topp"><b>${esc(d?forslagNavn(d):'Forslag '+a.fs)}</b><span class="utf${vant?' ok':''}">${vant?'Vant':'Tapte'} · ${a.n}</span></div>
      ${partiStolpe(a.navn,tot)}<div class="lg">${partiTekst(a.navn)}</div>
      <details><summary>Les forslaget og se navnene</summary>${tekst}${d?`<p class="liten">${fremmetAv(d)}</p>`:''}<div class="names">${navnPerParti(a.navn)}</div></details></div>`}).join('');
}
// Én boks for et forslag som ble stemt over for seg. Merknadene står på møtet.
function voteBoks(v,alene){
  const prot=protFor(v.hid),gjelder=prot?`${ut(prot,'Protokollen')} gjelder.`:'Protokollen gjelder.';
  const ok=v.en||v.res==='vedtatt';
  const utf=v.holdt?'<span class="utf">Stemmene vises ikke</span>':v.en?'<span class="utf ok">Enstemmig</span>':`<span class="utf${ok?' ok':''}">${ok?'Vedtatt':'Falt'} ${v.nfor}–${v.nmot}</span>`;
  const navn=!v.holdt&&!v.en;
  const lg=navn?`<div class="lg"><b>For:</b>${partiTekst(v.f)}</div>${v.nmot?`<div class="lg"><b>Mot:</b>${partiTekst(v.m)}</div>`:''}`:'';
  const tekst=!v.en&&v.tekst?`<div class="forslag">${formater(v.tekst)}</div>`:'';
  const fold=tekst||navn?`<details><summary>${navn?'Les forslaget og se navnene':'Les forslaget'}</summary>${tekst}${fremmetAv(v)?`<p class="liten">${fremmetAv(v)}</p>`:''}${navn?namesBlock(v):''}</details>`:'';
  return `<div class="fboks${ok&&!v.holdt?' vant':''}"><div class="fboks-topp"><b>${votTittel(v,alene)}</b>${utf}</div>
    ${navn?segBar(v):''}${lg}${v.holdt?`<p class="why">${esc(v.holdt)} ${gjelder}</p>`:''}${fold}</div>`;
}
// Ett steg i saksgangen: møtet, hva som skjedde der, og forslagene.
function stegHtml(c,x,avgjort){
  const s=VOT_HID[x.hid],vt=x.vt,fram=isFut(x.date);
  let tekst='',bokser='',merk='';
  if(fram)tekst='Står på sakslisten.';
  else if(!x.pub)tekst=x.restr?'Protokollen er skjermet.':(Date.parse(TODAY)-Date.parse(x.date.slice(0,10)))/864e5>30?'Protokollen er ikke publisert.':'Venter på protokoll.';
  else if(s){
    tekst=sakSvar(s);
    // Det som ble vedtatt, først, i rekkefølgen fra møtet. Faller to eller
    // flere forslag, samles de under én linje som kan åpnes.
    const vs=[...s.v].sort((a,b)=>a.nr-b.nr),boks=v=>erAlt(v)&&v.alt.length?altBokser(v):voteBoks(v,s.v.length===1);
    const falt=vs.filter(v=>!erAlt(v)&&!v.en&&!v.holdt&&v.res!=='vedtatt');
    const fold=falt.length>1?falt:[];
    bokser=[...vs.filter(v=>!falt.includes(v)),...falt.filter(v=>!fold.includes(v))].map(boks).join('')
      +(fold.length?`<details class="falt"><summary>${fold.length} forslag falt</summary>${fold.map(boks).join('')}</details>`:'');
    // Samme merknad gjelder ofte alle avstemningene i møtet; den står én gang.
    const m=[...new Set(s.v.flatMap(v=>v.merk||[]))];
    if(m.length)merk=`<div class="merk">${m.map(t=>`<b>Merk:</b> ${esc(t)}`).join(' ')} ${x.prot?`${ut(x.prot,'Protokollen')} gjelder.`:'Protokollen gjelder.'}</div>`;
  }
  else if(vt&&x!==avgjort)tekst=vt.length<=300?`${erRad(x.sc)?'Uttalelse':'Vedtak'}: «${esc(vt)}»`:`<details><summary>${erRad(x.sc)?'Les uttalelsen':'Les vedtaket'}</summary><div class="forslag">${formater(vt)}</div></details>`;
  else if(!vt)tekst='Behandlet. Ingen vedtakstekst i protokollen.';
  if(x===avgjort&&!s)tekst='Vedtaket står øverst.';
  const lenker=[MOTE_ID[x.mid]?`<a href="#mote/${x.mid}">Møtet</a>`:x.murl?ut(x.murl,'Møtet'):'',x.prot?ut(x.prot,'Protokollen'):''].filter(Boolean).join(' · ');
  const cls=fram?' fram':x===avgjort?' slutt':erRad(x.sc)&&!s?' rad':'';
  return `<li class="trad-steg${cls}"><div class="trad-hode"><b>${MOTE_ID[x.mid]?`<a href="#mote/${x.mid}">${esc(utName(x.sc)||x.ut)}</a>`:esc(utName(x.sc)||x.ut)}</b> <span class="muted">· ${datoAar(x.date)}</span></div>
    ${tekst?`<p class="trad-tekst">${tekst}</p>`:''}${merk}${bokser}${lenker?`<p class="liten trad-lenker">${lenker}</p>`:''}</li>`;
}
function renderSak(id){
  const c=SAK_ID[id],el=$('sak');
  if(!c){el.innerHTML='<div class="ingress"><h1>Fant ikke saken</h1><p>Saken finnes ikke i dataene for dette året. <a href="#saker">Se alle sakene</a>.</p></div>';return}
  document.title=`${tittel(c)} – ${K.navn} | ${S.merke}`;
  const f=fase(c),nv=c.st.reduce((n,x)=>n+(VOT_HID[x.hid]?VOT_HID[x.hid].v.length:0),0);
  // Vedtaket: siste behandling med vedtakstekst i et utvalg som avgjør, når saken ikke skal videre.
  const avgjort=c.next?null:[...c.st].reverse().find(x=>!erRad(x.sc)&&x.vt&&x.pub)||null;
  const sv=avgjort&&VOT_HID[avgjort.hid];
  // Formaliasakene har ikke c.last og c.first; saksnummeret tas fra saksgangen.
  const nr=(avgjort||c.last||c.st.at(-1)||{}).nr||'';
  el.innerHTML=`<div class="saksside"><div class="ingress">
    <h1>${esc(tittel(c))}</h1>
    ${c.a?`<p class="muted">Sakstittel: ${esc(c.t)}</p>`:''}
    <p class="sak-status"><span class="st ${f.cls}">${esc(f.t)}</span><span class="muted"><span class="mono">${esc(nr)}</span> · ${antall(c.st.length,'behandling','behandlinger')}${nv?` · ${antall(nv,'avstemning','avstemninger')}`:''}</span></p>
    ${c.tags.length?`<p>${c.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join(' ')}</p>`:''}</div>
    ${oppsummering(c)}
    ${avgjort?`<section class="blokk"><h2>Vedtaket i ${esc(smaa(utName(avgjort.sc)))}</h2>
      ${sv?`<p>${sakSvar(sv)}</p>`:''}<div class="forslag">${formater(avgjort.vt)}</div>
      <p class="liten muted">${avgjort.prot?`${ut(avgjort.prot,'Protokollen')} gjelder.`:'Protokollen gjelder.'}</p></section>`:''}
    <section class="blokk"><h2>Saksgangen</h2>${IKKE_STEMMER&&c.st.some(x=>!isFut(x.date))?MANGLER_STEMMER:''}<ol class="trad">${c.st.map(x=>stegHtml(c,x,avgjort)).join('')}</ol></section>
    <p class="liten muted mt">${[c.doc?ut(c.doc,'Saksframlegget (PDF)'):'',c.att?antall(c.att,'vedlegg','vedlegg')+' i innsynsportalen':''].filter(Boolean).join(' · ')}${c.doc||c.att?'. ':''}Stemmene er lest fra protokollene uten KI, og antall navn er kontrollert mot stemmetallene.</p>
  </div>`;
}

/* ---------- MØTET ---------- */
/* Én side per møte (#mote/<id>): tid, sted og dokumenter, og sakene på
   sakslisten med én setning hver og hva som ble bestemt. */
const SAKER_MOTE={};S.cases.forEach(c=>c.st.forEach(x=>{(SAKER_MOTE[x.mid]=SAKER_MOTE[x.mid]||[]).push({c,x})}));
function moteStatus(m){
  if(isFut(m.date))return m.n?{cls:'tb',t:'Kommende møte'}:{cls:'tb',t:'Kommende møte. Sakslisten er ikke publisert ennå'};
  if(m.docs.some(d=>d.ty==='MP'))return {cls:'ok',t:'Protokollen er publisert'};
  return (Date.parse(TODAY)-Date.parse(m.date.slice(0,10)))/864e5>30?{cls:'bh',t:'Protokollen er ikke publisert'}:{cls:'vp',t:'Venter på protokoll'};
}
// Hva som ble bestemt i saken i dette møtet, kort.
function moteUtfall(x){
  const s=VOT_HID[x.hid];
  if(!s)return '';
  const vs=s.v.filter(v=>!v.holdt);
  if(!vs.length)return '<span class="utf">Stemmene vises ikke</span>';
  if(vs.every(v=>v.en))return '<span class="utf ok">Enstemmig</span>';
  const u=utfall(s),en=vs.length===1?vs[0]:null;
  const tall=en&&!en.en?(erAlt(en)?`${en.alt.find(a=>a.fs===en.vinner)?.n??''}–${en.alt.filter(a=>a.fs!==en.vinner).map(a=>a.n).join('–')}`:`${en.nfor}–${en.nmot}`):'';
  return `<span class="utf${u.ok?' ok':''}">${esc(u.kort)}${tall?` ${tall}`:''}</span>`;
}
function moteSak({c,x},m){
  const videre=c.st.find(y=>y.date>x.date&&!erRad(y.sc));
  const mer=[videre?`Videre til ${smaa(utName(videre.sc))}${isFut(videre.date)?` ${ddl(videre.date)}`:''}`:'',c.st.length>1?pathHtml(c):''].filter(Boolean).join(' · ');
  return `<li class="mote-sak"><div class="mote-sak-topp"><span class="mono muted">${esc(x.nr)}</span>${isFut(m.date)?'':moteUtfall(x)}</div>
    <a class="t" href="#sak/${c.id}">${esc(tittel(c))}</a>${c.a?`<span class="o">${esc(c.t)}</span>`:''}
    ${c.a&&c.a.bet?`<p><span class="ki">KI</span> ${esc(c.a.bet)}</p>`:''}
    ${mer?`<p class="liten muted">${mer}</p>`:''}</li>`;
}
function renderMote(id){
  const m=MOTE_ID[id],el=$('mote');
  if(!m){el.innerHTML='<div class="ingress"><h1>Fant ikke møtet</h1><p>Møtet finnes ikke i dataene for dette året. <a href="#moter">Se kalenderen</a>.</p></div>';return}
  document.title=`${utName(m.sc)} ${ddl(m.date)} – ${K.navn} | ${S.merke}`;
  $('motetilbake').href='#moter/'+m.date.slice(0,7);
  const st=moteStatus(m),dok=t=>m.docs.find(d=>d.ty===t);
  const alle=(SAKER_MOTE[m.id]||[]).sort((a,b)=>{const ka=_saksnr(a.x.nr),kb=_saksnr(b.x.nr);return ka[0]-kb[0]||ka[1]-kb[1]});
  const pol=alle.filter(o=>o.c.typ==='PS'&&!o.c.formal),andre=alle.filter(o=>!pol.includes(o));
  const lenker=[dok('MI')?ut(dok('MI').u,'Møteinnkallingen (PDF)'):'',dok('MP')?ut(dok('MP').u,'Møteprotokollen (PDF)'):'',ut(m.url,'Møtet i innsynsportalen')].filter(Boolean).join(' · ');
  el.innerHTML=`<div class="ingress"><h1>${esc(utName(m.sc))}</h1>
    <p class="mote-fakta"><b>${forst(UKEDAG[new Date(m.date.slice(0,10)+'T12:00').getDay()])} ${datoAar(m.date)}, ${kl(m)}</b>${m.sted||m.rom?`<br>${stedTekst(m)}`:''}</p>
    <p><span class="st ${st.cls}">${esc(st.t)}</span></p>
    <p class="liten">${lenker}</p></div>
    <section class="blokk"><h2>${isFut(m.date)?'Sakene som skal opp':'Sakene og hva som ble bestemt'}</h2>
      ${pol.length?`<ol class="mote-saker">${pol.map(o=>moteSak(o,m)).join('')}</ol>`:`<p class="muted">${m.n?'Ingen politiske saker på sakslisten.':'Sakslisten er ikke publisert ennå.'}</p>`}
      ${IKKE_STEMMER&&!isFut(m.date)&&pol.length?MANGLER_STEMMER:''}
      ${andre.length?`<details class="falt"><summary>${antall(andre.length,'annen sak','andre saker')}: referater, orienteringer og formalia</summary><ol class="mote-saker">${andre.map(o=>moteSak(o,m)).join('')}</ol></details>`:''}
    </section>
    <section class="blokk"><h2>Om ${esc(smaa(utName(m.sc)))}</h2>
      ${oppgave(m.sc)?`<p>${esc(forst(oppgave(m.sc)))}.</p>`:''}
      ${!isFut(m.date)&&m.opp?oppmoteHtml(m):!isFut(m.date)&&IKKE_OPPMOTE?MANGLER_OPPMOTE:''}
      <details class="falt"><summary>Hvem sitter i ${esc(smaa(utName(m.sc)))} i dag</summary>${medlemHtml(m.sc)}</details>
      <p class="liten"><a href="#hvem-bestemmer/${encodeURIComponent(m.sc)}">Alle utvalgene</a></p>
    </section>`;
}
/* Sted og rom er fritekst i portalen. Ved befaringer står ruten i begge
   («Skolen/Barnehagen/Rådhuset» og «Skolen/Barnehagen/Møterommet»), og noen
   ganger står tidsplanen i rommet. Det som er likt, vises én gang, og en
   tidsplan står på egen linje. */
const renSted=t=>(t||'').replace(/\s*\/\s*/g,' / ').trim();
function stedTekst(m){
  const s=renSted(m.sted),r=renSted(m.rom);
  if(!r||r===s)return esc(s);
  if(!s)return esc(r);
  const sd=s.split(' / '),rd=r.split(' / ');let i=0;
  while(i<sd.length-1&&i<rd.length-1&&sd[i]===rd[i])i++;
  if(i)return esc(`${s}, ${rd.slice(i).join(' / ')}`);
  return /\d/.test(r)?`${esc(s)}<br><span class="liten">${esc(r)}</span>`:esc(`${s}, ${r}`);
}
// Hvem som møtte, fra møteprotokollen. Samme regler som for medlemmene: navn
// bare for dem som er valgt for et parti, og ingen navn for rådene.
function oppmoteHtml(m){
  const o=m.opp,tot=o.navn.length+o.andre,vara=o.navn.filter(p=>p.f==='Varamedlem').length;
  const mp=m.docs.find(d=>d.ty==='MP'),gjelder=mp?`${ut(mp.u,'Møteprotokollen')} gjelder.`:'Møteprotokollen gjelder.';
  const avvik=o.avvik?`<p class="merk">Oppmøtelisten stemmer ikke helt med stemmene i protokollen. ${gjelder}</p>`:'';
  if(RAD.includes(m.sc))return `<p>${forst(antall(tot,'person','personer'))} møtte, ifølge møteprotokollen.</p>${avvik}`;
  const liste=[...o.navn].sort((a,b)=>rolleRang(a.f)-rolleRang(b.f)||rang2(a.p)-rang2(b.p)||a.n.localeCompare(b.n,'nb'));
  const linje=p=>`<li><span class="dot" style="background:${pc(p.p)}"></span>${plink(p.n)} <span class="muted">${esc(p.p)}${p.f==='Leder'||p.f==='Nestleder'?`, ${rolle(m.sc,p.f)}`:''}${p.f==='Varamedlem'?`, vara${p.vf?` for ${esc(p.vf)}`:''}`:''}</span></li>`;
  return `<details class="falt"${o.avvik?' open':''}><summary>Hvem møtte: ${tot}${vara?`, av dem ${antall(vara,'varamedlem','varamedlemmer')}`:''}</summary>
    ${liste.length?`<ul class="medl">${liste.map(linje).join('')}</ul>`:''}
    ${o.andre?`<p class="liten muted">${forst(antall(o.andre,'person','personer'))}${o.navn.length?' til':''} er ikke valgt for et parti og vises ikke.</p>`:''}
    <p class="liten muted">Ifølge møteprotokollen.</p>${avvik}</details>`;
}
// «PS 13/2026» -> [13, 2026] for sortering.
const _saksnr=nr=>{const t=(nr||'').match(/(\d+)\/(\d+)/);return t?[+t[2],+t[1]]:[0,0]};

/* ---------- UTVALGENE ---------- */
/* Hva hvert utvalg gjør, når det møtes og hvem som sitter der, fra
   medlemslisten. Som på profilene vises bare de som er valgt for et parti, med
   navn; de andre telles. Rådene har mange medlemmer som ikke er valgt for et
   parti, så der vises ingen navn. Brukes under Hvem bestemmer og på møtesiden. */
const ORGAN={};K.organer.forEach(o=>{ORGAN[o.kode]=o});
const oppgave=sc=>{const o=ORGAN[sc];if(!o||!o.oppgave)return '';return sc===KSK?`${KSN} representanter, ${o.oppgave}`:o.oppgave};
function medlemHtml(sc){
  if(RAD.includes(sc))return '<p class="liten muted">Rådene har medlemmer fra organisasjoner og grupper, og mange er ikke valgt for et parti. Medlemmene vises derfor ikke her.</p>';
  const ms=FOLK.flatMap(p=>p.verv.filter(v=>v.u===sc&&v.i).map(v=>({p,v})));
  const faste=ms.filter(o=>fast(o.v)).sort((a,b)=>rolleRang(a.v.r)-rolleRang(b.v.r)||rang2(a.v.p)-rang2(b.v.p)||a.p.n.localeCompare(b.p.n,'nb'));
  const tot=(S.medl||{})[sc]||{faste:faste.length,vara:0};
  if(!tot.faste)return '<p class="liten muted">Utvalget står ikke i medlemslisten.</p>';
  const andre=tot.faste-faste.length;
  return `<ul class="medl">${faste.map(o=>`<li><span class="dot" style="background:${pc(o.v.p)}"></span><a href="#person/${o.p.id}">${esc(o.p.n)}</a> <span class="muted">${esc(o.v.p)}${o.v.r==='Leder'||o.v.r==='Nestleder'?`, ${rolle(sc,o.v.r)}`:''}</span></li>`).join('')}</ul>
    <p class="liten muted">${andre>0?`${forst(antall(andre,'fast medlem','faste medlemmer'))}${faste.length?' til':''} er ikke valgt for et parti og vises ikke. `:''}${tot.vara?`${forst(antall(tot.vara,'varamedlem','varamedlemmer'))}. `:''}Fra medlemslisten ${dato(S.ks.hentet)}.</p>`;
}
const rang2=p=>{const i=PORDER_ALLE.indexOf(p);return i<0?99:i};
function utvalgHtml(sc){
  const ms=meetings.filter(m=>m.sc===sc),neste=ms.find(m=>isFut(m.date)),sist=[...ms].reverse().find(m=>!isFut(m.date)),o=oppgave(sc);
  const mote=[neste?`Neste møte: <a href="#mote/${neste.id}">${naar(neste.date)}</a>`:'',sist?`Siste møte: <a href="#mote/${sist.id}">${ddl(sist.date)}</a>`:'',antall(ms.length,'møte','møter')+` i ${AAR}`].filter(Boolean).join(' · ');
  return `<details class="utvalg" id="utvalg-${sc}"><summary><b>${esc((ORGAN[sc]||{}).navn||utName(sc))}</b>${o?` <span class="muted">· ${esc(o)}</span>`:''}</summary>
    <div class="utvalg-innhold"><p class="liten">${mote}</p>${medlemHtml(sc)}</div></details>`;
}
(function(){
  const harMote=new Set(meetings.map(m=>m.sc));
  const avgjor=K.organer.map(o=>o.kode).filter(sc=>!RAD.includes(sc)&&harMote.has(sc));
  const rad=K.organer.map(o=>o.kode).filter(sc=>RAD.includes(sc)&&harMote.has(sc));
  $('utvalgene').innerHTML=`<h3 class="utvalg-gr">Utvalgene som avgjør saker</h3>${avgjor.map(utvalgHtml).join('')}
    ${rad.length?`<h3 class="utvalg-gr">Rådene</h3><p class="liten muted">Gir uttalelser i saker som gjelder dem, men avgjør ikke.</p>${rad.map(utvalgHtml).join('')}`:''}`;
})();

/* ---------- NAVIGASJON ---------- */
const VIEWS=['oversikt','saker','sak','moter','mote','politikere','person','hvem-bestemmer'];
const MENY={person:'politikere',sak:'saker',mote:'moter'};
const TITLER={oversikt:'',saker:'Saker',moter:'Møter',politikere:'Politikerne','hvem-bestemmer':'Hvem bestemmer'};
function go(v,o={}){
  // Fra forsiden: én fane og ett utvalg, eller et søk, uten andre filtre.
  if(v==='saker'&&('q' in o||'fane' in o||'ut' in o||'tag' in o)){
    $('q').value=o.q||'';$('fut').value=o.ut||'';$('ftema').value=o.tag||'';$('faar').value='';$('fmnd').value='';limit=40;
    if(FANER[o.fane]&&o.fane!=='avgjort')o.arg=o.fane;
  }
  const h='#'+v+(o.arg?'/'+o.arg:'');
  if(location.hash===h)vis();else location.hash=h;
}
let forrigeV=null;
function vis(){
  const [v0,arg]=decodeURIComponent(location.hash.slice(1)).split('/');
  // Om-fanen er flyttet til Om-siden, som er felles for alle kommunene.
  if(v0==='om'){location.replace('../om/');return}
  // Stemmer er flyttet: stemmene står på sakene, partiene under Politikere.
  if(v0==='stemmer'){location.replace(arg==='partiene'?'#politikere/partiene':arg==='politikerne'?'#politikere':'#saker');return}
  const v=VIEWS.includes(v0)?v0:'oversikt';
  VIEWS.forEach(x=>$('v-'+x).hidden=x!==v);
  document.querySelectorAll('#nav a').forEach(a=>{if(a.dataset.v===(MENY[v]||v))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  document.title=(TITLER[v]?TITLER[v]+' – ':'')+`${K.navn} | ${S.merke}`;
  if(v==='saker'){const f=FANER[arg]?arg:'avgjort';if(f!==sakFane){sakFane=f;limit=40}renderList()}
  if(v==='moter'){kalMnd=/^\d{4}-\d{2}$/.test(arg||'')?arg:mndNaa;renderMeet()}
  if(v==='mote')renderMote(+arg);
  // Partifilteret står i adressen (#politikere/AP), så lenker og tilbakeknappen
  // virker. #politikere/partiene er fanen Partiene.
  if(v==='politikere'){const f=arg==='partiene'?'partiene':'politikerne';visPolFane(f);
    if(f==='politikerne'){fparti=PARTI_I_FOLK.includes(arg)?arg:null;renderFChips();renderFolk()}}
  if(v==='person')renderPerson(arg);
  if(v==='sak')renderSak(+arg);
  const valgtUtvalg=v==='hvem-bestemmer'&&arg&&document.getElementById('utvalg-'+arg);
  if(valgtUtvalg){valgtUtvalg.open=true;requestAnimationFrame(()=>valgtUtvalg.scrollIntoView({block:'start'}));forrigeV=v;return}
  // Bytte av fane i samme visning flytter ikke siden.
  if(v!==forrigeV||!['saker','politikere','moter'].includes(v))window.scrollTo({top:0});
  forrigeV=v;
}
document.addEventListener('click',e=>{
  // Søkeikonet i menyen: til sakene, med markøren i søkefeltet. Feltet kan
  // først få fokus når visningen er vist, altså etter hashchange.
  if(e.target.closest('[data-sok]')){e.preventDefault();
    if(location.hash.startsWith('#saker'))$('q').focus();
    else{window.addEventListener('hashchange',()=>$('q').focus(),{once:true});go('saker')}
    return}
  const g=e.target.closest('a[data-go]');
  if(g){e.preventDefault();const o={};['fane','tag','ut'].forEach(k=>{if(g.dataset[k]!==undefined)o[k]=g.dataset[k]});go(g.dataset.go,o)}
});
/* Forsiden, «Se stemmene»: siste kommunestyremøte med publiserte avstemninger
   der noen stemte imot, ellers siste møte i et annet utvalg. De jevneste først,
   med lenke til saken. Står her fordi den bruker segBar. */
(function(){
  const omstridte=m=>m.saker.flatMap(s=>s.v.filter(omstridt));
  const ms=[...VOT.moter].reverse();
  const m=ms.find(m=>m.sc===KSK&&omstridte(m).length)||ms.find(m=>omstridte(m).length);
  if(!m){$('stemkort').innerHTML='<p class="muted">Ingen avstemninger der noen stemte imot ennå.</p>';return}
  // Én avstemning per sak, den jevneste, så kortet viser tre ulike saker.
  const vs=omstridte(m),diff=v=>Math.abs(v.nfor-v.nmot),perSak=new Map();
  vs.forEach(v=>{const x=perSak.get(v.hid);if(!x||diff(v)<diff(x))perSak.set(v.hid,v)});
  const jevne=[...perSak.values()].sort((a,b)=>diff(a)-diff(b)).slice(0,3);
  $('stemkort').innerHTML=`<div class="mote-gr"><h3>${esc(utName(m.sc))} <span class="muted">${naar(m.date)}</span></h3>
    <p class="liten muted">${antall(vs.length,'avstemning','avstemninger')} der noen stemte imot. De jevneste:</p>
    ${vs.some(v=>(v.merk||[]).length)?`<p class="liten merk">Protokollen fra møtet er selvmotsigende om hvem som møtte. Avstemningene er merket.</p>`:''}
    <ul class="saksliste">${jevne.map(v=>`<li><a class="t" href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a>${segBar(v)}<div class="liten"><b class="num">${v.nfor} for, ${v.nmot} mot</b> · <span class="res ${v.vinner||v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></div></li>`).join('')}</ul></div>`;
})();
renderList();renderMeet();renderHeat();
$('foot').innerHTML=`<div>Kilde: ${esc(K.navn)} kommunes innsynsportal (Elements Publikum): møtekalender, saksprotokoller, møteprotokoller og medlemslister. Data hentet ${dato(TODAY)}.</div><div>${esc(S.merke)} er en uoffisiell tjeneste, laget av en innbygger for innbyggerne. <a href="../">Andre kommuner</a> · <a href="../om/">Om ${esc(S.merke)}</a></div>`;
window.addEventListener('hashchange',vis);vis();
// Nådde vi hit, er siden tegnet. Ellers viser index.html en feilmelding.
window.KL_KLAR=true;
