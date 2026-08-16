import json
import unittest
from pathlib import Path

from oncoforge.core.evidence import EvidenceFabric, load_evidence_fabric
from oncoforge.core.onco_qsa import run_logic_gate_qsa
from oncoforge.core.target_forge import TargetForgeConfig, run_target_forge


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "target_forge_synthetic.json"


class TargetForgeTests(unittest.TestCase):
    def test_unknown_config_and_string_boolean_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown Target Forge config fields"):
            TargetForgeConfig.from_dict({"magic_score": 1.0})
        with self.assertRaisesRegex(ValueError, "use_qsa must be true or false"):
            TargetForgeConfig.from_dict({"use_qsa": "false"})
        with self.assertRaisesRegex(ValueError, "requires allow_transcript_fallback"):
            TargetForgeConfig.from_dict({"feature_order": ["transcript_abundance"]})

    def test_normal_tissue_is_a_hard_gate(self):
        report = run_target_forge(load_evidence_fabric(FIXTURE), {"use_qsa": False})
        rows = {row["expression"]: row for row in report["gate_candidates"]}

        unsafe = rows["FIXTURE:SURFACE_A"]
        exclusion = rows["FIXTURE:SURFACE_A AND NOT FIXTURE:SURFACE_C"]
        self.assertFalse(unsafe["eligible"])
        self.assertGreater(unsafe["critical_normal_activation"], 0.0)
        self.assertTrue(exclusion["eligible"])
        self.assertEqual(exclusion["tumor_coverage"], 1.0)
        self.assertEqual(exclusion["normal_activation"], 0.0)

    def test_missing_critical_normal_measurement_fails_closed(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["assertions"] = [
            row for row in payload["assertions"] if row["assertion_id"] != "FIXTURE:OBS_N1_C"
        ]
        report = run_target_forge(EvidenceFabric.from_dict(payload), {"use_qsa": False})
        row = next(
            item
            for item in report["gate_candidates"]
            if item["expression"] == "FIXTURE:SURFACE_A AND NOT FIXTURE:SURFACE_C"
        )

        self.assertFalse(row["eligible"])
        self.assertEqual(row["unknown_critical_normal_count"], 1)
        self.assertTrue(any("critical-normal" in reason for reason in row["rejection_reasons"]))

    def test_pareto_candidates_are_not_dominated(self):
        report = run_target_forge(load_evidence_fabric(FIXTURE), {"use_qsa": False})
        marked = set(report["pareto_candidate_ids"])

        self.assertEqual(len(marked), 2)
        self.assertTrue(marked)
        self.assertTrue(all(row["eligible"] for row in report["gate_candidates"] if row["candidate_id"] in marked))

    def test_target_preselection_reserves_normal_exclusion_sensor(self):
        report = run_target_forge(
            load_evidence_fabric(FIXTURE),
            {"max_targets": 2, "use_qsa": False},
        )

        self.assertEqual(
            report["target_selection"]["selected_target_ids"],
            ["FIXTURE:SURFACE_A", "FIXTURE:SURFACE_C"],
        )
        self.assertTrue(
            any(
                row["title"] == "Evaluate surface gate: FIXTURE:SURFACE_A AND NOT FIXTURE:SURFACE_C"
                for row in report["hypotheses"]
            )
        )

    def test_missing_critical_normal_cohort_rejects_all_candidates(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for entity in payload["entities"]:
            if entity.get("kind") == "Sample" and entity.get("attributes", {}).get("role") == "normal":
                entity["attributes"]["critical_normal"] = False
        report = run_target_forge(EvidenceFabric.from_dict(payload), {"use_qsa": False})

        self.assertTrue(report["gate_candidates"])
        self.assertFalse(any(row["eligible"] for row in report["gate_candidates"]))
        self.assertTrue(
            all(
                "no critical-normal samples are defined" in row["rejection_reasons"]
                for row in report["gate_candidates"]
            )
        )

    def test_missing_clone_identity_is_not_counted_as_clone_coverage(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        tumor = next(entity for entity in payload["entities"] if entity["entity_id"] == "FIXTURE:TUMOR_1")
        tumor["attributes"]["clone_id"] = ""
        report = run_target_forge(EvidenceFabric.from_dict(payload), {"use_qsa": False})

        self.assertFalse(any(row["eligible"] for row in report["gate_candidates"]))
        self.assertTrue(
            all(row["unknown_clone_fraction"] > 0.0 for row in report["gate_candidates"])
        )

    def test_qsa_matches_analytic_control(self):
        receipt = run_logic_gate_qsa(
            problem_id="TEST:LOGIC_GATE",
            problem_hash="a" * 64,
            candidate_ids=["A", "B", "C", "D", "E"],
            marked_candidate_ids=["A", "C"],
            classical_elapsed_ms=0.0,
        )

        if receipt["status"] == "classical_fallback":
            self.skipTest(receipt.get("failure", "QSA runtime unavailable"))
        self.assertEqual(receipt["status"], "executed_exact")
        self.assertTrue(receipt["representation_certificate"]["eligible"])
        self.assertTrue(receipt["execution"]["analytic_match"])
        self.assertLessEqual(receipt["execution"]["absolute_error"], 1e-12)
        self.assertIn("No computational advantage", receipt["advantage_assessment"])

    def test_report_scientific_hash_is_reproducible(self):
        config = TargetForgeConfig(use_qsa=True)
        first = run_target_forge(load_evidence_fabric(FIXTURE), config)
        second = run_target_forge(load_evidence_fabric(FIXTURE), config)

        self.assertEqual(first["report_hash"], second["report_hash"])
        self.assertEqual(
            [row["provenance"] for row in first["hypotheses"]],
            [row["provenance"] for row in second["hypotheses"]],
        )
        self.assertEqual(first["evidence_summary"]["evidence_classes"], {"synthetic_fixture": 18})
        self.assertFalse(first["evidence_categories"]["MEASURED"])
        self.assertEqual(len(first["evidence_categories"]["SIMULATED"]), 18)


if __name__ == "__main__":
    unittest.main()
