from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .connectors import BusproConnector
from .demo import dashboard as demo_dashboard

VERSION = "0.1.4"
STATIC = Path(__file__).parent / "static"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [e-face-x4] %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="e-Face X4", version=VERSION, docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "version": VERSION}

    @app.get("/api/bootstrap")
    async def bootstrap() -> dict:
        settings = load_settings()
        connectors = [BusproConnector(settings.buspro, settings.request_timeout_s)]
        providers = await asyncio.gather(*(connector.snapshot() for connector in connectors))
        return {
            "version": VERSION,
            "mode": "demo" if settings.demo_mode else "live",
            "dashboard": demo_dashboard() if settings.demo_mode else {"rooms": [], "widgets": [], "media": None},
            "providers": providers,
        }

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8099, access_log=False)


if __name__ == "__main__":
    main()
