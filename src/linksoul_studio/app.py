import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import Settings
from .service import Service

WEB = Path(__file__).parent / "web"
templates = Environment(loader=FileSystemLoader(WEB / "templates"), autoescape=select_autoescape())


def create_app(settings=None):
    config = settings or Settings.from_env()
    service = Service(config)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        service.start()
        yield
        service.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service
    app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "Referrer-Policy": "no-referrer",
                                 "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"})
        return response

    @app.get("/", response_class=HTMLResponse)
    def home():
        return templates.get_template("index.html").render(token=token)

    @app.get("/conversations", response_class=HTMLResponse)
    def conversations():
        return templates.get_template("conversations.html").render(token=token)

    @app.get("/api/conversations")
    def conversation_state():
        return service.recorder.snapshot()

    @app.get("/api/sessions/{sid}")
    def session_detail(sid: str):
        detail = service.recorder.db.detail(config.mode, sid)
        if not detail:
            raise HTTPException(404, "Session unavailable in the current mode. Check storage or retention.")
        return detail

    @app.post("/api/m2/{operation}")
    def m2(operation: str, request: Request, sid: str = ""):
        if not secrets.compare_digest(request.headers.get("x-studio-token", ""), token):
            raise HTTPException(403, "Reload the console before running a check.")
        if not service.actions.acquire(blocking=False):
            raise HTTPException(409, "Another operation is running.")
        try:
            if operation in {"prepare", "reopen"}:
                service.recorder.verify(sid, prepare=operation=="prepare")
            elif operation == "connect-replies":
                service.connect_robot(conversations=True)
            else:
                service.recorder.fixture(operation)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        finally:
            service.actions.release()
        return service.recorder.snapshot()

    @app.get("/api/state")
    def state():
        return service.snapshot()

    @app.get("/health")
    def health():
        healthy = not config.errors and not service.store.error and not service.dropped and not service.recorder.db.error and not service.recorder.dropped
        return JSONResponse({"ready": healthy, "mode": config.mode, "versions": service.versions},
                            status_code=200 if healthy else 503)

    @app.post("/api/action/{action}")
    def action(action: str, request: Request):
        # Prevent cross-origin form submissions from operating the local console.
        if not secrets.compare_digest(request.headers.get("x-studio-token", ""), token):
            raise HTTPException(403, "Reload the console before running a check.")
        if not service.actions.acquire(blocking=False):
            raise HTTPException(409, "Another operation is running. Wait for it to finish.")
        try:
            if action.startswith("fixture-"):
                service.run_fixture(action.removeprefix("fixture-"))
            elif action == "reset":
                service.reset_fixture()
            elif action == "start-check":
                service.start_check()
            elif action == "finish-check":
                service.finish_check()
            elif action == "connect":
                service.connect_robot()
            elif action == "disconnect":
                if config.mode != "robot":
                    raise ValueError("Use the fixture disconnect control in fixture mode.")
                service.disconnect_robot()
            elif action in {"step-connected", "step-online", "step-input", "step-disconnected", "step-offline"}:
                if config.mode != "fixture":
                    raise ValueError("Simulation controls are unavailable in robot mode.")
                import uuid
                kind = action.removeprefix("step-")
                service.emit(kind, config.agent_id or "fixture-a3" if kind in {"online", "offline", "input"} else None,
                             uuid.uuid4().hex if kind == "input" else None)
                service.drain()
            else:
                raise HTTPException(404, "Unknown operation.")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        finally:
            service.actions.release()
        return service.snapshot()

    @app.get("/api/reports/{mode}/{report_id}")
    def report(mode: str, report_id: str):
        if mode != config.mode:
            raise HTTPException(404, "Report is not in the current mode.")
        try:
            data = service.store.read_report(mode, report_id)
        except (OSError, ValueError):
            raise HTTPException(404, "Report unavailable; check storage or restore from backup.") from None
        return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{mode}-{report_id}.json"'})

    return app


app = create_app()
