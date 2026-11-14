from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.project import (
    ProjectArchiveResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services import project_service
from app.services.project_service import SortOrder

router = APIRouter()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    description=(
        "Creates a project only after the caller confirms authorization to "
        "assess the target. Confirmation is not proof of ownership."
    ),
    responses={
        201: {
            "description": "Project created.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "8e39e85a-5356-4833-becf-a7cc6d5aa920",
                        "name": "E-Commerce Testing",
                        "base_url": "https://example.com/",
                        "description": "Automated testing project",
                        "is_active": True,
                        "created_at": "2026-11-09T12:00:00Z",
                        "updated_at": "2026-11-09T12:00:00Z",
                    }
                }
            },
        },
        422: {"description": "Invalid project data or authorization missing."},
    },
)
def create_project(
    payload: Annotated[
        ProjectCreate,
        Body(
            openapi_examples={
                "authorized_project": {
                    "summary": "Create an authorized project",
                    "value": {
                        "name": "E-Commerce Testing",
                        "base_url": "https://example.com",
                        "description": "Automated testing project",
                        "authorization_confirmed": True,
                    },
                }
            }
        ),
    ],
    session: Session = Depends(get_db),
) -> ProjectResponse:
    return project_service.create_project(session, payload)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    description="Lists projects with stable pagination, text search, and status filtering.",
    responses={422: {"description": "Invalid pagination or sort parameters."}},
)
def list_projects(
    session: Session = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    is_active: bool | None = None,
    sort_order: SortOrder = SortOrder.DESC,
) -> ProjectListResponse:
    offset = skip if skip is not None else (page - 1) * page_size
    effective_limit = limit if limit is not None else page_size
    items, total = project_service.list_projects(
        session,
        offset=offset,
        limit=effective_limit,
        search=search,
        is_active=is_active,
        sort_order=sort_order,
    )
    return ProjectListResponse(
        items=items,
        total=total,
        page=offset // effective_limit + 1,
        page_size=effective_limit,
        skip=offset,
        limit=effective_limit,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project",
    responses={404: {"description": "Project not found."}},
)
def get_project(
    project_id: UUID,
    session: Session = Depends(get_db),
) -> ProjectResponse:
    return project_service.get_project(session, project_id)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    description="Updates only supplied fields. At least one field is required.",
    responses={
        404: {"description": "Project not found."},
        422: {"description": "Invalid or empty project update."},
    },
)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    session: Session = Depends(get_db),
) -> ProjectResponse:
    return project_service.update_project(session, project_id, payload)


@router.delete(
    "/{project_id}",
    response_model=ProjectArchiveResponse,
    summary="Archive a project",
    description=(
        "Soft-archives a project without deleting it or its execution history."
    ),
    responses={404: {"description": "Project not found."}},
)
def archive_project(
    project_id: UUID,
    session: Session = Depends(get_db),
) -> ProjectArchiveResponse:
    project = project_service.archive_project(session, project_id)
    return ProjectArchiveResponse(
        id=project.id,
        is_active=project.is_active,
        message="Project archived.",
    )
