"""Shared constants for OncoForge.

The names here are the public vocabulary used by the GUI, JSON data files,
and simulation engine. Keeping them explicit prevents hidden magic strings.
"""

from __future__ import annotations

SIGNALS = [
    "DNA_DAMAGE_HIGH",
    "REPLICATION_STRESS",
    "P53_INACTIVE",
    "RB_INACTIVE",
    "MMR_DEFECT",
    "BRCA_DEFECT",
    "PARP_DEPENDENCE",
    "MHC_LOW",
    "NEOANTIGEN_PRESENT",
    "STRESS_LIGAND_HIGH",
    "TELOMERASE_HIGH",
    "HYPOXIA_HIGH",
    "LACTATE_HIGH",
    "PD_L1_HIGH",
    "CASPASE_BLOCKED",
    "ECM_INVASION_HIGH",
    "ANGIOGENESIS_SIGNAL",
    "INFLAMMATION_HIGH",
    "APOPTOSIS_READY",
    "SENESCENCE_READY",
    "PROTEASOME_STRESS",
    "UNFOLDED_PROTEIN_RESPONSE",
    "FERROPTOSIS_SUSCEPTIBLE",
    "CD47_DONT_EAT_ME",
    "COMPLEMENT_SUSCEPTIBLE",
    "STING_DNA_SENSING",
    "AUTOPHAGY_DEPENDENCE",
]

MICROENVIRONMENT_TARGETS = [
    "TUMOR_ACIDITY",
    "LOW_OXYGEN_ENV",
    "INFLAMED_ENV",
    "HIGH_IMMUNE_PRESSURE",
]

ACTIONS = [
    "repair_dna",
    "cell_cycle_arrest",
    "increase_apoptosis",
    "execute_apoptosis",
    "increase_senescence",
    "immune_marking",
    "increase_nk_kill",
    "increase_tcell_kill",
    "restore_mhc",
    "block_pd_l1",
    "reduce_proliferation",
    "degrade_driver",
    "matrix_degradation",
    "hypoxia_local_activation",
    "increase_inflammation",
    "block_cd47",
    "increase_phagocytosis",
    "activate_complement",
    "trigger_ferroptosis",
    "proteostasis_overload",
    "sting_interferon_signal",
    "autophagy_pressure",
]

EVIDENCE_LEVEL_TO_LABEL = {
    1: "established_biology",
    2: "supported_model",
    3: "inferred_interaction",
    4: "speculative_hypothesis",
    5: "user_concept",
}

EVIDENCE_LABEL_TO_LEVEL = {label: level for level, label in EVIDENCE_LEVEL_TO_LABEL.items()}

EVIDENCE_LABELS = {
    "established_biology": "Canonical or well-established biological pathway, simplified for this simulator.",
    "supported_model": "Common modeling abstraction or supported biological concept represented qualitatively.",
    "inferred_interaction": "Plausible interaction inferred from related biology; useful for exploration, not validation.",
    "speculative_hypothesis": "Synthetic or systems-level hypothesis that needs experimental support.",
    "user_concept": "User-created conceptual mechanism; treated as a design idea, not established science.",
}

EVIDENCE_LEVELS = {
    level: f"{label} - {EVIDENCE_LABELS[label]}"
    for level, label in EVIDENCE_LEVEL_TO_LABEL.items()
}

ACTIVATION_LOGICS = ["WEIGHTED", "AND", "OR", "THRESHOLD"]

CELL_KINDS = ["healthy", "precancerous", "cancer", "immune", "stromal", "dead"]
DEFAULT_RANDOM_SEED = 1729
