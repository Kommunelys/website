/* Kommunelys. Bygges av bygg/bygg_nettsted.py.
   Dataene ligger i data/data.js: S (saker, møter, utvalg, kommunestyret og
   de folkevalgte) og VOT (voteringer per møte). Ingenting her er skrevet for
   hånd om enkeltsaker eller enkeltpersoner, og ingen kommune nevnes ved navn:
   det som er særegent for kommunen, står i S.kommune (kommuner/<kommune>.json). */
const TODAY=S.today, AAR=S.aar, K=S.kommune;
// Alle årene fra kommunens første år (ADR-022). Med ett år står S.aarene ikke i
// dataene, og tekstene sier «i 2026»; med flere sier de «siden 2026».
const FLERE_AAR=(S.aarene||[]).length>1, FRA_AAR=(S.aarene||[AAR])[0];
const PERIODE=FLERE_AAR?`siden ${FRA_AAR}`:`i ${AAR}`;
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
// Skjemaet i portalen, som krever innlogging (ADR-023). Tittelen vises bare der;
// meldingen lagres med kommunen og saken.
const meldUrl=c=>`${S.portal}/meld?${new URLSearchParams({kommune:K.slug,sak:c.id,tittel:c.t})}`;
// Redigering av sammendraget i portalen, bare for prosjektadmin (ADR-025).
// Lenken vises når kontomenyen vet at kontoen er prosjektadmin (konto.js).
const redigerUrl=c=>`${S.portal}/rediger?${new URLSearchParams({kommune:K.slug,sak:c.id})}`;
// Merknad fra den som har vurdert saken i portalen, med datoen.
const merknad=m=>`<p class="merk"><b>Merknad fra Kommunelys, ${dato(m.d)}:</b> ${esc(m.t)}</p>`;
const ut=(u,t)=>`<a href="${u}" target="_blank" rel="noopener">${t}</a>`;
/* Opptakene av møtene (ADR-026). De ligger hos kommunen; vi lenker dit, til
   starten av saken. Lenkene står også når opptaket ikke er tekstet. */
// En skjerm med avspilling, ikke bare en trekant: trekanten er allerede pilen
// på alt som kan åpnes (details), og ville blitt lest som «vis mer».
const SPILL='<svg class="spill" viewBox="0 0 16 16" aria-hidden="true"><rect x="1.25" y="2.25" width="13.5" height="9.5" rx="1.75" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6.6 4.7v4.6L10.4 7z" fill="currentColor"/><path d="M5 14.25h6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
const varighet=s=>{const t=Math.floor(s/3600),m=Math.round(s%3600/60);return t?`${t} t${m?` ${m} min`:''}`:`${Math.max(1,m)} min`};
const klokke=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
const opptakLenke=(u,t,cls='')=>`<a class="opptak${cls?' '+cls:''}" href="${esc(u)}" target="_blank" rel="noopener">${SPILL}<span>${t}</span></a>`;
// Behandlingen med opptak som saken bør åpnes på: den siste som er holdt.
const opptakSteg=c=>[...c.st].reverse().find(x=>x.op&&!isFut(x.date))||null;
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
/* Forsiden handler om kommunestyret: de siste og neste møtene øverst, så de
   viktigste sakene fra de siste møtene, og til slutt veier videre. Kortene
   tegnes nederst i filen (visViktige), fordi de bruker saksidens tidslinje
   og stemmestolpe. */
const meetings=S.meetings;
const RAD=K.rad;
const UKEDAG=['søndag','mandag','tirsdag','onsdag','torsdag','fredag','lørdag'];
const naar=d=>`${UKEDAG[new Date(d.slice(0,10)+'T12:00').getDay()]} ${ddl(d)}`;
const sakLenke=(c,hid)=>`<a class="t" href="${sakUrl(hid)}">${esc(tittel(c))}</a>`;
const smaa=s=>s.charAt(0).toLowerCase()+s.slice(1);

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
  // Tallene gjelder saker som begynte i år, også når dataene har flere år.
  const ps=FLERE_AAR?PS.filter(c=>((c.st[0]||{}).date||'').startsWith(AAR)):PS;
  const full=ps.filter(c=>{const s=c.st.map(x=>x.sc);return s.includes(KSK)&&s.includes('FS')&&s.some(x=>HU.includes(x))}).length;
  const fsks=ps.filter(c=>{const s=[...new Set(c.st.map(x=>x.sc))];return s.join()===['FS',KSK].join()}).length;
  const ksAll=ps.filter(c=>c.ks).length;
  // Bare saker som er avgjort; de som fortsatt er til behandling, kan gå videre.
  const avgjort=c=>c.status!=='Til behandling';
  const fsSelv=ps.filter(c=>c.st.some(x=>x.sc==='FS')&&!c.ks&&avgjort(c)).length;
  const huSelv=ps.filter(c=>c.st.some(x=>HU.includes(x.sc))&&!c.st.some(x=>['FS',KSK].includes(x.sc))&&avgjort(c)).length;
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
     <span class="m">${sakMeta(c)}${c.st.some(x=>x.op)?`<span class="opptak-merke" title="Saken er diskutert i et møte med opptak">${SPILL}Opptak</span>`:''}${c.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</span></a></div>`;
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
// Pilene stopper ved første og siste måned med møter (eller i dag).
const MNDENE=meetings.map(m=>m.date.slice(0,7)).sort();
const FORSTE_MND=[MNDENE[0]||mndNaa,mndNaa].sort()[0], SISTE_MND=[MNDENE.at(-1)||mndNaa,mndNaa].sort()[1];
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
  $('mforr').disabled=kalMnd<=FORSTE_MND;$('mneste').disabled=kalMnd>=SISTE_MND;
  // Rutenettet: uker fra mandag til søndag.
  const forste=(new Date(aa,mm-1,1).getDay()+6)%7,dager=new Date(aa,mm,0).getDate();
  let h='<div class="kal-uke kal-dager">'+['Man','Tir','Ons','Tor','Fre','Lør','Søn'].map(d=>`<span>${d}</span>`).join('')+'</div><div class="kal-uke">';
  for(let i=0;i<forste;i++)h+='<div class="kal-dag tom"></div>';
  for(let d=1;d<=dager;d++){
    const dato=`${kalMnd}-${String(d).padStart(2,'0')}`,dm=ms.filter(m=>m.date.startsWith(dato));
    h+=`<div class="kal-dag${dato===TODAY.slice(0,10)?' idag':''}"><span class="kal-nr">${d}</span>${dm.map(m=>`<a class="kal-m ${nivaa(m.sc)}" href="#mote/${m.id}" title="${esc(utName(m.sc))} ${kl(m)}"><span class="mono">${m.date.slice(11,16)}</span> ${esc(K.utvalg_liste[m.sc]||utName(m.sc))}${m.op?`<span class="vh"> (med opptak)</span>${SPILL}`:''}</a>`).join('')}</div>`;
    if((forste+d)%7===0&&d<dager)h+='</div><div class="kal-uke">';
  }
  for(let i=(forste+dager)%7;i&&i<7;i++)h+='<div class="kal-dag tom"></div>';
  $('kal').innerHTML=h+'</div>';
  // Listen: samme møter, for smale skjermer.
  $('mlist').innerHTML=ms.map(m=>`<a class="mote" href="#mote/${m.id}"><span class="mote-dato"><b>${+m.date.slice(8,10)}.</b> ${UKEDAG[new Date(m.date.slice(0,10)+'T12:00').getDay()].slice(0,3)}</span><span>${utvMerke(m.sc)}<span class="liten muted">${kl(m)}${m.sted?` · ${esc(renSted(m.sted))}`:''} · ${m.nps?antall(m.nps,'politisk sak','politiske saker'):m.n?antall(m.n,'sak','saker'):'sakslisten er ikke publisert'}</span>${m.op?`<span class="opptak-merke">${SPILL}Opptak${m.op.d?` · ${varighet(m.op.d)}`:''}</span>`:''}</span></a>`).join('')
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
const vlinje=(v,vo,ekstra,skjult)=>`<div class="vrow"${skjult?' hidden':''}><span class="muted">${ddn(v.dato)} ${esc(v.usc)}</span><span><a href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a><br><span class="liten muted klipp">${esc(typeNavn(v))}: ${esc(v.lbl)}</span>${ekstra||''}</span><span class="v ${vo||''}">${vo==='for'?'For':vo==='mot'?'Mot':''}</span><span class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></div>`;
function renderHeat(){
  const ps=ordne(PORDER_ALLE,[...new Set(contested.flatMap(v=>Object.keys(SIDES.get(v.id))))]);
  const agree=(a,b)=>{let n=0,k=0;contested.forEach(v=>{const s=SIDES.get(v.id);if(s[a]&&s[b]){n++;if(s[a]===s[b])k++}});return n?k/n:null};
  // --i lar radene komme fram etter hverandre (stil.css).
  let h=`<tr><th></th>${ps.map(p=>`<th><span class="sq" style="background:${pc(p)}"></span>${p}</th>`).join('')}</tr>`;
  ps.forEach((a,i)=>{h+=`<tr style="--i:${i+1}"><th class="rh">${esc(PNAME[a]||a)}</th>`+ps.map(b=>{if(a===b)return `<td style="background:var(--soft);color:var(--muted)">–</td>`;const r=agree(a,b);if(r===null)return '<td class="muted">·</td>';const pct=Math.round(r*100);return `<td title="${a} og ${b} stemte likt i ${pct} %" style="background:color-mix(in srgb,var(--ink) ${Math.max(6,pct)}%,var(--bg));color:${pct>55?'var(--bg)':'var(--ink)'}">${pct}</td>`}).join('')+'</tr>'});
  $('heat').innerHTML=contested.length?h:'<tr><td class="muted">Ingen avstemninger der noen stemte imot.</td></tr>';
  $('close').innerHTML=contested.filter(v=>Math.abs(v.nfor-v.nmot)<=3).map(v=>{const s=SIDES.get(v.id);const cross=[...v.f.filter(n=>s[party(n)]!=='for'),...v.m.filter(n=>s[party(n)]!=='mot')];
    // Som en rad på saken: tittel og utfall, stolpen, og partimerket ved dem som brøt med partiet.
    return `<div class="jevn"><div class="vlinje"><span class="vt"><a href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a><br><span class="liten muted">${esc(typeNavn(v))}: ${esc(v.lbl)}</span></span><span class="vutf ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)} ${v.nfor}–${v.nmot}</span></div>${segBar(v)}<div class="liten muted">${cross.length?'Stemte annerledes enn partiet: '+cross.map(n=>`<span class="cross">${plink(n)}</span> ${pm(party(n))}`).join(' '):'Alle stemte som partiet sitt.'}</div>${(v.merk||[]).map(t=>`<div class="merk">Merknad: ${esc(t)}</div>`).join('')}</div>`}).join('')||'<p class="muted">Ingen avstemninger ble avgjort med tre stemmer eller mindre.</p>';
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
  // «Møtt» med en stolpe som viser hvor stor del av møtene det er.
  const rad=v=>{const n=S.mprot[v.u];return `<tr><td>${esc(utName(v.u))}${v.p&&v.p!==p.p?` <span class="liten muted">(for ${esc(PNAME[v.p]||v.p)})</span>`:''}</td><td>${rolle(v.u,v.r)}</td><td class="num">${n&&v.m?`<span class="maaler mmaaler" aria-hidden="true"><i style="width:${Math.min(100,Math.round(100*v.m/n))}%"></i></span>`:''}${v.m||'–'}</td><td class="num">${n||'–'}</td></tr>`};
  const pct=st.omst.length?Math.round(st.maj/st.omst.length*100):0;
  const sakLenke=v=>`<a href="${sakUrl(v.hid)}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a>`;
  // Mange forslag foldes, som punktene i debatten på saken.
  const visF=st.forslag.length>8?6:st.forslag.length;
  // Tallene om stemmene som tre små ruter. Stolpen i den midterste fylles.
  const tall=`<div class="tall3"><div><b>${st.mine.length}</b><span>${st.mine.length===1?'avstemning':'avstemninger'} med navneliste ${PERIODE}</span></div>
    ${st.omst.length?`<div><b>${pct} %</b><span>stemte som flertallet, i de ${st.omst.length} der noen stemte imot</span><span class="maaler" aria-hidden="true"><i style="width:${pct}%"></i></span></div>
    <div><b>${st.brk.length}</b><span>${st.brk.length===1?'gang':'ganger'} annerledes enn resten av partiet</span></div>`:''}</div>`;
  el.innerHTML=`<div class="profil"><div class="ingress">
    <p class="parti"><span class="dot" style="background:${pc(p.p)}"></span>${esc(PNAME[p.p]||p.p)}</p>
    <h1>${esc(p.n)}</h1>
    <p class="fakta">${hoved}. ${antall(vv.length,'verv','verv')} ifølge medlemslisten ${dato(S.ks.hentet)}.${lenke?` Partiet: ${lenke}.`:''}</p></div>
    ${sakKort({id:'pkort-verv',type:'sti',ikon:'verv',tittel:'Verv',under:`${antall(vv.length,'verv','verv')} i dag${tidl.length?`, ${tidl.length} tidligere`:''}`,innhold:`
      <div class="tw"><table><thead><tr><th>Utvalg</th><th>Rolle</th><th class="num">Møtt</th><th class="num">Møter</th></tr></thead><tbody>${vv.map(rad).join('')}</tbody></table></div>
      ${tidl.length?`<p class="liten muted">Sett i protokollene, men ikke i dagens medlemsliste: ${tidl.map(v=>esc(utName(v.u))).join(', ')}.</p>`:''}
      ${varaFor.length?`<p class="liten">Har møtt som varamedlem for ${varaFor.map(plink).join(', ')}.</p>`:''}
      <p class="liten muted">«Møtt» er antall møter ${PERIODE} der navnet står på oppmøtelisten i protokollen. «Møter» er antall møter utvalget har hatt med møteprotokoll. Permisjoner og bytter tidligere i året vises ikke.</p>`})}
    ${sakKort({id:'pkort-stemmer',type:'sti',ikon:'stemmer',tittel:'Stemmer',under:`Lest fra protokollene ${PERIODE}, uten KI`,innhold:`
      ${IKKE_STEMMER?MANGLER_STEMMER:st.mine.length?tall
        :`<p class="oppsum muted">Ingen avstemninger med navneliste ${PERIODE}. Når alle stemmer likt, har protokollen ingen navneliste.</p>`}
      ${st.brk.length?`<details${st.brk.length<=8?' open':''}><summary>Stemte annerledes enn partiet (${st.brk.length})</summary><div>${st.brk.map(v=>vlinje(v,voteOf(v,p.n))).join('')}</div></details>`:''}
      ${st.omst.length?`<details><summary>Alle avstemninger der noen stemte imot (${st.omst.length})</summary><div>${st.omst.map(v=>vlinje(v,voteOf(v,p.n))).join('')}</div></details>`:''}`})}
    ${sakKort({id:'pkort-forslag',type:'fremmet',ikon:'forslag',tittel:'Forslag',under:!IKKE_STEMMER&&st.forslag.length?`${antall(st.forslag.length,'forslag','forslag')} med navn i protokollene`:'',innhold:`
      ${IKKE_STEMMER?MANGLER_STEMMER:st.forslag.length?`<div id="pforslag">${st.forslag.map((v,i)=>vlinje(v,null,'',i>=visF)).join('')}</div>${st.forslag.length>visF?`<button type="button" class="mer" data-flere="pforslag">Vis alle ${st.forslag.length} forslagene</button>`:''}`:`<p class="muted">Ingen forslag med navn i protokollene ${PERIODE}.</p>`}`})}
    <p class="liten muted mt">Kilder: medlemslisten i innsynsportalen (${dato(S.ks.hentet)}), møteprotokollene og saksprotokollene ${FLERE_AAR?`siden ${FRA_AAR}`:`for ${AAR}`}.${HOLDT?` ${antall(HOLDT,'avstemning','avstemninger')} der stemmene ikke vises, er ikke med.`:''} Ingen tekst her er skrevet av KI.</p>
  </div>`;
}

