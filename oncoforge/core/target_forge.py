"""Tumor-versus-normal target and surface logic-gate discovery."""

from __future__ import annotations

import html
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .evidence import EvidenceFabric, canonical_json, provenance_hash
from .tumor_model import TargetMeasurement, TumorResearchModel


TARGET_FORGE_SCOPE = (
    "OncoForge Target Forge generates auditable research hypotheses from supplied evidence. "
    "It is not medical advice, a clinical prediction, or proof of therapeutic safety or efficacy."
)
TARGET_SIGNAL_FEATURES = {
    "surface_abundance",
    "antigen_density",
    "protein_abundance",
    "transcript_abundance",
}

EVIDENCE_CLASS_TO_TIER = {
    "synthetic_fixture": 0,
    "computational_prediction": 1,
    "predicted_structure": 1,
    "literature_inference": 1,
    "mechanistic_hypothesis": 1,
    "transcriptomic_observation": 3,
    "patient_multiomics": 4,
    "proteomic_detection": 4,
    "immunopeptidomic_detection": 4,
    "functional_screen": 5,
    "experimentally_validated": 6,
    "clinical_observation": 9,
}


@dataclass
class TargetForgeConfig:
    min_tumor_coverage: float = 0.60
    min_clone_coverage: float = 0.50
    max_normal_activation: float = 0.05
    max_critical_normal_activation: float = 0.0
    max_unknown_normal_fraction: float = 0.0
    max_unknown_clone_fraction: float = 0.0
    require_critical_normal_samples: bool = True
    require_dependency: bool = False
    min_dependency_support: float = 0.0
    max_targets: int = 16
    max_candidates: int = 1500
    max_results: int = 50
    feature_order: List[str] = field(
        default_factory=lambda: [
            "surface_abundance",
            "antigen_density",
            "protein_abundance",
        ]
    )
    allow_transcript_fallback: bool = False
    include_single_targets: bool = True
    include_and: bool = True
    include_or: bool = True
    include_and_not: bool = True
    use_qsa: bool = True
    qsa_max_logical_states: int = 1048576

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TargetForgeConfig":
        base = cls()
        unknown = sorted(set(data) - set(base.__dict__))
        if unknown:
            raise ValueError("unknown Target Forge config fields: " + ", ".join(unknown))
        for key, value in data.items():
            setattr(base, key, value)
        for name in (
            "min_tumor_coverage",
            "min_clone_coverage",
            "max_normal_activation",
            "max_critical_normal_activation",
            "max_unknown_normal_fraction",
            "max_unknown_clone_fraction",
            "min_dependency_support",
        ):
            if isinstance(getattr(base, name), bool):
                raise ValueError(f"{name} must be a number")
            value = float(getattr(base, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
            setattr(base, name, value)
        for name in ("max_targets", "max_candidates", "max_results", "qsa_max_logical_states"):
            if isinstance(getattr(base, name), bool):
                raise ValueError(f"{name} must be an integer")
            value = int(getattr(base, name))
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
            setattr(base, name, value)
        for name in (
            "require_dependency",
            "require_critical_normal_samples",
            "allow_transcript_fallback",
            "include_single_targets",
            "include_and",
            "include_or",
            "include_and_not",
            "use_qsa",
        ):
            if not isinstance(getattr(base, name), bool):
                raise ValueError(f"{name} must be true or false")
        if not isinstance(base.feature_order, list):
            raise ValueError("feature_order must be an array")
        base.feature_order = [str(value) for value in base.feature_order]
        unsupported_features = sorted(set(base.feature_order) - TARGET_SIGNAL_FEATURES)
        if unsupported_features:
            raise ValueError("unsupported target signal features: " + ", ".join(unsupported_features))
        if len(set(base.feature_order)) != len(base.feature_order):
            raise ValueError("feature_order cannot contain duplicates")
        if "transcript_abundance" in base.feature_order and not base.allow_transcript_fallback:
            raise ValueError("transcript_abundance requires allow_transcript_fallback=true")
        if base.allow_transcript_fallback and "transcript_abundance" not in base.feature_order:
            base.feature_order.append("transcript_abundance")
        if not base.feature_order:
            raise ValueError("feature_order cannot be empty")
        if not any((base.include_single_targets, base.include_and, base.include_or, base.include_and_not)):
            raise ValueError("at least one gate family must be enabled")
        return base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateDefinition:
    operation: str
    positive_targets: Tuple[str, ...]
    negative_targets: Tuple[str, ...] = ()

    @property
    def gate_id(self) -> str:
        return "GATE:" + provenance_hash(
            {
                "operation": self.operation,
                "positive_targets": self.positive_targets,
                "negative_targets": self.negative_targets,
            }
        )[:16]

    @property
    def expression(self) -> str:
        if self.operation == "SINGLE":
            return self.positive_targets[0]
        if self.operation == "AND":
            return f"{self.positive_targets[0]} AND {self.positive_targets[1]}"
        if self.operation == "OR":
            return f"{self.positive_targets[0]} OR {self.positive_targets[1]}"
        if self.operation == "AND_NOT":
            return f"{self.positive_targets[0]} AND NOT {self.negative_targets[0]}"
        return self.operation

    @property
    def sensor_count(self) -> int:
        return len(self.positive_targets) + len(self.negative_targets)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "operation": self.operation,
            "expression": self.expression,
            "positive_targets": list(self.positive_targets),
            "negative_targets": list(self.negative_targets),
            "sensor_count": self.sensor_count,
        }


@dataclass
class TargetSignal:
    target_id: str
    known_mask: int
    active_mask: int
    assertion_ids: List[str]
    evidence_classes: List[str]
    modality_counts: Dict[str, int]
    measurement_summary: List[Dict[str, Any]]


@dataclass
class GateResult:
    definition: GateDefinition
    tumor_coverage: float
    normal_activation: float
    critical_normal_activation: float
    clone_coverage: float
    patient_coverage: float
    dependency_support: float
    unknown_tumor_fraction: float
    unknown_normal_fraction: float
    unknown_critical_normal_count: int
    unknown_clone_fraction: float
    unknown_patient_fraction: float
    worst_positive_dropout_tumor_coverage: float
    worst_negative_dropout_normal_activation: float
    active_tumor_samples: List[str]
    active_normal_samples: List[str]
    unknown_normal_samples: List[str]
    assertion_ids: List[str]
    evidence_classes: List[str]
    eligible: bool
    rejection_reasons: List[str]
    pareto: bool = False

    @property
    def candidate_id(self) -> str:
        return self.definition.gate_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.definition.to_dict(),
            "candidate_id": self.candidate_id,
            "tumor_coverage": self.tumor_coverage,
            "normal_activation": self.normal_activation,
            "critical_normal_activation": self.critical_normal_activation,
            "clone_coverage": self.clone_coverage,
            "patient_coverage": self.patient_coverage,
            "dependency_support": self.dependency_support,
            "unknown_tumor_fraction": self.unknown_tumor_fraction,
            "unknown_normal_fraction": self.unknown_normal_fraction,
            "unknown_critical_normal_count": self.unknown_critical_normal_count,
            "unknown_clone_fraction": self.unknown_clone_fraction,
            "unknown_patient_fraction": self.unknown_patient_fraction,
            "worst_positive_dropout_tumor_coverage": self.worst_positive_dropout_tumor_coverage,
            "worst_negative_dropout_normal_activation": self.worst_negative_dropout_normal_activation,
            "active_tumor_samples": list(self.active_tumor_samples),
            "active_normal_samples": list(self.active_normal_samples),
            "unknown_normal_samples": list(self.unknown_normal_samples),
            "assertion_ids": list(self.assertion_ids),
            "evidence_classes": list(self.evidence_classes),
            "eligible": self.eligible,
            "rejection_reasons": list(self.rejection_reasons),
            "pareto": self.pareto,
        }


