# Claims And Safety Policy

OncoForge can be ambitious without overclaiming. The system may search, rank, explain, and compare conceptual simulation hypotheses. It must not present outputs as real cures, clinical protocols, patient treatment advice, or validated oncology predictions.

Required notice:

```text
OncoForge is for conceptual modeling and hypothesis generation only.
It is not medical advice, not a clinical prediction tool, and not a treatment recommendation system.
```

## Allowed Language

Use:

- conceptual profile
- simulated marker
- modeled signal
- hypothesis
- candidate simulation
- preclinical concept
- ranked for exploration
- requires external validation

Avoid:

- cures cancer
- treatment recommendation
- patient-specific
- clinically proven by OncoForge
- validated therapy
- guaranteed selectivity
- safe for humans

## Output Labels

Every report and portal result should separate:

```text
established biology
supported modeling assumption
inferred interaction
speculative hypothesis
user concept
```

The existing evidence labels already support this pattern. Do not collapse them into a single confidence score that looks clinical.

## Account And Data Safety

The first portal should not accept patient medical records, protected health information, or clinical histories. If that ever changes, the project needs a separate compliance design before launch.

Allowed early data:

- user account email
- project title and notes
- selected built-in profiles
- custom conceptual profiles
- simulation settings
- simulation outputs

Not allowed in early public portal:

- patient names
- medical record numbers
- real treatment plans
- lab orders
- diagnostic claims
- emergency or care decisions

## AI Safety

Local or hosted AI may summarize simulation data and suggest next simulations. It must not suggest real treatment decisions.

AI output must be treated as advisory text unless it passes a strict schema validator. Current research-loop behavior records free text and does not execute AI suggestions automatically.

## QSA Safety

QSA jobs are math and simulation search jobs. They do not validate biology by themselves.

Every QSA result should include:

- exactness or fallback status
- resource limits used
- candidate ranking
- reason fields
- scope notice
- rejection details if limits fail

## Portal Safety Gates

Required gates:

- Rate limit account creation and login.
- Require confirmation before long research loops.
- Reject over-limit simulation and QSA jobs.
- Store audit events for profile edits, job starts, report exports, and role changes.
- Show scope notices beside recommendation outputs.
- Disable public custom-agent sharing until review controls exist.

## Human Review Gate

Any claim that moves from simulation to wet-lab or clinical language requires human review outside OncoForge. The software should provide reproducible reports, not authority.

