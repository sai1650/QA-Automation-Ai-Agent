from fastapi import APIRouter

from app.api.routes.executions import router as executions_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.projects import router as projects_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(executions_router, tags=["executions"])
api_router.include_router(knowledge_router, tags=["knowledge"])
api_router.include_router(evaluations_router, prefix="/evaluations", tags=["evaluations"])
