"""Numerical helpers for OncoForge."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, Iterable, Mapping


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a numeric value to the inclusive interval [low, high]."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def coerce_float(value: Any, field_name: str = "value") -> float:
    """Convert user/data input to float with a field-specific error message."""
    if callable(value):
        raise ValueError(f"{field_name} must be numeric, got callable {value!r}.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric, got {value!r}.") from exc


def coerce_probability(value: Any, field_name: str = "value") -> float:
    """Convert a value to a clamped probability-like float."""
    return clamp(coerce_float(value, field_name))


def sigmoid(x: float, steepness: float = 6.0, midpoint: float = 0.5) -> float:
    """Stable sigmoid used for turning weighted signals into probabilities."""
    z = max(-60.0, min(60.0, steepness * (x - midpoint)))
    return 1.0 / (1.0 + math.exp(-z))


def weighted_average(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total_weight = 0.0
    total = 0.0
    for key, weight in weights.items():
        total += values.get(key, 0.0) * weight
        total_weight += abs(weight)
    if total_weight <= 1e-12:
        return 0.0
    return clamp(total / total_weight)


def noisy(value: float, spread: float, rng: random.Random) -> float:
    """Add bounded noise while keeping the result in [0, 1]."""
    return clamp(value + rng.uniform(-spread, spread))


def normalize_signal_dict(values: Mapping[str, float], keys: Iterable[str]) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    for key in keys:
        normalized[key] = coerce_probability(values.get(key, 0.0), f"signal {key}")
    return normalized


def event(probability: float, rng: random.Random) -> bool:
    return rng.random() < clamp(probability)
