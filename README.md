<div align="center">

<h1>ONCOFORGE</h1>

<h2>EVIDENCE-GOVERNED CANCER TARGET DISCOVERY</h2>

<p><strong>Target analysis · Multi-signal systems · Research provenance · Synthetic modeling</strong></p>

<p>
  <a href="https://rdbiotech-alaska.brenton-cart-3224.chatgpt.site/lab/oncoforge/login/">
    <img src="https://img.shields.io/badge/OPEN%20ONCOFORGE-ACCESS%20PORTAL-173B57?style=for-the-badge" alt="Open OncoForge portal">
  </a>
</p>

<p>
  <img src="https://img.shields.io/badge/PYTHON-3.10%2B-3776AB?style=flat-square" alt="Python 3.10 or newer">
  <img src="https://img.shields.io/badge/CORE-PYTHON%20STANDARD%20LIBRARY-34495E?style=flat-square" alt="Python standard library">
  <img src="https://img.shields.io/badge/MODEL-EVIDENCE%20GOVERNED-246B62?style=flat-square" alt="Evidence governed">
</p>

<p><em>Turning structured biological evidence into traceable research hypotheses.</em></p>

</div>

---

## Overview

OncoForge is an evidence-governed cancer-target discovery engine and
conceptual cancer-systems research platform. Its primary discovery
workflow connects **tumor-versus-normal analysis**, **multi-signal gate
search**, **evidence provenance**, optional **QSA structural checks**,
and auditable reporting.

It also retains a separate synthetic cell simulator for exploring
conceptual cancer-system behavior.

OncoForge uses multiple AI databases, including Rosalind GPT-6, to
integrate genetic profiles, enzymes, and protein inclusions.

> **RESEARCH USE ONLY.** OncoForge is not a clinical
> predictor, medical-advice service, proof of safety or efficacy, or
> treatment-recommendation system. Discovery outputs are research
> hypotheses requiring independent measurement and experimental
> validation. Synthetic simulator parameters are not biological
> evidence.

ChatGPT sign-in is optional and serves only as an additional login
method. ChatGPT is not used to execute research workflows, and no
ChatGPT information is stored or used by OncoForge.

## Platform

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>Target Forge</h3>
      Evidence-driven target discovery, tumor-versus-normal comparisons, multi-signal gates, hard safety rules, and Pareto-ranked hypotheses.
    </td>
    <td width="33%" valign="top">
      <h3>Evidence Fabric</h3>
      Typed evidence, provenance tracking, explicit evidence states, validation, and auditable JSON or HTML reports.
    </td>
    <td width="33%" valign="top">
      <h3>Cell Simulator</h3>
      Separate synthetic workflows for cell populations, pathway abstractions, agent systems, dosing experiments, and sensitivity analysis.
    </td>
  </tr>
</table>

## Target Forge

Target Forge accepts an `oncoforge.evidence.v1` evidence fabric and
executes one connected workflow:

``` text
EVIDENCE FABRIC
      |
      v
Validation + provenance
      |
      v
Tumor / clone / patient / normal-tissue model
      |
      v
Target-activation matrices
      |
      v
SINGLE / AND / OR / AND NOT gate search
      |
      v
Tumor-coverage + normal-safety constraints
      |
      v
Pareto-ranked research hypotheses
      |
      v
Classical control + optional QSA receipt
      |
      v
Auditable JSON / HTML report
```

Evidence states remain explicit rather than being collapsed into a
single probability:

`MEASURED` · `DERIVED` · `PREDICTED` · `INFERRED` · `HYPOTHESIZED` ·
`SIMULATED`

Missing critical-normal evidence fails closed.

**Run the synthetic software fixture:**

``` bash
python run_oncoforge.py target-forge --input examples/target_forge_synthetic.json --output outputs/target_forge/report.json
```

The schema is `schemas/evidence_fabric.schema.json`. The fixture is
software-test data only and makes no biological claim.

**Optional QSA integration:**

``` bash
python -m pip install ".[qsa]"
```

Without QSA, Target Forge retains the exact classical result and records
a classical-fallback receipt.

## Biological & Systems Scope

| Area                | Included representations                                                                                                                                                                                                                   |
|---------------------|-----------------------------|
| Cell states         | Healthy, precancerous, cancer, and dead                                                                                                                                                                                                    |
| Cancer signals      | DNA damage, replication stress, p53/RB inactivity, repair defects, MHC-I loss, neoantigens, immune-evasion signals, hypoxia, acidity, ferroptosis susceptibility, STING-like sensing, proteostasis stress, and autophagy dependence        |
| Pathways            | ATM/ATR, p53, RB, mismatch repair, BRCA-style homologous recombination, apoptosis/caspase execution, antigen presentation, NK missing-self behavior, immune suppression, phagocytosis avoidance, complement, and microenvironment behavior |
| Agents              | Conceptual protein/enzyme agents with targets, activation logic, potency, specificity, decay, healthy-cell risk, evidence labels, and limitations                                                                                          |
| Multi-agent systems | Cocktails modeled as multi-signal decision systems                                                                                                                                                                                         |

## Evidence Framework

Each loaded agent receives a numeric evidence level and a corresponding
label.

| Label                    | Interpretation                                                       |
|--------------------------|----------------------------------------------------------------------|
| `established_biology`    | Canonical or well-established biology simplified for the model       |
| `supported_model`        | Common abstraction or supported concept represented qualitatively    |
| `inferred_interaction`   | Plausible interaction inferred from related biology                  |
| `speculative_hypothesis` | Synthetic or systems-level hypothesis requiring experimental support |
| `user_concept`           | User-created conceptual mechanism, not established science           |

Evidence labels appear in validation, reports, and pathway maps. They do
not imply clinical effectiveness.

