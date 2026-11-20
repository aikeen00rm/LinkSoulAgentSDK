const $ = id => document.getElementById(id);
const steps = ['Gateway connected', 'Selected agent online', 'First input received', 'Gateway disconnected', 'Gateway reconnected', 'Selected agent online again', 'New input after reconnect'];
let busy = false, latestEvents = '', latestReports = '';
const text = (id, value) => { $(id).textContent = value; };
const el = (tag, value, cls) => { const e = document.createElement(tag); if (value !== undefined) e.textContent = value; if (cls) e.className = cls; return e; };
function message(id, content) { text(id, content || ''); $(id).hidden = !content; }
function render(s) {
  const fixture = s.mode === 'fixture';
  text('mode', `${s.mode} · ${fixture ? 'simulated evidence' : 'hardware evidence only'}`);
  $('mode').classList.toggle('robot', !fixture);
  text('versions', `Build ${s.versions.studio} / SDK ${s.versions.sdk} / Python ${s.versions.python}`);
  text('footer-mode', fixture ? 'Fixture checks never count as hardware acceptance.' : 'Physical association and hardware acceptance remain operator-verified.');
  for (const name of ['gateway','presence','input']) text(name, s[name]);
  for (const [name, good] of [['gateway',s.gateway==='Connected'],['presence',s.presence==='Online reported'],['input',s.input==='Fresh']]) {
    $(`${name}-dot`).className = `dot ${good ? 'good' : 'warn'}`;
    text(`${name}-evidence`, fixture ? 'Fixture simulation · no hardware evidence' : 'SDK captured · callback evidence');
  }
  text('presence-age', s.presence_age === null ? 'No current online evidence' : `Last selected-agent activity ${s.presence_age.toFixed(1)} s ago`);
  text('input-age', s.input_age === null ? 'New input required after reconnect' : `Latest input ${s.input_age.toFixed(1)} s ago`);
  text('agent', s.agent_id || 'Not discovered'); text('selection', s.selection); text('association', s.physical_association);
  message('errors', [...s.errors, s.storage_error].filter(Boolean).join(' '));
  message('incident', s.incident ? `${fixture ? 'Fixture scenario: ' : ''}${s.incident}. ${fixture ? 'Run the recovery check to clear scenario state. Persistent storage or queue failures require a restart.' : 'Check setup and reconnect; repeat the check after resolving the issue.'}` : '');
  $('fixture-controls').hidden = !fixture; $('fixture-steps').hidden = !fixture; $('robot-controls').hidden = s.mode !== 'robot';
  text('mode-help', fixture ? 'Try the complete recovery path, then a failure case. Every result is derived from collected events and saved automatically.' : 'Start a check while disconnected, connect the isolated test agent, speak, disconnect/reconnect and speak again. Finish to save the report.');
  text('storage', s.storage); $('storage').className = `pill ${s.storage === 'Ready' ? 'good' : 'bad'}`;
  text('dropped', s.dropped); text('report-count', s.reports.length);
  const r = s.last_report;
  text('check-status', s.check ? 'In progress' : r ? `${r.result} · ${s.mode}` : 'Not run');
  $('check-status').className = `pill ${s.check ? '' : r ? r.result === 'Passed' ? 'good' : 'bad' : 'neutral'}`;
  const observed = s.check?.steps || r?.steps || steps.map(label => ({label,observed:false}));
  $('steps').replaceChildren(...observed.map(v => el('li',v.label,v.observed?'done':'')));
  if (r && !s.check) {
    text('result', `${r.result} · ${r.mode}. ${r.reason} ${r.saved ? 'Report saved to persistent storage.' : 'Report NOT saved.'}`);
    $('result').className = `result ${r.result === 'Passed' ? 'good' : 'bad'}`;
  } else { text('result',s.check ? 'Collecting evidence. Complete the seven steps, then finish and save.' : 'Run a check to collect evidence. No result is assumed.'); $('result').className='result'; }
  const reportKey = JSON.stringify(s.reports);
  if (latestReports !== reportKey) {
    latestReports = reportKey;
    $('reports').replaceChildren(...(s.reports.length ? s.reports.map(r => {
      const row=el('div',undefined,'report-row');
      row.append(el('span',`${r.result} · ${r.mode}`,`pill ${r.result==='Passed'?'good':'bad'}`),el('span',r.scenario),el('span',new Date(r.ended_at).toLocaleString(),'muted'));
      const link=el('a','Download report'); link.href=`/api/reports/${r.mode}/${r.id}`; row.append(link);return row;
    }) : [el('p','No saved reports yet.','empty')]));
  }
  const eventKey = `${s.run_id}:${s.events[0]?.sequence}`;
  if (latestEvents !== eventKey) {
    latestEvents=eventKey;
    $('events').replaceChildren(...(s.events.length ? s.events.slice(0,12).map(e => {
      const row=el('div',undefined,'event-row'), time=el('time',new Date(e.timestamp).toLocaleTimeString()); time.dateTime=e.timestamp;
      const main=el('div',e.summary,'event-main'); main.append(el('small',`#${e.sequence}${e.agent_id ? ' · '+e.agent_id : ''}${e.event_id ? ' · '+e.event_id : ''}`));
      row.append(time,main,el('span',`${e.mode} / ${e.source}`,'event-source'));return row;
    }) : [el('p','Waiting for connection evidence.','empty')]));
  }
}
async function refresh() {
  if (busy) return;
  try { const res=await fetch('/api/state'); if(!res.ok)throw new Error(); render(await res.json()); $('offline').hidden=true; }
  catch { $('offline').hidden=false; }
}
for (const button of document.querySelectorAll('[data-action]')) button.addEventListener('click',async()=>{
  if(busy)return;busy=true;
  document.querySelectorAll('[data-action]').forEach(b=>b.disabled=true);
  try {
    const response=await fetch(`/api/action/${button.dataset.action}`,{method:'POST',headers:{'x-studio-token':document.querySelector('meta[name=studio-token]').content}});
    const data=await response.json(); if(!response.ok)throw new Error(data.detail || 'Operation failed.'); render(data);$('offline').hidden=true;
  } catch(error) {message('incident',error.message || 'Operation failed. Refresh the console.');}
  finally {busy=false;document.querySelectorAll('[data-action]').forEach(b=>b.disabled=false);}
});
refresh();setInterval(refresh,1000);
