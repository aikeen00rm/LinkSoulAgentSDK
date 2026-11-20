import json
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from linksoul_studio.app import create_app
from linksoul_studio.config import Settings
from linksoul_studio.conversations import Conversations
from linksoul_studio.provider import TextProvider, ProviderError
from linksoul_studio.service import Service


@pytest.fixture
def service(tmp_path):
    s=Service(Settings(data_dir=tmp_path));s.start()
    yield s
    s.close()


def test_migration_restart_and_exact_reconstruction(tmp_path):
    # M1 has no database; old reports must remain readable after v0 -> v1.
    a=Service(Settings(data_dir=tmp_path));a.start()
    old=a.run_fixture('recovery')
    r=a.recorder.fixture('history');sid=r['session_id']
    before=a.recorder.db.detail('fixture',sid)
    assert [t['reply'] for t in before['turns']]==[f'Marker {i}: echo echo ' for i in range(1,4)]
    assert len(before['unassigned'])==1
    assert sum(e['kind']=='history' for e in before['events'])==4
    assert a.recorder.verify(sid)['result']=='Pending'
    a.close()
    b=Service(Settings(data_dir=tmp_path));b.start()
    try:
        assert b.recorder.db.db.execute('PRAGMA user_version').fetchone()[0]==1
        assert b.recorder.verify(sid)['result']=='Passed'
        assert b.store.read_report('fixture',old['id'])==old
        assert b.recorder.db.detail('fixture',sid)['events']==before['events']
    finally:b.close()


def test_identity_mode_agent_reconnect_and_ambiguous_history(service):
    db=service.recorder.db
    ids=[]
    for mode,agent,conn in [('fixture','a','1'),('fixture','b','1'),('robot','a','1'),('fixture','a','2')]:
        sid=db.session(mode,agent,'run',conn);ids.append(sid)
        tid=db.turn(sid,'same','input '+agent,'SDK captured')
        db.event(sid,tid,'reply_chunk',agent,event='same')
    assert db.detail('robot',ids[0]) is None
    assert len(db.sessions('fixture'))==3 and len(db.sessions('robot'))==1
    db.history(ids[-1],{'event_id':'same','timestamp':1,'query':'ambiguous','answer':'unknown','complete':True})
    assert db.detail('fixture',ids[-1])['unassigned'][0]['turn_id'] is None
    db.history(ids[1],{'event_id':'same','timestamp':1,'query':'b','answer':'b','complete':True})
    assert not db.detail('fixture',ids[1])['unassigned']


def test_history_revisions_are_not_chunks_or_duplicate_snapshots(service):
    db=service.recorder.db;sid=db.session('fixture','a','r','c');tid=db.turn(sid,'e','x','Fixture simulation')
    for body in ['a','a','b']:
        db.event(sid,tid,'reply_chunk',body,event='e')
    for complete in [False,False,True,True]:
        db.history(sid,dict(event_id='e',timestamp=4,query='q',answer='history',complete=complete))
    d=db.detail('fixture',sid)
    assert d['turns'][0]['reply']=='aab'
    assert len([e for e in d['events'] if e['kind']=='history'])==2


def test_pending_turn_becomes_incomplete_after_restart(tmp_path):
    a=Conversations(Settings(data_dir=tmp_path));a.open()
    sid=a.session('fixture','a','r','c');a.turn(sid,'e','unfinished','Fixture simulation');a.close()
    b=Conversations(Settings(data_dir=tmp_path));b.open()
    assert b.detail('fixture',sid)['turns'][0]['status']=='incomplete'
    b.close()


def test_newer_schema_not_downgraded(tmp_path):
    c=sqlite3.connect(tmp_path/'linksoul.sqlite3');c.execute('PRAGMA user_version=99');c.close()
    db=Conversations(Settings(data_dir=tmp_path));db.open()
    assert db.error and db.db.execute('PRAGMA user_version').fetchone()[0]==99
    db.close()


def test_write_failure_and_retention_visible(tmp_path):
    db=Conversations(Settings(data_dir=tmp_path,max_sessions=2,max_turns=1));db.open()
    a=db.session('fixture','a','r','1');b=db.session('robot','a','r','2')
    db.session('fixture','a','r','3');c=db.session('fixture','a','r','4')
    assert db.detail('fixture',a) is None and db.detail('robot',b)
    assert db.pruned==1
    db.turn(c,'one','text','Fixture simulation')
    assert db.turn(c,'two','text','Fixture simulation') is None and db.error
    db.close()


