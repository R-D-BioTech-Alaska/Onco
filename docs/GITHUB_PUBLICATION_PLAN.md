# GitHub Publication Plan

This project folder is not currently a Git repository. To publish it cleanly, initialize or copy it into the target GitHub repository only after tests pass from this folder:

```text
C:\Users\inser\OneDrive\Desktop\OncoForge\OncoForge_improved\OncoForge
```

## Target Repository

Recommended target:

```text
https://github.com/R-D-BioTech-Alaska/Onco
```

If OncoForge receives its own repository later, keep the same structure and point the lab page to the new source repository.

## Repository Contents

Required public contents:

```text
oncoforge/
tests/
docs/
.github/workflows/oncoforge-ci.yml
README.md
USER_GUIDE.md
CHANGELOG.md
ROADMAP.md
requirements.txt
pyproject.toml
run_oncoforge.py
run_oncoforge.bat
```

Do not publish local caches, generated reports, OneDrive lock files, or `__pycache__` folders.

## First Commit Checklist

Run:

```powershell
python -m compileall -q .
python -m unittest discover -s tests -v
python run_oncoforge.py list-profiles
python run_oncoforge.py profile-info --profile melanoma_cutaneous
python run_oncoforge.py recommend-cocktail --profile melanoma_cutaneous
python run_oncoforge.py qsa-plan --profile melanoma_cutaneous --json outputs/reports/qsa_plan.json
```

Then inspect:

```powershell
git status --short
git diff --check
```

Commit only intentional source, docs, tests, and workflow files.

## Suggested Git Commands

From the project folder:

```powershell
git init
git branch -M main
git remote add origin https://github.com/R-D-BioTech-Alaska/Onco.git
git add .
git status --short
git commit -m "Prepare OncoForge portal and QSA strategy layer"
git push -u origin main
```

If the remote already has history, clone it fresh, copy this project into the clone, review the diff, then commit. Do not force-push over the public repository unless that is intentionally approved.

## GitHub Settings

Recommended:

- Branch protection on `main`.
- Require CI before merge.
- Require pull request review for public releases.
- Add `SECURITY.md` before accepting outside reports.
- Add release tags such as `v0.5.1`.
- Keep GitHub Actions on Python 3.10, 3.11, and 3.12.

## Release Notes Template

```text
OncoForge version:
Date:

Added:
- ...

Changed:
- ...

Validation:
- compileall passed
- unittest passed
- CLI smoke commands passed

Boundary:
OncoForge is a conceptual research simulator only. It is not medical advice,
not a clinical prediction tool, and not a treatment recommendation system.
```

