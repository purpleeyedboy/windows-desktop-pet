# Windows Source Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal GitHub-hosted Windows source-validation gate that runs the existing project with Python 3.11 and Pillow 11, without building or publishing an executable.

**Architecture:** One read-only GitHub Actions workflow runs on pull requests to `codex/desktop-pet-6-frame-alpha` and by manual dispatch. A repository test locks the workflow's security, platform, dependency, and command contract. The workflow runs the complete existing pytest suite on a GitHub-hosted Windows VM so Windows mutex, real Tk, and layered-window tests are no longer silently skipped.

**Tech Stack:** GitHub Actions, `windows-latest`, Python 3.11, Pillow 11, pytest 8.

## Global Constraints

- Keep R5 blocked.
- Do not generate, edit, recolor, crop, or replace visual assets.
- Do not modify anything under `assets/keyframes/`, `assets/rig/v1/source/`, or `qa/`.
- Do not build, upload, package, release, or modify an EXE.
- Do not begin head directions, blink, head tilt, or other runtime features.
- Use only official GitHub Actions pinned to full commit SHAs.
- Grant only `contents: read`; persist no checkout credentials and use no repository secrets.
- Use Python `3.11` and verify the installed Pillow major version is exactly `11`.
- Run the complete `python -m pytest -q` suite on `windows-latest`.
- A passing hosted Windows job is automated source evidence only. It does not approve motion naturalness, neutral/action joins, four-size performance, multi-monitor behavior, or R5.

---

### Task 1: Windows source-validation workflow

**Files:**

- Create: `.github/workflows/windows-source-validation.yml`
- Create: `tests/test_windows_source_validation_workflow.py`
- Create: `.superpowers/sdd/windows-source-validation-report.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**

- Consumes: the existing `pyproject.toml` package metadata and complete pytest suite.
- Produces: a pull-request-triggered Windows source-validation job named `windows-source-tests`.

**Acceptance:**

- [ ] Write a repository test that fails because the workflow does not yet exist.
- [ ] Verify the RED failure is specifically the missing workflow.
- [ ] Create the smallest workflow satisfying every Global Constraint.
- [ ] Verify the focused workflow-contract test passes.
- [ ] Run the applicable local non-Tk regression suite and `git diff --check`.
- [ ] Commit the implementation and write exact RED/GREEN evidence to the report.
- [ ] Obtain independent spec and code-quality approval.

### Task 2: Remote Windows execution and safe integration

**Files:**

- Modify if evidence requires it: `.github/workflows/windows-source-validation.yml`
- Modify if evidence requires it: `tests/test_windows_source_validation_workflow.py`
- Create if checkout evidence requires it: `.gitattributes`
- Create if checkout evidence requires it: `tests/test_repository_byte_hash_attributes.py`
- Modify if Windows-only test infrastructure fails: `tests/test_interpolate_action.py`
- Modify if cross-platform authoring bytes differ: `tests/test_neutral_eye_layers.py`
- Modify: `.superpowers/sdd/windows-source-validation-report.md`
- Modify: `.superpowers/sdd/progress.md`

**Acceptance:**

- [ ] Publish Task 1 to a dedicated branch rooted at the current remote head without replaying local hydration commits.
- [ ] Open a pull request targeting `codex/desktop-pet-6-frame-alpha`.
- [ ] Inspect the actual pull-request workflow run, jobs, steps, and failure logs when applicable.
- [ ] If the job fails, reproduce the smallest responsible layer, add a RED regression or contract check when practical, fix, re-review, and rerun.
- [ ] Preserve LF checkout bytes for only the text assets whose approved SHA values are part of the test contract.
- [ ] Keep cross-drive path aliases portable on Windows without changing product interpolation code.
- [ ] Separate cross-platform raw-pixel identity, same-host PNG byte determinism, and published-asset fixed-SHA integrity without weakening the production loader.
- [ ] Require the hosted Windows job to pass before integration.
- [ ] Verify the PR diff contains only the plan, workflow, workflow test, evidence-led test infrastructure fixes, report, and progress ledger.
- [ ] Merge only after independent final review and re-reading the remote head.
- [ ] Confirm the default branch moved to the reviewed commit and R5 remains blocked.

## Explicitly deferred

- Human visual approval of eye motion and neutral/action joins.
- Four-size callback p50/p95/max, update-rate, CPU, and working-set measurement.
- Physical multi-monitor drag and resize checks.
- Packaging, release archives, stable delivery replacement, and EXE work.
