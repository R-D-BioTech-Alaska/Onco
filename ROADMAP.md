# OncoForge Roadmap

This roadmap separates working software from future research. Items here are not implemented unless noted elsewhere in the README or changelog.

## Near-Term Engineering

- Build the logged-in website workspace against `website/ONCOFORGE_VNEXT_WEBSITE_PROMPT.md` and the authenticated Target Forge API.
- Add account-owned project/run persistence and a bounded production job queue in the website service.
- Add strict surfaceome, single-cell tumor/normal, dependency, immunopeptidomic, and protease-activity evidence adapters.
- Add independent discovery/validation cohort handling and dataset-domain receipts.
- Add a public schema/version endpoint and signed report download from the production service.
- Add portal run comparison without collapsing safety, coverage, evidence, and uncertainty into one score.
- Add a remission-test comparison dashboard that ranks cocktails by durable clearance, healthy preservation, and recovery quality.
- Expand the new parameter sweep runner with multi-parameter grid sweeps and GUI controls.
- Add a richer custom cancer-profile editor with validation, import/export, and profile diffing.
- Add profile-specific comparison dashboards that contrast starter cocktails, low-toxicity cocktails, and broad max-force cocktails.
- Add marker evolution charts for initial markers, survivor markers, reduced markers, and escape-enriched markers.
- Add saved research-loop manifests that can replay every bounded experiment deterministically.
- Add Monte Carlo summary reports with confidence-style bands across repeated seeds and cure-pathway classifications.
- Extend machine-readable schemas to saved experiments, cancer presets, agents, and cocktails.
- Add a custom cancer-preset designer parallel to the custom agent designer.
- Add richer GUI charts for tumor burden, immune activation, healthy damage, and clone counts.
- Add CSV/JSON export for signal matrices and pathway coverage.

## Model Clarity

- Add uncertainty text for every bundled cancer profile marker and vulnerability assumption.
- Add per-rule uncertainty notes and parameter ranges.
- Add separate rule modules for DNA repair, apoptosis, immune recognition, microenvironment, and stress-death behavior.
- Add lineage trees for clone emergence, escape events, and dominant clone replacement.
- Deepen the current plain-English interpretation engine into full "why did this cocktail work/fail?" explanations based on target matches, missed signals, escape pressure, and healthy-cell risk.

## Scientific Research Needed

- Calibrate qualitative parameters against published experimental systems only where appropriate.
- Separate tissue-specific assumptions from generic carcinoma assumptions.
- Improve immune abstractions for macrophages, T cells, NK cells, complement, checkpoint signaling, and inflammation feedback.
- Improve microenvironment modeling for oxygen/glucose gradients, acidity, matrix barriers, and vascular support.
- Treat speculative synthetic gates as design hypotheses until external evidence exists.

## Possible Architecture Extensions

- Role-based collaborative projects, bounded job queues, and private report libraries in the account portal.
- Optional QSA/BrainQ/Onco adapters that stay out of the core package unless explicitly installed.
- Plugin-style rule registration for future biological mechanisms.
- Batch experiment manifests for reproducible scenario libraries.
- Optional local AI structured-output schema for suggested simulation experiments, with strict validation before execution.
- Exportable pathway graphs for external visualization.
- Optional plotting dependency with graceful fallback to standard-library outputs.
