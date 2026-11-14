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
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)

from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, include_in_schema=False)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    class CachedStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    if (frontend_dist / "assets").exists():
        app.mount("/assets", CachedStaticFiles(directory=str(frontend_dist / "assets")), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = frontend_dist / full_path
        if full_path and target.exists() and target.is_file():
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if full_path.startswith("assets/") else {"Cache-Control": "public, max-age=3600"}
            return FileResponse(target, headers=headers)
        return FileResponse(frontend_dist / "index.html", headers={"Cache-Control": "no-cache"})

else:
    @app.get("/", tags=["application"], summary="Application status")
    async def root(request: Request) -> dict[str, str]:
        app_settings = request.app.state.settings
        return {
            "application": app_settings.app_name,
            "version": app_settings.app_version,
            "environment": app_settings.environment,
            "status": "API is operational",
        }
