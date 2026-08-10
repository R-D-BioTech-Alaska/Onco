"""Metric aggregation and reporting helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

from .models import BioAgent, Cell, DosingState, MetricsSnapshot, Microenvironment


def _mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += float(value)
        count += 1
    return total / count if count else 0.0


class AnalyticsRecorder:
    def __init__(self) -> None:
        self.history: List[MetricsSnapshot] = []

    def clear(self) -> None:
        self.history.clear()

    def record(
        self,
        step: int,
        cells: Iterable[Cell],
        treatment_hits: int,
        immune_kills: int,
        apoptosis_events: int,
        senescence_events: int,
        proliferation_events: int,
        escape_clone_events: int,
        healthy_damage_events: int,
        microenvironment: Optional[Microenvironment] = None,
        agents: Optional[Iterable[BioAgent]] = None,
        dosing_state: Optional[DosingState] = None,
    ) -> MetricsSnapshot:
        cell_list = list(cells)
        living = [c for c in cell_list if c.alive]
        cancer = [c for c in living if c.cell_kind == "cancer"]
        precancer = [c for c in living if c.cell_kind == "precancerous"]
        healthy = [c for c in living if c.cell_kind == "healthy"]
        if living:
            mean_malignancy = _mean(c.malignancy_score() for c in living)
            mean_dna_damage = _mean(c.dna_damage for c in living)
            mean_visibility = _mean((c.mhc_expression + c.neoantigen_load + c.stress_ligand_expression) / 3.0 for c in living)
            mean_apoptosis_pressure = _mean(c.signals.get("APOPTOSIS_READY", 0.0) for c in living)
        else:
            mean_malignancy = mean_dna_damage = mean_visibility = mean_apoptosis_pressure = 0.0
        total_living = max(1, len(living))
        clone_counts: Dict[str, int] = {}
        for c in cancer:
            clone_counts[c.clone_id] = clone_counts.get(c.clone_id, 0) + 1
        if clone_counts:
            dominant_clone_id, dominant_clone_count = max(clone_counts.items(), key=lambda item: item[1])
            dominant_clone_fraction = dominant_clone_count / max(1, len(cancer))
        else:
            dominant_clone_id = ""
            dominant_clone_fraction = 0.0
        agent_list = list(agents or [])
        mean_agent_concentration = _mean(a.concentration for a in agent_list) if agent_list else 0.0
        inflammation = microenvironment.inflammation if microenvironment else 0.0
        immune_pressure = microenvironment.immune_pressure if microenvironment else 0.0
        immune_activation_level = min(1.0, (mean_visibility * 0.45) + (immune_pressure * 0.40) + (inflammation * 0.15))
        dosing = dosing_state or DosingState()
        snapshot = MetricsSnapshot(
            step=step,
            healthy_alive=len(healthy),
            cancer_alive=len(cancer),
            precancerous_alive=len(precancer),
            dead_cells=sum(1 for c in cell_list if not c.alive or c.cell_kind == "dead"),
            mean_malignancy=mean_malignancy,
            mean_dna_damage=mean_dna_damage,
            mean_immune_visibility=mean_visibility,
            mean_apoptosis_pressure=mean_apoptosis_pressure,
            treatment_hits=treatment_hits,
            immune_kills=immune_kills,
            apoptosis_events=apoptosis_events,
            senescence_events=senescence_events,
            proliferation_events=proliferation_events,
            escape_clone_events=escape_clone_events,
            healthy_damage_events=healthy_damage_events,
            tumor_burden=len(cancer) / total_living,
            cancer_death_rate=(immune_kills + apoptosis_events) / max(1, len(cancer) + immune_kills + apoptosis_events),
            healthy_damage_rate=healthy_damage_events / max(1, len(healthy) + healthy_damage_events),
            immune_activation_level=immune_activation_level,
            escape_clone_count=sum(1 for clone_id in clone_counts if clone_id.startswith("escape_")),
            dominant_clone_id=dominant_clone_id,
            dominant_clone_fraction=dominant_clone_fraction,
            inflammation=inflammation,
            immune_pressure=immune_pressure,
            mean_agent_concentration=mean_agent_concentration,
            treatment_intensity=dosing.intensity,
            dosing_phase=dosing.phase,
            post_clearance_steps=dosing.post_clearance_steps,
            clearance_step=dosing.clearance_step,
            zero_cancer_steps=dosing.zero_cancer_steps,
            recurrence_after_clearance=dosing.recurrence_after_clearance,
            max_cancer_after_clearance=dosing.max_cancer_after_clearance,
            rebound_step=dosing.rebound_step,
        )
        self.history.append(snapshot)
        return snapshot

    def latest(self) -> MetricsSnapshot | None:
        return self.history[-1] if self.history else None

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.history]

    def export_csv(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.to_dicts()
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def export_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dicts(), indent=2), encoding="utf-8")

    def summary_text(self) -> str:
        if not self.history:
            return "No simulation has been run yet."
        first = self.history[0]
        last = self.history[-1]
        cancer_delta = last.cancer_alive - first.cancer_alive
        healthy_delta = last.healthy_alive - first.healthy_alive
        return (
            f"Steps recorded: {len(self.history)}\n"
            f"Cancer cells: {first.cancer_alive} -> {last.cancer_alive} ({cancer_delta:+d})\n"
            f"Healthy cells: {first.healthy_alive} -> {last.healthy_alive} ({healthy_delta:+d})\n"
            f"Dead cells final: {last.dead_cells}\n"
            f"Tumor burden final: {last.tumor_burden:.3f}\n"
            f"Mean malignancy final: {last.mean_malignancy:.3f}\n"
            f"Mean immune visibility final: {last.mean_immune_visibility:.3f}\n"
            f"Immune activation final: {last.immune_activation_level:.3f}\n"
            f"Treatment intensity final: {last.treatment_intensity:.3f} ({last.dosing_phase})\n"
            f"Clearance step: {last.clearance_step if last.clearance_step >= 0 else 'not reached'}\n"
            f"Post-clearance steps final: {last.post_clearance_steps}\n"
            f"Zero-cancer confirmation steps final: {last.zero_cancer_steps}\n"
            f"Recurrence after clearance: {last.recurrence_after_clearance}\n"
            f"Max cancer after clearance: {last.max_cancer_after_clearance}\n"
            f"Rebound step: {last.rebound_step if last.rebound_step >= 0 else 'not observed'}\n"
            f"Escape clone count final: {last.escape_clone_count}\n"
            f"Dominant clone final: {last.dominant_clone_id or 'none'} ({last.dominant_clone_fraction:.3f})\n"
            f"Treatment hits total: {sum(s.treatment_hits for s in self.history)}\n"
            f"Immune kills total: {sum(s.immune_kills for s in self.history)}\n"
            f"Apoptosis events total: {sum(s.apoptosis_events for s in self.history)}\n"
            f"Escape clone events total: {sum(s.escape_clone_events for s in self.history)}\n"
            f"Healthy damage events total: {sum(s.healthy_damage_events for s in self.history)}"
        )
