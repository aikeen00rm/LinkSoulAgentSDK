from uuid import uuid4


class FixtureAdapter:
    def __init__(self, emit):
        self.emit = emit
        self.run_id = str(uuid4())

    def start(self):
        self.emit("gateway_connecting")

    def stop(self):
        pass

    def action(self, action):
        kind = {"connect": "gateway_connected", "online": "robot_online",
                "input": "input", "disconnect": "gateway_disconnected",
                "offline": "robot_offline", "adapter-error": "adapter_error"}[action]
        self.emit(kind, agent_id="fixture-agent", event_id=str(uuid4()) if kind == "input" else None)
