# OncoForge Website Implementation Prompt

Continue the existing `https://rdbiotech.org/lab/oncoforge/` website project. Build the real logged-in OncoForge research portal against the Python API described below. Do not replace the current website stack, authentication system, brand, or shared components. Read the existing website code first and make focused changes in its established style.

## Nonnegotiable Direction

OncoForge is a website-based computational cancer research and hypothesis system. The browser is the interface. The Python repository at `R-D-BioTech-Alaska/Onco` is the scientific execution service. Do not recreate its target/gate algorithms in JavaScript and do not build a desktop app.

Keep the implementation direct and authored-looking: no generated-agent scaffolding, PR agents, placeholder dashboards, fake datasets, fake citations, decorative quantum effects, or buttons without complete behavior. Reuse the website's current auth, database, navigation, forms, tables, dialog, toast, and server-route patterns.

This is research software only. Never call a result a cure, treatment, diagnosis, safe therapy, clinical prediction, or validated biological fact. A computational candidate is a hypothesis until independently measured and experimentally validated.

## Runtime Boundary

```text
browser
  -> existing website login/session
  -> same-origin website server route
  -> private ONCOFORGE_API_KEY added server-side
  -> OncoForge Python API
```

The browser must never receive `ONCOFORGE_API_KEY` or the private Python service URL. Every protected server route must verify the website session and check that the signed-in account owns the requested project/run before proxying it.

Private server variables:

```text
ONCOFORGE_SERVICE_URL=<private origin of the Python service>
ONCOFORGE_API_KEY=<long private shared secret>
```

Do not store patient records or protected health information. Evidence uploads in this version are research datasets that the account is authorized to use.

## Required Routes

Use the existing login/create-account routes. Add or finish these authenticated portal routes using the website's current route conventions:

```text
/lab/oncoforge/                         research workspace and recent runs
/lab/oncoforge/projects/new             create a research project
/lab/oncoforge/projects/{projectId}     project evidence and run history
/lab/oncoforge/projects/{projectId}/target-forge/new
/lab/oncoforge/projects/{projectId}/runs/{runId}
```

The first authenticated screen must be the usable research workspace, not a marketing page. If the user is signed out, preserve the intended destination through login.

## Python API

Same-origin proxy prefix:

```text
/lab/oncoforge/api
```

Public service calls:

```text
GET /health
GET /profiles
GET /profiles/{profile_id}
```

Protected calls:

```text
POST /portal/missions
GET  /portal/missions/{mission_id}
POST /target-forge/runs
GET  /target-forge/runs/{run_id}
```

Use `website/oncoforge-client.js` from the Onco repository. Its Target Forge call is:

```javascript
const result = await runTargetForge(evidenceFabric, config);
// result = { ok: true, run_id: string, report: TargetForgeReport }
```

The create request is:

```json
{
  "evidence": { "schema_version": "oncoforge.evidence.v1", "project_id": "...", "entities": [], "sources": [], "assertions": [] },
  "config": {
    "min_tumor_coverage": 0.6,
    "min_clone_coverage": 0.5,
    "max_normal_activation": 0.05,
    "max_critical_normal_activation": 0.0,
    "max_unknown_normal_fraction": 0.0,
    "max_unknown_clone_fraction": 0.0,
    "require_critical_normal_samples": true,
    "max_targets": 16,
    "max_candidates": 1500,
    "max_results": 50,
    "allow_transcript_fallback": false,
    "use_qsa": true
  }
}
```

The website proxy must accept JSON bodies up to 2 MiB for this route, enforce the website's per-account rate limit, forward the body unchanged, apply an execution timeout appropriate to the host, and return the Python status code and JSON error. Never let the browser choose a server filesystem path.

## Project Storage

Use the existing website database and ownership patterns. Store only what the portal needs:

```text
OncoForgeProject
  id, ownerUserId, name, description, createdAt, updatedAt
  evidenceFileName, evidenceSchemaVersion, evidenceFabricHash
  evidencePayload or private object-storage reference

OncoForgeRun
  id, ownerUserId, projectId, pythonRunId
  status, createdAt, completedAt, error
  config, reportHash
  reportPayload or private object-storage reference
```

Validate ownership on every read. Do not expose sequential database IDs when the current website supports opaque IDs. Follow existing retention/deletion behavior. A project deletion must remove its private evidence and run payloads.

## Workspace

Build a quiet, dark research interface consistent with the current R&D BioTech site. Use graphite/near-black surfaces, clear white text, cyan for selection, green for eligible, amber for uncertain, and red for rejected or normal-tissue liability. Do not make it a one-color dark-blue interface. Keep corners at 8 px or less. Use the site's icon library; use icon buttons for familiar actions and tooltips for unfamiliar icons.

Desktop layout:

```text
compact top bar: OncoForge / project switcher / service status / account
left navigation: Workspace, Projects, Target Forge, Runs, Evidence
main content: dense page header, controls, tables, inspectors
```

Mobile layout must collapse navigation without hiding scientific fields. Tables may become horizontally scrollable, but labels and values must never overlap.

The workspace page shows recent projects, recent runs, failed runs needing attention, and one primary `New Target Forge run` command. Do not add decorative metric cards. Use compact status rows and tables.

## Target Forge Run Page

Create a complete one-run workflow so users do not have to perform each computational step manually.

### Evidence

Support drag/drop and file selection for one OncoForge evidence JSON. Parse it in the browser only for immediate schema shape feedback and summary counts; the Python service remains authoritative. Show:

