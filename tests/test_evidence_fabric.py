import json
import unittest
from pathlib import Path

from oncoforge.core.evidence import EvidenceFabric, load_evidence_fabric
from oncoforge.core.tumor_model import TumorResearchModel


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "target_forge_synthetic.json"


class EvidenceFabricTests(unittest.TestCase):
    def test_fixture_builds_typed_tumor_model(self):
        fabric = load_evidence_fabric(FIXTURE)
        model = TumorResearchModel.from_evidence(fabric)

        self.assertEqual(model.origin, "synthetic_fixture")
        self.assertEqual(len(model.samples_by_role("tumor")), 3)
        self.assertEqual(len(model.samples_by_role("normal")), 3)
        self.assertEqual(len(model.measurements), 18)
        self.assertEqual(fabric.summary()["evidence_classes"], {"synthetic_fixture": 18})

    def test_assertion_provenance_rejects_tampering(self):
        fabric = load_evidence_fabric(FIXTURE)
        payload = fabric.to_dict()
        payload.pop("fabric_hash")
        payload["assertions"][0]["value"]["value"] = 999.0

        with self.assertRaisesRegex(ValueError, "provenance hash"):
            EvidenceFabric.from_dict(payload)

    def test_unknown_entity_reference_fails_closed(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["assertions"][0]["object_id"] = "FIXTURE:MISSING_TARGET"

        with self.assertRaisesRegex(ValueError, "unknown object"):
            EvidenceFabric.from_dict(payload)

    def test_nonidentical_duplicate_measurements_require_normalization(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        duplicate = dict(payload["assertions"][0])
        duplicate["assertion_id"] = "FIXTURE:OBS_T1_A_SECOND_ASSAY"
        duplicate["value"] = dict(duplicate["value"])
        duplicate["value"]["value"] = 7.0
        payload["assertions"].append(duplicate)
        model = TumorResearchModel.from_evidence(EvidenceFabric.from_dict(payload))

        with self.assertRaisesRegex(ValueError, "normalize or select one assay"):
            model.preferred_measurement(
                "FIXTURE:TUMOR_1",
                "FIXTURE:SURFACE_A",
                ["surface_abundance"],
            )

    def test_unknown_evidence_field_is_not_silently_ignored(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["assertions"][0]["confidence_score"] = 0.99

        with self.assertRaisesRegex(ValueError, "unknown fields: confidence_score"):
            EvidenceFabric.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