@dataclass
class CandidateHypothesis:
    hypothesis_id: str
    candidate_id: str
    title: str
    tumor_context: Dict[str, Any]
    biological_mechanism: str
    targets: List[str]
    modality: str
    required_biomarkers: List[Dict[str, Any]]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    normal_tissue_liabilities: Dict[str, Any]
    clone_coverage: float
    predicted_escape_routes: List[str]
    molecular_design_requirements: Dict[str, Any]
    uncertainty: Dict[str, Any]
    evidence_tier: int
    evidence_classes: List[str]
    qsa_receipt: Dict[str, Any]
    proposed_validation_experiment: Dict[str, Any]
    falsification_condition: str
    provenance: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DiscoveryMatrix:
    def __init__(self, model: TumorResearchModel, config: TargetForgeConfig) -> None:
        self.model = model
        self.config = config
        self.samples = sorted(model.samples.values(), key=lambda item: item.sample_id)
        self.sample_index = {sample.sample_id: index for index, sample in enumerate(self.samples)}
        self.universe_mask = (1 << len(self.samples)) - 1
        self.tumor_mask = self._sample_mask(sample.role == "tumor" for sample in self.samples)
        self.normal_mask = self._sample_mask(sample.role == "normal" for sample in self.samples)
        self.critical_normal_mask = self._sample_mask(
            sample.role == "normal" and sample.critical_normal for sample in self.samples
        )
        self.signals = {
            target_id: self._build_signal(target_id)
            for target_id in sorted(model.targets)
        }

    @staticmethod
    def _sample_mask(values: Iterable[bool]) -> int:
        mask = 0
        for index, value in enumerate(values):
            if value:
                mask |= 1 << index
        return mask

    def _build_signal(self, target_id: str) -> TargetSignal:
        known_mask = 0
        active_mask = 0
        assertion_ids: List[str] = []
        classes = set()
        modalities: Dict[str, int] = {}
        summary_groups: Dict[Tuple[str, str], List[TargetMeasurement]] = {}
        for sample in self.samples:
            measurement = self.model.preferred_measurement(
                sample.sample_id,
                target_id,
                self.config.feature_order,
            )
            if measurement is None:
                continue
            bit = 1 << self.sample_index[sample.sample_id]
            known_mask |= bit
            if measurement.positive:
                active_mask |= bit
            assertion_ids.append(measurement.assertion_id)
            classes.add(measurement.evidence_class)
            modalities[measurement.feature] = modalities.get(measurement.feature, 0) + 1
            summary_groups.setdefault((measurement.feature, measurement.unit), []).append(measurement)
        summaries = []
        for (feature, unit), rows in sorted(summary_groups.items()):
            values = [row.value for row in rows]
            thresholds = sorted({row.positive_threshold for row in rows})
            directions = sorted({row.direction for row in rows})
            summaries.append(
                {
                    "feature": feature,
                    "unit": unit,
                    "count": len(values),
                    "minimum": min(values),
                    "median": median(values),
                    "maximum": max(values),
                    "positive_thresholds": thresholds,
                    "directions": directions,
                }
            )
        return TargetSignal(
            target_id=target_id,
            known_mask=known_mask,
            active_mask=active_mask,
            assertion_ids=sorted(assertion_ids),
            evidence_classes=sorted(classes),
            modality_counts=dict(sorted(modalities.items())),
            measurement_summary=summaries,
        )

    def sample_ids(self, mask: int) -> List[str]:
        return [sample.sample_id for index, sample in enumerate(self.samples) if mask & (1 << index)]

    def target_masks(self, target_id: str, forced_false: Sequence[str] = ()) -> Tuple[int, int]:
        if target_id in forced_false:
            return self.universe_mask, 0
        signal = self.signals[target_id]
        return signal.known_mask, signal.active_mask

    def gate_masks(self, definition: GateDefinition, forced_false: Sequence[str] = ()) -> Tuple[int, int]:
        first_known, first_active = self.target_masks(definition.positive_targets[0], forced_false)
        if definition.operation == "SINGLE":
            return first_known, first_active
        if definition.operation in {"AND", "OR"}:
            second_known, second_active = self.target_masks(definition.positive_targets[1], forced_false)
            if definition.operation == "AND":
                return _and_masks(first_known, first_active, second_known, second_active, self.universe_mask)
            return _or_masks(first_known, first_active, second_known, second_active, self.universe_mask)
        negative_known, negative_active = self.target_masks(definition.negative_targets[0], forced_false)
        not_active = negative_known & ~negative_active & self.universe_mask
        return _and_masks(first_known, first_active, negative_known, not_active, self.universe_mask)


