"""
Stage 1 - Milestone 1: Repository Cleanup & Archival
Archives intermediate implementation artifacts while preserving
final certification documents in their natural locations.
"""
import glob
import io
import os
import shutil
import sys

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = os.path.abspath(".")
ARTIFACTS_DIR = os.environ.get("ARTIFACTS_DIR", os.path.join(BASE, "artifacts"))
ARCHIVE_ROOT = os.path.join(BASE, "archive", "implementation-history")

ARCHIVE_SCRIPTS = os.path.join(ARCHIVE_ROOT, "scripts")
ARCHIVE_PLANS   = os.path.join(ARCHIVE_ROOT, "plans")
ARCHIVE_REPORTS = os.path.join(ARCHIVE_ROOT, "reports")
ARCHIVE_QA      = os.path.join(ARCHIVE_ROOT, "qa")
ARCHIVE_CERT    = os.path.join(ARCHIVE_ROOT, "certification")

# Final certification docs - keep accessible, do NOT archive
KEEP_DOCS = {
    "01_ARCHITECTURE_COMPLIANCE_REPORT.md",
    "02_PRD_COMPLIANCE_MATRIX.md",
    "03_SOLUTION_OVERVIEW_COMPLIANCE_REPORT.md",
    "04_FEATURE_COMPLETENESS_MATRIX.md",
    "API_COMPLIANCE_REPORT.md",
    "06_DATABASE_COMPLIANCE_REPORT.md",
    "07_AI_WORKFLOW_VALIDATION_REPORT.md",
    "08_SECURITY_COMPLIANCE_REPORT.md",
    "09_OBSERVABILITY_COMPLIANCE_REPORT.md",
    "10_PRODUCTION_READINESS_REPORT.md",
    "11_GAP_ANALYSIS_REPORT.md",
    "12_FINAL_ENTERPRISE_CERTIFICATION_REPORT.md",
    "STAGE_1_RELEASE_PACKAGING_IMPLEMENTATION_PLAN.md",
}


def makedirs():
    for d in [ARCHIVE_SCRIPTS, ARCHIVE_PLANS, ARCHIVE_REPORTS, ARCHIVE_QA, ARCHIVE_CERT]:
        os.makedirs(d, exist_ok=True)
    print("[1/7] Archive directories created.")


def archive_scripts():
    patterns = [
        os.path.join(ARTIFACTS_DIR, "impl_m*.py"),
        os.path.join(ARTIFACTS_DIR, "impl_stage*.py"),
    ]
    moved = 0
    for pat in patterns:
        for fpath in glob.glob(pat):
            dest = os.path.join(ARCHIVE_SCRIPTS, os.path.basename(fpath))
            shutil.move(fpath, dest)
            moved += 1
    print(f"[2/7] Archived {moved} implementation scripts -> archive/scripts/")


def archive_plans():
    pattern = os.path.join(ARTIFACTS_DIR, "PHASE_*_IMPLEMENTATION_PLAN.md")
    moved = 0
    for fpath in glob.glob(pattern):
        dest = os.path.join(ARCHIVE_PLANS, os.path.basename(fpath))
        shutil.move(fpath, dest)
        moved += 1
    print(f"[3/7] Archived {moved} implementation plans -> archive/plans/")


