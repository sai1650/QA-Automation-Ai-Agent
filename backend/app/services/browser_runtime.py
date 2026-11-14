import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from app.config import get_settings


class BrowserRuntime:
    """Lazily launch one shared Chromium process and create isolated contexts."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(
            get_settings().browser_max_concurrent_executions
        )

    async def _ensure_browser(self) -> Browser:
        if self._browser is not None and self._browser.is_connected():
            return self._browser

        async with self._lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            manager = async_playwright()
            self._playwright = await manager.start()
            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=get_settings().browser_headless
                )
            except Exception:
                await self._playwright.stop()
                self._playwright = None
                raise
        return self._browser

    @asynccontextmanager
    async def execution_slot(self) -> AsyncGenerator[None, None]:
        async with self._slots:
            yield

    @asynccontextmanager
    async def isolated_context(self) -> AsyncGenerator[BrowserContext, None]:
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            accept_downloads=False,
            service_workers="block",
        )
        try:
            yield context
        finally:
            await context.close()

    async def close(self) -> None:
        async with self._lock:
            browser, playwright = self._browser, self._playwright
            self._browser = None
            self._playwright = None
            try:
                if browser is not None and browser.is_connected():
                    await browser.close()
            finally:
                if playwright is not None:
                    await playwright.stop()


browser_runtime = BrowserRuntime()