def _and_masks(
    first_known: int,
    first_active: int,
    second_known: int,
    second_active: int,
    universe: int,
) -> Tuple[int, int]:
    first_false = first_known & ~first_active & universe
    second_false = second_known & ~second_active & universe
    known = (first_known & second_known) | first_false | second_false
    active = first_active & second_active
    return known & universe, active & universe


def _or_masks(
    first_known: int,
    first_active: int,
    second_known: int,
    second_active: int,
    universe: int,
) -> Tuple[int, int]:
    known = (first_known & second_known) | first_active | second_active
    active = first_active | second_active
    return known & universe, active & universe


def _fraction(mask: int, universe: int) -> float:
    total = universe.bit_count()
    return (mask & universe).bit_count() / total if total else 0.0


def _group_coverage(matrix: DiscoveryMatrix, active_mask: int, attribute: str) -> Tuple[float, float]:
    groups: Dict[str, int] = {}
    missing = 0
    tumor_count = 0
    for index, sample in enumerate(matrix.samples):
        if sample.role != "tumor":
            continue
        tumor_count += 1
        value = str(getattr(sample, attribute))
        if not value:
            missing += 1
            continue
        groups[value] = groups.get(value, 0) | (1 << index)
    if not groups:
        return 0.0, missing / tumor_count if tumor_count else 0.0
    covered = sum(1 for mask in groups.values() if active_mask & mask)
    return covered / len(groups), missing / tumor_count if tumor_count else 0.0


def _dependency_support(model: TumorResearchModel, target_ids: Sequence[str]) -> float:
    tumor_samples = model.samples_by_role("tumor")
    if not tumor_samples:
        return 0.0
    supported = 0
    for sample in tumor_samples:
        values = [
            measurement
            for target_id in target_ids
            for measurement in model.find_measurements(
                sample_id=sample.sample_id,
                target_id=target_id,
                feature="dependency_effect",
            )
        ]
        if values and any(measurement.positive for measurement in values):
            supported += 1
    return supported / len(tumor_samples)