/* ---------- SAKEN ---------- */
/* Én side per sak (#sak/<id>). Øverst det viktigste: tittel, hvor saken står,
   saksgangen som en linje, «Hva betyr det?», opptaket og dokumentene. Under
   står kortene i denne rekkefølgen: sammendraget, debatten, vedtaket, og
   saksgangen med stemmene i hvert møte. En stor sak (mange avstemninger, debatt
   eller mange møter) får kort som kan lukkes og snarveier; i en liten sak står
   alt åpent, og stemmene står i vedtaket. */
const VOT_HID={};VOT.moter.forEach(m=>m.saker.forEach(s=>{VOT_HID[s.hid]={...s,m}}));
/* Detaljene (ADR-022): hele sammendraget, vedtakstekstene og forslagstekstene
   står i data/detaljer-<år>.json og hentes første gang en sak fra året åpnes.
   Året er året saken begynte (c.y, eller S.aar med ett år). Med begrenset
   innsyn (ADR-024) hentes filen fra databasen av innsyn.js (HENT_FIL). */
const VOTE_ID={};ALLEV.forEach(v=>{VOTE_ID[v.id]=v});
const DETALJER={},DETALJER_KLAR=new Set();
const sakensAar=c=>String(c.y||AAR);
const hentFil=window.HENT_FIL||(fil=>fetch('data/'+fil).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}));
function hentDetaljer(aar){
  const fil=(S.detaljer||{})[aar];
  if(!fil||DETALJER_KLAR.has(aar))return Promise.resolve();
  return DETALJER[aar]||(DETALJER[aar]=hentFil(fil).then(d=>{if(!d)throw new Error('mangler '+fil);return d}).then(d=>{
    Object.entries(d.a||{}).forEach(([id,a])=>{const c=SAK_ID[id];if(c&&c.a)Object.assign(c.a,a)});
    Object.entries(d.vt||{}).forEach(([hid,vt])=>{if(STEG[hid])STEG[hid].vt=vt});
    Object.entries(d.d||{}).forEach(([hid,deb])=>{if(STEG[hid])STEG[hid].deb=deb});
    Object.entries(d.v||{}).forEach(([id,x])=>{const v=VOTE_ID[id];if(!v)return;v.tekst=x.tekst;(x.deler||[]).forEach((tk,i)=>{if(v.deler&&v.deler[i])v.deler[i].tekst=tk})});
    DETALJER_KLAR.add(aar);
  }).catch(e=>{delete DETALJER[aar];throw e}));
}
// Sakssiden venter på detaljene. Feiler hentingen, vises saken uten dem.
// Pilene for å bla i møtet (mid) vises med en gang, før detaljene er hentet.
function visSak(id,mid){
  const c=SAK_ID[id],aar=c&&sakensAar(c),b=c&&blaI(c,mid);
  visBla(b);
  if(!c||!(S.detaljer||{})[aar]||DETALJER_KLAR.has(aar)){renderSak(id,false,b);return}
  $('sak').innerHTML='<div class="ingress"><p class="muted">Henter saken …</p></div>';
  const her=location.hash;
  hentDetaljer(aar).then(()=>{if(location.hash===her)renderSak(id,false,b)},()=>{if(location.hash===her)renderSak(id,true,b)});
}
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
// Partiet som et lite merke med fargen: «■ SP», eller «■ SP 8» med tall.
const pm=(p,n)=>`<span class="pm"><i style="background:${pc(p)}"></i>${esc(p)}${n!=null?' '+n:''}</span>`;
// Ikonene på kortene og knappene, i samme strek som resten av siden.
const IKON={
  ki:'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8z"/>',
  debatt:'<path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/>',
  vedtak:'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="m9 15 2 2 4-4"/>',
  sti:'<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="12" r="2"/><path d="M6 7v10M8 5h4a4 4 0 0 1 4 4v1"/>',
  dok:'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  pil:'<path d="m6 9 6 6 6-6"/>',
  // Bla i møtet: forrige og neste sak, og videre nederst.
  forrige:'<path d="m15 18-6-6 6-6"/>',
  neste:'<path d="m9 18 6-6-6-6"/>',
  videre:'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  // De under brukes på møtesiden, profilen og under Partiene.
  kalender:'<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
  folk:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  verv:'<rect width="20" height="14" x="2" y="7" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
  stemmer:'<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
  forslag:'<path d="M12 22h6a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v10"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10.4 12.6a2 2 0 1 1 3 3L8 21l-4 1 1-4Z"/>',
  vekt:'<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
};
const ikon=(n,s=20,cls='')=>`<svg${cls?` class="${cls}"`:''} viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${IKON[n]}</svg>`;
/* Et kort på saksiden. I en stor sak kan det lukkes: en <details> som
   bevegelsen under åpner og lukker mykt. I en liten sak, og for
   sammendraget, står det alltid åpent. */
function sakKort({id,type,ikon:ik,tittel,under,innhold,lukkbar,apen=true}){
  const hode=`<span class="kikon">${ikon(ik||type)}</span><span class="khode"><h2>${tittel}</h2>${under?`<span>${under}</span>`:''}</span>`;
  return lukkbar
    ?`<details class="sakkort ${type}" id="${id}"${apen?' open':''}><summary>${hode}${ikon('pil',20,'kpil')}</summary><div class="kinnhold">${innhold}</div></details>`
    :`<section class="sakkort ${type}" id="${id}"><div class="ktopp">${hode}</div><div class="kinnhold">${innhold}</div></section>`;
}

/* Saksgangen som en linje øverst, med ett punkt per utvalg og datoen. Råd og
   hovedutvalg som behandler saken etter hverandre, blir ett punkt («3 råd»);
   et trykk viser hvilke. Et punkt med ett møte går til møtet under. */
