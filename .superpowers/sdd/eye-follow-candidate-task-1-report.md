# Task 1: Frozen-safe neutral-eye runtime loading

## Status

Completed. Implementation commit: `63a46f5e8b1f8b1ff47c30b990853f7b1070fe30`.

## RED

Added the runtime-root and compositor-resolution tests to `tests/test_assets.py`
before production edits, including the frozen-bundle case where the runtime
directory is absent. Ran:

```text
python -m pytest -q tests/test_assets.py
```

Result: `5 failed, 6 passed in 0.59s`.

The failures were the expected missing interfaces:

```text
AttributeError: module 'desktop_pet.assets' has no attribute 'neutral_eye_runtime_root'
AttributeError: module 'desktop_pet.assets' has no attribute 'load_neutral_eye_compositor'
AttributeError: module 'desktop_pet.assets' has no attribute 'sys'
```

## Implementation

- Added `neutral_eye_runtime_root()`, resolved through
  `asset_path("assets", "rig", "v1", "runtime", "eye-neutral-v1")`.
- Added `load_neutral_eye_compositor(root=None)`. Explicit roots go directly to
  `NeutralEyeCompositor.load`; otherwise it uses an existing runtime root,
  falls back to the source-checkout probe only outside PyInstaller, and keeps a
  frozen bundle on the runtime path even when that path is missing.
- Preserved `load_neutral_eye_source_probe` unchanged for compatibility.
- Switched application startup to `load_neutral_eye_compositor()`.
- Updated existing `main` startup tests to patch and assert the new loader;
  their original ordering, error routing, and cleanup coverage remains intact.

## Verification

```text
python -m pytest -q tests/test_assets.py tests/test_main.py tests/test_neutral_eye_compositor.py
52 passed, 1 skipped in 4.36s

python -m pytest -q tests/test_animation.py tests/test_eye_follow.py tests/test_eye_runtime.py tests/test_model.py tests/test_repository_attributes.py
187 passed in 2.21s

git diff --check
(no output; passed)
```

The broader non-Tk collection command also attempted to include
`tests/test_interpolate_action.py`, but is pre-existingly blocked during
collection because `tools.interpolate_action` is absent:

```text
ModuleNotFoundError: No module named 'tools.interpolate_action'
```

## Self-review

The resolver does not alter eye-follow math, motion limits, window behavior,
assets, head/blink/tilt behavior, packaging, or R5 status. In a frozen context
it never uses the source-checkout path, so a missing packaged runtime resource
fails transparently through `NeutralEyeCompositor.load`.

## Concerns

- Full non-Tk collection remains blocked by the unrelated missing
  `tools.interpolate_action` module noted above.
- R5 remains blocked pending the required real-Windows-EXE visual review.
