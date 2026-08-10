"""Integrated portal payload builder for OncoForge.

The portal mission layer gives the website one compact way to run the useful
OncoForge sequence: load a profile, read markers, rank cocktails, build a QSA
plan, optionally run a simulation, then return a web-ready JSON payload.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cancer_profiles import CancerProfile, SCOPE_NOTICE, create_profile_simulation, find_cancer_profile
from .exporter import export_json_report
from .models import Cocktail
from .presets import default_cocktails
from .quantum_strategy import (
    QuantumWorkloadLimits,
    build_quantum_search_request,
    run_quantum_strategy,
)
from .research_loop import ResearchLoopConfig
from .signal_interpreter import analyze_signals
from .treatment_matcher import recommend_treatments
from .utils import clamp


PORTAL_PAYLOAD_VERSION = "oncoforge.portal.v1"


@dataclass
class PortalMissionConfig:
    profile: str
    cocktail: str = ""
    steps: int = 120
    healthy: int = 300
    cancer: int = 100
    seed: int = 1729
    profile_strength: float = 1.0
    profile_heterogeneity: float = 0.15
    immune_pressure: Optional[float] = None
    mutation_rate: Optional[float] = None
    run_simulation: bool = True
    auto_select_cocktail: bool = True
    include_qsa: bool = True
    include_research_loop_plan: bool = True
    max_auto_experiments: int = 5
    max_qsa_candidates: int = 12
    max_marker_qubits: int = 16
    max_component_states: int = 4096
    output_dir: str = "outputs/portal"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortalMissionConfig":
        base = cls(profile=str(data.get("profile", "")))
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        base.steps = max(1, int(base.steps))
        base.healthy = max(0, int(base.healthy))
        base.cancer = max(0, int(base.cancer))
        base.seed = int(base.seed)
        base.profile_strength = clamp(float(base.profile_strength))
        base.profile_heterogeneity = clamp(float(base.profile_heterogeneity))
        base.run_simulation = bool(base.run_simulation)
        base.auto_select_cocktail = bool(base.auto_select_cocktail)
        base.include_qsa = bool(base.include_qsa)
        base.include_research_loop_plan = bool(base.include_research_loop_plan)
        base.max_auto_experiments = max(1, int(base.max_auto_experiments))
        base.max_qsa_candidates = max(1, int(base.max_qsa_candidates))
        base.max_marker_qubits = max(1, int(base.max_marker_qubits))
        base.max_component_states = max(1, int(base.max_component_states))
        return base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _choose_cocktail(name: str) -> Cocktail:
    cocktails = default_cocktails()
    if not name:
        return cocktails[-1]
    requested = _key(name)
    matches = []
    for cocktail in cocktails:
        key = _key(cocktail.name)
        if requested == key:
            return cocktail
        if requested in key or key.startswith(requested):
            matches.append(cocktail)
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(cocktail.name for cocktail in cocktails)
    raise ValueError(f"Unknown cocktail: {name}. Available: {available}")


def _best_recommended_cocktail(recommendation: Dict[str, Any], fallback: str) -> str:
    best = recommendation.get("best_first_line_conceptual_match") or {}
    return str(best.get("cocktail_name") or fallback or "Full conceptual swarm")


def _metrics_payload(sim: Any) -> Dict[str, Any]:
    latest = sim.analytics.latest()
    if latest is None:
        return {}
    return latest.to_dict()


def _hypothesis_index(metrics: Dict[str, Any], recommendation: Dict[str, Any], qsa_result: Dict[str, Any]) -> Dict[str, Any]:
    initial_cancer = max(1, int(metrics.get("cancer_alive", 0)) + int(metrics.get("dead_cells", 0)))
    final_cancer = max(0, int(metrics.get("cancer_alive", 0)))
    final_healthy = max(0, int(metrics.get("healthy_alive", 0)))
    cancer_pressure = clamp(1.0 - (final_cancer / initial_cancer))
    healthy_preservation = clamp(final_healthy / max(1, final_healthy + int(metrics.get("healthy_damage_events", 0))))
    best = recommendation.get("best_first_line_conceptual_match") or {}
    selectivity = float(best.get("predicted_selectivity", 0.0))
    qsa_best = qsa_result.get("best_candidate") or {}
    qsa_score = float(qsa_best.get("structural_score", 0.0))
    index = clamp(cancer_pressure * 0.30 + healthy_preservation * 0.25 + selectivity * 0.25 + qsa_score * 0.20)
    risk = clamp(
        float(best.get("healthy_overlap_penalty", 0.0)) * 0.40
        + float(best.get("inflammation_risk_penalty", 0.0)) * 0.35
        + float(best.get("broadness_penalty", 0.0)) * 0.25
    )
    return {
        "hypothesis_strength_index": index,
        "model_risk_index": risk,
        "basis": [
            "cancer pressure in this simulation",
            "healthy preservation in this simulation",
            "conceptual selectivity from cocktail matcher",
            "bounded QSA structural score when available",
        ],
        "warning": "This is a simulation triage score, not clinical confidence.",
    }


def build_web_handoff() -> Dict[str, Any]:
    return {
        "page_mount": "/lab/oncoforge/",
        "portal_routes": [
            "/lab/oncoforge/login",
            "/lab/oncoforge/signup",
            "/lab/oncoforge/portal",
            "/lab/oncoforge/portal/projects",
            "/lab/oncoforge/portal/profiles",
            "/lab/oncoforge/portal/experiments/{experiment_id}",
            "/lab/oncoforge/portal/qsa/{job_id}",
            "/lab/oncoforge/portal/reports/{report_id}",
        ],
        "required_components": [
            "AuthShell",
            "ProjectDashboard",
            "CancerProfilePicker",
            "MissionSetupPanel",
            "MarkerSignalPanel",
            "CocktailRankerPanel",
            "QsaMissionPanel",
            "SimulationRunnerPanel",
            "ResearchLoopPanel",
            "ReportLibrary",
            "SafetyNoticeBanner",
        ],
        "primary_buttons": [
            "Create Account",
            "Start Project",
            "Load Profile",
            "Analyze Markers",
            "Auto-Select Smallest Cocktail",
            "Run Mission",
            "Build QSA Plan",
            "Start Bounded Research Loop",
            "Export Report",
        ],
        "api_endpoints": [
            "GET /lab/oncoforge/api/profiles",
            "POST /lab/oncoforge/api/portal/missions",
            "GET /lab/oncoforge/api/portal/missions/{mission_id}",
            "POST /lab/oncoforge/api/qsa/jobs",
            "GET /lab/oncoforge/api/qsa/jobs/{job_id}",
            "POST /lab/oncoforge/api/research-loops",
            "GET /lab/oncoforge/api/reports/{report_id}",
        ],
        "frontend_state_keys": [
            "session.profile",
            "session.initial_interpretation",
            "session.recommendation",
            "session.qsa_result",
            "session.simulation",
            "session.post_run_interpretation",
            "session.research_loop_plan",
            "session.safety_notice",
        ],
        "hard_rules": [
            "Show scope notice beside every marker, cocktail, QSA, and report panel.",
            "Long jobs must display limits before start.",
            "Never label a result as a real cure or clinical treatment recommendation.",
            "Prefer the smallest cocktail that covers cancer-specific signals with lower healthy overlap.",
        ],
    }


def build_stage_cards(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    cards = [
        {
            "id": "profile",
            "label": "Profile",
            "status": "ready",
            "headline": payload.get("profile", {}).get("display_name", ""),
        },
        {
            "id": "markers",
            "label": "Markers",
            "status": "ready",
            "headline": ", ".join(
                row.get("signal", "")
                for row in payload.get("initial_interpretation", {}).get("top_targetable_signals", [])[:3]
            ),
        },
        {
            "id": "cocktail",
            "label": "Cocktail",
            "status": "ready",
            "headline": payload.get("selected_cocktail", ""),
        },
    ]
    if payload.get("qsa_result"):
        best = payload["qsa_result"].get("best_candidate") or {}
        cards.append(
            {
                "id": "qsa",
                "label": "QSA",
                "status": "ready" if payload["qsa_result"].get("ok") else "blocked",
                "headline": best.get("cocktail_name", payload["qsa_result"].get("message", "")),
            }
        )
    if payload.get("simulation"):
        metrics = payload["simulation"].get("final_metrics", {})
        cards.append(
            {
                "id": "simulation",
                "label": "Simulation",
                "status": "ready",
                "headline": f"cancer {metrics.get('cancer_alive')} / healthy {metrics.get('healthy_alive')}",
            }
        )
    if payload.get("research_loop_plan"):
        cards.append(
            {
                "id": "loop",
                "label": "Research Loop",
                "status": "planned",
                "headline": f"{payload['research_loop_plan']['max_auto_experiments']} bounded experiments",
            }
        )
    return cards


def build_portal_mission(config: PortalMissionConfig | Dict[str, Any]) -> Dict[str, Any]:
    cfg = config if isinstance(config, PortalMissionConfig) else PortalMissionConfig.from_dict(config)
    profile = find_cancer_profile(cfg.profile)
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    initial_cocktail = _choose_cocktail(cfg.cocktail or (profile.starter_cocktails[0] if profile.starter_cocktails else "Full conceptual swarm"))
    scout = create_profile_simulation(
        profile,
        healthy=cfg.healthy,
        cancer=cfg.cancer,
        seed=cfg.seed,
        steps=1,
        profile_strength=cfg.profile_strength,
        profile_heterogeneity=cfg.profile_heterogeneity,
        immune_pressure=cfg.immune_pressure,
        mutation_rate=cfg.mutation_rate,
        cocktail=initial_cocktail,
    )
    initial_interpretation = analyze_signals(scout, profile)
    initial_recommendation = recommend_treatments(sim=scout, profile=profile, interpretation=initial_interpretation)
    selected_name = _best_recommended_cocktail(initial_recommendation, initial_cocktail.name) if cfg.auto_select_cocktail else initial_cocktail.name
    selected_cocktail = _choose_cocktail(selected_name)

    qsa_request = None
    qsa_result: Dict[str, Any] = {}
    if cfg.include_qsa:
        qsa_limits = QuantumWorkloadLimits.from_dict(
            {
                "max_candidates": cfg.max_qsa_candidates,
                "max_marker_qubits": cfg.max_marker_qubits,
                "max_component_states": cfg.max_component_states,
                "max_steps_per_candidate": cfg.steps,
            }
        )
        qsa_request = build_quantum_search_request(
            profile=profile,
            interpretation=initial_interpretation,
            recommendation=initial_recommendation,
            limits=qsa_limits,
        )
        qsa_result = run_quantum_strategy(qsa_request)

    simulation_payload: Dict[str, Any] = {}
    post_interpretation: Dict[str, Any] = {}
    post_recommendation: Dict[str, Any] = {}
    if cfg.run_simulation:
        sim = create_profile_simulation(
            profile,
            healthy=cfg.healthy,
            cancer=cfg.cancer,
            seed=cfg.seed,
            steps=cfg.steps,
            profile_strength=cfg.profile_strength,
            profile_heterogeneity=cfg.profile_heterogeneity,
            immune_pressure=cfg.immune_pressure,
            mutation_rate=cfg.mutation_rate,
            cocktail=selected_cocktail,
        )
        sim.run(cfg.steps)
        experiment_path = output_dir / f"portal_experiment_{profile.id}_{cfg.seed}.json"
        export_json_report(sim, experiment_path)
        final_metrics = _metrics_payload(sim)
        post_interpretation = analyze_signals(sim, profile)
        post_recommendation = recommend_treatments(sim=sim, profile=profile, interpretation=post_interpretation)
        simulation_payload = {
            "experiment_path": str(experiment_path),
            "final_metrics": final_metrics,
            "post_run_summary": post_interpretation.get("plain_english_summary", ""),
        }

    research_loop_plan: Dict[str, Any] = {}
    if cfg.include_research_loop_plan:
        research_loop_plan = ResearchLoopConfig(
            profile=profile.id,
            cocktail=selected_cocktail.name,
            max_auto_experiments=cfg.max_auto_experiments,
            max_steps_per_experiment=cfg.steps,
            healthy=cfg.healthy,
            cancer=cfg.cancer,
            seed=cfg.seed,
            output_dir=str(output_dir / "research_loop"),
            require_user_confirmation_before_start=True,
        ).to_dict()

    mission = {
        "payload_version": PORTAL_PAYLOAD_VERSION,
        "scope_notice": SCOPE_NOTICE,
        "config": cfg.to_dict(),
        "profile": profile.to_dict(),
        "selected_cocktail": selected_cocktail.name,
        "initial_interpretation": initial_interpretation,
        "initial_recommendation": initial_recommendation,
        "qsa_request": qsa_request.to_dict() if qsa_request else {},
        "qsa_result": qsa_result,
        "simulation": simulation_payload,
        "post_run_interpretation": post_interpretation,
        "post_run_recommendation": post_recommendation,
        "research_loop_plan": research_loop_plan,
        "web_handoff": build_web_handoff(),
        "automated_sequence": [
            "load_profile",
            "interpret_markers",
            "rank_cocktails",
            "select_smallest_effective_conceptual_match",
            "build_qsa_plan",
            "run_simulation",
            "reanalyze_survivors",
            "prepare_bounded_research_loop",
            "export_report",
        ],
    }
    mission["stage_cards"] = build_stage_cards(mission)
    mission["hypothesis_index"] = _hypothesis_index(
        simulation_payload.get("final_metrics", {}),
        post_recommendation or initial_recommendation,
        qsa_result,
    )
    mission_path = output_dir / f"portal_mission_{profile.id}_{cfg.seed}.json"
    mission_path.write_text(json.dumps(mission, indent=2, sort_keys=True), encoding="utf-8")
    mission["mission_path"] = str(mission_path)
    return mission


def format_portal_mission_summary(mission: Dict[str, Any]) -> str:
    lines = [
        mission.get("scope_notice", SCOPE_NOTICE),
        "",
        f"Portal mission: {mission.get('profile', {}).get('display_name', '')}",
        f"Selected cocktail: {mission.get('selected_cocktail', '')}",
    ]
    best_qsa = (mission.get("qsa_result") or {}).get("best_candidate") or {}
    if best_qsa:
        lines.append(f"QSA structural candidate: {best_qsa.get('cocktail_name')} ({float(best_qsa.get('structural_score', 0.0)):.3f})")
    sim = mission.get("simulation") or {}
    metrics = sim.get("final_metrics") or {}
    if metrics:
        lines.append(f"Simulation final: cancer {metrics.get('cancer_alive')}, healthy {metrics.get('healthy_alive')}")
    index = mission.get("hypothesis_index") or {}
    if index:
        lines.append(f"Hypothesis index: {float(index.get('hypothesis_strength_index', 0.0)):.3f}")
        lines.append(f"Model risk index: {float(index.get('model_risk_index', 0.0)):.3f}")
    lines.append(f"Mission JSON: {mission.get('mission_path', '')}")
    return "\n".join(lines)
