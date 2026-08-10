import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from oncoforge.cli import main as cli_main
from oncoforge.core.cancer_profiles import SCOPE_NOTICE
from oncoforge.core.portal_mission import (
    PORTAL_PAYLOAD_VERSION,
    PortalMissionConfig,
    build_portal_mission,
    build_web_handoff,
)


class PortalMissionTests(unittest.TestCase):
    def test_web_handoff_names_required_portal_parts(self):
        handoff = build_web_handoff()
        self.assertIn("/lab/oncoforge/portal", handoff["portal_routes"])
        self.assertIn("MissionSetupPanel", handoff["required_components"])
        self.assertIn("POST /lab/oncoforge/api/portal/missions", handoff["api_endpoints"])
        self.assertTrue(any("scope notice" in rule.lower() for rule in handoff["hard_rules"]))

    def test_portal_mission_builds_integrated_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = build_portal_mission(
                PortalMissionConfig(
                    profile="melanoma_cutaneous",
                    steps=4,
                    healthy=24,
                    cancer=8,
                    seed=101,
                    max_qsa_candidates=4,
                    max_marker_qubits=6,
                    output_dir=tmp,
                )
            )
            self.assertEqual(mission["payload_version"], PORTAL_PAYLOAD_VERSION)
            self.assertEqual(mission["scope_notice"], SCOPE_NOTICE)
            self.assertEqual(mission["profile"]["id"], "melanoma_cutaneous")
            self.assertTrue(mission["initial_interpretation"]["top_targetable_signals"])
            self.assertTrue(mission["initial_recommendation"]["ranked_cocktails"])
            self.assertTrue(mission["qsa_result"]["ok"])
            self.assertIn("simulation", mission)
            self.assertTrue(Path(mission["simulation"]["experiment_path"]).exists())
            self.assertTrue(Path(mission["mission_path"]).exists())
            self.assertIn("stage_cards", mission)
            self.assertIn("hypothesis_strength_index", mission["hypothesis_index"])

    def test_portal_mission_can_prepare_without_run_or_qsa(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission = build_portal_mission(
                {
                    "profile": "melanoma_cutaneous",
                    "run_simulation": False,
                    "include_qsa": False,
                    "output_dir": tmp,
                }
            )
            self.assertEqual(mission["qsa_result"], {})
            self.assertEqual(mission["simulation"], {})
            self.assertEqual(mission["post_run_interpretation"], {})
            self.assertTrue(Path(mission["mission_path"]).exists())

    def test_portal_session_cli_exports_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "portal_payload.json"
            with redirect_stdout(io.StringIO()) as buf:
                rc = cli_main(
                    [
                        "portal-session",
                        "--profile",
                        "melanoma_cutaneous",
                        "--steps",
                        "3",
                        "--healthy",
                        "20",
                        "--cancer",
                        "6",
                        "--output-dir",
                        tmp,
                        "--json",
                        str(out),
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["payload_version"], PORTAL_PAYLOAD_VERSION)
            self.assertIn("Portal mission", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
