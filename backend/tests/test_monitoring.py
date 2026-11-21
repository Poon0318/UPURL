import asyncio
import socket
import unittest

import httpx

from app.models import Website
from app.monitoring import Monitor, normalized_url


def fake_dns(hostname, port):
    if hostname == "unresolvable.test":
        raise socket.gaierror("name or service not known")
    return ["127.0.0.1"]


class MonitoringTests(unittest.TestCase):
    def run_check(self, site, handler, fallback_handler=None):
        async def execute():
            monitor = Monitor(
                timeout_seconds=1,
                dns_resolver=fake_dns,
                transport=httpx.MockTransport(handler),
                fallback_transport=httpx.MockTransport(fallback_handler) if fallback_handler else None,
            )
            try:
                return await monitor.check_one(site)
            finally:
                await monitor.close()

        return asyncio.run(execute())

    def test_connection_error_retries_over_ipv4_when_available(self):
        def broken_connection(request):
            raise httpx.ConnectError("simulated IPv6 route failure", request=request)

        result = self.run_check(
            Website(6, "Dual stack service", "https://example.test/"),
            broken_connection,
            lambda request: httpx.Response(200, request=request),
        )
        self.assertEqual(result.status, "UP")
        self.assertTrue(result.connection_ok)

    def test_normalizes_hostname_trailing_slash_and_encoding(self):
        self.assertEqual(
            normalized_url("HTTPS://Example.COM/a%20b/"),
            normalized_url("https://example.com/a b"),
        )
        self.assertNotEqual(
            normalized_url("http://example.com"),
            normalized_url("https://example.com"),
        )
        self.assertEqual(
            normalized_url("http://example.com", allow_scheme_mismatch=True),
            normalized_url("https://example.com", allow_scheme_mismatch=True),
        )

    def test_success_and_redirect_chain(self):
        def handler(request):
            if request.url.path == "/start":
                return httpx.Response(302, headers={"location": "/health/"}, request=request)
            return httpx.Response(200, text="service ready", request=request)

        result = self.run_check(
            Website(1, "Redirecting service", "https://example.test/start", expected_final_url="https://example.test/health"),
            handler,
        )
        self.assertEqual(result.status, "UP")
        self.assertEqual(result.actual_url, "https://example.test/health/")
        self.assertEqual([hop["status_code"] for hop in result.redirect_chain], [302, 200])

    def test_unexpected_redirect_is_url_mismatch(self):
        def handler(request):
            if request.url.host == "example.test":
                return httpx.Response(302, headers={"location": "https://other.test/login"}, request=request)
            return httpx.Response(200, text="login", request=request)

        result = self.run_check(
            Website(2, "Unexpected redirect", "https://example.test/"),
            handler,
        )
        self.assertEqual(result.status, "URL_MISMATCH")
        self.assertEqual(result.actual_url, "https://other.test/login")

    def test_http_errors_and_server_failures_have_separate_statuses(self):
        for code, expected in [(404, "HTTP_ERROR"), (503, "DOWN")]:
            result = self.run_check(
                Website(code, "Test status", "https://example.test/"),
                lambda request, code=code: httpx.Response(code, request=request),
            )
            self.assertEqual(result.status, expected)
            self.assertEqual(result.http_status_code, code)

    def test_dns_failure_does_not_prevent_other_checks(self):
        async def execute():
            monitor = Monitor(
                timeout_seconds=1,
                max_concurrent_checks=2,
                dns_resolver=fake_dns,
                transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request)),
            )
            try:
                return await monitor.check_many(
                    [
                        Website(4, "DNS failure", "https://unresolvable.test/"),
                        Website(5, "Healthy", "https://example.test/"),
                    ]
                )
            finally:
                await monitor.close()

        failed, healthy = asyncio.run(execute())
        self.assertEqual(failed.status, "DOWN")
        self.assertFalse(failed.dns_ok)
        self.assertEqual(healthy.status, "UP")


if __name__ == "__main__":
    unittest.main()