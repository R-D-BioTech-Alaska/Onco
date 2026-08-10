import json
import random
import tempfile
import unittest
from pathlib import Path

from oncoforge.core.constants import ACTIONS, SIGNALS
from oncoforge.core.automation import automation_profile_options, automation_profiles, build_automation_options, run_automated_protocol
from oncoforge.core.experiment_runner import compare_cocktails, export_results_csv, format_results_table
from oncoforge.core.exporter import export_json_report
from oncoforge.core.knowledge import cocktail_coverage, pathway_map_text, validate_agent, validate_cocktail
from oncoforge.core.models import BioAgent, Cell, Cocktail, Microenvironment, SimulationConfig
from oncoforge.core.presets import default_cocktails, load_agents
from oncoforge.core.rule_engine import RuleEngine
from oncoforge.core.simulation import Simulation


class ExtendedFeatureTests(unittest.TestCase):
    def test_new_signal_and_action_vocabulary_present(self):
        self.assertIn("CD47_DONT_EAT_ME", SIGNALS)
        self.assertIn("increase_phagocytosis", ACTIONS)
        self.assertIn("trigger_ferroptosis", ACTIONS)

    def test_all_bundled_agents_validate(self):
        agents = load_agents()
        for agent in agents:
            errors = [x for x in validate_agent(agent) if x.severity == "error"]
            self.assertEqual(errors, [], f"{agent.name}: {errors}")

    def test_cocktail_coverage_and_validation(self):
        cocktail = default_cocktails()[-1]
        self.assertFalse([x for x in validate_cocktail(cocktail) if x.severity == "error"])
        cov = cocktail_coverage(cocktail)
        self.assertGreater(cov["target_coverage"], 0.10)
        self.assertGreater(cov["action_coverage"], 0.10)

    def test_batch_compare_returns_ranked_results_and_exports(self):
        cfg = SimulationConfig(initial_healthy_cells=40, initial_cancer_cells=20, steps=5, random_seed=55)
        results = compare_cocktails(cocktails=default_cocktails()[:2], config=cfg, steps=5, seeds=[55, 56])
        self.assertEqual(len(results), 4)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        table = format_results_table(results)
        self.assertIn("Cocktail", table)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "compare.csv"
            export_results_csv(results, path)
            self.assertIn("cocktail_name", path.read_text(encoding="utf-8"))

    def test_custom_agent_changes_model_state(self):
        agent = BioAgent(
            name="Test phagocytosis gate",
            category="test",
            targets={"CD47_DONT_EAT_ME": 0.1, "STRESS_LIGAND_HIGH": 0.1},
            activation_logic="WEIGHTED",
            actions={"block_cd47": 1.0, "increase_phagocytosis": 1.0},
            specificity=1.0,
            potency=1.0,
            healthy_cell_risk=0.0,
            evidence_level=5,
        )
        sim = Simulation(SimulationConfig(initial_healthy_cells=0, initial_cancer_cells=20, steps=3, random_seed=3), cocktail=Cocktail("test", [agent]))
        sim.reset()
        before = sim.live_cell_counts().get("cancer", 0)
        sim.run(3)
        after = sim.live_cell_counts().get("cancer", 0)
        self.assertLessEqual(after, before + 5)  # population can still proliferate, but should not explode.

    def test_pathway_map_includes_user_concept_channels(self):
        text = pathway_map_text()
        self.assertIn("Macrophage/phagocytosis", text)
        self.assertIn("Tumor microenvironment", text)
        self.assertIn("Explanation:", text)

    def test_repeated_seed_is_reproducible(self):
        cfg = SimulationConfig(initial_healthy_cells=35, initial_cancer_cells=18, steps=8, random_seed=1729)
        cocktail = default_cocktails()[-1]
        first = Simulation(cfg, cocktail=Cocktail.from_dict(cocktail.to_dict()))
        second = Simulation(SimulationConfig.from_dict(cfg.to_dict()), cocktail=Cocktail.from_dict(cocktail.to_dict()))
        first.reset()
        second.reset()
        first.run(8)
        second.run(8)
        self.assertEqual(first.analytics.to_dicts(), second.analytics.to_dicts())
        self.assertEqual([c.to_dict() for c in first.cells], [c.to_dict() for c in second.cells])

    def test_save_load_preserves_rng_for_continuation(self):
        sim = Simulation(SimulationConfig(initial_healthy_cells=20, initial_cancer_cells=10, steps=6, random_seed=99), cocktail=default_cocktails()[2])
        sim.reset()
        sim.run(3)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "saved.json"
            sim.save_experiment(path)
            loaded = Simulation.load_experiment(path)
            sim.run(3)
            loaded.run(3)
            self.assertEqual(sim.analytics.to_dicts(), loaded.analytics.to_dicts())
            self.assertEqual([c.to_dict() for c in sim.cells], [c.to_dict() for c in loaded.cells])

    def test_threshold_activation_and_agent_decay(self):
        agent = BioAgent(
            name="Threshold tester",
            category="test",
            targets={"DNA_DAMAGE_HIGH": 0.5},
            activation_logic="THRESHOLD",
            activation_threshold=0.9,
            actions={"reduce_proliferation": 1.0},
            potency=1.0,
            specificity=1.0,
            decay_rate=0.5,
            healthy_cell_risk=0.0,
            evidence_level=5,
        )
        engine = RuleEngine(random.Random(1))
        cell = Cell(id=1, clone_id="x", cell_kind="cancer", dna_damage=0.1)
        cell.generate_signals()
        self.assertEqual(engine.detection_score(cell, agent, Microenvironment()), 0.0)
        cell.dna_damage = 0.95
        cell.generate_signals()
        self.assertGreater(engine.detection_score(cell, agent, Microenvironment()), 0.0)

        sim = Simulation(SimulationConfig(initial_healthy_cells=0, initial_cancer_cells=1, random_seed=5), cocktail=Cocktail("decay", [agent]))
        sim.reset()
        sim.step()
        self.assertAlmostEqual(sim.cocktail.agents[0].concentration, 0.5)

    def test_json_report_contains_scope_and_curves(self):
        sim = Simulation(SimulationConfig(initial_healthy_cells=10, initial_cancer_cells=5, steps=3, random_seed=11), cocktail=default_cocktails()[0])
        sim.reset()
        sim.run(3)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            export_json_report(sim, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("not medical advice", payload["scope"])
            self.assertIn("tumor_burden_curve", payload)
            self.assertIn("cocktail_scores", payload)
            self.assertIn("metrics_history", payload)

    def test_automated_protocol_exports_complete_run(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_automated_protocol(
                name="test automation",
                preset_name="generic_p53_loss",
                cocktail_name="full_conceptual_swarm",
                steps=4,
                healthy=12,
                cancer=6,
                seed=101,
                output_dir=d,
                compare=False,
            )
            self.assertIn("Cancer cells:", result["summary"])
            paths = result["paths"]
            self.assertTrue(Path(paths["html"]).exists())
            self.assertTrue(Path(paths["json"]).exists())
            self.assertTrue(Path(paths["csv"]).exists())
            self.assertTrue(Path(paths["experiment"]).exists())

    def test_automation_profiles_build_overridable_options(self):
        profiles = automation_profiles()
        self.assertGreaterEqual(len(profiles), 4)
        scout = automation_profile_options("best_cocktail_scout")
        self.assertTrue(scout["auto_select_cocktail"])
        options = build_automation_options("fast_triage", {"steps": 3, "compare": False})
        self.assertEqual(options["steps"], 3)
        self.assertFalse(options["compare"])
        self.assertEqual(options["preset_name"], "Generic p53-loss carcinoma")

    def test_automated_protocol_can_auto_select_cocktail(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_automated_protocol(
                name="selection test",
                preset_name="generic_p53_loss",
                cocktail_name="damage_to_death",
                steps=2,
                healthy=10,
                cancer=5,
                seed=202,
                output_dir=d,
                compare=False,
                compare_seeds=[202],
                auto_select_cocktail=True,
                compare_limit=5,
            )
            self.assertTrue(result["auto_select_cocktail"])
            self.assertIn(result["selected_cocktail"], [c.name for c in default_cocktails()])
            self.assertTrue(result["selection_summary"])
            paths = result["paths"]
            self.assertTrue(Path(paths["selection_csv"]).exists())
            self.assertTrue(Path(paths["selection_json"]).exists())
            self.assertTrue(Path(paths["selection_summary_json"]).exists())
            self.assertNotIn("comparison_json", paths)


if __name__ == "__main__":
    unittest.main()
