/* Steinkjer i klartekst. Bygges av bygg/bygg_nettsted.py.
   Dataene ligger i data/data.js: S (saker, møter, utvalg, kommunestyret)
   og VOT (voteringer per møte). Ingenting her er skrevet for hånd om enkeltsaker. */
const TODAY=S.today, AAR=S.aar;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const MON=['jan','feb','mar','apr','mai','jun','jul','aug','sep','okt','nov','des'];
const MONL=['Januar','Februar','Mars','April','Mai','Juni','Juli','August','September','Oktober','November','Desember'];
const dd=d=>`${+d.slice(8,10)}. ${MON[+d.slice(5,7)-1]}`;
const ddn=d=>d?`${d.slice(8,10)}.${d.slice(5,7)}`:'';
const isFut=d=>(d||'').slice(0,10)>=TODAY;
const PNAME=S.partier;
const PORDER_ALLE=["AP","SP","H","R","INP","FRP","SV","PP","V","UAVH"];
const SPECTRUM_ALLE=["R","SV","AP","SP","UAVH","INP","PP","V","H","FRP"];
const ordne=(rekke,finnes)=>[...rekke.filter(p=>finnes.includes(p)),...finnes.filter(p=>!rekke.includes(p)).sort()];
const SEATS=S.ks.seter;
const KSN=Object.values(SEATS).reduce((a,b)=>a+b,0);
const PORDER=ordne(PORDER_ALLE,Object.keys(SEATS));
const SPECTRUM=ordne(SPECTRUM_ALLE,Object.keys(SEATS));
const pc=p=>`var(--p-${p},var(--muted))`;
const UTN={};Object.entries(S.utvalg).forEach(([n,c])=>{if(c)UTN[c]=n});
const SHORTN={KS:"Kommunestyret",FS:"Formannskapet",HPNM:"Hovedutvalg plan, næring og miljø",HOK:"Hovedutvalg oppvekst og kultur",HHO:"Hovedutvalg helse og omsorg"};
const utName=c=>SHORTN[c]||UTN[c]||c;
document.querySelectorAll('.aar').forEach(e=>e.textContent=AAR);

const PS=S.cases.filter(c=>c.typ==='PS'&&!c.formal);
PS.forEach(c=>{c.next=c.st.find(x=>isFut(x.date))||null;c.last=c.st.filter(x=>!isFut(x.date)).pop()||null;c.first=c.st[0];});
const antall=(n,en,flere)=>`${n} ${n===1?en:flere}`;
const stCls={"Til kommunestyret":"ks","Til behandling":"tb","Vedtatt i kommunestyret":"ok","Behandlet":"bh","Venter på protokoll":"vp"};
const stPill=s=>`<span class="st ${stCls[s]||'bh'}">${s}</span>`;
function pathHtml(c){
  const seen=[];c.st.forEach(x=>{if(!seen.length||seen[seen.length-1].sc!==x.sc)seen.push(x)});
  return `<div class="path">${seen.map((x,i)=>`${i?'<i>›</i>':''}<span class="${isFut(x.date)?(x===c.next?'next':''):'done'}" title="${esc(utName(x.sc))} ${ddn(x.date)}">${esc(x.sc)}</span>`).join('')}</div>`;
}
document.getElementById('upd').textContent=`${dd(TODAY)} ${AAR}`;

/* ---------- OVERSIKT ---------- */
const meetings=S.meetings;
const upcoming=meetings.filter(m=>isFut(m.date));
const nextM=upcoming[0];
const tilB=PS.filter(c=>c.next);
const ksDone=PS.filter(c=>c.status==='Vedtatt i kommunestyret');
const hor=PS.filter(c=>c.tags.includes('Høring'));
const ico=(path,col)=>`<div class="ic" style="background:color-mix(in srgb,${col} 14%,var(--surface));color:${col}"><svg viewBox="0 0 24 24" stroke="${col}">${path}</svg></div>`;
const K=[
 {l:`Saker i ${AAR}`,n:PS.length,s:"politiske saker i alle utvalg",i:ico('<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>','var(--accent)'),go:['saker','']},
 {l:"Til behandling",n:tilB.length,s:"står på sakslisten til et kommende møte",i:ico('<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>','var(--warn)'),go:['saker','Til']},
 {l:"Vedtatt i kommunestyret",n:ksDone.length,s:"endelige vedtak hittil i år",i:ico('<path d="M5 12l5 5 9-10"/>','var(--good)'),go:['saker','Vedtatt i kommunestyret']},
 {l:"Høringssaker",n:hor.length,s:"der kommunen gir eller ber om innspill",i:ico('<path d="M4 5h16v10H9l-5 4z"/>','var(--info)'),go:['saker','','Høring']},
 {l:"Neste møte",n:nextM?ddn(nextM.date):'–',s:nextM?nextM.ut:'',i:ico('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>','var(--bad)'),go:['moter']}
];
document.getElementById('kpis').innerHTML=K.map((k,i)=>`<div class="kpi clk" tabindex="0" data-k="${i}">${k.i}<div style="min-width:0"><div class="l">${k.l}</div><div class="n">${k.n}</div><div class="s">${esc(k.s)}</div></div></div>`).join('');
document.getElementById('kpis').addEventListener('click',e=>{const k=e.target.closest('.kpi');if(k){const g=K[+k.dataset.k].go;go(g[0],{status:g[1],tag:g[2]})}});
document.getElementById('kpis').addEventListener('keydown',e=>{if(e.key==='Enter'){const k=e.target.closest('.kpi');if(k)k.click()}});

