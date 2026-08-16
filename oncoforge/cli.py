"""Command line interface for OncoForge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.automation import automation_profiles, build_automation_options, run_automated_protocol
from .core.experiment_runner import compare_cocktails, export_results_csv, format_results_table
from .core.models import SimulationConfig
from .core.presets import default_cocktails, load_cancer_presets
from .core.simulation import Simulation
from .core.exporter import export_html_report, export_json_report, export_report_by_suffix
from .core.interpretation import assess_cure_pathway, interpret_latest
from .core.sweep import export_sweep_csv, export_sweep_json, format_sweep_table, run_parameter_sweep
from .core.cancer_profiles import create_profile_simulation, find_cancer_profile, load_cancer_profiles, profile_summary_text
from .core.local_ai import LocalAIConfig, analyze_experiment_with_ai, check_local_ai_available, load_ai_config
from .core.quantum_strategy import (
    QuantumWorkloadLimits,
    build_quantum_search_request,
    format_quantum_strategy_summary,
    run_quantum_strategy,
)
from .core.portal_mission import PortalMissionConfig, build_portal_mission, format_portal_mission_summary
from .core.research_loop import ResearchLoopConfig, run_research_loop
from .core.signal_interpreter import analyze_signals
from .core.treatment_matcher import recommend_treatments
from .core.evidence import load_evidence_fabric
from .core.target_forge import (
    TargetForgeConfig,
    export_target_forge_report,
    format_target_forge_summary,
    run_target_forge,
)


def _key(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _item_name(item) -> str:
    if hasattr(item, "name"):
        return str(item.name)
    return str(item.get("name", ""))


def _lookup_named(items, name: str | None, label: str):
    if not name:
        return None
    by_key = {_key(_item_name(item)): item for item in items}
    requested = _key(name)
    found = by_key.get(requested)
    if found is None:
        matches = [item for key, item in by_key.items() if key.startswith(requested) or requested in key]
        if len(matches) == 1:
            found = matches[0]
    if found is None:
        available = ", ".join(_item_name(item) for item in items)
        raise SystemExit(f"Unknown {label}: {name}. Available: {available}")
    return found


def _load_saved_simulation(path: str | Path) -> Simulation:
    try:
        return Simulation.load_experiment(path)
    except Exception as exc:
        raise SystemExit(
            f"Could not load experiment JSON: {path}. Use a saved experiment file, not only a report JSON. Details: {exc}"
        )




def _add_adaptive_dosing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--adaptive-dosing", action="store_true", help="Enable adaptive tapering based on cancer burden and toxicity signals")
    parser.add_argument("--auto-shutoff", action="store_true", help="Allow treatment shutdown only after zero-cancer confirmation")
    parser.add_argument("--no-remission-surveillance", action="store_true", help="After confirmed clearance, stop all agents instead of leaving low-intensity surveillance")
    parser.add_argument("--taper-count", type=int, default=None, help="Cancer count at or below which adaptive tapering begins")
    parser.add_argument("--surveillance-count", type=int, default=None, help="Cancer count at or below which minimal-residual watch begins")
    parser.add_argument("--zero-confirmation-steps", type=int, default=None, help="Consecutive zero-cancer steps required before auto-shutoff")
    parser.add_argument("--adaptive-minimum-intensity", type=float, default=None, help="Minimum treatment intensity while cancer remains detectable")
    parser.add_argument("--remission-surveillance-intensity", type=float, default=None, help="Treatment intensity during remission confirmation/surveillance")
    parser.add_argument("--recovery-rate", type=float, default=None, help="Post-clearance recovery rate for inflammation/immune pressure")


def _apply_adaptive_args(cfg: SimulationConfig, args) -> SimulationConfig:
    if getattr(args, "adaptive_dosing", False):
        cfg.adaptive_dosing_enabled = True
    if getattr(args, "auto_shutoff", False):
        cfg.auto_shutoff_enabled = True
    if getattr(args, "no_remission_surveillance", False):
        cfg.remission_surveillance_enabled = False
    if getattr(args, "taper_count", None) is not None:
        cfg.taper_start_cancer_count = int(args.taper_count)
    if getattr(args, "surveillance_count", None) is not None:
        cfg.surveillance_start_cancer_count = int(args.surveillance_count)
    if getattr(args, "zero_confirmation_steps", None) is not None:
        cfg.zero_cancer_confirmation_steps = int(args.zero_confirmation_steps)
    if getattr(args, "adaptive_minimum_intensity", None) is not None:
        cfg.adaptive_minimum_intensity = float(args.adaptive_minimum_intensity)
    if getattr(args, "remission_surveillance_intensity", None) is not None:
        cfg.remission_surveillance_intensity = float(args.remission_surveillance_intensity)
    if getattr(args, "recovery_rate", None) is not None:
        cfg.recovery_rate = float(args.recovery_rate)
    return cfg

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OncoForge conceptual cancer-systems simulator")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run one simulation headlessly and export outputs")
    run.add_argument("--steps", type=int, default=100)
    run.add_argument("--healthy", type=int, default=300)
    run.add_argument("--cancer", type=int, default=120)
    run.add_argument("--seed", type=int, default=1729)
    run.add_argument("--cocktail", default="Full conceptual swarm")
    run.add_argument("--preset", default=None)
    run.add_argument("--name", default="OncoForge headless run")
    run.add_argument("--export", default=None, help="Export by extension: .html, .json, or .csv")
    run.add_argument("--out", default="outputs/reports/headless_report.html")
    run.add_argument("--html", default=None, help="Explicit HTML report path")
    run.add_argument("--json", default=None, help="Explicit JSON report path")
    run.add_argument("--csv", default=None, help="Explicit metric CSV path")
    run.add_argument("--interpret", action="store_true", help="Print a plain-English interpretation after the run")
    _add_adaptive_dosing_args(run)

    cmp = sub.add_parser("compare", help="Compare bundled cocktails headlessly")
    cmp.add_argument("--steps", type=int, default=100)
    cmp.add_argument("--healthy", type=int, default=250)
    cmp.add_argument("--cancer", type=int, default=100)
    cmp.add_argument("--seeds", default="1729,1730,1731")
    cmp.add_argument("--preset", default=None)
    cmp.add_argument("--cocktails", default=None, help="Comma-separated cocktail names or snake-case aliases")
    cmp.add_argument("--csv", default=None)
    cmp.add_argument("--json", default=None)
    cmp.add_argument("--limit", type=int, default=15)
    _add_adaptive_dosing_args(cmp)

    rem = sub.add_parser("remission-test", help="Run a clearance plus post-clearance watch experiment")
    rem.add_argument("--steps", type=int, default=None, help="Total steps. Defaults to treat-steps + watch-steps")
    rem.add_argument("--treat-steps", type=int, default=120)
    rem.add_argument("--watch-steps", type=int, default=250)
    rem.add_argument("--healthy", type=int, default=700)
    rem.add_argument("--cancer", type=int, default=300)
    rem.add_argument("--seed", type=int, default=1729)
    rem.add_argument("--cocktail", default="Full conceptual swarm")
    rem.add_argument("--preset", default="Generic p53-loss carcinoma")
    rem.add_argument("--name", default="OncoForge remission test")
    rem.add_argument("--export", default="outputs/reports/remission_test.html", help="Export by extension: .html, .json, or .csv")
    _add_adaptive_dosing_args(rem)

    sweep = sub.add_parser("sweep", help="Sweep one parameter across values and rank outcomes")
    sweep.add_argument("--parameter", required=True, help="Parameter to sweep, e.g. treatment, immune, oxygen, micro.acidity, config.recovery_rate")
    sweep.add_argument("--values", required=True, help="Comma-separated values, e.g. 0.5,0.75,1.0,1.25")
    sweep.add_argument("--steps", type=int, default=100)
    sweep.add_argument("--healthy", type=int, default=250)
    sweep.add_argument("--cancer", type=int, default=100)
    sweep.add_argument("--seed", type=int, default=1729)
    sweep.add_argument("--cocktail", default="Full conceptual swarm")
    sweep.add_argument("--preset", default=None)
    sweep.add_argument("--csv", default=None)
    sweep.add_argument("--json", default=None)
    sweep.add_argument("--limit", type=int, default=20)
    _add_adaptive_dosing_args(sweep)

    auto = sub.add_parser("auto", help="Run an automated simulation, exports, and optional comparison")
    auto.add_argument("--profile", default=None, help="Named workflow profile, such as fast_triage or best_cocktail_scout")
    auto.add_argument("--list-profiles", action="store_true", help="List automation profiles and exit")
    auto.add_argument("--name", default=None)
    auto.add_argument("--preset", default=None)
    auto.add_argument("--cocktail", default=None)
    auto.add_argument("--steps", type=int, default=None)
    auto.add_argument("--healthy", type=int, default=None)
    auto.add_argument("--cancer", type=int, default=None)
    auto.add_argument("--seed", type=int, default=None)
    auto.add_argument("--compare-seeds", default=None)
    auto.add_argument("--output-dir", default=None)
    auto.add_argument("--limit", type=int, default=None)
    auto.add_argument("--no-compare", action="store_true")
    auto.add_argument("--auto-select-cocktail", action="store_true", help="Rank cocktails first, then run the top-scoring cocktail")

    sub.add_parser("list-profiles", help="List bundled cancer profiles")

    profile_info = sub.add_parser("profile-info", help="Show cancer profile details")
    profile_info.add_argument("--profile", required=True)

    run_profile = sub.add_parser("run-profile", help="Run a simulation from a cancer profile")
    run_profile.add_argument("--profile", required=True)
    run_profile.add_argument("--cocktail", default="Full conceptual swarm")
    run_profile.add_argument("--steps", type=int, default=200)
    run_profile.add_argument("--healthy", type=int, default=800)
    run_profile.add_argument("--cancer", type=int, default=200)
    run_profile.add_argument("--seed", type=int, default=1729)
    run_profile.add_argument("--profile-strength", type=float, default=1.0)
    run_profile.add_argument("--heterogeneity", type=float, default=0.15)
    run_profile.add_argument("--immune-pressure", type=float, default=None)
    run_profile.add_argument("--mutation-rate", type=float, default=None)
    run_profile.add_argument("--export", default="outputs/reports/profile_run.html")
    run_profile.add_argument("--save-experiment", default=None)
    _add_adaptive_dosing_args(run_profile)

    interpret_signals = sub.add_parser("interpret-signals", help="Analyze cancer-vs-healthy signals in a saved experiment")
    interpret_signals.add_argument("--experiment", required=True)
    interpret_signals.add_argument("--json", default=None)

    recommend = sub.add_parser("recommend-cocktail", help="Recommend conceptual cocktails from a profile or saved experiment")
    recommend.add_argument("--profile", default=None)
    recommend.add_argument("--experiment", default=None)
    recommend.add_argument("--json", default=None)

    qsa_plan = sub.add_parser("qsa-plan", help="Build a bounded QSA-ready structural search plan")
    qsa_plan.add_argument("--profile", required=True)
    qsa_plan.add_argument("--max-candidates", type=int, default=12)
    qsa_plan.add_argument("--max-marker-qubits", type=int, default=16)
    qsa_plan.add_argument("--max-component-states", type=int, default=4096)
    qsa_plan.add_argument("--json", default=None)

    target_forge = sub.add_parser(
        "target-forge",
        help="Discover evidence-traceable tumor-versus-normal targets and logic gates",
    )
    target_forge.add_argument("--input", required=True, help="OncoForge evidence fabric JSON")
    target_forge.add_argument("--output", default="outputs/target_forge/report.json")
    target_forge.add_argument("--min-tumor-coverage", type=float, default=0.60)
    target_forge.add_argument("--min-clone-coverage", type=float, default=0.50)
    target_forge.add_argument("--max-normal-activation", type=float, default=0.05)
    target_forge.add_argument("--max-critical-normal-activation", type=float, default=0.0)
    target_forge.add_argument("--max-unknown-normal-fraction", type=float, default=0.0)
    target_forge.add_argument("--max-unknown-clone-fraction", type=float, default=0.0)
    target_forge.add_argument("--max-targets", type=int, default=16)
    target_forge.add_argument("--max-candidates", type=int, default=1500)
    target_forge.add_argument("--max-results", type=int, default=50)
    target_forge.add_argument("--require-dependency", action="store_true")
    target_forge.add_argument("--min-dependency-support", type=float, default=0.0)
    target_forge.add_argument("--allow-transcript-fallback", action="store_true")
    target_forge.add_argument("--allow-missing-critical-normal-cohort", action="store_true")
    target_forge.add_argument("--no-single", action="store_true")
    target_forge.add_argument("--no-and", action="store_true")
    target_forge.add_argument("--no-or", action="store_true")
    target_forge.add_argument("--no-and-not", action="store_true")
    target_forge.add_argument("--no-qsa", action="store_true")

    portal = sub.add_parser("portal-session", help="Build a full webpage-ready OncoForge mission payload")
    portal.add_argument("--profile", required=True)
    portal.add_argument("--cocktail", default="")
    portal.add_argument("--steps", type=int, default=120)
    portal.add_argument("--healthy", type=int, default=300)
    portal.add_argument("--cancer", type=int, default=100)
    portal.add_argument("--seed", type=int, default=1729)
    portal.add_argument("--profile-strength", type=float, default=1.0)
    portal.add_argument("--heterogeneity", type=float, default=0.15)
    portal.add_argument("--immune-pressure", type=float, default=None)
    portal.add_argument("--mutation-rate", type=float, default=None)
    portal.add_argument("--max-auto-experiments", type=int, default=5)
    portal.add_argument("--max-qsa-candidates", type=int, default=12)
    portal.add_argument("--max-marker-qubits", type=int, default=16)
    portal.add_argument("--max-component-states", type=int, default=4096)
    portal.add_argument("--output-dir", default="outputs/portal")
    portal.add_argument("--no-run", action="store_true", help="Build the portal mission without running the simulation")
    portal.add_argument("--no-qsa", action="store_true", help="Build the portal mission without the QSA structural plan")
    portal.add_argument("--no-auto-select", action="store_true", help="Use the requested cocktail instead of auto-selecting the top conceptual match")
    portal.add_argument("--json", default=None, help="Optional copy of the mission payload JSON")

    serve_api = sub.add_parser("serve-api", help="Run the local OncoForge portal API")
    serve_api.add_argument("--host", default="127.0.0.1")
    serve_api.add_argument("--port", type=int, default=8765)

    ai_test = sub.add_parser("ai-test", help="Test optional local AI connection")
    ai_test.add_argument("--provider", default=None)
    ai_test.add_argument("--base-url", default=None)
    ai_test.add_argument("--model", default=None)

    ai_analyze = sub.add_parser("ai-analyze", help="Send a saved simulation summary to local AI")
    ai_analyze.add_argument("--experiment", required=True)
    ai_analyze.add_argument("--provider", default=None)
    ai_analyze.add_argument("--base-url", default=None)
    ai_analyze.add_argument("--model", default=None)

    research = sub.add_parser("research-loop", help="Run a bounded auto-experiment loop")
    research.add_argument("--profile", required=True)
    research.add_argument("--cocktail", default="")
    research.add_argument("--max-experiments", type=int, default=5)
    research.add_argument("--steps", type=int, default=150)
    research.add_argument("--healthy", type=int, default=400)
    research.add_argument("--cancer", type=int, default=120)
    research.add_argument("--seed", type=int, default=1729)
    research.add_argument("--output-dir", default="outputs/research_loop")
    research.add_argument("--confirmed", action="store_true", help="Confirm bounded loop start")

    sub.add_parser("list-presets", help="List bundled cancer presets")
    sub.add_parser("list-cocktails", help="List bundled cocktail presets")
    sub.add_parser("list-automation-profiles", help="List automated workflow profiles")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        from .ui.app import main as gui_main
        gui_main()
        return 0

    if args.command == "list-presets":
        for p in load_cancer_presets():
            print(p.get("name", "Unnamed"))
        return 0

    if args.command == "list-cocktails":
        for c in default_cocktails():
            print(c.name)
        return 0

    if args.command == "list-automation-profiles":
        for profile in automation_profiles():
            print(f"{profile.key}: {profile.label} - {profile.description}")
        return 0

    if args.command == "serve-api":
        from .web_api import serve

        serve(host=args.host, port=args.port)
        return 0

    if args.command == "list-profiles":
        for profile in load_cancer_profiles():
            print(f"{profile.id}: {profile.display_name} [{profile.category}]")
        return 0

    if args.command == "profile-info":
        profile = find_cancer_profile(args.profile)
        print(profile_summary_text(profile))
        return 0

    if args.command == "run-profile":
        profile = find_cancer_profile(args.profile)
        cocktail = _lookup_named(default_cocktails(), args.cocktail, "cocktail")
        sim = create_profile_simulation(
            profile,
            healthy=args.healthy,
            cancer=args.cancer,
            seed=args.seed,
            steps=args.steps,
            profile_strength=args.profile_strength,
            profile_heterogeneity=args.heterogeneity,
            immune_pressure=args.immune_pressure,
            mutation_rate=args.mutation_rate,
            cocktail=cocktail,
        )
        _apply_adaptive_args(sim.config, args)
        sim.run(args.steps)
        out = Path(args.export)
        if not out.is_absolute():
            out = Path.cwd() / out
        export_report_by_suffix(sim, out)
        if args.save_experiment:
            save_path = Path(args.save_experiment)
            if not save_path.is_absolute():
                save_path = Path.cwd() / save_path
            sim.save_experiment(save_path)
            print(f"Experiment: {save_path}")
        print(sim.analytics.summary_text())
        print()
        print(analyze_signals(sim, profile)["plain_english_summary"])
        print()
        print(recommend_treatments(sim=sim, profile=profile)["plain_english_summary"])
        print(f"Export: {out}")
        return 0

    if args.command == "interpret-signals":
        sim = _load_saved_simulation(args.experiment)
        result = analyze_signals(sim)
        print(result["plain_english_summary"])
        print("Top targetable signals:")
        for row in result.get("top_targetable_signals", [])[:10]:
            print(f"  {row['signal']}: targetability {row['targetability_score']:.3f}, cancer {row['cancer_mean']:.3f}, healthy {row['healthy_mean']:.3f}")
        if args.json:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            print(f"JSON: {out}")
        return 0

    if args.command == "recommend-cocktail":
        if args.experiment:
            sim = _load_saved_simulation(args.experiment)
            profile = find_cancer_profile(args.profile) if args.profile else None
            result = recommend_treatments(sim=sim, profile=profile)
        elif args.profile:
            profile = find_cancer_profile(args.profile)
            sim = create_profile_simulation(profile, healthy=80, cancer=40, steps=1)
            result = recommend_treatments(sim=sim, profile=profile)
        else:
            raise SystemExit("recommend-cocktail requires --profile or --experiment.")
        print(result["plain_english_summary"])
        if args.json:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            print(f"JSON: {out}")
        return 0

    if args.command == "qsa-plan":
        profile = find_cancer_profile(args.profile)
        sim = create_profile_simulation(profile, healthy=80, cancer=40, steps=1)
        signal_result = analyze_signals(sim, profile)
        recommendation = recommend_treatments(sim=sim, profile=profile, interpretation=signal_result)
        limits = QuantumWorkloadLimits.from_dict(
            {
                "max_candidates": args.max_candidates,
                "max_marker_qubits": args.max_marker_qubits,
                "max_component_states": args.max_component_states,
            }
        )
        request = build_quantum_search_request(
            profile=profile,
            interpretation=signal_result,
            recommendation=recommendation,
            limits=limits,
        )
        result = run_quantum_strategy(request)
        print(format_quantum_strategy_summary(result))
        if args.json:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"request": request.to_dict(), "result": result}, indent=2, sort_keys=True), encoding="utf-8")
            print(f"JSON: {out}")
        return 0

    if args.command == "target-forge":
        fabric = load_evidence_fabric(args.input)
        config = TargetForgeConfig.from_dict(
            {
                "min_tumor_coverage": args.min_tumor_coverage,
                "min_clone_coverage": args.min_clone_coverage,
                "max_normal_activation": args.max_normal_activation,
                "max_critical_normal_activation": args.max_critical_normal_activation,
                "max_unknown_normal_fraction": args.max_unknown_normal_fraction,
                "max_unknown_clone_fraction": args.max_unknown_clone_fraction,
                "max_targets": args.max_targets,
                "max_candidates": args.max_candidates,
                "max_results": args.max_results,
                "require_dependency": args.require_dependency,
                "min_dependency_support": args.min_dependency_support,
                "allow_transcript_fallback": args.allow_transcript_fallback,
                "require_critical_normal_samples": not args.allow_missing_critical_normal_cohort,
                "include_single_targets": not args.no_single,
                "include_and": not args.no_and,
                "include_or": not args.no_or,
                "include_and_not": not args.no_and_not,
                "use_qsa": not args.no_qsa,
            }
        )
        report = run_target_forge(fabric, config)
        output = Path(args.output)
        if not output.is_absolute():
            output = Path.cwd() / output
        export_target_forge_report(report, output)
        print(format_target_forge_summary(report))
        print(f"Export: {output}")
        return 0

    if args.command == "portal-session":
        cfg = PortalMissionConfig(
            profile=args.profile,
            cocktail=args.cocktail,
            steps=args.steps,
            healthy=args.healthy,
            cancer=args.cancer,
            seed=args.seed,
            profile_strength=args.profile_strength,
            profile_heterogeneity=args.heterogeneity,
            immune_pressure=args.immune_pressure,
            mutation_rate=args.mutation_rate,
            run_simulation=not args.no_run,
            auto_select_cocktail=not args.no_auto_select,
            include_qsa=not args.no_qsa,
            max_auto_experiments=args.max_auto_experiments,
            max_qsa_candidates=args.max_qsa_candidates,
            max_marker_qubits=args.max_marker_qubits,
            max_component_states=args.max_component_states,
            output_dir=args.output_dir,
        )
        mission = build_portal_mission(cfg)
        print(format_portal_mission_summary(mission))
        if args.json:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(mission, indent=2, sort_keys=True), encoding="utf-8")
            print(f"JSON: {out}")
        return 0

    if args.command == "ai-test":
        cfg = load_ai_config()
        if args.provider:
            cfg.provider = args.provider
        if args.base_url:
            cfg.base_url = args.base_url.rstrip("/")
        if args.model:
            cfg.model = args.model
        result = check_local_ai_available(cfg)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("available") else 1

    if args.command == "ai-analyze":
        cfg = load_ai_config()
        cfg.enabled = True
        if args.provider:
            cfg.provider = args.provider
        if args.base_url:
            cfg.base_url = args.base_url.rstrip("/")
        if args.model:
            cfg.model = args.model
        sim = _load_saved_simulation(args.experiment)
        signal_result = analyze_signals(sim)
        recommendation = recommend_treatments(sim=sim, interpretation=signal_result)
        result = analyze_experiment_with_ai(cfg, sim, signal_result, recommendation)
        print(result.get("response") or result.get("message"))
        return 0 if result.get("ok") else 1

    if args.command == "research-loop":
        cfg = ResearchLoopConfig(
            profile=args.profile,
            cocktail=args.cocktail,
            max_auto_experiments=args.max_experiments,
            max_steps_per_experiment=args.steps,
            healthy=args.healthy,
            cancer=args.cancer,
            seed=args.seed,
            output_dir=args.output_dir,
            require_user_confirmation_before_start=True,
        )
        result = run_research_loop(cfg, load_ai_config(), confirmed=args.confirmed)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1

    if args.command == "run":
        cocktails = default_cocktails()
        cocktail = _lookup_named(cocktails, args.cocktail, "cocktail")
        cfg = SimulationConfig(
            name=args.name,
            initial_healthy_cells=args.healthy,
            initial_cancer_cells=args.cancer,
            random_seed=args.seed,
            steps=args.steps,
        )
        _apply_adaptive_args(cfg, args)
        sim = Simulation(cfg, cocktail=cocktail)
        sim.reset()
        if args.preset:
            preset = _lookup_named(load_cancer_presets(), args.preset, "preset")
            sim.set_cancer_preset(preset)
        sim.run(args.steps)
        export_paths = []
        if args.export:
            export_paths.append(("auto", Path(args.export)))
        elif args.out:
            export_paths.append(("auto", Path(args.out)))
        if args.html:
            export_paths.append(("html", Path(args.html)))
        if args.json:
            export_paths.append(("json", Path(args.json)))
        if args.csv:
            export_paths.append(("csv", Path(args.csv)))
        written = []
        for kind, out in export_paths:
            if not out.is_absolute():
                out = Path.cwd() / out
            if kind == "html":
                export_html_report(sim, out)
            elif kind == "json":
                export_json_report(sim, out)
            elif kind == "csv":
                sim.analytics.export_csv(out)
            else:
                export_report_by_suffix(sim, out)
            written.append(out)
        print(sim.analytics.summary_text())
        if args.interpret:
            print()
            print(interpret_latest(sim))
        for path in written:
            print(f"Export: {path}")
        return 0

    if args.command == "remission-test":
        # Remission tests default to adaptive dosing + post-clearance surveillance.
        args.adaptive_dosing = True if not getattr(args, "adaptive_dosing", False) else args.adaptive_dosing
        args.auto_shutoff = True if not getattr(args, "auto_shutoff", False) else args.auto_shutoff
        total_steps = int(args.steps if args.steps is not None else args.treat_steps + args.watch_steps)
        cocktails = default_cocktails()
        cocktail = _lookup_named(cocktails, args.cocktail, "cocktail")
        cfg = SimulationConfig(
            name=args.name,
            initial_healthy_cells=args.healthy,
            initial_cancer_cells=args.cancer,
            random_seed=args.seed,
            steps=total_steps,
        )
        _apply_adaptive_args(cfg, args)
        sim = Simulation(cfg, cocktail=cocktail)
        sim.reset()
        if args.preset:
            preset = _lookup_named(load_cancer_presets(), args.preset, "preset")
            sim.set_cancer_preset(preset)
        sim.run(total_steps)
        out = Path(args.export)
        if not out.is_absolute():
            out = Path.cwd() / out
        export_report_by_suffix(sim, out)
        print(sim.analytics.summary_text())
        print()
        print(interpret_latest(sim))
        assessment = assess_cure_pathway(sim)
        print()
        print(f"Cure-pathway classification: {assessment.classification}")
        print(f"Cure-pathway score: {assessment.score:.3f}")
        print(f"Export: {out}")
        return 0

    if args.command == "compare":
        seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
        cfg = SimulationConfig(initial_healthy_cells=args.healthy, initial_cancer_cells=args.cancer, steps=args.steps)
        _apply_adaptive_args(cfg, args)
        cocktail_list = None
        if args.cocktails:
            available = default_cocktails()
            cocktail_list = [_lookup_named(available, name.strip(), "cocktail") for name in args.cocktails.split(",") if name.strip()]
        results = compare_cocktails(cocktails=cocktail_list, config=cfg, cancer_preset_name=args.preset, steps=args.steps, seeds=seeds)
        print(format_results_table(results, limit=args.limit))
        if args.csv:
            export_results_csv(results, args.csv)
            print(f"CSV: {args.csv}")
        if args.json:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps([r.to_dict() for r in results], indent=2, sort_keys=True), encoding="utf-8")
            print(f"JSON: {args.json}")
        return 0

    if args.command == "sweep":
        values = [float(x.strip()) for x in args.values.split(",") if x.strip()]
        cocktails = default_cocktails()
        cocktail = _lookup_named(cocktails, args.cocktail, "cocktail")
        cfg = SimulationConfig(
            initial_healthy_cells=args.healthy,
            initial_cancer_cells=args.cancer,
            random_seed=args.seed,
            steps=args.steps,
        )
        _apply_adaptive_args(cfg, args)
        results = run_parameter_sweep(
            parameter=args.parameter,
            values=values,
            config=cfg,
            cocktail=cocktail,
            cancer_preset_name=args.preset,
            steps=args.steps,
            seed=args.seed,
        )
        print(format_sweep_table(results, limit=args.limit))
        if args.csv:
            export_sweep_csv(results, args.csv)
            print(f"CSV: {args.csv}")
        if args.json:
            export_sweep_json(results, args.json)
            print(f"JSON: {args.json}")
        return 0

    if args.command == "auto":
        if args.list_profiles:
            for profile in automation_profiles():
                print(f"{profile.key}: {profile.label} - {profile.description}")
            return 0
        compare_seeds = None
        if args.compare_seeds is not None:
            compare_seeds = [int(x.strip()) for x in args.compare_seeds.split(",") if x.strip()]
        options = build_automation_options(
            args.profile,
            {
                "name": args.name,
                "preset_name": args.preset,
                "cocktail_name": args.cocktail,
                "steps": args.steps,
                "healthy": args.healthy,
                "cancer": args.cancer,
                "seed": args.seed,
                "output_dir": args.output_dir,
                "compare": False if args.no_compare else None,
                "compare_seeds": compare_seeds,
                "compare_limit": args.limit,
                "auto_select_cocktail": True if args.auto_select_cocktail else None,
            },
        )
        result = run_automated_protocol(**options)
        if result.get("auto_select_cocktail"):
            print(f"Selected cocktail: {result.get('selected_cocktail')}")
        print(result["summary"])
        if result["comparison_table"]:
            print()
            print(result["comparison_table"])
        print()
        print("Exports:")
        for key, path in result["paths"].items():
            print(f"  {key}: {path}")
        return 0

    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
