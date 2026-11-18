import json
import logging
import ssl
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from linksoul_studio.app import create_app
from linksoul_studio.config import Settings
from linksoul_studio.diagnostics.store import Diagnostics, SafeSDKHandler, redact
from linksoul_studio.events.collector import Collector
from linksoul_studio.sdk.robot import RobotAdapter


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def test_recovery_reports_real_collector_events(client, settings):
    report = client.post('/api/fixture/recovery').json()
    assert report['mode'] == 'fixture'
    assert report['result'] == 'Passed'
    assert len(report['evidence']) == 7
    assert len({e['record_id'] for e in report['evidence']}) == 7
    assert all(e['connection_run_id'] for e in report['evidence'])
    assert report['evidence'][-1]['sequence'] > report['evidence'][-3]['sequence']
    saved = client.get(report['download'])
    assert saved.status_code == 200
    assert saved.json()['versions']['linksoul-agentsdk'] == '1.5.0a1'
    assert list((settings.data_dir / 'logs').glob('*.jsonl'))


def test_reconnect_without_input_cannot_reuse_prior_success(client):
    assert client.post('/api/fixture/recovery').json()['result'] == 'Passed'
    report = client.post('/api/fixture/no-input').json()
    state = client.get('/api/state').json()
    assert report['result'] == 'Failed'
    assert report['checks'][3]['result'] == 'Failed'
    assert state['gateway'] == 'Connected'
    assert state['presence'] == 'Online'
    assert state['freshness'] == 'Waiting for new input'


def test_gateway_and_presence_independent(client):
    client.post('/api/fixture/connect')
    assert client.get('/api/state').json()['presence'] == 'Unknown'
    client.post('/api/fixture/online')
    client.post('/api/fixture/input')
    assert client.get('/api/state').json()['freshness'] == 'Fresh'
    client.post('/api/fixture/disconnect')
    s = client.get('/api/state').json()
    assert s['gateway'] == 'Disconnected' and s['presence'] == 'Unknown'
    assert s['freshness'] != 'Fresh'


def test_freshness_and_presence_expire(settings, monkeypatch):
    c = Collector(settings)
    c.start()
    try:
        for a in ['connect', 'online', 'input']: c.adapter.action(a)
        c.flush()
        now = c.last_input.collector_mono
        monkeypatch.setattr('linksoul_studio.events.collector.monotonic', lambda: now + 31)
        assert c.snapshot()['freshness'] == 'Stale / unavailable'
        monkeypatch.setattr('linksoul_studio.events.collector.monotonic', lambda: now + 61)
        assert c.snapshot()['presence'] == 'Unknown / stale'
    finally:
        c.stop()


@pytest.mark.parametrize('scenario,explanation', [('invalid-config', 'credentials'), ('storage-failure', 'writable')])
def test_failure_scenarios_save_failed_report(client, scenario, explanation):
    r = client.post('/api/fixture/' + scenario).json()
    assert r['result'] == 'Failed'
    assert explanation in ' '.join(client.get('/api/state').json()['problems'])
    assert explanation in ' '.join(r['problems'])
    assert client.get(r['download']).status_code == 200
    assert client.get('/health').status_code == 503
    client.post('/api/fixture/clear-error')
    assert client.get('/health').status_code == 200


def test_config_failure_keeps_ui_and_never_exposes_secrets(settings):
    s = replace(settings, mode='robot', app_key='secret-key', app_secret='secret-value', gateway='https://wrong')
    with TestClient(create_app(s)) as client:
        assert client.get('/').status_code == 200
        state = client.get('/api/state')
        assert state.json()['problems']
        assert 'secret-key' not in state.text and 'secret-value' not in state.text
        assert client.post('/api/fixture/recovery').status_code == 403


def test_actual_log_directory_failure_is_visible(settings):
    (settings.data_dir / 'logs').write_text('blocked')
    with TestClient(create_app(settings)) as client:
        state = client.get('/api/state').json()
        assert state['diagnostics'] == 'Write failed'
        assert client.get('/health').status_code == 503
        assert client.post('/api/fixture/recovery').json()['result'] == 'Failed'


