# Portable Win32 Error Construction Report

## Verification

1. `python -m pytest tests/test_layered_window.py::test_partial_dib_creation_deletes_returned_bitmap -q`
   - RED: failed with `AttributeError: module 'ctypes' has no attribute 'WinError'`.
2. `python -m pytest tests/test_layered_window.py::test_partial_dib_creation_deletes_returned_bitmap -q`
   - GREEN: `1 passed in 0.04s`.
3. `python -m pytest tests/test_layered_window.py -q`
   - `3 passed, 2 skipped in 0.04s`.
4. `python -m pytest tests/test_main.py tests/test_layered_window.py -q`
   - `5 passed, 3 skipped in 0.08s`.
5. `git diff --check`
   - Passed with no output.

## Change

Added a portable Win32 error helper that delegates to native `ctypes.WinError` when available and otherwise returns an `OSError` carrying the numeric code. Existing Win32 failure paths in `layered_window.py` now use the helper, with a portable last-error lookup for non-Windows test runtimes.

## Independent Regression Review

1. Added `test_win32_error_without_native_winerror_carries_numeric_code` and `test_win32_error_delegates_to_native_winerror` before implementation review.
2. `python -m pytest tests/test_layered_window.py::test_win32_error_without_native_winerror_carries_numeric_code tests/test_layered_window.py::test_win32_error_delegates_to_native_winerror -q`
   - `2 passed in 0.05s`; the existing helper already satisfied both assertions, so no production-code adjustment was required.
3. `python -m pytest tests/test_layered_window.py -q`
   - `5 passed, 2 skipped in 0.05s`.
4. `python -m pytest tests/test_main.py tests/test_layered_window.py -q`
   - `7 passed, 3 skipped in 0.09s`.
