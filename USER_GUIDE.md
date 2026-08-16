# OncoForge User Guide

OncoForge combines an evidence-governed website research engine with a separate conceptual cancer-systems simulator. It is not a clinical tool and does not predict patient outcomes, prove safety or efficacy, or recommend treatment.

## Website Target Forge

Target Forge is the primary workflow for evidence-backed target and logic-gate research:

1. Sign in to the OncoForge website workspace.
2. Create a research project.
3. Upload an `oncoforge.evidence.v1` JSON file, or choose the clearly labeled synthetic demonstration.
4. Keep `Strict normal exclusion` selected unless the research protocol requires documented changes.
5. Select **Run full Target Forge**. Evidence validation, tumor/normal compilation, bounded gate search, Pareto selection, classical control, and the optional QSA check run as one operation.
6. Review **Normal safety** before tumor coverage or QSA output.
7. Open a hypothesis to inspect source assertions, contradiction links, missing evidence, escape routes, validation experiment, and falsification condition.
8. Download the original report JSON for the audit record.

`SYNTHETIC FIXTURE` means software-test data. `EVIDENCE BACKED` means the result was derived from supplied evidence; it does not mean experimentally validated or clinically safe. Missing critical-normal evidence is a rejection, not zero risk.

The machine-readable evidence contract is `schemas/evidence_fabric.schema.json`. The complete website implementation handoff is `website/ONCOFORGE_VNEXT_WEBSITE_PROMPT.md`.

## The core idea

OncoForge treats the system as four interacting parts:

```text
Cancer cells      = abnormal signal generators
Healthy cells     = the tissue you must protect
Agents            = proteins, enzymes, immune mechanisms, or synthetic concepts
Cocktails         = multi-agent signal-reading systems
```

A strong run is not simply `Cancer = 0`. A stronger run looks like this:

```text
Cancer clears
Healthy cells remain high
Treatment intensity tapers or shuts off
Inflammation falls
Immune pressure falls
Healthy damage stops
Cancer does not recur during post-clearance watch steps
```

## Legacy Simulator GUI

1. Run the app:

```bash
python run_oncoforge.py
```

2. Go to **Cell Population** and choose a cancer preset.
3. Go to **Cocktail Builder** and choose a cocktail.
4. Go to **Dosing & Cure Test**.
5. Turn on:
   - **Enable adaptive dosing**
   - **Auto-shutoff after confirmed zero cancer**
   - **Leave low-intensity surveillance after clearance** if you want a gentle monitoring phase
6. Go to **Dashboard** and click **Reset**.
7. Click **Run 100** or use the cure/remission test button.
8. Read **Dosing & Cure Test -> Plain-English interpretation**.
9. Export an HTML or JSON report.

## How to read a run

Read outputs in this order:

1. **Cancer count**: did the model clear cancer or only suppress it?
2. **Healthy count**: how much healthy tissue survived?
3. **Dead count**: how expensive was the run biologically?
4. **Healthy damage events**: is the cocktail injuring healthy cells?
5. **Inflammation / immune pressure**: is the system overactivated?
6. **Treatment intensity / dosing phase**: did the controller taper, surveil, or shut off?
7. **Escape clone events**: did resistant clones emerge?
8. **Zero-cancer confirmation steps**: how long did the system remain cancer-free before shutoff?
9. **Cure-pathway classification**: what does the simulator think the next experimental step is?

## Cancer profiles and marker-driven cocktail choice

Cancer profiles are simulation presets, not clinical diagnostic profiles. They bias generated cancer cells toward conceptual marker patterns such as immune visibility, immune evasion, DNA-repair stress, hypoxia, stromal barrier, or high proliferation.

Tutorial: Choosing a cocktail from cancer-cell markers

1. Open **Cancer Profiles**.
2. Select a cancer profile.
3. Click **Create cells from profile**.
4. Click **Analyze current profile signals**.
5. Review top cancer-specific markers and healthy-overlap warnings.
6. Click **Recommend cocktail from profile**.
7. Prefer the smallest cocktail that covers cancer-specific signals with lower healthy overlap.
8. Click **Run profile simulation**.
9. Review marker evolution and survivor markers.
10. Run a remission test and export the report.