def _evaluate_gate(
    matrix: DiscoveryMatrix,
    definition: GateDefinition,
    config: TargetForgeConfig,
) -> GateResult:
    known, active = matrix.gate_masks(definition)
    tumor_active = active & matrix.tumor_mask
    normal_active = active & matrix.normal_mask
    critical_active = active & matrix.critical_normal_mask
    unknown = ~known & matrix.universe_mask
    unknown_tumor = unknown & matrix.tumor_mask
    unknown_normal = unknown & matrix.normal_mask
    unknown_critical = unknown & matrix.critical_normal_mask
    tumor_coverage = _fraction(tumor_active, matrix.tumor_mask)
    normal_activation = _fraction(normal_active, matrix.normal_mask)
    critical_activation = _fraction(critical_active, matrix.critical_normal_mask)
    unknown_tumor_fraction = _fraction(unknown_tumor, matrix.tumor_mask)
    unknown_normal_fraction = _fraction(unknown_normal, matrix.normal_mask)
    clone_coverage, unknown_clone_fraction = _group_coverage(matrix, tumor_active, "clone_id")
    patient_coverage, unknown_patient_fraction = _group_coverage(matrix, tumor_active, "patient_id")
    dependency_support = _dependency_support(matrix.model, definition.positive_targets)

    dropout_coverages = []
    for target_id in definition.positive_targets:
        _, dropout_active = matrix.gate_masks(definition, forced_false=(target_id,))
        dropout_coverages.append(_fraction(dropout_active & matrix.tumor_mask, matrix.tumor_mask))
    worst_positive_dropout = min(dropout_coverages) if dropout_coverages else tumor_coverage

    negative_dropout = normal_activation
    if definition.negative_targets:
        _, dropout_active = matrix.gate_masks(definition, forced_false=definition.negative_targets)
        negative_dropout = _fraction(dropout_active & matrix.normal_mask, matrix.normal_mask)

    reasons = []
    if config.require_critical_normal_samples and not matrix.critical_normal_mask:
        reasons.append("no critical-normal samples are defined")
    if tumor_coverage < config.min_tumor_coverage:
        reasons.append(f"tumor coverage {tumor_coverage:.3f} is below {config.min_tumor_coverage:.3f}")
    if clone_coverage < config.min_clone_coverage:
        reasons.append(f"clone coverage {clone_coverage:.3f} is below {config.min_clone_coverage:.3f}")
    if normal_activation > config.max_normal_activation:
        reasons.append(f"normal activation {normal_activation:.3f} exceeds {config.max_normal_activation:.3f}")
    if critical_activation > config.max_critical_normal_activation:
        reasons.append(
            f"critical-normal activation {critical_activation:.3f} exceeds "
            f"{config.max_critical_normal_activation:.3f}"
        )
    if unknown_normal_fraction > config.max_unknown_normal_fraction:
        reasons.append(
            f"unknown normal fraction {unknown_normal_fraction:.3f} exceeds "
            f"{config.max_unknown_normal_fraction:.3f}"
        )
    if unknown_clone_fraction > config.max_unknown_clone_fraction:
        reasons.append(
            f"unknown clone fraction {unknown_clone_fraction:.3f} exceeds "
            f"{config.max_unknown_clone_fraction:.3f}"
        )
    if unknown_critical:
        reasons.append(f"{unknown_critical.bit_count()} critical-normal samples lack decisive measurements")
    if config.require_dependency and dependency_support < config.min_dependency_support:
        reasons.append(
            f"dependency support {dependency_support:.3f} is below {config.min_dependency_support:.3f}"
        )

    target_ids = list(definition.positive_targets + definition.negative_targets)
    assertions = sorted(
        {
            assertion_id
            for target_id in target_ids
            for assertion_id in matrix.signals[target_id].assertion_ids
        }
    )
    classes = sorted(
        {
            evidence_class
            for target_id in target_ids
            for evidence_class in matrix.signals[target_id].evidence_classes
        }
    )
    return GateResult(
        definition=definition,
        tumor_coverage=tumor_coverage,
        normal_activation=normal_activation,
        critical_normal_activation=critical_activation,
        clone_coverage=clone_coverage,
        patient_coverage=patient_coverage,
        dependency_support=dependency_support,
        unknown_tumor_fraction=unknown_tumor_fraction,
        unknown_normal_fraction=unknown_normal_fraction,
        unknown_critical_normal_count=unknown_critical.bit_count(),
        unknown_clone_fraction=unknown_clone_fraction,
        unknown_patient_fraction=unknown_patient_fraction,
        worst_positive_dropout_tumor_coverage=worst_positive_dropout,
        worst_negative_dropout_normal_activation=negative_dropout,
        active_tumor_samples=matrix.sample_ids(tumor_active),
        active_normal_samples=matrix.sample_ids(normal_active),
        unknown_normal_samples=matrix.sample_ids(unknown_normal),
        assertion_ids=assertions,
        evidence_classes=classes,
        eligible=not reasons,
        rejection_reasons=reasons,
    )


