"""Loading and validating bundled OncoForge presets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import BioAgent, Cocktail

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PACKAGE_ROOT / "data"


def load_json_file(name: str) -> Any:
    path = DATA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def load_agents() -> List[BioAgent]:
    items: List[Dict[str, Any]] = []
    for filename in ["natural_agents.json", "synthetic_agents.json"]:
        items.extend(load_json_file(filename))
    return [BioAgent.from_dict(x) for x in items]


def load_agent_map() -> Dict[str, BioAgent]:
    return {agent.name: agent for agent in load_agents()}


def load_cancer_presets() -> List[Dict[str, Any]]:
    return load_json_file("cancer_types.json")


def load_evidence_sources() -> Dict[str, Any]:
    return load_json_file("evidence_sources.json")


def default_cocktails() -> List[Cocktail]:
    agents = load_agent_map()

    def a(name: str) -> BioAgent:
        return agents[name]

    return [
        Cocktail(
            "Immune visibility starter",
            [a("MHC-I Restoration Factor"), a("PD-L1 Blockade Mimic"), a("T-cell Engagement Amplifier")],
            "Raises antigen visibility and lowers immune suppression in the conceptual model.",
        ),
        Cocktail(
            "Damage-to-death cascade",
            [a("p53 Pathway Restorer"), a("Caspase Accessibility Opener"), a("Apoptosis Execution Trigger")],
            "Pushes damaged high-risk cells toward arrest/apoptosis in the conceptual model.",
        ),
        Cocktail(
            "NK stress-response swarm",
            [a("Stress Ligand Amplifier"), a("NK Missing-Self Enhancer"), a("Tumor Stress Binder")],
            "Focuses on MHC-low or stress-ligand-high cells.",
        ),
        Cocktail(
            "Hypoxic tumor bath",
            [a("Hypoxia-Activated Enzyme Gate"), a("Tumor Protease Enzyme Gate"), a("Matrix Barrier Softener")],
            "Uses tumor microenvironment signals such as hypoxia, acidity, protease activity, and matrix barrier.",
        ),
        Cocktail(
            "Innate immune cleanup bath",
            [
                a("CD47 Phagocytosis Brake Remover"),
                a("Complement Deposition Gate"),
                a("STING Interferon Visibility Pulse"),
                a("NK Missing-Self Enhancer"),
            ],
            "Tests macrophage/complement/NK-style clearance logic around abnormal surface and stress signals.",
        ),
        Cocktail(
            "Stress death pressure bath",
            [
                a("Ferroptosis Susceptibility Trigger"),
                a("Proteostasis Collapse Gate"),
                a("Autophagy Dependency Pressure"),
                a("Telomerase Pressure Clamp"),
            ],
            "Tests non-apoptotic and stress-adaptation pressure against metabolically stressed clones.",
        ),
        Cocktail(
            "Four-signal waste-cell gate",
            [
                a("Four-Signal Waste Cell Gate"),
                a("CD47 Phagocytosis Brake Remover"),
                a("Apoptosis Execution Trigger"),
                a("MHC-I Restoration Factor"),
            ],
            "Closest bundled version of the user concept: multi-signal abnormal-cell detection plus removal routes.",
        ),
        Cocktail(
            "Checkpoint priming pair",
            [
                a("Neoantigen Visibility Amplifier"),
                a("T-cell Priming Signal"),
                a("PD-L1 Blockade Mimic"),
            ],
            "Narrow conceptual immune-visibility/checkpoint package for immune-visible profiles.",
        ),
        Cocktail(
            "Repair-defect precision pair",
            [
                a("HR-Defect Exploiter"),
                a("PARP Dependence Exploiter"),
                a("Replication-Stress Amplifier"),
            ],
            "Conceptual DNA-repair vulnerability package for BRCA/PARP/replication-stress profiles.",
        ),
        Cocktail(
            "Stromal access microenvironment set",
            [
                a("Tumor Acidity Gate"),
                a("Vascular Normalization Concept"),
                a("ECM Invasion Brake"),
            ],
            "Microenvironment-oriented conceptual set for hypoxic, acidic, or stromal-barrier-heavy profiles.",
        ),
        Cocktail(
            "Remission surveillance set",
            [
                a("MHC-I Restoration Factor"),
                a("Neoantigen Visibility Amplifier"),
                a("NK Persistence Support"),
            ],
            "Lower-force conceptual surveillance option for post-clearance or minimal-residual simulations.",
        ),
        Cocktail(
            "Full conceptual swarm",
            [
                a("p53 Pathway Restorer"),
                a("MHC-I Restoration Factor"),
                a("PD-L1 Blockade Mimic"),
                a("Caspase Accessibility Opener"),
                a("NK Missing-Self Enhancer"),
                a("Hypoxia-Activated Enzyme Gate"),
                a("Tumor Protease Enzyme Gate"),
                a("CD47 Phagocytosis Brake Remover"),
                a("STING Interferon Visibility Pulse"),
                a("Ferroptosis Susceptibility Trigger"),
            ],
            "A deliberately broad multi-signal cocktail for exploratory simulation.",
        ),
    ]