def test_runtime_write_failure_visible(settings, monkeypatch):
    d = Diagnostics(settings)
    monkeypatch.setattr(d.handlers['app'], 'emit', Mock(side_effect=OSError('secret-value')))
    assert not d.write('app', 'probe')
    assert 'secret-value' not in d.error
    d.close()


def test_redaction_rotation_and_sdk_payload_suppression(settings):
    settings.app_secret = 'known-secret'
    settings.log_bytes = 1024
    settings.log_backups = 2
    d = Diagnostics(settings)
    for i in range(100):
        d.write('app', 'test', credentials={'app_key': 'private'}, note='known-secret', count=i)
    handler = SafeSDKHandler(d, lambda *a: None)
    rec = logging.makeLogRecord({'name': 'linksoul_agentsdk.handlers', 'levelno': logging.INFO,
                                'levelname': 'INFO', 'msg': 'histories=%s token=%s',
                                'args': ('conversation-body-private', 'private-token')})
    handler.emit(rec)
    d.close()
    files = list((settings.data_dir / 'logs').glob('app.jsonl*'))
    assert len(files) == 3
    content = ''.join(p.read_text() for p in (settings.data_dir / 'logs').glob('*'))
    assert all(v not in content for v in ['known-secret', 'conversation-body-private', 'private-token', '"app_key": "private"'])
    assert 'sdk_diagnostic' in content
    assert redact({'authorization': 'secret', 'text': 'conversation'}) == {'authorization': '[redacted]', 'text': '[redacted]'}


def test_report_write_failure_has_no_false_download(client, settings):
    (settings.data_dir / 'verification').write_text('blocked')
    r = client.post('/api/fixture/recovery').json()
    assert r['result'] == 'Failed'
    assert 'download' not in r
    assert r['save_error']


def test_diagnostics_and_report_survive_new_service(settings):
    with TestClient(create_app(settings)) as client:
        r = client.post('/api/fixture/recovery').json()
    log = (settings.data_dir / 'logs/app.jsonl').read_text()
    with TestClient(create_app(settings)) as client:
        assert client.get(r['download']).status_code == 200
        assert client.get('/api/state').json()['input_utc'] is None
    after = (settings.data_dir / 'logs/app.jsonl').read_text()
    assert log in after
    assert after.count('service_start') == 2


def test_queue_overflow_visible_and_prevents_pass(settings):
    c = Collector(settings)
    for _ in range(600): c.emit('input')
    assert c.dropped == 88
    assert 'overflow' in ' '.join(c.snapshot()['problems'])
    c.diag.close()


def test_sdk_adapter_contract_without_network(settings):
    from linksoul_agentsdk import AgentSdk
    from linksoul_agentsdk.passive import Asr2LlmCallback
    settings = replace(settings, mode='robot', app_id='test-app', app_key='test-key',
                       app_secret='test-secret', agent_id='chosen', gateway='wss://example.invalid/agent')
    sdk = AgentSdk.create(settings.gateway, settings.app_id, settings.app_key, settings.app_secret)
    # Install the real adapter, mocking only transport lifecycle at the SDK boundary.
    sdk.initialize = Mock()
    sdk.release = Mock(wraps=sdk.release)
    events = []
    adapter = RobotAdapter(settings, lambda kind, **kw: events.append((kind, kw)))
    try:
        adapter.start()
        assert isinstance(adapter.callback, Asr2LlmCallback)
        sdk.initialize.assert_called_once()
        client = sdk._client_factory(sdk)
        assert client._build_sslopt(settings.gateway)['cert_reqs'] == ssl.CERT_REQUIRED
        response = Mock()
        adapter.callback.on_request('other', 'event-other', 'private text', None, response)
        response.on_error.assert_not_called()
        adapter.callback.on_request('chosen', 'event-1', 'private text', None, response)
        assert events[-2] == ('input', {'agent_id': 'chosen', 'event_id': 'event-1'})
        response.on_error.assert_called_once_with('event-1', 503, 'Connection test agent: inference is not configured')
        assert 'private text' not in json.dumps(events)
        adapter.stop()
        sdk.release.assert_called_once()
    finally:
        AgentSdk._reset_for_test()