const nivaaSti=sc=>erRad(sc)?'rad':(K.hovedutvalg||[]).includes(sc)?'hu':sc;
// Lange ord kan deles der linjen er smal: «Kommune-styret».
const myk=t=>t.replace(/^(Kommune|Formann)(styret|skapet)$/,'$1­$2');
const spenn=(a,b)=>a.slice(0,10)===b.slice(0,10)?dd(a):a.slice(5,7)===b.slice(5,7)?`${+a.slice(8,10)}.–${dd(b)}`:`${dd(a)}–${dd(b)}`;
// På forsiden (bareVis) er punktene ikke knapper: hele kortet går til saken.
function tidslinje(c,bareVis=false){
  const stopp=[];
  stiSteg(c).forEach(x=>{const n=nivaaSti(x.sc),s=stopp.at(-1);
    if(s&&(n==='rad'||n==='hu')&&s.n===n)s.steg.push(x);else stopp.push({n,steg:[x]})});
  if(stopp.length<2)return '';
  const ferdig=!c.next&&['Vedtatt i kommunestyret','Behandlet'].includes(c.status);
  return `<ol class="tidslinje">${stopp.map((s,i)=>{
    const f=s.steg[0],l=s.steg.at(-1),fler=s.steg.length>1;
    const navn=s.n==='rad'?antall(s.steg.length,'råd','råd'):fler?`${s.steg.length} hoved­utvalg`:esc(myk(utvKort(f.sc)));
    const cls=[s.n==='rad'?'rad':'',isFut(f.date)?'fram':'',i===stopp.length-1&&ferdig?'slutt':''].filter(Boolean).join(' ');
    const attr=fler||s.n==='rad'?`data-navn="${esc(s.steg.map(x=>utName(x.sc)).join(', '))} · ${esc(spenn(f.date,l.date))}"`:`data-til="mote-${f.hid}"`;
    const innhold=`<b>${navn}</b><span>${spenn(f.date,l.date)}</span>`;
    return `<li${cls?` class="${cls}"`:''} style="--i:${i}">${bareVis?`<div>${innhold}</div>`:`<button type="button" ${attr}>${innhold}</button>`}</li>`}).join('')}</ol>`;
}

/* Dokumentene i saken bak én knapp ved temaene: saksframlegget, vedleggene og
   protokollen fra hvert møte. Opptaket har sin egen knapp øverst. */
function dokumenter(c){
  const d=[];
  if(c.doc)d.push(['PDF','Saksframlegget','Kommunedirektørens forslag og bakgrunn',c.doc]);
  const m=c.att&&c.st.find(x=>x.murl);
  if(m)d.push([String(c.att),'Vedlegg',`${antall(c.att,'vedlegg','vedlegg')} i innsynsportalen`,m.murl]);
  c.st.filter(x=>x.prot&&x.pub).forEach(x=>d.push(['PDF','Protokollen',`${utName(x.sc)} ${datoAar(x.date)}`,x.prot]));
  return dokKnapp(`dok-${c.id}`,d);
}
// Knappen og listen. Hvert dokument er [type, navn, forklaring, adresse].
function dokKnapp(id,d){
  if(!d.length)return '';
  return `<button type="button" class="dokknapp" aria-expanded="false" aria-controls="${id}">${ikon('dok',18)}Dokumenter <span class="ant">${d.length}</span>${ikon('pil',14,'dokpil')}</button>
    <div class="dokboks" id="${id}" hidden><ul class="dokliste">${d.map(([t,b,s,u])=>`<li><a href="${esc(u)}" target="_blank" rel="noopener"><span class="dt${t==='PDF'?'':' n'}">${esc(t)}</span><span><b>${b}</b><small>${esc(s)}</small></span></a></li>`).join('')}</ul></div>`;
}

// Kort fortalt: hele sammendraget fra KI med kildene. «Hva betyr det?» står øverst på siden.
function kortFortalt(c){
  const a=c.a;
  return `<p>${esc(a.sum)}</p>${a.uen?`<p><b>Uenigheten:</b> ${esc(a.uen)}</p>`:''}
    <p class="kilde"><span class="ki">KI</span> Skrevet av ${esc(a.modell)} ut fra ${a.kilder.map(k=>ut(k.url,esc(k.tittel))).join(', ')}${a.red?`, redigert av Kommunelys ${dato(a.red)}`:''}. Dokumentene gjelder.</p>${a.merk?merknad(a.merk):''}`;
}

/* Debatten (ADR-026): hovedlinjene, og hvert punkt som en boble med partiets
   farge i kanten og tiden i opptaket. Spilleren hos kommunen kan bare åpnes på
   starten av saken, så tiden står i teksten. */
function debattInnhold(x){
  const d=x.deb,op=x.op||[];
  const tid=p=>{const o=op[p.del-1]||op[0];return o?`<a class="tid" href="${esc(o.u)}" target="_blank" rel="noopener" title="Ca. ${klokke(p.s)} inn i saken${op.length>1?`, ${esc(smaa(o.t||'del '+p.del))}`:''}">▶ ${klokke(p.s)}</a>`:''};
  const pkt=[...d.p].sort((a,b)=>(a.del||1)-(b.del||1)||a.s-b.s);
  const vis=pkt.length>4?3:pkt.length;
  return `<p class="hovedlinje">${esc(d.o)}</p>
    <ul class="innlegg" id="innlegg-${x.hid}">${pkt.map((p,i)=>{const pa=p.pa||[];return `<li${i>=vis?' hidden':''} style="--parti:${pa[0]?pc(pa[0]):'var(--muted)'}"><div class="itopp">${pa.map(q=>pm(q)).join('')}${tid(p)}</div><p>${esc(p.t)}</p></li>`}).join('')}</ul>
    ${pkt.length>vis?`<button type="button" class="mer" data-flere="innlegg-${x.hid}">Vis alle ${pkt.length} punktene</button>`:''}
    <p class="kilde"><span class="ki">KI</span> Sammendraget er laget av en språkmodell fra kommunens automatiske teksting av opptaket, og kan ha feil. ${op[0]?ut(op[0].u,'Opptaket'):'Opptaket'} viser hva som faktisk ble sagt. Stemmene er lest fra protokollen.</p>${d.merk?merknad(d.merk):''}`;
}

/* Vedtaket delt i avsnitt, slik protokollen deler det (kulepunkt eller nummer). */
function avsnitt(t){
  t=(t||'').trim();
  const kule=t.split(/\s*•\s*/).filter(Boolean);
  if(kule.length>1)return kule;
  const merker=[];let neste=null;
  for(const m of t.matchAll(/(^|\s)(\d{1,2})\.(?!\d)\s?/g)){const n=+m[2];if(neste===null||n===neste){merker.push({fra:m.index+m[1].length,til:m.index+m[0].length});neste=n+1}}
  if(merker.length<2)return [t];
  const for_=t.slice(0,merker[0].fra).trim();
  return [...(for_?[for_]:[]),...merker.map((m,i)=>t.slice(m.til,i+1<merker.length?merker[i+1].fra:t.length).trim())];
}
/* Avstemningen som avgjorde et avsnitt: den vedtatte, der forslagsteksten
   inneholder avsnittets første ord. Den korteste vinner, fordi den er mest
   presis. Finnes ingen, står avsnittet uten tall; stemmetall gjettes aldri. */
const norm=t=>(t||'').toLowerCase().replace(/^[\s\d.•)–-]+/,'').replace(/[^a-zæøå0-9]+/g,' ').trim();
function stemmeFor(s,tekst){
  const k=norm(tekst).slice(0,60);
  if(k.length<15)return null;
  const kand=s.v.filter(v=>!v.holdt).map(v=>{
    if(erAlt(v)){const d=(v.deler||[]).find(d=>d.fs===v.vinner);return d&&d.tekst?{v,d,t:norm(d.tekst),ny:d.type!=='innstilling'}:null}
    if(!(v.en||v.res==='vedtatt')||!v.tekst)return null;
    return {v,d:v,t:norm(v.tekst),ny:!erInnst(v)};
  }).filter(o=>o&&o.t.includes(k));
  return kand.sort((a,b)=>a.t.length-b.t.length)[0]||null;
}
// Et alternativt forslag eller et endringsforslag endret innstillingen; de andre la noe til.
const ENDRET=['alternative forslag','endringsforslag'];
const tallTekst=v=>{
  if(v.en)return 'Enstemmig';
  if(erAlt(v)){const a=v.alt.find(a=>a.fs===v.vinner),andre=v.alt.filter(x=>x!==a).map(x=>x.n);return `${a?a.n:''}${andre.length?'–'+andre.join('–'):''}`}
  return v.nmot?`${v.nfor}–${v.nmot}`:'Alle for';
};
const jevnV=v=>!v.en&&!erAlt(v)&&v.nmot>0&&Math.abs(v.nfor-v.nmot)<=3;
const forMot=v=>`<div class="lg"><b>For:</b>${partiTekst(v.f)}</div>${v.nmot?`<div class="lg"><b>Mot:</b>${partiTekst(v.m)}</div>`:''}`;
/* Vedtaket. Hadde saken flere avstemninger, står stemmetallet ved avsnittet
   det gjelder, og avsnitt fra forslag i møtet er merket. Gjelder én
   avstemning mer enn to avsnitt, var det hele forslaget, og tallet står heller
   i setningen øverst. I en liten sak står stemmene øverst i kortet. */
function vedtakInnhold(c,x,s,stor){
  const deler=avsnitt(x.vt);
  const kobling=s&&s.v.length>1?deler.map(t=>stemmeFor(s,t)):deler.map(()=>null);
  const telle=new Map();kobling.forEach(o=>o&&telle.set(o.v,(telle.get(o.v)||0)+1));
  kobling.forEach((o,i)=>{if(o&&telle.get(o.v)>2)kobling[i]=null});
  const nye=kobling.filter(o=>o&&o.ny).length;
  const vis=stor&&deler.length>7?5:deler.length;
  const ok=!s||utfall(s).ok;
  const stempel=stor&&ok?`<div class="stempel" aria-hidden="true">Vedtatt<small>${dato(x.date)}</small></div>`:'';
  const topp=!s?'':stor||s.v.length>1||erAlt(s.v[0])||s.v[0].holdt||s.v[0].en
    ?`<p>${sakSvar(s)}${kobling.some(Boolean)?' Trykk på stemmetallet ved et avsnitt for å se hvem som stemte for og mot.':''}</p>${!stor&&s.v.length>1?vrader(s):''}`
    :enStemme(s.v[0]);
  const tekst=deler.length<2?`<div class="vtekst enkel">${formater(x.vt)}</div>`
    :`<ol class="vedtak" id="vedtak-${c.id}">${deler.map((t,i)=>{const o=kobling[i];
      const vtopp=o?`<div class="vtopp">${o.ny?`<span class="nytt">${ENDRET.includes(o.d.type)?'Endret':'Lagt til'} i møtet${fra(o.d)?', '+esc(fra(o.d)):''}</span>`:''}<button type="button" class="vchip${jevnV(o.v)?' knapt':''}" aria-expanded="false" aria-controls="vc-${c.id}-${i}">${tallTekst(o.v)}</button></div>`:'';
      const det=o?`<div class="vdetalj" id="vc-${c.id}-${i}" hidden>${!o.v.en&&!erAlt(o.v)?segBar(o.v)+forMot(o.v):''}<button type="button" class="lenkeknapp" data-til="vot-${o.v.id}">Se avstemningen</button></div>`:'';
      return `<li${o&&o.ny?' class="ny"':''}${i>=vis?' hidden':''}>${vtopp}<div class="vtekst${stor&&t.length>240?' lang':''}">${esc(t)}</div>${det}</li>`}).join('')}</ol>
      ${deler.length>vis?`<button type="button" class="mer" data-flere="vedtak-${c.id}">Vis de ${deler.length-vis} andre avsnittene</button>`:''}`;
  return {
    under:deler.length>1?[antall(deler.length,'avsnitt','avsnitt'),nye?`${nye} fra forslag i møtet`:''].filter(Boolean).join(' · '):datoAar(x.date),
    html:`${stempel}${topp}${tekst}<p class="kilde">${x.prot?`${ut(x.prot,'Protokollen')} gjelder.`:'Protokollen gjelder.'}</p>`};
}
// Én avstemning i en liten sak: utfallet stort, stolpen og partiene, og navnene bak et trykk.
function enStemme(v){
  const ok=v.res==='vedtatt';
  return `<div class="utfall"><b class="${ok?'ok':'no'}">${ok?'Vedtatt':'Falt'} ${v.nfor}–${v.nmot}</b>${v.nmot?'':'<span>Alle som stemte, stemte for</span>'}</div>
    ${segBar(v)}${forMot(v)}<details class="navnefold"><summary>Se navnene</summary>${namesBlock(v)}</details>`;
}

