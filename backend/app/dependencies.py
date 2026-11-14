from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db
from app.services.browser_inspection import BrowserInspectionService
from app.services.browser_runtime import BrowserRuntime, browser_runtime
from app.services.qa_workflow_service import QAWorkflowService
from app.rag.service import KnowledgeService, create_knowledge_service
from app.evaluation.service import EvaluationService


def get_app_settings() -> Settings:
    return get_settings()


def get_database_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_browser_runtime() -> BrowserRuntime:
    return browser_runtime


def get_browser_inspection_service(
) -> BrowserInspectionService:
    return BrowserInspectionService(browser_runtime)


def get_qa_workflow_service() -> QAWorkflowService:
    return QAWorkflowService(
        get_browser_inspection_service(),
        knowledge_service=get_knowledge_service(),
    )


@lru_cache(maxsize=1)
def get_knowledge_service() -> KnowledgeService:
    return create_knowledge_service()


@lru_cache(maxsize=1)
def get_evaluation_service() -> EvaluationService:
    return EvaluationService()
