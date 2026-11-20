"""Pinned SDK boundary. Private transport hooks must be rechecked on upgrades."""
import logging
import ssl
import threading
import uuid

from linksoul_agentsdk import AgentSdk, AgentAuthCallback
from linksoul_agentsdk.client.linksky_client import LinkskyClient
from linksoul_agentsdk.passive import Asr2LlmCallback


class MetadataHandler(logging.Handler):
    def __init__(self, service):
        super().__init__(logging.WARNING)
        self.service = service

    def emit(self, record):
        # Never format message, args, exception or traceback: SDK logs include bodies/secrets.
        self.service.emit("sdk_error" if record.levelno >= logging.ERROR else "sdk_warning",
                          source="Application measured")


class RobotAdapter:
    def __init__(self, service, conversations=False):
        self.service = service
        self.conversations = conversations
        self.connection = uuid.uuid4().hex
        self.active = False
        self.sdk = None
        self.logging_state = []
        self.route_lock = threading.Lock()
        self.gateway_open = False
        self.online = False
        self.selected = service.selected

    def start(self):
        s = self.service.settings
        self.active = True
        for name in ("linksoul_agentsdk", "websocket"):
            logger = logging.getLogger(name)
            self.logging_state.append((logger, logger.handlers[:], logger.level, logger.propagate))
            logger.handlers = [MetadataHandler(self.service)]
            logger.setLevel(logging.WARNING)
            logger.propagate = False
        self.sdk = AgentSdk.create(s.gateway, s.app_id, s.app_key, s.app_secret)
        owner = self

        class Transport(LinkskyClient):
            @staticmethod
            def _build_sslopt(url):
                return {"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True}

            def _on_close(self, ws, code, reason):
                with owner.route_lock:
                    owner.boundary()
                    owner.gateway_open = owner.online = False
                super()._on_close(ws, code, reason)
                if owner.active:
                    owner.service.emit("disconnected")

            def _on_error(self, ws, error):
                with owner.route_lock:
                    owner.boundary()
                    owner.gateway_open = owner.online = False
                super()._on_error(ws, error)
                if owner.active:
                    owner.service.emit("transport_error")

        class Auth(AgentAuthCallback):
            def on_auth_state(self, app_id, code, msg):
                if owner.active:
                    with owner.route_lock:
                        owner.boundary()
                        owner.gateway_open = code == 0
                        owner.online = False
                    owner.service.emit("connected" if code == 0 else "transport_error")

        class Callback(Asr2LlmCallback):
            def on_robot_online(self, agent_id, agent_meta):
                if not owner.active:
                    return
                with owner.route_lock:
                    if owner.gateway_open:
                        if not owner.selected:
                            owner.selected = agent_id
                        if owner.selected == agent_id:
                            owner.online = True
                owner.service.emit("online", agent_id)

            def on_robot_offline(self, agent_id):
                if owner.active:
                    with owner.route_lock:
                        if owner.selected == agent_id:
                            owner.boundary()
                            owner.online = False
                    owner.service.emit("offline", agent_id)

            def on_request(self, agent_id, event_id, text, param, response):
                if not owner.active:
                    return
                owner.service.emit("input", agent_id, event_id)
                with owner.route_lock:
                    admitted = owner.gateway_open and owner.online and agent_id == owner.selected
                    connection = owner.connection
                if admitted and owner.conversations:
                    owner.service.recorder.submit('request',agent=owner.service._identifier(agent_id),connection=connection,
                        event=owner.service._identifier(event_id) if event_id else None,
                        text=str(text)[:owner.service.settings.max_text+1],response=response,
                        valid=lambda:owner.active and owner.gateway_open and owner.online and owner.connection==connection)
                elif admitted:
                    # Isolated M1 connection test: deliberately no inference or robot motion.
                    owner.service.emit("response_attempted", agent_id, event_id, "Application measured")
                    try:
                        response.on_error(event_id, 503, "M1 connection test: inference is not configured.")
                    except Exception:
                        owner.service.emit("sdk_error", source="Application measured")

            def on_histories(self, agent_id, event_id, histories):
                if not owner.active or not owner.conversations or agent_id != owner.selected:
                    return
                entries=[]
                for h in (histories or [])[:100]:
                    if any(len(str(getattr(h,key,''))) > owner.service.settings.max_text for key in ('query','answer')):
                        owner.service.recorder.dropped += 1
                    entries.append({
                        'event_id':owner.service._identifier(getattr(h,'event_id',None)),
                        'timestamp':getattr(h,'timestamp',None),
                        'query':str(getattr(h,'query',''))[:owner.service.settings.max_text],
                        'answer':str(getattr(h,'answer',''))[:owner.service.settings.max_text],
                        'complete':bool(getattr(h,'complete',False))})
                if len(histories or [])>100:
                    owner.service.recorder.dropped += len(histories)-100
                owner.service.recorder.submit('history',agent=owner.service._identifier(agent_id),connection=owner.connection,entries=entries)

        self.transport_type = Transport
        self.callback = Callback(self.sdk)
        self.auth = Auth()
        self.sdk.set_linksky_client_factory(Transport)
        self.sdk.register_auth(self.auth)
        self.sdk.register_asr2_llm(self.callback)
        self.sdk.initialize()

    def boundary(self):
        if self.conversations:
            self.service.recorder.submit('boundary',connection=self.connection)
        self.connection = uuid.uuid4().hex

    def stop(self):
        self.active = False
        with self.route_lock:
            self.boundary()
            self.gateway_open = self.online = False
        if self.sdk:
            self.sdk.release()
            self.sdk = None
        for logger, handlers, level, propagate in self.logging_state:
            logger.handlers, logger.level, logger.propagate = handlers, level, propagate
        self.logging_state.clear()
