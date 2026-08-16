# QSA Integration Contract

QSA is the optional structural quantum execution layer for OncoForge. It may organize or validate bounded mathematical workloads, but it does not replace biological evidence and may not claim acceleration until an information-identical benchmark demonstrates it.

OncoForge sends QSA a compact workload:

```text
cancer profile
marker qubits
candidate cocktail states
objective terms
hard resource limits
```

QSA returns a ranked candidate list, resource notes, and exactness/fallback status.

## Design Rule

QSA should follow its own structural rule inside OncoForge:

```text
Do not build a global statevector unless the workload actually requires one.
```

For OncoForge, that means marker/candidate search starts as independent or lightly coupled components. If a job becomes globally entangled, too wide, or too expensive, the adapter rejects it or falls back through an explicit exact route. It must not silently approximate.

## Current Target Forge Adapter

The implemented adapter is:

```text
oncoforge/core/onco_qsa.py
```

Target Forge first evaluates every gate with the exact classical bitset engine and identifies the Pareto class. The QSA adapter then certifies whether the candidate state space is exactly representable as marked and unmarked permutation-symmetric count classes. Eligible work executes with `qsa.SymmetryState`; ineligible, unavailable, or mismatched work fails closed to the retained classical result.

Every receipt records candidate/marked/padded counts, qubits, class counts, oracle hash, QSA runtime version, iterations, expected and observed marked probability, analytic error, classical control hashes, fallback state, and a deterministic receipt hash.

Version 1 does not claim a search advantage because oracle compilation enumerates all candidates classically. The QSA result validates exact compressed amplitude evolution; it does not validate target biology.

## Legacy Simulation Strategy Contract

The local module is:

```text
oncoforge/core/quantum_strategy.py
```

CLI:

```powershell
python run_oncoforge.py qsa-plan --profile melanoma_cutaneous --json outputs/reports/qsa_plan.json
```

The module produces a `QuantumSearchRequest` with:

```text
profile_id
profile_name
marker_qubits
candidates
limits
objective_terms
scope_notice
```

If no QSA backend is attached, `run_quantum_strategy()` uses a deterministic structural fallback scorer. This older profile/cocktail strategy path is separate from the implemented Target Forge `SymmetryState` receipt.

## Backend Adapter Function

A QSA adapter should expose:

```python
evaluate_oncoforge_candidates(request_dict: dict) -> dict
```

The returned dictionary should include:

```text
ok
backend
profile_id
profile_name
ranked_candidates
resource_report
exactness_report
scope_notice
message
```

If the backend cannot certify an exact bounded route, it should return:

```text
ok: false
errors: [...]
message: clear rejection or exact fallback explanation
```

## Marker Qubits

Marker qubits are not patient markers. They are compact simulation variables derived from OncoForge signal interpretation:

```text
signal
group
weight
cancer_mean
healthy_mean
targetability_score
```

Weights come from targetability, cancer/healthy separation, and prevalence. High healthy overlap lowers the value.

## Candidate Cocktail States

Candidate states come from the treatment matcher:

```text
cocktail_name
agents
matched_signals
base_score
predicted_selectivity
remission_suitability
healthy_overlap_penalty
inflammation_risk_penalty
broadness_penalty
signal_focus
structural_score
```

QSA may re-rank candidates, test pair interactions, or estimate bounded objective landscapes. It must keep enough metadata to explain why a result moved up or down.

## Hard Limits

Default limits:

```text
max_candidates: 12
max_marker_qubits: 16
max_pair_terms: 48
max_steps_per_candidate: 300
max_qsa_seconds: 60
max_component_states: 4096
require_exact_or_reject: true
```

Portal users can request smaller limits. Larger limits need an admin-controlled policy and should still fail closed.

## What QSA May Do

Allowed:

- Rank simulation cocktails against marker qubits.
- Search bounded parameter settings for simulations.
- Run exact structural estimators where resource limits allow.
- Reject jobs when exactness or resource gates fail.
- Return reproducible resource and exactness reports.

Not allowed:

- Claim a real cure.
- Recommend patient treatment.
- Use patient-specific medical data without a compliant data policy.
- Hide approximation or truncation.
- Keep running after portal limits are exceeded.

## BrainQ And Onco Adapters

BrainQ and Onco should connect through the same adapter style:

```text
small request dict in
small result dict out
scope notice always present
bounded runtime
clear rejection on unsupported work
```

This keeps the portal from depending on internal code shape across separate repositories.