The recommendation engine ranks cocktails by signal match, selectivity, healthy overlap, inflammation risk, escape control, evidence level, and remission suitability. It suggests simulation experiments only.

To add custom profiles, copy the structure in `oncoforge/data/cancer_profiles.json` or use **Duplicate as custom profile** from the Cancer Profiles tab. To add agents, edit the JSON agent files and keep evidence labels/limitations explicit.

## Local AI assistant

Local AI is optional. Normal OncoForge runs do not require it.

Ollama example:

```powershell
ollama serve
ollama pull llama3.1
python run_oncoforge.py ai-test --provider ollama --model llama3.1
```

LM Studio or another OpenAI-compatible local endpoint:

```powershell
python run_oncoforge.py ai-test --provider lmstudio --base-url http://localhost:1234 --model local-model-name
```

The local AI receives only simulation summaries and must suggest simulation experiments, not medical decisions. The research loop is bounded by max experiment count, max steps, runtime limits, and an explicit confirmation flag.

## QSA-ready structural search

The QSA plan command builds a bounded quantum-strategy payload from a cancer profile, signal interpretation, and cocktail ranking. It does not require QSA to be installed. If no backend is attached, OncoForge uses a deterministic structural fallback scorer and tells you that plainly.

```powershell
python run_oncoforge.py qsa-plan --profile melanoma_cutaneous --json outputs/reports/qsa_plan.json
```

The JSON contains marker qubits, candidate cocktail states, objective terms, hard workload limits, and the scope notice. It is meant for the future web portal and optional QSA adapter, not for clinical treatment decisions.

## Portal mission payload

The portal mission command builds the integrated JSON payload the webpage should use for the logged-in workbench. It loads the profile, reads marker signals, ranks cocktails, builds a QSA plan, runs the selected simulation, re-analyzes survivors, and writes a mission payload.

```powershell
python run_oncoforge.py portal-session --profile melanoma_cutaneous --steps 120 --healthy 300 --cancer 100 --json outputs/portal/web_payload.json
```

Use `--no-run` to prepare a web payload without running the simulation, or `--no-qsa` if a page only needs profile/cocktail data.

## Website API

The website can call the mission engine through `oncoforge.web_api:application`. For a local connection test:

```powershell
$env:ONCOFORGE_API_KEY="local-test-key"
python run_oncoforge.py serve-api --host 127.0.0.1 --port 8765
```

The website server, not browser JavaScript, sends the private API key. Public mission requests are bounded, cannot select filesystem output paths, and do not receive server paths in responses. Use `website/WEBSITE_UPLOAD.md` as the deployment handoff.

Related design docs:

- `docs/ONCOFORGE_PORTAL_SYSTEM.md`
- `docs/QSA_INTEGRATION_CONTRACT.md`
- `docs/WEBPAGE_BUILD_PACKET.md`
- `docs/GITHUB_PUBLICATION_PLAN.md`
- `docs/CLAIMS_AND_SAFETY_POLICY.md`
- `website/WEBSITE_UPLOAD.md`

## Dosing phases

| Phase | Meaning |
|---|---|
| `manual_full_dose` | Adaptive dosing is off. The configured treatment multiplier is used. |
| `full_pressure` | Cancer is still above taper thresholds. Full pressure remains active. |
| `tapering` | Cancer burden dropped below the taper threshold. Dose is reduced. |
| `minimal_residual_watch` | Cancer burden is very low. Dose is reduced further. |
| `remission_confirmation` | Cancer is currently zero, but the run is still proving durability. Low treatment pressure remains active. |
| `remission_surveillance` | Cancer stayed at zero through confirmation. Broad pressure is reduced and only safer surveillance-style agents may remain active. |
| `post_clearance_shutoff` | Cancer stayed at zero through confirmation and treatment agents are paused. |
| `toxicity_adjusted_*` | Inflammation or healthy damage crossed a safety threshold, so dose was reduced. |

## Cure-pathway classifications