Use `schemas/evidence_fabric.schema.json` from the Onco repository for browser-side shape validation.

```text
project_id
schema_version
entity, source, assertion counts
evidence classes as separate counts
claim categories as separate counts
file name and size
```

Add `Use synthetic demonstration` only if the website ships the exact file `examples/target_forge_synthetic.json` from the Onco repository as a static asset. Label it `SYNTHETIC FIXTURE` everywhere. Never relabel its values as measured data.

### Run Controls

Default to a `Strict normal exclusion` preset using the request above. Put advanced settings in a clear expandable section. Use numeric inputs for thresholds and candidate bounds; toggles for critical-normal requirement, dependency requirement, transcript fallback, and QSA; and a compact multi-select for SINGLE, AND, OR, and AND-NOT gate families. Keep all gate families enabled by default and prevent a state with none selected. Do not use free-text controls for enumerated modes.

The primary command is `Run full Target Forge`. One click must:

1. validate the selected evidence and settings;
2. create a website run record with `running` status;
3. call `POST /target-forge/runs` through the authenticated server proxy;
4. save the returned Python run ID, report hash, config, and report;
5. mark the run complete or failed;
6. navigate to the completed run page.

Disable duplicate submission while running. Show an honest progress state such as `Validating evidence`, `Compiling tumor-normal model`, and `Evaluating bounded gates`; do not display invented percentages. A failure must preserve the form and show the API error.

### Results

The completed run page starts with this permanent notice:

```text
Research hypothesis output. Not medical advice, a clinical prediction, or proof of safety or efficacy.
```

Show origin prominently: `SYNTHETIC FIXTURE` or `EVIDENCE BACKED`. Never imply that evidence-backed means clinically validated.

Use tabs or clearly separated full-width views:

```text
Hypotheses
All gates
Evidence
Normal safety
QSA receipt
Reproducibility
```

Hypotheses table columns:

```text
gate expression
tumor coverage
clone coverage
patient coverage
normal activation
critical-normal activation
evidence tier
evidence classes
```

All-gates table adds operation, missing tumor fraction, missing normal fraction, missing clone fraction, missing patient fraction, dependency support, Pareto status, eligibility, and rejection reasons. Provide filtering by operation, eligible/rejected, Pareto, and evidence class. Provide sortable individual columns. Do not calculate or display one combined score.

Use a side inspector or full-width detail region for the selected candidate. It must show:

```text
candidate and hypothesis IDs
positive and negative sensors
required biomarker thresholds and units
supporting assertion IDs
contradicting assertion IDs
active and unknown normal samples
predicted escape routes
uncertainty fields
proposed validation experiment
falsification condition
provenance hash
```

Normal safety is a first-class view, not a footnote. Put critical-normal activation, unknown critical-normal count, active normal samples, unknown normal samples, and threshold failures at the top. Red is reserved for actual rejection/liability states, not decoration.

### QSA Inspector

Render `report.qsa_receipt` exactly as a computation receipt:

```text
status and runtime version
representation
eligibility and reason
candidate, marked, logical, and padded state counts
qubits and class counts
oracle hash
iterations
expected and observed marked probability
analytic error and tolerance
classical control hashes and information-identical flag
receipt hash
fallback or failure
advantage assessment
limitations
```

Display the API's `advantage_assessment` without rewriting it. Do not call the cell, tumor, target, or biology physically quantum. Do not claim quantum superiority or a discovered cure.

### Evidence and Reproducibility

Render evidence classes and claim categories as separate labeled groups. Keep these labels distinct throughout the UI:

```text
MEASURED
DERIVED
PREDICTED
INFERRED
HYPOTHESIZED
SIMULATED
```

Show fabric hash, input file hash, tumor-model hash, problem hash, report hash, software commit, algorithm, random seed, and configured bounds. Add JSON download using the saved report payload. Do not reconstruct a report in the browser.

## Existing Mission Simulator

Keep the current profile/mission simulator available under a `Simulation` area, but label it `Conceptual simulation`. Do not mix its hand-authored potency, specificity, healthy-cell risk, or cocktail rankings into Target Forge evidence or hypothesis tables.

## States and Accessibility

Implement loading, empty, validation error, API error, unauthorized, forbidden, not found, complete, synthetic, evidence-backed, QSA disabled, QSA ineligible, QSA fallback, and QSA exact states. All actions must be keyboard accessible, focus visible, and screen-reader labeled. Use real table headers and form labels. Confirm destructive project/run deletion.

## Acceptance Checks

1. A signed-out user cannot create or retrieve a run.
2. One account cannot retrieve another account's project or Python run ID.
3. The API key and private service URL never appear in browser code, HTML, logs returned to the browser, or network requests from the browser.
4. Uploading `target_forge_synthetic.json` and using strict defaults completes in one command and renders two or more Pareto hypotheses from the current fixture.
5. The unsafe synthetic single target is visibly rejected for normal/critical-normal activation.
6. The synthetic `A AND NOT C` result shows zero synthetic normal activation and remains labeled synthetic.
7. Missing critical-normal evidence is rendered as a rejection, not as zero risk.
8. QSA-disabled and QSA-fallback reports still render the classical results.
9. No view creates a combined truth, cure, or efficacy score.
10. Every visible button works, every protected route checks the website session, and desktop/mobile layouts have no overlap.

Run the website's formatter, type checker, unit tests, route tests, and browser tests. Exercise the complete signed-in upload-to-report flow with the exact synthetic fixture before considering the portal complete.
