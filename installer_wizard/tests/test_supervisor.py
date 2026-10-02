import json
import unittest

from fastapi.testclient import TestClient

import jarvis_supervisor
from config import FEATURES_DIR

HEADERS = {"X-Jarvis-Request": "1"}


class SupervisorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = TestClient(jarvis_supervisor.public)
        cls.admin = TestClient(jarvis_supervisor.admin)
        r = cls.admin.post("/api/auth/login", json={"username": "admin", "password": "jarvis"}, headers=HEADERS)
        assert r.status_code == 200, r.text

    def test_public_pages(self):
        for path in ("/", "/api/state"):
            with self.subTest(path=path):
                self.assertEqual(self.public.get(path).status_code, 200)
        state = self.public.get("/api/state").json()
        for key in ("phase", "components", "desk", "face", "sounds"):
            self.assertIn(key, state)

    def test_admin_requires_login(self):
        anon = TestClient(jarvis_supervisor.admin)
        self.assertEqual(anon.get("/api/automations", headers=HEADERS).status_code, 401)

    def test_admin_apis(self):
        for path in ("/", "/api/features", "/api/automations", "/api/automations/catalog", "/api/sounds", "/api/autonomy", "/api/selftest"):
            with self.subTest(path=path):
                r = self.admin.get(path, headers=HEADERS)
                self.assertEqual(r.status_code, 200, r.text[:300])

    def test_every_feature_manifest_loads(self):
        listing = self.admin.get("/api/features", headers=HEADERS).json()
        self.assertEqual(listing.get("errors") or [], [])
        ids = {f["id"] for f in listing["features"]}
        for manifest in FEATURES_DIR.glob("*/feature.json"):
            with self.subTest(feature=manifest.parent.name):
                self.assertIn(json.loads(manifest.read_text(encoding="utf-8"))["id"], ids)

    def test_automation_lifecycle(self):
        spec = {"name": "Prova CI", "triggers": [{"type": "manual"}], "actions": [{"type": "log", "text": "ciao"}]}
        created = self.admin.post("/api/automations", json=spec, headers=HEADERS)
        self.assertEqual(created.status_code, 200, created.text)
        aid = created.json()["id"]
        bad = self.admin.put(f"/api/automations/{aid}", json={"actions": []}, headers=HEADERS)
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.admin.delete(f"/api/automations/{aid}", headers=HEADERS).status_code, 200)

    def test_webhook_unknown_key(self):
        self.assertEqual(self.public.post("/api/automations/webhook/" + "0" * 32, json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
