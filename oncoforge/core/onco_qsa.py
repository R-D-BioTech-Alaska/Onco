"""Exact QSA receipt for bounded oncology logic-gate candidate classes."""

from __future__ import annotations

import math
import time
from importlib import metadata
from typing import Any, Dict, Sequence

from .evidence import provenance_hash


QSA_ADVANTAGE_NOTE = (
    "No computational advantage is claimed. Version 1 classifies every candidate "
    "classically, then uses QSA to validate exact compressed marked/unmarked amplitude evolution."
)


def _next_power_of_two(value: int) -> int:
    return 1 << max(1, value - 1).bit_length()


def _base_receipt(
    problem_id: str,
    problem_hash: str,
    candidate_ids: Sequence[str],
    marked_ids: Sequence[str],
    logical_states: int,
    classical_elapsed_ms: float,
) -> Dict[str, Any]:
    candidate_hash = provenance_hash(list(candidate_ids))
    marked_hash = provenance_hash(list(marked_ids))
    oracle_hash = provenance_hash(
        {
            "candidate_hash": candidate_hash,
            "marked_hash": marked_hash,
            "logical_states": logical_states,
        }
    )
    return {
        "schema_version": "oncoforge.qsa_receipt.v1",
        "problem_id": problem_id,
        "problem_hash": problem_hash,
        "status": "not_executed",
        "representation": "SymmetryState.count_classes",
        "representation_certificate": {
            "eligible": False,
            "reason": "not evaluated",
            "candidate_count": len(candidate_ids),
            "marked_count": len(marked_ids),
            "logical_state_count": logical_states,
            "padded_state_count": logical_states - len(candidate_ids),
            "qubits": int(math.log2(logical_states)),
            "equivalence_classes": 2,
            "class_counts": [len(marked_ids), logical_states - len(marked_ids)],
            "oracle_hash": oracle_hash,
        },
        "classical_control": {
            "algorithm": "exact_bitset_gate_search_v1",
            "comparison_scope": "marked/unmarked candidate class evolution",
            "candidate_hash": candidate_hash,
            "marked_hash": marked_hash,
            "candidate_count": len(candidate_ids),
            "marked_count": len(marked_ids),
            "information_identical": True,
        },
        "runtime": {
            "classical_elapsed_ms": float(classical_elapsed_ms),
            "setup_elapsed_ms": 0.0,
            "solve_elapsed_ms": 0.0,
            "readout_elapsed_ms": 0.0,
        },
        "advantage_assessment": QSA_ADVANTAGE_NOTE,
        "limitations": [
            "QSA receives candidate class membership after classical candidate enumeration.",
            "The amplitude result validates the representation and transform, not target biology.",
            "Candidate evidence, normal-tissue exclusion, and experimental validation remain authoritative.",
        ],
    }


def _finish(receipt: Dict[str, Any]) -> Dict[str, Any]:
    stable = {key: value for key, value in receipt.items() if key not in {"runtime", "receipt_hash"}}
    receipt["receipt_hash"] = provenance_hash(stable)
    return receipt


def run_logic_gate_qsa(
    *,
    problem_id: str,
    problem_hash: str,
    candidate_ids: Sequence[str],
    marked_candidate_ids: Sequence[str],
    classical_elapsed_ms: float,
    max_logical_states: int = 1048576,
    execute: bool = True,
) -> Dict[str, Any]:
    candidates = [str(value) for value in candidate_ids]
    marked = [str(value) for value in marked_candidate_ids]
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate_ids must be unique")
    if len(set(marked)) != len(marked):
        raise ValueError("marked_candidate_ids must be unique")
    unknown = sorted(set(marked) - set(candidates))
    if unknown:
        raise ValueError(f"marked candidates are not in the candidate set: {', '.join(unknown)}")

    logical_states = _next_power_of_two(max(2, len(candidates)))
    receipt = _base_receipt(
        problem_id,
        problem_hash,
        candidates,
        marked,
        logical_states,
        classical_elapsed_ms,
    )
    certificate = receipt["representation_certificate"]
    if not execute:
        receipt["status"] = "disabled"
        certificate["reason"] = "QSA execution disabled by configuration"
        return _finish(receipt)
    if len(candidates) < 2:
        receipt["status"] = "ineligible"
        certificate["reason"] = "at least two candidates are required"
        return _finish(receipt)
    if not marked or len(marked) >= logical_states:
        receipt["status"] = "ineligible"
        certificate["reason"] = "marked class must be nonempty and smaller than the logical state space"
        return _finish(receipt)
    if logical_states > int(max_logical_states):
        receipt["status"] = "ineligible"
        certificate["reason"] = (
            f"logical state count {logical_states} exceeds configured limit {int(max_logical_states)}"
        )
        return _finish(receipt)

    certificate["eligible"] = True
    certificate["reason"] = (
        "Candidate states form exact marked and unmarked permutation-symmetric count classes"
    )
    try:
        from qsa import SymmetryState

        try:
            runtime_version = metadata.version("qubit-state-algebra")
        except metadata.PackageNotFoundError:
            runtime_version = "not_recorded"
        receipt["runtime_version"] = runtime_version
        marked_count = len(marked)
        unmarked_count = logical_states - marked_count
        setup_started = time.perf_counter()
        state = SymmetryState.from_counts(
            int(math.log2(logical_states)),
            [marked_count, unmarked_count],
        )
        receipt["runtime"]["setup_elapsed_ms"] = (time.perf_counter() - setup_started) * 1000.0

        theta = math.asin(math.sqrt(marked_count / logical_states))
        iterations = max(0, int(round(math.pi / (4.0 * theta) - 0.5)))
        solve_started = time.perf_counter()
        for _ in range(iterations):
            state.phase(0, math.pi)
            state.reflect()
        receipt["runtime"]["solve_elapsed_ms"] = (time.perf_counter() - solve_started) * 1000.0

        readout_started = time.perf_counter()
        observed = float(state.class_probability(0))
        receipt["runtime"]["readout_elapsed_ms"] = (time.perf_counter() - readout_started) * 1000.0
        expected = math.sin((2 * iterations + 1) * theta) ** 2
        error = abs(observed - expected)
        receipt["execution"] = {
            "iterations": iterations,
            "expected_marked_probability": expected,
            "observed_marked_probability": observed,
            "absolute_error": error,
            "analytic_tolerance": 1e-12,
            "analytic_match": error <= 1e-12,
            "state_output_hash": provenance_hash(
                {
                    "iterations": iterations,
                    "observed_marked_probability": observed,
                    "logical_states": logical_states,
                }
            ),
        }
        if error > 1e-12:
            certificate["eligible"] = False
            receipt["status"] = "rejected_validation_mismatch"
            receipt["fallback"] = "classical Pareto result retained; QSA output rejected"
        else:
            receipt["status"] = "executed_exact"
            receipt["fallback"] = "not_used"
    except Exception as exc:
        certificate["eligible"] = False
        receipt["status"] = "classical_fallback"
        receipt["fallback"] = "classical Pareto result retained"
        receipt["failure"] = f"{type(exc).__name__}: {exc}"
    return _finish(receipt)
