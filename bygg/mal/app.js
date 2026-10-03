/* Kommunelys. Bygges av bygg/bygg_nettsted.py.
   Dataene ligger i data/data.js: S (saker, møter, utvalg, kommunestyret og
   de folkevalgte) og VOT (voteringer per møte). Ingenting her er skrevet for
   hånd om enkeltsaker eller enkeltpersoner, og ingen kommune nevnes ved navn:
   det som er særegent for kommunen, står i S.kommune (kommuner/<kommune>.json). */
const TODAY=S.today, AAR=S.aar, K=S.kommune;
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
const SAK_FOR={};S.cases.forEach(c=>c.st.forEach(x=>{SAK_FOR[x.hid]=c}));
const stCls={"Til kommunestyret":"ks","Til behandling":"tb","Vedtatt i kommunestyret":"ok","Behandlet":"bh","Venter på protokoll":"vp","Protokoll ikke publisert":"bh","Unntatt offentlighet":"bh"};
const stPill=s=>`<span class="st ${stCls[s]||'bh'}">${s}</span>`;
/* Sammendrag fra KI (c.a) vises bare når det har bestått kontrollene i bygget. */
const tittel=c=>c.a?c.a.tk:c.t;
const sokTekst=c=>(c.t+' '+(c.a?`${c.a.tk} ${c.a.sum}`:'')).toLowerCase();
const meldUrl=c=>`${S.meld}?title=${encodeURIComponent('Feil i sammendraget: '+(c.first||c.st[0]).nr)}&body=${encodeURIComponent(`Sak: ${c.t}\nSaksnummer: ${(c.first||c.st[0]).nr}\n\nHva er feil?\n`)}`;
const ut=(u,t)=>`<a href="${u}" target="_blank" rel="noopener">${t}</a>`;
function oppsummering(c){
  if(!c.a)return c.typ==='PS'&&!c.formal?'<p class="liten muted">Ingen sammendrag ennå. Les dokumentene i lenkene under.</p>':'';
  const a=c.a;
  return `<div class="ai"><span class="ki">KI-sammendrag</span><p>${esc(a.sum)}</p>${a.bet?`<p><b>Hva betyr det?</b> ${esc(a.bet)}</p>`:''}${a.uen?`<p><b>Uenigheten:</b> ${esc(a.uen)}</p>`:''}
   <p class="aikilde">Skrevet av ${esc(a.modell)} ut fra ${a.kilder.map(k=>ut(k.url,esc(k.tittel))).join(', ')}. Dokumentene gjelder. ${ut(meldUrl(c),'Meld fra om feil')}</p></div>`;
}
function pathHtml(c){
  const seen=[];c.st.forEach(x=>{if(!seen.length||seen[seen.length-1].sc!==x.sc)seen.push(x)});
  return `<span class="sti">${seen.map(x=>x===c.next?`<b title="Neste: ${esc(utName(x.sc))} ${ddn(x.date)}">${esc(x.sc)}</b>`:`<span title="${esc(utName(x.sc))} ${ddn(x.date)}">${esc(x.sc)}</span>`).join(' › ')}</span>`;
}

/* ---------- FOLKEVALGTE OG STEMMER ---------- */
const FOLK=S.folk||[];const PERS={},PID={};FOLK.forEach(p=>{PERS[p.n]=p;PID[p.id]=p});
const plink=n=>PERS[n]?`<a href="#person/${PERS[n].id}">${esc(n)}</a>`:esc(n);
const RANG=K.rekkefolge;
const rang=u=>{const i=RANG.indexOf(u);return i<0?50:i};
const ROLLE_KS={Leder:'ordfører',Nestleder:'varaordfører',Medlem:'fast medlem',Varamedlem:'varamedlem'};
const ROLLE={Leder:'leder',Nestleder:'nestleder',Medlem:'medlem',Varamedlem:'varamedlem'};
const rolle=(u,r)=>(u==='KS'?ROLLE_KS:ROLLE)[r]||(r?String(r).toLowerCase():'rolle ikke oppgitt');
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
   bestemt, og hvordan ble det stemt. Under kortene: hva venter vi på. Ingen
   nøkkeltall; de hjelper ikke innbyggeren med å forstå hva kommunen gjør.
   Kortene viser lite og lenker videre til hele listen. */
const meetings=S.meetings;
const upcoming=meetings.filter(m=>isFut(m.date));
const nextM=upcoming[0];
const tilB=PS.filter(c=>c.next);
const RAD=K.rad;
const UKEDAG=['søndag','mandag','tirsdag','onsdag','torsdag','fredag','lørdag'];
const naar=d=>`${UKEDAG[new Date(d.slice(0,10)+'T12:00').getDay()]} ${ddl(d)}`;
const sakLenke=(c,hid)=>`<a class="t" href="#saker" data-sak="${hid}">${esc(tittel(c))}</a>`;
const smaa=s=>s.charAt(0).toLowerCase()+s.slice(1);
/* Saker gruppert per møte: «Formannskapet onsdag 8. oktober», med de første sakene. */
function moteGrupper(saker,steg,maks,sorter){
  const per=new Map();
  saker.forEach(c=>{const x=steg(c);if(!x)return;if(!per.has(x.mid))per.set(x.mid,{x,saker:[]});per.get(x.mid).saker.push(c)});
  return [...per.values()].sort(sorter).slice(0,maks);
}
function moteHtml(g,vis,ekstra,mer){
  return `<div class="mote-gr"><h3>${esc(utName(g.x.sc))} <span class="muted">${naar(g.x.date)}</span></h3>
    <ul class="saksliste">${g.saker.slice(0,vis).map(c=>`<li>${sakLenke(c,g.x.hid)}${ekstra?ekstra(c,g):''}</li>`).join('')}</ul>
    ${g.saker.length>vis?`<p class="liten">${mer(g)}</p>`:''}</div>`;
}

/* Hva skal skje: de neste politiske møtene og sakene på sakslisten. Råd som
   bare gir uttalelse, hoppes over; saken vises under neste politiske møte. */
