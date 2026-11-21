import asyncio
import json
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import httpx

from .config import settings
from .models import CheckResult, Website


logger = logging.getLogger("website_monitor")


def resolve_dns(hostname: str, port: int) -> list[str]:
    records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(record[4][0] for record in records))


def normalized_url(url: str, allow_scheme_mismatch: bool = False) -> str:
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    if allow_scheme_mismatch and scheme in {"http", "https"}:
        scheme = "http+https"

    path = quote(unquote(parsed.path or "/"), safe="/:@-._~!$&'()*+,;=%")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, hostname, path, parsed.query, ""))


class Monitor:
    def __init__(
        self,
        timeout_seconds: float = settings.request_timeout_seconds,
        max_concurrent_checks: int = settings.max_concurrent_checks,
        dns_resolver: Callable[[str, int], list[str]] = resolve_dns,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        fallback_transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent_checks)
        self.dns_resolver = dns_resolver
        limits = httpx.Limits(max_connections=max_concurrent_checks, max_keepalive_connections=max_concurrent_checks)
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=10,
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0)),
            limits=limits,
            transport=transport,
            headers={"User-Agent": "UPURL-Monitor/1.0"},
        )
        self.ipv4_client = None
        if fallback_transport is not None or transport is None:
            ipv4_transport = fallback_transport or httpx.AsyncHTTPTransport(local_address="0.0.0.0", limits=limits)
            self.ipv4_client = httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=10,
                timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0)),
                limits=limits,
                transport=ipv4_transport,
                headers={"User-Agent": "UPURL-Monitor/1.0"},
            )

    async def close(self) -> None:
        await self.client.aclose()
        if self.ipv4_client:
            await self.ipv4_client.aclose()

    async def check_many(self, websites: list[Website]) -> list[CheckResult]:
        return await asyncio.gather(*(self.check_one(site) for site in websites))

    async def check_one(self, site: Website) -> CheckResult:
        checked_at = datetime.now(timezone.utc).isoformat()
        dns_ok = False
        connection_ok = False
        actual_url = None
        http_status = None
        response_time_ms = None
        error_message = None
        redirect_chain: list[dict] = []
        resolved_addresses = []

        try:
            parsed = urlsplit(site.expected_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Expected URL must be a valid HTTP or HTTPS URL")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            async with self.semaphore:
                resolved_addresses = await asyncio.wait_for(
                    asyncio.to_thread(self.dns_resolver, parsed.hostname, port),
                    timeout=self.timeout_seconds,
                )
                dns_ok = True
                started = time.perf_counter()
                try:
                    response = await self.client.get(site.expected_url)
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    has_ipv4_address = any(":" not in address for address in resolved_addresses)
                    if not self.ipv4_client or not has_ipv4_address:
                        raise
                    response = await self.ipv4_client.get(site.expected_url)
                response_time_ms = round((time.perf_counter() - started) * 1000, 2)
                connection_ok = True
                http_status = response.status_code
                actual_url = str(response.url)
                redirect_chain = [
                    {"url": str(item.url), "status_code": item.status_code}
                    for item in response.history
                ]
                if response.history:
                    redirect_chain.append({"url": actual_url, "status_code": response.status_code})

                status, error_message = self._classify(site, response, actual_url)
        except (httpx.InvalidURL, ValueError) as exc:
            status = "DOWN"
            error_message = str(exc)
        except socket.gaierror as exc:
            status = "DOWN"
            error_message = f"DNS resolution failed: {exc}"
        except asyncio.TimeoutError:
            status = "DOWN"
            error_message = "DNS resolution timed out"
        except httpx.TimeoutException as exc:
            status = "DOWN"
            error_message = f"Request timed out: {exc.__class__.__name__}"
        except httpx.ConnectError as exc:
            status = "DOWN"
            error_message = self._connection_error(exc)
        except httpx.TooManyRedirects:
            status = "DOWN"
            error_message = "Redirect loop or too many redirects"
        except httpx.TransportError as exc:
            status = "DOWN"
            error_message = f"HTTP transport failure: {exc.__class__.__name__}"
        except Exception as exc:
            status = "DOWN"
            error_message = f"Unexpected check failure: {exc.__class__.__name__}"

        result = CheckResult(
            website_id=site.id,
            checked_at=checked_at,
            status=status,
            http_status_code=http_status,
            expected_url=site.expected_url,
            actual_url=actual_url,
            response_time_ms=response_time_ms,
            error_message=error_message,
            dns_ok=dns_ok,
            connection_ok=connection_ok,
            redirect_chain=redirect_chain,
        )
        logger.info(json.dumps({"website": site.name, **result.as_dict()}, separators=(",", ":")))
        return result

    @staticmethod
    def _classify(site: Website, response: httpx.Response, actual_url: str) -> tuple[str, Optional[str]]:
        if response.status_code >= 500:
            return "DOWN", f"Server returned HTTP {response.status_code}"

        expected_url = site.expected_final_url or site.expected_url
        allow_scheme = site.allow_scheme_mismatch or settings.allow_scheme_mismatch
        if normalized_url(expected_url, allow_scheme) != normalized_url(actual_url, allow_scheme):
            return "URL_MISMATCH", "Unexpected final URL after redirects"

        if response.status_code != site.expected_status_code:
            return "HTTP_ERROR", f"Expected HTTP {site.expected_status_code}, received {response.status_code}"
        if site.expected_text and site.expected_text not in response.text:
            return "HTTP_ERROR", "Expected text was not found in the response"
        return "UP", None

    @staticmethod
    def _connection_error(exc: httpx.ConnectError) -> str:
        text = str(exc).lower()
        detail = str(exc).strip() or exc.__class__.__name__
        if "certificate" in text or "ssl" in text or "tls" in text:
            return f"SSL/TLS error: {detail}"
        if "refused" in text:
            return f"Connection refused: {detail}"
        return f"Connection failed: {detail}"