| Classification | Meaning |
|---|---|
| `not_started` | No simulation history exists yet. |
| `not_cleared` | Cancer remains detectable. |
| `clearance_needs_remission_test` | Cancer reached zero, but not enough post-clearance steps have been run. |
| `recurrence_observed` | Cancer reached zero and later reappeared. |
| `clearance_with_recovery_concerns` | Cancer cleared, but healthy preservation, inflammation, or immune pressure are concerning. |
| `clearance_with_post_clearance_damage` | Cancer cleared, but treatment kept damaging healthy cells afterward. |
| `strong_cure_like_simulation_outcome` | The run cleared cancer, watched afterward, avoided recurrence, and recovery metrics looked acceptable. This is still only a simulation result. |

## Recommended experiment sequence

Use a repeated pattern instead of trusting one run.

### 1. Baseline

Run with a weak or no cocktail to see the preset's natural behavior.

### 2. Small cocktail

Try a narrow cocktail that targets only one or two systems.

### 3. Broader cocktail

Add immune visibility, apoptosis pressure, or microenvironment gating.

### 4. Adaptive remission test

Enable adaptive dosing and run a longer watch period.

### 5. Compare across seeds

A result is more interesting if it repeats across several random seeds.

## Useful CLI commands

Run a guided remission test:

```bash
python run_oncoforge.py remission-test --healthy 700 --cancer 300 --steps 370 --preset generic_p53_loss --cocktail full_conceptual_swarm --export outputs/reports/remission_test.html
```

Run one adaptive simulation and print the interpretation:

```bash
python run_oncoforge.py run --steps 150 --healthy 700 --cancer 300 --preset generic_p53_loss --cocktail full_conceptual_swarm --adaptive-dosing --auto-shutoff --interpret --export outputs/reports/adaptive_run.html
```

Compare cocktails with adaptive dosing:

```bash
python run_oncoforge.py compare --steps 120 --healthy 250 --cancer 100 --seeds 1729,1730,1731 --adaptive-dosing --auto-shutoff --limit 20
```

Sweep one parameter to see how sensitive a result is:

```bash
python run_oncoforge.py sweep --parameter treatment --values 0.5,0.75,1.0,1.25 --steps 120 --adaptive-dosing --auto-shutoff --json outputs/sweep_treatment.json
python run_oncoforge.py sweep --parameter oxygen --values 0.25,0.50,0.75,1.0 --steps 120 --csv outputs/sweep_oxygen.csv
```

Export JSON instead of HTML:

```bash
python run_oncoforge.py remission-test --steps 300 --export outputs/reports/remission_test.json
```

## Parameter sweeps

Parameter sweeps answer a different question than single runs. Instead of asking "did this run work?" they ask "how dependent is this result on one parameter?"

Useful sweep parameters include:

- `treatment`
- `immune`
- `mutation`
- `recovery`
- `surveillance_intensity`
- `oxygen`
- `acidity`
- `inflammation`
- `immune_pressure`
- `stromal_barrier`

Sweeps are ranked by cure-pathway score, final cancer, recovery, and healthy-cell outcomes.

## Good signs vs warning signs

Good signs:

- Cancer count reaches zero.
- Healthy cells remain high.
- Treatment intensity falls after clearance.
- Healthy damage events stop.
- Inflammation and immune pressure fall.
- No recurrence during the watch period.

Warning signs:

- Cancer reaches zero but treatment hits continue.
- Healthy damage keeps occurring after clearance.
- Inflammation stays near 1.0.
- Immune pressure stays near 1.0.
- Escape clones increase.
- Cancer reappears after clearance.

## What to improve after a warning sign

| Warning sign | Try this |
|---|---|
| Healthy damage after cancer = 0 | Turn on auto-shutoff or lower surveillance intensity. |
| Inflammation too high | Lower inflammation-driving agents or lower treatment multiplier. |
| Cancer not clearing | Add agents that cover missed signals in the Signal Matrix. |
| Recurrence | Inspect clone summary and add surveillance for the recurrent clone's signals. |
| Too many escape events | Use multi-signal gates, reduce selective pressure, or add coverage for immune-evasion channels. |

## Scientific caution

OncoForge can help you think. It cannot tell anyone what treatment to take. A model result is a hypothesis, not evidence of real-world safety or efficacy.
