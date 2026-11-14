import unittest
from fastapi.testclient import TestClient

from main import app


class TestBaseRoutes(unittest.TestCase):
    """Verify all CrowdGuard Bengaluru routes return HTTP 200 and expected payloads."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_root_returns_200(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("CrowdGuard Bengaluru", response.text)

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
        self.assertIn("n8n", payload)

    def test_notes_roundtrip_returns_200(self) -> None:
        post_res = self.client.post("/api/notes", json={"note": "Connectivity check"})
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json().get("status"), "saved")

        get_res = self.client.get("/api/notes")
        self.assertEqual(get_res.status_code, 200)
        notes = get_res.json().get("notes", [])
        self.assertTrue(any(item["note"] == "Connectivity check" for item in notes))

    def test_state_and_corridor_filtering_returns_200(self) -> None:
        self.client.post("/api/demo/scenario", json={"scenario": "reset"})
        res = self.client.get("/api/state?corridor=koramangala_madiwala")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["city"], "Bengaluru")
        self.assertEqual(len(data["zones"]), 5)
        # Ensure Chinnaswamy alerts do not leak into Koramangala-Madiwala route alerts
        for alert in data["route_alerts"]:
            self.assertEqual(alert["corridor"], "koramangala_madiwala")

    def test_public_photo_report_updates_madiwala_and_police_feed(self) -> None:
        self.client.post("/api/demo/scenario", json={"scenario": "reset"})
        fake_photo = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
        post_res = self.client.post(
            "/api/reports",
            json={
                "zone_id": "madiwala_koramangala",
                "note": "Small crowd and traffic jam near Madiwala Water Tank junction",
                "reporter_corridor": "koramangala_madiwala",
                "photo_data": fake_photo,
            },
        )
        self.assertEqual(post_res.status_code, 200)
        body = post_res.json()
        self.assertEqual(body["status"], "published")
        self.assertIn("Madiwala", body["ai_summary"])

        # Verify friend's phone on koramangala_madiwala corridor immediately receives the alert
        state_res = self.client.get("/api/state?corridor=koramangala_madiwala")
        self.assertEqual(state_res.status_code, 200)
        state_data = state_res.json()
        self.assertTrue(len(state_data["corridor_reports"]) >= 1)
        self.assertTrue(any(r["zone_id"] == "madiwala_koramangala" for r in state_data["all_reports"]))

    def test_police_override_and_n8n_config_return_200(self) -> None:
        override_res = self.client.post(
            "/api/zones/chinnaswamy_gate3/override",
            json={"action": "reallocate_from_gate1", "officer_note": "Move 2 units to Gate 3"},
        )
        self.assertEqual(override_res.status_code, 200)
        self.assertEqual(override_res.json()["status"], "updated")

        n8n_res = self.client.post(
            "/api/n8n/config",
            json={"webhook_url": "", "police_email": "controlroom.blr@ksp.gov.in"},
        )
        self.assertEqual(n8n_res.status_code, 200)
        self.assertEqual(n8n_res.json()["status"], "ok")

        # Reset back to clean baseline after test
        self.client.post("/api/demo/scenario", json={"scenario": "reset"})


if __name__ == "__main__":
    unittest.main()
