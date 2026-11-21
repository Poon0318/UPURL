import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import config, main
from app.models import CheckResult


class ApiTests(unittest.TestCase):
    def test_website_crud_status_and_history(self):
        async def idle_monitoring_loop(app):
            await asyncio.Future()

        class FakeMonitor:
            async def close(self):
                return None

            async def check_many(self, websites):
                site = websites[0]
                return [
                    CheckResult(
                        website_id=site.id,
                        checked_at="2026-10-07T12:00:00+00:00",
                        status="URL_MISMATCH",
                        http_status_code=200,
                        expected_url=site.expected_url,
                        actual_url="https://unexpected.example.test/",
                        response_time_ms=42.5,
                        error_message="Unexpected final URL after redirects",
                        dns_ok=True,
                        connection_ok=True,
                        redirect_chain=[
                            {"url": site.expected_url, "status_code": 302},
                            {"url": "https://unexpected.example.test/", "status_code": 200},
                        ],
                    )
                ]

        original_database_path = config.settings.database_path
        with tempfile.TemporaryDirectory() as temporary_directory:
            object.__setattr__(config.settings, "database_path", Path(temporary_directory) / "test.db")
            try:
                with patch.object(main, "monitoring_loop", idle_monitoring_loop):
                    with TestClient(main.app) as client:
                        seeded = client.get("/api/websites")
                        self.assertEqual(seeded.status_code, 200)
                        self.assertEqual(len(seeded.json()), 3)

                        created = client.post(
                            "/api/websites",
                            json={
                                "name": "Test target",
                                "expected_url": "https://target.example.test/",
                                "expected_status_code": 200,
                                "expected_final_url": None,
                                "expected_text": None,
                                "enabled": True,
                                "allow_scheme_mismatch": False,
                            },
                        )
                        self.assertEqual(created.status_code, 201)
                        website_id = created.json()["id"]

                        bulk_created = client.post(
                            "/api/websites/bulk",
                            json={
                                "websites": [
                                    {
                                        "name": f"Bulk target {index}",
                                        "expected_url": f"https://bulk-{index}.example.test/",
                                    }
                                    for index in range(2)
                                ],
                            },
                        )
                        self.assertEqual(bulk_created.status_code, 201)
                        self.assertEqual(bulk_created.json()["inserted"], 2)
                        self.assertEqual(len(bulk_created.json()["websites"]), 2)

                        invalid_bulk = client.post(
                            "/api/websites/bulk",
                            json={
                                "websites": [
                                    {"name": "Would be valid", "expected_url": "https://valid.example.test/"},
                                    {"name": "Invalid URL", "expected_url": "not-a-url"},
                                ],
                            },
                        )
                        self.assertEqual(invalid_bulk.status_code, 422)
                        self.assertEqual(len(client.get("/api/websites").json()), 6)

                        status_response = client.get("/api/status")
                        self.assertEqual(status_response.json()["summary"]["total"], 6)
                        self.assertEqual(status_response.json()["summary"]["enabled"], 6)
                        self.assertTrue(status_response.json()["monitoring_active"])

                        client.app.state.monitor = FakeMonitor()
                        checked = client.post(f"/api/check/{website_id}")
                        self.assertEqual(checked.status_code, 200)
                        self.assertEqual(checked.json()["status"], "URL_MISMATCH")
                        status_row = next(
                            row for row in client.get("/api/status").json()["websites"]
                            if row["name"] == "Test target"
                        )
                        self.assertEqual(status_row["id"], website_id)
                        self.assertEqual(status_row["result_id"], 1)
                        history = client.get(f"/api/history/{website_id}").json()
                        self.assertEqual(len(history), 1)
                        self.assertEqual(history[0]["redirect_chain"][0]["status_code"], 302)

                        updated = client.put(
                            f"/api/websites/{website_id}",
                            json={
                                **created.json(),
                                "name": "Updated target",
                            },
                        )
                        self.assertEqual(updated.status_code, 200)
                        self.assertEqual(updated.json()["name"], "Updated target")
                        self.assertEqual(len(client.get(f"/api/history/{website_id}").json()), 1)

                        self.assertEqual(client.delete(f"/api/websites/{website_id}").status_code, 204)
                        self.assertEqual(client.get(f"/api/websites/{website_id}").status_code, 404)

                        csv_content = (
                            "name,expected_url\n"
                            "Bulk One,https://bulk-one.example.test/\n"
                            "Bulk Two,https://bulk-two.example.test/\n"
                        )
                        imported = client.post(
                            "/api/websites/import",
                            content=csv_content,
                            headers={"Content-Type": "text/csv"},
                        )
                        self.assertEqual(imported.status_code, 201)
                        self.assertEqual(imported.json()["inserted"], 2)
                        self.assertEqual(len(imported.json()["websites"]), 2)

                        invalid_csv = (
                            "name,expected_url\n"
                            "Would Be Valid,https://valid.example.test/\n"
                            "Invalid URL,not-a-url\n"
                        )
                        rejected = client.post(
                            "/api/websites/import",
                            content=invalid_csv,
                            headers={"Content-Type": "text/csv"},
                        )
                        self.assertEqual(rejected.status_code, 400)
                        self.assertEqual(len(client.get("/api/websites").json()), 7)
            finally:
                object.__setattr__(config.settings, "database_path", original_database_path)


if __name__ == "__main__":
    unittest.main()