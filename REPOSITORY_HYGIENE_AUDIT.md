# Repository Hygiene Audit

## Overview
This audit inspects the repository for files that should not be tracked by source control under enterprise guidelines. This includes caches, temporary files, build outputs, environment-specific configurations, generated reports, and IDE configurations.

## Audit Findings

### 1. Temporary & Generated Files
- **Generated Reports:** `ruff_output.json`, `docs/Archive/retrieval_results.json` were found checked into Git. These are volatile generated test/lint outputs that should be excluded.
- **Generated Documentation Copies / Tracker Snapshots:** The `docs/Archive` directory correctly holds historical design snapshots, but temporary operational exports should be ignored.

### 2. Local Environments & Caches
- **Local Dev Configs:** `docker-compose.override.yml` is tracked in Git, violating the principle that local infrastructure overrides should be strictly local and untracked.
- **Python Virtual Environments:** `venv` / `.venv` are successfully ignored and not tracked.
- **Node Modules:** `node_modules` is successfully ignored and not tracked.
- **Language Caches:** `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, and `__pycache__` are properly ignored by current `.gitignore` but coverage can be expanded to catch all edge cases.

### 3. IDE & OS Files
- OS files like `.DS_Store` and IDE files like `.vscode/` and `.idea/` are mostly ignored, but `.gitignore` coverage can be hardened.

### 4. Uploaded Artifacts & AI Scratch Files
- **Gemini Scratch Files:** `.gemini/` is ignored by `.gitignore`.
- **Test Datasets:** `qa_dataset/` contains test fixtures. These are intentional static fixtures rather than temporary uploads, but temporary upload locations (`temp/`, `scratch/`) need firmer exclusion rules to prevent accidental staging.

## Recommendation
Transition the identified operational/generated files to `.gitignore` and untrack them from the repository using `git rm --cached`.