(function(){
  const steg=c=>c.st.find(x=>isFut(x.date)&&!RAD.includes(x.sc));
  const gr=moteGrupper(tilB,steg,2,(a,b)=>a.x.date.localeCompare(b.x.date)||(b.x.sc==='KS')-(a.x.sc==='KS'));
  let h=gr.map(g=>moteHtml(g,3,
    (c,g)=>c.ks&&g.x.sc!=='KS'?' <span class="liten muted">· skal videre til kommunestyret</span>':'',
    g=>`<a href="#saker" data-go="saker" data-status="Til" data-ut="${g.x.sc}">${antall(g.saker.length-3,'sak','saker')} til i dette møtet</a>`)).join('');
  const ksM=upcoming.find(m=>m.sc==='KS');
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
    if(vs.every(v=>v.holdt))return 'avstemningene er holdt tilbake';
    if(vs.every(v=>v.en))return 'enstemmig';
    const pub=vs.filter(v=>!v.holdt&&!v.en);
    if(vs.length===1&&!(pub[0].alt&&pub[0].alt.length))return pub[0].nmot?`${pub[0].nfor} mot ${pub[0].nmot} stemmer`:'alle stemte for';
    return antall(vs.length,'avstemning','avstemninger');
  };
  $('nylig').innerHTML=vis.map(c=>{
    const hvor=c.last.sc==='KS'?`Vedtatt i kommunestyret ${ddl(c.last.date)}`:`Avgjort i ${smaa(utName(c.last.sc))} ${ddl(c.last.date)}`;
    const st=stemmer(c);
    return `<li>${sakLenke(c,c.last.hid)}${c.a&&c.a.bet?`<p class="bet">${esc(c.a.bet)}</p>`:''}
      <div class="m">${hvor}${st?` · ${st}`:''}${MED_STEMMER.has(c.last.hid)?` · <a href="#stemmer" data-go="stemmer" data-m="${c.last.mid}">hvem stemte hva</a>`:''}</div></li>`}).join('')
    ||'<li class="muted">Ingen avgjørelser med protokoll ennå.</li>';
})();

/* Hva venter vi på: møter de siste 30 dagene der protokollen ikke er publisert.
   Eldre har status «Protokoll ikke publisert» (tolk/bygg_saker.py). */
