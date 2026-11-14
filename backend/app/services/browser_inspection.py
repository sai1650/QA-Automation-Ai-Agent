import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from playwright.async_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from app.config import Settings, get_settings
from app.security.url_validation import (
    UnsafeTargetURL,
    validate_public_http_url,
)
from app.services.browser_artifacts import ArtifactStore
from app.services.browser_runtime import BrowserRuntime

_ELEMENTS_SCRIPT = """() => {
    const maximum = __MAX_ELEMENTS__;
    const definitions = {
      buttons: 'button,input[type=button],input[type=submit],[role=button]',
      links: 'a[href]',
      inputs: 'input',
      selects: 'select',
      textareas: 'textarea',
      forms: 'form'
    };
    const attributes = ['id', 'name', 'type', 'placeholder', 'href',
                        'aria-label', 'role'];
    const allInteractive = new Set(
      Object.values(definitions).flatMap(
        (selector) => Array.from(document.querySelectorAll(selector))
      )
    );
    const result = {total_count: allInteractive.size};
    let remaining = maximum;
    for (const [kind, selector] of Object.entries(definitions)) {
      const nodes = Array.from(document.querySelectorAll(selector));
      result[kind] = nodes.slice(0, remaining).map((node) => {
        const item = {tag: node.tagName.toLowerCase()};
        for (const name of attributes) {
          const value = node.getAttribute(name);
          if (value) {
            if (name === 'href') {
              try {
                const link = new URL(value, location.href);
                item.href = ['http:', 'https:'].includes(link.protocol)
                  ? link.origin + link.pathname
                  : null;
              } catch (_) {
                item.href = null;
              }
            } else {
              item[name] = value.slice(0, 200);
            }
          }
        }
        return item;
      });
      remaining = Math.max(0, remaining - result[kind].length);
    }
    result.truncated = result.total_count > maximum;
    return result;
}"""

_PAGE_METADATA_SCRIPT = """() => {
    const metadata = {};
    for (const node of document.querySelectorAll('meta[name],meta[property]')) {
      const key = (node.getAttribute('name') || node.getAttribute('property') || '')
        .trim().toLowerCase();
      if (!key || /token|auth|csrf|password|secret|cookie|key/.test(key)) continue;
      const value = (node.getAttribute('content') || '').slice(0, 500);
      if (value) metadata[key.slice(0, 100)] = value;
      if (Object.keys(metadata).length >= 50) break;
    }
    return {
      title: (document.title || '').slice(0, 500),
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      },
      document_size: {
        width: document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight
      },
      metadata
    };
}"""

_SENSITIVE_TEXT = re.compile(
    r"(?i)\b(password|token|secret|authorization|cookie|api[_-]?(?:key|token))\b"
    r"(\s*[:=]\s*)[^\s,;]+"
)


class BrowserInspectionFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        result: dict[str, Any],
        artifacts: list[dict[str, Any]],
        status_code: int = 502,
        code: str = "browser_inspection_failed",
    ) -> None:
        super().__init__(message)
        self.result = result
        self.artifacts = artifacts
        self.status_code = status_code
        self.code = code


def sanitize_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    netloc = f"{host}:{port}" if port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _safe_text(value: str, limit: int = 500) -> str:
    return _SENSITIVE_TEXT.sub(r"\1\2[redacted]", value)[:limit]


async def _guard_request(route: Any, request: Any) -> None:
    if request.method.upper() not in {"GET", "HEAD"}:
        await route.abort("blockedbyclient")
        return
    try:
        await validate_public_http_url(request.url)
    except UnsafeTargetURL:
        await route.abort("blockedbyclient")
        return
    await route.continue_()


async def _block_websocket(route: Any) -> None:
    await route.close(code=1008, reason="WebSocket traffic is disabled for inspection.")


