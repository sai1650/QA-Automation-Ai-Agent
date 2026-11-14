import pytest

from app.security import url_validation
from app.security.url_validation import (
    UnsafeTargetURL,
    validate_public_http_url,
)
from app.services.browser_inspection import _guard_request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
    ],
)
async def test_rejects_local_private_or_credentialed_urls(url: str) -> None:
    with pytest.raises(UnsafeTargetURL):
        await validate_public_http_url(url)


@pytest.mark.asyncio
async def test_accepts_public_ip_address() -> None:
    addresses = await validate_public_http_url("https://93.184.216.34/")

    assert addresses == {"93.184.216.34"}


@pytest.mark.asyncio
async def test_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve_private(_: str, port: int) -> set[str]:
        assert port == 443
        raise UnsafeTargetURL("Target host resolves to a private or reserved network.")

    monkeypatch.setattr(url_validation, "resolve_public_addresses", resolve_private)

    with pytest.raises(UnsafeTargetURL, match="private or reserved"):
        await validate_public_http_url("https://example.test/")


class FakeRoute:
    def __init__(self) -> None:
        self.aborted = False
        self.continued = False

    async def abort(self, _: str) -> None:
        self.aborted = True

    async def continue_(self) -> None:
        self.continued = True


class FakeRequest:
    method = "GET"
    url = "http://169.254.169.254/latest/meta-data/"


@pytest.mark.asyncio
async def test_redirected_private_request_is_aborted() -> None:
    route = FakeRoute()

    await _guard_request(route, FakeRequest())

    assert route.aborted is True
    assert route.continued is False


class FakeMutationRequest:
    method = "POST"
    url = "https://93.184.216.34/submit"


@pytest.mark.asyncio
async def test_non_read_only_request_is_aborted() -> None:
    route = FakeRoute()

    await _guard_request(route, FakeMutationRequest())

    assert route.aborted is True
    assert route.continued is False
