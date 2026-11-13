import unittest
from fastapi.testclient import TestClient

from main import app


class TestBaseRoutes(unittest.TestCase):
    """Verify core routes return HTTP 200 and expected payloads."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_root_returns_200(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("Application Ready", response.text)

    def test_health_returns_200(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertIn("environment", payload)
        self.assertIn("supabase_configured", payload)

    def test_health_db_returns_200(self) -> None:
        response = self.client.get("/health/db")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("status", payload)
        self.assertIn("supabase_connected", payload)


if __name__ == "__main__":
    unittest.main()
