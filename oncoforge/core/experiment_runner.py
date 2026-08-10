"""Headless experiment comparison tools.

These functions are used by the GUI batch tab, tests, and CLI. They make the
program useful when no desktop display is available.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .knowledge import cocktail_coverage
from .interpretation import assess_cure_pathway
from .models import Cocktail, Microenvironment, SimulationConfig
from .presets import default_cocktails, load_cancer_presets
from .simulation import Simulation


def _name_key(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


@dataclass
class CocktailResult:
    cocktail_name: str
    seed: int
    steps: int
    final_healthy: int
    final_cancer: int
    final_dead: int
    cancer_delta: int
    healthy_delta: int
    cancer_suppression_fraction: float
    healthy_preservation_fraction: float
    total_treatment_hits: int
    total_immune_kills: int
    total_apoptosis_events: int
    total_escape_events: int
    total_healthy_damage_events: int
    final_tumor_burden: float
    final_immune_activation: float
    final_inflammation: float
    final_treatment_intensity: float
    final_dosing_phase: str
    cure_pathway_classification: str
    cure_pathway_score: float
    escape_clone_count: int
    score: float
    target_coverage: float
    action_coverage: float
    pathway_coverage: float
    signal_coverage: float
    redundancy: float
    mean_specificity: float
    mean_healthy_risk: float
    inflammation_risk: float
    escape_pressure: float
    conceptual_plausibility: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def run_cocktail_once(
    cocktail: Cocktail,
    config: Optional[SimulationConfig] = None,
    microenvironment: Optional[Microenvironment] = None,
    cancer_preset: Optional[Dict] = None,
    steps: Optional[int] = None,
) -> CocktailResult:
    cfg = SimulationConfig.from_dict((config or SimulationConfig()).to_dict())
    n_steps = int(steps if steps is not None else cfg.steps)
    sim = Simulation(cfg, microenvironment=Microenvironment.from_dict((microenvironment or Microenvironment()).to_dict()), cocktail=Cocktail.from_dict(cocktail.to_dict()))
    sim.reset()
    if cancer_preset:
        sim.set_cancer_preset(cancer_preset)
    initial = sim.analytics.history[0]
    sim.run(n_steps)
    final = sim.analytics.latest()
    if final is None:
        raise RuntimeError("Simulation produced no final metrics.")
    total_treatment_hits = sum(x.treatment_hits for x in sim.analytics.history)
    total_immune_kills = sum(x.immune_kills for x in sim.analytics.history)
    total_apoptosis_events = sum(x.apoptosis_events for x in sim.analytics.history)
    total_escape_events = sum(x.escape_clone_events for x in sim.analytics.history)
    total_healthy_damage_events = sum(x.healthy_damage_events for x in sim.analytics.history)
    cancer_suppression = (initial.cancer_alive - final.cancer_alive) / max(1, initial.cancer_alive)
    healthy_preservation = final.healthy_alive / max(1, initial.healthy_alive)
    cov = cocktail_coverage(cocktail)
    assessment = assess_cure_pathway(sim)
    healthy_damage_pressure = total_healthy_damage_events / max(1, n_steps * max(1, initial.healthy_alive))
    escape_event_pressure = total_escape_events / max(1, n_steps)
    score = (
        cancer_suppression * 1.75
        + healthy_preservation * 0.80
        + final.immune_activation_level * 0.20
        + cov["pathway_coverage"] * 0.18
        + cov["conceptual_plausibility"] * 0.15
        + assessment.score * 0.25
        - healthy_damage_pressure * 1.40
        - escape_event_pressure * 0.08
        - cov["inflammation_risk"] * 0.08
        - cov["escape_pressure"] * 0.04
    )
    return CocktailResult(
        cocktail_name=cocktail.name,
        seed=cfg.random_seed,
        steps=n_steps,
        final_healthy=final.healthy_alive,
        final_cancer=final.cancer_alive,
        final_dead=final.dead_cells,
        cancer_delta=final.cancer_alive - initial.cancer_alive,
        healthy_delta=final.healthy_alive - initial.healthy_alive,
        cancer_suppression_fraction=cancer_suppression,
        healthy_preservation_fraction=healthy_preservation,
        total_treatment_hits=total_treatment_hits,
        total_immune_kills=total_immune_kills,
        total_apoptosis_events=total_apoptosis_events,
        total_escape_events=total_escape_events,
        total_healthy_damage_events=total_healthy_damage_events,
        final_tumor_burden=final.tumor_burden,
        final_immune_activation=final.immune_activation_level,
        final_inflammation=final.inflammation,
        final_treatment_intensity=final.treatment_intensity,
        final_dosing_phase=final.dosing_phase,
        cure_pathway_classification=assessment.classification,
        cure_pathway_score=assessment.score,
        escape_clone_count=final.escape_clone_count,
        score=score,
        target_coverage=cov["target_coverage"],
        action_coverage=cov["action_coverage"],
        pathway_coverage=cov["pathway_coverage"],
        signal_coverage=cov["signal_coverage"],
        redundancy=cov["redundancy"],
        mean_specificity=cov["mean_specificity"],
        mean_healthy_risk=cov["mean_healthy_risk"],
        inflammation_risk=cov["inflammation_risk"],
        escape_pressure=cov["escape_pressure"],
        conceptual_plausibility=cov["conceptual_plausibility"],
    )


def compare_cocktails(
    cocktails: Optional[Iterable[Cocktail]] = None,
    config: Optional[SimulationConfig] = None,
    microenvironment: Optional[Microenvironment] = None,
    cancer_preset_name: Optional[str] = None,
    steps: Optional[int] = None,
    seeds: Optional[Iterable[int]] = None,
) -> List[CocktailResult]:
    presets = load_cancer_presets()
    preset = None
    if cancer_preset_name:
        requested = _name_key(cancer_preset_name)
        matches = []
        for item in presets:
            item_key = _name_key(str(item.get("name", "")))
            if item_key == requested:
                preset = item
                break
            if item_key.startswith(requested) or requested in item_key:
                matches.append(item)
        if preset is None and len(matches) == 1:
            preset = matches[0]
        if preset is None:
            available = ", ".join(str(item.get("name", "")) for item in presets)
            raise ValueError(f"Unknown cancer preset: {cancer_preset_name}. Available: {available}")
    base_cfg = config or SimulationConfig()
    cocktail_list = list(cocktails or default_cocktails())
    seed_list = list(seeds or [base_cfg.random_seed])
    results: List[CocktailResult] = []
    for seed in seed_list:
        for cocktail in cocktail_list:
            cfg = SimulationConfig.from_dict(base_cfg.to_dict())
            cfg.random_seed = int(seed)
            results.append(run_cocktail_once(cocktail, cfg, microenvironment, preset, steps))
    results.sort(key=lambda x: x.score, reverse=True)
    return results


def export_results_csv(results: Iterable[CocktailResult], path: str | Path) -> None:
    rows = [r.to_dict() for r in results]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_results_table(results: Iterable[CocktailResult], limit: int = 12) -> str:
    rows = list(results)[:limit]
    if not rows:
        return "No comparison results."
    header = f"{'Rank':>4}  {'Cocktail':34} {'Seed':>5} {'Cancer':>8} {'Healthy':>8} {'Score':>8} {'Cure':>8} {'Suppression':>11} {'HealthyKeep':>11} {'ImmuneAct':>9} {'Dose':>6} {'Escapes':>7} {'H-Damage':>8}"
    sep = "-" * len(header)
    out = [header, sep]
    for i, r in enumerate(rows, 1):
        out.append(f"{i:>4}  {r.cocktail_name[:34]:34} {r.seed:>5} {r.final_cancer:>8} {r.final_healthy:>8} {r.score:>8.3f} {r.cure_pathway_score:>8.3f} {r.cancer_suppression_fraction:>11.3f} {r.healthy_preservation_fraction:>11.3f} {r.final_immune_activation:>9.3f} {r.final_treatment_intensity:>6.3f} {r.total_escape_events:>7} {r.total_healthy_damage_events:>8}")
    return "\n".join(out)