## Quick Start

**Requirements**

-   Python 3.10 or newer recommended.
-   Python standard library for the core application.
-   Tkinter for the desktop GUI; included with most Windows and macOS
    Python installers.

**Launch the desktop simulator**

``` bash
python run_oncoforge.py
```

On Windows, if `python` opens the Microsoft Store stub:

``` powershell
py run_oncoforge.py
```

The desktop application is retained for synthetic simulation. The
website portal is the primary interface for the new evidence-discovery
system.

## CLI

The CLI supports individual simulations, cocktail comparisons, parameter
sweeps, remission tests, and automated workflows.

``` bash
# List available configurations
python run_oncoforge.py list-presets
python run_oncoforge.py list-cocktails
python run_oncoforge.py list-automation-profiles

# Run a simulation
python run_oncoforge.py run --preset generic_p53_loss --cocktail full_conceptual_swarm --steps 200 --seed 1729 --export outputs/report.html

# Compare cocktails across seeds
python run_oncoforge.py compare --steps 100 --healthy 250 --cancer 100 --seeds 1729,1730,1731 --limit 20

# Sweep a parameter
python run_oncoforge.py sweep --parameter treatment --values 0.5,0.75,1.0,1.25 --steps 120 --json outputs/sweep_treatment.json

# Run an automated workflow
python run_oncoforge.py auto --profile fast_triage
```

Additional profiles include `balanced_exploration`,
`best_cocktail_scout`, `immune_escape_focus`, `repair_defect_focus`, and
`hypoxia_invasion_focus`. Use `--auto-select-cocktail` to rank bundled
cocktails before the main run, or `--no-compare` to run only the
selected scenario.

See [`USER_GUIDE.md`](USER_GUIDE.md) for the complete operating guide
and additional command options.

## Website API

The website portal uses a small WSGI API to connect authenticated
website sessions to the same Python evidence, Target Forge, QSA, and
simulation engines. Scientific logic remains in Python rather than being
duplicated in JavaScript.

**Local API test:**

``` powershell
$env:ONCOFORGE_API_KEY="local-test-key"
python run_oncoforge.py serve-api --host 127.0.0.1 --port 8765
```

Deployable WSGI application: `oncoforge.web_api:application`

Protected Target Forge routes:

| Method | Route                                           |
|--------|-------------------------------------------------|
| `POST` | `/lab/oncoforge/api/target-forge/runs`          |
| `GET`  | `/lab/oncoforge/api/target-forge/runs/{run_id}` |

Mission endpoints fail closed until `ONCOFORGE_API_KEY` is configured.
The website server must keep the key private, verify the user's website
session, and proxy mission requests to OncoForge.

Implementation handoff: `website/ONCOFORGE_VNEXT_WEBSITE_PROMPT.md` and
`website/WEBSITE_UPLOAD.md`.

## Simulator Capabilities

The legacy desktop simulator includes:

-   Automated runs with workflow profiles, exports, saved experiments,
    cocktail comparisons, and optional automatic selection.
-   Adaptive dosing, automatic shutoff, remission surveillance, and run
    interpretation.
-   Population, seed, treatment, immune, mutation, and microenvironment
    controls.
-   Protein/enzyme library, cocktail builder, and custom-agent designer.
-   `AND`, `OR`, `WEIGHTED`, and `THRESHOLD` activation logic.
-   Pathway maps, evidence labels, batch comparisons, and parameter
    sweeps.
-   Live cell viewer, signal matrix, charts, tables, and experiment
    notebook.
-   CSV, HTML, and JSON exports; experiment save/load.

Adaptive dosing and remission assessments are heuristic synthetic-model
outputs. The strongest assessment label,
`strong_cure_like_simulation_outcome`, is not evidence of biological
cure or clinical effectiveness.

## Validation

Run the test suite and representative workflow checks:

``` bash
python -m compileall -q .
python -m unittest discover -s tests -v
python run_oncoforge.py compare --steps 25 --healthy 100 --cancer 40 --seeds 1729,1730 --limit 5
python run_oncoforge.py remission-test --steps 30 --healthy 80 --cancer 10 --export outputs/reports/remission_smoke.json
python run_oncoforge.py sweep --parameter treatment --values 0.5,1.0 --steps 10 --healthy 40 --cancer 10 --adaptive-dosing --auto-shutoff --limit 5
```

On Windows, replace `python` with `py`.

## Project Files

| Path               | Purpose                                   |
|--------------------|-------------------------------------------|
| `run_oncoforge.py` | Application and CLI entry point           |
| `oncoforge/`       | Core engine, data, API, and desktop UI    |
| `schemas/`         | Evidence-fabric schema                    |
| `examples/`        | Synthetic fixtures                        |
| `tests/`           | Automated tests                           |
| `website/`         | Portal integration and deployment handoff |
| `USER_GUIDE.md`    | Operating instructions                    |
| `ROADMAP.md`       | Development roadmap                       |
| `CHANGELOG.md`     | Change history                            |

## Scientific Limitations

-   The model is qualitative and is not calibrated to patient, animal,
    organoid, or clinical data.
-   Agent actions are simplified signal/action abstractions, not
    pharmacology.
-   Immune behavior, microenvironment behavior, mutation escape, and
    repair pathways are deliberately coarse.
-   Speculative and user-concept agents are exploratory constructs, not
    established biological claims.
-   Repeated seeds, parameter sweeps, sensitivity analysis, and
    experimental validation are necessary before interpreting patterns.

---

<div align="center">

<strong>ONCOFORGE</strong>

<a href="https://rdbiotech-alaska.brenton-cart-3224.chatgpt.site/lab/oncoforge/login/">Access the research portal</a>

<sub>For access, submit an email or access request through the
portal.</sub>

</div>

