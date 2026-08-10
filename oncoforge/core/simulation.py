"""Main simulation engine."""

from __future__ import annotations

import json
import random
from dataclasses import fields
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .analytics import AnalyticsRecorder
from .constants import SIGNALS
from .models import Cell, BioAgent, Cocktail, DosingState, Microenvironment, PathwayState, SimulationConfig
from .rule_engine import RuleEngine
from .utils import clamp, event, noisy


def _json_to_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_json_to_tuple(item) for item in value)
    return value


class Simulation:
    """Agent-based conceptual cancer/protein interaction simulator."""

    def __init__(
        self,
        config: Optional[SimulationConfig] = None,
        microenvironment: Optional[Microenvironment] = None,
        cocktail: Optional[Cocktail] = None,
    ) -> None:
        self.config = config or SimulationConfig()
        self.microenvironment = microenvironment or Microenvironment()
        self.cocktail = cocktail or Cocktail("No active cocktail")
        self.rng = random.Random(self.config.random_seed)
        self.rule_engine = RuleEngine(self.rng)
        self.analytics = AnalyticsRecorder()
        self.cells: List[Cell] = []
        self.step_index = 0
        self._next_id = 1
        self.dosing_state = DosingState()
        self._last_step_stats: Dict[str, int] = {}
        self.cancer_profile: Dict[str, Any] = {}
        self.marker_snapshots: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        self.rng = random.Random(int(self.config.random_seed))
        self.rule_engine = RuleEngine(self.rng)
        self.analytics.clear()
        self.cells = []
        self.step_index = 0
        self._next_id = 1
        self.dosing_state = DosingState()
        self.marker_snapshots = {}
        self._seed_population()
        self.capture_marker_snapshot("initial")
        self._record_zero()

    def _seed_population(self) -> None:
        for _ in range(int(self.config.initial_healthy_cells)):
            self.cells.append(self._new_healthy_cell())
        for _ in range(int(self.config.initial_cancer_cells)):
            self.cells.append(self._new_cancer_cell("founder_clone"))

    def _position(self) -> Tuple[float, float]:
        return (
            self.rng.uniform(0, self.config.width),
            self.rng.uniform(0, self.config.height),
        )

    def _new_healthy_cell(self) -> Cell:
        c = Cell(
            id=self._next_id,
            clone_id="healthy",
            cell_kind="healthy",
            tissue_type="generic",
            position=self._position(),
            genome_instability=self.rng.uniform(0.005, 0.04),
            mutation_burden=self.rng.uniform(0.000, 0.03),
            dna_damage=self.rng.uniform(0.005, 0.05),
            repair_capacity=self.rng.uniform(0.85, 1.0),
            proliferation_rate=self.rng.uniform(0.01, 0.06),
            apoptosis_sensitivity=self.rng.uniform(0.65, 0.90),
            apoptosis_resistance=self.rng.uniform(0.00, 0.08),
            senescence_probability=self.rng.uniform(0.01, 0.05),
            telomerase_activity=self.rng.uniform(0.00, 0.08),
            invasion_potential=self.rng.uniform(0.00, 0.02),
            mhc_expression=self.rng.uniform(0.75, 1.00),
            neoantigen_load=self.rng.uniform(0.00, 0.05),
            stress_ligand_expression=self.rng.uniform(0.00, 0.06),
            pd_l1_expression=self.rng.uniform(0.00, 0.05),
            immune_suppression_output=self.rng.uniform(0.00, 0.04),
            oxygen_need=self.rng.uniform(0.25, 0.45),
            glucose_need=self.rng.uniform(0.25, 0.45),
            lactate_output=self.rng.uniform(0.00, 0.06),
            hypoxia_tolerance=self.rng.uniform(0.05, 0.25),
        )
        self._next_id += 1
        c.generate_signals(self.microenvironment.oxygen)
        return c

    def _new_cancer_cell(self, clone_id: str = "founder_clone") -> Cell:
        p53_active = self.rng.choice([0.0, 0.1, 0.35, 0.65])
        rb_active = self.rng.choice([0.2, 0.4, 0.8])
        mmr_active = self.rng.choice([0.25, 0.65, 0.9])
        brca_active = self.rng.choice([0.35, 0.75, 0.95])
        c = Cell(
            id=self._next_id,
            clone_id=clone_id,
            cell_kind="cancer",
            tissue_type="generic_carcinoma",
            position=self._position(),
            genome_instability=self.rng.uniform(0.35, 0.85),
            mutation_burden=self.rng.uniform(0.30, 0.90),
            dna_damage=self.rng.uniform(0.25, 0.85),
            repair_capacity=self.rng.uniform(0.10, 0.65),
            proliferation_rate=self.rng.uniform(0.35, 0.90),
            apoptosis_sensitivity=self.rng.uniform(0.15, 0.55),
            apoptosis_resistance=self.rng.uniform(0.35, 0.90),
            senescence_probability=self.rng.uniform(0.00, 0.12),
            telomerase_activity=self.rng.uniform(0.35, 0.95),
            invasion_potential=self.rng.uniform(0.05, 0.60),
            mhc_expression=self.rng.uniform(0.15, 0.75),
            neoantigen_load=self.rng.uniform(0.20, 0.95),
            stress_ligand_expression=self.rng.uniform(0.15, 0.80),
            pd_l1_expression=self.rng.uniform(0.05, 0.75),
            immune_suppression_output=self.rng.uniform(0.10, 0.75),
            oxygen_need=self.rng.uniform(0.35, 0.75),
            glucose_need=self.rng.uniform(0.40, 0.85),
            lactate_output=self.rng.uniform(0.25, 0.80),
            hypoxia_tolerance=self.rng.uniform(0.35, 0.90),
            pathways=PathwayState(
                p53_active=p53_active,
                rb_active=rb_active,
                atm_atr_active=self.rng.uniform(0.35, 0.95),
                mmr_active=mmr_active,
                brca_active=brca_active,
                caspase_accessible=self.rng.uniform(0.10, 0.75),
                apoptosis_blockade=self.rng.uniform(0.15, 0.75),
                checkpoint_strength=self.rng.uniform(0.05, 0.55),
            ),
            surface_markers={
                "EGFR_LIKE": self.rng.uniform(0.0, 1.0),
                "HER2_LIKE": self.rng.uniform(0.0, 1.0),
                "MUCIN_ABNORMAL": self.rng.uniform(0.1, 1.0),
                "TUMOR_PROTEASE_ACTIVITY": self.rng.uniform(0.15, 1.0),
                "CD47_LIKE": self.rng.uniform(0.10, 0.95),
                "COMPLEMENT_BINDING_LIKE": self.rng.uniform(0.05, 0.80),
            },
        )
        self._next_id += 1
        c.generate_signals(self.microenvironment.oxygen)
        return c

    def set_cancer_preset(self, preset: Dict[str, Any]) -> None:
        """Apply a cancer preset to all current/future cancer cells."""
        self.config.cancer_preset_name = str(preset.get("name", ""))
        # This function adjusts existing founder cells; new cells inherit by cloning.
        for cell in self.cells:
            if cell.cell_kind == "cancer":
                self._apply_preset_to_cell(cell, preset)

    def _apply_preset_to_cell(self, cell: Cell, preset: Dict[str, Any]) -> None:
        traits = preset.get("traits", {})
        pathways = preset.get("pathways", {})
        markers = preset.get("surface_markers", {})
        for key, value in traits.items():
            if hasattr(cell, key):
                setattr(cell, key, clamp(float(value)))
        for key, value in pathways.items():
            if hasattr(cell.pathways, key):
                setattr(cell.pathways, key, clamp(float(value)))
        for key, value in markers.items():
            cell.surface_markers[key] = clamp(float(value))
        cell.tissue_type = preset.get("tissue_type", cell.tissue_type)
        cell.generate_signals(self.microenvironment.oxygen)

    def _record_zero(self) -> None:
        self._update_dosing_state()
        self.analytics.record(
            0,
            self.cells,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            self.microenvironment,
            self.cocktail.agents,
            self.dosing_state,
        )

    def step(self) -> Dict[str, int]:
        if not self.cells:
            self.reset()

        stats = {
            "treatment_hits": 0,
            "immune_kills": 0,
            "apoptosis_events": 0,
            "senescence_events": 0,
            "proliferation_events": 0,
            "escape_clone_events": 0,
            "healthy_damage_events": 0,
        }

        self.step_index += 1
        self._update_microenvironment()
        self._update_dosing_state()

        # Internal cell aging, damage, repair, mutation, signal generation.
        living_cells = [c for c in self.cells if c.alive]
        for cell in living_cells:
            self._update_cell_baseline(cell, stats)
            cell.generate_signals(self.microenvironment.oxygen)

        # Apply synthetic/natural cocktail agents. Adaptive dosing changes dose, not the
        # agent definitions. In remission phases broad damaging agents can be paused.
        effective_treatment_multiplier = self.config.treatment_strength_multiplier * self.dosing_state.intensity
        for agent in self.cocktail.agents:
            if not self._agent_active_for_current_phase(agent):
                continue
            for cell in list(self.cells):
                if not cell.alive:
                    continue
                before_alive = cell.alive
                effects = self.rule_engine.apply_agent(
                    cell,
                    agent,
                    self.microenvironment,
                    treatment_multiplier=effective_treatment_multiplier,
                )
                for eff in effects:
                    if eff.occurred:
                        stats["treatment_hits"] += 1
                        if eff.healthy_damage:
                            stats["healthy_damage_events"] += 1
                if before_alive and not cell.alive:
                    if any(e.action_name in {"increase_nk_kill", "increase_tcell_kill"} and e.occurred for e in effects):
                        stats["immune_kills"] += 1
                    else:
                        stats["apoptosis_events"] += 1

        # Natural immune surveillance and cell fates.
        for cell in list(self.cells):
            if not cell.alive:
                continue
            self._natural_immune_surveillance(cell, stats)
            if not cell.alive:
                continue
            self._natural_apoptosis_or_senescence(cell, stats)
            if not cell.alive:
                continue

        # Proliferate after deaths to avoid newly created cells acting same step.
        if self.config.allow_proliferation:
            newborns = []
            alive_count = sum(1 for c in self.cells if c.alive)
            for cell in list(self.cells):
                if cell.alive:
                    child = self._maybe_proliferate(cell, stats, alive_count)
                    if child:
                        newborns.append(child)
            self.cells.extend(newborns)

        # Keep population manageable while preserving dynamics.
        self._population_pressure()
        self._decay_agents()
        self._apply_recovery_pressure()
        self._update_dosing_state()
        self.analytics.record(
            self.step_index,
            self.cells,
            **stats,
            microenvironment=self.microenvironment,
            agents=self.cocktail.agents,
            dosing_state=self.dosing_state,
        )
        self.capture_marker_snapshot("latest")
        latest = self.analytics.latest()
        if latest and latest.cancer_alive <= 0 and latest.precancerous_alive <= 0 and "clearance" not in self.marker_snapshots:
            self.marker_snapshots["clearance"] = dict(self.marker_snapshots.get("last_living_cancer", {}))
        self._last_step_stats = stats
        return stats

    def run(self, steps: Optional[int] = None) -> None:
        if not self.cells:
            self.reset()
        n = int(steps if steps is not None else self.config.steps)
        for _ in range(n):
            self.step()

    def _completed_zero_cancer_steps(self) -> int:
        """Return completed recorded steps with no cancer/precancer in a row."""
        streak = 0
        for snapshot in reversed(self.analytics.history):
            if snapshot.step <= 0:
                continue
            if snapshot.cancer_alive <= 0 and snapshot.precancerous_alive <= 0:
                streak += 1
                continue
            break
        return streak

    def _update_dosing_state(self) -> DosingState:
        """Update the conceptual dosing controller.

        Adaptive dosing is designed to remove one common modeling artifact: a
        broad cocktail continuing to injure healthy cells after cancer has been
        cleared. The controller is intentionally transparent and deterministic.
        """
        counts = self.live_cell_counts()
        cancer_count = counts.get("cancer", 0) + counts.get("precancerous", 0)
        previous_state = self.dosing_state
        clearance_step = previous_state.clearance_step
        latest = self.analytics.latest()
        completed_zero_steps = self._completed_zero_cancer_steps()
        zero_cancer_steps = 0
        if cancer_count == 0 and clearance_step < 0 and self.step_index > 0:
            clearance_step = self.step_index
        if cancer_count == 0 and clearance_step >= 0:
            if latest and latest.step == self.step_index and latest.cancer_alive <= 0 and latest.precancerous_alive <= 0:
                zero_cancer_steps = completed_zero_steps
            else:
                zero_cancer_steps = completed_zero_steps + (1 if self.step_index > 0 else 0)
        post_clearance = zero_cancer_steps if clearance_step >= 0 else 0

        recurrence_after_clearance = previous_state.recurrence_after_clearance
        max_cancer_after_clearance = previous_state.max_cancer_after_clearance
        rebound_step = previous_state.rebound_step
        if clearance_step >= 0 and cancer_count > 0:
            recurrence_after_clearance = True
            max_cancer_after_clearance = max(max_cancer_after_clearance, cancer_count)
            if rebound_step < 0:
                rebound_step = self.step_index

        if not self.config.adaptive_dosing_enabled:
            self.dosing_state = DosingState(
                phase="manual_full_dose",
                intensity=1.0,
                reason="Adaptive dosing disabled; using the configured treatment multiplier.",
                cancer_count=cancer_count,
                clearance_step=clearance_step,
                post_clearance_steps=post_clearance,
                zero_cancer_steps=zero_cancer_steps,
                recurrence_after_clearance=recurrence_after_clearance,
                max_cancer_after_clearance=max_cancer_after_clearance,
                rebound_step=rebound_step,
            )
            return self.dosing_state

        previous_healthy_damage_rate = latest.healthy_damage_rate if latest else 0.0
        intensity = 1.0
        phase = "full_pressure"
        reason = "Cancer burden remains above adaptive taper thresholds."

        if cancer_count <= 0:
            confirmation_steps = max(1, int(self.config.zero_cancer_confirmation_steps))
            if zero_cancer_steps < confirmation_steps:
                phase = "remission_confirmation"
                intensity = self.config.remission_surveillance_intensity
                reason = (
                    "Cancer is currently zero, but remission is still being confirmed. "
                    f"Zero-cancer streak {zero_cancer_steps}/{confirmation_steps}; maintaining surveillance pressure."
                )
            elif self.config.auto_shutoff_enabled:
                phase = "post_clearance_shutoff"
                intensity = 0.0
                reason = (
                    "Cancer remained at zero for the configured confirmation window; "
                    "auto-shutoff paused treatment agents."
                )
            elif self.config.remission_surveillance_enabled:
                phase = "remission_surveillance"
                intensity = self.config.remission_surveillance_intensity
                reason = (
                    "Cancer remained at zero through confirmation; maintaining low-intensity surveillance."
                )
            else:
                phase = "post_clearance_shutoff"
                intensity = 0.0
                reason = "Cancer remained at zero through confirmation; surveillance is disabled, so treatment is paused."
        elif cancer_count <= max(0, self.config.surveillance_start_cancer_count):
            phase = "minimal_residual_watch"
            intensity = max(self.config.adaptive_minimum_intensity, 0.18)
            reason = "Cancer burden is very low; dosing reduced to minimize collateral damage."
        elif cancer_count <= max(1, self.config.taper_start_cancer_count):
            phase = "tapering"
            intensity = max(self.config.adaptive_minimum_intensity, 0.45)
            reason = "Cancer burden is below taper threshold; reducing treatment intensity."
        if recurrence_after_clearance and cancer_count > 0:
            reason = "Recurrence after clearance detected; active treatment pressure restored. " + reason

        toxicity_notes = []
        if cancer_count > 0:
            if self.microenvironment.inflammation >= self.config.inflammation_toxicity_threshold:
                intensity *= 0.65
                toxicity_notes.append("inflammation exceeded toxicity threshold")
            if previous_healthy_damage_rate >= self.config.healthy_damage_toxicity_threshold:
                intensity *= 0.60
                toxicity_notes.append("healthy-cell damage rate exceeded toxicity threshold")
            if toxicity_notes:
                phase = f"toxicity_adjusted_{phase}"
                reason += " Toxicity adjustment: " + "; ".join(toxicity_notes) + "."

        if cancer_count > 0:
            intensity = max(self.config.adaptive_minimum_intensity, intensity)
        intensity = clamp(intensity)
        self.dosing_state = DosingState(
            phase=phase,
            intensity=intensity,
            reason=reason,
            cancer_count=cancer_count,
            clearance_step=clearance_step,
            post_clearance_steps=post_clearance,
            zero_cancer_steps=zero_cancer_steps,
            recurrence_after_clearance=recurrence_after_clearance,
            max_cancer_after_clearance=max_cancer_after_clearance,
            rebound_step=rebound_step,
        )
        return self.dosing_state

    def _agent_active_for_current_phase(self, agent: BioAgent) -> bool:
        """Return whether an agent should act in the current dosing phase."""
        if not self.config.adaptive_dosing_enabled:
            return True
        if self.dosing_state.intensity <= 0.0:
            return False
        if self.dosing_state.phase == "post_clearance_shutoff":
            return False
        if self.dosing_state.phase != "remission_surveillance":
            return True

        safe_surveillance_actions = {
            "repair_dna",
            "cell_cycle_arrest",
            "increase_senescence",
            "immune_marking",
            "restore_mhc",
            "block_pd_l1",
            "reduce_proliferation",
        }
        action_names = set(agent.actions.keys())
        return (
            bool(action_names)
            and action_names <= safe_surveillance_actions
            and agent.specificity >= 0.80
            and agent.healthy_cell_risk <= 0.06
        )

    def _apply_recovery_pressure(self) -> None:
        """Allow tissue-scale stress variables to recover after cancer clearance."""
        if not self.config.adaptive_dosing_enabled:
            return
        if self.dosing_state.phase not in {"remission_confirmation", "remission_surveillance", "post_clearance_shutoff"}:
            return
        rate = clamp(self.config.recovery_rate)
        self.microenvironment.inflammation = clamp(self.microenvironment.inflammation + (0.08 - self.microenvironment.inflammation) * rate)
        self.microenvironment.immune_pressure = clamp(self.microenvironment.immune_pressure + (0.30 - self.microenvironment.immune_pressure) * rate)
        self.microenvironment.acidity = clamp(self.microenvironment.acidity + (0.05 - self.microenvironment.acidity) * rate)
        self.microenvironment.stromal_barrier = clamp(self.microenvironment.stromal_barrier + (0.10 - self.microenvironment.stromal_barrier) * rate)

    def _update_microenvironment(self) -> None:
        living = [c for c in self.cells if c.alive]
        cancer = [c for c in living if c.cell_kind == "cancer"]
        if not living:
            return
        cancer_fraction = len(cancer) / max(1, len(living))
        mean_lactate = sum(c.lactate_output for c in living) / len(living)
        mean_oxygen_need = sum(c.oxygen_need for c in living) / len(living)
        self.microenvironment.oxygen = clamp(self.microenvironment.oxygen + 0.025 * self.microenvironment.vascular_support - 0.030 * mean_oxygen_need - 0.040 * cancer_fraction)
        self.microenvironment.glucose = clamp(self.microenvironment.glucose + 0.02 * self.microenvironment.vascular_support - 0.025 * cancer_fraction)
        self.microenvironment.acidity = clamp(self.microenvironment.acidity + 0.030 * mean_lactate + 0.015 * cancer_fraction - 0.010 * self.microenvironment.vascular_support)
        self.microenvironment.inflammation = clamp(self.microenvironment.inflammation + 0.010 * cancer_fraction + 0.004 * self.microenvironment.immune_pressure)
        self.microenvironment.immune_pressure = clamp(self.microenvironment.immune_pressure + 0.004 * self.microenvironment.inflammation - 0.012 * cancer_fraction)
        self.microenvironment.vascular_support = clamp(self.microenvironment.vascular_support + 0.010 * cancer_fraction + 0.008 * (1.0 - self.microenvironment.oxygen))
        self.microenvironment.stromal_barrier = clamp(self.microenvironment.stromal_barrier + 0.006 * cancer_fraction)

    def _update_cell_baseline(self, cell: Cell, stats: Dict[str, int]) -> None:
        cell.age += 1
        # Damage accumulates with replication stress, hypoxia, and genome instability.
        hypoxia = clamp(1.0 - self.microenvironment.oxygen)
        damage_gain = (0.010 * cell.genome_instability + 0.008 * cell.proliferation_rate + 0.006 * hypoxia) * self.config.mutation_rate_multiplier
        repair = 0.012 * cell.repair_capacity * cell.pathways.atm_atr_active
        cell.dna_damage = clamp(cell.dna_damage + damage_gain - repair)

        # Mutations accumulate when damage exceeds repair.
        mutation_gain = clamp(cell.dna_damage - cell.repair_capacity * 0.25) * 0.010 * self.config.mutation_rate_multiplier
        if self.config.allow_evolution:
            cell.mutation_burden = clamp(cell.mutation_burden + mutation_gain)
            cell.genome_instability = clamp(cell.genome_instability + mutation_gain * 0.40)

        # Stress ligands and neoantigens rise with abnormal state.
        cell.stress_ligand_expression = clamp(cell.stress_ligand_expression + 0.006 * cell.dna_damage + 0.003 * hypoxia)
        cell.neoantigen_load = clamp(cell.neoantigen_load + 0.004 * cell.mutation_burden)

        # Cancer escape drift.
        if self.config.allow_evolution and cell.cell_kind == "cancer":
            if event(0.002 * cell.genome_instability, self.rng):
                stats["escape_clone_events"] += 1
                cell.clone_id = f"escape_{cell.id}_{self.step_index}"
                # Escape is not always beneficial, but frequently lowers recognition or raises resistance.
                cell.mhc_expression = clamp(cell.mhc_expression - self.rng.uniform(0.02, 0.10))
                cell.pd_l1_expression = clamp(cell.pd_l1_expression + self.rng.uniform(0.02, 0.12))
                cell.apoptosis_resistance = clamp(cell.apoptosis_resistance + self.rng.uniform(0.02, 0.10))

    def _natural_immune_surveillance(self, cell: Cell, stats: Dict[str, int]) -> None:
        if cell.cell_kind not in {"cancer", "precancerous"}:
            return
        immune_strength = self.microenvironment.immune_pressure * self.config.immune_strength_multiplier
        tcell_visibility = cell.mhc_expression * cell.neoantigen_load * clamp(1.0 - cell.pd_l1_expression)
        nk_visibility = clamp((1.0 - cell.mhc_expression) * 0.55 + cell.stress_ligand_expression * 0.45)
        immune_suppression = clamp(cell.immune_suppression_output + self.microenvironment.stromal_barrier * 0.30)
        kill_prob = clamp((tcell_visibility * 0.18 + nk_visibility * 0.16) * immune_strength * (1.0 - immune_suppression))
        if event(kill_prob, self.rng):
            cell.alive = False
            cell.cell_kind = "dead"
            stats["immune_kills"] += 1

    def _natural_apoptosis_or_senescence(self, cell: Cell, stats: Dict[str, int]) -> None:
        p53_pressure = cell.dna_damage * cell.pathways.p53_active * cell.apoptosis_sensitivity
        blockade = clamp(cell.apoptosis_resistance + cell.pathways.apoptosis_blockade)
        apoptosis_prob = clamp((p53_pressure - blockade * 0.45) * 0.10)
        if event(apoptosis_prob, self.rng):
            cell.alive = False
            cell.cell_kind = "dead"
            stats["apoptosis_events"] += 1
            return
        senescence_prob = clamp(cell.senescence_probability * cell.pathways.checkpoint_strength * (1.0 - cell.telomerase_activity) * 0.08)
        if event(senescence_prob, self.rng):
            cell.proliferation_rate = clamp(cell.proliferation_rate - 0.20)
            cell.apoptosis_sensitivity = clamp(cell.apoptosis_sensitivity + 0.05)
            stats["senescence_events"] += 1

    def _maybe_proliferate(self, cell: Cell, stats: Dict[str, int], alive_count: int) -> Optional[Cell]:
        oxygen_penalty = max(0.20, self.microenvironment.oxygen + cell.hypoxia_tolerance * 0.35)
        density_penalty = max(0.15, 1.0 - alive_count / 5000.0)
        p = clamp(cell.proliferation_rate * oxygen_penalty * density_penalty * (1.0 - cell.signals.get("SENESCENCE_READY", 0.0) * 0.5))
        p *= 0.045 if cell.cell_kind == "healthy" else 0.085
        if not event(p, self.rng):
            return None
        child = self._clone_cell(cell)
        stats["proliferation_events"] += 1
        return child

    def _clone_cell(self, parent: Cell) -> Cell:
        data = parent.to_dict()
        data["id"] = self._next_id
        self._next_id += 1
        x, y = parent.position
        data["position"] = (
            clamp(x + self.rng.uniform(-2.0, 2.0), 0.0, self.config.width),
            clamp(y + self.rng.uniform(-2.0, 2.0), 0.0, self.config.height),
        )
        data["age"] = 0
        child = Cell.from_dict(data)
        # Daughter cells vary. Cancer daughters mutate more.
        spread = 0.01 if parent.cell_kind == "healthy" else 0.04
        for attr in [
            "genome_instability", "mutation_burden", "dna_damage", "repair_capacity",
            "proliferation_rate", "apoptosis_sensitivity", "apoptosis_resistance",
            "telomerase_activity", "invasion_potential", "mhc_expression", "neoantigen_load",
            "stress_ligand_expression", "pd_l1_expression", "immune_suppression_output",
            "lactate_output", "hypoxia_tolerance"
        ]:
            setattr(child, attr, noisy(float(getattr(child, attr)), spread, self.rng))
        child.generate_signals(self.microenvironment.oxygen)
        return child

    def _population_pressure(self) -> None:
        # Cap prevents runaway memory use while maintaining sample behavior.
        max_cells = 6000
        if len(self.cells) <= max_cells:
            return
        alive = [c for c in self.cells if c.alive]
        dead = [c for c in self.cells if not c.alive]
        self.rng.shuffle(dead)
        self.cells = alive + dead[: max(0, max_cells - len(alive))]
        if len(self.cells) > max_cells:
            self.rng.shuffle(self.cells)
            self.cells = self.cells[:max_cells]

    def _decay_agents(self) -> None:
        for agent in self.cocktail.agents:
            if agent.decay_rate <= 0.0 or agent.concentration <= 0.0:
                continue
            agent.concentration = clamp(agent.concentration * (1.0 - agent.decay_rate))

    def clone_summary(self, limit: int = 10) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Cell]] = {}
        for cell in self.cells:
            if cell.alive and cell.cell_kind == "cancer":
                groups.setdefault(cell.clone_id, []).append(cell)
        rows: List[Dict[str, Any]] = []
        for clone_id, cells in groups.items():
            rows.append(
                {
                    "clone_id": clone_id,
                    "count": len(cells),
                    "mean_malignancy": sum(c.malignancy_score() for c in cells) / max(1, len(cells)),
                    "mean_mhc_expression": sum(c.mhc_expression for c in cells) / max(1, len(cells)),
                    "mean_pd_l1_expression": sum(c.pd_l1_expression for c in cells) / max(1, len(cells)),
                    "mean_apoptosis_resistance": sum(c.apoptosis_resistance for c in cells) / max(1, len(cells)),
                }
            )
        rows.sort(key=lambda row: row["count"], reverse=True)
        return rows[:limit]

    def capture_marker_snapshot(self, label: str = "latest") -> Dict[str, Any]:
        living = [c for c in self.cells if c.alive]
        cancer = [c for c in living if c.cell_kind in {"cancer", "precancerous"}]
        if not cancer:
            snapshot = {
                "label": label,
                "step": self.step_index,
                "cancer_count": 0,
                "mean_signals": {},
                "dominant_signals": [],
            }
            self.marker_snapshots[label] = snapshot
            return snapshot
        means: Dict[str, float] = {}
        for signal in SIGNALS:
            means[signal] = sum(c.signals.get(signal, 0.0) for c in cancer) / max(1, len(cancer))
        dominant = sorted(means, key=means.get, reverse=True)[:12]
        snapshot = {
            "label": label,
            "step": self.step_index,
            "cancer_count": len(cancer),
            "mean_signals": means,
            "dominant_signals": dominant,
        }
        self.marker_snapshots[label] = snapshot
        self.marker_snapshots["last_living_cancer"] = snapshot
        return snapshot

    def save_experiment(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load_experiment(cls, path: str | Path) -> "Simulation":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        sim = cls(
            config=SimulationConfig.from_dict(payload.get("config", {})),
            microenvironment=Microenvironment.from_dict(payload.get("microenvironment", {})),
            cocktail=Cocktail.from_dict(payload.get("cocktail", {"name": "Loaded cocktail", "agents": []})),
        )
        sim.cells = [Cell.from_dict(c) for c in payload.get("cells", [])]
        sim.step_index = int(payload.get("step_index", 0))
        sim._next_id = max([c.id for c in sim.cells], default=0) + 1
        if "dosing_state" in payload:
            sim.dosing_state = DosingState.from_dict(payload.get("dosing_state", {}))
        sim.cancer_profile = dict(payload.get("cancer_profile", {}))
        sim.marker_snapshots = dict(payload.get("marker_snapshots", {}))
        if "rng_state" in payload:
            sim.rng.setstate(_json_to_tuple(payload["rng_state"]))
        # Restore metric history when available so loaded experiments keep their plots/reports.
        from .models import MetricsSnapshot
        metric_fields = {field.name for field in fields(MetricsSnapshot)}
        sim.analytics.history = [
            MetricsSnapshot(**{key: value for key, value in row.items() if key in metric_fields})
            for row in payload.get("analytics", [])
        ]
        if not sim.analytics.history and sim.cells:
            sim.analytics.record(sim.step_index, sim.cells, 0, 0, 0, 0, 0, 0, 0, sim.microenvironment, sim.cocktail.agents)
        return sim

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.2",
            "config": self.config.to_dict(),
            "microenvironment": self.microenvironment.to_dict(),
            "cocktail": self.cocktail.to_dict(),
            "step_index": self.step_index,
            "cells": [c.to_dict() for c in self.cells],
            "analytics": self.analytics.to_dicts(),
            "dosing_state": self.dosing_state.to_dict(),
            "cancer_profile": self.cancer_profile,
            "marker_snapshots": self.marker_snapshots,
            "rng_state": self.rng.getstate(),
        }

    def live_cell_counts(self) -> Dict[str, int]:
        counts = {"healthy": 0, "precancerous": 0, "cancer": 0, "immune": 0, "stromal": 0, "dead": 0}
        for c in self.cells:
            if not c.alive or c.cell_kind == "dead":
                counts["dead"] += 1
            else:
                counts[c.cell_kind] = counts.get(c.cell_kind, 0) + 1
        return counts
