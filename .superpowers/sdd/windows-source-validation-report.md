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

## Task 2 hosted-failure remediation

### Hosted platform RED

GitHub Actions run `33345159857`, job `99347761338`, ran on Windows Server
2025 with Python 3.11.9 and Pillow 11.3.0. Dependency installation and the
Pillow-major gate passed; the complete `python -m pytest -q` run then reported
`24 failed, 459 passed`. The known platform failures were CRLF conversion of
the four fixed-hash text sources, cross-drive `relpath` in the interpolation
test helper, and fresh neutral-eye PNG encoding bytes differing despite equal
decoded pixels.

### TDD evidence

1. Before `.gitattributes` existed,
   `python -m pytest -q tests/test_repository_attributes.py` exited 1 with
   `1 failed`; the expected assertion was `repository .gitattributes is
   missing`.
2. Added only the four exact-path `text eol=lf` rules. The same command then
   exited 0 with `1 passed`.
3. A mocked cross-drive `os.path.relpath` ValueError first made
   `python -m pytest -q tests/test_interpolate_action.py::test_relative_alias_uses_absolute_target_when_paths_have_different_drives`
   exit 1 with that ValueError. After the test-helper-only fallback to the
   resolved absolute target, the restored remote test module passed:
   `9 passed`.
4. `test_fresh_outputs_match_approved_mode_size_and_raw_pixels` is the hard
   gate for each fresh output PNG's mode, size, and decoded `tobytes()` against
   its committed approved counterpart. The focused regression re-encodes a
   temporary same-pixel PNG with distinct bytes, proves the unchanged
   `ValidatedNeutralEyeSnapshot.load` fixed-SHA loader rejects it, then copies
   only committed approved PNG bytes plus committed `authoring.json` into the
   temporary integration fixture after that pixel gate. Generator-content
   tests continue to use the fresh build. The two-build byte test remains and
   is explicitly scoped to same-host/same-codec determinism.

### Verification

- `python -m pytest -q tests/test_neutral_eye_layers.py`: `34 passed`.
- `python -m pytest -q tests/test_neutral_eye_compositor.py`: `36 passed`.
- `python -m pytest -q tests/test_repository_attributes.py tests/test_windows_source_validation_workflow.py`:
  `2 passed`.
- `python -m pytest -q tests/test_neutral_eye_preview.py`: `27 passed`.
- `python -m pytest -q tests/test_animation.py tests/test_assets.py tests/test_eye_follow.py tests/test_eye_runtime.py tests/test_layered_window.py tests/test_main.py tests/test_model.py`:
  `202 passed, 3 skipped`.
- The applicable local non-Tk total is `310 passed, 3 skipped`; Tk window tests
  remain excluded because this headless checkout has no display server.
- `git diff --check`: exit 0 with no output.

### Scope and remaining hosted unknowns

No PNG, GIF, font binary, approved metadata, production fixed-SHA loader, or
product interpolation code was changed. Local validation temporarily hydrated
the byte-for-byte remote `tools/interpolate_action.py`, `tools/animation_qa.py`,
and `requirements-assets.txt` only because this continuation checkout omitted
them; they are not staged or committed. The next hosted Windows run is still
needed to confirm Windows checkout applies the new exact LF attributes and to
observe the complete suite there. R5 remains blocked.

### Task 2 fixture-metadata follow-up

An independent review found that the normalized test fixture copied committed
`authoring.json` but returned the pre-normalization fresh metadata object. On
Windows that object can contain fresh PNG hashes while the temporary directory
contains approved bytes.

1. The same-pixel/different-byte regression was extended first to require the
   normalization helper to return metadata equal to parsing the written
   temporary `authoring.json`. Before the helper change,
   `python -m pytest -q tests/test_neutral_eye_layers.py::test_same_pixel_different_png_bytes_require_test_only_normalization`
   exited 1: the helper returned `None` instead of the parsed normalized
   metadata.
2. The test-only helper now parses and returns the `authoring.json` it wrote,
   and `normalized_built` returns that normalized object rather than the fresh
   builder metadata. The focused regression then passed (`1 passed`), as did
   `python -m pytest -q tests/test_neutral_eye_layers.py` (`34 passed`) and
   `python -m pytest -q tests/test_neutral_eye_compositor.py` (`36 passed`).
3. `git diff --check` and `git diff --cached --check` both exited 0 with no
   output. No production code or visual asset changed.

### Hosted Windows GREEN

GitHub Actions run `33347015369`, job `99352958003`, completed successfully on
Windows Server 2025 with Pillow 11.3.0. Every workflow step succeeded and the
unmodified full command `python -m pytest -q` reported `487 passed in
256.96s`.

This is the hosted confirmation that the Windows raw-pixel gate passed: freshly
built neutral-eye PNGs decoded to the approved mode, size, and raw pixel bytes
before the test-only strict-loader/evidence normalization path was used. The
PR contains the expected nine scoped files. It remains open and unmerged;
merge authorization has not been granted. R5 remains blocked.

### Task 2 metadata-semantic normalization follow-up

Independent whole-PR review found that copying the full approved
`authoring.json` after only comparing PNG raw pixels could hide a fresh
non-SHA metadata change such as a movement anchor.

1. A focused regression first changed only the fresh temporary left-eye
   `movement_anchor`, leaving all PNG pixels unchanged. Before the fix,
   `PYTHONPATH=/root/.local/lib/python3.12/site-packages python -m pytest -q tests/test_neutral_eye_layers.py::test_normalization_rejects_fresh_non_sha_metadata_drift`
   exited 1 with `Failed: DID NOT RAISE <class 'ValueError'>`.
2. Normalization now reads both fresh and approved metadata, changes only the
   five named `outputs.*.sha256` values in a comparison copy, and rejects any
   remaining mismatch before copying approved PNG or metadata bytes. It returns
   the parsed metadata from the written temporary file, so fixture metadata
   remains directory-consistent.
3. The focused regression and same-pixel regression passed (`2 passed`). The
   complete neutral-eye layers coverage passed in two non-overlapping groups
   (`17 passed` and `18 passed`); compositor coverage passed (`36 passed`).
   `git diff --check` exited 0 with no output. Production loader, workflow,
   and visual assets were unchanged.