/* Avstemningene i et møte som rader: tittel, utfall og stolpe. Et trykk viser
   partiene, forslagsteksten og navnene. Faller to eller flere forslag, samles
   de under én linje som kan åpnes. */
function vrader(s){
  const vs=[...s.v].sort((a,b)=>a.nr-b.nr);
  const falt=vs.filter(v=>!erAlt(v)&&!v.en&&!v.holdt&&v.res!=='vedtatt');
  const fold=falt.length>1?falt:[];
  return `<ul class="vrader">${vs.filter(v=>!fold.includes(v)).map(v=>vrad(v,s)).join('')}</ul>
    ${fold.length?`<details class="falt"><summary>${fold.length} forslag falt</summary><ul class="vrader">${fold.map(v=>vrad(v,s)).join('')}</ul></details>`:''}`;
}
// Tittelen på en rad. Sju rader som alle heter «Forslaget saken kom med», sier
// ingenting; da står starten på teksten etter.
const kortTekst=(t,n)=>{t=(t||'').replace(/^[\s\d.•)]+/,'').replace(/\s*…$/,'');return t.length<=n?t:t.slice(0,t.lastIndexOf(' ',n))+' …'};
function radTittel(v,alene){
  const t=votTittel(v,alene);
  return !alene&&!erAlt(v)&&v.lbl&&!/punkt/.test(t)&&!/^Forslaget saken kom med$/i.test(v.lbl)?`${t}: ${esc(kortTekst(v.lbl,70))}`:t;
}
function vrad(v,s){
  const alene=s.v.length===1;
  const utf=v.holdt?'<span class="vutf">Stemmene vises ikke</span>':v.en?'<span class="vutf ok">Enstemmig</span>'
    :erAlt(v)?`<span class="vutf ok">${esc(resTxt(v))}</span>`:`<span class="vutf ${v.res==='vedtatt'?'ok':'no'}">${v.res==='vedtatt'?'Vedtatt':'Falt'} ${v.nfor}–${v.nmot}</span>`;
  const vinn=erAlt(v)&&v.alt.find(a=>a.fs===v.vinner);
  const stolpe=v.holdt||v.en?'':vinn?partiStolpe(vinn.navn,v.alt.reduce((n,a)=>n+a.n,0)):segBar(v);
  let det;
  if(erAlt(v)&&v.alt.length)det=altBokser(v);
  else{
    const navn=!v.holdt&&!v.en,prot=protFor(v.hid);
    const tekst=!v.en&&v.tekst?`<div class="forslag">${formater(v.tekst)}</div>`:'';
    det=`${navn?forMot(v):''}${v.holdt?`<p class="why">${esc(v.holdt)} ${prot?ut(prot,'Protokollen'):'Protokollen'} gjelder.</p>`:''}
      ${tekst||navn?`<details><summary>${navn?'Les forslaget og se navnene':'Les forslaget'}</summary>${tekst}${fremmetAv(v)?`<p class="liten">${fremmetAv(v)}</p>`:''}${navn?namesBlock(v):''}</details>`:''}`;
  }
  return `<li class="vrad" id="vot-${v.id}"><button type="button" aria-expanded="false" aria-controls="vd-${v.id}"><span class="vlinje"><span class="vt">${radTittel(v,alene)}</span>${utf}</span>${stolpe}</button><div class="vdetalj" id="vd-${v.id}" hidden>${det}</div></li>`;
}
/* Den vanligste skillelinjen i et møte med mange avstemninger: hvilke partier
   som oftest sto sammen. Bare telling fra protokollen, ingen KI. Et parti står
   på den siden flertallet av representantene stemte. */
function skillelinje(s){
  const vs=s.v.filter(v=>!v.holdt&&!v.en&&!erAlt(v)&&v.nfor&&v.nmot);
  if(vs.length<8)return '';
  const tell=new Map();
  vs.forEach(v=>{const g=SIDES.get(v.id)||groupSide(v);const k=ordne(PORDER_ALLE,Object.keys(g).filter(p=>g[p]==='for'&&p!=='?')).join(' ');tell.set(k,(tell.get(k)||0)+1)});
  const [k,n]=[...tell].sort((a,b)=>b[1]-a[1])[0];
  if(n<3)return '';
  const a=k.split(' ').filter(Boolean),b=ordne(PORDER_ALLE,[...new Set(vs.flatMap(v=>[...v.f,...v.m].map(party)))].filter(p=>p!=='?'&&!a.includes(p)));
  return `<div class="skille"><b>Den vanligste skillelinjen.</b> I ${n} av ${vs.length} avstemninger der noen stemte imot, delte partiene seg slik:
    <div class="side">${a.map(p=>pm(p)).join('')}</div><div class="liten muted">mot</div><div class="side">${b.map(p=>pm(p)).join('')}</div>
    <p class="liten muted">Telt fra protokollen: partiet står på den siden flertallet av representantene stemte.</p></div>`;
}

/* Ett møte i saksgangen: hva som skjedde der, avstemningene og lenkene. I en
   stor sak kan møtet lukkes, og bare møtet som avgjorde saken står åpent. */
function moteDel(c,x,avgjort,stor,apen){
  const s=VOT_HID[x.hid],fram=isFut(x.date);
  let tekst='';
  if(fram)tekst='Står på sakslisten.';
  else if(!x.pub)tekst=x.restr?'Protokollen er skjermet.':(Date.parse(TODAY)-Date.parse(x.date.slice(0,10)))/864e5>30?'Protokollen er ikke publisert.':'Venter på protokoll.';
  else if(s)tekst=sakSvar(s);
  else if(x.vt&&x!==avgjort)tekst=x.vt.length<=300?`${erRad(x.sc)?'Uttalelse':'Vedtak'}: «${esc(x.vt)}»`:`<details><summary>${erRad(x.sc)?'Les uttalelsen':'Les vedtaket'}</summary><div class="forslag">${formater(x.vt)}</div></details>`;
  else if(!x.vt)tekst='Behandlet. Ingen vedtakstekst i protokollen.';
  if(x===avgjort&&!s)tekst='Vedtaket står over.';
  if(x.deb&&x.deb.ing)tekst+=(tekst?' ':'')+'Ingen hadde ordet i opptaket.';
  // Samme merknad gjelder ofte alle avstemningene i møtet; den står én gang.
  const merk=s?[...new Set(s.v.flatMap(v=>v.merk||[]))]:[];
  const lenker=[MOTE_ID[x.mid]?`<a href="#mote/${x.mid}">Møtet</a>`:x.murl?ut(x.murl,'Møtet'):'',x.prot?ut(x.prot,'Protokollen'):'',
    ...(x.op||[]).map((o,i)=>opptakLenke(o.u,x.op.length>1?`Opptaket, ${esc(smaa(o.t||'del '+(i+1)))}`:'Opptaket','liten'))].filter(Boolean).join(' · ');
  const innhold=`${tekst?`<p class="mtekst">${tekst}</p>`:''}${merk.length?`<div class="merk">${merk.map(t=>`<b>Merk:</b> ${esc(t)}`).join(' ')} ${x.prot?`${ut(x.prot,'Protokollen')} gjelder.`:'Protokollen gjelder.'}</div>`:''}
    ${s&&!fram&&x.pub?skillelinje(s)+vrader(s):''}${lenker?`<p class="liten mlenker">${lenker}</p>`:''}`;
  const under=[datoAar(x.date),fram?'på sakslisten':s?antall(s.v.length,'avstemning','avstemninger'):''].filter(Boolean).join(' · ');
  const cls=['mdel',fram?'fram':'',x===avgjort?'slutt':'',erRad(x.sc)?'rad':''].filter(Boolean).join(' ');
  const hode=`<span class="mtittel"><b>${esc(utName(x.sc)||x.ut)}</b><span>${under}</span></span>`;
  return stor?`<details class="${cls}" id="mote-${x.hid}"${apen?' open':''}><summary>${hode}${ikon('pil',18,'kpil')}</summary><div class="minnhold">${innhold}</div></details>`
    :`<div class="${cls}" id="mote-${x.hid}"><div class="msum">${hode}</div><div class="minnhold">${innhold}</div></div>`;
}