class BrowserInspectionService:
    def __init__(
        self,
        runtime: BrowserRuntime,
        settings: Settings | None = None,
    ) -> None:
        self.runtime = runtime
        self.settings = settings or get_settings()
        self.artifacts = ArtifactStore(self.settings.artifact_root)
        self.last_artifacts: list[dict[str, Any]] = []

    async def inspect(self, execution_id: UUID, target_url: str) -> dict[str, Any]:
        try:
            await validate_public_http_url(target_url)
        except UnsafeTargetURL as exc:
            raise BrowserInspectionFailure(
                str(exc),
                result={"error": str(exc)},
                artifacts=[],
                status_code=422,
                code="unsafe_target_url",
            ) from exc

        events: dict[str, list[dict[str, Any]]] = {
            "console": [],
            "page_errors": [],
            "network": [],
        }
        artifacts: list[dict[str, Any]] = []
        result: dict[str, Any] = {}
        async with self.runtime.execution_slot():
            async with self.runtime.isolated_context() as context:
                await context.route("**/*", _guard_request)
                await context.route_web_socket("**/*", _block_websocket)
                page = await context.new_page()
                page.set_default_navigation_timeout(
                    self.settings.browser_navigation_timeout_ms
                )
                page.set_default_timeout(self.settings.browser_action_timeout_ms)
                self._attach_event_handlers(page, events)
                try:
                    response = await page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=self.settings.browser_navigation_timeout_ms,
                    )
                    load_status = "domcontentloaded"
                    try:
                        await page.wait_for_load_state(
                            "load",
                            timeout=self.settings.browser_action_timeout_ms,
                        )
                        load_status = "load"
                    except PlaywrightTimeoutError:
                        pass
                    result = await self._collect_page(page, response, load_status)
                    artifacts.extend(
                        await self._capture_success(execution_id, page, result, events)
                    )
                    self.last_artifacts = artifacts
                    return result
                except (PlaywrightError, OSError) as exc:
                    message = (
                        "Navigation timed out."
                        if isinstance(exc, PlaywrightTimeoutError)
                        else "Browser navigation or inspection failed."
                    )
                    result = {
                        "final_url": sanitize_url(page.url) if page.url else None,
                        "error": message,
                        "events": events,
                    }
                    artifacts.extend(
                        await self._capture_failure(
                            execution_id,
                            page,
                            result,
                            events,
                        )
                    )
                    self.last_artifacts = artifacts
                    raise BrowserInspectionFailure(
                        message,
                        result=result,
                        artifacts=artifacts,
                    ) from exc
                except Exception as exc:
                    message = "Browser inspection failed."
                    result = {
                        "final_url": sanitize_url(page.url) if page.url else None,
                        "error": message,
                        "failure_type": type(exc).__name__,
                        "events": events,
                    }
                    artifacts.extend(
                        await self._capture_failure(
                            execution_id,
                            page,
                            result,
                            events,
                        )
                    )
                    self.last_artifacts = artifacts
                    raise BrowserInspectionFailure(
                        message,
                        result=result,
                        artifacts=artifacts,
                    ) from exc

    def _attach_event_handlers(
        self,
        page: Page,
        events: dict[str, list[dict[str, Any]]],
    ) -> None:
        maximum = self.settings.browser_max_events

        def append(kind: str, item: dict[str, Any]) -> None:
            if len(events[kind]) < maximum:
                events[kind].append(item)

        page.on(
            "console",
            lambda message: append(
                "console",
                {
                    "type": message.type,
                    "text": _safe_text(message.text),
                },
            )
            if message.type in {"error", "warning", "log"}
            else None,
        )
        page.on(
            "pageerror",
            lambda error: append(
                "page_errors",
                {"message": _safe_text(str(error))},
            ),
        )
        page.on(
            "requestfailed",
            lambda request: append(
                "network",
                {
                    "event": "request_failed",
                    "method": request.method,
                    "url": sanitize_url(request.url),
                    "failure": _safe_text(request.failure or "request failed"),
                },
            ),
        )
        page.on(
            "response",
            lambda response: append(
                "network",
                {
                    "event": "http_error",
                    "method": response.request.method,
                    "url": sanitize_url(response.url),
                    "status": response.status,
                },
            )
            if response.status >= 400
            else None,
        )

    async def _collect_page(
        self,
        page: Page,
        response: Any,
        load_status: str,
    ) -> dict[str, Any]:
        metadata = await page.evaluate(_PAGE_METADATA_SCRIPT)
        metadata_values = metadata.get("metadata", {})
        safe_metadata = {
            key: _safe_text(value, 500)
            for key, value in metadata_values.items()
            if isinstance(value, str)
        }
        elements_script = _ELEMENTS_SCRIPT.replace(
            "__MAX_ELEMENTS__",
            str(self.settings.browser_max_elements),
        )
        elements = await page.evaluate(elements_script)
        return {
            "final_url": sanitize_url(page.url),
            "title": _safe_text(metadata.get("title", "")),
            "navigation_status": response.status if response else None,
            "page_load_status": load_status,
            "viewport": metadata.get("viewport", {}),
            "document_size": metadata.get("document_size", {}),
            "metadata": safe_metadata,
            "interactive_elements": elements,
        }

    async def _capture_success(
        self,
        execution_id: UUID,
        page: Page,
        result: dict[str, Any],
        events: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        artifacts = [
            await self.artifacts.write_json(
                execution_id,
                "inspection/page_metadata.json",
                {key: value for key, value in result.items() if key != "interactive_elements"},
            ),
            await self.artifacts.write_json(
                execution_id,
                "inspection/elements.json",
                result["interactive_elements"],
            ),
        ]
        artifacts.extend(await self._capture_screenshots(execution_id, page, "screenshots"))
        artifacts.extend(await self._write_events(execution_id, events))
        return artifacts

    async def _capture_failure(
        self,
        execution_id: UUID,
        page: Page,
        result: dict[str, Any],
        events: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        try:
            screenshot = await page.screenshot(
                type="png",
                full_page=False,
                timeout=self.settings.browser_action_timeout_ms,
            )
            if len(screenshot) <= self.settings.browser_max_screenshot_bytes:
                artifacts.append(
                    await self.artifacts.write_bytes(
                        execution_id,
                        "screenshots/failure.png",
                        screenshot,
                        "image/png",
                    )
                )
        except PlaywrightError:
            pass
        artifacts.append(
            await self.artifacts.write_json(
                execution_id,
                "inspection/failure.json",
                result,
            )
        )
        artifacts.extend(await self._write_events(execution_id, events))
        return artifacts

    async def _capture_screenshots(
        self,
        execution_id: UUID,
        page: Page,
        directory: str,
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        dimensions = await page.evaluate(
            """() => ({
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight
            })"""
        )
        full_page_pixels = dimensions["width"] * dimensions["height"]
        if full_page_pixels <= self.settings.browser_max_page_pixels:
            try:
                screenshot = await page.screenshot(
                    type="png",
                    full_page=True,
                    animations="disabled",
                    timeout=self.settings.browser_action_timeout_ms,
                )
                if len(screenshot) <= self.settings.browser_max_screenshot_bytes:
                    artifacts.append(
                        await self.artifacts.write_bytes(
                            execution_id,
                            f"{directory}/full_page.png",
                            screenshot,
                            "image/png",
                        )
                    )
            except PlaywrightError:
                pass

        screenshot = await page.screenshot(
            type="png",
            full_page=False,
            animations="disabled",
            timeout=self.settings.browser_action_timeout_ms,
        )
        if len(screenshot) <= self.settings.browser_max_screenshot_bytes:
            artifacts.append(
                await self.artifacts.write_bytes(
                    execution_id,
                    f"{directory}/viewport.png",
                    screenshot,
                    "image/png",
                )
            )
        return artifacts

    async def _write_events(
        self,
        execution_id: UUID,
        events: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        names = {
            "console": "logs/browser_console.json",
            "page_errors": "logs/page_errors.json",
            "network": "logs/network_events.json",
        }
        return [
            await self.artifacts.write_json(execution_id, names[kind], values)
            for kind, values in events.items()
        ]
