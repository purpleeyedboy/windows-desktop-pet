# Windows source-validation Task 1 report

## Scope

Added the read-only Windows GitHub Actions source-validation workflow and its
repository contract test. The workflow is limited to pull requests targeting
`codex/desktop-pet-6-frame-alpha` and manual dispatch. It uses the approved
pinned official actions, Python 3.11, project dev-test dependencies, a Pillow
major-version 11 assertion, and the complete `python -m pytest -q` suite.

No hosted workflow was triggered by this task. No executable, package, upload,
release, or visual asset was created or modified.

## TDD evidence

1. `python -m pytest -q tests/test_windows_source_validation_workflow.py`
   before the workflow existed: exit 1; `1 failed in 0.02s`. The assertion
   explicitly reported `Windows source-validation workflow is missing`.
2. The first workflow draft exposed a command-quoting defect in the contract
   test: the same command exited 1 because the Pillow assertion contained
   literal backslash escapes. The command was rewritten with PowerShell-safe
   single quotes around the Python expression.
3. `python -m pytest -q tests/test_windows_source_validation_workflow.py`
   after that correction: exit 0; `1 passed in 0.01s`.
4. The contract was strengthened to require exactly the approved trigger and
   permission blocks and exactly two action uses. The workflow was temporarily
   removed before this strengthened test was run. The same focused command
   exited 1; `1 failed in 0.02s`, again specifically because the workflow was
   missing.
5. After restoring the minimal workflow, the same focused command exited 0;
   `1 passed in 0.01s`.

## Regression and static checks

- An initial `python -m pytest -q --ignore=tests/test_window.py` attempt lost
  its tool-session result after partial progress output, so it was not treated
  as evidence.
- The completed rerun of
  `python -m pytest -q --ignore=tests/test_window.py` exited 0:
  `298 passed, 3 skipped, 1107 warnings in 49.65s`. The warnings are existing
  Pillow 14 deprecation warnings for `Image.Image.getdata`; this task made no
  source changes in those areas.
- `git diff --check` after intent-to-add of all four scoped files exited 0 with
  no output.

## Limits

The future hosted Windows job will provide automated source evidence only. It
does not approve motion naturalness, neutral/action joins, four-size
performance, multi-monitor behavior, or R5. R5 remains blocked.

## Hosted RED follow-up and local fix

GitHub Actions run `33344898515`, job `99347046952`, completed on Windows
Server 2025 with Python 3.11.9 and Pillow 11.3.0. Checkout, Python setup,
project dev-dependency installation, and the Pillow verification passed. The
full `python -m pytest -q` command then failed during collection because the
remote-base `tests/test_interpolate_action.py` imports NumPy while the workflow
installed only `.[dev]`.

The remote merge tree already contains `requirements-assets.txt` with the
asset-test dependencies. The local continuation checkout intentionally does
not hydrate that unchanged remote file, so it was neither created nor edited.

TDD for the workflow-only correction:

1. The contract test was first strengthened to require
   `python -m pip install ".[dev]" -r requirements-assets.txt`.
2. `python -m pytest -q tests/test_windows_source_validation_workflow.py`
   before the workflow edit exited 1: `1 failed in 0.02s`. The only failed
   assertion was the missing `requirements-assets.txt` install argument.
3. The workflow dependency command was changed to
   `python -m pip install ".[dev]" -r requirements-assets.txt`.
4. The same focused command then exited 0: `1 passed in 0.01s`.
5. `git diff --check` after the three scoped updates exited 0 with no output.

This preserves the complete suite command and does not skip or ignore
`tests/test_interpolate_action.py`. R5 remains blocked.
