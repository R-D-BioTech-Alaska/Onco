import io
import json
import tempfile
from contextlib import redirect_stdout
import unittest
from pathlib import Path

from oncoforge.core.exporter import build_report_payload
from oncoforge.core.interpretation import assess_cure_pathway, interpret_latest
from oncoforge.core.models import SimulationConfig
from oncoforge.core.presets import default_cocktails
from oncoforge.core.simulation import Simulation
from oncoforge.cli import main as cli_main


class AdaptiveDosingTests(unittest.TestCase):
    def test_immediate_zero_cancer_enters_confirmation_not_shutoff(self):
        cfg = SimulationConfig(
            initial_healthy_cells=40,
            initial_cancer_cells=0,
            random_seed=101,
            adaptive_dosing_enabled=True,
            auto_shutoff_enabled=True,
            remission_surveillance_enabled=True,
            zero_cancer_confirmation_steps=5,
        )
        sim = Simulation(cfg, cocktail=default_cocktails()[-1])
        sim.reset()
        sim.step()
        latest = sim.analytics.latest()
        self.assertEqual(latest.cancer_alive, 0)
        self.assertEqual(latest.dosing_phase, "remission_confirmation")
        self.assertEqual(latest.zero_cancer_steps, 1)
        self.assertGreater(latest.treatment_intensity, 0.0)
        self.assertAlmostEqual(latest.treatment_intensity, cfg.remission_surveillance_intensity)

    def test_auto_shutoff_waits_for_confirmation_window(self):
        cfg = SimulationConfig(
            initial_healthy_cells=40,
            initial_cancer_cells=0,
            random_seed=102,
            adaptive_dosing_enabled=True,
            auto_shutoff_enabled=True,
            remission_surveillance_enabled=False,
            zero_cancer_confirmation_steps=3,
        )
        sim = Simulation(cfg, cocktail=default_cocktails()[-1])
        sim.reset()
        sim.run(2)
        latest = sim.analytics.latest()
        self.assertEqual(latest.dosing_phase, "remission_confirmation")
        self.assertGreater(latest.treatment_intensity, 0.0)
        sim.step()
        latest = sim.analytics.latest()
        self.assertEqual(latest.dosing_phase, "post_clearance_shutoff")
        self.assertEqual(latest.treatment_intensity, 0.0)

    def test_recurrence_restores_active_treatment(self):
        cfg = SimulationConfig(
            initial_healthy_cells=40,
            initial_cancer_cells=0,
            random_seed=104,
            adaptive_dosing_enabled=True,
            auto_shutoff_enabled=True,
            remission_surveillance_enabled=False,
            zero_cancer_confirmation_steps=1,
        )
        sim = Simulation(cfg, cocktail=default_cocktails()[-1])
        sim.reset()
        sim.step()
        self.assertEqual(sim.dosing_state.phase, "post_clearance_shutoff")
        sim.cells.append(sim._new_cancer_cell("rebound_clone"))
        sim._update_dosing_state()
        self.assertTrue(sim.dosing_state.recurrence_after_clearance)
        self.assertEqual(sim.dosing_state.max_cancer_after_clearance, 1)
        self.assertGreaterEqual(sim.dosing_state.rebound_step, 1)
        self.assertNotEqual(sim.dosing_state.phase, "post_clearance_shutoff")
        self.assertGreater(sim.dosing_state.intensity, 0.0)

    def test_adaptive_confirmation_reduces_post_clearance_damage_without_rebound(self):
        full_cfg = SimulationConfig(
            initial_healthy_cells=120,
            initial_cancer_cells=0,
            random_seed=105,
            treatment_strength_multiplier=2.0,
            adaptive_dosing_enabled=False,
        )
        adaptive_cfg = SimulationConfig(
            initial_healthy_cells=120,
            initial_cancer_cells=0,
            random_seed=105,
            treatment_strength_multiplier=2.0,
            adaptive_dosing_enabled=True,
            auto_shutoff_enabled=True,
            remission_surveillance_enabled=False,
            remission_surveillance_intensity=0.25,
            zero_cancer_confirmation_steps=3,
        )
        full = Simulation(full_cfg, cocktail=default_cocktails()[-1])
        adaptive = Simulation(adaptive_cfg, cocktail=default_cocktails()[-1])
        full.reset()
        adaptive.reset()
        full.run(25)
        adaptive.run(25)
        full_damage = sum(row.healthy_damage_events for row in full.analytics.history[1:])
        adaptive_damage = sum(row.healthy_damage_events for row in adaptive.analytics.history[1:])
        self.assertLess(adaptive_damage, full_damage)
        self.assertFalse(adaptive.dosing_state.recurrence_after_clearance)

    def test_cure_pathway_assessment_and_report_payload(self):
        cfg = SimulationConfig(
            initial_healthy_cells=30,
            initial_cancer_cells=0,
            random_seed=103,
            adaptive_dosing_enabled=True,
            auto_shutoff_enabled=True,
            remission_surveillance_enabled=False,
            zero_cancer_confirmation_steps=3,
        )
        sim = Simulation(cfg, cocktail=default_cocktails()[0])
        sim.reset()
        sim.run(30)
        assessment = assess_cure_pathway(sim)
        self.assertTrue(assessment.cleared)
        self.assertGreaterEqual(assessment.post_clearance_steps, 20)
        self.assertIn("Cancer", interpret_latest(sim))
        payload = build_report_payload(sim)
        self.assertIn("cure_pathway_assessment", payload)
        self.assertIn("readable_interpretation", payload)
        self.assertIn("dosing_state", payload)
        self.assertIn("remission_controller", payload)
        self.assertIn("dosing_phase_history", payload)
        self.assertGreaterEqual(payload["remission_controller"]["zero_cancer_confirmation_steps_observed"], 3)

    def test_cli_sweep_exports_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sweep.json"
            with redirect_stdout(io.StringIO()):
                rc = cli_main([
                    "sweep",
                    "--parameter", "treatment",
                    "--values", "0.5,1.0",
                    "--steps", "5",
                    "--healthy", "20",
                    "--cancer", "5",
                    "--json", str(out),
                    "--adaptive-dosing",
                    "--auto-shutoff",
                    "--zero-confirmation-steps", "3",
                ])
            self.assertEqual(rc, 0)
            rows = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 2)
            self.assertIn("cure_pathway_score", rows[0])

    def test_cli_remission_test_exports_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "remission.json"
            with redirect_stdout(io.StringIO()):
                rc = cli_main([
                    "remission-test",
                    "--steps", "5",
                    "--healthy", "20",
                    "--cancer", "0",
                    "--export", str(out),
                    "--no-remission-surveillance",
                    "--zero-confirmation-steps", "3",
                ])
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("cure_pathway_assessment", payload)
            self.assertIn("remission_controller", payload)
            self.assertEqual(payload["final_metrics"]["cancer_alive"], 0)


if __name__ == "__main__":
    unittest.main()
