"""Pinned 1.5.0a1 API boundary. No arbitrary SDK payload reaches storage."""
import ssl
from importlib.metadata import version
from uuid import uuid4


class RobotAdapter:
    def __init__(self, settings, emit):
        self.settings, self.emit = settings, emit
        self.run_id = str(uuid4())
        self.sdk = None

    def start(self):
        if version("linksoul-agentsdk") != "1.5.0a1":
            raise RuntimeError("unsupported SDK")
        from linksoul_agentsdk import AgentSdk, AgentAuthCallback
        from linksoul_agentsdk.client.linksky_client import LinkskyClient
        from linksoul_agentsdk.passive import Asr2LlmCallback

        emit, s = self.emit, self.settings

        class Client(LinkskyClient):
            @staticmethod
            def _build_sslopt(url):
                return {"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True}

            def _on_close(self, ws, code, reason):
                emit("gateway_disconnected")
                super()._on_close(ws, code, reason)

            def _on_error(self, ws, error):
                emit("gateway_error")
                # Do not format the server's arbitrary error or credential-bearing URL.

        class Auth(AgentAuthCallback):
            def on_auth_state(self, app_id, code, msg):
                emit("gateway_connected" if code == 0 else "gateway_error")

        class Callback(Asr2LlmCallback):
            def on_robot_online(self, agent_id, agent_meta):
                emit("robot_online", agent_id=agent_id)

            def on_robot_offline(self, agent_id):
                emit("robot_offline", agent_id=agent_id)

            def on_request(self, agent_id, event_id, text, param, response):
                if s.agent_id and agent_id != s.agent_id:
                    return
                # Capture input arrival only. Text is never persisted in M1.
                if emit("input", agent_id=agent_id, event_id=event_id) is False:
                    return
                # This is an explicit connection-test agent, not a conversation provider.
                # Fail the request visibly instead of silently consuming its response chain.
                response.on_error(event_id, 503, "Connection test agent: inference is not configured")
                emit("response_attempted", agent_id=agent_id, event_id=event_id)

            def on_state(self, agent_id, event_id, state_name, state_value):
                emit("robot_state", agent_id=agent_id, event_id=event_id)

            # Suppress base implementations that log sensitive payloads.
            def on_histories(self, *args): pass
            def on_face_info(self, *args): pass
            def on_video_frame(self, *args): pass
            def on_greet_signal(self, *args): pass
            def on_function_call(self, *args): pass

        self.sdk = AgentSdk.create(s.gateway, s.app_id, s.app_key, s.app_secret)
        self.sdk.set_linksky_client_factory(Client)
        self.sdk.register_auth(Auth())
        self.callback = Callback(self.sdk)
        self.sdk.register_asr2_llm(self.callback)
        emit("gateway_connecting")
        self.sdk.initialize()

    def stop(self):
        if self.sdk:
            self.sdk.release()
