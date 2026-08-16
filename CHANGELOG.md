# Changelog

## 0.7.0

- Added a canonical evidence fabric with typed biological entities, stable namespace identifiers, source hashes, evidence classes, claim categories, contexts, contradictions, limitations, and assertion provenance hashes.
- Added `TumorResearchModel` as the typed boundary between evidence ingestion and optimization.
- Added Target Forge for exact tumor-versus-normal single-target, AND, OR, and AND-NOT discovery with continuous source measurements, explicit thresholds, missing-data rejection, normal-tissue hard bounds, clone/patient coverage, dropout checks, and a Pareto front without a combined truth score.
- Added formal candidate hypotheses with evidence links, normal liabilities, uncertainty, escape routes, validation experiments, falsification conditions, and reproducible provenance.
- Added a fail-closed QSA `SymmetryState` adapter with representation certificates, information-identical analytic controls, runtime receipts, deterministic hashes, classical fallback, and no unsupported advantage claim.
- Added authenticated bounded Target Forge web API creation/retrieval endpoints and browser client calls for the website portal.
- Added `target-forge` CLI execution and JSON/HTML reports.
- Added a clearly labeled synthetic fixture, machine-readable evidence schema, current-system audit, and a complete website implementation prompt.
- Added tests for provenance tampering, identifier failures, normal-tissue exclusion, missing critical-normal evidence, Pareto behavior, QSA/control equality, report reproducibility, portal authentication, and workload limits.

## 0.6.0

- Connected the improved project to the public `R-D-BioTech-Alaska/Onco` Git history.
- Added a standard-library WSGI API for website health checks, profile discovery, authenticated mission creation, and mission retrieval.
- Added strict request validation, private API-key authentication, server-controlled output paths, public-response path scrubbing, and hard cell-step/QSA workload limits.
- Added `run_oncoforge.py serve-api` for local API connection testing.
- Added a website upload handoff with a browser API client, mission request example, environment template, and server proxy rules.
- Added web API tests covering authentication, profile discovery, mission creation/retrieval, path confinement, and workload rejection.

## 0.5.1

- Added a bounded QSA-ready quantum strategy layer that converts profile signals and cocktail rankings into inspectable structural-search workloads.
- Added `run_oncoforge.py qsa-plan` for generating deterministic QSA-ready plans without requiring QSA as a dependency.
- Added `run_oncoforge.py portal-session` for one-call webpage-ready mission payloads covering profiles, markers, cocktail ranking, QSA planning, simulation results, and bounded next-loop planning.
- Added portal system, QSA integration, GitHub publication, and claims/safety documentation under `docs/`.
- Added a concrete webpage build packet with routes, components, controls, API payloads, safety gates, and copy rules.
- Added GitHub Actions CI, `.gitignore`, and package metadata for public GitHub availability.
- Added tests for the QSA strategy contract, workload limits, fallback scorer, backend adapter failures, and CLI JSON export.

## 0.5.0

- Added JSON-backed cancer profiles with 16 built-in conceptual profiles.
- Added profile-driven simulation generation with profile strength, heterogeneity, microenvironment biasing, and marker snapshots.
- Added Cancer Profiles GUI tab for profile browsing, generation, signal analysis, cocktail recommendation, comparison, report export, and custom-profile duplication.
- Added cancer-vs-healthy signal interpreter with transparent targetability scoring and zero-cancer fallback snapshots.
- Added conceptual treatment matcher ranking cocktails by marker coverage, selectivity, healthy overlap, inflammation risk, escape control, evidence, and remission suitability.
- Expanded the synthetic agent library and added narrower default cocktails for checkpoint priming, repair defects, stromal access, and remission surveillance.
- Added optional local AI connector for Ollama, LM Studio, and generic OpenAI-compatible local endpoints.
- Added Local AI Assistant GUI tab with connection testing, current-run analysis, next-simulation suggestions, and bounded research loop controls.
- Added bounded research-loop engine with hard experiment, step, runtime, and confirmation limits.
- Expanded reports with cancer profile, signal interpretation, cocktail recommendations, marker evolution, local AI, and research-loop sections.
- Added CLI commands: `list-profiles`, `profile-info`, `run-profile`, `interpret-signals`, `recommend-cocktail`, `ai-test`, `ai-analyze`, and `research-loop`.
- Added tests for profiles, signal interpretation, treatment matching, local AI graceful failure, research-loop limits, and CLI commands.

## 0.4.1

- Replaced immediate auto-shutoff with a remission-confirmation controller.
- Added `zero_cancer_confirmation_steps` with a default of 50 steps before shutoff is allowed.
- Added `remission_confirmation` phase so cancer reaching zero keeps low treatment pressure instead of stopping instantly.
- Increased default adaptive minimum intensity to 0.20 and remission surveillance intensity to 0.25.
- Added recurrence/rebound tracking: recurrence after clearance, max cancer after clearance, rebound step, and zero-cancer streak.
- Added GUI fields for confirmation steps, current remission phase, zero-cancer steps, rebound detected, and max cancer after clearance.
- Expanded JSON/HTML reports with remission-controller state and dosing-phase history.
- Added CLI flags for confirmation steps and adaptive/surveillance intensities.
- Added regression tests proving delayed shutoff, confirmation pressure, rebound recovery, and reduced post-clearance healthy damage.

