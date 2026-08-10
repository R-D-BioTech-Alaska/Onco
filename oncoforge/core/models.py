"""Dataclasses for cells, agents, cocktails, and simulation metrics."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Any

from .constants import EVIDENCE_LABEL_TO_LEVEL, EVIDENCE_LEVEL_TO_LABEL, SIGNALS
from .utils import clamp, coerce_float, coerce_probability, normalize_signal_dict


def _probability_mapping(data: Dict[str, Any], field_name: str) -> Dict[str, float]:
    return {str(k): coerce_probability(v, f"{field_name}.{k}") for k, v in dict(data or {}).items()}


def _normalize_evidence(level: Any = 3, label: Any = "") -> Tuple[int, str]:
    raw_label = str(label or "").strip()
    if raw_label in EVIDENCE_LABEL_TO_LEVEL:
        normalized_level = EVIDENCE_LABEL_TO_LEVEL[raw_label]
        return normalized_level, raw_label
    try:
        normalized_level = int(coerce_float(level, "evidence_level"))
    except ValueError:
        normalized_level = 3
    if normalized_level not in EVIDENCE_LEVEL_TO_LABEL:
        return normalized_level, raw_label or "inferred_interaction"
    return normalized_level, EVIDENCE_LEVEL_TO_LABEL[normalized_level]


@dataclass
class PathwayState:
    p53_active: float = 1.0
    rb_active: float = 1.0
    atm_atr_active: float = 1.0
    mmr_active: float = 1.0
    brca_active: float = 1.0
    caspase_accessible: float = 1.0
    apoptosis_blockade: float = 0.0
    checkpoint_strength: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "p53_active": self.p53_active,
            "rb_active": self.rb_active,
            "atm_atr_active": self.atm_atr_active,
            "mmr_active": self.mmr_active,
            "brca_active": self.brca_active,
            "caspase_accessible": self.caspase_accessible,
            "apoptosis_blockade": self.apoptosis_blockade,
            "checkpoint_strength": self.checkpoint_strength,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PathwayState":
        base = cls()
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, clamp(float(value)))
        return base


@dataclass
class Cell:
    id: int
    clone_id: str
    cell_kind: str = "healthy"
    tissue_type: str = "generic"
    position: Tuple[float, float] = (0.0, 0.0)

    genome_instability: float = 0.02
    mutation_burden: float = 0.01
    dna_damage: float = 0.02
    repair_capacity: float = 0.95

    proliferation_rate: float = 0.03
    apoptosis_sensitivity: float = 0.70
    apoptosis_resistance: float = 0.05
    senescence_probability: float = 0.02
    telomerase_activity: float = 0.05
    invasion_potential: float = 0.01

    mhc_expression: float = 0.85
    neoantigen_load: float = 0.02
    stress_ligand_expression: float = 0.02
    pd_l1_expression: float = 0.02
    immune_suppression_output: float = 0.02

    oxygen_need: float = 0.35
    glucose_need: float = 0.35
    lactate_output: float = 0.04
    hypoxia_tolerance: float = 0.20

    surface_markers: Dict[str, float] = field(default_factory=dict)
    signals: Dict[str, float] = field(default_factory=lambda: {s: 0.0 for s in SIGNALS})
    pathways: PathwayState = field(default_factory=PathwayState)

    alive: bool = True
    age: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        self.id = int(self.id)
        self.clone_id = str(self.clone_id)
        self.cell_kind = str(self.cell_kind)
        self.tissue_type = str(self.tissue_type)
        x, y = self.position
        self.position = (coerce_float(x, "position.x"), coerce_float(y, "position.y"))
        for field_name in [
            "genome_instability",
            "mutation_burden",
            "dna_damage",
            "repair_capacity",
            "proliferation_rate",
            "apoptosis_sensitivity",
            "apoptosis_resistance",
            "senescence_probability",
            "telomerase_activity",
            "invasion_potential",
            "mhc_expression",
            "neoantigen_load",
            "stress_ligand_expression",
            "pd_l1_expression",
            "immune_suppression_output",
            "oxygen_need",
            "glucose_need",
            "lactate_output",
            "hypoxia_tolerance",
        ]:
            setattr(self, field_name, coerce_probability(getattr(self, field_name), field_name))
        self.surface_markers = _probability_mapping(self.surface_markers, "surface_markers")
        self.signals = normalize_signal_dict(self.signals, SIGNALS)
        if isinstance(self.pathways, dict):
            self.pathways = PathwayState.from_dict(self.pathways)
        if not isinstance(self.pathways, PathwayState):
            raise ValueError("pathways must be a PathwayState or dictionary.")
        self.alive = bool(self.alive)
        self.age = int(self.age)
        self.notes = str(self.notes)

    def generate_signals(self, oxygen: float = 1.0) -> Dict[str, float]:
        """Produce an interpretable signal vector from the current cell state."""
        p = self.pathways
        hypoxia = clamp(1.0 - oxygen + self.oxygen_need * 0.25)
        stress = clamp((self.dna_damage * 0.45) + (self.genome_instability * 0.25) + (hypoxia * 0.20) + (self.proliferation_rate * 0.10))
        apoptosis_ready = clamp((self.dna_damage * p.p53_active * self.apoptosis_sensitivity) - self.apoptosis_resistance)
        senescence_ready = clamp(self.dna_damage * p.checkpoint_strength * (1.0 - self.telomerase_activity))

        values: Dict[str, float] = {}
        values["DNA_DAMAGE_HIGH"] = self.dna_damage
        values["REPLICATION_STRESS"] = clamp(self.proliferation_rate * 0.7 + self.dna_damage * 0.3)
        values["P53_INACTIVE"] = clamp(1.0 - p.p53_active)
        values["RB_INACTIVE"] = clamp(1.0 - p.rb_active)
        values["MMR_DEFECT"] = clamp(1.0 - p.mmr_active)
        values["BRCA_DEFECT"] = clamp(1.0 - p.brca_active)
        values["PARP_DEPENDENCE"] = clamp((1.0 - p.brca_active) * self.dna_damage)
        values["MHC_LOW"] = clamp(1.0 - self.mhc_expression)
        values["NEOANTIGEN_PRESENT"] = self.neoantigen_load
        values["STRESS_LIGAND_HIGH"] = clamp(max(self.stress_ligand_expression, stress))
        values["TELOMERASE_HIGH"] = self.telomerase_activity
        values["HYPOXIA_HIGH"] = hypoxia
        values["LACTATE_HIGH"] = self.lactate_output
        values["PD_L1_HIGH"] = self.pd_l1_expression
        values["CASPASE_BLOCKED"] = clamp(1.0 - p.caspase_accessible + p.apoptosis_blockade)
        values["ECM_INVASION_HIGH"] = self.invasion_potential
        values["ANGIOGENESIS_SIGNAL"] = clamp(hypoxia * 0.7 + self.invasion_potential * 0.3)
        values["INFLAMMATION_HIGH"] = self.immune_suppression_output
        values["APOPTOSIS_READY"] = apoptosis_ready
        values["SENESCENCE_READY"] = senescence_ready
        values["PROTEASOME_STRESS"] = clamp(self.mutation_burden * 0.20 + self.proliferation_rate * 0.25 + self.dna_damage * 0.20 + self.lactate_output * 0.10)
        values["UNFOLDED_PROTEIN_RESPONSE"] = clamp(self.proliferation_rate * 0.20 + self.hypoxia_tolerance * hypoxia * 0.35 + self.genome_instability * 0.15)
        values["FERROPTOSIS_SUSCEPTIBLE"] = clamp(self.lactate_output * 0.20 + self.dna_damage * 0.20 + self.genome_instability * 0.20 + (1.0 - self.repair_capacity) * 0.20)
        values["CD47_DONT_EAT_ME"] = clamp(self.surface_markers.get("CD47_LIKE", 0.0) * 0.85 + self.immune_suppression_output * 0.15)
        values["COMPLEMENT_SUSCEPTIBLE"] = clamp(self.surface_markers.get("COMPLEMENT_BINDING_LIKE", 0.0) * 0.80 + stress * 0.20)
        values["STING_DNA_SENSING"] = clamp(self.dna_damage * 0.45 + self.genome_instability * 0.35 + (1.0 - self.repair_capacity) * 0.20)
        values["AUTOPHAGY_DEPENDENCE"] = clamp(hypoxia * 0.30 + self.proliferation_rate * 0.25 + self.lactate_output * 0.20 + self.hypoxia_tolerance * 0.15)
        self.signals = values
        return self.signals

    def malignancy_score(self) -> float:
        factors = [
            self.mutation_burden,
            self.genome_instability,
            self.proliferation_rate,
            self.apoptosis_resistance,
            self.telomerase_activity,
            1.0 - self.mhc_expression,
            self.neoantigen_load,
            self.pd_l1_expression,
            self.invasion_potential,
            self.lactate_output,
        ]
        if self.cell_kind == "cancer":
            bias = 0.18
        elif self.cell_kind == "precancerous":
            bias = 0.08
        else:
            bias = -0.10
        return clamp((sum(factors) / len(factors)) + bias)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "clone_id": self.clone_id,
            "cell_kind": self.cell_kind,
            "tissue_type": self.tissue_type,
            "position": tuple(self.position),
            "genome_instability": self.genome_instability,
            "mutation_burden": self.mutation_burden,
            "dna_damage": self.dna_damage,
            "repair_capacity": self.repair_capacity,
            "proliferation_rate": self.proliferation_rate,
            "apoptosis_sensitivity": self.apoptosis_sensitivity,
            "apoptosis_resistance": self.apoptosis_resistance,
            "senescence_probability": self.senescence_probability,
            "telomerase_activity": self.telomerase_activity,
            "invasion_potential": self.invasion_potential,
            "mhc_expression": self.mhc_expression,
            "neoantigen_load": self.neoantigen_load,
            "stress_ligand_expression": self.stress_ligand_expression,
            "pd_l1_expression": self.pd_l1_expression,
            "immune_suppression_output": self.immune_suppression_output,
            "oxygen_need": self.oxygen_need,
            "glucose_need": self.glucose_need,
            "lactate_output": self.lactate_output,
            "hypoxia_tolerance": self.hypoxia_tolerance,
            "surface_markers": dict(self.surface_markers),
            "signals": dict(self.signals),
            "pathways": self.pathways.to_dict(),
            "alive": self.alive,
            "age": self.age,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Cell":
        payload = dict(data)
        payload["pathways"] = PathwayState.from_dict(payload.get("pathways", {}))
        if "signals" not in payload:
            payload["signals"] = {s: 0.0 for s in SIGNALS}
        if "surface_markers" not in payload:
            payload["surface_markers"] = {}
        if "position" in payload:
            payload["position"] = tuple(payload["position"])
        return cls(**payload)


@dataclass
class BioAgent:
    name: str
    category: str
    targets: Dict[str, float]
    activation_logic: str = "WEIGHTED"  # WEIGHTED, AND, OR, THRESHOLD
    activation_threshold: float = 0.50
    actions: Dict[str, float] = field(default_factory=dict)
    specificity: float = 0.75
    potency: float = 0.50
    decay_rate: float = 0.03
    diffusion_rate: float = 0.20
    healthy_cell_risk: float = 0.05
    concentration: float = 1.0
    evidence_level: int = 3
    evidence_label: str = ""
    microenvironment_requirements: Dict[str, float] = field(default_factory=dict)
    description: str = ""
    source_note: str = ""
    notes_limitations: str = ""

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.category = str(self.category)
        self.targets = _probability_mapping(self.targets, "targets")
        self.activation_logic = str(self.activation_logic or "WEIGHTED").upper()
        if self.activation_logic == "WEIGHTED_SCORE":
            self.activation_logic = "WEIGHTED"
        self.activation_threshold = coerce_probability(self.activation_threshold, "activation_threshold")
        self.actions = _probability_mapping(self.actions, "actions")
        self.specificity = coerce_probability(self.specificity, "specificity")
        self.potency = coerce_probability(self.potency, "potency")
        self.decay_rate = coerce_probability(self.decay_rate, "decay_rate")
        self.diffusion_rate = coerce_probability(self.diffusion_rate, "diffusion_rate")
        self.healthy_cell_risk = coerce_probability(self.healthy_cell_risk, "healthy_cell_risk")
        self.concentration = coerce_probability(self.concentration, "concentration")
        self.evidence_level, self.evidence_label = _normalize_evidence(self.evidence_level, self.evidence_label)
        self.microenvironment_requirements = _probability_mapping(
            self.microenvironment_requirements,
            "microenvironment_requirements",
        )
        self.description = str(self.description)
        self.source_note = str(self.source_note)
        self.notes_limitations = str(self.notes_limitations)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BioAgent":
        evidence_level, evidence_label = _normalize_evidence(
            data.get("evidence_level", 3),
            data.get("evidence_label", ""),
        )
        return cls(
            name=str(data.get("name", "Unnamed agent")),
            category=str(data.get("category", "conceptual")),
            targets=_probability_mapping(data.get("targets", {}), "targets"),
            activation_logic=str(data.get("activation_logic", "WEIGHTED")).upper(),
            activation_threshold=coerce_probability(data.get("activation_threshold", 0.50), "activation_threshold"),
            actions=_probability_mapping(data.get("actions", {}), "actions"),
            specificity=coerce_probability(data.get("specificity", 0.75), "specificity"),
            potency=coerce_probability(data.get("potency", 0.50), "potency"),
            decay_rate=coerce_probability(data.get("decay_rate", 0.03), "decay_rate"),
            diffusion_rate=coerce_probability(data.get("diffusion_rate", 0.20), "diffusion_rate"),
            healthy_cell_risk=coerce_probability(data.get("healthy_cell_risk", 0.05), "healthy_cell_risk"),
            concentration=coerce_probability(data.get("concentration", 1.0), "concentration"),
            evidence_level=evidence_level,
            evidence_label=evidence_label,
            microenvironment_requirements=_probability_mapping(
                data.get("microenvironment_requirements", {}),
                "microenvironment_requirements",
            ),
            description=str(data.get("description", "")),
            source_note=str(data.get("source_note", "")),
            notes_limitations=str(data.get("notes_limitations", data.get("limitations", ""))),
        )


@dataclass
class Cocktail:
    name: str
    agents: List[BioAgent] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "agents": [a.to_dict() for a in self.agents], "notes": self.notes}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Cocktail":
        return cls(
            name=str(data.get("name", "Unnamed cocktail")),
            agents=[BioAgent.from_dict(x) for x in data.get("agents", [])],
            notes=str(data.get("notes", "")),
        )


@dataclass
class Microenvironment:
    oxygen: float = 0.85
    glucose: float = 0.85
    acidity: float = 0.15
    inflammation: float = 0.10
    immune_pressure: float = 0.35
    stromal_barrier: float = 0.15
    vascular_support: float = 0.35

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Microenvironment":
        base = cls()
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, clamp(float(value)))
        return base


@dataclass
class DosingState:
    """Current adaptive treatment intensity state.

    The dosing controller is a conceptual abstraction, not a pharmacokinetic
    model. It lets the simulator distinguish maximum pressure, tapering,
    surveillance, and post-clearance recovery phases.
    """

    phase: str = "manual_full_dose"
    intensity: float = 1.0
    reason: str = "Manual treatment multiplier is being used."
    cancer_count: int = 0
    clearance_step: int = -1
    post_clearance_steps: int = 0
    zero_cancer_steps: int = 0
    recurrence_after_clearance: bool = False
    max_cancer_after_clearance: int = 0
    rebound_step: int = -1

    def __post_init__(self) -> None:
        self.phase = str(self.phase)
        self.intensity = coerce_probability(self.intensity, "dosing.intensity")
        self.reason = str(self.reason)
        self.cancer_count = int(self.cancer_count)
        self.clearance_step = int(self.clearance_step)
        self.post_clearance_steps = int(self.post_clearance_steps)
        self.zero_cancer_steps = int(self.zero_cancer_steps)
        self.recurrence_after_clearance = bool(self.recurrence_after_clearance)
        self.max_cancer_after_clearance = int(self.max_cancer_after_clearance)
        self.rebound_step = int(self.rebound_step)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DosingState":
        return cls(
            phase=str(data.get("phase", "manual_full_dose")),
            intensity=coerce_probability(data.get("intensity", 1.0), "dosing.intensity"),
            reason=str(data.get("reason", "Manual treatment multiplier is being used.")),
            cancer_count=int(coerce_float(data.get("cancer_count", 0), "dosing.cancer_count")),
            clearance_step=int(coerce_float(data.get("clearance_step", -1), "dosing.clearance_step")),
            post_clearance_steps=int(coerce_float(data.get("post_clearance_steps", 0), "dosing.post_clearance_steps")),
            zero_cancer_steps=int(coerce_float(data.get("zero_cancer_steps", data.get("post_clearance_steps", 0)), "dosing.zero_cancer_steps")),
            recurrence_after_clearance=bool(data.get("recurrence_after_clearance", False)),
            max_cancer_after_clearance=int(coerce_float(data.get("max_cancer_after_clearance", 0), "dosing.max_cancer_after_clearance")),
            rebound_step=int(coerce_float(data.get("rebound_step", -1), "dosing.rebound_step")),
        )


@dataclass
class SimulationConfig:
    name: str = "OncoForge experiment"
    steps: int = 200
    width: int = 100
    height: int = 100
    initial_healthy_cells: int = 800
    initial_cancer_cells: int = 200
    random_seed: int = 1729
    mutation_rate_multiplier: float = 1.0
    immune_strength_multiplier: float = 1.0
    treatment_strength_multiplier: float = 1.0
    adaptive_dosing_enabled: bool = False
    auto_shutoff_enabled: bool = False
    remission_surveillance_enabled: bool = True
    taper_start_cancer_count: int = 50
    surveillance_start_cancer_count: int = 10
    adaptive_minimum_intensity: float = 0.20
    remission_surveillance_intensity: float = 0.25
    zero_cancer_confirmation_steps: int = 50
    inflammation_toxicity_threshold: float = 0.85
    healthy_damage_toxicity_threshold: float = 0.015
    recovery_rate: float = 0.05
    allow_evolution: bool = True
    allow_proliferation: bool = True
    cancer_preset_name: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationConfig":
        base = cls()
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        for key in [
            "steps",
            "width",
            "height",
            "initial_healthy_cells",
            "initial_cancer_cells",
            "random_seed",
            "taper_start_cancer_count",
            "surveillance_start_cancer_count",
            "zero_cancer_confirmation_steps",
        ]:
            setattr(base, key, int(coerce_float(getattr(base, key), key)))
        for key in [
            "mutation_rate_multiplier",
            "immune_strength_multiplier",
            "treatment_strength_multiplier",
            "adaptive_minimum_intensity",
            "remission_surveillance_intensity",
            "inflammation_toxicity_threshold",
            "healthy_damage_toxicity_threshold",
            "recovery_rate",
        ]:
            setattr(base, key, coerce_float(getattr(base, key), key))
        base.adaptive_minimum_intensity = clamp(base.adaptive_minimum_intensity)
        base.remission_surveillance_intensity = clamp(base.remission_surveillance_intensity)
        base.inflammation_toxicity_threshold = clamp(base.inflammation_toxicity_threshold)
        base.healthy_damage_toxicity_threshold = clamp(base.healthy_damage_toxicity_threshold)
        base.recovery_rate = clamp(base.recovery_rate)
        base.zero_cancer_confirmation_steps = max(1, int(base.zero_cancer_confirmation_steps))
        base.adaptive_dosing_enabled = bool(base.adaptive_dosing_enabled)
        base.auto_shutoff_enabled = bool(base.auto_shutoff_enabled)
        base.remission_surveillance_enabled = bool(base.remission_surveillance_enabled)
        base.allow_evolution = bool(base.allow_evolution)
        base.allow_proliferation = bool(base.allow_proliferation)
        base.name = str(base.name)
        base.cancer_preset_name = str(base.cancer_preset_name)
        base.notes = str(base.notes)
        return base


@dataclass
class MetricsSnapshot:
    step: int
    healthy_alive: int
    cancer_alive: int
    precancerous_alive: int
    dead_cells: int
    mean_malignancy: float
    mean_dna_damage: float
    mean_immune_visibility: float
    mean_apoptosis_pressure: float
    treatment_hits: int
    immune_kills: int
    apoptosis_events: int
    senescence_events: int
    proliferation_events: int
    escape_clone_events: int
    healthy_damage_events: int
    tumor_burden: float = 0.0
    cancer_death_rate: float = 0.0
    healthy_damage_rate: float = 0.0
    immune_activation_level: float = 0.0
    escape_clone_count: int = 0
    dominant_clone_id: str = ""
    dominant_clone_fraction: float = 0.0
    inflammation: float = 0.0
    immune_pressure: float = 0.0
    mean_agent_concentration: float = 0.0
    treatment_intensity: float = 1.0
    dosing_phase: str = "manual_full_dose"
    post_clearance_steps: int = 0
    clearance_step: int = -1
    zero_cancer_steps: int = 0
    recurrence_after_clearance: bool = False
    max_cancer_after_clearance: int = 0
    rebound_step: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
