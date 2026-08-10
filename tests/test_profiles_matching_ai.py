import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from oncoforge.cli import main as cli_main
from oncoforge.core.cancer_profiles import create_profile_simulation, load_cancer_profiles
from oncoforge.core.local_ai import LocalAIConfig, SYSTEM_PROMPT, ask_local_ai, check_local_ai_available
from oncoforge.core.research_loop import ResearchLoopConfig, run_research_loop
from oncoforge.core.signal_interpreter import analyze_signals
from oncoforge.core.treatment_matcher import recommend_treatments


class ProfileMatchingAITests(unittest.TestCase):
    def test_profile_data_loads_and_is_valid(self):
        profiles = load_cancer_profiles()
        self.assertGreaterEqual(len(profiles), 16)
        ids = [profile.id for profile in profiles]
        self.assertEqual(len(ids), len(set(ids)))
        for profile in profiles:
            self.assertTrue(profile.display_name)
            self.assertTrue(profile.default_signal_biases)
            for value in profile.default_signal_biases.values():
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_profile_generated_cells_express_expected_markers_with_heterogeneity(self):
        sim = create_profile_simulation("melanoma_cutaneous", healthy=30, cancer=20, seed=44, profile_heterogeneity=0.20)
        cancer = [cell for cell in sim.cells if cell.alive and cell.cell_kind == "cancer"]
        self.assertEqual(len(cancer), 20)
        neo = [cell.signals["NEOANTIGEN_PRESENT"] for cell in cancer]
        self.assertGreater(sum(neo) / len(neo), 0.55)
        self.assertGreater(max(neo) - min(neo), 0.01)
        for cell in cancer:
            for value in cell.signals.values():
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_signal_interpreter_structure_and_zero_cancer_fallback(self):
        sim = create_profile_simulation("melanoma_cutaneous", healthy=30, cancer=15, seed=45)
        result = analyze_signals(sim)
        self.assertIn("top_targetable_signals", result)
        self.assertIn("recommended_cocktails", result)
        names = [row["signal"] for row in result["top_targetable_signals"][:8]]
        self.assertIn("NEOANTIGEN_PRESENT", names)
        for cell in sim.cells:
            if cell.cell_kind == "cancer":
                cell.alive = False
                cell.cell_kind = "dead"
        fallback = analyze_signals(sim)
        self.assertTrue(fallback["used_fallback_snapshot"])
        self.assertIn("last saved cancer-signal snapshot", fallback["plain_english_summary"])

    def test_signal_interpreter_no_cancer_no_snapshot_message(self):
        sim = create_profile_simulation("melanoma_cutaneous", healthy=20, cancer=0, seed=46)
        sim.marker_snapshots = {}
        result = analyze_signals(sim)
        self.assertIn("No living cancer cells", result["plain_english_summary"])

    def test_treatment_matcher_returns_reasoned_rankings_and_avoid_list(self):
        sim = create_profile_simulation("pancreatic_stromal_barrier", healthy=40, cancer=20, seed=47)
        result = recommend_treatments(sim=sim)
        self.assertIn("ranked_cocktails", result)
        self.assertTrue(result["ranked_cocktails"])
        self.assertIn("reason", result["ranked_cocktails"][0])
        full = [row for row in result["ranked_cocktails"] if row["cocktail_name"] == "Full conceptual swarm"][0]
        narrow = [row for row in result["ranked_cocktails"] if row["cocktail_name"] == "Stromal access microenvironment set"][0]
        self.assertGreaterEqual(full["broadness_penalty"], narrow["broadness_penalty"])
        self.assertIn("avoid_or_gate_agents", result)

    def test_local_ai_disabled_and_connection_failure_are_graceful(self):
        cfg = LocalAIConfig(enabled=False)
        disabled = ask_local_ai(cfg, {"hello": "world"})
        self.assertFalse(disabled["ok"])
        self.assertIn("disabled", disabled["message"].lower())
        self.assertIn("must not provide medical advice", SYSTEM_PROMPT)
        cfg = LocalAIConfig(enabled=True, base_url="http://127.0.0.1:9", provider="ollama")
        unavailable = check_local_ai_available(cfg)
        self.assertFalse(unavailable["available"])
        self.assertIn("not available", unavailable["message"])

    def test_research_loop_respects_max_experiment_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ResearchLoopConfig(
                profile="melanoma_cutaneous",
                max_auto_experiments=2,
                max_steps_per_experiment=3,
                healthy=20,
                cancer=8,
                output_dir=tmp,
                require_user_confirmation_before_start=True,
            )
            blocked = run_research_loop(cfg, confirmed=False)
            self.assertFalse(blocked["ok"])
            result = run_research_loop(cfg, confirmed=True)
            self.assertTrue(result["ok"])
            self.assertLessEqual(result["experiments_run"], 2)
            self.assertTrue(Path(result["summary_path"]).exists())

    def test_profile_cli_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "profile_run.html"
            saved = Path(tmp) / "profile_experiment.json"
            commands = [
                ["list-profiles"],
                ["profile-info", "--profile", "melanoma_cutaneous"],
                ["recommend-cocktail", "--profile", "melanoma_cutaneous"],
                [
                    "run-profile",
                    "--profile", "melanoma_cutaneous",
                    "--cocktail", "NK stress-response swarm",
                    "--steps", "3",
                    "--healthy", "20",
                    "--cancer", "8",
                    "--export", str(out),
                    "--save-experiment", str(saved),
                ],
                ["interpret-signals", "--experiment", str(saved)],
            ]
            for command in commands:
                with redirect_stdout(io.StringIO()):
                    rc = cli_main(command)
                self.assertEqual(rc, 0, command)
            self.assertTrue(out.exists())
            self.assertTrue(saved.exists())
            with redirect_stdout(io.StringIO()):
                ai_rc = cli_main(["ai-test", "--provider", "ollama", "--base-url", "http://127.0.0.1:9", "--model", "none"])
            self.assertIn(ai_rc, {0, 1})


if __name__ == "__main__":
    unittest.main()