## 0.4.0

- Added adaptive dosing controller with full-pressure, tapering, minimal-residual watch, remission-surveillance, and post-clearance shutoff phases.
- Added dosing configuration fields for taper thresholds, surveillance intensity, toxicity thresholds, and post-clearance recovery rate.
- Added treatment intensity and dosing phase to analytics history, CSV exports, save/load, summaries, and reports.
- Added post-clearance recovery behavior for inflammation, immune pressure, acidity, and stromal barrier after cancer clearance.
- Added cure-pathway/remission assessment heuristics to distinguish clearance, short remission tests, recurrence, recovery concerns, post-clearance damage, and strong cure-like simulation outcomes.
- Added plain-English interpretation engine for dashboard/results/report use.
- Added `run_oncoforge.py remission-test` for clearance plus post-clearance watch experiments.
- Added adaptive dosing flags to `run` and `compare`: `--adaptive-dosing`, `--auto-shutoff`, `--no-remission-surveillance`, `--taper-count`, `--surveillance-count`, and `--recovery-rate`.
- Added Dosing & Cure Test GUI tab with adaptive controls, a beginner guide, and live interpretation.
- Expanded HTML/JSON reports with dosing state, cure-pathway assessment, interpretation text, and dosing-phase metric columns.
- Added `USER_GUIDE.md` explaining how to operate the simulator, read outputs, remission tests, and parameter sweeps.
- Added `run_oncoforge.py sweep` and `oncoforge.core.sweep` for sensitivity testing across config and microenvironment parameters.
- Added tests for adaptive dosing, auto-shutoff, cure-pathway reports, and the remission-test CLI.

## 0.3.1

- Added guided automation profiles for fast triage, balanced exploration, best-cocktail scouting, immune-escape focus, repair-defect focus, and hypoxia/invasion focus.
- Added cocktail auto-selection for automated workflows, including CSV/JSON selection exports and a ranked selection summary.
- Added GUI controls for workflow profiles and cocktail auto-selection in the Automated Run tab.
- Added `run_oncoforge.py list-automation-profiles`, `run_oncoforge.py auto --profile ...`, and `run_oncoforge.py auto --auto-select-cocktail`.
- Improved automated export filenames so generated report stems preserve readable word breaks.
- Hardened cell serialization during proliferation by replacing the hot `asdict` path with an explicit stable dictionary.
- Added tests for automation profiles and auto-selected workflow exports.

## 0.3.0

- Added a dark Tkinter theme with higher-contrast panels, tabs, tables, text areas, and canvases.
- Added an Automated Run GUI tab for one-click simulation, report exports, saved experiment creation, and optional cocktail comparison.
- Added dashboard quick-action buttons for automated runs and immediate cocktail comparison.
- Added `run_oncoforge.py auto` for a complete headless workflow without manual step-by-step operation.
- Added explicit evidence labels (`established_biology`, `supported_model`, `inferred_interaction`, `speculative_hypothesis`, `user_concept`) alongside numeric evidence levels.
- Added threshold activation logic for agents and GUI custom-agent creation.
- Added agent concentration decay during simulation steps.
- Added deterministic RNG-state persistence for save/load continuation.
- Added richer analytics: tumor burden, cancer death rate, healthy damage rate, immune activation, inflammation, immune pressure, escape clone count, dominant clone, and mean agent concentration.
- Added clone summary support for reports.
- Expanded pathway-map metadata with evidence labels and plain-English explanations for core modeled systems.
- Expanded cocktail scoring with pathway coverage, signal coverage, redundancy, inflammation risk, escape pressure, and conceptual plausibility.
- Added deterministic JSON report export and extension-based CLI export (`--export .html/.json/.csv`).
- Added explicit CLI JSON/CSV/HTML exports, lenient snake-case name lookup, optional comparison JSON export, and optional cocktail filtering.
- Added GUI JSON report export.
- Added stronger validation and numeric coercion for agents, cells, signal dictionaries, and loaded configs.
- Added tests for reproducibility, save/load continuation, threshold activation, agent decay, JSON reports, and richer pathway metadata.
- Rewrote README and added roadmap documentation.

## 0.2.0

- Added Agent Designer GUI tab.
- Added Pathway Map GUI tab.
- Added Batch Compare GUI tab.
- Added headless CLI with `run`, `compare`, `list-presets`, and `list-cocktails`.
- Added experiment comparison engine.
- Added agent/cocktail validation and coverage scoring.
- Added new signal channels: proteasome stress, unfolded protein response, ferroptosis susceptibility, CD47-like do-not-eat-me signaling, complement susceptibility, STING/cytosolic-DNA sensing, and autophagy dependence.
- Added new action channels: phagocytosis, complement, ferroptosis, proteostasis overload, STING/interferon visibility, and autophagy pressure.
- Added synthetic agents for innate immune cleanup, metabolic/stress death pressure, and four-signal waste-cell gating.
- Fixed save/load so analytics history persists in loaded experiments.
- Expanded tests.

## 0.1.0

- Initial Tkinter GUI.
- Core agent-based simulation engine.
- Natural and synthetic agent libraries.
- Cancer presets.
- Cocktail builder.
- Save/load/export.
