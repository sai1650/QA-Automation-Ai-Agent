import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.services.browser_runtime import browser_runtime

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Application startup: %s", settings.app_name)
    try:
        yield
    finally:
        await browser_runtime.close()
        logger.info("Application shutdown: %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend foundation for the Autonomous QA Intelligence Platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "health", "description": "Application health checks."},
        {"name": "projects", "description": "Project management operations."},
        {
            "name": "executions",
            "description": "Execution creation and status management.",
        },
    ],
    lifespan=lifespan,
)

app.state.settings = settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, include_in_schema=False)


@app.get("/", tags=["application"], summary="Application status")
async def root(request: Request) -> dict[str, str]:
    app_settings = request.app.state.settings
    return {
        "application": app_settings.app_name,
        "version": app_settings.app_version,
        "environment": app_settings.environment,
        "status": "API is operational",
    }
