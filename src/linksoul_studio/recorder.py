"""Bounded callback-to-storage/reply worker; one writer outside SDK callbacks."""
import queue
import tempfile
import threading
import time
import uuid
from pathlib import Path

from .conversations import Conversations, utc
from .config import Settings
from .provider import TextProvider, ProviderError


class Recorder:
    def __init__(self, service):
        self.service = service
        self.db = Conversations(service.settings)
        self.provider = TextProvider(service.settings)
        self.queue = queue.Queue(32)
        self.stopping = threading.Event()
        self.thread = None
        self.sessions = {}
        self.dropped = 0
        self.last_report = None

    def start(self):
        if self.service.store.error:
            self.db.error = 'Conversation storage not opened because exclusive data ownership or diagnostics are unavailable.'
            return
        self.db.open()
        self.thread = threading.Thread(target=self._work,name='studio-text',daemon=True)
        self.thread.start()

    def submit(self, kind, **data):
        if self.stopping.is_set() or not self.thread:
            return False
        try:
            self.queue.put_nowait((kind,data))
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _session(self, agent, connection):
        key=(agent,connection)
        if key not in self.sessions:
            self.sessions[key]=self.db.session(self.service.settings.mode,agent,self.service.run_id,connection)
        return self.sessions[key]

    def _work(self):
        while not self.stopping.is_set() or not self.queue.empty():
            try:
                kind,data=self.queue.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                if kind=='fixture':
                    self._fixture(data['scenario'])
                elif kind=='request':
                    self.request(**data)
                elif kind=='history':
                    sid=self._session(data['agent'],data['connection'])
                    for entry in data['entries']:
                        self.db.history(sid,entry)
                elif kind=='boundary':
                    for key,sid in list(self.sessions.items()):
                        if key[1]==data['connection']:
                            self.db.end(sid,'Connection ended; unfinished reply interrupted.')
                            del self.sessions[key]
            except Exception:
                self.dropped += 1
                self.service.store.write('app',{'kind':'conversation_worker_failed','mode':self.service.settings.mode})
            finally:
                self.queue.task_done()

    def request(self, agent, connection, event, text, response, valid):
        sid=self._session(agent,connection)
        if not sid:
            return
        source='SDK captured' if self.service.settings.mode=='robot' else 'Fixture simulation'
        tid=self.db.turn(sid,event,text,source)
        if not tid:
            return
        self.db.event(sid,tid,'input',text[:self.service.settings.max_text],event=event,source=source,direction='inbound',monotonic=time.monotonic())
        if not event or len(text)>self.service.settings.max_text:
            return
        if not valid():
            self.db.status(tid,'incomplete','Connection ended before reply; no send attempted.')
            return
        try:
            reply=self.provider.reply(text)
        except ProviderError as exc:
            self.db.status(tid,'failed',str(exc))
            self.service.store.write('app',{'kind':'reply_provider_failed','mode':self.service.settings.mode,'turn_id':tid})
            return
        if not valid() or self.stopping.is_set():
            self.db.status(tid,'incomplete','Connection ended during inference; no reply sent.')
            return
        item=uuid.uuid4().hex  # application-created outgoing item identity
        calls=[('interrupt_attempt',lambda:response.on_interrupt(event,'chat',None),''),
               ('reply_chunk',lambda:response.on_llm_item_delta(event,item,reply),reply),
               ('item_done_attempt',lambda:response.on_llm_item_done(event,item),''),
               ('reply_done_attempt',lambda:response.on_llm_done(event),'')]
        for kind,call,body in calls:
            if not valid() or self.stopping.is_set():
                self.db.status(tid,'incomplete','Connection ended between response calls; remaining calls cancelled.')
                return
            # Persist attempt before invoking SDK; no unrecorded sending on storage failure.
            if not self.db.event(sid,tid,kind,body,event=event,item=item,monotonic=time.monotonic()):
                return
            try:
                call()
                self.db.event(sid,tid,'call_returned',event=event,item=item)
            except Exception:
                self.db.status(tid,'failed','Response call raised an error; acceptance and execution unknown.')
                return
        self.db.status(tid,'attempted','All response calls returned. SDK may swallow transport failures; acceptance and playback unknown.')

    def fixture(self, scenario):
        if self.service.settings.mode != 'fixture' or scenario not in {'three-turns','history','interrupted','provider-disabled','storage'}:
            raise ValueError('Choose a valid scenario in fixture mode.')
        if not self.submit('fixture',scenario=scenario):
            return self.report(scenario,None,'Failed','Fixture could not enter the capture queue. Check capture/storage health.')
        self.queue.join()
        return self.last_report

    def _fixture(self, scenario):
        if self.service.settings.mode!='fixture':
            raise ValueError('Fixture scenarios are unavailable in robot mode.')
        if scenario not in {'three-turns','history','interrupted','provider-disabled','storage'}:
            raise ValueError('Unknown M2 fixture scenario.')
        if scenario=='storage':
            # Real SQLite failure through the same writer, isolated from saved sessions.
            with tempfile.TemporaryDirectory() as folder:
                probe=Conversations(Settings(data_dir=Path(folder)))
                probe.open()
                probe.db.execute('PRAGMA query_only=ON')
                probe.session('fixture','fixture-a3',self.service.run_id,'failure')
                failed=bool(probe.error)
                probe.close()
            return self.report(scenario,None,'Failed' if failed else 'Pending',
                'Save failure observed in isolated read-only database; existing sessions remain usable. Restore write access and retry.')
        sid=self.db.session('fixture','fixture-a3',self.service.run_id,uuid.uuid4().hex,'Fixture scenario')
        if not sid:
            return self.report(scenario,None,'Failed',self.db.error)
        count=3 if scenario in {'three-turns','history'} else 1
        tids=[]
        for i in range(count):
            event=f'fixture-{sid[:8]}-{i+1}'
            tid=self.db.turn(sid,event,f'Fixture question {i+1}: name marker {i+1}.','Fixture simulation')
            tids.append((tid,event))
            self.db.event(sid,tid,'input',f'Fixture question {i+1}: name marker {i+1}.',event=event,source='Fixture simulation',direction='inbound')
        # Interleave by chunk position, retaining identical chunks as legitimate evidence.
        for chunk in ('Marker ','echo ','echo '):
            for i,(tid,event) in enumerate(tids):
                self.db.event(sid,tid,'reply_chunk',chunk if chunk!='Marker ' else f'Marker {i+1}: ',event=event,item='fixture-item',source='Fixture simulation') if scenario!='provider-disabled' else None
        for i,(tid,event) in enumerate(tids):
            state='incomplete' if scenario=='interrupted' else 'failed' if scenario=='provider-disabled' else 'fixture complete'
            self.db.status(tid,state,'Fixture interruption before completion.' if state=='incomplete' else 'Reply provider disabled in this fixture; configure a provider to receive replies.' if state=='failed' else 'Simulated output saved; no robot response sent.')
            if scenario=='history':
                entry={'event_id':event,'timestamp':100+i,'query':f'History query {i+1}','answer':f'History answer {i+1}','complete':True}
                self.db.history(sid,entry); self.db.history(sid,entry)
        if scenario=='history':
            self.db.history(sid,{'event_id':None,'timestamp':999,'query':'Unassigned history','answer':'No reliable event identity','complete':False})
        self.db.end(sid,'Fixture finished')
        detail=self.db.detail('fixture',sid)
        correct=bool(detail and len(detail['turns'])==count and all(t['reply']==f'Marker {i+1}: echo echo ' for i,t in enumerate(detail['turns'])))
        if scenario=='history':
            correct=correct and sum(e['kind']=='history' for e in detail['events'])==4 and len(detail['unassigned'])==1
        result='Failed' if self.db.error or scenario in {'interrupted','provider-disabled'} or not correct else 'Pending'
        if result=='Pending':
            self.db.checkpoint('fixture',sid,self.service.run_id)
        reason=self.db.error or ('Saved and reconstructed three distinct turns. Recreate the service, select this session and verify reopening.' if result=='Pending' else 'Controlled incomplete/failed reply saved. Inspect the selected turn, then run the three-turn recovery check.')
        return self.report(scenario,sid,result,reason)

    def report(self, scenario, sid, result, reason):
        detail=self.db.detail(self.service.settings.mode,sid) if sid else None
        r={'id':uuid.uuid4().hex,'schema_version':1,'milestone':'M2','mode':self.service.settings.mode,
           'scenario':'M2 '+scenario,'started_at':utc(),'ended_at':utc(),'result':result,'reason':reason,
           'session_id':sid,'versions':self.service.versions,'agent_id':detail['agent_id'] if detail else None,
           'physical_association':'Simulated' if self.service.settings.mode=='fixture' else 'Operator verification pending',
           'evidence_ids':[e['id'] for e in detail['events']] if detail else [],
           'steps':[{'label':'Saved session readable','observed':bool(detail)},
                    {'label':'Reopened unchanged in a new service run','observed':bool(sid and self.db.reopened(self.service.settings.mode,sid,self.service.run_id))}],
           'limitations':['Fixture is not hardware acceptance.','Response attempts do not prove acceptance or physical playback.'],
           'saved':True}
        if self.db.error or self.dropped:
            r.update(result='Failed',reason=self.db.error or 'Conversation queue overflow; capture loss invalidates verification.')
        if not self.service.store.save(r):
            r.update(saved=False,result='Failed',reason=self.service.store.error)
        self.last_report=r
        self.service.store.write('app',{'kind':'m2_verification','mode':r['mode'],'report_id':r['id'],'result':r['result']})
        return r

    def verify(self, sid, prepare=False):
        self.queue.join()
        mode=self.service.settings.mode
        detail=self.db.detail(mode,sid)
        if not detail:
            raise ValueError('Select a saved session in the current mode first.')
        enough=len(detail['turns'])>=3 and all(t['status'] in {'attempted','fixture complete'} and t['input'] and t['reply'] for t in detail['turns'])
        if not enough:
            return self.report('reopen',sid,'Failed','Need at least three complete input/reply turns without incomplete or failed turns.')
        if prepare:
            self.db.checkpoint(mode,sid,self.service.run_id)
            return self.report('prepare reopen',sid,'Pending','Checkpoint saved. Recreate the service using the same volume, reopen this session and verify.')
        ok=self.db.reopened(mode,sid,self.service.run_id)
        return self.report('reopen',sid,'Passed' if ok else 'Pending','Three or more turns and all evidence reopened unchanged after service restart. Hardware acceptance still requires confirmed physical association.' if ok else 'No matching checkpoint from a prior service run. Save a restart checkpoint, recreate, then retry.')

    def snapshot(self):
        return {'error':self.db.error,'dropped':self.dropped,'pruned':self.db.pruned,
                'provider':self.provider.issue or 'Ollama configured; availability verified only on a real request.',
                'limits':f'{self.service.settings.max_sessions} sessions per mode / {self.service.settings.max_turns} turns per session / {self.service.settings.max_text} characters per text event',
                'sessions':self.db.sessions(self.service.settings.mode),'report':self.last_report}

    def close(self):
        self.stopping.set()
        if self.thread:
            self.thread.join()  # request timeout bounded; finish before closing database/SDK
        for sid in self.sessions.values():
            self.db.end(sid,'Service stopped; unfinished reply interrupted.')
        self.db.close()
