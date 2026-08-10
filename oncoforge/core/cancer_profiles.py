"""Cancer profile loading and profile-driven simulation helpers.

Cancer profiles are simulation presets, not diagnostic or clinical profiles.
They bias cell state, surface markers, pathways, and microenvironment values so
users can explore conceptual marker/cocktail matching in a transparent way.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .constants import EVIDENCE_LABEL_TO_LEVEL, SIGNALS
from .models import Cell, Cocktail, Microenvironment, SimulationConfig
from .presets import DATA_DIR, default_cocktails, load_json_file
from .simulation import Simulation
from .utils import clamp


SCOPE_NOTICE = (
    "OncoForge is for conceptual modeling and hypothesis generation only. "
    "It is not medical advice, not a clinical prediction tool, and not a treatment recommendation system."
)

SURFACE_MARKER_KEYS = {
    "EGFR_LIKE",
    "HER2_LIKE",
    "MUCIN_ABNORMAL",
    "TUMOR_PROTEASE_ACTIVITY",
    "CD47_LIKE",
    "COMPLEMENT_BINDING_LIKE",
}

SIGNAL_TO_CELL_FIELDS: Dict[str, Dict[str, float]] = {
    "DNA_DAMAGE_HIGH": {"dna_damage": 1.0, "genome_instability": 0.45},
    "REPLICATION_STRESS": {"proliferation_rate": 1.0},
    "P53_INACTIVE": {"pathways.p53_active": -1.0},
    "RB_INACTIVE": {"pathways.rb_active": -1.0},
    "MMR_DEFECT": {"pathways.mmr_active": -1.0, "mutation_burden": 0.65},
    "BRCA_DEFECT": {"pathways.brca_active": -1.0, "repair_capacity": -0.75},
    "PARP_DEPENDENCE": {"dna_damage": 0.70, "repair_capacity": -0.65},
    "MHC_LOW": {"mhc_expression": -1.0},
    "NEOANTIGEN_PRESENT": {"neoantigen_load": 1.0},
    "STRESS_LIGAND_HIGH": {"stress_ligand_expression": 1.0},
    "TELOMERASE_HIGH": {"telomerase_activity": 1.0},
    "HYPOXIA_HIGH": {"oxygen_need": 0.85, "hypoxia_tolerance": 0.85},
    "LACTATE_HIGH": {"lactate_output": 1.0},
    "PD_L1_HIGH": {"pd_l1_expression": 1.0, "immune_suppression_output": 0.45},
    "CASPASE_BLOCKED": {"pathways.caspase_accessible": -1.0, "apoptosis_resistance": 0.85},
    "ECM_INVASION_HIGH": {"invasion_potential": 1.0},
    "ANGIOGENESIS_SIGNAL": {"hypoxia_tolerance": 0.60, "invasion_potential": 0.35},
    "INFLAMMATION_HIGH": {"immune_suppression_output": 0.80},
    "APOPTOSIS_READY": {"apoptosis_sensitivity": 0.90},
    "PROTEASOME_STRESS": {"proliferation_rate": 0.55, "mutation_burden": 0.35},
    "UNFOLDED_PROTEIN_RESPONSE": {"hypoxia_tolerance": 0.45, "proliferation_rate": 0.35},
    "FERROPTOSIS_SUSCEPTIBLE": {"lactate_output": 0.55, "dna_damage": 0.45, "repair_capacity": -0.40},
    "CD47_DONT_EAT_ME": {"surface_markers.CD47_LIKE": 1.0, "immune_suppression_output": 0.35},
    "COMPLEMENT_SUSCEPTIBLE": {"surface_markers.COMPLEMENT_BINDING_LIKE": 1.0},
    "STING_DNA_SENSING": {"dna_damage": 0.65, "genome_instability": 0.55, "repair_capacity": -0.35},
    "AUTOPHAGY_DEPENDENCE": {"hypoxia_tolerance": 0.70, "lactate_output": 0.45},
    "MUCIN_ABNORMAL": {"surface_markers.MUCIN_ABNORMAL": 1.0},
    "TUMOR_PROTEASE_ACTIVITY": {"surface_markers.TUMOR_PROTEASE_ACTIVITY": 1.0},
    "EGFR_LIKE": {"surface_markers.EGFR_LIKE": 1.0},
    "HER2_LIKE": {"surface_markers.HER2_LIKE": 1.0},
}


@dataclass
class CancerProfile:
    id: str
    display_name: str
    category: str
    description: str
    evidence_label: str
    typical_markers: Dict[str, List[str]] = field(default_factory=dict)
    default_signal_biases: Dict[str, float] = field(default_factory=dict)
    default_pathway_biases: Dict[str, float] = field(default_factory=dict)
    microenvironment_biases: Dict[str, float] = field(default_factory=dict)
    expected_vulnerabilities: List[str] = field(default_factory=list)
    possible_escape_modes: List[str] = field(default_factory=list)
    starter_cocktails: List[str] = field(default_factory=list)
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CancerProfile":
        return cls(
            id=str(data.get("id", "")).strip(),
            display_name=str(data.get("display_name", data.get("id", ""))).strip(),
            category=str(data.get("category", "custom_profile")).strip(),
            description=str(data.get("description", "")).strip(),
            evidence_label=str(data.get("evidence_label", "inferred_interaction")).strip(),
            typical_markers={str(k): [str(x) for x in v] for k, v in dict(data.get("typical_markers", {})).items()},
            default_signal_biases={str(k): clamp(float(v)) for k, v in dict(data.get("default_signal_biases", {})).items()},
            default_pathway_biases={str(k): clamp(float(v)) for k, v in dict(data.get("default_pathway_biases", {})).items()},
            microenvironment_biases={str(k): clamp(float(v)) for k, v in dict(data.get("microenvironment_biases", {})).items()},
            expected_vulnerabilities=[str(x) for x in data.get("expected_vulnerabilities", [])],
            possible_escape_modes=[str(x) for x in data.get("possible_escape_modes", [])],
            starter_cocktails=[str(x) for x in data.get("starter_cocktails", [])],
            notes=str(data.get("notes", "")).strip(),
            tags=[str(x) for x in data.get("tags", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "category": self.category,
            "tags": list(self.tags),
            "description": self.description,
            "evidence_label": self.evidence_label,
            "typical_markers": self.typical_markers,
            "default_signal_biases": self.default_signal_biases,
            "default_pathway_biases": self.default_pathway_biases,
            "microenvironment_biases": self.microenvironment_biases,
            "expected_vulnerabilities": self.expected_vulnerabilities,
            "possible_escape_modes": self.possible_escape_modes,
            "starter_cocktails": self.starter_cocktails,
            "notes": self.notes,
            "scope_notice": SCOPE_NOTICE,
        }


def _key(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def load_cancer_profiles(path: Optional[str | Path] = None) -> List[CancerProfile]:
    data = json.loads(Path(path).read_text(encoding="utf-8")) if path else load_json_file("cancer_profiles.json")
    profiles = [CancerProfile.from_dict(item) for item in data]
    errors = validate_cancer_profiles(profiles)
    if errors:
        raise ValueError("Invalid cancer profile data: " + "; ".join(errors))
    return profiles


def validate_cancer_profiles(profiles: Iterable[CancerProfile]) -> List[str]:
    errors: List[str] = []
    seen = set()
    allowed_biases = set(SIGNALS) | set(SIGNAL_TO_CELL_FIELDS) | SURFACE_MARKER_KEYS
    for profile in profiles:
        if not profile.id:
            errors.append("profile missing id")
        if profile.id in seen:
            errors.append(f"duplicate profile id: {profile.id}")
        seen.add(profile.id)
        if not profile.display_name:
            errors.append(f"{profile.id}: missing display_name")
        if profile.evidence_label not in EVIDENCE_LABEL_TO_LEVEL:
            errors.append(f"{profile.id}: unknown evidence_label {profile.evidence_label}")
        for name, value in profile.default_signal_biases.items():
            if name not in allowed_biases:
                errors.append(f"{profile.id}: unknown signal/surface bias {name}")
            if not 0.0 <= float(value) <= 1.0:
                errors.append(f"{profile.id}: bias {name} outside 0-1")
        for name, value in profile.default_pathway_biases.items():
            if not 0.0 <= float(value) <= 1.0:
                errors.append(f"{profile.id}: pathway bias {name} outside 0-1")
        for name, value in profile.microenvironment_biases.items():
            if not 0.0 <= float(value) <= 1.0:
                errors.append(f"{profile.id}: microenvironment bias {name} outside 0-1")
    return errors


def find_cancer_profile(name: str, profiles: Optional[Iterable[CancerProfile]] = None) -> CancerProfile:
    profile_list = list(profiles or load_cancer_profiles())
    requested = _key(name)
    matches: List[CancerProfile] = []
    for profile in profile_list:
        keys = {_key(profile.id), _key(profile.display_name)}
        if requested in keys:
            return profile
        if any(key.startswith(requested) or requested in key for key in keys):
            matches.append(profile)
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(profile.id for profile in profile_list)
    raise ValueError(f"Unknown cancer profile: {name}. Available: {available}")


def filter_cancer_profiles(search: str = "", category: str = "") -> List[CancerProfile]:
    search_key = _key(search)
    category_key = _key(category)
    profiles = load_cancer_profiles()
    out: List[CancerProfile] = []
    for profile in profiles:
        haystack = " ".join([profile.id, profile.display_name, profile.category, profile.description] + profile.tags)
        if search_key and search_key not in _key(haystack):
            continue
        if category_key and category_key not in _key(" ".join([profile.category] + profile.tags)):
            continue
        out.append(profile)
    return out


def profile_summary_text(profile: CancerProfile) -> str:
    marker_lines = []
    for group, markers in profile.typical_markers.items():
        marker_lines.append(f"- {group}: {', '.join(markers)}")
    return "\n".join(
        [
            SCOPE_NOTICE,
            "",
            f"{profile.display_name} ({profile.id})",
            f"Category: {profile.category}",
            f"Evidence: {profile.evidence_label}",
            "",
            profile.description,
            "",
            "Key marker groups:",
            *marker_lines,
            "",
            "Expected conceptual vulnerabilities: " + ", ".join(profile.expected_vulnerabilities or ["not recorded"]),
            "Possible escape modes: " + ", ".join(profile.possible_escape_modes or ["not recorded"]),
            "Starter cocktails: " + ", ".join(profile.starter_cocktails or ["not recorded"]),
            "",
            "Microenvironment tendencies:",
            json.dumps(profile.microenvironment_biases, indent=2, sort_keys=True),
            "",
            "Limitations:",
            profile.notes or "Conceptual profile only.",
        ]
    )


def _vary(value: float, heterogeneity: float, rng: random.Random) -> float:
    return clamp(float(value) + rng.uniform(-heterogeneity, heterogeneity))


def _set_pathway(cell: Cell, name: str, value: float) -> None:
    if hasattr(cell.pathways, name):
        setattr(cell.pathways, name, clamp(value))


def _apply_field(cell: Cell, field_name: str, value: float, direction: float) -> None:
    if field_name.startswith("pathways."):
        raw_name = field_name.split(".", 1)[1]
        _set_pathway(cell, raw_name, 1.0 - value if direction < 0 else value)
    elif field_name.startswith("surface_markers."):
        raw_name = field_name.split(".", 1)[1]
        cell.surface_markers[raw_name] = clamp(value)
    elif hasattr(cell, field_name):
        setattr(cell, field_name, clamp(1.0 - value if direction < 0 else value))


def apply_profile_to_cell(cell: Cell, profile: CancerProfile, rng: random.Random, heterogeneity: float = 0.15) -> None:
    """Bias one cancer cell toward a profile while preserving heterogeneity."""
    heterogeneity = clamp(heterogeneity)
    cell.cell_kind = "cancer"
    cell.tissue_type = profile.id
    for signal_name, base_value in profile.default_signal_biases.items():
        value = _vary(base_value, heterogeneity, rng)
        for field_name, direction in SIGNAL_TO_CELL_FIELDS.get(signal_name, {}).items():
            _apply_field(cell, field_name, value, direction)
    for pathway_name, base_value in profile.default_pathway_biases.items():
        _set_pathway(cell, pathway_name, _vary(base_value, heterogeneity, rng))
    cell.generate_signals()
    for signal_name, base_value in profile.default_signal_biases.items():
        if signal_name in cell.signals:
            cell.signals[signal_name] = _vary(base_value, heterogeneity * 0.50, rng)


def apply_profile_microenvironment(microenvironment: Microenvironment, profile: CancerProfile, strength: float = 1.0) -> None:
    strength = clamp(strength)
    for key, value in profile.microenvironment_biases.items():
        if hasattr(microenvironment, key):
            current = float(getattr(microenvironment, key))
            setattr(microenvironment, key, clamp(current * (1.0 - strength) + float(value) * strength))


def create_profile_simulation(
    profile: CancerProfile | str,
    *,
    healthy: int = 800,
    cancer: int = 200,
    seed: int = 1729,
    steps: int = 200,
    profile_strength: float = 1.0,
    profile_heterogeneity: float = 0.15,
    immune_pressure: Optional[float] = None,
    mutation_rate: Optional[float] = None,
    cocktail: Optional[Cocktail] = None,
) -> Simulation:
    selected = find_cancer_profile(profile) if isinstance(profile, str) else profile
    cfg = SimulationConfig(
        name=f"Profile run - {selected.display_name}",
        steps=int(steps),
        initial_healthy_cells=int(healthy),
        initial_cancer_cells=int(cancer),
        random_seed=int(seed),
        cancer_preset_name=selected.display_name,
    )
    if mutation_rate is not None:
        cfg.mutation_rate_multiplier = float(mutation_rate)
    sim = Simulation(cfg, cocktail=cocktail or default_cocktails()[-1])
    sim.reset()
    apply_profile_to_simulation(
        sim,
        selected,
        profile_strength=profile_strength,
        profile_heterogeneity=profile_heterogeneity,
        immune_pressure=immune_pressure,
    )
    return sim


def apply_profile_to_simulation(
    sim: Simulation,
    profile: CancerProfile,
    *,
    profile_strength: float = 1.0,
    profile_heterogeneity: float = 0.15,
    immune_pressure: Optional[float] = None,
) -> None:
    rng = sim.rng
    for cell in sim.cells:
        if cell.alive and cell.cell_kind == "cancer":
            apply_profile_to_cell(cell, profile, rng, heterogeneity=profile_heterogeneity * clamp(profile_strength))
            cell.generate_signals(sim.microenvironment.oxygen)
    apply_profile_microenvironment(sim.microenvironment, profile, strength=profile_strength)
    if immune_pressure is not None:
        sim.microenvironment.immune_pressure = clamp(float(immune_pressure))
    sim.cancer_profile = profile.to_dict()
    sim.config.cancer_preset_name = profile.display_name
    sim.capture_marker_snapshot("initial_profile")


def duplicate_profile_as_custom(profile: CancerProfile, custom_id: str, output_path: Optional[str | Path] = None) -> Path:
    payload = profile.to_dict()
    payload["id"] = custom_id
    payload["display_name"] = f"{profile.display_name} custom copy"
    payload["category"] = "custom_profile"
    payload["tags"] = list(set(payload.get("tags", []) + ["custom profile"]))
    target = Path(output_path or DATA_DIR / "custom_cancer_profiles.json")
    existing = []
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
    existing.append(payload)
    target.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    return target
