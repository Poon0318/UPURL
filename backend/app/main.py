import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .config import PROJECT_ROOT, settings
from .monitoring import Monitor
from .routes import monitoring_loop, router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("website_monitor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    database.seed_from_csv(PROJECT_ROOT / "data" / "websites.csv")
    app.state.settings = settings
    app.state.logger = logger
    app.state.monitor = Monitor()
    scheduler = asyncio.create_task(monitoring_loop(app))
    app.state.monitoring_task = scheduler
    yield
    scheduler.cancel()
    try:
        await scheduler
    except asyncio.CancelledError:
        pass
    await app.state.monitor.close()


app = FastAPI(title="UPURL Website Monitor", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}