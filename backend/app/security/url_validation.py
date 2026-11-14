import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from pydantic import HttpUrl

from app.core.exceptions import ApplicationException


class UnsafeTargetURL(ValueError):
    """Raised when a target could resolve to a non-public network address."""


def validate_target_url(url: HttpUrl) -> None:
    """Validate URL shape; network-level SSRF checks belong before navigation."""
    if url.scheme not in {"http", "https"} or not url.host:
        raise ApplicationException(
            "Target URL must use HTTP or HTTPS.",
            status_code=422,
            code="invalid_target_url",
        )


async def resolve_public_addresses(host: str, port: int) -> set[str]:
    """Resolve a host and reject it unless every returned address is public."""
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            port,
            0,
            socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise UnsafeTargetURL("Target host could not be resolved.") from exc

    addresses = {
        str(ipaddress.ip_address(record[4][0]))
        for record in records
    }
    if not addresses:
        raise UnsafeTargetURL("Target host has no resolved IP addresses.")

    for address in addresses:
        parsed_address = ipaddress.ip_address(address)
        if isinstance(parsed_address, ipaddress.IPv6Address):
            parsed_address = parsed_address.ipv4_mapped or parsed_address
        if not parsed_address.is_global:
            raise UnsafeTargetURL(
                "Target host resolves to a private or reserved network."
            )
    return addresses


async def validate_public_http_url(url: str) -> set[str]:
    """Validate an HTTP(S) URL and its DNS results before browser requests."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise UnsafeTargetURL("Target URL is malformed.") from exc

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise UnsafeTargetURL("Only credential-free HTTP(S) URLs are allowed.")

    port = port or (443 if parsed.scheme.lower() == "https" else 80)
    if not 1 <= port <= 65535:
        raise UnsafeTargetURL("Target URL has an invalid port.")
    hostname = hostname.rstrip(".").lower()
    if (
        hostname == "localhost"
        or hostname.endswith((".localhost", ".local", ".internal"))
        or hostname in {"metadata", "metadata.google.internal"}
    ):
        raise UnsafeTargetURL("Local and internal hostnames are not allowed.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return await resolve_public_addresses(hostname, port)
    if isinstance(address, ipaddress.IPv6Address):
        address = address.ipv4_mapped or address
    if not address.is_global:
        raise UnsafeTargetURL("Private and reserved IP addresses are not allowed.")
    return {str(address)}