def _candidate_sort_key(result: GateResult) -> Tuple[Any, ...]:
    return (
        not result.eligible,
        result.critical_normal_activation,
        result.normal_activation,
        result.unknown_normal_fraction,
        -result.tumor_coverage,
        -result.clone_coverage,
        -result.patient_coverage,
        -result.dependency_support,
        result.definition.sensor_count,
        result.definition.expression,
    )


def _dominates(first: GateResult, second: GateResult) -> bool:
    maximize = (
        (first.tumor_coverage, second.tumor_coverage),
        (first.clone_coverage, second.clone_coverage),
        (first.patient_coverage, second.patient_coverage),
        (first.dependency_support, second.dependency_support),
        (
            first.worst_positive_dropout_tumor_coverage,
            second.worst_positive_dropout_tumor_coverage,
        ),
    )
    minimize = (
        (first.normal_activation, second.normal_activation),
        (first.critical_normal_activation, second.critical_normal_activation),
        (first.unknown_normal_fraction, second.unknown_normal_fraction),
        (
            first.worst_negative_dropout_normal_activation,
            second.worst_negative_dropout_normal_activation,
        ),
        (first.definition.sensor_count, second.definition.sensor_count),
    )
    no_worse = all(left >= right for left, right in maximize) and all(
        left <= right for left, right in minimize
    )
    strictly_better = any(left > right for left, right in maximize) or any(
        left < right for left, right in minimize
    )
    return no_worse and strictly_better


def pareto_front(results: Sequence[GateResult]) -> List[GateResult]:
    eligible = [result for result in results if result.eligible]
    front = []
    for candidate in eligible:
        if any(_dominates(other, candidate) for other in eligible if other is not candidate):
            continue
        candidate.pareto = True
        front.append(candidate)
    return sorted(front, key=_candidate_sort_key)


def _select_targets(matrix: DiscoveryMatrix, config: TargetForgeConfig) -> Tuple[List[str], List[str]]:
    singles = [
        _evaluate_gate(matrix, GateDefinition("SINGLE", (target_id,)), config)
        for target_id in sorted(matrix.signals)
    ]
    positive_order = sorted(
        singles,
        key=lambda result: (
            -result.tumor_coverage,
            -result.clone_coverage,
            result.unknown_tumor_fraction,
            result.critical_normal_activation,
            result.normal_activation,
            result.definition.expression,
        ),
    )
    exclusion_order = sorted(
        singles,
        key=lambda result: (
            result.tumor_coverage,
            -result.critical_normal_activation,
            -result.normal_activation,
            result.unknown_normal_fraction,
            result.definition.expression,
        ),
    )
    exclusion_slots = 1 if config.max_targets > 1 else 0
    if config.max_targets >= 8:
        exclusion_slots = max(2, config.max_targets // 4)
    positive_slots = config.max_targets - exclusion_slots
    selected: List[str] = []
    for result in positive_order[:positive_slots]:
        selected.append(result.definition.positive_targets[0])
    for result in exclusion_order:
        target_id = result.definition.positive_targets[0]
        if target_id not in selected:
            selected.append(target_id)
        if len(selected) >= config.max_targets:
            break
    full_order = [result.definition.positive_targets[0] for result in positive_order]
    excluded = [target_id for target_id in full_order if target_id not in selected]
    return selected, excluded


def _gate_definitions(target_ids: Sequence[str], config: TargetForgeConfig) -> List[GateDefinition]:
    definitions: List[GateDefinition] = []
    if config.include_single_targets:
        definitions.extend(GateDefinition("SINGLE", (target_id,)) for target_id in target_ids)
    for first_index, first in enumerate(target_ids):
        for second in target_ids[first_index + 1 :]:
            if config.include_and:
                definitions.append(GateDefinition("AND", (first, second)))
            if config.include_or:
                definitions.append(GateDefinition("OR", (first, second)))
    if config.include_and_not:
        for positive in target_ids:
            for negative in target_ids:
                if positive != negative:
                    definitions.append(GateDefinition("AND_NOT", (positive,), (negative,)))
    if len(definitions) > config.max_candidates:
        raise ValueError(
            f"gate search requires {len(definitions)} candidates, above max_candidates={config.max_candidates}; "
            "lower max_targets or disable a gate family"
        )
    return definitions


def _threshold_requirements(matrix: DiscoveryMatrix, target_ids: Sequence[str]) -> List[Dict[str, Any]]:
    requirements = []
    for target_id in target_ids:
        signal = matrix.signals[target_id]
        requirements.append(
            {
                "target_id": target_id,
                "preferred_modalities": list(matrix.config.feature_order),
                "observed_modalities": dict(signal.modality_counts),
                "measurement_summary": list(signal.measurement_summary),
            }
        )
    return requirements


def _contradictions(fabric: EvidenceFabric, assertion_ids: Sequence[str]) -> List[str]:
    selected = set(assertion_ids)
    contradictions = set()
    for assertion_id in selected:
        assertion = fabric.assertions[assertion_id]
        contradictions.update(assertion.contradicts)
    for assertion in fabric.assertions.values():
        if selected.intersection(assertion.contradicts):
            contradictions.add(assertion.assertion_id)
    return sorted(contradictions)


def _evidence_tier(fabric: EvidenceFabric, assertion_ids: Sequence[str]) -> int:
    return max(
        (EVIDENCE_CLASS_TO_TIER.get(fabric.assertions[value].evidence_class, 0) for value in assertion_ids),
        default=0,
    )


def _stable_qsa_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in receipt.items()
        if key != "runtime"
    }


