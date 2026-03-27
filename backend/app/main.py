from contextlib import asynccontextmanager
import logging
from pathlib import Path
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.notifications import process_due_notifications


logger = logging.getLogger("glamour.notifications")


def _process_notifications_once() -> None:
    settings = get_settings()
    if not settings.vk_access_token:
        return

    with SessionLocal() as db:
        result = process_due_notifications(db)

    if result["processed"] > 0:
        logger.info(
            "Автоуведомления обработаны: processed=%s sent=%s skipped=%s failed=%s",
            result["processed"],
            result["sent"],
            result["skipped"],
            result["failed"],
        )


def _notification_worker(stop_event: Event) -> None:
    settings = get_settings()
    poll_interval = max(15, settings.notification_poll_interval_seconds)

    while not stop_event.wait(poll_interval):
        try:
            _process_notifications_once()
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось автоматически обработать уведомления.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    stop_event = Event()
    worker: Thread | None = None

    try:
        _process_notifications_once()
        if settings.vk_access_token:
            worker = Thread(
                target=_notification_worker,
                args=(stop_event,),
                name="glamour-notifications",
                daemon=True,
            )
            worker.start()
        yield
    finally:
        stop_event.set()
        if worker is not None and worker.is_alive():
            worker.join(timeout=2)


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allow_cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/admin", StaticFiles(directory=frontend_dist, html=True), name="admin")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"name": "Glamour", "service": settings.app_name, "status": "ok"}


@app.get("/healthz", tags=["meta"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
