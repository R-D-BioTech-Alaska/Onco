"""Rule engine for natural and synthetic biological agents.

This is a conceptual simulator. It does not claim clinical prediction. The goal is
transparent hypothesis generation: every decision is interpretable and inspectable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models import Cell, BioAgent, Microenvironment
from .utils import clamp, coerce_probability, sigmoid, event


@dataclass
class AgentEffect:
    agent_name: str
    cell_id: int
    detection_score: float
    action_probability: float
    action_name: str
    occurred: bool
    healthy_damage: bool = False


class RuleEngine:
    """Applies BioAgent logic to cells."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def detection_score(self, cell: Cell, agent: BioAgent, microenvironment: Microenvironment) -> float:
        """Compute agent detection/activation score against one cell.

        Scores combine marker/signal matches with microenvironment gates.
        """
        threshold_blocked = False
        if not agent.targets:
            base = 0.0
        else:
            matches: List[float] = []
            for target, required in tuple(agent.targets.items()):
                observed = self._observed_target_value(cell, target, microenvironment)
                required = coerce_probability(required, f"{agent.name}.targets.{target}")
                # Match is high when observed signal meets/exceeds target weight.
                if required <= 0.0:
                    match = 0.0
                else:
                    match = clamp(observed / required)
                matches.append(match)

            logic = agent.activation_logic.upper()
            if logic == "AND":
                base = min(matches) if matches else 0.0
            elif logic == "OR":
                base = max(matches) if matches else 0.0
            elif logic == "THRESHOLD":
                weighted = sum(matches) / len(matches) if matches else 0.0
                if weighted >= agent.activation_threshold:
                    base = weighted
                else:
                    base = 0.0
                    threshold_blocked = True
            else:
                base = sum(matches) / len(matches) if matches else 0.0

        micro_gate = 1.0
        for target, required in tuple(agent.microenvironment_requirements.items()):
            observed = self._observed_target_value(cell, target, microenvironment)
            required = coerce_probability(required, f"{agent.name}.microenvironment_requirements.{target}")
            micro_gate = min(micro_gate, clamp(observed / max(required, 1e-9)))
        if threshold_blocked:
            return 0.0

        malignancy_bonus = 0.35 * cell.malignancy_score()
        healthy_penalty = agent.healthy_cell_risk * (1.0 - cell.malignancy_score())
        specificity_boost = agent.specificity * 0.30
        micro_barrier = microenvironment.stromal_barrier * 0.12
        raw = base * 0.70 + malignancy_bonus + specificity_boost - healthy_penalty - micro_barrier
        return clamp(sigmoid(raw, steepness=5.0, midpoint=0.45) * micro_gate * agent.concentration)

    @staticmethod
    def _observed_target_value(cell: Cell, target: str, microenvironment: Microenvironment) -> float:
        if target in cell.signals:
            return coerce_probability(cell.signals.get(target, 0.0), f"signal {target}")
        if target in cell.surface_markers:
            return coerce_probability(cell.surface_markers.get(target, 0.0), f"surface marker {target}")
        if target == "TUMOR_ACIDITY":
            return microenvironment.acidity
        if target == "LOW_OXYGEN_ENV":
            return 1.0 - microenvironment.oxygen
        if target == "INFLAMED_ENV":
            return microenvironment.inflammation
        if target == "HIGH_IMMUNE_PRESSURE":
            return microenvironment.immune_pressure
        return 0.0

    def apply_agent(self, cell: Cell, agent: BioAgent, microenvironment: Microenvironment, treatment_multiplier: float = 1.0) -> List[AgentEffect]:
        """Apply one biological/synthetic agent to a cell."""
        effects: List[AgentEffect] = []
        if not cell.alive:
            return effects
        d = self.detection_score(cell, agent, microenvironment)
        potency = clamp(agent.potency * treatment_multiplier)
        for action_name, strength in tuple(agent.actions.items()):
            p = clamp(d * potency * strength)
            occurred = event(p, self.rng)
            healthy_damage = False
            if occurred:
                healthy_damage = self._perform_action(cell, action_name, strength, agent, microenvironment)
            effects.append(AgentEffect(agent.name, cell.id, d, p, action_name, occurred, healthy_damage))
        return effects

    def _perform_action(self, cell: Cell, action_name: str, strength: float, agent: BioAgent, microenvironment: Microenvironment) -> bool:
        """Modify a cell or environment according to an action.

        Returns True when action harms a healthy cell.
        """
        healthy_damage = cell.cell_kind == "healthy" and self.rng.random() < agent.healthy_cell_risk * strength
        s = clamp(strength)

        if action_name == "repair_dna":
            cell.dna_damage = clamp(cell.dna_damage - 0.20 * s)
            cell.repair_capacity = clamp(cell.repair_capacity + 0.08 * s)
            cell.genome_instability = clamp(cell.genome_instability - 0.05 * s)

        elif action_name == "cell_cycle_arrest":
            cell.proliferation_rate = clamp(cell.proliferation_rate - 0.18 * s)
            cell.pathways.checkpoint_strength = clamp(cell.pathways.checkpoint_strength + 0.15 * s)
            cell.signals["SENESCENCE_READY"] = clamp(cell.signals.get("SENESCENCE_READY", 0.0) + 0.20 * s)

        elif action_name == "increase_apoptosis":
            cell.apoptosis_sensitivity = clamp(cell.apoptosis_sensitivity + 0.18 * s)
            cell.apoptosis_resistance = clamp(cell.apoptosis_resistance - 0.12 * s)
            cell.signals["APOPTOSIS_READY"] = clamp(cell.signals.get("APOPTOSIS_READY", 0.0) + 0.30 * s)

        elif action_name == "execute_apoptosis":
            kill_pressure = s * cell.apoptosis_sensitivity * (1.0 - cell.apoptosis_resistance) * cell.malignancy_score()
            if self.rng.random() < clamp(kill_pressure):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "increase_senescence":
            cell.senescence_probability = clamp(cell.senescence_probability + 0.25 * s)
            cell.proliferation_rate = clamp(cell.proliferation_rate - 0.10 * s)

        elif action_name == "immune_marking":
            cell.neoantigen_load = clamp(cell.neoantigen_load + 0.12 * s)
            cell.stress_ligand_expression = clamp(cell.stress_ligand_expression + 0.14 * s)
            cell.immune_suppression_output = clamp(cell.immune_suppression_output - 0.08 * s)

        elif action_name == "increase_nk_kill":
            pressure = s * microenvironment.immune_pressure * clamp((1.0 - cell.mhc_expression) + cell.stress_ligand_expression) * cell.malignancy_score()
            if self.rng.random() < clamp(pressure):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "increase_tcell_kill":
            pressure = s * microenvironment.immune_pressure * cell.mhc_expression * cell.neoantigen_load * clamp(1.0 - cell.pd_l1_expression) * (0.2 + cell.malignancy_score())
            if self.rng.random() < clamp(pressure):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "restore_mhc":
            cell.mhc_expression = clamp(cell.mhc_expression + 0.20 * s)

        elif action_name == "block_pd_l1":
            cell.pd_l1_expression = clamp(cell.pd_l1_expression - 0.25 * s)
            cell.immune_suppression_output = clamp(cell.immune_suppression_output - 0.15 * s)

        elif action_name == "reduce_proliferation":
            cell.proliferation_rate = clamp(cell.proliferation_rate - 0.20 * s)
            cell.telomerase_activity = clamp(cell.telomerase_activity - 0.08 * s)

        elif action_name == "degrade_driver":
            cell.proliferation_rate = clamp(cell.proliferation_rate - 0.12 * s)
            cell.apoptosis_resistance = clamp(cell.apoptosis_resistance - 0.08 * s)
            cell.genome_instability = clamp(cell.genome_instability - 0.04 * s)

        elif action_name == "matrix_degradation":
            microenvironment.stromal_barrier = clamp(microenvironment.stromal_barrier - 0.06 * s)
            cell.invasion_potential = clamp(cell.invasion_potential - 0.05 * s)

        elif action_name == "hypoxia_local_activation":
            hypoxic_factor = clamp(1.0 - microenvironment.oxygen + cell.signals.get("HYPOXIA_HIGH", 0.0))
            pressure = s * hypoxic_factor * cell.malignancy_score() * (0.5 + agent.specificity / 2.0)
            if self.rng.random() < clamp(pressure):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "increase_inflammation":
            microenvironment.inflammation = clamp(microenvironment.inflammation + 0.04 * s)
            microenvironment.immune_pressure = clamp(microenvironment.immune_pressure + 0.03 * s)

        elif action_name == "block_cd47":
            # Conceptual removal of a macrophage/phagocytosis brake.
            marker = cell.surface_markers.get("CD47_LIKE", 0.0)
            cell.surface_markers["CD47_LIKE"] = clamp(marker - 0.28 * s)
            cell.immune_suppression_output = clamp(cell.immune_suppression_output - 0.10 * s)

        elif action_name == "increase_phagocytosis":
            cd47_brake = cell.surface_markers.get("CD47_LIKE", 0.0)
            eat_me = clamp(cell.stress_ligand_expression + cell.signals.get("COMPLEMENT_SUSCEPTIBLE", 0.0))
            pressure = s * microenvironment.immune_pressure * eat_me * (1.0 - 0.75 * cd47_brake) * (0.25 + cell.malignancy_score())
            if self.rng.random() < clamp(pressure):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "activate_complement":
            complement = cell.signals.get("COMPLEMENT_SUSCEPTIBLE", 0.0)
            pressure = s * complement * (0.20 + cell.malignancy_score()) * (0.50 + microenvironment.immune_pressure * 0.50)
            cell.stress_ligand_expression = clamp(cell.stress_ligand_expression + 0.10 * s)
            if self.rng.random() < clamp(pressure * 0.55):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "trigger_ferroptosis":
            susceptibility = cell.signals.get("FERROPTOSIS_SUSCEPTIBLE", 0.0)
            pressure = s * susceptibility * (0.35 + cell.malignancy_score())
            cell.dna_damage = clamp(cell.dna_damage + 0.08 * s)
            if self.rng.random() < clamp(pressure * 0.75):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "proteostasis_overload":
            pressure_signal = max(cell.signals.get("PROTEASOME_STRESS", 0.0), cell.signals.get("UNFOLDED_PROTEIN_RESPONSE", 0.0))
            cell.dna_damage = clamp(cell.dna_damage + 0.05 * s * pressure_signal)
            cell.apoptosis_sensitivity = clamp(cell.apoptosis_sensitivity + 0.10 * s)
            cell.apoptosis_resistance = clamp(cell.apoptosis_resistance - 0.06 * s * pressure_signal)
            if self.rng.random() < clamp(s * pressure_signal * cell.malignancy_score() * 0.45):
                cell.alive = False
                cell.cell_kind = "dead"

        elif action_name == "sting_interferon_signal":
            # Cytosolic-DNA/interferon abstraction: boosts visibility and local immune pressure.
            signal = cell.signals.get("STING_DNA_SENSING", 0.0)
            cell.neoantigen_load = clamp(cell.neoantigen_load + 0.08 * s * signal)
            cell.mhc_expression = clamp(cell.mhc_expression + 0.10 * s * signal)
            cell.stress_ligand_expression = clamp(cell.stress_ligand_expression + 0.08 * s * signal)
            microenvironment.inflammation = clamp(microenvironment.inflammation + 0.03 * s * signal)
            microenvironment.immune_pressure = clamp(microenvironment.immune_pressure + 0.04 * s * signal)

        elif action_name == "autophagy_pressure":
            dependence = cell.signals.get("AUTOPHAGY_DEPENDENCE", 0.0)
            cell.hypoxia_tolerance = clamp(cell.hypoxia_tolerance - 0.10 * s * dependence)
            cell.apoptosis_sensitivity = clamp(cell.apoptosis_sensitivity + 0.08 * s * dependence)
            if self.rng.random() < clamp(s * dependence * (1.0 - microenvironment.oxygen) * cell.malignancy_score() * 0.45):
                cell.alive = False
                cell.cell_kind = "dead"

        # If a healthy cell was affected, model mild injury unless apoptosis already killed it.
        if healthy_damage and cell.alive:
            cell.dna_damage = clamp(cell.dna_damage + 0.08 * s)
            cell.proliferation_rate = clamp(cell.proliferation_rate - 0.04 * s)
            cell.apoptosis_sensitivity = clamp(cell.apoptosis_sensitivity + 0.04 * s)
        return healthy_damage
