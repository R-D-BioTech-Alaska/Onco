# OncoForge

OncoForge is an evidence-governed cancer target discovery engine and conceptual cancer-systems research platform. Its website API runs typed tumor-versus-normal target discovery, multi-signal gate search, provenance tracking, bounded QSA structural checks, and the existing synthetic simulation workflows.

OncoForge is not a clinical predictor, medical advice, proof of safety or efficacy, or a treatment recommendation system. Computational candidates are research hypotheses that require independent measurement and experimental validation. The older cell simulator remains a separate synthetic lane whose hand-authored parameters are never treated as biological evidence.

## Evidence-Governed Target Forge

Target Forge accepts an `oncoforge.evidence.v1` evidence fabric and performs one connected research workflow:

```text
evidence validation and provenance
  -> tumor/clone/patient and normal-tissue model
  -> exact target activation matrices
  -> SINGLE, AND, OR, and AND NOT gate search
  -> hard tumor-coverage and normal-safety rules
  -> Pareto hypotheses
  -> fair classical control and optional QSA receipt
  -> auditable JSON or HTML report
```

It preserves evidence classes and `MEASURED`, `DERIVED`, `PREDICTED`, `INFERRED`, `HYPOTHESIZED`, and `SIMULATED` labels instead of collapsing them into a fake probability of truth. Missing critical-normal evidence fails closed.

Run the labeled synthetic fixture:

```bash
python run_oncoforge.py target-forge --input examples/target_forge_synthetic.json --output outputs/target_forge/report.json
```

The schema is in `schemas/evidence_fabric.schema.json`. The fixture is software-test data only and makes no biological claim.

QSA is optional. Install the compatible QSA runtime when the service should execute the certified class check:

```bash
python -m pip install ".[qsa]"
```

Without QSA, Target Forge retains the exact classical result and records a classical fallback receipt.

## What It Models

- Healthy, precancerous, cancer, and dead cell states.
- Cancer signals such as DNA damage, replication stress, p53/RB inactivity, repair defects, MHC-I loss, neoantigens, PD-L1-like suppression, CD47-like avoidance, stress ligands, hypoxia, acidity, ferroptosis susceptibility, STING-like sensing, proteostasis stress, and autophagy dependence.
- Natural pathway abstractions including ATM/ATR, p53, RB, mismatch repair, BRCA-style homologous recombination repair, apoptosis/caspase execution, MHC-I presentation, NK missing-self behavior, PD-1/PD-L1-like immune suppression, CD47-like phagocytosis avoidance, complement susceptibility, STING-like innate visibility, and hypoxia/acidity microenvironment behavior.
- Synthetic/conceptual protein or enzyme agents with targets, activation logic, potency, specificity, decay, healthy-cell risk, evidence labels, and limitations.
- Cocktails as multi-signal decision systems.

## Evidence Labels

Every loaded agent receives both a numeric level and a string label:

- `established_biology`: canonical or well-established biology simplified for the model.
- `supported_model`: common abstraction or supported concept represented qualitatively.
- `inferred_interaction`: plausible interaction inferred from related biology.
- `speculative_hypothesis`: synthetic or systems-level hypothesis needing experimental support.
- `user_concept`: user-created conceptual mechanism, not established science.

The labels are used in validation, reports, and pathway-map text. They do not imply clinical effectiveness.

## Requirements

OncoForge intentionally uses the Python standard library only.

- Python 3.10 or newer recommended.
- Tkinter for the GUI. It is included with most Windows/macOS Python installers.

On Windows, if `python` opens the Microsoft Store stub, use `py` instead:

```powershell
py run_oncoforge.py
```

## Run The Legacy Simulator GUI

```bash
python run_oncoforge.py
```

This interface is retained for synthetic simulation work; the new evidence discovery system belongs in the website portal. The legacy GUI includes:

- Dark desktop theme with higher-contrast text, tables, tabs, and canvas views.
- Automated Run tab with workflow profiles, one-click simulation, export, saved experiment creation, optional cocktail comparison, and optional cocktail auto-selection.
- Dosing & Cure Test tab with adaptive dosing controls, auto-shutoff, remission surveillance, and plain-English run interpretation.
- GUI and headless parameter sweeps for treatment strength, immune strength, mutation rate, dosing fields, and microenvironment fields.
- Dashboard controls for reset, stepping, live run/pause, seed, population size, and multipliers.
- Dashboard one-click workflow buttons for automated runs and cocktail comparison.
- Cancer preset selector and microenvironment controls.
- Protein/enzyme library and cocktail builder.
- Custom agent designer with AND, OR, WEIGHTED, and THRESHOLD activation logic.
- Pathway map with evidence labels and plain-English explanations.
- Batch comparison tab.
- Parameter Sweep tab for sensitivity testing without using the command line.
- Live cell viewer, signal matrix, results chart/table, CSV export, HTML export, JSON export, save/load experiment JSON, and experiment notebook.

