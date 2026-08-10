"""Bounded QSA-style search planning for OncoForge.

This module turns OncoForge profile, signal, and cocktail outputs into a small
structural-search payload that a future QSA adapter can execute. QSA is optional:
without a backend, OncoForge uses a deterministic scorer so the portal and CLI
can still inspect the exact workload that would be handed to a quantum layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .cancer_profiles import CancerProfile, SCOPE_NOTICE, create_profile_simulation, find_cancer_profile
from .signal_interpreter import SIGNAL_GROUPS, analyze_signals
from .treatment_matcher import recommend_treatments
from .utils import clamp


QUANTUM_SCOPE_NOTICE = (
    SCOPE_NOTICE
    + " QSA/quantum search layers rank conceptual simulation hypotheses only; "
    "they do not create, validate, or recommend real cancer treatments."
)


@dataclass
class QuantumWorkloadLimits:
    max_candidates: int = 12
    max_marker_qubits: int = 16
    max_pair_terms: int = 48
    max_steps_per_candidate: int = 300
    max_qsa_seconds: int = 60
    max_component_states: int = 4096
    require_exact_or_reject: bool = True

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "QuantumWorkloadLimits":
        base = cls()
        for key, value in dict(data or {}).items():
            if hasattr(base, key):
                setattr(base, key, value)
        base.max_candidates = max(1, int(base.max_candidates))
        base.max_marker_qubits = max(1, int(base.max_marker_qubits))
        base.max_pair_terms = max(0, int(base.max_pair_terms))
        base.max_steps_per_candidate = max(1, int(base.max_steps_per_candidate))
        base.max_qsa_seconds = max(1, int(base.max_qsa_seconds))
        base.max_component_states = max(1, int(base.max_component_states))
        base.require_exact_or_reject = bool(base.require_exact_or_reject)
        return base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarkerQubit:
    index: int
    signal: str
    group: str
    weight: float
    cancer_mean: float = 0.0
    healthy_mean: float = 0.0
    targetability_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateCocktailState:
    index: int
    cocktail_name: str
    agents: List[str] = field(default_factory=list)
    matched_signals: List[str] = field(default_factory=list)
    base_score: float = 0.0
    predicted_selectivity: float = 0.0
    remission_suitability: float = 0.0
    healthy_overlap_penalty: float = 0.0
    inflammation_risk_penalty: float = 0.0
    broadness_penalty: float = 0.0
    signal_focus: float = 0.0
    structural_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuantumSearchRequest:
    profile_id: str
    profile_name: str
    marker_qubits: List[MarkerQubit]
    candidates: List[CandidateCocktailState]
    limits: QuantumWorkloadLimits
    objective_terms: List[Dict[str, Any]]
    portal_route: str = "/lab/oncoforge/api/qsa/jobs"
    source: str = "oncoforge.structural_search_plan"
    scope_notice: str = QUANTUM_SCOPE_NOTICE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "marker_qubits": [item.to_dict() for item in self.marker_qubits],
            "candidates": [item.to_dict() for item in self.candidates],
            "limits": self.limits.to_dict(),
            "objective_terms": list(self.objective_terms),
            "portal_route": self.portal_route,
            "source": self.source,
            "scope_notice": self.scope_notice,
        }


def _signal_group(signal: str) -> str:
    for group, names in SIGNAL_GROUPS.items():
        if signal in names:
            return group
    return "general_signal"


def _marker_weight(row: Dict[str, Any]) -> float:
    return clamp(
        float(row.get("targetability_score", 0.0)) * 0.58
        + max(float(row.get("difference", 0.0)), 0.0) * 0.22
        + float(row.get("cancer_prevalence", 0.0)) * 0.14
        - float(row.get("healthy_prevalence", 0.0)) * 0.10
    )


def _unique_signal_rows(rows: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    ranked = sorted(rows, key=_marker_weight, reverse=True)
    for row in ranked:
        signal = str(row.get("signal", "")).strip()
        if not signal or signal in seen:
            continue
        seen.add(signal)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _collect_marker_rows(interpretation: Dict[str, Any], limits: QuantumWorkloadLimits) -> List[MarkerQubit]:
    rows: List[Dict[str, Any]] = []
    for key in [
        "top_targetable_signals",
        "cancer_specific_signals",
        "escape_warnings",
        "immune_evasion_signals",
        "DNA_repair_defect_signals",
        "metabolic_stress_signals",
        "microenvironment_signals",
    ]:
        rows.extend(interpretation.get(key, []) or [])
    compact = _unique_signal_rows(rows, limits.max_marker_qubits)
    return [
        MarkerQubit(
            index=index,
            signal=str(row.get("signal", "")),
            group=_signal_group(str(row.get("signal", ""))),
            weight=_marker_weight(row),
            cancer_mean=float(row.get("cancer_mean", 0.0)),
            healthy_mean=float(row.get("healthy_mean", 0.0)),
            targetability_score=float(row.get("targetability_score", 0.0)),
        )
        for index, row in enumerate(compact)
    ]


def _candidate_focus(row: Dict[str, Any], marker_qubits: List[MarkerQubit]) -> float:
    matched = set(row.get("matched_signals", []) or [])
    weights = [marker.weight for marker in marker_qubits]
    total = sum(weights) or 1.0
    covered = sum(marker.weight for marker in marker_qubits if marker.signal in matched)
    return clamp(covered / total)


def _candidate_score(row: Dict[str, Any], focus: float) -> float:
    return clamp(
        float(row.get("score", 0.0)) * 0.42
        + float(row.get("predicted_selectivity", 0.0)) * 0.20
        + float(row.get("remission_suitability", 0.0)) * 0.12
        + focus * 0.18
        + (1.0 - float(row.get("broadness_penalty", 0.0))) * 0.06
        - float(row.get("healthy_overlap_penalty", 0.0)) * 0.18
        - float(row.get("inflammation_risk_penalty", 0.0)) * 0.12
    )


def _collect_candidates(recommendation: Dict[str, Any], marker_qubits: List[MarkerQubit], limits: QuantumWorkloadLimits) -> List[CandidateCocktailState]:
    rows = list(recommendation.get("ranked_cocktails", []) or [])
    out: List[CandidateCocktailState] = []
    for index, row in enumerate(rows[: limits.max_candidates]):
        focus = _candidate_focus(row, marker_qubits)
        out.append(
            CandidateCocktailState(
                index=index,
                cocktail_name=str(row.get("cocktail_name", "")),
                agents=[str(item) for item in row.get("agents", [])],
                matched_signals=[str(item) for item in row.get("matched_signals", [])],
                base_score=float(row.get("score", 0.0)),
                predicted_selectivity=float(row.get("predicted_selectivity", 0.0)),
                remission_suitability=float(row.get("remission_suitability", 0.0)),
                healthy_overlap_penalty=float(row.get("healthy_overlap_penalty", 0.0)),
                inflammation_risk_penalty=float(row.get("inflammation_risk_penalty", 0.0)),
                broadness_penalty=float(row.get("broadness_penalty", 0.0)),
                signal_focus=focus,
                structural_score=_candidate_score(row, focus),
            )
        )
    out.sort(key=lambda item: item.structural_score, reverse=True)
    for index, item in enumerate(out):
        item.index = index
    return out


def _objective_terms() -> List[Dict[str, Any]]:
    return [
        {"name": "maximize_marker_focus", "weight": 0.18, "direction": "maximize"},
        {"name": "maximize_predicted_selectivity", "weight": 0.20, "direction": "maximize"},
        {"name": "maximize_remission_suitability", "weight": 0.12, "direction": "maximize"},
        {"name": "penalize_healthy_overlap", "weight": 0.18, "direction": "minimize"},
        {"name": "penalize_inflammation_risk", "weight": 0.12, "direction": "minimize"},
        {"name": "penalize_broadness", "weight": 0.06, "direction": "minimize"},
        {"name": "respect_exact_resource_bounds", "weight": 1.00, "direction": "hard_gate"},
    ]


def build_quantum_search_request(
    *,
    profile: CancerProfile | str,
    interpretation: Optional[Dict[str, Any]] = None,
    recommendation: Optional[Dict[str, Any]] = None,
    limits: Optional[QuantumWorkloadLimits | Dict[str, Any]] = None,
) -> QuantumSearchRequest:
    selected = find_cancer_profile(profile) if isinstance(profile, str) else profile
    bounded_limits = limits if isinstance(limits, QuantumWorkloadLimits) else QuantumWorkloadLimits.from_dict(limits)
    if interpretation is None or recommendation is None:
        sim = create_profile_simulation(selected, healthy=80, cancer=40, steps=1)
        interpretation = interpretation or analyze_signals(sim, selected)
        recommendation = recommendation or recommend_treatments(sim=sim, profile=selected, interpretation=interpretation)
    marker_qubits = _collect_marker_rows(interpretation, bounded_limits)
    candidates = _collect_candidates(recommendation, marker_qubits, bounded_limits)
    return QuantumSearchRequest(
        profile_id=selected.id,
        profile_name=selected.display_name,
        marker_qubits=marker_qubits,
        candidates=candidates,
        limits=bounded_limits,
        objective_terms=_objective_terms(),
    )


def validate_quantum_request(request: QuantumSearchRequest) -> List[str]:
    errors: List[str] = []
    limits = request.limits
    if len(request.candidates) > limits.max_candidates:
        errors.append("candidate count exceeds max_candidates")
    if len(request.marker_qubits) > limits.max_marker_qubits:
        errors.append("marker qubit count exceeds max_marker_qubits")
    if len(request.candidates) * max(1, len(request.marker_qubits)) > limits.max_component_states:
        errors.append("candidate-marker component count exceeds max_component_states")
    if limits.require_exact_or_reject and not request.objective_terms:
        errors.append("exact-or-reject workload is missing objective terms")
    for marker in request.marker_qubits:
        if not 0.0 <= marker.weight <= 1.0:
            errors.append(f"marker weight outside 0-1: {marker.signal}")
    for candidate in request.candidates:
        if not 0.0 <= candidate.structural_score <= 1.0:
            errors.append(f"candidate score outside 0-1: {candidate.cocktail_name}")
    return errors


def run_quantum_strategy(request: QuantumSearchRequest, backend: Optional[Any] = None) -> Dict[str, Any]:
    errors = validate_quantum_request(request)
    if errors:
        return {
            "ok": False,
            "backend": "none",
            "scope_notice": QUANTUM_SCOPE_NOTICE,
            "errors": errors,
            "message": "Quantum strategy request rejected by workload limits.",
        }
    if backend is not None:
        runner = getattr(backend, "evaluate_oncoforge_candidates", None)
        if callable(runner):
            try:
                result = runner(request.to_dict())
                if isinstance(result, dict):
                    result.setdefault("scope_notice", QUANTUM_SCOPE_NOTICE)
                    result.setdefault("ok", True)
                    return result
            except Exception as exc:
                return {
                    "ok": False,
                    "backend": type(backend).__name__,
                    "scope_notice": QUANTUM_SCOPE_NOTICE,
                    "errors": [str(exc)],
                    "message": "QSA backend rejected or failed the bounded workload.",
                }
        return {
            "ok": False,
            "backend": type(backend).__name__,
            "scope_notice": QUANTUM_SCOPE_NOTICE,
            "errors": ["backend missing evaluate_oncoforge_candidates(request_dict)"],
            "message": "QSA backend adapter does not match the OncoForge contract.",
        }
    ranked = [candidate.to_dict() for candidate in request.candidates]
    return {
        "ok": True,
        "backend": "deterministic_structural_fallback",
        "scope_notice": QUANTUM_SCOPE_NOTICE,
        "profile_id": request.profile_id,
        "profile_name": request.profile_name,
        "marker_qubits": [item.to_dict() for item in request.marker_qubits],
        "ranked_candidates": ranked,
        "best_candidate": ranked[0] if ranked else None,
        "message": "No QSA backend was attached; used the bounded deterministic structural scorer.",
    }


def format_quantum_strategy_summary(result: Dict[str, Any]) -> str:
    lines = [
        result.get("scope_notice", QUANTUM_SCOPE_NOTICE),
        "",
        f"Backend: {result.get('backend', 'unknown')}",
        f"Profile: {result.get('profile_name', '') or result.get('profile_id', '')}",
    ]
    if not result.get("ok"):
        lines.append("Rejected:")
        for error in result.get("errors", []):
            lines.append(f"- {error}")
        return "\n".join(lines)
    best = result.get("best_candidate") or {}
    if best:
        lines.extend(
            [
                f"Best structural candidate: {best.get('cocktail_name')}",
                f"Structural score: {float(best.get('structural_score', 0.0)):.3f}",
                f"Signal focus: {float(best.get('signal_focus', 0.0)):.3f}",
            ]
        )
    lines.append("")
    lines.append(result.get("message", ""))
    return "\n".join(lines).strip()
