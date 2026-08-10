# OncoForge 0.4.0 Release Notes

This build focuses on making OncoForge easier to understand while making it more useful for advanced exploration.

## Major additions

- Adaptive dosing controller with tapering, minimal-residual watch, remission confirmation, remission surveillance, and delayed post-clearance shutoff.
- Post-clearance recovery behavior for inflammation, immune pressure, acidity, and stromal barrier.
- Cure-pathway/remission assessment with plain-English classifications.
- Dosing & Cure Test GUI tab with adaptive controls and live interpretation.
- Parameter Sweep GUI tab and `run_oncoforge.py sweep` CLI command.
- `run_oncoforge.py remission-test` command for clearance plus post-clearance watch experiments.
- Expanded HTML/JSON reports with dosing state, cure-pathway assessment, and readable interpretation.
- `USER_GUIDE.md` for step-by-step operation.
- New tests covering adaptive dosing, auto-shutoff, cure-pathway reports, remission CLI, and sweep CLI.

## 0.4.1 controller update

Auto-shutoff now waits for a configurable zero-cancer confirmation window instead of turning off immediately when cancer first reaches zero. The controller tracks zero-cancer steps, recurrence after clearance, max cancer after clearance, and rebound step.

## Validation commands

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python run_oncoforge.py compare --steps 25 --healthy 100 --cancer 40 --seeds 1729,1730 --limit 5
python run_oncoforge.py remission-test --steps 30 --healthy 80 --cancer 10 --export outputs/reports/remission_validation.json
python run_oncoforge.py sweep --parameter treatment --values 0.5,1.0 --steps 10 --healthy 40 --cancer 10 --adaptive-dosing --auto-shutoff --limit 5
```

Validation result: all tests passed (`Ran 23 tests ... OK`).

## Scientific caution

The cure-pathway assessment is a simulator heuristic. It does not indicate a clinical cure. It is designed to help reason about cancer clearance, recurrence risk inside the model, healthy-cell preservation, and recovery after treatment pressure stops.
