import tempfile
import unittest
from pathlib import Path

from oncoforge.core.models import SimulationConfig
from oncoforge.core.presets import load_agents, load_cancer_presets, default_cocktails
from oncoforge.core.simulation import Simulation
from oncoforge.core.exporter import export_html_report


class EngineTests(unittest.TestCase):
    def test_agents_load(self):
        agents = load_agents()
        self.assertGreaterEqual(len(agents), 15)
        self.assertTrue(all(a.targets for a in agents))
        self.assertTrue(all(a.actions for a in agents))

    def test_presets_load(self):
        presets = load_cancer_presets()
        self.assertGreaterEqual(len(presets), 4)
        self.assertTrue(all("traits" in p for p in presets))

    def test_simulation_runs_and_records_metrics(self):
        cocktails = default_cocktails()
        sim = Simulation(SimulationConfig(initial_healthy_cells=50, initial_cancer_cells=25, steps=10, random_seed=123), cocktail=cocktails[-1])
        sim.reset()
        sim.run(10)
        self.assertEqual(sim.step_index, 10)
        self.assertEqual(len(sim.analytics.history), 11)
        latest = sim.analytics.latest()
        self.assertIsNotNone(latest)
        self.assertGreater(latest.healthy_alive + latest.cancer_alive + latest.dead_cells, 0)

    def test_save_load_round_trip(self):
        sim = Simulation(SimulationConfig(initial_healthy_cells=10, initial_cancer_cells=5, steps=3, random_seed=7), cocktail=default_cocktails()[0])
        sim.reset()
        sim.run(3)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "experiment.json"
            sim.save_experiment(path)
            loaded = Simulation.load_experiment(path)
            self.assertEqual(loaded.step_index, sim.step_index)
            self.assertEqual(len(loaded.cells), len(sim.cells))
            self.assertEqual(loaded.cocktail.name, sim.cocktail.name)

    def test_report_export(self):
        sim = Simulation(SimulationConfig(initial_healthy_cells=10, initial_cancer_cells=5, steps=3, random_seed=9), cocktail=default_cocktails()[1])
        sim.reset()
        sim.run(3)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.html"
            export_html_report(sim, path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("OncoForge Experiment Report", text)
            self.assertIn(sim.cocktail.name, text)


if __name__ == "__main__":
    unittest.main()
