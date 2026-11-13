import unittest
from fastapi.testclient import TestClient

from main import app


class TestBaseRoutes(unittest.TestCase):
    """Verify all routes return HTTP 200 and expected payloads."""

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

    def test_diagnostics_returns_200(self) -> None:
        response = self.client.get("/api/diagnostics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["backend"]["status"], "ok")
        self.assertTrue(payload["sqlite"]["connected"])
        self.assertIn("supabase", payload)

    def test_notes_roundtrip_returns_200(self) -> None:
        post_res = self.client.post("/api/notes", json={"note": "Connectivity check"})
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json().get("status"), "saved")

        get_res = self.client.get("/api/notes")
        self.assertEqual(get_res.status_code, 200)
        notes = get_res.json().get("notes", [])
        self.assertTrue(any(item["note"] == "Connectivity check" for item in notes))


if __name__ == "__main__":
    unittest.main()
