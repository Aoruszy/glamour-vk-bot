from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.appointments import router as appointments_router
from app.api.routes.clients import router as clients_router
from app.api.routes.health import router as health_router
from app.api.routes.masters import router as masters_router
from app.api.routes.meta import router as meta_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.schedules import router as schedules_router
from app.api.routes.services import router as services_router
from app.api.routes.stats import router as stats_router
from app.api.routes.vk import router as vk_router
from app.config import get_settings

settings = get_settings()

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(meta_router, prefix=settings.api_prefix)
api_router.include_router(auth_router, prefix=settings.api_prefix)
api_router.include_router(clients_router, prefix=settings.api_prefix)
api_router.include_router(services_router, prefix=settings.api_prefix)
api_router.include_router(masters_router, prefix=settings.api_prefix)
api_router.include_router(schedules_router, prefix=settings.api_prefix)
api_router.include_router(appointments_router, prefix=settings.api_prefix)
api_router.include_router(notifications_router, prefix=settings.api_prefix)
api_router.include_router(stats_router, prefix=settings.api_prefix)
api_router.include_router(vk_router, prefix=settings.api_prefix)