(function(){
  const gr=moteGrupper(venter,c=>c.last,4,(a,b)=>b.x.date.localeCompare(a.x.date));
  $('venter').innerHTML=gr.map(g=>moteHtml(g,3,null,
    g=>`<a href="#saker" data-go="saker" data-status="Venter på protokoll" data-ut="${g.x.sc}">${antall(g.saker.length-3,'sak','saker')} til fra dette møtet</a>`)).join('')
    ||'<p class="muted">Alle møter den siste måneden har publisert protokoll.</p>';
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
  const ks=FOLK.flatMap(x=>x.verv.filter(v=>v.u==='KS'&&v.i&&v.p===ksValgt).map(v=>({x,v})));
  const faste=ks.filter(o=>fast(o.v)).sort((a,b)=>rolleRang(a.v.r)-rolleRang(b.v.r)||a.x.n.localeCompare(b.x.n,'nb'));
  const vara=ks.filter(o=>!fast(o.v)).sort((a,b)=>b.v.m-a.v.m||a.x.n.localeCompare(b.x.n,'nb'));
  const li=o=>`<li><a href="#person/${o.x.id}">${esc(o.x.n)}</a>${o.v.r==='Leder'||o.v.r==='Nestleder'?` <small>${rolle('KS',o.v.r)}</small>`:''}${!fast(o.v)?` <small>${o.v.m?`møtt ${antall(o.v.m,'gang','ganger')}`:'ikke møtt'}</small>`:''}</li>`;
  const lenke=partiLenke(ksValgt);
  $('ksparti').innerHTML=`<div class="partivisning"><div class="hode2"><h3><span class="dot" style="background:${pc(ksValgt)}"></span>${esc(PNAME[ksValgt]||ksValgt)}</h3><span class="liten">${lenke?lenke+' · ':''}<a href="#politikere/${ksValgt}">Alle verv i partiet</a></span></div>
   <div class="kol"><div><h3>Faste representanter (${faste.length})</h3><ul>${faste.map(li).join('')}</ul></div><div><h3>Varamedlemmer (${vara.length})</h3><ul>${vara.map(li).join('')||'<li class="muted">Ingen</li>'}</ul></div></div></div>`;
}
$('ks').addEventListener('click',e=>{const t=e.target.closest('[data-p]');if(t&&(t.tagName==='BUTTON'||t.tagName==='circle'))velgParti(t.dataset.p)});

/* Saksflyt */
(function(){
  const HU=K.hovedutvalg;
  const full=PS.filter(c=>{const s=c.st.map(x=>x.sc);return s.includes('KS')&&s.includes('FS')&&s.some(x=>HU.includes(x))}).length;
  const fsks=PS.filter(c=>{const s=[...new Set(c.st.map(x=>x.sc))];return s.join()==='FS,KS'}).length;
  const ksAll=PS.filter(c=>c.ks).length;
  // Bare saker som er avgjort; de som fortsatt er til behandling, kan gå videre.
  const avgjort=c=>c.status!=='Til behandling';
  const fsSelv=PS.filter(c=>c.st.some(x=>x.sc==='FS')&&!c.ks&&avgjort(c)).length;
  const huSelv=PS.filter(c=>c.st.some(x=>HU.includes(x.sc))&&!c.st.some(x=>['FS','KS'].includes(x.sc))&&avgjort(c)).length;
  $('flowfact').innerHTML=`I ${AAR} har ${ksAll} saker vært eller skal til kommunestyret. ${fsks} gikk rett fra formannskapet, og ${full} gikk hele veien fra et hovedutvalg via formannskapet. Formannskapet avgjorde ${fsSelv} saker selv, og hovedutvalgene ${huSelv}.`;
})();

/* Utvalg og roller */
(function(){
  const mc={};meetings.forEach(m=>{mc[m.sc]=(mc[m.sc]||0)+1});
  $('org').innerHTML=K.organer.map(({kode:sc,navn:n,oppgave:o,lenke})=>{if(sc==='KS')o=`${KSN} representanter, ${o}`;
    return `<tr><td>${lenke?`<a href="#politikere" data-utv="${sc}">${esc(n)}</a>`:esc(n)}</td><td class="muted">${esc(o)}</td><td class="num">${mc[sc]||'–'}</td></tr>`}).join('');
})();
$('q0').addEventListener('keydown',e=>{if(e.key==='Enter')go('saker',{q:e.target.value})});

/* ---------- SAKER ---------- */
const STATUSES=["Til kommunestyret","Til behandling","Vedtatt i kommunestyret","Behandlet","Venter på protokoll","Protokoll ikke publisert","Unntatt offentlighet"];
const fstatus=$('fstatus');fstatus.innerHTML+=`<option value="Til">Til behandling (alle)</option>`+STATUSES.map(s=>`<option>${s}</option>`).join('');
const utSet=[...new Set(S.cases.flatMap(c=>c.st.map(x=>x.sc)))].filter(Boolean).sort((a,b)=>utName(a).localeCompare(utName(b),'nb'));
$('fut').innerHTML+=utSet.map(s=>`<option value="${s}">${esc(utName(s))}</option>`).join('');
let ftag=null,limit=40,openT=null,LISTE=[];
const TAGS=[...new Set(PS.flatMap(c=>c.tags))].sort((a,b)=>a.localeCompare(b,'nb'));
function filtered(){
  const q=$('q').value.trim().toLowerCase(),st=fstatus.value,u=$('fut').value,all=$('fall').checked;
  return (all?ALL:PS).filter(c=>(!q||sokTekst(c).includes(q))&&(!st||(st==='Til'?c.status.startsWith('Til'):c.status===st))&&(!u||c.st.some(x=>x.sc===u))&&(!ftag||c.tags.includes(ftag)))
   .sort((a,b)=>{const ka=a.next?'1'+a.next.date:'0'+(a.last?a.last.date:'');const kb=b.next?'1'+b.next.date:'0'+(b.last?b.last.date:'');
     if(ka[0]!==kb[0])return kb[0]-ka[0];return ka[0]==='1'?ka.localeCompare(kb):kb.localeCompare(ka)});
}
function renderTagChips(){
  const cnt=t=>PS.filter(c=>c.tags.includes(t)).length;
  $('tchips').innerHTML=['Alle tema',...TAGS].map(t=>`<button aria-pressed="${(t==='Alle tema'&&!ftag)||t===ftag}" data-t="${t}">${t}${t!=='Alle tema'?`<i>${cnt(t)}</i>`:''}</button>`).join('');
}
$('tchips').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;ftag=b.dataset.t==='Alle tema'?null:b.dataset.t;limit=40;renderTagChips();renderList()});
['q','fstatus','fut','fall'].forEach(id=>$(id).addEventListener('input',()=>{limit=40;renderList()}));
function detail(c){
  const typ={PS:'Politisk sak',OS:'Orienteringssak',RS:'Referatsak',FO:'Sak'}[c.typ]||'Sak';
  return `<div class="det">${oppsummering(c)}<div class="liten muted">${typ}${c.att?` · ${antall(c.att,'vedlegg','vedlegg')}`:''}${c.doc?` · ${ut(c.doc,'Saksframlegget (PDF)')}`:''}</div>
   <div class="steg">${c.st.map(x=>`<div><span class="mono">${dato(x.date)}</span><span><b>${esc(utName(x.sc)||x.ut)}</b> <span class="muted mono">${esc(x.nr)}</span>${isFut(x.date)?' <span class="st tb">kommende</span>':''}</span><span class="lk">${x.prot?ut(x.prot,'Vedtak'):(!isFut(x.date)?'<span class="muted">Ingen protokoll ennå</span>':'')}${MED_STEMMER.has(x.hid)?`<a href="#stemmer" data-go="stemmer" data-m="${x.mid}">Stemmene</a>`:''}${x.murl?ut(x.murl,'Møtet'):''}</span></div>`).join('')}</div></div>`;
}
function renderList(){
  LISTE=filtered();
  $('count').textContent=antall(LISTE.length,'sak','saker');
  $('clist').innerHTML=LISTE.slice(0,limit).map((c,i)=>{const op=openT===c.t;return `<div class="sak"><button aria-expanded="${op}" data-i="${i}">
     <span class="t">${esc(tittel(c))}${c.a?`<span class="o">${esc(c.t)}</span>`:''}</span><span class="r">${stPill(c.status)}<span class="mono muted">${c.next?ddn(c.next.date):c.last?ddn(c.last.date):''}</span></span>
     <span class="m"><span class="mono">${esc(c.first.nr)}</span>${pathHtml(c)}${c.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</span></button>${op?detail(c):''}</div>`}).join('')||'<p class="muted">Ingen saker passer filtrene.</p>';
  const mb=$('more');mb.hidden=LISTE.length<=limit;mb.textContent=`Vis flere (${LISTE.length-limit} til)`;
}
$('clist').addEventListener('click',e=>{const b=e.target.closest('.sak>button');if(!b)return;const c=LISTE[+b.dataset.i];openT=openT===c.t?null:c.t;renderList()});
$('more').addEventListener('click',()=>{limit+=40;renderList()});

/* ---------- MØTER ---------- */
const mut=$('mut');
[...new Set(meetings.map(m=>m.ut))].sort((a,b)=>a.localeCompare(b,'nb')).forEach(u=>mut.innerHTML+=`<option>${esc(u)}</option>`);
function renderMeet(){
  const w=$('mwhen').value,u=mut.value;
  let L=meetings.filter(m=>(!u||m.ut===u)&&(w==='all'||(w==='up'?isFut(m.date):!isFut(m.date))));
  if(w==='past')L=[...L].reverse();
  let h='',cur='';
  L.forEach(m=>{const k=m.date.slice(0,7);if(k!==cur){cur=k;h+=`<h2 class="mnd">${MONL[+k.slice(5)-1]}</h2>`}
    const docs=m.docs.map(d=>ut(d.u,esc(d.t||d.ty))).join('');
    h+=`<div class="mote"><div><b class="mono">${ddn(m.date)}</b> <span class="muted mono">kl. ${m.date.slice(11,16)}</span></div><div><b>${esc(m.ut)}</b><div class="liten muted">${esc([m.sted,m.rom].filter(Boolean).join(', '))}${m.sted||m.rom?' · ':''}${m.n?antall(m.n,'sak','saker'):'sakslisten er ikke publisert'}</div></div><div class="docs">${docs}${ut(m.url,'Sakslisten')}</div></div>`});
  $('mlist').innerHTML=h||'<p class="muted">Ingen møter.</p>';
}
$('mwhen').addEventListener('input',renderMeet);mut.addEventListener('input',renderMeet);

