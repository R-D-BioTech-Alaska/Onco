import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from oncoforge.cli import main as cli_main
from oncoforge.core.quantum_strategy import (
    QUANTUM_SCOPE_NOTICE,
    QuantumWorkloadLimits,
    build_quantum_search_request,
    run_quantum_strategy,
    validate_quantum_request,
)


class QuantumStrategyTests(unittest.TestCase):
    def test_quantum_request_is_bounded_and_caveated(self):
        limits = QuantumWorkloadLimits(max_candidates=3, max_marker_qubits=5, max_component_states=100)
        request = build_quantum_search_request(profile="melanoma_cutaneous", limits=limits)
        self.assertEqual(request.scope_notice, QUANTUM_SCOPE_NOTICE)
        self.assertLessEqual(len(request.candidates), 3)
        self.assertLessEqual(len(request.marker_qubits), 5)
        self.assertFalse(validate_quantum_request(request))

    def test_structural_fallback_ranks_candidates(self):
        request = build_quantum_search_request(profile="melanoma_cutaneous", limits={"max_candidates": 5})
        result = run_quantum_strategy(request)
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "deterministic_structural_fallback")
        ranked = result["ranked_candidates"]
        self.assertTrue(ranked)
        scores = [row["structural_score"] for row in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("not medical advice", result["scope_notice"])

    def test_component_limit_rejects_oversized_request(self):
        request = build_quantum_search_request(
            profile="melanoma_cutaneous",
            limits={"max_candidates": 4, "max_marker_qubits": 4, "max_component_states": 3},
        )
        result = run_quantum_strategy(request)
        self.assertFalse(result["ok"])
        self.assertIn("component count", " ".join(result["errors"]))

    def test_backend_contract_failure_is_clear(self):
        request = build_quantum_search_request(profile="melanoma_cutaneous", limits={"max_candidates": 2})
        result = run_quantum_strategy(request, backend=object())
        self.assertFalse(result["ok"])
        self.assertIn("adapter", result["message"].lower())

    def test_qsa_plan_cli_exports_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "qsa_plan.json"
            with redirect_stdout(io.StringIO()) as buf:
                rc = cli_main(
                    [
                        "qsa-plan",
                        "--profile",
                        "melanoma_cutaneous",
                        "--max-candidates",
                        "3",
                        "--max-marker-qubits",
                        "5",
                        "--json",
                        str(out),
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("request", payload)
            self.assertIn("result", payload)
            self.assertIn("Best structural candidate", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
