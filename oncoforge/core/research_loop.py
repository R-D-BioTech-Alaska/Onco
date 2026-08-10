"""Bounded automated research loop for OncoForge."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cancer_profiles import SCOPE_NOTICE, create_profile_simulation, find_cancer_profile
from .exporter import export_json_report
from .local_ai import LocalAIConfig, analyze_experiment_with_ai
from .presets import default_cocktails
from .signal_interpreter import analyze_signals
from .treatment_matcher import recommend_treatments


@dataclass
class ResearchLoopConfig:
    profile: str
    cocktail: str = ""
    max_auto_experiments: int = 10
    max_steps_per_experiment: int = 300
    max_total_runtime_minutes: int = 30
    require_user_confirmation_before_start: bool = True
    healthy: int = 400
    cancer: int = 120
    seed: int = 1729
    output_dir: str = "outputs/research_loop"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchLoopConfig":
        base = cls(profile=str(data.get("profile", "")))
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        base.max_auto_experiments = max(1, int(base.max_auto_experiments))
        base.max_steps_per_experiment = max(1, int(base.max_steps_per_experiment))
        base.max_total_runtime_minutes = max(1, int(base.max_total_runtime_minutes))
        base.healthy = max(0, int(base.healthy))
        base.cancer = max(0, int(base.cancer))
        base.seed = int(base.seed)
        return base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _choose_cocktail(name: str):
    cocktails = default_cocktails()
    if not name:
        return cocktails[-1]
    requested = "".join(ch for ch in name.lower() if ch.isalnum())
    for cocktail in cocktails:
        key = "".join(ch for ch in cocktail.name.lower() if ch.isalnum())
        if key == requested or requested in key:
            return cocktail
    raise ValueError(f"Unknown cocktail for research loop: {name}")


def _validate_ai_suggestion(_text: str) -> Dict[str, Any]:
    # Conservative parser: keep AI suggestions advisory unless a future schema is added.
    return {"accepted": False, "reason": "AI suggestions are recorded as text only unless they match an explicit future schema."}


def run_research_loop(config: ResearchLoopConfig, ai_config: Optional[LocalAIConfig] = None, confirmed: bool = False) -> Dict[str, Any]:
    if config.require_user_confirmation_before_start and not confirmed:
        return {
            "ok": False,
            "message": "Research loop requires confirmation before start.",
            "experiments": [],
            "scope_notice": SCOPE_NOTICE,
        }
    profile = find_cancer_profile(config.profile)
    output = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    max_seconds = config.max_total_runtime_minutes * 60
    experiments: List[Dict[str, Any]] = []
    cocktail_name = config.cocktail or (profile.starter_cocktails[0] if profile.starter_cocktails else "Full conceptual swarm")

    for index in range(config.max_auto_experiments):
        if time.monotonic() - start > max_seconds:
            break
        cocktail = _choose_cocktail(cocktail_name)
        sim = create_profile_simulation(
            profile,
            healthy=config.healthy,
            cancer=config.cancer,
            seed=config.seed + index,
            steps=config.max_steps_per_experiment,
            cocktail=cocktail,
        )
        sim.run(config.max_steps_per_experiment)
        signal_result = analyze_signals(sim, profile)
        recommendation = recommend_treatments(sim=sim, profile=profile, interpretation=signal_result)
        report_path = output / f"experiment_{index + 1:02d}.json"
        export_json_report(sim, report_path)
        ai_result = {}
        suggestion_validation = {}
        if ai_config and ai_config.enabled and ai_config.allow_continuous_experiments:
            ai_result = analyze_experiment_with_ai(ai_config, sim, signal_result, recommendation)
            suggestion_validation = _validate_ai_suggestion(ai_result.get("response", ""))
        latest = sim.analytics.latest()
        row = {
            "index": index + 1,
            "profile": profile.id,
            "cocktail": cocktail.name,
            "seed": sim.config.random_seed,
            "steps": config.max_steps_per_experiment,
            "final_cancer": latest.cancer_alive if latest else None,
            "final_healthy": latest.healthy_alive if latest else None,
            "dosing_phase": latest.dosing_phase if latest else "",
            "top_targetable_signals": [item["signal"] for item in signal_result.get("top_targetable_signals", [])[:5]],
            "best_match": (recommendation.get("best_first_line_conceptual_match") or {}).get("cocktail_name"),
            "report": str(report_path),
            "ai_result": ai_result,
            "ai_suggestion_validation": suggestion_validation,
        }
        experiments.append(row)
        # Non-AI loop remains bounded and deterministic: try the current best match next.
        next_match = row.get("best_match")
        if next_match:
            cocktail_name = str(next_match)

    final = {
        "ok": True,
        "scope_notice": SCOPE_NOTICE,
        "config": config.to_dict(),
        "experiments_run": len(experiments),
        "experiments": experiments,
        "summary": (
            f"Ran {len(experiments)} bounded OncoForge experiments. "
            "Results are conceptual simulations only, not clinical recommendations."
        ),
    }
    final_path = output / "research_loop_summary.json"
    final_path.write_text(json.dumps(final, indent=2, sort_keys=True), encoding="utf-8")
    final["summary_path"] = str(final_path)
    return final
