const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
let sid=localStorage.getItem('m2-session')||'',tid='',detail=null,busy=false,sessionKey='',detailKey='',reportKey='';
function notice(message){$('error').textContent=message||'';$('error').hidden=!message;}
function renderTurn(){
 const t=detail?.turns.find(t=>t.id===$('turns').value);tid=t?.id||'';
 $('turn-status').textContent=t?`${t.status} · ${t.reason}`:'No associated turns. Inspect unassigned evidence below.';
 $('turn-status').className=`result ${t&&['failed','incomplete'].includes(t.status)?'bad':''}`;
 $('input-text').textContent=t?.input||'No saved input.';$('reply-text').textContent=t?.reply||'No outgoing reply captured.';
 $('input-source').textContent=t?.source||'Unavailable';$('reply-source').textContent=t?.reply?(detail.mode==='fixture'?'Fixture simulation':'Application measured · outgoing call text'):'Unavailable';
 $('sending').textContent=t?.status==='attempted'?'Calls returned · transport success unconfirmed':detail?.mode==='fixture'?'Simulated only · no robot sends':'No completed sending sequence';
 $('acceptance').textContent=t?.acceptance||'Unavailable';
 $('evidence').replaceChildren(...(t?.evidence||[]).map(e=>evidence(e)));
}
function evidence(e){const box=el('div',undefined,'evidence-row');box.append(el('strong',`#${e.sequence} ${e.kind} · ${e.source}`),el('small',`${e.timestamp} · event ${e.event_id||'unavailable'} · item ${e.item_id||'unavailable'} · ${e.direction}`));if(e.kind==='history')box.append(el('pre',e.body));return box;}
async function selectSession(id){sid=id;tid='';detailKey='';localStorage.setItem('m2-session',sid);await loadDetail();renderSessions();}
let sessions=[];
function renderSessions(){
 $('session-count').textContent=sessions.length;
 $('sessions').replaceChildren(...(sessions.length?sessions.map(s=>{const b=el('button',undefined,'session-button');b.setAttribute('aria-pressed',String(s.id===sid));b.append(el('strong',`${s.mode} · ${new Date(s.started_at).toLocaleString()}`),el('span',`${s.turns} turns · ${s.agent_id||'unassigned'}`),el('small',`${s.id.slice(0,12)} · ${s.ended_at?'saved':'recording'}`));b.onclick=()=>selectSession(s.id).catch(()=>notice('Unable to reopen session. Check storage.'));return b;}):[el('p','No saved sessions. Run the three-turn fixture check to begin.','empty')]));
}
async function loadDetail(){
 if(!sid)return;
 const r=await fetch(`/api/sessions/${encodeURIComponent(sid)}`);
 if(!r.ok){sid='';detail=null;detailKey='';$('session-heading').textContent='Session unavailable';$('session-meta').textContent='Select a current session. Older sessions may have reached retention limits.';$('turns').replaceChildren();$('unassigned').replaceChildren();renderTurn();return;}
 const d=await r.json(),key=JSON.stringify(d);if(key===detailKey)return;detailKey=key;detail=d;
 $('session-heading').textContent=`Session ${d.id.slice(0,12)}`;$('session-mode').textContent=d.mode;
 $('session-meta').textContent=`${d.agent_id||'Unknown agent'} · ${d.boundary} · run ${d.run_id.slice(0,10)} · ${d.started_at}`;
 $('turns').replaceChildren(...d.turns.map((t,i)=>{const o=el('option',`${i+1}. ${t.input.slice(0,65)} · ${t.status}`);o.value=t.id;return o;}));
 if(d.turns.some(t=>t.id===tid))$('turns').value=tid;
 $('unassigned-count').textContent=`Unassigned evidence · ${d.unassigned.length}`;$('unassigned').replaceChildren(...d.unassigned.map(evidence));renderTurn();
}
function renderReport(r){if(!r)return;$('check-status').textContent=`${r.result} · ${r.mode}`;$('check-status').className=`pill ${r.result==='Passed'?'good':r.result==='Failed'?'bad':''}`;$('result').textContent=`${r.result} · ${r.reason} ${r.saved?'Report saved.':'Report NOT saved.'}`;$('result').className=`result ${r.result==='Failed'?'bad':r.result==='Passed'?'good':''}`;}
function renderData(c){sessions=c.sessions;const key=JSON.stringify(sessions);if(key!==sessionKey){sessionKey=key;renderSessions();}notice(c.error|| (c.dropped?'Capture loss: conversation queue overflow. Restart and repeat verification.':''));$('storage').textContent=c.error?'Save/read failure':'Ready';$('storage').className=`pill ${c.error?'bad':'good'}`;$('limits').textContent=c.limits;$('loss').textContent=`Capture loss: ${c.dropped} · Sessions expired this run: ${c.pruned}`;$('provider').textContent=c.provider;renderReport(c.report);}
async function refresh(){if(busy)return;try{const [sr,cr]=await Promise.all([fetch('/api/state'),fetch('/api/conversations')]);if(!sr.ok||!cr.ok)throw Error();const s=await sr.json(),c=await cr.json();$('offline').hidden=true;$('mode').textContent=`${s.mode} · ${s.mode==='fixture'?'simulated evidence':'hardware evidence only'}`;$('versions').textContent=`Build ${s.versions.studio} / SDK ${s.versions.sdk} / Python ${s.versions.python}`;$('connection').textContent=`Gateway: ${s.gateway}  ·  Presence: ${s.presence}  ·  Input: ${s.input}  ·  Agent: ${s.agent_id||'not selected'}  ·  ${s.interaction}`;$('fixtures').hidden=s.mode!=='fixture';$('robot-setup').hidden=s.mode!=='robot';renderData(c);if(s.storage_error||s.errors.length)notice([s.storage_error,...s.errors,c.error].filter(Boolean).join(' '));const key=JSON.stringify(s.reports);if(key!==reportKey){reportKey=key;$('reports').replaceChildren(...s.reports.map(r=>{const row=el('div',undefined,'report-row'),a=el('a','Download report');a.href=`/api/reports/${r.mode}/${r.id}`;row.append(el('span',`${r.result} · ${r.mode}`,'pill'),el('span',r.scenario),el('span',new Date(r.ended_at).toLocaleString(),'muted'),a);return row;}));}await loadDetail();}catch{$('offline').hidden=false;}}
$('turns').onchange=renderTurn;
$('callback-confirmed').onchange=()=>{$('connect-replies').disabled=!$('callback-confirmed').checked;};
for(const b of document.querySelectorAll('[data-m2]'))b.onclick=async()=>{if(busy)return;busy=true;document.querySelectorAll('[data-m2]').forEach(b=>b.disabled=true);try{const r=await fetch(`/api/m2/${b.dataset.m2}?sid=${encodeURIComponent(sid)}`,{method:'POST',headers:{'x-studio-token':document.querySelector('meta[name=studio-token]').content}});const c=await r.json();if(!r.ok)throw Error(c.detail||'Operation failed.');renderData(c);if(c.report?.session_id)await selectSession(c.report.session_id);}catch(e){notice(e.message);}finally{busy=false;document.querySelectorAll('[data-m2]').forEach(b=>b.disabled=false);$('connect-replies').disabled=!$('callback-confirmed').checked;refresh();}};
refresh();setInterval(refresh,2000);
