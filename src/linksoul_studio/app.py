import asyncio
import fcntl
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from linksoul_studio.config import Settings
from linksoul_studio.events.collector import Collector

WEB = Path(__file__).parent / "web"


def create_app(settings=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        # One process owns the SDK and volume. A bad log path still leaves UI available.
        lease = None
        try:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            lease = (settings.data_dir / ".service.lock").open("a")
        except OSError:
            pass
        if lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lease.close()
                raise RuntimeError("Another studio process owns this data directory; use one worker.") from None
        collector = Collector(settings)
        if lease is None and settings.mode == "robot":
            collector.errors.append("Robot adapter blocked: data directory cannot be locked. Make it writable and restart.")
        app.state.collector = collector
        app.state.scenario_lock = asyncio.Lock()
        collector.start()
        try:
            yield
        finally:
            await run_in_threadpool(collector.stop)
            if lease: lease.close()

    app = FastAPI(title="LinkSoul Interaction Studio", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
    templates = Jinja2Templates(directory=WEB / "templates")

    @app.middleware("http")
    async def local_only_mutations(request, call_next):
        # No secrets or remote configuration API. Block cross-site form/fetch mutations.
        from urllib.parse import urlsplit
        from starlette.responses import JSONResponse
        origin = request.headers.get("origin")
        if request.method == "POST" and (request.headers.get("sec-fetch-site") == "cross-site"
                or (origin and urlsplit(origin).netloc != request.headers.get("host"))):
            return JSONResponse({"detail": "Open the console directly to perform this action."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        return response

    @app.get("/")
    def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={})

    @app.get("/health")
    def health():
        state = app.state.collector.snapshot()
        from starlette.responses import JSONResponse
        return JSONResponse({"service": "running", "mode": state["mode"],
                             "ready": not state["problems"], "build": state["versions"]["build"]},
                            status_code=503 if state["problems"] else 200)

    @app.get("/api/state")
    def state():
        return app.state.collector.snapshot()

    @app.post("/api/checks/{action}")
    async def checks(action: str):
        if app.state.scenario_lock.locked():
            raise HTTPException(409, "Wait for the fixture scenario to finish.")
        c = app.state.collector
        if action == "begin":
            await run_in_threadpool(c.begin)
            return {"started": True}
        if action == "save":
            if not c.check_started:
                raise HTTPException(409, "Start a new check before saving.")
            return await run_in_threadpool(c.report)
        raise HTTPException(404, "Unknown check action")

    @app.post("/api/fixture/{action}")
    async def fixture(action: str):
        c = app.state.collector
        if settings.mode != "fixture":
            raise HTTPException(403, "Fixture actions are unavailable in robot mode.")
        if app.state.scenario_lock.locked():
            raise HTTPException(409, "Wait for the current fixture scenario.")
        async with app.state.scenario_lock:
            if action in {"recovery", "no-input", "invalid-config", "storage-failure"}:
                c.probe_error = None
                c.adapter_error = False
                await run_in_threadpool(c.begin)
                if action in {"invalid-config", "storage-failure"}:
                    await run_in_threadpool(c.probe, action)
                else:
                    # Disconnect first so previous state never supplies this check's evidence.
                    sequence = ["disconnect", "connect", "online", "input", "disconnect", "connect", "online"]
                    if action == "recovery": sequence.append("input")
                    for step in sequence:
                        c.adapter.action(step)
                        await asyncio.sleep(.25)
                return await run_in_threadpool(c.report, action)
            if action == "clear-error":
                c.probe_error, c.adapter_error = None, False
            elif action in {"connect", "online", "input", "disconnect", "offline", "adapter-error"}:
                c.adapter.action(action)
                await run_in_threadpool(c.flush)
            else:
                raise HTTPException(404, "Unknown fixture action")
            return c.snapshot()

    @app.get("/api/reports/{report_id}")
    def report(report_id: UUID):
        path = settings.data_dir / "verification" / settings.mode / f"{report_id}.json"
        if not path.is_file(): raise HTTPException(404, "Report unavailable")
        return FileResponse(path, media_type="application/json", filename=f"{settings.mode}-{report_id}.json")

    return app


app = create_app()
