# OncoForge

OncoForge is an interactive cancer-systems simulator for conceptual research, hypothesis exploration, and education. It models cancer cells as abnormal signal generators and proteins, enzymes, immune mechanisms, and synthetic agents as signal readers with action mechanisms.

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
- Tkinter for the GUI. *duh*

  *More to follow*