function renderSak(id,uten_detaljer,bla){
  const c=SAK_ID[id],el=$('sak');
  if(!c){el.innerHTML='<div class="ingress"><h1>Fant ikke saken</h1><p>Saken finnes ikke i dataene'+(FLERE_AAR?'':' for dette året')+'. <a href="#saker">Se alle sakene</a>.</p></div>';return}
  document.title=`${tittel(c)} – ${K.navn} | ${S.merke}`;
  const feil=uten_detaljer?'<p class="merk">Vedtakene og forslagstekstene kunne ikke hentes nå. Last siden på nytt, eller les protokollene i innsynsportalen.</p>':'';
  const f=fase(c),nv=c.st.reduce((n,x)=>n+(VOT_HID[x.hid]?VOT_HID[x.hid].v.length:0),0);
  // Vedtaket: siste behandling med vedtakstekst i et utvalg som avgjør, når saken ikke skal videre.
  const avgjort=c.next?null:[...c.st].reverse().find(x=>!erRad(x.sc)&&x.vt&&x.pub)||null;
  const sv=avgjort&&VOT_HID[avgjort.hid];
  // Formaliasakene har ikke c.last og c.first; saksnummeret tas fra saksgangen.
  const nr=(avgjort||c.last||c.st.at(-1)||{}).nr||'';
  const ops=opptakSteg(c),deb=c.st.filter(x=>x.deb&&!x.deb.ing);
  // En stor sak får kort som kan lukkes, snarveier og bevegelse; en liten viser alt.
  const stor=nv>3||deb.length>0||stiSteg(c).length>2;
  // Kildene står i detaljene. Uten kildelenke vises verken sammendraget eller
  // «Hva betyr det?» (CLAUDE.md regel 5).
  const harSum=!!(c.a&&c.a.kilder);
  const kort=[];
  if(harSum)kort.push({id:'kort-sum',type:'sum',ikon:'ki',kort:'Kort fortalt',tittel:'Kort fortalt',under:'KI-sammendrag av dokumentene',innhold:kortFortalt(c),fast:true});
  deb.forEach((x,i)=>kort.push({id:`kort-debatt${i?'-'+i:''}`,type:'debatt',kort:'Debatten',tittel:`Debatten i ${esc(smaa(utName(x.sc)))}`,
    under:[x.deb.n?antall(x.deb.n,'innlegg','innlegg'):'',`ca. ${varighet((x.op||[]).reduce((n,o)=>n+o.d,0))} i opptaket`].filter(Boolean).join(' · '),innhold:debattInnhold(x)}));
  if(avgjort){const v=vedtakInnhold(c,avgjort,sv,stor);
    kort.push({id:'kort-vedtak',type:'vedtak',kort:'Vedtaket',tittel:`Vedtaket i ${esc(smaa(utName(avgjort.sc)))}`,under:v.under,innhold:v.html})}
  // I en liten sak med ett møte står stemmene i vedtaket, og saksgangen trengs ikke.
  if(stor||!(avgjort&&c.st.length===1)){
    const siste=[...c.st].reverse().find(x=>!isFut(x.date))||c.st.at(-1);
    kort.push({id:'kort-gang',type:'sti',kort:'Stemmene',tittel:'Saksgangen og stemmene',apen:!stor||!avgjort,
      under:[antall(c.st.length,'møte','møter'),nv?antall(nv,'avstemning','avstemninger'):''].filter(Boolean).join(' · '),
      innhold:`${IKKE_STEMMER&&c.st.some(x=>!isFut(x.date))?MANGLER_STEMMER:''}<div class="moter">${c.st.map(x=>moteDel(c,x,avgjort,stor,x===(avgjort||siste))).join('')}</div>`});
  }
  const snarvei=stor&&kort.length>2?`<nav class="snarvei" aria-label="Snarveier i saken">${kort.map(k=>`<button type="button" data-til="${k.id}">${k.kort}</button>`).join('')}${folgKnapp(c)}</nav>`:'';
  el.innerHTML=`<div class="saksside${stor?' stor':''}"><div class="ingress">
    <div class="sak-topp"><h1>${esc(tittel(c))}</h1>${folgKnapp(c)}</div>
    <p class="merk folg-melding" role="status" hidden></p>
    ${c.a?`<p class="muted">Sakstittel: ${esc(c.t)}</p>`:''}
    <p class="sak-status"><span class="st ${f.cls}">${esc(f.t)}</span><span class="muted"><span class="mono">${esc(nr)}</span> · ${antall(c.st.length,'behandling','behandlinger')}${nv?` · ${antall(nv,'avstemning','avstemninger')}`:''}</span></p>
    ${tidslinje(c)}
    ${harSum&&c.a.bet?`<div class="betyr"><b>Hva betyr det? <span class="ki">KI</span></b>${esc(c.a.bet)}</div>`:''}
    ${ops?`<p class="opptak-linje">${opptakLenke(ops.op[0].u,`Se saken i opptaket fra ${esc(smaa(utName(ops.sc)))}`,'knapp')}<span class="liten muted">${datoAar(ops.date)} · ${varighet(ops.op.reduce((n,o)=>n+o.d,0))}</span></p>`:''}
    <div class="tagrad"><p class="tags">${c.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join(' ')}</p>${dokumenter(c)}</div></div>
    ${snarvei}${feil}${!harSum&&c.typ==='PS'&&!c.formal?'<p class="liten muted">Ingen sammendrag ennå. Les dokumentene under Dokumenter.</p>':''}${(c.merk||[]).map(merknad).join('')}
    ${kort.map(k=>sakKort({...k,lukkbar:stor&&!k.fast})).join('')}
    ${bla?blaBunn(bla):''}
    <p class="liten muted mt">Stemmene er lest fra protokollene uten KI, og antall navn er kontrollert mot stemmetallene.</p>
    <p class="liten mt"><a href="${meldUrl(c)}">Meld fra om feil i saken</a> <span class="muted">(krever innlogging)</span><span class="bare-prosjektadmin"> · <a href="${redigerUrl(c)}">Rediger sammendraget</a></span></p>
  </div>`;
  bevegelse(el);
  if(BLA.retning)blaInn(el);
  if(FOLG.vis===c.id){FOLG.vis=null;folgMelding(c,true)}
  const k=folgKonto();
  if(k.innlogget&&!k.nokkel)folgForny(`${S.portal}/login?tilbake=${encodeURIComponent(location.href)}`);
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
  const lengde=(x.op||[]).reduce((n,o)=>n+o.d,0);
  const op=x.op&&x.op[0]?opptakLenke(x.op[0].u,`Opptaket${lengde>=60?`, ${varighet(lengde)}`:''}`,'liten'):'';
  // Én avstemning der noen stemte imot, får stolpen med partiene, som på saken.
  const vs=(VOT_HID[x.hid]||{v:[]}).v.filter(v=>!v.holdt),en=vs.length===1&&omstridt(vs[0])&&!erAlt(vs[0])?vs[0]:null;
  return `<li class="mote-sak"><div class="mote-sak-topp"><span class="mono muted">${esc(x.nr)}</span><span class="mote-sak-hoyre">${op}${isFut(m.date)?'':moteUtfall(x)}</span></div>
    <a class="t" href="${sakIMote(c,m)}">${esc(tittel(c))}</a>${c.a?`<span class="o">${esc(c.t)}</span>`:''}
    ${en?segBar(en):''}
    ${c.a&&c.a.bet?`<p class="mbetyr"><span class="ki">KI</span> ${esc(c.a.bet)}</p>`:''}
    ${mer?`<p class="liten muted">${mer}</p>`:''}</li>`;
}
/* Møtesiden følger saksiden: et toppkort med tid, sted, opptaket og knappen
   Dokumenter, og under det kortene med sakene og om utvalget. */
function renderMote(id){
  const m=MOTE_ID[id],el=$('mote');
  if(!m){el.innerHTML='<div class="ingress"><h1>Fant ikke møtet</h1><p>Møtet finnes ikke i dataene'+(FLERE_AAR?'':' for dette året')+'. <a href="#moter">Se kalenderen</a>.</p></div>';return}
  document.title=`${utName(m.sc)} ${ddl(m.date)} – ${K.navn} | ${S.merke}`;
  $('motetilbake').href='#moter/'+m.date.slice(0,7);
  const st=moteStatus(m),dok=t=>m.docs.find(d=>d.ty===t),fram=isFut(m.date);
  const alle=(SAKER_MOTE[m.id]||[]).sort(etterNr);
  const pol=alle.filter(o=>politisk(o.c)),andre=alle.filter(o=>!pol.includes(o));
  const dokumentene=[dok('MI')&&['PDF','Møteinnkallingen','Sakslisten med alle saksframleggene',dok('MI').u],
    dok('MP')&&['PDF','Møteprotokollen','Vedtakene og hvem som møtte',dok('MP').u],
    m.url&&['↗','Innsynsportalen','Møtet hos kommunen, med alle dokumentene',m.url]].filter(Boolean);
  const nv=pol.reduce((n,o)=>n+((VOT_HID[o.x.hid]||{v:[]}).v.length),0);
  const saker=sakKort({id:'mkort-saker',type:fram?'fram':'vedtak',ikon:fram?'kalender':'vedtak',
    tittel:fram?'Sakene som skal opp':'Sakene og hva som ble bestemt',
    under:[pol.length?antall(pol.length,'politisk sak','politiske saker'):'',nv?antall(nv,'avstemning','avstemninger'):'',andre.length?antall(andre.length,'annen sak','andre saker'):''].filter(Boolean).join(' · '),
    innhold:`${pol.length?`<ol class="mote-saker">${pol.map(o=>moteSak(o,m)).join('')}</ol>`:`<p class="muted">${m.n?'Ingen politiske saker på sakslisten.':'Sakslisten er ikke publisert ennå.'}</p>`}
      ${IKKE_STEMMER&&!fram&&pol.length?MANGLER_STEMMER:''}
      ${andre.length?`<details class="falt"><summary>${antall(andre.length,'annen sak','andre saker')}: referater, orienteringer og formalia</summary><ol class="mote-saker">${andre.map(o=>moteSak(o,m)).join('')}</ol></details>`:''}`});
  const om=sakKort({id:'mkort-om',type:'sti',ikon:'folk',tittel:`Om ${esc(smaa(utName(m.sc)))}`,
    under:!fram&&m.opp?`${m.opp.navn.length+m.opp.andre} møtte`:'',
    innhold:`${oppgave(m.sc)?`<p>${esc(forst(oppgave(m.sc)))}.</p>`:''}
      ${!fram&&m.opp?oppmoteHtml(m):!fram&&IKKE_OPPMOTE?MANGLER_OPPMOTE:''}
      <details class="falt"><summary>Hvem sitter i ${esc(smaa(utName(m.sc)))} i dag</summary>${medlemHtml(m.sc)}</details>
      <p class="liten"><a href="#hvem-bestemmer/${encodeURIComponent(m.sc)}">Alle utvalgene</a></p>`});
  el.innerHTML=`<div class="moteside"><div class="ingress"><h1>${esc(utName(m.sc))}</h1>
    <p class="mote-fakta"><b>${forst(UKEDAG[new Date(m.date.slice(0,10)+'T12:00').getDay()])} ${datoAar(m.date)}, ${kl(m)}</b>${m.sted||m.rom?`<br>${stedTekst(m)}`:''}</p>
    ${m.op?`<p class="opptak-linje">${opptakLenke(m.op.u,'Se hele opptaket av møtet','knapp')}<span class="liten muted">${m.op.d?`${varighet(m.op.d)} · `:''}hos kommunen${m.op.tx?', med teksting':''}. Hver sak under har lenke til der den starter.</span></p>`:''}
    <div class="tagrad"><span class="st ${st.cls}">${esc(st.t)}</span>${dokKnapp(`dok-mote-${m.id}`,dokumentene)}</div></div>
    ${saker}${om}</div>`;
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
  // Partiene som møtte, som en stolpe og et merke per parti, slik stemmene vises på saken.
  const per=ordne(PORDER_ALLE,[...new Set(o.navn.map(p=>p.p))]).map(p=>({p,n:o.navn.filter(x=>x.p===p).length}));
  return `<div class="oppmote"><p><b>${forst(antall(tot,'person','personer'))} møtte</b>${vara?`, av dem ${antall(vara,'varamedlem','varamedlemmer')}`:''}.</p>
    ${per.length?`<div class="bar">${per.map(({p,n})=>`<span style="flex:${n};background:${pc(p)}" title="${esc(PNAME[p]||p)}: ${n}"></span>`).join('')}${o.andre?`<span style="flex:${o.andre};background:var(--line)" title="Ikke valgt for et parti: ${o.andre}"></span>`:''}</div>
      <p class="pmrad">${per.map(({p,n})=>pm(p,n)).join('')}</p>`:''}
    ${o.andre?`<p class="liten muted">${forst(antall(o.andre,'person','personer'))}${o.navn.length?' til':''} er ikke valgt for et parti og vises ikke.</p>`:''}
    ${liste.length?`<details class="falt"${o.avvik?' open':''}><summary>Se hvem som møtte</summary><ul class="medl">${liste.map(linje).join('')}</ul></details>`:''}
    <p class="liten muted">Ifølge møteprotokollen.</p>${avvik}</div>`;
}
// «PS 13/2026» -> [13, 2026] for sortering.
const _saksnr=nr=>{const t=(nr||'').match(/(\d+)\/(\d+)/);return t?[+t[2],+t[1]]:[0,0]};
const etterNr=(a,b)=>{const ka=_saksnr(a.x.nr),kb=_saksnr(b.x.nr);return ka[0]-kb[0]||ka[1]-kb[1]};
const politisk=c=>c.typ==='PS'&&!c.formal;