## Headless CLI

List presets and cocktails:

```bash
python run_oncoforge.py list-presets
python run_oncoforge.py list-cocktails
python run_oncoforge.py list-automation-profiles
```

Run one simulation and export by file extension:

```bash
python run_oncoforge.py run --preset generic_p53_loss --cocktail full_conceptual_swarm --steps 200 --seed 1729 --export outputs/report.html
python run_oncoforge.py run --steps 100 --healthy 300 --cancer 120 --seed 1729 --export outputs/report.json
python run_oncoforge.py run --steps 100 --healthy 300 --cancer 120 --seed 1729 --export outputs/metrics.csv
```

Run an adaptive dosing simulation and print the interpretation:

```bash
python run_oncoforge.py run --steps 150 --healthy 700 --cancer 300 --preset generic_p53_loss --cocktail full_conceptual_swarm --adaptive-dosing --auto-shutoff --interpret --export outputs/reports/adaptive_run.html
```

Run a clearance plus post-clearance watch experiment:

```bash
python run_oncoforge.py remission-test --steps 370 --healthy 700 --cancer 300 --preset generic_p53_loss --cocktail full_conceptual_swarm --export outputs/reports/remission_test.html
```

Explicit multi-export is also supported:

```bash
python run_oncoforge.py run --steps 100 --seed 1729 --html outputs/report.html --json outputs/report.json --csv outputs/metrics.csv
```

Compare cocktails across seeds:

```bash
python run_oncoforge.py compare --steps 100 --healthy 250 --cancer 100 --seeds 1729,1730,1731 --limit 20
python run_oncoforge.py compare --steps 100 --healthy 250 --cancer 100 --seeds 1729,1730,1731 --csv outputs/batch_compare.csv --json outputs/batch_compare.json
python run_oncoforge.py compare --steps 120 --healthy 250 --cancer 100 --seeds 1729,1730,1731 --adaptive-dosing --auto-shutoff --limit 20
```

Sweep one parameter across values:

```bash
python run_oncoforge.py sweep --parameter treatment --values 0.5,0.75,1.0,1.25 --steps 120 --adaptive-dosing --auto-shutoff --json outputs/sweep_treatment.json
python run_oncoforge.py sweep --parameter micro.oxygen --values 0.25,0.50,0.75,1.0 --steps 120 --csv outputs/sweep_oxygen.csv
```

Run the full automated workflow:

```bash
python run_oncoforge.py auto --preset generic_p53_loss --cocktail full_conceptual_swarm --steps 100 --healthy 250 --cancer 100 --seed 1729 --output-dir outputs/automated
python run_oncoforge.py auto --profile fast_triage
python run_oncoforge.py auto --profile best_cocktail_scout --auto-select-cocktail
```

The automated workflow runs the simulation, exports HTML/JSON/CSV reports, saves the experiment JSON, and optionally compares bundled cocktails across seeds. Use `--profile` for guided presets such as `fast_triage`, `balanced_exploration`, `best_cocktail_scout`, `immune_escape_focus`, `repair_defect_focus`, and `hypoxia_invasion_focus`. Use `--auto-select-cocktail` to rank bundled cocktails first and then run the top-scoring option. Use `--no-compare` to only run/export the selected scenario.

Names are matched leniently, so `full_conceptual_swarm` resolves to `Full conceptual swarm`.

## Website Portal API

The website portal is the primary interface for the new discovery system. OncoForge includes a small WSGI API so the logged-in website uses the same Python evidence, Target Forge, QSA, and simulation engines without copying scientific logic into JavaScript.

Local connection test:

```powershell
$env:ONCOFORGE_API_KEY="local-test-key"
python run_oncoforge.py serve-api --host 127.0.0.1 --port 8765
```

The deployable WSGI application is `oncoforge.web_api:application`. Mission endpoints fail closed until `ONCOFORGE_API_KEY` is configured. The website server must keep that key private, verify the user's website session, and proxy mission requests to OncoForge.

Protected Target Forge routes are `POST /lab/oncoforge/api/target-forge/runs` and `GET /lab/oncoforge/api/target-forge/runs/{run_id}`. The complete website handoff is in `website/ONCOFORGE_VNEXT_WEBSITE_PROMPT.md` and `website/WEBSITE_UPLOAD.md`. The portal does not store passwords or patient records and does not provide treatment instructions.

## Adaptive Dosing And Remission Testing

Adaptive dosing is designed to make the simulator easier to reason about after a powerful cocktail clears cancer. It can reduce intensity as cancer burden falls, enter a minimal-residual watch phase, and switch to low-intensity surveillance or shutoff after cancer reaches zero. The post-clearance recovery model lets inflammation, acidity, immune pressure, and stromal stress move back toward baseline.

