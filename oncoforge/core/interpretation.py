"""Plain-language interpretation helpers for OncoForge runs.

The functions in this file translate raw simulator metrics into readable
engineering/science guidance. They are deliberately heuristic and conservative:
OncoForge is for conceptual hypothesis exploration, not clinical prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

from .models import MetricsSnapshot
from .utils import clamp

if TYPE_CHECKING:
    from .simulation import Simulation


@dataclass
class CurePathwayAssessment:
    """Heuristic post-clearance assessment for a simulation run."""

    classification: str
    score: float
    cleared: bool
    clearance_step: int
    post_clearance_steps: int
    zero_cancer_confirmation_steps: int
    recurrence_observed: bool
    max_cancer_after_clearance: int
    rebound_step: int
    final_cancer: int
    final_healthy: int
    final_dead: int
    healthy_preservation_fraction: float
    healthy_damage_after_clearance: int
    final_inflammation: float
    final_immune_pressure: float
    final_treatment_intensity: float
    explanation: str
    next_step: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clearance_step(history: Iterable[MetricsSnapshot]) -> int:
    for snapshot in history:
        if snapshot.step > 0 and snapshot.cancer_alive <= 0 and snapshot.precancerous_alive <= 0:
            return snapshot.step
    return -1


def assess_cure_pathway(sim: "Simulation") -> CurePathwayAssessment:
    """Assess whether a run reached a cure-like *simulation* outcome.

    This is not a medical statement. A strong result requires clearance,
    survival/healthy preservation, a post-clearance watch period, no recurrence,
    and recovery of inflammatory pressure.
    """

    history: List[MetricsSnapshot] = list(sim.analytics.history)
    latest = sim.analytics.latest()
    if latest is None or not history:
        return CurePathwayAssessment(
            classification="not_started",
            score=0.0,
            cleared=False,
            clearance_step=-1,
            post_clearance_steps=0,
            zero_cancer_confirmation_steps=0,
            recurrence_observed=False,
            max_cancer_after_clearance=0,
            rebound_step=-1,
            final_cancer=0,
            final_healthy=0,
            final_dead=0,
            healthy_preservation_fraction=0.0,
            healthy_damage_after_clearance=0,
            final_inflammation=0.0,
            final_immune_pressure=0.0,
            final_treatment_intensity=0.0,
            explanation="No simulation history is available yet.",
            next_step="Run a simulation, then review the cure-pathway assessment again.",
        )

    first = history[0]
    clearance = _clearance_step(history)
    cleared = clearance >= 0 and latest.cancer_alive <= 0 and latest.precancerous_alive <= 0
    post_clearance = 0 if clearance < 0 else max(0, latest.step - clearance)
    post_clearance_rows = [row for row in history if clearance >= 0 and row.step > clearance]
    recurrence = sim.dosing_state.recurrence_after_clearance or any(row.cancer_alive > 0 or row.precancerous_alive > 0 for row in post_clearance_rows)
    healthy_damage_after_clearance = sum(row.healthy_damage_events for row in post_clearance_rows)
    healthy_preservation = latest.healthy_alive / max(1, first.healthy_alive)

    clearance_component = 1.0 if cleared else clamp((first.cancer_alive - latest.cancer_alive) / max(1, first.cancer_alive))
    watch_component = clamp(post_clearance / 150.0)
    recovery_component = (clamp(1.0 - latest.inflammation) + clamp(1.0 - latest.immune_pressure)) / 2.0
    damage_penalty = clamp(healthy_damage_after_clearance / max(1, first.healthy_alive) * 3.0)
    recurrence_penalty = 0.45 if recurrence else 0.0
    score = clamp(
        clearance_component * 0.38
        + healthy_preservation * 0.24
        + watch_component * 0.18
        + recovery_component * 0.20
        - damage_penalty
        - recurrence_penalty
    )

    if not cleared:
        classification = "not_cleared"
        explanation = "Cancer remains detectable in the conceptual model. This is a treatment-control or suppression problem, not a remission result yet."
        next_step = "Compare smaller or better-gated cocktails, increase run length, or inspect resistant clone signals."
    elif recurrence:
        classification = "recurrence_observed"
        explanation = "Cancer reached zero but reappeared during the post-clearance watch period."
        next_step = "Study the clone summary and add surveillance/gating logic targeted to the recurrent signal pattern."
    elif post_clearance < 25:
        classification = "clearance_needs_remission_test"
        explanation = "Cancer reached zero, but the model has not watched long enough after clearance to judge durability."
        next_step = "Run a remission test with adaptive dosing and at least 150-300 post-clearance watch steps."
    elif healthy_preservation < 0.65 or latest.inflammation > 0.75 or latest.immune_pressure > 0.85:
        classification = "clearance_with_recovery_concerns"
        explanation = "Cancer cleared, but healthy-cell preservation or inflammatory recovery is still concerning."
        next_step = "Enable adaptive dosing/shutoff, lower broad-agent intensity, or add stricter multi-signal gating."
    elif healthy_damage_after_clearance > max(1, first.healthy_alive * 0.02):
        classification = "clearance_with_post_clearance_damage"
        explanation = "Cancer cleared, but treatment continued harming healthy cells during the remission watch period."
        next_step = "Use auto-shutoff or surveillance-only agents after cancer reaches zero."
    else:
        classification = "strong_cure_like_simulation_outcome"
        explanation = "The run achieved cancer clearance, post-clearance survival, no recurrence in the watch period, and acceptable recovery metrics."
        next_step = "Repeat across more seeds, cancer presets, and lower-intensity cocktails to stress-test the result."

    return CurePathwayAssessment(
        classification=classification,
        score=score,
        cleared=cleared,
        clearance_step=clearance,
        post_clearance_steps=post_clearance,
        zero_cancer_confirmation_steps=sim.dosing_state.zero_cancer_steps,
        recurrence_observed=recurrence,
        max_cancer_after_clearance=sim.dosing_state.max_cancer_after_clearance,
        rebound_step=sim.dosing_state.rebound_step,
        final_cancer=latest.cancer_alive,
        final_healthy=latest.healthy_alive,
        final_dead=latest.dead_cells,
        healthy_preservation_fraction=healthy_preservation,
        healthy_damage_after_clearance=healthy_damage_after_clearance,
        final_inflammation=latest.inflammation,
        final_immune_pressure=latest.immune_pressure,
        final_treatment_intensity=latest.treatment_intensity,
        explanation=explanation,
        next_step=next_step,
    )


def interpret_latest(sim: "Simulation") -> str:
    """Return a readable interpretation of the latest run state."""

    latest = sim.analytics.latest()
    if latest is None:
        return "No metrics yet. Run the simulation first."
    assessment = assess_cure_pathway(sim)
    counts = sim.live_cell_counts()
    lines = [
        "OncoForge interpretation",
        "========================",
        f"Current step: {latest.step}",
        f"Living healthy cells: {counts.get('healthy', 0)}",
        f"Living cancer cells: {counts.get('cancer', 0)}",
        f"Dead cells: {counts.get('dead', 0)}",
        "",
        "Main read:",
    ]
    if latest.cancer_alive <= 0:
        lines.append("- Cancer is cleared in the current model state.")
    elif latest.tumor_burden < 0.05:
        lines.append("- Cancer burden is low but not cleared; this is a minimal-residual-disease style model state.")
    else:
        lines.append("- Cancer remains active; compare signal coverage and clone escape behavior.")

    if latest.healthy_damage_events > 0:
        lines.append(f"- Healthy damage occurred this step ({latest.healthy_damage_events} events); dose/gating may need adjustment.")
    else:
        lines.append("- No healthy damage occurred in the latest step.")

    if latest.inflammation >= 0.85 or latest.immune_pressure >= 0.90:
        lines.append("- Inflammation or immune pressure is very high; adaptive taper/shutoff is recommended for recovery testing.")
    elif latest.inflammation <= 0.35 and latest.immune_pressure <= 0.60:
        lines.append("- Inflammation and immune pressure are in a more controlled range.")
    else:
        lines.append("- Inflammation/immune pressure are moderate; watch the trend over more steps.")

    lines.extend(
        [
            "",
            "Dosing state:",
            f"- Phase: {latest.dosing_phase}",
            f"- Treatment intensity: {latest.treatment_intensity:.3f}",
            f"- Dosing reason: {sim.dosing_state.reason}",
            "",
            "Cure-pathway / remission assessment:",
            f"- Classification: {assessment.classification}",
            f"- Score: {assessment.score:.3f}",
            f"- Clearance step: {assessment.clearance_step if assessment.clearance_step >= 0 else 'not reached'}",
            f"- Post-clearance watch steps: {assessment.post_clearance_steps}",
            f"- Zero-cancer confirmation steps: {assessment.zero_cancer_confirmation_steps}/{sim.config.zero_cancer_confirmation_steps}",
            f"- Recurrence observed: {assessment.recurrence_observed}",
            f"- Max cancer after clearance: {assessment.max_cancer_after_clearance}",
            f"- Rebound step: {assessment.rebound_step if assessment.rebound_step >= 0 else 'not observed'}",
            f"- Healthy damage after clearance: {assessment.healthy_damage_after_clearance}",
            f"- Explanation: {assessment.explanation}",
            f"- Next step: {assessment.next_step}",
        ]
    )
    return "\n".join(lines)
