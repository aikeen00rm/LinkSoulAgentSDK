const $ = id => document.getElementById(id);
let busy = false, lastActivity = '', requestError = '', lastAnnouncement = '';
const time = value => value ? new Date(value).toLocaleString() : 'Unavailable';
function node(tag, text, cls) { const e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; }
function render(s) {
  $('mode').textContent = s.mode === 'fixture' ? 'FIXTURE · SIMULATED' : s.mode === 'robot' ? 'ROBOT · LIVE ADAPTER' : 'INVALID MODE';
  $('fixture').hidden = s.mode !== 'fixture';
  $('gateway').textContent = s.gateway;
  $('gateway').className = s.gateway === 'Connected' ? 'good' : 'warn';
  $('gateway-note').textContent = s.gateway === 'Connected' ? 'Gateway is open. Robot input is checked separately.' : 'Check network, regional endpoint and application access.';
  $('presence').textContent = s.presence;
  $('agent-id').textContent = s.selected_agent_id || 'Waiting for discovery';
  $('agent-selection').textContent = s.agent_selection;
  $('presence').className = s.presence === 'Online' ? 'good' : 'warn';
  $('freshness').textContent = s.freshness;
  $('freshness').className = s.freshness === 'Fresh' ? 'good' : 'warn';
  $('input-note').textContent = s.input_utc ? `${time(s.input_utc)} · ${s.input_age}s ago` : 'No input received in this service run.';
  for (const [id, present, label] of [['gateway-source', s.gateway !== 'Unknown', 'SDK captured'], ['presence-source', s.presence !== 'Unknown', 'Robot reported'], ['input-source', s.input_utc, 'Application measured · SDK input arrival']]) {
    $(id).textContent = present ? (s.mode === 'fixture' ? 'Fixture simulation' : label) : 'Unavailable';
  }
  $('activity-mode').textContent = `${s.mode.toUpperCase()} EVIDENCE`;
  $('diagnostics').textContent = s.diagnostics;
  $('diagnostics').className = s.diagnostics === 'Saved' ? 'good' : 'bad';
  $('verify-mode').textContent = `${s.mode.toUpperCase()} CHECK · ${s.mode === 'fixture' ? 'NO HARDWARE EVIDENCE' : 'SELECTED ASR TEST AGENT'}`;
  $('check-status').textContent = s.checking ? 'Check in progress · collecting new evidence.' : s.report ? `Saved ${time(s.report.saved_utc)}` : 'No check in progress.';
  $('save').disabled = busy || !s.checking;
  $('setup-context').textContent = s.mode === 'fixture' ? 'Fixture mode needs no credentials. Switch modes using server configuration and restart the service.' : 'Robot mode uses the selected ASR test agent. Confirm the following with your administrator before verification.';
  $('build').textContent = `Build ${s.versions.build} · ${s.mode}`;
  $('sdk').textContent = `SDK ${s.versions['linksoul-agentsdk']}`;
  $('python').textContent = `Python ${s.versions.python}`;
  const key = s.activity.map(e => e.record_id).join();
  if (key !== lastActivity) {
    lastActivity = key;
    $('timeline').replaceChildren(...s.activity.map(e => {
      const li = document.createElement('li');
      li.append(node('time', time(e.collector_utc)), node('span', e.summary), node('small', `${e.evidence} · #${e.sequence} · ${e.record_id.slice(0, 8)}`));
      return li;
    }));
  }
  $('errors').replaceChildren(...[...s.problems, ...(requestError ? [requestError] : [])].map(p => node('div', p, 'alert')));
  const r = s.report;
  const announcement = `${s.mode}. Gateway ${s.gateway}. Robot ${s.presence}. Input ${s.freshness}. Check ${r?.result || 'not run'}.`;
  if (announcement !== lastAnnouncement) { $('announcer').textContent = announcement; lastAnnouncement = announcement; }
  $('result').textContent = r ? `${r.result} · ${r.mode}` : 'Not run';
  $('result').className = `pill ${r ? (r.result === 'Passed' ? 'good' : 'bad') : ''}`;
  $('checks').replaceChildren(...(r?.checks || []).map(c => {
    const row = node('div', '', 'check'); row.append(node('span', c.label), node('b', c.result, c.result === 'Passed' ? 'good' : 'bad')); return row;
  }));
  $('download').hidden = !r?.download;
  if (r?.download) $('download').href = r.download;
  $('guidance').textContent = s.problems.length ? s.problems[0] : s.freshness === 'Fresh' ? 'Fresh input has arrived in this connection. Save a check to assess the full reconnect sequence.' : 'Waiting for fresh input. Check the robot’s agent association and ASR input configuration. Reconnecting the gateway alone cannot pass.';
}
async function refresh() {
  try { const res = await fetch('/api/state'); if (!res.ok) throw new Error(); render(await res.json()); $('feed').textContent = 'Console live · updates every second'; }
  catch { $('feed').textContent = 'Console unavailable · retrying'; $('gateway').textContent = 'Unknown · console disconnected'; $('presence').textContent = 'Unknown'; $('freshness').textContent = 'Unavailable'; }
}
async function action(path) {
  if (busy) return;
  busy = true; requestError = '';
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try {
    const res = await fetch(path, {method: 'POST'});
    if (!res.ok) { const data = await res.json(); requestError = data.detail || 'Action failed. Retry from the console.'; }
  } catch { requestError = 'Console connection lost. Check the service and retry.'; }
  finally { busy = false; document.querySelectorAll('button').forEach(b => b.disabled = false); await refresh(); }
}
document.querySelectorAll('[data-fixture]').forEach(b => b.addEventListener('click', () => action(`/api/fixture/${b.dataset.fixture}`)));
$('begin').addEventListener('click', () => action('/api/checks/begin'));
$('save').addEventListener('click', () => action('/api/checks/save'));
refresh(); setInterval(refresh, 1000);