The cure-pathway assessment is heuristic and conceptual. It checks whether cancer cleared, whether it stayed cleared during post-clearance watch steps, whether healthy cells survived, whether healthy damage continued after clearance, and whether inflammation/immune pressure recovered. The strongest label is `strong_cure_like_simulation_outcome`, which is still only a simulation outcome.

See `USER_GUIDE.md` for a step-by-step operating guide.

## Custom Agents

A custom agent has:

- `name`
- `category`
- `description`
- `evidence_level` and derived `evidence_label`
- `targets`
- `activation_logic`: `AND`, `OR`, `WEIGHTED`, or `THRESHOLD`
- `activation_threshold` for threshold gates
- `actions`
- `potency`
- `specificity`
- `decay_rate`
- `healthy_cell_risk`
- optional `microenvironment_requirements`
- `notes_limitations`

Use the GUI Agent Designer or create a `BioAgent` in Python and validate it with `validate_agent`.

## Cocktails And Scoring

Cocktails are scored and compared using:

- cancer-cell suppression
- healthy-cell preservation and damage
- immune activation
- inflammation risk
- escape event pressure
- pathway coverage
- signal coverage
- redundancy
- specificity
- conceptual plausibility

Scores are for ranking conceptual experiments only. They are not biological efficacy scores.

## Save, Load, Reports, And Exports

Saved experiment JSON now includes:

- config and preset metadata
- microenvironment
- active cocktail and agents
- cells
- analytics history
- deterministic RNG state for continuation

HTML and JSON reports include:

- scope disclaimer
- experiment metadata and random seed
- cancer preset
- starting population
- active cocktail and evidence labels
- final metrics
- dosing state and treatment intensity
- cure-pathway/remission assessment
- plain-English interpretation
- tumor burden, healthy-cell, and immune-activation curves
- healthy damage and escape totals
- clone summary
- signal/pathway coverage
- limitations

CSV exports contain the analytics history.

## Automated Workflows

For legacy synthetic simulation, the desktop app's Automated Run tab provides a guided workflow:

1. Choose a workflow profile such as `Fast triage`, `Balanced exploration`, or `Best cocktail scout`.
2. Adjust the preset, cocktail, counts, steps, seed, or output folder only if needed.
3. Leave comparison enabled to rank bundled cocktails automatically, or enable auto-selection to let OncoForge pick the top-scoring cocktail before the main run.
4. Click `Run automated workflow`.

When it finishes, OncoForge loads the generated experiment back into the current session and writes all exports to the selected output folder.

## Tests

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python run_oncoforge.py compare --steps 25 --healthy 100 --cancer 40 --seeds 1729,1730 --limit 5
python run_oncoforge.py remission-test --steps 30 --healthy 80 --cancer 10 --export outputs/reports/remission_smoke.json
python run_oncoforge.py sweep --parameter treatment --values 0.5,1.0 --steps 10 --healthy 40 --cancer 10 --adaptive-dosing --auto-shutoff --limit 5
```

On Windows with the Python launcher:

```powershell
py -m compileall -q .
py -m unittest discover -s tests -v
py run_oncoforge.py compare --steps 25 --healthy 100 --cancer 40 --seeds 1729,1730 --limit 5
py run_oncoforge.py remission-test --steps 30 --healthy 80 --cancer 10 --export outputs/reports/remission_smoke.json
py run_oncoforge.py sweep --parameter treatment --values 0.5,1.0 --steps 10 --healthy 40 --cancer 10 --adaptive-dosing --auto-shutoff --limit 5
```

## Project Structure

```text
OncoForge/
  run_oncoforge.py
  run_oncoforge.bat
  README.md
  CHANGELOG.md
  ROADMAP.md
  USER_GUIDE.md
  oncoforge/
    cli.py
    core/
      analytics.py
      constants.py
      experiment_runner.py
      exporter.py
      interpretation.py
      knowledge.py
      models.py
      presets.py
      rule_engine.py
      simulation.py
      sweep.py
      utils.py
    data/
      cancer_types.json
      evidence_sources.json
      natural_agents.json
      synthetic_agents.json
    ui/
      app.py
  tests/
    test_adaptive_dosing.py
    test_engine.py
    test_extended_features.py
  outputs/
```

## Scientific Limitations

- The model is qualitative and not calibrated to patient, animal, organoid, or clinical data.
- Agent actions are simplified signal/action abstractions, not pharmacology.
- Immune behavior, microenvironment behavior, mutation escape, and repair pathways are deliberately coarse.
- Speculative and user-concept agents are included for exploration, not claims.
- Repeated seeds, parameter sweeps, and sensitivity analysis are necessary before interpreting any pattern.

## Development Roadmap

See `ROADMAP.md` for recommended next work.
