"""Experiment reporting utilities."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from .constants import EVIDENCE_LABELS
from .knowledge import cocktail_coverage
from .interpretation import assess_cure_pathway, interpret_latest
from .signal_interpreter import analyze_marker_evolution, analyze_signals
from .treatment_matcher import recommend_treatments

if TYPE_CHECKING:
    from .simulation import Simulation


DISCLAIMER = (
    "OncoForge is a conceptual research simulator for hypothesis generation. "
    "It is not medical advice, not a clinical prediction tool, and not a treatment recommendation system."
)


def build_report_payload(sim: "Simulation") -> Dict[str, Any]:
    """Build a deterministic, machine-readable experiment report payload."""
    rows = sim.analytics.to_dicts()
    latest = sim.analytics.latest()
    dosing_state = sim.dosing_state.to_dict()
    totals = {
        "treatment_hits": sum(row["treatment_hits"] for row in rows),
        "immune_kills": sum(row["immune_kills"] for row in rows),
        "apoptosis_events": sum(row["apoptosis_events"] for row in rows),
        "senescence_events": sum(row["senescence_events"] for row in rows),
        "proliferation_events": sum(row["proliferation_events"] for row in rows),
        "escape_clone_events": sum(row["escape_clone_events"] for row in rows),
        "healthy_damage_events": sum(row["healthy_damage_events"] for row in rows),
    }
    assessment = assess_cure_pathway(sim)
    signal_interpretation = analyze_signals(sim)
    cocktail_recommendation = recommend_treatments(sim=sim, interpretation=signal_interpretation)
    marker_evolution = analyze_marker_evolution(sim, signal_interpretation)
    return {
        "schema_version": "1.3",
        "scope": DISCLAIMER,
        "experiment": {
            "name": sim.config.name,
            "random_seed": sim.config.random_seed,
            "current_step": sim.step_index,
            "cancer_preset": sim.config.cancer_preset_name or "not recorded",
            "starting_population": {
                "healthy": sim.config.initial_healthy_cells,
                "cancer": sim.config.initial_cancer_cells,
            },
            "allow_evolution": sim.config.allow_evolution,
            "allow_proliferation": sim.config.allow_proliferation,
            "notes": sim.config.notes,
        },
        "microenvironment": sim.microenvironment.to_dict(),
        "cancer_profile": getattr(sim, "cancer_profile", {}) or {},
        "cocktail": sim.cocktail.to_dict(),
        "cocktail_scores": cocktail_coverage(sim.cocktail),
        "dosing_state": dosing_state,
        "remission_controller": {
            "clearance_step": dosing_state.get("clearance_step", -1),
            "zero_cancer_confirmation_steps_required": sim.config.zero_cancer_confirmation_steps,
            "zero_cancer_confirmation_steps_observed": dosing_state.get("zero_cancer_steps", 0),
            "current_phase": dosing_state.get("phase", "manual_full_dose"),
            "current_intensity": dosing_state.get("intensity", 1.0),
            "recurrence_after_clearance": dosing_state.get("recurrence_after_clearance", False),
            "max_cancer_after_clearance": dosing_state.get("max_cancer_after_clearance", 0),
            "rebound_step": dosing_state.get("rebound_step", -1),
        },
        "cure_pathway_assessment": assessment.to_dict(),
        "signal_interpretation": signal_interpretation,
        "cocktail_recommendation": cocktail_recommendation,
        "marker_evolution": marker_evolution,
        "local_ai_interpretation": getattr(sim, "local_ai_interpretation", {}),
        "research_loop_summary": getattr(sim, "research_loop_summary", {}),
        "readable_interpretation": interpret_latest(sim),
        "evidence_levels": EVIDENCE_LABELS,
        "final_metrics": latest.to_dict() if latest else {},
        "totals": totals,
        "tumor_burden_curve": [
            {
                "step": row["step"],
                "tumor_burden": row.get("tumor_burden", 0.0),
                "cancer_alive": row["cancer_alive"],
            }
            for row in rows
        ],
        "healthy_curve": [
            {
                "step": row["step"],
                "healthy_alive": row["healthy_alive"],
                "healthy_damage_rate": row.get("healthy_damage_rate", 0.0),
            }
            for row in rows
        ],
        "immune_curve": [
            {
                "step": row["step"],
                "immune_activation_level": row.get("immune_activation_level", 0.0),
                "immune_pressure": row.get("immune_pressure", 0.0),
            }
            for row in rows
        ],
        "clone_summary": sim.clone_summary(),
        "metrics_history": rows,
        "dosing_phase_history": [
            {
                "step": row["step"],
                "phase": row.get("dosing_phase", "manual_full_dose"),
                "treatment_intensity": row.get("treatment_intensity", 1.0),
                "cancer_alive": row.get("cancer_alive", 0),
                "zero_cancer_steps": row.get("zero_cancer_steps", 0),
                "recurrence_after_clearance": row.get("recurrence_after_clearance", False),
                "max_cancer_after_clearance": row.get("max_cancer_after_clearance", 0),
                "rebound_step": row.get("rebound_step", -1),
            }
            for row in rows
        ],
        "limitations": [
            "Complete remission in this simulator is not the same thing as a biological or clinical cure.",
            "Qualitative, conceptual model only; no calibrated clinical endpoints.",
            "Agent actions are simplified signal/action abstractions rather than pharmacology.",
            "Immune and microenvironment behavior is intentionally coarse and should be stress-tested across seeds.",
            "Speculative and user-concept agents require external biological validation before any scientific claim.",
        ],
    }


def export_json_report(sim: "Simulation", path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_report_payload(sim), indent=2, sort_keys=True), encoding="utf-8")


def export_html_report(sim: "Simulation", path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(sim)
    rows = payload["metrics_history"]
    final_metrics = payload["final_metrics"]
    assessment = payload["cure_pathway_assessment"]
    remission_controller = payload["remission_controller"]
    signal_interpretation = payload["signal_interpretation"]
    cocktail_recommendation = payload["cocktail_recommendation"]
    marker_evolution = payload["marker_evolution"]
    cancer_profile = payload["cancer_profile"]
    score_rows = "".join(
        f"<tr><td>{html.escape(key)}</td><td>{value:.3f}</td></tr>"
        for key, value in payload["cocktail_scores"].items()
        if isinstance(value, (int, float))
    )
    agent_rows = "".join(
        "<tr>"
        f"<td>{html.escape(agent.name)}</td>"
        f"<td>{html.escape(agent.category)}</td>"
        f"<td>{html.escape(agent.evidence_label)}</td>"
        f"<td>{html.escape(', '.join(agent.targets.keys()))}</td>"
        f"<td>{html.escape(', '.join(agent.actions.keys()))}</td>"
        f"<td>{html.escape(agent.notes_limitations or 'See model limitations.')}</td>"
        "</tr>"
        for agent in sim.cocktail.agents
    )
    metric_rows = "".join(
        "<tr>"
        f"<td>{row['step']}</td>"
        f"<td>{row['healthy_alive']}</td>"
        f"<td>{row['cancer_alive']}</td>"
        f"<td>{row['dead_cells']}</td>"
        f"<td>{row.get('tumor_burden', 0.0):.3f}</td>"
        f"<td>{row.get('immune_activation_level', 0.0):.3f}</td>"
        f"<td>{row.get('treatment_intensity', 1.0):.3f}</td>"
        f"<td>{html.escape(str(row.get('dosing_phase', 'manual_full_dose')))}</td>"
        f"<td>{row.get('zero_cancer_steps', 0)}</td>"
        f"<td>{html.escape(str(row.get('recurrence_after_clearance', False)))}</td>"
        f"<td>{row.get('escape_clone_count', 0)}</td>"
        f"<td>{row['healthy_damage_events']}</td>"
        "</tr>"
        for row in rows[-75:]
    )
    clone_rows = "".join(
        "<tr>"
        f"<td>{html.escape(row['clone_id'])}</td>"
        f"<td>{row['count']}</td>"
        f"<td>{row['mean_malignancy']:.3f}</td>"
        f"<td>{row['mean_mhc_expression']:.3f}</td>"
        f"<td>{row['mean_pd_l1_expression']:.3f}</td>"
        "</tr>"
        for row in payload["clone_summary"]
    )
    limitation_rows = "".join(f"<li>{html.escape(item)}</li>" for item in payload["limitations"])
    top_signal_rows = "".join(
        "<tr>"
        f"<td>{html.escape(row.get('signal', ''))}</td>"
        f"<td>{row.get('cancer_mean', 0.0):.3f}</td>"
        f"<td>{row.get('healthy_mean', 0.0):.3f}</td>"
        f"<td>{row.get('targetability_score', 0.0):.3f}</td>"
        f"<td>{row.get('healthy_overlap_risk', 0.0):.3f}</td>"
        "</tr>"
        for row in signal_interpretation.get("top_targetable_signals", [])[:12]
    )
    recommendation_rows = "".join(
        "<tr>"
        f"<td>{html.escape(row.get('cocktail_name', ''))}</td>"
        f"<td>{row.get('score', 0.0):.3f}</td>"
        f"<td>{html.escape(row.get('reason', ''))}</td>"
        "</tr>"
        for row in cocktail_recommendation.get("ranked_cocktails", [])[:10]
    )
    body = f"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(sim.config.name)} - OncoForge Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 28px; line-height: 1.45; }}
code, pre {{ background: #f3f3f3; padding: 2px 4px; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #eee; }}
.notice {{ padding: 12px; background: #fff6d8; border: 1px solid #e0c56e; }}
</style>
</head>
<body>
<h1>OncoForge Experiment Report</h1>
<p class="notice"><strong>Scope:</strong> {html.escape(DISCLAIMER)}</p>
<h2>Configuration</h2>
<ul>
<li>Name: {html.escape(sim.config.name)}</li>
<li>Current step: {sim.step_index}</li>
<li>Initial healthy cells: {sim.config.initial_healthy_cells}</li>
<li>Initial cancer cells: {sim.config.initial_cancer_cells}</li>
<li>Random seed: {sim.config.random_seed}</li>
<li>Cancer preset: {html.escape(sim.config.cancer_preset_name or 'not recorded')}</li>
<li>Evolution enabled: {sim.config.allow_evolution}</li>
</ul>
<h2>Final Summary</h2>
<pre>{html.escape(sim.analytics.summary_text())}</pre>
<h2>Plain-English Interpretation</h2>
<pre>{html.escape(payload['readable_interpretation'])}</pre>
<h2>Cure-Pathway / Remission Assessment</h2>
<pre>{html.escape(json.dumps(assessment, indent=2, sort_keys=True))}</pre>
<h2>Remission Controller</h2>
<pre>{html.escape(json.dumps(remission_controller, indent=2, sort_keys=True))}</pre>
<h2>Cancer Profile</h2>
<pre>{html.escape(json.dumps(cancer_profile or {'profile': 'not recorded'}, indent=2, sort_keys=True))}</pre>
<h2>Signal Interpreter</h2>
<p>{html.escape(signal_interpretation.get('plain_english_summary', ''))}</p>
<table><tr><th>Signal</th><th>Cancer Mean</th><th>Healthy Mean</th><th>Targetability</th><th>Healthy Overlap</th></tr>{top_signal_rows}</table>
<h2>Cocktail Recommendations</h2>
<pre>{html.escape(cocktail_recommendation.get('plain_english_summary', ''))}</pre>
<table><tr><th>Cocktail</th><th>Score</th><th>Reason</th></tr>{recommendation_rows}</table>
<h2>Marker Evolution</h2>
<pre>{html.escape(json.dumps(marker_evolution, indent=2, sort_keys=True))}</pre>
<h2>Local AI Interpretation</h2>
<pre>{html.escape(json.dumps(payload.get('local_ai_interpretation') or {'status': 'not enabled'}, indent=2, sort_keys=True))}</pre>
<h2>Auto-Experiment Loop Summary</h2>
<pre>{html.escape(json.dumps(payload.get('research_loop_summary') or {'status': 'not used'}, indent=2, sort_keys=True))}</pre>
<h2>Final Metrics</h2>
<pre>{html.escape(json.dumps(final_metrics, indent=2, sort_keys=True))}</pre>
<h2>Microenvironment</h2>
<pre>{html.escape(json.dumps(sim.microenvironment.to_dict(), indent=2, sort_keys=True))}</pre>
<h2>Active Cocktail</h2>
<p>{html.escape(sim.cocktail.name)} - {html.escape(sim.cocktail.notes)}</p>
<table><tr><th>Agent</th><th>Category</th><th>Evidence Label</th><th>Targets</th><th>Actions</th><th>Limitations</th></tr>{agent_rows}</table>
<h2>Cocktail Coverage / Risk Scores</h2>
<table><tr><th>Metric</th><th>Value</th></tr>{score_rows}</table>
<h2>Recent Metrics</h2>
<table><tr><th>Step</th><th>Healthy</th><th>Cancer</th><th>Dead</th><th>Tumor Burden</th><th>Immune Activation</th><th>Treatment Intensity</th><th>Dosing Phase</th><th>Zero-Cancer Steps</th><th>Rebound Detected</th><th>Escape Clones</th><th>Healthy Damage Events</th></tr>{metric_rows}</table>
<h2>Clone Summary</h2>
<table><tr><th>Clone</th><th>Count</th><th>Mean Malignancy</th><th>Mean MHC-I</th><th>Mean PD-L1</th></tr>{clone_rows}</table>
<h2>Interpretation Notes</h2>
<p>The best next scientific use is not to trust one run. Use repeated seeds, parameter sweeps, and compare the same cancer preset against multiple cocktails.</p>
<h2>Limitations</h2>
<ul>{limitation_rows}</ul>
</body></html>
"""
    path.write_text(body, encoding="utf-8")


def export_report_by_suffix(sim: "Simulation", path: str | Path) -> None:
    path = Path(path)
    if path.suffix.lower() == ".json":
        export_json_report(sim, path)
    elif path.suffix.lower() == ".csv":
        sim.analytics.export_csv(path)
    else:
        export_html_report(sim, path)
