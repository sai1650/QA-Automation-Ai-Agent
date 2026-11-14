from typing import Any

import pytest

from app.services import browser_runtime as runtime_module
from app.services.browser_runtime import BrowserRuntime


class FakeContext:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.connected = True
        self.contexts: list[FakeContext] = []
        self.launch_options: dict[str, Any] | None = None

    def is_connected(self) -> bool:
        return self.connected

    async def new_context(self, **_: Any) -> FakeContext:
        context = FakeContext()
        self.contexts.append(context)
        return context

    async def close(self) -> None:
        self.connected = False


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_count = 0

    async def launch(self, **options: Any) -> FakeBrowser:
        self.launch_count += 1
        self.browser.launch_options = options
        return self.browser


class FakePlaywright:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakePlaywrightManager:
    def __init__(self, playwright: FakePlaywright) -> None:
        self.playwright = playwright

    async def start(self) -> FakePlaywright:
        return self.playwright


@pytest.mark.asyncio
async def test_runtime_reuses_browser_and_closes_isolated_contexts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = FakeBrowser()
    playwright = FakePlaywright(browser)
    manager = FakePlaywrightManager(playwright)
    monkeypatch.setattr(runtime_module, "async_playwright", lambda: manager)
    runtime = BrowserRuntime()

    async with runtime.isolated_context():
        pass
    async with runtime.isolated_context():
        pass

    assert playwright.chromium.launch_count == 1
    assert len(browser.contexts) == 2
    assert all(context.closed for context in browser.contexts)

    await runtime.close()

    assert browser.connected is False
    assert playwright.stopped is True
