from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import Settings
from app.services.browser_inspection import (
    BrowserInspectionFailure,
    BrowserInspectionService,
)


class FakeResponse:
    status = 200


class FakeConsoleMessage:
    type = "error"
    text = "failed request api_token=should-not-be-saved"


class FakeFailedRequest:
    method = "GET"
    url = "https://example.com/fail?token=hidden"
    failure = "net::ERR_FAILED"


class FakeHttpErrorRequest:
    method = "GET"


class FakeHttpErrorResponse:
    status = 503
    url = "https://example.com/unavailable?secret=hidden"
    request = FakeHttpErrorRequest()


class FakePage:
    def __init__(self, *, timeout: bool = False) -> None:
        self.url = "https://example.com/final?auth=hidden"
        self.viewport_size = {"width": 1280, "height": 720}
        self.handlers: dict[str, Any] = {}
        self.timeout = timeout

    def set_default_navigation_timeout(self, _: int) -> None:
        pass

    def set_default_timeout(self, _: int) -> None:
        pass

    def on(self, name: str, callback: Any) -> None:
        self.handlers[name] = callback

    async def goto(self, *_: Any, **__: Any) -> FakeResponse:
        if self.timeout:
            raise PlaywrightTimeoutError("timeout")
        self.handlers["console"](FakeConsoleMessage())
        self.handlers["requestfailed"](FakeFailedRequest())
        self.handlers["response"](FakeHttpErrorResponse())
        return FakeResponse()

    async def wait_for_load_state(self, *_: Any, **__: Any) -> None:
        return None

    async def evaluate(self, script: str) -> dict[str, Any]:
        if "definitions" in script:
            return {
                "total_count": 1,
                "buttons": [{"tag": "button", "aria-label": "Submit"}],
                "links": [],
                "inputs": [],
                "selects": [],
                "textareas": [],
                "forms": [],
                "truncated": False,
            }
        if "meta[name" in script:
            return {
                "title": "Example page",
                "viewport": {"width": 1280, "height": 720},
                "document_size": {"width": 1280, "height": 1500},
                "metadata": {"description": "A test page"},
            }
        return {"width": 1280, "height": 1500}

    async def title(self) -> str:
        return "Example page"

    async def screenshot(self, **_: Any) -> bytes:
        return b"fake png"


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.route_handler: Any = None
        self.websocket_route_handler: Any = None
        self.closed = False

    async def route(self, _: str, handler: Any) -> None:
        self.route_handler = handler

    async def route_web_socket(self, _: str, handler: Any) -> None:
        self.websocket_route_handler = handler

    async def new_page(self) -> FakePage:
        return self.page

    async def close(self) -> None:
        self.closed = True


class FakeRuntime:
    def __init__(self, context: FakeContext) -> None:
        self.context = context

    @asynccontextmanager
    async def execution_slot(self):
        yield

    @asynccontextmanager
    async def isolated_context(self):
        try:
            yield self.context
        finally:
            await self.context.close()


def create_inspector(tmp_path: Path, page: FakePage) -> BrowserInspectionService:
    settings = Settings(
        _env_file=None,
        artifact_dir=str(tmp_path),
        browser_max_page_pixels=3_000_000,
        browser_max_screenshot_bytes=1024,
    )
    return BrowserInspectionService(
        FakeRuntime(FakeContext(page)),  # type: ignore[arg-type]
        settings,
    )


@pytest.mark.asyncio
async def test_inspection_collects_bounded_page_data_and_artifacts(
    tmp_path: Path,
) -> None:
    execution_id = uuid4()
    inspector = create_inspector(tmp_path, FakePage())

    result = await inspector.inspect(execution_id, "https://93.184.216.34/")

    assert result["final_url"] == "https://example.com/final"
    assert result["navigation_status"] == 200
    assert result["title"] == "Example page"
    assert result["interactive_elements"]["buttons"][0]["tag"] == "button"
    assert len(inspector.last_artifacts) == 7
    assert (tmp_path / str(execution_id) / "screenshots" / "viewport.png").exists()
    assert (tmp_path / str(execution_id) / "screenshots" / "full_page.png").exists()
    console_file = (
        tmp_path / str(execution_id) / "logs" / "browser_console.json"
    ).read_text(encoding="utf-8")
    network_file = (
        tmp_path / str(execution_id) / "logs" / "network_events.json"
    ).read_text(encoding="utf-8")
    assert "should-not-be-saved" not in console_file
    assert "token=hidden" not in network_file
    assert "secret=hidden" not in network_file


@pytest.mark.asyncio
async def test_navigation_timeout_saves_failure_artifact(tmp_path: Path) -> None:
    execution_id = uuid4()
    inspector = create_inspector(tmp_path, FakePage(timeout=True))

    with pytest.raises(BrowserInspectionFailure, match="timed out") as failure:
        await inspector.inspect(execution_id, "https://93.184.216.34/")

    assert failure.value.artifacts
    assert (
        tmp_path / str(execution_id) / "screenshots" / "failure.png"
    ).exists()