const akt=[...tilB].sort((a,b)=>a.next.date.localeCompare(b.next.date)||(b.next.sc==='KS')-(a.next.sc==='KS'));
const RAD=['ELRÅ','UNGRÅ','RÅFIM'];const aktPick=akt.filter(c=>!c.st.every(x=>RAD.includes(x.sc))).slice(0,9);
document.getElementById('aktuelle').innerHTML=aktPick.map(c=>`<tr class="clk" tabindex="0" data-t="${esc(c.t)}"><td><div style="font-weight:600">${esc(c.t)}</div><div class="muted mono" style="font-size:11.5px">${esc(c.first.nr)}</div></td><td>${stPill(c.status)}</td><td>${pathHtml(c)}</td><td class="nw mono">${ddn(c.next.date)}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">Ingen saker står på sakslisten til et kommende møte.</td></tr>';
document.getElementById('aktuelle').addEventListener('click',e=>{const tr=e.target.closest('tr[data-t]');if(tr)go('saker',{q:tr.dataset.t,open:true})});

/* Kommunestyret: halvsirkel med plassene fra medlemslisten */
document.getElementById('kssub').textContent=`${KSN} representanter · fra medlemslisten ${ddn(S.ks.hentet)}.${S.ks.hentet.slice(0,4)}`;
(function(){
  const N=KSN,rows=4,R0=60,R1=118,W=260,Hh=130,cx=130,cy=124;
  if(!N)return;
  const radii=[...Array(rows)].map((_,i)=>R0+i*(R1-R0)/(rows-1));
  const tot=radii.reduce((a,b)=>a+b,0);
  let cnt=radii.map(r=>Math.round(N*r/tot));let diff=N-cnt.reduce((a,b)=>a+b,0);cnt[rows-1]+=diff;
  const pts=[];radii.forEach((r,i)=>{for(let k=0;k<cnt[i];k++){const a=Math.PI*(1-k/Math.max(cnt[i]-1,1));pts.push({x:cx+r*Math.cos(a),y:cy-r*Math.sin(a),a})}});
  pts.sort((p,q)=>q.a-p.a);
  const cols=[];SPECTRUM.forEach(p=>{for(let i=0;i<SEATS[p];i++)cols.push(p)});
  document.getElementById('hemi').innerHTML=`<svg viewBox="0 0 ${W} ${Hh+8}" role="img" aria-label="Kommunestyret: ${N} representanter fordelt på partier">${pts.map((p,i)=>`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="7.2" fill="${pc(cols[i])}"><title>${esc(PNAME[cols[i]]||cols[i])}</title></circle>`).join('')}<text x="${cx}" y="${cy-14}" text-anchor="middle" font-family="Literata,Georgia,serif" font-weight="650" font-size="28" fill="var(--ink)">${N}</text><text x="${cx}" y="${cy+2}" text-anchor="middle" font-size="11" fill="var(--muted)">representanter</text></svg>`;
  document.getElementById('seats').innerHTML=PORDER.map(p=>`<tr><td><span class="dot" style="background:${pc(p)}"></span><abbr title="${esc(PNAME[p]||p)}">${p}</abbr></td><td class="num">${SEATS[p]}</td><td class="num">${(SEATS[p]/N*100).toFixed(1).replace('.',',')} %</td></tr>`).join('');
})();

/* Saksflyt */
(function(){
  const full=PS.filter(c=>{const s=c.st.map(x=>x.sc);return s.includes('KS')&&s.includes('FS')&&s.some(x=>['HPNM','HOK','HHO'].includes(x))}).length;
  const fsks=PS.filter(c=>{const s=[...new Set(c.st.map(x=>x.sc))];return s.join()==='FS,KS'}).length;
  const ksAll=PS.filter(c=>c.ks).length;
  document.getElementById('flowfact').innerHTML=`I ${AAR} har <b>${ksAll}</b> saker vært eller skal til kommunestyret. <b>${fsks}</b> gikk rett fra formannskapet, og <b>${full}</b> gikk hele veien fra et hovedutvalg via formannskapet.`;
})();

/* Utvalg og roller */
(function(){
  const mc={};meetings.forEach(m=>{mc[m.sc]=(mc[m.sc]||0)+1});
  const b=(sc,name,sub,top)=>`<div class="ob${top?' top':''}"><b>${name}</b><small>${[sub,mc[sc]?`${mc[sc]} møter`:''].filter(Boolean).join(' · ')}</small></div>`;
  document.getElementById('org').innerHTML=`
   <div class="lvl l1">${b('KS','Kommunestyret',`${KSN} representanter, øverste organ`,true)}</div>
   <div class="olbl">Forbereder og avgjør</div>
   <div class="lvl l2">${b('FS','Formannskapet','innstiller til kommunestyret')}${b('KN','Klagenemnda','behandler klager')}</div>
   <div class="olbl">Hovedutvalg</div>
   <div class="lvl l3">${b('HPNM','Plan, næring og miljø','arealplaner, landbruk')}${b('HOK','Oppvekst og kultur','skole, barnehage, kultur')}${b('HHO','Helse og omsorg','helse, omsorg, velferd')}</div>
   <div class="olbl">Råd som gir uttalelser</div>
   <div class="lvl l4">${b('ELRÅ','Eldrerådet','')}${b('UNGRÅ','Ungdomsrådet','')}${b('RÅFIM','Rådet for personer med funksjonsnedsettelse','')}</div>`;
})();

/* Kommende møter */
function mcard(m){return `<a class="mc" href="${m.url}" target="_blank" rel="noopener"><div class="d">${+m.date.slice(8,10)}<small>${MON[+m.date.slice(5,7)-1]}</small></div><div style="min-width:0"><b>${esc(m.ut)}</b><span>kl. ${m.date.slice(11,16)} · ${esc(m.sted||'')}</span><br><span>${m.nps?antall(m.nps,'politisk sak','politiske saker'):m.n?antall(m.n,'sak','saker'):'Saksliste ikke publisert'}</span></div></a>`}
document.getElementById('kommende').innerHTML=upcoming.slice(0,8).map(mcard).join('')||'<div class="muted">Ingen kommende møter er publisert.</div>';

/* I tall: bare tall som regnes ut fra dataene, ingen tekst skrevet for hånd */
(function(){
  const nextKS=upcoming.find(m=>m.sc==='KS'),fsNext=upcoming.find(m=>m.sc==='FS');
  const box=(col,tt,body,btn)=>`<div class="ic2" style="background:color-mix(in srgb,${col} 10%,var(--surface))"><div class="tt" style="color:${col}">${tt}</div><p>${body}</p>${btn||''}</div>`;
  const bokser=[];
  if(fsNext||nextKS){
    const linjer=[];
    if(fsNext)linjer.push(`Formannskapet møtes ${dd(fsNext.date)}${fsNext.nps?` med ${antall(fsNext.nps,'politisk sak','politiske saker')}`:''}.`);
    if(nextKS)linjer.push(`Kommunestyret møtes ${dd(nextKS.date)}${nextKS.n?` med ${antall(nextKS.n,'sak','saker')}`:'; sakslisten er ikke publisert ennå'}.`);
    bokser.push(box('var(--warn)','Neste politiske møter',linjer.join(' '),`<button class="more" data-go="saker" data-status="Til">Se sakene →</button>`));
  }
  bokser.push(box('var(--info)',`${hor.length} høringssaker i år`,'Saker der kommunen gir eller ber om innspill, merket ut fra sakstittelen.',`<button class="more" data-go="saker" data-tag="Høring">Se høringene →</button>`));
  const ksAlle=VOT.moter.filter(m=>m.sc==='KS');
  const ksM=[...ksAlle].reverse().find(m=>m.saker.some(s=>s.v.some(v=>!v.holdt)));
  if(ksM){
    const vs=ksM.saker.flatMap(s=>s.v);const holdt=vs.filter(v=>v.holdt).length;
    const omst=vs.filter(v=>!v.holdt&&v.nfor>0&&v.nmot>0).sort((a,b)=>Math.abs(a.nfor-a.nmot)-Math.abs(b.nfor-b.nmot));
    const nyere=ksAlle.filter(m=>m.date>ksM.date);
    let t=`${antall(vs.length,'votering','voteringer')} i kommunestyret ${dd(ksM.date)}.`;
    if(omst.length)t+=` ${omst.length} var omstridte, og den jevneste endte ${omst[0].nfor}–${omst[0].nmot}.`;
    if(holdt)t+=` ${holdt} er holdt tilbake fordi protokollen er selvmotsigende.`;
    if(nyere.length)t+=` Voteringene fra ${nyere.map(m=>dd(m.date)).join(' og ')} er holdt tilbake til kommunen har svart på hvem som møtte.`;
    bokser.push(box('var(--good)',`Kommunestyret ${dd(ksM.date)}`,t,`<button class="more" data-go="stemmer" data-m="${ksM.id}">Se hvem som stemte hva →</button>`));
  }
  document.getElementById('ins').innerHTML=bokser.join('');
})();
document.getElementById('v-oversikt').addEventListener('click',e=>{
  const b=e.target.closest('[data-go],[data-q]');if(!b||b.closest('#kpis'))return;
  if(b.dataset.q)go('saker',{q:b.dataset.q,open:true});else go(b.dataset.go,{status:b.dataset.status,tag:b.dataset.tag,m:b.dataset.m});
});
document.getElementById('q0').addEventListener('keydown',e=>{if(e.key==='Enter')go('saker',{q:e.target.value})});

/* ---------- ALLE SAKER ---------- */
const ALL=S.cases.filter(c=>!c.formal);
ALL.forEach(c=>{if(!c.first){c.next=c.st.find(x=>isFut(x.date))||null;c.last=c.st.filter(x=>!isFut(x.date)).pop()||null;c.first=c.st[0]}});
const STATUSES=["Til kommunestyret","Til behandling","Vedtatt i kommunestyret","Behandlet","Venter på protokoll"];
const fstatus=document.getElementById('fstatus');fstatus.innerHTML+=`<option value="Til">Til behandling (alle)</option>`+STATUSES.map(s=>`<option>${s}</option>`).join('');
const utSet=[...new Set(S.cases.flatMap(c=>c.st.map(x=>x.sc)))].filter(Boolean).sort((a,b)=>utName(a).localeCompare(utName(b),'nb'));
document.getElementById('fut').innerHTML+=utSet.map(s=>`<option value="${s}">${esc(utName(s))}</option>`).join('');
let ftag=null,limit=40,openT=null;
const TAGS=[...new Set(PS.flatMap(c=>c.tags))].sort((a,b)=>a.localeCompare(b,'nb'));
function filtered(){
  const q=document.getElementById('q').value.trim().toLowerCase();const st=fstatus.value;const ut=document.getElementById('fut').value;const all=document.getElementById('fall').checked;
  return (all?ALL:PS).filter(c=>(!q||c.t.toLowerCase().includes(q))&&(!st||(st==='Til'?c.status.startsWith('Til'):c.status===st))&&(!ut||c.st.some(x=>x.sc===ut))&&(!ftag||c.tags.includes(ftag)))
   .sort((a,b)=>{const ka=a.next?'1'+a.next.date:'0'+(a.last?a.last.date:'');const kb=b.next?'1'+b.next.date:'0'+(b.last?b.last.date:'');
     if(ka[0]!==kb[0])return kb[0]-ka[0];return ka[0]==='1'?ka.localeCompare(kb):kb.localeCompare(ka)});
}
function renderTagChips(){
  const cnt=t=>PS.filter(c=>c.tags.includes(t)).length;
  document.getElementById('tchips').innerHTML=['Alle',...TAGS].map(t=>`<button class="chip" aria-pressed="${(t==='Alle'&&!ftag)||t===ftag}" data-t="${t}">${t}${t!=='Alle'?`<i>${cnt(t)}</i>`:''}</button>`).join('');
}
document.getElementById('tchips').addEventListener('click',e=>{const b=e.target.closest('.chip');if(!b)return;ftag=b.dataset.t==='Alle'?null:b.dataset.t;limit=40;renderTagChips();renderList()});
['q','fstatus','fut','fall'].forEach(id=>document.getElementById(id).addEventListener('input',()=>{limit=40;renderList()}));
function detail(c){
  const typ={PS:'Politisk sak',OS:'Orienteringssak',RS:'Referatsak',FO:'Sak'}[c.typ]||'Sak';
  return `<div class="det"><div class="muted">${typ}${c.att?` · ${c.att} vedlegg`:''}${c.doc?` · <a href="${c.doc}" target="_blank" rel="noopener">Les saksframlegget (PDF)</a>`:''}</div>
   <div class="steps">${c.st.map(x=>`<div class="stp"><span class="mono">${ddn(x.date)}.${(x.date||'').slice(2,4)}</span><span><b>${esc(utName(x.sc)||x.ut)}</b> <span class="muted mono" style="font-size:12px">${esc(x.nr)}</span>${isFut(x.date)?' <span class="st tb" style="margin-left:4px">kommende</span>':''}</span><span class="lk">${x.prot?`<a href="${x.prot}" target="_blank" rel="noopener">Vedtak</a>`:(!isFut(x.date)?'<span class="muted">Ingen protokoll ennå</span>':'')}${x.murl?`<a href="${x.murl}" target="_blank" rel="noopener">Møtet</a>`:''}</span></div>`).join('')}</div></div>`;
}
function renderList(){
  const L=filtered();
  document.getElementById('count').textContent=`${L.length} saker`;
  document.getElementById('clist').innerHTML=L.slice(0,limit).map((c,i)=>{const op=openT===c.t;return `<div class="ci"><button aria-expanded="${op}" data-i="${i}">
     <span class="t">${esc(c.t)}</span><span class="r">${stPill(c.status)}<span class="mono muted" style="font-size:12px">${c.next?ddn(c.next.date):c.last?ddn(c.last.date):''}</span></span>
     <span class="m"><span class="mono">${esc(c.first.nr)}</span>${pathHtml(c)}${c.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</span></button>${op?detail(c):''}</div>`}).join('')||'<div class="panel muted">Ingen saker passer filtrene.</div>';
  const mb=document.getElementById('more');mb.hidden=L.length<=limit;mb.textContent=`Vis flere (${L.length-limit} til)`;
  window._L=L;
}
document.getElementById('clist').addEventListener('click',e=>{const b=e.target.closest('.ci>button');if(!b)return;const c=window._L[+b.dataset.i];openT=openT===c.t?null:c.t;renderList()});
document.getElementById('more').addEventListener('click',()=>{limit+=40;renderList()});

/* ---------- MØTER ---------- */
const mut=document.getElementById('mut');
[...new Set(meetings.map(m=>m.ut))].sort((a,b)=>a.localeCompare(b,'nb')).forEach(u=>mut.innerHTML+=`<option>${esc(u)}</option>`);
function renderMeet(){
  const w=document.getElementById('mwhen').value,u=mut.value;
  let L=meetings.filter(m=>(!u||m.ut===u)&&(w==='all'||(w==='up'?isFut(m.date):!isFut(m.date))));
  if(w==='past')L=[...L].reverse();
  let h='',cur='';
  L.forEach(m=>{const k=m.date.slice(0,7);if(k!==cur){cur=k;h+=`<div class="mon">${MONL[+k.slice(5)-1]}</div>`}
    const docs=m.docs.map(d=>`<a href="${d.u}" target="_blank" rel="noopener">${esc(d.t||d.ty)}</a>`).join('');
    h+=`<div class="mi"><div><b class="mono">${ddn(m.date)}</b> <span class="muted mono">kl. ${m.date.slice(11,16)}</span></div><div style="min-width:0"><b>${esc(m.ut)}</b><div class="muted" style="font-size:12.5px">${esc([m.sted,m.rom].filter(Boolean).join(' · '))} · ${m.n?antall(m.n,'sak','saker'):'saksliste ikke publisert'}</div></div><div class="docs">${docs}<a href="${m.url}" target="_blank" rel="noopener">Sakslisten</a></div></div>`});
  document.getElementById('mlist').innerHTML=h||'<div class="panel muted">Ingen møter.</div>';
}
document.getElementById('mwhen').addEventListener('input',renderMeet);mut.addEventListener('input',renderMeet);

/* ---------- STEMMEGIVNING ---------- */
const party=n=>VOT.parti[n]||'?';
const vsel=document.getElementById('vsel');
(function(){
  const utv=[...new Set(VOT.moter.map(m=>m.sc))].sort((a,b)=>(b==='KS')-(a==='KS')||(b==='FS')-(a==='FS')||utName(a).localeCompare(utName(b),'nb'));
  vsel.innerHTML=utv.map(u=>{const ms=VOT.moter.filter(m=>m.sc===u);
    return `<optgroup label="${esc(utName(u))}"><option value="u:${u}">${esc(utName(u))}: alle møter i ${AAR}</option>${ms.map(m=>`<option value="m:${m.id}">${esc(utName(u))} ${ddn(m.date)}: ${m.saker.reduce((n,s)=>n+s.v.length,0)} voteringer</option>`).join('')}</optgroup>`}).join('');
  if(utv.includes('KS'))vsel.value='u:KS';
})();
let V=[],contested=[],sides=new Map(),members=[],pstats=[],VID={};
const voteOf=(v,n)=>v.f.includes(n)?'for':v.m.includes(n)?'mot':null;
function groupSide(v){const c={};v.f.forEach(n=>{const p=party(n);(c[p]=c[p]||{f:0,m:0}).f++});v.m.forEach(n=>{const p=party(n);(c[p]=c[p]||{f:0,m:0}).m++});const o={};for(const p in c)o[p]=c[p].f>=c[p].m?'for':'mot';return o}
const pord=ns=>ordne(PORDER_ALLE,[...new Set(ns.map(party))]);
function segBar(v){const seg=ns=>{const c={};ns.forEach(n=>{const p=party(n);c[p]=(c[p]||0)+1});return pord(ns).map(p=>`<span style="flex:${c[p]};background:${pc(p)}" title="${esc(PNAME[p]||p)}: ${c[p]}"></span>`).join('')};
  return `<div class="bar" role="img" aria-label="${v.nfor} for, ${v.nmot} mot">${seg(v.f)}${v.nfor&&v.nmot?'<span class="gap"></span>':''}${v.nmot?`<span style="flex:${v.nmot};display:flex;opacity:.45">${seg(v.m)}</span>`:''}</div>`}
function namesBlock(v){
  const grp=(ns,side)=>{const by={};ns.forEach(n=>{(by[party(n)]=by[party(n)]||[]).push(n)});return pord(ns).map(p=>`<div class="pg"><span class="sq" style="background:${pc(p)}"></span><b>${p}</b> ${by[p].map(n=>side&&sides.get(v.id)&&sides.get(v.id)[p]!==side?`<span class="cross" title="Stemte annerledes enn egen gruppe">${esc(n)}</span>`:esc(n)).join(', ')}</div>`).join('')||'<span class="muted">Ingen</span>'};
  const borte=v.borte&&v.borte.length?`<div class="vmeta">Ikke til stede: ${v.borte.map(esc).join(', ')}</div>`:'';
  if(v.alt&&v.alt.length)return `<div class="names altl">${v.alt.map(a=>`<div><h4>Forslag ${esc(a.fs)} (${a.n})</h4>${grp(a.navn,null)}</div>`).join('')}${borte}</div>`;
  return `<div class="names"><div><h4 style="color:var(--good)">For (${v.nfor})</h4>${grp(v.f,'for')}</div><div><h4 style="color:var(--bad)">Mot (${v.nmot})</h4>${grp(v.m,'mot')}</div>${borte}</div>`}
const stillerTxt=v=>v.type==='innstilling'?'Innstillingen':v.type==='enstemmig'?'':v.stiller?`${esc(v.stiller)}${v.parti?' ('+esc(v.parti)+')':''}`:esc(v.type);
const resTxt=v=>v.res==='vedtatt'?'Vedtatt':'Falt';
function vrow(v){
  const merk=(v.merk||[]).map(t=>`<div class="merk">Merknad: ${esc(t)}</div>`).join('');
  if(v.holdt)return `<div class="row held"><div><div class="w">${esc(v.lbl)}</div><div class="who">${stillerTxt(v)}</div></div><div class="nums">–</div><div class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</div><div class="why">${esc(v.holdt)}</div></div>`;
  if(v.en)return `<div class="row held"><div><div class="w">${esc(v.lbl)}</div><div class="who">Ingen navneliste i protokollen</div></div><div class="nums"></div><div class="res ok">Enstemmig</div></div>${merk}`;
  const tall=v.alt&&v.alt.length?v.alt.map(a=>a.n).join(' / '):`${v.nfor}–${v.nmot}`;
  const dob=v.dob?` · avgjort med ${v.dob}s dobbeltstemme`:'';
  return `<div class="row" tabindex="0" data-v="${v.id}"><div><div class="w">${esc(v.lbl)}</div><div class="who">${stillerTxt(v)}${v.alt&&v.alt.length?' · alternativ votering':''}${dob}</div></div><div class="mini">${segBar(v)}</div><div class="nums">${tall}</div><div class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</div></div><div data-nb="${v.id}" hidden></div>${merk}`;
}
function renderStemmer(){
  const val=vsel.value;
  const ms=val.startsWith('u:')?VOT.moter.filter(m=>m.sc===val.slice(2)):VOT.moter.filter(m=>'m:'+m.id===val);
  const saker=ms.flatMap(m=>m.saker.map(s=>({...s,m})));
  VID={};saker.forEach(s=>s.v.forEach(v=>{v.id=`${s.hid}-${v.nr}`;v.sak=s.nr;VID[v.id]=v}));
  V=saker.flatMap(s=>s.v).filter(v=>!v.holdt&&!v.en);
  contested=V.filter(v=>v.nfor>0&&v.nmot>0);
  sides=new Map(V.map(v=>[v.id,groupSide(v)]));
  members=[...new Set(V.flatMap(v=>[...v.f,...v.m]))];
  pstats=members.map(n=>{const p=party(n);let tot=0,maj=0,brk=0;contested.forEach(v=>{const s=voteOf(v,n);if(!s)return;tot++;if(s===(v.res==='vedtatt'?'for':'mot'))maj++;if(sides.get(v.id)[p]!==s)brk++});return {name:n,party:p,tot,maj:tot?maj/tot:0,brk,prop:V.filter(v=>v.stiller===n).length}});
  document.getElementById('vcards').innerHTML=saker.map(s=>{
    const omst=s.v.filter(v=>!v.holdt&&!v.en&&v.nfor>0&&v.nmot>0).sort((a,b)=>Math.abs(a.nfor-a.nmot)-Math.abs(b.nfor-b.nmot));
    const alleEn=s.v.every(v=>v.en);const holdt=s.v.filter(v=>v.holdt).length;
    const badge=alleEn?'<span class="st ok" style="justify-self:start">Enstemmig vedtatt</span>':holdt?`<span class="st ks" style="justify-self:start">${holdt} holdt tilbake</span>`:'';
    const score=omst.length?`<div class="score">${omst[0].nfor}–${omst[0].nmot}<small>jevneste votering</small></div>`:'';
    return `<article class="vc"><div class="vtop"><div><div class="muted" style="font-size:12.5px"><span class="mono">${esc(s.nr)}</span> · ${esc(utName(s.m.sc))} ${ddn(s.m.date)}</div><h3 style="margin-top:4px">${esc(s.t)}</h3></div>
    <div style="display:grid;gap:6px;align-content:start">${badge}${score}${omst.length?segBar(omst[0]):''}</div></div>
    <details${s.v.length<=3?' open':''}><summary>${s.v.length} ${s.v.length===1?'votering':'voteringer'}</summary><div style="margin-top:8px">${s.v.map(vrow).join('')}</div></details></article>`}).join('')||'<div class="panel muted">Ingen voteringer for dette valget.</div>';
  document.getElementById('ncont').textContent=contested.length;
  selP=null;renderPC();renderPT();renderPP();renderHeat();
}
function toggleRow(r){if(!r)return;const id=r.dataset.v;const nb=document.querySelector(`[data-nb="${id}"]`);if(nb.hidden){nb.innerHTML=namesBlock(VID[id]);nb.hidden=false;r.classList.add('sel')}else{nb.hidden=true;r.classList.remove('sel')}}
document.getElementById('vcards').addEventListener('click',e=>toggleRow(e.target.closest('.row[data-v]')));
document.getElementById('vcards').addEventListener('keydown',e=>{if(e.key==='Enter'){toggleRow(e.target.closest('.row[data-v]'))}});
vsel.addEventListener('input',renderStemmer);
let pf=null,sk='maj',sd=-1,selP=null;
function renderPC(){const ps=ordne(PORDER_ALLE,[...new Set(pstats.map(x=>x.party))]);document.getElementById('pchips').innerHTML=['Alle',...ps].map(p=>`<button class="chip" aria-pressed="${(p==='Alle'&&!pf)||p===pf}" data-p="${p}">${p==='Alle'?p:`<span class="sq" style="background:${pc(p)}"></span>${p}`}</button>`).join('')}
document.getElementById('pchips').addEventListener('click',e=>{const b=e.target.closest('.chip');if(!b)return;pf=b.dataset.p==='Alle'?null:b.dataset.p;renderPC();renderPT()});
document.querySelector('#ptable thead').addEventListener('click',e=>{const th=e.target.closest('th');if(!th)return;const k=th.dataset.k;if(sk===k)sd*=-1;else{sk=k;sd=(k==='name'||k==='party')?1:-1}renderPT()});
function renderPT(){const rows=pstats.filter(x=>!pf||x.party===pf).sort((a,b)=>{const A=a[sk],B=b[sk];return (typeof A==='string'?A.localeCompare(B,'nb'):A-B)*sd||a.name.localeCompare(b.name,'nb')});
  document.querySelector('#ptable tbody').innerHTML=rows.map(x=>`<tr class="clk" tabindex="0" data-n="${esc(x.name)}" style="${x.name===selP?'background:var(--accent-soft)':''}"><td>${esc(x.name)}</td><td><span class="sq" style="background:${pc(x.party)}"></span>${x.party}</td><td class="num">${x.tot?Math.round(x.maj*100)+' %':'–'}<span class="meter"><i style="width:${x.maj*100}%"></i></span></td><td class="num">${x.brk||'–'}</td><td class="num">${x.prop||'–'}</td></tr>`).join('')||'<tr><td colspan="5" class="muted">Ingen voteringer med navneliste.</td></tr>'}
document.querySelector('#ptable tbody').addEventListener('click',e=>{const tr=e.target.closest('tr[data-n]');if(!tr)return;selP=tr.dataset.n;renderPT();renderPP()});
function renderPP(){const el=document.getElementById('ppanel');
  if(!selP){el.innerHTML=`<div class="eyebrow">Velg en representant</div><p class="muted" style="margin:4px 0 0">Klikk et navn i tabellen for å se hvordan personen stemte.</p>`;return}
  const s=pstats.find(x=>x.name===selP);
  el.innerHTML=`<div class="eyebrow">${esc(PNAME[s.party]||s.party)}</div><h3>${esc(s.name)}</h3><p style="margin:6px 0 10px;font-size:13.5px">Stemte med flertallet i ${Math.round(s.maj*100)} % av ${s.tot} omstridte voteringer. Stemte annerledes enn egen gruppe ${s.brk} ${s.brk===1?'gang':'ganger'}. Fremmet ${s.prop} forslag.</p>`+
   contested.map(v=>{const vo=voteOf(v,selP);if(!vo)return'';const br=sides.get(v.id)[s.party]!==vo;return `<div class="vrow"><span class="mono muted">${esc(v.sak)}</span><span>${esc(v.lbl)}${br?' <span class="cross">· mot egen gruppe</span>':''}</span><span class="v ${vo}">${vo==='for'?'For':'Mot'}</span><span class="muted" style="text-align:right;font-size:12px">${resTxt(v)}</span></div>`}).join('')}
function renderHeat(){
  const ps=ordne(PORDER_ALLE,[...new Set(contested.flatMap(v=>Object.keys(sides.get(v.id))))]);
  const agree=(a,b)=>{let n=0,k=0;contested.forEach(v=>{const s=sides.get(v.id);if(s[a]&&s[b]){n++;if(s[a]===s[b])k++}});return n?k/n:null};
  let h=`<tr><th></th>${ps.map(p=>`<th><span class="sq" style="background:${pc(p)}"></span>${p}</th>`).join('')}</tr>`;
  ps.forEach(a=>{h+=`<tr><th class="rh">${esc(PNAME[a]||a)}</th>`+ps.map(b=>{if(a===b)return `<td style="background:var(--soft);color:var(--muted)">–</td>`;const r=agree(a,b);if(r===null)return '<td class="muted">·</td>';const pct=Math.round(r*100);return `<td title="${a} og ${b} stemte likt i ${pct} %" style="background:color-mix(in srgb,var(--accent) ${Math.max(6,pct)}%,var(--surface));color:${pct>55?'var(--bg)':'var(--ink)'}">${pct}</td>`}).join('')+'</tr>'});
  document.getElementById('heat').innerHTML=contested.length?h:'<tr><td class="muted">Ingen omstridte voteringer.</td></tr>';
  document.getElementById('close').innerHTML=contested.filter(v=>Math.abs(v.nfor-v.nmot)<=3).map(v=>{const s=sides.get(v.id);const cross=[...v.f.filter(n=>s[party(n)]!=='for'),...v.m.filter(n=>s[party(n)]!=='mot')];
    return `<div style="display:grid;gap:4px;padding:9px 0;border-bottom:1px solid var(--soft)"><div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><span><span class="mono muted">${esc(v.sak)}</span> ${esc(v.lbl)}</span><span class="mono"><b>${v.nfor}–${v.nmot}</b> <span class="res ${v.res==='vedtatt'?'ok':'no'}">${resTxt(v)}</span></span></div>${segBar(v)}<div class="muted" style="font-size:12.5px">${cross.length?'Stemte mot egen gruppe: '+cross.map(n=>`<span class="cross">${esc(n)} (${party(n)})</span>`).join(', '):'Alle stemte med egen gruppe.'}</div>${(v.merk||[]).map(t=>`<div class="merk">Merknad: ${esc(t)}</div>`).join('')}</div>`}).join('')||'<div class="muted">Ingen voteringer ble avgjort med tre stemmer eller mindre.</div>';
}

/* ---------- NAVIGASJON ---------- */
const VIEWS=['oversikt','saker','moter','stemmer','om'];
function go(v,o={}){
  VIEWS.forEach(x=>document.getElementById('v-'+x).hidden=x!==v);
  document.querySelectorAll('#nav button').forEach(b=>b.toggleAttribute('aria-current',b.dataset.v===v));
  document.querySelectorAll('#nav button[aria-current]').forEach(b=>b.setAttribute('aria-current','page'));
  if(v==='saker'){
    if('q' in o||'status' in o||'tag' in o){document.getElementById('q').value=o.q||'';fstatus.value=o.status||'';document.getElementById('fut').value='';ftag=o.tag||null;limit=40;
      openT=null;if(o.open){const m=PS.find(c=>c.t.toLowerCase().includes((o.q||'').toLowerCase()));if(m)openT=m.t}}
    renderTagChips();renderList();
  }
  if(v==='moter')renderMeet();
  if(v==='stemmer'&&o.m){vsel.value='m:'+o.m;renderStemmer()}
  if(history.replaceState)history.replaceState(null,'','#'+v);
  window.scrollTo({top:0});
}
document.getElementById('nav').addEventListener('click',e=>{const b=e.target.closest('button');if(b)go(b.dataset.v)});
renderTagChips();renderList();renderMeet();renderStemmer();
document.getElementById('foot').innerHTML=`<div>Kilde: Steinkjer kommunes innsynsportal (Elements Publikum): møtekalender, saksprotokoller, møteprotokoller og medlemslister. Data hentet ${dd(TODAY)} ${AAR}.</div><div>Uoffisiell tjeneste. Ikke laget av Steinkjer kommune.</div>`;
const fraAdresse=()=>{const h=location.hash.slice(1);if(VIEWS.includes(h))go(h)};
window.addEventListener('hashchange',fraAdresse);fraAdresse();