/* ---------- STEMMER ---------- */
/* Skrevet for folk som ikke kjenner møteordningen: «avstemning», ikke
   «votering», og «forslaget saken kom med» foran «innstillingen». Hver sak
   forteller først hva som skjedde, så hvilke forslag som ble vedtatt og
   hvilke som falt. */
const vsel=$('vsel');
(function(){
  const utv=[...new Set(VOT.moter.map(m=>m.sc))].sort((a,b)=>(b==='KS')-(a==='KS')||(b==='FS')-(a==='FS')||utName(a).localeCompare(utName(b),'nb'));
  vsel.innerHTML=utv.map(u=>{const ms=VOT.moter.filter(m=>m.sc===u).reverse();
    return `<optgroup label="${esc(utName(u))}">${ms.map(m=>`<option value="m:${m.id}">${esc(utName(u))} ${ddl(m.date)} ${m.date.slice(0,4)} (${antall(m.saker.reduce((n,s)=>n+s.v.length,0),'avstemning','avstemninger')})</option>`).join('')}<option value="u:${u}">${esc(utName(u))}: alle møter i ${AAR}</option></optgroup>`}).join('');
  // Først vises siste kommunestyremøte der avstemningene er publisert.
  const ks=[...VOT.moter].reverse().find(m=>m.sc==='KS'&&m.saker.some(s=>s.v.some(v=>!v.holdt)));
  if(ks)vsel.value='m:'+ks.id;else if(utv.length)vsel.value='u:'+utv[0];
})();
let V=[],contested=[],pstats=[],VID={};
const pord=ns=>ordne(PORDER_ALLE,[...new Set(ns.map(party))]);
function segBar(v){const seg=ns=>{const c={};ns.forEach(n=>{const p=party(n);c[p]=(c[p]||0)+1});return pord(ns).map(p=>`<span style="flex:${c[p]};background:${pc(p)}" title="${esc(PNAME[p]||p)}: ${c[p]}"></span>`).join('')};
  return `<div class="bar" role="img" aria-label="${v.nfor} stemte for, ${v.nmot} stemte mot">${seg(v.f)}${v.nfor&&v.nmot?'<span class="gap"></span>':''}${v.nmot?`<span style="flex:${v.nmot};display:flex;gap:1px;opacity:.45">${seg(v.m)}</span>`:''}</div>`}
function namesBlock(v){
  const sides=SIDES.get(v.id)||{};
  const grp=(ns,side)=>{const by={};ns.forEach(n=>{(by[party(n)]=by[party(n)]||[]).push(n)});return pord(ns).map(p=>`<div class="pg"><span class="sq" style="background:${pc(p)}"></span><b>${p}</b> ${by[p].map(n=>side&&sides[p]!==side?`<span class="cross" title="Stemte annerledes enn partiet">${plink(n)}</span>`:plink(n)).join(', ')}</div>`).join('')||'<span class="muted">Ingen</span>'};
  const borte=v.borte&&v.borte.length?`<div class="vmeta">Ikke til stede: ${v.borte.map(plink).join(', ')}</div>`:'';
  const merkForklart=`<div class="vmeta">Uthevet: stemte annerledes enn resten av partiet.</div>`;
  if(erAlt(v))return `<div class="names">${v.alt.map(a=>`<div><h4>Stemte for forslag ${esc(a.fs)} (${a.n})</h4>${grp(a.navn,null)}</div>`).join('')}${borte}</div>`;
  return `<div class="names"><div><h4 style="color:var(--good)">Stemte for (${v.nfor})</h4>${grp(v.f,'for')}</div><div><h4 style="color:var(--bad)">Stemte mot (${v.nmot})</h4>${grp(v.m,'mot')}</div>${borte}${merkForklart}</div>`}

