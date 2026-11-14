from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health", summary="Health check")
async def health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