/* ---------- BLA I MØTET ---------- */
/* På saken kan man bla til forrige og neste sak på sakslisten til ett møte, i
   samme rekkefølge som på møtesiden, og bare de politiske sakene. Møtet står i
   adressen (#sak/<id>/mote/<id>) når man kommer fra møtet eller har bladd, så
   tilbakeknappen og en delt lenke blar i samme møte. Uten møte i adressen er
   det det siste møtet saken er behandlet i, det fase() kaller «Behandlet i»;
   har saken ikke vært oppe ennå, det neste. */
const sakIMote=(c,m)=>`#sak/${c.id}/mote/${m.id}`;
// En sak kan ha to behandlinger med samme saksnummer i ett møte; den tas med én gang.
const sakslisten=m=>{const sett=new Set();return (SAKER_MOTE[m.id]||[]).filter(o=>politisk(o.c)&&!sett.has(o.c)&&sett.add(o.c)).sort(etterNr)};
const moteNavn=m=>`${smaa(utName(m.sc))} ${ddl(m.date).replace(' ',' ')}${m.date.slice(0,4)===TODAY.slice(0,4)?'':' '+m.date.slice(0,4)}`;
function blaMote(c,mid){
  const holdt=c.st.filter(x=>!isFut(x.date));
  const x=(mid&&c.st.find(x=>x.mid===mid))||[...holdt].reverse().find(x=>!erRad(x.sc))
    ||c.st.find(x=>isFut(x.date)&&!erRad(x.sc))||holdt.at(-1);
  return x&&MOTE_ID[x.mid]||null;
}
// Hvor saken står på sakslisten, og sakene før og etter. Null når det ikke er noe å bla i.
function blaI(c,mid){
  const m=politisk(c)&&blaMote(c,mid);if(!m)return null;
  const liste=sakslisten(m),i=liste.findIndex(o=>o.c===c);
  if(i<0||liste.length<2)return null;
  return {m,i,n:liste.length,navn:moteNavn(m),forrige:liste[i-1]?.c,neste:liste[i+1]?.c};
}
// Øverst, ved «Alle saker»: pilene og hvor man er. Midten går til møtet.
function visBla(b){
  const n=$('sakbla');n.hidden=!b;
  if(!b){n.innerHTML='';return}
  n.setAttribute('aria-label',`Sakene i ${b.navn}`);
  const pil=(s,r)=>s?`<a class="bla-pil" href="${sakIMote(s,b.m)}" data-bla="${r}" aria-label="${r<0?'Forrige':'Neste'} sak i ${esc(b.navn)}: ${esc(tittel(s))}">${ikon(r<0?'forrige':'neste')}</a>`
    :`<span class="bla-pil av" title="${r<0?'Første':'Siste'} sak i møtet" aria-hidden="true">${ikon(r<0?'forrige':'neste')}</span>`;
  n.innerHTML=`${pil(b.forrige,-1)}<a class="bla-mote" href="#mote/${b.m.id}" aria-label="Sak ${b.i+1} av ${b.n} i ${esc(b.navn)}. Gå til møtet"><b>Sak ${b.i+1} av ${b.n}</b> i ${esc(b.navn)}</a>${pil(b.neste,1)}`;
  // Neste sak kan være fra et annet år; detaljene hentes alt nå.
  if(b.neste)hentDetaljer(sakensAar(b.neste)).catch(()=>{});
}
// Nederst, etter kortene: neste sak med tittelen, eller tilbake til møtet etter den siste.
function blaBunn(b){
  if(!b.neste)return `<nav class="bla-slutt" aria-label="Slutten av sakslisten"><p>Det var siste sak i ${esc(b.navn)}.</p><a href="#mote/${b.m.id}">Tilbake til møtet</a></nav>`;
  return `<nav class="bla-videre" aria-label="Videre i ${esc(b.navn)}"><a href="${sakIMote(b.neste,b.m)}" data-bla="1">
    <small>Videre i møtet · sak ${b.i+2} av ${b.n}</small><b>${esc(tittel(b.neste))}</b>${ikon('videre',22)}</a></nav>`;
}
/* Saken glir inn fra den siden man blar mot, og overskriften får fokus, så en
   skjermleser leser den nye saken. Ingen bevegelse med mindre bevegelse. */
const BLA={retning:0};
function blaInn(el){
  const r=BLA.retning;BLA.retning=0;
  if(!MINDRE)el.animate([{opacity:0,transform:`translateX(${r*24}px)`},{opacity:1,transform:'none'}],{duration:TID,easing:GLI});
  const h=el.querySelector('h1');if(h){h.tabIndex=-1;h.focus({preventScroll:true})}
}

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
  const mote=[neste?`Neste møte: <a href="#mote/${neste.id}">${naar(neste.date)}</a>`:'',sist?`Siste møte: <a href="#mote/${sist.id}">${ddl(sist.date)}</a>`:'',antall(ms.filter(m=>!FLERE_AAR||m.date.startsWith(AAR)).length,'møte','møter')+` i ${AAR}`].filter(Boolean).join(' · ');
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

/* ---------- BEVEGELSE ---------- */
/* Det som åpnes og lukkes, glir i stedet for å hoppe. Alt går gjennom Web
   Animations, som virker likt i Safari på iPhone og i Chrome; den nye CSS-en
   for <details> finnes ikke i Safari ennå. Ingenting beveger seg for dem som
   har bedt om mindre bevegelse. Gjelder alle <details> på kommunesiden. */
const MINDRE=matchMedia('(prefers-reduced-motion: reduce)').matches;
const GLI='cubic-bezier(.2,.8,.2,1)',TID=MINDRE?0:300;
/* Høyden fra fra til til. Glir noe fram fra 0 eller bort til 0, følger luft
   og marger med, så det ikke hopper i starten eller slutten. */
function gli(el,fra,til,tone=false){
  if(!TID)return Promise.resolve();
  const cs=getComputedStyle(el),a={height:fra+'px'},b={height:til+'px'};
  ['paddingTop','paddingBottom','marginTop','marginBottom'].forEach(k=>{if(fra===0){a[k]='0px';b[k]=cs[k]}if(til===0){a[k]=cs[k];b[k]='0px'}});
  if(tone){a.opacity=fra<til?0:1;b.opacity=fra<til?1:0}
  const for_={overflow:el.style.overflow,boxSizing:el.style.boxSizing};
  el.style.overflow='hidden';el.style.boxSizing='border-box';
  return el.animate([a,b],{duration:TID,easing:GLI}).finished.catch(()=>{}).then(()=>Object.assign(el.style,for_));
}
// Elementene kommer fram ett etter ett, litt nedenfra.
function etterHverandre(els,fra=0,steg=35){
  if(MINDRE)return;
  [...els].slice(0,12).forEach((e,i)=>e.animate([{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'none'}],{duration:280,delay:fra+i*steg,easing:GLI,fill:'backwards'}));
}
/* <details>: høyden går fra overskriften til alt, og innholdet tones inn.
   data-s sier hvor den er på vei, så pilen snur med en gang man trykker;
   open fjernes først når den er lukket. */
