# Task 2: Eye-follow candidate EXE

## RED

Created the two candidate packaging contract-test files before the implementation
files, then ran:

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
FFFF
4 failed in 0.05s
```

Each failure was the intended missing-file assertion for the candidate spec,
PowerShell build script, archive verifier, and Windows workflow.

## Implementation

- Added a separate one-file windowed PyInstaller spec for
  `桌面宠物-眼球跟随测试版.exe`, with isolated candidate paths, stable runtime
  resources, only the six neutral-eye runtime files, and `numpy`/`cv2` excluded.
- Added a PowerShell build gate that runs the stable validators, full tests by
  default, safely removes only the two candidate output paths, checks the exact
  EXE count/name, verifies the archive, enforces 50 MiB, and prints SHA-256.
- Added an archive verifier that byte-compares every packaged stable resource
  and each runtime neutral-eye file; it rejects rig-source, QA, and GIF members
  and prints `neutral-eye 6` on success.
- Added a pinned, read-only Windows PR/manual workflow that runs the complete
  test command before building and uploads only the candidate EXE for seven days.

## Verification

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
5 passed in 0.05s

python -m pytest -q tests/test_assets.py tests/test_main.py tests/test_neutral_eye_compositor.py
52 passed, 1 skipped in 4.14s

python -m pytest -q tests/test_animation.py tests/test_model.py tests/test_eye_follow.py tests/test_eye_runtime.py tests/test_repository_attributes.py tests/test_windows_source_validation_workflow.py
188 passed in 1.83s

git diff --check
(no output)
```

The archive contract test creates a minimal PyInstaller CArchive and proves that
the verifier accepts matching bytes, rejects a modified resource, and rejects a
QA GIF archive path.

## Self-review

- The candidate build never invokes, cleans, or names the stable build spec,
  script, or EXE.
- The workflow has only the three required pinned Actions uses, read-only
  contents permission, no secrets, and no publishing action.
- The build script checks native-command exit codes explicitly, so validators,
  tests, packaging, and archive verification cannot silently continue after a
  failure.

## Concerns

This intentionally sparse local checkout omits the unchanged stable files that
the candidate spec consumes (`run_desktop_pet.py`, `THIRD_PARTY_NOTICES.txt`,
the stable validators, and stable bubble/font/dialogue assets). Therefore a
local candidate EXE build and the complete unmodified suite cannot run here.
The remote PR checkout contains those files; the new Windows workflow performs
the full suite, package, byte verification, size gate, and SHA-256 recording.
`tests/test_interpolate_action.py` is likewise not locally collectible because
its unchanged remote-only `tools.interpolate_action` module is absent.

## Commit

Original implementation commit: 0774f8906e857dd525e88da5694f894a7bb0556a.
Original report-only follow-up: 9ca2059.

## Review fix RED

Added review regressions before changing the candidate implementation, then ran:

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
FFF..FF.                                                                 [100%]
5 failed, 3 passed in 0.13s
```

The five intended failures covered the missing Pillow Tk hidden import, UTF-8
BOM, Tcl/Tk environment setup and reparse-point cleanup contract, Windows-style
backslash CArchive members, and controlled source-read errors.

## Review fixes

- The archive verifier now builds a normalized-forward-slash-to-raw-member map,
  rejects collisions such as slash and backslash spellings of the same member,
  validates normalized names, and extracts with the original raw name.
- Source `read_bytes()` failures are wrapped in `VerificationError` with the
  affected archive member in the controlled message.
- The candidate spec preserves `hiddenimports=["PIL._tkinter_finder"]`.
- The candidate script now has a UTF-8 BOM, resolves `sys.base_prefix` from the
  selected Python, checks that command's exit code, and sets `TCL_LIBRARY` and
  `TK_LIBRARY` before validators, tests, and PyInstaller.
- Asset validation uses the exact stable command and six-frame direct-layout
  report arguments.
- Candidate cleanup checks `FileAttributes.ReparsePoint` before recursion,
  removes the link itself without `-Recurse`, and recurses only into ordinary
  directories.
- Contract tests now require the exact six eye names/mapping, excludes, hidden
  import, validator arguments, BOM, Tcl/Tk ordering, and cleanup branching.

## Review fix GREEN and regression evidence

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
8 passed in 0.06s

python -m pytest -q tests/test_assets.py tests/test_main.py tests/test_neutral_eye_compositor.py
52 passed, 1 skipped in 3.77s

python -m pytest -q tests/test_animation.py tests/test_model.py tests/test_eye_follow.py tests/test_eye_runtime.py tests/test_repository_attributes.py tests/test_windows_source_validation_workflow.py
188 passed in 1.48s

python -m py_compile tools/verify_eye_follow_candidate_archive.py tests/test_eye_follow_candidate_packaging.py
(no output)

git diff --check
(no output)
```