/* Hva et forslag heter, i vanlige ord. */
const SLAG={forslag:'Forslag','alternative forslag':'Alternativt forslag',tilleggsforslag:'Tilleggsforslag',endringsforslag:'Endringsforslag'};
const erAlt=v=>!!(v.alt&&v.alt.length);
const fra=d=>d.bak?`fra ${d.bak}`:d.parti?`fra ${PNAME[d.parti]||d.parti}`:d.stiller?`fra ${d.stiller}`:'';
const forslagNavn=d=>d.type==='innstilling'?'Forslaget saken kom med':`${SLAG[d.type]||'Forslag'} ${fra(d)}`.trim();
const enNavn=v=>!v.lbl||/innstilling|forslag til vedtak/i.test(v.lbl)?'Forslaget saken kom med':v.lbl;
const typeNavn=v=>v.en?enNavn(v):erAlt(v)?'Valg mellom forslag':forslagNavn(v);
const fremmetAv=d=>d.stiller?`Fremmet av ${plink(d.stiller)}${d.parti?' ('+esc(d.parti)+')':''}.`:'';
const innstMerke=d=>d.type==='innstilling'?' <span class="muted">(innstillingen)</span>':'';
const vedtatt=v=>v.en||erAlt(v)||v.res==='vedtatt';

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
/* Én setning om hva som skjedde i saken. Bare fra dataene. */
function sakSvar(s){
  const org=utName(s.m.sc),vs=s.v,pub=vs.filter(v=>!v.holdt),nh=vs.length-pub.length;
  const holdtTxt=nh?` ${nh===1?'Én avstemning er':`${nh} avstemninger er`} holdt tilbake.`:'';
  if(vs.length===1){
    const v=vs[0];
    if(v.holdt)return `${org} stemte over saken, men avstemningen er holdt tilbake.`;
    if(v.en)return `${org} vedtok saken. Alle stemte for.`;
    if(erAlt(v))return `${org} valgte mellom ${v.deler&&v.deler.length===2?'to':v.deler?v.deler.length:'flere'} forslag. ${altVinner(v)}`;
    const forslaget=v.type==='innstilling'?'forslaget saken kom med':'ett forslag';
    if(!v.nmot)return `${org} stemte over ${forslaget}. Det ble vedtatt. Alle ${v.nfor} stemte for.`;
    return `${org} stemte over ${forslaget}. Det ble ${v.res==='vedtatt'?'vedtatt':'ikke vedtatt'}: ${v.nfor} stemte for og ${v.nmot} mot.`;
  }
  const innst=vs.some(v=>v.type==='innstilling'),andre=vs.some(v=>v.type!=='innstilling'&&!v.en);
  // «Fremmet i møtet», ikke «fra partiene»: i noen utvalg sitter ansatte, ikke partier.
  const over=innst&&andre?'over forslaget saken kom med og over andre forslag fremmet i møtet':innst?'over forslaget saken kom med, del for del':'over forslag fremmet i møtet';
  const nv=pub.filter(vedtatt).length,nf=pub.length-nv,alle=pub.length===2?'Begge':'Alle';
  const utfall=!pub.length?'':!nf?`${alle} ble vedtatt.`:!nv?`${alle} falt.`:`${nv} ble vedtatt og ${nf} falt.`;
  return [`${org} stemte ${vs.length} ganger i denne saken, ${over}.`,utfall,holdtTxt.trim()].filter(Boolean).join(' ');
}