// Mens den glir, gjelder retningen; ellers det nettleseren sier (koden kan ha åpnet den).
const tilstand=d=>d._gaar?d.dataset.s:d.open?'open':'closed';
const innholdI=d=>[...d.children].filter(e=>e.tagName!=='SUMMARY');
function aapne(d){
  if(tilstand(d)==='open'){d.dataset.s='open';return Promise.resolve()}
  const fra=d.offsetHeight;d.dataset.s='open';d.open=true;
  if(MINDRE)return Promise.resolve();
  d._gaar=true;
  innholdI(d).forEach(e=>e.animate([{opacity:0},{opacity:1}],{duration:TID,easing:'ease-out'}));
  innholdI(d).forEach(e=>{const l=e.matches('ul,ol')?e:e.querySelector(':scope>ul,:scope>ol');if(l)etterHverandre(l.children,60)});
  return gli(d,fra,d.offsetHeight).then(()=>{d._gaar=false});
}
function lukk(d){
  if(tilstand(d)==='closed')return Promise.resolve();
  const s=d.querySelector(':scope>summary'),fra=d.offsetHeight,til=s.offsetHeight+(d.offsetHeight-d.clientHeight);
  d.dataset.s='closed';
  if(MINDRE){d.open=false;return Promise.resolve()}
  d._gaar=true;
  const ut=innholdI(d).map(e=>e.animate([{opacity:1},{opacity:0}],{duration:TID*.6,easing:'ease-in',fill:'forwards'}));
  return gli(d,fra,til).then(()=>{d._gaar=false;if(d.dataset.s==='closed')d.open=false;ut.forEach(a=>a.cancel())});
}
// Et element skjult med hidden glir fram eller bort.
function veksle(el,vis){
  if(vis){el.hidden=false;el.dataset.s='open';const l=el.querySelector('ul');if(l)etterHverandre(l.children,40,40);return gli(el,0,el.offsetHeight,true)}
  el.dataset.s='closed';
  return gli(el,el.offsetHeight,0,true).then(()=>{if(el.dataset.s==='closed')el.hidden=true});
}
// Gå til en del av siden: åpne det som er lukket rundt den, rull dit og la den lyse kort opp.
function gaTil(id){
  const m=$(id);if(!m)return;
  const rundt=[];for(let p=m;p;p=p.parentElement)if(p.tagName==='DETAILS')rundt.unshift(p);
  Promise.all(rundt.map(aapne)).then(()=>{
    m.scrollIntoView({behavior:MINDRE?'auto':'smooth',block:'start'});
    if(!MINDRE)m.animate([{boxShadow:'0 0 0 0 transparent'},{boxShadow:'0 0 0 4px var(--lys)',offset:.25},{boxShadow:'0 0 0 0 transparent'}],{duration:1500,delay:300,easing:'ease-out'});
  });
}
document.addEventListener('click',e=>{
  // Bla i møtet: lenken bytter sak selv; her huskes bare retningen for bevegelsen.
  const bl=e.target.closest('[data-bla]');
  if(bl&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&!e.altKey){BLA.retning=+bl.dataset.bla;return}
  const s=e.target.closest('#innhold details>summary');
  if(s&&!e.target.closest('a')){e.preventDefault();const d=s.parentElement;tilstand(d)==='open'?lukk(d):aapne(d);return}
  // Lange vedtaksavsnitt og lister med flere punkter foldes ut.
  const lang=e.target.closest('.vtekst.lang');
  if(lang){const fra=lang.offsetHeight;lang.classList.remove('lang');gli(lang,fra,lang.offsetHeight);return}
  const fl=e.target.closest('[data-flere]');
  if(fl){const l=$(fl.dataset.flere),fra=l.offsetHeight,nye=[...l.children].filter(x=>x.hidden);nye.forEach(x=>x.hidden=false);gli(l,fra,l.offsetHeight);etterHverandre(nye,0,45);fl.remove();return}
  // Avstemningene og stemmetallene i vedtaket viser partiene under.
  const vb=e.target.closest('.vrad>button,.vchip,.dokknapp');
  if(vb){const vis=vb.getAttribute('aria-expanded')!=='true';vb.setAttribute('aria-expanded',vis);veksle($(vb.getAttribute('aria-controls')),vis);return}
  // Et samlet punkt i tidslinjen viser hvilke råd eller utvalg det gjelder.
  const n=e.target.closest('.tidslinje button[data-navn]');
  if(n){const ol=n.closest('.tidslinje');let p=ol.nextElementSibling;const ny=!p||!p.classList.contains('tidslinje-navn');
    if(!ny&&p.textContent===n.dataset.navn){gli(p,p.offsetHeight,0,true).then(()=>p.remove());return}
    if(ny){p=document.createElement('p');p.className='tidslinje-navn';ol.after(p)}
    p.textContent=n.dataset.navn;if(ny)gli(p,0,p.offsetHeight,true);return}
  const fk=e.target.closest('[data-folg]');
  if(fk){folgKlikk(SAK_ID[+fk.dataset.folg]);return}
  const an=e.target.closest('[data-angre]');
  if(an){folgSlutt(SAK_ID[+an.dataset.angre]);return}
  const t=e.target.closest('[data-til]');
  if(t){gaTil(t.dataset.til);const r=$(t.dataset.til);if(r&&r.classList.contains('vrad')){const b=r.querySelector(':scope>button');if(b.getAttribute('aria-expanded')!=='true')b.click()}}
  // Dokumentmenyen lukkes av et trykk utenfor.
  document.querySelectorAll('.dokknapp[aria-expanded="true"]').forEach(k=>{if(!$(k.getAttribute('aria-controls')).contains(e.target)){k.setAttribute('aria-expanded','false');veksle($(k.getAttribute('aria-controls')),false)}});
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.dokknapp[aria-expanded="true"]').forEach(k=>{k.setAttribute('aria-expanded','false');veksle($(k.getAttribute('aria-controls')),false);k.focus()})});
/* Etter at en side er tegnet: kortene glir opp når de kommer inn på skjermen,
   stemplet slås ned på vedtaket, og snarveiene viser hvor man leser. Kalles
   for hver visning som vises (vis under NAVIGASJON) og når saken er tegnet. */
let synlig=null,leser=null;
function bevegelse(rot){
  if(MINDRE||!('IntersectionObserver' in window))return;
  document.documentElement.classList.add('bev');
  synlig?.disconnect();leser?.disconnect();
  // Det som ikke kom fram i en visning man forlot, skal stå synlig når man kommer tilbake.
  document.querySelectorAll('.sakkort:not(.synlig),.stempel:not(.slag)').forEach(e=>{if(!rot.contains(e))e.classList.add(e.classList.contains('stempel')?'slag':'synlig')});
  synlig=new IntersectionObserver(ok=>ok.forEach(o=>{if(o.isIntersecting){o.target.classList.add(o.target.classList.contains('stempel')?'slag':'synlig');synlig.unobserve(o.target)}}),{rootMargin:'0px 0px -6% 0px'});
  rot.querySelectorAll('.sakkort,.stempel').forEach(e=>synlig.observe(e));
  const knapper=[...rot.querySelectorAll('.snarvei button[data-til]')];
  if(!knapper.length)return;
  // Under en fast toppmeny (bred skjerm) står snarveiene rett under den.
  const hode=document.querySelector('.hode'),fast=hode&&getComputedStyle(hode).position==='sticky';
  rot.querySelector('.snarvei').style.top=fast?hode.offsetHeight+'px':'0px';
  // Det som rulles fram, skal ikke havne under toppmenyen og snarveiene (scroll-margin-top i stil.css).
  document.documentElement.style.setProperty('--fast-topp',(fast?hode.offsetHeight:0)+'px');
  const sett=new Map();
  leser=new IntersectionObserver(ok=>{ok.forEach(o=>sett.set(o.target.id,o.isIntersecting));
    const her=knapper.find(b=>sett.get(b.dataset.til));knapper.forEach(b=>b.classList.toggle('her',b===her))},{rootMargin:'-80px 0px -50% 0px'});
  knapper.forEach(b=>{const k=$(b.dataset.til);if(k)leser.observe(k)});
}
// Lesefremdriften: en tynn strek under snarveiene som vokser med saken.
let tegnes=false;
addEventListener('scroll',()=>{if(tegnes)return;tegnes=true;requestAnimationFrame(()=>{tegnes=false;
  const side=document.querySelector('#v-sak:not([hidden]) .saksside.stor'),sv=side&&side.querySelector('.snarvei');if(!sv)return;
  const r=side.getBoundingClientRect();sv.style.setProperty('--fremdrift',(Math.min(1,Math.max(0,-r.top/Math.max(1,r.height-innerHeight)))*100).toFixed(1)+'%')})},{passive:true});

/* ---------- FØLG SAKEN ---------- */
/* «Følg saken» (ADR-027): e-post når saken kommer videre. Hvilke saker
   brukeren følger, hentes fra portalen med tilgangsnøkkelen som konto.js har
   lagret (slik innsyn.js henter dataene), og ligger aldri i dataene på
   nettstedet. Uten bruker går knappen til registreringen i portalen, med
   saken i adressen. Når brukeren kommer tilbake med ?folg=, følges saken, og
   parameteren fjernes. Vi følger behandlingen med samme ID som saken: ID-en
   til saken kan endre seg, men databasen finner saken igjen fra behandlingen. */
const FOLG={saker:null,vis:null};
const BJELLE='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>';
const folger=c=>!!(FOLG.saker&&FOLG.saker.has(c.id));
const folgKnapp=c=>`<button type="button" class="folg" data-folg="${c.id}" aria-pressed="${folger(c)}">${BJELLE}<span>${folger(c)?'Følger':'Følg saken'}</span></button>`;
function folgLes(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(e){return null}}
// Innlogget som i konto.js, og en nøkkel som gjelder minst ett minutt til.
function folgKonto(){
  const k=folgLes('kommunelys-konto'),inn=folgLes('kommunelys-innsyn');
  return {innlogget:!!(k&&k.epost&&Date.now()-k.tid<30*24*3600*1000),
          nokkel:inn&&inn.nokkel&&inn.utloper*1000>Date.now()+60000?inn.nokkel:null};
}
// Innlogget, men nøkkelen er gått ut: portalen gir en ny og sender brukeren
// tilbake, uten å spørre (som innsyn.js). Ellers vet ikke knappen om saken
// følges. Høyst hvert andre minutt, så det aldri går i ring.
function folgForny(til){
  if(FOLG.forny)return;
  try{const sist=+sessionStorage.getItem('kommunelys-innsyn-forsok')||0;if(Date.now()-sist<120000)return;
    sessionStorage.setItem('kommunelys-innsyn-forsok',String(Date.now()))}catch(e){return}
  FOLG.forny=true;location.replace(til);
}
// Tilbake til saken etter registreringen eller innloggingen, med ?folg= før #.
const folgTilbake=c=>`${location.origin}${location.pathname}?folg=${c.id}#sak/${c.id}`;
const folgPortal=(sti,c)=>`${S.portal}${sti}?${new URLSearchParams({grunn:'folg',sak:c.t,tilbake:folgTilbake(c)})}`;
function folgApi(sti,valg={}){
  const b=document.querySelector('.konto');
  return fetch(`${b.dataset.api}/rest/v1/${sti}`,{...valg,cache:'no-store',headers:{apikey:b.dataset.nokkel,
    Authorization:'Bearer '+folgKonto().nokkel,'Accept-Profile':'portal','Content-Profile':'portal',
    'Content-Type':'application/json',Prefer:'return=minimal'}})
    .then(r=>{if(!r.ok){const e=new Error('HTTP '+r.status);e.status=r.status;throw e}return r.status===200?r.json():null});
}
// Sakene brukeren følger i kommunen: {sak-ID: [følgingene]}.
function folgHent(){
  return folgApi(`folger?select=id,sak_id&kommune=eq.${encodeURIComponent(K.slug)}`).then(r=>{
    FOLG.saker=new Map();r.forEach(f=>{if(f.sak_id!=null)FOLG.saker.set(f.sak_id,[...(FOLG.saker.get(f.sak_id)||[]),f.id])});
    folgOppdater();
  });
}
// Knappene på siden viser om saken følges.
function folgOppdater(){
  document.querySelectorAll('[data-folg]').forEach(b=>{const c=SAK_ID[+b.dataset.folg],p=folger(c);
    b.setAttribute('aria-pressed',p);b.querySelector('span').textContent=p?'Følger':'Følg saken'});
}
function folgMelding(c,fulgt,feil){
  const m=document.querySelector('#sak .folg-melding');if(!m)return;
  m.innerHTML=feil?esc(feil):fulgt?`<span><b>Du følger saken.</b> Du får e-post når den kommer videre.</span><button type="button" class="lenkeknapp" data-angre="${c.id}">Angre</button>`
    :'<span>Du følger ikke lenger saken.</span>';
  if(m.hidden)veksle(m,true);
  if(fulgt&&!MINDRE)document.querySelectorAll(`[data-folg="${c.id}"]`).forEach(b=>{b.classList.remove('ringer');void b.offsetWidth;b.classList.add('ringer')});
}
// Nøkkelen godtas ikke: portalen gir en ny og sender brukeren hit igjen.
function folgFeil(c,e){
  if(e.status===401){try{localStorage.removeItem('kommunelys-innsyn')}catch(x){}location.href=folgPortal('/login',c);return}
  folgMelding(c,false,'Det gikk ikke å følge saken nå. Prøv igjen senere.');
}
function folgStart(c){
  return folgApi('folger',{method:'POST',body:JSON.stringify({kommune:K.slug,behandling_id:c.id})})
    .then(folgHent).then(()=>folgMelding(c,true));
}
function folgSlutt(c){
  const ider=(FOLG.saker&&FOLG.saker.get(c.id))||[];
  if(!ider.length)return;
  folgApi(`folger?id=in.(${ider.join(',')})`,{method:'DELETE'}).then(folgHent).then(()=>folgMelding(c,false),e=>folgFeil(c,e));
}
function folgKlikk(c){
  const k=folgKonto();
  if(!k.innlogget){location.href=folgPortal('/registrer',c);return}
  if(!k.nokkel){location.href=folgPortal('/login',c);return}
  if(folger(c))folgSlutt(c);else folgStart(c).catch(e=>folgFeil(c,e));
}
// Ved oppstart: hent hvilke saker brukeren følger, og følg saken i ?folg=.
(function(){
  const q=new URLSearchParams(location.search),ny=+q.get('folg'),k=folgKonto();
  if(q.has('folg')){q.delete('folg');history.replaceState(null,'',location.pathname+(q.toString()?'?'+q:'')+location.hash)}
  if(!k.nokkel){if(ny&&SAK_ID[ny]&&k.innlogget)folgForny(folgPortal('/login',SAK_ID[ny]));return}
  // Er saken ikke tegnet ennå (detaljene hentes), viser renderSak meldingen.
  if(ny&&SAK_ID[ny]){const c=SAK_ID[ny];folgStart(c).then(()=>{if(!document.querySelector(`#sak [data-folg="${ny}"]`))FOLG.vis=ny},e=>folgFeil(c,e));return}
  folgHent().catch(()=>{});
})();

/* ---------- NAVIGASJON ---------- */
const VIEWS=['oversikt','saker','sak','moter','mote','politikere','person','hvem-bestemmer'];
const MENY={person:'politikere',sak:'saker',mote:'moter'};
// Om-siden er felles; ?kommune= holder kommunen i toppen der.
const OM=`../om/?kommune=${encodeURIComponent(K.slug)}`;
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
  const [v0,arg,...mer]=decodeURIComponent(location.hash.slice(1)).split('/');
  // Om-fanen er flyttet til Om-siden, som er felles for alle kommunene.
  if(v0==='om'){location.replace(OM);return}
  // Stemmer er flyttet: stemmene står på sakene, partiene under Politikere.
  if(v0==='stemmer'){location.replace(arg==='partiene'?'#politikere/partiene':arg==='politikerne'?'#politikere':'#saker');return}
  const v=VIEWS.includes(v0)?v0:'oversikt';
  VIEWS.forEach(x=>$('v-'+x).hidden=x!==v);
  document.querySelectorAll('#nav a').forEach(a=>{if(a.dataset.v===(MENY[v]||v))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  // Oversikten har samme tittel som i index.html, som søkemotorene viser.
  document.title=v==='oversikt'?`Politikken i ${K.navn}: saker, vedtak og stemmer | ${S.merke}`:(TITLER[v]?TITLER[v]+' – ':'')+`${K.navn} | ${S.merke}`;
  if(v==='saker'){const f=FANER[arg]?arg:'avgjort';if(f!==sakFane){sakFane=f;limit=40}renderList()}
  if(v==='moter'){kalMnd=/^\d{4}-\d{2}$/.test(arg||'')?arg:mndNaa;renderMeet()}
  if(v==='mote')renderMote(+arg);
  // Partifilteret står i adressen (#politikere/AP), så lenker og tilbakeknappen
  // virker. #politikere/partiene er fanen Partiene.
  if(v==='politikere'){const f=arg==='partiene'?'partiene':'politikerne';visPolFane(f);
    if(f==='politikerne'){fparti=PARTI_I_FOLK.includes(arg)?arg:null;renderFChips();renderFolk()}}
  if(v==='person')renderPerson(arg);
  // #sak/<id>/mote/<id>: møtet man blar i.
  if(v==='sak')visSak(+arg,mer[0]==='mote'?+mer[1]:null);
  // Saken kaller bevegelse selv, når detaljene er hentet.
  else bevegelse($('v-'+v));
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
/* Forsiden: kommunestyret. Står her fordi kortene bruker tidslinjen, fase()
   og stemmestolpen fra saksiden. */
const KS_MOTER=meetings.filter(m=>m.sc===KSK);
const KS_HOLDT=KS_MOTER.filter(m=>!isFut(m.date)),KS_NESTE=KS_MOTER.find(m=>isFut(m.date));
$('alle-ks').dataset.ut=KSK;
// Toppfeltet: siste og neste møte, med lenke til møtet.
(function(){
  const sist=KS_HOLDT.at(-1);
  const venter=sist&&PS.some(c=>c.status==='Venter på protokoll'&&c.st.some(x=>x.mid===sist.id));
  const mote=(m,etikett,tekst)=>`<a class="ksmote" href="#mote/${m.id}"><small>${etikett}</small><b>${naar(m.date)}</b><span>${tekst}</span></a>`;
  $('ksnaa').innerHTML=[
    sist?mote(sist,'Siste møte',[sist.nps?antall(sist.nps,'sak','saker'):'',venter?'protokollen kommer':'',sist.op?'opptak':''].filter(Boolean).join(' · ')):'',
    KS_NESTE?mote(KS_NESTE,'Neste møte',KS_NESTE.nps?`${antall(KS_NESTE.nps,'sak','saker')} på sakslisten`:'Sakslisten er ikke publisert ennå'):''].join('');
})();

/* De viktigste sakene fra de tre siste møtene: to fra det siste og én fra
   hvert av de to før, så det nyeste alltid er med. Har et møte for få, fylles
   det opp fra de andre. Innen møtet får sakene poeng for det saksiden kan vise
   fram: utvalgene saken har vært gjennom, debatt fra opptaket og jevne
   avstemninger. Bare saker med sammendrag er med, og ikke saker om
   enkeltpersoners verv (temaet «Folkevalgte»). */
const VIKTIGE_PLASSER=[2,1,1];
function viktigeSaker(){
  const moter=KS_HOLDT.slice(-VIKTIGE_PLASSER.length).reverse();
  const jevn=vs=>Math.min(...vs.map(v=>Math.abs(v.nfor-v.nmot)));
  const perMote=moter.map(m=>PS.filter(c=>c.a&&c.a.bet&&!(c.tags||[]).includes('Folkevalgte')&&c.st.some(x=>x.mid===m.id)).map(c=>{
    const x=c.st.find(x=>x.mid===m.id);
    const forbi=stiSteg(c).filter(y=>y.date<x.date&&y.sc!==KSK).length;
    const her=ALLEV.filter(v=>v.hid===x.hid&&omstridt(v));
    const tidligere=ALLEV.filter(v=>v.hid!==x.hid&&SAK_FOR[v.hid]===c&&omstridt(v));
    const p=Math.min(forbi,5)+(her.length?3+(jevn(her)<=5?2:0):tidligere.length?2:0)+(x.db?2:0);
    return {c,x,m,p};
  }).sort((a,b)=>b.p-a.p));
  const valgt=perMote.flatMap((s,i)=>s.slice(0,VIKTIGE_PLASSER[i]));
  const rest=perMote.flatMap((s,i)=>s.slice(VIKTIGE_PLASSER[i])).sort((a,b)=>b.p-a.p);
  const n=VIKTIGE_PLASSER.reduce((a,b)=>a+b,0);
  return [...valgt,...rest.slice(0,n-valgt.length)].sort((a,b)=>b.m.date.localeCompare(a.m.date)||b.p-a.p);
}
// Debatten: partiene som hadde ordet, når detaljene er hentet. Uten debatt
// lenker kortet til opptaket, om det finnes.
function vDebatt(x){
  const d=STEG[x.hid].deb;
  if(d&&!d.ing){const pa=ordne(PORDER_ALLE,[...new Set(d.p.flatMap(p=>p.pa||[]))]);
    return `<p>${antall(d.n,'innlegg','innlegg')} fra ${pa.length===1?'ett parti':`${pa.length} partier`}</p><div>${pa.map(p=>pm(p)).join('')}</div>`}
  if(x.db)return '<p class="muted">Henter debatten …</p>';
  return x.op&&x.op.length?opptakLenke(x.op[0].u,'Se debatten i opptaket'):'';
}
// Vedtaket: den delte avstemningen som avgjorde saken, altså et forslag som ble
// vedtatt (ikke et tillegg), ellers forslaget saken kom med. Venter møtet på
// protokoll, vises avstemningen i møtet før, om den var delt.
const vedtatt=v=>!!v.vinner||v.res==='vedtatt';
function vVedtak(c,x){
  if(c.status==='Venter på protokoll'||!x.pub){
    const v=[...ALLEV].reverse().find(v=>SAK_FOR[v.hid]===c&&v.hid!==x.hid&&omstridt(v)&&!erRad(v.usc));
    return `<p>Vedtaket og stemmene kommer med protokollen.</p>${v&&!IKKE_STEMMER?`<p class="liten">I ${esc(smaa(utName(v.usc)))}: <b class="num">${v.nfor} for, ${v.nmot} mot</b></p>${segBar(v)}`:''}`}
  if(IKKE_STEMMER)return '<p>Stemmene vises ikke for denne kommunen ennå.</p>';
  const vs=ALLEV.filter(v=>v.hid===x.hid);
  if(!vs.length)return '<p>Vedtatt uten avstemning med navneliste.</p>';
  const delt=vs.filter(omstridt);
  const v=delt.find(v=>vedtatt(v)&&!/tillegg/.test(v.type||''))||delt.find(vedtatt)||delt.find(v=>v.type==='innstilling')||delt[0]||vs.find(v=>!v.holdt)||vs[0];
  const flere=vs.filter(omstridt).length>1?`<p class="liten muted">${antall(vs.filter(omstridt).length,'delt avstemning','delte avstemninger')} i saken</p>`:'';
  if(v.holdt)return '<p>Stemmene vises ikke ennå.</p>';
  if(v.en)return '<p>Enstemmig</p>';
  if(!omstridt(v))return '<p>Alle stemte for</p>';
  const hvem=v.parti&&v.type!=='innstilling'&&!v.vinner?`Forslaget fra ${esc(v.parti)} ${vedtatt(v)?'vedtatt':'falt'}`:resTxt(v);
  return `<p><span class="res ${vedtatt(v)?'ok':'no'}">${hvem}</span>, <b class="num">${v.nfor} mot ${v.nmot}</b></p>${segBar(v)}${flere}`;
}
function viktigKort({c,x,m}){
  const f=fase(c);
  const deb=x.db||(x.op&&x.op.length)?`<div class="vcelle debatt" id="vdeb-${x.hid}"><span class="vl">${ikon('debatt',16)}Debatten</span>${vDebatt(x)}</div>`:'';
  return `<article class="sakkort vkort">
    <div class="vtopp"><a href="#mote/${m.id}">Kommunestyret ${ddl(m.date)}</a><span class="st ${f.cls}">${c.status==='Vedtatt i kommunestyret'?'Vedtatt':esc(c.status)}</span></div>
    <h3><a href="${sakIMote(c,m)}">${esc(tittel(c))}</a></h3>
    <p class="bet"><span class="ki" title="Skrevet av KI ut fra saksdokumentene">KI</span> ${esc(c.a.bet)}</p>
    ${tidslinje(c,true)}
    <div class="vfakta">${deb}<div class="vcelle vedtak"><span class="vl">${ikon('vedtak',16)}Vedtaket</span>${vVedtak(c,x)}</div></div>
    <a class="kort-lenke" href="${sakIMote(c,m)}">Se hele saken</a>
  </article>`;
}
(function(){
  const vis=viktigeSaker();
  $('viktig').innerHTML=vis.map(viktigKort).join('')||'<p class="muted">Ingen saker med sammendrag fra kommunestyrets siste møter ennå.</p>';
  // Debatten står i detaljene, som hentes nå. Da åpnes saken også raskere.
  vis.filter(o=>o.x.db).forEach(o=>hentDetaljer(sakensAar(o.c)).then(()=>{const e=$('vdeb-'+o.x.hid);if(e)e.innerHTML=`<span class="vl">${ikon('debatt',16)}Debatten</span>${vDebatt(o.x)}`},()=>{const e=$('vdeb-'+o.x.hid);if(e)e.remove()}));
})();
// Temaene med flest saker, som snarveier til sakene.
(function(){
  const n={};PS.forEach(c=>(c.tags||[]).forEach(t=>{n[t]=(n[t]||0)+1}));
  const top=Object.entries(n).sort((a,b)=>b[1]-a[1]).slice(0,8);
  $('temaer').innerHTML=top.length?`<span class="liten muted">Tema:</span>${top.map(([t,k])=>`<a href="#saker" data-go="saker" data-tag="${esc(t)}">${esc(t)} <span class="ant">${k}</span></a>`).join('')}`:'';
})();
renderList();renderMeet();renderHeat();
$('foot').innerHTML=`<div>Kilde: ${esc(K.navn)} kommunes innsynsportal (Elements Publikum): møtekalender, saksprotokoller, møteprotokoller og medlemslister. Data hentet ${dato(TODAY)}.</div><div>${esc(S.merke)} er en uoffisiell tjeneste, laget av en innbygger for innbyggerne. <a href="../">Andre kommuner</a> · <a href="${OM}">Om ${esc(S.merke)}</a></div>`;
window.addEventListener('hashchange',vis);vis();
// Nådde vi hit, er siden tegnet. Ellers viser index.html en feilmelding.
window.KL_KLAR=true;