The Windows-member regression uses a real PyInstaller CArchive with backslash
member names. It proves byte verification succeeds through raw-name extraction,
then proves a second archive containing both separator spellings is rejected as
a normalized-path collision.

## Final reviewed state

- Review-fix implementation commit:
  `9b1ac59caa5287846cd9a88e13488123958f1080`.
- Final reviewed implementation head:
  `9b1ac59caa5287846cd9a88e13488123958f1080`.
- The following report-only commit records this evidence; its SHA is returned in
  the task handoff. It contains no implementation or asset changes.
- The sparse-checkout concerns above remain unchanged. No visual assets,
  head/blink/tilt behavior, stable build files, or R5 status were changed.

## Final-review nested-junction cleanup fix

### RED

Added the static recursive-deletion guard and Windows-only real nested-junction
regression before changing the candidate script, then ran:

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
.FFs.....
2 failed, 6 passed, 1 skipped in 0.10s
```

The two expected Linux failures proved that `-CleanupOnly` was absent and that
ordinary candidate directories still used `Remove-Item ... -Recurse`. The real
junction test was collected and skipped because it requires Windows; on the
hosted Windows full suite it creates a nested directory junction to an external
sentinel, invokes cleanup, and requires the sentinel to survive.

### Implementation

- Added the narrowly scoped `-CleanupOnly` entrypoint; the default validator,
  test, PyInstaller, archive, size, and hash behavior remains unchanged.
- Replaced recursive `Remove-Item` with child-by-child cleanup. Every immediate
  child is re-inspected before descent, directory and file reparse points use
  non-recursive .NET delete calls, recursion occurs only for ordinary
  directories, and an ordinary directory is deleted only after it is empty.
- Strengthened the static contract to reject any `Remove-Item` command line
  containing `-Recurse`, regardless of parameter ordering.
- Added a Windows-only regression using `cmd.exe mklink /J` with a real nested
  junction and external sentinel. It runs under the existing workflow's full,
  unmodified `python -m pytest -q` command and skips on non-Windows.

### GREEN and regression evidence

Verified the exact implementation commit
`df82b3157a5404515a144bfd194c6b5d10254ec5`:

```text
python -m pytest -q tests/test_eye_follow_candidate_packaging.py tests/test_windows_eye_follow_candidate_workflow.py
8 passed, 1 skipped in 0.09s

python -m pytest -q tests/test_assets.py tests/test_main.py tests/test_neutral_eye_compositor.py
52 passed, 1 skipped in 4.07s

python -m pytest -q tests/test_animation.py tests/test_model.py tests/test_eye_follow.py tests/test_eye_runtime.py tests/test_repository_attributes.py tests/test_windows_source_validation_workflow.py
188 passed in 1.65s

python -m py_compile tools/verify_eye_follow_candidate_archive.py tests/test_eye_follow_candidate_packaging.py
(no output; exit 0)

git diff --check
(no output; exit 0)
```

### Self-review and concerns

- The two exact candidate output roots are still validated as repository
  children before cleanup.
- No `Remove-Item -Recurse` remains in the candidate script, so a nested
  junction is never handed to PowerShell recursive deletion.
- Only the candidate script, its contract tests, and this appended report were
  changed. Assets, R5, head/blink/tilt behavior, and the stable build are
  untouched.
- The real junction assertion cannot execute in this Linux checkout. It is
  explicitly Windows-only and is part of the hosted full pytest collection.
