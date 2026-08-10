"""Automated experiment workflows for OncoForge."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .experiment_runner import compare_cocktails, export_results_csv, format_results_table
from .exporter import export_html_report, export_json_report
from .models import Cocktail, SimulationConfig
from .presets import default_cocktails, load_cancer_presets
from .simulation import Simulation


@dataclass(frozen=True)
class AutomationProfile:
    """A named workflow preset for users who do not want to tune every field."""

    key: str
    label: str
    description: str
    name: str
    preset_name: str
    cocktail_name: str
    steps: int
    healthy: int
    cancer: int
    seed: int = 1729
    compare_seeds: tuple[int, ...] = (1729, 1730, 1731)
    output_dir: str = "outputs/automated"
    compare: bool = True
    auto_select_cocktail: bool = False
    compare_limit: int = 12

    def to_run_kwargs(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "preset_name": self.preset_name,
            "cocktail_name": self.cocktail_name,
            "steps": self.steps,
            "healthy": self.healthy,
            "cancer": self.cancer,
            "seed": self.seed,
            "output_dir": self.output_dir,
            "compare": self.compare,
            "compare_seeds": list(self.compare_seeds),
            "compare_limit": self.compare_limit,
            "auto_select_cocktail": self.auto_select_cocktail,
        }

    def to_dict(self) -> Dict[str, Any]:
        data = self.to_run_kwargs()
        data.update({"key": self.key, "label": self.label, "description": self.description})
        return data


_DEFAULT_OPTIONS: Dict[str, Any] = {
    "name": "Automated OncoForge experiment",
    "preset_name": "Generic p53-loss carcinoma",
    "cocktail_name": "Full conceptual swarm",
    "steps": 100,
    "healthy": 250,
    "cancer": 100,
    "seed": 1729,
    "output_dir": "outputs/automated",
    "compare": True,
    "compare_seeds": [1729, 1730, 1731],
    "compare_limit": 12,
    "auto_select_cocktail": False,
}


_AUTOMATION_PROFILES: List[AutomationProfile] = [
    AutomationProfile(
        key="fast_triage",
        label="Fast triage",
        description="Small, quick run for checking that a preset/cocktail behaves sensibly.",
        name="Fast triage automated run",
        preset_name="Generic p53-loss carcinoma",
        cocktail_name="Full conceptual swarm",
        steps=40,
        healthy=120,
        cancer=50,
        compare_seeds=(1729, 1730),
        compare_limit=8,
    ),
    AutomationProfile(
        key="balanced_exploration",
        label="Balanced exploration",
        description="Default-sized exploratory run with reports and cocktail ranking.",
        name="Balanced automated exploration",
        preset_name="Generic p53-loss carcinoma",
        cocktail_name="Full conceptual swarm",
        steps=100,
        healthy=250,
        cancer=100,
        compare_seeds=(1729, 1730, 1731),
        compare_limit=12,
    ),
    AutomationProfile(
        key="best_cocktail_scout",
        label="Best cocktail scout",
        description="Ranks bundled cocktails first, then runs the top-scoring option.",
        name="Auto-selected cocktail scout",
        preset_name="Generic p53-loss carcinoma",
        cocktail_name="Full conceptual swarm",
        steps=80,
        healthy=220,
        cancer=90,
        compare_seeds=(1729, 1730, 1731),
        auto_select_cocktail=True,
        compare_limit=12,
    ),
    AutomationProfile(
        key="immune_escape_focus",
        label="Immune escape focus",
        description="MHC-low/checkpoint-heavy scenario with innate and NK-style pressure.",
        name="Immune escape focused run",
        preset_name="MHC-low immune escape clone",
        cocktail_name="Innate immune cleanup bath",
        steps=120,
        healthy=260,
        cancer=110,
        compare_seeds=(1729, 1730, 1731),
        compare_limit=12,
    ),
    AutomationProfile(
        key="repair_defect_focus",
        label="Repair defect focus",
        description="BRCA-like repair-stressed clone with damage-to-death pressure.",
        name="Repair defect focused run",
        preset_name="BRCA-defective repair-stressed clone",
        cocktail_name="Damage-to-death cascade",
        steps=120,
        healthy=260,
        cancer=110,
        compare_seeds=(1729, 1730, 1731),
        compare_limit=12,
    ),
    AutomationProfile(
        key="hypoxia_invasion_focus",
        label="Hypoxia invasion focus",
        description="Hypoxic invasive clone with microenvironment-gated pressure.",
        name="Hypoxia invasion focused run",
        preset_name="Hypoxic invasive clone",
        cocktail_name="Hypoxic tumor bath",
        steps=120,
        healthy=260,
        cancer=110,
        compare_seeds=(1729, 1730, 1731),
        compare_limit=12,
    ),
]


def _key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _item_name(item: Any) -> str:
    if hasattr(item, "name"):
        return str(item.name)
    return str(item.get("name", ""))


def lookup_named(items: Iterable[Any], name: Optional[str], label: str) -> Any:
    item_list = list(items)
    if not name:
        return item_list[0] if item_list else None
    requested = _key(name)
    keyed = {_key(_item_name(item)): item for item in item_list}
    found = keyed.get(requested)
    if found is None:
        matches = [item for key, item in keyed.items() if key.startswith(requested) or requested in key]
        if len(matches) == 1:
            found = matches[0]
    if found is None:
        available = ", ".join(_item_name(item) for item in item_list)
        raise ValueError(f"Unknown {label}: {name}. Available: {available}")
    return found


def slugify(name: str) -> str:
    cleaned = []
    last_was_sep = False
    for char in str(name).lower():
        if char.isalnum():
            cleaned.append(char)
            last_was_sep = False
        elif not last_was_sep:
            cleaned.append("_")
            last_was_sep = True
    return "".join(cleaned).strip("_") or "oncoforge_run"


def automation_profiles() -> List[AutomationProfile]:
    return list(_AUTOMATION_PROFILES)


def resolve_automation_profile(name: Optional[str]) -> Optional[AutomationProfile]:
    if not name:
        return None
    requested = _key(name)
    matches: List[AutomationProfile] = []
    for profile in _AUTOMATION_PROFILES:
        keys = {_key(profile.key), _key(profile.label), _key(profile.name)}
        if requested in keys:
            return profile
        if any(key.startswith(requested) or requested in key for key in keys):
            matches.append(profile)
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(profile.label for profile in _AUTOMATION_PROFILES)
    raise ValueError(f"Unknown automation profile: {name}. Available: {available}")


def automation_profile_options(name: str) -> Dict[str, Any]:
    profile = resolve_automation_profile(name)
    if profile is None:
        raise ValueError("Automation profile name is required.")
    return profile.to_dict()


def build_automation_options(profile_name: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    profile = resolve_automation_profile(profile_name)
    options = profile.to_run_kwargs() if profile else dict(_DEFAULT_OPTIONS)
    for key, value in (overrides or {}).items():
        if value is not None:
            options[key] = value
    return options


def summarize_cocktail_results(results: Iterable[Any]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Any]] = {}
    for result in results:
        grouped.setdefault(str(result.cocktail_name), []).append(result)

    summary: List[Dict[str, Any]] = []
    for cocktail_name, rows in grouped.items():
        runs = len(rows)
        if runs == 0:
            continue
        summary.append(
            {
                "cocktail_name": cocktail_name,
                "runs": runs,
                "mean_score": sum(r.score for r in rows) / runs,
                "mean_final_cancer": sum(r.final_cancer for r in rows) / runs,
                "mean_final_healthy": sum(r.final_healthy for r in rows) / runs,
                "mean_cancer_suppression_fraction": sum(r.cancer_suppression_fraction for r in rows) / runs,
                "mean_healthy_preservation_fraction": sum(r.healthy_preservation_fraction for r in rows) / runs,
                "mean_immune_activation": sum(r.final_immune_activation for r in rows) / runs,
                "total_escape_events": sum(r.total_escape_events for r in rows),
                "total_healthy_damage_events": sum(r.total_healthy_damage_events for r in rows),
            }
        )
    summary.sort(
        key=lambda row: (
            float(row["mean_score"]),
            float(row["mean_cancer_suppression_fraction"]),
            float(row["mean_healthy_preservation_fraction"]),
        ),
        reverse=True,
    )
    return summary


def run_automated_protocol(
    *,
    name: str = "Automated OncoForge experiment",
    preset_name: Optional[str] = None,
    cocktail_name: str = "Full conceptual swarm",
    steps: int = 100,
    healthy: int = 250,
    cancer: int = 100,
    seed: int = 1729,
    output_dir: str | Path = "outputs/automated",
    compare: bool = True,
    compare_seeds: Optional[Iterable[int]] = None,
    compare_limit: int = 12,
    auto_select_cocktail: bool = False,
) -> Dict[str, Any]:
    """Run a complete local workflow: simulation, reports, and optional comparison."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    cocktails = default_cocktails()
    preset = lookup_named(load_cancer_presets(), preset_name, "preset") if preset_name else None
    steps = int(steps)
    seed = int(seed)
    healthy = int(healthy)
    cancer = int(cancer)
    compare_limit = int(compare_limit)
    cfg = SimulationConfig(
        name=name,
        steps=steps,
        initial_healthy_cells=healthy,
        initial_cancer_cells=cancer,
        random_seed=seed,
    )
    stem = slugify(f"{name}_{seed}")
    paths: Dict[str, Path] = {}

    requested_cocktail_name = cocktail_name
    selection_results = None
    selection_summary: List[Dict[str, Any]] = []
    selection_table = ""
    if auto_select_cocktail:
        seeds = list(compare_seeds or [seed, seed + 1, seed + 2])
        selection_results = compare_cocktails(
            config=cfg,
            cancer_preset_name=preset.get("name") if preset else None,
            steps=steps,
            seeds=seeds,
        )
        selection_summary = summarize_cocktail_results(selection_results)
        if not selection_summary:
            raise RuntimeError("Cocktail auto-selection produced no results.")
        cocktail_name = str(selection_summary[0]["cocktail_name"])
        selection_csv = output_path / f"{stem}_selection.csv"
        selection_json = output_path / f"{stem}_selection.json"
        selection_summary_json = output_path / f"{stem}_selection_summary.json"
        export_results_csv(selection_results, selection_csv)
        selection_json.write_text(json.dumps([r.to_dict() for r in selection_results], indent=2, sort_keys=True), encoding="utf-8")
        selection_summary_json.write_text(json.dumps(selection_summary, indent=2, sort_keys=True), encoding="utf-8")
        paths["selection_csv"] = selection_csv
        paths["selection_json"] = selection_json
        paths["selection_summary_json"] = selection_summary_json
        selection_table = format_results_table(selection_results, limit=compare_limit)

    cocktail = lookup_named(cocktails, cocktail_name, "cocktail")
    sim = Simulation(cfg, cocktail=Cocktail.from_dict(cocktail.to_dict()))
    sim.reset()
    if preset:
        sim.set_cancer_preset(preset)
    sim.run(steps)

    paths.update({
        "html": output_path / f"{stem}.html",
        "json": output_path / f"{stem}.json",
        "csv": output_path / f"{stem}_metrics.csv",
        "experiment": output_path / f"{stem}_experiment.json",
    })
    export_html_report(sim, paths["html"])
    export_json_report(sim, paths["json"])
    sim.analytics.export_csv(paths["csv"])
    sim.save_experiment(paths["experiment"])

    compare_payload = None
    compare_table = ""
    if compare:
        seeds = list(compare_seeds or [seed, seed + 1, seed + 2])
        results = selection_results or compare_cocktails(config=cfg, cancer_preset_name=preset.get("name") if preset else None, steps=steps, seeds=seeds)
        compare_csv = output_path / f"{stem}_comparison.csv"
        compare_json = output_path / f"{stem}_comparison.json"
        export_results_csv(results, compare_csv)
        compare_json.write_text(json.dumps([r.to_dict() for r in results], indent=2, sort_keys=True), encoding="utf-8")
        paths["comparison_csv"] = compare_csv
        paths["comparison_json"] = compare_json
        compare_table = format_results_table(results, limit=compare_limit)
        compare_payload = [r.to_dict() for r in results[:compare_limit]]

    return {
        "name": name,
        "preset": preset.get("name") if preset else "not recorded",
        "requested_cocktail": requested_cocktail_name,
        "cocktail": cocktail.name,
        "selected_cocktail": cocktail.name,
        "auto_select_cocktail": bool(auto_select_cocktail),
        "steps": steps,
        "seed": seed,
        "paths": {key: str(value) for key, value in paths.items()},
        "summary": sim.analytics.summary_text(),
        "selection_table": selection_table,
        "selection_summary": selection_summary,
        "comparison_table": compare_table,
        "top_comparison_results": compare_payload or [],
    }
