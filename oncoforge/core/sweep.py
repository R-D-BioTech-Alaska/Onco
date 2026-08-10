"""Parameter sweep utilities for OncoForge.

Sweeps are useful for asking questions like: "Does this result depend on the
exact treatment strength?" or "Does hypoxia change the cocktail ranking?"
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .automation import lookup_named
from .interpretation import assess_cure_pathway
from .models import Cocktail, Microenvironment, SimulationConfig
from .presets import default_cocktails, load_cancer_presets
from .simulation import Simulation


@dataclass
class SweepResult:
    parameter: str
    value: float
    seed: int
    steps: int
    cocktail_name: str
    preset_name: str
    final_healthy: int
    final_cancer: int
    final_dead: int
    final_inflammation: float
    final_immune_pressure: float
    final_treatment_intensity: float
    dosing_phase: str
    total_healthy_damage_events: int
    total_escape_events: int
    cure_pathway_classification: str
    cure_pathway_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_CONFIG_ALIASES = {
    "treatment": "treatment_strength_multiplier",
    "treatment_strength": "treatment_strength_multiplier",
    "immune": "immune_strength_multiplier",
    "immune_strength": "immune_strength_multiplier",
    "mutation": "mutation_rate_multiplier",
    "mutation_rate": "mutation_rate_multiplier",
    "recovery": "recovery_rate",
    "surveillance_intensity": "remission_surveillance_intensity",
    "adaptive_minimum": "adaptive_minimum_intensity",
    "zero_confirmation": "zero_cancer_confirmation_steps",
    "zero_confirmation_steps": "zero_cancer_confirmation_steps",
}

_MICRO_ALIASES = {
    "oxygen": "oxygen",
    "glucose": "glucose",
    "acidity": "acidity",
    "inflammation": "inflammation",
    "immune_pressure": "immune_pressure",
    "stromal_barrier": "stromal_barrier",
    "vascular_support": "vascular_support",
}


def _normalize_parameter(parameter: str) -> tuple[str, str]:
    raw = str(parameter).strip()
    if "." in raw:
        scope, name = raw.split(".", 1)
        scope = scope.lower().strip()
        name = name.strip()
        if scope in {"config", "cfg"}:
            return "config", _CONFIG_ALIASES.get(name, name)
        if scope in {"micro", "microenvironment", "env"}:
            return "microenvironment", _MICRO_ALIASES.get(name, name)
    key = raw.lower().strip()
    if key in _CONFIG_ALIASES:
        return "config", _CONFIG_ALIASES[key]
    if key in _MICRO_ALIASES:
        return "microenvironment", _MICRO_ALIASES[key]
    if hasattr(SimulationConfig(), key):
        return "config", key
    if hasattr(Microenvironment(), key):
        return "microenvironment", key
    raise ValueError(
        f"Unknown sweep parameter: {parameter}. Use config.<field>, micro.<field>, "
        "or aliases like treatment, immune, mutation, oxygen, acidity, inflammation."
    )


def run_parameter_sweep(
    *,
    parameter: str,
    values: Iterable[float],
    config: Optional[SimulationConfig] = None,
    microenvironment: Optional[Microenvironment] = None,
    cocktail: Optional[Cocktail] = None,
    cancer_preset_name: Optional[str] = None,
    steps: Optional[int] = None,
    seed: Optional[int] = None,
) -> List[SweepResult]:
    scope, field_name = _normalize_parameter(parameter)
    base_cfg = SimulationConfig.from_dict((config or SimulationConfig()).to_dict())
    base_micro = Microenvironment.from_dict((microenvironment or Microenvironment()).to_dict())
    if seed is not None:
        base_cfg.random_seed = int(seed)
    n_steps = int(steps if steps is not None else base_cfg.steps)
    selected_cocktail = Cocktail.from_dict((cocktail or default_cocktails()[-1]).to_dict())
    preset = lookup_named(load_cancer_presets(), cancer_preset_name, "preset") if cancer_preset_name else None

    results: List[SweepResult] = []
    for raw_value in values:
        value = float(raw_value)
        cfg = SimulationConfig.from_dict(base_cfg.to_dict())
        micro = Microenvironment.from_dict(base_micro.to_dict())
        if scope == "config":
            setattr(cfg, field_name, value)
            cfg = SimulationConfig.from_dict(cfg.to_dict())
        else:
            setattr(micro, field_name, max(0.0, min(1.0, value)))
        sim = Simulation(cfg, microenvironment=micro, cocktail=Cocktail.from_dict(selected_cocktail.to_dict()))
        sim.reset()
        if preset:
            sim.set_cancer_preset(preset)
        sim.run(n_steps)
        latest = sim.analytics.latest()
        if latest is None:
            raise RuntimeError("Sweep simulation produced no metrics.")
        assessment = assess_cure_pathway(sim)
        results.append(
            SweepResult(
                parameter=f"{scope}.{field_name}",
                value=value,
                seed=cfg.random_seed,
                steps=n_steps,
                cocktail_name=sim.cocktail.name,
                preset_name=sim.config.cancer_preset_name,
                final_healthy=latest.healthy_alive,
                final_cancer=latest.cancer_alive,
                final_dead=latest.dead_cells,
                final_inflammation=latest.inflammation,
                final_immune_pressure=latest.immune_pressure,
                final_treatment_intensity=latest.treatment_intensity,
                dosing_phase=latest.dosing_phase,
                total_healthy_damage_events=sum(row.healthy_damage_events for row in sim.analytics.history),
                total_escape_events=sum(row.escape_clone_events for row in sim.analytics.history),
                cure_pathway_classification=assessment.classification,
                cure_pathway_score=assessment.score,
            )
        )
    results.sort(key=lambda row: (row.cure_pathway_score, -row.final_cancer, row.final_healthy), reverse=True)
    return results


def export_sweep_csv(results: Iterable[SweepResult], path: str | Path) -> None:
    rows = [row.to_dict() for row in results]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_sweep_json(results: Iterable[SweepResult], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([row.to_dict() for row in results], indent=2, sort_keys=True), encoding="utf-8")


def format_sweep_table(results: Iterable[SweepResult], limit: int = 20) -> str:
    rows = list(results)[:limit]
    if not rows:
        return "No sweep results."
    header = f"{'Rank':>4}  {'Parameter':30} {'Value':>8} {'Cancer':>8} {'Healthy':>8} {'Cure':>8} {'Inflam':>7} {'Immune':>7} {'Dose':>6} {'Class':34}"
    sep = "-" * len(header)
    out = [header, sep]
    for i, row in enumerate(rows, 1):
        out.append(
            f"{i:>4}  {row.parameter[:30]:30} {row.value:>8.3f} {row.final_cancer:>8} {row.final_healthy:>8} "
            f"{row.cure_pathway_score:>8.3f} {row.final_inflammation:>7.3f} {row.final_immune_pressure:>7.3f} "
            f"{row.final_treatment_intensity:>6.3f} {row.cure_pathway_classification[:34]:34}"
        )
    return "\n".join(out)
