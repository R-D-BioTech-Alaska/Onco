# Webpage Build Packet For OncoForge

This is the exact website handoff for turning `/lab/oncoforge/` into the OncoForge portal front door.

The current public page can remain the overview. Add the authenticated portal under:

```text
/lab/oncoforge/login
/lab/oncoforge/signup
/lab/oncoforge/portal
```

Every cancer, cocktail, QSA, AI, and report panel must display:

```text
OncoForge is for conceptual modeling and hypothesis generation only.
It is not medical advice, not a clinical prediction tool, and not a treatment recommendation system.
```

## What The Website Needs To Create

Create these pages:

```text
/lab/oncoforge/login
/lab/oncoforge/signup
/lab/oncoforge/portal
/lab/oncoforge/portal/projects
/lab/oncoforge/portal/profiles
/lab/oncoforge/portal/experiments/{experiment_id}
/lab/oncoforge/portal/qsa/{job_id}
/lab/oncoforge/portal/reports/{report_id}
```

Create these UI components:

```text
AuthShell
ProjectDashboard
CancerProfilePicker
MissionSetupPanel
MarkerSignalPanel
CocktailRankerPanel
QsaMissionPanel
SimulationRunnerPanel
ResearchLoopPanel
ReportLibrary
SafetyNoticeBanner
AuditTimeline
```

Create these visible commands:

```text
Create Account
Start Project
Load Profile
Analyze Markers
Auto-Select Smallest Cocktail
Run Mission
Build QSA Plan
Start Bounded Research Loop
Export Report
```

Do not create dead buttons. If the backend endpoint does not exist yet, hide the button or label it as unavailable.

## First Portal Workflow

The primary workflow should be one page and one action:

```text
choose profile
choose run size
click Run Mission
show marker readout
show cocktail rank
show QSA plan
show simulation result
show next bounded loop plan
show report/export links
```

The website should call:

```text
POST /lab/oncoforge/api/portal/missions
```

Payload:

```json
{
  "profile": "melanoma_cutaneous",
  "cocktail": "",
  "steps": 120,
  "healthy": 300,
  "cancer": 100,
  "seed": 1729,
  "profile_strength": 1.0,
  "profile_heterogeneity": 0.15,
  "run_simulation": true,
  "auto_select_cocktail": true,
  "include_qsa": true,
  "include_research_loop_plan": true,
  "max_auto_experiments": 5,
  "max_qsa_candidates": 12,
  "max_marker_qubits": 16,
  "max_component_states": 4096
}
```

The local CLI equivalent is:

```powershell
python run_oncoforge.py portal-session --profile melanoma_cutaneous --steps 120 --healthy 300 --cancer 100 --json outputs/portal/web_payload.json
```

## Response Shape

The website should expect:

```text
payload_version
scope_notice
config
profile
selected_cocktail
initial_interpretation
initial_recommendation
qsa_request
qsa_result
simulation
post_run_interpretation
post_run_recommendation
research_loop_plan
web_handoff
stage_cards
hypothesis_index
mission_path
```

The most important cards are in `stage_cards`. Render those first so the page feels immediate.

## Dashboard Layout

Top band:

```text
project selector
profile selector
run mission button
safety notice
```

Main grid:

```text
left column       profile and setup
center column     marker signals and cocktail ranking
right column      QSA, run result, next action
bottom band       report library and audit timeline
```

Do not make a marketing hero inside the logged-in portal. The portal is a workbench.

## Mission Setup Fields

Use these controls:

```text
profile selector
cocktail selector
steps number input
healthy cell count number input
cancer cell count number input
seed number input
profile strength slider
heterogeneity slider
include QSA toggle
auto-select cocktail toggle
run simulation toggle
max auto experiments number input
max QSA candidates number input
max marker qubits number input
max component states number input
```

Defaults:

```text
steps: 120
healthy: 300
cancer: 100
seed: 1729
profile_strength: 1.0
profile_heterogeneity: 0.15
include_qsa: true
auto_select_cocktail: true
run_simulation: true
max_auto_experiments: 5
max_qsa_candidates: 12
max_marker_qubits: 16
max_component_states: 4096
```

## Safety Gates

Before running a larger mission, show confirmation when:

```text
steps > 300
max_auto_experiments > 10
max_qsa_candidates > 12
max_marker_qubits > 16
max_component_states > 4096
```

Reject or require admin approval when:

```text
steps > 1000
max_auto_experiments > 25
max_marker_qubits > 24
max_component_states > 20000
```

## Backend Bridge

The production bridge now exists as a WSGI application:

```text
oncoforge.web_api:application
```

The website server must verify its own user session, then proxy mission requests with the private `ONCOFORGE_API_KEY`. Never send that key to browser JavaScript. The browser helper and deployment instructions are in:

```text
website/oncoforge-client.js
website/WEBSITE_UPLOAD.md
```

For local connection testing, run `python run_oncoforge.py serve-api`. For production, use the hosting provider's WSGI process manager behind HTTPS.

## Visual Copy

Use these labels:

```text
Mission Control
Marker Readout
Cocktail Rank
QSA Structural Plan
Simulation Result
Next Bounded Loop
Reports
```

Avoid these labels:

```text
Cure found
Treatment recommendation
Clinical prediction
Patient result
```

## Account Rules

First launch should allow:

```text
email account
project workspaces
saved missions
saved reports
role: viewer, researcher, maintainer, admin
```

First launch should not allow:

```text
patient medical records
real treatment instructions
public sharing of custom agents without review
unbounded background jobs
```

## Done Means

The webpage side is ready when:

- Login and signup route users into `/lab/oncoforge/portal`.
- The portal can submit a mission payload.
- The portal can render stage cards immediately.
- The portal shows marker/cocktail/QSA/simulation/report panels.
- Scope notice is visible in every scientific result area.
- Long jobs are bounded or confirmed.