function delBlokk(d,a,vinner){
  const vant=d.fs===vinner;
  return `<div class="altdel${vant?' vant':''}"><div class="vot-topp"><div><b>Forslag ${esc(d.fs)}: ${esc(forslagNavn(d))}</b>${innstMerke(d)}</div><div class="vot-res">${a?antall(a.n,'stemme','stemmer'):''}${vant?' <span class="res ok">vant</span>':''}</div></div>${d.stiller?`<div class="liten muted">${fremmetAv(d)}</div>`:''}<p class="utdrag">${esc(d.tekst)}</p></div>`;
}
function vrow(v){
  const merk=(v.merk||[]).map(t=>`<div class="merk">Merknad: ${esc(t)}</div>`).join('');
  const navn=!v.holdt&&!v.en;
  if(erAlt(v)&&v.deler&&!v.holdt){
    const a={};v.alt.forEach(x=>{a[x.fs]=x});
    return `<div class="vot" data-v="${v.id}"><div class="vot-topp"><div><b>Valg mellom ${v.deler.length} forslag</b> <span class="muted">· alle stemte for ett av dem</span></div></div>
     ${v.deler.map(d=>delBlokk(d,a[d.fs],v.vinner)).join('')}${merk}
     <button class="mer" aria-expanded="false">Vis hele forslagene og hvem som stemte hva</button><div class="full" hidden></div></div>`;
  }
  const tekst=v.en?'':(v.tekst||'');
  const tall=v.holdt?'':v.en?'Alle stemte for':`${v.nfor} for, ${v.nmot} mot`;
  const ekstra=v.dob?` Avgjort med ${esc(v.dob)}s dobbeltstemme.`:'';
  const knapp=navn?(tekst.length>150?'Vis hele forslaget og hvem som stemte hva':'Vis hvem som stemte hva'):tekst.length>150?'Vis hele forslaget':'';
  return `<div class="vot${v.holdt?' held':''}" data-v="${v.id}">
   <div class="vot-topp"><div><b>${esc(typeNavn(v))}</b>${v.en?'':innstMerke(v)}</div><div class="vot-res num">${tall}</div></div>
   ${v.stiller||ekstra?`<div class="liten muted">${fremmetAv(v)}${ekstra}</div>`:''}
   ${tekst?`<p class="utdrag">${esc(tekst)}</p>`:''}
   ${navn?segBar(v):''}${v.holdt?`<p class="why">${esc(v.holdt)}</p>`:''}${merk}
   ${knapp?`<button class="mer" aria-expanded="false">${knapp}</button><div class="full" hidden></div>`:''}</div>`;
}
function apneVot(b){
  const el=b.closest('.vot'),v=VID[el.dataset.v],full=el.querySelector('.full');
  const apen=b.getAttribute('aria-expanded')==='true';
  if(!apen&&!full.innerHTML){
    const tekst=erAlt(v)&&v.deler?v.deler.map(d=>`<h4>Forslag ${esc(d.fs)}: ${esc(forslagNavn(d))}</h4>${formater(d.tekst)}`).join(''):v.en?'':formater(v.tekst);
    full.innerHTML=(tekst?`<div class="forslag">${tekst}</div>`:'')+(!v.holdt&&!v.en?namesBlock(v):'');
  }
  full.hidden=apen;el.classList.toggle('apen',!apen);b.setAttribute('aria-expanded',String(!apen));
  if(!b.dataset.lukket)b.dataset.lukket=b.textContent;
  b.textContent=apen?b.dataset.lukket:'Skjul';
}
function gruppe(tittel,cls,liste){
  if(!liste.length)return '';
  return `<details class="gruppe"${liste.length<=4?' open':''}><summary><span class="${cls}">${tittel}</span> <span class="muted">(${liste.length})</span></summary><div class="vots">${liste.map(vrow).join('')}</div></details>`;
}
function sakKort(s,visMote){
  const sak=SAK_FOR[s.hid];
  const pub=s.v.filter(v=>!v.holdt);
  const ja=pub.filter(vedtatt).sort((a,b)=>(b.type==='innstilling')-(a.type==='innstilling'));
  const nei=pub.filter(v=>!vedtatt(v));
  // Uenigheten fra sammendraget gjelder hele saken. Hele sammendraget står på saken.
  const uen=sak&&sak.a&&sak.a.uen?`<div class="sum"><span class="ki">KI-sammendrag</span><p><b>Uenigheten:</b> ${esc(sak.a.uen)}</p><p class="aikilde">Protokollen gjelder. ${ut(meldUrl(sak),'Meld fra om feil')}</p></div>`:'';
  return `<article class="vc"><div class="liten muted"><span class="mono">${esc(s.nr)}</span>${visMote?` · ${esc(utName(s.m.sc))} ${ddl(s.m.date)}`:''}</div>
    <h3>${esc(sak?tittel(sak):s.t)}</h3>${sak&&sak.a?`<div class="liten muted">${esc(s.t)}</div>`:''}
    <p class="svar">${sakSvar(s)}</p>${uen}
    ${gruppe('Vedtatt','ok',ja)}${gruppe('Falt','no',nei)}${gruppe('Holdt tilbake','ks',s.v.filter(v=>v.holdt))}
    ${sak?`<p class="liten"><a href="#saker" data-sak="${s.hid}">Mer om saken</a></p>`:''}</article>`;
}
function renderStemmer(){
  const val=vsel.value;
  const ms=val.startsWith('u:')?VOT.moter.filter(m=>m.sc===val.slice(2)):VOT.moter.filter(m=>'m:'+m.id===val);
  const saker=ms.flatMap(m=>m.saker.map(s=>({...s,m})));
  VID={};saker.forEach(s=>s.v.forEach(v=>{VID[v.id]=v}));
  V=saker.flatMap(s=>s.v).filter(v=>!v.holdt&&!v.en);
  contested=V.filter(v=>v.nfor>0&&v.nmot>0);
  const members=[...new Set(V.flatMap(v=>[...v.f,...v.m]))];
  pstats=members.map(n=>{const p=party(n);let tot=0,maj=0,brk=0;contested.forEach(v=>{const s=voteOf(v,n);if(!s)return;tot++;if(s===(v.res==='vedtatt'?'for':'mot'))maj++;if(SIDES.get(v.id)[p]!==s)brk++});return {name:n,party:p,tot,maj:tot?maj/tot:0,brk,prop:V.filter(v=>v.stiller===n).length}});
  const flere=ms.length>1;
  $('vcards').innerHTML=ms.map(m=>{const ss=saker.filter(s=>s.m===m);
    return (flere?`<h3 class="motehode">${esc(utName(m.sc))} ${ddl(m.date)} ${m.date.slice(0,4)}</h3>`:`<p class="liten muted motelinje">${esc(utName(m.sc))}, møtet ${ddl(m.date)} ${m.date.slice(0,4)}: ${antall(ss.length,'sak','saker')} med avstemninger.</p>`)+ss.map(s=>sakKort(s,false)).join('')}).join('')||'<p class="muted">Ingen avstemninger for dette valget.</p>';
  $('ncont').textContent=contested.length;
  selP=null;renderPC();renderPT();renderPP();renderHeat();
}
$('vcards').addEventListener('click',e=>{const b=e.target.closest('button.mer');if(b)apneVot(b)});
// Valget står i adressen: #stemmer/KS for et utvalg, #stemmer/1285 for ett møte.
const stemmeArg=val=>val.slice(2);
vsel.addEventListener('input',()=>{history.replaceState(null,'','#stemmer/'+stemmeArg(vsel.value));renderStemmer()});
let pf=null,sk='maj',sd=-1,selP=null;
function renderPC(){const ps=ordne(PORDER_ALLE,[...new Set(pstats.map(x=>x.party))]);$('pchips').innerHTML=['Alle',...ps].map(p=>`<button aria-pressed="${(p==='Alle'&&!pf)||p===pf}" data-p="${p}">${p==='Alle'?'Alle partier':`<span class="sq" style="background:${pc(p)}"></span>${p}`}</button>`).join('')}
$('pchips').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;pf=b.dataset.p==='Alle'?null:b.dataset.p;renderPC();renderPT()});
function sortPil(tabell,k,d){document.querySelectorAll(`#${tabell} th[data-k]`).forEach(th=>{if(th.dataset.k===k)th.setAttribute('aria-sort',d>0?'ascending':'descending');else th.removeAttribute('aria-sort')})}
document.querySelector('#ptable thead').addEventListener('click',e=>{const th=e.target.closest('th[data-k]');if(!th)return;const k=th.dataset.k;if(sk===k)sd*=-1;else{sk=k;sd=(k==='name'||k==='party')?1:-1}renderPT()});
function renderPT(){const rows=pstats.filter(x=>!pf||x.party===pf).sort((a,b)=>{const A=a[sk],B=b[sk];return (typeof A==='string'?A.localeCompare(B,'nb'):A-B)*sd||a.name.localeCompare(b.name,'nb')});
  sortPil('ptable',sk,sd);
  document.querySelector('#ptable tbody').innerHTML=rows.map(x=>`<tr class="klikk" tabindex="0" data-n="${esc(x.name)}" aria-selected="${x.name===selP}"><td>${esc(x.name)}</td><td><span class="sq" style="background:${pc(x.party)}"></span>${x.party}</td><td class="num">${x.tot?Math.round(x.maj*100)+' %':'–'}<span class="meter"><i style="width:${x.maj*100}%"></i></span></td><td class="num">${x.brk||'–'}</td><td class="num">${x.prop||'–'}</td></tr>`).join('')||'<tr><td colspan="5" class="muted">Ingen avstemninger med navneliste.</td></tr>'}
