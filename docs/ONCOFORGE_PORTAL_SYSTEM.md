# OncoForge Portal System

OncoForge should become a public GitHub-backed cancer-systems research portal while keeping the current Python simulator clean, inspectable, and standard-library friendly.

Core rule:

```text
Read the cancer-cell marker/signaling profile first, then choose the smallest effective conceptual cocktail that covers cancer-specific signals while avoiding healthy-cell overlap and excessive inflammation.
```

Every layer keeps the same boundary:

```text
OncoForge is for conceptual modeling and hypothesis generation only.
It is not medical advice, not a clinical prediction tool, and not a treatment recommendation system.
```

## Product Shape

The public webpage at `/lab/oncoforge/` becomes the front door. The portal itself should be an authenticated web app mounted under the same lab path:

```text
/lab/oncoforge/                public overview
/lab/oncoforge/login           login
/lab/oncoforge/signup          account creation
/lab/oncoforge/portal          authenticated workspace
/lab/oncoforge/api/...         backend API
```

The existing Tkinter app remains a local research workstation. The portal calls the same core concepts through an API layer, not by duplicating model logic in JavaScript.

## User-Facing Portal Views

1. Login and account creation
2. Project dashboard
3. Cancer profile library
4. Marker interpreter
5. Cocktail matcher
6. Simulation runner
7. QSA structural search
8. Research loop monitor
9. Reports and exports
10. Audit and safety log

No page should imply clinical use. Every recommendation panel must say it is ranking simulation experiments.

## System Layers

```text
Web portal
  Auth, projects, forms, dashboards, reports

Portal API
  Validates requests, owns accounts, queues long jobs, stores results

OncoForge core
  Profiles, signals, simulations, treatment matching, reports, research loops

Quantum strategy layer
  Converts marker/cocktail outputs into bounded QSA-ready search workloads

Optional adapters
  QSA, BrainQ, Onco, local AI

Storage
  Users, projects, experiments, reports, audit events, exported JSON/HTML
```

The portal should never let a browser directly run unbounded simulations or unbounded QSA jobs. All heavy work goes through a bounded job API.

## Account Model

Use server-side authentication, not a browser-only login. Good first options:

- Email magic link or OAuth for public accounts.
- Admin-created accounts for early private testing.
- Session cookies with `HttpOnly`, `Secure`, and `SameSite=Lax`.
- Password login only if password reset, rate limits, hashing, and lockout are implemented correctly.

Suggested roles:

```text
viewer       read reports and public examples
researcher   create projects and run bounded jobs
maintainer   edit shared profile/agent libraries
admin        manage users, limits, and releases
```

## Data Objects

```text
User
  id, email, display_name, role, created_at, disabled_at

Project
  id, owner_id, title, description, visibility, created_at

CancerProfile
  id, display_name, category, tags, markers, biases, limitations

Experiment
  id, project_id, profile_id, cocktail_name, config, status, created_at

SignalInterpretation
  experiment_id, dominant_signals, targetable_signals, overlap_warnings

CocktailRecommendation
  experiment_id, ranked_cocktails, addon_agents, avoid_or_gate_agents

QSAJob
  id, project_id, request, limits, status, result, created_at, completed_at

Report
  id, experiment_id, html_path, json_path, summary, scope_notice

AuditEvent
  actor_id, action, object_type, object_id, before, after, created_at
```

## API Contract

Keep API payloads JSON-first and close to the existing CLI outputs.

```text
GET  /lab/oncoforge/api/health
GET  /lab/oncoforge/api/profiles
GET  /lab/oncoforge/api/profiles/{profile_id}
POST /lab/oncoforge/api/projects
GET  /lab/oncoforge/api/projects
POST /lab/oncoforge/api/experiments
GET  /lab/oncoforge/api/experiments/{experiment_id}
POST /lab/oncoforge/api/experiments/{experiment_id}/run
POST /lab/oncoforge/api/experiments/{experiment_id}/interpret-signals
POST /lab/oncoforge/api/experiments/{experiment_id}/recommend-cocktail
POST /lab/oncoforge/api/qsa/jobs
GET  /lab/oncoforge/api/qsa/jobs/{job_id}
POST /lab/oncoforge/api/research-loops
GET  /lab/oncoforge/api/research-loops/{loop_id}
GET  /lab/oncoforge/api/reports/{report_id}
GET  /lab/oncoforge/api/audit
```

Long-running endpoints return a job ID. The portal polls status or uses server-sent events. No long request should hold a browser connection open for a full simulation loop.

## Automated Flow

The portal's one-click path should map to the existing bounded logic:

```text
select profile
  -> generate bounded profile simulation
  -> interpret markers
  -> rank cocktails
  -> run selected cocktail
  -> capture marker evolution
  -> suggest next bounded simulation
  -> export report
```

The default should run a small, fast job. Larger jobs require explicit confirmation and show the exact limits before starting.

The current one-call core entrypoint is:

```powershell
python run_oncoforge.py portal-session --profile melanoma_cutaneous --steps 120 --healthy 300 --cancer 100 --json outputs/portal/web_payload.json
```

For a backend service, import:

```python
from oncoforge.core.portal_mission import PortalMissionConfig, build_portal_mission
```

The webpage build requirements are listed in `docs/WEBPAGE_BUILD_PACKET.md`.

## Workload Limits

Suggested portal defaults:

```text
max_steps_per_experiment: 300
max_auto_experiments: 10
max_total_runtime_minutes: 30
max_candidates_for_qsa: 12
max_marker_qubits_for_qsa: 16
max_component_states_for_qsa: 4096
max_saved_reports_per_project: configurable
```

When a request exceeds a limit, reject it with a clear message and a smaller suggested configuration.

## Adapter Boundaries

Adapters should be optional and small:

```text
oncoforge.core       local simulator and scoring
QSA adapter          exact structural search and estimator workloads
BrainQ adapter       future neural/brain-inspired analysis surface
Onco adapter         legacy or public Onco compatibility surface
Local AI adapter     simulation summaries and next-simulation suggestions
```

Do not vendor QSA, BrainQ, or Onco inside this project. Link them as optional dependencies or sibling services so each repository stays understandable.

## Public GitHub Shape

The GitHub repository should expose:

```text
oncoforge/               core Python package
oncoforge/data/          profiles, agents, presets
tests/                   unit tests
docs/                    portal, QSA, safety, publication docs
.github/workflows/       CI
run_oncoforge.py         GUI/CLI entrypoint
requirements.txt         required dependencies
pyproject.toml           package metadata
```

The public README can stay plain and direct. It should say what the system does, how to run it, what it does not do, and how to reproduce tests.

## Release Gate

A release is ready only when:

- `python -m compileall -q .` passes.
- `python -m unittest discover -s tests -v` passes.
- Required CLI smoke commands pass.
- Reports include scope notices.
- QSA jobs reject over-limit workloads.
- Local AI failure remains graceful.
- No absolute local paths are required to run the project.
