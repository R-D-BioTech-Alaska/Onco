"""Evidence-backed tumor and normal-tissue research model."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .evidence import EvidenceAssertion, EvidenceFabric, provenance_hash


TARGET_MEASUREMENT_RELATION = "TARGET_MEASUREMENT"
TARGET_FEATURES = {
    "transcript_abundance",
    "protein_abundance",
    "surface_abundance",
    "antigen_density",
    "spatial_accessibility",
    "dependency_effect",
    "shedding",
    "internalization",
}
MEASUREMENT_DIRECTIONS = {"higher_is_positive", "lower_is_positive"}
TARGET_ENTITY_KINDS = {"Gene", "Protein", "ProteinSurfaceTarget", "Receptor"}


@dataclass
class TumorSample:
    sample_id: str
    label: str
    role: str
    tissue: str = ""
    cell_type: str = ""
    clone_id: str = ""
    patient_id: str = ""
    critical_normal: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_entity(cls, entity: Any) -> "TumorSample":
        attributes = dict(entity.attributes)
        role = str(attributes.get("role", "")).strip().lower()
        if role not in {"tumor", "normal"}:
            raise ValueError(f"{entity.entity_id}: sample role must be tumor or normal")
        return cls(
            sample_id=entity.entity_id,
            label=entity.label,
            role=role,
            tissue=str(attributes.get("tissue", "")),
            cell_type=str(attributes.get("cell_type", "")),
            clone_id=str(attributes.get("clone_id", "")),
            patient_id=str(attributes.get("patient_id", "")),
            critical_normal=bool(attributes.get("critical_normal", False)),
            attributes=attributes,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "label": self.label,
            "role": self.role,
            "tissue": self.tissue,
            "cell_type": self.cell_type,
            "clone_id": self.clone_id,
            "patient_id": self.patient_id,
            "critical_normal": self.critical_normal,
            "attributes": dict(self.attributes),
        }


@dataclass
class TargetMeasurement:
    assertion_id: str
    sample_id: str
    target_id: str
    feature: str
    value: float
    unit: str
    positive_threshold: float
    direction: str
    evidence_class: str
    claim_category: str
    source_id: str
    provenance: str

    @classmethod
    def from_assertion(cls, assertion: EvidenceAssertion) -> "TargetMeasurement":
        if assertion.relation != TARGET_MEASUREMENT_RELATION:
            raise ValueError(f"{assertion.assertion_id}: not a target measurement")
        if not assertion.object_id:
            raise ValueError(f"{assertion.assertion_id}: target measurement requires object_id")
        if not isinstance(assertion.value, dict):
            raise ValueError(f"{assertion.assertion_id}: measurement value must be an object")
        feature = str(assertion.value.get("feature", ""))
        if feature not in TARGET_FEATURES:
            raise ValueError(f"{assertion.assertion_id}: unsupported target feature {feature}")
        try:
            value = float(assertion.value["value"])
            threshold = float(assertion.value["positive_threshold"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{assertion.assertion_id}: value and positive_threshold must be numbers") from exc
        if not math.isfinite(value) or not math.isfinite(threshold):
            raise ValueError(f"{assertion.assertion_id}: measurement values must be finite")
        direction = str(assertion.value.get("direction", assertion.direction or "higher_is_positive"))
        if direction not in MEASUREMENT_DIRECTIONS:
            raise ValueError(f"{assertion.assertion_id}: unsupported direction {direction}")
        unit = str(assertion.value.get("unit", assertion.unit)).strip()
        if not unit:
            raise ValueError(f"{assertion.assertion_id}: measurement unit is required")
        return cls(
            assertion_id=assertion.assertion_id,
            sample_id=assertion.subject_id,
            target_id=assertion.object_id,
            feature=feature,
            value=value,
            unit=unit,
            positive_threshold=threshold,
            direction=direction,
            evidence_class=assertion.evidence_class,
            claim_category=assertion.claim_category,
            source_id=assertion.source_id,
            provenance=assertion.provenance,
        )

    @property
    def positive(self) -> bool:
        if self.direction == "lower_is_positive":
            return self.value <= self.positive_threshold
        return self.value >= self.positive_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "sample_id": self.sample_id,
            "target_id": self.target_id,
            "feature": self.feature,
            "value": self.value,
            "unit": self.unit,
            "positive_threshold": self.positive_threshold,
            "direction": self.direction,
            "positive": self.positive,
            "evidence_class": self.evidence_class,
            "claim_category": self.claim_category,
            "source_id": self.source_id,
            "provenance": self.provenance,
        }


@dataclass
class TumorResearchModel:
    project_id: str
    samples: Dict[str, TumorSample]
    targets: Dict[str, Dict[str, Any]]
    measurements: List[TargetMeasurement]
    evidence_fabric_hash: str
    source_assertion_ids: List[str]
    origin: str
    schema_version: str = "oncoforge.tumor_research_model.v1"

    @classmethod
    def from_evidence(cls, fabric: EvidenceFabric) -> "TumorResearchModel":
        fabric.validate()
        samples = {
            entity.entity_id: TumorSample.from_entity(entity)
            for entity in fabric.entities.values()
            if entity.kind == "Sample"
        }
        targets = {
            entity.entity_id: entity.to_dict()
            for entity in fabric.entities.values()
            if entity.kind in TARGET_ENTITY_KINDS
        }
        measurements: List[TargetMeasurement] = []
        for assertion in fabric.find_assertions(relation=TARGET_MEASUREMENT_RELATION):
            if assertion.subject_id not in samples:
                raise ValueError(f"{assertion.assertion_id}: measurement subject is not a Sample")
            if assertion.context.sample_id and assertion.context.sample_id != assertion.subject_id:
                raise ValueError(
                    f"{assertion.assertion_id}: context sample_id does not match measurement subject"
                )
            if assertion.object_id not in targets:
                raise ValueError(f"{assertion.assertion_id}: measurement object is not a target entity")
            measurements.append(TargetMeasurement.from_assertion(assertion))
        if not samples:
            raise ValueError("tumor research model requires sample entities")
        if not any(sample.role == "tumor" for sample in samples.values()):
            raise ValueError("tumor research model requires at least one tumor sample")
        if not any(sample.role == "normal" for sample in samples.values()):
            raise ValueError("tumor research model requires at least one normal sample")
        if not measurements:
            raise ValueError("tumor research model requires target measurements")
        source_ids = sorted(measurement.assertion_id for measurement in measurements)
        origin = (
            "synthetic_fixture"
            if all(measurement.evidence_class == "synthetic_fixture" for measurement in measurements)
            else "evidence_backed"
        )
        return cls(
            project_id=fabric.project_id,
            samples=samples,
            targets=targets,
            measurements=sorted(
                measurements,
                key=lambda item: (item.sample_id, item.target_id, item.feature, item.assertion_id),
            ),
            evidence_fabric_hash=fabric.fabric_hash,
            source_assertion_ids=source_ids,
            origin=origin,
        )

    def samples_by_role(self, role: str) -> List[TumorSample]:
        return sorted(
            (sample for sample in self.samples.values() if sample.role == role),
            key=lambda item: item.sample_id,
        )

    def find_measurements(
        self,
        *,
        sample_id: str = "",
        target_id: str = "",
        feature: str = "",
    ) -> List[TargetMeasurement]:
        rows = []
        for measurement in self.measurements:
            if sample_id and measurement.sample_id != sample_id:
                continue
            if target_id and measurement.target_id != target_id:
                continue
            if feature and measurement.feature != feature:
                continue
            rows.append(measurement)
        return rows

    def preferred_measurement(
        self,
        sample_id: str,
        target_id: str,
        feature_order: Iterable[str],
    ) -> Optional[TargetMeasurement]:
        by_feature: Dict[str, List[TargetMeasurement]] = {}
        for measurement in self.find_measurements(sample_id=sample_id, target_id=target_id):
            by_feature.setdefault(measurement.feature, []).append(measurement)
        for feature in feature_order:
            rows = by_feature.get(feature, [])
            if rows:
                signatures = {
                    (row.value, row.unit, row.positive_threshold, row.direction)
                    for row in rows
                }
                if len(signatures) > 1:
                    raise ValueError(
                        f"multiple nonidentical {feature} measurements for {sample_id} and {target_id}; "
                        "normalize or select one assay before discovery"
                    )
                return sorted(rows, key=lambda item: item.assertion_id)[0]
        return None

    @property
    def model_hash(self) -> str:
        return provenance_hash(
            {
                "schema_version": self.schema_version,
                "project_id": self.project_id,
                "evidence_fabric_hash": self.evidence_fabric_hash,
                "samples": [self.samples[key].to_dict() for key in sorted(self.samples)],
                "targets": [self.targets[key] for key in sorted(self.targets)],
                "measurements": [measurement.to_dict() for measurement in self.measurements],
                "origin": self.origin,
            }
        )

    def to_dict(self, *, include_measurements: bool = True) -> Dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "origin": self.origin,
            "evidence_fabric_hash": self.evidence_fabric_hash,
            "model_hash": self.model_hash,
            "samples": [self.samples[key].to_dict() for key in sorted(self.samples)],
            "targets": [self.targets[key] for key in sorted(self.targets)],
            "source_assertion_ids": list(self.source_assertion_ids),
        }
        if include_measurements:
            payload["measurements"] = [measurement.to_dict() for measurement in self.measurements]
        return payload