def test_query_only_failure_keeps_web_and_m1_usable(tmp_path):
    app=create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as c:
        app.state.service.recorder.db.db.execute('PRAGMA query_only=ON')
        token=re.search('name="studio-token" content="([^"]+)"',c.get('/conversations').text)[1]
        r=c.post('/api/m2/three-turns',headers={'x-studio-token':token}).json()
        assert r['error'] and r['report']['result']=='Failed'
        assert c.get('/health').status_code==503
        assert c.get('/').status_code==200 and c.get('/conversations').status_code==200


def test_failure_scenarios_preserve_reason_and_report_without_bodies(service):
    for scenario,state in [('interrupted','incomplete'),('provider-disabled','failed')]:
        r=service.recorder.fixture(scenario)
        assert r['result']=='Failed' and r['saved']
        t=service.recorder.db.detail('fixture',r['session_id'])['turns'][0]
        assert t['status']==state and t['reason']
        assert t['input'] not in json.dumps(service.store.read_report('fixture',r['id']))
    r=service.recorder.fixture('storage')
    assert r['result']=='Failed' and r['saved'] and service.recorder.db.error is None


def test_request_order_duplicate_and_disconnect(service):
    rec=service.recorder;rec.provider.reply=Mock(return_value='private-reply')
    response=Mock();args=dict(agent='a',connection='c',event='e',text='private-input',response=response,valid=lambda:True)
    rec.submit('request',**args);rec.submit('request',**args);rec.queue.join()
    assert [call[0] for call in response.method_calls]==['on_interrupt','on_llm_item_delta','on_llm_item_done','on_llm_done']
    assert rec.provider.reply.call_count==1
    sid=rec.db.sessions('fixture')[0]['id'];t=rec.db.detail('fixture',sid)['turns'][0]
    assert t['reply']=='private-reply' and t['status']=='attempted'
    assert 'Unavailable' in t['acceptance']
    logs=''.join(p.read_text() for p in (service.store.root/'logs').glob('*'))
    assert 'private-input' not in logs and 'private-reply' not in logs
    response.reset_mock()
    rec.submit('request',**{**args,'connection':'new','valid':lambda:False});rec.queue.join()
    assert not response.method_calls
    sid=rec.db.sessions('fixture')[0]['id']
    assert rec.db.detail('fixture',sid)['turns'][0]['status']=='incomplete'


def test_provider_disabled_and_throwing_send(service):
    r=service.recorder;response=Mock()
    r.request('a','c','e','text',response,lambda:True)
    sid=r.db.sessions('fixture')[0]['id']
    assert r.db.detail('fixture',sid)['turns'][0]['status']=='failed' and not response.method_calls
    r.provider.reply=lambda _: 'answer'
    response.on_llm_item_delta.side_effect=RuntimeError('private error')
    r.request('a','c','e2','text',response,lambda:True)
    t=r.db.detail('fixture',sid)['turns'][1]
    assert t['status']=='failed' and not response.on_llm_done.called and 'private error' not in t['reason']


def test_disconnect_during_provider_cancels_all_calls(service):
    rec=service.recorder;response=Mock();active=[True]
    def reply(text):active[0]=False;return 'answer'
    rec.provider.reply=reply
    rec.request('a','c','e','text',response,lambda:active[0])
    assert not response.method_calls
    sid=rec.db.sessions('fixture')[0]['id']
    assert rec.db.detail('fixture',sid)['turns'][0]['status']=='incomplete'


def test_missing_identity_and_oversized_input_never_send(service):
    r=service.recorder;response=Mock();r.provider.reply=Mock(return_value='answer')
    r.request('a','c',None,'x',response,lambda:True)
    r.request('a','c','e','x'*9000,response,lambda:True)
    assert not response.method_calls and not r.provider.reply.called
    sid=r.db.sessions('fixture')[0]['id']
    assert all(t['status']=='incomplete' for t in r.db.detail('fixture',sid)['turns'])


