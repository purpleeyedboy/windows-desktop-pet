# Task 1 Report: Immutable Canonical Contract

## RED

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_contract.py -q
```

Result: collection failed as expected with `ModuleNotFoundError: No module named 'tools.rig_center_contract'`.

## GREEN

Command (sandbox-external retry because pytest temporary-directory access returned WinError 5):

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_contract.py -q
```

Result: `3 passed in 0.33s`.

Canonical copy command:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.rig_center_contract import copy_canonical; print(copy_canonical(Path('assets/keyframes/jump/00.png'), Path('assets/rig/v1/source/canonical-idle.png')))"
```

Result: `{'sha256': '48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7', 'mode': 'RGBA', 'size': [512, 768]}`.

## Files

- `tools/rig_center_contract.py`
- `tests/test_rig_center_contract.py`
- `assets/rig/v1/source/canonical-idle.png`

The canonical PNG is a byte-preserving copy of `assets/keyframes/jump/00.png`.

## Self-review

- Contract fixes the 512x768 canvas and approved SHA-256.
- Validation rejects non-RGBA/wrong-size images, non-zero RGB under alpha zero, and visible outer borders.
- Copy creates parent directories, refuses a differing existing copy, and returns the requested metadata.
- No runtime code or unrelated assets were changed.

## Concerns

- Pytest cannot access the sandbox-managed temporary directory on this host; the focused GREEN run was repeated with the approved sandbox-external execution.
- Runtime/in-app rendering proof is outside Task 1 scope.
