"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from booktures import __version__
from booktures.api import media, router
from booktures.engine import Engine

WEB_DIR = Path(__file__).parent / "web"

NO_UI = """<!doctype html><meta charset="utf-8"><title>Booktures API</title>
<body style="font:16px/1.6 system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>Booktures API is running</h1>
<p>The web app has not been built. Run <code>npm --prefix frontend install && npm --prefix frontend run build</code>,
or start the dev server with <code>npm --prefix frontend run dev</code> and open
<a href="http://localhost:5173">localhost:5173</a>.</p><p><a href="/docs">API docs</a></p></body>"""


def create_app(home: str | Path | None = None, plugin_dirs: list[Path] | None = None) -> FastAPI:
    engine = Engine(home, plugin_dirs)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        engine.shutdown()

    app = FastAPI(title="Booktures", version=__version__, lifespan=lifespan)
    app.state.engine = engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(media)

    if (WEB_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    else:

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        def no_ui():
            return NO_UI

    return app
