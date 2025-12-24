from __future__ import annotations

import asyncio
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from .api.routes import router as api_router
from .config import settings
from .database import init_db
from .services.jobs import downgrade_jobs
from .services.licensing import licensing_client
from .services.scheduler import scheduler
from .utils.auth import get_api_key

app = FastAPI(title="ZSTRM Backend")
app.mount("/static", StaticFiles(directory="server/app/static"), name="static")


@app.on_event("startup")
async def startup() -> None:
    init_db()
    licensing_client.start()
    scheduler.start()
    downgrade_jobs()


@app.get("/health")
def health(_: str = Depends(get_api_key)) -> dict[str, str]:
    return {"status": "ok", "runner": settings.runner_id}


@app.get("/dashboard")
def dashboard(_: str = Depends(get_api_key)) -> dict[str, str]:
    return {"message": "Navigate to /static/index.html for dashboard"}


app.include_router(api_router, prefix="/api")