def _build_hypothesis(
    result: GateResult,
    matrix: DiscoveryMatrix,
    fabric: EvidenceFabric,
    qsa_receipt: Dict[str, Any],
) -> CandidateHypothesis:
    target_ids = list(result.definition.positive_targets + result.definition.negative_targets)
    payload = {
        "candidate_id": result.candidate_id,
        "model_hash": matrix.model.model_hash,
        "assertion_ids": result.assertion_ids,
        "config": matrix.config.to_dict(),
    }
    hypothesis_id = "HYPOTHESIS:" + provenance_hash(payload)[:20]
    mechanism = (
        "Surface-recognition logic gate using measured or explicitly modeled target abundance. "
        "Activation is constrained by the supplied tumor and normal sample evidence."
    )
    escape_routes = [
        f"loss or downregulation of positive sensor {target_id}"
        for target_id in result.definition.positive_targets
    ]
    if result.unknown_tumor_fraction:
        escape_routes.append("unmeasured tumor states may lack one or more required sensors")
    uncertainty = {
        "unknown_tumor_fraction": result.unknown_tumor_fraction,
        "unknown_normal_fraction": result.unknown_normal_fraction,
        "unknown_critical_normal_count": result.unknown_critical_normal_count,
        "unknown_clone_fraction": result.unknown_clone_fraction,
        "unknown_patient_fraction": result.unknown_patient_fraction,
        "positive_sensor_dropout_tumor_coverage": result.worst_positive_dropout_tumor_coverage,
        "negative_sensor_dropout_normal_activation": result.worst_negative_dropout_normal_activation,
        "thresholds_are_dataset_specific": True,
        "independent_validation_required": True,
    }
    proposed_experiment = {
        "question": f"Does {result.definition.expression} separate malignant from critical normal cells?",
        "minimum_design": [
            "independent tumor and matched normal samples",
            "surface-protein measurement by flow cytometry, imaging, or targeted proteomics",
            "single-cell or clone-resolved sensor co-expression",
            "tumor-normal organoid functional test of the complete gate",
        ],
        "primary_observables": [
            "malignant-cell activation fraction",
            "critical-normal activation fraction",
            "antigen density and sensor co-expression",
            "escape after positive-sensor dropout",
        ],
        "validation_tier_target": 5,
    }
    contradiction_ids = _contradictions(fabric, result.assertion_ids)
    provisional = {
        "hypothesis_id": hypothesis_id,
        "candidate_id": result.candidate_id,
        "title": f"Evaluate surface gate: {result.definition.expression}",
        "tumor_context": {
            "project_id": matrix.model.project_id,
            "tumor_sample_count": matrix.tumor_mask.bit_count(),
            "normal_sample_count": matrix.normal_mask.bit_count(),
            "origin": matrix.model.origin,
        },
        "biological_mechanism": mechanism,
        "targets": target_ids,
        "modality": "logic_gated_surface_targeting_research_concept",
        "required_biomarkers": _threshold_requirements(matrix, target_ids),
        "supporting_evidence": list(result.assertion_ids),
        "contradicting_evidence": contradiction_ids,
        "normal_tissue_liabilities": {
            "activated_samples": list(result.active_normal_samples),
            "unknown_samples": list(result.unknown_normal_samples),
            "normal_activation": result.normal_activation,
            "critical_normal_activation": result.critical_normal_activation,
        },
        "clone_coverage": result.clone_coverage,
        "predicted_escape_routes": escape_routes,
        "molecular_design_requirements": {
            "gate_expression": result.definition.expression,
            "positive_sensors": list(result.definition.positive_targets),
            "negative_sensors": list(result.definition.negative_targets),
            "sequence_design_status": "not_started_target_biology_first",
        },
        "uncertainty": uncertainty,
        "evidence_tier": _evidence_tier(fabric, result.assertion_ids),
        "evidence_classes": list(result.evidence_classes),
        "qsa_receipt": _stable_qsa_receipt(qsa_receipt),
        "proposed_validation_experiment": proposed_experiment,
        "falsification_condition": (
            f"Reject if independent tumor coverage is below {matrix.config.min_tumor_coverage:.3f}, "
            f"normal activation exceeds {matrix.config.max_normal_activation:.3f}, or any critical-normal "
            "activation exceeds the configured bound."
        ),
    }
    return CandidateHypothesis(**provisional, provenance=provenance_hash(provisional))