def archive_reports():
    patterns = [
        os.path.join(ARTIFACTS_DIR, "PHASE_*_IMPLEMENTATION_REPORT.md"),
        os.path.join(ARTIFACTS_DIR, "bug-fix-summary.md"),
        os.path.join(ARTIFACTS_DIR, "cross-phase-integration-report.md"),
        os.path.join(ARTIFACTS_DIR, "e2e-validation-report.md"),
        os.path.join(ARTIFACTS_DIR, "final-system-certification-report.md"),
        os.path.join(ARTIFACTS_DIR, "FINAL_WAVE_*_VERIFICATION_REPORT.md"),
        os.path.join(ARTIFACTS_DIR, "performance-validation-report.md"),
        os.path.join(ARTIFACTS_DIR, "PHASES_*_RELEASE_SUMMARY.md"),
        os.path.join(ARTIFACTS_DIR, "security-validation-report.md"),
        os.path.join(ARTIFACTS_DIR, "wave-3-final-qa-report.md"),
    ]
    moved = 0
    for pat in patterns:
        for fpath in glob.glob(pat):
            dest = os.path.join(ARCHIVE_REPORTS, os.path.basename(fpath))
            shutil.move(fpath, dest)
            moved += 1
    print(f"[4/7] Archived {moved} phase reports -> archive/reports/")


def archive_wave_qa():
    patterns = [
        os.path.join(ARTIFACTS_DIR, "wave-4-final-qa-report.md"),
        os.path.join(ARTIFACTS_DIR, "wave-5-final-qa-report.md"),
    ]
    moved = 0
    for pat in patterns:
        for fpath in glob.glob(pat):
            dest = os.path.join(ARCHIVE_QA, os.path.basename(fpath))
            shutil.move(fpath, dest)
            moved += 1
    print(f"[5/7] Archived {moved} QA reports -> archive/qa/")


def create_archive_readme():
    content = """# RAGuard AI - Engineering History Archive

This directory preserves the complete engineering history of the RAGuard AI
platform (Phases 1-24, Waves 1-5, Stage 1).

## Structure

- scripts/       : All impl_m*.py and impl_stage*.py scripts
- plans/         : All PHASE_*_IMPLEMENTATION_PLAN.md documents
- reports/       : All phase implementation reports and bug-fix logs
- qa/            : Wave QA reports and validation reports
- certification/ : Intermediate certification artifacts

## Purpose

These artifacts are preserved for full engineering traceability.
They are NOT part of the active codebase, but are available for
audit, reference, and compliance verification.

## Official Release Documentation

Final certification documents remain in:
  docs/certification/  (root-accessible)
"""
    readme_path = os.path.join(ARCHIVE_ROOT, "readme.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("[6/7] Archive README written.")


def ensure_gitignore():
    gitignore_path = os.path.join(BASE, ".gitignore")
    existing = ""
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            existing = f.read()

    additions = []
    for entry in ["__pycache__/", "*.pyc", "*.pyo", ".env", ".pytest_cache/",
                  "*.egg-info/", "dist/", "build/", ".mypy_cache/", ".ruff_cache/",
                  "*.log", "htmlcov/", ".coverage"]:
        if entry not in existing:
            additions.append(entry)

    if additions:
        with open(gitignore_path, "a") as f:
            f.write("\n# Stage 1 additions\n")
            for entry in additions:
                f.write(f"{entry}\n")
        print(f"[+] .gitignore updated with {len(additions)} new entries.")
    else:
        print("[+] .gitignore already complete.")


def ensure_docs_dirs():
    for d in ["docs", "docs/assets", "docs/portfolio", "docs/certification"]:
        os.makedirs(os.path.join(BASE, d), exist_ok=True)
    print("[7/7] docs/ directory structure ensured.")


def copy_certification_to_docs():
    for fname in KEEP_DOCS:
        src = os.path.join(ARTIFACTS_DIR, fname)
        if os.path.exists(src):
            dst = os.path.join(BASE, "docs", "certification", fname)
            shutil.copy2(src, dst)
    print("[+] Final certification docs copied to docs/certification/")


if __name__ == "__main__":
    print("=" * 60)
    print("Stage 1 - Milestone 1: Repository Cleanup & Archival")
    print("=" * 60)
    makedirs()
    archive_scripts()
    archive_plans()
    archive_reports()
    archive_wave_qa()
    create_archive_readme()
    ensure_gitignore()
    ensure_docs_dirs()
    copy_certification_to_docs()
    print()
    print("[DONE] Milestone 1 Complete.")
