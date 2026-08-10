"""Knowledge and validation helpers for OncoForge.

This module is deliberately conservative: it validates model vocabulary and
produces interpretable summaries. It does not claim clinical validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .constants import ACTIONS, ACTIVATION_LOGICS, EVIDENCE_LABELS, EVIDENCE_LEVELS, EVIDENCE_LEVEL_TO_LABEL, MICROENVIRONMENT_TARGETS, SIGNALS
from .models import BioAgent, Cell, Cocktail, Microenvironment
from .utils import clamp, coerce_probability

SURFACE_TARGETS = {"EGFR_LIKE", "HER2_LIKE", "MUCIN_ABNORMAL", "TUMOR_PROTEASE_ACTIVITY", "CD47_LIKE", "COMPLEMENT_BINDING_LIKE"}
ALL_TARGETS = set(SIGNALS) | set(MICROENVIRONMENT_TARGETS) | SURFACE_TARGETS
ALL_ACTIONS = set(ACTIONS)

PATHWAY_RULES = [
    {
        "name": "DNA damage checkpoint",
        "inputs": ["DNA_DAMAGE_HIGH", "REPLICATION_STRESS"],
        "natural_systems": ["ATM", "ATR", "CHK1/CHK2", "p53"],
        "model_outputs": ["cell_cycle_arrest", "repair_dna", "increase_apoptosis"],
        "evidence_level": 1,
        "evidence_label": "established_biology",
        "explanation": "Cells use ATM/ATR-style DNA-damage signaling to slow the cell cycle, repair damage, or trigger death when damage is severe.",
    },
    {
        "name": "RB cell-cycle checkpoint",
        "inputs": ["RB_INACTIVE", "REPLICATION_STRESS", "TELOMERASE_HIGH"],
        "natural_systems": ["RB/E2F checkpoint", "cell-cycle restriction point"],
        "model_outputs": ["cell_cycle_arrest", "reduce_proliferation", "increase_senescence"],
        "evidence_level": 1,
        "evidence_label": "established_biology",
        "explanation": "RB-like checkpoint activity is represented as a brake on uncontrolled proliferation and a route toward senescence-like arrest.",
    },
    {
        "name": "Mismatch / repair pressure",
        "inputs": ["MMR_DEFECT", "BRCA_DEFECT", "PARP_DEPENDENCE"],
        "natural_systems": ["MMR", "BRCA1/2", "PARP-associated repair dependency"],
        "model_outputs": ["repair_dna", "increase_apoptosis"],
        "evidence_level": 2,
        "evidence_label": "supported_model",
        "explanation": "Mismatch repair and homologous recombination defects increase mutation burden and repair stress in this qualitative model.",
    },
    {
        "name": "Caspase apoptosis execution",
        "inputs": ["APOPTOSIS_READY", "CASPASE_BLOCKED", "DNA_DAMAGE_HIGH"],
        "natural_systems": ["intrinsic apoptosis", "caspase execution phase"],
        "model_outputs": ["increase_apoptosis", "execute_apoptosis"],
        "evidence_level": 2,
        "evidence_label": "supported_model",
        "explanation": "The simulator treats caspase accessibility as a simplified final common route for apoptosis execution.",
    },
    {
        "name": "T-cell visibility",
        "inputs": ["NEOANTIGEN_PRESENT", "MHC_LOW", "PD_L1_HIGH"],
        "natural_systems": ["MHC-I", "TCR", "CD8 T cells", "PD-1/PD-L1 axis"],
        "model_outputs": ["restore_mhc", "block_pd_l1", "increase_tcell_kill"],
        "evidence_level": 2,
        "evidence_label": "supported_model",
        "explanation": "Neoantigen load, MHC-I display, and PD-L1-like suppression are simplified into a T-cell visibility score.",
    },
    {
        "name": "NK missing-self / stress surveillance",
        "inputs": ["MHC_LOW", "STRESS_LIGAND_HIGH"],
        "natural_systems": ["NK cell activating/inhibitory receptor balance"],
        "model_outputs": ["increase_nk_kill", "immune_marking"],
        "evidence_level": 2,
        "evidence_label": "supported_model",
        "explanation": "NK-cell recognition is modeled as a balance between missing-self behavior and stress-ligand activation.",
    },
    {
        "name": "Macrophage/phagocytosis gate",
        "inputs": ["CD47_DONT_EAT_ME", "STRESS_LIGAND_HIGH", "COMPLEMENT_SUSCEPTIBLE"],
        "natural_systems": ["phagocytosis brakes", "eat-me signals", "complement-like opsonization"],
        "model_outputs": ["block_cd47", "increase_phagocytosis", "activate_complement"],
        "evidence_level": 3,
        "evidence_label": "inferred_interaction",
        "explanation": "CD47-like brakes, complement susceptibility, and stress signals are modeled as conceptual macrophage-style cleanup cues.",
    },
    {
        "name": "Tumor microenvironment enzyme gates",
        "inputs": ["HYPOXIA_HIGH", "LACTATE_HIGH", "ECM_INVASION_HIGH", "TUMOR_ACIDITY"],
        "natural_systems": ["hypoxia response", "tumor proteases", "matrix remodeling"],
        "model_outputs": ["hypoxia_local_activation", "matrix_degradation"],
        "evidence_level": 4,
        "evidence_label": "speculative_hypothesis",
        "explanation": "Hypoxia, acidity, protease activity, and matrix behavior are used as local gates for synthetic/enzyme-style concepts.",
    },
    {
        "name": "Stress-death alternatives",
        "inputs": ["FERROPTOSIS_SUSCEPTIBLE", "PROTEASOME_STRESS", "AUTOPHAGY_DEPENDENCE"],
        "natural_systems": ["metabolic stress", "proteostasis", "autophagy dependence"],
        "model_outputs": ["trigger_ferroptosis", "proteostasis_overload", "autophagy_pressure"],
        "evidence_level": 4,
        "evidence_label": "speculative_hypothesis",
        "explanation": "Non-apoptotic and stress-adaptation vulnerabilities are represented as exploratory pressure channels.",
    },
    {
        "name": "STING / cytosolic-DNA sensing",
        "inputs": ["STING_DNA_SENSING", "DNA_DAMAGE_HIGH", "INFLAMMATION_HIGH"],
        "natural_systems": ["cGAS-STING-like sensing", "type-I interferon-like visibility"],
        "model_outputs": ["sting_interferon_signal", "immune_marking"],
        "evidence_level": 3,
        "evidence_label": "inferred_interaction",
        "explanation": "Cytosolic-DNA sensing is simplified as a visibility and inflammation pulse, not as a detailed immune network.",
    },
]


@dataclass
class ValidationIssue:
    severity: str
    location: str
    message: str


def validate_agent(agent: BioAgent) -> List[ValidationIssue]:
    """Return interpretable validation issues for a BioAgent."""
    issues: List[ValidationIssue] = []
    if not agent.name.strip():
        issues.append(ValidationIssue("error", "name", "Agent must have a name."))
    if agent.activation_logic.upper() not in set(ACTIVATION_LOGICS):
        issues.append(ValidationIssue("error", "activation_logic", f"Activation logic must be one of: {', '.join(ACTIVATION_LOGICS)}."))
    if not agent.targets:
        issues.append(ValidationIssue("warning", "targets", "Agent has no targets and will not activate."))
    for target, required in agent.targets.items():
        if target not in ALL_TARGETS:
            issues.append(ValidationIssue("error", "targets", f"Unknown target: {target}"))
        try:
            coerce_probability(required, f"targets.{target}")
        except ValueError as exc:
            issues.append(ValidationIssue("error", "targets", str(exc)))
    if not agent.actions:
        issues.append(ValidationIssue("warning", "actions", "Agent has no actions."))
    for action, strength in agent.actions.items():
        if action not in ALL_ACTIONS:
            issues.append(ValidationIssue("error", "actions", f"Unknown action: {action}"))
        try:
            coerce_probability(strength, f"actions.{action}")
        except ValueError as exc:
            issues.append(ValidationIssue("error", "actions", str(exc)))
    if not (1 <= int(agent.evidence_level) <= 5):
        issues.append(ValidationIssue("error", "evidence_level", "Evidence level should be 1 through 5."))
    if agent.evidence_label not in EVIDENCE_LABELS:
        issues.append(ValidationIssue("error", "evidence_label", f"Evidence label must be one of: {', '.join(EVIDENCE_LABELS)}."))
    if EVIDENCE_LEVEL_TO_LABEL.get(agent.evidence_level) != agent.evidence_label:
        issues.append(ValidationIssue("warning", "evidence_label", "Evidence level and evidence label do not match."))
    for target, required in agent.microenvironment_requirements.items():
        if target not in ALL_TARGETS:
            issues.append(ValidationIssue("error", "microenvironment_requirements", f"Unknown requirement target: {target}"))
        try:
            coerce_probability(required, f"microenvironment_requirements.{target}")
        except ValueError as exc:
            issues.append(ValidationIssue("error", "microenvironment_requirements", str(exc)))
    return issues


def validate_cocktail(cocktail: Cocktail) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    names = set()
    for idx, agent in enumerate(cocktail.agents):
        loc = f"agents[{idx}]"
        if agent.name in names:
            issues.append(ValidationIssue("warning", loc, f"Duplicate agent: {agent.name}"))
        names.add(agent.name)
        for issue in validate_agent(agent):
            issues.append(ValidationIssue(issue.severity, f"{loc}.{issue.location}", issue.message))
    return issues


def cocktail_coverage(cocktail: Cocktail) -> Dict[str, float]:
    """Return target and action coverage scores for a cocktail."""
    targeted = set()
    actions = set()
    target_counts: Dict[str, int] = {}
    action_counts: Dict[str, int] = {}
    evidence_scores = []
    specificity = []
    risk = []
    potency = []
    inflammatory_action_pressure = 0.0
    for agent in cocktail.agents:
        targeted.update(agent.targets.keys())
        actions.update(agent.actions.keys())
        for target in agent.targets:
            target_counts[target] = target_counts.get(target, 0) + 1
        for action, strength in agent.actions.items():
            action_counts[action] = action_counts.get(action, 0) + 1
            if action in {"increase_inflammation", "activate_complement", "sting_interferon_signal"}:
                inflammatory_action_pressure += strength * agent.potency
        evidence_scores.append(max(1, min(5, agent.evidence_level)))
        specificity.append(agent.specificity)
        risk.append(agent.healthy_cell_risk)
        potency.append(agent.potency)
    pathway_hits = 0
    for rule in PATHWAY_RULES:
        if targeted.intersection(rule["inputs"]) or actions.intersection(rule["model_outputs"]):
            pathway_hits += 1
    repeated_targets = sum(count - 1 for count in target_counts.values() if count > 1)
    repeated_actions = sum(count - 1 for count in action_counts.values() if count > 1)
    redundancy = clamp((repeated_targets + repeated_actions) / max(1, len(cocktail.agents) * 2))
    mean_specificity = sum(specificity) / max(1, len(specificity))
    mean_potency = sum(potency) / max(1, len(potency))
    mean_healthy_risk = sum(risk) / max(1, len(risk))
    mean_evidence_level = sum(evidence_scores) / max(1, len(evidence_scores))
    signal_coverage = len(targeted & ALL_TARGETS) / max(1, len(ALL_TARGETS))
    pathway_coverage = pathway_hits / max(1, len(PATHWAY_RULES))
    evidence_strength = 1.0 - ((mean_evidence_level - 1.0) / 4.0)
    inflammation_risk = clamp((inflammatory_action_pressure / max(1, len(cocktail.agents))) + mean_healthy_risk * 0.35)
    escape_pressure = clamp(mean_potency * (1.0 - redundancy * 0.25) * (1.0 - pathway_coverage * 0.35))
    conceptual_plausibility = clamp(
        mean_specificity * 0.35
        + (1.0 - mean_healthy_risk) * 0.25
        + evidence_strength * 0.20
        + pathway_coverage * 0.15
        + redundancy * 0.05
    )
    return {
        "target_coverage": len(targeted & set(SIGNALS)) / max(1, len(SIGNALS)),
        "action_coverage": len(actions & set(ACTIONS)) / max(1, len(ACTIONS)),
        "signal_coverage": signal_coverage,
        "pathway_coverage": pathway_coverage,
        "redundancy": redundancy,
        "mean_specificity": mean_specificity,
        "mean_potency": mean_potency,
        "mean_healthy_risk": mean_healthy_risk,
        "mean_evidence_level": mean_evidence_level,
        "inflammation_risk": inflammation_risk,
        "escape_pressure": escape_pressure,
        "conceptual_plausibility": conceptual_plausibility,
    }


def agent_activation_preview(agent: BioAgent, cell: Cell, micro: Microenvironment) -> Dict[str, float]:
    """Deterministic preview of target matches without mutating the simulation."""
    cell.generate_signals(micro.oxygen)
    matches: Dict[str, float] = {}
    for target, required in agent.targets.items():
        if target in cell.signals:
            observed = cell.signals[target]
        elif target in cell.surface_markers:
            observed = cell.surface_markers[target]
        elif target == "TUMOR_ACIDITY":
            observed = micro.acidity
        elif target == "LOW_OXYGEN_ENV":
            observed = 1.0 - micro.oxygen
        elif target == "INFLAMED_ENV":
            observed = micro.inflammation
        elif target == "HIGH_IMMUNE_PRESSURE":
            observed = micro.immune_pressure
        else:
            observed = 0.0
        matches[target] = clamp(observed / max(required, 1e-9))
    return matches


def pathway_map_text() -> str:
    lines = ["OncoForge pathway map", ""]
    for item in PATHWAY_RULES:
        lines.append(f"{item['name']}  [Evidence {item['evidence_label']}: {EVIDENCE_LEVELS[item['evidence_level']]}]")
        lines.append(f"  Inputs: {', '.join(item['inputs'])}")
        lines.append(f"  Natural systems: {', '.join(item['natural_systems'])}")
        lines.append(f"  Model outputs: {', '.join(item['model_outputs'])}")
        lines.append(f"  Explanation: {item['explanation']}")
        lines.append("")
    return "\n".join(lines)
