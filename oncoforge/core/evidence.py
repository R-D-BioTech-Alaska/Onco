"""Typed evidence records and provenance for research discovery work."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ENTITY_KINDS = {
    "CancerType",
    "TumorSubtype",
    "Sample",
    "Clone",
    "CellState",
    "NormalCellType",
    "Gene",
    "Transcript",
    "Isoform",
    "Mutation",
    "CopyNumberEvent",
    "Protein",
    "ProteinComplex",
    "ProteinSurfaceTarget",
    "PostTranslationalModification",
    "HLAAllele",
    "Peptide",
    "Neoantigen",
    "Protease",
    "ProteaseSubstrate",
    "Enzyme",
    "Metabolite",
    "Pathway",
    "Dependency",
    "SyntheticLethalPair",
    "ImmuneCell",
    "Ligand",
    "Receptor",
    "SpatialNiche",
    "Drug",
    "Binder",
    "Degrader",
    "Prodrug",
    "TherapeuticModality",
    "ResistanceState",
    "Experiment",
    "Publication",
}

EVIDENCE_CLASSES = {
    "experimentally_validated",
    "clinical_observation",
    "patient_multiomics",
    "functional_screen",
    "proteomic_detection",
    "immunopeptidomic_detection",
    "transcriptomic_observation",
    "predicted_structure",
    "computational_prediction",
    "literature_inference",
    "mechanistic_hypothesis",
    "synthetic_fixture",
}

CLAIM_CATEGORIES = {
    "MEASURED",
    "DERIVED",
    "PREDICTED",
    "INFERRED",
    "HYPOTHESIZED",
    "SIMULATED",
}

SOURCE_TYPES = {
    "dataset",
    "publication",
    "experiment",
    "model",
    "synthetic_fixture",
}

HASH_PATTERN = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def provenance_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _reject_unknown(data: Dict[str, Any], allowed: Iterable[str], label: str) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ValueError(f"{label}: unknown fields: {', '.join(unknown)}")


@dataclass
class BiologicalEntity:
    entity_id: str
    kind: str
    label: str
    identifiers: Dict[str, str] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entity_id = str(self.entity_id).strip()
        self.kind = str(self.kind).strip()
        self.label = str(self.label).strip()
        self.identifiers = {str(key): str(value) for key, value in self.identifiers.items()}
        self.aliases = [str(value) for value in self.aliases]
        if not self.entity_id or ":" not in self.entity_id:
            raise ValueError("entity_id must include a stable namespace, such as HGNC:3596")
        if self.kind not in ENTITY_KINDS:
            raise ValueError(f"unknown entity kind: {self.kind}")
        if not self.label:
            raise ValueError(f"{self.entity_id}: label is required")
        canonical_json(self.attributes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "kind": self.kind,
            "label": self.label,
            "identifiers": dict(self.identifiers),
            "aliases": list(self.aliases),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BiologicalEntity":
        _reject_unknown(
            data,
            {"entity_id", "kind", "label", "identifiers", "aliases", "attributes"},
            "entity",
        )
        return cls(
            entity_id=str(data.get("entity_id", "")),
            kind=str(data.get("kind", "")),
            label=str(data.get("label", "")),
            identifiers=dict(data.get("identifiers", {})),
            aliases=list(data.get("aliases", [])),
            attributes=dict(data.get("attributes", {})),
        )


@dataclass
class EvidenceSource:
    source_id: str
    title: str
    source_type: str
    version: str
    content_hash: str
    uri: str = ""
    accessed_on: str = ""
    license_note: str = ""
    transformation_history: List[str] = field(default_factory=list)
    identifier_mapping: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source_id = str(self.source_id).strip()
        self.title = str(self.title).strip()
        self.source_type = str(self.source_type).strip()
        self.version = str(self.version).strip()
        self.content_hash = str(self.content_hash).strip().lower()
        self.uri = str(self.uri).strip()
        self.accessed_on = str(self.accessed_on).strip()
        self.license_note = str(self.license_note).strip()
        self.transformation_history = [str(value) for value in self.transformation_history]
        self.identifier_mapping = {str(key): str(value) for key, value in self.identifier_mapping.items()}
        if not self.source_id or ":" not in self.source_id:
            raise ValueError("source_id must include a namespace")
        if not self.title or not self.version:
            raise ValueError(f"{self.source_id}: title and version are required")
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"{self.source_id}: unknown source_type {self.source_type}")
        if not HASH_PATTERN.fullmatch(self.content_hash):
            raise ValueError(f"{self.source_id}: content_hash must be a SHA-256 digest")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "source_type": self.source_type,
            "version": self.version,
            "content_hash": self.content_hash,
            "uri": self.uri,
            "accessed_on": self.accessed_on,
            "license_note": self.license_note,
            "transformation_history": list(self.transformation_history),
            "identifier_mapping": dict(self.identifier_mapping),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceSource":
        _reject_unknown(
            data,
            {
                "source_id", "title", "source_type", "version", "content_hash", "uri",
                "accessed_on", "license_note", "transformation_history", "identifier_mapping",
            },
            "source",
        )
        return cls(
            source_id=str(data.get("source_id", "")),
            title=str(data.get("title", "")),
            source_type=str(data.get("source_type", "")),
            version=str(data.get("version", "")),
            content_hash=str(data.get("content_hash", "")),
            uri=str(data.get("uri", "")),
            accessed_on=str(data.get("accessed_on", "")),
            license_note=str(data.get("license_note", "")),
            transformation_history=list(data.get("transformation_history", [])),
            identifier_mapping=dict(data.get("identifier_mapping", {})),
        )


@dataclass
class EvidenceContext:
    cancer_type: str = ""
    tumor_subtype: str = ""
    sample_id: str = ""
    cell_type: str = ""
    clone_id: str = ""
    tissue: str = ""
    assay: str = ""
    model_system: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "cancer_type": self.cancer_type,
            "tumor_subtype": self.tumor_subtype,
            "sample_id": self.sample_id,
            "cell_type": self.cell_type,
            "clone_id": self.clone_id,
            "tissue": self.tissue,
            "assay": self.assay,
            "model_system": self.model_system,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceContext":
        _reject_unknown(data, cls.__dataclass_fields__, "evidence context")
        return cls(**{key: str(data.get(key, "")) for key in cls.__dataclass_fields__})


@dataclass
class EvidenceAssertion:
    assertion_id: str
    subject_id: str
    relation: str
    source_id: str
    evidence_class: str
    claim_category: str
    value: Any
    object_id: str = ""
    unit: str = ""
    direction: str = ""
    context: EvidenceContext = field(default_factory=EvidenceContext)
    source_record_id: str = ""
    observed_on: str = ""
    statistics: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    contradicts: List[str] = field(default_factory=list)
    provenance: str = ""

    def __post_init__(self) -> None:
        self.assertion_id = str(self.assertion_id).strip()
        self.subject_id = str(self.subject_id).strip()
        self.object_id = str(self.object_id).strip()
        self.relation = str(self.relation).strip().upper()
        self.source_id = str(self.source_id).strip()
        self.evidence_class = str(self.evidence_class).strip()
        self.claim_category = str(self.claim_category).strip().upper()
        self.unit = str(self.unit).strip()
        self.direction = str(self.direction).strip()
        self.source_record_id = str(self.source_record_id).strip()
        self.observed_on = str(self.observed_on).strip()
        self.limitations = [str(value) for value in self.limitations]
        self.contradicts = [str(value) for value in self.contradicts]
        if isinstance(self.context, dict):
            self.context = EvidenceContext.from_dict(self.context)
        if not self.assertion_id or not self.subject_id or not self.relation:
            raise ValueError("assertion_id, subject_id, and relation are required")
        if ":" not in self.assertion_id:
            raise ValueError("assertion_id must include a stable namespace")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"{self.assertion_id}: unknown evidence_class {self.evidence_class}")
        if self.claim_category not in CLAIM_CATEGORIES:
            raise ValueError(f"{self.assertion_id}: unknown claim_category {self.claim_category}")
        canonical_json(self.value)
        canonical_json(self.statistics)
        expected = provenance_hash(self._provenance_payload())
        if self.provenance and self.provenance != expected:
            raise ValueError(f"{self.assertion_id}: provenance hash does not match assertion content")
        self.provenance = expected

    def _provenance_payload(self) -> Dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "subject_id": self.subject_id,
            "relation": self.relation,
            "object_id": self.object_id,
            "value": self.value,
            "unit": self.unit,
            "direction": self.direction,
            "context": self.context.to_dict(),
            "source_id": self.source_id,
            "source_record_id": self.source_record_id,
            "observed_on": self.observed_on,
            "evidence_class": self.evidence_class,
            "claim_category": self.claim_category,
            "statistics": self.statistics,
            "limitations": self.limitations,
            "contradicts": sorted(self.contradicts),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {**self._provenance_payload(), "provenance": self.provenance}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceAssertion":
        _reject_unknown(
            data,
            {
                "assertion_id", "subject_id", "relation", "object_id", "value", "unit",
                "direction", "context", "source_id", "source_record_id", "observed_on",
                "evidence_class", "claim_category", "statistics", "limitations", "contradicts",
                "provenance",
            },
            "assertion",
        )
        return cls(
            assertion_id=str(data.get("assertion_id", "")),
            subject_id=str(data.get("subject_id", "")),
            relation=str(data.get("relation", "")),
            object_id=str(data.get("object_id", "")),
            value=data.get("value"),
            unit=str(data.get("unit", "")),
            direction=str(data.get("direction", "")),
            context=EvidenceContext.from_dict(dict(data.get("context", {}))),
            source_id=str(data.get("source_id", "")),
            source_record_id=str(data.get("source_record_id", "")),
            observed_on=str(data.get("observed_on", "")),
            evidence_class=str(data.get("evidence_class", "")),
            claim_category=str(data.get("claim_category", "")),
            statistics=dict(data.get("statistics", {})),
            limitations=list(data.get("limitations", [])),
            contradicts=list(data.get("contradicts", [])),
            provenance=str(data.get("provenance", "")),
        )


@dataclass
class EvidenceFabric:
    project_id: str
    entities: Dict[str, BiologicalEntity] = field(default_factory=dict)
    sources: Dict[str, EvidenceSource] = field(default_factory=dict)
    assertions: Dict[str, EvidenceAssertion] = field(default_factory=dict)
    schema_version: str = "oncoforge.evidence.v1"
    input_file_hash: str = ""

    def add_entity(self, entity: BiologicalEntity) -> None:
        if entity.entity_id in self.entities:
            raise ValueError(f"duplicate entity: {entity.entity_id}")
        self.entities[entity.entity_id] = entity

    def add_source(self, source: EvidenceSource) -> None:
        if source.source_id in self.sources:
            raise ValueError(f"duplicate source: {source.source_id}")
        self.sources[source.source_id] = source

    def add_assertion(self, assertion: EvidenceAssertion) -> None:
        if assertion.assertion_id in self.assertions:
            raise ValueError(f"duplicate assertion: {assertion.assertion_id}")
        self.assertions[assertion.assertion_id] = assertion

    def validate(self) -> None:
        if not self.project_id or ":" not in self.project_id:
            raise ValueError("project_id must include a stable namespace")
        for assertion in self.assertions.values():
            if assertion.subject_id not in self.entities:
                raise ValueError(f"{assertion.assertion_id}: unknown subject {assertion.subject_id}")
            if assertion.object_id and assertion.object_id not in self.entities:
                raise ValueError(f"{assertion.assertion_id}: unknown object {assertion.object_id}")
            if assertion.source_id not in self.sources:
                raise ValueError(f"{assertion.assertion_id}: unknown source {assertion.source_id}")
            for contradiction_id in assertion.contradicts:
                if contradiction_id == assertion.assertion_id:
                    raise ValueError(f"{assertion.assertion_id}: assertion cannot contradict itself")
                if contradiction_id not in self.assertions:
                    raise ValueError(f"{assertion.assertion_id}: unknown contradiction {contradiction_id}")

    def find_assertions(
        self,
        *,
        subject_id: str = "",
        relation: str = "",
        object_id: str = "",
        evidence_classes: Optional[Iterable[str]] = None,
    ) -> List[EvidenceAssertion]:
        allowed = set(evidence_classes or [])
        relation_key = relation.upper()
        rows = []
        for assertion in self.assertions.values():
            if subject_id and assertion.subject_id != subject_id:
                continue
            if relation_key and assertion.relation != relation_key:
                continue
            if object_id and assertion.object_id != object_id:
                continue
            if allowed and assertion.evidence_class not in allowed:
                continue
            rows.append(assertion)
        return sorted(rows, key=lambda item: item.assertion_id)

    @property
    def fabric_hash(self) -> str:
        return provenance_hash(
            {
                "schema_version": self.schema_version,
                "project_id": self.project_id,
                "entities": [self.entities[key].to_dict() for key in sorted(self.entities)],
                "sources": [self.sources[key].to_dict() for key in sorted(self.sources)],
                "assertions": [self.assertions[key].to_dict() for key in sorted(self.assertions)],
            }
        )

    def summary(self) -> Dict[str, Any]:
        classes: Dict[str, int] = {}
        categories: Dict[str, int] = {}
        for assertion in self.assertions.values():
            classes[assertion.evidence_class] = classes.get(assertion.evidence_class, 0) + 1
            categories[assertion.claim_category] = categories.get(assertion.claim_category, 0) + 1
        contradictions = {
            pair
            for assertion in self.assertions.values()
            for pair in [tuple(sorted((assertion.assertion_id, other))) for other in assertion.contradicts]
        }
        return {
            "project_id": self.project_id,
            "schema_version": self.schema_version,
            "entity_count": len(self.entities),
            "source_count": len(self.sources),
            "assertion_count": len(self.assertions),
            "evidence_classes": dict(sorted(classes.items())),
            "claim_categories": dict(sorted(categories.items())),
            "contradiction_count": len(contradictions),
            "fabric_hash": self.fabric_hash,
            "input_file_hash": self.input_file_hash,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "entities": [self.entities[key].to_dict() for key in sorted(self.entities)],
            "sources": [self.sources[key].to_dict() for key in sorted(self.sources)],
            "assertions": [self.assertions[key].to_dict() for key in sorted(self.assertions)],
            "fabric_hash": self.fabric_hash,
            "input_file_hash": self.input_file_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, input_file_hash: str = "") -> "EvidenceFabric":
        _reject_unknown(
            data,
            {
                "schema_version", "project_id", "entities", "sources", "assertions",
                "fabric_hash", "input_file_hash",
            },
            "evidence fabric",
        )
        fabric = cls(
            project_id=str(data.get("project_id", "")),
            schema_version=str(data.get("schema_version", "oncoforge.evidence.v1")),
            input_file_hash=input_file_hash,
        )
        if fabric.schema_version != "oncoforge.evidence.v1":
            raise ValueError(f"unsupported evidence schema: {fabric.schema_version}")
        for row in data.get("entities", []):
            fabric.add_entity(BiologicalEntity.from_dict(dict(row)))
        for row in data.get("sources", []):
            fabric.add_source(EvidenceSource.from_dict(dict(row)))
        for row in data.get("assertions", []):
            fabric.add_assertion(EvidenceAssertion.from_dict(dict(row)))
        fabric.validate()
        supplied_hash = str(data.get("fabric_hash", ""))
        if supplied_hash and supplied_hash != fabric.fabric_hash:
            raise ValueError("fabric_hash does not match evidence content")
        return fabric


def load_evidence_fabric(path: str | Path) -> EvidenceFabric:
    source = Path(path)
    raw = source.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evidence file must contain one JSON object")
    return EvidenceFabric.from_dict(data, input_file_hash=hashlib.sha256(raw).hexdigest())


def save_evidence_fabric(fabric: EvidenceFabric, path: str | Path) -> None:
    fabric.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fabric.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