def test_robot_filters_unselected_agent(settings):
    settings = replace(settings, mode='robot', agent_id='selected')
    c = Collector(settings)
    c.emit('input', agent_id='other', event_id='unrelated')
    assert c.queue.empty()
    c.diag.close()


def test_cross_site_action_blocked(client):
    assert client.post('/api/fixture/input', headers={'Origin': 'https://foreign.invalid'}).status_code == 403
    assert client.post('/api/fixture/input', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403


def test_multiple_service_owners_rejected(settings):
    with TestClient(create_app(settings)):
        with pytest.raises(RuntimeError, match='Another studio process'):
            with TestClient(create_app(settings)): pass


def test_manual_check_requires_new_window(client):
    assert client.post('/api/checks/save').status_code == 409
    assert client.post('/api/checks/begin').status_code == 200
    assert client.post('/api/checks/save').json()['result'] == 'Failed'


def test_config_numeric_validation(monkeypatch):
    monkeypatch.setenv('STUDIO_STALE_SECONDS', 'nan')
    monkeypatch.setenv('STUDIO_LOG_BACKUPS', '-1')
    assert len(Settings.from_env().validate()) >= 2


def test_robot_credentials_do_not_require_agent_id(settings):
    s = replace(settings, mode='robot', gateway='wss://example.invalid/sdk',
                app_id='app', app_key='key', app_secret='secret')
    assert s.validate() == []


def test_auto_discovery_keeps_one_agent_across_reconnect(settings):
    c = Collector(replace(settings, mode='robot'))
    try:
        assert c.emit('input', agent_id='early', event_id='early') is False
        c.emit('robot_online', agent_id='robot-a')
        assert c.snapshot()['selected_agent_id'] == 'robot-a'
        assert c.emit('input', agent_id='robot-a', event_id='one') is True
        c.emit('gateway_disconnected')
        c.emit('gateway_connected')
        assert c.emit('robot_online', agent_id='robot-b') is False
        assert c.emit('input', agent_id='robot-b', event_id='two') is False
        assert c.snapshot()['selected_agent_id'] == 'robot-a'
        assert 'another agent' in ' '.join(c.snapshot()['problems']).lower()
        assert c.emit('robot_online', agent_id='robot-a') is True
    finally:
        c.diag.close()


def test_discovery_adapter_and_report_without_network(settings, monkeypatch):
    from linksoul_agentsdk import AgentSdk
    monkeypatch.setattr(AgentSdk, 'initialize', lambda self: None)
    s = replace(settings, mode='robot', gateway='wss://example.invalid/sdk',
                app_id='test-app', app_key='test-key', app_secret='test-secret')
    with TestClient(create_app(s)) as client:
        c = client.app.state.collector
        callback = c.adapter.callback
        assert client.get('/health').status_code == 200
        assert client.get('/api/state').json()['selected_agent_id'] is None
        client.post('/api/checks/begin')
        c.emit('gateway_connected')
        callback.on_robot_online('discovered-agent', None)
        first = Mock()
        callback.on_request('discovered-agent', 'event-1', 'private', None, first)
        first.on_error.assert_called_once()
        c.emit('gateway_disconnected')
        c.emit('gateway_connected')
        callback.on_robot_online('discovered-agent', None)
        callback.on_request('discovered-agent', 'event-2', 'private', None, Mock())
        c.flush()
        report = client.post('/api/checks/save').json()
        assert report['result'] == 'Passed'
        assert report['selected_agent_id'] == 'discovered-agent'
        callback.on_robot_online('other-agent', None)
        other = Mock()
        callback.on_request('other-agent', 'other-event', 'private', None, other)
        other.on_error.assert_not_called()
        c.flush()
        assert c.last_input.event_id == 'event-2'
        assert client.get('/health').status_code == 503
    AgentSdk._reset_for_test()