const velgP=tr=>{if(!tr)return;selP=tr.dataset.n;renderPT();renderPP()};
document.querySelector('#ptable tbody').addEventListener('click',e=>velgP(e.target.closest('tr[data-n]')));
document.querySelector('#ptable tbody').addEventListener('keydown',e=>{if(e.key==='Enter')velgP(e.target.closest('tr[data-n]'))});
const vlinje=(v,vo,ekstra)=>`<div class="vrow"><span class="muted">${ddn(v.dato)} ${esc(v.usc)}</span><span><a href="#saker" data-sak="${v.hid}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a><br><span class="liten muted klipp">${esc(typeNavn(v))}: ${esc(v.lbl)}</span>${ekstra||''}</span><span class="v ${vo||''}">${vo==='for'?'For':vo==='mot'?'Mot':''}</span><span class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></div>`;
function renderPP(){const el=$('ppanel');
  if(!selP){el.innerHTML=`<p class="liten muted">Trykk på et navn i tabellen for å se hvordan personen stemte.</p>`;return}
  const s=pstats.find(x=>x.name===selP);
  el.innerHTML=`<div class="liten muted">${esc(PNAME[s.party]||s.party)}</div><h3>${plink(s.name)}</h3><p class="liten">Stemte som flertallet i ${Math.round(s.maj*100)} % av ${s.tot} avstemninger der noen stemte imot. Stemte annerledes enn partiet ${antall(s.brk,'gang','ganger')}. Fremmet ${antall(s.prop,'forslag','forslag')}.${PERS[s.name]?` <a href="#person/${PERS[s.name].id}">Se hele profilen</a>`:''}</p>`+
   contested.map(v=>{const vo=voteOf(v,selP);if(!vo)return'';const br=SIDES.get(v.id)[s.party]!==vo;return vlinje(v,vo,br?' <span class="cross">· annerledes enn partiet</span>':'')}).join('')}
function renderHeat(){
  const ps=ordne(PORDER_ALLE,[...new Set(contested.flatMap(v=>Object.keys(SIDES.get(v.id))))]);
  const agree=(a,b)=>{let n=0,k=0;contested.forEach(v=>{const s=SIDES.get(v.id);if(s[a]&&s[b]){n++;if(s[a]===s[b])k++}});return n?k/n:null};
  let h=`<tr><th></th>${ps.map(p=>`<th><span class="sq" style="background:${pc(p)}"></span>${p}</th>`).join('')}</tr>`;
  ps.forEach(a=>{h+=`<tr><th class="rh">${esc(PNAME[a]||a)}</th>`+ps.map(b=>{if(a===b)return `<td style="background:var(--soft);color:var(--muted)">–</td>`;const r=agree(a,b);if(r===null)return '<td class="muted">·</td>';const pct=Math.round(r*100);return `<td title="${a} og ${b} stemte likt i ${pct} %" style="background:color-mix(in srgb,var(--ink) ${Math.max(6,pct)}%,var(--bg));color:${pct>55?'var(--bg)':'var(--ink)'}">${pct}</td>`}).join('')+'</tr>'});
  $('heat').innerHTML=contested.length?h:'<tr><td class="muted">Ingen avstemninger der noen stemte imot.</td></tr>';
  $('close').innerHTML=contested.filter(v=>Math.abs(v.nfor-v.nmot)<=3).map(v=>{const s=SIDES.get(v.id);const cross=[...v.f.filter(n=>s[party(n)]!=='for'),...v.m.filter(n=>s[party(n)]!=='mot')];
    return `<div class="jevn"><div><span><span class="mono muted">${esc(v.sak)}</span> <b>${esc(typeNavn(v))}:</b> ${esc(v.lbl)}</span><span><b class="num">${v.nfor} for, ${v.nmot} mot</b> <span class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></span></div>${segBar(v)}<div class="liten muted">${cross.length?'Stemte annerledes enn partiet: '+cross.map(n=>`<span class="cross">${plink(n)} (${party(n)})</span>`).join(', '):'Alle stemte som partiet sitt.'}</div>${(v.merk||[]).map(t=>`<div class="merk">Merknad: ${esc(t)}</div>`).join('')}</div>`}).join('')||'<p class="muted">Ingen avstemninger ble avgjort med tre stemmer eller mindre.</p>';
}

