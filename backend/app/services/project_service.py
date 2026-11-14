from enum import Enum
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationException
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.security.url_validation import validate_target_url


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


def create_project(session: Session, payload: ProjectCreate) -> Project:
    if not payload.authorization_confirmed:
        raise ApplicationException(
            "Authorization must be confirmed.",
            status_code=422,
            code="authorization_required",
        )
    validate_target_url(payload.base_url)
    project = Project(
        name=payload.name,
        base_url=str(payload.base_url),
        description=payload.description,
    )
    try:
        session.add(project)
        session.commit()
        session.refresh(project)
    except Exception:
        session.rollback()
        raise
    return project


def list_projects(
    session: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    is_active: bool | None,
    sort_order: SortOrder,
) -> tuple[list[Project], int]:
    filters = [Project.is_active.is_(True)] if is_active is None else []
    normalized_search = search.strip() if search is not None else None
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                Project.name.ilike(pattern),
                Project.description.ilike(pattern),
            )
        )
    if is_active is not None:
        filters.append(Project.is_active.is_(is_active))

    total = session.scalar(
        select(func.count()).select_from(Project).where(*filters)
    )
    ordering = (
        (Project.created_at.asc(), Project.id.asc())
        if sort_order is SortOrder.ASC
        else (Project.created_at.desc(), Project.id.desc())
    )
    projects = list(
        session.scalars(
            select(Project)
            .where(*filters)
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        )
    )
    return projects, total or 0


def get_project(session: Session, project_id: UUID) -> Project:
    project = session.get(Project, project_id)
    if project is None or not project.is_active:
        raise ApplicationException(
            "Project not found.", status_code=404, code="project_not_found"
        )
    return project


def update_project(
    session: Session,
    project_id: UUID,
    payload: ProjectUpdate,
) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None or not project.is_active:
        raise ApplicationException(
            "Project not found.", status_code=404, code="project_not_found"
        )

    changes = payload.model_dump(exclude_unset=True)
    if "base_url" in changes and changes["base_url"] is not None:
        validate_target_url(changes["base_url"])
        changes["base_url"] = str(changes["base_url"])
    for field, value in changes.items():
        setattr(project, field, value)
    try:
        session.commit()
        session.refresh(project)
    except Exception:
        session.rollback()
        raise
    return project


def archive_project(session: Session, project_id: UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None or not project.is_active:
        raise ApplicationException(
            "Project not found.", status_code=404, code="project_not_found"
        )
    project.is_active = False
    try:
        session.commit()
        session.refresh(project)
    except Exception:
        session.rollback()
        raise
    return project
