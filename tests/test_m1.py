import json
import logging
import re
import ssl
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from linksoul_studio.app import create_app
from linksoul_studio.config import Settings
from linksoul_studio.service import Service, STEPS
from linksoul_studio.storage import Store


@pytest.fixture
def service(tmp_path):
    s = Service(Settings(data_dir=tmp_path))
    s.start()
    yield s
    s.close()


def chain(s, ids=('one', 'two')):
    it = iter(ids)
    for kind in STEPS:
        s.emit(kind, 'a' if kind in {'online', 'input'} else None,
               next(it) if kind == 'input' else None)
    s.drain()


@pytest.mark.parametrize('scenario,result', [('recovery','Passed'), ('no-input','Failed'), ('configuration','Failed'), ('storage','Failed')])
def test_scenarios(service, scenario, result):
    r = service.run_fixture(scenario)
    assert r['result'] == result and r['saved']
    assert service.store.read_report('fixture', r['id']) == r
    assert len(service.snapshot()['last_report']['steps']) == 7


@pytest.mark.parametrize('ids', [('same','same'), (None,None)])
def test_no_replay_or_missing_identity(service, ids):
    service.start_check()
    chain(service, ids)
    assert service.finish_check()['result'] == 'Failed'


def test_freshness_and_reconnect(service):
    now = [100.0]
    service.clock = lambda: now[0]
    service.start_check(); chain(service)
    now[0] += 31
    assert service.snapshot()['input'] == 'Stale'
    assert service.finish_check()['result'] == 'Failed'
    service.emit('connected'); service.drain()
    assert service.snapshot()['input'] == 'Waiting for input'
    assert service.snapshot()['presence'] == 'Awaiting online'


def test_unrelated_agent_does_not_change_target(service):
    service.emit('connected'); service.emit('online','a'); service.emit('input','b','wrong')
    service.emit('online','b'); service.drain()
    assert service.selected == 'a' and service.input_at is None
    assert service.incident


def test_configured_filter_and_out_of_order(tmp_path):
    s = Service(Settings(data_dir=tmp_path, agent_id='a')); s.start()
    try:
        s.emit('input','a','early'); s.emit('connected'); s.emit('online','b'); s.drain()
        assert not s.online and not s.incident and s.input_at is None
    finally: s.close()


def test_queue_overflow_blocks_pass(tmp_path):
    s = Service(Settings(data_dir=tmp_path), queue_size=1)
    s.emit('connected'); s.emit('online','a'); s.start()
    try:
        assert s.dropped == 1
        assert s.run_fixture('recovery')['result'] == 'Failed'
    finally: s.close()


def test_storage_rotation_lock_and_restart(tmp_path):
    cfg = Settings(data_dir=tmp_path, log_bytes=200, log_backups=2, app_secret='private-key')
    a = Store(cfg); a.open()
    b = Store(cfg); b.open(); assert b.error
    for _ in range(20): a.write('app', {'kind':'private-key', 'padding':'x'*80})
    assert len(list((tmp_path/'logs').glob('app.jsonl*'))) == 3
    assert 'private-key' not in ''.join(p.read_text() for p in (tmp_path/'logs').glob('*'))
    a.close(); b.close()
    c = Store(cfg); c.open(); assert not c.error; c.close()


def test_report_survives_new_service(tmp_path):
    a = Service(Settings(data_dir=tmp_path)); a.start()
    r = a.run_fixture('recovery'); a.close()
    b = Service(Settings(data_dir=tmp_path)); b.start()
    try:
        assert b.store.read_report('fixture',r['id']) == r
        assert b.snapshot()['gateway'] == 'Disconnected'
    finally: b.close()


def test_actual_report_write_failure(service, monkeypatch):
    import linksoul_studio.storage as storage
    monkeypatch.setattr(storage.os, 'replace', Mock(side_effect=OSError('disk full')))
    r = service.run_fixture('recovery')
    assert r['result'] == 'Failed' and not r['saved']
    assert service.snapshot()['storage'] == 'Unavailable'


def test_http_controls_and_mode_isolation(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as c:
        html = c.get('/').text
        token = re.search(r'name="studio-token" content="([^"]+)"',html)[1]
        assert c.get('/health').status_code == 200
        assert c.post('/api/action/fixture-recovery').status_code == 403
        r = c.post('/api/action/fixture-recovery',headers={'x-studio-token':token}).json()['last_report']
        assert r['result'] == 'Passed'
        assert c.get('/api/reports/fixture/'+r['id']).status_code == 200
        assert c.get('/api/reports/robot/'+r['id']).status_code == 404
        assert c.get('/api/reports/fixture/invalid').status_code == 404
        assert c.post('/api/action/connect',headers={'x-studio-token':token}).status_code == 400


def test_invalid_robot_configuration(tmp_path):
    settings = Settings.from_env({'STUDIO_MODE':'robot','STUDIO_DATA_DIR':str(tmp_path)})
    with TestClient(create_app(settings)) as c:
        assert c.get('/health').status_code == 503
        assert c.get('/api/state').json()['errors']


def test_sdk_boundary_lifecycle_tls_and_no_body(service, monkeypatch):
    from linksoul_studio.robot import AgentSdk, RobotAdapter
    # Actual SDK instance and registrations; only initialization is prevented from networking.
    monkeypatch.setattr(AgentSdk, 'initialize', lambda self: None)
    adapter = RobotAdapter(service)
    adapter.start()
    try:
        assert adapter.transport_type._build_sslopt('wss://example.com')['cert_reqs'] == ssl.CERT_REQUIRED
        adapter.auth.on_auth_state('app',0,'secret-auth-body')
        adapter.callback.on_robot_online('a',{'secret':'private-meta'})
        response = Mock()
        adapter.callback.on_request('a','evt','private-transcript',{'body':'private-param'},response)
        logging.getLogger('linksoul_agentsdk').error('secret-log-body %s','private-transcript')
        service.drain()
        response.on_error.assert_called_once_with('evt',503,'M1 connection test: inference is not configured.')
        assert any(e['kind'] == 'response_attempted' for e in service.events)
        data = json.dumps(service.snapshot()) + ''.join(p.read_text() for p in (service.store.root/'logs').glob('*'))
        for secret in ['secret-auth-body','private-meta','private-transcript','private-param','secret-log-body']:
            assert secret not in data
        adapter.callback.on_request('other','evt2','ignored',{},response)
        assert response.on_error.call_count == 1
    finally: adapter.stop()
    adapter.callback.on_robot_online('a',{})
    assert not adapter.active and adapter.sdk is None