/* ---------- POLITIKERE ---------- */
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
  const ks=vv.find(v=>v.u==='KS');
  const hoved=ks?(fast(ks)?`${rolle('KS',ks.r)[0].toUpperCase()+rolle('KS',ks.r).slice(1)} i kommunestyret`:'Varamedlem i kommunestyret'):'Verv i kommunens utvalg';
  const st=stemmeStat(p.n);
  const varaFor=[...new Set(p.verv.flatMap(v=>v.for))].sort((a,b)=>a.localeCompare(b,'nb'));
  const lenke=partiLenke(p.p);
  const rad=v=>`<tr><td>${esc(utName(v.u))}${v.p&&v.p!==p.p?` <span class="liten muted">(for ${esc(PNAME[v.p]||v.p)})</span>`:''}</td><td>${rolle(v.u,v.r)}</td><td class="num">${v.m||'–'}</td><td class="num">${S.mprot[v.u]||'–'}</td></tr>`;
  const pct=st.omst.length?Math.round(st.maj/st.omst.length*100):0;
  const sakLenke=v=>`<a href="#saker" data-sak="${v.hid}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a>`;
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
      ${st.mine.length?`<p class="oppsum">Har vært med på ${antall(st.mine.length,'avstemning','avstemninger')} med navneliste i ${AAR}.${st.omst.length?` I de ${st.omst.length} der noen stemte imot, var stemmen den samme som flertallets i ${pct} % av tilfellene, og annerledes enn resten av partiet ${antall(st.brk.length,'gang','ganger')}.`:''}</p>`
        :`<p class="oppsum muted">Ingen avstemninger med navneliste i ${AAR}. Når alle stemmer likt, har protokollen ingen navneliste.</p>`}
      ${st.brk.length?`<details${st.brk.length<=8?' open':''}><summary>Stemte annerledes enn partiet (${st.brk.length})</summary><div>${st.brk.map(v=>vlinje(v,voteOf(v,p.n))).join('')}</div></details>`:''}
      ${st.omst.length?`<details><summary>Alle avstemninger der noen stemte imot (${st.omst.length})</summary><div>${st.omst.map(v=>vlinje(v,voteOf(v,p.n))).join('')}</div></details>`:''}
    </section>
    <section><h2>Forslag</h2>
      ${st.forslag.length?st.forslag.map(v=>vlinje(v,null)).join(''):`<p class="muted">Ingen forslag med navn i protokollene i ${AAR}.</p>`}
    </section>
    <p class="liten muted mt">Kilder: medlemslisten i innsynsportalen (${dato(S.ks.hentet)}), møteprotokollene og saksprotokollene for ${AAR}.${HOLDT?` ${antall(HOLDT,'avstemning','avstemninger')} som er holdt tilbake, er ikke med.`:''} Ingen tekst her er skrevet av KI.</p>
  </div>`;
}

/* ---------- NAVIGASJON ---------- */
const VIEWS=['oversikt','saker','moter','stemmer','politikere','person','om'];
const MENY={person:'politikere'};
const TITLER={oversikt:'',saker:'Saker',moter:'Møter',stemmer:'Hvem stemte hva',politikere:'Politikerne',om:'Slik fungerer det'};
function go(v,o={}){
  if(v==='saker'&&('q' in o||'status' in o||'tag' in o)){
    $('q').value=o.q||'';fstatus.value=o.status||'';$('fut').value=o.ut||'';ftag=o.tag||null;limit=40;openT=o.open||null;
    if(o.alle)$('fall').checked=true;
  }
  if(v==='stemmer'&&o.m)o.arg=o.m;
  if(v==='politikere'&&'utv' in o){futv.value=o.utv||'';fparti=null}
  const h='#'+v+(o.arg?'/'+o.arg:'');
  if(location.hash===h)vis();else location.hash=h;
}
function vis(){
  const [v0,arg]=decodeURIComponent(location.hash.slice(1)).split('/');
  const v=VIEWS.includes(v0)?v0:'oversikt';
  VIEWS.forEach(x=>$('v-'+x).hidden=x!==v);
  document.querySelectorAll('#nav a').forEach(a=>{if(a.dataset.v===(MENY[v]||v))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  document.title=(TITLER[v]?TITLER[v]+' – ':'')+`${K.navn} | ${S.merke}`;
  if(v==='saker'){renderTagChips();renderList()}
  if(v==='moter')renderMeet();
  if(v==='stemmer'&&arg){const val=(/^\d+$/.test(arg)?'m:':'u:')+arg;if(vsel.querySelector(`option[value="${val}"]`)&&vsel.value!==val){vsel.value=val;renderStemmer()}}
  // Partifilteret står i adressen (#politikere/AP), så lenker og tilbakeknappen virker.
  if(v==='politikere'){fparti=PARTI_I_FOLK.includes(arg)?arg:null;renderFChips();renderFolk()}
  if(v==='person')renderPerson(arg);
  window.scrollTo({top:0});
}
document.addEventListener('click',e=>{
  const s=e.target.closest('[data-sak]');
  if(s){e.preventDefault();const c=SAK_FOR[s.dataset.sak];if(c)go('saker',{q:c.t,open:c.t,alle:!PS.includes(c)});return}
  const u=e.target.closest('[data-utv]');
  if(u){e.preventDefault();go('politikere',{utv:u.dataset.utv});return}
  // Søkeikonet i menyen: til sakene, med markøren i søkefeltet. Feltet kan
  // først få fokus når visningen er vist, altså etter hashchange.
  if(e.target.closest('[data-sok]')){e.preventDefault();
    if(location.hash==='#saker')$('q').focus();
    else{window.addEventListener('hashchange',()=>$('q').focus(),{once:true});go('saker')}
    return}
  const g=e.target.closest('a[data-go]');
  if(g){e.preventDefault();const o={};['status','tag','m','ut'].forEach(k=>{if(g.dataset[k]!==undefined)o[k]=g.dataset[k]});go(g.dataset.go,o)}
});
/* Forsiden, «Se stemmene»: siste kommunestyremøte med publiserte avstemninger
   der noen stemte imot, ellers siste møte i et annet utvalg. De jevneste først.
   Står her fordi den bruker segBar og resten av stemmedelen. */
(function(){
  const omstridte=m=>m.saker.flatMap(s=>s.v.filter(omstridt));
  const ms=[...VOT.moter].reverse();
  const m=ms.find(m=>m.sc==='KS'&&omstridte(m).length)||ms.find(m=>omstridte(m).length);
  if(!m){$('stemkort').innerHTML='<p class="muted">Ingen avstemninger der noen stemte imot ennå.</p>';return}
  // Én avstemning per sak, den jevneste, så kortet viser tre ulike saker.
  const vs=omstridte(m),diff=v=>Math.abs(v.nfor-v.nmot),perSak=new Map();
  vs.forEach(v=>{const x=perSak.get(v.hid);if(!x||diff(v)<diff(x))perSak.set(v.hid,v)});
  const jevne=[...perSak.values()].sort((a,b)=>diff(a)-diff(b)).slice(0,3);
  $('stemkort').innerHTML=`<div class="mote-gr"><h3>${esc(utName(m.sc))} <span class="muted">${naar(m.date)}</span></h3>
    <p class="liten muted">${antall(vs.length,'avstemning','avstemninger')} der noen stemte imot. De jevneste:</p>
    <ul class="saksliste">${jevne.map(v=>`<li><a class="t" href="#saker" data-sak="${v.hid}">${esc(SAK_FOR[v.hid]?tittel(SAK_FOR[v.hid]):v.sak)}</a>${segBar(v)}<div class="liten"><b class="num">${v.nfor} for, ${v.nmot} mot</b> · <span class="res ${v.vinner||v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></div></li>`).join('')}</ul></div>`;
  const l=$('stemlenke');l.href='#stemmer/'+m.id;l.dataset.go='stemmer';l.dataset.m=m.id;
})();
renderTagChips();renderList();renderMeet();renderStemmer();
$('repo').href=S.repo;
$('foot').innerHTML=`<div>Kilde: ${esc(K.navn)} kommunes innsynsportal (Elements Publikum): møtekalender, saksprotokoller, møteprotokoller og medlemslister. Data hentet ${dato(TODAY)}.</div><div>${esc(S.merke)} er en uoffisiell tjeneste. Ikke laget av ${esc(K.navn)} kommune. <a href="../">Andre kommuner</a> · ${ut(S.repo,'Kode og data')}</div>`;
window.addEventListener('hashchange',vis);vis();