def test_queue_bounds_surface_capture_loss(service):
    rec=service.recorder
    entered=threading.Event();release=threading.Event()
    def provider(text):entered.set();release.wait(3);return 'reply'
    rec.provider.reply=provider
    rec.submit('request',agent='a',connection='c',event='e',text='x',response=Mock(),valid=lambda:True)
    assert entered.wait(2)
    try:
        for _ in range(40):rec.submit('boundary',connection='other')
        assert rec.snapshot()['dropped']>0
    finally:release.set();rec.queue.join()


def test_sdk_callback_m2_and_history(service,monkeypatch):
    from linksoul_studio.robot import AgentSdk,RobotAdapter
    from linksoul_agentsdk import HistoryInfo
    monkeypatch.setattr(AgentSdk,'initialize',lambda self:None)
    adapter=RobotAdapter(service,conversations=True);adapter.start()
    service.recorder.provider.reply=lambda _: 'reply'
    try:
        adapter.auth.on_auth_state('app',0,'')
        adapter.callback.on_robot_online('a',{})
        response=Mock()
        adapter.callback.on_request('a','e','input',None,response)
        service.recorder.queue.join()
        adapter.callback.on_histories('a','outer',[HistoryInfo(timestamp=5,query='input',answer='reply',complete=True,event_id='e')]*2)
        service.recorder.queue.join()
        sid=service.recorder.db.sessions('fixture')[0]['id']
        d=service.recorder.db.detail('fixture',sid)
        assert len([e for e in d['events'] if e['kind']=='history'])==1
        assert response.on_interrupt.called and response.on_llm_done.called
    finally:adapter.stop()


def test_http_mode_csrf_and_checkpoint(service,tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path/'web'))) as c:
        assert c.post('/api/m2/three-turns').status_code==403
        token=re.search('name="studio-token" content="([^"]+)"',c.get('/conversations').text)[1]
        h={'x-studio-token':token}
        result=c.post('/api/m2/three-turns',headers=h).json()
        sid=result['report']['session_id']
        assert len(c.get('/api/sessions/'+sid).json()['turns'])==3
        assert c.post('/api/m2/reopen',params={'sid':sid},headers=h).json()['report']['result']=='Pending'
        assert c.post('/api/m2/connect-replies',headers=h).status_code==400
        assert c.get('/api/sessions/unknown').status_code==404


def test_real_provider_http_contract_and_sanitized_failures():
    captured=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'done':True,'message':{'content':'real HTTP reply'}}).encode())
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        p=TextProvider(Settings(reply_provider='ollama',ollama_url=f'http://127.0.0.1:{server.server_port}',ollama_model='test'))
        assert p.reply('test input')=='real HTTP reply'
        assert captured[0][0]=='/api/chat' and captured[0][1]['stream'] is False
        assert captured[0][1]['messages'][-1]['content']=='test input'
    finally:server.shutdown();server.server_close();thread.join()
    with pytest.raises(ProviderError,match='failed or timed out'):p.reply('private input')


def test_conflicting_request_and_missing_history_identity_preserved(service):
    db=service.recorder.db;sid=db.session('fixture','a','r','c')
    tid=db.turn(sid,'same','first','Fixture simulation')
    assert db.turn(sid,'same','conflicting','Fixture simulation') is None
    entry=dict(event_id=None,timestamp=1,query='same words',answer='same words',complete=False)
    db.history(sid,entry);db.history(sid,entry)
    d=db.detail('fixture',sid)
    assert d['turns'][0]['status']=='incomplete'
    assert len(d['unassigned'])==3 and d['unassigned'][0]['body']=='conflicting'


def test_history_from_prior_connection_stays_local_and_unassigned(service):
    db=service.recorder.db
    prior=db.session('fixture','a','r','old');db.turn(prior,'old-event','input','Fixture simulation')
    current=db.session('fixture','a','r','new')
    db.history(current,dict(event_id='old-event',timestamp=1,query='input',answer='answer',complete=True))
    assert len(db.detail('fixture',current)['unassigned'])==1
    with db.db:db.db.execute('DELETE FROM sessions WHERE id=?',(prior,))
    assert len(db.detail('fixture',current)['events'])==1


def test_invalid_provider_url_is_readable_configuration_error():
    provider=TextProvider(Settings(reply_provider='ollama',ollama_url='http://[invalid',ollama_model='test'))
    assert 'Invalid reply provider configuration' in provider.issue
