import io
import json
import tempfile
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from oncoforge.web_api import PortalAPI, PortalAPIConfig


def call_api(app, method, path, payload=None, api_key=""):
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    environ = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_TYPE": "application/json" if payload is not None else "",
            "CONTENT_LENGTH": str(len(body)) if payload is not None else "",
            "wsgi.input": io.BytesIO(body),
        }
    )
    if api_key:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {api_key}"
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    response["body"] = b"".join(app(environ, start_response))
    response["json"] = json.loads(response["body"]) if response["body"] else None
    return response


class WebAPITests(unittest.TestCase):
    def test_health_and_profiles_are_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = PortalAPI(PortalAPIConfig(api_key="", output_dir=Path(tmp)))
            health = call_api(app, "GET", "/lab/oncoforge/api/health")
            profiles = call_api(app, "GET", "/lab/oncoforge/api/profiles")

        self.assertEqual(health["status"], "200 OK")
        self.assertFalse(health["json"]["mission_auth_configured"])
        self.assertEqual(profiles["status"], "200 OK")
        self.assertTrue(profiles["json"]["profiles"])

    def test_mission_endpoint_fails_closed_without_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = PortalAPI(PortalAPIConfig(api_key="", output_dir=Path(tmp)))
            response = call_api(
                app,
                "POST",
                "/lab/oncoforge/api/portal/missions",
                {"profile": "melanoma_cutaneous"},
            )

        self.assertEqual(response["status"], "503 Service Unavailable")

    def test_authenticated_mission_can_be_created_and_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = PortalAPI(PortalAPIConfig(api_key="test-key", output_dir=Path(tmp)))
            created = call_api(
                app,
                "POST",
                "/lab/oncoforge/api/portal/missions",
                {
                    "profile": "melanoma_cutaneous",
                    "steps": 3,
                    "healthy": 20,
                    "cancer": 6,
                    "max_qsa_candidates": 4,
                    "max_marker_qubits": 6,
                },
                api_key="test-key",
            )
            mission_id = created["json"]["mission_id"]
            loaded = call_api(
                app,
                "GET",
                f"/lab/oncoforge/api/portal/missions/{mission_id}",
                api_key="test-key",
            )

        self.assertEqual(created["status"], "201 Created")
        self.assertEqual(created["json"]["profile"]["id"], "melanoma_cutaneous")
        self.assertNotIn("mission_path", created["json"])
        self.assertNotIn("experiment_path", created["json"]["simulation"])
        self.assertNotIn("output_dir", created["json"]["config"])
        self.assertNotIn("output_dir", created["json"]["research_loop_plan"])
        self.assertEqual(loaded["status"], "200 OK")
        self.assertEqual(loaded["json"]["mission_id"], mission_id)

    def test_web_request_cannot_choose_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = PortalAPI(PortalAPIConfig(api_key="test-key", output_dir=Path(tmp)))
            response = call_api(
                app,
                "POST",
                "/lab/oncoforge/api/portal/missions",
                {"profile": "melanoma_cutaneous", "output_dir": "C:/outside"},
                api_key="test-key",
            )

        self.assertEqual(response["status"], "400 Bad Request")
        self.assertIn("output_dir", response["json"]["error"])

    def test_web_request_rejects_unbounded_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = PortalAPI(PortalAPIConfig(api_key="test-key", output_dir=Path(tmp)))
            response = call_api(
                app,
                "POST",
                "/lab/oncoforge/api/portal/missions",
                {
                    "profile": "melanoma_cutaneous",
                    "steps": 1000,
                    "healthy": 5000,
                    "cancer": 1000,
                },
                api_key="test-key",
            )

        self.assertEqual(response["status"], "422 Unprocessable Entity")
        self.assertIn("cell-step workload", response["json"]["error"])


if __name__ == "__main__":
    unittest.main()
