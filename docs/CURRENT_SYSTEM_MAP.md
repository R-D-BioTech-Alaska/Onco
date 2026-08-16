# OncoForge Current System Map

Audited for OncoForge `0.7.0` against the public QSA `0.2.0` source on 2026-08-15. This map separates working software from biological evidence and planned capability.

## Current Components

| Component | Current function | Scientific status | Decision |
|---|---|---|---|
| Cell simulation | Agent-based cancer/healthy cell signal simulation, evolution, escape, dosing, and remission watch | Synthetic conceptual model | Retain in the simulation lane; never use its hand-authored potency or risk values as patient evidence |
| Cancer profiles | Curated conceptual profile presets and marker biases | Mixed literature-inspired abstraction | Retain for education and synthetic experiments; replace profile claims with evidence-fabric assertions in discovery work |
| Signal interpreter | Compares modeled cancer and healthy signals | Derived from synthetic state | Retain for simulator interpretation only |
| Treatment matcher | Ranks bundled conceptual cocktails | Synthetic heuristic | Retain under explicit simulation labels; do not merge with Target Forge evidence ranking |
| Automation and sweeps | Runs bounded simulations, comparisons, and exports | Reproducible software workflow | Retain |
| Local AI connector | Optional bounded summary and experiment suggestions | Language-model output | Retain as optional; never accept as evidence without a source assertion |
| Portal mission API | Authenticated profile/simulation mission creation | Working web transport over conceptual simulation | Retain |
| Evidence fabric | Typed entities, contexts, sources, assertions, contradictions, and provenance hashes | Working evidence infrastructure | Foundation for all discovery engines |
| TumorResearchModel | Compiles tumor, clone, patient, normal, and target measurements from evidence | Working typed intermediate representation | Foundation |
| Target Forge | Exact tumor/normal single-target and two-sensor gate discovery | Working first discovery slice; biological validity depends entirely on supplied evidence | Extend with real adapters and independent validation sets |
| QSA gate receipt | Exact marked/unmarked `SymmetryState` evolution with analytic control | Working structural computation; no speed advantage claimed in version 1 | Retain as optional, fail-closed validation boundary |
| Target Forge web API | Authenticated bounded run creation and retrieval | Working server interface | Connect to website account/session layer |

## First Connected Vertical Slice

```text
Evidence sources
  -> EvidenceFabric validation and provenance
  -> TumorResearchModel
  -> exact sample/target bitsets
  -> single, AND, OR, AND NOT gates
  -> tumor coverage plus normal-tissue exclusion
  -> hard eligibility rules and Pareto front
  -> classical control and optional certified QSA class evolution
  -> formal hypotheses, falsification criteria, JSON/HTML report
  -> CLI, authenticated web API, website portal
```

No computational result in this chain is clinical advice, proof of safety, proof of efficacy, or proof of a cure. A candidate remains a research hypothesis until independently measured and experimentally tested.

## Next Evidence Adapters

1. Surfaceome and spatial-proteomic observations with stable HGNC, NCBI Gene, UniProt, sample, assay, and normal-tissue identifiers.
2. Single-cell tumor and normal expression matrices with patient-aware train/validation separation.
3. Functional dependency screens kept distinct from expression and computational dependency transfer.
4. Immunopeptidomic evidence kept distinct from predicted binding and transcript expression.
5. Protease activity and substrate-cleavage evidence with blood and normal-organ counter-screens.

Each adapter must emit the same evidence schema, preserve source versions and hashes, record transformation history, and fail on unmapped identifiers. It must not hard-code a published target as the expected answer.

## Expansion Order

1. Real-data importers and validation cohorts for Target Forge.
2. Protease-activated targeting with direct activity measurements and negative selection.
3. Dependency and synthetic-lethal hypotheses with domain-shift receipts.
4. Neoantigen and antigen-presentation hypotheses with measured/predicted classes separated.
5. Resistance and escape models tied to perturbation evidence.
6. Sequence and structure design only after target biology passes the evidence and safety gates.

Higher-order gates and larger searches stay bounded until their exact classical cost, QSA representation certificate, and independent control are all inspectable.