def _software_commit() -> str:
    configured = os.environ.get("ONCOFORGE_COMMIT", "").strip()
    if configured:
        return configured
    try:
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "not_recorded"


def run_target_forge(
    evidence: EvidenceFabric | Dict[str, Any],
    config: TargetForgeConfig | Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    fabric = evidence if isinstance(evidence, EvidenceFabric) else EvidenceFabric.from_dict(evidence)
    cfg = config if isinstance(config, TargetForgeConfig) else TargetForgeConfig.from_dict(dict(config or {}))
    model = TumorResearchModel.from_evidence(fabric)
    matrix = DiscoveryMatrix(model, cfg)
    selected_targets, excluded_targets = _select_targets(matrix, cfg)
    definitions = _gate_definitions(selected_targets, cfg)
    started = time.perf_counter()
    results = [_evaluate_gate(matrix, definition, cfg) for definition in definitions]
    classical_ms = (time.perf_counter() - started) * 1000.0
    results.sort(key=_candidate_sort_key)
    front = pareto_front(results)
    marked_ids = [result.candidate_id for result in front]
    problem_hash = provenance_hash(
        {
            "model_hash": model.model_hash,
            "config": cfg.to_dict(),
            "candidate_ids": [result.candidate_id for result in results],
            "marked_ids": marked_ids,
        }
    )
    from .onco_qsa import run_logic_gate_qsa

    qsa_receipt = run_logic_gate_qsa(
        problem_id="ONCO_LOGIC_GATE:" + problem_hash[:20],
        problem_hash=problem_hash,
        candidate_ids=[result.candidate_id for result in results],
        marked_candidate_ids=marked_ids,
        classical_elapsed_ms=classical_ms,
        max_logical_states=cfg.qsa_max_logical_states,
        execute=cfg.use_qsa,
    )
    hypotheses = [
        _build_hypothesis(result, matrix, fabric, qsa_receipt)
        for result in front[: cfg.max_results]
    ]
    target_rows = [
        result.to_dict()
        for result in results
        if result.definition.operation == "SINGLE"
    ]
    report = {
        "schema_version": "oncoforge.target_forge.v1",
        "scope_notice": TARGET_FORGE_SCOPE,
        "software_commit": _software_commit(),
        "evidence_summary": fabric.summary(),
        "tumor_model": model.to_dict(include_measurements=False),
        "config": cfg.to_dict(),
        "target_selection": {
            "selected_target_ids": selected_targets,
            "excluded_target_ids": excluded_targets,
            "selection_rule": (
                "bounded positive-sensor coverage ranking plus reserved normal-exclusion sensors; "
                "stable target id breaks ties"
            ),
        },
        "target_candidates": target_rows,
        "gate_candidates": [result.to_dict() for result in results],
        "pareto_candidate_ids": marked_ids,
        "qsa_receipt": qsa_receipt,
        "hypotheses": [hypothesis.to_dict() for hypothesis in hypotheses],
        "evidence_categories": {
            category: sorted(
                assertion.assertion_id
                for assertion in fabric.assertions.values()
                if assertion.claim_category == category
            )
            for category in (
                "MEASURED",
                "DERIVED",
                "PREDICTED",
                "INFERRED",
                "HYPOTHESIZED",
                "SIMULATED",
            )
        },
        "reproducibility": {
            "fabric_hash": fabric.fabric_hash,
            "input_file_hash": fabric.input_file_hash,
            "tumor_model_hash": model.model_hash,
            "problem_hash": problem_hash,
            "random_seed": None,
            "algorithm": "exact_bitset_gate_search_v1",
            "classical_elapsed_ms": classical_ms,
        },
        "limitations": [
            "Ranked candidates are hypotheses, not validated targets or treatments.",
            "Thresholds are inherited from source assertions and may not transfer across assays.",
            "Missing critical-normal evidence fails closed but cannot prove safety.",
            "The first slice evaluates bounded single- and two-sensor gates only.",
            "Bounded target preselection can exclude gates outside the configured target limit.",
            "The QSA receipt does not claim a computational advantage when oracle compilation enumerates candidates.",
        ],
    }
    report["evidence_categories"]["DERIVED"].extend(
        ["target_candidates", "gate_candidates", "pareto_candidate_ids"]
    )
    report["evidence_categories"]["HYPOTHESIZED"].extend(
        hypothesis.hypothesis_id for hypothesis in hypotheses
    )
    stable_report = json.loads(canonical_json(report))
    stable_report.get("reproducibility", {}).pop("classical_elapsed_ms", None)
    stable_report.get("qsa_receipt", {}).pop("runtime", None)
    report["report_hash"] = provenance_hash(stable_report)
    return report


def format_target_forge_summary(report: Dict[str, Any]) -> str:
    targets = report.get("target_candidates", [])
    gates = report.get("gate_candidates", [])
    accepted = [row for row in gates if row.get("eligible")]
    lines = [
        report.get("scope_notice", TARGET_FORGE_SCOPE),
        "",
        f"Project: {report.get('tumor_model', {}).get('project_id', '')}",
        f"Origin: {report.get('tumor_model', {}).get('origin', '')}",
        f"Target candidates: {len(targets)}",
        f"Gate candidates: {len(gates)}",
        f"Eligible gates: {len(accepted)}",
        f"Pareto hypotheses: {len(report.get('hypotheses', []))}",
    ]
    receipt = report.get("qsa_receipt", {})
    lines.append(
        f"QSA: {receipt.get('status', 'not_recorded')} / {receipt.get('representation', 'none')}"
    )
    for row in report.get("hypotheses", [])[:8]:
        liabilities = row.get("normal_tissue_liabilities", {})
        lines.append(
            f"- {row.get('title')}: clone {float(row.get('clone_coverage', 0.0)):.3f}, "
            f"normal {float(liabilities.get('normal_activation', 0.0)):.3f}, tier {row.get('evidence_tier')}"
        )
    return "\n".join(lines)


def export_target_forge_json(report: Dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return target


def export_target_forge_html(report: Dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    hypothesis_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('title', '')))}</td>"
        f"<td>{float(row.get('clone_coverage', 0.0)):.3f}</td>"
        f"<td>{float(row.get('normal_tissue_liabilities', {}).get('normal_activation', 0.0)):.3f}</td>"
        f"<td>{row.get('evidence_tier', 0)}</td>"
        f"<td>{html.escape(str(row.get('falsification_condition', '')))}</td>"
        "</tr>"
        for row in report.get("hypotheses", [])
    )
    rejected_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('expression', '')))}</td>"
        f"<td>{html.escape('; '.join(row.get('rejection_reasons', [])))}</td>"
        "</tr>"
        for row in report.get("gate_candidates", [])
        if not row.get("eligible")
    )
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>OncoForge Target Forge Report</title>
<style>body{{font-family:Arial,sans-serif;margin:28px;line-height:1.45}}table{{border-collapse:collapse;width:100%;margin:12px 0 24px}}th,td{{border:1px solid #bbb;padding:7px;text-align:left;vertical-align:top}}th{{background:#eee}}.notice{{padding:12px;background:#fff6d8;border:1px solid #d4b95f}}pre{{white-space:pre-wrap;background:#f4f4f4;padding:10px}}</style>
</head><body><h1>OncoForge Target + Gate Forge</h1>
<p class="notice">{html.escape(report.get('scope_notice', TARGET_FORGE_SCOPE))}</p>
<h2>Summary</h2><pre>{html.escape(format_target_forge_summary(report))}</pre>
<h2>Evidence and Reproducibility</h2><pre>{html.escape(json.dumps({'evidence': report.get('evidence_summary'), 'reproducibility': report.get('reproducibility')}, indent=2, sort_keys=True))}</pre>
<h2>Pareto Hypotheses</h2><table><tr><th>Hypothesis</th><th>Clone Coverage</th><th>Normal Activation</th><th>Evidence Tier</th><th>Falsification</th></tr>{hypothesis_rows}</table>
<h2>QSA Receipt</h2><pre>{html.escape(json.dumps(report.get('qsa_receipt', {}), indent=2, sort_keys=True))}</pre>
<h2>Rejected Candidates</h2><table><tr><th>Gate</th><th>Rejection Reasons</th></tr>{rejected_rows}</table>
<h2>Limitations</h2><ul>{''.join(f'<li>{html.escape(item)}</li>' for item in report.get('limitations', []))}</ul>
</body></html>"""
    target.write_text(body, encoding="utf-8")
    return target


def export_target_forge_report(report: Dict[str, Any], path: str | Path) -> Path:
    return export_target_forge_html(report, path) if Path(path).suffix.lower() == ".html" else export_target_forge_json(report, path)
