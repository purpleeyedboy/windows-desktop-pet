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
